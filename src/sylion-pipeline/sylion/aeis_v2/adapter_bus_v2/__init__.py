"""W11 Adapter Bus v2 — retry-policy + circuit-breaker backplane.

Public surface:

    from sylion.aeis_v2.adapter_bus_v2 import (
        RetryPolicy, retry_call, retry_call_async,
        CircuitBreakerState, CircuitBreakerPolicy,
        CircuitBreaker, CircuitBreakerOpen,
        AdapterBusV2,
    )

This module is **purely additive**. It does NOT modify the v1 AdapterBus
(``sylion/execution/adapter_bus.py``), which is load-bearing and routes
calls between SYLION layers without retry semantics. The v1 bus has no
exponential backoff and no circuit breaker — a transient failure in one
adapter takes down the call.

W11 charter (extension) called for retry semantics in v2. This module
provides the building blocks AND the composition wrapper:

- ``retry.py``           — exponential-backoff RetryPolicy + sync/async wrappers
- ``circuit_breaker.py`` — 3-state breaker (CLOSED → OPEN → HALF_OPEN)
- ``bus_wrapper.py``     — ``AdapterBusV2`` composes v1 dispatch + retry + breaker

G2 integration: ``AdapterBusV2(bus=v1_bus, ...)`` wraps each adapter call
with one ``RetryPolicy`` (default + per-adapter overrides) and one
``CircuitBreaker`` per ``adapter_id`` (lazily created). v1 untouched —
callers opt in by calling ``v2.call(adapter_id, *args, **kwargs)``
instead of ``v1.dispatch(adapter_id, *args, **kwargs)``.
"""
from __future__ import annotations

from .bus_wrapper import AdapterBusV2
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerPolicy,
    CircuitBreakerState,
)
from .retry import RetryPolicy, retry_call, retry_call_async

__all__ = [
    "RetryPolicy",
    "retry_call",
    "retry_call_async",
    "CircuitBreakerState",
    "CircuitBreakerPolicy",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "AdapterBusV2",
]
