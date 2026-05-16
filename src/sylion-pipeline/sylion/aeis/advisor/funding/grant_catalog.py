"""Grant catalog: CRUD over `advisor_funding.grant_programs` + manual loading.

Manual loading creates a default scoring profile that spreads weights uniformly
across the universal component pool (per manifest §8 default_weights). Operators
or downstream automation can later override the profile.
"""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import (
    DEFAULT_HARD_FLOORS,
    GRANT_SOURCES,
    GrantProgram,
    ProfileComponentEntry,
    ScoringProfile,
    UNIVERSAL_COMPONENT_IDS,
)


def register_grant(
    *,
    display_name: str,
    source: str,
    country: str,
    region: str = "",
    program_code: str = "",
    managing_body: str = "",
    description: str = "",
    amount_min_usd: float = 0.0,
    amount_max_usd: float = 0.0,
    call_open_at: float = 0.0,
    call_close_at: float = 0.0,
    source_url: str = "",
    source_documents: list[dict[str, Any]] | None = None,
    custom_criteria: dict[str, Any] | None = None,
    is_user_loaded: bool = False,
    loaded_by: str = "",
    profile: ScoringProfile | None = None,
    profile_overrides: dict[str, dict[str, float]] | None = None,
) -> tuple[GrantProgram, ScoringProfile]:
    """Insert a grant program and ensure an active scoring profile exists.

    `profile_overrides` is a mapping `component_id -> {"weight": float, "hard_floor": float}`.
    When provided, weights are renormalised so they sum to 100.
    """
    if source not in GRANT_SOURCES:
        raise ValueError(f"unknown grant source: {source}")

    grant = GrantProgram(
        program_code=program_code,
        display_name=display_name,
        source=source,
        country=country,
        region=region,
        managing_body=managing_body,
        description=description,
        amount_min_usd=amount_min_usd,
        amount_max_usd=amount_max_usd,
        call_open_at=call_open_at,
        call_close_at=call_close_at,
        source_url=source_url,
        source_documents=list(source_documents or []),
        custom_criteria=dict(custom_criteria or {}),
        is_active=True,
        is_user_loaded=is_user_loaded,
        loaded_by=loaded_by,
    )
    _db.insert_grant_program(grant)

    if profile is None:
        if profile_overrides:
            profile = _build_profile_from_overrides(grant.program_id, profile_overrides)
        else:
            profile = _db.make_default_profile(grant.program_id)
    else:
        profile.program_id = grant.program_id

    _db.insert_scoring_profile(profile)
    _db.update_grant_program(grant.program_id, {"scoring_profile_id": profile.profile_id})
    grant.scoring_profile_id = profile.profile_id
    return grant, profile


def load_grant_manually(
    *,
    operator_id: str,
    display_name: str,
    source: str,
    country: str,
    region: str = "",
    description: str = "",
    amount_max_usd: float = 0.0,
    custom_criteria: dict[str, Any] | None = None,
    profile_overrides: dict[str, dict[str, float]] | None = None,
) -> tuple[GrantProgram, ScoringProfile]:
    """Operator-initiated grant load. Forces is_user_loaded=true and source=custom by default."""
    return register_grant(
        display_name=display_name,
        source=source or "custom",
        country=country,
        region=region,
        description=description,
        amount_max_usd=amount_max_usd,
        custom_criteria=custom_criteria,
        is_user_loaded=True,
        loaded_by=operator_id,
        profile_overrides=profile_overrides,
    )


def get_grant(program_id: str) -> GrantProgram | None:
    return _db.fetch_grant_program(program_id)


def list_grants(
    *, country: str | None = None, region: str | None = None
) -> list[GrantProgram]:
    return _db.fetch_active_grant_programs(country=country, region=region)


def disable_grant(program_id: str) -> None:
    _db.update_grant_program(program_id, {"is_active": False})


def get_active_profile(program_id: str) -> ScoringProfile | None:
    return _db.fetch_active_profile_for_program(program_id)


def _build_profile_from_overrides(
    program_id: str, overrides: dict[str, dict[str, float]]
) -> ScoringProfile:
    components = []
    raw_weights: dict[str, float] = {}
    for cid in UNIVERSAL_COMPONENT_IDS:
        if cid in overrides:
            raw_weights[cid] = float(overrides[cid].get("weight", 0.0))
    total = sum(raw_weights.values())
    factor = (100.0 / total) if total > 0 else 0.0
    for cid in UNIVERSAL_COMPONENT_IDS:
        if cid not in overrides:
            continue
        ov = overrides[cid]
        components.append(
            ProfileComponentEntry(
                component_id=cid,
                weight=raw_weights[cid] * factor,
                hard_floor=float(ov.get("hard_floor", DEFAULT_HARD_FLOORS.get(cid, 0.0))),
            )
        )
    if not components:
        return _db.make_default_profile(program_id)
    return ScoringProfile(program_id=program_id, components=components, total_weight=100.0)
