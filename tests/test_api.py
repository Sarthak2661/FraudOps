from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from api import main as api_main
from api.database import initialize_database


def make_client(tmp_path: Path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'api_test.db'}", connect_args={"check_same_thread": False}, future=True)
    initialize_database(engine)
    api_main.engine = engine
    return TestClient(api_main.app)


def test_health_and_docs(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/health", headers={"x-correlation-id": "test-corr"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-correlation-id"] == "test-corr"
    assert client.get("/docs").status_code == 200


def test_score_is_idempotent_and_creates_single_alert(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = {
        "transaction_id": "api-test-txn-001",
        "customer_id": "cust-api",
        "amount": 920.0,
        "currency": "USD",
        "model_probability_override": 0.92,
    }
    first = client.post("/v1/transactions/score", json=payload)
    second = client.post("/v1/transactions/score", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["alert_id"] == second.json()["alert_id"]
    assert second.json()["idempotent_replay"] is True
    alerts = client.get("/v1/alerts").json()
    assert len(alerts) == 1


def test_invalid_score_request_returns_useful_error(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/v1/transactions/score", json={"transaction_id": "bad", "amount": -1})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["correlation_id"]


def test_case_workflow(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    score = client.post(
        "/v1/transactions/score",
        json={"transaction_id": "api-test-txn-002", "customer_id": "cust-case", "amount": 500, "model_probability_override": 0.88},
    ).json()
    case = client.post("/v1/cases", json={"customer_id": "cust-case", "alert_ids": [score["alert_id"]], "assigned_to": "analyst1"})
    assert case.status_code == 200
    case_id = case.json()["case_id"]
    action = client.post(f"/v1/cases/{case_id}/actions", json={"actor": "analyst1", "action_type": "NOTE", "notes": "Called customer"})
    assert action.status_code == 200
    resolved = client.post(f"/v1/cases/{case_id}/resolve", json={"actor": "analyst1", "outcome": "CONFIRMED_FRAUD", "notes": "Customer confirmed fraud"})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "CLOSED"
    assert resolved.json()["outcome"] == "CONFIRMED_FRAUD"
