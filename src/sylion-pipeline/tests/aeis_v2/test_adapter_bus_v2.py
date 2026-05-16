"""Tests for sylion.aeis_v2.adapter_bus_v2 — RetryPolicy + CircuitBreaker.

Covers:
- RetryPolicy.should_retry: retriable vs non-retriable exception classification.
- RetryPolicy.delay_for_attempt: exponential growth with jitter tolerance.
- retry_call: success on 1st attempt, success on 2nd, exhaustion + raise.
- CircuitBreaker: opens after N failures, rejects when OPEN, transitions to
  HALF_OPEN after open_duration, resets to CLOSED on half-open success,
  re-opens on half-open failure.

Timing: short delays (<=10 ms) keep the suite under 1 s. The breaker
duration test uses 0.1 s.
"""
from __future__ import annotations

import time

import pytest

from sylion.aeis_v2.adapter_bus_v2 import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerPolicy,
    CircuitBreakerState,
    RetryPolicy,
    retry_call,
)


# --------------------------------------------------------------------- RetryPolicy


def test_retry_policy_should_retry_returns_true_for_connection_error():
    pol = RetryPolicy(max_attempts=3)
    exc = ConnectionError("boom")
    assert pol.should_retry(exc, attempt=1) is True
    assert pol.should_retry(exc, attempt=2) is True
    # At max_attempts: no more retries.
    assert pol.should_retry(exc, attempt=3) is False


def test_retry_policy_should_retry_returns_false_for_value_error():
    pol = RetryPolicy(max_attempts=3)
    exc = ValueError("bad input")
    # Non-retriable: never retry, regardless of attempt.
    assert pol.should_retry(exc, attempt=1) is False
    assert pol.should_retry(exc, attempt=2) is False


def test_retry_policy_delay_grows_exponentially():
    # Zero jitter so we can assert exact values.
    pol = RetryPolicy(
        initial_delay_s=0.5,
        backoff_multiplier=2.0,
        max_delay_s=30.0,
        jitter=0.0,
    )
    assert pol.delay_for_attempt(1) == pytest.approx(0.5)
    assert pol.delay_for_attempt(2) == pytest.approx(1.0)
    assert pol.delay_for_attempt(3) == pytest.approx(2.0)
    # With jitter, values stay within ±10 % of the deterministic base.
    pol_j = RetryPolicy(
        initial_delay_s=0.5,
        backoff_multiplier=2.0,
        max_delay_s=30.0,
        jitter=0.1,
    )
    for _ in range(20):
        d1 = pol_j.delay_for_attempt(1)
        assert 0.45 <= d1 <= 0.55
        d2 = pol_j.delay_for_attempt(2)
        assert 0.9 <= d2 <= 1.1


def test_retry_policy_delay_capped_at_max():
    pol = RetryPolicy(
        initial_delay_s=10.0, backoff_multiplier=10.0, max_delay_s=30.0, jitter=0.0
    )
    # 10 * 10^3 = 10000 → capped at 30.
    assert pol.delay_for_attempt(4) == pytest.approx(30.0)


# --------------------------------------------------------------------- retry_call


def test_retry_call_succeeds_on_first_attempt():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return "ok"

    result = retry_call(fn, policy=RetryPolicy(initial_delay_s=0.01))
    assert result == "ok"
    assert calls["n"] == 1


def test_retry_call_succeeds_on_second_attempt():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("transient")
        return "ok"

    pol = RetryPolicy(max_attempts=3, initial_delay_s=0.01, jitter=0.0)
    result = retry_call(fn, policy=pol)
    assert result == "ok"
    assert calls["n"] == 2


def test_retry_call_exhausts_and_raises():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ConnectionError(f"fail #{calls['n']}")

    pol = RetryPolicy(max_attempts=3, initial_delay_s=0.01, jitter=0.0)
    with pytest.raises(ConnectionError) as excinfo:
        retry_call(fn, policy=pol)
    assert calls["n"] == 3
    assert "fail #3" in str(excinfo.value)


def test_retry_call_raises_immediately_for_non_retriable():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("programming error")

    pol = RetryPolicy(max_attempts=5, initial_delay_s=0.01)
    with pytest.raises(ValueError):
        retry_call(fn, policy=pol)
    # Non-retriable: only one call.
    assert calls["n"] == 1


# --------------------------------------------------------------------- CircuitBreaker


def _failing(msg: str = "boom"):
    def _fn():
        raise ConnectionError(msg)

    return _fn


def _ok(value: str = "ok"):
    def _fn():
        return value

    return _fn


def test_circuit_breaker_opens_after_n_failures():
    pol = CircuitBreakerPolicy(failure_threshold=3, open_duration_s=10.0)
    br = CircuitBreaker("test", policy=pol)
    assert br.state is CircuitBreakerState.CLOSED

    fail = _failing()
    for _ in range(3):
        with pytest.raises(ConnectionError):
            br.call(fail)
    assert br.state is CircuitBreakerState.OPEN


def test_circuit_breaker_rejects_calls_when_open():
    pol = CircuitBreakerPolicy(failure_threshold=2, open_duration_s=10.0)
    br = CircuitBreaker("test", policy=pol)
    fail = _failing()
    for _ in range(2):
        with pytest.raises(ConnectionError):
            br.call(fail)
    assert br.state is CircuitBreakerState.OPEN
    # Now the breaker rejects without invoking the function.
    invoked = {"n": 0}

    def tracker():
        invoked["n"] += 1
        return "should not happen"

    with pytest.raises(CircuitBreakerOpen):
        br.call(tracker)
    assert invoked["n"] == 0


def test_circuit_breaker_transitions_to_half_open_after_duration():
    pol = CircuitBreakerPolicy(failure_threshold=2, open_duration_s=0.1)
    br = CircuitBreaker("test", policy=pol)
    fail = _failing()
    for _ in range(2):
        with pytest.raises(ConnectionError):
            br.call(fail)
    assert br.state is CircuitBreakerState.OPEN
    # Wait out the open_duration.
    time.sleep(0.15)
    # Reading state triggers the transition.
    assert br.state is CircuitBreakerState.HALF_OPEN


def test_circuit_breaker_resets_to_closed_on_half_open_success():
    pol = CircuitBreakerPolicy(failure_threshold=2, open_duration_s=0.05)
    br = CircuitBreaker("test", policy=pol)
    fail = _failing()
    for _ in range(2):
        with pytest.raises(ConnectionError):
            br.call(fail)
    assert br.state is CircuitBreakerState.OPEN
    time.sleep(0.08)
    # Trial succeeds → CLOSED, counter reset.
    result = br.call(_ok("recovered"))
    assert result == "recovered"
    assert br.state is CircuitBreakerState.CLOSED


def test_circuit_breaker_reopens_on_half_open_failure():
    pol = CircuitBreakerPolicy(failure_threshold=2, open_duration_s=0.05)
    br = CircuitBreaker("test", policy=pol)
    fail = _failing()
    for _ in range(2):
        with pytest.raises(ConnectionError):
            br.call(fail)
    assert br.state is CircuitBreakerState.OPEN
    time.sleep(0.08)
    # Trial fails → back to OPEN.
    with pytest.raises(ConnectionError):
        br.call(fail)
    assert br.state is CircuitBreakerState.OPEN


def test_circuit_breaker_state_property_is_read_only():
    br = CircuitBreaker("ro")
    # Can't set the state attribute directly (it's a property without a setter).
    with pytest.raises(AttributeError):
        br.state = CircuitBreakerState.OPEN  # type: ignore[misc]
