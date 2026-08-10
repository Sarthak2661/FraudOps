from __future__ import annotations

import os
from datetime import timedelta

from airflow.operators.bash import BashOperator

PROJECT_ROOT = os.getenv("FRAUDOPS_PROJECT_ROOT", "/opt/airflow/project")
PYTHON = os.getenv("FRAUDOPS_PYTHON", "/opt/airflow/fraudops_venv/bin/python")
DEFAULT_ARGS = {
    "owner": "fraudops",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def project_bash(task_id: str, command: str) -> BashOperator:
    return BashOperator(
        task_id=task_id,
        bash_command=f"cd {PROJECT_ROOT} && {command}",
        env={
            "PYTHONPATH": f"{PROJECT_ROOT}/src:{PROJECT_ROOT}",
            "FRAUDOPS_PROJECT_ROOT": PROJECT_ROOT,
            "FRAUDOPS_POSTGRES_HOST": os.getenv("FRAUDOPS_POSTGRES_HOST", "fraud-postgres"),
            "FRAUDOPS_POSTGRES_PORT": os.getenv("FRAUDOPS_POSTGRES_PORT", "5432"),
            "FRAUDOPS_POSTGRES_DB": os.getenv("FRAUDOPS_POSTGRES_DB", "fraudops"),
            "FRAUDOPS_POSTGRES_USER": os.getenv("FRAUDOPS_POSTGRES_USER", "fraudops_user"),
            "FRAUDOPS_POSTGRES_PASSWORD": os.getenv("FRAUDOPS_POSTGRES_PASSWORD", "fraudops_password"),
            "FRAUDOPS_API_DATABASE_URL": os.getenv(
                "FRAUDOPS_API_DATABASE_URL",
                "postgresql+psycopg://fraudops_user:fraudops_password@fraud-postgres:5432/fraudops",
            ),
        },
    )
