"""Direction A: idea -> [grants]."""

from __future__ import annotations

from dataclasses import dataclass

from sylion.aeis.advisor.funding import _db, company_manager
from sylion.aeis.advisor.funding._models import (
    Company,
    GrantProgram,
    IdeaContext,
    ScoringHistoryEntry,
)
from sylion.aeis.advisor.funding.scoring.calculator import compute_score


@dataclass
class GrantMatch:
    grant: GrantProgram
    scoring: ScoringHistoryEntry


def list_eligible_grants(
    *,
    operator_id: str,
    company_id: str,
    idea: IdeaContext,
    countries: list[str] | None = None,
    triggering_event: str = "idea_change",
    persist: bool = True,
) -> list[GrantMatch]:
    """Score the idea + company against every active grant in `countries`.

    `countries` defaults to the company's home country plus EU. Region filter
    excludes regional grants whose region != company.region.
    """
    company = company_manager.get_company(company_id)
    if company is None:
        return []
    countries = list(countries or [company.country])
    if "EU" not in countries:
        countries.append("EU")

    matches: list[GrantMatch] = []
    for c in countries:
        grants = _db.fetch_active_grant_programs(country=c)
        for grant in grants:
            if not _region_compatible(company, grant):
                continue
            entry = compute_score(
                operator_id=operator_id,
                company=company,
                idea=idea,
                grant=grant,
                triggering_event=triggering_event,
                persist=persist,
            )
            matches.append(GrantMatch(grant=grant, scoring=entry))

    matches.sort(key=lambda m: m.scoring.total_score, reverse=True)
    return matches


def _region_compatible(company: Company, grant: GrantProgram) -> bool:
    if not grant.region:
        return True
    return (company.region or "").upper() == grant.region.upper()
