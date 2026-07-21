from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Iterable

import pandas as pd

REQUIRED_TRANSACTION_FIELDS = [
    "transaction_id",
    "transaction_external_id",
    "customer_id",
    "account_id",
    "card_id",
    "device_id",
    "merchant_id",
    "transaction_at",
    "amount",
    "currency",
    "merchant_country",
    "merchant_city",
    "channel",
    "status",
    "fraud_label",
]
ALLOWED_CURRENCIES = {"USD", "CAD", "GBP", "EUR", "BRL", "JPY", "SGD"}
ALLOWED_CHANNELS = {"card_present", "card_not_present", "mobile_wallet", "atm"}
ALLOWED_STATUSES = {"AUTHORIZED", "DECLINED", "REVERSED", "SETTLED"}
ALLOWED_LABELS = {"unknown", "legitimate", "fraud"}


def _append_reason(reasons: pd.Series, mask: pd.Series, reason: str) -> pd.Series:
    reasons = reasons.copy()
    reasons.loc[mask.fillna(True)] = reasons.loc[mask.fillna(True)].apply(lambda items: [*items, reason])
    return reasons


def _json_record(row: pd.Series) -> str:
    clean = {}
    for key, value in row.items():
        if pd.isna(value):
            clean[key] = None
        elif isinstance(value, pd.Timestamp):
            clean[key] = value.isoformat()
        else:
            clean[key] = value
    return json.dumps(clean, default=str, sort_keys=True)


