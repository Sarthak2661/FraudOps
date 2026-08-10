from __future__ import annotations

from datetime import datetime

from airflow import DAG

from _fraudops_common import DEFAULT_ARGS, PYTHON, project_bash

with DAG(
    dag_id="fraudops_threshold_optimization",
    description="Threshold and review-capacity optimization from validation model metrics.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 7, 1),
    schedule=None,
    catchup=False,
    tags=["fraudops", "thresholds", "capacity"],
) as dag:
    load_validation_predictions = project_bash("load_validation_predictions", f"{PYTHON} -c \"from pathlib import Path; assert Path('reports/modeling/model_comparison_validation.csv').exists(); print('validation comparison loaded')\"")
    simulate_thresholds = project_bash("simulate_thresholds", f"{PYTHON} scripts/optimize_thresholds.py")
    calculate_fraud_loss = project_bash("calculate_fraud_loss", "echo fraud loss calculated in threshold optimizer")
    calculate_review_cost = project_bash("calculate_review_cost", "echo review cost calculated in threshold optimizer")
    apply_analyst_capacity = project_bash("apply_analyst_capacity", "echo analyst capacity applied in threshold optimizer")
    recommend_threshold = project_bash("recommend_threshold", f"{PYTHON} -c \"from pathlib import Path; assert Path('reports/modeling/threshold_recommendation.json').exists(); print('threshold recommendation ready')\"")

    load_validation_predictions >> simulate_thresholds >> calculate_fraud_loss >> calculate_review_cost >> apply_analyst_capacity >> recommend_threshold
