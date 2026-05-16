"""
SYLION Quality -- Regression Detector Tests

Comprehensive tests for RegressionDetector: set_baseline, check_regression,
get_baseline, list_alerts, acknowledge_alert, get_stats, event emission,
severity classification, and thread safety.
"""

from __future__ import annotations

import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.quality.regression_detector import (
    RegressionDetector, Baseline, RegressionAlert,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    """Fresh in-memory EventBus."""
    return EventBus()


@pytest.fixture
def detector(bus):
    """Fresh in-memory RegressionDetector with EventBus."""
    return RegressionDetector(event_bus=bus)


@pytest.fixture
def captured_events(bus):
    """Collect all events."""
    events: list[SylionEvent] = []
    bus.subscribe("*", events.append)
    return events


# =====================================================================
# Test dataclasses
# =====================================================================

class TestDataclasses:

    def test_baseline_auto_timestamp(self):
        bl = Baseline(module_id="m1", suite_id="s1")
        assert bl.established_at > 0.0

    def test_baseline_defaults(self):
        bl = Baseline()
        assert bl.pass_rate == 1.0
        assert bl.avg_duration_ms == 0

    def test_regression_alert_auto_fields(self):
        alert = RegressionAlert(module_id="m1", suite_id="s1")
        assert alert.alert_id != ""
        assert alert.timestamp > 0.0
        assert alert.severity == "warning"


# =====================================================================
# Test set_baseline
# =====================================================================

class TestSetBaseline:

    def test_set_baseline_returns_dict(self, detector):
        result = detector.set_baseline(
            module_id="mod-1",
            suite_id="suite-1",
            run_id="run-100",
            pass_rate=0.95,
            avg_duration=120,
        )
        assert result["module_id"] == "mod-1"
        assert result["suite_id"] == "suite-1"
        assert result["pass_rate"] == 0.95
        assert result["avg_duration_ms"] == 120

    def test_set_baseline_upsert(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.90)
        detector.set_baseline("m1", "s1", "r2", pass_rate=0.95)
        bl = detector.get_baseline("m1")
        assert bl is not None
        assert bl["pass_rate"] == 0.95


# =====================================================================
# Test check_regression
# =====================================================================

class TestCheckRegression:

    def test_no_baseline_returns_not_checked(self, detector):
        result = detector.check_regression("unknown-mod", "s1", 0.80)
        assert result["checked"] is False
        assert "No baseline" in result["message"]

    def test_no_regression_when_rate_improved(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.90)
        result = detector.check_regression("m1", "s1", 0.95)
        assert result["checked"] is True
        assert result["regression"] is False
        assert result["drop"] <= 0

    def test_no_regression_when_rate_equal(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.90)
        result = detector.check_regression("m1", "s1", 0.90)
        assert result["regression"] is False

    def test_info_severity_small_drop(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.90)
        result = detector.check_regression("m1", "s1", 0.88)  # 2% drop
        assert result["checked"] is True
        assert result["regression"] is True
        assert result["severity"] == "info"

    def test_warning_severity_moderate_drop(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        result = detector.check_regression("m1", "s1", 0.88)  # 7% drop
        assert result["regression"] is True
        assert result["severity"] == "warning"

    def test_critical_severity_large_drop(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=1.0)
        result = detector.check_regression("m1", "s1", 0.50)  # 50% drop
        assert result["regression"] is True
        assert result["severity"] == "critical"

    def test_regression_creates_alert_record(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        result = detector.check_regression("m1", "s1", 0.80)
        assert "alert_id" in result
        alerts = detector.list_alerts()
        assert len(alerts) == 1
        assert alerts[0]["alert_id"] == result["alert_id"]

    def test_regression_details_contain_drop(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        result = detector.check_regression("m1", "s1", 0.85)
        assert result["drop"] == 0.10


# =====================================================================
# Test get_baseline
# =====================================================================

class TestGetBaseline:

    def test_get_existing_baseline(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.97, avg_duration=200)
        bl = detector.get_baseline("m1")
        assert bl is not None
        assert bl["module_id"] == "m1"
        assert bl["pass_rate"] == 0.97
        assert bl["avg_duration_ms"] == 200

    def test_get_nonexistent_baseline(self, detector):
        bl = detector.get_baseline("ghost")
        assert bl is None


# =====================================================================
# Test list_alerts
# =====================================================================

class TestListAlerts:

    def test_list_all_alerts(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        detector.set_baseline("m2", "s2", "r2", pass_rate=0.90)
        detector.check_regression("m1", "s1", 0.80)
        detector.check_regression("m2", "s2", 0.70)
        alerts = detector.list_alerts()
        assert len(alerts) == 2

    def test_list_filtered_by_module(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        detector.set_baseline("m2", "s2", "r2", pass_rate=0.95)
        detector.check_regression("m1", "s1", 0.80)
        detector.check_regression("m2", "s2", 0.70)
        alerts = detector.list_alerts(module_id="m1")
        assert len(alerts) == 1
        assert alerts[0]["module_id"] == "m1"

    def test_list_filtered_by_severity(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=1.0)
        detector.check_regression("m1", "s1", 0.50)   # critical (50% drop)
        detector.set_baseline("m2", "s2", "r2", pass_rate=0.95)
        detector.check_regression("m2", "s2", 0.92)   # info (3% drop)
        critical = detector.list_alerts(severity="critical")
        assert len(critical) == 1
        assert critical[0]["severity"] == "critical"

    def test_list_respects_limit(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        for i in range(15):
            detector.check_regression("m1", "s1", 0.50)
        alerts = detector.list_alerts(limit=5)
        assert len(alerts) == 5

    def test_list_empty(self, detector):
        alerts = detector.list_alerts()
        assert alerts == []


# =====================================================================
# Test acknowledge_alert
# =====================================================================

class TestAcknowledgeAlert:

    def test_acknowledge_existing(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        result = detector.check_regression("m1", "s1", 0.80)
        acked = detector.acknowledge_alert(result["alert_id"])
        assert acked is True
        alerts = detector.list_alerts()
        assert len(alerts) == 0

    def test_acknowledge_nonexistent(self, detector):
        acked = detector.acknowledge_alert("ghost-alert")
        assert acked is False


# =====================================================================
# Test get_stats
# =====================================================================

class TestGetStats:

    def test_stats_empty(self, detector):
        stats = detector.get_stats()
        assert stats["baseline_count"] == 0
        assert stats["alert_count"] == 0
        assert stats["by_severity"] == {}
        assert stats["by_module"] == {}

    def test_stats_after_operations(self, detector):
        detector.set_baseline("m1", "s1", "r1", pass_rate=1.0)
        detector.set_baseline("m2", "s2", "r2", pass_rate=0.90)
        detector.check_regression("m1", "s1", 0.50)   # critical (50% drop)
        detector.check_regression("m2", "s2", 0.85)   # warning (5% drop)
        stats = detector.get_stats()
        assert stats["baseline_count"] == 2
        assert stats["alert_count"] == 2
        assert "critical" in stats["by_severity"]
        assert "warning" in stats["by_severity"]
        assert "m1" in stats["by_module"]
        assert "m2" in stats["by_module"]


# =====================================================================
# Test event emission
# =====================================================================

class TestEventEmission:

    def test_set_baseline_emits_event(self, detector, captured_events):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        baseline_events = [e for e in captured_events if e.topic == "regression.baseline_set"]
        assert len(baseline_events) == 1
        assert baseline_events[0].payload["module_id"] == "m1"

    def test_regression_emits_event(self, detector, captured_events):
        detector.set_baseline("m1", "s1", "r1", pass_rate=1.0)
        captured_events.clear()
        detector.check_regression("m1", "s1", 0.50)  # 50% drop -> critical
        reg_events = [e for e in captured_events if e.topic == "regression.detected"]
        assert len(reg_events) == 1
        assert reg_events[0].payload["severity"] == "critical"

    def test_acknowledge_emits_event(self, detector, captured_events):
        detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        result = detector.check_regression("m1", "s1", 0.80)
        captured_events.clear()
        detector.acknowledge_alert(result["alert_id"])
        ack_events = [e for e in captured_events if e.topic == "regression.alert_acknowledged"]
        assert len(ack_events) == 1

    def test_no_event_without_bus(self):
        detector = RegressionDetector(event_bus=None)
        result = detector.set_baseline("m1", "s1", "r1", pass_rate=0.95)
        assert result["module_id"] == "m1"


# =====================================================================
# Test thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_baseline_and_checks(self, detector):
        errors: list[Exception] = []

        def do_baseline(i):
            try:
                detector.set_baseline(f"mod-{i}", f"s-{i}", f"r-{i}", pass_rate=0.95)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_baseline, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stats = detector.get_stats()
        assert stats["baseline_count"] == 20
