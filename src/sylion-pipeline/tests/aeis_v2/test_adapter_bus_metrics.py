"""Tests for ``sylion.aeis_v2.adapter_bus_v2.metrics`` — W11 telemetry."""
from __future__ import annotations

import pytest

from sylion.aeis_v2.adapter_bus_v2.metrics import (
    record_circuit_state,
    record_dispatch_attempt,
    record_failure,
    render_adapter_bus_metrics,
    reset_adapter_bus_metrics,
    snapshot_adapter_bus_metrics,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_adapter_bus_metrics()
    yield
    reset_adapter_bus_metrics()


# ---------------------------------------------------------------------------
# record_dispatch_attempt
# ---------------------------------------------------------------------------


def test_dispatch_attempt_counts_success_outcome() -> None:
    record_dispatch_attempt("ollama", success=True, duration_s=0.5)
    out = render_adapter_bus_metrics()
    assert 'adapter_bus_dispatch_total{adapter="ollama",outcome="success"} 1' in out


def test_dispatch_attempt_counts_failure_outcome() -> None:
    record_dispatch_attempt("ollama", success=False, duration_s=1.0)
    out = render_adapter_bus_metrics()
    assert 'adapter_bus_dispatch_total{adapter="ollama",outcome="failure"} 1' in out


def test_dispatch_attempt_accumulates_duration() -> None:
    record_dispatch_attempt("a", success=True, duration_s=0.1)
    record_dispatch_attempt("a", success=True, duration_s=0.2)
    record_dispatch_attempt("a", success=True, duration_s=0.3)
    out = render_adapter_bus_metrics()
    assert 'adapter_bus_dispatch_seconds_sum{adapter="a"} 0.6' in out
    assert 'adapter_bus_dispatch_seconds_count{adapter="a"} 3' in out


def test_dispatch_attempt_clamps_negative_duration() -> None:
    """Defensive: negative durations clamp to 0.0."""
    record_dispatch_attempt("a", success=True, duration_s=-1.0)
    snap = snapshot_adapter_bus_metrics()
    assert snap["dispatch_seconds"]["a"]["sum"] == 0.0


# ---------------------------------------------------------------------------
# record_failure
# ---------------------------------------------------------------------------


def test_failure_counts_by_reason() -> None:
    record_failure("ollama", "timeout")
    record_failure("ollama", "timeout")
    record_failure("ollama", "breaker_open")
    out = render_adapter_bus_metrics()
    assert (
        'adapter_bus_failures_total{adapter="ollama",reason="timeout"} 2'
        in out
    )
    assert (
        'adapter_bus_failures_total{adapter="ollama",reason="breaker_open"} 1'
        in out
    )


def test_failure_unknown_reason_falls_back() -> None:
    record_failure("a", "")
    out = render_adapter_bus_metrics()
    assert (
        'adapter_bus_failures_total{adapter="a",reason="unknown"} 1' in out
    )


# ---------------------------------------------------------------------------
# record_circuit_state — gauge
# ---------------------------------------------------------------------------


def test_circuit_state_sets_one_active_zero_others() -> None:
    record_circuit_state("ollama", "open")
    out = render_adapter_bus_metrics()
    assert 'adapter_bus_circuit_state{adapter="ollama",state="open"} 1' in out
    assert (
        'adapter_bus_circuit_state{adapter="ollama",state="closed"} 0' in out
    )
    assert (
        'adapter_bus_circuit_state{adapter="ollama",state="half_open"} 0' in out
    )


def test_circuit_state_transitions() -> None:
    record_circuit_state("a", "closed")
    record_circuit_state("a", "open")
    out = render_adapter_bus_metrics()
    assert 'adapter_bus_circuit_state{adapter="a",state="open"} 1' in out
    assert 'adapter_bus_circuit_state{adapter="a",state="closed"} 0' in out


def test_circuit_state_unknown_falls_back_to_closed() -> None:
    record_circuit_state("a", "ghost")
    out = render_adapter_bus_metrics()
    assert 'adapter_bus_circuit_state{adapter="a",state="closed"} 1' in out


# ---------------------------------------------------------------------------
# render_adapter_bus_metrics — exposition shape
# ---------------------------------------------------------------------------


def test_render_includes_help_and_type_lines() -> None:
    record_dispatch_attempt("a", success=True)
    out = render_adapter_bus_metrics()
    for header in (
        "# HELP adapter_bus_dispatch_total",
        "# TYPE adapter_bus_dispatch_total counter",
        "# HELP adapter_bus_circuit_state",
        "# TYPE adapter_bus_circuit_state gauge",
        "# HELP adapter_bus_failures_total",
        "# TYPE adapter_bus_failures_total counter",
    ):
        assert header in out


def test_render_terminates_with_newline() -> None:
    out = render_adapter_bus_metrics()
    assert out.endswith("\n")


def test_render_isolated_per_adapter() -> None:
    """Two adapters → two distinct label sets, no merging."""
    record_dispatch_attempt("a1", success=True)
    record_dispatch_attempt("a2", success=False)
    out = render_adapter_bus_metrics()
    assert 'adapter="a1"' in out
    assert 'adapter="a2"' in out


# ---------------------------------------------------------------------------
# Snapshot + reset
# ---------------------------------------------------------------------------


def test_snapshot_returns_json_friendly_dict() -> None:
    record_dispatch_attempt("a", success=True, duration_s=0.5)
    record_failure("a", "timeout")
    record_circuit_state("a", "open")
    snap = snapshot_adapter_bus_metrics()
    assert "dispatch_total" in snap
    assert "dispatch_seconds" in snap
    assert "circuit_state" in snap
    assert "failures_total" in snap
    import json
    json.dumps(snap)


def test_reset_clears_all_state() -> None:
    record_dispatch_attempt("a", success=True)
    record_failure("a", "x")
    record_circuit_state("a", "open")
    reset_adapter_bus_metrics()
    snap = snapshot_adapter_bus_metrics()
    assert snap["dispatch_total"] == {}
    assert snap["dispatch_seconds"] == {}
    assert snap["circuit_state"] == {}
    assert snap["failures_total"] == {}


# ---------------------------------------------------------------------------
# Integration with /api/v1/metrics/v2 endpoint
# ---------------------------------------------------------------------------


def test_metrics_v2_endpoint_includes_adapter_bus_section(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    from sylion.api.metrics_v2_routes import render_metrics

    record_dispatch_attempt("ollama", success=True, duration_s=0.5)
    record_circuit_state("ollama", "closed")
    out = render_metrics(log_root=tmp_path)
    # The aggregated /metrics/v2 page now embeds the adapter_bus block.
    assert "adapter_bus_dispatch_total" in out
    assert "adapter_bus_circuit_state" in out
