"""advisor layer schemas and tables.

Revision ID: phase3_0002_advisor_layer
Revises: phase3_0001_baseline
Create Date: 2026-04-25
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "phase3_0002_advisor_layer"
down_revision: str | Sequence[str] | None = "phase3_0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the advisor-layer schema bundle."""
    sql_path = Path(__file__).resolve().parents[2] / "sylion" / "db" / "advisor_layer.sql"
    if sql_path.exists():
        op.execute(sql_path.read_text(encoding="utf-8"))
        return

    from sylion.db.pg_migration import _ADVISOR_LAYER_SQL

    op.execute(_ADVISOR_LAYER_SQL)


def downgrade() -> None:
    """Drop advisor schemas in reverse dependency order."""
    op.execute(
        """
        DROP SCHEMA IF EXISTS advisor_outbound CASCADE;
        DROP SCHEMA IF EXISTS advisor_evidence CASCADE;
        DROP SCHEMA IF EXISTS advisor_funding CASCADE;
        DROP SCHEMA IF EXISTS advisor_scaling CASCADE;
        DROP SCHEMA IF EXISTS advisor_subscription CASCADE;
        DROP SCHEMA IF EXISTS advisor_actions CASCADE;
        DROP SCHEMA IF EXISTS advisor_history CASCADE;
        DROP SCHEMA IF EXISTS advisor_engine CASCADE;
        DROP SCHEMA IF EXISTS advisor_pricing CASCADE;
        DROP SCHEMA IF EXISTS advisor_preferences CASCADE;
        DROP SCHEMA IF EXISTS advisor_events CASCADE;
        """
    )
