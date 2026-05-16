"""Tests for NATS JetStream adapter and EventBus factory.

All NATS interactions are mocked — no live NATS server required.
"""
from __future__ import annotations

import asyncio
import json
import os
import struct
import time
import unittest
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.nats_adapter import NATSEventBus, _uuid_v7


def _run(coro):
    """Run an async coroutine synchronously (no pytest-asyncio needed)."""
    return asyncio.run(coro)


# ===========================================================================
# UUIDv7 tests
# ===========================================================================

class TestUUIDv7:
    """Tests for UUIDv7 generation."""

    def test_uuid_v7_format(self):
        uid = _uuid_v7()
        # Standard UUID string format: 8-4-4-4-12
        parts = uid.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12

    def test_uuid_v7_version_bits(self):
        uid = _uuid_v7()
        # Version nibble (char at position 12 after removing dashes) should be '7'
        raw = uid.replace("-", "")
        assert raw[12] == "7", f"expected version 7, got {raw[12]}"

    def test_uuid_v7_variant_bits(self):
        uid = _uuid_v7()
        raw = uid.replace("-", "")
        # Variant: top 2 bits of byte 8 must be 10 -> first hex digit is 8, 9, a, or b
        variant_char = raw[16]
        assert variant_char in ("8", "9", "a", "b"), f"bad variant nibble: {variant_char}"

    def test_uuid_v7_timestamps_advance(self):
        """Two UUIDs generated in sequence should have non-decreasing timestamps."""
        uid1 = _uuid_v7()
        uid2 = _uuid_v7()
        raw1 = bytes.fromhex(uid1.replace("-", ""))
        raw2 = bytes.fromhex(uid2.replace("-", ""))
        ts1 = struct.unpack(">Q", b"\x00\x00" + raw1[:6])[0]
        ts2 = struct.unpack(">Q", b"\x00\x00" + raw2[:6])[0]
        assert ts1 <= ts2, "UUIDv7 embedded timestamps should be non-decreasing"

    def test_uuid_v7_unique(self):
        """100 UUIDs should all be unique."""
        uuids = set(_uuid_v7() for _ in range(100))
        assert len(uuids) == 100

    def test_uuid_v7_timestamp_embedded(self):
        """The first 48 bits should encode a unix timestamp in milliseconds."""
        uid = _uuid_v7()
        raw = bytes.fromhex(uid.replace("-", ""))
        ts_ms = struct.unpack(">Q", b"\x00\x00" + raw[:6])[0]
        now_ms = int(time.time() * 1000)
        # Should be within 5 seconds of now
        assert abs(ts_ms - now_ms) < 5000, f"timestamp drift too large: {abs(ts_ms - now_ms)}ms"


# ===========================================================================
# NATSEventBus with mocked NATS
# ===========================================================================

def _make_mock_kv():
    """Create a mock KV store that simulates dedup."""
    store = {}

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
    return kv


def _make_mock_js():
    """Create a mock JetStream context."""
    js = AsyncMock()

    # stream_info: succeed (stream exists)
    js.stream_info = AsyncMock(return_value=MagicMock())

    # publish: return ack with sequence number
    ack = MagicMock()
    ack.seq = 1
    js.publish = AsyncMock(return_value=ack)

    # key_value: return mock KV
    kv = _make_mock_kv()
    js.key_value = AsyncMock(return_value=kv)
    js.create_key_value = AsyncMock(return_value=kv)

    return js, kv


def _make_connected_bus() -> tuple[NATSEventBus, AsyncMock, AsyncMock, dict]:
    """Create a NATSEventBus with mocked NATS connection.

    Returns (bus, mock_nc, mock_js, kv_store).
    """
    bus = NATSEventBus("nats://mock:4222")

    mock_nc = AsyncMock()
    mock_js, kv_store = _make_mock_js()

    bus._nc = mock_nc
    bus._js = mock_js
    bus._kv = kv_store
    bus._connected = True

    return bus, mock_nc, mock_js, kv_store


