"""Tests for sylion.sdr.signal_analyzer -- SignalAnalyzer."""

import pytest

from sylion.sdr.signal_analyzer import SignalAnalyzer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sa():
    return SignalAnalyzer(db_path=":memory:")


# ---------------------------------------------------------------------------
# analyze_spectrum()
# ---------------------------------------------------------------------------

class TestAnalyzeSpectrum:
    def test_returns_analysis_result(self, sa):
        r = sa.analyze_spectrum("cap-1")
        assert "analysis_id" in r
        assert r["capture_id"] == "cap-1"
        assert r["analysis_type"] == "spectrum"

    def test_findings_contain_spectrum_data(self, sa):
        r = sa.analyze_spectrum("cap-1")
        f = r["findings"]
        assert f["type"] == "spectrum"
        assert "peak_power_dbm" in f
        assert "noise_floor_dbm" in f

    def test_custom_fft_size(self, sa):
        r = sa.analyze_spectrum("cap-1", fft_size=8192)
        assert r["params"]["fft_size"] == 8192
        assert r["findings"]["num_bins"] == 8192

    def test_result_persisted(self, sa):
        r = sa.analyze_spectrum("cap-1")
        fetched = sa.get(r["analysis_id"])
        assert fetched is not None
        assert fetched["analysis_type"] == "spectrum"


# ---------------------------------------------------------------------------
# classify_modulation()
# ---------------------------------------------------------------------------

class TestClassifyModulation:
    def test_returns_modulation_result(self, sa):
        r = sa.classify_modulation("cap-1")
        assert r["analysis_type"] == "modulation"
        f = r["findings"]
        assert f["type"] == "modulation_classification"

    def test_has_candidates(self, sa):
        r = sa.classify_modulation("cap-1")
        candidates = r["findings"]["candidates"]
        assert isinstance(candidates, list)
        assert len(candidates) > 0

    def test_confidence_is_float(self, sa):
        r = sa.classify_modulation("cap-1")
        assert isinstance(r["findings"]["confidence"], float)
        assert 0.0 <= r["findings"]["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# detect_signals()
# ---------------------------------------------------------------------------

class TestDetectSignals:
    def test_returns_detection_result(self, sa):
        r = sa.detect_signals("cap-1")
        assert r["analysis_type"] == "detection"
        f = r["findings"]
        assert f["type"] == "signal_detection"
        assert "signals" in f

    def test_custom_threshold(self, sa):
        r = sa.detect_signals("cap-1", threshold_db=-70)
        assert r["params"]["threshold_db"] == -70
        assert r["findings"]["threshold_db"] == -70

    def test_signals_have_required_fields(self, sa):
        r = sa.detect_signals("cap-1")
        for sig in r["findings"]["signals"]:
            assert "frequency_hz" in sig
            assert "power_dbm" in sig
            assert "bandwidth_hz" in sig


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_get_existing(self, sa):
        r = sa.analyze_spectrum("cap-1")
        fetched = sa.get(r["analysis_id"])
        assert fetched is not None
        assert isinstance(fetched["params"], dict)
        assert isinstance(fetched["findings"], dict)

    def test_get_nonexistent_returns_none(self, sa):
        assert sa.get("nonexistent") is None


# ---------------------------------------------------------------------------
# list_analyses()
# ---------------------------------------------------------------------------

class TestListAnalyses:
    def test_list_all(self, sa):
        sa.analyze_spectrum("cap-1")
        sa.classify_modulation("cap-1")
        assert len(sa.list_analyses()) == 2

    def test_filter_by_capture(self, sa):
        sa.analyze_spectrum("cap-1")
        sa.analyze_spectrum("cap-2")
        filtered = sa.list_analyses(capture_id="cap-1")
        assert len(filtered) == 1
        assert filtered[0]["capture_id"] == "cap-1"

    def test_limit(self, sa):
        for i in range(5):
            sa.analyze_spectrum(f"cap-{i}")
        assert len(sa.list_analyses(limit=3)) == 3

    def test_empty_list(self, sa):
        assert sa.list_analyses() == []

    def test_findings_deserialized_in_list(self, sa):
        sa.analyze_spectrum("cap-1")
        results = sa.list_analyses()
        for r in results:
            assert isinstance(r["params"], dict)
            assert isinstance(r["findings"], dict)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_analysis_emits_event(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        sa = SignalAnalyzer(db_path=":memory:", event_bus=MockBus())
        sa.analyze_spectrum("cap-1")
        assert any(e.topic == "sdr.analysis.completed" for e in events)

    def test_all_analysis_types_emit(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        sa = SignalAnalyzer(db_path=":memory:", event_bus=MockBus())
        sa.analyze_spectrum("c1")
        sa.classify_modulation("c2")
        sa.detect_signals("c3")
        assert len(events) == 3
