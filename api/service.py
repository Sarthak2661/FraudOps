from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sqlalchemy import Engine, Select, insert, select, update

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fraudops.decisioning import decide_transaction, load_yaml
from api.database import alerts, case_actions, cases, scored_transactions
from api.schemas import (
    AlertResponse,
    CaseActionRequest,
    CaseActionResponse,
    CaseCreateRequest,
    CasePatchRequest,
    CaseResolveRequest,
    CaseResponse,
    ModelCurrentResponse,
    RuleResponse,
    ScoreResponse,
    ScoreTransactionRequest,
    TransactionResponse,
)

FEATURE_PATH = PROJECT_ROOT / "data" / "curated" / "analytical_features" / "pipeline_run_id=phase3_full_002" / "features.parquet"
MODEL_PATH = PROJECT_ROOT / "reports" / "modeling" / "selected_model.joblib"
FINAL_METRICS_PATH = PROJECT_ROOT / "reports" / "modeling" / "selected_model_final_test_metrics.json"
RULES_PATH = PROJECT_ROOT / "configs" / "rules.yaml"
COST_CONFIG_PATH = PROJECT_ROOT / "configs" / "cost_config.yaml"


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


@lru_cache(maxsize=1)
def load_features() -> pd.DataFrame:
    if not FEATURE_PATH.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(FEATURE_PATH)
    frame["transaction_at"] = pd.to_datetime(frame["transaction_at"], utc=True)
    return frame


@lru_cache(maxsize=1)
def load_model_bundle() -> dict[str, Any] | None:
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def load_rules_config() -> dict[str, Any]:
    return load_yaml(RULES_PATH)


@lru_cache(maxsize=1)
def load_cost_config() -> dict[str, Any]:
    return load_yaml(COST_CONFIG_PATH)


def _row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return data


def _json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return list(value)


def _feature_for_request(request: ScoreTransactionRequest) -> dict[str, Any]:
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


def predict_probability(feature_row: dict[str, Any], override: float | None = None) -> float:
    if override is not None:
        return float(override)
    bundle = load_model_bundle()
    if not bundle:
        return 0.01
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


