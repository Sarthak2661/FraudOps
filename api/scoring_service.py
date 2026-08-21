from __future__ import annotations

import sys
import uuid
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Engine, insert, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from api._support import json_list, now_utc, row_to_dict
from api.database import alerts, scored_transactions
from api.model_service import DEFAULT_FALLBACK_PROBABILITY, load_cost_config, load_model_bundle, load_rules_config
from api.schemas import ScoreResponse, ScoreTransactionRequest, TransactionResponse
from fraudops.decisioning import decide_transaction

FEATURE_PATH = PROJECT_ROOT / "data" / "curated" / "analytical_features" / "pipeline_run_id=phase3_full_002" / "features.parquet"


@lru_cache(maxsize=1)
def load_features() -> pd.DataFrame:
    if not FEATURE_PATH.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(FEATURE_PATH)
    frame["transaction_at"] = pd.to_datetime(frame["transaction_at"], utc=True)
    return frame


def feature_for_request(request: ScoreTransactionRequest) -> dict[str, Any]:
    features = load_features()
    if not features.empty:
        matched = features.loc[features["transaction_id"].eq(request.transaction_id)]
        if not matched.empty:
            row = matched.iloc[0].to_dict()
            row["transaction_amount"] = float(row.get("transaction_amount", request.amount))
            return row
    return {
        "transaction_id": request.transaction_id,
        "customer_id": request.customer_id,
        "account_id": request.account_id,
        "card_id": request.card_id,
        "device_id": request.device_id,
        "merchant_id": request.merchant_id,
        "transaction_at": request.transaction_at or now_utc(),
        "transaction_amount": request.amount,
        "amount": request.amount,
        "currency": request.currency,
        "channel": request.channel,
        "merchant_country": request.merchant_country,
        "is_new_device": False,
        "amount_to_customer_avg_ratio": 1.0,
        "transactions_last_1h": 0,
        "transactions_last_10m": 0,
        "failed_attempts_last_24h": 0,
        "is_international": False,
        "ip_country_mismatch": False,
        "distance_from_previous_transaction": 0,
        "time_since_previous_transaction": -1,
        "merchant_fraud_rate_30d": 0,
        "merchant_transaction_count_30d": 0,
        "device_fraud_rate_history": 0,
        "device_transaction_velocity": 0,
    }


def predict_probability(feature_row: dict[str, Any]) -> float:
    bundle = load_model_bundle()
    if not bundle:
        return DEFAULT_FALLBACK_PROBABILITY
    model = bundle["model"]
    columns = bundle["features"]
    frame = pd.DataFrame([{column: feature_row.get(column, 0) for column in columns}])
    return float(model.predict_proba(frame)[0, 1])


def priority_for(risk_score: float, amount: float) -> int:
    if risk_score >= 0.9 or amount >= 1000:
        return 5
    if risk_score >= 0.7:
        return 4
    if risk_score >= 0.5:
        return 3
    if risk_score >= 0.35:
        return 2
    return 1


def should_create_alert(decision: str, risk_score: float) -> bool:
    return decision in {"STEP_UP_AUTHENTICATION", "MANUAL_REVIEW", "HOLD_OR_DECLINE"} or risk_score >= 0.35


def score_transaction(engine: Engine, request: ScoreTransactionRequest, correlation_id: str) -> ScoreResponse:
    with engine.begin() as connection:
        existing = connection.execute(select(scored_transactions).where(scored_transactions.c.transaction_id == request.transaction_id)).first()
        if existing:
            row = row_to_dict(existing)
            return ScoreResponse(
                transaction_id=row["transaction_id"],
                risk_score=float(row["risk_score"]),
                decision=row["decision"],
                triggered_rules=json_list(row["triggered_rules"]),
                estimated_exposure=float(row["estimated_exposure"]),
                explanation=json_list(row["explanation"]),
                alert_id=row.get("alert_id"),
                idempotent_replay=True,
                correlation_id=correlation_id,
            )

        feature_row = feature_for_request(request)
        probability = predict_probability(feature_row)
        decision = decide_transaction(feature_row, probability, load_rules_config(), load_cost_config())
        amount = float(feature_row.get("transaction_amount", request.amount))
        alert_id = None
        if should_create_alert(decision["decision"], decision["risk_score"]):
            alert_id = f"ALT-{uuid.uuid4().hex[:12].upper()}"
            connection.execute(
                insert(alerts).values(
                    alert_id=alert_id,
                    transaction_id=request.transaction_id,
                    customer_id=request.customer_id or feature_row.get("customer_id"),
                    amount=amount,
                    risk_score=decision["risk_score"],
                    decision=decision["decision"],
                    priority=priority_for(decision["risk_score"], amount),
                    status="OPEN",
                    assigned_analyst=None,
                    sla_deadline=now_utc() + timedelta(hours=8),
                    triggered_rules=decision["triggered_rules"],
                )
            )
        connection.execute(
            insert(scored_transactions).values(
                transaction_id=request.transaction_id,
                customer_id=request.customer_id or feature_row.get("customer_id"),
                amount=amount,
                risk_score=decision["risk_score"],
                decision=decision["decision"],
                model_probability=probability,
                triggered_rules=decision["triggered_rules"],
                explanation=decision["explanation"],
                estimated_exposure=decision["estimated_exposure"],
                alert_id=alert_id,
                request_payload=request.model_dump(mode="json"),
            )
        )
        return ScoreResponse(
            transaction_id=request.transaction_id,
            risk_score=decision["risk_score"],
            decision=decision["decision"],
            triggered_rules=decision["triggered_rules"],
            estimated_exposure=decision["estimated_exposure"],
            explanation=decision["explanation"],
            alert_id=alert_id,
            correlation_id=correlation_id,
        )


def get_transaction(engine: Engine, transaction_id: str) -> TransactionResponse | None:
    with engine.begin() as connection:
        existing = connection.execute(select(scored_transactions).where(scored_transactions.c.transaction_id == transaction_id)).first()
    if existing:
        row = row_to_dict(existing)
        return TransactionResponse(
            transaction_id=row["transaction_id"],
            amount=float(row["amount"]),
            customer_id=row.get("customer_id"),
            decision=row["decision"],
            risk_score=float(row["risk_score"]),
            alert_id=row.get("alert_id"),
            scored_at=row["created_at"],
            source="api_score_store",
        )
    features = load_features()
    if not features.empty:
        matched = features.loc[features["transaction_id"].eq(transaction_id)]
        if not matched.empty:
            row = matched.iloc[0]
            return TransactionResponse(
                transaction_id=transaction_id,
                amount=float(row.get("transaction_amount", 0)),
                customer_id=str(row.get("customer_id")),
                source="curated_features",
            )
    return None
