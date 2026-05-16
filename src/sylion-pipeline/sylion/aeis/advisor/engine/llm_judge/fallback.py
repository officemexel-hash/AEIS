"""Resolve which model to call for a given judge purpose, with local fallback.

The role_resolver module (Kimi WP4) owns canonical routing. Until its gRPC is
reachable, this resolver applies a sensible default routing matrix derived from
`00_master_spec.md` §5 LLM pool defaults plus operator preferences fetched via
preferences gRPC (or env defaults).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger("sylion.aeis.advisor.engine.llm_judge.fallback")


_DEFAULT_ROUTING = {
    # (judge_purpose, risk_level) -> [primary, fallback_external, local]
    ("rationale", "low"): ["claude-haiku-4-5", "gpt-5-mini", "qwen2.5:7b-instruct"],
    ("rationale", "medium"): ["claude-sonnet-4-6", "gpt-5", "qwen2.5:72b-instruct"],
    ("rationale", "high"): ["claude-sonnet-4-6", "gpt-5", "qwen2.5:72b-instruct"],
    ("rationale", "critical"): ["claude-opus-4-7", "gpt-5", "qwen2.5:72b-instruct"],
    ("alternatives", "low"): ["claude-haiku-4-5", "gpt-5-mini", "qwen2.5:7b-instruct"],
    ("alternatives", "medium"): ["claude-sonnet-4-6", "gpt-5", "qwen2.5:72b-instruct"],
    ("alternatives", "high"): ["claude-sonnet-4-6", "gpt-5", "qwen2.5:72b-instruct"],
    ("evidence_rationale", "default"): [
        "claude-sonnet-4-6",
        "gpt-5",
        "qwen2.5:72b-instruct",
    ],
    ("evidence_rollback", "default"): [
        "claude-sonnet-4-6",
        "gpt-5",
        "qwen2.5:72b-instruct",
    ],
    ("evidence_fidelity", "default"): [
        "claude-sonnet-4-6",
        "gpt-5",
        "qwen2.5:72b-instruct",
    ],
    ("evidence_risk", "default"): ["claude-opus-4-7", "gpt-5", "qwen2.5:72b-instruct"],
    ("evidence_compliance", "default"): [
        "claude-opus-4-7",
        "gpt-5",
        "qwen2.5:72b-instruct",
    ],
}

_LOCAL_FALLBACK_DEFAULT = "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M"


@dataclass
class RoutingDecision:
    primary_model_id: str
    fallback_chain: list[str]
    forced_local: bool = False
    reason: str = ""


def _split_model_chain(value: object) -> list[str]:
    """Split UI routing values like ``gpt-5+claude-sonnet`` into models."""
    if not isinstance(value, str):
        return []
    return [
        item.strip()
        for item in value.replace(",", "+").split("+")
        if item.strip()
    ]


def _decision_from_override(value: object) -> RoutingDecision | None:
    chain = _split_model_chain(value)
    if not chain:
        return None
    if _LOCAL_FALLBACK_DEFAULT not in chain:
        chain.append(_LOCAL_FALLBACK_DEFAULT)
    return RoutingDecision(primary_model_id=chain[0], fallback_chain=chain, reason="operator_override")


def resolve_judge_model(
    *,
    judge_purpose: str,
    risk_level: str = "medium",
    operator_preferences: dict | None = None,
) -> RoutingDecision:
    """Pick a model id given purpose + risk + operator overrides.

    Operator overrides come from `preferences.llm_judge_routing_override` if set:
        { "rationale": {"low": "gpt-5-mini", ...}, "evidence_rationale": "..." }
    """
    operator_preferences = operator_preferences or {}
    override = operator_preferences.get("llm_judge_routing_override") or {}
    direct_routing = operator_preferences.get("llm_judge_routing")
    if not override and isinstance(direct_routing, dict):
        override = {"rationale": direct_routing}
    purpose_override = override.get(judge_purpose)
    if isinstance(purpose_override, dict) and purpose_override.get(risk_level):
        decision = _decision_from_override(purpose_override[risk_level])
        if decision is not None:
            return decision
    if isinstance(purpose_override, str) and purpose_override:
        decision = _decision_from_override(purpose_override)
        if decision is not None:
            return decision

    # Forced local mode (e.g. air-gapped install)
    if str(os.environ.get("SYLION_ADVISOR_LOCAL_ONLY", "")).lower() in ("1", "true", "yes"):
        return RoutingDecision(
            primary_model_id=_LOCAL_FALLBACK_DEFAULT,
            fallback_chain=[_LOCAL_FALLBACK_DEFAULT],
            forced_local=True,
            reason="env:SYLION_ADVISOR_LOCAL_ONLY",
        )

    chain = _DEFAULT_ROUTING.get((judge_purpose, risk_level)) or _DEFAULT_ROUTING.get(
        (judge_purpose, "default")
    ) or _DEFAULT_ROUTING[("rationale", "medium")]
    return RoutingDecision(primary_model_id=chain[0], fallback_chain=list(chain), reason="default_matrix")
