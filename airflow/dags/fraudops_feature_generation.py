from __future__ import annotations

from datetime import datetime

from airflow import DAG

from _fraudops_common import DEFAULT_ARGS, PYTHON, project_bash

with DAG(
    dag_id="fraudops_feature_generation",
    description="Point-in-time feature snapshot generation and validation.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 7, 1),
    schedule="@daily",
    catchup=False,
    tags=["fraudops", "features"],
) as dag:
    identify_feature_window = project_bash("identify_feature_window", "echo feature_window={{ ds }}")
    calculate_customer_features = project_bash("calculate_customer_features", "echo customer features included in batch feature builder")
    calculate_device_features = project_bash("calculate_device_features", "echo device features included in batch feature builder")
    calculate_merchant_features = project_bash("calculate_merchant_features", "echo merchant features included in batch feature builder")
    publish_feature_snapshot = project_bash(
        "publish_feature_snapshot",
        f"{PYTHON} scripts/run_batch_ingestion.py --pipeline-run-id airflow_features_{{{{ ds_nodash }}}} --feature-start-date {{{{ ds }}}}",
    )
    validate_feature_table = project_bash(
        "validate_feature_table",
        f"{PYTHON} scripts/validate_feature_snapshot.py --pipeline-run-id airflow_features_{{{{ ds_nodash }}}}",
    )

    identify_feature_window >> [calculate_customer_features, calculate_device_features, calculate_merchant_features] >> publish_feature_snapshot >> validate_feature_table
