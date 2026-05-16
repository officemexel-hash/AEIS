"""Tests for sylion.devices.device_registry -- DeviceRegistry."""

import json

import pytest

from sylion.devices.device_registry import (
    DeviceRegistry,
    LIFECYCLE_STATES,
    _VALID_TRANSITIONS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reg():
    return DeviceRegistry(db_path=":memory:")


def _register_device(reg, device_id="dev-001", transport="usb",
                     model="TestModel", firmware="1.0", capabilities=None):
    return reg.register(device_id, transport, model, firmware, capabilities)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_lifecycle_states_count(self):
        assert len(LIFECYCLE_STATES) == 7

    def test_lifecycle_states_order(self):
        expected = [
            "attached", "identified", "quarantined", "authorized",
            "provisioned", "active", "released",
        ]
        assert LIFECYCLE_STATES == expected

    def test_released_is_terminal(self):
        assert _VALID_TRANSITIONS["released"] == set()


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_returns_device(self, reg):
        d = _register_device(reg)
        assert d["device_id"] == "dev-001"
        assert d["transport"] == "usb"
        assert d["model"] == "TestModel"

    def test_initial_lifecycle_is_attached(self, reg):
        d = _register_device(reg)
        assert d["lifecycle"] == "attached"

    def test_capabilities_stored(self, reg):
        caps = {"sensor": True, "frequency": 2.4e9}
        d = _register_device(reg, capabilities=caps)
        assert d["capabilities"] == caps

    def test_default_capabilities_empty(self, reg):
        d = _register_device(reg)
        assert d["capabilities"] == {}

    def test_register_replaces_existing(self, reg):
        _register_device(reg, device_id="dup")
        d2 = _register_device(reg, device_id="dup", model="Updated")
        assert d2["model"] == "Updated"

    def test_firmware_stored(self, reg):
        d = _register_device(reg, firmware="2.1.3")
        assert d["firmware"] == "2.1.3"


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self, reg):
        _register_device(reg, device_id="abc")
        d = reg.get("abc")
        assert d is not None
        assert d["device_id"] == "abc"

    def test_get_nonexistent_returns_none(self, reg):
        assert reg.get("nope") is None

    def test_capabilities_deserialized(self, reg):
        _register_device(reg, capabilities={"x": 1})
        d = reg.get("dev-001")
        assert isinstance(d["capabilities"], dict)


# ---------------------------------------------------------------------------
# transition()
# ---------------------------------------------------------------------------

class TestTransition:
    def test_valid_forward_transition(self, reg):
        _register_device(reg)
        d = reg.transition("dev-001", "identified")
        assert d["lifecycle"] == "identified"

    def test_invalid_transition_raises(self, reg):
        _register_device(reg)
        with pytest.raises(ValueError, match="Invalid transition"):
            reg.transition("dev-001", "active")

    def test_unknown_lifecycle_raises(self, reg):
        _register_device(reg)
        with pytest.raises(ValueError, match="Unknown lifecycle"):
            reg.transition("dev-001", "exploded")

    def test_unknown_device_raises(self, reg):
        with pytest.raises(ValueError, match="Device not found"):
            reg.transition("ghost", "identified")

    def test_full_lifecycle_walk(self, reg):
        _register_device(reg)
        for state in ["identified", "quarantined", "authorized",
                       "provisioned", "active", "released"]:
            d = reg.transition("dev-001", state)
            assert d["lifecycle"] == state

    def test_release_from_any_state(self, reg):
        _register_device(reg)
        reg.transition("dev-001", "identified")
        d = reg.transition("dev-001", "released")
        assert d["lifecycle"] == "released"

    def test_no_transition_from_released(self, reg):
        _register_device(reg)
        reg.transition("dev-001", "identified")
        reg.transition("dev-001", "released")
        with pytest.raises(ValueError, match="Invalid transition"):
            reg.transition("dev-001", "attached")


# ---------------------------------------------------------------------------
# authorize()
# ---------------------------------------------------------------------------

class TestAuthorize:
    def test_authorize_quarantined_device(self, reg):
        _register_device(reg)
        reg.transition("dev-001", "identified")
        reg.transition("dev-001", "quarantined")
        d = reg.authorize("dev-001", "admin")
        assert d["lifecycle"] == "authorized"
        assert d["authorized_by"] == "admin"

    def test_authorize_non_quarantined_raises(self, reg):
        _register_device(reg)
        with pytest.raises(ValueError, match="must be quarantined"):
            reg.authorize("dev-001", "admin")

    def test_authorize_unknown_device_raises(self, reg):
        with pytest.raises(ValueError, match="Device not found"):
            reg.authorize("ghost", "admin")


# ---------------------------------------------------------------------------
# list_devices()
# ---------------------------------------------------------------------------

class TestListDevices:
    def test_list_all(self, reg):
        _register_device(reg, "d1")
        _register_device(reg, "d2")
        assert len(reg.list_devices()) == 2

    def test_filter_by_lifecycle(self, reg):
        _register_device(reg, "d1")
        _register_device(reg, "d2")
        reg.transition("d1", "identified")
        attached = reg.list_devices(lifecycle="attached")
        assert len(attached) == 1
        assert attached[0]["device_id"] == "d2"

    def test_empty_list(self, reg):
        assert reg.list_devices() == []


# ---------------------------------------------------------------------------
# get_stats()
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty(self, reg):
        stats = reg.get_stats()
        assert stats["total"] == 0
        assert stats["by_lifecycle"] == {}

    def test_stats_counts(self, reg):
        _register_device(reg, "d1")
        _register_device(reg, "d2")
        reg.transition("d1", "identified")
        stats = reg.get_stats()
        assert stats["total"] == 2
        assert stats["by_lifecycle"]["attached"] == 1
        assert stats["by_lifecycle"]["identified"] == 1


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_register_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        reg = DeviceRegistry(db_path=":memory:", event_bus=MockBus())
        reg.register("e1", "usb", "M")
        reg_topics = [e.topic for e in events]
        assert "device.registered" in reg_topics

    def test_transition_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        reg = DeviceRegistry(db_path=":memory:", event_bus=MockBus())
        reg.register("e1", "usb", "M")
        reg.transition("e1", "identified")
        lc_events = [e for e in events if e.topic == "device.lifecycle.changed"]
        assert len(lc_events) == 1

    def test_authorize_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        reg = DeviceRegistry(db_path=":memory:", event_bus=MockBus())
        reg.register("e1", "usb", "M")
        reg.transition("e1", "identified")
        reg.transition("e1", "quarantined")
        reg.authorize("e1", "council")
        auth = [e for e in events if e.topic == "device.authorized"]
        assert len(auth) == 1
