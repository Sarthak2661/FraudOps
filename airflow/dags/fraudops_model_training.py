from __future__ import annotations

from datetime import datetime

from airflow import DAG

from _fraudops_common import DEFAULT_ARGS, PYTHON, project_bash

with DAG(
    dag_id="fraudops_model_training",
    description="Chronological model training and MLflow experiment logging.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 7, 1),
    schedule=None,
    catchup=False,
    tags=["fraudops", "modeling", "mlflow"],
) as dag:
    build_training_dataset = project_bash(
        "build_training_dataset",
        f"{PYTHON} scripts/build_training_dataset.py --start-date 2026-07-01 --end-date 2026-09-29",
    )
    validate_labels = project_bash("validate_labels", f"{PYTHON} scripts/validate_training_labels.py --dataset data/curated/training_dataset.parquet")
    chronological_split = project_bash("chronological_split", "echo chronological split is handled inside train_baseline_models.py")
    train_baseline_models = project_bash("train_logistic_random_forest_gradient_boosting", f"{PYTHON} scripts/train_baseline_models.py")
    evaluate_models = project_bash("evaluate_models", f"{PYTHON} -c \"from pathlib import Path; assert Path('reports/modeling/model_comparison_validation.csv').exists(); print('model comparison exists')\"")
    log_to_mlflow = project_bash("log_to_mlflow", "echo MLflow logging is handled inside train_baseline_models.py")
    register_candidate_model = project_bash("register_candidate_model", f"{PYTHON} -c \"from pathlib import Path; assert Path('reports/modeling/selected_model.joblib').exists(); print('candidate model artifact exists')\"")

    build_training_dataset >> validate_labels >> chronological_split >> train_baseline_models >> evaluate_models >> log_to_mlflow >> register_candidate_model
