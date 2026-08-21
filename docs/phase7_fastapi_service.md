# Phase 7: FastAPI Service

## Objective

Expose transaction scoring and fraud case-management through versioned APIs.

## Run

```powershell
cd FraudOps
.\.venv\Scripts\Activate.ps1
$env:FRAUDOPS_API_DATABASE_URL="postgresql+psycopg://fraudops_user:fraudops_password@127.0.0.1:55433/fraudops"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Open Swagger docs:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

- `GET /health`
- `POST /v1/transactions/score`
- `GET /v1/transactions/{transaction_id}`
- `GET /v1/alerts`
- `GET /v1/alerts/{alert_id}`
- `POST /v1/cases`
- `GET /v1/cases/{case_id}`
- `PATCH /v1/cases/{case_id}`
- `POST /v1/cases/{case_id}/actions`
- `POST /v1/cases/{case_id}/resolve`
- `GET /v1/models/current`
- `GET /v1/rules`

## Engineering Features

- Pydantic request and response schemas
- Structured validation errors
- Request correlation IDs through `x-correlation-id`
- Structured request logging
- SQLAlchemy-backed API state database
- Transaction-scoped writes
- Idempotent transaction scoring by `transaction_id`
- API versioning under `/v1`
- Swagger documentation at `/docs`
- Integration tests in `tests/test_api.py`

## Scoring Workflow

Request validation -> curated feature lookup -> model prediction -> rule evaluation -> cost-sensitive decision -> score storage -> alert creation when needed -> API response.

## Definition of Done

- `/health` returns successfully
- Transactions can be scored
- Repeated scoring requests do not create duplicate alerts
- Invalid requests return structured error messages
- API documentation is available at `/docs`
- API tests pass
