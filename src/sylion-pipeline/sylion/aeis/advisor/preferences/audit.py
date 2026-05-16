"""Audit helpers for advisor preference mutations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sylion.aeis.advisor.preferences import _db
from sylion.aeis.advisor.preferences._models import AuditRow


def log_change(
    *,
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
    old_value: Any,
    new_value: Any,
    change_type: str,
    changed_by: str,
    reason: str | None = None,
) -> str:
    """Append one audit row and return its id."""
    return _db.insert_audit_row(
        user_id=user_id,
        project_type=project_type,
        project_domain=project_domain,
        preference_key=preference_key,
        old_value=old_value,
        new_value=new_value,
        change_type=change_type,
        changed_by=changed_by,
        reason=reason,
    )


def get_history(
    user_id: str,
    *,
    since: datetime | None = None,
    limit: int = 100,
    filter_preference_key: str | None = None,
) -> list[AuditRow]:
    """Return audit history for one user."""
    return [
        AuditRow(
            audit_id=str(row["audit_id"]),
            user_id=str(row["user_id"]),
            project_type=row.get("project_type"),  # type: ignore[arg-type]
            project_domain=row.get("project_domain"),  # type: ignore[arg-type]
            preference_key=str(row["preference_key"]),
            old_value=row.get("old_value"),
            new_value=row.get("new_value"),
            change_type=str(row["change_type"]),
            changed_by=str(row["changed_by"]),
            changed_at=row["changed_at"],  # type: ignore[arg-type]
            reason=row.get("reason"),  # type: ignore[arg-type]
        )
        for row in _db.list_audit_rows(
            user_id,
            since=since,
            limit=limit,
            preference_key=filter_preference_key,
        )
    ]
