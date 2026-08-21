# FraudOps Streaming Path

The streaming profile provides a local Kafka broker, Kafka UI, and a Python scoring consumer for event-based transaction scoring experiments.

## Topics

Recommended topics:

- `fraudops.transactions.raw`: inbound transaction events
- `fraudops.transactions.scored`: scored transaction responses
- `fraudops.alerts.created`: alerts created by the scoring API

## Start Locally

```powershell
docker compose --profile streaming up -d kafka kafka-ui
```

Open Kafka UI:

```text
http://127.0.0.1:8081
```

Create or inspect topics in Kafka UI, or use the Kafka container CLI:

```powershell
docker exec fraudops-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic fraudops.transactions.raw
docker exec fraudops-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic fraudops.transactions.scored
docker exec fraudops-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic fraudops.alerts.created
```

Publish sample events:

```powershell
docker exec -i fraudops-kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic fraudops.transactions.raw < streaming/sample_transaction_events.jsonl
```

Run the scoring consumer in another terminal while the FastAPI service is running:

```powershell
$env:FRAUDOPS_API_BASE_URL="http://127.0.0.1:8000"
python streaming\score_transactions_consumer.py --max-messages 3
```

If the API is protected with `FRAUDOPS_API_KEY`, set the same value before starting the consumer:

```powershell
$env:FRAUDOPS_API_KEY="replace-with-local-demo-key"
```

Consume scored events:

```powershell
docker exec fraudops-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic fraudops.transactions.scored --from-beginning --max-messages 3
```

Consume alert events:

```powershell
docker exec fraudops-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic fraudops.alerts.created --from-beginning --max-messages 3
```

## Scoring Worker

`streaming/score_transactions_consumer.py` reads `fraudops.transactions.raw`, calls FastAPI `/v1/transactions/score`, publishes scored responses to `fraudops.transactions.scored`, and publishes alert-created events to `fraudops.alerts.created` when scoring creates an alert.

The worker strips non-API fields such as `event_id` and `model_probability_override` before calling the public scoring endpoint, so Kafka events use the same request validation and API-key boundary as direct HTTP scoring.
