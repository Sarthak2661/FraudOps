from __future__ import annotations

from streaming.score_transactions_consumer import build_score_payload, build_scored_event, score_event


class DummyResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.body


class DummyClient:
    def __init__(self):
        self.requests = []

    def post(self, url, json, headers):
        self.requests.append({"url": url, "json": json, "headers": headers})
        return DummyResponse(
            {
                "transaction_id": json["transaction_id"],
                "risk_score": 0.84,
                "decision": "MANUAL_REVIEW",
                "triggered_rules": ["R001"],
                "estimated_exposure": 920.0,
                "correlation_id": headers["x-correlation-id"],
                "alert_id": "alert-001",
            }
        )


def test_build_score_payload_strips_non_api_fields() -> None:
    payload = build_score_payload(
        {
            "event_id": "evt-001",
            "transaction_id": "stream-txn-001",
            "customer_id": "cust-001",
            "amount": 920.0,
            "currency": "USD",
            "model_probability_override": 0.99,
        }
    )

    assert payload == {
        "transaction_id": "stream-txn-001",
        "customer_id": "cust-001",
        "amount": 920.0,
        "currency": "USD",
    }


def test_score_event_calls_public_scoring_endpoint_with_api_key() -> None:
    client = DummyClient()
    response = score_event(
        {"event_id": "evt-001", "transaction_id": "stream-txn-001", "amount": 920.0},
        api_base_url="http://127.0.0.1:8000/",
        api_key="local-key",
        client=client,
    )

    assert response["decision"] == "MANUAL_REVIEW"
    assert client.requests[0]["url"] == "http://127.0.0.1:8000/v1/transactions/score"
    assert client.requests[0]["headers"]["x-api-key"] == "local-key"
    assert client.requests[0]["headers"]["x-correlation-id"] == "evt-001"


def test_build_scored_event_keeps_alert_context() -> None:
    scored = build_scored_event(
        {"event_id": "evt-001", "customer_id": "cust-001"},
        {
            "transaction_id": "stream-txn-001",
            "risk_score": 0.84,
            "decision": "MANUAL_REVIEW",
            "triggered_rules": ["R001"],
            "estimated_exposure": 920.0,
            "correlation_id": "evt-001",
            "alert_id": "alert-001",
        },
    )

    assert scored["event_id"] == "evt-001"
    assert scored["customer_id"] == "cust-001"
    assert scored["alert_id"] == "alert-001"
    assert scored["triggered_rules"] == ["R001"]
