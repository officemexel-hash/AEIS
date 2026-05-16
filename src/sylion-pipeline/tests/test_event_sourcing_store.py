"""Tests for sylion.surface.event_sourcing_store -- Event Sourcing Store.

SQLite-backed append-only event stream with snapshots and replay.
Uses in-memory SQLite. Thread-safety tested with retry loops.
Covers:
  1. Instantiation (in-memory, with EventBus)
  2. StoredEvent and Snapshot dataclass defaults
  3. Event append, version auto-increment
  4. Event querying (get_events, get_event)
  5. Snapshots (create, load_from_snapshot, get_latest_snapshot)
  6. Replay
  7. list_streams, get_stats
  8. Concurrent access (thread safety)
  9. Singleton get_event_sourcing_store()
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.surface.event_sourcing_store import (
    EventSourcingStore,
    Snapshot,
    StoredEvent,
    get_event_sourcing_store,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def bus():
    """Fresh EventBus for each test."""
    return EventBus()


@pytest.fixture
def store(bus):
    """Fresh EventSourcingStore (in-memory) with EventBus."""
    return EventSourcingStore(db_path=None, event_bus=bus)


@pytest.fixture
def bare_store():
    """Fresh EventSourcingStore without EventBus."""
    return EventSourcingStore(db_path=None, event_bus=None)


def _retry(fn, max_attempts=8, base_delay=0.05):
    """Retry fn() on transient SQLite errors with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except (sqlite3.OperationalError, sqlite3.InterfaceError):
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))


# ===========================================================================
# StoredEvent dataclass
# ===========================================================================


class TestStoredEvent:
    """Tests for StoredEvent dataclass defaults."""

    def test_auto_generates_event_id(self):
        """When event_id is empty, a hex UUID is auto-generated."""
        evt = StoredEvent()
        assert evt.event_id != ""
        assert len(evt.event_id) == 32  # uuid4 hex

    def test_auto_generates_timestamp(self):
        """When timestamp is 0, current time is used."""
        before = time.time()
        evt = StoredEvent()
        after = time.time()
        assert before <= evt.timestamp <= after

    def test_preserves_explicit_event_id(self):
        """Explicitly set event_id is not overwritten."""
        evt = StoredEvent(event_id="custom-id-123")
        assert evt.event_id == "custom-id-123"

    def test_preserves_explicit_timestamp(self):
        """Explicitly set timestamp is not overwritten."""
        evt = StoredEvent(timestamp=1000.0)
        assert evt.timestamp == 1000.0

    def test_default_payload_and_metadata(self):
        """Defaults to empty dicts."""
        evt = StoredEvent()
        assert evt.payload == {}
        assert evt.metadata == {}


# ===========================================================================
# Snapshot dataclass
# ===========================================================================


class TestSnapshot:
    """Tests for Snapshot dataclass defaults."""

    def test_auto_generates_snapshot_id(self):
        snap = Snapshot()
        assert snap.snapshot_id != ""
        assert len(snap.snapshot_id) == 32

    def test_auto_generates_timestamp(self):
        before = time.time()
        snap = Snapshot()
        after = time.time()
        assert before <= snap.timestamp <= after

    def test_preserves_explicit_fields(self):
        snap = Snapshot(snapshot_id="snap-1", version=5, state={"k": "v"})
        assert snap.snapshot_id == "snap-1"
        assert snap.version == 5
        assert snap.state == {"k": "v"}


# ===========================================================================
# EventSourcingStore instantiation
# ===========================================================================


class TestInstantiation:
    """Tests for EventSourcingStore creation."""

    def test_in_memory_default(self):
        """Default creates in-memory store."""
        s = EventSourcingStore()
        assert s._db_path == ":memory:"

    def test_with_event_bus(self, bus):
        """Store accepts and stores EventBus reference."""
        s = EventSourcingStore(event_bus=bus)
        assert s._event_bus is bus

    def test_without_event_bus(self):
        """Store works without EventBus (no emissions)."""
        s = EventSourcingStore(event_bus=None)
        assert s._event_bus is None

    def test_tables_created(self, store):
        """All three tables are created on init."""
        rows = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {r["name"] for r in rows}
        assert "event_stream" in table_names
        assert "event_log" in table_names
        assert "snapshots" in table_names


# ===========================================================================
# Event append
# ===========================================================================