class TestNATSEventBusPublish:
    """Test NATSEventBus.publish with mocked NATS."""

    def test_publish_basic(self):
        bus, mock_nc, mock_js, kv_store = _make_connected_bus()
        event = SylionEvent(event_id="", topic="test.published", payload={"x": 1}, source_module="tester")

        eid = _run(bus._publish_async(event))

        assert eid != ""
        assert event.event_id == eid
        # Should have called JetStream publish
        mock_js.publish.assert_called_once()
        call_args = mock_js.publish.call_args
        assert call_args[0][0] == "sylion.test.published"

    def test_publish_assigns_uuid_v7(self):
        bus, _, _, _ = _make_connected_bus()
        event = SylionEvent(event_id="", topic="test.uuid", payload={})

        _run(bus._publish_async(event))

        assert event.event_id != ""
        # Verify it's a UUIDv7 (version nibble = 7)
        raw = event.event_id.replace("-", "")
        assert raw[12] == "7"

    def test_publish_assigns_timestamp(self):
        bus, _, _, _ = _make_connected_bus()
        event = SylionEvent(event_id="", topic="test.ts", payload={}, timestamp=0)

        before = time.time()
        _run(bus._publish_async(event))
        after = time.time()

        assert before <= event.timestamp <= after

    def test_publish_idempotent(self):
        bus, _, _, kv_store = _make_connected_bus()
        event = SylionEvent(event_id="dup-001", topic="test.dup", payload={}, idempotency_key="dup-key")

        # First publish
        eid1 = _run(bus._publish_async(event))

        # Second publish with same idempotency_key — should be deduped
        event2 = SylionEvent(event_id="dup-002", topic="test.dup", payload={}, idempotency_key="dup-key")
        eid2 = _run(bus._publish_async(event2))

        # Should return original event_id
        assert eid2 == eid1
        # NATS publish should only have been called once
        bus._js.publish.assert_called_once()


class TestNATSEventBusSubscribe:
    """Test NATSEventBus.subscribe with mocked NATS."""

    def test_subscribe_exact_topic(self):
        bus, _, _, _ = _make_connected_bus()
        received = []
        bus.subscribe("test.sub", lambda e: received.append(e))

        event = SylionEvent(event_id="sub-1", topic="test.sub", payload={})
        bus._dispatch(event)

        assert len(received) == 1
        assert received[0].event_id == "sub-1"

    def test_subscribe_wildcard(self):
        bus, _, _, _ = _make_connected_bus()
        received = []
        bus.subscribe("*", lambda e: received.append(e))

        event = SylionEvent(event_id="wc-1", topic="any.topic", payload={})
        bus._dispatch(event)

        assert len(received) == 1

    def test_subscribe_no_cross_talk(self):
        bus, _, _, _ = _make_connected_bus()
        received_a = []
        received_b = []
        bus.subscribe("topic.a", lambda e: received_a.append(e))
        bus.subscribe("topic.b", lambda e: received_b.append(e))

        bus._dispatch(SylionEvent(event_id="1", topic="topic.a", payload={}))
        bus._dispatch(SylionEvent(event_id="2", topic="topic.b", payload={}))

        assert len(received_a) == 1
        assert len(received_b) == 1
        assert received_a[0].event_id == "1"
        assert received_b[0].event_id == "2"


class TestNATSEventBusAck:
    """Test ack (no-op in NATS mode)."""

    def test_ack_returns_true(self):
        bus, _, _, _ = _make_connected_bus()
        assert bus.ack("any-id") is True


class TestNATSEventBusReplay:
    """Test replay dispatches events to subscribers."""

    def test_replay_dispatches(self):
        bus, _, _, _ = _make_connected_bus()
        received = []
        bus.subscribe("test.replay", lambda e: received.append(e))

        # Query returns events in DESC timestamp order (like the real query).
        # replay() reverses to chronological order before dispatch.
        events_data = [
            {"event_id": "r2", "topic": "test.replay", "payload": {}, "source_module": "", "timestamp": 2.0},
            {"event_id": "r1", "topic": "test.replay", "payload": {}, "source_module": "", "timestamp": 1.0},
        ]

        # Patch _query_async to return our data
        async def mock_query(topic=None, since=None, limit=100):
            return events_data

        bus._query_async = mock_query

        count = bus.replay()
        assert count == 2
        assert len(received) == 2
        # After reverse, chronological: r1 then r2
        assert received[0].event_id == "r1"
        assert received[1].event_id == "r2"


class TestNATSEventBusNotConnected:
    """Test error handling when bus is not connected."""

    def test_publish_raises_when_not_connected(self):
        bus = NATSEventBus()
        with pytest.raises(RuntimeError, match="not connected"):
            _run(bus._publish_async(
                SylionEvent(event_id="", topic="x", payload={})
            ))


# ===========================================================================
# EventBus Factory tests
# ===========================================================================

