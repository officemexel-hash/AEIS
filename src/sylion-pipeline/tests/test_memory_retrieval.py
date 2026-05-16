"""
SYLION Memory Retrieval -- Comprehensive Unit Tests

Tests for sylion.memory.retrieval.Retrieval:
  - retrieve() with ranking, limit, min_score filtering
  - get_context() with token budgets
  - EventBus integration
  - edge cases: empty queries, no results, single-result retrieval
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.memory.indexer import Indexer
from sylion.memory.retrieval import Retrieval, RetrievalResult


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def indexer_with_data():
    """Indexer pre-loaded with 5 sections of varied content."""
    idx = Indexer()
    idx.index_section(
        "sec-python", "Python Tutorial",
        "Python is a popular programming language used for web development "
        "data science automation scripting machine learning deep learning.",
    )
    idx.index_section(
        "sec-rust", "Rust Guide",
        "Rust is a systems programming language focused on safety speed "
        "performance and concurrency without garbage collection.",
    )
    idx.index_section(
        "sec-js", "JavaScript Basics",
        "JavaScript is the language of the web used in browsers servers "
        "and full-stack development with node.",
    )
    idx.index_section(
        "sec-go", "Go Programming",
        "Go is a statically typed compiled language designed at Google "
        "for simplicity concurrency and fast compilation speed.",
    )
    idx.index_section(
        "sec-ml", "Machine Learning Intro",
        "Machine learning is a subset of artificial intelligence that "
        "enables systems to learn from data and improve over time.",
    )
    return idx


@pytest.fixture
def retrieval(indexer_with_data):
    """Retrieval wired to the pre-loaded indexer."""
    return Retrieval(indexer=indexer_with_data)


@pytest.fixture
def retrieval_with_bus(indexer_with_data):
    """Retrieval wired to indexer + EventBus with a captured subscriber."""
    bus = EventBus()
    captured: list[SylionEvent] = []
    bus.subscribe("*", captured.append)
    ret = Retrieval(indexer=indexer_with_data, event_bus=bus)
    return ret, captured


@pytest.fixture
def empty_retrieval():
    """Retrieval over an empty indexer."""
    return Retrieval(indexer=Indexer())


# =====================================================================
# Tests
# =====================================================================

class TestRetrievalRetrieve:

    def test_retrieve_returns_ranked_results(self, retrieval):
        results = retrieval.retrieve("Python programming")
        assert len(results) >= 1
        assert all(isinstance(r, RetrievalResult) for r in results)
        # Scores should be descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_retrieve_top_result_matches_query(self, retrieval):
        results = retrieval.retrieve("Rust safety concurrency")
        assert results[0].section_id == "sec-rust"

    def test_retrieve_limit_parameter(self, retrieval):
        results = retrieval.retrieve("programming language", limit=2)
        assert len(results) <= 2

    def test_retrieve_min_score_filters(self, retrieval):
        all_results = retrieval.retrieve("Python", min_score=0.0)
        filtered = retrieval.retrieve("Python", min_score=9999.0)
        assert len(filtered) < len(all_results)
        assert len(filtered) == 0

    def test_retrieve_preserves_section_id_and_title(self, retrieval):
        results = retrieval.retrieve("Machine learning")
        assert len(results) >= 1
        top = results[0]
        assert top.section_id == "sec-ml"
        assert top.title == "Machine Learning Intro"
        assert top.score > 0.0

    def test_retrieve_empty_index(self, empty_retrieval):
        results = empty_retrieval.retrieve("anything")
        assert results == []

    def test_retrieve_query_with_only_stop_words(self, retrieval):
        # "the a an" are all stop words -- tokenizer drops them, search returns []
        results = retrieval.retrieve("the a an")
        assert results == []

    def test_retrieve_query_no_matching_terms(self, retrieval):
        results = retrieval.retrieve("xylophone zephyr")
        assert results == []

    def test_retrieve_result_has_snippet_default_empty(self, retrieval):
        results = retrieval.retrieve("Python")
        for r in results:
            assert hasattr(r, "snippet")
            assert r.snippet == ""


class TestRetrievalGetContext:

    def test_get_context_returns_string(self, retrieval):
        ctx = retrieval.get_context("Python")
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_get_context_respects_token_budget(self, retrieval):
        small_budget_ctx = retrieval.get_context("programming", max_tokens=5)
        large_budget_ctx = retrieval.get_context("programming", max_tokens=5000)
        # Larger budget should produce equal or longer context
        assert len(large_budget_ctx) >= len(small_budget_ctx)

    def test_get_context_contains_titles(self, retrieval):
        ctx = retrieval.get_context("Rust")
        assert "Rust Guide" in ctx

    def test_get_context_empty_index(self, empty_retrieval):
        ctx = empty_retrieval.get_context("nothing")
        assert ctx == ""

    def test_get_context_very_small_budget(self, retrieval):
        ctx = retrieval.get_context("Python", max_tokens=1)
        # With 1 token budget (4 chars), maybe 0 or 1 result fits
        # It should not raise an error
        assert isinstance(ctx, str)

    def test_get_context_includes_score_in_output(self, retrieval):
        ctx = retrieval.get_context("Python")
        assert "score:" in ctx


class TestRetrievalEventBus:

    def test_retrieve_emits_event(self, retrieval_with_bus):
        ret, captured = retrieval_with_bus
        ret.retrieve("Python")
        events = [e for e in captured if e.topic == "retrieval.retrieve"]
        assert len(events) == 1
        assert events[0].payload["query"] == "Python"
        assert "results_count" in events[0].payload

    def test_get_context_emits_event(self, retrieval_with_bus):
        ret, captured = retrieval_with_bus
        ret.get_context("Rust", max_tokens=100)
        events = [e for e in captured if e.topic == "retrieval.get_context"]
        assert len(events) == 1
        assert events[0].payload["max_tokens"] == 100
        assert "sections_used" in events[0].payload
        assert "approx_tokens" in events[0].payload

    def test_no_event_without_bus(self, retrieval):
        # Should not raise when no EventBus is set
        retrieval.retrieve("Python")
        retrieval.get_context("Python")

    def test_retrieve_event_count_matches_results(self, retrieval_with_bus):
        ret, captured = retrieval_with_bus
        results = ret.retrieve("Python")
        event = [e for e in captured if e.topic == "retrieval.retrieve"][0]
        assert event.payload["results_count"] == len(results)


class TestRetrievalResult:

    def test_result_dataclass_defaults(self):
        r = RetrievalResult()
        assert r.section_id == ""
        assert r.title == ""
        assert r.score == 0.0
        assert r.snippet == ""

    def test_result_dataclass_values(self):
        r = RetrievalResult(section_id="abc", title="T", score=3.5, snippet="hi")
        assert r.section_id == "abc"
        assert r.score == 3.5
