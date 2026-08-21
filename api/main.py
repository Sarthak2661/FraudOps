from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.database import get_engine, initialize_database
from api.schemas import (
    CaseActionRequest,
    CaseActionResponse,
    CaseCreateRequest,
    CasePatchRequest,
    CaseResolveRequest,
    CaseResponse,
    ErrorResponse,
    HealthResponse,
    ScoreResponse,
    ScoreTransactionRequest,
)
from api.alerts import get_alert, list_alerts
from api.cases import (
    add_case_action,
    create_case,
    get_case,
    patch_case,
    resolve_case,
)
from api.scoring import current_model, get_transaction, rules, score_transaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s correlation_id=%(correlation_id)s %(message)s")
logger = logging.getLogger("fraudops.api")
engine = get_engine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database(engine)
    yield


app = FastAPI(
    title="FraudOps API",
    version="0.7.0",
    description="Transaction scoring, alert triage, and fraud case-management APIs.",
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next: Callable) -> Response:
    correlation_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled request failure", extra={"correlation_id": correlation_id})
        raise
    response.headers["x-correlation-id"] = correlation_id
    logger.info("request_complete path=%s status=%s", request.url.path, response.status_code, extra={"correlation_id": correlation_id})
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": exc.errors(), "correlation_id": request.state.correlation_id},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "detail": exc.detail, "correlation_id": request.state.correlation_id},
    )


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", service="fraudops-api", version=app.version, correlation_id=request.state.correlation_id)


@app.post("/v1/transactions/score", response_model=ScoreResponse, tags=["transactions"])
def score(request_body: ScoreTransactionRequest, request: Request) -> ScoreResponse:
    return score_transaction(engine, request_body, request.state.correlation_id)


@app.get("/v1/transactions/{transaction_id}", tags=["transactions"])
def transaction(transaction_id: str):
    result = get_transaction(engine, transaction_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    return result


@app.get("/v1/alerts", tags=["alerts"])
def alerts(status: str | None = None):
    return list_alerts(engine, status=status)


@app.get("/v1/alerts/{alert_id}", tags=["alerts"])
def alert(alert_id: str):
    result = get_alert(engine, alert_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return result


@app.post("/v1/cases", response_model=CaseResponse, tags=["cases"])
def create_case_endpoint(request_body: CaseCreateRequest) -> CaseResponse:
    return create_case(engine, request_body)


@app.get("/v1/cases/{case_id}", response_model=CaseResponse, tags=["cases"])
def case(case_id: str) -> CaseResponse:
    result = get_case(engine, case_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return result


@app.patch("/v1/cases/{case_id}", response_model=CaseResponse, tags=["cases"])
def update_case(case_id: str, request_body: CasePatchRequest) -> CaseResponse:
    result = patch_case(engine, case_id, request_body)
    if not result:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return result


@app.post("/v1/cases/{case_id}/actions", response_model=CaseActionResponse, tags=["cases"])
def add_action(case_id: str, request_body: CaseActionRequest) -> CaseActionResponse:
    result = add_case_action(engine, case_id, request_body)
    if not result:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return result


@app.post("/v1/cases/{case_id}/resolve", response_model=CaseResponse, tags=["cases"])
def resolve(case_id: str, request_body: CaseResolveRequest) -> CaseResponse:
    result = resolve_case(engine, case_id, request_body)
    if not result:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return result


@app.get("/v1/models/current", tags=["models"])
def model_current():
    return current_model()


@app.get("/v1/rules", tags=["rules"])
def rules_endpoint():
    return rules()
