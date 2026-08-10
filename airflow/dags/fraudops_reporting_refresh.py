from __future__ import annotations

from datetime import datetime

from airflow import DAG

from _fraudops_common import DEFAULT_ARGS, PYTHON, project_bash

with DAG(
    dag_id="fraudops_reporting_refresh",
    description="Publish and validate PostgreSQL reporting views for Power BI.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 7, 1),
    schedule="@daily",
    catchup=False,
    tags=["fraudops", "reporting", "powerbi"],
) as dag:
    build_daily_metrics = project_bash("build_daily_metrics", "echo daily metrics are defined in reporting SQL")
    validate_aggregates = project_bash("validate_aggregates", f"{PYTHON} scripts/validate_reporting_views.py --check-only")
    publish_reporting_views = project_bash("publish_reporting_views", f"{PYTHON} scripts/publish_reporting_views.py")
    record_refresh_status = project_bash("record_refresh_status", f"{PYTHON} scripts/validate_reporting_views.py")

    build_daily_metrics >> validate_aggregates >> publish_reporting_views >> record_refresh_status
