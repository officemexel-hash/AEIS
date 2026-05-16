"""AEIS Advisor — Scaling DB layer (PG-only).

Per 08_audit_revisions.md Revision 2. Schema lives in Alembic migration.
"""

from __future__ import annotations


def ensure_tables() -> None:
    """No-op in PG-only mode. Schema lives in Alembic migration."""
    return None
