# FraudOps

[![CI](https://github.com/Sarthak2661/FraudOps/actions/workflows/ci.yml/badge.svg)](https://github.com/Sarthak2661/FraudOps/actions/workflows/ci.yml)

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

Version 2 local scaffolding includes Airflow DAGs, Kafka, Kafka UI, and job-observability runbooks.

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

Full local instructions are in `docs/phase10_12_orchestration_streaming.md`.

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

## Documentation Map

- `docs/phase2_database_and_synthetic_data.md`: schema and data generation
- `docs/phase3_batch_ingestion_quality.md`: ingestion, validation, rejected records, and pipeline audit
- `docs/phase4_exploration_features.md`: exploratory analysis and point-in-time features
- `docs/feature_dictionary.md`: feature definitions and leakage notes
- `docs/phase5_baseline_models_mlflow.md`: model training and experiment tracking
- `docs/phase6_rules_decision_engine.md`: rules, risk scores, and decisions
- `docs/phase7_fastapi_service.md`: API endpoints and scoring flow
- `docs/phase8_react_analyst_console.md`: analyst console pages
- `docs/phase9_powerbi_dashboards.md`: dashboard pages and reporting views
- `docs/powerbi_metric_dictionary.md`: metric definitions and SQL lineage
- `docs/release_plan.md`: version 1, 2, and 3 scope
- `docs/security_notes.md`: local security assumptions and deployment controls

## License

MIT License. See LICENSE.
