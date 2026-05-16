"""
Tests for SYLION Audit Trail Aggregator.

Covers:
  - record() with validation, hash computation
  - get_entry() retrieval
  - query() with all filter combinations
  - count_by_action() and count_by_actor()
  - verify_integrity() (valid and tampered entries)
  - get_stats()
  - EventBus integration
  - Singleton get/reset functions
  - Thread safety
  - Edge cases (empty tables, missing entries, boundary filters)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.security.audit_trail_aggregator import (
    VALID_OUTCOMES,
    VALID_SOURCES,
    AuditTrailAggregator,
    get_audit_trail_aggregator,
    reset_audit_trail_aggregator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def agg():
    """Fresh AuditTrailAggregator with :memory: SQLite."""
    return AuditTrailAggregator(db_path=":memory:")


@pytest.fixture
def agg_with_bus():
    """AuditTrailAggregator connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return AuditTrailAggregator(db_path=":memory:", event_bus=bus), bus


# ---------------------------------------------------------------------------
# Test: record()
# ---------------------------------------------------------------------------

class TestRecord:
    def test_record_returns_entry_dict(self, agg):
        result = agg.record(source="api", action="login", actor="alice")
        assert "entry_id" in result
        assert result["source"] == "api"
        assert result["action"] == "login"
        assert result["actor"] == "alice"

    def test_record_default_outcome_is_success(self, agg):
        result = agg.record(source="api", action="login")
        assert result["outcome"] == "success"

    def test_record_default_resource_empty(self, agg):
        result = agg.record(source="api", action="login")
        assert result["resource"] == ""

    def test_record_default_metadata_empty(self, agg):
        result = agg.record(source="api", action="login")
        assert result["metadata"] == {}

    def test_record_generates_entry_id(self, agg):
        result = agg.record(source="api", action="login")
        assert len(result["entry_id"]) == 32

    def test_record_sets_timestamp(self, agg):
        before = time.time()
        result = agg.record(source="api", action="login")
        after = time.time()
        assert before <= result["timestamp"] <= after

    def test_record_computes_sha256_hash(self, agg):
        result = agg.record(source="api", action="login", actor="alice")
        assert len(result["hash"]) == 64  # SHA-256 hex digest

    def test_record_hash_is_deterministic(self, agg):
        """Hash is recomputed from stored values and matches."""
        result = agg.record(
            source="security", action="key_access", actor="bob",
            resource="vault_key_1", outcome="success",
            metadata={"ip": "10.0.0.1"},
        )
        # Recompute from return values
        metadata_json = json.dumps({"ip": "10.0.0.1"}, sort_keys=True)
        raw = (
            f"{result['entry_id']}|security|key_access|bob|vault_key_1|"
            f"success|{result['timestamp']}|{metadata_json}"
        )
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert result["hash"] == expected

    def test_record_with_all_fields(self, agg):
        result = agg.record(
            source="governance", action="policy_update", actor="admin",
            resource="policy-42", outcome="success",
            metadata={"change": "updated threshold"},
        )
        assert result["source"] == "governance"
        assert result["action"] == "policy_update"
        assert result["actor"] == "admin"
        assert result["resource"] == "policy-42"
        assert result["outcome"] == "success"
        assert result["metadata"] == {"change": "updated threshold"}

    def test_record_rejects_invalid_source(self, agg):
        with pytest.raises(ValueError, match="Invalid source"):
            agg.record(source="invalid_source", action="test")

    def test_record_rejects_invalid_outcome(self, agg):
        with pytest.raises(ValueError, match="Invalid outcome"):
            agg.record(source="api", action="test", outcome="invalid_outcome")

    def test_record_all_valid_sources(self, agg):
        for source in VALID_SOURCES:
            result = agg.record(source=source, action="test")
            assert result["source"] == source

    def test_record_all_valid_outcomes(self, agg):
        for outcome in VALID_OUTCOMES:
            result = agg.record(source="api", action="test", outcome=outcome)
            assert result["outcome"] == outcome

    def test_record_metadata_stored_as_json(self, agg):
        meta = {"nested": {"key": [1, 2]}, "flag": True}
        result = agg.record(source="api", action="test", metadata=meta)
        assert result["metadata"] == meta

        # Roundtrip through DB
        retrieved = agg.get_entry(result["entry_id"])
        assert retrieved["metadata"] == meta

    def test_record_none_metadata_becomes_empty_dict(self, agg):
        result = agg.record(source="api", action="test", metadata=None)
        assert result["metadata"] == {}

    def test_record_multiple_entries_unique_ids(self, agg):
        ids = set()
        for i in range(20):
            r = agg.record(source="api", action=f"action_{i}")
            ids.add(r["entry_id"])
        assert len(ids) == 20


