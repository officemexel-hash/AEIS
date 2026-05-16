-- SYLION AEIS PostgreSQL Migration 003: Remaining Layers
-- Execution, Cognitive, Memory, Security, Quality, Efficiency, Rebuild, Cellular, Devices, SDR

BEGIN;

-- ============================================================
-- EXECUTION (H1-H8)
-- ============================================================

CREATE TABLE IF NOT EXISTS exec_tools (
    tool_id        TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    tool_type      TEXT         NOT NULL DEFAULT '',
    config         JSONB        NOT NULL DEFAULT '{}',
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exec_tool_runs (
    run_id         TEXT         PRIMARY KEY,
    tool_id        TEXT         NOT NULL,
    input_data     JSONB        NOT NULL DEFAULT '{}',
    output_data    JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'pending',
    duration_ms    INTEGER      NOT NULL DEFAULT 0,
    error          TEXT         NOT NULL DEFAULT '',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_toolrun_tool ON exec_tool_runs(tool_id);
CREATE INDEX IF NOT EXISTS idx_toolrun_status ON exec_tool_runs(status);

CREATE TABLE IF NOT EXISTS exec_workflows (
    workflow_id    TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    steps          JSONB        NOT NULL DEFAULT '[]',
    status         TEXT         NOT NULL DEFAULT 'DRAFT',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exec_jobs (
    job_id         TEXT         PRIMARY KEY,
    workflow_id    TEXT         NOT NULL,
    status         TEXT         NOT NULL DEFAULT 'pending',
    result         JSONB        NOT NULL DEFAULT '{}',
    priority       INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ  DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON exec_jobs(status);

CREATE TABLE IF NOT EXISTS exec_adapters (
    adapter_id     TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    adapter_type   TEXT         NOT NULL DEFAULT '',
    route          TEXT         NOT NULL DEFAULT '',
    config         JSONB        NOT NULL DEFAULT '{}',
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS exec_connectors (
    connector_id   TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    connector_type TEXT         NOT NULL DEFAULT '',
    config         JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'active',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_connector_type ON exec_connectors(connector_type);

CREATE TABLE IF NOT EXISTS exec_retries (
    retry_id       TEXT         PRIMARY KEY,
    target_id      TEXT         NOT NULL,
    target_type    TEXT         NOT NULL,
    attempt        INTEGER      NOT NULL DEFAULT 1,
    max_attempts   INTEGER      NOT NULL DEFAULT 3,
    status         TEXT         NOT NULL DEFAULT 'pending',
    next_retry_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_retry_status ON exec_retries(status);

-- ============================================================
-- COGNITIVE (L1-L6)
-- ============================================================

CREATE TABLE IF NOT EXISTS cognitive_plans (
    plan_id        TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    plan_type      TEXT         NOT NULL DEFAULT '',
    steps          JSONB        NOT NULL DEFAULT '[]',
    status         TEXT         NOT NULL DEFAULT 'DRAFT',
    priority       INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_plan_status ON cognitive_plans(status);

CREATE TABLE IF NOT EXISTS cognitive_evaluations (
    eval_id        TEXT         PRIMARY KEY,
    target_type    TEXT         NOT NULL,
    target_id      TEXT         NOT NULL,
    score          REAL         NOT NULL DEFAULT 0,
    verdict        TEXT         NOT NULL DEFAULT '',
    reasoning      TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cognitive_reasoning_chains (
    chain_id       TEXT         PRIMARY KEY,
    question       TEXT         NOT NULL,
    steps          JSONB        NOT NULL DEFAULT '[]',
    conclusion     TEXT         NOT NULL DEFAULT '',
    confidence     REAL         NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cognitive_contexts (
    context_id     TEXT         PRIMARY KEY,
    context_type   TEXT         NOT NULL,
    content        JSONB        NOT NULL DEFAULT '{}',
    tokens_used    INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cognitive_llm_calls (
    call_id        TEXT         PRIMARY KEY,
    model          TEXT         NOT NULL,
    prompt_tokens  INTEGER      NOT NULL DEFAULT 0,
    completion_tokens INTEGER   NOT NULL DEFAULT 0,
    duration_ms    INTEGER      NOT NULL DEFAULT 0,
    status         TEXT         NOT NULL DEFAULT 'success',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_llm_model ON cognitive_llm_calls(model);

-- ============================================================
-- MEMORY (N1-N4)
-- ============================================================

CREATE TABLE IF NOT EXISTS memory_kanon (
    key            TEXT         PRIMARY KEY,
    value          TEXT         NOT NULL DEFAULT '',
    section        TEXT         NOT NULL DEFAULT 'general',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_kanon_section ON memory_kanon(section);

CREATE TABLE IF NOT EXISTS memory_compact_layers (
    layer_id       TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    description    TEXT         NOT NULL DEFAULT '',
    entries        JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_evidence (
    evidence_id    TEXT         PRIMARY KEY,
    claim          TEXT         NOT NULL,
    source         TEXT         NOT NULL DEFAULT '',
    hash           TEXT         NOT NULL DEFAULT '',
    metadata       JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mem_evidence_source ON memory_evidence(source);

CREATE TABLE IF NOT EXISTS memory_index (
    index_id       TEXT         PRIMARY KEY,
    doc_id         TEXT         NOT NULL,
    content        TEXT         NOT NULL DEFAULT '',
    tokens         JSONB        NOT NULL DEFAULT '[]',
    embedding      BYTEA        DEFAULT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_memidx_doc ON memory_index(doc_id);

CREATE TABLE IF NOT EXISTS memory_kb_sources (
    source_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    source_type    TEXT         NOT NULL DEFAULT '',
    config         JSONB        NOT NULL DEFAULT '{}',
    active         BOOLEAN      NOT NULL DEFAULT TRUE,
    last_indexed   TIMESTAMPTZ  DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS memory_self_models (
    model_id       TEXT         PRIMARY KEY,
    model_data     JSONB        NOT NULL DEFAULT '{}',
    version        INTEGER      NOT NULL DEFAULT 1,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memory_model_snapshots (
    snapshot_id    TEXT         PRIMARY KEY,
    model_id       TEXT         NOT NULL REFERENCES memory_self_models(model_id),
    summary        TEXT         NOT NULL DEFAULT '',
    reason         TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_model_snap_model ON memory_model_snapshots(model_id);

-- ============================================================
-- SECURITY (K1-K10)
-- ============================================================

CREATE TABLE IF NOT EXISTS security_auth (
    user_id        TEXT         PRIMARY KEY,
    username       TEXT         NOT NULL UNIQUE,
    roles          JSONB        NOT NULL DEFAULT '[]',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS security_sessions (
    session_id     TEXT         PRIMARY KEY,
    user_id        TEXT         NOT NULL,
    token_hash     TEXT         NOT NULL DEFAULT '',
    expires_at     TIMESTAMPTZ  NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_session_user ON security_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires ON security_sessions(expires_at);

CREATE TABLE IF NOT EXISTS security_policies (
    policy_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    rules          JSONB        NOT NULL DEFAULT '[]',
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS security_audit_log (
    audit_id       BIGSERIAL    PRIMARY KEY,
    action         TEXT         NOT NULL,
    subject        TEXT         NOT NULL DEFAULT '',
    resource       TEXT         NOT NULL DEFAULT '',
    outcome        TEXT         NOT NULL DEFAULT '',
    details        JSONB        NOT NULL DEFAULT '{}',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_action ON security_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON security_audit_log(timestamp);

CREATE TABLE IF NOT EXISTS security_secrets (
    secret_id      TEXT         PRIMARY KEY,
    key_path       TEXT         NOT NULL UNIQUE,
    encrypted_value BYTEA       NOT NULL,
    version        INTEGER      NOT NULL DEFAULT 1,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_secret_path ON security_secrets(key_path);

-- ============================================================
-- QUALITY (P1-P5)
-- ============================================================

CREATE TABLE IF NOT EXISTS quality_golden_sets (
    set_id         TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    module_id      TEXT         NOT NULL DEFAULT '',
    cases          JSONB        NOT NULL DEFAULT '[]',
    version        TEXT         NOT NULL DEFAULT '1.0.0',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_golden_module ON quality_golden_sets(module_id);

CREATE TABLE IF NOT EXISTS quality_test_runs (
    run_id         TEXT         PRIMARY KEY,
    set_id         TEXT         NOT NULL,
    results        JSONB        NOT NULL DEFAULT '[]',
    pass_count     INTEGER      NOT NULL DEFAULT 0,
    fail_count     INTEGER      NOT NULL DEFAULT 0,
    duration_ms    INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_testrun_set ON quality_test_runs(set_id);

CREATE TABLE IF NOT EXISTS quality_regressions (
    regression_id  TEXT         PRIMARY KEY,
    module_id      TEXT         NOT NULL,
    description    TEXT         NOT NULL DEFAULT '',
    severity       TEXT         NOT NULL DEFAULT 'medium',
    detected_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ  DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_regression_module ON quality_regressions(module_id);

-- ============================================================
-- EFFICIENCY (I1-I5)
-- ============================================================

CREATE TABLE IF NOT EXISTS efficiency_code_bloat (
    report_id      TEXT         PRIMARY KEY,
    module_id      TEXT         NOT NULL,
    metrics        JSONB        NOT NULL DEFAULT '{}',
    score          REAL         NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS efficiency_runtime_metrics (
    metric_id      TEXT         PRIMARY KEY,
    module_id      TEXT         NOT NULL,
    metric_type    TEXT         NOT NULL,
    value          REAL         NOT NULL,
    unit           TEXT         NOT NULL DEFAULT '',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runtime_module ON efficiency_runtime_metrics(module_id);

CREATE TABLE IF NOT EXISTS efficiency_memory_snapshots (
    snapshot_id    TEXT         PRIMARY KEY,
    module_id      TEXT         NOT NULL,
    heap_size_mb   REAL         NOT NULL DEFAULT 0,
    object_count   INTEGER      NOT NULL DEFAULT 0,
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS efficiency_cost_records (
    record_id      TEXT         PRIMARY KEY,
    category       TEXT         NOT NULL,
    amount         REAL         NOT NULL DEFAULT 0,
    currency       TEXT         NOT NULL DEFAULT 'USD',
    period         TEXT         NOT NULL DEFAULT '',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cost_category ON efficiency_cost_records(category);

CREATE TABLE IF NOT EXISTS efficiency_budgets (
    budget_id      TEXT         PRIMARY KEY,
    category       TEXT         NOT NULL,
    limit_amount   REAL         NOT NULL,
    period         TEXT         NOT NULL DEFAULT 'monthly',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- REBUILD (O1-O4)
-- ============================================================

CREATE TABLE IF NOT EXISTS rebuild_orchestrations (
    orchestration_id TEXT       PRIMARY KEY,
    name             TEXT       NOT NULL,
    status           TEXT       NOT NULL DEFAULT 'pending',
    config           JSONB      NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rebuild_lpw_checkpoints (
    checkpoint_id  TEXT         PRIMARY KEY,
    orchestration_id TEXT       NOT NULL,
    phase          TEXT         NOT NULL,
    state_data     JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lpw_orch ON rebuild_lpw_checkpoints(orchestration_id);

CREATE TABLE IF NOT EXISTS rebuild_cutover_events (
    event_id       TEXT         PRIMARY KEY,
    orchestration_id TEXT       NOT NULL,
    event_type     TEXT         NOT NULL,
    details        JSONB        NOT NULL DEFAULT '{}',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rebuild_cft_runs (
    run_id         TEXT         PRIMARY KEY,
    orchestration_id TEXT       NOT NULL,
    test_suite     TEXT         NOT NULL DEFAULT '',
    results        JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CELLULAR (X1-X8)
-- ============================================================

CREATE TABLE IF NOT EXISTS cellular_networks (
    network_id     TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    config         JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'inactive',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cellular_ran_configs (
    config_id      TEXT         PRIMARY KEY,
    network_id     TEXT         NOT NULL REFERENCES cellular_networks(network_id),
    band           TEXT         NOT NULL DEFAULT '',
    bandwidth      TEXT         NOT NULL DEFAULT '',
    power_dbm      REAL         NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cellular_ue_sessions (
    session_id     TEXT         PRIMARY KEY,
    network_id     TEXT         NOT NULL,
    imsi           TEXT         NOT NULL DEFAULT '',
    status         TEXT         NOT NULL DEFAULT 'idle',
    connected_at   TIMESTAMPTZ  DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS cellular_rf_measurements (
    measurement_id TEXT         PRIMARY KEY,
    network_id     TEXT         NOT NULL,
    freq_mhz       REAL         NOT NULL,
    power_dbm      REAL         NOT NULL,
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rf_net ON cellular_rf_measurements(network_id);

CREATE TABLE IF NOT EXISTS cellular_attack_logs (
    log_id         TEXT         PRIMARY KEY,
    network_id     TEXT         NOT NULL,
    attack_type    TEXT         NOT NULL,
    result         TEXT         NOT NULL DEFAULT '',
    evidence       JSONB        NOT NULL DEFAULT '{}',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DEVICES (W1-W6)
-- ============================================================

CREATE TABLE IF NOT EXISTS devices (
    device_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    device_type    TEXT         NOT NULL DEFAULT '',
    status         TEXT         NOT NULL DEFAULT 'registered',
    config         JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_device_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_device_status ON devices(status);

CREATE TABLE IF NOT EXISTS device_deployments (
    deployment_id  TEXT         PRIMARY KEY,
    device_id      TEXT         NOT NULL REFERENCES devices(device_id),
    artifact_id    TEXT         NOT NULL DEFAULT '',
    version        TEXT         NOT NULL DEFAULT '',
    status         TEXT         NOT NULL DEFAULT 'pending',
    deployed_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_deploy_device ON device_deployments(device_id);

-- ============================================================
-- SDR (Y1-Y5)
-- ============================================================

CREATE TABLE IF NOT EXISTS sdr_devices (
    sdr_id         TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    device_type    TEXT         NOT NULL DEFAULT '',
    config         JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'offline',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sdr_captures (
    capture_id     TEXT         PRIMARY KEY,
    sdr_id         TEXT         NOT NULL,
    freq_hz        BIGINT       NOT NULL,
    sample_rate    REAL         NOT NULL DEFAULT 0,
    duration_ms    INTEGER      NOT NULL DEFAULT 0,
    status         TEXT         NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_capture_sdr ON sdr_captures(sdr_id);

CREATE TABLE IF NOT EXISTS sdr_signals (
    signal_id      TEXT         PRIMARY KEY,
    capture_id     TEXT         NOT NULL,
    freq_hz        BIGINT       NOT NULL,
    bandwidth_hz   BIGINT       NOT NULL DEFAULT 0,
    modulation     TEXT         NOT NULL DEFAULT '',
    confidence     REAL         NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_signal_capture ON sdr_signals(capture_id);

CREATE TABLE IF NOT EXISTS sdr_decoded (
    decode_id      TEXT         PRIMARY KEY,
    signal_id      TEXT         NOT NULL,
    protocol       TEXT         NOT NULL DEFAULT '',
    data           TEXT         NOT NULL DEFAULT '',
    metadata       JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMIT;
