from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports" / "orchestration" / "reporting_refresh_status.json"
REQUIRED_VIEWS = [
    "vw_daily_fraud_summary",
    "vw_alert_operations",
    "vw_case_performance",
    "vw_analyst_productivity",
    "vw_rule_performance",
    "vw_model_performance",
    "vw_fraud_loss",
    "vw_data_quality",
    "vw_source_to_curated_reconciliation",
]


def conninfo() -> str:
    return " ".join(
        [
            f"host={os.getenv('FRAUDOPS_POSTGRES_HOST', '127.0.0.1')}",
            f"port={os.getenv('FRAUDOPS_POSTGRES_PORT', '55433')}",
            f"dbname={os.getenv('FRAUDOPS_POSTGRES_DB', 'fraudops')}",
            f"user={os.getenv('FRAUDOPS_POSTGRES_USER', 'fraudops_user')}",
            f"password={os.getenv('FRAUDOPS_POSTGRES_PASSWORD', 'fraudops_password')}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate FraudOps reporting views.")
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = {}
    with psycopg.connect(conninfo()) as connection:
        with connection.cursor() as cursor:
            for view in REQUIRED_VIEWS:
                cursor.execute(f"SELECT count(*) FROM fraudops_reporting.{view}")
                counts[view] = cursor.fetchone()[0]
    missing_rows = [view for view, count in counts.items() if count == 0 and view not in {"vw_model_performance"}]
    if missing_rows:
        raise ValueError(f"Reporting views returned zero rows: {missing_rows}")
    result = {"status": "valid", "view_counts": counts}
    if not args.check_only:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
