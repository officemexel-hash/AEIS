"""
tests/test_sdr.py — Class N (SDR & Signal Research) module tests

Covers: N1 SDRGateway, N2 CaptureOrchestrator, N3 SignalAnalyzer,
        N4 ProtocolDecoder, N5 RFSafetyGovernor
"""

import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.sdr.sdr_gateway import SDRGateway
from sylion.sdr.capture_orchestrator import CaptureOrchestrator
from sylion.sdr.signal_analyzer import SignalAnalyzer
from sylion.sdr.protocol_decoder import ProtocolDecoder
from sylion.sdr.rf_safety_governor import RFSafetyGovernor


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    """Fresh EventBus for each test."""
    return EventBus()


@pytest.fixture
def gateway(bus):
    return SDRGateway(event_bus=bus)


@pytest.fixture
def governor(bus):
    return RFSafetyGovernor(event_bus=bus)


@pytest.fixture
def orchestrator(bus, governor):
    """CaptureOrchestrator with RF governor singleton set."""
    # Wire up the governor singleton so CaptureOrchestrator.start() can find it
    import sylion.sdr.rf_safety_governor as gov_mod
    gov_mod._var = governor
    orch = CaptureOrchestrator(event_bus=bus)
    yield orch
    gov_mod._var = None  # cleanup


@pytest.fixture
def analyzer(bus):
    return SignalAnalyzer(event_bus=bus)


@pytest.fixture
def decoder(bus):
    return ProtocolDecoder(event_bus=bus)


# =====================================================================
# N1 SDRGateway
# =====================================================================

class TestSDRGateway:

    def test_register_sdr_returns_device_record(self, gateway):
        dev = gateway.register_sdr("sdr-001", "HackRF", freq_min=1e6, freq_max=6e9)
        assert dev["sdr_id"] == "sdr-001"
        assert dev["device_type"] == "HackRF"
        assert dev["driver"] == "soapysdr"
        assert dev["freq_min"] == 1e6
        assert dev["freq_max"] == 6e9
        assert dev["status"] == "available"

    def test_get_capabilities(self, gateway):
        gateway.register_sdr("sdr-002", "RTL-SDR", sample_rate_max=2.4e6)
        caps = gateway.get_capabilities("sdr-002")
        assert caps is not None
        assert caps["device_type"] == "RTL-SDR"
        assert caps["sample_rate_max"] == 2.4e6
        # Non-existent returns None
        assert gateway.get_capabilities("nonexistent") is None

    def test_list_sdrs_and_filter_by_status(self, gateway):
        gateway.register_sdr("sdr-a", "HackRF")
        gateway.register_sdr("sdr-b", "RTL-SDR")
        gateway.update_status("sdr-a", "in_use")

        all_sdrs = gateway.list_sdrs()
        assert len(all_sdrs) == 2

        available = gateway.list_sdrs(status="available")
        assert len(available) == 1
        assert available[0]["sdr_id"] == "sdr-b"

    def test_check_available(self, gateway):
        gateway.register_sdr("sdr-003", "USRP")
        assert gateway.check_available("sdr-003") is True
        gateway.update_status("sdr-003", "in_use")
        assert gateway.check_available("sdr-003") is False
        assert gateway.check_available("nonexistent") is False

    def test_update_status(self, gateway):
        gateway.register_sdr("sdr-004", "BladeRF")
        updated = gateway.update_status("sdr-004", "error")
        assert updated is not None
        assert updated["status"] == "error"
        # Non-existent returns None
        assert gateway.update_status("ghost", "available") is None

    def test_register_sdr_emits_event(self, gateway, bus):
        events = []
        bus.subscribe("sdr.device.registered", lambda e: events.append(e))
        gateway.register_sdr("sdr-ev", "LimeSDR")
        assert len(events) == 1
        assert events[0].payload["sdr_id"] == "sdr-ev"


# =====================================================================
# N2 CaptureOrchestrator
# =====================================================================

