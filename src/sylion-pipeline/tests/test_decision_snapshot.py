"""Tests for SYLION Governance -- Decision Snapshot Manager.

Covers: CRUD, snapshot comparison, timeline, factors, EventBus integration,
thread safety, validation, and singleton management.
"""
import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.decision_snapshot import (
    VALID_OUTCOMES,
    DecisionSnapshotManager,
    get_decision_snapshot_manager,
    reset_decision_snapshot_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr():
    """Fresh DecisionSnapshotManager with :memory: SQLite."""
    return DecisionSnapshotManager(db_path=":memory:")


@pytest.fixture
def mgr_with_bus():
    """DecisionSnapshotManager connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return DecisionSnapshotManager(db_path=":memory:", event_bus=bus), bus


# ---------------------------------------------------------------------------
# Test: create_snapshot
# ---------------------------------------------------------------------------

class TestCreateSnapshot:
    def test_creates_basic_snapshot(self, mgr):
        result = mgr.create_snapshot("DEC-001")
        assert "snapshot_id" in result
        assert result["decision_id"] == "DEC-001"
        assert result["outcome"] == "approved"
        assert result["confidence"] == 1.0
        assert result["factors"] == []
        assert result["context"] == {}

    def test_with_context_dict(self, mgr):
        ctx = {"module": "auth", "version": "2.0"}
        result = mgr.create_snapshot("DEC-002", context_json=ctx)
        assert result["context"] == ctx

    def test_with_context_json_string(self, mgr):
        ctx = json.dumps({"key": "val"})
        result = mgr.create_snapshot("DEC-003", context_json=ctx)
        assert result["context"] == {"key": "val"}

    def test_with_outcome(self, mgr):
        for outcome in VALID_OUTCOMES:
            result = mgr.create_snapshot("DEC-O", outcome=outcome)
            assert result["outcome"] == outcome

    def test_with_confidence(self, mgr):
        result = mgr.create_snapshot("DEC-C", confidence=0.75)
        assert result["confidence"] == 0.75

    def test_confidence_clamped_above_one(self, mgr):
        result = mgr.create_snapshot("DEC-CH", confidence=2.0)
        assert result["confidence"] == 1.0

    def test_confidence_clamped_below_zero(self, mgr):
        result = mgr.create_snapshot("DEC-CL", confidence=-0.5)
        assert result["confidence"] == 0.0

    def test_with_factors(self, mgr):
        factors = [
            {"name": "risk", "value": "0.3", "weight": 1.5},
            {"name": "complexity", "value": "low", "weight": 1.0},
        ]
        result = mgr.create_snapshot("DEC-F", factors_list=factors)
        assert len(result["factors"]) == 2

    def test_rejects_empty_decision_id(self, mgr):
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.create_snapshot("")

    def test_rejects_whitespace_decision_id(self, mgr):
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.create_snapshot("   ")

    def test_rejects_invalid_outcome(self, mgr):
        with pytest.raises(ValueError, match="Invalid outcome"):
            mgr.create_snapshot("DEC-I", outcome="maybe")

    def test_snapshot_id_is_unique(self, mgr):
        r1 = mgr.create_snapshot("DEC-U1")
        r2 = mgr.create_snapshot("DEC-U2")
        assert r1["snapshot_id"] != r2["snapshot_id"]

    def test_timestamp_set(self, mgr):
        before = time.time()
        result = mgr.create_snapshot("DEC-TS")
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_none_context_gives_empty_dict(self, mgr):
        result = mgr.create_snapshot("DEC-NC", context_json=None)
        assert result["context"] == {}


# ---------------------------------------------------------------------------
# Test: get_snapshot
# ---------------------------------------------------------------------------

class TestGetSnapshot:
    def test_returns_created_snapshot(self, mgr):
        created = mgr.create_snapshot("DEC-G1", context_json={"a": 1},
                                      outcome="rejected", confidence=0.6)
        fetched = mgr.get_snapshot(created["snapshot_id"])
        assert fetched is not None
        assert fetched["snapshot_id"] == created["snapshot_id"]
        assert fetched["decision_id"] == "DEC-G1"
        assert fetched["context"] == {"a": 1}
        assert fetched["outcome"] == "rejected"
        assert fetched["confidence"] == 0.6

    def test_returns_none_for_missing(self, mgr):
        assert mgr.get_snapshot("nonexistent") is None

    def test_factors_included(self, mgr):
        factors = [{"name": "x", "value": "1", "weight": 2.0}]
        created = mgr.create_snapshot("DEC-GF", factors_list=factors)
        fetched = mgr.get_snapshot(created["snapshot_id"])
        assert len(fetched["factors"]) == 1
        assert fetched["factors"][0]["name"] == "x"
        assert fetched["factors"][0]["weight"] == 2.0


# ---------------------------------------------------------------------------
# Test: list_snapshots
# ---------------------------------------------------------------------------

class TestListSnapshots:
    def test_lists_all(self, mgr):
        mgr.create_snapshot("DEC-L1")
        mgr.create_snapshot("DEC-L2")
        assert len(mgr.list_snapshots()) == 2

    def test_filter_by_decision_id(self, mgr):
        mgr.create_snapshot("DEC-LA")
        mgr.create_snapshot("DEC-LB")
        result = mgr.list_snapshots(decision_id="DEC-LA")
        assert len(result) == 1
        assert result[0]["decision_id"] == "DEC-LA"

    def test_respects_limit(self, mgr):
        for i in range(10):
            mgr.create_snapshot(f"DEC-LIM-{i}")
        result = mgr.list_snapshots(limit=5)
        assert len(result) == 5

    def test_newest_first(self, mgr):
        mgr.create_snapshot("DEC-ORD1")
        time.sleep(0.01)
        mgr.create_snapshot("DEC-ORD2")
        result = mgr.list_snapshots()
        assert result[0]["decision_id"] == "DEC-ORD2"

    def test_empty_list(self, mgr):
        assert mgr.list_snapshots() == []


# ---------------------------------------------------------------------------
# Test: compare_snapshots
# ---------------------------------------------------------------------------

class TestCompareSnapshots:
    def test_identical_snapshots(self, mgr):
        ctx = {"module": "auth"}
        s1 = mgr.create_snapshot("DEC-CMP", context_json=ctx)
        s2 = mgr.create_snapshot("DEC-CMP", context_json=ctx)
        diff = mgr.compare_snapshots(s1["snapshot_id"], s2["snapshot_id"])
        assert diff is not None
        assert diff["context_diff"] == {}
        assert diff["outcome_changed"] is False
        assert diff["confidence_delta"] == 0.0

    def test_context_diff(self, mgr):
        s1 = mgr.create_snapshot("DEC-CD", context_json={"a": 1, "b": 2})
        s2 = mgr.create_snapshot("DEC-CD", context_json={"a": 1, "b": 3})
        diff = mgr.compare_snapshots(s1["snapshot_id"], s2["snapshot_id"])
        assert "b" in diff["context_diff"]
        assert diff["context_diff"]["b"]["before"] == 2
        assert diff["context_diff"]["b"]["after"] == 3

    def test_context_added(self, mgr):
        s1 = mgr.create_snapshot("DEC-CA", context_json={"a": 1})
        s2 = mgr.create_snapshot("DEC-CA", context_json={"a": 1, "c": 3})
        diff = mgr.compare_snapshots(s1["snapshot_id"], s2["snapshot_id"])
        assert "c" in diff["context_diff"]

    def test_outcome_changed(self, mgr):
        s1 = mgr.create_snapshot("DEC-OC", outcome="approved")
        s2 = mgr.create_snapshot("DEC-OC", outcome="rejected")
        diff = mgr.compare_snapshots(s1["snapshot_id"], s2["snapshot_id"])
        assert diff["outcome_changed"] is True
        assert diff["outcome_before"] == "approved"
        assert diff["outcome_after"] == "rejected"

    def test_confidence_delta(self, mgr):
        s1 = mgr.create_snapshot("DEC-CD2", confidence=0.5)
        s2 = mgr.create_snapshot("DEC-CD2", confidence=0.8)
        diff = mgr.compare_snapshots(s1["snapshot_id"], s2["snapshot_id"])
        assert abs(diff["confidence_delta"] - 0.3) < 1e-6

    def test_factors_diff(self, mgr):
        f1 = [{"name": "risk", "value": "0.3", "weight": 1.0}]
        f2 = [{"name": "risk", "value": "0.7", "weight": 1.0}]
        s1 = mgr.create_snapshot("DEC-FD", factors_list=f1)
        s2 = mgr.create_snapshot("DEC-FD", factors_list=f2)
        diff = mgr.compare_snapshots(s1["snapshot_id"], s2["snapshot_id"])
        assert "risk" in diff["factors_diff"]

    def test_returns_none_for_missing_snapshot(self, mgr):
        s1 = mgr.create_snapshot("DEC-MIS")
        result = mgr.compare_snapshots(s1["snapshot_id"], "nonexistent")
        assert result is None

    def test_returns_none_for_both_missing(self, mgr):
        result = mgr.compare_snapshots("a", "b")
        assert result is None


# ---------------------------------------------------------------------------
# Test: get_timeline
# ---------------------------------------------------------------------------

class TestGetTimeline:
    def test_returns_chronological_order(self, mgr):
        mgr.create_snapshot("DEC-TL")
        time.sleep(0.01)
        mgr.create_snapshot("DEC-TL")
        time.sleep(0.01)
        mgr.create_snapshot("DEC-TL")
        timeline = mgr.get_timeline("DEC-TL")
        assert len(timeline) == 3
        for i in range(len(timeline) - 1):
            assert timeline[i]["created_at"] <= timeline[i + 1]["created_at"]

    def test_filters_by_decision_id(self, mgr):
        mgr.create_snapshot("DEC-TLA")
        mgr.create_snapshot("DEC-TLB")
        timeline = mgr.get_timeline("DEC-TLA")
        assert len(timeline) == 1

    def test_empty_for_no_match(self, mgr):
        assert mgr.get_timeline("DEC-NONE") == []

    def test_includes_factors(self, mgr):
        factors = [{"name": "x", "value": "1", "weight": 1.0}]
        mgr.create_snapshot("DEC-TLF", factors_list=factors)
        timeline = mgr.get_timeline("DEC-TLF")
        assert len(timeline[0]["factors"]) == 1


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_snapshot_created_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("snapshot_created", lambda e: events.append(e))
        mgr.create_snapshot("DEC-EV")
        assert len(events) == 1
        assert events[0].payload["decision_id"] == "DEC-EV"

    def test_snapshots_compared_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("snapshots_compared", lambda e: events.append(e))
        s1 = mgr.create_snapshot("DEC-EVC")
        s2 = mgr.create_snapshot("DEC-EVC", confidence=0.5)
        mgr.compare_snapshots(s1["snapshot_id"], s2["snapshot_id"])
        assert len(events) == 1
        assert "context_changes" in events[0].payload

    def test_no_event_without_bus(self, mgr):
        mgr.create_snapshot("DEC-NOBUS")


# ---------------------------------------------------------------------------
# Test: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_creates(self, mgr):
        errors = []
        results = []

        def create(i):
            try:
                r = mgr.create_snapshot(f"DEC-THR-{i}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20

    def test_concurrent_reads_and_writes(self, mgr):
        mgr.create_snapshot("DEC-RW")
        errors = []

        def reader():
            try:
                for _ in range(50):
                    mgr.list_snapshots()
                    mgr.get_timeline("DEC-RW")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    mgr.create_snapshot(f"DEC-RW-{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Test: singleton management
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        reset_decision_snapshot_manager()
        s1 = get_decision_snapshot_manager(db_path=":memory:")
        s2 = get_decision_snapshot_manager()
        assert s1 is s2
        reset_decision_snapshot_manager()

    def test_reset_clears_singleton(self):
        s1 = get_decision_snapshot_manager(db_path=":memory:")
        reset_decision_snapshot_manager()
        s2 = get_decision_snapshot_manager(db_path=":memory:")
        assert s1 is not s2
        reset_decision_snapshot_manager()


# ---------------------------------------------------------------------------
# Test: constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_valid_outcomes(self):
        assert "approved" in VALID_OUTCOMES
        assert "rejected" in VALID_OUTCOMES
        assert "deferred" in VALID_OUTCOMES
        assert "escalated" in VALID_OUTCOMES
        assert "auto_approved" in VALID_OUTCOMES
