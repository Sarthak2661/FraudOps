from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fraudops.decisioning import decide_transaction


def test_decision_engine_returns_operational_response() -> None:
    rules = {
        "rules": [
            {
                "rule_id": "R001",
                "name": "high_value_new_device",
                "conditions": [
                    {"feature": "is_new_device", "operator": "equals", "value": True},
                    {"feature": "amount_to_customer_avg_ratio", "operator": "greater_than", "value": 5},
                ],
                "risk_points": 30,
                "decision_override": None,
                "severity": "high",
                "active": True,
                "explanation": "New device with high spend",
            }
        ]
    }
    costs = {
        "average_manual_review_cost": 8.5,
        "average_step_up_cost": 1.25,
        "legitimate_decline_cost": 45.0,
        "average_fraud_loss": 250.0,
        "customer_friction_cost": 5.0,
        "analyst_daily_capacity": 500,
        "model_weight": 0.70,
        "rule_weight": 0.30,
    }
    transaction = {
        "transaction_id": "txn-1",
        "transaction_amount": 920.0,
        "is_new_device": True,
        "amount_to_customer_avg_ratio": 6.2,
    }

    result = decide_transaction(transaction, 0.84, rules, costs)

    assert result["risk_score"] == 0.678
    assert result["triggered_rules"] == ["R001"]
    assert result["estimated_exposure"] == 623.76
    assert result["decision"] in {"APPROVE", "STEP_UP_AUTHENTICATION", "MANUAL_REVIEW", "HOLD_OR_DECLINE"}
    assert result["explanation"] == ["New device with high spend"]
