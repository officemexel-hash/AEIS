"""Effective preference resolution for the advisor preferences module."""

from __future__ import annotations

from sylion.aeis.advisor.preferences import _db
from sylion.aeis.advisor.preferences._models import (
    PreferenceRow,
    ResolvedPreference,
    ResolutionLevel,
)


def resolve_effective(
    *,
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
) -> ResolvedPreference:
    """Resolve the effective value using the 4-level fallback cascade."""
    candidates = (
        (project_type, project_domain, ResolutionLevel.SPECIFIC),
        (project_type, None, ResolutionLevel.TYPE_ONLY),
        (None, project_domain, ResolutionLevel.DOMAIN_ONLY),
        (None, None, ResolutionLevel.USER_DEFAULT),
    )
    for candidate_type, candidate_domain, level in candidates:
        row = _db.get_preference_row(user_id, candidate_type, candidate_domain, preference_key)
        if row is not None:
            return ResolvedPreference(
                value=row["preference_value"],
                resolution_level=level,
                source_row=_to_preference_row(row),
            )
    return ResolvedPreference(
        value=_db.get_system_default(preference_key),
        resolution_level=ResolutionLevel.SYSTEM_DEFAULT,
        source_row=None,
    )


def get_explicit(
    *,
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
) -> PreferenceRow | None:
    """Return one explicit row without fallback."""
    row = _db.get_preference_row(user_id, project_type, project_domain, preference_key)
    return None if row is None else _to_preference_row(row)


def find_most_specific_existing_level(
    *,
    user_id: str,
    project_type: str | None,
    project_domain: str | None,
    preference_key: str,
) -> tuple[str | None, str | None] | None:
    """Return the most specific explicit level already present for the key."""
    for candidate_type, candidate_domain in (
        (project_type, project_domain),
        (project_type, None),
        (None, project_domain),
        (None, None),
    ):
        if _db.get_preference_row(user_id, candidate_type, candidate_domain, preference_key):
            return candidate_type, candidate_domain
    return None


def _to_preference_row(row: dict[str, object]) -> PreferenceRow:
    return PreferenceRow(
        user_id=str(row["user_id"]),
        project_type=row.get("project_type"),  # type: ignore[arg-type]
        project_domain=row.get("project_domain"),  # type: ignore[arg-type]
        preference_key=str(row["preference_key"]),
        preference_value=row.get("preference_value"),
        set_by=str(row["set_by"]),
        created_at=row["created_at"],  # type: ignore[arg-type]
        updated_at=row["updated_at"],  # type: ignore[arg-type]
    )
