from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate label readiness for FraudOps model training.")
    parser.add_argument("--dataset", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dataset.exists():
        raise FileNotFoundError(args.dataset)
    frame = pd.read_parquet(args.dataset)
    if "fraud_label" not in frame.columns:
        raise ValueError("Training dataset is missing fraud_label")
    label_counts = frame["fraud_label"].fillna("unknown").value_counts().to_dict()
    if label_counts.get("fraud", 0) == 0:
        raise ValueError("Training dataset has no fraud labels")
    print(json.dumps({"dataset": str(args.dataset), "rows": len(frame), "label_counts": label_counts, "status": "valid"}, indent=2))


if __name__ == "__main__":
    main()