class TestAppend:
    """Tests for event appending."""

    def test_append_returns_event_info(self, store):
        """append() returns dict with event_id, stream_id, version."""
        result = store.append("stream-1", "item.created", {"name": "foo"})
        assert "event_id" in result
        assert result["stream_id"] == "stream-1"
        assert result["version"] == 1

    def test_version_auto_increments(self, store):
        """Each append on same stream increments version."""
        r1 = store.append("stream-1", "item.created")
        r2 = store.append("stream-1", "item.updated")
        r3 = store.append("stream-1", "item.deleted")
        assert r1["version"] == 1
        assert r2["version"] == 2
        assert r3["version"] == 3

    def test_different_streams_independent_versions(self, store):
        """Different streams have independent version counters."""
        r1 = store.append("s-a", "evt")
        r2 = store.append("s-b", "evt")
        r3 = store.append("s-a", "evt")
        assert r1["version"] == 1
        assert r2["version"] == 1
        assert r3["version"] == 2

    def test_payload_stored_correctly(self, store):
        """Payload dict is serialized and retrievable."""
        store.append("s-1", "test", payload={"key": "value", "nested": {"a": 1}})
        events = store.get_events("s-1")
        assert events[0]["payload"]["key"] == "value"
        assert events[0]["payload"]["nested"]["a"] == 1

    def test_metadata_stored_correctly(self, store):
        """Metadata dict is serialized and retrievable."""
        store.append("s-1", "test", metadata={"source": "api", "trace": "abc"})
        events = store.get_events("s-1")
        assert events[0]["metadata"]["source"] == "api"

    def test_default_payload_and_metadata(self, store):
        """Empty payload/metadata default to empty dicts."""
        store.append("s-1", "test")
        events = store.get_events("s-1")
        assert events[0]["payload"] == {}
        assert events[0]["metadata"] == {}

    def test_emit_on_append(self, store, bus):
        """Appending emits surface.event_sourcing.event_appended to EventBus."""
        store.append("s-emit", "test.evt", {"x": 1})
        results = bus.query(topic="surface.event_sourcing.event_appended")
        assert len(results) >= 1
        payload = json.loads(results[-1]["payload"])
        assert payload["stream_id"] == "s-emit"
        assert payload["event_type"] == "test.evt"
        assert payload["version"] == 1

    def test_no_emit_without_event_bus(self, bare_store):
        """No crash when event_bus is None and events are appended."""
        result = bare_store.append("s-1", "test")
        assert result["version"] == 1


# ===========================================================================
# Event querying
# ===========================================================================


class TestGetEvents:
    """Tests for get_events() and get_event()."""

    def test_get_events_returns_all_for_stream(self, store):
        """get_events returns all events for a given stream."""
        store.append("s-1", "a")
        store.append("s-1", "b")
        store.append("s-2", "c")  # different stream
        events = store.get_events("s-1")
        assert len(events) == 2
        assert events[0]["event_type"] == "a"
        assert events[1]["event_type"] == "b"

    def test_get_events_from_version(self, store):
        """get_events with from_version skips earlier events."""
        store.append("s-1", "v1")
        store.append("s-1", "v2")
        store.append("s-1", "v3")
        events = store.get_events("s-1", from_version=2)
        assert len(events) == 2
        assert events[0]["version"] == 2
        assert events[1]["version"] == 3

    def test_get_events_version_range(self, store):
        """get_events with from_version and to_version returns bounded range."""
        for i in range(5):
            store.append("s-1", f"v{i+1}")
        events = store.get_events("s-1", from_version=2, to_version=4)
        assert len(events) == 3
        assert [e["version"] for e in events] == [2, 3, 4]

    def test_get_events_empty_stream(self, store):
        """get_events returns empty list for nonexistent stream."""
        events = store.get_events("nonexistent")
        assert events == []

    def test_get_event_by_id(self, store):
        """get_event returns single event by event_id."""
        result = store.append("s-1", "test", {"key": "val"})
        event = store.get_event(result["event_id"])
        assert event is not None
        assert event["event_type"] == "test"
        assert event["payload"]["key"] == "val"

    def test_get_event_not_found(self, store):
        """get_event returns None for nonexistent event_id."""
        assert store.get_event("nonexistent-id") is None

    def test_events_ordered_by_version(self, store):
        """Events are returned in version order."""
        store.append("s-1", "third")
        store.append("s-1", "second")
        store.append("s-1", "first")
        events = store.get_events("s-1")
        versions = [e["version"] for e in events]
        assert versions == sorted(versions)


# ===========================================================================
# Snapshots
# ===========================================================================


