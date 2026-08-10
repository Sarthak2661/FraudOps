from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["APPROVE", "STEP_UP_AUTHENTICATION", "MANUAL_REVIEW", "HOLD_OR_DECLINE"]
AlertStatus = Literal["OPEN", "IN_REVIEW", "ESCALATED", "CLOSED"]
CaseStatus = Literal["OPEN", "PENDING_CUSTOMER", "ESCALATED", "CLOSED"]
CaseOutcome = Literal[
    "CONFIRMED_FRAUD",
    "LEGITIMATE",
    "CUSTOMER_AUTHENTICATED",
    "INSUFFICIENT_EVIDENCE",
    "DUPLICATE_ALERT",
    "RULE_ERROR",
]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    correlation_id: str


class ScoreTransactionRequest(BaseModel):
    transaction_id: str = Field(..., min_length=3)
    customer_id: str | None = None
    card_id: str | None = None
    account_id: str | None = None
    merchant_id: str | None = None
    device_id: str | None = None
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    channel: str = "card_not_present"
    merchant_country: str = "US"
    transaction_at: datetime | None = None
    model_probability_override: float | None = Field(default=None, ge=0, le=1)


class ScoreResponse(BaseModel):
    transaction_id: str
    risk_score: float
    decision: Decision
    triggered_rules: list[str]
    estimated_exposure: float
    explanation: list[str]
    alert_id: str | None = None
    idempotent_replay: bool = False
    correlation_id: str


class TransactionResponse(BaseModel):
    transaction_id: str
    amount: float | None = None
    customer_id: str | None = None
    decision: Decision | None = None
    risk_score: float | None = None
    alert_id: str | None = None
    scored_at: datetime | None = None
    source: str


class AlertResponse(BaseModel):
    alert_id: str
    transaction_id: str
    risk_score: float
    amount: float
    priority: int
    customer_id: str | None = None
    decision: Decision
    alert_age_minutes: int
    status: AlertStatus
    assigned_analyst: str | None = None
    sla_deadline: datetime
    triggered_rules: list[str]


class CaseCreateRequest(BaseModel):
    customer_id: str | None = None
    alert_ids: list[str] = Field(default_factory=list)
    assigned_to: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    case_summary: str = ""


class CasePatchRequest(BaseModel):
    status: CaseStatus | None = None
    assigned_to: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    case_summary: str | None = None


class CaseActionRequest(BaseModel):
    actor: str = "analyst"
    action_type: str
    notes: str = ""


class CaseResolveRequest(BaseModel):
    actor: str = "analyst"
    outcome: CaseOutcome
    notes: str = ""


class CaseActionResponse(BaseModel):
    action_id: str
    case_id: str
    actor: str
    action_type: str
    notes: str
    created_at: datetime


class CaseResponse(BaseModel):
    case_id: str
    customer_id: str | None = None
    alert_ids: list[str]
    status: CaseStatus
    priority: int
    assigned_to: str | None = None
    case_summary: str
    outcome: CaseOutcome | None = None
    created_at: datetime
    updated_at: datetime
    actions: list[CaseActionResponse] = Field(default_factory=list)


class ModelCurrentResponse(BaseModel):
    model_name: str
    model_status: Literal["READY", "FALLBACK"]
    scoring_mode: Literal["model_artifact", "fallback_default_probability"]
    threshold: float | None
    feature_count: int
    artifact_path: str | None
    artifact_exists: bool
    trained_model_available: bool
    fallback_probability: float | None = None
    metrics: dict[str, Any]
    message: str


class RuleResponse(BaseModel):
    rule_id: str
    name: str
    description: str
    severity: str
    active: bool
    risk_points: float
    decision_override: str | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: Any
    correlation_id: str

    model_config = ConfigDict(json_schema_extra={"example": {"error": "validation_error", "detail": [], "correlation_id": "abc"}})
