"""Comprehensive tests for sylion.surface.event_sourcing_store module.

Covers: append, get_events, get_event, snapshots, replay,
        load_from_snapshot, list_streams, stats, edge cases,
        thread safety, event emission, append-only enforcement.
"""
import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.surface.event_sourcing_store import (
    EventSourcingStore,
    Snapshot,
    StoredEvent,
    get_event_sourcing_store,
)
import sylion.surface.event_sourcing_store as mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    mod._store = None
    yield
    mod._store = None


@pytest.fixture
def store():
    return EventSourcingStore()


@pytest.fixture
def store_with_events():
    eb = EventBus()
    collected = []
    eb.subscribe("*", lambda e: collected.append(e))
    s = EventSourcingStore(event_bus=eb)
    return s, collected


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class TestStoredEventDataclass:
    def test_auto_id(self):
        e = StoredEvent()
        assert len(e.event_id) == 32

    def test_auto_timestamp(self):
        e = StoredEvent()
        assert e.timestamp > 0

    def test_custom_fields(self):
        e = StoredEvent(
            stream_id="s1", event_type="order.created",
            payload={"item": "widget"}, metadata={"source": "api"},
        )
        assert e.stream_id == "s1"
        assert e.event_type == "order.created"


class TestSnapshotDataclass:
    def test_auto_id(self):
        s = Snapshot()
        assert len(s.snapshot_id) == 32

    def test_auto_timestamp(self):
        s = Snapshot()
        assert s.timestamp > 0

    def test_custom_fields(self):
        s = Snapshot(stream_id="s1", version=5, state={"v1": {"x": 1}})
        assert s.version == 5
        assert s.state == {"v1": {"x": 1}}


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------

class TestAppend:
    def test_first_event_version_1(self, store):
        r = store.append("stream-1", "order.created", {"item": "widget"})
        assert r["version"] == 1
        assert r["stream_id"] == "stream-1"
        assert len(r["event_id"]) == 32

    def test_auto_increment_version(self, store):
        store.append("s1", "evt.a", {"v": 1})
        store.append("s1", "evt.b", {"v": 2})
        r = store.append("s1", "evt.c", {"v": 3})
        assert r["version"] == 3

    def test_append_with_metadata(self, store):
        r = store.append("s1", "evt", {"data": 1}, {"correlation_id": "abc"})
        evt = store.get_event(r["event_id"])
        assert evt["metadata"] == {"correlation_id": "abc"}

    def test_append_empty_payload(self, store):
        r = store.append("s1", "evt")
        evt = store.get_event(r["event_id"])
        assert evt["payload"] == {}

    def test_multiple_streams(self, store):
        store.append("sa", "evt.a", {"stream": "a"})
        store.append("sb", "evt.b", {"stream": "b"})
        events_a = store.get_events("sa")
        events_b = store.get_events("sb")
        assert len(events_a) == 1
        assert len(events_b) == 1

    def test_append_returns_event_id(self, store):
        r = store.append("s1", "evt")
        assert len(r["event_id"]) == 32


# ---------------------------------------------------------------------------
# Get events
# ---------------------------------------------------------------------------

class TestGetEvents:
    def test_get_all_events(self, store):
        store.append("s1", "evt.a", {"v": 1})
        store.append("s1", "evt.b", {"v": 2})
        store.append("s1", "evt.c", {"v": 3})
        events = store.get_events("s1")
        assert len(events) == 3
        assert events[0]["version"] == 1
        assert events[2]["version"] == 3

    def test_get_events_from_version(self, store):
        store.append("s2", "evt.a", {})
        store.append("s2", "evt.b", {})
        store.append("s2", "evt.c", {})
        events = store.get_events("s2", from_version=2)
        assert len(events) == 2
        assert events[0]["version"] == 2

    def test_get_events_range(self, store):
        for i in range(5):
            store.append("s3", f"evt.{i}", {"i": i})
        events = store.get_events("s3", from_version=2, to_version=4)
        assert len(events) == 3
        versions = [e["version"] for e in events]
        assert versions == [2, 3, 4]

    def test_get_events_empty_stream(self, store):
        events = store.get_events("nonexistent")
        assert events == []

    def test_get_events_payload_deserialized(self, store):
        store.append("s1", "evt", {"key": "val", "nested": {"a": 1}})
        events = store.get_events("s1")
        assert events[0]["payload"] == {"key": "val", "nested": {"a": 1}}

    def test_get_events_metadata_deserialized(self, store):
        store.append("s1", "evt", {}, {"trace": "xyz"})
        events = store.get_events("s1")
        assert events[0]["metadata"] == {"trace": "xyz"}


# ---------------------------------------------------------------------------
# Get single event
# ---------------------------------------------------------------------------

class TestGetEvent:
    def test_get_event_by_id(self, store):
        r = store.append("s1", "order.placed", {"item": "book"})
        evt = store.get_event(r["event_id"])
        assert evt is not None
        assert evt["event_type"] == "order.placed"
        assert evt["payload"] == {"item": "book"}

    def test_get_event_not_found(self, store):
        assert store.get_event("missing") is None


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

