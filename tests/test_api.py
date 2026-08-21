from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

os.environ.setdefault("FRAUDOPS_API_DATABASE_URL", "sqlite:///:memory:")

from api import main as api_main
from api import model_service
from api import scoring_service
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


def test_local_vite_ports_are_allowed_by_cors(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.options(
        "/v1/models/current",
        headers={
            "origin": "http://127.0.0.1:5176",
            "access-control-request-method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5176"


def test_score_is_idempotent_and_creates_single_alert(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    monkeypatch.setattr(scoring_service, "predict_probability", lambda feature_row: 0.92)
    payload = {
        "transaction_id": "api-test-txn-001",
        "customer_id": "cust-api",
        "amount": 920.0,
        "currency": "USD",
    }
    first = client.post("/v1/transactions/score", json=payload)
    second = client.post("/v1/transactions/score", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["alert_id"] == second.json()["alert_id"]
    assert second.json()["idempotent_replay"] is True
    alerts = client.get("/v1/alerts").json()
    assert len(alerts) == 1


def test_score_rejects_public_probability_override(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post(
        "/v1/transactions/score",
        json={
            "transaction_id": "api-test-txn-override",
            "customer_id": "cust-api",
            "amount": 920.0,
            "currency": "USD",
            "model_probability_override": 0.92,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_invalid_score_request_returns_useful_error(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.post("/v1/transactions/score", json={"transaction_id": "bad", "amount": -1})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert body["correlation_id"]


def test_api_key_boundary_is_enforced_when_configured(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRAUDOPS_API_KEY", "local-test-key")
    client = make_client(tmp_path)
    payload = {"transaction_id": "api-test-auth-001", "customer_id": "cust-api", "amount": 100.0, "currency": "USD"}

    rejected = client.post("/v1/transactions/score", json=payload)
    accepted = client.post("/v1/transactions/score", json=payload, headers={"x-api-key": "local-test-key"})

    assert rejected.status_code == 401
    assert rejected.json()["error"] == "unauthorized"
    assert accepted.status_code == 200
    monkeypatch.delenv("FRAUDOPS_API_KEY", raising=False)


def test_case_workflow(tmp_path: Path, monkeypatch) -> None:
    client = make_client(tmp_path)
    monkeypatch.setattr(scoring_service, "predict_probability", lambda feature_row: 0.88)
    score = client.post(
        "/v1/transactions/score",
        json={"transaction_id": "api-test-txn-002", "customer_id": "cust-case", "amount": 500},
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


def test_current_model_reports_artifact_status(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/v1/models/current")
    assert response.status_code == 200
    body = response.json()
    assert body["model_status"] in {"READY", "FALLBACK"}
    assert body["scoring_mode"] in {"model_artifact", "fallback_default_probability"}
    assert isinstance(body["artifact_exists"], bool)
    assert isinstance(body["trained_model_available"], bool)
    assert body["message"]


def test_current_model_uses_model_selection_name(tmp_path: Path, monkeypatch) -> None:
    selection_path = tmp_path / "model_selection.json"
    selection_path.write_text('{"selected_model": "hist_gradient_boosting"}', encoding="utf-8")
    monkeypatch.setattr(model_service, "MODEL_SELECTION_PATH", selection_path)
    monkeypatch.setattr(model_service, "MODEL_PATH", tmp_path / "selected_model.joblib")
    monkeypatch.setattr(model_service, "FINAL_METRICS_PATH", tmp_path / "metrics.json")
    monkeypatch.setattr(model_service, "load_model_bundle", lambda: {"threshold": 0.05, "features": ["amount", "velocity"]})

    response = model_service.current_model()

    assert response.model_name == "hist_gradient_boosting"
    assert response.threshold == 0.05
    assert response.feature_count == 2
