from __future__ import annotations

import os

from sqlalchemy import JSON, Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, func
from sqlalchemy.engine import Engine

REQUIRED_DATABASE_ENV = "FRAUDOPS_API_DATABASE_URL"

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
    if database_url is None:
        try:
            database_url = os.environ[REQUIRED_DATABASE_ENV]
        except KeyError as exc:
            raise RuntimeError(
                f"{REQUIRED_DATABASE_ENV} is required. Set it explicitly instead of relying on local demo credentials."
            ) from exc
    url = database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def initialize_database(engine: Engine) -> None:
    metadata.create_all(engine)
