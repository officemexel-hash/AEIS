"""Tests for the W18 Terminal SessionStore memory-hygiene reaper.

Targets the KIMI adversarial review of ``sylion.aeis_v2.terminal.sessions``,
mirroring the dead-subscriber TTL reaper that landed for ``stream.py`` in
commit ``1f740888``. Three classes of leak the reaper closes:

1. **Bounded active session count** — operator (or buggy frontend) cannot
   create more than ``MAX_ACTIVE_SESSIONS`` active rows; once at the cap,
   the oldest active session is auto-archived to make room.
2. **Idle auto-archive** — any active session whose ``updated_at`` is
   older than ``SESSION_IDLE_TIMEOUT_S`` is flipped to ``archived``.
3. **Archive hard-delete** — archived sessions older than
   ``SESSION_HARD_DELETE_AFTER_ARCHIVE_S`` are dropped from the store
   entirely, capping steady-state memory.

All tests construct a fresh :class:`SessionStore` (NOT the singleton) so
they are isolated from each other and from the rest of the suite.
"""
from __future__ import annotations

import time

import pytest

from sylion.aeis_v2.terminal import sessions as sessions_mod
from sylion.aeis_v2.terminal.sessions import (
    MAX_ACTIVE_SESSIONS,
    SESSION_HARD_DELETE_AFTER_ARCHIVE_S,
    SESSION_IDLE_TIMEOUT_S,
    SESSION_REAP_INTERVAL_S,
    SessionStore,
)


# --------------------------------------------------------------------------
# A. Bounded active session cap
# --------------------------------------------------------------------------


def test_session_store_caps_active_sessions():
    """Brief #2: at MAX_ACTIVE_SESSIONS active rows, the next create()
    auto-archives the oldest active session and admits the new one.
    Total active count stays at MAX_ACTIVE_SESSIONS."""
    store = SessionStore()
    # Fill exactly to the cap.
    first = store.create("first")
    for i in range(1, MAX_ACTIVE_SESSIONS):
        store.create(f"session-{i}")
    assert len(store.list_active()) == MAX_ACTIVE_SESSIONS

    # One more push triggers eviction of the oldest (the very first one).
    overflow = store.create("overflow")
    actives = store.list_active()
    assert len(actives) == MAX_ACTIVE_SESSIONS, "active count must stay at cap"
    # The 'first' session was the oldest by ``created_at`` and should be
    # archived now, not deleted.
    evicted = store.get(first.session_id)
    assert evicted is not None, "evicted session should still be in store, just archived"
    assert evicted.status == "archived"
    # The new one is in.
    assert store.get(overflow.session_id) is not None
    assert overflow.status == "active"


# --------------------------------------------------------------------------
# B. Idle auto-archive
# --------------------------------------------------------------------------


def test_session_store_reap_archives_idle():
    """Brief #3: sessions with updated_at older than SESSION_IDLE_TIMEOUT_S
    are archived; fresh ones stay active."""
    store = SessionStore()
    s1 = store.create("idle-a")
    s2 = store.create("idle-b")
    s3 = store.create("fresh-c")
    # Make s1, s2 stale by overriding updated_at directly (cleaner than
    # monkeypatching time.time globally — only affects these two rows).
    stale_ts = time.time() - (SESSION_IDLE_TIMEOUT_S + 400.0)
    s1.updated_at = stale_ts
    s2.updated_at = stale_ts
    # s3 is left fresh — created_at == updated_at == "now"
    archived, deleted = store.reap_idle()
    assert archived == 2
    assert deleted == 0
    assert s1.status == "archived"
    assert s2.status == "archived"
    assert s3.status == "active"


def test_session_store_active_session_not_reaped():
    """Brief #5: a brand-new session is not touched by reap_idle."""
    store = SessionStore()
    sess = store.create("just-born")
    archived, deleted = store.reap_idle()
    assert archived == 0
    assert deleted == 0
    assert sess.status == "active"
    # Still discoverable.
    assert store.get(sess.session_id) is sess


# --------------------------------------------------------------------------
# C. Reap throttling
# --------------------------------------------------------------------------


