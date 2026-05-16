"""Prometheus metrics for the W11 Adapter Bus v2.

Sprint 3 deliverable per the W11 charter telemetry section + Kimi
review k1 round 50:30 on adapter-bus visibility.

Exposes 4 metric families:

* ``adapter_bus_dispatch_total{adapter,outcome}``       — counter
* ``adapter_bus_dispatch_seconds_sum{adapter}``         — counter (sum)
* ``adapter_bus_dispatch_seconds_count{adapter}``       — counter (count)
* ``adapter_bus_circuit_state{adapter,state}``          — gauge (1/0)
* ``adapter_bus_failures_total{adapter,reason}``        — counter

The module keeps an in-process tally — production deployments will
swap the underlying store for ``prometheus_client`` once the latter
is added to the dependency lock. The exposition text format mirrors
``metrics_v2_routes.render_metrics`` so the existing endpoint can
concatenate the adapter-bus section transparently.

Thread-safe via a single ``RLock``.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Iterable

#: Module-level state — process-wide.
_LOCK = threading.RLock()

#: Mapping ``(adapter, outcome) -> count``.
_DISPATCH_TOTAL: dict[tuple[str, str], int] = {}

#: Mapping ``adapter -> (sum_seconds, count)`` for histogram emulation.
_DISPATCH_SECONDS: dict[str, tuple[float, int]] = {}

#: Mapping ``(adapter, state) -> 1|0`` (gauge).
_CIRCUIT_STATE: dict[tuple[str, str], int] = {}

#: Mapping ``(adapter, reason) -> count``.
_FAILURES_TOTAL: dict[tuple[str, str], int] = {}

#: Canonical circuit states for gauge cardinality control.
_CIRCUIT_STATES = ("closed", "open", "half_open")


def _escape(label: str) -> str:
    """Prometheus label value escaping."""
    return (
        str(label)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


# ---------------------------------------------------------------------------
# Recording helpers — call from the adapter-bus hot path.
# ---------------------------------------------------------------------------


def record_dispatch_attempt(
    adapter: str, *, success: bool, duration_s: float = 0.0,
) -> None:
    """Tally one dispatch outcome + observe its duration."""
    outcome = "success" if success else "failure"
    with _LOCK:
        key = (adapter, outcome)
        _DISPATCH_TOTAL[key] = _DISPATCH_TOTAL.get(key, 0) + 1
        prev_sum, prev_count = _DISPATCH_SECONDS.get(adapter, (0.0, 0))
        _DISPATCH_SECONDS[adapter] = (
            prev_sum + max(0.0, duration_s),
            prev_count + 1,
        )


def record_failure(adapter: str, reason: str) -> None:
    """Tally a typed failure (e.g. ``"timeout"``, ``"breaker_open"``)."""
    with _LOCK:
        key = (adapter, reason or "unknown")
        _FAILURES_TOTAL[key] = _FAILURES_TOTAL.get(key, 0) + 1


def record_circuit_state(adapter: str, state: str) -> None:
    """Update the per-adapter circuit-breaker state gauge.

    Sets the matching ``state`` gauge to 1 and the others to 0 so the
    Prometheus exposition shows exactly one active state per adapter at
    any time.
    """
    if state not in _CIRCUIT_STATES:
        state = "closed"  # defensive: unknown → closed (safe default)
    with _LOCK:
        for s in _CIRCUIT_STATES:
            _CIRCUIT_STATE[(adapter, s)] = 1 if s == state else 0


# ---------------------------------------------------------------------------
# Exposition rendering
# ---------------------------------------------------------------------------


def _format_metric(
    name: str, value: float | int, labels: dict[str, str] | None,
) -> str:
    if not labels:
        return f"{name} {value}"
    label_str = ",".join(
        f'{k}="{_escape(str(v))}"' for k, v in sorted(labels.items())
    )
    return f"{name}{{{label_str}}} {value}"


def render_adapter_bus_metrics() -> str:
    """Return the adapter-bus metrics in Prometheus exposition format."""
    lines: list[str] = []

    # 1. dispatch_total
    lines.append(
        "# HELP adapter_bus_dispatch_total adapter dispatches by outcome"
    )
    lines.append("# TYPE adapter_bus_dispatch_total counter")
    with _LOCK:
        for (adapter, outcome), count in sorted(_DISPATCH_TOTAL.items()):
            lines.append(_format_metric(
                "adapter_bus_dispatch_total", count,
                {"adapter": adapter, "outcome": outcome},
            ))

    # 2. dispatch_seconds (sum + count) — histogram-like via two series
    lines.append(
        "# HELP adapter_bus_dispatch_seconds_sum total dispatch duration"
    )
    lines.append("# TYPE adapter_bus_dispatch_seconds_sum counter")
    with _LOCK:
        for adapter, (sum_s, _count) in sorted(_DISPATCH_SECONDS.items()):
            lines.append(_format_metric(
                "adapter_bus_dispatch_seconds_sum",
                round(sum_s, 6), {"adapter": adapter},
            ))

    lines.append(
        "# HELP adapter_bus_dispatch_seconds_count number of observations"
    )
    lines.append("# TYPE adapter_bus_dispatch_seconds_count counter")
    with _LOCK:
        for adapter, (_sum, count) in sorted(_DISPATCH_SECONDS.items()):
            lines.append(_format_metric(
                "adapter_bus_dispatch_seconds_count", count,
                {"adapter": adapter},
            ))

    # 3. circuit_state (gauge)
    lines.append(
        "# HELP adapter_bus_circuit_state circuit breaker state per adapter"
    )
    lines.append("# TYPE adapter_bus_circuit_state gauge")
    with _LOCK:
        for (adapter, state), v in sorted(_CIRCUIT_STATE.items()):
            lines.append(_format_metric(
                "adapter_bus_circuit_state", v,
                {"adapter": adapter, "state": state},
            ))

    # 4. failures_total
    lines.append(
        "# HELP adapter_bus_failures_total typed adapter failures"
    )
    lines.append("# TYPE adapter_bus_failures_total counter")
    with _LOCK:
        for (adapter, reason), count in sorted(_FAILURES_TOTAL.items()):
            lines.append(_format_metric(
                "adapter_bus_failures_total", count,
                {"adapter": adapter, "reason": reason},
            ))

    return "\n".join(lines) + "\n"


def reset_adapter_bus_metrics() -> None:
    """Drop all in-memory counters/gauges. Test + operator helper."""
    with _LOCK:
        _DISPATCH_TOTAL.clear()
        _DISPATCH_SECONDS.clear()
        _CIRCUIT_STATE.clear()
        _FAILURES_TOTAL.clear()


def snapshot_adapter_bus_metrics() -> dict[str, object]:
    """Return a JSON-friendly snapshot of the current metrics state."""
    with _LOCK:
        return {
            "dispatch_total": {
                f"{a}|{o}": c for (a, o), c in _DISPATCH_TOTAL.items()
            },
            "dispatch_seconds": {
                a: {"sum": round(s, 6), "count": c}
                for a, (s, c) in _DISPATCH_SECONDS.items()
            },
            "circuit_state": {
                f"{a}|{s}": v for (a, s), v in _CIRCUIT_STATE.items()
            },
            "failures_total": {
                f"{a}|{r}": c for (a, r), c in _FAILURES_TOTAL.items()
            },
        }


__all__ = [
    "record_circuit_state",
    "record_dispatch_attempt",
    "record_failure",
    "render_adapter_bus_metrics",
    "reset_adapter_bus_metrics",
    "snapshot_adapter_bus_metrics",
]
