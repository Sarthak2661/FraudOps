from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import JSON, Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, func
from sqlalchemy.engine import Engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSTGRES_URL = (
    "postgresql+psycopg://"
    f"{os.getenv('FRAUDOPS_POSTGRES_USER', 'fraudops_user')}:"
    f"{os.getenv('FRAUDOPS_POSTGRES_PASSWORD', 'fraudops_password')}@"
    f"{os.getenv('FRAUDOPS_POSTGRES_HOST', '127.0.0.1')}:"
    f"{os.getenv('FRAUDOPS_POSTGRES_PORT', '55433')}/"
    f"{os.getenv('FRAUDOPS_POSTGRES_DB', 'fraudops')}"
)
API_DATABASE_URL = os.getenv("FRAUDOPS_API_DATABASE_URL", DEFAULT_POSTGRES_URL)

metadata = MetaData()

scored_transactions = Table(
    "scored_transactions",
    metadata,
    Column("transaction_id", String, primary_key=True),
    Column("customer_id", String, nullable=True),
    Column("amount", Float, nullable=False),
    Column("risk_score", Float, nullable=False),
    Column("decision", String, nullable=False),
    Column("model_probability", Float, nullable=False),
    Column("triggered_rules", JSON, nullable=False),
    Column("explanation", JSON, nullable=False),
    Column("estimated_exposure", Float, nullable=False),
    Column("alert_id", String, nullable=True),
    Column("request_payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

alerts = Table(
    "alerts",
    metadata,
    Column("alert_id", String, primary_key=True),
    Column("transaction_id", String, nullable=False, unique=True),
    Column("customer_id", String, nullable=True),
    Column("amount", Float, nullable=False),
    Column("risk_score", Float, nullable=False),
    Column("decision", String, nullable=False),
    Column("priority", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("assigned_analyst", String, nullable=True),
    Column("sla_deadline", DateTime(timezone=True), nullable=False),
    Column("triggered_rules", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

cases = Table(
    "cases",
    metadata,
    Column("case_id", String, primary_key=True),
    Column("customer_id", String, nullable=True),
    Column("alert_ids", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("priority", Integer, nullable=False),
    Column("assigned_to", String, nullable=True),
    Column("case_summary", Text, nullable=False),
    Column("outcome", String, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

case_actions = Table(
    "case_actions",
    metadata,
    Column("action_id", String, primary_key=True),
    Column("case_id", String, nullable=False),
    Column("actor", String, nullable=False),
    Column("action_type", String, nullable=False),
    Column("notes", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or API_DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def initialize_database(engine: Engine) -> None:
    metadata.create_all(engine)
