"""Direction C: gap analysis — what's blocking eligibility + how to qualify."""

from __future__ import annotations

from dataclasses import dataclass

from sylion.aeis.advisor.funding._models import (
    ComponentScore,
    Money,
    RecommendedAction,
    ScoringHistoryEntry,
)


@dataclass
class GapAnalysis:
    gaps_to_qualify: list[str]
    recommended_actions: list[RecommendedAction]
    eligibility_floor_breached: bool


_DEFAULT_ACTIONS: dict[str, dict[str, str]] = {
    "eligibility": {
        "description": "Adjust legal form / MŚP status / PKD codes to match grant requirements.",
        "difficulty": "moderate",
        "third_party_type": "accounting_firm",
    },
    "thematic_alignment": {
        "description": "Re-align idea narrative with the grant's call topic and keywords.",
        "difficulty": "easy",
        "third_party_type": "",
    },
    "capacity": {
        "description": "Increase R&D budget allocation or expand the team with key personnel.",
        "difficulty": "hard",
        "third_party_type": "",
    },
    "competitive_position": {
        "description": "Strengthen unique-value-proposition vs prior winning applicants.",
        "difficulty": "moderate",
        "third_party_type": "",
    },
    "regional_fit": {
        "description": "Open a regional branch or relocate registered office to qualify.",
        "difficulty": "very_hard",
        "third_party_type": "lawyer",
    },
    "consortium_readiness": {
        "description": "Engage a consortium partner from the recommended pool.",
        "difficulty": "moderate",
        "third_party_type": "consortium_partner",
    },
    "timeline_fit": {
        "description": "Tighten preparation plan or defer to next call window.",
        "difficulty": "easy",
        "third_party_type": "",
    },
}


def analyze_gaps(scoring: ScoringHistoryEntry, threshold: float = 60.0) -> GapAnalysis:
    """Inspect a scoring breakdown and surface gaps + recommended actions."""
    gaps: list[str] = []
    actions: list[RecommendedAction] = []
    for comp in scoring.component_breakdown:
        if comp.floor_breached or comp.score < threshold:
            gaps.append(_describe_gap(comp))
            actions.append(_action_for(comp))
    if scoring.eligibility_floor_breached and not actions:
        # Defensive: ensure floor breach always emits at least one action
        for comp in scoring.component_breakdown:
            if comp.component_id == "eligibility":
                gaps.append(_describe_gap(comp))
                actions.append(_action_for(comp))
                break
    return GapAnalysis(
        gaps_to_qualify=gaps,
        recommended_actions=actions,
        eligibility_floor_breached=scoring.eligibility_floor_breached,
    )


def _describe_gap(comp: ComponentScore) -> str:
    bits = [f"component={comp.component_id}", f"score={comp.score:.1f}"]
    if comp.hard_floor:
        bits.append(f"floor={comp.hard_floor:.1f}")
    if comp.driving_factors:
        bits.append("factors=" + "; ".join(comp.driving_factors[:3]))
    return " ".join(bits)


def _action_for(comp: ComponentScore) -> RecommendedAction:
    template = _DEFAULT_ACTIONS.get(comp.component_id, {
        "description": f"Improve {comp.component_id} component score.",
        "difficulty": "moderate",
        "third_party_type": "",
    })
    delta = max(0.0, 100.0 - comp.score) * (comp.weight_in_grant / 100.0)
    return RecommendedAction(
        description=template["description"],
        difficulty=template["difficulty"],
        estimated_time_seconds=86400 if template["difficulty"] in ("easy", "trivial") else 7 * 86400,
        estimated_cost=Money(amount="0", currency="USD"),
        expected_score_delta=round(delta, 2),
        requires_third_party=bool(template["third_party_type"]),
        third_party_type=template["third_party_type"],
    )
