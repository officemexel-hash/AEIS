"""Tests for sylion.memory.kanon_access -- KanonAccess."""

import pytest

from sylion.memory.kanon_access import KanonAccess, KanonSection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ka():
    return KanonAccess(db_path=":memory:")


# ---------------------------------------------------------------------------
# KanonSection dataclass
# ---------------------------------------------------------------------------

class TestKanonSection:
    def test_auto_generates_section_id(self):
        s = KanonSection(title="Test", content="Body")
        assert len(s.section_id) > 0

    def test_auto_computes_hash(self):
        s = KanonSection(content="hello world")
        assert len(s.hash) == 64  # SHA-256

    def test_no_hash_without_content(self):
        s = KanonSection(title="Empty")
        assert s.hash == ""

    def test_explicit_id_preserved(self):
        s = KanonSection(section_id="my-id", content="test")
        assert s.section_id == "my-id"

    def test_different_content_different_hash(self):
        s1 = KanonSection(content="alpha")
        s2 = KanonSection(content="beta")
        assert s1.hash != s2.hash


# ---------------------------------------------------------------------------
# load_text() - separator-based parsing
# ---------------------------------------------------------------------------

class TestLoadText:
    def test_load_with_dash_separators(self, ka):
        raw = "Section one content\n---\nSection two content"
        r = ka.load_text(raw)
        assert r["sections_loaded"] == 2

    def test_load_with_headers(self, ka):
        raw = "# Chapter One\nContent one\n# Chapter Two\nContent two"
        r = ka.load_text(raw)
        assert r["sections_loaded"] >= 2

    def test_load_returns_section_ids(self, ka):
        r = ka.load_text("# Title\nBody text")
        assert len(r["section_ids"]) > 0

    def test_load_empty_text(self, ka):
        r = ka.load_text("")
        assert r["sections_loaded"] == 0

    def test_load_whitespace_only(self, ka):
        r = ka.load_text("   \n   \n   ")
        assert r["sections_loaded"] == 0

    def test_title_extracted_from_header(self, ka):
        r = ka.load_text("# My Title\nSome content here")
        sections = ka.list_sections()
        assert sections[0]["title"] == "My Title"

    def test_chapter_derived_from_title(self, ka):
        r = ka.load_text("# Chapter Alpha: Section\nBody")
        sections = ka.list_sections()
        assert sections[0]["chapter"] == "Chapter Alpha"

    def test_section_numbering(self, ka):
        raw = "# S1\nBody1\n---\n# S2\nBody2\n---\n# S3\nBody3"
        ka.load_text(raw)
        sections = ka.list_sections()
        assert sections[0]["section_number"] == 1
        assert sections[1]["section_number"] == 2
        assert sections[2]["section_number"] == 3


# ---------------------------------------------------------------------------
# store_section()
# ---------------------------------------------------------------------------

class TestStoreSection:
    def test_store_returns_id_and_hash(self, ka):
        s = KanonSection(title="Test", content="Hello world")
        r = ka.store_section(s)
        assert "section_id" in r
        assert "hash" in r

    def test_store_persists(self, ka):
        s = KanonSection(title="Persist", content="Stored content")
        ka.store_section(s)
        fetched = ka.get_section(s.section_id)
        assert fetched is not None
        assert fetched["title"] == "Persist"

    def test_store_replace_existing(self, ka):
        s1 = KanonSection(section_id="dup", title="First", content="V1")
        ka.store_section(s1)
        s2 = KanonSection(section_id="dup", title="Second", content="V2")
        ka.store_section(s2)
        fetched = ka.get_section("dup")
        assert fetched["title"] == "Second"


# ---------------------------------------------------------------------------
# get_section()
# ---------------------------------------------------------------------------

class TestGetSection:
    def test_get_existing(self, ka):
        ka.load_text("# Test\nContent")
        sections = ka.list_sections()
        sid = sections[0]["section_id"]
        fetched = ka.get_section(sid)
        assert fetched is not None
        assert fetched["section_id"] == sid

    def test_get_nonexistent(self, ka):
        assert ka.get_section("nope") is None


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_by_content(self, ka):
        ka.load_text("# Alpha\nThe quick brown fox\n# Beta\nLazy dog runs")
        results = ka.search("quick brown")
        assert len(results) == 1
        assert "Alpha" in results[0]["title"]

    def test_search_by_title(self, ka):
        ka.load_text("# Foobar Rules\nSome content\n# Other\nMore")
        results = ka.search("Foobar")
        assert len(results) >= 1

    def test_search_no_results(self, ka):
        ka.load_text("# Hello\nWorld")
        assert ka.search("nonexistent") == []

    def test_search_limit(self, ka):
        raw = "\n---\n".join([f"# Section {i}\nkeyword match" for i in range(5)])
        ka.load_text(raw)
        results = ka.search("keyword", limit=3)
        assert len(results) <= 3


# ---------------------------------------------------------------------------
# list_sections()
# ---------------------------------------------------------------------------

class TestListSections:
    def test_list_all(self, ka):
        ka.load_text("# A\nA content\n---\n# B\nB content")
        sections = ka.list_sections()
        assert len(sections) == 2

    def test_filter_by_chapter(self, ka):
        ka.load_text("# Chapter X: Part 1\nBody\n---\n# Chapter Y: Part 2\nBody")
        x_sections = ka.list_sections(chapter="Chapter X")
        assert len(x_sections) == 1

    def test_empty_list(self, ka):
        assert ka.list_sections() == []

    def test_ordered_by_section_number(self, ka):
        raw = "# First\nFirst content\n---\n# Second\nSecond content\n---\n# Third\nThird content"
        ka.load_text(raw)
        sections = ka.list_sections()
        numbers = [s["section_number"] for s in sections]
        assert numbers == sorted(numbers)


# ---------------------------------------------------------------------------
# get_full_text()
# ---------------------------------------------------------------------------

class TestGetFullText:
    def test_reconstructs_text(self, ka):
        ka.load_text("# Title One\nBody one\n---\n# Title Two\nBody two")
        full = ka.get_full_text()
        assert "# Title One" in full
        assert "Body one" in full
        assert "# Title Two" in full
        assert "Body two" in full

    def test_empty_db_returns_empty(self, ka):
        assert ka.get_full_text() == ""

    def test_sections_in_order(self, ka):
        ka.load_text("# First\nFirst body\n---\n# Second\nSecond body")
        full = ka.get_full_text()
        first_pos = full.index("First")
        second_pos = full.index("Second")
        assert first_pos < second_pos


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_load_text_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        ka = KanonAccess(event_bus=MockBus(), db_path=":memory:")
        ka.load_text("# Test\nContent")
        assert any(e.topic == "kanon.loaded" for e in events)

    def test_store_section_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        ka = KanonAccess(event_bus=MockBus(), db_path=":memory:")
        s = KanonSection(title="T", content="C")
        ka.store_section(s)
        assert any(e.topic == "kanon.section_stored" for e in events)
