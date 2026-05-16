"""Tests for ImprovementQueue -- self-improvement queue management.

25 tests covering submit, get_next, start, complete, reject, list_improvements,
get_stats, thread safety, singleton, and EventBus integration.
"""

import json
import threading

import pytest

from sylion.aeis.improvement_queue import (
    ImprovementQueue,
    get_improvement_queue,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh in-memory EventBus capturing events."""
    eb = EventBus()
    eb._captured: list[SylionEvent] = []
    eb.subscribe("*", lambda e: eb._captured.append(e))
    return eb


@pytest.fixture
def q(bus):
    """Fresh in-memory ImprovementQueue with EventBus."""
    return ImprovementQueue(event_bus=bus)


@pytest.fixture
def q_no_bus():
    """Fresh in-memory ImprovementQueue without EventBus."""
    return ImprovementQueue()


# ===================================================================
# Initialization
# ===================================================================

class TestInit:
    def test_default_memory_db(self, q_no_bus):
        assert q_no_bus._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db = tmp_path / "iq.db"
        iq = ImprovementQueue(db_path=str(db))
        assert iq._db_path == str(db)

    def test_tables_created(self, q_no_bus):
        tables = q_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "improvements" in names

    def test_indexes_created(self, q_no_bus):
        indexes = q_no_bus._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        names = {r["name"] for r in indexes}
        assert "idx_imp_status" in names
        assert "idx_imp_category" in names
        assert "idx_imp_priority" in names

    def test_has_lock(self, q_no_bus):
        assert isinstance(q_no_bus._lock, type(threading.Lock()))

    def test_wal_mode_for_file_db(self, tmp_path):
        db = tmp_path / "wal_test.db"
        iq = ImprovementQueue(db_path=str(db))
        mode = iq._conn.execute("PRAGMA journal_mode").fetchone()["journal_mode"]
        assert mode == "wal"


# ===================================================================
# Submit
# ===================================================================

class TestSubmit:
    def test_submit_returns_basic_fields(self, q):
        result = q.submit("Fix latency", description="Reduce p99")
        assert result["improvement_id"]
        assert result["title"] == "Fix latency"
        assert result["status"] == "queued"

    def test_submit_stores_in_db(self, q):
        r = q.submit("Fix latency", category="performance", priority=5)
        row = q._conn.execute(
            "SELECT * FROM improvements WHERE improvement_id = ?",
            (r["improvement_id"],),
        ).fetchone()
        assert row is not None
        assert row["title"] == "Fix latency"
        assert row["category"] == "performance"
        assert row["priority"] == 5
        assert row["status"] == "queued"

    def test_submit_with_evidence(self, q):
        r = q.submit("Fix X", evidence={"metric": "p99", "value": 500})
        row = q._conn.execute(
            "SELECT evidence FROM improvements WHERE improvement_id = ?",
            (r["improvement_id"],),
        ).fetchone()
        ev = json.loads(row["evidence"])
        assert ev["metric"] == "p99"
        assert ev["value"] == 500

    def test_submit_default_evidence_empty(self, q):
        r = q.submit("Fix Y")
        row = q._conn.execute(
            "SELECT evidence FROM improvements WHERE improvement_id = ?",
            (r["improvement_id"],),
        ).fetchone()
        assert json.loads(row["evidence"]) == {}

    def test_submit_emits_event(self, q, bus):
        q.submit("Fix latency", priority=3)
        events = [e for e in bus._captured
                  if e.topic == "aeis.improvement_queue.submitted"]
        assert len(events) == 1
        assert events[0].payload["title"] == "Fix latency"
        assert events[0].payload["priority"] == 3

    def test_submit_default_category(self, q):
        r = q.submit("T")
        row = q._conn.execute(
            "SELECT category FROM improvements WHERE improvement_id = ?",
            (r["improvement_id"],),
        ).fetchone()
        assert row["category"] == "performance"


# ===================================================================
# Get next
# ===================================================================

class TestGetNext:
    def test_empty_queue_returns_none(self, q):
        assert q.get_next() is None

    def test_returns_highest_priority(self, q):
        q.submit("Low", priority=1)
        r_high = q.submit("High", priority=10)
        result = q.get_next()
        assert result is not None
        assert result["improvement_id"] == r_high["improvement_id"]

    def test_tie_breaks_by_created_at(self, q):
        r1 = q.submit("First", priority=5)
        r2 = q.submit("Second", priority=5)
        result = q.get_next()
        assert result["improvement_id"] == r1["improvement_id"]

    def test_skips_non_queued(self, q):
        r = q.submit("Item", priority=5)
        q.start(r["improvement_id"])
        assert q.get_next() is None

    def test_get_next_parses_evidence_json(self, q):
        q.submit("Item", evidence={"k": "v"})
        result = q.get_next()
        assert isinstance(result["evidence"], dict)
        assert result["evidence"]["k"] == "v"


# ===================================================================
# Lifecycle transitions
# ===================================================================

class TestLifecycle:
    def test_start_updates_status(self, q):
        r = q.submit("Item")
        result = q.start(r["improvement_id"])
        assert result["status"] == "in_progress"
        row = q._conn.execute(
            "SELECT status, started_at FROM improvements WHERE improvement_id = ?",
            (r["improvement_id"],),
        ).fetchone()
        assert row["status"] == "in_progress"
        assert row["started_at"] > 0

    def test_start_emits_event(self, q, bus):
        r = q.submit("Item")
        q.start(r["improvement_id"])
        events = [e for e in bus._captured
                  if e.topic == "aeis.improvement_queue.started"]
        assert len(events) == 1
        assert events[0].payload["improvement_id"] == r["improvement_id"]

    def test_complete_updates_status(self, q):
        r = q.submit("Item")
        result = q.complete(r["improvement_id"])
        assert result["status"] == "completed"
        row = q._conn.execute(
            "SELECT status, completed_at FROM improvements WHERE improvement_id = ?",
            (r["improvement_id"],),
        ).fetchone()
        assert row["status"] == "completed"
        assert row["completed_at"] > 0

    def test_complete_emits_event(self, q, bus):
        r = q.submit("Item")
        q.complete(r["improvement_id"], result="Done")
        events = [e for e in bus._captured
                  if e.topic == "aeis.improvement_queue.completed"]
        assert len(events) == 1
        assert events[0].payload["result"] == "Done"

    def test_reject_updates_status(self, q):
        r = q.submit("Item")
        result = q.reject(r["improvement_id"], reason="Duplicate")
        assert result["status"] == "rejected"
        row = q._conn.execute(
            "SELECT status FROM improvements WHERE improvement_id = ?",
            (r["improvement_id"],),
        ).fetchone()
        assert row["status"] == "rejected"

    def test_reject_emits_event(self, q, bus):
        r = q.submit("Item")
        q.reject(r["improvement_id"], reason="Bad")
        events = [e for e in bus._captured
                  if e.topic == "aeis.improvement_queue.rejected"]
        assert len(events) == 1
        assert events[0].payload["reason"] == "Bad"


# ===================================================================
# list_improvements
# ===================================================================

class TestListImprovements:
    def test_empty_list(self, q):
        assert q.list_improvements() == []

    def test_returns_all_without_filter(self, q):
        q.submit("A")
        q.submit("B")
        assert len(q.list_improvements()) == 2

    def test_filter_by_status(self, q):
        r = q.submit("A")
        q.submit("B")
        q.start(r["improvement_id"])
        queued = q.list_improvements(status="queued")
        assert len(queued) == 1
        assert queued[0]["title"] == "B"

    def test_filter_by_category(self, q):
        q.submit("A", category="security")
        q.submit("B", category="performance")
        sec = q.list_improvements(category="security")
        assert len(sec) == 1
        assert sec[0]["title"] == "A"

    def test_limit_works(self, q):
        for i in range(10):
            q.submit(f"Item {i}")
        results = q.list_improvements(limit=3)
        assert len(results) == 3

    def test_evidence_parsed_as_dict(self, q):
        q.submit("Item", evidence={"k": "v"})
        results = q.list_improvements()
        assert isinstance(results[0]["evidence"], dict)


# ===================================================================
# get_stats
# ===================================================================

class TestGetStats:
    def test_empty_stats(self, q):
        stats = q.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}
        assert stats["by_category"] == {}

    def test_stats_counts(self, q):
        r1 = q.submit("A", category="security")
        r2 = q.submit("B", category="performance")
        q.start(r1["improvement_id"])

        stats = q.get_stats()
        assert stats["total"] == 2
        assert stats["by_status"]["queued"] == 1
        assert stats["by_status"]["in_progress"] == 1
        assert stats["by_category"]["security"] == 1
        assert stats["by_category"]["performance"] == 1

    def test_stats_after_complete_and_reject(self, q):
        r1 = q.submit("A")
        r2 = q.submit("B")
        r3 = q.submit("C")
        q.complete(r1["improvement_id"])
        q.reject(r2["improvement_id"])
        stats = q.get_stats()
        assert stats["by_status"]["completed"] == 1
        assert stats["by_status"]["rejected"] == 1
        assert stats["by_status"]["queued"] == 1


# ===================================================================
# Thread safety
# ===================================================================

class TestThreadSafety:
    def test_concurrent_submits(self, q):
        errors = []

        def submit(n):
            try:
                q.submit(f"Item {n}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        rows = q._conn.execute("SELECT COUNT(*) as c FROM improvements").fetchone()
        assert rows["c"] == 20

    def test_concurrent_start_and_complete(self, q):
        ids = [q.submit(f"Item {i}")["improvement_id"] for i in range(10)]
        errors = []

        def transition(iid):
            try:
                q.start(iid)
                q.complete(iid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=transition, args=(iid,)) for iid in ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        rows = q._conn.execute(
            "SELECT COUNT(*) as c FROM improvements WHERE status='completed'"
        ).fetchone()
        assert rows["c"] == 10


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_improvement_queue_returns_instance(self):
        import sylion.aeis.improvement_queue as mod
        mod._queue = None
        iq = get_improvement_queue()
        assert isinstance(iq, ImprovementQueue)
        mod._queue = None

    def test_singleton_returns_same_instance(self):
        import sylion.aeis.improvement_queue as mod
        mod._queue = None
        iq1 = get_improvement_queue()
        iq2 = get_improvement_queue()
        assert iq1 is iq2
        mod._queue = None


# ===================================================================
# EventBus integration
# ===================================================================

class TestEventBusIntegration:
    def test_no_bus_no_error(self, q_no_bus):
        r = q_no_bus.submit("Item")
        q_no_bus.start(r["improvement_id"])
        q_no_bus.complete(r["improvement_id"])
        # No crash = success

    def test_event_source_module(self, q, bus):
        q.submit("Item")
        events = [e for e in bus._captured
                  if e.topic == "aeis.improvement_queue.submitted"]
        assert events[0].source_module == "aeis.improvement_queue"

    def test_multiple_events_different_topics(self, q, bus):
        r = q.submit("Item")
        q.start(r["improvement_id"])
        q.complete(r["improvement_id"])
        topics = {e.topic for e in bus._captured}
        assert "aeis.improvement_queue.submitted" in topics
        assert "aeis.improvement_queue.started" in topics
        assert "aeis.improvement_queue.completed" in topics
