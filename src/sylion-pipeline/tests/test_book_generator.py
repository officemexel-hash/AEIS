"""Tests for sylion.memory.book_generator — BookGenerator.

Uses in-memory SQLite (:memory:) for full isolation.
Autouse fixture resets the global singleton before/after each test.
"""

import json
import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.memory.book_generator import (
    BookGenerator,
    get_book_generator,
    reset_book_generator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_book_generator()
    yield
    reset_book_generator()


@pytest.fixture
def gen() -> BookGenerator:
    """Fresh BookGenerator backed by an in-memory database."""
    return BookGenerator()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def gen_with_bus(bus) -> BookGenerator:
    return BookGenerator(event_bus=bus)


# ---------------------------------------------------------------------------
# TestCreateBook  (7 tests)
# ---------------------------------------------------------------------------

class TestCreateBook:
    def test_returns_dict_with_book_id(self, gen):
        result = gen.create_book("Test Book")
        assert isinstance(result, dict)
        assert "book_id" in result
        assert isinstance(result["book_id"], str)
        assert len(result["book_id"]) > 0

    def test_title_stored(self, gen):
        result = gen.create_book("My Title")
        assert result["title"] == "My Title"

    def test_description_optional(self, gen):
        result = gen.create_book("No Desc")
        assert result["description"] is None

    def test_with_description(self, gen):
        result = gen.create_book("Desc", description="A description")
        assert result["description"] == "A description"

    def test_source_type_stored(self, gen):
        result = gen.create_book("Chat Book", source_type="chat")
        assert result["source_type"] == "chat"

    def test_source_id_and_created_by(self, gen):
        result = gen.create_book(
            "Full", source_type="pipeline", source_id="p42",
            created_by="alice",
        )
        assert result["source_type"] == "pipeline"
        assert result["source_id"] == "p42"
        assert result["created_by"] == "alice"

    def test_invalid_source_type_raises(self, gen):
        with pytest.raises(ValueError, match="Invalid source_type"):
            gen.create_book("Bad", source_type="invalid_type")


# ---------------------------------------------------------------------------
# TestGetBook  (4 tests)
# ---------------------------------------------------------------------------

class TestGetBook:
    def test_get_existing(self, gen):
        book = gen.create_book("Gettable")
        result = gen.get_book(book["book_id"])
        assert result is not None
        assert result["title"] == "Gettable"

    def test_get_nonexistent_returns_none(self, gen):
        assert gen.get_book("no_such_id") is None

    def test_get_includes_chapters(self, gen):
        book = gen.create_book("With Ch")
        gen.add_chapter(book["book_id"], "Ch1", "content", 0)
        result = gen.get_book(book["book_id"])
        assert "chapters" in result
        assert len(result["chapters"]) == 1

    def test_initial_chapter_count_is_zero(self, gen):
        book = gen.create_book("Empty")
        result = gen.get_book(book["book_id"])
        assert result["chapter_count"] == 0


# ---------------------------------------------------------------------------
# TestListBooks  (5 tests)
# ---------------------------------------------------------------------------

class TestListBooks:
    def test_list_empty(self, gen):
        assert gen.list_books() == []

    def test_list_returns_created(self, gen):
        gen.create_book("A")
        gen.create_book("B")
        books = gen.list_books()
        assert len(books) == 2
        titles = {b["title"] for b in books}
        assert titles == {"A", "B"}

    def test_list_filter_by_source_type(self, gen):
        gen.create_book("Chat", source_type="chat")
        gen.create_book("Manual", source_type="manual")
        chat_books = gen.list_books(source_type="chat")
        assert len(chat_books) == 1
        assert chat_books[0]["title"] == "Chat"

    def test_list_limit(self, gen):
        for i in range(10):
            gen.create_book(f"Book {i}")
        books = gen.list_books(limit=3)
        assert len(books) == 3

    def test_list_offset(self, gen):
        for i in range(6):
            gen.create_book(f"Book {i}")
        books = gen.list_books(limit=2, offset=4)
        assert len(books) == 2


# ---------------------------------------------------------------------------
# TestDeleteBook  (3 tests)
# ---------------------------------------------------------------------------

class TestDeleteBook:
    def test_delete_existing(self, gen):
        book = gen.create_book("Bye")
        assert gen.delete_book(book["book_id"]) is True
        assert gen.get_book(book["book_id"]) is None

    def test_delete_nonexistent(self, gen):
        assert gen.delete_book("no_id") is False

    def test_delete_cascades_chapters(self, gen):
        book = gen.create_book("Cascaded")
        gen.add_chapter(book["book_id"], "Ch1", "c1", 0)
        gen.add_chapter(book["book_id"], "Ch2", "c2", 1)
        gen.delete_book(book["book_id"])
        assert gen.list_chapters(book["book_id"]) == []


# ---------------------------------------------------------------------------
# TestAddChapter  (5 tests)
# ---------------------------------------------------------------------------

class TestAddChapter:
    def test_add_returns_chapter_dict(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Intro", "Hello", 0)
        assert ch["chapter_id"]
        assert ch["title"] == "Intro"
        assert ch["content"] == "Hello"
        assert ch["chapter_order"] == 0

    def test_add_increments_chapter_count(self, gen):
        book = gen.create_book("BK")
        gen.add_chapter(book["book_id"], "A", "a", 0)
        gen.add_chapter(book["book_id"], "B", "b", 1)
        updated = gen.get_book(book["book_id"])
        assert updated["chapter_count"] == 2

    def test_add_with_source(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(
            book["book_id"], "From Chat", "content", 0,
            source_type="chat", source_id="sess1",
        )
        assert ch["source_type"] == "chat"
        assert ch["source_id"] == "sess1"

    def test_add_to_nonexistent_book_raises(self, gen):
        with pytest.raises(ValueError, match="does not exist"):
            gen.add_chapter("no_book", "Ch", "c", 0)

    def test_created_at_populated(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Ch", "c", 0)
        assert ch["created_at"] > 0


# ---------------------------------------------------------------------------
# TestUpdateChapter  (5 tests)
# ---------------------------------------------------------------------------

class TestUpdateChapter:
    def test_update_title(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Old", "c", 0)
        updated = gen.update_chapter(ch["chapter_id"], title="New")
        assert updated["title"] == "New"

    def test_update_content(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Ch", "old", 0)
        updated = gen.update_chapter(ch["chapter_id"], content="new content")
        assert updated["content"] == "new content"

    def test_update_multiple_fields(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Old", "c", 0)
        updated = gen.update_chapter(
            ch["chapter_id"], title="Renamed", content="rewritten",
        )
        assert updated["title"] == "Renamed"
        assert updated["content"] == "rewritten"

    def test_update_nonexistent_returns_none(self, gen):
        assert gen.update_chapter("no_id", title="X") is None

    def test_update_no_allowed_fields_returns_chapter(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Ch", "c", 0)
        result = gen.update_chapter(ch["chapter_id"], bogus_field="ignored")
        assert result is not None
        assert result["title"] == "Ch"


# ---------------------------------------------------------------------------
# TestGetChapter  (3 tests)
# ---------------------------------------------------------------------------

class TestGetChapter:
    def test_get_existing(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Fetch", "c", 0)
        result = gen.get_chapter(ch["chapter_id"])
        assert result is not None
        assert result["title"] == "Fetch"

    def test_get_nonexistent(self, gen):
        assert gen.get_chapter("no_id") is None

    def test_get_reflects_updates(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Old", "c", 0)
        gen.update_chapter(ch["chapter_id"], title="New")
        result = gen.get_chapter(ch["chapter_id"])
        assert result["title"] == "New"


# ---------------------------------------------------------------------------
# TestListChapters  (3 tests)
# ---------------------------------------------------------------------------

class TestListChapters:
    def test_empty_for_new_book(self, gen):
        book = gen.create_book("BK")
        assert gen.list_chapters(book["book_id"]) == []

    def test_ordered_by_chapter_order(self, gen):
        book = gen.create_book("BK")
        gen.add_chapter(book["book_id"], "Third", "c3", 2)
        gen.add_chapter(book["book_id"], "First", "c1", 0)
        gen.add_chapter(book["book_id"], "Second", "c2", 1)
        chapters = gen.list_chapters(book["book_id"])
        assert [c["title"] for c in chapters] == ["First", "Second", "Third"]

    def test_multiple_books_isolated(self, gen):
        b1 = gen.create_book("B1")
        b2 = gen.create_book("B2")
        gen.add_chapter(b1["book_id"], "B1Ch", "c", 0)
        gen.add_chapter(b2["book_id"], "B2Ch", "c", 0)
        assert len(gen.list_chapters(b1["book_id"])) == 1
        assert len(gen.list_chapters(b2["book_id"])) == 1


# ---------------------------------------------------------------------------
# TestDeleteChapter  (3 tests)
# ---------------------------------------------------------------------------

class TestDeleteChapter:
    def test_delete_existing(self, gen):
        book = gen.create_book("BK")
        ch = gen.add_chapter(book["book_id"], "Bye", "c", 0)
        assert gen.delete_chapter(ch["chapter_id"]) is True
        assert gen.get_chapter(ch["chapter_id"]) is None

    def test_delete_decrements_count(self, gen):
        book = gen.create_book("BK")
        gen.add_chapter(book["book_id"], "A", "a", 0)
        ch = gen.add_chapter(book["book_id"], "B", "b", 1)
        gen.delete_chapter(ch["chapter_id"])
        updated = gen.get_book(book["book_id"])
        assert updated["chapter_count"] == 1

    def test_delete_nonexistent(self, gen):
        assert gen.delete_chapter("no_id") is False


# ---------------------------------------------------------------------------
# TestReorderChapters  (3 tests)
# ---------------------------------------------------------------------------

class TestReorderChapters:
    def test_reorder_changes_order(self, gen):
        book = gen.create_book("BK")
        ch1 = gen.add_chapter(book["book_id"], "A", "a", 0)
        ch2 = gen.add_chapter(book["book_id"], "B", "b", 1)
        ch3 = gen.add_chapter(book["book_id"], "C", "c", 2)

        # Reverse order
        gen.reorder_chapters(
            book["book_id"],
            [ch3["chapter_id"], ch2["chapter_id"], ch1["chapter_id"]],
        )
        chapters = gen.list_chapters(book["book_id"])
        assert [c["title"] for c in chapters] == ["C", "B", "A"]

    def test_reorder_returns_count(self, gen):
        book = gen.create_book("BK")
        ch1 = gen.add_chapter(book["book_id"], "A", "a", 0)
        ch2 = gen.add_chapter(book["book_id"], "B", "b", 1)
        result = gen.reorder_chapters(
            book["book_id"],
            [ch2["chapter_id"], ch1["chapter_id"]],
        )
        assert result["reordered"] == 2
        assert result["book_id"] == book["book_id"]

    def test_reorder_partial(self, gen):
        book = gen.create_book("BK")
        ch1 = gen.add_chapter(book["book_id"], "A", "a", 0)
        ch2 = gen.add_chapter(book["book_id"], "B", "b", 1)
        ch3 = gen.add_chapter(book["book_id"], "C", "c", 2)
        # Only reorder first two
        gen.reorder_chapters(
            book["book_id"],
            [ch2["chapter_id"], ch1["chapter_id"]],
        )
        chapters = gen.list_chapters(book["book_id"])
        # ch2 is now order 0, ch1 is order 1, ch3 stays at order 2
        assert chapters[0]["title"] == "B"
        assert chapters[1]["title"] == "A"


# ---------------------------------------------------------------------------
# TestGenerateFromChat  (4 tests)
# ---------------------------------------------------------------------------

class TestGenerateFromChat:
    def test_generates_chapters(self, gen):
        book = gen.create_book("Chat Book", source_type="chat")
        result = gen.generate_from_chat(book["book_id"], "sess1", chapter_count=3)
        assert result["status"] == "complete"
        assert result["chapter_count"] == 3

    def test_chapter_content_contains_session(self, gen):
        book = gen.create_book("Content")
        gen.generate_from_chat(book["book_id"], "sess42", chapter_count=2)
        chapters = gen.list_chapters(book["book_id"])
        assert len(chapters) == 2
        for ch in chapters:
            assert "sess42" in ch["content"]

    def test_nonexistent_book_returns_empty(self, gen):
        result = gen.generate_from_chat("no_book", "sess1")
        assert result == {}

    def test_chapters_have_chat_source(self, gen):
        book = gen.create_book("Src")
        gen.generate_from_chat(book["book_id"], "sess1", chapter_count=2)
        chapters = gen.list_chapters(book["book_id"])
        for ch in chapters:
            assert ch["source_type"] == "chat"
            assert ch["source_id"] == "sess1"


# ---------------------------------------------------------------------------
# TestGenerateFromCouncil  (3 tests)
# ---------------------------------------------------------------------------

class TestGenerateFromCouncil:
    def test_generates_four_chapters(self, gen):
        book = gen.create_book("Council Book", source_type="council")
        result = gen.generate_from_council(book["book_id"], "council-1")
        assert result["status"] == "complete"
        assert result["chapter_count"] == 4

    def test_chapter_titles_match_template(self, gen):
        book = gen.create_book("Titles")
        gen.generate_from_council(book["book_id"], "cs1")
        chapters = gen.list_chapters(book["book_id"])
        titles = [c["title"] for c in chapters]
        assert "Analyses" in titles
        assert "Discussion" in titles
        assert "Consolidated" in titles
        assert "Recommendations" in titles

    def test_nonexistent_book_returns_empty(self, gen):
        result = gen.generate_from_council("no_book", "cs1")
        assert result == {}


# ---------------------------------------------------------------------------
# TestExportBook  (4 tests)
# ---------------------------------------------------------------------------

class TestExportBook:
    def test_export_markdown(self, gen):
        book = gen.create_book("MD Book", description="A desc")
        gen.add_chapter(book["book_id"], "Intro", "Hello world", 0)
        md = gen.export_book(book["book_id"], "markdown")
        assert "# MD Book" in md
        assert "A desc" in md
        assert "## Intro" in md
        assert "Hello world" in md

    def test_export_json(self, gen):
        book = gen.create_book("JSON Book")
        gen.add_chapter(book["book_id"], "Ch1", "Content", 0)
        result = gen.export_book(book["book_id"], "json")
        parsed = json.loads(result)
        assert parsed["title"] == "JSON Book"
        assert len(parsed["chapters"]) == 1

    def test_export_nonexistent_returns_empty(self, gen):
        assert gen.export_book("no_id") == ""

    def test_export_default_format_is_markdown(self, gen):
        book = gen.create_book("Default")
        gen.add_chapter(book["book_id"], "Ch", "C", 0)
        result = gen.export_book(book["book_id"])
        assert result.startswith("# Default")


# ---------------------------------------------------------------------------
# TestGetBookStats  (4 tests)
# ---------------------------------------------------------------------------

class TestGetBookStats:
    def test_empty_stats(self, gen):
        stats = gen.get_book_stats()
        assert stats["total_books"] == 0
        assert stats["total_chapters"] == 0
        assert stats["avg_chapters_per_book"] == 0.0

    def test_counts_books(self, gen):
        gen.create_book("A")
        gen.create_book("B")
        assert gen.get_book_stats()["total_books"] == 2

    def test_counts_chapters(self, gen):
        book = gen.create_book("BK")
        gen.add_chapter(book["book_id"], "Ch1", "c1", 0)
        gen.add_chapter(book["book_id"], "Ch2", "c2", 1)
        assert gen.get_book_stats()["total_chapters"] == 2

    def test_by_source_type(self, gen):
        gen.create_book("Chat", source_type="chat")
        gen.create_book("Manual", source_type="manual")
        gen.create_book("Chat2", source_type="chat")
        stats = gen.get_book_stats()
        assert stats["by_source_type"]["chat"] == 2
        assert stats["by_source_type"]["manual"] == 1


# ---------------------------------------------------------------------------
# TestSearchBooks  (4 tests)
# ---------------------------------------------------------------------------

class TestSearchBooks:
    def test_search_by_title(self, gen):
        gen.create_book("Python Guide")
        gen.create_book("Rust Guide")
        results = gen.search_books("Python")
        assert len(results) == 1
        assert results[0]["title"] == "Python Guide"

    def test_search_by_description(self, gen):
        gen.create_book("Book A", description="Learn machine learning")
        results = gen.search_books("machine learning")
        assert len(results) == 1

    def test_search_by_chapter_content(self, gen):
        book = gen.create_book("Hidden Gems")
        gen.add_chapter(book["book_id"], "Ch", "deep learning techniques", 0)
        results = gen.search_books("deep learning")
        assert len(results) == 1
        assert results[0]["title"] == "Hidden Gems"

    def test_search_no_match(self, gen):
        gen.create_book("A")
        assert gen.search_books("zzz_nothing") == []


# ---------------------------------------------------------------------------
# TestEvents  (4 tests)
# ---------------------------------------------------------------------------

class TestEvents:
    def test_book_created_event(self, gen_with_bus, bus):
        events = []
        bus.subscribe("book.created", lambda e: events.append(e))
        gen_with_bus.create_book("Evt Book")
        assert len(events) == 1
        assert events[0].payload["title"] == "Evt Book"

    def test_chapter_added_event(self, gen_with_bus, bus):
        events = []
        bus.subscribe("book.chapter.added", lambda e: events.append(e))
        book = gen_with_bus.create_book("BK")
        gen_with_bus.add_chapter(book["book_id"], "Ch", "c", 0)
        assert len(events) == 1
        assert events[0].payload["book_id"] == book["book_id"]

    def test_book_generated_event_chat(self, gen_with_bus, bus):
        events = []
        bus.subscribe("book.generated", lambda e: events.append(e))
        book = gen_with_bus.create_book("BK")
        gen_with_bus.generate_from_chat(book["book_id"], "s1", chapter_count=2)
        assert len(events) == 1
        assert events[0].payload["source"] == "chat"

    def test_book_exported_event(self, gen_with_bus, bus):
        events = []
        bus.subscribe("book.exported", lambda e: events.append(e))
        book = gen_with_bus.create_book("BK")
        gen_with_bus.add_chapter(book["book_id"], "Ch", "c", 0)
        gen_with_bus.export_book(book["book_id"])
        assert len(events) == 1
        assert events[0].payload["format"] == "markdown"


# ---------------------------------------------------------------------------
# TestSingleton  (3 tests)
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_instance(self):
        inst = get_book_generator()
        assert isinstance(inst, BookGenerator)

    def test_idempotent(self):
        a = get_book_generator()
        b = get_book_generator()
        assert a is b

    def test_reset_clears(self):
        a = get_book_generator()
        reset_book_generator()
        b = get_book_generator()
        assert a is not b

    def test_reset_returns_new_instance(self):
        a = reset_book_generator()
        b = get_book_generator()
        assert a is b


# ---------------------------------------------------------------------------
# TestThreadSafety  (2 tests)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_create_books(self, gen):
        errors = []
        books = []

        def create(title):
            try:
                b = gen.create_book(title)
                books.append(b)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create, args=(f"Book-{i}",))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(books) == 20
        # All unique IDs
        ids = [b["book_id"] for b in books]
        assert len(set(ids)) == 20

    def test_concurrent_add_chapters(self, gen):
        book = gen.create_book("Concurrent Ch")
        errors = []
        chapters = []

        def add(order):
            try:
                ch = gen.add_chapter(
                    book["book_id"], f"Ch-{order}", f"Content-{order}", order,
                )
                chapters.append(ch)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(chapters) == 10
