"""
Tests for sylion.efficiency.runtime_perf — RuntimePerfTracker

CRUD: record, define_slo, check_slo
Queries: get_measurements, list_slos, get_stats
SLO logic: pass/fail based on p95 and error_rate vs targets
Events: verify EventBus emissions
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.efficiency.runtime_perf import RuntimePerfTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    eb = EventBus()
    eb._captured: list[SylionEvent] = []

    _orig = eb.publish

    def _capture(event: SylionEvent):
        eb._captured.append(event)
        return _orig(event)

    eb.publish = _capture
    return eb


@pytest.fixture
def tracker(bus):
    return RuntimePerfTracker(event_bus=bus)


# ---------------------------------------------------------------------------
# Record measurements
# ---------------------------------------------------------------------------

class TestRecord:
    def test_record_returns_expected_fields(self, tracker):
        result = tracker.record("/api/ping", latency_ms=42,
                                p50=40, p95=50, p99=80,
                                error_rate=0.01, throughput=120.5)
        assert result["endpoint"] == "/api/ping"
        assert "measurement_id" in result
        assert "timestamp" in result

    def test_record_stores_all_fields(self, tracker):
        tracker.record("/api/data", latency_ms=100, p95=120, p99=200,
                       error_rate=0.05, throughput=50.0)
        rows = tracker.get_measurements("/api/data")
        assert len(rows) == 1
        r = rows[0]
        assert r["endpoint"] == "/api/data"
        assert r["latency_ms"] == 100
        assert r["p95_ms"] == 120
        assert r["p99_ms"] == 200
        assert r["error_rate"] == pytest.approx(0.05)
        assert r["throughput_rps"] == pytest.approx(50.0)

    def test_record_multiple_measurements(self, tracker):
        for i in range(5):
            tracker.record("/api/batch", latency_ms=10 + i)
        rows = tracker.get_measurements("/api/batch")
        assert len(rows) == 5

    def test_record_defaults(self, tracker):
        tracker.record("/api/minimal", latency_ms=10)
        rows = tracker.get_measurements("/api/minimal")
        r = rows[0]
        assert r["p50_ms"] == 0
        assert r["p95_ms"] == 0
        assert r["p99_ms"] == 0
        assert r["error_rate"] == 0.0
        assert r["throughput_rps"] == 0.0


# ---------------------------------------------------------------------------
# SLO management
# ---------------------------------------------------------------------------

class TestSLO:
    def test_define_slo_returns_fields(self, tracker):
        result = tracker.define_slo("/api/ping", target_p95_ms=50,
                                    target_error_rate=0.01,
                                    description="Ping SLO")
        assert result["endpoint"] == "/api/ping"
        assert "slo_id" in result

    def test_list_slos_returns_defined(self, tracker):
        tracker.define_slo("/api/a", target_p95_ms=100)
        tracker.define_slo("/api/b", target_p95_ms=200)
        slos = tracker.list_slos()
        assert len(slos) == 2

    def test_check_slo_passes_within_target(self, tracker):
        tracker.define_slo("/api/pass", target_p95_ms=100, target_error_rate=0.05)
        tracker.record("/api/pass", latency_ms=50, p95=80, error_rate=0.01)
        result = tracker.check_slo("/api/pass")
        assert result["pass"] is True
        assert result["target_p95_ms"] == 100

    def test_check_slo_fails_p95_exceeded(self, tracker):
        tracker.define_slo("/api/fail", target_p95_ms=50, target_error_rate=0.05)
        tracker.record("/api/fail", latency_ms=200, p95=120, error_rate=0.01)
        result = tracker.check_slo("/api/fail")
        assert result["pass"] is False

    def test_check_slo_fails_error_rate_exceeded(self, tracker):
        tracker.define_slo("/api/err", target_p95_ms=200, target_error_rate=0.01)
        tracker.record("/api/err", latency_ms=50, p95=100, error_rate=0.05)
        result = tracker.check_slo("/api/err")
        assert result["pass"] is False

    def test_check_slo_no_slo_defined_passes(self, tracker):
        result = tracker.check_slo("/api/noslo")
        assert result["pass"] is True
        assert result["reason"] == "no_slo_defined"

    def test_check_slo_no_measurements_passes(self, tracker):
        tracker.define_slo("/api/nodata", target_p95_ms=100)
        result = tracker.check_slo("/api/nodata")
        assert result["pass"] is True
        assert result["reason"] == "no_measurements"


# ---------------------------------------------------------------------------
# Queries and stats
# ---------------------------------------------------------------------------

class TestQueries:
    def test_get_measurements_respects_limit(self, tracker):
        for i in range(10):
            tracker.record("/api/lim", latency_ms=i)
        rows = tracker.get_measurements("/api/lim", limit=3)
        assert len(rows) == 3

    def test_get_measurements_ordered_by_timestamp_desc(self, tracker):
        tracker.record("/api/ord", latency_ms=10)
        tracker.record("/api/ord", latency_ms=20)
        rows = tracker.get_measurements("/api/ord")
        assert rows[0]["latency_ms"] >= rows[1]["latency_ms"]

    def test_get_stats_empty_endpoint(self, tracker):
        stats = tracker.get_stats("/api/empty")
        assert stats["count"] == 0

    def test_get_stats_with_data(self, tracker):
        tracker.record("/api/stats", latency_ms=10)
        tracker.record("/api/stats", latency_ms=20)
        tracker.record("/api/stats", latency_ms=30)
        stats = tracker.get_stats("/api/stats")
        assert stats["cnt"] == 3
        assert stats["avg_latency"] == pytest.approx(20.0)
        assert stats["min_latency"] == 10
        assert stats["max_latency"] == 30


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class TestRuntimePerfEvents:
    def test_record_emits_event(self, tracker, bus):
        tracker.record("/api/ev", latency_ms=42)
        topics = [e.topic for e in bus._captured]
        assert "efficiency.runtime_perf.recorded" in topics

    def test_define_slo_emits_event(self, tracker, bus):
        tracker.define_slo("/api/slo_ev", target_p95_ms=100)
        topics = [e.topic for e in bus._captured]
        assert "efficiency.runtime_perf.slo_defined" in topics

    def test_check_slo_emits_event(self, tracker, bus):
        tracker.define_slo("/api/chk_ev", target_p95_ms=100)
        tracker.record("/api/chk_ev", latency_ms=50, p95=80)
        tracker.check_slo("/api/chk_ev")
        topics = [e.topic for e in bus._captured]
        assert "efficiency.runtime_perf.slo_checked" in topics
