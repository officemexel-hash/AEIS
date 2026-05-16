"""3-state circuit breaker for the v2 Adapter Bus.

States: CLOSED (normal) → OPEN (failing, reject calls) → HALF_OPEN (probing).

State machine:

    CLOSED  --N consecutive failures-->  OPEN
    OPEN    --open_duration_s elapsed-->  HALF_OPEN
    HALF_OPEN  --trial succeeds-->  CLOSED  (counters reset)
    HALF_OPEN  --trial fails-->     OPEN    (opened_at refreshed)

Thread-safe via a single ``threading.Lock`` per breaker instance.

Note: G2 will integrate this with v1 adapter_bus via a wrapper that
injects RetryPolicy + CircuitBreaker around each adapter call.
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Optional


class CircuitBreakerState(str, Enum):
    """Breaker state — string-valued for easy logging/serialization."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerPolicy:
    """Tuning knobs for the breaker."""

    failure_threshold: int = 5
    open_duration_s: float = 30.0
    half_open_max_calls: int = 1


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the breaker is OPEN."""


_DEFAULT_POLICY = CircuitBreakerPolicy()


class CircuitBreaker:
    """A simple 3-state circuit breaker.

    Use::

        breaker = CircuitBreaker("my_adapter")
        try:
            result = breaker.call(some_fn, arg1, arg2)
        except CircuitBreakerOpen:
            # breaker is OPEN — short-circuit, no call was made
            ...
    """

    def __init__(
        self,
        name: str,
        policy: Optional[CircuitBreakerPolicy] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.policy = policy if policy is not None else _DEFAULT_POLICY
        self._clock = clock
        self._lock = threading.Lock()
        self._state: CircuitBreakerState = CircuitBreakerState.CLOSED
        self._consecutive_failures: int = 0
        self._opened_at: Optional[float] = None
        self._half_open_in_flight: int = 0

    # ----------------------------------------------------------------- API

    @property
    def state(self) -> CircuitBreakerState:
        """Read-only state for observability.

        Side-effect: if we are OPEN and the open_duration has elapsed,
        the read transitions to HALF_OPEN. This is intentional — it lets
        the next ``call()`` issue a trial without an external poker.
        """
        with self._lock:
            self._maybe_half_open_locked()
            return self._state

    @property
    def failure_count(self) -> int:
        """Read-only consecutive-failures counter for observability.

        Resets to 0 on a successful call in CLOSED state, or on the trial
        success that flips HALF_OPEN → CLOSED. Never exposed for mutation —
        the wrapper's ``stats()`` helper relies on this snapshot.
        """
        with self._lock:
            return self._consecutive_failures

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Sync wrapper. Raises CircuitBreakerOpen if breaker is OPEN."""
        self._before_call()
        try:
            result = fn(*args, **kwargs)
        except BaseException:
            self._record_failure()
            raise
        else:
            self._record_success()
            return result

    async def call_async(
        self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
    ) -> Any:
        """Async wrapper. Raises CircuitBreakerOpen if breaker is OPEN."""
        self._before_call()
        try:
            result = await fn(*args, **kwargs)
        except BaseException:
            self._record_failure()
            raise
        else:
            self._record_success()
            return result

    # ----------------------------------------------------------------- internals

    def _before_call(self) -> None:
        """Decide whether to allow this call. Raises if breaker is OPEN."""
        with self._lock:
            self._maybe_half_open_locked()
            if self._state is CircuitBreakerState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN — call rejected"
                )
            if self._state is CircuitBreakerState.HALF_OPEN:
                if self._half_open_in_flight >= self.policy.half_open_max_calls:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker '{self.name}' is HALF_OPEN — "
                        f"trial slot already taken"
                    )
                self._half_open_in_flight += 1

    def _record_success(self) -> None:
        with self._lock:
            if self._state is CircuitBreakerState.HALF_OPEN:
                # Trial succeeded → reset to CLOSED.
                self._state = CircuitBreakerState.CLOSED
                self._consecutive_failures = 0
                self._opened_at = None
                self._half_open_in_flight = 0
            elif self._state is CircuitBreakerState.CLOSED:
                # Healthy call: reset the failure counter.
                self._consecutive_failures = 0

    def _record_failure(self) -> None:
        with self._lock:
            if self._state is CircuitBreakerState.HALF_OPEN:
                # Trial failed → re-open.
                self._half_open_in_flight = 0
                self._state = CircuitBreakerState.OPEN
                self._opened_at = self._clock()
                # Counter stays at threshold (we don't reset it on re-open).
                if self._consecutive_failures < self.policy.failure_threshold:
                    self._consecutive_failures = self.policy.failure_threshold
                return

            self._consecutive_failures += 1
            if (
                self._state is CircuitBreakerState.CLOSED
                and self._consecutive_failures >= self.policy.failure_threshold
            ):
                self._state = CircuitBreakerState.OPEN
                self._opened_at = self._clock()

    def _maybe_half_open_locked(self) -> None:
        """If OPEN and duration elapsed, transition to HALF_OPEN.

        Caller must hold self._lock.
        """
        if (
            self._state is CircuitBreakerState.OPEN
            and self._opened_at is not None
            and (self._clock() - self._opened_at) >= self.policy.open_duration_s
        ):
            self._state = CircuitBreakerState.HALF_OPEN
            self._half_open_in_flight = 0
