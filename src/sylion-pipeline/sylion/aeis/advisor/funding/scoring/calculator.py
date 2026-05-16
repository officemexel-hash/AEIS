"""Scoring calculator: apply a profile to (company, idea, grant)."""

from __future__ import annotations

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import (
    Company,
    ComponentScore,
    GrantProgram,
    IdeaContext,
    ScoringHistoryEntry,
    ScoringProfile,
)
from sylion.aeis.advisor.funding.scoring.components import COMPONENT_SCORERS
from sylion.aeis.advisor.funding.scoring.profile_loader import resolve_profile


def score_with_profile(
    company: Company,
    idea: IdeaContext,
    grant: GrantProgram,
    profile: ScoringProfile,
) -> tuple[float, list[ComponentScore], bool]:
    """Apply a profile and return (total_score, breakdown, eligibility_floor_breached)."""
    breakdown: list[ComponentScore] = []
    floor_breached = False
    weighted_total = 0.0
    weight_total = 0.0
    for entry in profile.components:
        scorer = COMPONENT_SCORERS.get(entry.component_id)
        if scorer is None:
            continue
        raw, factors = scorer(company, grant, idea)
        breached = entry.hard_floor > 0 and raw < entry.hard_floor
        if breached and entry.component_id == "eligibility":
            floor_breached = True
        breakdown.append(
            ComponentScore(
                component_id=entry.component_id,
                component_name=entry.component_id,
                weight_in_grant=entry.weight,
                score=raw,
                hard_floor=entry.hard_floor,
                floor_breached=breached,
                explanation="",
                driving_factors=factors,
            )
        )
        weighted_total += raw * entry.weight
        weight_total += entry.weight
    total = (weighted_total / weight_total) if weight_total > 0 else 0.0
    if floor_breached:
        total = min(total, profile_floor_cap(breakdown))
    return total, breakdown, floor_breached


def profile_floor_cap(breakdown: list[ComponentScore]) -> float:
    """When eligibility floor breached, cap effective total to <50 to signal block."""
    return 49.0


def compute_score(
    *,
    operator_id: str,
    company: Company,
    idea: IdeaContext,
    grant: GrantProgram,
    triggering_event: str = "manual_recalc",
    profile_id: str = "",
    persist: bool = True,
) -> ScoringHistoryEntry:
    profile = resolve_profile(grant.program_id, profile_id)
    if profile is None:
        from sylion.aeis.advisor.funding.scoring.profile_loader import ensure_profile
        profile = ensure_profile(grant.program_id)

    total, breakdown, floor_breached = score_with_profile(company, idea, grant, profile)
    entry = ScoringHistoryEntry(
        operator_id=operator_id,
        company_id=company.company_id,
        idea_id=idea.idea_id,
        program_id=grant.program_id,
        scoring_profile_id=profile.profile_id,
        total_score=total,
        component_breakdown=breakdown,
        eligibility_floor_breached=floor_breached,
        triggering_event=triggering_event,
    )
    if persist:
        _db.insert_scoring_history(entry)
    return entry
