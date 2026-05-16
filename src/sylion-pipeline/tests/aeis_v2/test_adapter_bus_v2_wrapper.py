"""Tests for sylion.aeis_v2.adapter_bus_v2.bus_wrapper — AdapterBusV2.

Covers the composition wrapper that adds retry + circuit-breaker around
v1 ``AdapterBus.dispatch()``:

- v1 dispatch is invoked on first attempt and the result is forwarded.
- Transient errors (ConnectionError) trigger retries with backoff.
- The breaker opens after the configured number of FAILED wrapper calls
  (each wrapper call may consume multiple retries internally but counts
  as one breaker failure once the retries exhaust).
- Each adapter_id gets its own breaker — one adapter failing does not
  trip another adapter's breaker.
- Per-adapter retry policy overrides the default.
- ``stats()`` reports per-adapter breaker state for observability.

Tests are hermetic: they use a ``_FakeBus`` instead of importing the
real v1 ``AdapterBus`` (which would pull in sqlite + EventBus).
Retry delays are kept tiny (≤10 ms) and jitter is zeroed out so the
suite stays deterministic and well under 1 s.
"""
from __future__ import annotations

from typing import Any

import pytest

from sylion.aeis_v2.adapter_bus_v2 import (
    AdapterBusV2,
    CircuitBreakerOpen,
    CircuitBreakerPolicy,
    RetryPolicy,
)


# --------------------------------------------------------------------- helpers


