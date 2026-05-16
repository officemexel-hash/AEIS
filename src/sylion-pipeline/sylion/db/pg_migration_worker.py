"""
SYLION DB -- Postgres schema & migration for Worker + Integration modules.

Provides SQL DDL for PostgreSQL and a one-way sync script from SQLite.
Tables mirror the SQLite schema but use proper Postgres types:
  - UUID / TEXT primary keys
  - JSONB for structured data
  - TIMESTAMP WITH TIME ZONE
  - Proper indexes and foreign keys

Usage:
    python scripts/migrate_to_postgres.py --sqlite-path sylion_aeis.db --pg-url postgresql://...
"""

from __future__ import annotations

import json
from typing import Any

WORKER_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS worker_registry (
    worker_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    host              TEXT NOT NULL DEFAULT 'localhost',
    status            TEXT NOT NULL DEFAULT 'active',
    capacity          INTEGER NOT NULL DEFAULT 3,
    api_key_hash      TEXT NOT NULL DEFAULT '',
    budget_limit      NUMERIC(16,4) NOT NULL DEFAULT 0.0,
    budget_spent      NUMERIC(16,4) NOT NULL DEFAULT 0.0,
    token_usage       BIGINT NOT NULL DEFAULT 0,
    last_heartbeat    TIMESTAMPTZ,
    assigned_modules  JSONB NOT NULL DEFAULT '[]',
    tags              JSONB NOT NULL DEFAULT '[]',
    metadata_json     JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_worker_status ON worker_registry(status);
CREATE INDEX IF NOT EXISTS idx_worker_host   ON worker_registry(host);

CREATE TABLE IF NOT EXISTS worker_assignments (
    assignment_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id         UUID NOT NULL REFERENCES worker_registry(worker_id) ON DELETE CASCADE,
    module_id         TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    priority          INTEGER NOT NULL DEFAULT 5,
    patch_proposal    TEXT,
    evidence_pack     JSONB,
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    error_log         TEXT,
    metadata_json     JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_asgn_worker ON worker_assignments(worker_id);
CREATE INDEX IF NOT EXISTS idx_asgn_module ON worker_assignments(module_id);
CREATE INDEX IF NOT EXISTS idx_asgn_status ON worker_assignments(status);

CREATE TABLE IF NOT EXISTS build_topology (
    topology_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    config_json       JSONB NOT NULL DEFAULT '{}',
    status            TEXT NOT NULL DEFAULT 'draft',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

INTEGRATION_DDL = """
CREATE TABLE IF NOT EXISTS candidate_builds (
    build_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    description       TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft',
    patch_ids         JSONB NOT NULL DEFAULT '[]',
    module_ids        JSONB NOT NULL DEFAULT '[]',
    validation_results JSONB NOT NULL DEFAULT '{}',
    evidence_pack     TEXT,
    error_log         TEXT,
    metadata_json     JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_build_status ON candidate_builds(status);

CREATE TABLE IF NOT EXISTS integration_results (
    result_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_id          UUID NOT NULL REFERENCES candidate_builds(build_id) ON DELETE CASCADE,
    stage             TEXT NOT NULL,
    success           BOOLEAN NOT NULL DEFAULT FALSE,
    stdout            TEXT,
    stderr            TEXT,
    duration_ms       INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_result_build ON integration_results(build_id);

CREATE TABLE IF NOT EXISTS drift_records (
    drift_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drift_type        TEXT NOT NULL,
    source_module     TEXT NOT NULL,
    target_module     TEXT,
    description       TEXT NOT NULL,
    severity          TEXT NOT NULL DEFAULT 'warning',
    status            TEXT NOT NULL DEFAULT 'open',
    resolution        TEXT,
    metadata_json     JSONB NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_drift_type   ON drift_records(drift_type);
CREATE INDEX IF NOT EXISTS idx_drift_source ON drift_records(source_module);
CREATE INDEX IF NOT EXISTS idx_drift_status ON drift_records(status);
"""


def get_all_ddl() -> str:
    return WORKER_REGISTRY_DDL + "\n" + INTEGRATION_DDL


def sync_sqlite_to_postgres(sqlite_path: str, pg_url: str) -> dict[str, Any]:
    """One-way sync of worker + integration data from SQLite to Postgres."""
    import sqlite3
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Postgres sync requires 'psycopg'. Install: pip install psycopg[binary]") from exc

    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    dst = psycopg.connect(pg_url)

    counts: dict[str, int] = {}

    tables = [
        "worker_registry",
        "worker_assignments",
        "build_topology",
        "candidate_builds",
        "integration_results",
        "drift_records",
    ]

    with dst.cursor() as cur:
        for table in tables:
            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                counts[table] = 0
                continue
            # Build INSERT with ON CONFLICT
            cols = list(rows[0].keys())
            col_str = ", ".join(cols)
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
            for row in rows:
                vals = []
                for c in cols:
                    v = row[c]
                    # Convert JSON strings to dicts for JSONB columns
                    if c.endswith("_json") or c in ("assigned_modules", "tags", "patch_ids", "module_ids", "validation_results", "evidence_pack"):
                        if isinstance(v, str):
                            try:
                                v = json.loads(v)
                            except Exception:
                                pass
                    vals.append(v)
                cur.execute(sql, vals)
            counts[table] = len(rows)

    dst.commit()
    src.close()
    dst.close()
    return {"synced": counts}
