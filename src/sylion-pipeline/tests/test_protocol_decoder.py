"""Tests for sylion.sdr.protocol_decoder -- ProtocolDecoder."""

import pytest

from sylion.sdr.protocol_decoder import (
    ProtocolDecoder,
    SUPPORTED_PROTOCOLS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dec():
    return ProtocolDecoder(db_path=":memory:")


# ---------------------------------------------------------------------------
# Supported protocols
# ---------------------------------------------------------------------------

class TestProtocols:
    def test_supported_protocols_list(self):
        assert "adsb" in SUPPORTED_PROTOCOLS
        assert "pocsag" in SUPPORTED_PROTOCOLS
        assert "lora" in SUPPORTED_PROTOCOLS
        assert "wifi" in SUPPORTED_PROTOCOLS
        assert "ble" in SUPPORTED_PROTOCOLS

    def test_list_protocols(self, dec):
        protocols = dec.list_protocols()
        assert protocols == SUPPORTED_PROTOCOLS
        assert len(protocols) == 7


# ---------------------------------------------------------------------------
# decode()
# ---------------------------------------------------------------------------

class TestDecode:
    def test_decode_adsb(self, dec):
        r = dec.decode("cap-1", "adsb")
        assert r["protocol"] == "adsb"
        assert len(r["messages"]) > 0
        assert r["messages"][0]["icao"] == "4D2235"

    def test_decode_pocsag(self, dec):
        r = dec.decode("cap-1", "pocsag")
        assert r["protocol"] == "pocsag"
        assert r["messages"][0]["message"] == "TEST PAGE"

    def test_decode_lora(self, dec):
        r = dec.decode("cap-1", "lora")
        assert r["protocol"] == "lora"
        assert "spreading_factor" in r["messages"][0]

    def test_decode_wifi(self, dec):
        r = dec.decode("cap-1", "wifi")
        assert r["messages"][0]["ssid"] == "TestNetwork"

    def test_decode_ble(self, dec):
        r = dec.decode("cap-1", "ble")
        assert r["messages"][0]["name"] == "BLE_Device"

    def test_decode_aprs(self, dec):
        r = dec.decode("cap-1", "aprs")
        assert r["messages"][0]["source"] == "SP5ABC"

    def test_decode_rds(self, dec):
        r = dec.decode("cap-1", "rds")
        assert r["messages"][0]["station_name"] == "PR1"

    def test_unsupported_protocol(self, dec):
        r = dec.decode("cap-1", "zigbee")
        assert "error" in r
        assert "supported" in r

    def test_case_insensitive(self, dec):
        r = dec.decode("cap-1", "ADSB")
        assert r["protocol"] == "adsb"

    def test_decode_returns_decode_id(self, dec):
        r = dec.decode("cap-1", "adsb")
        assert "decode_id" in r
        assert len(r["decode_id"]) > 0

    def test_decode_has_stats(self, dec):
        r = dec.decode("cap-1", "adsb")
        assert "stats" in r
        assert r["stats"]["total_messages"] > 0

    def test_decode_persists(self, dec):
        r = dec.decode("cap-1", "adsb")
        fetched = dec.get(r["decode_id"])
        assert fetched is not None
        assert fetched["protocol"] == "adsb"


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing_deserializes_json(self, dec):
        r = dec.decode("cap-1", "wifi")
        fetched = dec.get(r["decode_id"])
        assert isinstance(fetched["messages"], list)
        assert isinstance(fetched["stats"], dict)

    def test_get_nonexistent_returns_none(self, dec):
        assert dec.get("nope") is None


# ---------------------------------------------------------------------------
# list_decodes()
# ---------------------------------------------------------------------------

class TestListDecodes:
    def test_list_all(self, dec):
        dec.decode("c1", "adsb")
        dec.decode("c2", "wifi")
        assert len(dec.list_decodes()) == 2

    def test_filter_by_capture(self, dec):
        dec.decode("c1", "adsb")
        dec.decode("c1", "wifi")
        dec.decode("c2", "lora")
        filtered = dec.list_decodes(capture_id="c1")
        assert len(filtered) == 2

    def test_limit(self, dec):
        for i in range(5):
            dec.decode("c1", "adsb")
        assert len(dec.list_decodes(limit=3)) == 3

    def test_empty_list(self, dec):
        assert dec.list_decodes() == []


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_decode_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        dec = ProtocolDecoder(db_path=":memory:", event_bus=MockBus())
        dec.decode("c1", "adsb")
        assert any(e.topic == "sdr.protocol.decoded" for e in events)
