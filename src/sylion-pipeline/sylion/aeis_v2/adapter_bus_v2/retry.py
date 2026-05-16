"""Exponential-backoff retry policy for the v2 Adapter Bus.

Provides:

- ``RetryPolicy`` — dataclass holding max_attempts, delays, jitter,
  retriable / non-retriable exception tuples.
- ``retry_call(fn, *args, policy=..., **kwargs)`` — sync wrapper using
  ``time.sleep``.
- ``retry_call_async(fn, *args, policy=..., **kwargs)`` — async wrapper
  using ``asyncio.sleep``.

Both wrappers:

- Track attempt count (1-indexed in delay calculation).
- Sleep ``policy.delay_for_attempt(attempt)`` between retries.
- Re-raise the last exception if all retries exhausted.
- Re-raise immediately for exceptions in ``non_retriable_exceptions``
  (programming errors — ValueError, TypeError, KeyError by default).

Note: G2 will integrate this with v1 adapter_bus via a wrapper that
injects RetryPolicy + CircuitBreaker around each adapter call.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional


@dataclass
class RetryPolicy:
    """Exponential-backoff retry policy with jitter."""

    max_attempts: int = 3
    initial_delay_s: float = 0.5
    max_delay_s: float = 30.0
    backoff_multiplier: float = 2.0
    jitter: float = 0.1  # ±10% randomization
    retriable_exceptions: tuple[type[BaseException], ...] = field(
        default_factory=lambda: (ConnectionError, TimeoutError, OSError)
    )
    non_retriable_exceptions: tuple[type[BaseException], ...] = field(
        default_factory=lambda: (ValueError, TypeError, KeyError)
    )

    def should_retry(self, exc: BaseException, attempt: int) -> bool:
        """Return True iff exc is retriable AND we have attempts left.

        attempt is 1-indexed: attempt=1 means the first call has just
        failed. So we retry if attempt < max_attempts.
        """
        if attempt >= self.max_attempts:
            return False
        # Non-retriable wins over retriable if both match (defensive).
        if isinstance(exc, self.non_retriable_exceptions):
            return False
        if isinstance(exc, self.retriable_exceptions):
            return True
        return False

    def delay_for_attempt(self, attempt: int) -> float:
        """Compute delay before next attempt.

        attempt is 1-indexed: delay_for_attempt(1) is the delay AFTER the
        1st call failed and BEFORE the 2nd call. Uses exponential growth
        capped at max_delay_s, with ±jitter randomization.

        Formula: base = initial_delay_s * (backoff_multiplier ** (attempt-1))
                 capped at max_delay_s
                 jitter offset: uniform(-jitter, +jitter) * base
        """
        if attempt < 1:
            attempt = 1
        base = self.initial_delay_s * (self.backoff_multiplier ** (attempt - 1))
        if base > self.max_delay_s:
            base = self.max_delay_s
        if self.jitter > 0:
            offset = random.uniform(-self.jitter, self.jitter) * base
            base = base + offset
        # Never return negative delay even with extreme jitter.
        return max(0.0, base)


_DEFAULT_POLICY = RetryPolicy()


def retry_call(
    fn: Callable[..., Any],
    *args: Any,
    policy: Optional[RetryPolicy] = None,
    **kwargs: Any,
) -> Any:
    """Sync retry wrapper. Calls fn(*args, **kwargs) up to max_attempts."""
    pol = policy if policy is not None else _DEFAULT_POLICY
    last_exc: Optional[BaseException] = None
    for attempt in range(1, pol.max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — controlled rethrow
            last_exc = exc
            # Non-retriable: fail fast.
            if isinstance(exc, pol.non_retriable_exceptions):
                raise
            # Out of attempts or not in retriable list: re-raise.
            if not pol.should_retry(exc, attempt):
                raise
            time.sleep(pol.delay_for_attempt(attempt))
    # Defensive: should never get here, the loop always raises or returns.
    assert last_exc is not None
    raise last_exc


async def retry_call_async(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    policy: Optional[RetryPolicy] = None,
    **kwargs: Any,
) -> Any:
    """Async retry wrapper using asyncio.sleep for delays."""
    pol = policy if policy is not None else _DEFAULT_POLICY
    last_exc: Optional[BaseException] = None
    for attempt in range(1, pol.max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — controlled rethrow
            last_exc = exc
            if isinstance(exc, pol.non_retriable_exceptions):
                raise
            if not pol.should_retry(exc, attempt):
                raise
            await asyncio.sleep(pol.delay_for_attempt(attempt))
    assert last_exc is not None
    raise last_exc
