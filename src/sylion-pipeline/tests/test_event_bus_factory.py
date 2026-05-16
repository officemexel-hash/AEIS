"""Tests for sylion.core.event_bus_factory module."""

import os

import pytest

from sylion.core.event_bus_factory import get_event_bus_mode, create_event_bus


class TestGetEventBusMode:
    def test_default_is_inprocess(self):
        os.environ.pop("SYLION_EVENT_MODE", None)
        assert get_event_bus_mode() == "inprocess"

    def test_inprocess_mode(self):
        os.environ["SYLION_EVENT_MODE"] = "inprocess"
        assert get_event_bus_mode() == "inprocess"

    def test_nats_mode(self):
        os.environ["SYLION_EVENT_MODE"] = "nats"
        assert get_event_bus_mode() == "nats"

    def test_invalid_falls_back(self):
        os.environ["SYLION_EVENT_MODE"] = "invalid"
        assert get_event_bus_mode() == "inprocess"

    def test_case_insensitive(self):
        os.environ["SYLION_EVENT_MODE"] = "INPROCESS"
        assert get_event_bus_mode() == "inprocess"


class TestCreateEventBus:
    def test_create_inprocess(self):
        os.environ.pop("SYLION_EVENT_MODE", None)
        bus = create_event_bus(mode="inprocess")
        assert bus is not None

    def test_create_default(self):
        os.environ.pop("SYLION_EVENT_MODE", None)
        bus = create_event_bus()
        assert bus is not None

    def test_create_inprocess_publish_subscribe(self):
        bus = create_event_bus(mode="inprocess")
        from sylion.core.event_bus import SylionEvent
        received = []
        bus.subscribe("test.factory", lambda e: received.append(e))
        event = SylionEvent(event_id="f1", topic="test.factory", source_module="test")
        bus.publish(event)
        assert len(received) == 1
        assert received[0].event_id == "f1"
