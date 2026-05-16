"""Build AdvisorCardHeader from accumulated context + judge output + confidence."""

from __future__ import annotations

import time
from typing import Any

from sylion.aeis.advisor.engine._models import (
    AdvisorCardHeader,
    CardContext,
    confidence_label_for,
    new_uuid,
)
from sylion.aeis.advisor.engine.confidence.calculator import ConfidenceBreakdown


def build_header(
    *,
    context: CardContext,
    title: str,
    rationale: str,
    risk_level: str,
    risk_explanation: str,
    confidence: ConfidenceBreakdown,
    sources: list[str],
    d_level: str,
    d_level_trace: dict[str, Any],
    evidence_pack_id: str = "",
    llm_judge_audit_id: str = "",
    history_based: bool = False,
    related_history_card_ids: list[str] | None = None,
    push_priority: str = "normal",
    requires_biometric: bool = False,
    parent_card_id: str = "",
    card_type: str = "decision",
) -> AdvisorCardHeader:
    h = AdvisorCardHeader(
        card_id=new_uuid(),
        schema_version="1.0.0",
        card_type=card_type,
        parent_card_id=parent_card_id,
        title=title,
        rationale=rationale,
        confidence_score=confidence.final_score,
        confidence_label=confidence_label_for(confidence.final_score),
        sources=sources,
        risk_level=risk_level,
        risk_explanation=risk_explanation,
        project_domain=context.project_domain,
        project_type=context.project_type,
        project_id=context.project_id,
        idea_id=context.idea_id,
        d_level=d_level,
        evidence_pack_id=evidence_pack_id,
        history_based=history_based,
        related_history_card_ids=related_history_card_ids or [],
        historical_acceptance_rate=confidence.historical_acceptance_rate,
        created_at=time.time(),
        updated_at=time.time(),
        priority=_priority_for(risk_level),
        tags=[],
        dont_learn=False,
        human_gate_required=d_level in ("D3", "D4", "D5"),
        mobile_allowed=True,
        requires_biometric=requires_biometric,
        push_priority=push_priority,
        audit_trail_id=new_uuid(),
        llm_judge_audit_id=llm_judge_audit_id,
        operator_id=context.operator_id,
        emitting_module="sylion.aeis.advisor.engine",
        used_local_fallback=confidence.used_local_fallback,
        local_fallback_reason="" if not confidence.used_local_fallback else "external_unavailable",
        d_level_assignment_trace=d_level_trace,
    )
    return h


def _priority_for(risk_level: str) -> str:
    return {
        "low": "low",
        "medium": "normal",
        "high": "high",
        "critical": "urgent",
    }.get(risk_level, "normal")
