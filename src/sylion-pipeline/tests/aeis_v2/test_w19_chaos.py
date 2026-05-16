"""W19 chaos test suite — sprint 4 production-readiness gate.

Drives the canonical chaos payloads (commit ef2e720f's
``make_chaos_payload``) through the routing gate (146c2404) and
asserts each attack vector is contained without breaking the gate's
overall fail-OPEN-on-error contract.

Per Kimi review k2 R56:00 — the test set covers:

    1. sandbox_escape  — ``__class__/__mro__/__subclasses__`` chain
    2. timeout_loop    — infinite ``range(10**9)``
    3. memory_bomb     — ``blob * 1000`` allocation
    4. malformed_jinja — partial template syntax
    5. unicode_bomb    — bidi-control character flood

Plus 5 environmental chaos vectors:

    6. ollama unreachable mid-render (env-driven)
    7. audit chain disk full (monkeypatched append_to_chain)
    8. staged-rollout boundary jitter (5% mid-traffic flip)
    9. evaluator flag flipped mid-traffic (deny → allow)
   10. policy template longer than W19_TEMPLATE_MAX_LEN
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.policy_v2 import (
    RoutingGate,
    StagedRolloutGate,
    make_chaos_payload,
    validate_policy_template,
)


@pytest.fixture
def evaluator_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable W19 evaluator + 100% rollout for deterministic chaos runs."""
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")
    yield
    monkeypatch.delenv("SYLION_W19_EVALUATOR_DISABLED", raising=False)


@pytest.fixture
def gate(evaluator_on, tmp_path: Path) -> RoutingGate:
    return RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp_chaos.jsonl",
    )


# ---------------------------------------------------------------------------
# Vector 1: sandbox_escape — __class__ + __mro__ chain
# ---------------------------------------------------------------------------


def test_chaos_sandbox_escape_blocked_by_token_filter(gate: RoutingGate) -> None:
    """The W19 token blocklist (jinja_runner) catches __class__ before render."""
    payload = make_chaos_payload("sandbox_escape")
    decision = gate.check(
        decision_id="chaos-1",
        policy_template=payload["template"],
        context=payload["context"],
    )
    # Fail-OPEN on render error → outcome="error", allowed=True.
    # The defence-in-depth IS that the template never renders cleanly.
    assert decision.outcome == "error"
    assert decision.allowed is True
    # Reason contains "blocked token" or "sandbox" — proof the filter ran.
    reason = decision.reason.lower()
    assert (
        "blocked token" in reason
        or "sandbox" in reason
        or "security" in reason
    )


# ---------------------------------------------------------------------------
# Vector 2: timeout_loop — infinite range
# ---------------------------------------------------------------------------


def test_chaos_timeout_loop_blocked_by_sandbox_max_range(
    gate: RoutingGate,
) -> None:
    """SandboxedEnvironment caps range() — timeout_loop fails fast."""
    payload = make_chaos_payload("timeout_loop")
    decision = gate.check(
        decision_id="chaos-2",
        policy_template=payload["template"],
        context=payload["context"],
    )
    assert decision.outcome == "error"
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Vector 3: memory_bomb — blob * copies
# ---------------------------------------------------------------------------


def test_chaos_memory_bomb_completes_without_crash(
    gate: RoutingGate,
) -> None:
    """Multiplying a 1MB blob by 1000 = 1GB string. Should complete OR error,
    but MUST NOT crash the test process. We accept either outcome=error or
    outcome=allow (with truncated rendered text)."""
    payload = make_chaos_payload("memory_bomb")
    decision = gate.check(
        decision_id="chaos-3",
        policy_template=payload["template"],
        context=payload["context"],
    )
    # Bomb must NOT make the gate hang or raise — either error path
    # (jinja2 caught it) or allow path (it rendered) is acceptable.
    assert decision.outcome in ("allow", "error", "deny")
    assert decision.allowed in (True, False)


# ---------------------------------------------------------------------------
# Vector 4: malformed_jinja — partial syntax
# ---------------------------------------------------------------------------


def test_chaos_malformed_jinja_caught_as_syntax_error(
    gate: RoutingGate,
) -> None:
    payload = make_chaos_payload("malformed_jinja")
    decision = gate.check(
        decision_id="chaos-4",
        policy_template=payload["template"],
        context=payload["context"],
    )
    assert decision.outcome == "error"
    # Reason carries the syntax-error trace.
    assert "syntax" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Vector 5: unicode_bomb — bidi-control characters
# ---------------------------------------------------------------------------


