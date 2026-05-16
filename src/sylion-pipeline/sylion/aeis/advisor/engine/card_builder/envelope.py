"""Wrap header + body in AdvisorCardEnvelope."""

from __future__ import annotations

from sylion.aeis.advisor.engine._models import (
    AdvisorCardEnvelope,
    AdvisorCardHeader,
    DecisionCard,
    FundingCard,
    OnboardingCard,
    ScalingCard,
    SecurityCard,
)


def build_envelope(
    *,
    header: AdvisorCardHeader,
    body: DecisionCard | FundingCard | SecurityCard | ScalingCard | OnboardingCard,
) -> AdvisorCardEnvelope:
    env = AdvisorCardEnvelope(envelope_version="1.0.0", header=header)
    if isinstance(body, DecisionCard):
        env.decision = body
        header.card_type = "decision"
    elif isinstance(body, FundingCard):
        env.funding = body
        header.card_type = "funding"
    elif isinstance(body, SecurityCard):
        env.security = body
        header.card_type = "security"
    elif isinstance(body, ScalingCard):
        env.scaling = body
        header.card_type = "scaling"
    elif isinstance(body, OnboardingCard):
        env.onboarding = body
        header.card_type = "onboarding"
    else:
        raise TypeError(f"unknown body type: {type(body)!r}")
    return env
