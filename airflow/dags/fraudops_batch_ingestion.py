from __future__ import annotations

from datetime import datetime

from airflow import DAG

from _fraudops_common import DEFAULT_ARGS, PYTHON, project_bash

with DAG(
    dag_id="fraudops_batch_ingestion",
    description="Raw-to-curated transaction ingestion with quality checks and reconciliation.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 7, 1),
    schedule="@daily",
    catchup=False,
    tags=["fraudops", "batch", "quality"],
) as dag:
    register_pipeline_run = project_bash("register_pipeline_run", "mkdir -p data/curated/pipeline_runs && echo airflow_ingestion_{{ ds_nodash }}")
    locate_input_files = project_bash("locate_input_files", f"{PYTHON} -c \"from pathlib import Path; assert (Path('data/sample/transaction.csv')).exists(); print('sample files located')\"")
    validate_schema_and_quarantine = project_bash(
        "validate_schema_and_quarantine",
        f"{PYTHON} scripts/run_batch_ingestion.py --pipeline-run-id airflow_ingestion_{{{{ ds_nodash }}}}",
    )
    load_valid_transactions = project_bash("load_valid_transactions", f"{PYTHON} -c \"from pathlib import Path; print(Path('data/validated/transactions').exists())\"")
    reconcile_counts = project_bash(
        "reconcile_counts",
        f"{PYTHON} scripts/validate_pipeline_outputs.py --pipeline-run-id airflow_ingestion_{{{{ ds_nodash }}}}",
    )
    close_pipeline_run = project_bash("close_pipeline_run", "echo ingestion pipeline closed")

    register_pipeline_run >> locate_input_files >> validate_schema_and_quarantine >> load_valid_transactions >> reconcile_counts >> close_pipeline_run
