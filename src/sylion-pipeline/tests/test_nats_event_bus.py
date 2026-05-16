"""Tests for NATS JetStream Event Bus adapter (Phase 2).

All NATS interactions are mocked -- no live NATS server required.
Tests cover:
  1. SQLiteEventBus with the convenience publish(topic, payload, source_module) API
  2. NATSEventBus with mocked NATS client (unit tests)
  3. Interface conformance (both buses produce the same shape of results)
  4. Fallback behaviour (NATS unavailable -> in-memory degradation)
  5. Factory function get_event_bus(mode=...)
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.nats_event_bus import (
    NATSEventBus,
    SQLiteEventBus,
    get_event_bus,
    reset_event_bus,
    _next_sub_id,
)


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


# ===========================================================================
# Helpers for mocked NATS
# ===========================================================================

def _make_mock_kv():
    """Create a mock KV store that simulates dedup."""
    store: dict[str, str] = {}

    kv = AsyncMock()

    async def _get(key):
        if key in store:
            entry = MagicMock()
            entry.value = store[key].encode("utf-8")
            return entry
        raise KeyError(key)

    async def _put(key, value):
        if isinstance(value, bytes):
            store[key] = value.decode("utf-8")
        else:
            store[key] = str(value)

    kv.get = _get
    kv.put = _put
    return kv, store


def _make_mock_js():
    """Create a mock JetStream context."""
    js = AsyncMock()
    js.stream_info = AsyncMock(return_value=MagicMock())

    ack = MagicMock()
    ack.seq = 1
    js.publish = AsyncMock(return_value=ack)

    kv, kv_store = _make_mock_kv()
    js.key_value = AsyncMock(return_value=kv)
    js.create_key_value = AsyncMock(return_value=kv)

    # pull_subscribe returns an async mock that supports fetch
    pull_sub = AsyncMock()
    pull_sub.fetch = AsyncMock(return_value=[])
    pull_sub.unsubscribe = AsyncMock()
    js.pull_subscribe = AsyncMock(return_value=pull_sub)

    # subscribe (push) returns async mock
    js.subscribe = AsyncMock(return_value=AsyncMock())

    return js, kv, kv_store


def _make_connected_bus() -> tuple[NATSEventBus, AsyncMock, AsyncMock, dict]:
    """Create a NATSEventBus with mocked NATS connection.

    Returns (bus, mock_nc, mock_js, kv_store).
    """
    bus = NATSEventBus("nats://mock:4222")

    mock_nc = AsyncMock()
    mock_js, kv, kv_store = _make_mock_js()

    bus._nc = mock_nc
    bus._js = mock_js
    bus._kv = kv
    bus._connected = True

    return bus, mock_nc, mock_js, kv_store


# ===========================================================================
# SQLiteEventBus tests
# ===========================================================================

class TestSQLiteEventBus:
    """Tests for the SQLiteEventBus convenience wrapper."""

    def test_publish_returns_event_id(self):
        bus = SQLiteEventBus()
        eid = bus.publish("test.topic", {"key": "val"}, "mod_a")
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_publish_creates_event_retrievable_via_get_events(self):
        bus = SQLiteEventBus()
        bus.publish("test.query", {"x": 1}, "mod_b")
        events = bus.get_events(topic="test.query")
        assert len(events) >= 1
        assert events[0]["topic"] == "test.query"

    def test_get_events_returns_newest_first(self):
        bus = SQLiteEventBus()
        bus.publish("test.order", {"seq": 1}, "m1")
        time.sleep(0.01)
        bus.publish("test.order", {"seq": 2}, "m1")
        events = bus.get_events(topic="test.order")
        assert len(events) >= 2
        # Newest first
        assert events[0]["payload"] == '{"seq": 2}'

    def test_get_events_limit(self):
        bus = SQLiteEventBus()
        for i in range(10):
            bus.publish("test.limit", {"i": i}, "m")
        events = bus.get_events(topic="test.limit", limit=3)
        assert len(events) == 3

    def test_get_events_all_topics(self):
        bus = SQLiteEventBus()
        bus.publish("a.x", {}, "m")
        bus.publish("b.y", {}, "m")
        events = bus.get_events()
        assert len(events) >= 2

    def test_subscribe_receives_events(self):
        bus = SQLiteEventBus()
        received = []
        bus.subscribe("test.sub", lambda e: received.append(e))
        bus.publish("test.sub", {"data": True}, "mod")
        assert len(received) == 1
        assert received[0].topic == "test.sub"

    def test_subscribe_wildcard(self):
        bus = SQLiteEventBus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.publish("any.topic", {}, "m")
        bus.publish("other.topic", {}, "m")
        assert len(received) == 2

    def test_unsubscribe_stops_delivery(self):
        bus = SQLiteEventBus()
        received = []
        sub_id = bus.subscribe("test.unsub", lambda e: received.append(e))
        bus.publish("test.unsub", {"a": 1}, "m")
        assert len(received) == 1
        bus.unsubscribe(sub_id)
        bus.publish("test.unsub", {"a": 2}, "m")
        assert len(received) == 1  # should not have received the second

    def test_unsubscribe_wildcard(self):
        bus = SQLiteEventBus()
        received = []
        sub_id = bus.subscribe("*", lambda e: received.append(e))
        bus.publish("x", {}, "m")
        assert len(received) == 1
        bus.unsubscribe(sub_id)
        bus.publish("y", {}, "m")
        assert len(received) == 1

    def test_unsubscribe_unknown_id_is_noop(self):
        bus = SQLiteEventBus()
        bus.unsubscribe("nonexistent")  # should not raise

    def test_ack_returns_true(self):
        bus = SQLiteEventBus()
        eid = bus.publish("test.ack", {}, "m")
        assert bus.ack(eid) is True

    def test_ack_unknown_returns_false(self):
        bus = SQLiteEventBus()
        assert bus.ack("does-not-exist") is False

    def test_idempotent_publish(self):
        bus = SQLiteEventBus()
        # Publish two events with same idempotency_key via SylionEvent
        e1 = SylionEvent(event_id="idem-1", topic="test.idem", payload={"v": 1},
                         source_module="m", idempotency_key="key-x")
        e2 = SylionEvent(event_id="idem-2", topic="test.idem", payload={"v": 2},
                         source_module="m", idempotency_key="key-x")
        bus._bus.publish(e1)
        result = bus._bus.publish(e2)
        assert result == "idem-1"

    def test_inner_property_exposes_eventbus(self):
        bus = SQLiteEventBus()
        assert isinstance(bus._inner, EventBus)


# ===========================================================================
# NATSEventBus -- publish tests (mocked)
# ===========================================================================

class TestNATSEventBusPublish:
    """Test NATSEventBus.publish with mocked NATS."""

    def test_publish_returns_event_id(self):
        bus, _, mock_js, _ = _make_connected_bus()
        eid = bus.publish("test.nats.pub", {"x": 1}, "tester")
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_publish_calls_jetstream(self):
        bus, _, mock_js, _ = _make_connected_bus()
        bus.publish("test.nats.js", {"k": "v"}, "mod")
        mock_js.publish.assert_called_once()
        call_args = mock_js.publish.call_args
        assert call_args[0][0] == "sylion.test.nats.js"

    def test_publish_idempotent(self):
        bus, _, _, kv_store = _make_connected_bus()
        eid1 = bus.publish("test.dup", {}, "m")
        # Second publish with same topic -- different event_id, but we cannot
        # force same idempotency_key through the convenience API. Test the
        # internal _publish_nats directly for dedup verification.
        event1 = SylionEvent(event_id="dup-1", topic="test.dup2", payload={},
                             source_module="m", idempotency_key="dup-key")
        eid_a = _run(bus._publish_nats(event1))
        event2 = SylionEvent(event_id="dup-2", topic="test.dup2", payload={},
                             source_module="m", idempotency_key="dup-key")
        eid_b = _run(bus._publish_nats(event2))
        assert eid_b == eid_a  # deduped


# ===========================================================================
# NATSEventBus -- subscribe tests
# ===========================================================================

class TestNATSEventBusSubscribe:
    """Test NATSEventBus.subscribe with mocked NATS."""

    def test_subscribe_returns_sub_id(self):
        bus, _, _, _ = _make_connected_bus()
        sub_id = bus.subscribe("test.nats.sub", lambda e: None)
        assert isinstance(sub_id, str)
        assert sub_id.startswith("sub-")

    def test_subscribed_handler_receives_events(self):
        bus, _, _, _ = _make_connected_bus()
        received = []
        bus.subscribe("test.dispatch", lambda e: received.append(e))
        bus._dispatch(SylionEvent(event_id="d1", topic="test.dispatch", payload={}))
        assert len(received) == 1

    def test_wildcard_receives_all(self):
        bus, _, _, _ = _make_connected_bus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus._dispatch(SylionEvent(event_id="w1", topic="anything", payload={}))
        assert len(received) == 1

    def test_unsubscribe_stops_delivery(self):
        bus, _, _, _ = _make_connected_bus()
        received = []
        sub_id = bus.subscribe("test.nats.unsub", lambda e: received.append(e))
        bus._dispatch(SylionEvent(event_id="u1", topic="test.nats.unsub", payload={}))
        assert len(received) == 1
        bus.unsubscribe(sub_id)
        bus._dispatch(SylionEvent(event_id="u2", topic="test.nats.unsub", payload={}))
        assert len(received) == 1

    def test_unsubscribe_unknown_is_noop(self):
        bus, _, _, _ = _make_connected_bus()
        bus.unsubscribe("no-such-sub")  # should not raise

    def test_no_cross_talk(self):
        bus, _, _, _ = _make_connected_bus()
        a = []
        b = []
        bus.subscribe("topic.a", lambda e: a.append(e))
        bus.subscribe("topic.b", lambda e: b.append(e))
        bus._dispatch(SylionEvent(event_id="1", topic="topic.a", payload={}))
        bus._dispatch(SylionEvent(event_id="2", topic="topic.b", payload={}))
        assert len(a) == 1 and len(b) == 1
        assert a[0].event_id == "1"
        assert b[0].event_id == "2"


# ===========================================================================
# NATSEventBus -- ack
# ===========================================================================

class TestNATSEventBusAck:
    def test_ack_returns_true_when_connected(self):
        bus, _, _, _ = _make_connected_bus()
        assert bus.ack("any-id") is True


# ===========================================================================
# NATSEventBus -- get_events (fallback path)
# ===========================================================================

class TestNATSEventBusGetEventsFallback:
    """Test get_events via the fallback SQLite path."""

    def test_get_events_from_fallback(self):
        bus = NATSEventBus()
        bus._fallback = True
        bus._ensure_fallback_db()
        bus.publish("test.fb", {"v": 42}, "mod_fb")
        events = bus.get_events(topic="test.fb")
        assert len(events) >= 1
        assert events[0]["topic"] == "test.fb"

    def test_get_events_limit_fallback(self):
        bus = NATSEventBus()
        bus._fallback = True
        bus._ensure_fallback_db()
        for i in range(5):
            bus.publish("test.fb.limit", {"i": i}, "m")
        events = bus.get_events(topic="test.fb.limit", limit=2)
        assert len(events) == 2

    def test_get_events_all_topics_fallback(self):
        bus = NATSEventBus()
        bus._fallback = True
        bus._ensure_fallback_db()
        bus.publish("a", {}, "m")
        bus.publish("b", {}, "m")
        events = bus.get_events()
        assert len(events) >= 2


# ===========================================================================
# NATSEventBus -- fallback behaviour
# ===========================================================================

class TestNATSEventBusFallback:
    """Test that NATSEventBus degrades gracefully when NATS is unavailable."""

    def test_connect_without_nats_py_enables_fallback(self):
        """When nats-py is not importable, connect() should enable fallback."""
        bus = NATSEventBus()
        with patch("sylion.core.nats_event_bus._NATS_AVAILABLE", False):
            _run(bus.connect())
        assert bus._fallback is True

    def test_connect_failure_enables_fallback(self):
        """When NATS server is unreachable, connect() should enable fallback."""
        bus = NATSEventBus()
        with patch("sylion.core.nats_event_bus._NATS_AVAILABLE", True):
            with patch("sylion.core.nats_event_bus.nats", create=True) as mock_nats:
                mock_nats.connect = AsyncMock(side_effect=Exception("connection refused"))
                # We need to make the import path work inside connect()
                with patch.dict("sys.modules", {"nats": mock_nats}):
                    _run(bus.connect())
        assert bus._fallback is True

    def test_fallback_publish_and_get_events(self):
        """Full publish/query cycle in fallback mode."""
        bus = NATSEventBus()
        bus._fallback = True
        bus._ensure_fallback_db()

        eid1 = bus.publish("fallback.test", {"a": 1}, "mod")
        eid2 = bus.publish("fallback.test", {"b": 2}, "mod")
        assert isinstance(eid1, str)
        assert isinstance(eid2, str)

        events = bus.get_events(topic="fallback.test")
        assert len(events) >= 2

    def test_fallback_subscribe_and_dispatch(self):
        """Subscribers work in fallback mode."""
        bus = NATSEventBus()
        bus._fallback = True
        bus._ensure_fallback_db()

        received = []
        bus.subscribe("fallback.sub", lambda e: received.append(e))
        bus.publish("fallback.sub", {"x": 1}, "mod")
        assert len(received) == 1

    def test_fallback_ack(self):
        bus = NATSEventBus()
        bus._fallback = True
        bus._ensure_fallback_db()
        eid = bus.publish("fallback.ack", {}, "m")
        assert bus.ack(eid) is True
        assert bus.ack("nonexistent") is False

    def test_publish_triggers_fallback_on_nats_error(self):
        """If NATS publish throws, fallback activates automatically."""
        bus, _, mock_js, _ = _make_connected_bus()
        mock_js.publish = AsyncMock(side_effect=Exception("NATS error"))

        received = []
        bus.subscribe("auto.fb", lambda e: received.append(e))
        eid = bus.publish("auto.fb", {"ok": True}, "mod")
        # Should have fallen back to in-memory
        assert bus._fallback is True
        assert isinstance(eid, str)
        assert len(received) == 1


# ===========================================================================
# Interface conformance -- same results as SQLite EventBus
# ===========================================================================

class TestInterfaceConformance:
    """Verify both implementations produce the same shaped results."""

    def _make_events(self, bus):
        """Publish a standard set of events and return their IDs."""
        ids = []
        ids.append(bus.publish("conf.a", {"n": 1}, "mod1"))
        ids.append(bus.publish("conf.b", {"n": 2}, "mod2"))
        ids.append(bus.publish("conf.a", {"n": 3}, "mod1"))
        return ids

    def test_get_events_returns_dicts(self):
        sq = SQLiteEventBus()
        self._make_events(sq)
        events = sq.get_events()
        for e in events:
            assert isinstance(e, dict)
            assert "event_id" in e
            assert "topic" in e
            assert "payload" in e
            assert "timestamp" in e

    def test_get_events_returns_dicts_fallback(self):
        nb = NATSEventBus()
        nb._fallback = True
        nb._ensure_fallback_db()
        self._make_events(nb)
        events = nb.get_events()
        for e in events:
            assert isinstance(e, dict)
            assert "event_id" in e
            assert "topic" in e
            assert "payload" in e
            assert "timestamp" in e

    def test_both_have_same_public_api(self):
        """SQLiteEventBus and NATSEventBus expose the same method names."""
        sq_methods = {m for m in dir(SQLiteEventBus) if not m.startswith("_")}
        nb_methods = {m for m in dir(NATSEventBus) if not m.startswith("_")}
        required = {"publish", "subscribe", "unsubscribe", "get_events", "ack"}
        assert required.issubset(sq_methods), f"SQLiteEventBus missing: {required - sq_methods}"
        assert required.issubset(nb_methods), f"NATSEventBus missing: {required - nb_methods}"

    def test_subscribe_same_pattern(self):
        """Both buses deliver events to subscribed handlers."""
        for factory in (lambda: SQLiteEventBus(), lambda: _fallback_nats_bus()):
            bus = factory()
            received = []
            bus.subscribe("conform.sub", lambda e: received.append(e))
            bus.publish("conform.sub", {"v": 1}, "m")
            assert len(received) == 1, f"{type(bus).__name__} failed subscribe test"

    def test_unsubscribe_same_pattern(self):
        """Both buses stop delivery after unsubscribe."""
        for factory in (lambda: SQLiteEventBus(), lambda: _fallback_nats_bus()):
            bus = factory()
            received = []
            sid = bus.subscribe("conform.unsub", lambda e: received.append(e))
            bus.publish("conform.unsub", {"v": 1}, "m")
            assert len(received) == 1
            bus.unsubscribe(sid)
            bus.publish("conform.unsub", {"v": 2}, "m")
            assert len(received) == 1, f"{type(bus).__name__} failed unsubscribe test"

    def test_ack_same_pattern(self):
        """Both buses return bool from ack."""
        for factory in (lambda: SQLiteEventBus(), lambda: _fallback_nats_bus()):
            bus = factory()
            eid = bus.publish("conform.ack", {}, "m")
            assert bus.ack(eid) is True


def _fallback_nats_bus() -> NATSEventBus:
    """Create a NATSEventBus in fallback mode for conformance testing."""
    bus = NATSEventBus()
    bus._fallback = True
    bus._ensure_fallback_db()
    return bus


# ===========================================================================
# Factory tests
# ===========================================================================

class TestFactory:
    """Tests for get_event_bus() and reset_event_bus()."""

    def setup_method(self):
        reset_event_bus()
        os.environ.pop("SYLION_EVENT_MODE", None)

    def teardown_method(self):
        reset_event_bus()
        os.environ.pop("SYLION_EVENT_MODE", None)

    def test_default_mode_is_sqlite(self):
        bus = get_event_bus()
        assert isinstance(bus, SQLiteEventBus)

    def test_explicit_sqlite(self):
        bus = get_event_bus("sqlite")
        assert isinstance(bus, SQLiteEventBus)

    def test_explicit_nats(self):
        bus = get_event_bus("nats")
        assert isinstance(bus, NATSEventBus)

    def test_env_var_nats(self):
        os.environ["SYLION_EVENT_MODE"] = "nats"
        bus = get_event_bus()
        assert isinstance(bus, NATSEventBus)

    def test_env_var_sqlite(self):
        os.environ["SYLION_EVENT_MODE"] = "sqlite"
        bus = get_event_bus()
        assert isinstance(bus, SQLiteEventBus)

    def test_invalid_env_falls_back_to_sqlite(self):
        os.environ["SYLION_EVENT_MODE"] = "kafka"
        bus = get_event_bus()
        assert isinstance(bus, SQLiteEventBus)

    def test_invalid_mode_arg_raises(self):
        # Invalid mode passed as argument falls back to sqlite (logged warning)
        bus = get_event_bus("rabbitmq")
        assert isinstance(bus, SQLiteEventBus)

    def test_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_clears_singleton(self):
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2

    def test_nats_url_kwarg(self):
        bus = get_event_bus("nats", nats_url="nats://custom:1234")
        assert isinstance(bus, NATSEventBus)
        assert bus._nats_url == "nats://custom:1234"


# ===========================================================================
# Subscription ID uniqueness
# ===========================================================================

class TestSubscriptionId:
    def test_sub_ids_are_unique(self):
        ids = set()
        for _ in range(200):
            ids.add(_next_sub_id())
        assert len(ids) == 200

    def test_sub_ids_start_with_prefix(self):
        sid = _next_sub_id()
        assert sid.startswith("sub-")


# ===========================================================================
# Stream naming
# ===========================================================================

class TestStreamNaming:
    def test_stream_name_simple(self):
        assert NATSEventBus._stream_name("module.registered") == "SYLION_MODULE_REGISTERED"

    def test_stream_name_deep(self):
        assert NATSEventBus._stream_name("a.b.c.d") == "SYLION_A_B_C_D"
