"""Tests for ``sylion.aeis_v2.policy_v2.metrics`` — sprint 4 W19 telemetry."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.policy_v2.metrics import (
    record_deny,
    record_evaluator_enabled,
    record_render,
    record_rollout_percent,
    render_w19_metrics,
    reset_w19_metrics,
    snapshot_w19_metrics,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_w19_metrics()
    yield
    reset_w19_metrics()


# ---------------------------------------------------------------------------
# record_render — outcome counter + duration histogram
# ---------------------------------------------------------------------------


def test_record_render_counts_outcomes() -> None:
    record_render("allow", duration_s=0.1)
    record_render("allow", duration_s=0.2)
    record_render("deny", duration_s=0.3)
    record_render("error", duration_s=0.4)
    out = render_w19_metrics()
    assert 'sylion_v2_w19_renders_total{outcome="allow"} 2' in out
    assert 'sylion_v2_w19_renders_total{outcome="deny"} 1' in out
    assert 'sylion_v2_w19_renders_total{outcome="error"} 1' in out


def test_record_render_accumulates_duration() -> None:
    record_render("allow", duration_s=0.1)
    record_render("allow", duration_s=0.2)
    record_render("allow", duration_s=0.3)
    snap = snapshot_w19_metrics()
    assert snap["render_seconds"]["sum"] == pytest.approx(0.6, abs=1e-9)
    assert snap["render_seconds"]["count"] == 3


def test_record_render_clamps_negative_duration() -> None:
    record_render("allow", duration_s=-1.0)
    snap = snapshot_w19_metrics()
    assert snap["render_seconds"]["sum"] == 0.0


# ---------------------------------------------------------------------------
# record_deny — by rule
# ---------------------------------------------------------------------------


def test_record_deny_counts_by_rule() -> None:
    record_deny("admin-only")
    record_deny("admin-only")
    record_deny("vip-block")
    out = render_w19_metrics()
    assert 'sylion_v2_w19_denies_total{rule="admin-only"} 2' in out
    assert 'sylion_v2_w19_denies_total{rule="vip-block"} 1' in out


def test_record_deny_empty_rule_falls_to_unknown() -> None:
    record_deny("")
    out = render_w19_metrics()
    assert 'sylion_v2_w19_denies_total{rule="unknown"} 1' in out


# ---------------------------------------------------------------------------
# record_rollout_percent — gauge
# ---------------------------------------------------------------------------


def test_record_rollout_percent_clamps_high() -> None:
    record_rollout_percent(150)
    out = render_w19_metrics()
    assert "sylion_v2_w19_rollout_percent 100" in out


def test_record_rollout_percent_clamps_negative() -> None:
    record_rollout_percent(-5)
    out = render_w19_metrics()
    assert "sylion_v2_w19_rollout_percent 0" in out


def test_record_rollout_percent_overwrites() -> None:
    """Gauge — last write wins."""
    record_rollout_percent(1)
    record_rollout_percent(50)
    out = render_w19_metrics()
    assert "sylion_v2_w19_rollout_percent 50" in out


# ---------------------------------------------------------------------------
# record_evaluator_enabled
# ---------------------------------------------------------------------------


def test_record_evaluator_enabled_true_yields_one() -> None:
    record_evaluator_enabled(True)
    out = render_w19_metrics()
    assert "sylion_v2_w19_evaluator_enabled 1" in out


def test_record_evaluator_enabled_false_yields_zero() -> None:
    record_evaluator_enabled(False)
    out = render_w19_metrics()
    assert "sylion_v2_w19_evaluator_enabled 0" in out


# ---------------------------------------------------------------------------
# render_w19_metrics — exposition shape
# ---------------------------------------------------------------------------


def test_render_includes_help_and_type() -> None:
    out = render_w19_metrics()
    for header in (
        "# HELP sylion_v2_w19_renders_total",
        "# TYPE sylion_v2_w19_renders_total counter",
        "# HELP sylion_v2_w19_render_seconds_sum",
        "# HELP sylion_v2_w19_denies_total",
        "# TYPE sylion_v2_w19_denies_total counter",
        "# HELP sylion_v2_w19_rollout_percent",
        "# TYPE sylion_v2_w19_rollout_percent gauge",
        "# HELP sylion_v2_w19_evaluator_enabled",
        "# TYPE sylion_v2_w19_evaluator_enabled gauge",
    ):
        assert header in out, f"missing: {header}"


def test_render_terminates_with_newline() -> None:
    out = render_w19_metrics()
    assert out.endswith("\n")


# ---------------------------------------------------------------------------
# Snapshot + reset
# ---------------------------------------------------------------------------


def test_snapshot_returns_json_friendly() -> None:
    record_render("allow", duration_s=0.5)
    record_deny("admin")
    record_rollout_percent(25)
    record_evaluator_enabled(True)
    snap = snapshot_w19_metrics()
    json.dumps(snap)
    assert snap["renders_total"]["allow"] == 1
    assert snap["denies_total"]["admin"] == 1
    assert snap["rollout_percent"] == 25
    assert snap["evaluator_enabled"] == 1


def test_reset_clears_all_state() -> None:
    record_render("allow", duration_s=0.1)
    record_deny("x")
    record_rollout_percent(50)
    record_evaluator_enabled(True)
    reset_w19_metrics()
    snap = snapshot_w19_metrics()
    assert snap["renders_total"] == {}
    assert snap["denies_total"] == {}
    assert snap["rollout_percent"] == 0
    assert snap["evaluator_enabled"] == 0


# ---------------------------------------------------------------------------
# Integration — RoutingGate.check pushes to W19 metrics
# ---------------------------------------------------------------------------


def test_routing_gate_records_render_outcome(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from sylion.aeis_v2.policy_v2 import RoutingGate, StagedRolloutGate

    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")
    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=100),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    gate.check(decision_id="d1", policy_template="allow", context={})
    gate.check(decision_id="d2", policy_template="deny", context={})

    snap = snapshot_w19_metrics()
    assert snap["renders_total"].get("allow") == 1
    assert snap["renders_total"].get("deny") == 1
    # Deny was recorded with reason="policy_returned_deny" as the rule.
    assert snap["denies_total"].get("policy_returned_deny") == 1


def test_routing_gate_updates_rollout_gauge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from sylion.aeis_v2.policy_v2 import RoutingGate, StagedRolloutGate

    monkeypatch.setenv("SYLION_W19_EVALUATOR_DISABLED", "0")
    gate = RoutingGate(
        rollout_gate=StagedRolloutGate(fixed_percent=25),
        audit_log_path=tmp_path / "fp.jsonl",
    )
    gate.check(decision_id="d1", policy_template="allow", context={})
    snap = snapshot_w19_metrics()
    assert snap["rollout_percent"] == 25
    assert snap["evaluator_enabled"] == 1


def test_metrics_v2_endpoint_includes_w19_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from sylion.api.metrics_v2_routes import render_metrics

    record_render("allow", duration_s=0.05)
    record_rollout_percent(5)
    record_evaluator_enabled(True)
    out = render_metrics(log_root=tmp_path)
    assert "sylion_v2_w19_renders_total" in out
    assert "sylion_v2_w19_rollout_percent 5" in out
    assert "sylion_v2_w19_evaluator_enabled 1" in out
