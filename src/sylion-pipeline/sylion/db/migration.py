"""
sylion.db.migration — SYLION AEIS v3.5 database schema migration.

Creates all tables required by the 65 SYLION modules and the dashboard.
Idempotent: safe to run multiple times (uses IF NOT EXISTS).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional


_SCHEMA_SQL = """
-- ============================================================
-- SYLION AEIS v3.5 — complete database schema
-- ============================================================

-- 1. modules — registered SYLION modules
CREATE TABLE IF NOT EXISTS modules (
    module_id   TEXT PRIMARY KEY,
    module_kind TEXT    NOT NULL,
    owner_plan  TEXT,
    description TEXT,
    lifecycle   TEXT    NOT NULL DEFAULT 'active',
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_modules_kind     ON modules(module_kind);
CREATE INDEX IF NOT EXISTS idx_modules_lifecycle ON modules(lifecycle);

-- 2. module_events — event-bus persistence
CREATE TABLE IF NOT EXISTS module_events (
    event_id       TEXT PRIMARY KEY,
    topic          TEXT    NOT NULL,
    payload        TEXT,                          -- JSON
    source_module  TEXT,
    timestamp      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_events_topic   ON module_events(topic);
CREATE INDEX IF NOT EXISTS idx_events_source  ON module_events(source_module);
CREATE INDEX IF NOT EXISTS idx_events_ts      ON module_events(timestamp);

-- 3. evidence_entries — evidence-spine append-only log
CREATE TABLE IF NOT EXISTS evidence_entries (
    entry_id    TEXT PRIMARY KEY,
    source_plan TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    payload_hash TEXT   NOT NULL,
    prev_hash   TEXT,
    timestamp   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_plan  ON evidence_entries(source_plan);
CREATE INDEX IF NOT EXISTS idx_evidence_ts    ON evidence_entries(timestamp);

-- 4. decisions — decision records
CREATE TABLE IF NOT EXISTS decisions (
    decision_id     TEXT PRIMARY KEY,
    decision_class  TEXT    NOT NULL,
    description     TEXT,
    source_plan     TEXT,
    module_id       TEXT,
    status          TEXT    NOT NULL DEFAULT 'pending',
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_decisions_class  ON decisions(decision_class);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_module ON decisions(module_id);

-- 5. council_sessions — governance council sessions
CREATE TABLE IF NOT EXISTS council_sessions (
    session_id      TEXT PRIMARY KEY,
    proposal_id     TEXT,
    decision_class  TEXT,
    title           TEXT,
    status          TEXT    NOT NULL DEFAULT 'open',
    opened_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_council_status     ON council_sessions(status);
CREATE INDEX IF NOT EXISTS idx_council_proposal   ON council_sessions(proposal_id);

-- 6. council_votes — individual votes within a session
CREATE TABLE IF NOT EXISTS council_votes (
    vote_id     TEXT PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    member_id   TEXT    NOT NULL,
    value       TEXT    NOT NULL,
    rationale   TEXT,
    timestamp   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    FOREIGN KEY (session_id) REFERENCES council_sessions(session_id)
);
CREATE INDEX IF NOT EXISTS idx_votes_session ON council_votes(session_id);
CREATE INDEX IF NOT EXISTS idx_votes_member  ON council_votes(member_id);

-- 7. evidence_packs — packaged evidence for proposals
CREATE TABLE IF NOT EXISTS evidence_packs (
    pack_id         TEXT PRIMARY KEY,
    proposal_id     TEXT,
    decision_class  TEXT,
    status          TEXT    NOT NULL DEFAULT 'draft',
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_epacks_proposal ON evidence_packs(proposal_id);
CREATE INDEX IF NOT EXISTS idx_epacks_status   ON evidence_packs(status);

-- 8. evidence_artefacts — individual artefacts within a pack
CREATE TABLE IF NOT EXISTS evidence_artefacts (
    artefact_id   TEXT PRIMARY KEY,
    pack_id       TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    content_hash  TEXT,
    FOREIGN KEY (pack_id) REFERENCES evidence_packs(pack_id)
);
CREATE INDEX IF NOT EXISTS idx_earpack_pack ON evidence_artefacts(pack_id);

-- 9. contracts — inter-module contracts
CREATE TABLE IF NOT EXISTS contracts (
    contract_id      TEXT PRIMARY KEY,
    name             TEXT    NOT NULL,
    contract_type    TEXT    NOT NULL,
    version          INTEGER NOT NULL DEFAULT 1,
    schema_def       TEXT,                          -- JSON schema
    producer_module  TEXT
);
CREATE INDEX IF NOT EXISTS idx_contracts_name     ON contracts(name);
CREATE INDEX IF NOT EXISTS idx_contracts_producer ON contracts(producer_module);

-- 10. agents — synthetic agent registry
CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    name        TEXT    NOT NULL,
    role        TEXT,
    department  TEXT,
    level       INTEGER NOT NULL DEFAULT 1,
    status      TEXT    NOT NULL DEFAULT 'active',
    health      TEXT    NOT NULL DEFAULT 'ok'
);
CREATE INDEX IF NOT EXISTS idx_agents_status     ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_department ON agents(department);

-- 11. skills — skill registry
CREATE TABLE IF NOT EXISTS skills (
    skill_id     TEXT PRIMARY KEY,
    name         TEXT    NOT NULL,
    domain       TEXT,
    lifecycle    TEXT    NOT NULL DEFAULT 'active',
    usage_count  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_skills_domain    ON skills(domain);
CREATE INDEX IF NOT EXISTS idx_skills_lifecycle ON skills(lifecycle);

-- 12. runs — pipeline run tracking
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    project_name  TEXT    NOT NULL,
    phase         TEXT,
    progress      REAL    NOT NULL DEFAULT 0.0,
    status        TEXT    NOT NULL DEFAULT 'pending',
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_runs_status   ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_project  ON runs(project_name);

-- 13. audit_log — system-wide audit trail
CREATE TABLE IF NOT EXISTS audit_log (
    log_id     TEXT PRIMARY KEY,
    actor      TEXT    NOT NULL,
    action     TEXT    NOT NULL,
    resource   TEXT,
    result     TEXT,
    timestamp  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_ts     ON audit_log(timestamp);
"""


def run_migration(db_path: str = "sylion_aeis.db") -> sqlite3.Connection:
    """Execute the full schema migration.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.  Use ``":memory:"`` for an
        in-memory database (useful in tests).

    Returns
    -------
    sqlite3.Connection
        Open connection to the database with the schema applied.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run SYLION AEIS v3.5 database migration"
    )
    parser.add_argument(
        "--db-path",
        default="sylion_aeis.db",
        help="Path to the SQLite database (default: sylion_aeis.db)",
    )
    args = parser.parse_args()

    conn = run_migration(args.db_path)
    # Quick sanity check: count tables
    cursor = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    table_count = cursor.fetchone()[0]
    print(f"Migration complete. {table_count} tables created in {args.db_path}")
    conn.close()
