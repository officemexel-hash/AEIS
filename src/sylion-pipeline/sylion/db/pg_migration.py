"""
sylion.db.pg_migration -- SYLION AEIS v3.5 PostgreSQL schema migration.

Creates the same 13 tables as sylion.db.migration but with PostgreSQL-native
types (JSONB instead of TEXT for JSON columns, TIMESTAMPTZ for timestamps).
Idempotent: safe to run multiple times (uses IF NOT EXISTS).
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def _normalize_advisor_layer_sql(sql: str) -> str:
    """Make legacy advisor-layer table/index DDL idempotent for the runner."""
    sql = re.sub(
        r"(?m)^CREATE TABLE (?!IF NOT EXISTS)(.+)$",
        r"CREATE TABLE IF NOT EXISTS \1",
        sql,
    )
    sql = re.sub(
        r"(?m)^CREATE INDEX (?!IF NOT EXISTS)(.+)$",
        r"CREATE INDEX IF NOT EXISTS \1",
        sql,
    )
    return sql


def _load_advisor_layer_sql() -> str:
    """Load the advisor-layer schema shipped alongside this module."""
    sql_path = Path(__file__).with_name("advisor_layer.sql")
    if not sql_path.exists():
        return ""
    return _normalize_advisor_layer_sql(sql_path.read_text(encoding="utf-8"))


_ADVISOR_LAYER_SQL = _load_advisor_layer_sql()


_PG_SCHEMA_SQL = """
-- ============================================================
-- SYLION AEIS v3.5 -- PostgreSQL database schema
-- ============================================================

