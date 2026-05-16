"""W19 routing gate — production hook for federation routing.

Sprint 4 critical-path. This is the call site that the federation
router invokes to decide whether to consult the W19 policy evaluator
for a particular routing decision.

Three gates compose, each independently fail-closed:

    1. ``is_evaluator_enabled()``    — env flag (off until ADR-003 ACCEPTED)
    2. ``StagedRolloutGate``         — canary 0/1/5/25/50/100% bucket
    3. ``render_template(...)``      — jinja2 sandbox + timeout

When ALL three fire and the rendered template equals the literal
string ``"deny"`` (case-insensitive), routing is blocked. Anything
else (including evaluator failures) defaults to ALLOW so a broken
evaluator never blocks production traffic.

The default is **deliberately permissive on the evaluator's failure
modes** because:

* The evaluator is opt-in (operator must flip the env flag) — the
  feature flag itself is the kill-switch.
* Council Hybrid sign-off has already vetted the policy templates.
* Failing closed on every evaluator error during a canary rollout
  amplifies the blast radius of a regression.

Per Kimi review k1 round 56:00:

* The hot-path latency budget for the gate is **5 ms p99** — render
  timeout (1s) + thread spawn + audit emit. Production deployments
  should pre-wire a thread pool if the budget tightens.
* Audit emission via ``append_to_chain`` is best-effort and never
  blocks routing — the existing chained audit pattern.
* ``decision_id`` from the caller is treated as **untrusted** for
  bucket assignment, but since the bucket function is deterministic
  + cryptographically uniform, an attacker can at most pin their own
  request to a specific bucket — they cannot cross-pollinate other
  decisions.

Public surface::

    from sylion.aeis_v2.policy_v2 import RoutingGate
    gate = RoutingGate()
    decision = gate.check(
        decision_id="dec-uuid",
        policy_template="{% if request.role == 'admin' %}allow{% else %}deny{% endif %}",
        context={"request": {"role": "user"}},
    )
    if decision.allowed:
        # proceed with routing
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.aeis_v2.audit_chain import append_to_chain
from sylion.aeis_v2.policy_v2.jinja_runner import (
    JinjaRenderResult,
    is_evaluator_enabled,
    render_template,
)
from sylion.aeis_v2.policy_v2.metrics import (
    record_deny,
    record_evaluator_enabled,
    record_render,
    record_rollout_percent,
)
from sylion.aeis_v2.policy_v2.staged_rollout import StagedRolloutGate

log = logging.getLogger(__name__)

#: Audit JSONL — chained per ac97e957.
ROUTING_GATE_AUDIT_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "federation_policy.jsonl"
)

#: Outcome of the gate check.
ROUTING_OUTCOMES = ("allow", "deny", "skipped", "error")


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Outcome of a single ``RoutingGate.check`` call."""

    decision_id: str
    outcome: str  # one of ROUTING_OUTCOMES
    rendered: str | None
    reason: str
    elapsed_ms: float
    rolled_out: bool

    @property
    def allowed(self) -> bool:
        return self.outcome != "deny"

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "outcome": self.outcome,
            "rendered": self.rendered,
            "reason": self.reason,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "rolled_out": self.rolled_out,
        }


class RoutingGate:
    """Compose feature-flag + staged-rollout + jinja_runner into one check.

    Construction is cheap; instances are safe to share. The gate keeps
    no mutable state — everything routes through the env-driven
    :class:`StagedRolloutGate`.
    """

    def __init__(
        self,
        *,
        rollout_gate: StagedRolloutGate | None = None,
        audit_log_path: Path | str | None = None,
    ) -> None:
        self._rollout_gate = rollout_gate or StagedRolloutGate()
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None
            else ROUTING_GATE_AUDIT_PATH
        )

    @property
    def rollout_gate(self) -> StagedRolloutGate:
        return self._rollout_gate

    def _emit_audit(self, decision: RoutingDecision) -> None:
        try:
            append_to_chain(
                self._audit_log_path,
                {
                    "kind": "federation_policy.gate_check",
                    **decision.to_dict(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("routing_gate: audit emit failed (%s)", exc)

    def _record_metrics(self, decision: RoutingDecision) -> None:
        """Push outcome counters + duration to /api/v1/metrics/v2."""
        try:
            record_render(
                decision.outcome,
                duration_s=decision.elapsed_ms / 1000.0,
            )
            if decision.outcome == "deny":
                record_deny(decision.reason or "unknown")
            # Refresh gauges every call so operator dial changes
            # propagate to /metrics/v2 within one call.
            record_rollout_percent(self._rollout_gate.percent)
            record_evaluator_enabled(is_evaluator_enabled())
        except Exception as exc:  # noqa: BLE001
            log.warning("routing_gate: metrics push failed (%s)", exc)

    def check(
        self,
        *,
        decision_id: str,
        policy_template: str | None,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Run all 3 gates and return a :class:`RoutingDecision`.

        Args:
            decision_id: caller-supplied UUID. Used for the canary bucket.
            policy_template: jinja2 source. None / empty → skip evaluator.
            context: jinja2 render context. None → empty dict.

        Returns:
            RoutingDecision with ``outcome`` in ROUTING_OUTCOMES and
            ``allowed`` True for everything except ``"deny"``.
        """
        start = time.perf_counter()
        context = context or {}

        # Gate 1: feature flag.
        if not is_evaluator_enabled():
            d = RoutingDecision(
                decision_id=decision_id,
                outcome="skipped",
                rendered=None,
                reason="evaluator_flag_off",
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                rolled_out=False,
            )
            self._emit_audit(d)
            self._record_metrics(d)
            return d

        # Gate 2: staged rollout bucket.
        rolled_out = self._rollout_gate.should_run(decision_id)
        if not rolled_out:
            d = RoutingDecision(
                decision_id=decision_id,
                outcome="skipped",
                rendered=None,
                reason="not_in_rollout_bucket",
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                rolled_out=False,
            )
            self._emit_audit(d)
            self._record_metrics(d)
            return d

        # Gate 3: jinja2 template render.
        if not policy_template:
            d = RoutingDecision(
                decision_id=decision_id,
                outcome="skipped",
                rendered=None,
                reason="no_policy_template",
                elapsed_ms=(time.perf_counter() - start) * 1000.0,
                rolled_out=True,
            )
            self._emit_audit(d)
            self._record_metrics(d)
            return d

        result: JinjaRenderResult = render_template(
            policy_template, context,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if result.error is not None:
            # Fail-OPEN on render error per Kimi k1 R56:00 (see module
            # docstring). The error is recorded so observability
            # surfaces broken templates immediately.
            d = RoutingDecision(
                decision_id=decision_id,
                outcome="error",
                rendered=None,
                reason=result.error,
                elapsed_ms=elapsed_ms,
                rolled_out=True,
            )
            self._emit_audit(d)
            self._record_metrics(d)
            return d

        rendered = (result.rendered or "").strip().lower()
        if rendered == "deny":
            d = RoutingDecision(
                decision_id=decision_id,
                outcome="deny",
                rendered=rendered,
                reason="policy_returned_deny",
                elapsed_ms=elapsed_ms,
                rolled_out=True,
            )
        else:
            d = RoutingDecision(
                decision_id=decision_id,
                outcome="allow",
                rendered=rendered,
                reason="policy_returned_allow_or_other",
                elapsed_ms=elapsed_ms,
                rolled_out=True,
            )
        self._emit_audit(d)
        self._record_metrics(d)
        return d


__all__ = [
    "ROUTING_GATE_AUDIT_PATH",
    "ROUTING_OUTCOMES",
    "RoutingDecision",
    "RoutingGate",
]
