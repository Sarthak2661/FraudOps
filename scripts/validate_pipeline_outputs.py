from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate FraudOps batch pipeline output files.")
    parser.add_argument("--pipeline-run-id", required=True)
    parser.add_argument("--curated-dir", type=Path, default=PROJECT_ROOT / "data" / "curated")
    parser.add_argument("--validated-dir", type=Path, default=PROJECT_ROOT / "data" / "validated" / "transactions")
    parser.add_argument("--rejected-dir", type=Path, default=PROJECT_ROOT / "data" / "rejected" / "transactions")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_path = args.curated_dir / "pipeline_runs" / f"pipeline_summary_{args.pipeline_run_id}.json"
    validated_path = args.validated_dir / f"pipeline_run_id={args.pipeline_run_id}" / "transactions.parquet"
    rejected_path = args.rejected_dir / f"pipeline_run_id={args.pipeline_run_id}" / "rejected_records.parquet"
    feature_path = args.curated_dir / "analytical_features" / f"pipeline_run_id={args.pipeline_run_id}" / "features.parquet"

    missing = [str(path) for path in [summary_path, validated_path, rejected_path, feature_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing pipeline outputs: {missing}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    reconciled = summary["input_records"] == summary["accepted_records"] + summary["rejected_records"]
    if not reconciled:
        raise ValueError(f"Pipeline counts do not reconcile: {summary}")
    print(json.dumps({"pipeline_run_id": args.pipeline_run_id, "status": "valid", "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
