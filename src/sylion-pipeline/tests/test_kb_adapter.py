"""
SYLION Memory KB Adapter -- Comprehensive Unit Tests

Tests for sylion.memory.kb_adapter.KBAdapter:
  - register_source / get_source / list_sources CRUD
  - query (stub) and index (stub)
  - get_stats aggregation
  - EventBus integration
  - error cases: nonexistent sources, empty states
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.memory.kb_adapter import KBAdapter, KBSource, KBQuery


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def adapter():
    """Fresh in-memory KBAdapter."""
    return KBAdapter()


@pytest.fixture
def adapter_with_bus():
    """KBAdapter with EventBus + captured events."""
    bus = EventBus()
    captured: list[SylionEvent] = []
    bus.subscribe("*", captured.append)
    kba = KBAdapter(event_bus=bus)
    return kba, captured


@pytest.fixture
def populated_adapter(adapter):
    """Adapter with 3 registered sources."""
    adapter.register_source(
        "src-files", "File Store", source_type="file", path="/data/files",
        config={"format": "json"},
    )
    adapter.register_source(
        "src-api", "Remote API", source_type="api", path="https://api.example.com",
        config={"timeout": 30},
    )
    adapter.register_source(
        "src-vector", "Vector DB", source_type="vector", path="localhost:6333",
        config={"dimension": 768},
    )
    return adapter


# =====================================================================
# Source CRUD Tests
# =====================================================================

class TestKBSourceRegister:

    def test_register_returns_source_dict(self, adapter):
        result = adapter.register_source(
            "s1", "Test KB", source_type="file", path="/data",
        )
        assert result["source_id"] == "s1"
        assert result["name"] == "Test KB"
        assert result["source_type"] == "file"
        assert result["path"] == "/data"
        assert result["active"] == 1
        assert result["last_indexed"] == 0.0

    def test_register_with_config(self, adapter):
        config = {"batch_size": 100, "encoding": "utf-8"}
        result = adapter.register_source("s2", "Configured", config=config)
        assert result["config"] == config

    def test_register_upserts(self, adapter):
        adapter.register_source("s-up", name="Original")
        adapter.register_source("s-up", name="Updated")
        src = adapter.get_source("s-up")
        assert src["name"] == "Updated"

    def test_register_defaults(self, adapter):
        result = adapter.register_source("s-def", name="Default")
        assert result["source_type"] == "file"
        assert result["path"] == ""
        assert result["config"] == {}


class TestKBSourceGet:

    def test_get_existing_source(self, populated_adapter):
        src = populated_adapter.get_source("src-files")
        assert src is not None
        assert src["name"] == "File Store"
        assert src["source_type"] == "file"

    def test_get_nonexistent_source(self, adapter):
        assert adapter.get_source("ghost") is None

    def test_get_returns_parsed_config(self, populated_adapter):
        src = populated_adapter.get_source("src-api")
        assert src["config"]["timeout"] == 30

    def test_get_preserves_all_fields(self, populated_adapter):
        src = populated_adapter.get_source("src-vector")
        assert src["source_id"] == "src-vector"
        assert src["config"]["dimension"] == 768
        assert src["path"] == "localhost:6333"


class TestKBSourceList:

    def test_list_all_active(self, populated_adapter):
        sources = populated_adapter.list_sources(active_only=True)
        assert len(sources) == 3

    def test_list_includes_inactive(self, adapter):
        adapter.register_source("active-1", "Active One")
        # Manually deactivate
        adapter._conn.execute(
            "UPDATE kb_sources SET active = 0 WHERE source_id = ?", ("active-1",)
        )
        adapter._conn.commit()

        active = adapter.list_sources(active_only=True)
        all_src = adapter.list_sources(active_only=False)
        assert len(active) == 0
        assert len(all_src) == 1

    def test_list_ordered_by_name(self, adapter):
        adapter.register_source("z-src", name="Zebra")
        adapter.register_source("a-src", name="Alpha")
        adapter.register_source("m-src", name="Middle")
        sources = adapter.list_sources()
        names = [s["name"] for s in sources]
        assert names == sorted(names)

    def test_list_empty_adapter(self, adapter):
        assert adapter.list_sources() == []


# =====================================================================
# Query Tests (stub)
# =====================================================================

class TestKBQuery:

    def test_query_returns_empty_list(self, populated_adapter):
        results = populated_adapter.query("src-files", "find something")
        assert isinstance(results, list)
        assert len(results) == 0  # Phase 1 stub

    def test_query_logs_audit_entry(self, populated_adapter):
        populated_adapter.query("src-api", "search terms")
        # Check that a query was logged via stats
        stats = populated_adapter.get_stats()
        assert stats["total_queries"] == 1

    def test_multiple_queries_accumulate(self, populated_adapter):
        for i in range(5):
            populated_adapter.query("src-files", f"query {i}")
        stats = populated_adapter.get_stats()
        assert stats["total_queries"] == 5

    def test_query_nonexistent_source_still_logs(self, adapter):
        # Query does not validate source_id -- it just logs the query
        results = adapter.query("nonexistent", "test")
        assert results == []


# =====================================================================
# Index Tests (stub)
# =====================================================================

class TestKBIndex:

    def test_index_updates_last_indexed(self, adapter):
        adapter.register_source("idx-1", "To Index")
        src_before = adapter.get_source("idx-1")
        assert src_before["last_indexed"] == 0.0

        result = adapter.index("idx-1")
        assert result is not None
        assert result["last_indexed"] > 0.0

    def test_index_returns_source_dict(self, adapter):
        adapter.register_source("idx-2", "Index Check")
        result = adapter.index("idx-2")
        assert result["source_id"] == "idx-2"
        assert result["name"] == "Index Check"

    def test_index_nonexistent_returns_none(self, adapter):
        result = adapter.index("nope")
        assert result is None

    def test_index_idempotent(self, adapter):
        adapter.register_source("idx-3", "Repeat")
        first = adapter.index("idx-3")
        second = adapter.index("idx-3")
        assert first is not None
        assert second is not None
        assert second["last_indexed"] >= first["last_indexed"]


# =====================================================================
# Stats Tests
# =====================================================================

class TestKBStats:

    def test_stats_empty_adapter(self, adapter):
        stats = adapter.get_stats()
        assert stats["total_sources"] == 0
        assert stats["active_sources"] == 0
        assert stats["total_queries"] == 0
        assert stats["avg_latency_ms"] == 0.0

    def test_stats_counts_sources(self, populated_adapter):
        stats = populated_adapter.get_stats()
        assert stats["total_sources"] == 3
        assert stats["active_sources"] == 3

    def test_stats_counts_queries(self, populated_adapter):
        populated_adapter.query("src-files", "q1")
        populated_adapter.query("src-api", "q2")
        populated_adapter.query("src-files", "q3")
        stats = populated_adapter.get_stats()
        assert stats["total_queries"] == 3

    def test_stats_avg_latency(self, populated_adapter):
        populated_adapter.query("src-files", "fast query")
        stats = populated_adapter.get_stats()
        assert stats["avg_latency_ms"] >= 0.0

    def test_stats_after_deactivation(self, adapter):
        adapter.register_source("s1", "One")
        adapter.register_source("s2", "Two")
        adapter._conn.execute(
            "UPDATE kb_sources SET active = 0 WHERE source_id = ?", ("s1",)
        )
        adapter._conn.commit()
        stats = adapter.get_stats()
        assert stats["total_sources"] == 2
        assert stats["active_sources"] == 1


# =====================================================================
# EventBus Integration
# =====================================================================

class TestKBEventBus:

    def test_register_emits_event(self, adapter_with_bus):
        kba, captured = adapter_with_bus
        kba.register_source("ev-1", "Event Test")
        events = [e for e in captured if e.topic == "kb.source_registered"]
        assert len(events) == 1
        assert events[0].payload["source_id"] == "ev-1"
        assert events[0].payload["name"] == "Event Test"

    def test_query_emits_event(self, adapter_with_bus):
        kba, captured = adapter_with_bus
        kba.register_source("ev-q", "Q Test")
        captured.clear()
        kba.query("ev-q", "search")
        events = [e for e in captured if e.topic == "kb.queried"]
        assert len(events) == 1
        assert "query_id" in events[0].payload
        assert events[0].payload["results_count"] == 0

    def test_index_emits_event(self, adapter_with_bus):
        kba, captured = adapter_with_bus
        kba.register_source("ev-i", "Index Event")
        captured.clear()
        kba.index("ev-i")
        events = [e for e in captured if e.topic == "kb.indexed"]
        assert len(events) == 1
        assert events[0].payload["source_id"] == "ev-i"
        assert events[0].payload["timestamp"] > 0

    def test_no_events_without_bus(self, adapter):
        # Should not raise when no EventBus
        adapter.register_source("no-bus", "No Bus")
        adapter.query("no-bus", "test")
        adapter.index("no-bus")


# =====================================================================
# Dataclass Tests
# =====================================================================

class TestKBDataclass:

    def test_kb_source_defaults(self):
        s = KBSource()
        assert s.source_id == ""
        assert s.source_type == "file"
        assert s.active == 1
        assert s.config == {}

    def test_kb_source_custom(self):
        s = KBSource(source_id="abc", name="N", source_type="api")
        assert s.source_id == "abc"
        assert s.source_type == "api"

    def test_kb_query_auto_fields(self):
        q = KBQuery()
        assert len(q.query_id) == 32  # uuid hex
        assert q.timestamp > 0

    def test_kb_query_custom_id(self):
        q = KBQuery(query_id="custom-qid")
        assert q.query_id == "custom-qid"
