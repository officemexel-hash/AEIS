"""Partner matching for grant + company combos."""

from __future__ import annotations

from sylion.aeis.advisor.funding import _db
from sylion.aeis.advisor.funding._models import (
    Company,
    ConsortiumSuggestion,
    GrantProgram,
)


def suggest_partners(
    *,
    grant: GrantProgram,
    company: Company,
    requirements: list[str] | None = None,
    limit: int = 5,
) -> list[ConsortiumSuggestion]:
    """Return up to `limit` partners that satisfy the grant's region + entity_type."""
    custom = grant.custom_criteria or {}
    if not custom.get("requires_consortium", False):
        return []

    needed_types: list[str] = list(
        custom.get("required_consortium_entity_types") or ["research_institution"]
    )
    region = grant.region or ""

    suggestions: list[ConsortiumSuggestion] = []
    for entity_type in needed_types:
        partners = _db.fetch_consortium_partners(
            entity_type=entity_type,
            country=grant.country or None,
            region=region or None,
        )
        for p in partners:
            suggestions.append(
                ConsortiumSuggestion(
                    suggestion_id=p.partner_id,
                    entity_type=p.entity_type,
                    suggested_name=p.display_name,
                    required_qualifications=list(requirements or p.qualifications),
                    region_constraint=region,
                    rationale=(
                        f"Partner {p.display_name} matches required type "
                        f"{entity_type} in {p.country or 'any'}/{p.region or 'any'}."
                    ),
                )
            )
            if len(suggestions) >= limit:
                return suggestions

        if not partners:
            suggestions.append(
                ConsortiumSuggestion(
                    entity_type=entity_type,
                    suggested_name="",
                    required_qualifications=list(requirements or []),
                    region_constraint=region,
                    rationale=(
                        f"No partner of type {entity_type} in pool for region "
                        f"{region or 'any'}; recommend external sourcing."
                    ),
                )
            )
    return suggestions[:limit]
