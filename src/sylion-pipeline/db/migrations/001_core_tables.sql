-- SYLION AEIS PostgreSQL Migration 001: Core Tables
-- Migrates all SQLite-backed services to PostgreSQL 16

BEGIN;

-- Core: Event Bus (append-only)
CREATE TABLE IF NOT EXISTS event_log (
    event_id       BIGSERIAL    PRIMARY KEY,
    topic          TEXT         NOT NULL,
    payload        JSONB        NOT NULL DEFAULT '{}',
    source_module  TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_event_log_topic ON event_log(topic);
CREATE INDEX IF NOT EXISTS idx_event_log_source ON event_log(source_module);
CREATE INDEX IF NOT EXISTS idx_event_log_created ON event_log(created_at);

-- Core: Contract Registry
CREATE TABLE IF NOT EXISTS contracts (
    contract_id    TEXT         PRIMARY KEY,
    module_id      TEXT         NOT NULL,
    version        TEXT         NOT NULL DEFAULT '1.0.0',
    proto_def      TEXT         NOT NULL DEFAULT '',
    status         TEXT         NOT NULL DEFAULT 'DRAFT',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_contracts_module ON contracts(module_id);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);

-- Core: Module Registry
CREATE TABLE IF NOT EXISTS modules (
    module_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    layer          TEXT         NOT NULL DEFAULT '',
    port           INTEGER      DEFAULT NULL,
    status         TEXT         NOT NULL DEFAULT 'registered',
    contract_id    TEXT         DEFAULT NULL REFERENCES contracts(contract_id),
    config         JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_modules_layer ON modules(layer);
CREATE INDEX IF NOT EXISTS idx_modules_status ON modules(status);

-- Core: Decision Gate Engine
CREATE TABLE IF NOT EXISTS decisions (
    decision_id    TEXT         PRIMARY KEY,
    title          TEXT         NOT NULL,
    decision_class TEXT         NOT NULL DEFAULT 'D0',
    status         TEXT         NOT NULL DEFAULT 'OPEN',
    rationale      TEXT         NOT NULL DEFAULT '',
    evidence_pack  JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ  DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_class ON decisions(decision_class);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);

-- Core: Evidence Spine
CREATE TABLE IF NOT EXISTS evidence_records (
    evidence_id    TEXT         PRIMARY KEY,
    source         TEXT         NOT NULL,
    claim          TEXT         NOT NULL DEFAULT '',
    hash           TEXT         NOT NULL DEFAULT '',
    signature      TEXT         NOT NULL DEFAULT '',
    verified       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence_records(source);

-- Core: Bundle Assembler
CREATE TABLE IF NOT EXISTS bundles (
    bundle_id      TEXT         PRIMARY KEY,
    name           TEXT         NOT NULL,
    version        TEXT         NOT NULL DEFAULT '1.0.0',
    modules        JSONB        NOT NULL DEFAULT '[]',
    status         TEXT         NOT NULL DEFAULT 'DRAFT',
    checksum       TEXT         NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Core: Manifests
CREATE TABLE IF NOT EXISTS manifests (
    manifest_id    TEXT         PRIMARY KEY,
    bundle_id      TEXT         NOT NULL REFERENCES bundles(bundle_id),
    content        JSONB        NOT NULL DEFAULT '{}',
    version        TEXT         NOT NULL DEFAULT '1.0.0',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_manifests_bundle ON manifests(bundle_id);

-- Core: Health Monitor
CREATE TABLE IF NOT EXISTS health_checks (
    check_id       TEXT         PRIMARY KEY,
    module_id      TEXT         NOT NULL,
    status         TEXT         NOT NULL DEFAULT 'unknown',
    message        TEXT         NOT NULL DEFAULT '',
    latency_ms     REAL         NOT NULL DEFAULT 0,
    checked_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_health_module ON health_checks(module_id);
CREATE INDEX IF NOT EXISTS idx_health_checked ON health_checks(checked_at);

-- Core: Rollback Manager
CREATE TABLE IF NOT EXISTS rollback_snapshots (
    snapshot_id    TEXT         PRIMARY KEY,
    target         TEXT         NOT NULL,
    state_data     JSONB        NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    restored_at    TIMESTAMPTZ  DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_rollback_target ON rollback_snapshots(target);

-- Core: Lifecycle Gates
CREATE TABLE IF NOT EXISTS lifecycle_gates (
    gate_id        TEXT         PRIMARY KEY,
    module_id      TEXT         NOT NULL,
    gate_type      TEXT         NOT NULL,
    status         TEXT         NOT NULL DEFAULT 'pending',
    checked_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_lifecycle_module ON lifecycle_gates(module_id);

COMMIT;
