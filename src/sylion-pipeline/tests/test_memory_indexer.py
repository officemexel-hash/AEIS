"""
SYLION Memory -- Indexer Tests

Comprehensive tests for Indexer: index_section, remove_section, search,
get_stats, stop words, tokenization, event emission, and error handling.
"""

from __future__ import annotations

import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.memory.indexer import (
    Indexer, IndexEntry, IndexMetadata,
    _tokenize, _count_terms, STOP_WORDS, MIN_TERM_LENGTH,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    """Fresh in-memory EventBus."""
    return EventBus()


@pytest.fixture
def indexer(bus):
    """Fresh in-memory Indexer with EventBus attached."""
    return Indexer(event_bus=bus)


@pytest.fixture
def captured_events(bus):
    """Collect all events."""
    events: list[SylionEvent] = []
    bus.subscribe("*", events.append)
    return events


# =====================================================================
# Test tokenization helpers
# =====================================================================

class TestTokenize:

    def test_basic_tokenization(self):
        tokens = _tokenize("Hello World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_filters_short_terms(self):
        tokens = _tokenize("I am a x go")
        # "I", "am", "a", "x" all < MIN_TERM_LENGTH (2)
        for t in tokens:
            assert len(t) >= MIN_TERM_LENGTH

    def test_filters_stop_words(self):
        tokens = _tokenize("the quick brown fox")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_extracts_alphanumeric_only(self):
        tokens = _tokenize("hello-world foo_bar baz!qux")
        # hyphens, underscores, punctuation split words
        assert "hello" in tokens
        assert "world" in tokens
        assert "foo" in tokens
        assert "bar" in tokens
        assert "baz" in tokens
        assert "qux" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_numbers_preserved(self):
        tokens = _tokenize("python3 version 10")
        assert "python3" in tokens
        assert "version" in tokens
        assert "10" in tokens  # "10" has length 2, passes MIN_TERM_LENGTH


class TestCountTerms:

    def test_basic_count(self):
        counts = _count_terms(["hello", "world", "hello"])
        assert counts["hello"] == 2
        assert counts["world"] == 1

    def test_empty_list(self):
        assert _count_terms([]) == {}


# =====================================================================
# Test dataclasses
# =====================================================================

class TestDataclasses:

    def test_index_entry(self):
        entry = IndexEntry(term="python", section_id="s1", frequency=3)
        assert entry.term == "python"
        assert entry.frequency == 3

    def test_index_metadata_auto_timestamp(self):
        meta = IndexMetadata(section_id="s1", title="Test")
        assert meta.indexed_at > 0.0


# =====================================================================
# Test index_section
# =====================================================================

class TestIndexSection:

    def test_index_returns_summary(self, indexer):
        result = indexer.index_section("sec1", "Python Guide", "Python is a great language")
        assert result["section_id"] == "sec1"
        assert result["unique_terms"] > 0
        assert result["word_count"] > 0

    def test_index_stores_terms(self, indexer):
        indexer.index_section("sec1", "Testing", "unit testing integration testing")
        stats = indexer.get_stats()
        assert stats["indexed_sections"] == 1
        assert stats["total_postings"] > 0

    def test_index_reindex_replaces(self, indexer):
        indexer.index_section("sec1", "Title", "alpha beta gamma")
        indexer.index_section("sec1", "New Title", "delta epsilon")
        stats = indexer.get_stats()
        assert stats["indexed_sections"] == 1
        # Search for "alpha" should not find the re-indexed section
        results = indexer.search("alpha")
        assert len(results) == 0

    def test_index_title_included_in_tokens(self, indexer):
        indexer.index_section("sec1", "Quantum Computing", "")
        results = indexer.search("quantum")
        assert len(results) == 1
        assert results[0]["title"] == "Quantum Computing"

    def test_index_empty_content(self, indexer):
        result = indexer.index_section("sec2", "Empty", "")
        # Title "Empty" contributes 1 token after tokenization
        assert result["word_count"] == 1

    def test_index_stops_words_excluded(self, indexer):
        indexer.index_section("sec3", "Test", "the quick brown fox jumps over the lazy dog")
        results = indexer.search("the")
        assert len(results) == 0  # "the" is a stop word


# =====================================================================
# Test remove_section
# =====================================================================

class TestRemoveSection:

    def test_remove_existing_section(self, indexer):
        indexer.index_section("sec1", "Title", "content here")
        removed = indexer.remove_section("sec1")
        assert removed is True
        stats = indexer.get_stats()
        assert stats["indexed_sections"] == 0

    def test_remove_nonexistent_section(self, indexer):
        removed = indexer.remove_section("ghost-section")
        assert removed is False

    def test_remove_clears_postings(self, indexer):
        indexer.index_section("sec1", "T", "unique word xyzzy")
        indexer.remove_section("sec1")
        results = indexer.search("xyzzy")
        assert len(results) == 0


# =====================================================================
# Test search
# =====================================================================

class TestSearch:

    def test_search_single_term(self, indexer):
        indexer.index_section("s1", "Python Intro", "Python programming language")
        results = indexer.search("python")
        assert len(results) == 1
        assert results[0]["section_id"] == "s1"
        assert results[0]["score"] > 0

    def test_search_ranked_by_frequency(self, indexer):
        indexer.index_section("s1", "Doc A", "python python python code")
        indexer.index_section("s2", "Doc B", "python code")
        results = indexer.search("python")
        assert len(results) == 2
        # s1 has "python" 3 times, s2 has it 1 time
        assert results[0]["section_id"] == "s1"
        assert results[0]["score"] > results[1]["score"]

    def test_search_multi_term_sums_frequencies(self, indexer):
        indexer.index_section("s1", "Full", "python testing code")
        results = indexer.search("python testing")
        assert len(results) == 1
        # score = freq("python") + freq("testing") + freq("code")
        assert results[0]["score"] >= 2

    def test_search_no_results(self, indexer):
        indexer.index_section("s1", "Title", "hello world")
        results = indexer.search("nonexistent term")
        assert results == []

    def test_search_empty_query(self, indexer):
        indexer.index_section("s1", "T", "content")
        results = indexer.search("")
        assert results == []

    def test_search_stop_word_only_query(self, indexer):
        indexer.index_section("s1", "T", "hello world")
        results = indexer.search("the a an")
        assert results == []

    def test_search_respects_limit(self, indexer):
        for i in range(15):
            indexer.index_section(f"s{i}", f"Doc {i}", "common keyword")
        results = indexer.search("common", limit=5)
        assert len(results) == 5


# =====================================================================
# Test get_stats
# =====================================================================

class TestGetStats:

    def test_stats_empty(self, indexer):
        stats = indexer.get_stats()
        assert stats["unique_terms"] == 0
        assert stats["total_postings"] == 0
        assert stats["indexed_sections"] == 0
        assert stats["avg_word_count"] == 0.0

    def test_stats_after_indexing(self, indexer):
        indexer.index_section("s1", "T1", "alpha beta gamma")
        indexer.index_section("s2", "T2", "delta epsilon alpha")
        stats = indexer.get_stats()
        assert stats["indexed_sections"] == 2
        assert stats["total_postings"] >= 5  # at least 5 unique (term, section) combos
        assert stats["avg_word_count"] > 0.0

    def test_stats_unique_terms_count(self, indexer):
        indexer.index_section("s1", "T", "hello world hello")
        stats = indexer.get_stats()
        # "hello" and "world" = 2 unique terms
        assert stats["unique_terms"] == 2


# =====================================================================
# Test event emission
# =====================================================================

class TestEventEmission:

    def test_index_emits_event(self, indexer, captured_events):
        indexer.index_section("s1", "Title", "content")
        assert len(captured_events) == 1
        evt = captured_events[0]
        assert evt.topic == "indexer.section_indexed"
        assert evt.payload["section_id"] == "s1"

    def test_remove_emits_event(self, indexer, captured_events):
        indexer.index_section("s1", "T", "content")
        captured_events.clear()
        indexer.remove_section("s1")
        assert len(captured_events) == 1
        assert captured_events[0].topic == "indexer.section_removed"

    def test_no_event_without_bus(self):
        idx = Indexer(event_bus=None)
        result = idx.index_section("s1", "T", "content")
        assert result["section_id"] == "s1"


# =====================================================================
# Test thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_indexing(self, indexer):
        errors: list[Exception] = []

        def do_index(i):
            try:
                indexer.index_section(f"sec-{i}", f"Title {i}", f"content number {i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_index, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stats = indexer.get_stats()
        assert stats["indexed_sections"] == 20
