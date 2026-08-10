from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fraudops.paths import default_feature_path

DECISIONS = {"APPROVE", "STEP_UP_AUTHENTICATION", "MANUAL_REVIEW", "HOLD_OR_DECLINE"}


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    name: str
    risk_points: float
    decision_override: str | None
    severity: str
    explanation: str


OPERATORS = {
    "equals": lambda actual, expected: actual == expected,
    "not_equals": lambda actual, expected: actual != expected,
    "greater_than": lambda actual, expected: actual is not None and actual > expected,
    "greater_than_or_equal": lambda actual, expected: actual is not None and actual >= expected,
    "less_than": lambda actual, expected: actual is not None and actual < expected,
    "less_than_or_equal": lambda actual, expected: actual is not None and actual <= expected,
    "in": lambda actual, expected: actual in expected,
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _normalize_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def evaluate_rule(rule: dict[str, Any], transaction: dict[str, Any]) -> RuleResult | None:
    if not rule.get("active", True):
        return None
    for condition in rule.get("conditions", []):
        operator = condition["operator"]
        if operator not in OPERATORS:
            raise ValueError(f"Unsupported rule operator: {operator}")
        actual = _normalize_value(transaction.get(condition["feature"]))
        expected = condition.get("value")
        if not OPERATORS[operator](actual, expected):
            return None
    override = rule.get("decision_override")
    if override is not None and override not in DECISIONS:
        raise ValueError(f"Invalid decision override for {rule['rule_id']}: {override}")
    return RuleResult(
        rule_id=rule["rule_id"],
        name=rule["name"],
        risk_points=float(rule.get("risk_points", 0)),
        decision_override=override,
        severity=rule.get("severity", "medium"),
        explanation=rule.get("explanation", rule.get("description", rule["name"])),
    )


def evaluate_rules(transaction: dict[str, Any], rules_config: dict[str, Any]) -> list[RuleResult]:
    return [result for rule in rules_config.get("rules", []) if (result := evaluate_rule(rule, transaction)) is not None]


def normalized_rule_score(triggered_rules: list[RuleResult]) -> float:
    raw_points = sum(rule.risk_points for rule in triggered_rules)
    return max(0.0, min(1.0, raw_points / 100.0))


def combine_scores(model_probability: float, rule_score: float, cost_config: dict[str, Any]) -> float:
    model_weight = float(cost_config.get("model_weight", 0.70))
    rule_weight = float(cost_config.get("rule_weight", 0.30))
    return max(0.0, min(1.0, model_weight * model_probability + rule_weight * rule_score))


def expected_decision_costs(probability: float, amount: float, cost_config: dict[str, Any]) -> dict[str, float]:
    fraud_loss = max(float(cost_config.get("average_fraud_loss", 250.0)), amount)
    manual_review_cost = float(cost_config.get("average_manual_review_cost", 8.50))
    step_up_cost = float(cost_config.get("average_step_up_cost", 1.25))
    legitimate_decline_cost = float(cost_config.get("legitimate_decline_cost", 45.0))
    friction_cost = float(cost_config.get("customer_friction_cost", 5.0))

    return {
        "APPROVE": probability * fraud_loss,
        "STEP_UP_AUTHENTICATION": step_up_cost + friction_cost + probability * fraud_loss * 0.25,
        "MANUAL_REVIEW": manual_review_cost + probability * fraud_loss * 0.10,
        "HOLD_OR_DECLINE": (1 - probability) * legitimate_decline_cost + friction_cost,
    }


def choose_lowest_cost_decision(costs: dict[str, float], risk_score: float, cost_config: dict[str, Any]) -> str:
    if risk_score >= float(cost_config.get("hold_threshold", 0.90)):
        return "HOLD_OR_DECLINE"
    if risk_score < float(cost_config.get("step_up_threshold", 0.35)):
        return "APPROVE"
    return min(costs, key=costs.get)


def apply_overrides(decision: str, triggered_rules: list[RuleResult]) -> str:
    priority = ["APPROVE", "STEP_UP_AUTHENTICATION", "MANUAL_REVIEW", "HOLD_OR_DECLINE"]
    chosen = decision
    for rule in triggered_rules:
        if rule.decision_override and priority.index(rule.decision_override) > priority.index(chosen):
            chosen = rule.decision_override
    return chosen


def decide_transaction(
    transaction: dict[str, Any],
    model_probability: float,
    rules_config: dict[str, Any],
    cost_config: dict[str, Any],
) -> dict[str, Any]:
    triggered = evaluate_rules(transaction, rules_config)
    rule_score = normalized_rule_score(triggered)
    risk_score = combine_scores(model_probability, rule_score, cost_config)
    amount = float(transaction.get("transaction_amount", transaction.get("amount", 0.0)) or 0.0)
    costs = expected_decision_costs(risk_score, amount, cost_config)
    decision = choose_lowest_cost_decision(costs, risk_score, cost_config)
    decision = apply_overrides(decision, triggered)
    estimated_exposure = round(risk_score * max(amount, float(cost_config.get("average_fraud_loss", 250.0))), 2)

    return {
        "transaction_id": transaction.get("transaction_id"),
        "risk_score": round(risk_score, 4),
        "decision": decision,
        "triggered_rules": [rule.rule_id for rule in triggered],
        "rule_score": round(rule_score, 4),
        "model_probability": round(float(model_probability), 4),
        "estimated_exposure": estimated_exposure,
        "expected_costs": {key: round(value, 2) for key, value in costs.items()},
        "explanation": [rule.explanation for rule in triggered],
    }


def apply_analyst_capacity(decisions: pd.DataFrame, analyst_daily_capacity: int) -> pd.DataFrame:
    frame = decisions.copy()
    manual_mask = frame["decision"].eq("MANUAL_REVIEW")
    frame["review_priority_score"] = (
        frame["risk_score"].astype(float)
        * frame.get("transaction_amount", 0).astype(float).clip(lower=1)
        * frame.get("estimated_exposure", 0).astype(float).clip(lower=1)
    )
    manual = frame.loc[manual_mask].sort_values("review_priority_score", ascending=False)
    overflow = manual.iloc[analyst_daily_capacity:].index
    frame.loc[overflow, "decision"] = "STEP_UP_AUTHENTICATION"
    frame.loc[overflow, "capacity_adjusted"] = True
    frame["capacity_adjusted"] = frame.get("capacity_adjusted", False).fillna(False)
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FraudOps rules and cost-sensitive decision engine.")
    parser.add_argument("--features", type=Path, default=default_feature_path())
    parser.add_argument("--rules", type=Path, default=Path("configs/rules.yaml"))
    parser.add_argument("--cost-config", type=Path, default=Path("configs/cost_config.yaml"))
    parser.add_argument("--model-probability", type=float, default=None)
    parser.add_argument("--transaction-id", default=None)
    parser.add_argument("--output", type=Path, default=Path("reports/decisioning/sample_decision.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rules_config = load_yaml(args.rules)
    cost_config = load_yaml(args.cost_config)
    features = pd.read_parquet(args.features).sort_values("transaction_at")
    row = features.iloc[-1] if args.transaction_id is None else features.loc[features["transaction_id"].eq(args.transaction_id)].iloc[0]
    probability = args.model_probability
    if probability is None:
        probability = float(row.get("merchant_fraud_rate_30d", 0.0)) * 0.4 + float(row.get("amount_to_customer_avg_ratio", 1.0) > 5) * 0.4
        probability = max(0.01, min(0.99, probability))
    result = decide_transaction(row.to_dict(), probability, rules_config, cost_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
