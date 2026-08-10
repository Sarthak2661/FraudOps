# Power BI Metric Dictionary

## Connection

Use PostgreSQL as the Power BI source.

- Server: `localhost:55433`
- Database: `fraudops`
- User: `fraudops_user`
- Password: `fraudops_password`
- Reporting schema: `fraudops_reporting`

Connect Power BI to reporting views, not normalized operational tables.

## Reporting Views

| View | Grain | Purpose |
|---|---|---|
| `vw_daily_fraud_summary` | One row per transaction date | Executive fraud value and rate trends |
| `vw_alert_operations` | One row per alert | Alert queue, SLA, ageing, analyst assignment |
| `vw_case_performance` | One row per case | Case backlog and investigation cycle time |
| `vw_analyst_productivity` | One row per analyst | Analyst throughput and SLA compliance |
| `vw_rule_performance` | One row per rule | Rule trigger volume, confirmed fraud, false positives |
| `vw_model_performance` | One row per model version | Model precision, recall, PR-AUC, ROC-AUC, artifact lineage |
| `vw_fraud_loss` | One row per transaction | Attempted fraud, prevented loss, confirmed loss |
| `vw_data_quality` | One row per pipeline quality check | Failed rules, rejected records, freshness |
| `vw_source_to_curated_reconciliation` | One row per pipeline run | Source-to-curated row-count reconciliation |

## Executive Overview Metrics

| Metric | Definition | Source |
|---|---|---|
| Attempted fraud value | Sum of transaction amount where `fraud_label = 'fraud'` | `vw_daily_fraud_summary.attempted_fraud_value` |
| Prevented fraud value | Fraud value with a friction decision: step-up, review, hold, or decline | `vw_daily_fraud_summary.prevented_fraud_value` |
| Confirmed fraud loss | Fraud value approved without intervention | `vw_daily_fraud_summary.confirmed_fraud_loss` |
| Fraud-value capture rate | `prevented_fraud_value / attempted_fraud_value` | `vw_daily_fraud_summary.fraud_value_capture_rate` |
| False-positive rate | Legitimate transactions receiving friction decisions divided by legitimate transactions | `vw_daily_fraud_summary.false_positive_rate` |
| Cases awaiting review | Open or escalated cases | `vw_case_performance.case_status` |

## Fraud Operations Metrics

| Metric | Definition | Source |
|---|---|---|
| Alert volume | Count of alerts opened | `vw_alert_operations.alert_id` |
| Alert ageing | Minutes since alert opened | `vw_alert_operations.alert_age_minutes` |
| SLA breaches | Open alerts past SLA deadline | `vw_alert_operations.sla_breached` |
| Case backlog | Cases not closed | `vw_case_performance.case_status` |
| Average investigation time | Average hours from case open to close | `vw_case_performance.investigation_hours` |
| Cases by status | Count grouped by status | `vw_case_performance.case_status` |

## Rule Performance Metrics

| Metric | Definition | Source |
|---|---|---|
| Alerts by rule | Triggered rule count | `vw_rule_performance.triggered_count` |
| Confirmed fraud by rule | Triggered records with confirmed fraud label | `vw_rule_performance.confirmed_fraud_count` |
| False-positive rate by rule | Non-fraud triggered records divided by triggered records | `vw_rule_performance.false_positive_rate` |
| Estimated prevented loss by rule | Fraud amount associated with triggered rule | `vw_rule_performance.estimated_prevented_loss` |

## Model Performance Metrics

| Metric | Definition | Source |
|---|---|---|
| Precision | True positives divided by predicted positives | `vw_model_performance.precision` |
| Recall | True positives divided by actual positives | `vw_model_performance.recall` |
| PR-AUC | Area under precision-recall curve | `vw_model_performance.pr_auc` |
| Fraud-value recall | Fraud dollar value captured by model decisions | `vw_model_performance.fraud_value_recall` |
| Score distribution | Histogram of prediction scores | Later: `model_prediction.fraud_probability` or API score store |
| Model-version comparison | Compare model rows over version labels | `vw_model_performance.version_label` |

## Analyst Performance Metrics

| Metric | Definition | Source |
|---|---|---|
| Cases handled | Assigned cases by analyst | `vw_analyst_productivity.assigned_cases` |
| Average resolution time | Mean resolved case hours | `vw_analyst_productivity.avg_resolution_hours` |
| Confirmed fraud rate | Confirmed fraud outcomes divided by resolved cases | Later: case outcome feedback |
| SLA compliance | Cases resolved within 24 hours divided by resolved cases | `vw_analyst_productivity.sla_compliance_rate` |

## Data Quality Metrics

| Metric | Definition | Source |
|---|---|---|
| Failed rules | Count or sum of failed quality checks | `vw_data_quality.failed_records` |
| Rejected records | Records quarantined during ingestion | `vw_data_quality.rejected_records` |
| Missing fields | Completeness rule failures | `vw_data_quality.dimension = 'Completeness'` |
| Pipeline freshness | Hours since pipeline completed | `vw_data_quality.hours_since_refresh` |
| Source-to-curated reconciliation | Whether input equals accepted plus rejected | `vw_source_to_curated_reconciliation.reconciled` |


## Source System Field

Operational reporting views may include `source_system`:

- `operational`: records came from PostgreSQL operational tables.
- `seeded_reporting_data`: records were derived from the synthetic transaction dataset so Power BI pages can be developed before API state is moved into PostgreSQL.
## Validated Current Values

As of the Phase 9 validation run:

- Transactions: `10,000`
- Confirmed fraud transactions: `200`
- Attempted fraud value: `$52,188.88`
- Rejected records: `0`
- Failed data-quality records: `0`
- Source-to-curated reconciliation: `true`
