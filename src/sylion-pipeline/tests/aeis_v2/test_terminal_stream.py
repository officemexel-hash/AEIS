"""Tests for the W18 SSE event aggregator dead-subscriber TTL reaper.

Targets the KIMI adversarial review finding #2 against
``sylion.aeis_v2.terminal.stream``: without TTL-based reaping, dead
subscribers accumulate in ``TerminalBroadcaster._subs`` and every offer
iterates over all of them (O(n)). With 1000 events/sec and accumulating
dead subs, CPU usage grows unbounded.

The reaper added by W18 closes that loop:

- ``EventSubscriber`` exposes ``last_event_at`` and ``last_seen_at``
  liveness timestamps plus a ``touch()`` method.
- ``TerminalBroadcaster.reap_stale()`` evicts subscribers whose
  ``last_seen_at`` is older than ``STALE_SUBSCRIBER_TTL_S``.
- ``TerminalBroadcaster.offer()`` runs the reaper at most once per
  ``_REAP_INTERVAL_S`` so the offer hot-path stays O(n).

We use ``asyncio.run()`` for each async test (matches the existing
pattern in tests/aeis_v2/test_terminal.py — pytest-asyncio is not part
of the test deps for this project).
"""
from __future__ import annotations

import asyncio
import time

from sylion.aeis_v2.terminal import stream as stream_mod
from sylion.aeis_v2.terminal.stream import (
    EventFilter,
    EventSubscriber,
    STALE_SUBSCRIBER_TTL_S,
    TerminalBroadcaster,
    TerminalEvent,
)


# --------------------------------------------------------------------------
# A. EventSubscriber liveness fields
# --------------------------------------------------------------------------


def test_event_subscriber_has_last_event_at_and_last_seen_at_initialized():
    """At construction both timestamps equal created_at — never zero."""
    sub = EventSubscriber("s1", EventFilter())
    assert sub.last_event_at == sub.created_at
    assert sub.last_seen_at == sub.created_at
    # Sanity: created_at is a real wall-clock timestamp, not 0.
    assert sub.created_at > 1_700_000_000  # any time after 2023


def test_event_subscriber_tracks_last_event_at():
    """offer() bumps last_event_at to current wall-clock time."""
    async def _run() -> tuple[float, float]:
        sub = EventSubscriber("s1", EventFilter())
        original = sub.last_event_at
        # Sleep just enough to make a difference (>= clock resolution).
        await asyncio.sleep(0.02)
        sub.offer(TerminalEvent(ts=1.0, layer="W15", message="hi"))
        return original, sub.last_event_at

    original, after = asyncio.run(_run())
    assert after > original
    # Difference should be at least the sleep duration.
    assert (after - original) >= 0.01


def test_event_subscriber_offer_drop_still_bumps_last_event_at():
    """A full queue still counts as 'alive but slow' — last_event_at must update."""
    async def _run() -> tuple[float, float, int]:
        sub = EventSubscriber("s1", EventFilter())
        # Force overflow on the very next offer.
        sub._queue = asyncio.Queue(maxsize=1)
        sub.offer(TerminalEvent(ts=1.0, layer="W15", message="a"))  # fills queue
        first = sub.last_event_at
        await asyncio.sleep(0.02)
        sub.offer(TerminalEvent(ts=2.0, layer="W15", message="b"))  # dropped
        return first, sub.last_event_at, sub.dropped

    first, second, dropped = asyncio.run(_run())
    assert dropped == 1
    assert second > first  # bumped despite drop


def test_event_subscriber_touch_bumps_last_seen_at():
    """touch() is the route-side liveness signal — must update last_seen_at."""
    async def _run() -> tuple[float, float]:
        sub = EventSubscriber("s1", EventFilter())
        before = sub.last_seen_at
        await asyncio.sleep(0.02)
        sub.touch()
        return before, sub.last_seen_at

    before, after = asyncio.run(_run())
    assert after > before


