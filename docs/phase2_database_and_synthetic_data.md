# Phase 2: Database and Synthetic Data

## Objective

Create a realistic synthetic banking transaction dataset without real customer data.

## Database Entities

Phase 2 covers these entity groups:

- Customer and banking: `customer`, `account`, `card`, `device`, `merchant`, `transaction`
- Fraud: `fraud_rule`, `rule_execution`, `model_prediction`, `fraud_decision`, `fraud_alert`
- Investigation: `fraud_case`, `case_alert`, `case_action`, `fraud_feedback`
- Platform: `pipeline_run`, `data_quality_rule`, `data_quality_result`, `model_version`, `threshold_configuration`

## Start PostgreSQL

```powershell
cd FraudOps
docker compose up -d fraud-postgres
docker compose ps
```

Connect with:

```powershell
psql -h localhost -p 55433 -U fraudops_user -d fraudops
```

The Docker container loads `database/sql/001_initial_schema.sql` on first database initialization. For migration-driven setup, install requirements and run:

```powershell
alembic upgrade head
```

## Generate Synthetic Data

Small reproducible dataset:

```powershell
python scripts/generate_synthetic_data.py --seed 42 --customers 500 --transactions 10000 --output-dir data/sample
```

Larger dataset after the flow is stable:

```powershell
python scripts/generate_synthetic_data.py --seed 42 --customers 5000 --transactions 100000 --days 90 --output-dir data/raw
```

Optional database load after PostgreSQL is running and `psycopg` is installed:

```powershell
python scripts/generate_synthetic_data.py --seed 42 --customers 500 --transactions 10000 --output-dir data/sample --load-db
```

## Fraud Scenarios

The generator creates both fraud and legitimate behavior, including:

- Card testing
- Impossible travel
- New-device takeover
- Transaction velocity
- Behavior deviation
- Merchant fraud burst
- Normal travel false positives

Delayed fraud labels are modeled with `fraud_label`, `label_source`, `label_available_at`, `chargeback_date`, and `analyst_confirmed_at`.


## Docker Pull Note

If `postgres:17` fails to pull with a Docker Hub or CloudFront `EOF` error, use the smaller Alpine image already configured in `docker-compose.yml`:

```yaml
image: postgres:17-alpine
```

## Load Sample CSVs Through Docker

If Python dependencies are not installed yet, load the generated CSVs through the running container:

```powershell
docker cp .\data\sample fraudops-postgres:/tmp/fraudops-sample
docker cp .\database\sql\002_load_sample_data.sql fraudops-postgres:/tmp/002_load_sample_data.sql
docker exec fraudops-postgres psql -v ON_ERROR_STOP=1 -U fraudops_user -d fraudops -f /tmp/002_load_sample_data.sql
```
## Definition of Done

- Database tables exist
- Synthetic records load successfully
- Foreign-key relationships work
- Fraud and legitimate transactions are present
- Fraud scenarios can be explained
- Data generation is reproducible using a random seed
