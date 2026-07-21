# FraudOps

FraudOps is a local fraud-operations platform for banking transaction risk scoring, analyst review, case management, and management reporting. It uses generated banking data only; no real customer records are required.

## What Works Today

- PostgreSQL 17 stores the banking, transaction, fraud, model, quality, and reporting schemas.
- A synthetic data generator creates customers, accounts, cards, devices, merchants, transactions, delayed fraud labels, and realistic fraud scenarios.
- Batch ingestion writes raw Parquet files, validates records, quarantines rejected rows, and records pipeline audit results.
- Feature engineering produces point-in-time-safe behavioural, device, merchant, and transaction features.
- Baseline models are trained with chronological splits and tracked with MLflow.
- A configurable rules engine combines model probability, rule signals, analyst capacity, and cost-sensitive decisioning.
- FastAPI exposes scoring, transaction lookup, alerts, cases, model metadata, and rules.
- The React analyst console provides alert queue, investigation, case management, customer timeline, and analyst workbench views.
- Power BI reporting views summarize executive, operations, rule, model, analyst, fraud-loss, and data-quality metrics.

## Local Runbook

Start PostgreSQL:

```powershell
docker compose up -d fraud-postgres
```

Activate Python and install dependencies:

```powershell
py -3.13 -m venv .venv
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


## Power BI Dashboard

The Power BI project lives at:

```text
reports/powerbi/FraudOps_v1.pbip
```

Version 1 includes these completed report pages:

- Executive Overview
- Fraud Operations
- Rule Performance
- Model Performance
- Analyst Performance
- Data Quality

The report connects to PostgreSQL through the `fraudops_reporting` schema on:

```text
Server: 127.0.0.1:55433
Database: fraudops
```

Screenshot exports are intentionally deferred for now. When screenshots are ready, save them in:

```text
reports/powerbi/screenshots/
```
## Current Boundaries

- The API currently stores live scored alerts and cases in a local SQLite file under `api/`.
- Power BI connects to PostgreSQL reporting views. Until API state is moved into PostgreSQL, the reporting views include seeded operational rows when PostgreSQL alert and case tables are empty.
- The project is ready for a local walkthrough, but production deployment work is still future scope: authentication, secrets management, CI, observability, API persistence migration, and hosted infrastructure.

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

