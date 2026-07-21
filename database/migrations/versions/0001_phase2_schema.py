"""create phase 2 fraudops schema

Revision ID: 0001_phase2_schema
Revises:
Create Date: 2026-07-13
"""
from __future__ import annotations

from alembic import op

revision = "0001_phase2_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with open("database/sql/001_initial_schema.sql", encoding="utf-8") as schema_file:
        op.execute(schema_file.read())


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS fraudops CASCADE")
