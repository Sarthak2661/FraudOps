from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fraudops.io import read_parquet_tree, write_single_parquet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a date-filtered FraudOps training dataset from curated features.")
    parser.add_argument("--features-dir", type=Path, default=PROJECT_ROOT / "data" / "curated" / "analytical_features")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "curated" / "training_dataset.parquet")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = read_parquet_tree(args.features_dir)
    features["transaction_at"] = pd.to_datetime(features["transaction_at"], utc=True)
    training = features[
        (features["transaction_at"] >= pd.Timestamp(args.start_date, tz="UTC"))
        & (features["transaction_at"] < pd.Timestamp(args.end_date, tz="UTC"))
    ].copy()
    write_single_parquet(training, args.output)
    print(f"Wrote {len(training)} training rows to {args.output}")


if __name__ == "__main__":
    main()
