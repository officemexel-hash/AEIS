"""Per-grant scoring profile resolution.

Returns the active profile version for a given grant. Falls back to a default
profile (creating one on demand) when no profile is registered yet — important
when grants are loaded manually without an explicit profile.
"""

from __future__ import annotations

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import ScoringProfile


def resolve_profile(program_id: str, profile_id: str = "") -> ScoringProfile | None:
    if profile_id:
        return _db.fetch_profile_by_id(profile_id)
    return _db.fetch_active_profile_for_program(program_id)


def ensure_profile(program_id: str) -> ScoringProfile:
    """Return the active profile, creating a default one if missing."""
    profile = _db.fetch_active_profile_for_program(program_id)
    if profile:
        return profile
    profile = _db.make_default_profile(program_id)
    _db.insert_scoring_profile(profile)
    _db.update_grant_program(program_id, {"scoring_profile_id": profile.profile_id})
    return profile
