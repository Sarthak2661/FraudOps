# FraudOps Development Roadmap

## Core Recommendation

Build FraudOps in four major milestones:

1. Batch fraud analytics MVP
2. Fraud operations and case-management application
3. Real-time Kafka and MLOps platform
4. AWS production-style deployment

Do not begin with Kafka, Airflow, AWS deployment, and many Docker containers at the same time. First make fraud detection, decisioning, and analyst workflow work locally. Then add orchestration, streaming, cloud, and production polish.

## Confirmed Local Tooling

Use this project baseline:

- IDE: Visual Studio Code
- Python: use Python 3.13 for the project virtual environment
- Python 3.14: can remain installed, but do not use it as the project runtime yet
- PostgreSQL client/server target: PostgreSQL 16 or 17 are both acceptable
- Power BI: Power BI Desktop for local `.pbix` dashboards
- Git workflow: Git CLI plus GitHub Desktop if preferred

Python 3.13 is the safer runtime because third-party package compatibility is broader. Keep Python 3.14 installed only for experimentation until your main dependencies explicitly support it well.

## Corrected Phase Plan

The original phases are broadly correct. I would keep the same overall direction, but slightly reorder and clarify them so every phase produces a runnable outcome.

| Phase | Main result | Notes |
|---:|---|---|
| 0 | Business and technical design | Define users, decisions, KPIs, outcomes, architecture, and roadmap. |
| 1 | Development environment | Create `FraudOps`, Git repo, Python 3.13 venv, VS Code settings, `.env.example`, `.gitignore`, and baseline tests. |
| 2 | Database and synthetic data | Stand up PostgreSQL 16/17 locally, create schema, generate realistic transactions, customers, merchants, cards, and labels. |
| 3 | Batch ingestion and data quality | Load raw data, validate it, quarantine bad rows, and create curated tables. |
| 4 | Fraud features and exploratory analysis | Build features, profile fraud patterns, and document leakage risks. |
| 5 | Rules and cost-sensitive decisioning | Add baseline fraud rules, thresholds, alert routing, and business cost logic before ML. |
| 6 | ML models and MLflow | Train models, track experiments, compare against rules, and register candidate models. |
| 7 | FastAPI scoring service | Expose transaction scoring and decisioning through an API. |
| 8 | Analyst queue and case management | Build alert queue, case notes, assignments, statuses, SLA fields, and analyst resolutions. |
| 9 | Power BI dashboards | Connect Power BI Desktop to PostgreSQL and report fraud, false positives, backlog, SLA, and losses. |
| 10 | Airflow orchestration | Orchestrate batch ingestion, validation, feature builds, training, and reporting jobs. Use Docker/WSL2/Linux containers, not native Windows Airflow. |
| 11 | AWS S3 integration | Store raw, validated, curated, and model artifacts in S3. Add IAM, AWS CLI, and budgets early. |
| 12 | Kafka real-time processing | Add local Docker Kafka producers/consumers after the batch and API flows are stable. |
| 13 | Feedback, drift, and monitoring | Feed analyst outcomes back into training data, monitor model drift, data drift, queue health, and decision performance. |
| 14 | Testing, security, and CI/CD | Add unit/integration/API tests, Ruff, secrets handling, GitHub Actions, and security checks. |
| 15 | AWS deployment and production-style completion | Deploy selected services using EC2/ECR/RDS/S3/CloudWatch/Terraform as a production-style deployment version. |

## Important Adjustment

Move rules and cost-sensitive decisioning before ML. Fraud platforms need a transparent baseline before modeling. This lets you compare ML against business rules and gives the API/case-management workflow a usable decision engine even before the model is mature.

## Recommended Stack Choices

### Python

Use:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### PostgreSQL

Use PostgreSQL 16 or 17. Both are fine for this project. If Docker is available, run PostgreSQL through Docker Compose so the environment is reproducible. If using a local install, keep the schema and migrations in the repo.

### Airflow

Do not install Airflow directly into Windows Python. Use Docker, WSL2, or Linux containers. Add Airflow only after the batch pipeline works manually.

### Kafka

Use local Docker Kafka. Do not start with Amazon MSK. Document MSK as a target architecture option, but avoid its cost for a local development project.

### Power BI

Use Power BI Desktop locally. Keep the final `.pbix` file tracked if it is part of the final deliverable, but ignore temporary Power BI files such as `*.pbix~`.

### AWS

Use early:

- S3
- IAM
- AWS CLI
- AWS Budgets

Add near completion:

- RDS for PostgreSQL
- EC2
- ECR
- CloudWatch
- Terraform

Avoid initially:

- MSK
- MWAA
- SageMaker
- EKS

## Target Timeline

At 10-12 focused hours per week, 14-18 weeks is realistic. Each milestone should leave you with a runnable outcome, so the project still looks strong even before every advanced layer is complete.

## First Commands

```powershell
cd C:\Users\sarth\Documents\FraudOps
git init
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Then verify:

```powershell
python --version
git --version
docker --version
docker compose version
psql --version
```

Expected Python result:

```text
Python 3.13.x
```

## Phase 1 Definition of Done

- `FraudOps` folder exists
- Git repository exists
- Python 3.13 virtual environment works
- VS Code opens the folder cleanly
- `.env.example` exists and `.env` is ignored
- Docker works locally
- PostgreSQL 16 or 17 is reachable
- A basic `pytest` command runs successfully
- First commit is created

Suggested commit:

```powershell
git add .
git commit -m "chore: initialize FraudOps project structure"
```

