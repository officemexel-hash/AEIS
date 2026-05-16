"""W19 G2 policy_v2 — jinja2 sandbox-based policy evaluator (PROPOSED).

Status: SKELETON. ADR-003 still PROPOSED. NOT wired into routing/apply.

Public surface (skeleton):
    from sylion.aeis_v2.policy_v2 import (
        is_evaluator_enabled,    # feature flag check
        render_template,         # pure jinja2 sandbox helper
        emit_audit,              # JSONL audit emitter
        JinjaRenderResult,       # frozen dataclass result type
    )

When ADR-003 lands at ACCEPTED + Council Hybrid sign-off, the operator
flips ``SYLION_W19_EVALUATOR_DISABLED=0`` and routing/apply call sites
(federation.py, applier.py) start consulting this module. Until then it
exists only so the path is exercised by tests.
"""
from __future__ import annotations

from sylion.aeis_v2.policy_v2.chaos_payloads import get_chaos_payload, make_chaos_payload
from sylion.aeis_v2.policy_v2.jinja_runner import (
    JinjaContextSafelist,
    JinjaRenderResult,
    W19_AUDIT_LOG_PATH,
    W19_EVALUATOR_ENABLED_ENV,
    W19_RENDER_TIMEOUT_S,
    validate_policy_template,
    emit_audit,
    is_evaluator_enabled,
    render_template,
)
from sylion.aeis_v2.policy_v2.routing_gate import (
    ROUTING_GATE_AUDIT_PATH,
    ROUTING_OUTCOMES,
    RoutingDecision,
    RoutingGate,
)
from sylion.aeis_v2.policy_v2.staged_rollout import (
    DEFAULT_ROLLOUT_PERCENT,
    ROLLOUT_PERCENT_ENV,
    StagedRolloutGate,
    compute_rollout_bucket,
    is_in_rollout_bucket,
)

__all__ = [
    "DEFAULT_ROLLOUT_PERCENT",
    "JinjaContextSafelist",
    "JinjaRenderResult",
    "ROLLOUT_PERCENT_ENV",
    "ROUTING_GATE_AUDIT_PATH",
    "ROUTING_OUTCOMES",
    "RoutingDecision",
    "RoutingGate",
    "StagedRolloutGate",
    "W19_AUDIT_LOG_PATH",
    "W19_EVALUATOR_ENABLED_ENV",
    "W19_RENDER_TIMEOUT_S",
    "compute_rollout_bucket",
    "emit_audit",
    "get_chaos_payload",
    "is_evaluator_enabled",
    "is_in_rollout_bucket",
    "make_chaos_payload",
    "render_template",
    "validate_policy_template",
]
