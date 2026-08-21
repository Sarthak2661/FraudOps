from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Engine, insert, select, update

from api._support import json_list, now_utc, row_to_dict
from api.database import case_actions, cases
from api.schemas import (
    CaseActionRequest,
    CaseActionResponse,
    CaseCreateRequest,
    CasePatchRequest,
    CaseResolveRequest,
    CaseResponse,
)


def case_response(engine: Engine, row: dict[str, Any]) -> CaseResponse:
    with engine.begin() as connection:
        action_rows = [
            row_to_dict(item)
            for item in connection.execute(
                select(case_actions).where(case_actions.c.case_id == row["case_id"]).order_by(case_actions.c.created_at)
            ).all()
        ]
    return CaseResponse(
        case_id=row["case_id"],
        customer_id=row.get("customer_id"),
        alert_ids=json_list(row.get("alert_ids")),
        status=row["status"],
        priority=int(row["priority"]),
        assigned_to=row.get("assigned_to"),
        case_summary=row["case_summary"],
        outcome=row.get("outcome"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        actions=[
            CaseActionResponse(
                action_id=item["action_id"],
                case_id=item["case_id"],
                actor=item["actor"],
                action_type=item["action_type"],
                notes=item["notes"],
                created_at=item["created_at"],
            )
            for item in action_rows
        ],
    )


def create_case(engine: Engine, request: CaseCreateRequest) -> CaseResponse:
    case_id = f"CASE-{uuid.uuid4().hex[:12].upper()}"
    timestamp = now_utc()
    with engine.begin() as connection:
        connection.execute(
            insert(cases).values(
                case_id=case_id,
                customer_id=request.customer_id,
                alert_ids=request.alert_ids,
                status="OPEN",
                priority=request.priority,
                assigned_to=request.assigned_to,
                case_summary=request.case_summary,
                outcome=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        row = row_to_dict(connection.execute(select(cases).where(cases.c.case_id == case_id)).first())
    return case_response(engine, row)


def get_case(engine: Engine, case_id: str) -> CaseResponse | None:
    with engine.begin() as connection:
        row = connection.execute(select(cases).where(cases.c.case_id == case_id)).first()
    return case_response(engine, row_to_dict(row)) if row else None


def patch_case(engine: Engine, case_id: str, request: CasePatchRequest) -> CaseResponse | None:
    values = {key: value for key, value in request.model_dump(exclude_unset=True).items() if value is not None}
    values["updated_at"] = now_utc()
    with engine.begin() as connection:
        existing = connection.execute(select(cases).where(cases.c.case_id == case_id)).first()
        if not existing:
            return None
        connection.execute(update(cases).where(cases.c.case_id == case_id).values(**values))
        row = row_to_dict(connection.execute(select(cases).where(cases.c.case_id == case_id)).first())
    return case_response(engine, row)


def add_case_action(engine: Engine, case_id: str, request: CaseActionRequest) -> CaseActionResponse | None:
    action_id = f"ACT-{uuid.uuid4().hex[:12].upper()}"
    timestamp = now_utc()
    with engine.begin() as connection:
        existing = connection.execute(select(cases).where(cases.c.case_id == case_id)).first()
        if not existing:
            return None
        connection.execute(
            insert(case_actions).values(
                action_id=action_id,
                case_id=case_id,
                actor=request.actor,
                action_type=request.action_type,
                notes=request.notes,
                created_at=timestamp,
            )
        )
        connection.execute(update(cases).where(cases.c.case_id == case_id).values(updated_at=timestamp))
    return CaseActionResponse(
        action_id=action_id,
        case_id=case_id,
        actor=request.actor,
        action_type=request.action_type,
        notes=request.notes,
        created_at=timestamp,
    )


def resolve_case(engine: Engine, case_id: str, request: CaseResolveRequest) -> CaseResponse | None:
    action = add_case_action(
        engine,
        case_id,
        CaseActionRequest(actor=request.actor, action_type=f"RESOLVE_{request.outcome}", notes=request.notes),
    )
    if not action:
        return None
    with engine.begin() as connection:
        connection.execute(
            update(cases).where(cases.c.case_id == case_id).values(status="CLOSED", outcome=request.outcome, updated_at=now_utc())
        )
        row = row_to_dict(connection.execute(select(cases).where(cases.c.case_id == case_id)).first())
    return case_response(engine, row)