# ---------------------------------------------------------------------------
# Test: get_entry()
# ---------------------------------------------------------------------------

class TestGetEntry:
    def test_get_existing_entry(self, agg):
        recorded = agg.record(source="api", action="login", actor="alice")
        retrieved = agg.get_entry(recorded["entry_id"])
        assert retrieved is not None
        assert retrieved["entry_id"] == recorded["entry_id"]
        assert retrieved["source"] == "api"
        assert retrieved["action"] == "login"
        assert retrieved["actor"] == "alice"

    def test_get_nonexistent_entry_returns_none(self, agg):
        result = agg.get_entry("does_not_exist")
        assert result is None

    def test_get_entry_includes_hash(self, agg):
        recorded = agg.record(source="api", action="test")
        retrieved = agg.get_entry(recorded["entry_id"])
        assert retrieved["hash"] == recorded["hash"]
        assert len(retrieved["hash"]) == 64

    def test_get_entry_parses_metadata_json(self, agg):
        meta = {"key": "value", "count": 42}
        recorded = agg.record(source="api", action="test", metadata=meta)
        retrieved = agg.get_entry(recorded["entry_id"])
        assert retrieved["metadata"] == meta


# ---------------------------------------------------------------------------
# Test: query()
# ---------------------------------------------------------------------------

class TestQuery:
    def test_query_no_filters(self, agg):
        agg.record(source="api", action="login")
        agg.record(source="security", action="key_rotate")
        results = agg.query()
        assert len(results) == 2

    def test_query_by_source(self, agg):
        agg.record(source="api", action="a1")
        agg.record(source="security", action="a2")
        agg.record(source="api", action="a3")
        results = agg.query(source="api")
        assert len(results) == 2
        assert all(r["source"] == "api" for r in results)

    def test_query_by_action(self, agg):
        agg.record(source="api", action="login")
        agg.record(source="api", action="logout")
        agg.record(source="api", action="login")
        results = agg.query(action="login")
        assert len(results) == 2

    def test_query_by_actor(self, agg):
        agg.record(source="api", action="test", actor="alice")
        agg.record(source="api", action="test", actor="bob")
        agg.record(source="api", action="test", actor="alice")
        results = agg.query(actor="alice")
        assert len(results) == 2

    def test_query_by_resource(self, agg):
        agg.record(source="api", action="read", resource="doc1")
        agg.record(source="api", action="read", resource="doc2")
        agg.record(source="api", action="read", resource="doc1")
        results = agg.query(resource="doc1")
        assert len(results) == 2

    def test_query_by_outcome(self, agg):
        agg.record(source="api", action="test", outcome="success")
        agg.record(source="api", action="test", outcome="failure")
        agg.record(source="api", action="test", outcome="success")
        results = agg.query(outcome="failure")
        assert len(results) == 1

    def test_query_by_since(self, agg):
        agg.record(source="api", action="old_action")
        time.sleep(0.05)
        cutoff = time.time()
        agg.record(source="api", action="new_action")
        results = agg.query(since=cutoff)
        assert len(results) == 1
        assert results[0]["action"] == "new_action"

    def test_query_by_until(self, agg):
        agg.record(source="api", action="old_action")
        time.sleep(0.05)
        cutoff = time.time()
        agg.record(source="api", action="new_action")
        results = agg.query(until=cutoff)
        assert len(results) == 1
        assert results[0]["action"] == "old_action"

    def test_query_with_limit(self, agg):
        for i in range(50):
            agg.record(source="api", action=f"action_{i}")
        results = agg.query(limit=10)
        assert len(results) == 10

    def test_query_combined_filters(self, agg):
        agg.record(source="api", action="read", actor="alice", resource="doc1")
        agg.record(source="api", action="write", actor="alice", resource="doc1")
        agg.record(source="api", action="read", actor="bob", resource="doc1")
        agg.record(source="security", action="read", actor="alice", resource="doc1")

        results = agg.query(source="api", action="read", actor="alice")
        assert len(results) == 1
        assert results[0]["resource"] == "doc1"

    def test_query_returns_descending_order(self, agg):
        agg.record(source="api", action="first")
        time.sleep(0.02)
        agg.record(source="api", action="second")
        time.sleep(0.02)
        agg.record(source="api", action="third")

        results = agg.query()
        assert results[0]["action"] == "third"
        assert results[-1]["action"] == "first"

    def test_query_records_audit_query(self, agg):
        agg.record(source="api", action="test")
        agg.query(source="api")
        stats = agg.get_stats()
        assert stats["total_queries"] == 1

    def test_query_empty_result(self, agg):
        results = agg.query(source="nonexistent")
        assert results == []

    def test_query_since_and_until_range(self, agg):
        agg.record(source="api", action="before")
        time.sleep(0.05)
        t_start = time.time()
        agg.record(source="api", action="during")
        time.sleep(0.05)
        t_end = time.time()
        agg.record(source="api", action="after")

        results = agg.query(since=t_start, until=t_end)
        assert len(results) == 1
        assert results[0]["action"] == "during"


