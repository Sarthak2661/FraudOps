# FraudOps Streaming Path

The streaming profile provides a local Kafka broker and Kafka UI for event-based transaction scoring experiments.

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

Consume sample events:

```powershell
docker exec fraudops-kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic fraudops.transactions.raw --from-beginning --max-messages 3
```

## Scoring Worker Status

Version 2 includes the local Kafka broker, topic conventions, sample events, and Kafka UI. A durable Python consumer that reads `fraudops.transactions.raw`, calls FastAPI `/v1/transactions/score`, and publishes scored responses is the next implementation step.