class TestSnapshots:
    """Tests for snapshot creation and loading."""

    def test_create_snapshot(self, store):
        """create_snapshot returns snapshot info."""
        store.append("s-1", "evt1", {"a": 1})
        store.append("s-1", "evt2", {"b": 2})
        result = store.create_snapshot("s-1")
        assert "snapshot_id" in result
        assert result["stream_id"] == "s-1"
        assert result["version"] == 2

    def test_create_snapshot_empty_stream_returns_error(self, store):
        """create_snapshot on empty stream returns error dict."""
        result = store.create_snapshot("empty-stream")
        assert "error" in result
        assert result["stream_id"] == "empty-stream"

    def test_get_latest_snapshot(self, store):
        """get_latest_snapshot returns the most recent snapshot."""
        store.append("s-1", "e1", {"x": 1})
        store.append("s-1", "e2", {"x": 2})
        store.create_snapshot("s-1")
        snap = store.get_latest_snapshot("s-1")
        assert snap is not None
        assert snap["stream_id"] == "s-1"
        assert snap["version"] == 2

    def test_get_latest_snapshot_none(self, store):
        """get_latest_snapshot returns None when no snapshots exist."""
        assert store.get_latest_snapshot("no-snap") is None

    def test_snapshot_state_contains_all_versions(self, store):
        """Snapshot state accumulates all event payloads keyed by version."""
        store.append("s-1", "e1", {"val": 1})
        store.append("s-1", "e2", {"val": 2})
        store.create_snapshot("s-1")
        snap = store.get_latest_snapshot("s-1")
        assert "v1" in snap["state"]
        assert "v2" in snap["state"]
        assert snap["state"]["v1"]["val"] == 1

    def test_load_from_snapshot_includes_remaining(self, store):
        """load_from_snapshot replays events after snapshot."""
        store.append("s-1", "e1", {"v": 1})
        store.append("s-1", "e2", {"v": 2})
        store.create_snapshot("s-1")
        # Append more events after snapshot
        store.append("s-1", "e3", {"v": 3})
        store.append("s-1", "e4", {"v": 4})

        result = store.load_from_snapshot("s-1")
        assert result["snapshot_version"] == 2
        assert result["remaining_events"] == 2
        assert "v3" in result["state"]
        assert "v4" in result["state"]

    def test_load_from_snapshot_no_snapshot(self, store):
        """load_from_snapshot with no snapshot replays from scratch."""
        store.append("s-1", "e1", {"x": 1})
        store.append("s-1", "e2", {"x": 2})
        result = store.load_from_snapshot("s-1")
        assert result["snapshot_version"] == 0
        assert result["remaining_events"] == 2
        assert "v1" in result["state"]

    def test_snapshot_emits_event(self, store, bus):
        """create_snapshot emits snapshot_created event."""
        store.append("s-1", "e")
        store.create_snapshot("s-1")
        results = bus.query(topic="surface.event_sourcing.snapshot_created")
        assert len(results) >= 1
        payload = json.loads(results[-1]["payload"])
        assert payload["stream_id"] == "s-1"


# ===========================================================================
# Replay
# ===========================================================================


class TestReplay:
    """Tests for replay_stream()."""

    def test_replay_calls_handler_for_each_event(self, store):
        """Handler is called once per event in order."""
        store.append("s-1", "a", {"val": 1})
        store.append("s-1", "b", {"val": 2})
        store.append("s-1", "c", {"val": 3})

        handled = []
        results = store.replay_stream("s-1", lambda evt: handled.append(evt["event_type"]))
        assert len(results) == 3
        assert handled == ["a", "b", "c"]

    def test_replay_returns_handler_results(self, store):
        """replay_stream returns list of handler return values."""
        store.append("s-1", "a", {"val": 1})
        store.append("s-1", "b", {"val": 2})

        results = store.replay_stream("s-1", lambda evt: evt["payload"].get("val", 0) * 10)
        assert results == [10, 20]

    def test_replay_empty_stream(self, store):
        """Replaying empty stream returns empty list."""
        results = store.replay_stream("empty", lambda e: e)
        assert results == []


# ===========================================================================
# list_streams and get_stats
# ===========================================================================


