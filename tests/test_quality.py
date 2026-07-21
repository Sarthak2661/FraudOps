from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fraudops.quality import validate_transactions


def test_validate_transactions_quarantines_bad_records() -> None:
    customers = pd.DataFrame([{"customer_id": "cust-1"}])
    accounts = pd.DataFrame([{"account_id": "acct-1"}])
    cards = pd.DataFrame([{"card_id": "card-1", "account_id": "acct-1"}])
    devices = pd.DataFrame([{"device_id": "dev-1"}])
    merchants = pd.DataFrame([{"merchant_id": "merch-1"}])
    transactions = pd.DataFrame(
        [
            {
                "transaction_id": "txn-1",
                "transaction_external_id": "TXN-1",
                "customer_id": "cust-1",
                "account_id": "acct-1",
                "card_id": "card-1",
                "device_id": "dev-1",
                "merchant_id": "merch-1",
                "transaction_at": "2026-07-01T10:00:00Z",
                "amount": "25.00",
                "currency": "USD",
                "merchant_country": "US",
                "merchant_city": "New York",
                "channel": "card_present",
                "status": "AUTHORIZED",
                "fraud_label": "unknown",
            },
            {
                "transaction_id": "txn-2",
                "transaction_external_id": "TXN-2",
                "customer_id": "missing-customer",
                "account_id": "acct-1",
                "card_id": "card-1",
                "device_id": "dev-1",
                "merchant_id": "merch-1",
                "transaction_at": "2026-07-01T10:05:00Z",
                "amount": "-3.00",
                "currency": "NOT_A_CURRENCY",
                "merchant_country": "US",
                "merchant_city": "New York",
                "channel": "bad_channel",
                "status": "AUTHORIZED",
                "fraud_label": "unknown",
            },
        ]
    )

    accepted, rejected, quality = validate_transactions(
        transactions=transactions,
        customers=customers,
        accounts=accounts,
        cards=cards,
        devices=devices,
        merchants=merchants,
        pipeline_run_id="test-run",
        source_file="unit-test",
    )

    assert len(accepted) == 1
    assert len(rejected) == 1
    reason = rejected.loc[0, "rejection_reason"]
    assert "amount_not_positive" in reason
    assert "invalid_currency" in reason
    assert "invalid_channel" in reason
    assert "customer_not_found" in reason
    assert quality.loc[quality["rule_code"].eq("validity_positive_amount"), "failed_records"].iloc[0] == 1
