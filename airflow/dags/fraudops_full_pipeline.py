from __future__ import annotations

from datetime import datetime

from airflow import DAG

from _fraudops_common import DEFAULT_ARGS, PYTHON, project_bash

with DAG(
    dag_id="fraudops_full_pipeline",
    description="End-to-end FraudOps pipeline for local container walkthroughs.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 7, 1),
    schedule=None,
    catchup=False,
    tags=["fraudops", "end-to-end", "portfolio"],
) as dag:
    verify_sample_data = project_bash(
        "verify_sample_data",
        f"{PYTHON} -c \"from pathlib import Path; assert Path('data/sample/transaction.csv').exists(); print('sample transaction data found')\"",
    )
    ingest_transactions = project_bash(
        "ingest_transactions",
        f"{PYTHON} scripts/run_batch_ingestion.py --pipeline-run-id airflow_full_ingestion_{{{{ ds_nodash }}}}",
    )
    validate_ingestion = project_bash(
        "validate_ingestion",
        f"{PYTHON} scripts/validate_pipeline_outputs.py --pipeline-run-id airflow_full_ingestion_{{{{ ds_nodash }}}}",
    )
    publish_feature_snapshot = project_bash(
        "publish_feature_snapshot",
        f"{PYTHON} scripts/run_batch_ingestion.py --pipeline-run-id airflow_full_features_{{{{ ds_nodash }}}}",
    )
    validate_feature_snapshot = project_bash(
        "validate_feature_snapshot",
        f"{PYTHON} scripts/validate_feature_snapshot.py --pipeline-run-id airflow_full_features_{{{{ ds_nodash }}}}",
    )
    build_training_dataset = project_bash(
        "build_training_dataset",
        f"{PYTHON} scripts/build_training_dataset.py --start-date 2026-07-01 --end-date 2026-09-29",
    )
    validate_training_labels = project_bash(
        "validate_training_labels",
        f"{PYTHON} scripts/validate_training_labels.py --dataset data/curated/training_dataset.parquet",
    )
    train_baseline_models = project_bash(
        "train_baseline_models",
        f"{PYTHON} scripts/train_baseline_models.py --features data/curated/training_dataset.parquet",
    )
    optimize_threshold = project_bash(
        "optimize_threshold",
        f"{PYTHON} scripts/optimize_thresholds.py",
    )
    publish_reporting_views = project_bash(
        "publish_reporting_views",
        f"{PYTHON} scripts/publish_reporting_views.py",
    )
    validate_reporting_views = project_bash(
        "validate_reporting_views",
        f"{PYTHON} scripts/validate_reporting_views.py",
    )
    final_artifact_check = project_bash(
        "final_artifact_check",
        f"{PYTHON} -c \"from pathlib import Path; required = ['reports/modeling/model_selection.json', 'reports/modeling/threshold_recommendation.json', 'reports/orchestration/reporting_refresh_status.json']; missing = [p for p in required if not Path(p).exists()]; assert not missing, missing; print('full pipeline artifacts verified')\"",
    )

    (
        verify_sample_data
        >> ingest_transactions
        >> validate_ingestion
        >> publish_feature_snapshot
        >> validate_feature_snapshot
        >> build_training_dataset
        >> validate_training_labels
        >> train_baseline_models
        >> optimize_threshold
        >> publish_reporting_views
        >> validate_reporting_views
        >> final_artifact_check
    )
