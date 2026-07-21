CREATE SCHEMA IF NOT EXISTS fraudops;
SET search_path TO fraudops;

CREATE TABLE IF NOT EXISTS batch_pipeline_audit (
    pipeline_run_id TEXT PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    input_records INTEGER NOT NULL DEFAULT 0,
    accepted_records INTEGER NOT NULL DEFAULT 0,
    rejected_records INTEGER NOT NULL DEFAULT 0,
    duplicate_records INTEGER NOT NULL DEFAULT 0,
    input_uri TEXT,
    validated_uri TEXT,
    rejected_uri TEXT,
    curated_uri TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS batch_quality_result (
    batch_quality_result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id TEXT NOT NULL REFERENCES batch_pipeline_audit(pipeline_run_id),
    rule_code TEXT NOT NULL,
    dimension TEXT NOT NULL,
    description TEXT NOT NULL,
    total_records INTEGER NOT NULL,
    failed_records INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
