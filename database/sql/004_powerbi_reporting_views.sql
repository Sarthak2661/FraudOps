DROP VIEW IF EXISTS fraudops_reporting.vw_source_to_curated_reconciliation CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_data_quality CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_fraud_loss CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_model_performance CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_rule_performance CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_analyst_productivity CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_case_performance CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_alert_operations CASCADE;
DROP VIEW IF EXISTS fraudops_reporting.vw_daily_fraud_summary CASCADE;
CREATE SCHEMA IF NOT EXISTS fraudops_reporting;
CREATE TABLE IF NOT EXISTS public.scored_transactions (
    transaction_id text PRIMARY KEY,
    customer_id text,
    amount double precision NOT NULL,
    risk_score double precision NOT NULL,
    decision text NOT NULL,
    model_probability double precision NOT NULL,
    triggered_rules jsonb NOT NULL,
    explanation jsonb NOT NULL,
    estimated_exposure double precision NOT NULL,
    alert_id text,
    request_payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.alerts (
    alert_id text PRIMARY KEY,
    transaction_id text NOT NULL UNIQUE,
    customer_id text,
    amount double precision NOT NULL,
    risk_score double precision NOT NULL,
    decision text NOT NULL,
    priority integer NOT NULL,
    status text NOT NULL,
    assigned_analyst text,
    sla_deadline timestamptz NOT NULL,
    triggered_rules jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.cases (
    case_id text PRIMARY KEY,
    customer_id text,
    alert_ids jsonb NOT NULL,
    status text NOT NULL,
    priority integer NOT NULL,
    assigned_to text,
    case_summary text NOT NULL,
    outcome text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.case_actions (
    action_id text PRIMARY KEY,
    case_id text NOT NULL,
    actor text NOT NULL,
    action_type text NOT NULL,
    notes text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE VIEW fraudops_reporting.vw_daily_fraud_summary AS
WITH transaction_decisions AS (
    SELECT
        t.transaction_id,
        t.transaction_at,
        t.amount,
        t.fraud_label,
        t.fraud_scenario,
        CASE
            WHEN fd.outcome IS NOT NULL THEN fd.outcome::text
            WHEN t.fraud_label = 'fraud' AND abs(hashtext(t.transaction_id::text)) % 5 <> 0 THEN
                CASE WHEN t.amount >= 500 THEN 'HOLD_OR_DECLINE' ELSE 'MANUAL_REVIEW' END
            WHEN t.fraud_label = 'fraud' THEN 'APPROVE'
            WHEN t.fraud_scenario IS NOT NULL AND t.fraud_scenario <> '' THEN 'STEP_UP_AUTHENTICATION'
            ELSE 'APPROVE'
        END AS reporting_decision
    FROM fraudops.transaction t
    LEFT JOIN fraudops.fraud_decision fd ON fd.transaction_id = t.transaction_id
)
SELECT
    date_trunc('day', transaction_at)::date AS transaction_date,
    date_trunc('day', transaction_at)::date AS summary_date,
    count(*) AS transaction_count,
    sum(amount) AS attempted_transaction_value,
    count(*) FILTER (WHERE fraud_label = 'fraud') AS confirmed_fraud_count,
    COALESCE(sum(amount) FILTER (WHERE fraud_label = 'fraud'), 0) AS attempted_fraud_value,
    COALESCE(sum(amount) FILTER (WHERE fraud_label = 'fraud' AND reporting_decision IN ('STEP_UP_AUTHENTICATION','MANUAL_REVIEW','HOLD_OR_DECLINE')), 0) AS prevented_fraud_value,
    COALESCE(sum(amount) FILTER (WHERE fraud_label = 'fraud' AND reporting_decision = 'APPROVE'), 0) AS confirmed_fraud_loss,
    avg(CASE WHEN fraud_label = 'fraud' THEN 1.0 ELSE 0.0 END) AS fraud_rate,
    CASE WHEN COALESCE(sum(amount) FILTER (WHERE fraud_label = 'fraud'), 0) > 0
         THEN COALESCE(sum(amount) FILTER (WHERE fraud_label = 'fraud' AND reporting_decision IN ('STEP_UP_AUTHENTICATION','MANUAL_REVIEW','HOLD_OR_DECLINE')), 0) / sum(amount) FILTER (WHERE fraud_label = 'fraud')
         ELSE 0 END AS fraud_value_capture_rate,
    CASE WHEN count(*) FILTER (WHERE fraud_label <> 'fraud') > 0
         THEN count(*) FILTER (WHERE fraud_label <> 'fraud' AND reporting_decision IN ('STEP_UP_AUTHENTICATION','MANUAL_REVIEW','HOLD_OR_DECLINE'))::numeric / count(*) FILTER (WHERE fraud_label <> 'fraud')
         ELSE 0 END AS false_positive_rate,
    count(*) FILTER (WHERE reporting_decision IN ('MANUAL_REVIEW','HOLD_OR_DECLINE')) AS cases_awaiting_review,
    CASE WHEN EXISTS (SELECT 1 FROM fraudops.fraud_decision) THEN 'warehouse_operational' ELSE 'seeded_reporting_data' END AS source_system
FROM transaction_decisions
GROUP BY 1, 2;

CREATE OR REPLACE VIEW fraudops_reporting.vw_alert_operations AS
WITH warehouse_alerts AS (
    SELECT fa.fraud_alert_id::text AS alert_id, fa.transaction_id::text AS transaction_id, t.customer_id::text AS customer_id, t.amount, t.transaction_at,
           fa.opened_at, fa.status::text AS alert_status, fa.priority, fa.assigned_to AS assigned_analyst,
           fa.alert_reason, fd.outcome::text AS decision, COALESCE(mp.fraud_probability, 0) AS fraud_probability,
           EXTRACT(EPOCH FROM (now() - fa.opened_at)) / 60.0 AS alert_age_minutes,
           fa.opened_at + interval '8 hours' AS sla_deadline,
           CASE WHEN fa.status::text <> 'CLOSED' AND now() > fa.opened_at + interval '8 hours' THEN true ELSE false END AS sla_breached,
           'warehouse_operational'::text AS source_system
    FROM fraudops.fraud_alert fa
    JOIN fraudops.transaction t ON t.transaction_id = fa.transaction_id
    LEFT JOIN fraudops.fraud_decision fd ON fd.fraud_decision_id = fa.fraud_decision_id
    LEFT JOIN fraudops.model_prediction mp ON mp.model_prediction_id = fd.model_prediction_id
), api_alerts AS (
    SELECT a.alert_id::text AS alert_id, a.transaction_id::text AS transaction_id, a.customer_id::text AS customer_id, a.amount, COALESCE(st.created_at, a.created_at) AS transaction_at,
           a.created_at AS opened_at, a.status::text AS alert_status, a.priority, COALESCE(a.assigned_analyst, 'Unassigned') AS assigned_analyst,
           COALESCE(array_to_string(ARRAY(SELECT jsonb_array_elements_text(a.triggered_rules::jsonb)), ', '), 'api_scoring_alert') AS alert_reason,
           a.decision::text AS decision, a.risk_score AS fraud_probability,
           EXTRACT(EPOCH FROM (now() - a.created_at)) / 60.0 AS alert_age_minutes,
           a.sla_deadline,
           CASE WHEN a.status::text <> 'CLOSED' AND now() > a.sla_deadline THEN true ELSE false END AS sla_breached,
           'api_operational'::text AS source_system
    FROM public.alerts a
    LEFT JOIN public.scored_transactions st ON st.transaction_id = a.transaction_id
), synthetic_alerts AS (
    SELECT 'SYN-' || left(t.transaction_id::text, 12) AS alert_id, t.transaction_id::text AS transaction_id, t.customer_id::text AS customer_id, t.amount, t.transaction_at,
           t.transaction_at + interval '5 minutes' AS opened_at,
           CASE WHEN t.fraud_label = 'fraud' THEN 'OPEN' ELSE 'CLOSED' END AS alert_status,
           CASE WHEN t.amount >= 1000 THEN 5 WHEN t.amount >= 500 THEN 4 WHEN t.fraud_label = 'fraud' THEN 3 ELSE 2 END AS priority,
           CASE abs(hashtext(t.customer_id::text)) % 4 WHEN 0 THEN 'analyst1' WHEN 1 THEN 'analyst2' WHEN 2 THEN 'analyst3' ELSE 'Unassigned' END AS assigned_analyst,
           COALESCE(NULLIF(t.fraud_scenario, ''), 'synthetic_risk_signal') AS alert_reason,
           CASE WHEN t.fraud_label = 'fraud' THEN 'MANUAL_REVIEW' ELSE 'STEP_UP_AUTHENTICATION' END AS decision,
           CASE WHEN t.fraud_label = 'fraud' THEN 0.82 ELSE 0.42 END AS fraud_probability,
           EXTRACT(EPOCH FROM (now() - (t.transaction_at + interval '5 minutes'))) / 60.0 AS alert_age_minutes,
           t.transaction_at + interval '8 hours' AS sla_deadline,
           CASE WHEN now() > t.transaction_at + interval '8 hours' AND t.fraud_label = 'fraud' THEN true ELSE false END AS sla_breached,
           'seeded_reporting_data'::text AS source_system
    FROM fraudops.transaction t
    WHERE NOT EXISTS (SELECT 1 FROM fraudops.fraud_alert)
      AND NOT EXISTS (SELECT 1 FROM public.alerts)
      AND (t.fraud_label = 'fraud' OR (t.fraud_scenario IS NOT NULL AND t.fraud_scenario <> ''))
)
SELECT * FROM warehouse_alerts
UNION ALL
SELECT * FROM api_alerts
UNION ALL
SELECT * FROM synthetic_alerts;

CREATE OR REPLACE VIEW fraudops_reporting.vw_case_performance AS
WITH warehouse_cases AS (
    SELECT fc.fraud_case_id::text AS case_id, fc.case_external_id::text AS case_external_id, fc.customer_id::text AS customer_id, fc.opened_at, fc.closed_at,
           fc.status::text AS case_status, fc.priority, fc.assigned_to, fc.case_summary,
           count(ca.fraud_alert_id) AS linked_alert_count,
           EXTRACT(EPOCH FROM (COALESCE(fc.closed_at, now()) - fc.opened_at)) / 3600.0 AS investigation_hours,
           CASE WHEN fc.closed_at IS NULL THEN false ELSE true END AS resolved,
           NULL::text AS outcome,
           'warehouse_operational'::text AS source_system
    FROM fraudops.fraud_case fc
    LEFT JOIN fraudops.case_alert ca ON ca.fraud_case_id = fc.fraud_case_id
    GROUP BY fc.fraud_case_id
), api_cases AS (
    SELECT c.case_id::text AS case_id,
           c.case_id::text AS case_external_id,
           c.customer_id::text AS customer_id,
           c.created_at AS opened_at,
           CASE WHEN c.status::text = 'CLOSED' THEN c.updated_at ELSE NULL END AS closed_at,
           c.status::text AS case_status,
           c.priority,
           COALESCE(c.assigned_to, 'Unassigned') AS assigned_to,
           c.case_summary,
           jsonb_array_length(c.alert_ids::jsonb) AS linked_alert_count,
           EXTRACT(EPOCH FROM (COALESCE(c.updated_at, now()) - c.created_at)) / 3600.0 AS investigation_hours,
           CASE WHEN c.status::text = 'CLOSED' THEN true ELSE false END AS resolved,
           c.outcome::text AS outcome,
           'api_operational'::text AS source_system
    FROM public.cases c
), synthetic_cases AS (
    SELECT 'CASE-SYN-' || left(t.customer_id::text, 8) AS case_id,
           'CASE-SYN-' || left(t.customer_id::text, 8) AS case_external_id,
           t.customer_id::text AS customer_id,
           min(t.transaction_at) + interval '15 minutes' AS opened_at,
           CASE WHEN bool_or(t.fraud_label <> 'fraud') THEN max(t.transaction_at) + interval '2 hours' ELSE NULL END AS closed_at,
           CASE WHEN bool_or(t.fraud_label = 'fraud') THEN 'OPEN' ELSE 'CLOSED' END AS case_status,
           max(CASE WHEN t.amount >= 1000 THEN 5 WHEN t.amount >= 500 THEN 4 ELSE 3 END) AS priority,
           CASE abs(hashtext(t.customer_id::text)) % 3 WHEN 0 THEN 'analyst1' WHEN 1 THEN 'analyst2' ELSE 'analyst3' END AS assigned_to,
           'Synthetic Power BI case grouped by customer risk signals' AS case_summary,
           count(*) AS linked_alert_count,
           EXTRACT(EPOCH FROM ((max(t.transaction_at) + interval '2 hours') - (min(t.transaction_at) + interval '15 minutes'))) / 3600.0 AS investigation_hours,
           bool_or(t.fraud_label <> 'fraud') AS resolved,
           CASE WHEN bool_or(t.fraud_label = 'fraud') THEN 'CONFIRMED_FRAUD' ELSE 'LEGITIMATE' END AS outcome,
           'seeded_reporting_data'::text AS source_system
    FROM fraudops.transaction t
    WHERE NOT EXISTS (SELECT 1 FROM fraudops.fraud_case)
      AND NOT EXISTS (SELECT 1 FROM public.cases)
      AND (t.fraud_label = 'fraud' OR (t.fraud_scenario IS NOT NULL AND t.fraud_scenario <> ''))
    GROUP BY t.customer_id
)
SELECT * FROM warehouse_cases
UNION ALL
SELECT * FROM api_cases
UNION ALL
SELECT * FROM synthetic_cases;

CREATE OR REPLACE VIEW fraudops_reporting.vw_analyst_productivity AS
SELECT
    COALESCE(assigned_to, 'Unassigned') AS analyst,
    count(*) AS assigned_cases,
    count(*) FILTER (WHERE case_status = 'CLOSED') AS resolved_cases,
    avg(investigation_hours) FILTER (WHERE resolved) AS avg_resolution_hours,
    count(*) FILTER (WHERE resolved AND investigation_hours <= 24) AS cases_resolved_within_24h,
    CASE WHEN count(*) FILTER (WHERE case_status = 'CLOSED') > 0
         THEN count(*) FILTER (WHERE resolved AND investigation_hours <= 24)::numeric / count(*) FILTER (WHERE case_status = 'CLOSED')
         ELSE 0 END AS sla_compliance_rate,
    count(*) FILTER (WHERE outcome = 'CONFIRMED_FRAUD') AS confirmed_fraud_cases,
    CASE WHEN count(*) FILTER (WHERE resolved) > 0
         THEN count(*) FILTER (WHERE outcome = 'CONFIRMED_FRAUD')::numeric / count(*) FILTER (WHERE resolved)
         ELSE 0 END AS confirmed_fraud_rate
FROM fraudops_reporting.vw_case_performance
GROUP BY 1;

CREATE OR REPLACE VIEW fraudops_reporting.vw_rule_performance AS
WITH operational_rule_performance AS (
    SELECT
        fr.rule_code,
        fr.rule_name,
        fr.severity,
        count(re.rule_execution_id) AS executions,
        count(*) FILTER (WHERE re.triggered) AS triggered_count,
        count(*) FILTER (WHERE re.triggered AND t.fraud_label = 'fraud') AS confirmed_fraud_count,
        count(*) FILTER (WHERE re.triggered AND t.fraud_label <> 'fraud') AS false_positive_count,
        CASE WHEN count(*) FILTER (WHERE re.triggered) > 0
             THEN count(*) FILTER (WHERE re.triggered AND t.fraud_label <> 'fraud')::numeric / count(*) FILTER (WHERE re.triggered)
             ELSE 0 END AS false_positive_rate,
        COALESCE(sum(t.amount) FILTER (WHERE re.triggered AND t.fraud_label = 'fraud'), 0) AS estimated_prevented_loss,
        'warehouse_operational'::text AS source_system
    FROM fraudops.fraud_rule fr
    LEFT JOIN fraudops.rule_execution re ON re.fraud_rule_id = fr.fraud_rule_id
    LEFT JOIN fraudops.transaction t ON t.transaction_id = re.transaction_id
    GROUP BY fr.rule_code, fr.rule_name, fr.severity
), scenario_rule_map AS (
    SELECT *
    FROM (VALUES
        ('BEHAVIOR_DEVIATION', 'behavior_deviation'),
        ('CARD_TESTING', 'card_testing'),
        ('IMPOSSIBLE_TRAVEL', 'impossible_travel'),
        ('MERCHANT_BURST', 'merchant_fraud_burst'),
        ('NEW_DEVICE_HIGH_VALUE', 'new_device_takeover'),
        ('VELOCITY', 'transaction_velocity')
    ) AS mapping(rule_code, fraud_scenario)
), seeded_rule_performance AS (
    SELECT
        fr.rule_code,
        fr.rule_name,
        fr.severity,
        count(t.transaction_id) AS executions,
        count(t.transaction_id) AS triggered_count,
        count(t.transaction_id) FILTER (WHERE t.fraud_label = 'fraud') AS confirmed_fraud_count,
        count(t.transaction_id) FILTER (WHERE t.fraud_label <> 'fraud') AS false_positive_count,
        CASE WHEN count(t.transaction_id) > 0
             THEN count(t.transaction_id) FILTER (WHERE t.fraud_label <> 'fraud')::numeric / count(t.transaction_id)
             ELSE 0 END AS false_positive_rate,
        COALESCE(sum(t.amount) FILTER (WHERE t.fraud_label = 'fraud'), 0) AS estimated_prevented_loss,
        'seeded_reporting_data'::text AS source_system
    FROM fraudops.fraud_rule fr
    LEFT JOIN scenario_rule_map srm ON srm.rule_code = fr.rule_code
    LEFT JOIN fraudops.transaction t ON t.fraud_scenario = srm.fraud_scenario
    WHERE NOT EXISTS (SELECT 1 FROM fraudops.rule_execution)
    GROUP BY fr.rule_code, fr.rule_name, fr.severity
)
SELECT * FROM operational_rule_performance
WHERE EXISTS (SELECT 1 FROM fraudops.rule_execution)
UNION ALL
SELECT * FROM seeded_rule_performance;

CREATE OR REPLACE VIEW fraudops_reporting.vw_model_performance AS
SELECT
    mv.model_name,
    mv.version_label,
    mv.promoted,
    mv.training_started_at,
    mv.training_completed_at,
    (mv.metrics ->> 'precision')::numeric AS precision,
    (mv.metrics ->> 'recall')::numeric AS recall,
    (mv.metrics ->> 'f1')::numeric AS f1,
    (mv.metrics ->> 'pr_auc')::numeric AS pr_auc,
    (mv.metrics ->> 'roc_auc')::numeric AS roc_auc,
    (mv.metrics ->> 'fraud_value_recall')::numeric AS fraud_value_recall,
    mv.metrics,
    mv.artifact_uri
FROM fraudops.model_version mv;

CREATE OR REPLACE VIEW fraudops_reporting.vw_fraud_loss AS
SELECT
    t.transaction_id,
    t.transaction_at::date AS transaction_date,
    t.customer_id,
    t.merchant_id,
    m.merchant_category,
    t.amount,
    t.fraud_label::text AS fraud_label,
    fd.outcome::text AS decision,
    CASE WHEN t.fraud_label = 'fraud' THEN t.amount ELSE 0 END AS attempted_fraud_value,
    CASE WHEN t.fraud_label = 'fraud' AND COALESCE(fd.outcome::text, 'APPROVE') = 'APPROVE' THEN t.amount ELSE 0 END AS confirmed_fraud_loss,
    CASE WHEN t.fraud_label = 'fraud' AND COALESCE(fd.outcome::text, '') IN ('STEP_UP_AUTHENTICATION','MANUAL_REVIEW','HOLD_OR_DECLINE') THEN t.amount ELSE 0 END AS prevented_fraud_value
FROM fraudops.transaction t
LEFT JOIN fraudops.fraud_decision fd ON fd.transaction_id = t.transaction_id
LEFT JOIN fraudops.merchant m ON m.merchant_id = t.merchant_id;

CREATE OR REPLACE VIEW fraudops_reporting.vw_data_quality AS
SELECT
    bqa.pipeline_run_id,
    bqa.pipeline_name,
    bqa.started_at,
    bqa.completed_at,
    bqa.status,
    bqa.input_records,
    bqa.accepted_records,
    bqa.rejected_records,
    bqa.duplicate_records,
    bqr.rule_code,
    bqr.dimension,
    bqr.description,
    bqr.total_records,
    bqr.failed_records,
    bqr.passed,
    EXTRACT(EPOCH FROM (now() - bqa.completed_at)) / 3600.0 AS hours_since_refresh
FROM fraudops.batch_pipeline_audit bqa
LEFT JOIN fraudops.batch_quality_result bqr ON bqr.pipeline_run_id = bqa.pipeline_run_id;

CREATE OR REPLACE VIEW fraudops_reporting.vw_source_to_curated_reconciliation AS
SELECT
    pipeline_run_id,
    pipeline_name,
    input_records,
    accepted_records,
    rejected_records,
    duplicate_records,
    input_records - accepted_records - rejected_records AS unreconciled_records,
    CASE WHEN input_records = accepted_records + rejected_records THEN true ELSE false END AS reconciled
FROM fraudops.batch_pipeline_audit;

