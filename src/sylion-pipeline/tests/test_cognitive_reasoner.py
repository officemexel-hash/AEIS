"""
Comprehensive tests for sylion.cognitive.reasoner -- Reasoner

Covers:
  - reason() CRUD (create, read via get_chain, query_chains, get_stats)
  - chain_id generation and timestamp auto-fill
  - steps serialization / deserialization (JSON round-trip)
  - query_chains LIKE matching on query and conclusion fields
  - ordering by confidence then timestamp
  - get_stats aggregation (total, avg_confidence, by_source)
  - get_chain returns None for unknown IDs
  - empty steps defaults to []
  - event emission via EventBus
  - multiple chains from different sources
  - confidence ordering in query_chains results
  - thread safety under concurrent writes
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.reasoner import Reasoner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reasoner():
    """Fresh in-memory Reasoner with no event bus."""
    return Reasoner()


@pytest.fixture
def reasoner_with_bus():
    """Reasoner wired to a fresh EventBus so events can be captured."""
    bus = EventBus()
    r = Reasoner(event_bus=bus)
    return r, bus


# ===========================================================================
# 1. reason() -- create
# ===========================================================================

class TestReasonCreate:

    def test_reason_returns_chain_id(self, reasoner):
        result = reasoner.reason(
            query="What is the capital of France?",
            conclusion="Paris",
            steps=["Lookup geography database"],
            confidence=0.95,
            source="kanon",
        )
        assert "chain_id" in result
        assert len(result["chain_id"]) == 32  # uuid hex

    def test_reason_preserves_query_and_conclusion(self, reasoner):
        result = reasoner.reason(
            query="Why microservices?",
            conclusion="Scalability and isolation",
            confidence=0.88,
        )
        assert result["query"] == "Why microservices?"
        assert result["conclusion"] == "Scalability and isolation"

    def test_reason_auto_sets_timestamp(self, reasoner):
        before = time.time()
        result = reasoner.reason(query="Q", conclusion="C", confidence=0.5)
        after = time.time()
        assert before <= result["timestamp"] <= after

    def test_reason_default_steps_empty(self, reasoner):
        result = reasoner.reason(query="Q", conclusion="C", confidence=0.5)
        chain = reasoner.get_chain(result["chain_id"])
        assert chain["steps"] == []

    def test_reason_serializes_steps_as_json(self, reasoner):
        steps = ["Step A", "Step B", "Step C"]
        result = reasoner.reason(
            query="Q", conclusion="C", steps=steps, confidence=0.8,
        )
        chain = reasoner.get_chain(result["chain_id"])
        assert chain["steps"] == steps


# ===========================================================================
# 2. get_chain() -- read
# ===========================================================================

class TestGetChain:

    def test_get_chain_returns_full_record(self, reasoner):
        result = reasoner.reason(
            query="Test query",
            conclusion="Test conclusion",
            steps=["a", "b"],
            confidence=0.8,
            source="llm",
        )
        chain = reasoner.get_chain(result["chain_id"])
        assert chain is not None
        assert chain["query"] == "Test query"
        assert chain["conclusion"] == "Test conclusion"
        assert chain["steps"] == ["a", "b"]
        assert chain["confidence"] == 0.8
        assert chain["source"] == "llm"

    def test_get_chain_nonexistent_returns_none(self, reasoner):
        assert reasoner.get_chain("does_not_exist") is None


# ===========================================================================
# 3. query_chains() -- search
# ===========================================================================

class TestQueryChains:

    def test_query_matches_query_field(self, reasoner):
        reasoner.reason(query="Python performance tips", conclusion="Fast", confidence=0.7)
        reasoner.reason(query="Rust memory safety", conclusion="Safe", confidence=0.9)
        results = reasoner.query_chains("Python")
        assert len(results) == 1
        assert "Python" in results[0]["query"]

    def test_query_matches_conclusion_field(self, reasoner):
        reasoner.reason(query="Golang concurrency", conclusion="Uses goroutines", confidence=0.8)
        reasoner.reason(query="Java threads", conclusion="Uses OS threads", confidence=0.7)
        results = reasoner.query_chains("goroutines")
        assert len(results) == 1
        assert "goroutines" in results[0]["conclusion"]

    def test_query_returns_multiple_matches(self, reasoner):
        reasoner.reason(query="Python web framework", conclusion="Django is popular", confidence=0.8)
        reasoner.reason(query="Python data science", conclusion="Pandas is key", confidence=0.7)
        reasoner.reason(query="Rust systems", conclusion="No GC", confidence=0.9)
        results = reasoner.query_chains("Python")
        assert len(results) == 2

    def test_query_orders_by_confidence_desc(self, reasoner):
        reasoner.reason(query="test ordering A", conclusion="low conf", confidence=0.3)
        reasoner.reason(query="test ordering B", conclusion="high conf", confidence=0.95)
        reasoner.reason(query="test ordering C", conclusion="mid conf", confidence=0.6)
        results = reasoner.query_chains("test ordering")
        assert len(results) == 3
        assert results[0]["confidence"] >= results[1]["confidence"]
        assert results[1]["confidence"] >= results[2]["confidence"]

    def test_query_respects_limit(self, reasoner):
        for i in range(20):
            reasoner.reason(query=f"duplicate query {i}", conclusion="C", confidence=0.5)
        results = reasoner.query_chains("duplicate query", limit=5)
        assert len(results) == 5

    def test_query_no_match_returns_empty(self, reasoner):
        reasoner.reason(query="something", conclusion="else", confidence=0.5)
        results = reasoner.query_chains("completely different")
        assert results == []


# ===========================================================================
# 4. get_stats() -- aggregation
# ===========================================================================

class TestGetStats:

    def test_stats_empty_db(self, reasoner):
        stats = reasoner.get_stats()
        assert stats["total_chains"] == 0
        assert stats["avg_confidence"] == 0.0
        assert stats["by_source"] == {}

    def test_stats_counts_chains(self, reasoner):
        reasoner.reason(query="Q1", conclusion="C1", confidence=0.8, source="kanon")
        reasoner.reason(query="Q2", conclusion="C2", confidence=0.6, source="llm")
        reasoner.reason(query="Q3", conclusion="C3", confidence=0.9, source="kanon")
        stats = reasoner.get_stats()
        assert stats["total_chains"] == 3
        assert stats["avg_confidence"] == pytest.approx(0.7667, abs=0.01)
        assert stats["by_source"]["kanon"] == 2
        assert stats["by_source"]["llm"] == 1

    def test_stats_single_chain(self, reasoner):
        reasoner.reason(query="Q", conclusion="C", confidence=1.0, source="test")
        stats = reasoner.get_stats()
        assert stats["total_chains"] == 1
        assert stats["avg_confidence"] == 1.0
        assert stats["by_source"]["test"] == 1

    def test_stats_empty_source_grouped_as_empty_string(self, reasoner):
        reasoner.reason(query="Q", conclusion="C", confidence=0.5)
        stats = reasoner.get_stats()
        assert "" in stats["by_source"]


# ===========================================================================
# 5. Event emission
# ===========================================================================

class TestEventEmission:

    def test_reason_emits_event(self, reasoner_with_bus):
        r, bus = reasoner_with_bus
        events = []
        bus.subscribe("reasoning.recorded", lambda e: events.append(e))

        r.reason(query="Event test", conclusion="Yes", confidence=0.9)
        assert len(events) == 1
        assert events[0].payload["query"] == "Event test"
        assert events[0].payload["confidence"] == 0.9

    def test_reason_event_contains_chain_id(self, reasoner_with_bus):
        r, bus = reasoner_with_bus
        events = []
        bus.subscribe("reasoning.recorded", lambda e: events.append(e))

        result = r.reason(query="Q", conclusion="C", confidence=0.5)
        assert events[0].payload["chain_id"] == result["chain_id"]

    def test_no_event_bus_does_not_raise(self):
        r = Reasoner(event_bus=None)
        # Should not raise
        r.reason(query="Q", conclusion="C", confidence=0.5)


# ===========================================================================
# 6. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_reason_writes(self):
        r = Reasoner()
        results = []
        results_lock = threading.Lock()

        def write_chain(idx):
            res = r.reason(
                query=f"Concurrent query {idx}",
                conclusion=f"Concurrent conclusion {idx}",
                confidence=0.5 + (idx % 5) * 0.1,
                source="thread_test",
            )
            with results_lock:
                results.append(res)

        threads = [threading.Thread(target=write_chain, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 20
        # All chain_ids must be unique
        chain_ids = [r["chain_id"] for r in results]
        assert len(set(chain_ids)) == 20

        # All must be retrievable
        stats = r.get_stats()
        assert stats["total_chains"] == 20