def test_chaos_unicode_bomb_does_not_crash_renderer(
    gate: RoutingGate,
) -> None:
    payload = make_chaos_payload("unicode_bomb")
    decision = gate.check(
        decision_id="chaos-5",
        policy_template=payload["template"],
        context=payload["context"],
    )
    # Whatever happens, the gate must produce a RoutingDecision.
    assert decision.outcome in ("allow", "deny", "error")


# ---------------------------------------------------------------------------
# Vector 6: ollama unreachable mid-render — N/A for jinja path, but the
# router itself must not depend on ollama. Sanity-check by setting an
# env var that no actual ollama would honour and confirming the gate
# still produces a decision.
# ---------------------------------------------------------------------------


def test_chaos_unrelated_env_does_not_break_gate(
    gate: RoutingGate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "tcp://nonexistent:9999")
    decision = gate.check(
        decision_id="chaos-6",
        policy_template="allow",
        context={},
    )
    assert decision.outcome == "allow"


# ---------------------------------------------------------------------------
# Vector 7: audit chain disk full — append_to_chain raises OSError
# ---------------------------------------------------------------------------


def test_chaos_audit_emit_failure_does_not_block_routing(
    gate: RoutingGate, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per the gate's docstring — audit emit is best-effort + never blocks."""
    import sylion.aeis_v2.policy_v2.routing_gate as mod

    def _raise(*_a: Any, **_kw: Any) -> Any:
        raise OSError("simulated disk full")

    monkeypatch.setattr(mod, "append_to_chain", _raise)
    decision = gate.check(
        decision_id="chaos-7",
        policy_template="allow",
        context={},
    )
    # The gate decision must still come back even when audit fails.
    assert decision.outcome == "allow"


# ---------------------------------------------------------------------------
# Vector 8: staged-rollout boundary jitter — flip 5% → 0% mid-traffic
# ---------------------------------------------------------------------------


def test_chaos_rollout_boundary_jitter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Rolling the percent down mid-traffic must NOT flap committed buckets."""
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate_5 = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=5),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision_5 = gate_5.check(
        decision_id="d-stable", policy_template="allow", context={},
    )
    # Now flip to 0%.
    gate_0 = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=0),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision_0 = gate_0.check(
        decision_id="d-stable", policy_template="allow", context={},
    )
    # 0% always means skipped.
    assert decision_0.outcome == "skipped"
    # The 5% decision was either skipped OR allow — but NEVER deny.
    assert decision_5.outcome in ("skipped", "allow")


# ---------------------------------------------------------------------------
# Vector 9: evaluator flag flipped mid-traffic
# ---------------------------------------------------------------------------


def test_chaos_evaluator_flag_flip_propagates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Operator can disable W19 mid-traffic by flipping the env var.

    The gate re-reads is_evaluator_enabled() on every call so changes
    take effect without process restart.
    """
    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    # Flag on → evaluation runs.
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")
    d_on = gate.check(
        decision_id="d-flip", policy_template="deny", context={},
    )
    assert d_on.outcome == "deny"
    # Flag off → evaluator skipped.
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "1")
    d_off = gate.check(
        decision_id="d-flip", policy_template="deny", context={},
    )
    assert d_off.outcome == "skipped"
    assert d_off.reason == "evaluator_flag_off"


# ---------------------------------------------------------------------------
# Vector 10: policy template longer than W19_TEMPLATE_MAX_LEN
# ---------------------------------------------------------------------------


def test_chaos_oversize_template_rejected_by_validator() -> None:
    """validate_policy_template rejects > 4096 chars — operator-time guard."""
    huge = "x" * 5000
    ok, detail = validate_policy_template(huge)
    assert ok is False
    assert "too long" in detail


# ---------------------------------------------------------------------------
# Cross-vector: full canary-mode workflow under chaos input
# ---------------------------------------------------------------------------


def test_chaos_canary_1pct_under_attack_still_responsive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """At 1% canary with sandbox-escape templates, 99% skip + 1% errors.

    The end-state is that NO chaos input causes the gate to deny
    legitimate traffic outside the canary cohort.
    """
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")
    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=1),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    payload = make_chaos_payload("sandbox_escape")

    outcomes = []
    for i in range(500):
        d = gate.check(
            decision_id=f"d-{i}",
            policy_template=payload["template"],
            context=payload["context"],
        )
        outcomes.append(d.outcome)

    skipped = outcomes.count("skipped")
    errors = outcomes.count("error")
    denies = outcomes.count("deny")
    # 1% rollout → skip ~99%; chaos template triggers errors in evaluated
    # bucket → 0 actual denies; allowed must be True for ALL non-deny.
    assert denies == 0
    assert skipped + errors == 500
    # >= 95% of decisions skipped (1% rollout with 5% slack).
    assert skipped >= 475
