"""
Tests for sylion.security.audit_query -- AuditQuery

~35 tests covering event indexing, querying with filters,
get_event, actor history, resource timeline, statistics,
purge, tag filtering, EventBus emissions, concurrency,
and singleton lifecycle.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.security.audit_query import (
    AuditQuery,
    get_audit_query,
    reset_audit_query,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_audit_query()
    yield
    reset_audit_query()


@pytest.fixture
def bus():
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def aq(bus):
    return AuditQuery(event_bus=bus)


@pytest.fixture
def plain_aq():
    return AuditQuery()


def _seed_events(aq: AuditQuery, n: int = 5, event_type: str = "login",
                 actor: str = "alice", resource: str = "/auth",
                 tags: dict | None = None):
    """Seed n events into the query index."""
    base_ts = time.time() - n * 10
    for i in range(n):
        aq.index_event(
            event_id=f"evt-{i:04d}",
            event_type=event_type,
            actor=actor,
            resource=resource,
            timestamp=base_ts + i * 10,
            tags_json=tags or {"env": "test"},
        )


# ===========================================================================
# 1. Index events
# ===========================================================================

class TestIndexEvent:
    def test_returns_event_id(self, aq):
        r = aq.index_event("e1", "login", "alice", "/auth", time.time())
        assert r["event_id"] == "e1"

    def test_returns_event_type(self, aq):
        r = aq.index_event("e1", "login", "a", "/r", time.time())
        assert r["event_type"] == "login"

    def test_returns_actor(self, aq):
        r = aq.index_event("e1", "t", "bob", "/r", time.time())
        assert r["actor"] == "bob"

    def test_returns_resource(self, aq):
        r = aq.index_event("e1", "t", "a", "/data/file.txt", time.time())
        assert r["resource"] == "/data/file.txt"

    def test_returns_tags(self, aq):
        tags = {"env": "prod", "region": "us"}
        r = aq.index_event("e1", "t", "a", "/r", time.time(), tags_json=tags)
        assert r["tags_json"] == tags

    def test_default_tags_empty(self, aq):
        r = aq.index_event("e1", "t", "a", "/r", time.time())
        assert r["tags_json"] == {}

    def test_replace_existing_event(self, aq):
        aq.index_event("e1", "type_a", "a", "/r", time.time())
        aq.index_event("e1", "type_b", "b", "/r2", time.time())
        evt = aq.get_event("e1")
        assert evt["event_type"] == "type_b"
        assert evt["actor"] == "b"

    def test_emits_event_indexed(self, aq, bus):
        aq.index_event("e1", "login", "a", "/r", time.time())
        topics = [e.topic for e in bus._captured]
        assert "event_indexed" in topics


# ===========================================================================
# 2. Query events
# ===========================================================================

class TestQueryEvents:
    def test_query_empty(self, aq):
        assert aq.query_events() == []

    def test_query_returns_all(self, aq):
        _seed_events(aq, 5)
        assert len(aq.query_events()) == 5

    def test_query_by_event_type(self, aq):
        _seed_events(aq, 3, event_type="login")
        _seed_events(aq, 2, event_type="logout", actor="bob", resource="/r")
        # Reset event IDs to avoid collision
        for i in range(2):
            aq.index_event(f"extra-{i}", "logout", "bob", "/r",
                           time.time())
        result = aq.query_events({"event_type": "login"})
        assert all(r["event_type"] == "login" for r in result)

    def test_query_by_actor(self, aq):
        aq.index_event("e1", "t", "alice", "/r", time.time())
        aq.index_event("e2", "t", "bob", "/r", time.time())
        result = aq.query_events({"actor": "alice"})
        assert len(result) == 1
        assert result[0]["actor"] == "alice"

    def test_query_by_resource(self, aq):
        aq.index_event("e1", "t", "a", "/file1", time.time())
        aq.index_event("e2", "t", "a", "/file2", time.time())
        result = aq.query_events({"resource": "/file1"})
        assert len(result) == 1

    def test_query_by_since(self, aq):
        old_ts = time.time() - 1000
        new_ts = time.time()
        aq.index_event("e1", "t", "a", "/r", old_ts)
        aq.index_event("e2", "t", "a", "/r", new_ts)
        result = aq.query_events({"since": new_ts - 1})
        assert len(result) == 1
        assert result[0]["event_id"] == "e2"

    def test_query_by_until(self, aq):
        old_ts = time.time() - 1000
        new_ts = time.time()
        aq.index_event("e1", "t", "a", "/r", old_ts)
        aq.index_event("e2", "t", "a", "/r", new_ts)
        result = aq.query_events({"until": old_ts + 1})
        assert len(result) == 1
        assert result[0]["event_id"] == "e1"

    def test_query_limit(self, aq):
        aq.index_event("e1", "t", "a", "/r", time.time())
        aq.index_event("e2", "t", "a", "/r", time.time())
        aq.index_event("e3", "t", "a", "/r", time.time())
        assert len(aq.query_events({"limit": 2})) == 2

    def test_query_tag_key_filter(self, aq):
        aq.index_event("e1", "t", "a", "/r", time.time(),
                        tags_json={"env": "prod"})
        aq.index_event("e2", "t", "a", "/r", time.time(),
                        tags_json={"region": "eu"})
        result = aq.query_events({"tag_key": "env"})
        assert len(result) == 1

    def test_query_tag_key_value_filter(self, aq):
        aq.index_event("e1", "t", "a", "/r", time.time(),
                        tags_json={"env": "prod"})
        aq.index_event("e2", "t", "a", "/r", time.time(),
                        tags_json={"env": "dev"})
        result = aq.query_events({"tag_key": "env", "tag_value": "prod"})
        assert len(result) == 1
        assert result[0]["tags_json"]["env"] == "prod"

    def test_emits_query_executed(self, aq, bus):
        aq.index_event("e1", "t", "a", "/r", time.time())
        aq.query_events({"event_type": "t"})
        topics = [e.topic for e in bus._captured]
        assert "query_executed" in topics


# ===========================================================================
# 3. Get event
# ===========================================================================

class TestGetEvent:
    def test_get_existing(self, aq):
        aq.index_event("e1", "login", "alice", "/auth", time.time())
        evt = aq.get_event("e1")
        assert evt is not None
        assert evt["event_id"] == "e1"
        assert evt["event_type"] == "login"

    def test_get_nonexistent(self, aq):
        assert aq.get_event("nonexistent") is None

    def test_get_parses_tags_json(self, aq):
        tags = {"env": "prod"}
        aq.index_event("e1", "t", "a", "/r", time.time(), tags_json=tags)
        evt = aq.get_event("e1")
        assert evt["tags_json"] == tags


# ===========================================================================
# 4. Actor history
# ===========================================================================

class TestGetActorHistory:
    def test_returns_actor_events(self, aq):
        aq.index_event("e1", "login", "alice", "/r", time.time())
        aq.index_event("e2", "logout", "bob", "/r", time.time())
        aq.index_event("e3", "read", "alice", "/r", time.time())
        result = aq.get_actor_history("alice")
        assert len(result) == 2

    def test_empty_for_unknown_actor(self, aq):
        assert aq.get_actor_history("nobody") == []

    def test_respects_limit(self, aq):
        for i in range(10):
            aq.index_event(f"e{i}", "t", "alice", "/r", time.time())
        result = aq.get_actor_history("alice", limit=3)
        assert len(result) == 3


# ===========================================================================
# 5. Resource timeline
# ===========================================================================

class TestGetResourceTimeline:
    def test_returns_resource_events(self, aq):
        aq.index_event("e1", "read", "a", "/file.txt", time.time())
        aq.index_event("e2", "read", "a", "/other.txt", time.time())
        aq.index_event("e3", "write", "b", "/file.txt", time.time())
        result = aq.get_resource_timeline("/file.txt")
        assert len(result) == 2

    def test_empty_for_unknown_resource(self, aq):
        assert aq.get_resource_timeline("/nonexistent") == []

    def test_respects_limit(self, aq):
        for i in range(10):
            aq.index_event(f"e{i}", "t", "a", "/file.txt", time.time())
        result = aq.get_resource_timeline("/file.txt", limit=3)
        assert len(result) == 3


# ===========================================================================
# 6. Query stats
# ===========================================================================

class TestGetQueryStats:
    def test_empty_stats(self, plain_aq):
        stats = plain_aq.get_query_stats()
        assert stats["total_events"] == 0
        assert stats["events_by_type"] == {}
        assert stats["top_actors"] == {}
        assert stats["total_queries"] == 0

    def test_counts_events(self, aq):
        aq.index_event("e1", "login", "a", "/r", time.time())
        aq.index_event("e2", "logout", "a", "/r", time.time())
        stats = aq.get_query_stats()
        assert stats["total_events"] == 2

    def test_events_by_type(self, aq):
        aq.index_event("e1", "login", "a", "/r", time.time())
        aq.index_event("e2", "login", "b", "/r", time.time())
        aq.index_event("e3", "logout", "a", "/r", time.time())
        stats = aq.get_query_stats()
        assert stats["events_by_type"]["login"] == 2
        assert stats["events_by_type"]["logout"] == 1

    def test_top_actors(self, aq):
        aq.index_event("e1", "t", "alice", "/r", time.time())
        aq.index_event("e2", "t", "alice", "/r", time.time())
        aq.index_event("e3", "t", "bob", "/r", time.time())
        stats = aq.get_query_stats()
        assert stats["top_actors"]["alice"] == 2

    def test_tracks_query_count(self, aq):
        aq.index_event("e1", "t", "a", "/r", time.time())
        aq.query_events()
        aq.query_events({"event_type": "t"})
        stats = aq.get_query_stats()
        assert stats["total_queries"] == 2


# ===========================================================================
# 7. Purge index
# ===========================================================================

class TestPurgeIndex:
    def test_purge_removes_old_entries(self, plain_aq):
        old_ts = time.time() - 2000
        new_ts = time.time()
        plain_aq.index_event("e1", "t", "a", "/r", old_ts)
        plain_aq.index_event("e2", "t", "a", "/r", new_ts)
        purged = plain_aq.purge_index(1000)
        assert purged == 1
        assert plain_aq.get_event("e1") is None
        assert plain_aq.get_event("e2") is not None

    def test_purge_no_old_entries(self, plain_aq):
        plain_aq.index_event("e1", "t", "a", "/r", time.time())
        purged = plain_aq.purge_index(3600)
        assert purged == 0

    def test_purge_all_if_very_old(self, plain_aq):
        plain_aq.index_event("e1", "t", "a", "/r", time.time() - 10000)
        plain_aq.index_event("e2", "t", "a", "/r", time.time() - 10000)
        purged = plain_aq.purge_index(1)
        assert purged == 2

    def test_purge_returns_count(self, plain_aq):
        for i in range(5):
            plain_aq.index_event(f"e{i}", "t", "a", "/r",
                                 time.time() - 10000)
        assert plain_aq.purge_index(1) == 5


# ===========================================================================
# 8. Concurrency
# ===========================================================================

class TestConcurrency:
    def test_concurrent_index_and_query(self, plain_aq):
        errors = []

        def writer(i):
            try:
                for j in range(10):
                    plain_aq.index_event(
                        f"w{i}-{j}", "t", "a", "/r", time.time())
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                plain_aq.query_events()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,))
                   for i in range(5)]
        threads += [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ===========================================================================
# 9. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        inst = get_audit_query()
        assert isinstance(inst, AuditQuery)

    def test_get_is_idempotent(self):
        a = get_audit_query()
        b = get_audit_query()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_audit_query()
        reset_audit_query()
        b = get_audit_query()
        assert a is not b

    def test_double_reset_safe(self):
        reset_audit_query()
        reset_audit_query()
        inst = get_audit_query()
        assert isinstance(inst, AuditQuery)
