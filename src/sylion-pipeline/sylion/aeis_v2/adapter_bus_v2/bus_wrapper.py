"""W11 G2 — composition wrapper around v1 AdapterBus.

``AdapterBusV2`` adds retry semantics + per-adapter circuit breaker around
each ``v1_bus.dispatch()`` call WITHOUT modifying v1. The v1
``sylion.execution.adapter_bus.AdapterBus`` is load-bearing and routes
calls between SYLION layers without retry semantics — a transient failure
in one adapter takes down the call. Callers opt in to v2 semantics by
constructing ``AdapterBusV2(bus=v1_bus, ...)`` and calling
``v2.call(adapter_id, ...)`` instead of ``v1.dispatch(adapter_id, ...)``.

Sequence per call:

    breaker.call(retry_call, _dispatch, policy=retry_policy)
                    │           │
                    │           └─→ runs _dispatch(), retrying retriable
                    │               errors with exponential backoff
                    │
                    └─→ short-circuits with CircuitBreakerOpen if the
                        breaker is OPEN; tracks success/failure to drive
                        the CLOSED → OPEN → HALF_OPEN state machine

Per-adapter state:

- One ``CircuitBreaker(name=adapter_id)`` per adapter, lazily created on
  first call. Tracked in a dict guarded by a ``threading.Lock``.
- One shared default ``RetryPolicy``; per-adapter overrides via a
  ``per_adapter_retry`` map passed to the constructor.
- Same pattern for the breaker policy (per-adapter override map).

Phase 0 (this commit): synchronous only. Async support is tracked for a
later G2 step — would mirror this class with ``call_async`` + the
``retry_call_async`` / ``CircuitBreaker.call_async`` primitives.

Programming-error semantics: the retry layer's
``non_retriable_exceptions`` (ValueError, TypeError, KeyError by default)
bubble immediately on the first failure. They still count as a failure
for the breaker — that mirrors how a real adapter that raises
``ValueError`` is broken regardless of whether it's a "transient" error
class. Tests cover this via the ``ConnectionError`` happy-path; the
breaker semantics are independent of which exception fired.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Optional

from .circuit_breaker import CircuitBreaker, CircuitBreakerPolicy
from .retry import RetryPolicy, retry_call

if TYPE_CHECKING:  # pragma: no cover — type-only import to avoid v1 hard dep
    from sylion.execution.adapter_bus import AdapterBus


class AdapterBusV2:
    """Composition wrapper around v1 AdapterBus adding retry + circuit-breaker.

    Phase 0: synchronous only. Async support tracked for G2 step 2.

    Per-adapter state:
    - One CircuitBreaker per adapter_id, lazily created on first call.
    - One shared RetryPolicy (default), overridable per adapter via config map.

    Behavior:
    - call() acquires breaker.call() which short-circuits if OPEN
    - Inside breaker, retry_call() runs the v1 dispatch with backoff
    - Programming errors (ValueError/TypeError/KeyError) bubble immediately
    - Returns the v1 dispatch result on success
    - Raises CircuitBreakerOpen if the breaker is OPEN
    - Raises the underlying exception if all retries exhausted
    """

    def __init__(
        self,
        bus: "AdapterBus",  # v1 instance (or any object exposing .dispatch)
        *,
        default_retry_policy: Optional[RetryPolicy] = None,
        default_breaker_policy: Optional[CircuitBreakerPolicy] = None,
        per_adapter_retry: Optional[dict[str, RetryPolicy]] = None,
        per_adapter_breaker: Optional[dict[str, CircuitBreakerPolicy]] = None,
    ) -> None:
        self._bus = bus
        self._default_retry = default_retry_policy or RetryPolicy()
        self._default_breaker = default_breaker_policy or CircuitBreakerPolicy()
        self._per_adapter_retry: dict[str, RetryPolicy] = dict(per_adapter_retry or {})
        self._per_adapter_breaker: dict[str, CircuitBreakerPolicy] = dict(
            per_adapter_breaker or {}
        )
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- helpers

    def _get_breaker(self, adapter_id: str) -> CircuitBreaker:
        """Return the per-adapter breaker, creating it on first use."""
        with self._lock:
            br = self._breakers.get(adapter_id)
            if br is None:
                policy = self._per_adapter_breaker.get(
                    adapter_id, self._default_breaker
                )
                br = CircuitBreaker(adapter_id, policy=policy)
                self._breakers[adapter_id] = br
            return br

    def _get_retry_policy(self, adapter_id: str) -> RetryPolicy:
        """Return the per-adapter retry policy or the shared default."""
        return self._per_adapter_retry.get(adapter_id, self._default_retry)

    # -------------------------------------------------------------------- API

    def call(self, adapter_id: str, *args: Any, **kwargs: Any) -> Any:
        """Forward to v1 ``bus.dispatch(adapter_id, *args, **kwargs)`` with
        retry + circuit-breaker around the call.

        Sequence: breaker → retry → v1 dispatch.
        - The breaker checks state first; if OPEN it raises before retry runs.
        - Inside the breaker, retry_call() handles backoff for transient errors.
        - If retries exhaust, the underlying exception propagates and the
          breaker counts it as one failure.
        """
        breaker = self._get_breaker(adapter_id)
        retry_policy = self._get_retry_policy(adapter_id)

        def _dispatch() -> Any:
            return self._bus.dispatch(adapter_id, *args, **kwargs)

        return breaker.call(retry_call, _dispatch, policy=retry_policy)

    def stats(self) -> dict[str, dict[str, Any]]:
        """Snapshot of per-adapter breaker state — for observability.

        Returns a dict keyed by adapter_id with the breaker's current state
        (string-valued enum, e.g. "closed"/"open"/"half_open") and its
        consecutive-failures counter. Only adapters that have been called
        at least once are present.
        """
        with self._lock:
            breakers = list(self._breakers.items())
        return {
            aid: {
                "state": br.state.value,
                "consecutive_failures": br.failure_count,
            }
            for aid, br in breakers
        }

    # --------------------------------------------------------- config helpers

    def set_retry_policy(self, adapter_id: str, policy: RetryPolicy) -> None:
        """Install or replace the per-adapter retry policy.

        Useful for runtime tuning — e.g. a tight loop adapter wants
        ``max_attempts=1`` while a slow upstream wants ``max_attempts=5``.
        """
        with self._lock:
            self._per_adapter_retry[adapter_id] = policy

    def set_breaker_policy(
        self, adapter_id: str, policy: CircuitBreakerPolicy
    ) -> None:
        """Install or replace the per-adapter breaker policy.

        Note: only affects breakers created AFTER this call. An already-
        instantiated breaker keeps its original policy — replacing live
        breaker state is intentionally not supported (it would silently
        invalidate the failure counter).
        """
        with self._lock:
            self._per_adapter_breaker[adapter_id] = policy
