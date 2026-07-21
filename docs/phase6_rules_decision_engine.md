# Phase 6: Rules and Decision Engine

## Objective

Convert fraud probabilities and rules into operational banking decisions.

## Files

- `configs/rules.yaml`: configurable fraud rules
- `configs/cost_config.yaml`: financial and capacity settings
- `src/fraudops/decisioning.py`: rule evaluation, score blending, expected-cost decisions, and capacity adjustment
- `scripts/run_decision_engine.py`: command-line decision runner

## Implemented Rules

- Reported stolen card placeholder
- Excessive transaction velocity
- New device plus high amount
- Country mismatch
- Impossible travel
- High-risk merchant
- Repeated failed attempts
- Trusted device and normal behaviour
- Recent profile change plus unusual payment
- Known compromised device

## Score Combination

The engine combines model probability and normalized rule score using configurable weights:

```text
final_risk_score = model_weight * model_probability + rule_weight * normalized_rule_score
```

Current defaults:

```text
model_weight = 0.70
rule_weight = 0.30
```

Treat these weights as experimental.

## Cost-Sensitive Decisions

The engine estimates costs for:

- APPROVE
- STEP_UP_AUTHENTICATION
- MANUAL_REVIEW
- HOLD_OR_DECLINE

It selects the lowest-cost action, then applies mandatory rule overrides.

## Analyst Capacity

`apply_analyst_capacity` caps manual-review decisions using `analyst_daily_capacity` and reprioritizes by risk, exposure, and transaction amount.

## Example

```powershell
python scripts/run_decision_engine.py --model-probability 0.82 --output reports/decisioning/sample_decision.json
```

Response shape:

```json
{
  "risk_score": 0.598,
  "decision": "HOLD_OR_DECLINE",
  "triggered_rules": ["R005", "R007"],
  "estimated_exposure": 149.5,
  "explanation": ["High-risk merchant history", "Trusted device and normal behaviour"]
}
```
