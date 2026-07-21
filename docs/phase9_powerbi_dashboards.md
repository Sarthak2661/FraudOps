# Phase 9: Power BI Dashboards

## Objective

Create management, operations, model-performance, analyst-performance, and data-quality reporting in Power BI from PostgreSQL reporting views.

## SQL Setup

Apply the reporting views:

```powershell
docker cp database\sql\004_powerbi_reporting_views.sql fraudops-postgres:/tmp/004_powerbi_reporting_views.sql
docker exec fraudops-postgres psql -v ON_ERROR_STOP=1 -U fraudops_user -d fraudops -f /tmp/004_powerbi_reporting_views.sql
```

## Power BI Connection

In Power BI Desktop:

1. Get Data -> PostgreSQL database
2. Server: `localhost:55433`
3. Database: `fraudops`
4. Import these views from `fraudops_reporting`:
   - `vw_daily_fraud_summary`
   - `vw_alert_operations`
   - `vw_case_performance`
   - `vw_analyst_productivity`
   - `vw_rule_performance`
   - `vw_model_performance`
   - `vw_fraud_loss`
   - `vw_data_quality`
   - `vw_source_to_curated_reconciliation`

Do not connect visuals directly to the normalized operational tables.

## Dashboard Pages

### Executive Overview

Cards:

- Attempted fraud value
- Prevented fraud value
- Confirmed fraud loss
- Fraud-value capture rate
- False-positive rate
- Cases awaiting review

Charts:

- Daily attempted fraud value
- Daily fraud rate
- Fraud loss by merchant category

### Fraud Operations

Visuals:

- Alert volume by day
- Alert ageing distribution
- SLA breaches
- Case backlog
- Average investigation time
- Cases by status

Useful filters:

- Date
- Alert status
- Priority
- Assigned analyst

### Rule Performance

Visuals:

- Alerts by rule
- Confirmed fraud by rule
- False-positive rate by rule
- Estimated prevented loss by rule

Useful filters:

- Rule severity
- Rule active flag
- Date

### Model Performance

Visuals:

- Precision
- Recall
- PR-AUC
- ROC-AUC
- Fraud-value recall
- Model-version comparison table

Useful filters:

- Model name
- Version label
- Promotion status

### Analyst Performance

Visuals:

- Cases handled
- Average resolution time
- SLA compliance
- Assigned case backlog

Useful filters:

- Analyst
- Case status
- Priority

### Data Quality

Visuals:

- Failed rules
- Rejected records
- Missing field failures
- Pipeline freshness
- Source-to-curated reconciliation

Useful filters:

- Pipeline run
- Quality dimension
- Passed flag

## Screenshot Folder

Save Power BI screenshots here:

```text
reports/powerbi/screenshots/
```

Suggested files:

- `executive_overview.png`
- `fraud_operations.png`
- `rule_performance.png`
- `model_performance.png`
- `analyst_performance.png`
- `data_quality.png`


## Reporting Data Note

The API analyst console currently stores live scored alerts and cases in `api/fraudops_api.db`, while Power BI connects to PostgreSQL. Until Phase 11+ moves API state into PostgreSQL, `vw_alert_operations` and `vw_case_performance` include seeded reporting rows derived from the transaction risk signals whenever the PostgreSQL operational alert/case tables are empty.

Use the `source_system` column to distinguish:

- `operational`: rows from PostgreSQL operational tables
- `seeded_reporting_data`: management reporting rows derived from synthetic transaction risk signals

Latest validated row counts:

- Alert operations rows: `300`
- Case performance rows: `222`
- Analyst productivity rows: `3`
- Daily fraud summary rows: `61`
- Fraud loss rows: `10,000`
- Data quality rows: `10`
- Model performance rows: `1`
## Definition of Done Status

- Reporting views created in PostgreSQL: complete
- Metrics reconcile with SQL: complete
- Metric dictionary included: complete
- Dashboard page design documented: complete
- Power BI PBIX and screenshots: manual step in Power BI Desktop



