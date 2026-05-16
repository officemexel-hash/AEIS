"""Tests for sylion.skills.demand_signal module."""

import pytest

from sylion.skills.demand_signal import DemandSignalAnalyzer, DemandSignal, DemandReport


class TestDemandSignal:
    def test_auto_id(self):
        s = DemandSignal(signal_type="api_call")
        assert s.signal_id != ""
        assert s.first_seen > 0

    def test_custom_values(self):
        s = DemandSignal(signal_type="api_call", source="test", confidence=0.9)
        assert s.confidence == 0.9


class TestDemandReport:
    def test_auto_id(self):
        r = DemandReport()
        assert r.report_id != ""
        assert r.generated_at > 0


class TestDemandSignalAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return DemandSignalAnalyzer()

    def test_record(self, analyzer):
        result = analyzer.record("api_call", source="test", skill_id="s1", confidence=0.8)
        assert "signal_id" in result
        assert result["signal_type"] == "api_call"

    def test_record_duplicate_increments(self, analyzer):
        analyzer.record("dup", source="s", skill_id="s1")
        analyzer.record("dup", source="s", skill_id="s1")
        signals = analyzer.get_signals()
        dup = [s for s in signals if s["signal_type"] == "dup"]
        assert len(dup) == 1
        assert dup[0]["frequency"] == 2

    def test_get_signals(self, analyzer):
        for i in range(3):
            analyzer.record(f"type-{i}", source="s", skill_id=f"s{i}")
        signals = analyzer.get_signals()
        assert len(signals) >= 3

    def test_get_signals_filter_skill(self, analyzer):
        analyzer.record("t1", source="s", skill_id="target")
        analyzer.record("t2", source="s", skill_id="other")
        signals = analyzer.get_signals(skill_id="target")
        assert all(s["skill_id"] == "target" for s in signals)

    def test_get_signals_limit(self, analyzer):
        for i in range(5):
            analyzer.record(f"lim-{i}", source="s")
        signals = analyzer.get_signals(limit=2)
        assert len(signals) == 2

    def test_analyze(self, analyzer):
        analyzer.record("a1", source="s", skill_id="s1", confidence=0.9)
        analyzer.record("a2", source="s", skill_id="s2", confidence=0.7)
        result = analyzer.analyze()
        assert "report_id" in result
        assert "top_demands" in result

    def test_get_latest_report(self, analyzer):
        analyzer.record("t", source="s")
        analyzer.analyze()
        report = analyzer.get_latest_report()
        assert report is not None
        assert "report_id" in report

    def test_get_latest_report_none(self, analyzer):
        report = analyzer.get_latest_report()
        assert report is None

    def test_get_stats(self, analyzer):
        analyzer.record("s1", source="s")
        analyzer.record("s2", source="s")
        stats = analyzer.get_stats()
        assert stats["total_unique_signals"] >= 2
        assert stats["total_reports"] >= 0
