CREATE SCHEMA IF NOT EXISTS fraudops;
SET search_path TO fraudops;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'transaction_status') THEN
        CREATE TYPE transaction_status AS ENUM ('AUTHORIZED', 'DECLINED', 'REVERSED', 'SETTLED');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'decision_outcome') THEN
        CREATE TYPE decision_outcome AS ENUM ('APPROVE', 'STEP_UP_AUTHENTICATION', 'MANUAL_REVIEW', 'HOLD_OR_DECLINE');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fraud_label') THEN
        CREATE TYPE fraud_label AS ENUM ('unknown', 'legitimate', 'fraud');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_status') THEN
        CREATE TYPE alert_status AS ENUM ('OPEN', 'IN_REVIEW', 'ESCALATED', 'CLOSED');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'case_status') THEN
        CREATE TYPE case_status AS ENUM ('OPEN', 'PENDING_CUSTOMER', 'ESCALATED', 'CLOSED');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS customer (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_external_id TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone_number TEXT,
    home_country CHAR(2) NOT NULL,
    home_city TEXT NOT NULL,
    customer_segment TEXT NOT NULL,
    risk_tier TEXT NOT NULL DEFAULT 'standard',
    opened_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customer(customer_id),
    account_external_id TEXT NOT NULL UNIQUE,
    account_type TEXT NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    opened_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS card (
    card_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES account(account_id),
    card_external_id TEXT NOT NULL UNIQUE,
    card_network TEXT NOT NULL,
    last_four CHAR(4) NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL,
    expires_at DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS device (
    device_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customer(customer_id),
    device_external_id TEXT NOT NULL UNIQUE,
    device_type TEXT NOT NULL,
    operating_system TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL,
    trusted BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS merchant (
    merchant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_external_id TEXT NOT NULL UNIQUE,
    merchant_name TEXT NOT NULL,
    merchant_category_code TEXT NOT NULL,
    merchant_category TEXT NOT NULL,
    country CHAR(2) NOT NULL,
    city TEXT NOT NULL,
    risk_tier TEXT NOT NULL DEFAULT 'standard'
);

CREATE TABLE IF NOT EXISTS transaction (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_external_id TEXT NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customer(customer_id),
    account_id UUID NOT NULL REFERENCES account(account_id),
    card_id UUID NOT NULL REFERENCES card(card_id),
    device_id UUID REFERENCES device(device_id),
    merchant_id UUID NOT NULL REFERENCES merchant(merchant_id),
    transaction_at TIMESTAMPTZ NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    merchant_country CHAR(2) NOT NULL,
    merchant_city TEXT NOT NULL,
    channel TEXT NOT NULL,
    status transaction_status NOT NULL DEFAULT 'AUTHORIZED',
    authorization_code TEXT,
    fraud_label fraud_label NOT NULL DEFAULT 'unknown',
    label_source TEXT,
    label_available_at TIMESTAMPTZ,
    chargeback_date DATE,
    analyst_confirmed_at TIMESTAMPTZ,
    fraud_scenario TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fraud_rule (
    fraud_rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code TEXT NOT NULL UNIQUE,
    rule_name TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rule_execution (
    rule_execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fraud_rule_id UUID NOT NULL REFERENCES fraud_rule(fraud_rule_id),
    transaction_id UUID NOT NULL REFERENCES transaction(transaction_id),
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    triggered BOOLEAN NOT NULL,
    score NUMERIC(5, 4),
    reason TEXT
);

CREATE TABLE IF NOT EXISTS model_version (
    model_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    version_label TEXT NOT NULL,
    training_started_at TIMESTAMPTZ,
    training_completed_at TIMESTAMPTZ,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_uri TEXT,
    promoted BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (model_name, version_label)
);

CREATE TABLE IF NOT EXISTS model_prediction (
    model_prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transaction(transaction_id),
    model_version_id UUID REFERENCES model_version(model_version_id),
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fraud_probability NUMERIC(6, 5) NOT NULL CHECK (fraud_probability >= 0 AND fraud_probability <= 1),
    model_features JSONB NOT NULL DEFAULT '{}'::jsonb,
    explanation JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS threshold_configuration (
    threshold_configuration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    configuration_name TEXT NOT NULL UNIQUE,
    step_up_threshold NUMERIC(6, 5) NOT NULL,
    manual_review_threshold NUMERIC(6, 5) NOT NULL,
    hold_decline_threshold NUMERIC(6, 5) NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS fraud_decision (
    fraud_decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transaction(transaction_id),
    model_prediction_id UUID REFERENCES model_prediction(model_prediction_id),
    threshold_configuration_id UUID REFERENCES threshold_configuration(threshold_configuration_id),
    decision_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    outcome decision_outcome NOT NULL,
    reason_codes TEXT[] NOT NULL DEFAULT '{}',
    expected_loss NUMERIC(12, 2)
);

CREATE TABLE IF NOT EXISTS fraud_alert (
    fraud_alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transaction(transaction_id),
    fraud_decision_id UUID REFERENCES fraud_decision(fraud_decision_id),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status alert_status NOT NULL DEFAULT 'OPEN',
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    alert_reason TEXT NOT NULL,
    assigned_to TEXT
);

CREATE TABLE IF NOT EXISTS fraud_case (
    fraud_case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_external_id TEXT NOT NULL UNIQUE,
    customer_id UUID NOT NULL REFERENCES customer(customer_id),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    status case_status NOT NULL DEFAULT 'OPEN',
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    assigned_to TEXT,
    case_summary TEXT
);

CREATE TABLE IF NOT EXISTS case_alert (
    fraud_case_id UUID NOT NULL REFERENCES fraud_case(fraud_case_id),
    fraud_alert_id UUID NOT NULL REFERENCES fraud_alert(fraud_alert_id),
    linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (fraud_case_id, fraud_alert_id)
);

CREATE TABLE IF NOT EXISTS case_action (
    case_action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fraud_case_id UUID NOT NULL REFERENCES fraud_case(fraud_case_id),
    action_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor TEXT NOT NULL,
    action_type TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS fraud_feedback (
    fraud_feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fraud_case_id UUID REFERENCES fraud_case(fraud_case_id),
    transaction_id UUID NOT NULL REFERENCES transaction(transaction_id),
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    final_label fraud_label NOT NULL,
    feedback_source TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_run (
    pipeline_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    input_uri TEXT,
    output_uri TEXT,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS data_quality_rule (
    data_quality_rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code TEXT NOT NULL UNIQUE,
    table_name TEXT NOT NULL,
    column_name TEXT,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS data_quality_result (
    data_quality_result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_quality_rule_id UUID NOT NULL REFERENCES data_quality_rule(data_quality_rule_id),
    pipeline_run_id UUID REFERENCES pipeline_run(pipeline_run_id),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    passed BOOLEAN NOT NULL,
    failed_record_count INTEGER NOT NULL DEFAULT 0,
    sample_failures JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_transaction_customer_time ON transaction(customer_id, transaction_at);
CREATE INDEX IF NOT EXISTS idx_transaction_card_time ON transaction(card_id, transaction_at);
CREATE INDEX IF NOT EXISTS idx_transaction_merchant_time ON transaction(merchant_id, transaction_at);
CREATE INDEX IF NOT EXISTS idx_transaction_fraud_label ON transaction(fraud_label);
CREATE INDEX IF NOT EXISTS idx_alert_status_priority ON fraud_alert(status, priority);
CREATE INDEX IF NOT EXISTS idx_case_status_priority ON fraud_case(status, priority);
