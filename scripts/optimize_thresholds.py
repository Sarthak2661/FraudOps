from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPARISON_PATH = PROJECT_ROOT / "reports" / "modeling" / "model_comparison_validation.csv"
OUTPUT_PATH = PROJECT_ROOT / "reports" / "modeling" / "threshold_recommendation.json"


def main() -> None:
    if not COMPARISON_PATH.exists():
        raise FileNotFoundError(f"Run model training first: {COMPARISON_PATH}")
    comparison = pd.read_csv(COMPARISON_PATH)
    if comparison.empty:
        raise ValueError("Model comparison file is empty")
    sort_columns = [column for column in ["expected_financial_cost", "validation_expected_financial_cost"] if column in comparison.columns]
    if sort_columns:
        selected = comparison.sort_values(sort_columns[0], ascending=True).iloc[0]
    elif "pr_auc" in comparison.columns:
        selected = comparison.sort_values("pr_auc", ascending=False).iloc[0]
    else:
        selected = comparison.iloc[0]
    threshold = float(selected.get("threshold", selected.get("validation_threshold", 0.5)))
    recommendation = {
        "model_name": selected.get("model_name", selected.get("model", "unknown")),
        "recommended_threshold": threshold,
        "analyst_daily_capacity": 500,
        "selection_basis": "lowest validation expected financial cost when available; otherwise best PR-AUC",
        "source_file": str(COMPARISON_PATH),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(recommendation, indent=2), encoding="utf-8")
    print(json.dumps(recommendation, indent=2))


if __name__ == "__main__":
    main()
