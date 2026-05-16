"""Build a DecisionCard body from context + judge output."""

from __future__ import annotations

from typing import Any

from sylion.aeis.advisor.engine._models import (
    Alternative,
    CardContext,
    DecisionCard,
    Impact,
)


def build_decision_card(
    *,
    context: CardContext,
    judge_output: dict[str, Any],
    recommendation_type: str,
) -> DecisionCard:
    cost_impact = _impact_from(
        context.pricing_snapshot,
        unit="USD",
        absolute_value=str(context.cost_estimate_usd),
    )
    token_impact = _impact_from(context.pricing_snapshot, unit="tokens", absolute_value="0")
    time_impact = Impact(unit="seconds", absolute_value="0", estimate_confidence="assumption", is_assumption=True)

    judge_cost = _float_or_zero(judge_output.get("_llm_judge_cost_usd"))
    judge_tokens = _int_or_zero(judge_output.get("_llm_judge_prompt_tokens")) + _int_or_zero(
        judge_output.get("_llm_judge_response_tokens")
    )
    judge_latency_ms = _int_or_zero(judge_output.get("_llm_judge_latency_ms"))
    if judge_cost > 0:
        cost_impact = Impact(
            absolute_value=f"{judge_cost:.6f}",
            unit="USD",
            delta_vs_baseline_pct=0.0,
            baseline_label="llm_judge",
            estimate_confidence="measured",
            is_assumption=False,
            source_label="llm_judge_audit",
        )
    if judge_tokens > 0:
        token_impact = Impact(
            absolute_value=str(judge_tokens),
            unit="tokens",
            delta_vs_baseline_pct=0.0,
            baseline_label="llm_judge",
            estimate_confidence="measured",
            is_assumption=False,
            source_label="llm_judge_audit",
        )
    if judge_latency_ms > 0:
        time_impact = Impact(
            absolute_value=f"{judge_latency_ms / 1000.0:.3f}",
            unit="seconds",
            delta_vs_baseline_pct=0.0,
            baseline_label="llm_judge",
            estimate_confidence="measured",
            is_assumption=False,
            source_label="llm_judge_audit",
        )

    alternatives: list[Alternative] = []
    for raw in (judge_output.get("alternatives") or [])[:5]:
        if not isinstance(raw, dict):
            continue
        alt = Alternative(
            title=str(raw.get("title", "")),
            short_description=str(raw.get("short_description", ""))[:240],
            risk_level=str(raw.get("risk_level", "low")),
            confidence_score=_clip01(raw.get("confidence_score", 0.5)),
            trade_off_summary=str(raw.get("trade_off_summary", "")),
        )
        alternatives.append(alt)

    return DecisionCard(
        recommendation=str(judge_output.get("recommendation") or judge_output.get("rationale", ""))[:1000] or _default_recommendation(recommendation_type),
        expected_benefit=str(judge_output.get("expected_benefit", "")),
        expected_downside=str(judge_output.get("expected_downside", "")),
        quality_impact=str(judge_output.get("quality_impact", "")),
        cost_impact=cost_impact,
        token_impact=token_impact,
        time_impact=time_impact,
        alternatives=alternatives,
        recommendation_type=recommendation_type,
        metadata={
            "triggering_topic": context.triggering_event_topic,
            "llm_judge_model_id": str(judge_output.get("_llm_judge_model_id") or ""),
            "llm_judge_prompt_tokens": str(judge_output.get("_llm_judge_prompt_tokens") or ""),
            "llm_judge_response_tokens": str(judge_output.get("_llm_judge_response_tokens") or ""),
            "llm_judge_cost_usd": str(judge_output.get("_llm_judge_cost_usd") or ""),
            "llm_judge_latency_ms": str(judge_output.get("_llm_judge_latency_ms") or ""),
        },
        source_data_ids=[],
        assumption_note=(
            "Cost is an ASSUMPTION (no live pricing snapshot)"
            if cost_impact.is_assumption
            else "Cost includes measured LLM judge control-plane call from audit."
        ),
    )


def _impact_from(pricing_snapshot: dict | None, *, unit: str, absolute_value: str) -> Impact:
    src_label = (pricing_snapshot or {}).get("source_label") or "assumption"
    is_assumption = src_label == "assumption"
    return Impact(
        absolute_value=absolute_value,
        unit=unit,
        delta_vs_baseline_pct=0.0,
        baseline_label="current_baseline",
        estimate_confidence="measured" if src_label in ("measured", "live") else (
            "profile" if "profile" in src_label else "assumption"
        ),
        is_assumption=is_assumption,
        source_label=src_label,
    )


def _clip01(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


def _int_or_zero(v: Any) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def _float_or_zero(v: Any) -> float:
    try:
        return max(0.0, float(v))
    except (TypeError, ValueError):
        return 0.0


def _default_recommendation(rec_type: str) -> str:
    return f"Action recommended ({rec_type}). See rationale for details."