# ---------------------------------------------------------------------------
# Test: count_by_action()
# ---------------------------------------------------------------------------

class TestCountByAction:
    def test_empty_table(self, agg):
        result = agg.count_by_action()
        assert result == {}

    def test_counts_all_actions(self, agg):
        agg.record(source="api", action="login")
        agg.record(source="api", action="login")
        agg.record(source="api", action="logout")
        result = agg.count_by_action()
        assert result["login"] == 2
        assert result["logout"] == 1

    def test_filters_by_source(self, agg):
        agg.record(source="api", action="call")
        agg.record(source="api", action="call")
        agg.record(source="security", action="call")
        result = agg.count_by_action(source="api")
        assert result["call"] == 2

    def test_nonexistent_source_returns_empty(self, agg):
        agg.record(source="api", action="call")
        result = agg.count_by_action(source="security")
        assert result == {}


# ---------------------------------------------------------------------------
# Test: count_by_actor()
# ---------------------------------------------------------------------------

class TestCountByActor:
    def test_empty_table(self, agg):
        result = agg.count_by_actor()
        assert result == {}

    def test_counts_all_actors(self, agg):
        agg.record(source="api", action="test", actor="alice")
        agg.record(source="api", action="test", actor="alice")
        agg.record(source="api", action="test", actor="bob")
        result = agg.count_by_actor()
        assert result["alice"] == 2
        assert result["bob"] == 1

    def test_filters_by_source(self, agg):
        agg.record(source="api", action="test", actor="alice")
        agg.record(source="security", action="test", actor="alice")
        result = agg.count_by_actor(source="api")
        assert result["alice"] == 1

    def test_nonexistent_source_returns_empty(self, agg):
        agg.record(source="api", action="test", actor="alice")
        result = agg.count_by_actor(source="governance")
        assert result == {}


# ---------------------------------------------------------------------------
# Test: verify_integrity()
# ---------------------------------------------------------------------------