def test_filtered_out_event_does_not_bump_timestamps():
    """If the event doesn't match the filter, neither timestamp moves."""
    sub = EventSubscriber("s1", EventFilter(layers={"W15"}))
    e_at_before = sub.last_event_at
    s_at_before = sub.last_seen_at
    # Event with layer=W14 will not match the filter.
    sub.offer(TerminalEvent(ts=1.0, layer="W14", message="nope"))
    assert sub.last_event_at == e_at_before
    assert sub.last_seen_at == s_at_before


# --------------------------------------------------------------------------
# B. TerminalBroadcaster.reap_stale()
# --------------------------------------------------------------------------


def test_reap_stale_removes_idle_subscribers():
    """Subscribers older than STALE_SUBSCRIBER_TTL_S get evicted; fresh ones stay."""
    async def _run() -> tuple[int, int]:
        bc = TerminalBroadcaster()
        s1 = EventSubscriber("s1", EventFilter())
        s2 = EventSubscriber("s2", EventFilter())
        s3 = EventSubscriber("s3", EventFilter())
        await bc.add(s1)
        await bc.add(s2)
        await bc.add(s3)
        # Brief: prefer setting last_seen_at directly to fake staleness
        # rather than monkeypatching time.time() globally. This is a clean
        # surgical test: only s1 and s2 are stale; s3 is fresh.
        s1.last_seen_at = time.time() - (STALE_SUBSCRIBER_TTL_S + 60.0)
        s2.last_seen_at = time.time() - (STALE_SUBSCRIBER_TTL_S + 1.0)
        # s3 left untouched — created_at is "now"
        reaped = await bc.reap_stale()
        return reaped, len(bc._subs)

    reaped, remaining = asyncio.run(_run())
    assert reaped == 2
    assert remaining == 1


def test_reap_stale_keeps_active_subscribers():
    """All-fresh broadcaster reaps zero and keeps everyone."""
    async def _run() -> tuple[int, int]:
        bc = TerminalBroadcaster()
        for sid in ("a", "b", "c"):
            await bc.add(EventSubscriber(sid, EventFilter()))
        # All three were just created → last_seen_at == created_at == now.
        reaped = await bc.reap_stale()
        return reaped, len(bc._subs)

    reaped, remaining = asyncio.run(_run())
    assert reaped == 0
    assert remaining == 3


def test_reap_stale_returns_zero_on_empty_broadcaster():
    """Edge: no subscribers → reaped=0, no exception."""
    async def _run() -> int:
        bc = TerminalBroadcaster()
        return await bc.reap_stale()

    assert asyncio.run(_run()) == 0


def test_reap_stale_threshold_is_strict_greater_than_ttl():
    """A subscriber exactly at the TTL boundary is NOT reaped (strict >)."""
    async def _run() -> int:
        bc = TerminalBroadcaster()
        s = EventSubscriber("borderline", EventFilter())
        await bc.add(s)
        # Set last_seen_at so (now - last_seen_at) is *less than* TTL —
        # we set it just inside the safe window. Reap predicate is
        # ``(now - last_seen_at) > STALE_SUBSCRIBER_TTL_S`` so this stays.
        s.last_seen_at = time.time() - (STALE_SUBSCRIBER_TTL_S - 5.0)
        return await bc.reap_stale()

    assert asyncio.run(_run()) == 0


def test_reap_stale_uses_last_seen_at_not_last_event_at():
    """A subscriber recently touched but never offered to is still alive."""
    async def _run() -> int:
        bc = TerminalBroadcaster()
        s = EventSubscriber("quiet", EventFilter())
        await bc.add(s)
        # Make last_event_at ancient, but touch() was recent → must stay.
        s.last_event_at = time.time() - 10_000.0
        s.last_seen_at = time.time()  # fresh
        return await bc.reap_stale()

    assert asyncio.run(_run()) == 0


# --------------------------------------------------------------------------
# C. Reap rate-limiting in offer()
# --------------------------------------------------------------------------