class TestSnapshots:
    def test_create_snapshot(self, store):
        store.append("s3", "evt.a", {"data": "x"})
        store.append("s3", "evt.b", {"data": "y"})
        snap = store.create_snapshot("s3")
        assert snap["version"] == 2
        assert len(snap["snapshot_id"]) == 32
        assert snap["stream_id"] == "s3"

    def test_get_latest_snapshot(self, store):
        store.append("s3", "evt.a", {"data": "x"})
        store.append("s3", "evt.b", {"data": "y"})
        store.create_snapshot("s3")
        latest = store.get_latest_snapshot("s3")
        assert latest is not None
        assert latest["version"] == 2

    def test_snapshot_state_content(self, store):
        store.append("s3", "evt.a", {"x": 1})
        store.append("s3", "evt.b", {"y": 2})
        store.create_snapshot("s3")
        snap = store.get_latest_snapshot("s3")
        assert "v1" in snap["state"]
        assert "v2" in snap["state"]
        assert snap["state"]["v1"] == {"x": 1}

    def test_snapshot_empty_stream(self, store):
        result = store.create_snapshot("empty_stream")
        assert "error" in result
        assert "no events" in result["error"]

    def test_multiple_snapshots(self, store):
        store.append("s3", "evt.a", {"v": 1})
        store.create_snapshot("s3")
        store.append("s3", "evt.b", {"v": 2})
        store.create_snapshot("s3")
        snap = store.get_latest_snapshot("s3")
        assert snap["version"] == 2

    def test_snapshot_no_stream(self, store):
        result = store.get_latest_snapshot("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# Load from snapshot
# ---------------------------------------------------------------------------

class TestLoadFromSnapshot:
    def test_load_with_snapshot(self, store):
        store.append("s4", "evt.a", {"a": 1})
        store.append("s4", "evt.b", {"b": 2})
        store.create_snapshot("s4")
        store.append("s4", "evt.c", {"c": 3})

        loaded = store.load_from_snapshot("s4")
        assert loaded["snapshot_version"] == 2
        assert loaded["remaining_events"] == 1
        assert "v3" in loaded["state"]

    def test_load_without_snapshot(self, store):
        store.append("s5", "evt.a", {"a": 1})
        store.append("s5", "evt.b", {"b": 2})
        loaded = store.load_from_snapshot("s5")
        assert loaded["snapshot_version"] == 0
        assert loaded["remaining_events"] == 2

    def test_load_empty_stream(self, store):
        loaded = store.load_from_snapshot("nonexistent")
        assert loaded["state"] == {}
        assert loaded["remaining_events"] == 0


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

class TestReplay:
    def test_replay_basic(self, store):
        store.append("s5", "evt.a", {"val": 10})
        store.append("s5", "evt.b", {"val": 20})
        results = store.replay_stream("s5", lambda e: e["payload"].get("val", 0))
        assert results == [10, 20]

    def test_replay_empty_stream(self, store):
        results = store.replay_stream("empty", lambda e: e)
        assert results == []

    def test_replay_handler_collects_types(self, store):
        store.append("s6", "order.created", {"id": 1})
        store.append("s6", "order.shipped", {"id": 1})
        types = store.replay_stream("s6", lambda e: e["event_type"])
        assert types == ["order.created", "order.shipped"]


# ---------------------------------------------------------------------------
# List streams
# ---------------------------------------------------------------------------

class TestListStreams:
    def test_list_streams(self, store):
        store.append("sa", "evt", {})
        store.append("sb", "evt", {})
        streams = store.list_streams()
        assert len(streams) >= 2

    def test_list_streams_limit(self, store):
        for i in range(10):
            store.append(f"stream_{i}", "evt", {})
        streams = store.list_streams(limit=3)
        assert len(streams) == 3


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_empty_stats(self, store):
        stats = store.get_stats()
        assert stats["total_events"] == 0
        assert stats["total_streams"] == 0
        assert stats["total_snapshots"] == 0

    def test_stats_with_data(self, store):
        store.append("s1", "evt.a", {})
        store.append("s1", "evt.b", {})
        store.create_snapshot("s1")
        stats = store.get_stats()
        assert stats["total_events"] == 2
        assert stats["total_streams"] == 1
        assert stats["total_snapshots"] == 1


# ---------------------------------------------------------------------------
# Append-only enforcement
# ---------------------------------------------------------------------------

class TestAppendOnly:
    def test_events_never_update(self, store):
        r = store.append("s6", "evt.original", {"original": True})
        evt = store.get_event(r["event_id"])
        assert evt["payload"] == {"original": True}
        # Appending a new event does not change the original
        store.append("s6", "evt.new", {"new": True})
        evt = store.get_event(r["event_id"])
        assert evt["payload"] == {"original": True}

    def test_version_ordering_preserved(self, store):
        ids = []
        for i in range(5):
            r = store.append("s7", f"evt.{i}", {"i": i})
            ids.append(r["event_id"])
        events = store.get_events("s7")
        for idx, evt in enumerate(events):
            assert evt["version"] == idx + 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_append_emits_event(self, store_with_events):
        store, events = store_with_events
        store.append("s1", "evt.a", {})
        assert any("event_appended" in e.topic for e in events)

    def test_snapshot_emits_event(self, store_with_events):
        store, events = store_with_events
        store.append("s1", "evt", {})
        store.create_snapshot("s1")
        assert any("snapshot_created" in e.topic for e in events)

    def test_no_event_bus_no_crash(self, store):
        store.append("s1", "evt", {})
        store.create_snapshot("s1")


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_get_store_returns_same(self):
        s1 = get_event_sourcing_store()
        s2 = get_event_sourcing_store()
        assert s1 is s2


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_appends(self, store):
        errors = []

        def append_many(stream_id, count):
            try:
                for i in range(count):
                    store.append(stream_id, f"evt.{i}", {"i": i})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=append_many, args=(f"s{i}", 10))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = store.get_stats()
        assert stats["total_events"] == 50
        assert stats["total_streams"] == 5

    def test_concurrent_appends_same_stream(self, store):
        errors = []

        def append_to_stream(idx):
            try:
                store.append("shared", f"evt.{idx}", {"idx": idx})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=append_to_stream, args=(i,))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        events = store.get_events("shared")
        assert len(events) == 20
        versions = sorted(e["version"] for e in events)
        assert versions == list(range(1, 21))