-- 1. modules -- registered SYLION modules
CREATE TABLE IF NOT EXISTS modules (
    module_id   TEXT PRIMARY KEY,
    module_kind TEXT    NOT NULL,
    owner_plan  TEXT,
    description TEXT,
    lifecycle   TEXT    NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_modules_kind     ON modules(module_kind);
CREATE INDEX IF NOT EXISTS idx_modules_lifecycle ON modules(lifecycle);

-- 2. module_events -- event-bus persistence
CREATE TABLE IF NOT EXISTS module_events (
    event_id       TEXT PRIMARY KEY,
    topic          TEXT    NOT NULL,
    payload        JSONB,                        -- JSONB for structured querying
    source_module  TEXT,
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_topic   ON module_events(topic);
CREATE INDEX IF NOT EXISTS idx_events_source  ON module_events(source_module);
CREATE INDEX IF NOT EXISTS idx_events_ts      ON module_events(timestamp);

-- 3. evidence_entries -- evidence-spine append-only log
CREATE TABLE IF NOT EXISTS evidence_entries (
    entry_id    TEXT PRIMARY KEY,
    source_plan TEXT    NOT NULL,
    event_type  TEXT    NOT NULL,
    payload_hash TEXT   NOT NULL,
    prev_hash   TEXT,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evidence_plan  ON evidence_entries(source_plan);
CREATE INDEX IF NOT EXISTS idx_evidence_ts    ON evidence_entries(timestamp);

-- 4. decisions -- decision records
CREATE TABLE IF NOT EXISTS decisions (
    decision_id     TEXT PRIMARY KEY,
    decision_class  TEXT    NOT NULL,
    description     TEXT,
    source_plan     TEXT,
    module_id       TEXT,
    status          TEXT    NOT NULL DEFAULT 'pending',
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_decisions_class  ON decisions(decision_class);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_module ON decisions(module_id);

-- 5. council_sessions -- governance council sessions
CREATE TABLE IF NOT EXISTS council_sessions (
    session_id      TEXT PRIMARY KEY,
    proposal_id     TEXT,
    decision_class  TEXT,
    title           TEXT,
    status          TEXT    NOT NULL DEFAULT 'open',
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_council_status     ON council_sessions(status);
CREATE INDEX IF NOT EXISTS idx_council_proposal   ON council_sessions(proposal_id);

-- 6. council_votes -- individual votes within a session
CREATE TABLE IF NOT EXISTS council_votes (
    vote_id     TEXT PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    member_id   TEXT    NOT NULL,
    value       TEXT    NOT NULL,
    rationale   TEXT,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES council_sessions(session_id)
);
CREATE INDEX IF NOT EXISTS idx_votes_session ON council_votes(session_id);
CREATE INDEX IF NOT EXISTS idx_votes_member  ON council_votes(member_id);

-- 7. evidence_packs -- packaged evidence for proposals
CREATE TABLE IF NOT EXISTS evidence_packs (
    pack_id         TEXT PRIMARY KEY,
    proposal_id     TEXT,
    decision_class  TEXT,
    status          TEXT    NOT NULL DEFAULT 'draft',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_epacks_proposal ON evidence_packs(proposal_id);
CREATE INDEX IF NOT EXISTS idx_epacks_status   ON evidence_packs(status);

-- 8. evidence_artefacts -- individual artefacts within a pack
CREATE TABLE IF NOT EXISTS evidence_artefacts (
    artefact_id   TEXT PRIMARY KEY,
    pack_id       TEXT    NOT NULL,
    name          TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    content_hash  TEXT,
    FOREIGN KEY (pack_id) REFERENCES evidence_packs(pack_id)
);
CREATE INDEX IF NOT EXISTS idx_earpack_pack ON evidence_artefacts(pack_id);

-- 9. contracts -- inter-module contracts
CREATE TABLE IF NOT EXISTS contracts (
    contract_id      TEXT PRIMARY KEY,
    name             TEXT    NOT NULL,
    contract_type    TEXT    NOT NULL,
    version          INTEGER NOT NULL DEFAULT 1,
    schema_def       JSONB,                        -- JSONB for structured querying
    producer_module  TEXT
);
CREATE INDEX IF NOT EXISTS idx_contracts_name     ON contracts(name);
CREATE INDEX IF NOT EXISTS idx_contracts_producer ON contracts(producer_module);

-- 10. agents -- synthetic agent registry
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

-- 11. skills -- skill registry
CREATE TABLE IF NOT EXISTS skills (
    skill_id     TEXT PRIMARY KEY,
    name         TEXT    NOT NULL,
    domain       TEXT,
    lifecycle    TEXT    NOT NULL DEFAULT 'active',
    usage_count  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_skills_domain    ON skills(domain);
CREATE INDEX IF NOT EXISTS idx_skills_lifecycle ON skills(lifecycle);

-- 12. runs -- pipeline run tracking
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    project_name  TEXT    NOT NULL,
    phase         TEXT,
    progress      REAL    NOT NULL DEFAULT 0.0,
    status        TEXT    NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_runs_status   ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_project  ON runs(project_name);

-- 13. audit_log -- system-wide audit trail
CREATE TABLE IF NOT EXISTS audit_log (
    log_id     TEXT PRIMARY KEY,
    actor      TEXT    NOT NULL,
    action     TEXT    NOT NULL,
    resource   TEXT,
    result     TEXT,
    timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_ts     ON audit_log(timestamp);
"""

if _ADVISOR_LAYER_SQL:
    _PG_SCHEMA_SQL = f"{_PG_SCHEMA_SQL.rstrip()}\n\n{_ADVISOR_LAYER_SQL.strip()}\n"


def create_pg_engine(db_url: Optional[str] = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine for PostgreSQL.

    Parameters
    ----------
    db_url : str, optional
        PostgreSQL async connection string. Falls back to the
        ``SYLION_DB_URL`` environment variable.

    Returns
    -------
    AsyncEngine
        SQLAlchemy async engine configured for asyncpg.
    """
    url = (
        db_url
        or os.environ.get("SYLION_DB_URL")
        or os.environ.get("DATABASE_URL", "")
    )
    if not url:
        raise ValueError(
            "PostgreSQL URL required: pass db_url or set SYLION_DB_URL"
        )
    return create_async_engine(url, echo=False, pool_pre_ping=True)


async def run_pg_migration(engine: Optional[AsyncEngine] = None) -> AsyncEngine:
    """Execute the full PostgreSQL schema migration.

    Parameters
    ----------
    engine : AsyncEngine, optional
        Existing engine to use. If ``None``, a new one is created from
        the ``SYLION_DB_URL`` environment variable.

    Returns
    -------
    AsyncEngine
        The engine used for migration (caller is responsible for disposal).
    """
    _engine = engine or create_pg_engine()
    async with _engine.begin() as conn:
        await conn.execute(text(_PG_SCHEMA_SQL))
    return _engine


async def check_pg_health(engine: Optional[AsyncEngine] = None) -> dict:
    """Run a lightweight health check against PostgreSQL.

    Returns a dict with ``status``, ``db_mode`` and table count.
    """
    _engine = engine or create_pg_engine()
    try:
        async with _engine.connect() as conn:
            result = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            ))
            table_count = result.scalar()
        return {
            "status": "ok",
            "db_mode": "postgres",
            "tables": table_count,
        }
    except Exception as exc:
        return {
            "status": "error",
            "db_mode": "postgres",
            "error": str(exc),
        }
    finally:
        if engine is None:
            await _engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run SYLION AEIS v3.5 PostgreSQL migration"
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="PostgreSQL async URL (default: $SYLION_DB_URL)",
    )
    args = parser.parse_args()

    async def _main():
        _engine = await run_pg_migration(
            create_pg_engine(args.db_url) if args.db_url else None
        )
        health = await check_pg_health(_engine)
        print(f"Migration complete. {health.get('tables', '?')} tables created.")
        await _engine.dispose()

    asyncio.run(_main())
