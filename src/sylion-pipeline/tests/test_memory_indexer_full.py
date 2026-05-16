"""
SYLION Memory Indexer -- Full Unit Tests

Tests for sylion.memory.indexer:
  - _tokenize() helper: word extraction, stop-word filtering, min length
  - _count_terms() helper: frequency counting, empty input
  - Indexer.index_section(): insert, re-index, term storage, metadata
  - Indexer.remove_section(): removal, idempotent removal of missing section
  - Indexer.search(): TF-ranked search, multi-term queries, empty/missing cases
  - Indexer.get_stats(): aggregate statistics across edge states
  - EventBus integration: events emitted on index and remove
  - Thread safety: concurrent index_section calls
  - get_indexer() singleton behavior
  - Edge cases: empty content, only stop words, unicode, special characters
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.memory.indexer import (
    IndexEntry,
    IndexMetadata,
    Indexer,
    _count_terms,
    _tokenize,
    get_indexer,
)


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def indexer():
    """Fresh in-memory Indexer with no EventBus."""
    return Indexer()


@pytest.fixture
def indexer_with_bus():
    """In-memory Indexer wired to a real EventBus."""
    bus = EventBus()
    idx = Indexer(event_bus=bus)
    return idx, bus


@pytest.fixture
def indexer_with_data():
    """Indexer pre-loaded with several sections of varied content."""
    idx = Indexer()
    idx.index_section(
        "sec-python",
        "Python Tutorial",
        "Python is a popular programming language used for web development "
        "data science automation scripting machine learning deep learning.",
    )
    idx.index_section(
        "sec-rust",
        "Rust Guide",
        "Rust is a systems programming language focused on safety speed "
        "performance and concurrency without garbage collection.",
    )
    idx.index_section(
        "sec-js",
        "JavaScript Basics",
        "JavaScript is the language of the web used in browsers servers "
        "and full-stack applications everywhere.",
    )
    return idx


# =====================================================================
# _tokenize
# =====================================================================


class TestTokenize:
    """Tests for the _tokenize() helper."""

    def test_basic_tokenization(self):
        tokens = _tokenize("Hello World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_lowercase_conversion(self):
        tokens = _tokenize("PYTHON Rust JavaScript")
        assert "python" in tokens
        assert "rust" in tokens
        assert "javascript" in tokens

    def test_stop_words_removed(self):
        tokens = _tokenize("this is the best of all time")
        assert "is" not in tokens
        assert "the" not in tokens
        assert "of" not in tokens
        assert "all" not in tokens
        assert "best" in tokens
        assert "time" in tokens

    def test_min_term_length_filter(self):
        tokens = _tokenize("a I am go to x y z")
        for t in tokens:
            assert len(t) >= 2

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_only_stop_words(self):
        tokens = _tokenize("the a an and or but in on at")
        assert tokens == []

    def test_only_short_words(self):
        tokens = _tokenize("a I x y z")
        assert tokens == []

    def test_numbers_preserved(self):
        tokens = _tokenize("version 42 of the system")
        assert "42" in tokens
        assert "version" in tokens
        assert "system" in tokens

    def test_special_characters_stripped(self):
        tokens = _tokenize("hello! world? test@example.com #hash")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert "example" in tokens
        assert "com" in tokens
        assert "hash" in tokens

    def test_mixed_alphanumeric(self):
        tokens = _tokenize("Python3 Rust2024 c++")
        assert "python3" in tokens
        assert "rust2024" in tokens

    def test_whitespace_handling(self):
        tokens = _tokenize("  multiple   spaces\tand\nnewlines  ")
        assert "multiple" in tokens
        assert "spaces" in tokens
        assert "and" not in tokens  # stop word
        assert "newlines" in tokens

    def test_unicode_partial_extraction(self):
        # The regex [a-zA-Z0-9]+ strips non-ASCII chars but adjacent
        # ASCII letters are still captured
        tokens = _tokenize("uber flussig")
        assert "uber" in tokens
        assert "flussig" in tokens


# =====================================================================
# _count_terms
# =====================================================================


class TestCountTerms:
    """Tests for the _count_terms() helper."""

    def test_basic_counting(self):
        counts = _count_terms(["hello", "world", "hello"])
        assert counts["hello"] == 2
        assert counts["world"] == 1

    def test_empty_input(self):
        assert _count_terms([]) == {}

    def test_single_token(self):
        counts = _count_terms(["python"])
        assert counts == {"python": 1}

    def test_all_same(self):
        counts = _count_terms(["test", "test", "test", "test"])
        assert counts == {"test": 4}

    def test_preserves_case_exactly(self):
        # _count_terms does not lowercase; it counts whatever it receives
        counts = _count_terms(["Hello", "hello", "HELLO"])
        assert counts["Hello"] == 1
        assert counts["hello"] == 1
        assert counts["HELLO"] == 1


# =====================================================================
# IndexEntry / IndexMetadata dataclasses
# =====================================================================


class TestIndexEntry:
    """Tests for IndexEntry dataclass defaults."""

    def test_defaults(self):
        entry = IndexEntry()
        assert entry.term == ""
        assert entry.section_id == ""
        assert entry.frequency == 0

    def test_custom_values(self):
        entry = IndexEntry(term="python", section_id="sec-1", frequency=5)
        assert entry.term == "python"
        assert entry.section_id == "sec-1"
        assert entry.frequency == 5


class TestIndexMetadata:
    """Tests for IndexMetadata dataclass defaults and post_init."""

    def test_defaults(self):
        meta = IndexMetadata()
        assert meta.section_id == ""
        assert meta.title == ""
        assert meta.word_count == 0
        assert meta.indexed_at > 0  # auto-filled by __post_init__

    def test_custom_indexed_at_preserved(self):
        meta = IndexMetadata(section_id="s1", indexed_at=1234.5)
        assert meta.indexed_at == 1234.5

    def test_auto_timestamp(self):
        before = time.time()
        meta = IndexMetadata(section_id="s2")
        after = time.time()
        assert before <= meta.indexed_at <= after


# =====================================================================
# Indexer.__init__ / table creation
# =====================================================================


class TestIndexerInit:
    """Tests for Indexer initialization."""

    def test_in_memory_by_default(self):
        idx = Indexer()
        assert idx._db_path == ":memory:"

    def test_tables_created(self):
        idx = Indexer()
        rows = idx._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('text_index', 'index_metadata') ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in rows]
        assert "text_index" in names
        assert "index_metadata" in names

    def test_indexes_created(self):
        idx = Indexer()
        rows = idx._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_ti_%'"
        ).fetchall()
        names = [r["name"] for r in rows]
        assert "idx_ti_term" in names
        assert "idx_ti_sid" in names

    def test_with_none_event_bus(self):
        idx = Indexer(event_bus=None)
        assert idx._event_bus is None


# =====================================================================
# Indexer.index_section
# =====================================================================


class TestIndexSection:
    """Tests for Indexer.index_section()."""

    def test_basic_indexing(self, indexer):
        result = indexer.index_section("sec-1", "Hello World", "hello world")
        assert result["section_id"] == "sec-1"
        assert result["unique_terms"] >= 1
        assert result["word_count"] >= 1

    def test_returns_term_and_word_counts(self, indexer):
        result = indexer.index_section(
            "sec-counts", "Test Title",
            "python python python rust rust go",
        )
        assert result["unique_terms"] > 0
        assert result["word_count"] > 0
        assert result["word_count"] >= 6

    def test_metadata_stored(self, indexer):
        indexer.index_section("sec-meta", "My Title", "some content here")
        row = indexer._conn.execute(
            "SELECT * FROM index_metadata WHERE section_id = ?", ("sec-meta",)
        ).fetchone()
        assert row is not None
        assert row["section_id"] == "sec-meta"
        assert row["title"] == "My Title"
        assert row["word_count"] > 0
        assert row["indexed_at"] > 0

    def test_term_postings_stored(self, indexer):
        indexer.index_section("sec-post", "Python", "python python rust")
        rows = indexer._conn.execute(
            "SELECT term, frequency FROM text_index WHERE section_id = ? "
            "ORDER BY frequency DESC", ("sec-post",)
        ).fetchall()
        terms = {r["term"]: r["frequency"] for r in rows}
        assert "python" in terms
        assert terms["python"] == 3  # 1 from title + 2 from content
        assert "rust" in terms

    def test_reindex_replaces_previous(self, indexer):
        indexer.index_section("sec-re", "Old Title", "old content")
        indexer.index_section("sec-re", "New Title", "new content updated")
        row = indexer._conn.execute(
            "SELECT title FROM index_metadata WHERE section_id = ?", ("sec-re",)
        ).fetchone()
        assert row["title"] == "New Title"
        # Old terms should be gone
        old_row = indexer._conn.execute(
            "SELECT * FROM text_index WHERE section_id = ? AND term = 'old'",
            ("sec-re",),
        ).fetchone()
        assert old_row is None
        # New terms should exist
        new_row = indexer._conn.execute(
            "SELECT * FROM text_index WHERE section_id = ? AND term = 'new'",
            ("sec-re",),
        ).fetchone()
        assert new_row is not None

    def test_empty_content(self, indexer):
        result = indexer.index_section("sec-empty", "Title Only", "")
        assert result["word_count"] >= 1
        assert result["unique_terms"] >= 1

    def test_all_stop_words_content(self, indexer):
        result = indexer.index_section("sec-stop", "Stop Words", "the a an and or but")
        assert result["word_count"] >= 1  # at least "stop" and "words" from title

    def test_title_contributes_tokens(self, indexer):
        indexer.index_section("sec-titleonly", "Python Rust", "")
        rows = indexer._conn.execute(
            "SELECT term, frequency FROM text_index WHERE section_id = 'sec-titleonly'"
        ).fetchall()
        terms = {r["term"]: r["frequency"] for r in rows}
        assert "python" in terms
        assert "rust" in terms

    def test_multiple_sections_independent(self, indexer):
        indexer.index_section("sec-a", "Alpha", "alpha alpha")
        indexer.index_section("sec-b", "Beta", "beta beta beta")
        a_terms = indexer._conn.execute(
            "SELECT term FROM text_index WHERE section_id = 'sec-a'"
        ).fetchall()
        b_terms = indexer._conn.execute(
            "SELECT term FROM text_index WHERE section_id = 'sec-b'"
        ).fetchall()
        a_set = {r["term"] for r in a_terms}
        b_set = {r["term"] for r in b_terms}
        assert "alpha" in a_set
        assert "beta" not in a_set
        assert "beta" in b_set
        assert "alpha" not in b_set


# =====================================================================
# Indexer.remove_section
# =====================================================================


class TestRemoveSection:
    """Tests for Indexer.remove_section()."""

    def test_remove_existing_section(self, indexer_with_data):
        idx = indexer_with_data
        removed = idx.remove_section("sec-python")
        assert removed is True
        row = idx._conn.execute(
            "SELECT * FROM index_metadata WHERE section_id = 'sec-python'"
        ).fetchone()
        assert row is None
        rows = idx._conn.execute(
            "SELECT * FROM text_index WHERE section_id = 'sec-python'"
        ).fetchall()
        assert len(rows) == 0

    def test_remove_nonexistent_section(self, indexer):
        removed = indexer.remove_section("does-not-exist")
        assert removed is False

    def test_remove_twice(self, indexer):
        indexer.index_section("sec-dbl", "Title", "content")
        assert indexer.remove_section("sec-dbl") is True
        assert indexer.remove_section("sec-dbl") is False

    def test_other_sections_unaffected(self, indexer_with_data):
        idx = indexer_with_data
        idx.remove_section("sec-python")
        remaining = idx._conn.execute(
            "SELECT section_id FROM index_metadata ORDER BY section_id"
        ).fetchall()
        ids = [r["section_id"] for r in remaining]
        assert "sec-rust" in ids
        assert "sec-js" in ids
        assert "sec-python" not in ids

    def test_remove_from_empty_indexer(self, indexer):
        assert indexer.remove_section("anything") is False


# =====================================================================
# Indexer.search
# =====================================================================


class TestSearch:
    """Tests for Indexer.search()."""

    def test_single_term_search(self, indexer_with_data):
        idx = indexer_with_data
        results = idx.search("python")
        assert len(results) >= 1
        assert any(r["section_id"] == "sec-python" for r in results)

    def test_search_returns_score_and_title(self, indexer_with_data):
        idx = indexer_with_data
        results = idx.search("python")
        first = results[0]
        assert "section_id" in first
        assert "title" in first
        assert "score" in first
        assert isinstance(first["score"], (int, float))
        assert first["score"] > 0

    def test_results_ordered_by_score_desc(self, indexer_with_data):
        idx = indexer_with_data
        results = idx.search("programming")
        if len(results) >= 2:
            assert results[0]["score"] >= results[1]["score"]

    def test_limit_parameter(self, indexer_with_data):
        idx = indexer_with_data
        results = idx.search("language", limit=1)
        assert len(results) <= 1

    def test_multi_term_query_sums_frequency(self, indexer_with_data):
        idx = indexer_with_data
        results = idx.search("python learning")
        assert len(results) >= 1
        assert results[0]["section_id"] == "sec-python"

    def test_empty_query_returns_empty(self, indexer_with_data):
        results = indexer_with_data.search("")
        assert results == []

    def test_stop_words_only_query_returns_empty(self, indexer_with_data):
        results = indexer_with_data.search("the a an and or")
        assert results == []

    def test_no_matching_terms(self, indexer_with_data):
        results = indexer_with_data.search("quantum entanglement")
        assert results == []

    def test_search_on_empty_indexer(self, indexer):
        results = indexer.search("python")
        assert results == []

    def test_default_limit_is_10(self, indexer):
        for i in range(15):
            indexer.index_section(
                f"sec-common-{i}",
                f"Common Title {i}",
                "commonterm " * 5,
            )
        results = indexer.search("commonterm")
        assert len(results) <= 10

    def test_case_insensitive_search(self, indexer):
        indexer.index_section("sec-ci", "Python Guide", "Python python PYTHON")
        results_lower = indexer.search("python")
        results_upper = indexer.search("PYTHON")
        assert len(results_lower) >= 1
        assert len(results_upper) >= 1
        assert results_lower[0]["section_id"] == results_upper[0]["section_id"]


# =====================================================================
# Indexer.get_stats
# =====================================================================


class TestGetStats:
    """Tests for Indexer.get_stats()."""

    def test_empty_stats(self, indexer):
        stats = indexer.get_stats()
        assert stats["unique_terms"] == 0
        assert stats["total_postings"] == 0
        assert stats["indexed_sections"] == 0
        assert stats["avg_word_count"] == 0.0

    def test_stats_after_indexing(self, indexer_with_data):
        stats = indexer_with_data.get_stats()
        assert stats["indexed_sections"] == 3
        assert stats["unique_terms"] > 0
        assert stats["total_postings"] > 0
        assert stats["avg_word_count"] > 0.0

    def test_stats_after_removal(self, indexer_with_data):
        indexer_with_data.remove_section("sec-python")
        stats = indexer_with_data.get_stats()
        assert stats["indexed_sections"] == 2

    def test_avg_word_count_precision(self, indexer):
        indexer.index_section("s1", "A B C", "word " * 10)
        indexer.index_section("s2", "X Y", "term " * 4)
        stats = indexer.get_stats()
        assert isinstance(stats["avg_word_count"], float)
        assert stats["avg_word_count"] == round(stats["avg_word_count"], 1)

    def test_unique_terms_distinct(self, indexer):
        indexer.index_section("s1", "alpha", "alpha alpha")
        indexer.index_section("s2", "alpha", "alpha beta")
        stats = indexer.get_stats()
        assert stats["unique_terms"] >= 2
        assert stats["total_postings"] >= 2

    def test_stats_reflect_reindex(self, indexer):
        indexer.index_section("s1", "Old Title", "old content")
        before = indexer.get_stats()
        indexer.index_section("s1", "New Title", "new different content")
        after = indexer.get_stats()
        assert after["indexed_sections"] == before["indexed_sections"]
        assert isinstance(after["unique_terms"], int)


# =====================================================================
# EventBus integration
# =====================================================================


class TestEventBusIntegration:
    """Tests that Indexer emits events when wired to EventBus."""

    def test_index_emits_event(self):
        bus = EventBus()
        captured = []
        bus.subscribe("indexer.section_indexed", lambda e: captured.append(e))
        idx = Indexer(event_bus=bus)
        idx.index_section("sec-ev", "Event Test", "content for event")
        assert len(captured) == 1
        event = captured[0]
        assert isinstance(event, SylionEvent)
        assert event.topic == "indexer.section_indexed"
        assert event.source_module == "memory.indexer"
        assert event.payload["section_id"] == "sec-ev"

    def test_remove_emits_event(self):
        bus = EventBus()
        captured = []
        bus.subscribe("indexer.section_removed", lambda e: captured.append(e))
        idx = Indexer(event_bus=bus)
        idx.index_section("sec-rm", "Remove Test", "content")
        idx.remove_section("sec-rm")
        assert len(captured) == 1
        assert captured[0].payload["section_id"] == "sec-rm"

    def test_no_event_without_bus(self):
        idx = Indexer(event_bus=None)
        idx.index_section("sec-noev", "No Bus", "no event bus content")
        idx.remove_section("sec-noev")

    def test_remove_nonexistent_no_event(self):
        bus = EventBus()
        captured = []
        bus.subscribe("indexer.section_removed", lambda e: captured.append(e))
        idx = Indexer(event_bus=bus)
        idx.remove_section("ghost")
        assert len(captured) == 0

    def test_reindex_emits_event_each_time(self):
        bus = EventBus()
        captured = []
        bus.subscribe("indexer.section_indexed", lambda e: captured.append(e))
        idx = Indexer(event_bus=bus)
        idx.index_section("sec-multi", "V1", "version one")
        idx.index_section("sec-multi", "V2", "version two")
        assert len(captured) == 2
        assert captured[0].payload["section_id"] == "sec-multi"
        assert captured[1].payload["section_id"] == "sec-multi"


# =====================================================================
# Thread safety
# =====================================================================


class TestThreadSafety:
    """Tests for concurrent access to Indexer."""

    def test_concurrent_index_section(self):
        idx = Indexer()
        errors = []

        def worker(section_id, title, content):
            try:
                idx.index_section(section_id, title, content)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(
                target=worker,
                args=(f"sec-thread-{i}", f"Title {i}", f"content word{i} " * 5),
            )
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = idx.get_stats()
        assert stats["indexed_sections"] == 10

    def test_concurrent_search_and_index(self):
        idx = Indexer()
        for i in range(5):
            idx.index_section(f"sec-pre-{i}", f"Pre {i}", f"preload content {i}")

        errors = []

        def searcher():
            try:
                for _ in range(20):
                    results = idx.search("preload")
                    assert isinstance(results, list)
            except Exception as exc:
                errors.append(exc)

        def indexer_writer():
            try:
                for i in range(5, 15):
                    idx.index_section(
                        f"sec-conc-{i}", f"Concurrent {i}", f"preload data {i}"
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=searcher),
            threading.Thread(target=indexer_writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# =====================================================================
# get_indexer singleton
# =====================================================================


class TestGetIndexer:
    """Tests for the get_indexer() factory / singleton."""

    def setup_method(self):
        """Reset the global singleton before each test."""
        import sylion.memory.indexer as mod
        mod._indexer = None

    def teardown_method(self):
        """Clean up the global singleton after each test."""
        import sylion.memory.indexer as mod
        mod._indexer = None

    def test_returns_indexer_instance(self):
        idx = get_indexer()
        assert isinstance(idx, Indexer)

    def test_singleton_returns_same_instance(self):
        a = get_indexer()
        b = get_indexer()
        assert a is b

    def test_accepts_event_bus(self):
        bus = EventBus()
        idx = get_indexer(event_bus=bus)
        assert idx._event_bus is bus

    def test_accepts_db_path(self):
        idx = get_indexer(db_path=":memory:")
        assert isinstance(idx, Indexer)

    def test_second_call_ignores_parameters(self):
        """Once created, get_indexer returns the same instance regardless of args."""
        first = get_indexer(db_path=":memory:")
        second = get_indexer(db_path="/tmp/other.db")
        assert first is second


# =====================================================================
# Edge cases
# =====================================================================


class TestEdgeCases:
    """Edge-case scenarios for the Indexer."""

    def test_section_id_with_special_chars(self, indexer):
        result = indexer.index_section(
            "org/project:module@v2", "Special ID", "content here"
        )
        assert result["section_id"] == "org/project:module@v2"
        found = indexer._conn.execute(
            "SELECT * FROM index_metadata WHERE section_id = ?",
            ("org/project:module@v2",),
        ).fetchone()
        assert found is not None

    def test_very_long_content(self, indexer):
        content = "word " * 10000
        result = indexer.index_section("sec-long", "Long", content)
        assert result["word_count"] > 0
        stats = indexer.get_stats()
        assert stats["total_postings"] > 0

    def test_unicode_content(self, indexer):
        result = indexer.index_section(
            "sec-uni", "Unicode Test",
            "Some unicode characters but also ASCII words here.",
        )
        assert result["word_count"] > 0
        rows = indexer._conn.execute(
            "SELECT term FROM text_index WHERE section_id = 'sec-uni'"
        ).fetchall()
        terms = {r["term"] for r in rows}
        assert "ascii" in terms
        assert "words" in terms

    def test_duplicate_terms_across_sections(self, indexer):
        indexer.index_section("s1", "Shared", "common shared term")
        indexer.index_section("s2", "Shared", "common shared different")
        s1_rows = indexer._conn.execute(
            "SELECT term FROM text_index WHERE section_id = 's1'"
        ).fetchall()
        s2_rows = indexer._conn.execute(
            "SELECT term FROM text_index WHERE section_id = 's2'"
        ).fetchall()
        s1_terms = {r["term"] for r in s1_rows}
        s2_terms = {r["term"] for r in s2_rows}
        assert "shared" in s1_terms
        assert "shared" in s2_terms
        assert "common" in s1_terms
        assert "common" in s2_terms

    def test_single_character_terms_excluded(self, indexer):
        indexer.index_section("sec-short", "X Y Z", "a b c d e")
        rows = indexer._conn.execute(
            "SELECT term FROM text_index WHERE section_id = 'sec-short'"
        ).fetchall()
        terms = {r["term"] for r in rows}
        for t in terms:
            assert len(t) >= 2

    def test_search_limit_zero(self, indexer_with_data):
        results = indexer_with_data.search("python", limit=0)
        assert results == []

    def test_index_section_return_structure(self, indexer):
        result = indexer.index_section("sec-ret", "Return", "check return keys")
        assert set(result.keys()) == {"section_id", "unique_terms", "word_count"}

    def test_get_stats_return_structure(self, indexer):
        stats = indexer.get_stats()
        expected_keys = {
            "unique_terms", "total_postings", "indexed_sections", "avg_word_count",
        }
        assert set(stats.keys()) == expected_keys

    def test_search_return_structure(self, indexer_with_data):
        results = indexer_with_data.search("python")
        if results:
            expected_keys = {"section_id", "title", "score"}
            assert set(results[0].keys()) == expected_keys
