from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FEATURES = {
    "transaction_id",
    "transaction_at",
    "transaction_amount",
    "customer_avg_amount_7d",
    "transactions_last_1h",
    "amount_to_customer_avg_ratio",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a FraudOps feature snapshot.")
    parser.add_argument("--pipeline-run-id", required=True)
    parser.add_argument("--features-dir", type=Path, default=PROJECT_ROOT / "data" / "curated" / "analytical_features")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    feature_path = args.features_dir / f"pipeline_run_id={args.pipeline_run_id}" / "features.parquet"
    if not feature_path.exists():
        raise FileNotFoundError(feature_path)
    frame = pd.read_parquet(feature_path)
    missing = sorted(REQUIRED_FEATURES - set(frame.columns))
    if missing:
        raise ValueError(f"Feature snapshot is missing columns: {missing}")
    if frame["transaction_id"].duplicated().any():
        raise ValueError("Feature snapshot contains duplicate transaction_id values")
    print(json.dumps({"feature_path": str(feature_path), "rows": len(frame), "columns": len(frame.columns), "status": "valid"}, indent=2))


if __name__ == "__main__":
    main()
