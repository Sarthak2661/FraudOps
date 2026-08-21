from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fraudops.features import build_point_in_time_features
from fraudops.io import read_csv_table, read_parquet_tree, write_parquet_partitioned, write_single_parquet
from fraudops.quality import validate_transactions


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def append_csv(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row])
    if path.exists():
        frame.to_csv(path, mode="a", header=False, index=False)
    else:
        frame.to_csv(path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FraudOps raw-to-curated batch ingestion.")
    parser.add_argument("--source-dir", type=Path, default=PROJECT_ROOT / "data" / "sample")
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data" / "raw" / "transactions")
    parser.add_argument("--validated-dir", type=Path, default=PROJECT_ROOT / "data" / "validated" / "transactions")
    parser.add_argument("--rejected-dir", type=Path, default=PROJECT_ROOT / "data" / "rejected" / "transactions")
    parser.add_argument("--curated-dir", type=Path, default=PROJECT_ROOT / "data" / "curated")
    parser.add_argument("--pipeline-name", default="batch_transaction_ingestion")
    parser.add_argument("--pipeline-run-id", default=None)
    parser.add_argument("--feature-start-date", default=None)
    parser.add_argument("--feature-end-date", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pipeline_run_id = args.pipeline_run_id or f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    started_at = utc_now()
    status = "SUCCESS"
    error_message = ""

    try:
        transactions = read_csv_table(args.source_dir, "transaction")
        customers = read_csv_table(args.source_dir, "customer")
        accounts = read_csv_table(args.source_dir, "account")
        cards = read_csv_table(args.source_dir, "card")
        devices = read_csv_table(args.source_dir, "device")
        merchants = read_csv_table(args.source_dir, "merchant")

        raw_files = write_parquet_partitioned(transactions, args.raw_dir, "transaction_at")
        raw_transactions = read_parquet_tree(args.raw_dir)

        accepted, rejected, quality_results = validate_transactions(
            transactions=raw_transactions,
            customers=customers,
            accounts=accounts,
            cards=cards,
            devices=devices,
            merchants=merchants,
            pipeline_run_id=pipeline_run_id,
            source_file=str(args.raw_dir),
        )

        validated_path = args.validated_dir / f"pipeline_run_id={pipeline_run_id}" / "transactions.parquet"
        rejected_path = args.rejected_dir / f"pipeline_run_id={pipeline_run_id}" / "rejected_records.parquet"
        quality_path = args.curated_dir / "pipeline_runs" / f"quality_results_{pipeline_run_id}.parquet"
        write_single_parquet(accepted, validated_path)
        write_single_parquet(rejected, rejected_path)
        write_single_parquet(quality_results, quality_path)

        feature_input = accepted.copy()
        feature_input["transaction_at"] = pd.to_datetime(feature_input["transaction_at"], utc=True, errors="coerce")
        feature_start = pd.Timestamp(args.feature_start_date, tz="UTC") if args.feature_start_date else None
        feature_end = pd.Timestamp(args.feature_end_date, tz="UTC") if args.feature_end_date else None
        if feature_end is not None:
            feature_input = feature_input[feature_input["transaction_at"] < feature_end]

        features = build_point_in_time_features(
            transactions=feature_input,
            customers=customers,
            devices=devices,
            merchants=merchants,
            pipeline_run_id=pipeline_run_id,
        )
        if feature_start is not None:
            features = features[features["transaction_at"] >= feature_start]
        if feature_end is not None:
            features = features[features["transaction_at"] < feature_end]
        feature_path = args.curated_dir / "analytical_features" / f"pipeline_run_id={pipeline_run_id}" / "features.parquet"
        write_single_parquet(features, feature_path)

        completed_at = utc_now()
        audit_row = {
            "pipeline_run_id": pipeline_run_id,
            "pipeline_name": args.pipeline_name,
            "started_at": started_at,
            "completed_at": completed_at,
            "status": status,
            "input_records": len(raw_transactions),
            "accepted_records": len(accepted),
            "rejected_records": len(rejected),
            "duplicate_records": int(raw_transactions["transaction_id"].duplicated(keep="first").sum()),
            "input_uri": str(args.raw_dir),
            "validated_uri": str(validated_path),
            "rejected_uri": str(rejected_path),
            "curated_uri": str(feature_path),
            "error_message": error_message,
        }
        append_csv(args.curated_dir / "pipeline_runs" / "pipeline_runs.csv", audit_row)

        summary = {
            **audit_row,
            "raw_files_written": [str(path) for path in raw_files],
            "quality_results_uri": str(quality_path),
            "feature_records": len(features),
        }
        (args.curated_dir / "pipeline_runs" / f"pipeline_summary_{pipeline_run_id}.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))
    except Exception as exc:
        status = "FAILED"
        completed_at = utc_now()
        error_message = str(exc)
        audit_row = {
            "pipeline_run_id": pipeline_run_id,
            "pipeline_name": args.pipeline_name,
            "started_at": started_at,
            "completed_at": completed_at,
            "status": status,
            "input_records": 0,
            "accepted_records": 0,
            "rejected_records": 0,
            "duplicate_records": 0,
            "input_uri": str(args.source_dir),
            "validated_uri": "",
            "rejected_uri": "",
            "curated_uri": "",
            "error_message": error_message,
        }
        append_csv(args.curated_dir / "pipeline_runs" / "pipeline_runs.csv", audit_row)
        raise


if __name__ == "__main__":
    main()
