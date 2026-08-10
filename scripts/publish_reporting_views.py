from __future__ import annotations

import os
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = PROJECT_ROOT / "database" / "sql" / "004_powerbi_reporting_views.sql"


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


def main() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8")
    with psycopg.connect(conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()
    print(f"Published reporting views from {SQL_PATH}")


if __name__ == "__main__":
    main()