class TestCaptureOrchestrator:

    def test_create_capture(self, orchestrator):
        cap = orchestrator.create_capture("sdr-001", 100e6, sample_rate=2e6, mode="RX")
        assert "capture_id" in cap
        assert cap["sdr_id"] == "sdr-001"
        assert cap["frequency"] == 100e6
        assert cap["sample_rate"] == 2e6
        assert cap["mode"] == "RX"
        assert cap["status"] == "created"
        assert cap["duration_s"] == 60

    def test_start_stop_lifecycle(self, orchestrator):
        cap = orchestrator.create_capture("sdr-001", 433e6, mode="RX")
        cid = cap["capture_id"]

        started = orchestrator.start(cid)
        assert started["status"] == "running"

        stopped = orchestrator.stop(cid)
        assert stopped["status"] == "stopped"

    def test_start_tx_blocked_when_global_tx_disabled(self, orchestrator, governor):
        """TX capture must be blocked when RF governor has TX globally disabled."""
        assert governor.is_tx_enabled() is False
        cap = orchestrator.create_capture("sdr-001", 433e6, mode="TX")
        result = orchestrator.start(cap["capture_id"])
        assert "error" in result
        assert "TX blocked" in result["error"]

    def test_create_capture_emits_event(self, orchestrator, bus):
        events = []
        bus.subscribe("sdr.capture.created", lambda e: events.append(e))
        orchestrator.create_capture("sdr-001", 868e6)
        assert len(events) == 1
        assert events[0].payload["frequency"] == 868e6

    def test_list_captures_and_get(self, orchestrator):
        cap1 = orchestrator.create_capture("sdr-a", 100e6)
        cap2 = orchestrator.create_capture("sdr-b", 200e6)

        all_caps = orchestrator.list_captures()
        assert len(all_caps) == 2

        sdr_a_caps = orchestrator.list_captures(sdr_id="sdr-a")
        assert len(sdr_a_caps) == 1
        assert sdr_a_caps[0]["sdr_id"] == "sdr-a"

        fetched = orchestrator.get(cap1["capture_id"])
        assert fetched is not None
        assert fetched["capture_id"] == cap1["capture_id"]
        assert orchestrator.get("nonexistent") is None

    def test_stop_non_running_returns_error(self, orchestrator):
        cap = orchestrator.create_capture("sdr-001", 100e6, mode="RX")
        result = orchestrator.stop(cap["capture_id"])
        assert "error" in result


# =====================================================================
# N3 SignalAnalyzer
# =====================================================================

class TestSignalAnalyzer:

    def test_analyze_spectrum(self, analyzer):
        result = analyzer.analyze_spectrum("cap-001", fft_size=2048)
        assert "analysis_id" in result
        assert result["capture_id"] == "cap-001"
        assert result["analysis_type"] == "spectrum"
        assert result["params"]["fft_size"] == 2048
        assert result["findings"]["type"] == "spectrum"
        assert result["findings"]["num_bins"] == 2048

    def test_classify_modulation(self, analyzer):
        result = analyzer.classify_modulation("cap-002")
        assert "analysis_id" in result
        assert result["analysis_type"] == "modulation"
        assert result["findings"]["type"] == "modulation_classification"
        assert "detected_modulation" in result["findings"]
        assert "candidates" in result["findings"]

    def test_detect_signals(self, analyzer):
        result = analyzer.detect_signals("cap-003", threshold_db=-70)
        assert "analysis_id" in result
        assert result["analysis_type"] == "detection"
        assert result["findings"]["type"] == "signal_detection"
        assert result["params"]["threshold_db"] == -70
        assert "signals" in result["findings"]

    def test_get_and_list_analyses(self, analyzer):
        a1 = analyzer.analyze_spectrum("cap-010")
        a2 = analyzer.classify_modulation("cap-010")
        a3 = analyzer.detect_signals("cap-020")

        # get by ID
        fetched = analyzer.get(a1["analysis_id"])
        assert fetched is not None
        assert fetched["analysis_type"] == "spectrum"
        assert analyzer.get("nonexistent") is None

        # list all
        all_a = analyzer.list_analyses()
        assert len(all_a) == 3

        # list by capture
        cap010 = analyzer.list_analyses(capture_id="cap-010")
        assert len(cap010) == 2

    def test_analyze_emits_event(self, analyzer, bus):
        events = []
        bus.subscribe("sdr.analysis.completed", lambda e: events.append(e))
        analyzer.analyze_spectrum("cap-ev")
        assert len(events) == 1
        assert events[0].payload["analysis_type"] == "spectrum"


# =====================================================================
# N4 ProtocolDecoder
# =====================================================================

class TestProtocolDecoder:

    def test_decode_adsb(self, decoder):
        result = decoder.decode("cap-001", "adsb")
        assert "decode_id" in result
        assert result["protocol"] == "adsb"
        assert len(result["messages"]) > 0
        assert result["messages"][0]["icao"] is not None
        assert result["stats"]["protocol"] == "adsb"

    def test_decode_all_supported_protocols(self, decoder):
        for proto in decoder.list_protocols():
            result = decoder.decode(f"cap-{proto}", proto)
            assert "decode_id" in result
            assert result["protocol"] == proto
            assert "messages" in result

    def test_decode_unsupported_protocol(self, decoder):
        result = decoder.decode("cap-001", "zigbee")
        assert "error" in result
        assert "unsupported" in result["error"].lower()

    def test_list_protocols(self, decoder):
        protos = decoder.list_protocols()
        assert protos == ["adsb", "pocsag", "lora", "aprs", "rds", "wifi", "ble"]

    def test_get_and_list_decodes(self, decoder):
        d1 = decoder.decode("cap-a", "adsb")
        d2 = decoder.decode("cap-b", "lora")

        fetched = decoder.get(d1["decode_id"])
        assert fetched is not None
        assert fetched["protocol"] == "adsb"
        assert decoder.get("nonexistent") is None

        all_d = decoder.list_decodes()
        assert len(all_d) == 2

        cap_a = decoder.list_decodes(capture_id="cap-a")
        assert len(cap_a) == 1

    def test_decode_emits_event(self, decoder, bus):
        events = []
        bus.subscribe("sdr.protocol.decoded", lambda e: events.append(e))
        decoder.decode("cap-ev", "wifi")
        assert len(events) == 1
        assert events[0].payload["protocol"] == "wifi"


