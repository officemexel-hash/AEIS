"""Schema invariant validation for AdvisorCardEnvelope."""

from __future__ import annotations

from sylion.aeis.advisor.engine._models import (
    CARD_TYPES,
    CONFIDENCE_LABELS,
    DECISION_LEVELS,
    PRIORITIES,
    PUSH_PRIORITIES,
    RISK_LEVELS,
    AdvisorCardEnvelope,
    confidence_label_for,
)


class EnvelopeValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_envelope(env: AdvisorCardEnvelope) -> list[str]:
    errors: list[str] = []
    h = env.header

    if not h.card_id:
        errors.append("header.card_id missing")
    if h.card_type not in CARD_TYPES:
        errors.append(f"header.card_type invalid: {h.card_type}")
    if h.risk_level not in RISK_LEVELS:
        errors.append(f"header.risk_level invalid: {h.risk_level}")
    if h.priority not in PRIORITIES:
        errors.append(f"header.priority invalid: {h.priority}")
    if h.push_priority not in PUSH_PRIORITIES:
        errors.append(f"header.push_priority invalid: {h.push_priority}")
    if h.d_level not in DECISION_LEVELS:
        errors.append(f"header.d_level invalid: {h.d_level}")

    if not (0.0 <= h.confidence_score <= 1.0):
        errors.append(f"confidence_score out of range: {h.confidence_score}")
    expected_label = confidence_label_for(h.confidence_score)
    if h.confidence_label != expected_label:
        errors.append(
            f"confidence_label mismatch: score={h.confidence_score} label={h.confidence_label} "
            f"expected={expected_label}"
        )
    if h.confidence_label not in CONFIDENCE_LABELS:
        errors.append(f"confidence_label invalid: {h.confidence_label}")

    if h.d_level == "D5" and not h.evidence_pack_id:
        errors.append("D5 cards require evidence_pack_id")

    if env.decision and env.decision.recommendation_type in (
        "REC_TYPE_PURCHASE_PLAN",
        "REC_TYPE_DOWNGRADE_PLAN",
        "REC_TYPE_CANCEL_PLAN",
    ):
        idx = DECISION_LEVELS.index(h.d_level) if h.d_level in DECISION_LEVELS else -1
        if idx < DECISION_LEVELS.index("D3"):
            errors.append(f"subscription card requires d_level >= D3 (got {h.d_level})")
        if not h.evidence_pack_id:
            errors.append("subscription D3+ card requires evidence_pack_id")

    if env.decision and len(env.decision.alternatives) > 5:
        errors.append("decision.alternatives length > 5")

    if env.funding and env.funding.eligibility_floor_breached:
        if not env.funding.gaps_to_qualify:
            errors.append("funding floor breached but gaps_to_qualify empty")
        if not env.funding.recommended_actions:
            errors.append("funding floor breached but recommended_actions empty")

    if h.expires_at and h.created_at and h.expires_at <= h.created_at:
        errors.append("expires_at must be > created_at")

    if h.used_local_fallback:
        # Note: per design, the score has already been multiplied by 0.8 in calculator.
        # We can't recompute the raw here. Soft-check only if confidence_score is suspiciously high.
        if h.confidence_score > 0.8:
            errors.append("used_local_fallback=true but confidence_score > 0.8 (multiplier check)")

    if not h.audit_trail_id:
        errors.append("audit_trail_id missing")
    if "llm_judge" in h.sources and not h.llm_judge_audit_id:
        errors.append("llm_judge in sources but llm_judge_audit_id not set")

    return errors
