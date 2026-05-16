"""Tests for sylion.memory.compact_layer -- CompactLayer."""

import pytest

from sylion.memory.compact_layer import (
    CompactLayer,
    CompactionRecord,
    _canonical_form,
    _canonical_hash,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cl():
    return CompactLayer(db_path=":memory:")


# ---------------------------------------------------------------------------
# _canonical_form() and _canonical_hash()
# ---------------------------------------------------------------------------

class TestCanonicalHelpers:
    def test_canonical_form_extracts_sorted_unique_words(self):
        cf = _canonical_form("Hello world hello")
        assert cf == "hello world"

    def test_canonical_form_case_insensitive(self):
        assert _canonical_form("Hello") == _canonical_form("hello")

    def test_canonical_form_extracts_alphanumeric(self):
        cf = _canonical_form("test123!@# abc")
        assert "test123" in cf
        assert "abc" in cf

    def test_canonical_hash_is_sha256(self):
        h = _canonical_hash("hello world")
        assert len(h) == 64  # SHA-256 hex length
        assert all(c in "0123456789abcdef" for c in h)

    def test_canonical_hash_deterministic(self):
        assert _canonical_hash("test") == _canonical_hash("test")

    def test_canonical_form_empty(self):
        assert _canonical_form("") == ""


# ---------------------------------------------------------------------------
# CompactionRecord dataclass
# ---------------------------------------------------------------------------

class TestCompactionRecord:
    def test_auto_generates_record_id(self):
        r = CompactionRecord()
        assert len(r.record_id) > 0

    def test_auto_generates_timestamp(self):
        r = CompactionRecord()
        assert r.created_at > 0

    def test_preserves_explicit_id(self):
        r = CompactionRecord(record_id="my-id")
        assert r.record_id == "my-id"


# ---------------------------------------------------------------------------
# compact()
# ---------------------------------------------------------------------------

class TestCompact:
    def test_basic_compaction(self, cl):
        text = "Hello world\nHello world\nFoo bar baz"
        result = cl.compact(text)
        assert "compacted" in result
        assert result["compact_size"] < result["original_size"]

    def test_compact_removes_duplicates(self, cl):
        text = "Line one\nLine one\nLine one"
        result = cl.compact(text)
        lines = result["compacted"].split("\n")
        assert len(lines) == 1

    def test_compact_returns_ratio(self, cl):
        text = "Hello world\nHello world\nFoo bar baz qux"
        result = cl.compact(text)
        assert result["ratio"] >= 1.0

    def test_compact_returns_fidelity(self, cl):
        text = "Hello world\nFoo bar baz"
        result = cl.compact(text)
        assert 0.0 <= result["fidelity_score"] <= 1.0

    def test_compact_empty_text(self, cl):
        result = cl.compact("")
        assert result["original_size"] == 0
        assert result["compact_size"] == 0

    def test_compact_single_line(self, cl):
        result = cl.compact("Single line here")
        assert result["compacted"] == "Single line here"

    def test_compact_whitespace_only_lines_skipped(self, cl):
        text = "Real content\n   \n\t\nMore content"
        result = cl.compact(text)
        assert "\t" not in result["compacted"]

    def test_compact_preserves_content_words(self, cl):
        text = "The quick brown fox jumps over the lazy dog"
        result = cl.compact(text)
        for word in ["quick", "brown", "fox", "lazy", "dog"]:
            assert word in result["compacted"].lower()


# ---------------------------------------------------------------------------
# compute_fidelity()
# ---------------------------------------------------------------------------

class TestComputeFidelity:
    def test_identical_text_fidelity_1(self, cl):
        f = cl.compute_fidelity("Hello world", "Hello world")
        assert f == 1.0

    def test_no_overlap_fidelity_0(self, cl):
        f = cl.compute_fidelity("aaa bbb", "ccc ddd")
        assert f == 0.0

    def test_partial_overlap(self, cl):
        f = cl.compute_fidelity("aaa bbb ccc", "bbb ccc ddd")
        assert 0.0 < f < 1.0

    def test_empty_both_returns_1(self, cl):
        f = cl.compute_fidelity("", "")
        assert f == 1.0

    def test_empty_original_nonempty_compact(self, cl):
        f = cl.compute_fidelity("", "something")
        assert f == 0.0

    def test_nonempty_original_empty_compact(self, cl):
        f = cl.compute_fidelity("something", "")
        assert f == 0.0


# ---------------------------------------------------------------------------
# record_compaction()
# ---------------------------------------------------------------------------

class TestRecordCompaction:
    def test_record_returns_dict(self, cl):
        r = cl.record_compaction("original text here", "compact text")
        assert "record_id" in r
        assert "ratio" in r
        assert "fidelity_score" in r

    def test_record_stores_in_db(self, cl):
        cl.record_compaction("original", "compact")
        records = cl.list_records()
        assert len(records) == 1

    def test_record_auto_computes_fidelity(self, cl):
        r = cl.record_compaction("hello world", "hello world")
        assert r["fidelity_score"] == 1.0

    def test_record_explicit_fidelity(self, cl):
        r = cl.record_compaction("hello", "hello", fidelity=0.95)
        assert r["fidelity_score"] == 0.95

    def test_multiple_records(self, cl):
        cl.record_compaction("a", "a")
        cl.record_compaction("b", "b")
        assert len(cl.list_records()) == 2


# ---------------------------------------------------------------------------
# get_stats()
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_stats(self, cl):
        stats = cl.get_stats()
        assert stats["total_records"] == 0
        assert stats["avg_ratio"] == 0.0
        assert stats["min_fidelity"] == 0.0
        assert stats["max_fidelity"] == 0.0

    def test_stats_after_records(self, cl):
        cl.record_compaction("aaa bbb ccc", "aaa bbb")  # partial
        cl.record_compaction("hello world", "hello world")  # full
        stats = cl.get_stats()
        assert stats["total_records"] == 2
        assert stats["avg_ratio"] > 0.0
        assert stats["min_fidelity"] <= stats["max_fidelity"]


# ---------------------------------------------------------------------------
# list_records()
# ---------------------------------------------------------------------------

class TestListRecords:
    def test_empty_list(self, cl):
        assert cl.list_records() == []

    def test_limit(self, cl):
        for i in range(5):
            cl.record_compaction(f"text number {i}", f"compact {i}")
        assert len(cl.list_records(limit=3)) == 3

    def test_order_newest_first(self, cl):
        import time
        cl.record_compaction("first", "first")
        time.sleep(0.01)
        cl.record_compaction("second", "second")
        records = cl.list_records()
        assert records[0]["original_size"] == 6  # "second"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_compact_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        cl = CompactLayer(event_bus=MockBus(), db_path=":memory:")
        cl.compact("Hello world")
        assert any(e.topic == "compact.compacted" for e in events)

    def test_record_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        cl = CompactLayer(event_bus=MockBus(), db_path=":memory:")
        cl.record_compaction("hello", "hello")
        assert any(e.topic == "compact.recorded" for e in events)
