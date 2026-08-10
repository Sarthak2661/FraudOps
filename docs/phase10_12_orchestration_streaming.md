# Phase 10-12: Orchestration, Streaming, and Job Observability

## What Was Added

FraudOps now has a local v2 foundation for scheduled pipelines and event-based scoring experiments.

## Docker Compose Profiles

Use profiles so the laptop does not run every service at once:

- `core`: PostgreSQL only
- `airflow`: PostgreSQL, Airflow init, Airflow webserver, Airflow scheduler
- `streaming`: Kafka and Kafka UI
- `apps`: PostgreSQL plus app-facing database dependencies

## Airflow DAGs

DAG files live in `airflow/dags/`.

| DAG | Purpose | Schedule |
|---|---|---|
| `fraudops_batch_ingestion` | Raw-to-curated ingestion, schema validation, rejected rows, reconciliation | Daily |
| `fraudops_feature_generation` | Point-in-time feature snapshot generation and validation | Daily |
| `fraudops_model_training` | Training dataset validation, baseline training, MLflow artifact checks | Manual |
| `fraudops_threshold_optimization` | Threshold recommendation from validation model comparison | Manual |
| `fraudops_reporting_refresh` | Publish and validate PostgreSQL reporting views | Daily |

## Airflow Local Commands

Start Airflow:

```powershell
docker compose --profile airflow up -d fraud-postgres airflow-init airflow-webserver airflow-scheduler
```

Open Airflow:

```text
http://127.0.0.1:8080
```


Airflow dependency note: Airflow keeps its own Python environment clean. `airflow-init` creates `/opt/airflow/fraudops_venv` and installs FraudOps project dependencies there, so project packages such as SQLAlchemy 2.x do not overwrite Airflow's SQLAlchemy 1.4 requirement.
Default local login:

```text
Username: admin
Password: admin
```

Check scheduler logs:

```powershell
docker logs fraudops-airflow-scheduler --tail 100
```

Stop Airflow services:

```powershell
docker compose --profile airflow stop airflow-webserver airflow-scheduler
```

## Kafka Local Commands

Start Kafka and Kafka UI:

```powershell
docker compose --profile streaming up -d kafka kafka-ui
```

Open Kafka UI:

```text
http://127.0.0.1:8081
```

Create topics:

```powershell
docker exec fraudops-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic fraudops.transactions.raw
docker exec fraudops-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic fraudops.transactions.scored
docker exec fraudops-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --if-not-exists --topic fraudops.alerts.created
```

Publish sample transaction events:

```powershell
docker exec -i fraudops-kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic fraudops.transactions.raw < streaming/sample_transaction_events.jsonl
```

## Observability

Airflow provides the first local observability layer:

- DAG run status
- task retries
- task duration
- scheduler and task logs
- manual reruns and backfills
- persisted logs under `airflow/logs/`

Pipeline scripts also write validation artifacts under:

```text
data/curated/pipeline_runs/
reports/orchestration/
reports/modeling/
```

## When To Run What Locally

1. Start `core` when you only need PostgreSQL or Power BI refreshes.
2. Start `airflow` when you want scheduled ingestion, features, training, threshold, or reporting workflows.
3. Start `streaming` when you want to inspect Kafka topics and event payloads.
4. Start app servers separately when testing the analyst console and scoring API.

## Current Boundary

The Kafka profile proves the local broker, UI, topic design, and sample event path. The durable scoring consumer that reads Kafka events and calls FastAPI is intentionally left as the next implementation step so dependency and retry semantics can be designed cleanly.