def validate_transactions(
    transactions: pd.DataFrame,
    customers: pd.DataFrame,
    accounts: pd.DataFrame,
    cards: pd.DataFrame,
    devices: pd.DataFrame,
    merchants: pd.DataFrame,
    pipeline_run_id: str,
    source_file: str,
    max_age_days: int = 730,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate transaction rows and return accepted rows, rejected rows, and quality results."""
    frame = transactions.copy()
    rejected_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    missing_columns = [column for column in REQUIRED_TRANSACTION_FIELDS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    reasons = pd.Series([[] for _ in range(len(frame))], index=frame.index, dtype=object)
    for column in REQUIRED_TRANSACTION_FIELDS:
        reasons = _append_reason(reasons, frame[column].astype(str).str.strip().eq(""), f"missing_{column}")

    parsed_amount = pd.to_numeric(frame["amount"], errors="coerce")
    parsed_time = pd.to_datetime(frame["transaction_at"], utc=True, errors="coerce")
    now = pd.Timestamp.now(tz="UTC")
    min_allowed_time = now - pd.Timedelta(days=max_age_days)

    reasons = _append_reason(reasons, parsed_amount.isna(), "invalid_amount_type")
    reasons = _append_reason(reasons, parsed_amount <= 0, "amount_not_positive")
    reasons = _append_reason(reasons, parsed_time.isna(), "invalid_transaction_timestamp")
    reasons = _append_reason(reasons, parsed_time > now + pd.Timedelta(days=1), "transaction_timestamp_in_future")
    reasons = _append_reason(reasons, parsed_time < min_allowed_time, "transaction_timestamp_too_old")
    reasons = _append_reason(reasons, ~frame["currency"].isin(ALLOWED_CURRENCIES), "invalid_currency")
    reasons = _append_reason(reasons, ~frame["channel"].isin(ALLOWED_CHANNELS), "invalid_channel")
    reasons = _append_reason(reasons, ~frame["status"].isin(ALLOWED_STATUSES), "invalid_transaction_status")
    reasons = _append_reason(reasons, ~frame["fraud_label"].isin(ALLOWED_LABELS), "invalid_fraud_label")

    duplicate_mask = frame["transaction_id"].duplicated(keep="first") | frame["transaction_external_id"].duplicated(keep="first")
    reasons = _append_reason(reasons, duplicate_mask, "duplicate_transaction_id")

    customer_ids = set(customers["customer_id"].astype(str))
    account_ids = set(accounts["account_id"].astype(str))
    card_ids = set(cards["card_id"].astype(str))
    device_ids = set(devices["device_id"].astype(str))
    merchant_ids = set(merchants["merchant_id"].astype(str))
    card_account = dict(zip(cards["card_id"].astype(str), cards["account_id"].astype(str), strict=False))

    reasons = _append_reason(reasons, ~frame["customer_id"].astype(str).isin(customer_ids), "customer_not_found")
    reasons = _append_reason(reasons, ~frame["account_id"].astype(str).isin(account_ids), "account_not_found")
    reasons = _append_reason(reasons, ~frame["card_id"].astype(str).isin(card_ids), "card_not_found")
    reasons = _append_reason(reasons, ~frame["device_id"].astype(str).isin(device_ids), "device_not_found")
    reasons = _append_reason(reasons, ~frame["merchant_id"].astype(str).isin(merchant_ids), "merchant_not_found")

    expected_account = frame["card_id"].astype(str).map(card_account)
    reasons = _append_reason(
        reasons,
        expected_account.notna() & expected_account.ne(frame["account_id"].astype(str)),
        "card_account_mismatch",
    )

    accepted_mask = reasons.apply(len).eq(0)
    accepted = frame.loc[accepted_mask].copy()
    accepted["amount"] = parsed_amount.loc[accepted_mask].round(2)
    accepted["transaction_at"] = parsed_time.loc[accepted_mask]
    accepted["pipeline_run_id"] = pipeline_run_id
    accepted["source_file"] = source_file
    accepted["validated_at"] = rejected_at

    rejected_source = frame.loc[~accepted_mask].copy()
    rejected = pd.DataFrame(
        {
            "pipeline_run_id": pipeline_run_id,
            "source_file": source_file,
            "rejected_at": rejected_at,
            "rejection_reason": reasons.loc[~accepted_mask].apply(lambda values: ";".join(values)),
            "record": rejected_source.apply(_json_record, axis=1),
        }
    )

    quality_results = build_quality_results(
        pipeline_run_id=pipeline_run_id,
        total_records=len(frame),
        accepted_records=len(accepted),
        rejected_records=len(rejected),
        duplicate_records=int(duplicate_mask.sum()),
        reasons=reasons,
    )
    return accepted.reset_index(drop=True), rejected.reset_index(drop=True), quality_results


def build_quality_results(
    pipeline_run_id: str,
    total_records: int,
    accepted_records: int,
    rejected_records: int,
    duplicate_records: int,
    reasons: pd.Series,
) -> pd.DataFrame:
    checks = [
        ("completeness_required_fields", "Completeness", "Required transaction fields are populated", "missing_"),
        ("validity_positive_amount", "Validity", "Transaction amount is greater than zero", "amount_not_positive"),
        ("validity_currency", "Validity", "Currency is in the allowed code list", "invalid_currency"),
        ("validity_timestamp", "Validity", "Transaction timestamp is parseable and timely", "transaction_timestamp"),
        ("uniqueness_transaction_id", "Uniqueness", "Transaction identifiers are unique", "duplicate_transaction_id"),
        ("referential_customer", "Referential integrity", "Customer exists", "customer_not_found"),
        ("referential_card", "Referential integrity", "Card exists", "card_not_found"),
        ("referential_merchant", "Referential integrity", "Merchant exists", "merchant_not_found"),
        ("consistency_card_account", "Consistency", "Card belongs to the transaction account", "card_account_mismatch"),
    ]
    rows = []
    for rule_code, dimension, description, token in checks:
        failed = int(reasons.apply(lambda values: any(token in value for value in values)).sum())
        rows.append(
            {
                "pipeline_run_id": pipeline_run_id,
                "rule_code": rule_code,
                "dimension": dimension,
                "description": description,
                "total_records": total_records,
                "failed_records": failed,
                "passed": failed == 0,
            }
        )
    rows.append(
        {
            "pipeline_run_id": pipeline_run_id,
            "rule_code": "pipeline_summary",
            "dimension": "Audit",
            "description": "Input, accepted, rejected, and duplicate record counts",
            "total_records": total_records,
            "failed_records": rejected_records,
            "passed": rejected_records == 0,
            "accepted_records": accepted_records,
            "duplicate_records": duplicate_records,
        }
    )
    return pd.DataFrame(rows)
