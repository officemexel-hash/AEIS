"""Funding card body builder.

The funding module owns full body construction (per ownership map). This file
provides envelope-side glue and a minimal default body so the engine can issue
funding-flavored envelopes when the funding module isn't running.
"""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.engine._models import FundingCard, Money


def build_funding_card(*, suggestion_type: str, payload: dict[str, Any]) -> FundingCard:
    return FundingCard(
        suggestion_type=suggestion_type,
        headline_recommendation=str(payload.get("headline_recommendation", "")),
        grant_program_id=str(payload.get("grant_program_id", "")),
        grant_program_name=str(payload.get("grant_program_name", "")),
        grant_source=str(payload.get("grant_source", "")),
        country=str(payload.get("country", "")),
        region=str(payload.get("region", "")),
        grant_amount_min=_money(payload.get("grant_amount_min")),
        grant_amount_max=_money(payload.get("grant_amount_max")),
        eligibility_score=float(payload.get("eligibility_score", 0.0)),
        eligibility_breakdown=list(payload.get("eligibility_breakdown") or []),
        eligibility_floor_breached=bool(payload.get("eligibility_floor_breached", False)),
        current_match_summary=str(payload.get("current_match_summary", "")),
        gaps_to_qualify=list(payload.get("gaps_to_qualify") or []),
        recommended_actions=list(payload.get("recommended_actions") or []),
        consortium_required=bool(payload.get("consortium_required", False)),
        consortium_suggestions=list(payload.get("consortium_suggestions") or []),
        application_deadline=float(payload.get("application_deadline") or 0.0),
        time_to_prepare_seconds=int(payload.get("time_to_prepare_seconds") or 0),
        deadline_at_risk=bool(payload.get("deadline_at_risk", False)),
        static_simulations=list(payload.get("static_simulations") or []),
        dynamic_simulations=list(payload.get("dynamic_simulations") or []),
        auto_simulations=list(payload.get("auto_simulations") or []),
        match_confidence=float(payload.get("match_confidence", 0.0)),
        scoring_profile_id=str(payload.get("scoring_profile_id", "")),
    )


def _money(v: Any) -> Money:
    if isinstance(v, dict):
        return Money(amount=str(v.get("amount", "0")), currency=str(v.get("currency", "USD")))
    return Money()
