"""W19-specific Prometheus metrics.

Sprint 4 deliverable. Surfaces 6 W19-relevant series alongside the
adapter_bus + audit_chain metrics already on /api/v1/metrics/v2:

    sylion_v2_w19_renders_total{outcome}      counter
    sylion_v2_w19_render_seconds_sum          counter (sum)
    sylion_v2_w19_render_seconds_count        counter (count)
    sylion_v2_w19_denies_total{rule}          counter
    sylion_v2_w19_rollout_percent             gauge
    sylion_v2_w19_evaluator_enabled           gauge (1/0)

Per Kimi k5 R56:00 — these are the 5 essential metrics the operator
panel needs to see the canary's heartbeat in real time.

Same in-memory tally pattern as ``adapter_bus_v2/metrics.py`` (commit
a6d9b1a4) so rendering composes cleanly into the existing
``render_metrics()`` aggregator.
"""
from __future__ import annotations

import threading
from typing import Iterable

_LOCK = threading.RLock()

#: ``(outcome) -> count``  outcome ∈ ROUTING_OUTCOMES.
_RENDERS_TOTAL: dict[str, int] = {}

#: ``(sum_seconds, count)`` for histogram-emulation.
_RENDER_SECONDS: tuple[float, int] = (0.0, 0)

#: ``(rule) -> count`` — incremented when outcome="deny" + rule label.
_DENIES_TOTAL: dict[str, int] = {}

#: Last-known operator dial percent (0..100).
_ROLLOUT_PERCENT: int = 0

#: Last-known evaluator-enabled flag (1 = on, 0 = off).
_EVALUATOR_ENABLED: int = 0


def _escape(label: str) -> str:
    return (
        str(label)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )


def record_render(outcome: str, *, duration_s: float = 0.0) -> None:
    """Tally one render outcome + observe its duration."""
    global _RENDER_SECONDS
    with _LOCK:
        _RENDERS_TOTAL[outcome] = _RENDERS_TOTAL.get(outcome, 0) + 1
        prev_sum, prev_count = _RENDER_SECONDS
        _RENDER_SECONDS = (
            prev_sum + max(0.0, duration_s),
            prev_count + 1,
        )


def record_deny(rule: str) -> None:
    """Tally one deny by rule label (e.g. policy_id)."""
    with _LOCK:
        key = rule or "unknown"
        _DENIES_TOTAL[key] = _DENIES_TOTAL.get(key, 0) + 1


def record_rollout_percent(percent: int) -> None:
    """Update the rollout-percent gauge (clamped 0..100)."""
    global _ROLLOUT_PERCENT
    with _LOCK:
        _ROLLOUT_PERCENT = max(0, min(100, int(percent)))


def record_evaluator_enabled(enabled: bool) -> None:
    """Update the evaluator-enabled gauge (1 = on, 0 = off)."""
    global _EVALUATOR_ENABLED
    with _LOCK:
        _EVALUATOR_ENABLED = 1 if enabled else 0


def render_w19_metrics() -> str:
    """Return W19 metrics in Prometheus exposition format."""
    lines: list[str] = []

    lines.append("# HELP sylion_v2_w19_renders_total W19 evaluator render outcomes")
    lines.append("# TYPE sylion_v2_w19_renders_total counter")
    with _LOCK:
        for outcome, count in sorted(_RENDERS_TOTAL.items()):
            lines.append(
                f'sylion_v2_w19_renders_total{{outcome="{_escape(outcome)}"}} {count}'
            )

    with _LOCK:
        sum_s, count = _RENDER_SECONDS
    lines.append("# HELP sylion_v2_w19_render_seconds_sum total render duration")
    lines.append("# TYPE sylion_v2_w19_render_seconds_sum counter")
    lines.append(f"sylion_v2_w19_render_seconds_sum {round(sum_s, 6)}")

    lines.append("# HELP sylion_v2_w19_render_seconds_count render observations")
    lines.append("# TYPE sylion_v2_w19_render_seconds_count counter")
    lines.append(f"sylion_v2_w19_render_seconds_count {count}")

    lines.append("# HELP sylion_v2_w19_denies_total W19 deny outcomes by rule")
    lines.append("# TYPE sylion_v2_w19_denies_total counter")
    with _LOCK:
        for rule, count in sorted(_DENIES_TOTAL.items()):
            lines.append(
                f'sylion_v2_w19_denies_total{{rule="{_escape(rule)}"}} {count}'
            )

    lines.append("# HELP sylion_v2_w19_rollout_percent current canary dial percent")
    lines.append("# TYPE sylion_v2_w19_rollout_percent gauge")
    with _LOCK:
        lines.append(f"sylion_v2_w19_rollout_percent {_ROLLOUT_PERCENT}")

    lines.append(
        "# HELP sylion_v2_w19_evaluator_enabled evaluator feature flag (1/0)"
    )
    lines.append("# TYPE sylion_v2_w19_evaluator_enabled gauge")
    with _LOCK:
        lines.append(f"sylion_v2_w19_evaluator_enabled {_EVALUATOR_ENABLED}")

    return "\n".join(lines) + "\n"


def reset_w19_metrics() -> None:
    """Drop in-memory state — test/operator helper."""
    global _RENDER_SECONDS, _ROLLOUT_PERCENT, _EVALUATOR_ENABLED
    with _LOCK:
        _RENDERS_TOTAL.clear()
        _DENIES_TOTAL.clear()
        _RENDER_SECONDS = (0.0, 0)
        _ROLLOUT_PERCENT = 0
        _EVALUATOR_ENABLED = 0


def snapshot_w19_metrics() -> dict[str, object]:
    """Return JSON-friendly state snapshot."""
    with _LOCK:
        return {
            "renders_total": dict(_RENDERS_TOTAL),
            "render_seconds": {
                "sum": round(_RENDER_SECONDS[0], 6),
                "count": _RENDER_SECONDS[1],
            },
            "denies_total": dict(_DENIES_TOTAL),
            "rollout_percent": _ROLLOUT_PERCENT,
            "evaluator_enabled": _EVALUATOR_ENABLED,
        }


__all__ = [
    "record_deny",
    "record_evaluator_enabled",
    "record_render",
    "record_rollout_percent",
    "render_w19_metrics",
    "reset_w19_metrics",
    "snapshot_w19_metrics",
]
