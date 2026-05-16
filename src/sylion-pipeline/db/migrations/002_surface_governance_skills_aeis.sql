-- SYLION AEIS PostgreSQL Migration 002: Surface, Governance, Skills, AEIS
-- Migrates remaining SQLite-backed services to PostgreSQL 16

BEGIN;

-- ============================================================
-- SURFACE LAYER (J1-J8)
-- ============================================================

-- J1: Console API
CREATE TABLE IF NOT EXISTS surface_console_commands (
    command_id     TEXT         PRIMARY KEY,
    command_type   TEXT         NOT NULL,
    payload        JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'pending',
    result         JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMPTZ  DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_console_type ON surface_console_commands(command_type);
CREATE INDEX IF NOT EXISTS idx_console_status ON surface_console_commands(status);

-- J2: Console UI
CREATE TABLE IF NOT EXISTS surface_ui_components (
    component_id   TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    component_type TEXT         NOT NULL DEFAULT 'panel',
    config         JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS surface_ui_layouts (
    layout_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    panels         JSONB        NOT NULL DEFAULT '[]',
    role           TEXT         NOT NULL DEFAULT 'default',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- J3: WebSocket Gateway
CREATE TABLE IF NOT EXISTS surface_ws_connections (
    conn_id        TEXT         PRIMARY KEY,
    user_id        TEXT         NOT NULL,
    client_id      TEXT         NOT NULL,
    channels       JSONB        NOT NULL DEFAULT '[]',
    status         TEXT         NOT NULL DEFAULT 'connected',
    connected_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    disconnected_at TIMESTAMPTZ DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_ws_user ON surface_ws_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_ws_status ON surface_ws_connections(status);

-- J4: Command Bus
CREATE TABLE IF NOT EXISTS surface_intents (
    intent_id      TEXT         PRIMARY KEY,
    intent_type    TEXT         NOT NULL,
    payload        JSONB        NOT NULL DEFAULT '{}',
    phase          TEXT         NOT NULL DEFAULT 'PENDING',
    submitted_by   TEXT         NOT NULL DEFAULT '',
    approved_by    TEXT         NOT NULL DEFAULT '',
    rejection_reason TEXT       NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ  DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS surface_intent_events (
    event_id       TEXT         PRIMARY KEY,
    intent_id      TEXT         NOT NULL REFERENCES surface_intents(intent_id),
    event_type     TEXT         NOT NULL,
    details        JSONB        NOT NULL DEFAULT '{}',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_intent_phase ON surface_intents(phase);
CREATE INDEX IF NOT EXISTS idx_intent_type ON surface_intents(intent_type);

-- J5: Event Sourcing Store (APPEND-ONLY)
CREATE TABLE IF NOT EXISTS surface_event_streams (
    stream_id      TEXT         PRIMARY KEY,
    stream_type    TEXT         NOT NULL DEFAULT '',
    metadata       JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS surface_event_log (
    sequence_id    BIGSERIAL    PRIMARY KEY,
    stream_id      TEXT         NOT NULL REFERENCES surface_event_streams(stream_id),
    version        BIGINT       NOT NULL,
    event_type     TEXT         NOT NULL,
    payload        JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(stream_id, version)
);
CREATE INDEX IF NOT EXISTS idx_event_log_stream ON surface_event_log(stream_id);
-- APPEND-ONLY: no UPDATE or DELETE triggers on surface_event_log

CREATE TABLE IF NOT EXISTS surface_snapshots (
    snapshot_id    TEXT         PRIMARY KEY,
    stream_id      TEXT         NOT NULL REFERENCES surface_event_streams(stream_id),
    version        BIGINT       NOT NULL,
    state_data     JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_snapshots_stream ON surface_snapshots(stream_id);

-- J6: Artifact Control
CREATE TABLE IF NOT EXISTS surface_artifacts (
    artifact_id    TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    artifact_type  TEXT         NOT NULL DEFAULT '',
    version        TEXT         NOT NULL DEFAULT '1.0.0',
    status         TEXT         NOT NULL DEFAULT 'DRAFT',
    checksum       TEXT         NOT NULL DEFAULT '',
    metadata       JSONB        NOT NULL DEFAULT '{}',
    uploaded_by    TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    published_at   TIMESTAMPTZ  DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS surface_upload_sessions (
    session_id     TEXT         PRIMARY KEY,
    artifact_id    TEXT         NOT NULL REFERENCES surface_artifacts(artifact_id),
    signed_url     TEXT         NOT NULL DEFAULT '',
    status         TEXT         NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_artifact_status ON surface_artifacts(status);

-- J7: Process Canvas
CREATE TABLE IF NOT EXISTS surface_canvases (
    canvas_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    description    TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS surface_canvas_nodes (
    node_id        TEXT         PRIMARY KEY,
    canvas_id      TEXT         NOT NULL REFERENCES surface_canvases(canvas_id),
    node_type      TEXT         NOT NULL DEFAULT '',
    label          TEXT         NOT NULL DEFAULT '',
    position       JSONB        NOT NULL DEFAULT '{}',
    config         JSONB        NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS surface_canvas_edges (
    edge_id        TEXT         PRIMARY KEY,
    canvas_id      TEXT         NOT NULL REFERENCES surface_canvases(canvas_id),
    source_node    TEXT         NOT NULL REFERENCES surface_canvas_nodes(node_id),
    target_node    TEXT         NOT NULL REFERENCES surface_canvas_nodes(node_id),
    edge_type      TEXT         NOT NULL DEFAULT 'default',
    label          TEXT         NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_canvas_nodes_canvas ON surface_canvas_nodes(canvas_id);
CREATE INDEX IF NOT EXISTS idx_canvas_edges_canvas ON surface_canvas_edges(canvas_id);

-- J8: Readiness Engine
CREATE TABLE IF NOT EXISTS surface_readiness_checks (
    check_id       TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    description    TEXT         NOT NULL DEFAULT '',
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS surface_readiness_reports (
    report_id      TEXT         PRIMARY KEY,
    score          REAL         NOT NULL DEFAULT 0,
    total_checks   INTEGER      NOT NULL DEFAULT 0,
    pass_count     INTEGER      NOT NULL DEFAULT 0,
    warn_count     INTEGER      NOT NULL DEFAULT 0,
    fail_count     INTEGER      NOT NULL DEFAULT 0,
    ml_advisory    JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS surface_readiness_results (
    result_id      TEXT         PRIMARY KEY,
    report_id      TEXT         NOT NULL REFERENCES surface_readiness_reports(report_id),
    check_id       TEXT         NOT NULL,
    status         TEXT         NOT NULL DEFAULT 'pending',
    message        TEXT         NOT NULL DEFAULT '',
    details        JSONB        NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_readiness_report ON surface_readiness_results(report_id);

-- ============================================================
-- GOVERNANCE (M1-M6)
-- ============================================================

CREATE TABLE IF NOT EXISTS gov_decision_ladder (
    decision_id    TEXT         PRIMARY KEY,
    title          TEXT         NOT NULL,
    decision_class TEXT         NOT NULL DEFAULT 'D0',
    justification  TEXT         NOT NULL DEFAULT '',
    status         TEXT         NOT NULL DEFAULT 'OPEN',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ  DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_gov_class ON gov_decision_ladder(decision_class);

CREATE TABLE IF NOT EXISTS gov_council_sessions (
    session_id     TEXT         PRIMARY KEY,
    decision_id    TEXT         NOT NULL,
    votes          JSONB        NOT NULL DEFAULT '[]',
    outcome        TEXT         NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    closed_at      TIMESTAMPTZ  DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS gov_evidence_packs (
    pack_id        TEXT         PRIMARY KEY,
    decision_id    TEXT         NOT NULL,
    rationale      TEXT         NOT NULL DEFAULT '',
    rollback_plan  JSONB        NOT NULL DEFAULT '{}',
    fidelity_test  JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'DRAFT',
    author         TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evidence_decision ON gov_evidence_packs(decision_id);

CREATE TABLE IF NOT EXISTS gov_policies (
    policy_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    policy_type    TEXT         NOT NULL DEFAULT '',
    rules          JSONB        NOT NULL DEFAULT '[]',
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gov_gates (
    gate_id        TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    gate_type      TEXT         NOT NULL DEFAULT '',
    config         JSONB        NOT NULL DEFAULT '{}',
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ============================================================
-- SKILLS (Q1-Q5)
-- ============================================================

CREATE TABLE IF NOT EXISTS skills_registry (
    skill_id       TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    domain         TEXT         NOT NULL DEFAULT '',
    version        TEXT         NOT NULL DEFAULT '1.0.0',
    owner_role     TEXT         NOT NULL DEFAULT '',
    inputs         JSONB        NOT NULL DEFAULT '[]',
    outputs        JSONB        NOT NULL DEFAULT '[]',
    quality_gates  JSONB        NOT NULL DEFAULT '[]',
    cost_profile   TEXT         NOT NULL DEFAULT 'zero-cost',
    lifecycle      TEXT         NOT NULL DEFAULT 'DRAFT',
    description    TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_skills_domain ON skills_registry(domain);
CREATE INDEX IF NOT EXISTS idx_skills_lifecycle ON skills_registry(lifecycle);

CREATE TABLE IF NOT EXISTS skills_executions (
    exec_id        TEXT         PRIMARY KEY,
    skill_id       TEXT         NOT NULL,
    input_data     JSONB        NOT NULL DEFAULT '{}',
    output_data    JSONB        NOT NULL DEFAULT '{}',
    status         TEXT         NOT NULL DEFAULT 'pending',
    duration_ms    INTEGER      NOT NULL DEFAULT 0,
    error          TEXT         NOT NULL DEFAULT '',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_exec_skill ON skills_executions(skill_id);
CREATE INDEX IF NOT EXISTS idx_exec_status ON skills_executions(status);

CREATE TABLE IF NOT EXISTS skills_catalog (
    entry_id       TEXT         PRIMARY KEY,
    skill_id       TEXT         NOT NULL,
    name           TEXT         NOT NULL,
    category       TEXT         NOT NULL DEFAULT 'custom',
    domain         TEXT         NOT NULL DEFAULT '',
    tags           JSONB        NOT NULL DEFAULT '[]',
    description    TEXT         NOT NULL DEFAULT '',
    version        TEXT         NOT NULL DEFAULT '1.0.0',
    author         TEXT         NOT NULL DEFAULT '',
    compatibility  TEXT         NOT NULL DEFAULT '',
    rating         REAL         NOT NULL DEFAULT 0,
    usage_count    INTEGER      NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_catalog_cat ON skills_catalog(category);
CREATE INDEX IF NOT EXISTS idx_catalog_domain ON skills_catalog(domain);
CREATE INDEX IF NOT EXISTS idx_catalog_skill ON skills_catalog(skill_id);

-- ============================================================
-- AEIS (R1-R5)
-- ============================================================

CREATE TABLE IF NOT EXISTS aeis_observations (
    observation_id TEXT         PRIMARY KEY,
    metric         TEXT         NOT NULL,
    value          REAL         NOT NULL,
    unit           TEXT         NOT NULL DEFAULT '',
    source         TEXT         NOT NULL DEFAULT '',
    tags           JSONB        NOT NULL DEFAULT '{}',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_obs_metric ON aeis_observations(metric);
CREATE INDEX IF NOT EXISTS idx_obs_ts ON aeis_observations(timestamp);

CREATE TABLE IF NOT EXISTS aeis_observation_aggregates (
    metric         TEXT         PRIMARY KEY,
    avg_value      REAL         NOT NULL DEFAULT 0,
    min_value      REAL         NOT NULL DEFAULT 0,
    max_value      REAL         NOT NULL DEFAULT 0,
    sample_count   BIGINT       NOT NULL DEFAULT 0,
    last_updated   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS aeis_evolution_proposals (
    proposal_id    TEXT         PRIMARY KEY,
    target_module  TEXT         NOT NULL,
    mutation_type  TEXT         NOT NULL,
    description    TEXT         NOT NULL DEFAULT '',
    rationale      TEXT         NOT NULL DEFAULT '',
    expected_fitness_delta REAL NOT NULL DEFAULT 0,
    risk_level     TEXT         NOT NULL DEFAULT 'low',
    state          TEXT         NOT NULL DEFAULT 'PROPOSED',
    fitness_before REAL         NOT NULL DEFAULT 0,
    fitness_after  REAL         NOT NULL DEFAULT 0,
    rollback_plan  TEXT         NOT NULL DEFAULT '',
    metadata       JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evo_module ON aeis_evolution_proposals(target_module);
CREATE INDEX IF NOT EXISTS idx_evo_state ON aeis_evolution_proposals(state);

CREATE TABLE IF NOT EXISTS aeis_evolution_events (
    event_id       TEXT         PRIMARY KEY,
    proposal_id    TEXT         NOT NULL,
    from_state     TEXT         NOT NULL,
    to_state       TEXT         NOT NULL,
    reason         TEXT         NOT NULL DEFAULT '',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evoev_proposal ON aeis_evolution_events(proposal_id);

CREATE TABLE IF NOT EXISTS aeis_adaptations (
    adaptation_id  TEXT         PRIMARY KEY,
    adaptation_type TEXT        NOT NULL,
    trigger_metric TEXT         NOT NULL,
    trigger_value  REAL         NOT NULL DEFAULT 0,
    target_value   REAL         NOT NULL DEFAULT 0,
    strategy       TEXT         NOT NULL DEFAULT '',
    affected_modules JSONB      NOT NULL DEFAULT '[]',
    state          TEXT         NOT NULL DEFAULT 'PENDING',
    outcome        TEXT         NOT NULL DEFAULT '',
    confidence     REAL         NOT NULL DEFAULT 0,
    metadata       JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    applied_at     TIMESTAMPTZ  DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_adapt_type ON aeis_adaptations(adaptation_type);
CREATE INDEX IF NOT EXISTS idx_adapt_state ON aeis_adaptations(state);

CREATE TABLE IF NOT EXISTS aeis_feedback_signals (
    signal_id      TEXT         PRIMARY KEY,
    source         TEXT         NOT NULL,
    metric         TEXT         NOT NULL,
    value          REAL         NOT NULL,
    threshold      REAL         NOT NULL DEFAULT 0,
    severity       TEXT         NOT NULL DEFAULT 'info',
    message        TEXT         NOT NULL DEFAULT '',
    timestamp      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fb_metric ON aeis_feedback_signals(metric);
CREATE INDEX IF NOT EXISTS idx_fb_ts ON aeis_feedback_signals(timestamp);

CREATE TABLE IF NOT EXISTS aeis_adaptation_rules (
    rule_id        TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    trigger_metric TEXT         NOT NULL,
    condition_op   TEXT         NOT NULL DEFAULT '>',
    threshold      REAL         NOT NULL,
    adaptation_type TEXT        NOT NULL,
    strategy       TEXT         NOT NULL DEFAULT '',
    priority       INTEGER      NOT NULL DEFAULT 0,
    enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rule_metric ON aeis_adaptation_rules(trigger_metric);

COMMIT;
