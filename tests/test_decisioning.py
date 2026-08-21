from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fraudops.decisioning import (
    choose_lowest_cost_decision,
    decide_transaction,
    evaluate_rules,
    expected_decision_costs,
    fallback_model_probability,
)


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


def test_rule_evaluation_applies_override_and_skips_inactive_rules() -> None:
    rules = {
        "rules": [
            {
                "rule_id": "R009",
                "name": "known_compromised_device",
                "conditions": [{"feature": "device_fraud_rate_history", "operator": "greater_than", "value": 0.15}],
                "risk_points": 40,
                "decision_override": "HOLD_OR_DECLINE",
                "severity": "critical",
                "active": True,
            },
            {
                "rule_id": "R_OFF",
                "name": "disabled",
                "conditions": [{"feature": "amount", "operator": "greater_than", "value": 1}],
                "risk_points": 100,
                "decision_override": "HOLD_OR_DECLINE",
                "severity": "critical",
                "active": False,
            },
        ]
    }

    triggered = evaluate_rules({"device_fraud_rate_history": 0.22, "amount": 500}, rules)

    assert [rule.rule_id for rule in triggered] == ["R009"]
    assert triggered[0].decision_override == "HOLD_OR_DECLINE"


def test_cost_sensitive_decision_uses_thresholds_and_costs() -> None:
    costs = {
        "average_fraud_loss": 1000.0,
        "average_manual_review_cost": 8.5,
        "average_step_up_cost": 1.25,
        "legitimate_decline_cost": 45.0,
        "customer_friction_cost": 5.0,
        "step_up_threshold": 0.35,
        "hold_threshold": 0.90,
    }

    decision_costs = expected_decision_costs(0.6, 920.0, costs)

    assert decision_costs["APPROVE"] == 600.0
    assert choose_lowest_cost_decision(decision_costs, risk_score=0.95, cost_config=costs) == "HOLD_OR_DECLINE"
    assert choose_lowest_cost_decision(decision_costs, risk_score=0.10, cost_config=costs) == "APPROVE"


def test_fallback_model_probability_is_clamped_and_testable() -> None:
    assert fallback_model_probability({"merchant_fraud_rate_30d": 0.0, "amount_to_customer_avg_ratio": 1.0}) == 0.01
    assert fallback_model_probability({"merchant_fraud_rate_30d": 10.0, "amount_to_customer_avg_ratio": 9.0}) == 0.99