class TestMetadataQueries:
    """Tests for list_streams() and get_stats()."""

    def test_list_streams(self, store):
        """list_streams returns all registered streams."""
        store.append("s-a", "evt")
        store.append("s-b", "evt")
        store.append("s-c", "evt")
        streams = store.list_streams()
        stream_ids = {s["stream_id"] for s in streams}
        assert stream_ids == {"s-a", "s-b", "s-c"}

    def test_list_streams_limit(self, store):
        """list_streams respects the limit parameter."""
        for i in range(5):
            store.append(f"s-{i}", "evt")
        streams = store.list_streams(limit=3)
        assert len(streams) == 3

    def test_list_streams_ordered_by_created_at_desc(self, store):
        """Streams are returned newest first."""
        store.append("first", "evt")
        time.sleep(0.01)
        store.append("second", "evt")
        streams = store.list_streams()
        assert streams[0]["stream_id"] == "second"

    def test_get_stats_initial(self, store):
        """Fresh store has zero stats."""
        stats = store.get_stats()
        assert stats["total_events"] == 0
        assert stats["total_streams"] == 0
        assert stats["total_snapshots"] == 0

    def test_get_stats_after_operations(self, store):
        """Stats reflect appended events and created snapshots."""
        store.append("s-1", "a")
        store.append("s-1", "b")
        store.append("s-2", "c")
        store.create_snapshot("s-1")
        stats = store.get_stats()
        assert stats["total_events"] == 3
        assert stats["total_streams"] == 2
        assert stats["total_snapshots"] == 1


# ===========================================================================
# Concurrent access (thread safety)
# ===========================================================================


class TestThreadSafety:
    """Tests for concurrent access to EventSourcingStore."""

    def test_concurrent_appends_to_same_stream(self, store):
        """Multiple threads appending to same stream all succeed."""
        errors = []
        results = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        def append_one(idx):
            for attempt in range(8):
                try:
                    r = store.append("concurrent-stream", f"evt-{idx}", {"idx": idx})
                    results.append(r)
                    return
                except retriable:
                    if attempt == 7:
                        errors.append(RuntimeError(f"append gave up at {idx}"))
                    time.sleep(0.05 * (2 ** attempt))
                except Exception as e:
                    errors.append(e)
                    return

        threads = [threading.Thread(target=append_one, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20

        # Verify versions are unique and contiguous
        versions = sorted(r["version"] for r in results)
        assert versions == list(range(1, 21))

    def test_concurrent_appends_to_different_streams(self, store):
        """Multiple threads appending to different streams all succeed."""
        errors = []
        results = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        def append_to_stream(stream_id):
            for attempt in range(8):
                try:
                    r = store.append(stream_id, "test", {"s": stream_id})
                    results.append(r)
                    return
                except retriable:
                    if attempt == 7:
                        errors.append(RuntimeError(f"gave up on {stream_id}"))
                    time.sleep(0.05 * (2 ** attempt))
                except Exception as e:
                    errors.append(e)
                    return

        threads = [
            threading.Thread(target=append_to_stream, args=(f"stream-{i}",))
            for i in range(15)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 15

    def test_concurrent_reads_and_writes(self, store):
        """Reads and writes can proceed concurrently without errors."""
        errors = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        # Seed some events
        for i in range(5):
            store.append("rw-stream", f"seed-{i}")

        def writer():
            for i in range(10):
                for attempt in range(8):
                    try:
                        store.append("rw-stream", f"write-{i}", {"i": i})
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError(f"writer gave up at {i}"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        def reader():
            for _ in range(10):
                for attempt in range(8):
                    try:
                        events = store.get_events("rw-stream")
                        assert isinstance(events, list)
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError("reader gave up"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ===========================================================================
# Singleton get_event_sourcing_store()
# ===========================================================================


class TestSingleton:
    """Tests for get_event_sourcing_store() factory function."""

    def test_returns_store_instance(self):
        """Factory returns an EventSourcingStore."""
        import sylion.surface.event_sourcing_store as mod
        mod._store = None  # Reset singleton
        store = get_event_sourcing_store()
        assert isinstance(store, EventSourcingStore)
        mod._store = None  # Clean up

    def test_singleton_returns_same_instance(self):
        """Repeated calls return the same instance."""
        import sylion.surface.event_sourcing_store as mod
        mod._store = None
        s1 = get_event_sourcing_store()
        s2 = get_event_sourcing_store()
        assert s1 is s2
        mod._store = None

    def test_singleton_with_event_bus(self, bus):
        """Factory passes event_bus to the store."""
        import sylion.surface.event_sourcing_store as mod
        mod._store = None
        store = get_event_sourcing_store(event_bus=bus)
        assert store._event_bus is bus
        mod._store = None
