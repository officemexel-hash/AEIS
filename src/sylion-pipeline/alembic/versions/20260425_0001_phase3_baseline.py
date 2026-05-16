"""phase3 baseline — pin existing schema as alembic v1.

Revision ID: phase3_0001_baseline
Revises:
Create Date: 2026-04-25

The schema this revision installs is byte-identical to the SQL string in
``sylion.db.pg_migration._PG_SCHEMA_SQL``. Bootstrap order is:

1. Fresh DB:  alembic upgrade head -> runs this file -> 13 core tables.
2. Existing DB (already migrated via run_pg_migration): the
   alembic_version row is missing but every table already exists; running
   this revision is idempotent (CREATE TABLE IF NOT EXISTS) and just
   marks the database as alembic-aware.

All future schema changes go through new revisions; the legacy
``run_pg_migration`` keeps working as a "first-touch bootstrap" but does
NOT add tables that aren't here. See `docs/phase3/postgres_migration.md`
for the contract.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "phase3_0001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Re-emits the canonical Postgres schema. Idempotent.

    We import the schema string from ``sylion.db.pg_migration`` so this
    file stays in sync without copy-paste; if you change the schema there
    AND want a versioned migration, write a NEW alembic revision instead
    of editing the canonical string."""
    from sylion.db.pg_migration import _PG_SCHEMA_SQL

    op.execute(_PG_SCHEMA_SQL)


def downgrade() -> None:
    """Drop the 13 core tables in dependency-safe order. Used only by
    manual rollback during the W1.4 / W1.5 DR drill."""
    op.execute("""
        DROP TABLE IF EXISTS contract_violations CASCADE;
        DROP TABLE IF EXISTS contracts             CASCADE;
        DROP TABLE IF EXISTS task_history          CASCADE;
        DROP TABLE IF EXISTS task_states           CASCADE;
        DROP TABLE IF EXISTS observability_traces  CASCADE;
        DROP TABLE IF EXISTS observability_logs    CASCADE;
        DROP TABLE IF EXISTS observability_metrics CASCADE;
        DROP TABLE IF EXISTS authz_audit           CASCADE;
        DROP TABLE IF EXISTS authz_principals      CASCADE;
        DROP TABLE IF EXISTS skills_runs           CASCADE;
        DROP TABLE IF EXISTS skills                CASCADE;
        DROP TABLE IF EXISTS module_events         CASCADE;
        DROP TABLE IF EXISTS modules               CASCADE;
    """)
