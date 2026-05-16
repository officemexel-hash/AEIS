"""
tests/test_evidence_timeline.py -- Evidence Timeline module tests

Covers:
- Timeline CRUD (create, get, list, delete)
- Event creation with validation
- Event retrieval (list, filter by type, filter by since, single get)
- Cascade delete (events removed when timeline deleted)
- Event count tracking on timelines
- Stats aggregation
- EventBus integration
- Thread safety (concurrent writes)
- Singleton get/reset
- Edge cases (nonexistent IDs, empty timelines, invalid event types)
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.evidence_timeline import (
    VALID_EVENT_TYPES,
    EvidenceTimeline,
    get_evidence_timeline,
    reset_evidence_timeline,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def et(bus):
    """Fresh EvidenceTimeline with in-memory DB and event bus."""
    return EvidenceTimeline(event_bus=bus)


@pytest.fixture
def et_no_bus():
    """EvidenceTimeline without an event bus."""
    return EvidenceTimeline()


def _create_timeline(et, name="Test Timeline", desc="A test timeline"):
    return et.create_timeline(name, desc)


def _add_event(et, timeline_id, event_type="decision", title="Test Event", **kwargs):
    return et.add_event(timeline_id, event_type, title, **kwargs)


# =====================================================================
# Timeline Creation
# =====================================================================

class TestTimelineCreation:

    def test_create_timeline_basic(self, et):
        tl = _create_timeline(et)
        assert tl["timeline_id"]
        assert tl["name"] == "Test Timeline"
        assert tl["description"] == "A test timeline"
        assert tl["created_at"] > 0
        assert tl["updated_at"] > 0
        assert tl["event_count"] == 0

    def test_create_timeline_default_description(self, et):
        tl = et.create_timeline("Empty Desc")
        assert tl["description"] == ""

    def test_create_timeline_custom_description(self, et):
        tl = et.create_timeline("Audit Trail", "Full audit trail for D4 decision")
        assert tl["name"] == "Audit Trail"
        assert tl["description"] == "Full audit trail for D4 decision"

    def test_create_multiple_timelines(self, et):
        tl1 = et.create_timeline("First")
        tl2 = et.create_timeline("Second")
        tl3 = et.create_timeline("Third")
        assert tl1["timeline_id"] != tl2["timeline_id"]
        assert tl2["timeline_id"] != tl3["timeline_id"]
        timelines = et.list_timelines()
        assert len(timelines) == 3

    def test_create_timeline_unique_ids(self, et):
        ids = set()
        for i in range(20):
            tl = et.create_timeline(f"TL-{i}")
            ids.add(tl["timeline_id"])
        assert len(ids) == 20

    def test_created_at_reasonable(self, et):
        before = time.time()
        tl = et.create_timeline("Timecheck")
        after = time.time()
        assert before <= tl["created_at"] <= after


# =====================================================================
# Timeline Get
# =====================================================================

class TestTimelineGet:

    def test_get_existing_timeline(self, et):
        created = _create_timeline(et)
        fetched = et.get_timeline(created["timeline_id"])
        assert fetched is not None
        assert fetched["timeline_id"] == created["timeline_id"]
        assert fetched["name"] == created["name"]

    def test_get_nonexistent_timeline(self, et):
        assert et.get_timeline("does-not-exist") is None

    def test_get_returns_all_fields(self, et):
        tl = et.create_timeline("Fields", "desc")
        fetched = et.get_timeline(tl["timeline_id"])
        assert set(fetched.keys()) >= {
            "timeline_id", "name", "description",
            "created_at", "updated_at", "event_count"
        }


# =====================================================================
# Timeline List
# =====================================================================

class TestTimelineList:

    def test_list_empty(self, et):
        result = et.list_timelines()
        assert result == []

    def test_list_all_timelines(self, et):
        et.create_timeline("A")
        et.create_timeline("B")
        et.create_timeline("C")
        result = et.list_timelines()
        assert len(result) == 3

    def test_list_respects_limit(self, et):
        for i in range(10):
            et.create_timeline(f"TL-{i}")
        result = et.list_timelines(limit=5)
        assert len(result) == 5

    def test_list_ordered_by_updated_at_desc(self, et):
        tl1 = et.create_timeline("First")
        tl2 = et.create_timeline("Second")
        # Adding an event to tl1 updates its updated_at
        et.add_event(tl1["timeline_id"], "decision", "Late event")
        result = et.list_timelines()
        assert result[0]["timeline_id"] == tl1["timeline_id"]


# =====================================================================
# Timeline Delete
# =====================================================================

class TestTimelineDelete:

    def test_delete_existing_timeline(self, et):
        tl = _create_timeline(et)
        assert et.delete_timeline(tl["timeline_id"]) is True
        assert et.get_timeline(tl["timeline_id"]) is None

    def test_delete_nonexistent_timeline(self, et):
        assert et.delete_timeline("nonexistent") is False

    def test_delete_cascades_events(self, et):
        tl = _create_timeline(et)
        _add_event(et, tl["timeline_id"], "decision", "E1")
        _add_event(et, tl["timeline_id"], "evidence", "E2")
        _add_event(et, tl["timeline_id"], "action", "E3")

        assert len(et.get_events(tl["timeline_id"])) == 3

        et.delete_timeline(tl["timeline_id"])

        # Events should be gone
        assert et.get_events(tl["timeline_id"]) == []

    def test_delete_one_does_not_affect_others(self, et):
        tl1 = et.create_timeline("Keep")
        tl2 = et.create_timeline("Delete")
        _add_event(et, tl1["timeline_id"], "decision", "Keep event")
        _add_event(et, tl2["timeline_id"], "decision", "Delete event")

        et.delete_timeline(tl2["timeline_id"])

        assert et.get_timeline(tl1["timeline_id"]) is not None
        assert len(et.get_events(tl1["timeline_id"])) == 1


# =====================================================================
# Event Creation
# =====================================================================

class TestEventCreation:

    def test_add_event_basic(self, et):
        tl = _create_timeline(et)
        ev = _add_event(et, tl["timeline_id"], "decision", "Gate passed")
        assert ev["event_id"]
        assert ev["timeline_id"] == tl["timeline_id"]
        assert ev["event_type"] == "decision"
        assert ev["title"] == "Gate passed"
        assert ev["timestamp"] > 0

    def test_add_event_with_all_fields(self, et):
        tl = _create_timeline(et)
        ev = et.add_event(
            tl["timeline_id"],
            event_type="evidence",
            title="Evidence collected",
            description="Collected test results from pipeline run",
            source_module="pipeline.runner",
            actor="agent-01",
            evidence_ref="pack-abc123",
            metadata={"score": 0.95, "tags": ["unit", "integration"]},
        )
        assert ev["description"] == "Collected test results from pipeline run"
        assert ev["source_module"] == "pipeline.runner"
        assert ev["actor"] == "agent-01"
        assert ev["evidence_ref"] == "pack-abc123"
        assert ev["metadata"]["score"] == 0.95
        assert "unit" in ev["metadata"]["tags"]

    def test_add_event_defaults(self, et):
        tl = _create_timeline(et)
        ev = et.add_event(tl["timeline_id"], "observation", "Saw something")
        assert ev["description"] == ""
        assert ev["source_module"] == ""
        assert ev["actor"] == ""
        assert ev["evidence_ref"] == ""
        assert ev["metadata"] == {}

    @pytest.mark.parametrize("etype", VALID_EVENT_TYPES)
    def test_add_all_valid_event_types(self, et, etype):
        tl = _create_timeline(et)
        ev = et.add_event(tl["timeline_id"], etype, f"{etype} event")
        assert ev["event_type"] == etype

    def test_add_event_invalid_type(self, et):
        tl = _create_timeline(et)
        with pytest.raises(ValueError, match="Invalid event_type"):
            et.add_event(tl["timeline_id"], "invalid_type", "Bad")

    def test_add_event_to_nonexistent_timeline(self, et):
        with pytest.raises(ValueError, match="Timeline not found"):
            et.add_event("nonexistent", "decision", "Nowhere")

    def test_add_event_updates_event_count(self, et):
        tl = _create_timeline(et)
        assert tl["event_count"] == 0

        et.add_event(tl["timeline_id"], "decision", "E1")
        fetched = et.get_timeline(tl["timeline_id"])
        assert fetched["event_count"] == 1

        et.add_event(tl["timeline_id"], "evidence", "E2")
        fetched = et.get_timeline(tl["timeline_id"])
        assert fetched["event_count"] == 2

    def test_add_event_updates_updated_at(self, et):
        tl = _create_timeline(et)
        original_updated = tl["updated_at"]
        time.sleep(0.01)
        et.add_event(tl["timeline_id"], "decision", "E1")
        fetched = et.get_timeline(tl["timeline_id"])
        assert fetched["updated_at"] >= original_updated

    def test_metadata_serialization(self, et):
        tl = _create_timeline(et)
        meta = {"key": "value", "nested": {"a": 1}, "list": [1, 2, 3]}
        ev = et.add_event(tl["timeline_id"], "decision", "Meta", metadata=meta)
        assert ev["metadata"] == meta

    def test_metadata_none_becomes_empty_dict(self, et):
        tl = _create_timeline(et)
        ev = et.add_event(tl["timeline_id"], "decision", "No meta", metadata=None)
        assert ev["metadata"] == {}


# =====================================================================
# Event Retrieval
# =====================================================================

class TestEventRetrieval:

    def test_get_events_ordered_by_timestamp(self, et):
        tl = _create_timeline(et)
        ev1 = et.add_event(tl["timeline_id"], "decision", "First")
        ev2 = et.add_event(tl["timeline_id"], "evidence", "Second")
        ev3 = et.add_event(tl["timeline_id"], "action", "Third")

        events = et.get_events(tl["timeline_id"])
        assert len(events) == 3
        assert events[0]["event_id"] == ev1["event_id"]
        assert events[1]["event_id"] == ev2["event_id"]
        assert events[2]["event_id"] == ev3["event_id"]

    def test_get_events_filter_by_type(self, et):
        tl = _create_timeline(et)
        et.add_event(tl["timeline_id"], "decision", "D1")
        et.add_event(tl["timeline_id"], "evidence", "E1")
        et.add_event(tl["timeline_id"], "decision", "D2")
        et.add_event(tl["timeline_id"], "action", "A1")

        decisions = et.get_events(tl["timeline_id"], event_type="decision")
        assert len(decisions) == 2
        assert all(e["event_type"] == "decision" for e in decisions)

    def test_get_events_filter_by_since(self, et):
        tl = _create_timeline(et)
        et.add_event(tl["timeline_id"], "decision", "Old")
        cutoff = time.time()
        time.sleep(0.01)
        et.add_event(tl["timeline_id"], "decision", "New")

        events = et.get_events(tl["timeline_id"], since=cutoff)
        assert len(events) == 1
        assert events[0]["title"] == "New"

    def test_get_events_limit(self, et):
        tl = _create_timeline(et)
        for i in range(10):
            et.add_event(tl["timeline_id"], "decision", f"Event {i}")

        events = et.get_events(tl["timeline_id"], limit=3)
        assert len(events) == 3

    def test_get_events_empty_timeline(self, et):
        tl = _create_timeline(et)
        events = et.get_events(tl["timeline_id"])
        assert events == []

    def test_get_events_nonexistent_timeline(self, et):
        events = et.get_events("nonexistent")
        assert events == []

    def test_get_events_combined_filters(self, et):
        tl = _create_timeline(et)
        et.add_event(tl["timeline_id"], "decision", "D-old")
        et.add_event(tl["timeline_id"], "evidence", "E-old")
        cutoff = time.time()
        time.sleep(0.01)
        et.add_event(tl["timeline_id"], "decision", "D-new")
        et.add_event(tl["timeline_id"], "evidence", "E-new")

        events = et.get_events(tl["timeline_id"], event_type="decision", since=cutoff)
        assert len(events) == 1
        assert events[0]["title"] == "D-new"


# =====================================================================
# Single Event Get
# =====================================================================

class TestGetEvent:

    def test_get_existing_event(self, et):
        tl = _create_timeline(et)
        created = et.add_event(tl["timeline_id"], "milestone", "MS reached")
        fetched = et.get_event(created["event_id"])
        assert fetched is not None
        assert fetched["event_id"] == created["event_id"]
        assert fetched["title"] == "MS reached"
        assert fetched["event_type"] == "milestone"

    def test_get_nonexistent_event(self, et):
        assert et.get_event("does-not-exist") is None

    def test_get_event_has_all_fields(self, et):
        tl = _create_timeline(et)
        ev = et.add_event(
            tl["timeline_id"], "alert", "Alert!", description="desc",
            source_module="mod", actor="act", evidence_ref="ref",
            metadata={"k": "v"},
        )
        fetched = et.get_event(ev["event_id"])
        expected_keys = {
            "event_id", "timeline_id", "event_type", "title",
            "description", "source_module", "actor", "timestamp",
            "evidence_ref", "metadata",
        }
        assert expected_keys <= set(fetched.keys())


# =====================================================================
# Stats
# =====================================================================

class TestStats:

    def test_stats_empty(self, et):
        stats = et.get_stats()
        assert stats["timeline_count"] == 0
        assert stats["event_count"] == 0
        assert stats["by_event_type"] == {}

    def test_stats_after_creation(self, et):
        et.create_timeline("TL1")
        et.create_timeline("TL2")
        stats = et.get_stats()
        assert stats["timeline_count"] == 2
        assert stats["event_count"] == 0

    def test_stats_with_events(self, et):
        tl = et.create_timeline("TL")
        et.add_event(tl["timeline_id"], "decision", "D1")
        et.add_event(tl["timeline_id"], "decision", "D2")
        et.add_event(tl["timeline_id"], "evidence", "E1")

        stats = et.get_stats()
        assert stats["timeline_count"] == 1
        assert stats["event_count"] == 3
        assert stats["by_event_type"]["decision"] == 2
        assert stats["by_event_type"]["evidence"] == 1

    def test_stats_after_delete(self, et):
        tl1 = et.create_timeline("Keep")
        tl2 = et.create_timeline("Delete")
        et.add_event(tl1["timeline_id"], "decision", "Keep event")
        et.add_event(tl2["timeline_id"], "action", "Delete event")

        et.delete_timeline(tl2["timeline_id"])

        stats = et.get_stats()
        assert stats["timeline_count"] == 1
        assert stats["event_count"] == 1

    def test_stats_multiple_event_types(self, et):
        tl = et.create_timeline("All Types")
        for etype in VALID_EVENT_TYPES:
            et.add_event(tl["timeline_id"], etype, f"{etype} event")

        stats = et.get_stats()
        assert stats["event_count"] == len(VALID_EVENT_TYPES)
        for etype in VALID_EVENT_TYPES:
            assert stats["by_event_type"][etype] == 1


# =====================================================================
# EventBus Integration
# =====================================================================

class TestEventBusIntegration:

    def test_create_timeline_emits_event(self, bus):
        captured = []
        bus.subscribe("timeline.created", lambda e: captured.append(e))
        et = EvidenceTimeline(event_bus=bus)
        et.create_timeline("Emit Test")

        assert len(captured) == 1
        assert captured[0].payload["name"] == "Emit Test"
        assert captured[0].payload["timeline_id"]

    def test_add_event_emits_event(self, bus):
        captured = []
        bus.subscribe("timeline.event_added", lambda e: captured.append(e))
        et = EvidenceTimeline(event_bus=bus)
        tl = et.create_timeline("Emit TL")
        et.add_event(tl["timeline_id"], "decision", "Decide")

        assert len(captured) == 1
        assert captured[0].payload["event_type"] == "decision"
        assert captured[0].payload["timeline_id"] == tl["timeline_id"]
        assert captured[0].source_module == "governance.evidence_timeline"

    def test_no_bus_no_error(self, et_no_bus):
        tl = et_no_bus.create_timeline("No Bus")
        ev = et_no_bus.add_event(tl["timeline_id"], "action", "Works")
        assert tl["timeline_id"]
        assert ev["event_id"]

    def test_event_id_present_in_payload(self, bus):
        captured = []
        bus.subscribe("timeline.event_added", lambda e: captured.append(e))
        et = EvidenceTimeline(event_bus=bus)
        tl = et.create_timeline("Payload TL")
        et.add_event(tl["timeline_id"], "alert", "Alert!")

        assert captured[0].payload["event_id"]


# =====================================================================
# Thread Safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_event_adds(self, et):
        tl = _create_timeline(et)
        n = 50
        errors = []

        def add_events(start):
            try:
                for i in range(start, start + 10):
                    et.add_event(tl["timeline_id"], "decision", f"Thread-{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_events, args=(i * 10,)) for i in range(n // 10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        events = et.get_events(tl["timeline_id"])
        assert len(events) == n

    def test_concurrent_timeline_creates(self, et):
        errors = []

        def create_tl(idx):
            try:
                et.create_timeline(f"Concurrent-{idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=create_tl, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(et.list_timelines()) == 20

    def test_concurrent_create_and_add(self, et):
        errors = []

        def worker(idx):
            try:
                tl = et.create_timeline(f"TL-{idx}")
                et.add_event(tl["timeline_id"], "decision", f"Event-{idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = et.get_stats()
        assert stats["timeline_count"] == 20
        assert stats["event_count"] == 20


# =====================================================================
# Singleton
# =====================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        reset_evidence_timeline()
        inst = get_evidence_timeline()
        assert isinstance(inst, EvidenceTimeline)

    def test_get_returns_same_instance(self):
        reset_evidence_timeline()
        inst1 = get_evidence_timeline()
        inst2 = get_evidence_timeline()
        assert inst1 is inst2

    def test_reset_creates_new_instance(self):
        reset_evidence_timeline()
        inst1 = get_evidence_timeline()
        inst2 = reset_evidence_timeline()
        assert inst1 is not inst2

    def test_reset_with_params(self):
        bus = EventBus()
        inst = reset_evidence_timeline(event_bus=bus)
        assert inst._event_bus is bus


# =====================================================================
# Edge Cases
# =====================================================================

class TestEdgeCases:

    def test_empty_name(self, et):
        tl = et.create_timeline("")
        assert tl["name"] == ""
        assert tl["timeline_id"]

    def test_long_name_and_description(self, et):
        long_name = "A" * 500
        long_desc = "B" * 1000
        tl = et.create_timeline(long_name, long_desc)
        fetched = et.get_timeline(tl["timeline_id"])
        assert fetched["name"] == long_name
        assert fetched["description"] == long_desc

    def test_special_characters_in_fields(self, et):
        tl = et.create_timeline("TL with 'quotes' and \"doubles\"")
        ev = et.add_event(
            tl["timeline_id"], "decision", "Title with <html>",
            description="Line1\nLine2\tTabbed",
            metadata={"key": "val with 'quotes'"},
        )
        fetched = et.get_event(ev["event_id"])
        assert fetched["title"] == "Title with <html>"
        assert "Line1" in fetched["description"]
        assert fetched["metadata"]["key"] == "val with 'quotes'"

    def test_unicode_fields(self, et):
        tl = et.create_timeline("Chronologie des decisions", "Audite de conformite")
        ev = et.add_event(
            tl["timeline_id"], "milestone", "Revue complete",
            actor="Analyste",
            metadata={"note": "Conforme aux normes"},
        )
        fetched = et.get_event(ev["event_id"])
        assert fetched["title"] == "Revue complete"
        assert fetched["actor"] == "Analyste"

    def test_large_metadata(self, et):
        tl = _create_timeline(et)
        big_meta = {f"key_{i}": f"value_{i}" for i in range(100)}
        ev = et.add_event(tl["timeline_id"], "decision", "Big Meta", metadata=big_meta)
        fetched = et.get_event(ev["event_id"])
        assert len(fetched["metadata"]) == 100

    def test_zero_limit_list(self, et):
        et.create_timeline("TL")
        result = et.list_timelines(limit=0)
        assert result == []

    def test_get_events_zero_limit(self, et):
        tl = _create_timeline(et)
        et.add_event(tl["timeline_id"], "decision", "E1")
        events = et.get_events(tl["timeline_id"], limit=0)
        assert events == []

    def test_multiple_timelines_independent_events(self, et):
        tl1 = et.create_timeline("Alpha")
        tl2 = et.create_timeline("Beta")

        et.add_event(tl1["timeline_id"], "decision", "Alpha-1")
        et.add_event(tl1["timeline_id"], "evidence", "Alpha-2")
        et.add_event(tl2["timeline_id"], "action", "Beta-1")

        assert len(et.get_events(tl1["timeline_id"])) == 2
        assert len(et.get_events(tl2["timeline_id"])) == 1

        stats = et.get_stats()
        assert stats["event_count"] == 3