# =====================================================================
# N5 RFSafetyGovernor (SAFETY CRITICAL)
# =====================================================================

class TestRFSafetyGovernor:

    def test_tx_disabled_by_default(self, governor):
        """SAFETY INVARIANT: TX must be disabled by default."""
        assert governor.is_tx_enabled() is False

    def test_check_tx_blocked_when_globally_disabled(self, governor):
        result = governor.check_tx_allowed(433e6, 0)
        assert result["allowed"] is False
        assert "globally disabled" in result["reason"]

    def test_enable_tx_requires_approval(self, governor):
        """Empty approval must be rejected."""
        result = governor.enable_tx_global("")
        assert "error" in result
        assert result["enabled"] is False
        assert governor.is_tx_enabled() is False

        result2 = governor.enable_tx_global("   ")
        assert "error" in result2
        assert governor.is_tx_enabled() is False

    def test_enable_tx_with_approval(self, governor):
        """Valid Council approval enables TX."""
        result = governor.enable_tx_global("council-motion-2026-0420")
        assert result["enabled"] is True
        assert governor.is_tx_enabled() is True

    def test_check_tx_with_band_policy(self, governor):
        """After enabling TX globally, check band policy enforcement."""
        governor.enable_tx_global("council-approval")
        governor.add_band_policy(
            "ism-433", "PL", 433e6, 434e6,
            max_power_dbm=10, tx_allowed=True, requires_council=True
        )
        # Allowed within band, within power
        ok = governor.check_tx_allowed(433.5e6, 5, "PL")
        assert ok["allowed"] is True

        # Blocked: exceeds power
        too_hot = governor.check_tx_allowed(433.5e6, 20, "PL")
        assert too_hot["allowed"] is False
        assert "exceeds" in too_hot["reason"]

    def test_check_tx_no_policy_for_band(self, governor):
        """No matching policy means TX denied."""
        governor.enable_tx_global("council-approval")
        result = governor.check_tx_allowed(900e6, 0, "PL")
        assert result["allowed"] is False
        assert "no policy" in result["reason"]

    def test_check_tx_band_not_allowed(self, governor):
        """Policy exists but tx_allowed=False."""
        governor.enable_tx_global("council-approval")
        governor.add_band_policy(
            "restricted-band", "PL", 800e6, 900e6,
            max_power_dbm=-10, tx_allowed=False, requires_council=True
        )
        result = governor.check_tx_allowed(850e6, -20, "PL")
        assert result["allowed"] is False
        assert "not allowed" in result["reason"]

    def test_record_tx_event(self, governor):
        event = governor.record_tx("sdr-001", 433e6, 5, approved_by="admin")
        assert "event_id" in event
        assert event["sdr_id"] == "sdr-001"
        assert event["mode"] == "TX"
        assert event["frequency"] == 433e6
        assert event["power_dbm"] == 5
        assert event["approved_by"] == "admin"

    def test_get_policies_and_events(self, governor):
        governor.add_band_policy("p1", "PL", 433e6, 434e6, tx_allowed=True)
        governor.add_band_policy("p2", "DE", 868e6, 869e6, tx_allowed=False)
        governor.record_tx("sdr-001", 433e6, 0)

        all_policies = governor.get_policies()
        assert len(all_policies) == 2

        pl_policies = governor.get_policies(jurisdiction="PL")
        assert len(pl_policies) == 1
        assert pl_policies[0]["policy_id"] == "p1"

        events = governor.get_events()
        assert len(events) == 1

        sdr_events = governor.get_events(sdr_id="sdr-001")
        assert len(sdr_events) == 1
        assert governor.get_events(sdr_id="ghost") == []

    def test_enable_tx_emits_event(self, governor, bus):
        events = []
        bus.subscribe("sdr.rf.tx_enabled", lambda e: events.append(e))
        governor.enable_tx_global("council-ok")
        assert len(events) == 1
        assert events[0].payload["enabled_by"] == "council-ok"
