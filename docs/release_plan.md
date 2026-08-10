# Release Plan

## Version 1: Fraud Operations MVP

Version 1 is the current local product. It proves the end-to-end fraud operations workflow without relying on real customer data.

Included scope:

- Synthetic banking transaction data with realistic fraud scenarios and delayed labels
- PostgreSQL schema, migrations, and seed/load scripts
- Raw, validated, curated, and analytical feature data layers
- Data-quality checks, rejected-record handling, and pipeline run audit records
- Point-in-time-safe feature engineering
- Baseline model training with chronological splits and MLflow experiment tracking
- Rules and cost-sensitive decision engine
- FastAPI scoring, alert, case, model, and rule endpoints
- React analyst console for queue, investigation, case, timeline, and workbench flows
- PostgreSQL reporting views for Power BI management reporting, including API alert/case bridge rows
- Documentation, metric dictionary, tests, and local runbook

Version 1 readiness checklist:

- Tests pass locally
- Frontend builds locally
- API health and Swagger docs respond locally
- Scoring is idempotent by `transaction_id`
- Invalid API requests return structured validation errors
- Power BI reporting views return rows from PostgreSQL
- Generated data, local databases, dependencies, and model binaries are excluded from git

Known limits:

- Power BI Desktop refresh and screenshots are manual
- Authentication, role-based permissions, deployment, and monitoring are future scope

## Version 2: Orchestration and Streaming Foundation

Version 2 adds the local orchestration and streaming foundation for phases 10-12.

Included scope:

- Airflow orchestration through Docker Compose profiles
- Scheduled or manual DAGs for ingestion, features, training, threshold optimization, and reporting
- Local Kafka and Kafka UI profile with topic conventions and sample transaction events
- Event-style scoring path documented through Kafka topics and JSONL sample events
- Airflow UI, retries, task logs, and pipeline validation artifacts for scheduled-job observability
- README screenshots for Airflow and streaming workflows

## Version 3: Feedback, CI, Security, and AWS Deployment

Version 3 should cover phases 13-15.

Planned scope:

- Analyst feedback loop and validated training labels
- Monitoring for data drift, prediction drift, and performance drift
- Champion-challenger model comparison and auditable promotion
- Broader unit, data, integration, and regression tests
- Expand GitHub Actions with coverage, dependency scanning, and Docker checks
- Security assumptions and controls documented
- AWS deployment with S3, EC2, optional RDS, CloudWatch, and Terraform

Promotion rule:

- Do not promote a new model automatically. Require a manual approval step after comparing challenger results against the current champion model on the same recent dataset.
