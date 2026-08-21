# FraudOps

[![CI](https://github.com/Sarthak2661/FraudOps/actions/workflows/ci.yml/badge.svg)](https://github.com/Sarthak2661/FraudOps/actions/workflows/ci.yml)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue)](https://www.python.org/)
[![PostgreSQL 17](https://img.shields.io/badge/postgresql-17-4169E1)](https://www.postgresql.org/)
[![Dependencies Pinned](https://img.shields.io/badge/dependencies-pinned-brightgreen)](requirements.txt)
[![Security Audit](https://img.shields.io/badge/security-pip--audit-brightgreen)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

FraudOps is a local fraud-operations platform for banking transaction risk scoring, analyst review, case management, and management reporting. It uses generated banking data only; no real customer records are required.

## What Works Today

- PostgreSQL 17 stores the banking, transaction, fraud, model, quality, and reporting schemas.
- A synthetic data generator creates customers, accounts, cards, devices, merchants, transactions, delayed fraud labels, and realistic fraud scenarios.
- Batch ingestion writes raw Parquet files, validates records, quarantines rejected rows, and records pipeline audit results.
- Feature engineering produces point-in-time-safe behavioural, device, merchant, and transaction features.
- Baseline models are trained with chronological splits and tracked with MLflow.
- A configurable rules engine combines model probability, rule signals, analyst capacity, and cost-sensitive decisioning.
- FastAPI exposes scoring, transaction lookup, alerts, cases, model metadata, and rules, with API scoring state stored in PostgreSQL by default.
- The React analyst console provides alert queue, investigation, case management, customer timeline, and analyst workbench views.
- Power BI reporting views summarize executive, operations, rule, model, analyst, fraud-loss, and data-quality metrics.
- Airflow includes a single end-to-end container DAG for ingestion, features, training, threshold optimization, and reporting.
- Kafka includes a local scoring consumer that calls FastAPI and publishes scored and alert-created events.

## Current Boundaries

- The API stores live scored transactions, alerts, and cases in PostgreSQL by default through `FRAUDOPS_API_DATABASE_URL`.
- SQLite is still available for isolated tests or lightweight local runs by setting FRAUDOPS_API_DATABASE_URL=sqlite:///api/fraudops_api.db.
- Power BI connects to PostgreSQL reporting views. Alert and case views now combine warehouse operational rows, API operational rows, and seeded reporting rows when both operational sources are empty.
- Model binaries are intentionally excluded from Git. After a fresh clone, run `python scripts\train_baseline_models.py` before relying on model-backed scoring artifacts. `/v1/models/current` reports whether scoring is using a trained artifact or fallback probability.
- The project is ready for a local walkthrough, but production deployment work is still future scope: authentication, secrets management, production observability, fully unified production reporting, and hosted infrastructure.

## Architecture

```mermaid
flowchart LR
    A["Synthetic banking data"] --> B["Raw parquet batches"]
    B --> C["Validation and quarantine"]
    C --> D["Curated PostgreSQL tables"]
    D --> E["Point-in-time features"]
    E --> F["Baseline ML models and MLflow"]
    E --> G["Configurable rules engine"]
    F --> H["Cost-sensitive decisioning"]
    G --> H
    H --> I["FastAPI scoring service"]
    I --> J["React analyst console"]
    D --> K["Power BI reporting views"]
    H --> K
```

## Local Runbook

Prerequisites:

- Docker Desktop running before any `docker compose` command
- Python 3.14
- Node.js 24 with `npm.cmd`
- Power BI Desktop for the reporting project

Start PostgreSQL:

```powershell
docker compose up -d fraud-postgres
```

Activate Python and install dependencies:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use this for the current terminal session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Run the API:

```powershell
$env:FRAUDOPS_API_DATABASE_URL="postgresql+psycopg://fraudops_user:fraudops_password@127.0.0.1:55433/fraudops"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Optional local API-key boundary:

```powershell
$env:FRAUDOPS_API_KEY="replace-with-local-demo-key"
```

Open the API docs at:

```text
http://127.0.0.1:8000/docs
```

Run the analyst console:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the console at the Vite URL, usually:

```text
http://127.0.0.1:5173/
```

If that port is already busy, Vite will print the next available URL.

## Local Runbook For macOS/Linux

Start PostgreSQL:

```bash
docker compose up -d fraud-postgres
```

Create and activate Python:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the API:

```bash
export FRAUDOPS_API_DATABASE_URL="postgresql+psycopg://fraudops_user:fraudops_password@127.0.0.1:55433/fraudops"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Run the analyst console:

```bash
cd frontend
npm ci
npm run dev
```

## Useful Checks

Run tests:

```powershell
python -m pytest tests -q
```

Run CI checks locally:

```powershell
python -m pip install pip-audit==2.10.1
pip-audit -r requirements.txt --ignore-vuln PYSEC-2026-3552
ruff check .
python -m pytest tests -q
cd frontend
npm.cmd ci
npm.cmd run build
```

Train baseline models:

```powershell
python scripts\train_baseline_models.py
```

Apply Power BI reporting views:

```powershell
docker cp database\sql\004_powerbi_reporting_views.sql fraudops-postgres:/tmp/004_powerbi_reporting_views.sql
docker exec fraudops-postgres psql -v ON_ERROR_STOP=1 -U fraudops_user -d fraudops -f /tmp/004_powerbi_reporting_views.sql
```

Connect Power BI Desktop to PostgreSQL:

```text
Server: 127.0.0.1:55433
Database: fraudops
Schema: fraudops_reporting
```


## Orchestration And Streaming

Version 2 local scaffolding includes Airflow DAGs, Kafka, Kafka UI, a Python Kafka scoring consumer, and job-observability runbooks.

Start Airflow when you want scheduled pipeline runs:

```powershell
docker compose --profile airflow up -d fraud-postgres airflow-init airflow-webserver airflow-scheduler
```

Open Airflow:

```text
http://127.0.0.1:8080
```

Start Kafka and Kafka UI when you want the event-based scoring path:

```powershell
docker compose --profile streaming up -d kafka kafka-ui
```

Open Kafka UI:

```text
http://127.0.0.1:8081
```

Run the local Kafka scoring worker after publishing sample raw events:

```powershell
python streaming\score_transactions_consumer.py --max-messages 3
```

Run the full Airflow pipeline inside the Airflow container:

```powershell
docker compose --profile airflow run --rm airflow-scheduler airflow dags test fraudops_full_pipeline 2026-08-22
```

Full local instructions are in `docs/phase10_12_orchestration_streaming.md`.

Local verification has been run against the Compose profiles. The Airflow DAGs import, execute with task logs and retry history, and the Kafka path publishes scored and alert-created events after calling the FastAPI scoring API.

## Power BI Dashboard

The Power BI project lives at:

```text
reports/powerbi/FraudOps_v1.pbip
```

Version 1 includes these completed report pages:

- Executive Overview
- Fraud Operations
- Model Performance
- Analyst Performance
- Data Quality

Rule Performance is implemented in the report, but its screenshot is intentionally excluded from the README until the refreshed visual is re-exported with non-zero rule metrics.

The report connects to PostgreSQL through the `fraudops_reporting` schema on:

```text
Server: 127.0.0.1:55433
Database: fraudops
```

Screenshot exports are saved in:

```text
reports/powerbi/screenshots/
```

### Dashboard Screenshots

Executive Overview

![Executive Overview](reports/powerbi/screenshots/executive_overview.png)

Fraud Operations

![Fraud Operations](reports/powerbi/screenshots/fraud_operations.png)

Model Performance

![Model Performance](reports/powerbi/screenshots/model_performance.png)

Analyst Performance

![Analyst Performance](reports/powerbi/screenshots/analyst_performance.png)

Data Quality

![Data Quality](reports/powerbi/screenshots/data_quality.png)

## Application Screenshots

FastAPI Swagger Docs

![FastAPI Swagger Docs](reports/app_screenshots/fastapi_docs.png)

React Analyst Console

![React Analyst Console](reports/app_screenshots/react_analyst_console.png)

Airflow DAGs

![Airflow DAGs](reports/app_screenshots/airflow_dags.png)

Kafka UI

![Kafka UI](reports/app_screenshots/kafka_ui_topics.png)

## Documentation Map

- `docs/phase2_database_and_synthetic_data.md`: schema and data generation
- `docs/phase3_batch_ingestion_quality.md`: ingestion, validation, rejected records, and pipeline audit
- `docs/phase4_exploration_features.md`: exploratory analysis and point-in-time features
- `docs/feature_dictionary.md`: feature definitions and leakage notes
- `docs/data_card.md`: synthetic dataset scope, quality controls, and limitations
- `docs/model_card.md`: model scope, metrics, risks, and monitoring recommendations
- `docs/phase5_baseline_models_mlflow.md`: model training and experiment tracking
- `docs/phase6_rules_decision_engine.md`: rules, risk scores, and decisions
- `docs/phase7_fastapi_service.md`: API endpoints and scoring flow
- `docs/phase8_react_analyst_console.md`: analyst console pages
- `docs/phase9_powerbi_dashboards.md`: dashboard pages and reporting views
- `docs/powerbi_metric_dictionary.md`: metric definitions and SQL lineage
- `docs/release_plan.md`: version 1, 2, and 3 scope
- `docs/security_notes.md`: local security assumptions and deployment controls
- `docs/adr/0001-synthetic-data-only.md`: decision record for using generated data only

## License

MIT License. See LICENSE.