class TestEventBusFactory:
    """Test event_bus_factory module."""

    def setup_method(self):
        from sylion.core.event_bus_factory import reset_event_bus
        reset_event_bus()

    def teardown_method(self):
        from sylion.core.event_bus_factory import reset_event_bus
        reset_event_bus()
        # Clean env
        os.environ.pop("SYLION_EVENT_MODE", None)

    def test_default_mode_is_inprocess(self):
        from sylion.core.event_bus_factory import get_event_bus_mode
        assert get_event_bus_mode() == "inprocess"

    def test_nats_mode_from_env(self):
        from sylion.core.event_bus_factory import get_event_bus_mode
        os.environ["SYLION_EVENT_MODE"] = "nats"
        assert get_event_bus_mode() == "nats"

    def test_invalid_mode_falls_back(self):
        from sylion.core.event_bus_factory import get_event_bus_mode
        os.environ["SYLION_EVENT_MODE"] = "kafka"
        assert get_event_bus_mode() == "inprocess"

    def test_create_inprocess_returns_eventbus(self):
        from sylion.core.event_bus_factory import create_event_bus
        bus = create_event_bus("inprocess")
        assert isinstance(bus, EventBus)

    def test_create_nats_returns_nats_eventbus(self):
        from sylion.core.event_bus_factory import create_event_bus
        from sylion.core.nats_adapter import NATSEventBus
        bus = create_event_bus("nats")
        assert isinstance(bus, NATSEventBus)

    def test_singleton_inprocess(self):
        from sylion.core.event_bus_factory import create_event_bus
        bus1 = create_event_bus("inprocess")
        bus2 = create_event_bus("inprocess")
        assert bus1 is bus2

    def test_singleton_nats(self):
        from sylion.core.event_bus_factory import create_event_bus
        bus1 = create_event_bus("nats")
        bus2 = create_event_bus("nats")
        assert bus1 is bus2

    def test_different_modes_are_different_instances(self):
        from sylion.core.event_bus_factory import create_event_bus
        inproc = create_event_bus("inprocess")
        nats_bus = create_event_bus("nats")
        assert inproc is not nats_bus

    def test_invalid_mode_raises(self):
        from sylion.core.event_bus_factory import create_event_bus
        with pytest.raises(ValueError, match="invalid event bus mode"):
            create_event_bus("rabbitmq")

    def test_reset_clears_singletons(self):
        from sylion.core.event_bus_factory import create_event_bus, reset_event_bus
        bus1 = create_event_bus("inprocess")
        reset_event_bus()
        bus2 = create_event_bus("inprocess")
        assert bus1 is not bus2

    def test_factory_reads_env_when_mode_none(self):
        from sylion.core.event_bus_factory import create_event_bus
        from sylion.core.nats_adapter import NATSEventBus
        os.environ["SYLION_EVENT_MODE"] = "nats"
        bus = create_event_bus()
        assert isinstance(bus, NATSEventBus)


# ===========================================================================
# Integration: NATSEventBus API matches EventBus API
# ===========================================================================

class TestAPICompatibility:
    """Verify NATSEventBus has the same public methods as EventBus."""

    def test_has_publish(self):
        bus = NATSEventBus()
        assert hasattr(bus, "publish")
        assert callable(bus.publish)

    def test_has_subscribe(self):
        bus = NATSEventBus()
        assert hasattr(bus, "subscribe")
        assert callable(bus.subscribe)

    def test_has_query(self):
        bus = NATSEventBus()
        assert hasattr(bus, "query")
        assert callable(bus.query)

    def test_has_replay(self):
        bus = NATSEventBus()
        assert hasattr(bus, "replay")
        assert callable(bus.replay)

    def test_has_ack(self):
        bus = NATSEventBus()
        assert hasattr(bus, "ack")
        assert callable(bus.ack)

    def test_has_get_catalog(self):
        bus = NATSEventBus()
        assert hasattr(bus, "get_catalog")
        assert callable(bus.get_catalog)

    def test_has_connect(self):
        bus = NATSEventBus()
        assert hasattr(bus, "connect")
        assert callable(bus.connect)

    def test_has_close(self):
        bus = NATSEventBus()
        assert hasattr(bus, "close")
        assert callable(bus.close)

    def test_publish_signature_compatible(self):
        """publish(event) -> str on both classes."""
        import inspect
        eb_sig = inspect.signature(EventBus.publish)
        nb_sig = inspect.signature(NATSEventBus.publish)
        # Both should accept an event parameter and return str
        eb_params = list(eb_sig.parameters.keys())
        nb_params = list(nb_sig.parameters.keys())
        assert eb_params == nb_params, f"publish params differ: {eb_params} vs {nb_params}"

    def test_subscribe_signature_compatible(self):
        import inspect
        eb_sig = inspect.signature(EventBus.subscribe)
        nb_sig = inspect.signature(NATSEventBus.subscribe)
        eb_params = list(eb_sig.parameters.keys())
        nb_params = list(nb_sig.parameters.keys())
        assert eb_params == nb_params, f"subscribe params differ: {eb_params} vs {nb_params}"

    def test_query_signature_compatible(self):
        import inspect
        eb_sig = inspect.signature(EventBus.query)
        nb_sig = inspect.signature(NATSEventBus.query)
        eb_params = list(eb_sig.parameters.keys())
        nb_params = list(nb_sig.parameters.keys())
        assert eb_params == nb_params, f"query params differ: {eb_params} vs {nb_params}"
