"""
Tests for DecisionAudit -- log_event, get_audit_log, get_audit_entry,
get_audit_timeline, get_audit_stats, export_audit_log, purge_old_entries,
singleton lifecycle, thread safety.
"""

from __future__ import annotations

import json
import time
import threading

import pytest

from sylion.governance.decision_audit import (
    DecisionAudit,
    get_decision_audit,
    reset_decision_audit,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset global singleton before and after every test."""
    reset_decision_audit()
    yield
    reset_decision_audit()


@pytest.fixture
def da():
    """Fresh in-memory DecisionAudit instance."""
    return DecisionAudit()


@pytest.fixture
def da_bus():
    """DecisionAudit with EventBus."""
    from sylion.core.event_bus import EventBus
    bus = EventBus()
    return DecisionAudit(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(da, **overrides) -> dict:
    """Log a minimal event, overriding defaults with *overrides*."""
    defaults = dict(
        event_type="snapshot_captured",
        description="test event",
    )
    defaults.update(overrides)
    return da.log_event(**defaults)


# ===========================================================================
# TestLogEvent
# ===========================================================================

class TestLogEvent:

    def test_log_event_with_all_fields(self, da):
        entry = da.log_event(
            event_type="decision_changed",
            description="Decision D1 was changed from A to B",
            decision_id="DEC-001",
            snapshot_id="SNAP-001",
            actor="council",
            before_state={"choice": "A"},
            after_state={"choice": "B"},
            related_ids={"conflict_id": "CF-001"},
            metadata={"reason": "new evidence"},
            severity="warning",
            source_module="conflict_resolver",
        )
        assert entry["audit_id"]
        assert entry["event_type"] == "decision_changed"
        assert entry["decision_id"] == "DEC-001"
        assert entry["snapshot_id"] == "SNAP-001"
        assert entry["actor"] == "council"
        assert entry["description"] == "Decision D1 was changed from A to B"
        assert entry["before_state"] == {"choice": "A"}
        assert entry["after_state"] == {"choice": "B"}
        assert entry["related_ids"] == {"conflict_id": "CF-001"}
        assert entry["metadata"] == {"reason": "new evidence"}
        assert entry["severity"] == "warning"
        assert entry["source_module"] == "conflict_resolver"
        assert entry["created_at"] > 0

    def test_log_minimal_event(self, da):
        entry = da.log_event(
            event_type="snapshot_captured",
            description="minimal event",
        )
        assert entry["audit_id"]
        assert entry["event_type"] == "snapshot_captured"
        assert entry["description"] == "minimal event"
        assert entry["decision_id"] is None
        assert entry["snapshot_id"] is None
        assert entry["actor"] == "system"
        assert entry["before_state"] is None
        assert entry["after_state"] is None
        assert entry["related_ids"] is None
        assert entry["metadata"] is None
        assert entry["severity"] == "info"
        assert entry["source_module"] is None

    def test_log_returns_created_at(self, da):
        before = time.time()
        entry = _log(da)
        after = time.time()
        assert before <= entry["created_at"] <= after

    def test_log_emits_event(self, da_bus):
        events = []
        da_bus._event_bus.subscribe(
            "decision.audit.logged", lambda e: events.append(e))
        _log(da_bus, event_type="gate_evaluated", description="gate check")
        assert len(events) == 1
        assert events[0].payload["event_type"] == "gate_evaluated"

    def test_log_multiple_events(self, da):
        _log(da, event_type="snapshot_captured", description="first")
        _log(da, event_type="decision_changed", description="second")
        _log(da, event_type="cascade_triggered", description="third")
        entries = da.get_audit_log()
        assert len(entries) == 3

    def test_log_event_with_various_severities(self, da):
        _log(da, description="info event", severity="info")
        _log(da, description="warning event", severity="warning")
        _log(da, description="critical event", severity="critical")
        entries = da.get_audit_log()
        severities = {e["severity"] for e in entries}
        assert severities == {"info", "warning", "critical"}


# ===========================================================================
# TestGetAuditLog
# ===========================================================================

class TestGetAuditLog:

    def test_get_audit_log_unfiltered(self, da):
        _log(da, description="event 1")
        _log(da, description="event 2")
        entries = da.get_audit_log()
        assert len(entries) == 2

    def test_filter_by_event_type(self, da):
        _log(da, event_type="snapshot_captured", description="snap")
        _log(da, event_type="decision_changed", description="change")
        _log(da, event_type="conflict_detected", description="conflict")

        entries = da.get_audit_log(event_type="decision_changed")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "decision_changed"

    def test_filter_by_decision_id(self, da):
        _log(da, decision_id="DEC-001", description="for DEC-001")
        _log(da, decision_id="DEC-002", description="for DEC-002")
        _log(da, description="no decision")

        entries = da.get_audit_log(decision_id="DEC-001")
        assert len(entries) == 1
        assert entries[0]["decision_id"] == "DEC-001"

    def test_filter_by_severity(self, da):
        _log(da, description="info", severity="info")
        _log(da, description="critical", severity="critical")

        entries = da.get_audit_log(severity="critical")
        assert len(entries) == 1
        assert entries[0]["severity"] == "critical"

    def test_filter_by_time_range(self, da):
        t1 = time.time()
        _log(da, description="event at t1")
        t2 = time.time()
        _log(da, description="event at t2")
        t3 = time.time()
        _log(da, description="event at t3")
        t4 = time.time()

        entries = da.get_audit_log(from_time=t2, to_time=t3)
        # at least the second event should be in range
        assert len(entries) >= 1

    def test_combined_filters(self, da):
        _log(da, event_type="conflict_detected", decision_id="DEC-001",
             severity="critical", description="match")
        _log(da, event_type="conflict_detected", decision_id="DEC-002",
             severity="critical", description="no match on decision")
        _log(da, event_type="snapshot_captured", decision_id="DEC-001",
             severity="info", description="no match on type")

        entries = da.get_audit_log(
            event_type="conflict_detected",
            decision_id="DEC-001",
            severity="critical",
        )
        assert len(entries) == 1
        assert entries[0]["description"] == "match"

    def test_limit(self, da):
        for i in range(10):
            _log(da, description=f"event {i}")
        entries = da.get_audit_log(limit=5)
        assert len(entries) == 5

    def test_filter_by_source_module(self, da):
        _log(da, source_module="conflict_resolver", description="from cr")
        _log(da, source_module="compliance_engine", description="from ce")

        entries = da.get_audit_log(source_module="conflict_resolver")
        assert len(entries) == 1
        assert entries[0]["source_module"] == "conflict_resolver"

    def test_empty_log(self, da):
        entries = da.get_audit_log()
        assert entries == []

    def test_ordering_newest_first(self, da):
        _log(da, description="first")
        _log(da, description="second")
        entries = da.get_audit_log()
        assert entries[0]["description"] == "second"
        assert entries[1]["description"] == "first"


# ===========================================================================
# TestGetAuditEntry
# ===========================================================================

class TestGetAuditEntry:

    def test_get_audit_entry_by_id(self, da):
        created = _log(da, description="find me")
        audit_id = created["audit_id"]

        entry = da.get_audit_entry(audit_id)
        assert entry is not None
        assert entry["audit_id"] == audit_id
        assert entry["description"] == "find me"

    def test_get_audit_entry_not_found(self, da):
        entry = da.get_audit_entry("nonexistent")
        assert entry is None

    def test_get_audit_entry_parses_json_fields(self, da):
        created = _log(
            da,
            description="with json",
            before_state={"old": True},
            after_state={"new": True},
            related_ids={"conflict_id": "CF-99"},
            metadata={"key": "val"},
        )
        entry = da.get_audit_entry(created["audit_id"])
        assert entry["before_state"] == {"old": True}
        assert entry["after_state"] == {"new": True}
        assert entry["related_ids"] == {"conflict_id": "CF-99"}
        assert entry["metadata"] == {"key": "val"}


# ===========================================================================
# TestGetAuditTimeline
# ===========================================================================

class TestGetAuditTimeline:

    def test_timeline_for_decision(self, da):
        did = "DEC-TL"
        _log(da, decision_id=did, event_type="snapshot_captured",
             description="snapshot taken")
        _log(da, decision_id=did, event_type="decision_changed",
             description="decision changed")
        _log(da, decision_id=did, event_type="cascade_triggered",
             description="cascade fired")

        timeline = da.get_audit_timeline(did)
        assert len(timeline) == 3

    def test_timeline_excludes_other_decisions(self, da):
        _log(da, decision_id="DEC-A", description="for A")
        _log(da, decision_id="DEC-B", description="for B")
        _log(da, decision_id="DEC-A", description="also for A")

        timeline = da.get_audit_timeline("DEC-A")
        assert len(timeline) == 2
        assert all(e["decision_id"] == "DEC-A" for e in timeline)

    def test_timeline_is_chronological(self, da):
        did = "DEC-CHRONO"
        # Log events with small sleep to guarantee ordering
        _log(da, decision_id=did, description="first")
        _log(da, decision_id=did, description="second")
        _log(da, decision_id=did, description="third")

        timeline = da.get_audit_timeline(did)
        timestamps = [e["created_at"] for e in timeline]
        assert timestamps == sorted(timestamps)

    def test_timeline_empty_for_unknown_decision(self, da):
        timeline = da.get_audit_timeline("UNKNOWN")
        assert timeline == []

    def test_multiple_events_for_same_decision_create_timeline(self, da):
        did = "DEC-MULTI"
        events = [
            "snapshot_captured",
            "compliance_checked",
            "gate_evaluated",
            "decision_changed",
        ]
        for et in events:
            _log(da, decision_id=did, event_type=et, description=et)

        timeline = da.get_audit_timeline(did)
        assert len(timeline) == 4
        types = [e["event_type"] for e in timeline]
        assert types == events


# ===========================================================================
# TestGetAuditStats
# ===========================================================================

class TestGetAuditStats:

    def test_empty_stats(self, da):
        stats = da.get_audit_stats()
        assert stats["total"] == 0
        assert stats["by_event_type"] == {}
        assert stats["by_severity"] == {}
        assert stats["by_source_module"] == {}

    def test_stats_with_events(self, da):
        _log(da, event_type="snapshot_captured", severity="info",
             source_module="decision_snapshot", description="s1")
        _log(da, event_type="snapshot_captured", severity="info",
             source_module="decision_snapshot", description="s2")
        _log(da, event_type="conflict_detected", severity="critical",
             source_module="conflict_resolver", description="c1")

        stats = da.get_audit_stats()
        assert stats["total"] == 3
        assert stats["by_event_type"]["snapshot_captured"] == 2
        assert stats["by_event_type"]["conflict_detected"] == 1
        assert stats["by_severity"]["info"] == 2
        assert stats["by_severity"]["critical"] == 1
        assert stats["by_source_module"]["decision_snapshot"] == 2
        assert stats["by_source_module"]["conflict_resolver"] == 1

    def test_stats_by_event_type(self, da):
        for et in ("snapshot_captured", "decision_changed", "cascade_triggered",
                    "conflict_detected", "conflict_resolved"):
            _log(da, event_type=et, description=et)
        stats = da.get_audit_stats()
        assert len(stats["by_event_type"]) == 5

    def test_stats_by_severity(self, da):
        _log(da, severity="info", description="info")
        _log(da, severity="warning", description="warn")
        _log(da, severity="critical", description="crit")
        stats = da.get_audit_stats()
        assert stats["by_severity"] == {"info": 1, "warning": 1, "critical": 1}


# ===========================================================================
# TestExportAuditLog
# ===========================================================================

class TestExportAuditLog:

    def test_export_as_json(self, da):
        _log(da, event_type="snapshot_captured", description="export me")
        exported = da.export_audit_log()
        data = json.loads(exported)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["description"] == "export me"

    def test_export_with_time_filter(self, da):
        before = time.time()
        _log(da, description="included")
        after = time.time()

        _log(da, description="also included")
        much_later = after + 1

        exported = da.export_audit_log(from_time=before, to_time=much_later)
        data = json.loads(exported)
        assert len(data) == 2

    def test_export_empty(self, da):
        exported = da.export_audit_log()
        data = json.loads(exported)
        assert data == []

    def test_export_is_valid_json(self, da):
        _log(da, before_state={"x": 1}, after_state={"y": 2},
             related_ids={"z": 3}, metadata={"w": 4}, description="complex")
        exported = da.export_audit_log()
        # Should not raise
        data = json.loads(exported)
        assert data[0]["before_state"] == {"x": 1}


# ===========================================================================
# TestPurgeOldEntries
# ===========================================================================

class TestPurgeOldEntries:

    def test_purge_old_entries(self, da):
        # Manually insert an old entry
        old_time = time.time() - (400 * 86400)  # 400 days ago
        with da._lock:
            da._conn.execute("""
                INSERT INTO decision_audit_log
                (audit_id, event_type, description, severity, created_at)
                VALUES ('old_entry', 'snapshot_captured', 'old', 'info', ?)
            """, (old_time,))
            da._conn.commit()

        # Insert a recent entry
        _log(da, description="recent")

        deleted = da.purge_old_entries(older_than_days=365)
        assert deleted == 1

        entries = da.get_audit_log()
        assert len(entries) == 1
        assert entries[0]["description"] == "recent"

    def test_purge_does_not_remove_recent(self, da):
        _log(da, description="recent event")
        deleted = da.purge_old_entries(older_than_days=365)
        assert deleted == 0
        entries = da.get_audit_log()
        assert len(entries) == 1

    def test_purge_returns_count(self, da):
        old_time = time.time() - (400 * 86400)
        with da._lock:
            for i in range(5):
                da._conn.execute("""
                    INSERT INTO decision_audit_log
                    (audit_id, event_type, description, severity, created_at)
                    VALUES (?, 'snapshot_captured', ?, 'info', ?)
                """, (f"old_{i}", f"old event {i}", old_time))
            da._conn.commit()

        deleted = da.purge_old_entries(older_than_days=365)
        assert deleted == 5

    def test_purge_emits_event(self, da_bus):
        events = []
        da_bus._event_bus.subscribe(
            "decision.audit.purged", lambda e: events.append(e))

        old_time = time.time() - (400 * 86400)
        with da_bus._lock:
            da_bus._conn.execute("""
                INSERT INTO decision_audit_log
                (audit_id, event_type, description, severity, created_at)
                VALUES ('old_1', 'snapshot_captured', 'old', 'info', ?)
            """, (old_time,))
            da_bus._conn.commit()

        da_bus.purge_old_entries(older_than_days=365)
        assert len(events) == 1
        assert events[0].payload["deleted_count"] == 1


# ===========================================================================
# TestEventOrdering
# ===========================================================================

class TestEventOrdering:

    def test_event_ordering_is_chronological(self, da):
        did = "DEC-ORDER"
        _log(da, decision_id=did, description="first")
        _log(da, decision_id=did, description="second")
        _log(da, decision_id=did, description="third")

        timeline = da.get_audit_timeline(did)
        descriptions = [e["description"] for e in timeline]
        assert descriptions == ["first", "second", "third"]

    def test_get_audit_log_is_newest_first(self, da):
        _log(da, description="oldest")
        _log(da, description="middle")
        _log(da, description="newest")

        entries = da.get_audit_log()
        descriptions = [e["description"] for e in entries]
        assert descriptions == ["newest", "middle", "oldest"]


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_decision_audit(), DecisionAudit)

    def test_idempotent(self):
        a = get_decision_audit()
        b = get_decision_audit()
        assert a is b

    def test_reset_creates_new(self):
        a = get_decision_audit()
        b = reset_decision_audit()
        assert a is not b
        assert isinstance(b, DecisionAudit)

    def test_reset_then_get_returns_new(self):
        a = get_decision_audit()
        b = reset_decision_audit()
        c = get_decision_audit()
        assert b is c
        assert a is not c


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_log_events(self):
        da = DecisionAudit()
        count = 50
        errors: list[Exception] = []

        def log_many(thread_id):
            try:
                for i in range(count):
                    da.log_event(
                        event_type="snapshot_captured",
                        description=f"thread-{thread_id}-event-{i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=log_many, args=(t,))
            for t in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        entries = da.get_audit_log(limit=1000)
        assert len(entries) == 4 * count

    def test_concurrent_read_write(self):
        da = DecisionAudit()
        _log(da, description="seed")
        errors: list[Exception] = []

        def writer():
            try:
                for i in range(20):
                    da.log_event(
                        event_type="decision_changed",
                        description=f"write-{i}",
                    )
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    da.get_audit_log()
                    da.get_audit_stats()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
