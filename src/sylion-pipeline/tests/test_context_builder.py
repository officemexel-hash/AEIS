"""
Comprehensive tests for sylion.cognitive.context_builder -- ContextBuilder

Covers:
  - add_source CRUD (add, update same source_id, clear)
  - priority ordering (descending priority, ascending added_at for ties)
  - build_context character budget enforcement
  - build_context truncation of overflow content
  - build_context with specific source ID filter
  - build_context with no registered sources (empty string)
  - clear_sources returns count and empties state
  - get_context_stats aggregation
  - event emission via EventBus
  - source_id deduplication (re-adding same source_id replaces)
  - thread safety under concurrent source adds
"""

from __future__ import annotations

import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.context_builder import ContextBuilder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def builder():
    """Fresh in-memory ContextBuilder with no event bus."""
    return ContextBuilder()


@pytest.fixture
def builder_with_bus():
    """ContextBuilder wired to a fresh EventBus."""
    bus = EventBus()
    cb = ContextBuilder(event_bus=bus)
    return cb, bus


# ===========================================================================
# 1. add_source() -- create / update
# ===========================================================================

class TestAddSource:

    def test_add_source_returns_summary(self, builder):
        result = builder.add_source("src-1", "Hello world", priority=5)
        assert result["source_id"] == "src-1"
        assert result["priority"] == 5
        assert result["content_length"] == 11

    def test_add_source_empty_content(self, builder):
        result = builder.add_source("empty", "", priority=0)
        assert result["content_length"] == 0

    def test_add_source_deduplicates_by_id(self, builder):
        builder.add_source("dup", "Original content", priority=1)
        builder.add_source("dup", "Replaced content", priority=5)
        stats = builder.get_context_stats()
        assert stats["source_count"] == 1
        assert stats["total_content_chars"] == len("Replaced content")

    def test_add_source_uses_new_priority_on_replace(self, builder):
        builder.add_source("s1", "content", priority=1)
        builder.add_source("s1", "content", priority=10)
        context = builder.build_context("test")
        # The source with priority 10 should be present
        assert "[s1]" in context


# ===========================================================================
# 2. build_context() -- assembly
# ===========================================================================

class TestBuildContext:

    def test_build_empty_returns_empty_string(self, builder):
        context = builder.build_context("test query")
        assert context == ""

    def test_build_returns_single_source(self, builder):
        builder.add_source("s1", "Some content here", priority=1)
        context = builder.build_context("test")
        assert "[s1]" in context
        assert "Some content here" in context

    def test_build_orders_by_priority_desc(self, builder):
        builder.add_source("low", "low priority content", priority=1)
        builder.add_source("high", "high priority content", priority=10)
        builder.add_source("mid", "mid priority content", priority=5)

        context = builder.build_context("test", max_chars=10000)
        pos_high = context.index("[high]")
        pos_mid = context.index("[mid]")
        pos_low = context.index("[low]")
        assert pos_high < pos_mid < pos_low

    def test_build_respects_char_budget(self, builder):
        builder.add_source("s1", "A" * 500, priority=1)
        builder.add_source("s2", "B" * 500, priority=1)
        builder.add_source("s3", "C" * 500, priority=1)

        context = builder.build_context("test", max_chars=600)
        # Budget is 600 chars; total content is 1500 so truncation must occur
        assert len(context) <= 650  # small overhead for headers

    def test_build_truncates_overflow_with_ellipsis(self, builder):
        builder.add_source("big", "X" * 2000, priority=10)
        context = builder.build_context("test", max_chars=100)
        assert len(context) <= 110  # header overhead
        assert context.endswith("...")

    def test_build_with_specific_source_filter(self, builder):
        builder.add_source("s1", "Content one", priority=1)
        builder.add_source("s2", "Content two", priority=1)
        builder.add_source("s3", "Content three", priority=1)

        context = builder.build_context("test", sources=["s1", "s3"])
        assert "[s1]" in context
        assert "[s3]" in context
        assert "[s2]" not in context

    def test_build_with_nonexistent_source_filter(self, builder):
        builder.add_source("s1", "Available content", priority=1)
        context = builder.build_context("test", sources=["ghost"])
        assert context == ""

    def test_build_separates_sources_with_double_newline(self, builder):
        builder.add_source("s1", "Alpha", priority=2)
        builder.add_source("s2", "Beta", priority=1)
        context = builder.build_context("test", max_chars=10000)
        assert "[s1]\nAlpha" in context
        assert "[s2]\nBeta" in context
        assert "\n\n" in context


