"""Tests for ``sylion.aeis_v2.policy_v2.RoutingGate`` — sprint 4 wire-in."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.policy_v2 import (
    ROUTING_OUTCOMES,
    RoutingDecision,
    RoutingGate,
    StagedRolloutGate,
)


# ---------------------------------------------------------------------------
# Module invariants
# ---------------------------------------------------------------------------


def test_routing_outcomes_canonical() -> None:
    assert ROUTING_OUTCOMES == ("allow", "deny", "skipped", "error")


def test_routing_decision_to_dict_serialisable() -> None:
    d = RoutingDecision(
        decision_id="dec-1", outcome="allow",
        rendered="allow", reason="ok",
        elapsed_ms=1.234, rolled_out=True,
    )
    out = d.to_dict()
    json.dumps(out)
    assert out["outcome"] == "allow"
    assert out["elapsed_ms"] == 1.234


def test_routing_decision_allowed_property() -> None:
    """allowed is True for everything except outcome="deny"."""
    for outcome in ("allow", "skipped", "error"):
        d = RoutingDecision(
            decision_id="d", outcome=outcome, rendered=None,
            reason="x", elapsed_ms=0.0, rolled_out=False,
        )
        assert d.allowed is True
    d_deny = RoutingDecision(
        decision_id="d", outcome="deny", rendered="deny",
        reason="policy", elapsed_ms=0.0, rolled_out=True,
    )
    assert d_deny.allowed is False


# ---------------------------------------------------------------------------
# Gate 1: feature flag off → skipped
# ---------------------------------------------------------------------------


def test_gate_skipped_when_evaluator_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Feature flag default-off → outcome="skipped" + allowed."""
    monkeypatch.delenv("SYLION_W19_EVALUATOR_DISABLED", raising=False)

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision = gate.check(
        decision_id="dec-1",
        policy_template="{{ x }}",
        context={"x": "deny"},
    )
    assert decision.outcome == "skipped"
    assert decision.reason == "evaluator_flag_off"
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Gate 2: rollout bucket
# ---------------------------------------------------------------------------


def test_gate_skipped_when_not_in_rollout_bucket(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Flag on but rollout 0% → all decisions skipped."""
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=0),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision = gate.check(
        decision_id="dec-1",
        policy_template="deny",
        context={},
    )
    assert decision.outcome == "skipped"
    assert decision.reason == "not_in_rollout_bucket"
    assert decision.allowed is True
    assert decision.rolled_out is False


def test_gate_runs_when_rollout_full(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Flag on + 100% rollout → evaluator fires."""
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision = gate.check(
        decision_id="dec-1",
        policy_template="allow",
        context={},
    )
    assert decision.outcome == "allow"
    assert decision.rolled_out is True


# ---------------------------------------------------------------------------
# Gate 3: jinja2 template render
# ---------------------------------------------------------------------------


def test_gate_skipped_when_no_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """No template → skip evaluator (allow by default)."""
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision = gate.check(
        decision_id="dec-1",
        policy_template="",
        context={},
    )
    assert decision.outcome == "skipped"
    assert decision.reason == "no_policy_template"
    assert decision.rolled_out is True


def test_gate_denies_when_template_returns_deny(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision = gate.check(
        decision_id="dec-1",
        policy_template="{% if request.role == 'admin' %}allow{% else %}deny{% endif %}",
        context={"request": {"role": "user"}},
    )
    assert decision.outcome == "deny"
    assert decision.rendered == "deny"
    assert decision.allowed is False


def test_gate_allows_when_template_returns_allow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision = gate.check(
        decision_id="dec-1",
        policy_template="{% if request.role == 'admin' %}allow{% else %}deny{% endif %}",
        context={"request": {"role": "admin"}},
    )
    assert decision.outcome == "allow"
    assert decision.allowed is True


def test_gate_allows_on_render_error_fail_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Per Kimi k1 R56:00 — render error → allow (fail-OPEN to protect blast radius)."""
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    decision = gate.check(
        decision_id="dec-1",
        policy_template="{{ ',broken syntax",  # malformed
        context={},
    )
    assert decision.outcome == "error"
    assert decision.allowed is True
    assert decision.reason  # error message present


def test_gate_case_insensitive_deny(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """``DENY`` / ``Deny`` / mixed case → still triggers deny."""
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    for variant in ("deny", "DENY", "Deny", "  deny  "):
        gate = RoutingGate(
            rollout_gate=StagedRolloutGate(fixed_percent=100),
            audit_log_path=tmp_path / f"fp-{variant.strip()}.jsonl",
        )
        decision = gate.check(
            decision_id="dec",
            policy_template=f"{variant}",
            context={},
        )
        assert decision.outcome == "deny", f"variant {variant!r} failed"


def test_gate_other_renders_treated_as_allow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Anything not exactly ``deny`` → allow.

    Note: an empty template is a separate case (skipped — no_policy_template).
    """
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    for output in ("allow", "ok", "yes", "permit"):
        gate = RoutingGate(
            rollout_gate=StagedRolloutGate(fixed_percent=100),
            audit_log_path=tmp_path / f"fp-{output}.jsonl",
        )
        decision = gate.check(
            decision_id="dec",
            policy_template=f"{output}",
            context={},
        )
        assert decision.outcome == "allow"


# ---------------------------------------------------------------------------
# Audit emission
# ---------------------------------------------------------------------------


def test_gate_emits_chained_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")
    audit = tmp_path / "fp.jsonl"

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=audit,
    )
    gate.check(decision_id="d1", policy_template="allow", context={})
    gate.check(decision_id="d2", policy_template="deny", context={})
    gate.check(decision_id="d3", policy_template="", context={})

    assert verify_chain(audit) == []
    rows = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    assert len(rows) == 3
    assert all(r.get("kind") == "federation_policy.gate_check" for r in rows)
    outcomes = {r["decision_id"]: r["outcome"] for r in rows}
    assert outcomes["d1"] == "allow"
    assert outcomes["d2"] == "deny"
    assert outcomes["d3"] == "skipped"


def test_gate_audit_records_elapsed_and_rolled_out(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")
    audit = tmp_path / "fp.jsonl"

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=audit,
    )
    gate.check(decision_id="d1", policy_template="allow", context={})

    rows = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    assert rows[0]["rolled_out"] is True
    assert rows[0]["elapsed_ms"] >= 0.0


# ---------------------------------------------------------------------------
# End-to-end: 0% canary → no evaluation; 100% → evaluation runs.
# ---------------------------------------------------------------------------


def test_canary_zero_percent_never_evaluates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=0),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    for i in range(20):
        d = gate.check(
            decision_id=f"d-{i}",
            policy_template="deny",  # would deny at 100%
            context={},
        )
        assert d.outcome == "skipped"  # never evaluates


def test_canary_one_percent_evaluates_minority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")

    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=1),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    n = 1000
    evaluated = sum(
        1 for i in range(n)
        if gate.check(
            decision_id=f"d-{i}",
            policy_template="allow",
            context={},
        ).rolled_out
    )
    # 1% of 1000 ≈ 10, with reasonable variance allow [0, 60].
    assert 0 <= evaluated <= 60