class TestVerifyIntegrity:
    def test_empty_table_is_valid(self, agg):
        result = agg.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 0
        assert result["broken_at"] == []
        assert result["errors"] == []

    def test_single_entry_valid(self, agg):
        agg.record(source="api", action="login", actor="alice")
        result = agg.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 1

    def test_multiple_entries_valid(self, agg):
        for i in range(20):
            agg.record(source="api", action=f"action_{i}")
        result = agg.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 20

    def test_detects_tampered_hash(self, agg):
        entry = agg.record(source="api", action="login", actor="alice")
        agg.record(source="api", action="logout", actor="alice")

        # Tamper with the first entry's hash
        agg._conn.execute(
            "UPDATE audit_entries SET hash = ? WHERE entry_id = ?",
            ("deadbeef" + "0" * 56, entry["entry_id"]),
        )
        agg._conn.commit()

        result = agg.verify_integrity()
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert 0 in result["broken_at"]

    def test_detects_tampered_actor(self, agg):
        entry = agg.record(source="api", action="login", actor="alice")
        agg.record(source="api", action="logout", actor="alice")

        # Modify actor -- hash should no longer match
        agg._conn.execute(
            "UPDATE audit_entries SET actor = ? WHERE entry_id = ?",
            ("eve", entry["entry_id"]),
        )
        agg._conn.commit()

        result = agg.verify_integrity()
        assert result["valid"] is False

    def test_detects_tampered_metadata(self, agg):
        entry = agg.record(
            source="api", action="login", metadata={"ip": "10.0.0.1"},
        )
        agg._conn.execute(
            "UPDATE audit_entries SET metadata = ? WHERE entry_id = ?",
            ('{"ip": "99.99.99.99"}', entry["entry_id"]),
        )
        agg._conn.commit()

        result = agg.verify_integrity()
        assert result["valid"] is False

    def test_verify_with_since_filter(self, agg):
        agg.record(source="api", action="old")
        time.sleep(0.05)
        cutoff = time.time()
        agg.record(source="api", action="new1")
        agg.record(source="api", action="new2")

        result = agg.verify_integrity(since=cutoff)
        assert result["valid"] is True
        assert result["total_entries"] == 2

    def test_verify_middle_tampered_entry(self, agg):
        entries = []
        for i in range(5):
            e = agg.record(source="api", action=f"act_{i}")
            entries.append(e)

        # Tamper the middle entry
        middle = entries[2]
        agg._conn.execute(
            "UPDATE audit_entries SET action = ? WHERE entry_id = ?",
            ("tampered_action", middle["entry_id"]),
        )
        agg._conn.commit()

        result = agg.verify_integrity()
        assert result["valid"] is False
        assert 2 in result["broken_at"]


# ---------------------------------------------------------------------------
# Test: get_stats()
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_stats(self, agg):
        stats = agg.get_stats()
        assert stats["total_entries"] == 0
        assert stats["by_source"] == {}
        assert stats["by_action"] == {}
        assert stats["by_outcome"] == {}
        assert stats["total_queries"] == 0

    def test_counts_by_source(self, agg):
        agg.record(source="api", action="test")
        agg.record(source="api", action="test")
        agg.record(source="security", action="test")
        stats = agg.get_stats()
        assert stats["by_source"]["api"] == 2
        assert stats["by_source"]["security"] == 1

    def test_counts_by_action(self, agg):
        agg.record(source="api", action="login")
        agg.record(source="api", action="login")
        agg.record(source="api", action="logout")
        stats = agg.get_stats()
        assert stats["by_action"]["login"] == 2
        assert stats["by_action"]["logout"] == 1

    def test_counts_by_outcome(self, agg):
        agg.record(source="api", action="test", outcome="success")
        agg.record(source="api", action="test", outcome="failure")
        agg.record(source="api", action="test", outcome="success")
        stats = agg.get_stats()
        assert stats["by_outcome"]["success"] == 2
        assert stats["by_outcome"]["failure"] == 1

    def test_total_entries_count(self, agg):
        for i in range(10):
            agg.record(source="api", action=f"action_{i}")
        stats = agg.get_stats()
        assert stats["total_entries"] == 10

    def test_tracks_queries(self, agg):
        agg.record(source="api", action="test")
        agg.query(source="api")
        agg.query(action="test")
        stats = agg.get_stats()
        assert stats["total_queries"] == 2

    def test_all_sources_all_outcomes(self, agg):
        for source in VALID_SOURCES:
            for outcome in VALID_OUTCOMES:
                agg.record(source=source, action="test", outcome=outcome)
        stats = agg.get_stats()
        assert stats["total_entries"] == len(VALID_SOURCES) * len(VALID_OUTCOMES)
        for source in VALID_SOURCES:
            assert stats["by_source"][source] == len(VALID_OUTCOMES)
        for outcome in VALID_OUTCOMES:
            assert stats["by_outcome"][outcome] == len(VALID_SOURCES)


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_record_emits_event(self, agg_with_bus):
        agg, bus = agg_with_bus
        events = []
        bus.subscribe("audit.entry_recorded", lambda e: events.append(e))
        agg.record(source="api", action="login", actor="alice")
        assert len(events) == 1
        assert events[0].payload["source"] == "api"
        assert events[0].payload["action"] == "login"
        assert events[0].payload["actor"] == "alice"

    def test_event_includes_entry_id(self, agg_with_bus):
        agg, bus = agg_with_bus
        events = []
        bus.subscribe("audit.entry_recorded", lambda e: events.append(e))
        agg.record(source="api", action="test")
        assert len(events) == 1
        assert "entry_id" in events[0].payload
        assert len(events[0].payload["entry_id"]) == 32

    def test_event_includes_outcome(self, agg_with_bus):
        agg, bus = agg_with_bus
        events = []
        bus.subscribe("audit.entry_recorded", lambda e: events.append(e))
        agg.record(source="api", action="test", outcome="failure")
        assert events[0].payload["outcome"] == "failure"

    def test_no_event_without_bus(self, agg):
        # Should not raise -- _emit gracefully handles None event_bus
        agg.record(source="api", action="test")
        agg.record(source="security", action="test", outcome="denied")

    def test_multiple_records_multiple_events(self, agg_with_bus):
        agg, bus = agg_with_bus
        events = []
        bus.subscribe("audit.entry_recorded", lambda e: events.append(e))
        for i in range(5):
            agg.record(source="api", action=f"action_{i}")
        assert len(events) == 5

    def test_event_source_module(self, agg_with_bus):
        agg, bus = agg_with_bus
        events = []
        bus.subscribe("audit.entry_recorded", lambda e: events.append(e))
        agg.record(source="api", action="test")
        assert events[0].source_module == "security.audit_trail_aggregator"