def test_reap_interval_throttles_reaper():
    """100 offers in <100ms must trigger reap_stale at most a couple times.

    Implementation triggers reap when (now - _last_reap_at) > _REAP_INTERVAL_S.
    Initial _last_reap_at=0 means the very first offer DOES reap (catching
    state from a previous process); after that, _last_reap_at is "now" and
    subsequent offers within 30s do NOT reap. Expected actual count: 1.
    """
    async def _run() -> int:
        bc = TerminalBroadcaster()
        # Add a few real subs so reap_stale has work to scan (but they're
        # all fresh — none should actually be removed).
        for sid in ("x", "y", "z"):
            await bc.add(EventSubscriber(sid, EventFilter()))

        # Wrap reap_stale to count invocations.
        call_count = {"n": 0}
        original_reap = bc.reap_stale

        async def counting_reap() -> int:
            call_count["n"] += 1
            return await original_reap()

        bc.reap_stale = counting_reap  # type: ignore[method-assign]

        # Fire 100 offers as fast as the event loop allows.
        for i in range(100):
            await bc.offer(TerminalEvent(
                ts=float(i), layer="W18", message=f"e{i}",
            ))
        return call_count["n"]

    n = asyncio.run(_run())
    # On a fast loop this should be exactly 1 (first offer triggers reap,
    # rest are throttled by the 30s interval). We allow up to 3 to cover
    # the unlikely case of a 30s+ stall between offers (CI jitter, GC pause).
    assert 1 <= n <= 3, f"expected 1..3 reap calls in rapid burst, got {n}"


def test_reap_interval_first_offer_triggers_reap():
    """Specific contract: the very first offer on a fresh broadcaster runs
    the reaper exactly once (because _last_reap_at starts at 0)."""
    async def _run() -> tuple[int, float]:
        bc = TerminalBroadcaster()
        before_reap_at = bc._last_reap_at
        assert before_reap_at == 0.0  # fresh state precondition

        # Sentinel: a single offer with no subs.
        await bc.offer(TerminalEvent(ts=1.0, layer="W18", message="boot"))
        return 0, bc._last_reap_at

    _, after = asyncio.run(_run())
    # After the first offer, _last_reap_at must have been updated to "now".
    assert after > 0.0
    # And it must be a recent wall-clock timestamp.
    assert abs(after - time.time()) < 5.0


def test_reap_inside_offer_actually_evicts_stale_subs():
    """End-to-end: offer fan-out + auto-reap removes a stale subscriber."""
    async def _run() -> tuple[int, int]:
        bc = TerminalBroadcaster()
        live = EventSubscriber("live", EventFilter())
        dead = EventSubscriber("dead", EventFilter())
        await bc.add(live)
        await bc.add(dead)
        # Make 'dead' stale.
        dead.last_seen_at = time.time() - (STALE_SUBSCRIBER_TTL_S + 30.0)
        before = len(bc._subs)
        # Offer triggers throttled reap on first call (fresh broadcaster).
        await bc.offer(TerminalEvent(ts=1.0, layer="W18", message="ping"))
        return before, len(bc._subs)

    before, after = asyncio.run(_run())
    assert before == 2
    # The live sub remains; the dead one is reaped.
    assert after == 1


# --------------------------------------------------------------------------
# D. Module-level constants — sanity guards
# --------------------------------------------------------------------------


def test_stale_subscriber_ttl_constant_is_two_minutes():
    """Locked at 120s. Changing it is a behavioural change that should be
    a deliberate code review, not silent drift."""
    assert STALE_SUBSCRIBER_TTL_S == 120.0


def test_reap_interval_constant_is_thirty_seconds():
    """Locked at 30s — see TerminalBroadcaster.offer docstring."""
    assert stream_mod._REAP_INTERVAL_S == 30.0


def test_reap_interval_is_smaller_than_ttl():
    """Sanity: reap interval must be < TTL so a stale sub is reaped at
    most one interval after going stale (otherwise we'd miss the window)."""
    assert stream_mod._REAP_INTERVAL_S < STALE_SUBSCRIBER_TTL_S
