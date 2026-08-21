from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fraudops.features import build_point_in_time_features


def test_customer_average_uses_only_prior_transactions() -> None:
    customers = pd.DataFrame(
        [
            {
                "customer_id": "cust-1",
                "home_country": "US",
                "home_city": "New York",
                "customer_segment": "mass",
                "risk_tier": "standard",
            }
        ]
    )
    devices = pd.DataFrame(
        [
            {
                "device_id": "dev-1",
                "first_seen_at": "2026-06-30T00:00:00Z",
                "trusted": True,
            }
        ]
    )
    merchants = pd.DataFrame(
        [
            {
                "merchant_id": "merch-1",
                "merchant_category_code": "5411",
                "merchant_category": "Grocery",
                "risk_tier": "standard",
            }
        ]
    )
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
                "amount": 100.0,
                "currency": "USD",
                "merchant_country": "US",
                "merchant_city": "New York",
                "channel": "card_present",
                "status": "AUTHORIZED",
                "fraud_label": "unknown",
                "fraud_scenario": "",
            },
            {
                "transaction_id": "txn-2",
                "transaction_external_id": "TXN-2",
                "customer_id": "cust-1",
                "account_id": "acct-1",
                "card_id": "card-1",
                "device_id": "dev-1",
                "merchant_id": "merch-1",
                "transaction_at": "2026-07-01T11:00:00Z",
                "amount": 300.0,
                "currency": "USD",
                "merchant_country": "US",
                "merchant_city": "New York",
                "channel": "card_present",
                "status": "AUTHORIZED",
                "fraud_label": "unknown",
                "fraud_scenario": "",
            },
            {
                "transaction_id": "txn-3",
                "transaction_external_id": "TXN-3",
                "customer_id": "cust-1",
                "account_id": "acct-1",
                "card_id": "card-1",
                "device_id": "dev-1",
                "merchant_id": "merch-1",
                "transaction_at": "2026-07-01T12:00:00Z",
                "amount": 10000.0,
                "currency": "USD",
                "merchant_country": "US",
                "merchant_city": "New York",
                "channel": "card_present",
                "status": "AUTHORIZED",
                "fraud_label": "unknown",
                "fraud_scenario": "",
            },
        ]
    )

    features = build_point_in_time_features(
        transactions=transactions,
        customers=customers,
        devices=devices,
        merchants=merchants,
        pipeline_run_id="test-run",
    )

    second = features.loc[features["transaction_id"].eq("txn-2")].iloc[0]
    assert second["customer_avg_amount_7d"] == 100.0
    assert second["transactions_last_1h"] == 1
    assert second["amount_to_customer_avg_ratio"] == 3.0

    third = features.loc[features["transaction_id"].eq("txn-3")].iloc[0]
    assert third["customer_avg_amount_7d"] == 200.0
    assert third["amount_to_customer_avg_ratio"] == 50.0
