from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, Select, select

from api._support import json_list, now_utc, row_to_dict
from api.database import alerts
from api.schemas import AlertResponse


def alert_response(row: dict[str, Any]) -> AlertResponse:
    created_at = row["created_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    age_minutes = max(0, int((now_utc() - created_at).total_seconds() // 60))
    return AlertResponse(
        alert_id=row["alert_id"],
        transaction_id=row["transaction_id"],
        risk_score=float(row["risk_score"]),
        amount=float(row["amount"]),
        priority=int(row["priority"]),
        customer_id=row.get("customer_id"),
        decision=row["decision"],
        alert_age_minutes=age_minutes,
        status=row["status"],
        assigned_analyst=row.get("assigned_analyst"),
        sla_deadline=row["sla_deadline"],
        triggered_rules=json_list(row.get("triggered_rules")),
    )


def list_alerts(engine: Engine, status: str | None = None) -> list[AlertResponse]:
    query: Select[Any] = select(alerts).order_by(alerts.c.created_at.desc())
    if status:
        query = query.where(alerts.c.status == status)
    with engine.begin() as connection:
        rows = [row_to_dict(row) for row in connection.execute(query).all()]
    return [alert_response(row) for row in rows]


def get_alert(engine: Engine, alert_id: str) -> AlertResponse | None:
    with engine.begin() as connection:
        row = connection.execute(select(alerts).where(alerts.c.alert_id == alert_id)).first()
    return alert_response(row_to_dict(row)) if row else None