def test_session_store_reap_throttled():
    """Brief #3: a tight burst of create() calls invokes reap_idle at
    most a couple of times — not once per create — because the reaper
    is rate-limited by SESSION_REAP_INTERVAL_S.

    Implementation triggers reap when (now - _last_reap_at) >
    SESSION_REAP_INTERVAL_S. Initial _last_reap_at=0 means the very
    first create DOES reap; subsequent creates within 60s do NOT."""
    store = SessionStore()

    # Wrap reap_idle to count invocations.
    call_count = {"n": 0}
    original_reap = store.reap_idle

    def counting_reap() -> tuple[int, int]:
        call_count["n"] += 1
        return original_reap()

    store.reap_idle = counting_reap  # type: ignore[method-assign]

    # Fire 100 creates. Note the active-cap kicks in at MAX_ACTIVE_SESSIONS
    # but eviction is independent of the reaper count. We just measure
    # reap_idle invocation frequency.
    for i in range(100):
        store.create(f"burst-{i}")

    n = call_count["n"]
    # On a fast loop this should be exactly 1 (first create triggers
    # reap, rest are throttled by the 60s interval). Allow up to 3 to
    # cover CI jitter / GC pauses that might span the interval.
    assert 1 <= n <= 3, f"expected 1..3 reap invocations in tight burst, got {n}"


# --------------------------------------------------------------------------
# D. Hard-delete after archive period
# --------------------------------------------------------------------------


def test_session_store_reap_hard_deletes_old_archived():
    """Brief #4: archived sessions whose updated_at is older than
    SESSION_HARD_DELETE_AFTER_ARCHIVE_S are dropped from the store
    entirely."""
    store = SessionStore()
    sess = store.create("doomed")
    # Move it to archived state via close().
    assert store.close(sess.session_id, status="archived") is True
    assert sess.status == "archived"
    # Backdate updated_at to be older than the hard-delete cutoff.
    sess.updated_at = time.time() - (SESSION_HARD_DELETE_AFTER_ARCHIVE_S + 100.0)

    archived, deleted = store.reap_idle()
    assert archived == 0
    assert deleted == 1
    # The session is GONE from the store.
    assert store.get(sess.session_id) is None
    assert sess.session_id not in store._sessions


def test_session_store_recently_archived_not_hard_deleted():
    """Defense in depth: a freshly-archived session is NOT hard-deleted
    on the same sweep that archived it. The archive bumps updated_at to
    'now', so it gets the full SESSION_HARD_DELETE_AFTER_ARCHIVE_S grace."""
    store = SessionStore()
    sess = store.create("recently-archived")
    # Make it idle so pass 1 archives it.
    sess.updated_at = time.time() - (SESSION_IDLE_TIMEOUT_S + 50.0)

    archived, deleted = store.reap_idle()
    assert archived == 1
    assert deleted == 0
    # Still in the store, with status archived.
    assert store.get(sess.session_id) is sess
    assert sess.status == "archived"


# --------------------------------------------------------------------------
# E. Module-level constants — sanity guards
# --------------------------------------------------------------------------


def test_max_active_sessions_constant_is_100():
    """Phase 0 cap: 100 active sessions per process. G2 will lift to 10k
    once persistence is in place. Pinning the value so an accidental
    change is a deliberate review."""
    assert MAX_ACTIVE_SESSIONS == 100


def test_session_idle_timeout_is_one_hour():
    """1 hour idle threshold. Locked so silent drift triggers test
    review."""
    assert SESSION_IDLE_TIMEOUT_S == 3600.0


def test_session_hard_delete_cutoff_is_24h():
    """Archived sessions hard-deleted after 24h."""
    assert SESSION_HARD_DELETE_AFTER_ARCHIVE_S == 86400.0


def test_reap_interval_smaller_than_idle_timeout():
    """Sanity: reap interval must be << idle timeout, otherwise an idle
    session might wait nearly the timeout *plus* the interval before
    being archived."""
    assert SESSION_REAP_INTERVAL_S < SESSION_IDLE_TIMEOUT_S


def test_max_active_sessions_env_override(monkeypatch):
    """SYLION_MAX_ACTIVE_SESSIONS env var overrides the default at
    module import. We re-evaluate the helper to check the parsing,
    rather than reloading the module."""
    monkeypatch.setenv("SYLION_MAX_ACTIVE_SESSIONS", "42")
    assert sessions_mod._env_int("SYLION_MAX_ACTIVE_SESSIONS", 100) == 42
    monkeypatch.setenv("SYLION_MAX_ACTIVE_SESSIONS", "not-a-number")
    # Bad value falls back to the supplied default — does not raise.
    assert sessions_mod._env_int("SYLION_MAX_ACTIVE_SESSIONS", 100) == 100
