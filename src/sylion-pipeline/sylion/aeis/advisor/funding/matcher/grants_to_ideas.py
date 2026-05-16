"""Direction B: grant -> [ideas]."""

from __future__ import annotations

from dataclasses import dataclass

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import (
    Company,
    GrantProgram,
    IdeaContext,
    ScoringHistoryEntry,
)
from sylion.aeis.advisor.funding.scoring.calculator import compute_score


@dataclass
class IdeaMatch:
    idea: IdeaContext
    scoring: ScoringHistoryEntry


def list_matching_ideas(
    *,
    operator_id: str,
    program_id: str,
    company: Company,
    candidate_ideas: list[IdeaContext],
    triggering_event: str = "grant_data_refresh",
    persist: bool = True,
) -> list[IdeaMatch]:
    """Score each candidate idea against a single grant.

    The funding module is decoupled from IdeaVault; callers project ideas into
    `IdeaContext` first.
    """
    grant = _db.fetch_grant_program(program_id)
    if grant is None:
        return []

    matches: list[IdeaMatch] = []
    for idea in candidate_ideas:
        entry = compute_score(
            operator_id=operator_id,
            company=company,
            idea=idea,
            grant=grant,
            triggering_event=triggering_event,
            persist=persist,
        )
        matches.append(IdeaMatch(idea=idea, scoring=entry))
    matches.sort(key=lambda m: m.scoring.total_score, reverse=True)
    return matches