def _alert_response(row: dict[str, Any]) -> AlertResponse:
    created_at = row["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    age = max(0, int((now_utc() - created_at.replace(tzinfo=UTC)).total_seconds() // 60)) if created_at.tzinfo is None else max(0, int((now_utc() - created_at).total_seconds() // 60))
    return AlertResponse(
        alert_id=row["alert_id"],
        transaction_id=row["transaction_id"],
        risk_score=float(row["risk_score"]),
        amount=float(row["amount"]),
        priority=int(row["priority"]),
        customer_id=row.get("customer_id"),
        decision=row["decision"],
        alert_age_minutes=age,
        status=row["status"],
        assigned_analyst=row.get("assigned_analyst"),
        sla_deadline=row["sla_deadline"],
        triggered_rules=_json_list(row.get("triggered_rules")),
    )


def score_transaction(engine: Engine, request: ScoreTransactionRequest, correlation_id: str) -> ScoreResponse:
    with engine.begin() as connection:
        existing = connection.execute(select(scored_transactions).where(scored_transactions.c.transaction_id == request.transaction_id)).first()
        if existing:
            row = _row_to_dict(existing)
            return ScoreResponse(
                transaction_id=row["transaction_id"],
                risk_score=float(row["risk_score"]),
                decision=row["decision"],
                triggered_rules=_json_list(row["triggered_rules"]),
                estimated_exposure=float(row["estimated_exposure"]),
                explanation=_json_list(row["explanation"]),
                alert_id=row.get("alert_id"),
                idempotent_replay=True,
                correlation_id=correlation_id,
            )

        feature_row = _feature_for_request(request)
        probability = predict_probability(feature_row, request.model_probability_override)
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
        row = _row_to_dict(existing)
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


def list_alerts(engine: Engine, status: str | None = None) -> list[AlertResponse]:
    query: Select[Any] = select(alerts).order_by(alerts.c.created_at.desc())
    if status:
        query = query.where(alerts.c.status == status)
    with engine.begin() as connection:
        rows = [_row_to_dict(row) for row in connection.execute(query).all()]
    return [_alert_response(row) for row in rows]


def get_alert(engine: Engine, alert_id: str) -> AlertResponse | None:
    with engine.begin() as connection:
        row = connection.execute(select(alerts).where(alerts.c.alert_id == alert_id)).first()
    return _alert_response(_row_to_dict(row)) if row else None


def _case_response(engine: Engine, row: dict[str, Any]) -> CaseResponse:
    with engine.begin() as connection:
        action_rows = [_row_to_dict(item) for item in connection.execute(select(case_actions).where(case_actions.c.case_id == row["case_id"]).order_by(case_actions.c.created_at)).all()]
    return CaseResponse(
        case_id=row["case_id"],
        customer_id=row.get("customer_id"),
        alert_ids=_json_list(row.get("alert_ids")),
        status=row["status"],
        priority=int(row["priority"]),
        assigned_to=row.get("assigned_to"),
        case_summary=row["case_summary"],
        outcome=row.get("outcome"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        actions=[CaseActionResponse(action_id=item["action_id"], case_id=item["case_id"], actor=item["actor"], action_type=item["action_type"], notes=item["notes"], created_at=item["created_at"]) for item in action_rows],
    )


def create_case(engine: Engine, request: CaseCreateRequest) -> CaseResponse:
    case_id = f"CASE-{uuid.uuid4().hex[:12].upper()}"
    timestamp = now_utc()
    with engine.begin() as connection:
        connection.execute(
            insert(cases).values(
                case_id=case_id,
                customer_id=request.customer_id,
                alert_ids=request.alert_ids,
                status="OPEN",
                priority=request.priority,
                assigned_to=request.assigned_to,
                case_summary=request.case_summary,
                outcome=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        row = _row_to_dict(connection.execute(select(cases).where(cases.c.case_id == case_id)).first())
    return _case_response(engine, row)


def get_case(engine: Engine, case_id: str) -> CaseResponse | None:
    with engine.begin() as connection:
        row = connection.execute(select(cases).where(cases.c.case_id == case_id)).first()
    return _case_response(engine, _row_to_dict(row)) if row else None


def patch_case(engine: Engine, case_id: str, request: CasePatchRequest) -> CaseResponse | None:
    values = {key: value for key, value in request.model_dump(exclude_unset=True).items() if value is not None}
    values["updated_at"] = now_utc()
    with engine.begin() as connection:
        existing = connection.execute(select(cases).where(cases.c.case_id == case_id)).first()
        if not existing:
            return None
        connection.execute(update(cases).where(cases.c.case_id == case_id).values(**values))
        row = _row_to_dict(connection.execute(select(cases).where(cases.c.case_id == case_id)).first())
    return _case_response(engine, row)


def add_case_action(engine: Engine, case_id: str, request: CaseActionRequest) -> CaseActionResponse | None:
    action_id = f"ACT-{uuid.uuid4().hex[:12].upper()}"
    timestamp = now_utc()
    with engine.begin() as connection:
        existing = connection.execute(select(cases).where(cases.c.case_id == case_id)).first()
        if not existing:
            return None
        connection.execute(insert(case_actions).values(action_id=action_id, case_id=case_id, actor=request.actor, action_type=request.action_type, notes=request.notes, created_at=timestamp))
        connection.execute(update(cases).where(cases.c.case_id == case_id).values(updated_at=timestamp))
    return CaseActionResponse(action_id=action_id, case_id=case_id, actor=request.actor, action_type=request.action_type, notes=request.notes, created_at=timestamp)


def resolve_case(engine: Engine, case_id: str, request: CaseResolveRequest) -> CaseResponse | None:
    action = add_case_action(engine, case_id, CaseActionRequest(actor=request.actor, action_type=f"RESOLVE_{request.outcome}", notes=request.notes))
    if not action:
        return None
    with engine.begin() as connection:
        connection.execute(update(cases).where(cases.c.case_id == case_id).values(status="CLOSED", outcome=request.outcome, updated_at=now_utc()))
        row = _row_to_dict(connection.execute(select(cases).where(cases.c.case_id == case_id)).first())
    return _case_response(engine, row)


def current_model() -> ModelCurrentResponse:
    bundle = load_model_bundle()
    metrics = json.loads(FINAL_METRICS_PATH.read_text(encoding="utf-8")) if FINAL_METRICS_PATH.exists() else {}
    return ModelCurrentResponse(
        model_name="random_forest_balanced" if bundle else "unavailable",
        threshold=float(bundle.get("threshold")) if bundle else None,
        feature_count=len(bundle.get("features", [])) if bundle else 0,
        artifact_path=str(MODEL_PATH) if MODEL_PATH.exists() else None,
        metrics=metrics,
    )


def rules() -> list[RuleResponse]:
    return [
        RuleResponse(
            rule_id=item["rule_id"],
            name=item["name"],
            description=item.get("description", ""),
            severity=item.get("severity", "medium"),
            active=bool(item.get("active", True)),
            risk_points=float(item.get("risk_points", 0)),
            decision_override=item.get("decision_override"),
        )
        for item in load_rules_config().get("rules", [])
    ]