# ---------------------------------------------------------------------------
# Test: Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        import sylion.security.audit_trail_aggregator as mod
        mod._aggregator = None
        a1 = get_audit_trail_aggregator(db_path=":memory:")
        a2 = get_audit_trail_aggregator()
        assert a1 is a2
        mod._aggregator = None  # cleanup

    def test_reset_creates_new_instance(self):
        import sylion.security.audit_trail_aggregator as mod
        mod._aggregator = None
        a1 = get_audit_trail_aggregator(db_path=":memory:")
        a2 = reset_audit_trail_aggregator(db_path=":memory:")
        assert a1 is not a2
        mod._aggregator = None  # cleanup

    def test_get_after_reset_returns_new_instance(self):
        import sylion.security.audit_trail_aggregator as mod
        mod._aggregator = None
        a1 = get_audit_trail_aggregator(db_path=":memory:")
        a2 = reset_audit_trail_aggregator(db_path=":memory:")
        a3 = get_audit_trail_aggregator()
        assert a2 is a3
        assert a1 is not a3
        mod._aggregator = None  # cleanup


# ---------------------------------------------------------------------------
# Test: Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_records(self, agg):
        errors = []
        barrier = threading.Barrier(4)
        num_per_thread = 25

        def worker(tid):
            try:
                barrier.wait(timeout=5)
                for i in range(num_per_thread):
                    agg.record(
                        source="api",
                        action=f"action_{tid}_{i}",
                        actor=f"thread_{tid}",
                    )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Thread errors: {errors}"
        stats = agg.get_stats()
        assert stats["total_entries"] == 4 * num_per_thread

    def test_concurrent_read_write(self, agg):
        for i in range(10):
            agg.record(source="api", action=f"seed_{i}")

        errors = []

        def reader():
            try:
                for _ in range(50):
                    agg.query(source="api")
                    agg.count_by_action()
                    agg.count_by_actor()
                    agg.get_stats()
                    agg.verify_integrity()
            except Exception as exc:
                errors.append(str(exc))

        def writer():
            try:
                for i in range(20):
                    agg.record(source="api", action=f"write_{i}", actor="writer")
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert errors == [], f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# Test: File-backed DB
# ---------------------------------------------------------------------------

class TestFileBackedDB:
    def test_file_backed_persistence(self, tmp_path):
        db_file = tmp_path / "test_audit_trail.db"
        agg = AuditTrailAggregator(db_path=str(db_file))

        r = agg.record(source="api", action="login", actor="alice")
        assert agg.get_entry(r["entry_id"]) is not None

        # Verify data in file
        conn = sqlite3.connect(str(db_file))
        count = conn.execute("SELECT COUNT(*) FROM audit_entries").fetchone()[0]
        conn.close()
        assert count == 1

    def test_file_backed_integrity(self, tmp_path):
        db_file = tmp_path / "test_integrity.db"
        agg = AuditTrailAggregator(db_path=str(db_file))

        for i in range(10):
            agg.record(source="api", action=f"action_{i}")

        result = agg.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 10
