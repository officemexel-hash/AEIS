"""
Comprehensive tests for sylion.cognitive.chat_engine — ChatEngine class.

Tests: session CRUD, message CRUD, attachments, search, session stats,
       concurrent access, EventBus event emission, edge cases.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.cognitive.chat_engine import (
    ChatEngine,
    get_chat_engine,
    reset_chat_engine,
)
from sylion.core.event_bus import EventBus


def _payload(event_row: dict) -> dict:
    """Parse the JSON-encoded payload string from EventBus query results."""
    p = event_row["payload"]
    return json.loads(p) if isinstance(p, str) else p


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_chat_engine()
    yield
    reset_chat_engine()


@pytest.fixture
def engine() -> ChatEngine:
    return ChatEngine()


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def engine_with_bus(bus: EventBus) -> ChatEngine:
    return ChatEngine(event_bus=bus)


@pytest.fixture
def session_id(engine: ChatEngine) -> str:
    s = engine.create_session(title="Test Session", model_id="gpt-4")
    return s["session_id"]


# =====================================================================
# TestSessionCreate
# =====================================================================

class TestSessionCreate:

    def test_basic_create(self, engine):
        result = engine.create_session(title="Hello")
        assert result["title"] == "Hello"
        assert result["session_id"] != ""
        assert result["status"] == "active"

    def test_create_with_model_id(self, engine):
        result = engine.create_session(title="M", model_id="claude-3")
        assert result["model_id"] == "claude-3"

    def test_create_with_system_prompt(self, engine):
        result = engine.create_session(
            title="P", system_prompt="You are helpful."
        )
        assert result["system_prompt"] == "You are helpful."

    def test_create_has_timestamps(self, engine):
        before = time.time()
        result = engine.create_session(title="T")
        after = time.time()
        assert before <= result["created_at"] <= after
        assert result["created_at"] == result["updated_at"]

    def test_create_default_model_id_empty(self, engine):
        result = engine.create_session(title="NoModel")
        assert result["model_id"] == ""

    def test_create_default_system_prompt_empty(self, engine):
        result = engine.create_session(title="NoPrompt")
        assert result["system_prompt"] == ""

    def test_create_generates_unique_ids(self, engine):
        s1 = engine.create_session(title="A")
        s2 = engine.create_session(title="B")
        assert s1["session_id"] != s2["session_id"]


# =====================================================================
# TestSessionList
# =====================================================================

class TestSessionList:

    def test_list_empty(self, engine):
        assert engine.list_sessions() == []

    def test_list_after_create(self, engine):
        engine.create_session(title="S1")
        engine.create_session(title="S2")
        sessions = engine.list_sessions()
        assert len(sessions) == 2

    def test_list_default_excludes_archived(self, engine):
        s = engine.create_session(title="Arch")
        engine.archive_session(s["session_id"])
        active = engine.list_sessions(archived=False)
        assert len(active) == 0

    def test_list_archived_true_includes_archived(self, engine):
        s = engine.create_session(title="Arch")
        engine.archive_session(s["session_id"])
        all_sessions = engine.list_sessions(archived=True)
        assert len(all_sessions) == 1
        assert all_sessions[0]["status"] == "archived"

    def test_list_limit(self, engine):
        for i in range(10):
            engine.create_session(title=f"S{i}")
        sessions = engine.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_list_offset(self, engine):
        for i in range(5):
            engine.create_session(title=f"S{i}")
        first_page = engine.list_sessions(limit=2, offset=0)
        second_page = engine.list_sessions(limit=2, offset=2)
        assert len(first_page) == 2
        assert len(second_page) == 2
        assert first_page[0]["session_id"] != second_page[0]["session_id"]

    def test_list_ordered_by_updated_at_desc(self, engine):
        s1 = engine.create_session(title="Old")
        time.sleep(0.01)
        s2 = engine.create_session(title="New")
        sessions = engine.list_sessions()
        assert sessions[0]["session_id"] == s2["session_id"]
        assert sessions[1]["session_id"] == s1["session_id"]


# =====================================================================
# TestSessionGet
# =====================================================================

class TestSessionGet:

    def test_get_existing(self, engine):
        created = engine.create_session(title="Fetch")
        fetched = engine.get_session(created["session_id"])
        assert fetched is not None
        assert fetched["title"] == "Fetch"

    def test_get_nonexistent(self, engine):
        assert engine.get_session("nope") is None

    def test_get_returns_all_fields(self, engine):
        created = engine.create_session(
            title="Full", model_id="m1", system_prompt="sp"
        )
        fetched = engine.get_session(created["session_id"])
        assert "session_id" in fetched
        assert "title" in fetched
        assert "model_id" in fetched
        assert "system_prompt" in fetched
        assert "status" in fetched
        assert "created_at" in fetched
        assert "updated_at" in fetched


# =====================================================================
# TestSessionArchive
# =====================================================================

class TestSessionArchive:

    def test_archive_sets_status(self, engine):
        s = engine.create_session(title="Archive")
        result = engine.archive_session(s["session_id"])
        assert result is not None
        assert result["status"] == "archived"

    def test_archive_persists(self, engine):
        s = engine.create_session(title="Persist")
        engine.archive_session(s["session_id"])
        fetched = engine.get_session(s["session_id"])
        assert fetched["status"] == "archived"

    def test_archive_updates_timestamp(self, engine):
        s = engine.create_session(title="TS")
        original_updated = s["updated_at"]
        time.sleep(0.01)
        result = engine.archive_session(s["session_id"])
        assert result["updated_at"] > original_updated

    def test_archive_nonexistent_returns_none(self, engine):
        result = engine.archive_session("ghost-id")
        assert result is None


# =====================================================================
# TestMessageSend
# =====================================================================

class TestMessageSend:

    def test_send_basic(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "Hello")
        assert msg["session_id"] == session_id
        assert msg["role"] == "user"
        assert msg["content"] == "Hello"
        assert msg["message_id"] != ""

    def test_send_with_model_id(self, session_id, engine):
        msg = engine.send_message(
            session_id, "assistant", "Reply", model_id="gpt-4"
        )
        assert msg["model_id"] == "gpt-4"

    def test_send_with_metadata(self, session_id, engine):
        meta = {"tokens": 42, "latency_ms": 150}
        msg = engine.send_message(
            session_id, "user", "Meta", metadata=meta
        )
        assert msg["metadata"]["tokens"] == 42
        assert msg["metadata"]["latency_ms"] == 150

    def test_send_metadata_none_by_default(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "NoMeta")
        assert msg["metadata"] is None

    def test_send_updates_session_timestamp(self, session_id, engine):
        original = engine.get_session(session_id)["updated_at"]
        time.sleep(0.01)
        engine.send_message(session_id, "user", "Ping")
        updated = engine.get_session(session_id)["updated_at"]
        assert updated > original

    def test_send_generates_unique_ids(self, session_id, engine):
        m1 = engine.send_message(session_id, "user", "A")
        m2 = engine.send_message(session_id, "user", "B")
        assert m1["message_id"] != m2["message_id"]

    def test_send_has_created_at(self, session_id, engine):
        before = time.time()
        msg = engine.send_message(session_id, "user", "Time")
        after = time.time()
        assert before <= msg["created_at"] <= after


# =====================================================================
# TestMessageList
# =====================================================================

class TestMessageList:

    def test_list_empty_session(self, session_id, engine):
        assert engine.list_messages(session_id) == []

    def test_list_after_send(self, session_id, engine):
        engine.send_message(session_id, "user", "First")
        engine.send_message(session_id, "user", "Second")
        msgs = engine.list_messages(session_id)
        assert len(msgs) == 2

    def test_list_ordered_by_created_at_asc(self, session_id, engine):
        engine.send_message(session_id, "user", "A")
        engine.send_message(session_id, "user", "B")
        msgs = engine.list_messages(session_id)
        assert msgs[0]["content"] == "A"
        assert msgs[1]["content"] == "B"

    def test_list_limit(self, session_id, engine):
        for i in range(10):
            engine.send_message(session_id, "user", f"Msg{i}")
        msgs = engine.list_messages(session_id, limit=3)
        assert len(msgs) == 3

    def test_list_offset(self, session_id, engine):
        for i in range(5):
            engine.send_message(session_id, "user", f"Msg{i}")
        page1 = engine.list_messages(session_id, limit=2, offset=0)
        page2 = engine.list_messages(session_id, limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[1]["message_id"] != page2[0]["message_id"]

    def test_list_only_session_messages(self, engine):
        s1 = engine.create_session(title="S1")
        s2 = engine.create_session(title="S2")
        engine.send_message(s1["session_id"], "user", "In S1")
        engine.send_message(s2["session_id"], "user", "In S2")
        s1_msgs = engine.list_messages(s1["session_id"])
        assert len(s1_msgs) == 1
        assert s1_msgs[0]["content"] == "In S1"


# =====================================================================
# TestMessageGet
# =====================================================================

class TestMessageGet:

    def test_get_existing(self, session_id, engine):
        sent = engine.send_message(session_id, "user", "Fetch")
        fetched = engine.get_message(sent["message_id"])
        assert fetched is not None
        assert fetched["content"] == "Fetch"

    def test_get_nonexistent(self, engine):
        assert engine.get_message("ghost") is None

    def test_get_returns_all_fields(self, session_id, engine):
        sent = engine.send_message(
            session_id, "user", "Fields",
            model_id="m1", metadata={"k": "v"}
        )
        fetched = engine.get_message(sent["message_id"])
        assert "message_id" in fetched
        assert "session_id" in fetched
        assert "role" in fetched
        assert "content" in fetched
        assert "model_id" in fetched
        assert "metadata" in fetched
        assert "created_at" in fetched


# =====================================================================
# TestMessageDelete
# =====================================================================

class TestMessageDelete:

    def test_delete_existing(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "Delete me")
        assert engine.delete_message(msg["message_id"]) is True
        assert engine.get_message(msg["message_id"]) is None

    def test_delete_nonexistent(self, engine):
        assert engine.delete_message("nope") is False

    def test_delete_removes_from_list(self, session_id, engine):
        m1 = engine.send_message(session_id, "user", "Keep")
        m2 = engine.send_message(session_id, "user", "Remove")
        engine.delete_message(m2["message_id"])
        msgs = engine.list_messages(session_id)
        assert len(msgs) == 1
        assert msgs[0]["message_id"] == m1["message_id"]

    def test_delete_cascades_attachments(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "With attachment")
        engine.upload_attachment(
            msg["message_id"], "file.txt", "text/plain", b"data"
        )
        engine.delete_message(msg["message_id"])
        attachments = engine.list_attachments(msg["message_id"])
        assert len(attachments) == 0


# =====================================================================
# TestAttachments
# =====================================================================

class TestAttachmentUpload:

    def test_upload_basic(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "Attach")
        att = engine.upload_attachment(
            msg["message_id"], "test.txt", "text/plain", b"hello world"
        )
        assert att["attachment_id"] != ""
        assert att["filename"] == "test.txt"
        assert att["content_type"] == "text/plain"
        assert att["size"] == 11

    def test_upload_binary(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "Bin")
        data = bytes(range(256))
        att = engine.upload_attachment(
            msg["message_id"], "binary.bin", "application/octet-stream", data
        )
        assert att["size"] == 256

    def test_upload_has_timestamp(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "TS")
        before = time.time()
        att = engine.upload_attachment(
            msg["message_id"], "f.txt", "text/plain", b"x"
        )
        after = time.time()
        assert before <= att["created_at"] <= after


class TestAttachmentList:

    def test_list_empty(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "NoAtt")
        assert engine.list_attachments(msg["message_id"]) == []

    def test_list_after_upload(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "Att")
        engine.upload_attachment(msg["message_id"], "a.txt", "text/plain", b"a")
        engine.upload_attachment(msg["message_id"], "b.txt", "text/plain", b"b")
        atts = engine.list_attachments(msg["message_id"])
        assert len(atts) == 2

    def test_list_does_not_include_file_data(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "NoBlob")
        engine.upload_attachment(
            msg["message_id"], "f.txt", "text/plain", b"secret"
        )
        atts = engine.list_attachments(msg["message_id"])
        assert "file_data" not in atts[0]

    def test_list_ordered_by_created_at(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "Order")
        engine.upload_attachment(msg["message_id"], "a.txt", "text/plain", b"a")
        engine.upload_attachment(msg["message_id"], "b.txt", "text/plain", b"b")
        atts = engine.list_attachments(msg["message_id"])
        assert atts[0]["filename"] == "a.txt"
        assert atts[1]["filename"] == "b.txt"


class TestAttachmentGet:

    def test_get_existing(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "GetAtt")
        att = engine.upload_attachment(
            msg["message_id"], "data.json", "application/json", b'{"k":1}'
        )
        fetched = engine.get_attachment(att["attachment_id"])
        assert fetched is not None
        assert fetched["filename"] == "data.json"
        assert fetched["file_data"] == b'{"k":1}'

    def test_get_nonexistent(self, engine):
        assert engine.get_attachment("ghost") is None

    def test_get_includes_file_data(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "Blob")
        data = b"\x00\x01\x02\xff"
        att = engine.upload_attachment(
            msg["message_id"], "raw.bin", "application/octet-stream", data
        )
        fetched = engine.get_attachment(att["attachment_id"])
        assert fetched["file_data"] == data


# =====================================================================
# TestSearch
# =====================================================================

class TestSearchMessages:

    def test_search_finds_match(self, session_id, engine):
        engine.send_message(session_id, "user", "Python is great")
        engine.send_message(session_id, "user", "Java is okay")
        results = engine.search_messages("Python")
        assert len(results) == 1
        assert "Python" in results[0]["content"]

    def test_search_case_insensitive(self, session_id, engine):
        engine.send_message(session_id, "user", "Hello World")
        results = engine.search_messages("hello")
        assert len(results) == 1

    def test_search_no_match(self, session_id, engine):
        engine.send_message(session_id, "user", "Hello")
        results = engine.search_messages("xyzzy")
        assert len(results) == 0

    def test_search_multiple_results(self, session_id, engine):
        engine.send_message(session_id, "user", "test one")
        engine.send_message(session_id, "user", "no match")
        engine.send_message(session_id, "user", "test two")
        results = engine.search_messages("test")
        assert len(results) == 2

    def test_search_with_session_filter(self, engine):
        s1 = engine.create_session(title="S1")
        s2 = engine.create_session(title="S2")
        engine.send_message(s1["session_id"], "user", "findme in s1")
        engine.send_message(s2["session_id"], "user", "findme in s2")
        results = engine.search_messages("findme", session_id=s1["session_id"])
        assert len(results) == 1
        assert results[0]["session_id"] == s1["session_id"]

    def test_search_across_all_sessions(self, engine):
        s1 = engine.create_session(title="S1")
        s2 = engine.create_session(title="S2")
        engine.send_message(s1["session_id"], "user", "unique_keyword abc")
        engine.send_message(s2["session_id"], "user", "unique_keyword def")
        results = engine.search_messages("unique_keyword")
        assert len(results) == 2

    def test_search_limit(self, session_id, engine):
        for i in range(10):
            engine.send_message(session_id, "user", f"keyword item {i}")
        results = engine.search_messages("keyword", limit=3)
        assert len(results) == 3

    def test_search_empty_query(self, session_id, engine):
        engine.send_message(session_id, "user", "Some content")
        results = engine.search_messages("")
        assert len(results) == 1  # LIKE '%%' matches everything


# =====================================================================
# TestSessionStats
# =====================================================================

class TestSessionStats:

    def test_stats_empty_session(self, session_id, engine):
        stats = engine.get_session_stats(session_id)
        assert stats["total_messages"] == 0
        assert stats["messages_by_role"] == {}
        assert stats["attachment_count"] == 0
        assert stats["total_attachment_size"] == 0
        assert stats["first_message_at"] is None
        assert stats["last_message_at"] is None

    def test_stats_with_messages(self, session_id, engine):
        engine.send_message(session_id, "user", "Q1")
        engine.send_message(session_id, "assistant", "A1")
        engine.send_message(session_id, "user", "Q2")
        stats = engine.get_session_stats(session_id)
        assert stats["total_messages"] == 3
        assert stats["messages_by_role"]["user"] == 2
        assert stats["messages_by_role"]["assistant"] == 1

    def test_stats_with_attachments(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "With file")
        engine.upload_attachment(
            msg["message_id"], "a.txt", "text/plain", b"12345"
        )
        engine.upload_attachment(
            msg["message_id"], "b.txt", "text/plain", b"67890"
        )
        stats = engine.get_session_stats(session_id)
        assert stats["attachment_count"] == 2
        assert stats["total_attachment_size"] == 10

    def test_stats_timestamps(self, session_id, engine):
        engine.send_message(session_id, "user", "First")
        time.sleep(0.01)
        engine.send_message(session_id, "user", "Last")
        stats = engine.get_session_stats(session_id)
        assert stats["first_message_at"] is not None
        assert stats["last_message_at"] is not None
        assert stats["last_message_at"] > stats["first_message_at"]

    def test_stats_only_counts_session_messages(self, engine):
        s1 = engine.create_session(title="S1")
        s2 = engine.create_session(title="S2")
        engine.send_message(s1["session_id"], "user", "In S1")
        engine.send_message(s2["session_id"], "user", "In S2")
        engine.send_message(s2["session_id"], "user", "Also in S2")
        stats = engine.get_session_stats(s2["session_id"])
        assert stats["total_messages"] == 2


# =====================================================================
# TestEventBusIntegration
# =====================================================================

class TestEventBusIntegration:

    def test_session_created_event(self, engine_with_bus, bus):
        engine_with_bus.create_session(title="EventTest", model_id="m1")
        events = bus.query(topic="chat.session.created")
        assert len(events) == 1
        payload = _payload(events[0])
        assert "session_id" in payload
        assert payload["title"] == "EventTest"

    def test_message_sent_event(self, engine_with_bus, bus):
        s = engine_with_bus.create_session(title="Msg")
        engine_with_bus.send_message(
            s["session_id"], "user", "Test event"
        )
        events = bus.query(topic="chat.message.sent")
        assert len(events) == 1
        payload = _payload(events[0])
        assert payload["role"] == "user"

    def test_session_archived_event(self, engine_with_bus, bus):
        s = engine_with_bus.create_session(title="Arch")
        engine_with_bus.archive_session(s["session_id"])
        events = bus.query(topic="chat.session.archived")
        assert len(events) == 1

    def test_attachment_uploaded_event(self, engine_with_bus, bus):
        s = engine_with_bus.create_session(title="Att")
        msg = engine_with_bus.send_message(s["session_id"], "user", "File")
        engine_with_bus.upload_attachment(
            msg["message_id"], "f.txt", "text/plain", b"data"
        )
        events = bus.query(topic="chat.attachment.uploaded")
        assert len(events) == 1
        payload = _payload(events[0])
        assert payload["filename"] == "f.txt"

    def test_no_events_without_bus(self, engine):
        """Ensure no crash when event_bus is None."""
        s = engine.create_session(title="NoBus")
        engine.send_message(s["session_id"], "user", "Hello")
        engine.archive_session(s["session_id"])
        # No crash = success

    def test_event_source_module(self, engine_with_bus, bus):
        engine_with_bus.create_session(title="Source")
        events = bus.query(topic="chat.session.created")
        assert events[0]["source_module"] == "cognitive.chat_engine"


# =====================================================================
# TestSingleton
# =====================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        e = get_chat_engine()
        assert isinstance(e, ChatEngine)

    def test_get_idempotent(self):
        e1 = get_chat_engine()
        e2 = get_chat_engine()
        assert e1 is e2

    def test_reset_creates_new(self):
        e1 = get_chat_engine()
        reset_chat_engine()
        e2 = get_chat_engine()
        assert e1 is not e2

    def test_reset_returns_instance(self):
        e = reset_chat_engine()
        assert isinstance(e, ChatEngine)

    def test_reset_with_params(self):
        bus = EventBus()
        e = reset_chat_engine(event_bus=bus)
        assert e._event_bus is bus


# =====================================================================
# TestConcurrentAccess
# =====================================================================

class TestConcurrentAccess:

    def test_concurrent_send_messages(self, engine):
        s = engine.create_session(title="Concurrent")
        sid = s["session_id"]
        errors = []

        def send_n(n):
            try:
                for i in range(20):
                    engine.send_message(sid, "user", f"Msg {n}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=send_n, args=(i,))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        msgs = engine.list_messages(sid, limit=1000)
        assert len(msgs) == 100

    def test_concurrent_session_creation(self, engine):
        errors = []
        results = []

        def create_session(idx):
            try:
                s = engine.create_session(title=f"S{idx}")
                results.append(s)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_session, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        ids = [r["session_id"] for r in results]
        assert len(set(ids)) == 10  # all unique

    def test_concurrent_read_write(self, engine):
        s = engine.create_session(title="RW")
        sid = s["session_id"]
        engine.send_message(sid, "user", "Seed")
        errors = []

        def writer():
            try:
                for i in range(10):
                    engine.send_message(sid, "user", f"W{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(10):
                    engine.list_messages(sid)
                    engine.get_session_stats(sid)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# =====================================================================
# TestEdgeCases
# =====================================================================

class TestEdgeCases:

    def test_send_to_nonexistent_session_stores(self, engine):
        """send_message does not validate session_id — it still stores."""
        msg = engine.send_message("fake-session", "user", "Orphan")
        assert msg["session_id"] == "fake-session"

    def test_upload_to_nonexistent_message_stores(self, engine):
        """upload_attachment does not validate message_id — it still stores."""
        att = engine.upload_attachment(
            "fake-msg", "f.txt", "text/plain", b"data"
        )
        assert att["message_id"] == "fake-msg"

    def test_session_stats_for_nonexistent_session(self, engine):
        stats = engine.get_session_stats("ghost")
        assert stats["total_messages"] == 0
        assert stats["session_id"] == "ghost"

    def test_delete_already_deleted_message(self, engine):
        msg = engine.send_message("s1", "user", "X")
        assert engine.delete_message(msg["message_id"]) is True
        assert engine.delete_message(msg["message_id"]) is False

    def test_search_empty_database(self, engine):
        results = engine.search_messages("anything")
        assert results == []

    def test_list_messages_nonexistent_session(self, engine):
        msgs = engine.list_messages("no-session")
        assert msgs == []

    def test_list_attachments_nonexistent_message(self, engine):
        atts = engine.list_attachments("no-msg")
        assert atts == []

    def test_large_metadata(self, session_id, engine):
        big_meta = {f"key_{i}": f"value_{i}" for i in range(100)}
        msg = engine.send_message(
            session_id, "user", "Big meta", metadata=big_meta
        )
        fetched = engine.get_message(msg["message_id"])
        assert len(fetched["metadata"]) == 100

    def test_unicode_content(self, session_id, engine):
        msg = engine.send_message(
            session_id, "user",
            "Unicode: \u00e9\u00e8\u00ea \u4e2d\u6587 \U0001f600"
        )
        fetched = engine.get_message(msg["message_id"])
        assert "\u4e2d\u6587" in fetched["content"]

    def test_empty_content_message(self, session_id, engine):
        msg = engine.send_message(session_id, "user", "")
        assert msg["content"] == ""

    def test_archive_already_archived(self, engine):
        s = engine.create_session(title="Double")
        r1 = engine.archive_session(s["session_id"])
        r2 = engine.archive_session(s["session_id"])
        assert r1["status"] == "archived"
        assert r2["status"] == "archived"
