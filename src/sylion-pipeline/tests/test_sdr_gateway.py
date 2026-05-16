"""Tests for sylion.sdr.sdr_gateway -- SDRGateway."""

import pytest

from sylion.sdr.sdr_gateway import SDRGateway


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gw():
    return SDRGateway(db_path=":memory:")


def _register_sdr(gw, sdr_id="sdr-1", device_type="rtlsdr", **kwargs):
    return gw.register_sdr(sdr_id, device_type, **kwargs)


# ---------------------------------------------------------------------------
# register_sdr()
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_returns_device(self, gw):
        d = _register_sdr(gw)
        assert d["sdr_id"] == "sdr-1"
        assert d["device_type"] == "rtlsdr"

    def test_default_driver_is_soapysdr(self, gw):
        d = _register_sdr(gw)
        assert d["driver"] == "soapysdr"

    def test_custom_driver(self, gw):
        d = _register_sdr(gw, driver="uhd")
        assert d["driver"] == "uhd"

    def test_default_status_is_available(self, gw):
        d = _register_sdr(gw)
        assert d["status"] == "available"

    def test_tx_capable_false_by_default(self, gw):
        d = _register_sdr(gw)
        assert d["tx_capable"] == 0

    def test_tx_capable_true(self, gw):
        d = _register_sdr(gw, tx_capable=True)
        assert d["tx_capable"] == 1

    def test_custom_freq_range(self, gw):
        d = _register_sdr(gw, freq_min=24e6, freq_max=1.7e9)
        assert d["freq_min"] == 24e6
        assert d["freq_max"] == 1.7e9

    def test_register_replaces_existing(self, gw):
        _register_sdr(gw, sdr_id="dup")
        d2 = _register_sdr(gw, sdr_id="dup", device_type="hackrf")
        assert d2["device_type"] == "hackrf"


# ---------------------------------------------------------------------------
# get_capabilities()
# ---------------------------------------------------------------------------

class TestGetCapabilities:
    def test_get_existing(self, gw):
        _register_sdr(gw)
        caps = gw.get_capabilities("sdr-1")
        assert caps is not None
        assert caps["sdr_id"] == "sdr-1"

    def test_get_nonexistent_returns_none(self, gw):
        assert gw.get_capabilities("ghost") is None

    def test_includes_all_columns(self, gw):
        _register_sdr(gw)
        caps = gw.get_capabilities("sdr-1")
        expected_keys = {"sdr_id", "device_type", "driver", "freq_min",
                         "freq_max", "sample_rate_max", "tx_capable", "status"}
        assert expected_keys.issubset(set(caps.keys()))


# ---------------------------------------------------------------------------
# list_sdrs()
# ---------------------------------------------------------------------------

class TestListSdrs:
    def test_list_all(self, gw):
        _register_sdr(gw, sdr_id="s1")
        _register_sdr(gw, sdr_id="s2")
        assert len(gw.list_sdrs()) == 2

    def test_filter_by_status(self, gw):
        _register_sdr(gw, sdr_id="s1")
        _register_sdr(gw, sdr_id="s2")
        gw.update_status("s2", "busy")
        avail = gw.list_sdrs(status="available")
        assert len(avail) == 1
        assert avail[0]["sdr_id"] == "s1"

    def test_empty_list(self, gw):
        assert gw.list_sdrs() == []


# ---------------------------------------------------------------------------
# check_available()
# ---------------------------------------------------------------------------

class TestCheckAvailable:
    def test_available_device(self, gw):
        _register_sdr(gw)
        assert gw.check_available("sdr-1") is True

    def test_unavailable_device(self, gw):
        _register_sdr(gw)
        gw.update_status("sdr-1", "busy")
        assert gw.check_available("sdr-1") is False

    def test_nonexistent_device(self, gw):
        assert gw.check_available("ghost") is False


# ---------------------------------------------------------------------------
# update_status()
# ---------------------------------------------------------------------------

class TestUpdateStatus:
    def test_update_returns_updated(self, gw):
        _register_sdr(gw)
        result = gw.update_status("sdr-1", "busy")
        assert result["status"] == "busy"

    def test_update_nonexistent_returns_none(self, gw):
        assert gw.update_status("ghost", "busy") is None

    def test_update_persists(self, gw):
        _register_sdr(gw)
        gw.update_status("sdr-1", "offline")
        d = gw.get_capabilities("sdr-1")
        assert d["status"] == "offline"

    def test_multiple_status_changes(self, gw):
        _register_sdr(gw)
        for status in ["busy", "available", "offline"]:
            result = gw.update_status("sdr-1", status)
            assert result["status"] == status


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_register_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        gw = SDRGateway(db_path=":memory:", event_bus=MockBus())
        gw.register_sdr("s1", "rtlsdr")
        assert any(e.topic == "sdr.device.registered" for e in events)

    def test_status_change_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        gw = SDRGateway(db_path=":memory:", event_bus=MockBus())
        gw.register_sdr("s1", "rtlsdr")
        gw.update_status("s1", "busy")
        assert any(e.topic == "sdr.device.status_changed" for e in events)
