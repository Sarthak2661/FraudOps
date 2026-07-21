# Changelog

## 1.0.0 - Fraud Operations MVP

Version 1 is the local FraudOps MVP covering phases 2-9.

Included:

- Synthetic banking data generation and PostgreSQL schema
- Batch ingestion, validation, quarantine, and audit outputs
- Point-in-time-safe behavioural feature engineering
- Baseline ML training with chronological splits and MLflow tracking
- Configurable rules and cost-sensitive decisioning
- FastAPI scoring, alert, case, model, and rule endpoints
- React analyst console
- Power BI reporting views and metric dictionary
- Tests, README runbook, release plan, and security notes

Deferred:

- Version 2: phases 10-12, including Airflow orchestration and streaming foundation
- Version 3: phases 13-15, including feedback, monitoring, CI/security, and AWS deployment