# ===========================================================================
# 3. clear_sources()
# ===========================================================================

class TestClearSources:

    def test_clear_returns_count(self, builder):
        builder.add_source("s1", "content 1")
        builder.add_source("s2", "content 2")
        builder.add_source("s3", "content 3")
        result = builder.clear_sources()
        assert result["sources_cleared"] == 3

    def test_clear_empties_context(self, builder):
        builder.add_source("s1", "Hello")
        builder.clear_sources()
        context = builder.build_context("test")
        assert context == ""

    def test_clear_empty_returns_zero(self, builder):
        result = builder.clear_sources()
        assert result["sources_cleared"] == 0

    def test_clear_allows_new_adds(self, builder):
        builder.add_source("s1", "Old content")
        builder.clear_sources()
        builder.add_source("s2", "New content")
        context = builder.build_context("test")
        assert "New content" in context
        assert "Old content" not in context


# ===========================================================================
# 4. get_context_stats()
# ===========================================================================

class TestGetContextStats:

    def test_stats_empty(self, builder):
        stats = builder.get_context_stats()
        assert stats["source_count"] == 0
        assert stats["total_content_chars"] == 0
        assert stats["min_priority"] == 0
        assert stats["max_priority"] == 0

    def test_stats_single_source(self, builder):
        builder.add_source("s1", "Hello", priority=5)
        stats = builder.get_context_stats()
        assert stats["source_count"] == 1
        assert stats["total_content_chars"] == 5
        assert stats["min_priority"] == 5
        assert stats["max_priority"] == 5

    def test_stats_multiple_sources(self, builder):
        builder.add_source("s1", "Short", priority=1)
        builder.add_source("s2", "A bit longer", priority=10)
        builder.add_source("s3", "Medium length content", priority=5)
        stats = builder.get_context_stats()
        assert stats["source_count"] == 3
        assert stats["total_content_chars"] == len("Short") + len("A bit longer") + len("Medium length content")
        assert stats["min_priority"] == 1
        assert stats["max_priority"] == 10


# ===========================================================================
# 5. Event emission
# ===========================================================================

class TestEventEmission:

    def test_add_source_emits_event(self, builder_with_bus):
        cb, bus = builder_with_bus
        events = []
        bus.subscribe("context.source_added", lambda e: events.append(e))

        cb.add_source("src-1", "Hello", priority=3)
        assert len(events) == 1
        assert events[0].payload["source_id"] == "src-1"
        assert events[0].payload["priority"] == 3
        assert events[0].payload["content_length"] == 5

    def test_clear_sources_emits_event(self, builder_with_bus):
        cb, bus = builder_with_bus
        events = []
        bus.subscribe("context.cleared", lambda e: events.append(e))

        cb.add_source("s1", "A")
        cb.add_source("s2", "B")
        cb.clear_sources()
        assert len(events) == 1
        assert events[0].payload["sources_cleared"] == 2

    def test_build_context_emits_event(self, builder_with_bus):
        cb, bus = builder_with_bus
        events = []
        bus.subscribe("context.built", lambda e: events.append(e))

        cb.add_source("s1", "Content", priority=1)
        cb.build_context("my query", max_chars=500)
        assert len(events) == 1
        assert events[0].payload["query"] == "my query"
        assert events[0].payload["sources_used"] == 1
        assert events[0].payload["max_chars"] == 500

    def test_no_event_bus_does_not_raise(self):
        cb = ContextBuilder(event_bus=None)
        cb.add_source("s1", "No bus content")
        cb.build_context("test")
        cb.clear_sources()


# ===========================================================================
# 6. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_add_sources(self):
        cb = ContextBuilder()
        errors = []

        def add_source(idx):
            try:
                cb.add_source(f"src-{idx}", f"Content {idx}" * 10, priority=idx % 10)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_source, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        stats = cb.get_context_stats()
        assert stats["source_count"] == 30
