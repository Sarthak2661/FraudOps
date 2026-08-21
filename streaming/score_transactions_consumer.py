from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from kafka import KafkaConsumer, KafkaProducer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

LOGGER = logging.getLogger("fraudops.streaming.scoring_consumer")
DEFAULT_BOOTSTRAP_SERVERS = "localhost:9092"
DEFAULT_RAW_TOPIC = "fraudops.transactions.raw"
DEFAULT_SCORED_TOPIC = "fraudops.transactions.scored"
DEFAULT_ALERT_TOPIC = "fraudops.alerts.created"
DEFAULT_GROUP_ID = "fraudops-scoring-consumer"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_API_TIMEOUT_SECONDS = 60.0

SCORE_REQUEST_FIELDS = {
    "transaction_id",
    "customer_id",
    "card_id",
    "account_id",
    "merchant_id",
    "device_id",
    "amount",
    "currency",
    "channel",
    "merchant_country",
    "transaction_at",
}


def build_score_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    payload = {field: event[field] for field in SCORE_REQUEST_FIELDS if field in event and event[field] is not None}
    missing = {"transaction_id", "amount"} - payload.keys()
    if missing:
        raise ValueError(f"Missing required scoring fields: {', '.join(sorted(missing))}")
    return payload


def build_scored_event(raw_event: Mapping[str, Any], score_response: Mapping[str, Any], source_topic: str = DEFAULT_RAW_TOPIC) -> dict[str, Any]:
    return {
        "event_id": raw_event.get("event_id"),
        "transaction_id": score_response["transaction_id"],
        "customer_id": raw_event.get("customer_id"),
        "source_topic": source_topic,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "risk_score": score_response["risk_score"],
        "decision": score_response["decision"],
        "alert_id": score_response.get("alert_id"),
        "triggered_rules": score_response.get("triggered_rules", []),
        "estimated_exposure": score_response.get("estimated_exposure"),
        "correlation_id": score_response.get("correlation_id"),
    }


def build_alert_event(scored_event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "alert_id": scored_event["alert_id"],
        "transaction_id": scored_event["transaction_id"],
        "customer_id": scored_event.get("customer_id"),
        "risk_score": scored_event["risk_score"],
        "decision": scored_event["decision"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "kafka_scoring_consumer",
    }


def score_event(
    event: Mapping[str, Any],
    api_base_url: str,
    api_key: str | None = None,
    client: httpx.Client | None = None,
    timeout_seconds: float = DEFAULT_API_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    payload = build_score_payload(event)
    correlation_id = str(event.get("event_id") or uuid.uuid4())
    headers = {"x-correlation-id": correlation_id}
    if api_key:
        headers["x-api-key"] = api_key

    owns_client = client is None
    active_client = client or httpx.Client(timeout=timeout_seconds)
    try:
        response = active_client.post(f"{api_base_url.rstrip('/')}/v1/transactions/score", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            active_client.close()


def _json_serializer(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _json_deserializer(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


def run_consumer(
    *,
    bootstrap_servers: str,
    raw_topic: str,
    scored_topic: str,
    alert_topic: str,
    group_id: str,
    api_base_url: str,
    api_key: str | None,
    api_timeout_seconds: float,
    max_messages: int | None,
    idle_timeout_seconds: int,
) -> int:
    consumer = KafkaConsumer(
        raw_topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        consumer_timeout_ms=idle_timeout_seconds * 1000,
        value_deserializer=_json_deserializer,
    )
    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=_json_serializer,
        key_serializer=lambda value: str(value).encode("utf-8") if value is not None else None,
    )

    processed = 0
    try:
        for message in consumer:
            raw_event = message.value
            score_response = score_event(
                raw_event,
                api_base_url=api_base_url,
                api_key=api_key,
                timeout_seconds=api_timeout_seconds,
            )
            scored_event = build_scored_event(raw_event, score_response, source_topic=raw_topic)
            producer.send(scored_topic, key=scored_event["transaction_id"], value=scored_event)
            if scored_event.get("alert_id"):
                producer.send(alert_topic, key=scored_event["alert_id"], value=build_alert_event(scored_event))
            producer.flush()
            consumer.commit()
            processed += 1
            LOGGER.info(
                "scored transaction_id=%s decision=%s alert_id=%s",
                scored_event["transaction_id"],
                scored_event["decision"],
                scored_event.get("alert_id"),
            )
            if max_messages is not None and processed >= max_messages:
                break
    finally:
        consumer.close()
        producer.close()
    return processed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consume raw Kafka transaction events and call FraudOps FastAPI scoring.")
    parser.add_argument("--bootstrap-servers", default=os.getenv("FRAUDOPS_KAFKA_BOOTSTRAP_SERVERS", DEFAULT_BOOTSTRAP_SERVERS))
    parser.add_argument("--raw-topic", default=os.getenv("FRAUDOPS_RAW_TOPIC", DEFAULT_RAW_TOPIC))
    parser.add_argument("--scored-topic", default=os.getenv("FRAUDOPS_SCORED_TOPIC", DEFAULT_SCORED_TOPIC))
    parser.add_argument("--alert-topic", default=os.getenv("FRAUDOPS_ALERT_TOPIC", DEFAULT_ALERT_TOPIC))
    parser.add_argument("--group-id", default=os.getenv("FRAUDOPS_STREAM_GROUP_ID", DEFAULT_GROUP_ID))
    parser.add_argument("--api-base-url", default=os.getenv("FRAUDOPS_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--api-key", default=os.getenv("FRAUDOPS_API_KEY"))
    parser.add_argument("--api-timeout-seconds", type=float, default=float(os.getenv("FRAUDOPS_API_TIMEOUT_SECONDS", DEFAULT_API_TIMEOUT_SECONDS)))
    parser.add_argument("--max-messages", type=int, default=None)
    parser.add_argument("--idle-timeout-seconds", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args()
    processed = run_consumer(
        bootstrap_servers=args.bootstrap_servers,
        raw_topic=args.raw_topic,
        scored_topic=args.scored_topic,
        alert_topic=args.alert_topic,
        group_id=args.group_id,
        api_base_url=args.api_base_url,
        api_key=args.api_key,
        api_timeout_seconds=args.api_timeout_seconds,
        max_messages=args.max_messages,
        idle_timeout_seconds=args.idle_timeout_seconds,
    )
    LOGGER.info("processed_messages=%s", processed)


if __name__ == "__main__":
    main()
