"""Build FundingCard bodies + envelopes from scoring + gap data.

The engine builds the AdvisorCardEnvelope header; this module is responsible
for the funding-specific body and surfaces a helper that returns a ready
envelope for tests / non-engine flows.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sylion.aeis.advisor.engine._models import (
    AdvisorCardEnvelope,
    AdvisorCardHeader,
    FundingCard,
    Money as EngineMoney,
    confidence_label_for,
)
from sylion.aeis.advisor.funding._models import (
    FUNDING_SUGGESTION_TYPES,
    GrantProgram,
    ScoringHistoryEntry,
    SimulationScenario,
)
from sylion.aeis.advisor.funding.matcher.gap_analyzer import GapAnalysis


_D3_PLUS_TYPES = {
    "FUNDING_FORM_COMPANY",
    "FUNDING_CHANGE_LEGAL_FORM",
    "FUNDING_REGIONAL_RELOCATION",
}


def build_funding_card_body(
    *,
    suggestion_type: str,
    grant: GrantProgram,
    scoring: ScoringHistoryEntry,
    gap_analysis: GapAnalysis,
    headline_recommendation: str = "",
    consortium_required: bool = False,
    consortium_suggestions: list[dict[str, Any]] | None = None,
    static_simulations: list[SimulationScenario] | None = None,
    dynamic_simulations: list[SimulationScenario] | None = None,
    auto_simulations: list[SimulationScenario] | None = None,
    match_confidence: float = 0.0,
    deadline_at_risk: bool = False,
) -> FundingCard:
    if suggestion_type not in FUNDING_SUGGESTION_TYPES:
        raise ValueError(f"unknown suggestion_type: {suggestion_type}")

    breakdown = [_component_to_dict(c) for c in scoring.component_breakdown]
    actions = [
        {
            "action_id": a.action_id,
            "description": a.description,
            "difficulty": a.difficulty,
            "estimated_time_seconds": a.estimated_time_seconds,
            "estimated_cost": {"amount": a.estimated_cost.amount, "currency": a.estimated_cost.currency},
            "expected_score_delta": a.expected_score_delta,
            "requires_third_party": a.requires_third_party,
            "third_party_type": a.third_party_type,
        }
        for a in gap_analysis.recommended_actions
    ]

    return FundingCard(
        suggestion_type=suggestion_type,
        headline_recommendation=headline_recommendation,
        grant_program_id=grant.program_id,
        grant_program_name=grant.display_name,
        grant_source=grant.source,
        country=grant.country,
        region=grant.region,
        grant_amount_min=EngineMoney(amount=str(grant.amount_min_usd), currency="USD"),
        grant_amount_max=EngineMoney(amount=str(grant.amount_max_usd), currency="USD"),
        eligibility_score=scoring.total_score,
        eligibility_breakdown=breakdown,
        eligibility_floor_breached=scoring.eligibility_floor_breached,
        current_match_summary=_summarize_breakdown(scoring),
        gaps_to_qualify=list(gap_analysis.gaps_to_qualify),
        recommended_actions=actions,
        consortium_required=consortium_required,
        consortium_suggestions=list(consortium_suggestions or []),
        application_deadline=grant.call_close_at or 0.0,
        time_to_prepare_seconds=int(max(0, grant.call_close_at - grant.call_open_at)) if grant.call_close_at and grant.call_open_at else 0,
        deadline_at_risk=deadline_at_risk,
        static_simulations=[_scenario_to_dict(s) for s in (static_simulations or [])],
        dynamic_simulations=[_scenario_to_dict(s) for s in (dynamic_simulations or [])],
        auto_simulations=[_scenario_to_dict(s) for s in (auto_simulations or [])],
        match_confidence=match_confidence,
        scoring_profile_id=scoring.scoring_profile_id,
    )


def build_funding_envelope(
    *,
    operator_id: str,
    project_id: str,
    idea_id: str,
    body: FundingCard,
    rationale: str,
    confidence_score: float,
    risk_level: str = "medium",
    project_domain: str = "funding",
    project_type: str = "",
) -> AdvisorCardEnvelope:
    d_level = "D3" if body.suggestion_type in _D3_PLUS_TYPES else _default_d_level(body.suggestion_type)
    header = AdvisorCardHeader(
        card_type="funding",
        title=body.headline_recommendation or body.grant_program_name,
        rationale=rationale,
        confidence_score=confidence_score,
        confidence_label=confidence_label_for(confidence_score),
        sources=["rule_engine", "llm_judge"],
        risk_level=risk_level,
        project_domain=project_domain,
        project_type=project_type,
        project_id=project_id,
        idea_id=idea_id,
        d_level=d_level,
        operator_id=operator_id,
        emitting_module="sylion.aeis.advisor.funding",
    )
    return AdvisorCardEnvelope(header=header, funding=body)


def _default_d_level(suggestion_type: str) -> str:
    mapping = {
        "FUNDING_GRANT_FIT": "D0",
        "FUNDING_HOW_TO_QUALIFY": "D1",
        "FUNDING_FIND_CONSORTIUM": "D2",
        "FUNDING_ADJUST_IDEA_FOR_GRANT": "D2",
        "FUNDING_DEADLINE_WARNING": "D1",
        "FUNDING_GAP_CLOSURE_PLAN": "D2",
        "FUNDING_SCOPE_ADJUSTMENT": "D2",
    }
    return mapping.get(suggestion_type, "D1")


def _component_to_dict(c) -> dict[str, Any]:
    return {
        "component_id": c.component_id,
        "component_name": c.component_name,
        "weight_in_grant": c.weight_in_grant,
        "score": c.score,
        "hard_floor": c.hard_floor,
        "floor_breached": c.floor_breached,
        "explanation": c.explanation,
        "driving_factors": list(c.driving_factors),
    }


def _scenario_to_dict(s: SimulationScenario) -> dict[str, Any]:
    return {
        "scenario_id": s.scenario_id,
        "label": s.label,
        "mode": s.mode,
        "changes": [asdict(ch) for ch in s.changes],
        "resulting_eligibility_score": s.resulting_eligibility_score,
        "resulting_breakdown": [_component_to_dict(c) for c in s.resulting_breakdown],
        "cost_to_implement": {"amount": s.cost_to_implement.amount, "currency": s.cost_to_implement.currency},
        "time_to_implement_seconds": s.time_to_implement_seconds,
    }


def _summarize_breakdown(scoring: ScoringHistoryEntry) -> str:
    lines = []
    for c in scoring.component_breakdown:
        marker = "!" if c.floor_breached else ""
        lines.append(f"{c.component_id}={c.score:.0f}{marker}")
    return "; ".join(lines)
