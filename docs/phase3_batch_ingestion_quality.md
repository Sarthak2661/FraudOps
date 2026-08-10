# Phase 3: Batch Ingestion and Data Quality

## Objective

Create a repeatable raw-to-curated transaction pipeline with an auditable quality trail.

## Data Layers

- Raw: immutable Parquet partitions under `data/raw/transactions/year=YYYY/month=MM/day=DD/`
- Validated: accepted transaction records under `data/validated/transactions/pipeline_run_id=.../`
- Rejected: quarantined records with reasons under `data/rejected/transactions/pipeline_run_id=.../`
- Curated: analytical features and pipeline audit outputs under `data/curated/`

## Run the Pipeline

```powershell
cd FraudOps
python scripts/run_batch_ingestion.py
```

Useful fixed-run example:

```powershell
python scripts/run_batch_ingestion.py --pipeline-run-id phase3_full_002
```

## Validation Checks

The pipeline checks:

- Required fields are present
- Transaction IDs are unique
- Amounts are numeric and positive
- Currency codes are allowed
- Timestamps are parseable, not future-dated, and not unexpectedly old
- Customers, accounts, cards, devices, and merchants exist
- Channels and transaction statuses use allowed values
- Card/account relationships are consistent

## Audit Outputs

Each run writes:

- `data/curated/pipeline_runs/pipeline_runs.csv`
- `data/curated/pipeline_runs/pipeline_summary_<pipeline_run_id>.json`
- `data/curated/pipeline_runs/quality_results_<pipeline_run_id>.parquet`

Database DDL for audit tables is in:

```text
database/sql/003_phase3_batch_audit.sql
```

## Latest Verified Run

Run ID: `phase3_full_002`

- Input records: 10,000
- Accepted records: 10,000
- Rejected records: 0
- Duplicate records: 0
- Curated feature records: 10,000
- Raw Parquet partitions: 61

## Definition of Done

For each batch, the project can answer:

- How many records arrived?
- How many passed?
- How many failed?
- Why did records fail?
- Which pipeline run produced the curated data?