class _FakeBus:
    """Minimal v1-bus stand-in. ``dispatch`` plays back side_effects in order.

    A side-effect that is a ``BaseException`` instance is raised; otherwise
    it is returned. Each call appends ``(adapter_id, args, kwargs)`` to
    ``self.calls`` so tests can assert call counts and arguments.
    """

    def __init__(self, side_effects: list[Any]) -> None:
        self.side_effects = side_effects
        self.calls: list[tuple[str, tuple, dict]] = []

    def dispatch(self, adapter_id: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((adapter_id, args, kwargs))
        if not self.side_effects:
            raise AssertionError(
                f"FakeBus exhausted: unexpected dispatch({adapter_id!r}, ...)"
            )
        result = self.side_effects.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _fast_retry(max_attempts: int = 3) -> RetryPolicy:
    """Tight retry policy for tests — small delays, no jitter."""
    return RetryPolicy(
        max_attempts=max_attempts, initial_delay_s=0.001, jitter=0.0
    )


# --------------------------------------------------------------------- tests


def test_wrapper_calls_v1_dispatch_on_first_attempt():
    """Happy path: dispatch returns immediately, wrapper forwards the result."""
    bus = _FakeBus(side_effects=["ok"])
    wrapper = AdapterBusV2(bus, default_retry_policy=_fast_retry())

    result = wrapper.call("adp1", "payload", flag=True)

    assert result == "ok"
    assert len(bus.calls) == 1
    assert bus.calls[0] == ("adp1", ("payload",), {"flag": True})


def test_wrapper_retries_on_connection_error():
    """ConnectionError twice then "ok" → wrapper recovers, v1 invoked 3x."""
    bus = _FakeBus(
        side_effects=[
            ConnectionError("boom1"),
            ConnectionError("boom2"),
            "ok",
        ]
    )
    wrapper = AdapterBusV2(bus, default_retry_policy=_fast_retry(max_attempts=3))

    result = wrapper.call("flaky")

    assert result == "ok"
    assert len(bus.calls) == 3


def test_wrapper_opens_breaker_after_n_failures():
    """After ``failure_threshold`` exhausted wrapper calls, breaker is OPEN.

    With max_attempts=1 each wrapper.call() consumes exactly one v1 dispatch
    and counts as exactly one breaker failure. failure_threshold=3 → after
    3 failed wrapper calls the breaker flips to OPEN and the next call is
    short-circuited with CircuitBreakerOpen — no v1 dispatch happens.
    """
    # Always-fail bus: every dispatch raises ConnectionError.
    bus = _FakeBus(side_effects=[ConnectionError(f"fail-{i}") for i in range(10)])
    wrapper = AdapterBusV2(
        bus,
        default_retry_policy=_fast_retry(max_attempts=1),
        default_breaker_policy=CircuitBreakerPolicy(
            failure_threshold=3, open_duration_s=10.0
        ),
    )

    # Three failed wrapper calls: each dispatches once (max_attempts=1),
    # each counts as one breaker failure.
    for _ in range(3):
        with pytest.raises(ConnectionError):
            wrapper.call("doomed")
    assert len(bus.calls) == 3

    # Fourth call: breaker is OPEN, no dispatch happens.
    with pytest.raises(CircuitBreakerOpen):
        wrapper.call("doomed")
    assert len(bus.calls) == 3  # unchanged

    # And stats reflect it.
    snap = wrapper.stats()
    assert snap["doomed"]["state"] == "open"
    assert snap["doomed"]["consecutive_failures"] >= 3


def test_wrapper_circuit_breaker_per_adapter():
    """Two adapter_ids ⇒ two independent breakers.

    "doomed" fails repeatedly and trips its breaker; "healthy" returns "ok"
    every time. After tripping "doomed", "healthy" still works AND its own
    breaker is CLOSED.
    """

    class _MixedBus:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def dispatch(self, adapter_id: str, *args: Any, **kwargs: Any) -> Any:
            self.calls.append(adapter_id)
            if adapter_id == "doomed":
                raise ConnectionError("doomed always fails")
            return "ok"

    bus = _MixedBus()
    wrapper = AdapterBusV2(
        bus,  # type: ignore[arg-type]
        default_retry_policy=_fast_retry(max_attempts=1),
        default_breaker_policy=CircuitBreakerPolicy(
            failure_threshold=2, open_duration_s=10.0
        ),
    )

    # Trip "doomed".
    for _ in range(2):
        with pytest.raises(ConnectionError):
            wrapper.call("doomed")
    with pytest.raises(CircuitBreakerOpen):
        wrapper.call("doomed")

    # "healthy" still works — it has its own (CLOSED) breaker.
    assert wrapper.call("healthy") == "ok"
    assert wrapper.call("healthy") == "ok"

    snap = wrapper.stats()
    assert snap["doomed"]["state"] == "open"
    assert snap["healthy"]["state"] == "closed"
    assert snap["healthy"]["consecutive_failures"] == 0


def test_wrapper_per_adapter_retry_policy_overrides_default():
    """Per-adapter retry policy is honored; default applies to other adapters.

    Adapter "fast" gets max_attempts=1 — gives up after one dispatch.
    Adapter "slow" uses the default max_attempts=3.
    """
    # 1 dispatch for "fast" (gives up), then 3 for "slow" (exhausts default).
    bus = _FakeBus(
        side_effects=[
            ConnectionError("fast-1"),
            ConnectionError("slow-1"),
            ConnectionError("slow-2"),
            ConnectionError("slow-3"),
        ]
    )
    wrapper = AdapterBusV2(
        bus,
        default_retry_policy=_fast_retry(max_attempts=3),
        per_adapter_retry={"fast": _fast_retry(max_attempts=1)},
        # Big breaker threshold so it doesn't open mid-test.
        default_breaker_policy=CircuitBreakerPolicy(
            failure_threshold=100, open_duration_s=10.0
        ),
    )

    with pytest.raises(ConnectionError):
        wrapper.call("fast")
    # Only one dispatch for "fast" — it gave up after attempt #1.
    fast_calls = [c for c in bus.calls if c[0] == "fast"]
    assert len(fast_calls) == 1

    with pytest.raises(ConnectionError):
        wrapper.call("slow")
    # Three dispatches for "slow" — default max_attempts=3.
    slow_calls = [c for c in bus.calls if c[0] == "slow"]
    assert len(slow_calls) == 3


def test_wrapper_stats_reports_per_adapter_state():
    """After successful calls, stats() shows CLOSED and zero failures."""
    bus = _FakeBus(side_effects=["ok1", "ok2", "ok3"])
    wrapper = AdapterBusV2(bus, default_retry_policy=_fast_retry())

    wrapper.call("adp1")
    wrapper.call("adp1")
    wrapper.call("adp2")

    snap = wrapper.stats()
    # Both adapters present, both CLOSED, zero consecutive failures.
    assert set(snap.keys()) == {"adp1", "adp2"}
    assert snap["adp1"]["state"] == "closed"
    assert snap["adp1"]["consecutive_failures"] == 0
    assert snap["adp2"]["state"] == "closed"
    assert snap["adp2"]["consecutive_failures"] == 0


def test_wrapper_non_retriable_error_bubbles_immediately():
    """ValueError (non-retriable) raises on the first dispatch — no retries."""
    bus = _FakeBus(side_effects=[ValueError("bad input")])
    wrapper = AdapterBusV2(bus, default_retry_policy=_fast_retry(max_attempts=5))

    with pytest.raises(ValueError):
        wrapper.call("adp1", "payload")

    # Exactly one v1 dispatch — non-retriable short-circuits the retry loop.
    assert len(bus.calls) == 1
