"""
SYLION Monitoring -- Config Drift Detector Tests

Comprehensive tests for ConfigDriftDetector: set_baseline, get_baselines,
check_drift, run_full_check, get_drift_report, list_drift_reports,
resolve_drift, get_stats, event emission, severity classification,
thread safety, and edge cases.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.config_drift_detector import (
    ConfigDriftDetector,
    REPORT_STATUSES,
    VALID_SEVERITIES,
    get_config_drift_detector,
    reset_config_drift_detector,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure global singleton is reset before and after each test."""
    reset_config_drift_detector()
    yield
    reset_config_drift_detector()


@pytest.fixture
def bus():
    """Fresh in-memory EventBus."""
    return EventBus()


@pytest.fixture
def detector(bus):
    """Fresh in-memory ConfigDriftDetector with EventBus."""
    return ConfigDriftDetector(event_bus=bus)


@pytest.fixture
def captured_events(bus):
    """Collect all events published on the bus."""
    events: list[SylionEvent] = []
    bus.subscribe("*", events.append)
    return events


# =====================================================================
# Test constants
# =====================================================================

class TestConstants:

    def test_valid_severities(self):
        assert VALID_SEVERITIES == ("info", "warning", "critical")

    def test_report_statuses(self):
        assert REPORT_STATUSES == ("active", "resolved", "ignored")


# =====================================================================
# Test set_baseline
# =====================================================================

class TestSetBaseline:

    def test_returns_expected_keys(self, detector):
        result = detector.set_baseline("mod-1", "timeout", "30")
        assert "baseline_id" in result
        assert "module_id" in result
        assert "config_key" in result
        assert "expected_value" in result

    def test_baseline_id_format(self, detector):
        result = detector.set_baseline("mod-1", "timeout", "30")
        assert result["baseline_id"] == "mod-1:timeout"

    def test_expected_value_stored_as_string(self, detector):
        result = detector.set_baseline("mod-1", "retries", 3)
        assert result["expected_value"] == "3"

    def test_module_id_returned(self, detector):
        result = detector.set_baseline("my_module", "key", "val")
        assert result["module_id"] == "my_module"

    def test_config_key_returned(self, detector):
        result = detector.set_baseline("mod-1", "my_key", "val")
        assert result["config_key"] == "my_key"

    def test_upsert_replaces_existing(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        result = detector.set_baseline("mod-1", "timeout", "60")
        assert result["expected_value"] == "60"

    def test_multiple_keys_same_module(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        detector.set_baseline("mod-1", "retries", "3")
        baselines = detector.get_baselines("mod-1")
        assert len(baselines) == 2


# =====================================================================
# Test get_baselines
# =====================================================================

class TestGetBaselines:

    def test_list_all(self, detector):
        detector.set_baseline("mod-1", "k1", "v1")
        detector.set_baseline("mod-2", "k2", "v2")
        baselines = detector.get_baselines()
        assert len(baselines) == 2

    def test_filter_by_module(self, detector):
        detector.set_baseline("mod-1", "k1", "v1")
        detector.set_baseline("mod-2", "k2", "v2")
        baselines = detector.get_baselines(module_id="mod-1")
        assert len(baselines) == 1
        assert baselines[0]["module_id"] == "mod-1"

    def test_filter_nonexistent_module_returns_empty(self, detector):
        detector.set_baseline("mod-1", "k1", "v1")
        baselines = detector.get_baselines(module_id="ghost")
        assert baselines == []

    def test_empty_list_when_no_baselines(self, detector):
        baselines = detector.get_baselines()
        assert baselines == []

    def test_returns_dict_rows(self, detector):
        detector.set_baseline("mod-1", "k1", "v1")
        baselines = detector.get_baselines()
        assert isinstance(baselines[0], dict)
        assert "baseline_id" in baselines[0]
        assert "expected_value" in baselines[0]


# =====================================================================
# Test check_drift
# =====================================================================

class TestCheckDrift:

    def test_no_drift_when_matching(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        result = detector.check_drift("mod-1", "timeout", "30")
        assert result["is_drift"] is False

    def test_drift_detected_when_differing(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        result = detector.check_drift("mod-1", "timeout", "60")
        assert result["is_drift"] is True

    def test_expected_value_returned(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        result = detector.check_drift("mod-1", "timeout", "60")
        assert result["expected_value"] == "30"

    def test_actual_value_returned(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        result = detector.check_drift("mod-1", "timeout", "60")
        assert result["actual_value"] == "60"

    def test_no_baseline_returns_no_drift_flag(self, detector):
        result = detector.check_drift("ghost", "key", "val")
        assert result["is_drift"] is False
        assert result["reason"] == "no_baseline"

    def test_int_value_compared_as_string(self, detector):
        detector.set_baseline("mod-1", "port", "8080")
        result = detector.check_drift("mod-1", "port", 8080)
        assert result["is_drift"] is False

    def test_check_updates_actual_value_in_db(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        detector.check_drift("mod-1", "timeout", "60")
        baselines = detector.get_baselines("mod-1")
        assert baselines[0]["actual_value"] == "60"
        assert baselines[0]["is_drift"] == 1

    def test_check_no_drift_clears_flag(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        detector.check_drift("mod-1", "timeout", "60")
        detector.check_drift("mod-1", "timeout", "30")
        baselines = detector.get_baselines("mod-1")
        assert baselines[0]["is_drift"] == 0

    def test_baseline_id_returned(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        result = detector.check_drift("mod-1", "timeout", "30")
        assert result["baseline_id"] == "mod-1:timeout"


# =====================================================================
# Test run_full_check
# =====================================================================

class TestRunFullCheck:

    def test_no_drifts_report(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        detector.check_drift("mod-1", "timeout", "30")
        report = detector.run_full_check("mod-1")
        assert report["drift_count"] == 0
        assert report["severity"] == "info"

    def test_single_drift_info_severity(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        detector.check_drift("mod-1", "timeout", "60")
        report = detector.run_full_check("mod-1")
        assert report["drift_count"] == 1
        assert report["severity"] == "info"

    def test_multiple_drifts_warning_severity(self, detector):
        for i in range(3):
            detector.set_baseline("mod-1", f"key_{i}", f"val_{i}")
            detector.check_drift("mod-1", f"key_{i}", "changed")
        report = detector.run_full_check("mod-1")
        assert report["drift_count"] == 3
        assert report["severity"] == "warning"

    def test_many_drifts_critical_severity(self, detector):
        for i in range(7):
            detector.set_baseline("mod-1", f"key_{i}", f"val_{i}")
            detector.check_drift("mod-1", f"key_{i}", "changed")
        report = detector.run_full_check("mod-1")
        assert report["drift_count"] == 7
        assert report["severity"] == "critical"

    def test_report_has_report_id(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        assert isinstance(report["report_id"], str)
        assert len(report["report_id"]) == 32

    def test_report_status_is_active(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        assert report["status"] == "active"

    def test_report_reported_at_is_recent(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        before = time.time()
        report = detector.run_full_check("mod-1")
        after = time.time()
        assert before <= report["reported_at"] <= after

    def test_report_module_id_set(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        assert report["module_id"] == "mod-1"

    def test_report_all_modules_when_no_filter(self, detector):
        detector.set_baseline("mod-1", "k1", "v1")
        detector.set_baseline("mod-2", "k2", "v2")
        detector.check_drift("mod-1", "k1", "changed")
        detector.check_drift("mod-2", "k2", "changed")
        report = detector.run_full_check()
        assert report["drift_count"] == 2
        assert report["module_id"] == "__all__"

    def test_report_details_contains_drift_info(self, detector):
        detector.set_baseline("mod-1", "timeout", "30")
        detector.check_drift("mod-1", "timeout", "60")
        report = detector.run_full_check("mod-1")
        assert "timeout" in report["details"]
        assert "30" in report["details"]
        assert "60" in report["details"]

    def test_report_details_no_drifts(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        assert report["details"] == "no drifts"


# =====================================================================
# Test severity classification
# =====================================================================

class TestSeverityClassification:

    def test_zero_drifts_is_info(self):
        assert ConfigDriftDetector._classify_severity(0) == "info"

    def test_one_drift_is_info(self):
        assert ConfigDriftDetector._classify_severity(1) == "info"

    def test_two_drifts_is_warning(self):
        assert ConfigDriftDetector._classify_severity(2) == "warning"

    def test_five_drifts_is_warning(self):
        assert ConfigDriftDetector._classify_severity(5) == "warning"

    def test_six_drifts_is_critical(self):
        assert ConfigDriftDetector._classify_severity(6) == "critical"

    def test_ten_drifts_is_critical(self):
        assert ConfigDriftDetector._classify_severity(10) == "critical"

    def test_negative_drift_count_is_info(self):
        assert ConfigDriftDetector._classify_severity(-1) == "info"


# =====================================================================
# Test get_drift_report
# =====================================================================

class TestGetDriftReport:

    def test_get_existing_report(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        fetched = detector.get_drift_report(report["report_id"])
        assert fetched is not None
        assert fetched["report_id"] == report["report_id"]

    def test_get_nonexistent_report(self, detector):
        fetched = detector.get_drift_report("ghost-id")
        assert fetched is None

    def test_report_contains_all_fields(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        detector.check_drift("mod-1", "k", "changed")
        report = detector.run_full_check("mod-1")
        fetched = detector.get_drift_report(report["report_id"])
        assert "report_id" in fetched
        assert "module_id" in fetched
        assert "drift_count" in fetched
        assert "severity" in fetched
        assert "reported_at" in fetched
        assert "status" in fetched
        assert "details" in fetched


# =====================================================================
# Test list_drift_reports
# =====================================================================

class TestListDriftReports:

    def test_list_all_reports(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        detector.set_baseline("mod-2", "k", "v")
        detector.run_full_check("mod-1")
        detector.run_full_check("mod-2")
        reports = detector.list_drift_reports()
        assert len(reports) == 2

    def test_filter_by_module(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        detector.set_baseline("mod-2", "k", "v")
        detector.run_full_check("mod-1")
        detector.run_full_check("mod-2")
        reports = detector.list_drift_reports(module_id="mod-1")
        assert len(reports) == 1
        assert reports[0]["module_id"] == "mod-1"

    def test_filter_by_severity(self, detector):
        for i in range(7):
            detector.set_baseline("mod-1", f"key_{i}", f"val_{i}")
            detector.check_drift("mod-1", f"key_{i}", "changed")
        detector.run_full_check("mod-1")
        critical = detector.list_drift_reports(severity="critical")
        assert len(critical) == 1
        assert critical[0]["severity"] == "critical"

    def test_filter_by_status(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        detector.resolve_drift(report["report_id"])
        active = detector.list_drift_reports(status="active")
        resolved = detector.list_drift_reports(status="resolved")
        assert len(active) == 0
        assert len(resolved) == 1

    def test_limit_is_respected(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        for _ in range(15):
            detector.run_full_check("mod-1")
        reports = detector.list_drift_reports(limit=5)
        assert len(reports) == 5

    def test_empty_list_when_no_reports(self, detector):
        reports = detector.list_drift_reports()
        assert reports == []

    def test_combined_filters(self, detector):
        for i in range(7):
            detector.set_baseline("mod-1", f"key_{i}", f"val_{i}")
            detector.check_drift("mod-1", f"key_{i}", "changed")
        detector.run_full_check("mod-1")
        reports = detector.list_drift_reports(
            module_id="mod-1", severity="critical",
        )
        assert all(
            r["module_id"] == "mod-1" and r["severity"] == "critical"
            for r in reports
        )

    def test_ordered_by_reported_at_desc(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        detector.run_full_check("mod-1")
        time.sleep(0.01)
        detector.run_full_check("mod-1")
        reports = detector.list_drift_reports()
        assert reports[0]["reported_at"] >= reports[1]["reported_at"]


# =====================================================================
# Test resolve_drift
# =====================================================================

class TestResolveDrift:

    def test_resolve_existing(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        resolved = detector.resolve_drift(report["report_id"])
        assert resolved is True
        fetched = detector.get_drift_report(report["report_id"])
        assert fetched["status"] == "resolved"

    def test_resolve_nonexistent(self, detector):
        resolved = detector.resolve_drift("ghost-id")
        assert resolved is False

    def test_resolve_already_resolved_is_idempotent(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        assert detector.resolve_drift(report["report_id"]) is True
        assert detector.resolve_drift(report["report_id"]) is True


# =====================================================================
# Test get_stats
# =====================================================================

class TestGetStats:

    def test_stats_empty(self, detector):
        stats = detector.get_stats()
        assert stats["total_baselines"] == 0
        assert stats["total_drifts"] == 0
        assert stats["total_reports"] == 0
        assert stats["by_module"] == {}
        assert stats["by_severity"] == {}
        assert stats["by_status"] == {}

    def test_stats_after_baselines(self, detector):
        detector.set_baseline("mod-1", "k1", "v1")
        detector.set_baseline("mod-1", "k2", "v2")
        detector.set_baseline("mod-2", "k1", "v1")
        stats = detector.get_stats()
        assert stats["total_baselines"] == 3
        assert stats["total_drifts"] == 0

    def test_stats_after_drifts(self, detector):
        detector.set_baseline("mod-1", "k1", "v1")
        detector.set_baseline("mod-1", "k2", "v2")
        detector.check_drift("mod-1", "k1", "changed")
        stats = detector.get_stats()
        assert stats["total_drifts"] == 1
        assert stats["by_module"] == {"mod-1": 1}

    def test_stats_after_reports(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        detector.check_drift("mod-1", "k", "changed")
        detector.run_full_check("mod-1")
        stats = detector.get_stats()
        assert stats["total_reports"] == 1
        assert "info" in stats["by_severity"]

    def test_stats_by_status(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        detector.resolve_drift(report["report_id"])
        stats = detector.get_stats()
        assert "resolved" in stats["by_status"]

    def test_stats_multiple_modules(self, detector):
        detector.set_baseline("mod-1", "k", "v1")
        detector.set_baseline("mod-2", "k", "v2")
        detector.check_drift("mod-1", "k", "changed1")
        detector.check_drift("mod-2", "k", "changed2")
        stats = detector.get_stats()
        assert stats["by_module"]["mod-1"] == 1
        assert stats["by_module"]["mod-2"] == 1


# =====================================================================
# Test event emission
# =====================================================================

class TestEventEmission:

    def test_drift_detected_event_on_check(self, detector, captured_events):
        detector.set_baseline("mod-1", "timeout", "30")
        captured_events.clear()
        detector.check_drift("mod-1", "timeout", "60")
        detected = [e for e in captured_events
                    if e.topic == "config.drift_detected"]
        assert len(detected) == 1
        assert detected[0].payload["module_id"] == "mod-1"
        assert detected[0].payload["config_key"] == "timeout"

    def test_no_event_when_no_drift(self, detector, captured_events):
        detector.set_baseline("mod-1", "timeout", "30")
        captured_events.clear()
        detector.check_drift("mod-1", "timeout", "30")
        detected = [e for e in captured_events
                    if e.topic == "config.drift_detected"]
        assert len(detected) == 0

    def test_drift_detected_event_on_full_check(self, detector, captured_events):
        detector.set_baseline("mod-1", "k", "v")
        detector.check_drift("mod-1", "k", "changed")
        captured_events.clear()
        detector.run_full_check("mod-1")
        detected = [e for e in captured_events
                    if e.topic == "config.drift_detected"]
        assert len(detected) == 1
        assert "report_id" in detected[0].payload

    def test_no_full_check_event_when_no_drifts(self, detector, captured_events):
        detector.set_baseline("mod-1", "k", "v")
        captured_events.clear()
        detector.run_full_check("mod-1")
        detected = [e for e in captured_events
                    if e.topic == "config.drift_detected"]
        assert len(detected) == 0

    def test_resolve_emits_drift_resolved(self, detector, captured_events):
        detector.set_baseline("mod-1", "k", "v")
        report = detector.run_full_check("mod-1")
        captured_events.clear()
        detector.resolve_drift(report["report_id"])
        resolved = [e for e in captured_events
                    if e.topic == "config.drift_resolved"]
        assert len(resolved) == 1
        assert resolved[0].payload["report_id"] == report["report_id"]

    def test_resolve_nonexistent_no_event(self, detector, captured_events):
        detector.resolve_drift("ghost-id")
        resolved = [e for e in captured_events
                    if e.topic == "config.drift_resolved"]
        assert len(resolved) == 0

    def test_no_events_without_bus(self):
        det = ConfigDriftDetector(event_bus=None)
        det.set_baseline("mod-1", "k", "v")
        result = det.check_drift("mod-1", "k", "changed")
        assert result["is_drift"] is True
        # No crash means events are safely skipped


# =====================================================================
# Test singleton
# =====================================================================

class TestSingleton:

    def test_get_returns_same_instance(self):
        d1 = get_config_drift_detector()
        d2 = get_config_drift_detector()
        assert d1 is d2

    def test_reset_clears_singleton(self):
        d1 = get_config_drift_detector()
        reset_config_drift_detector()
        d2 = get_config_drift_detector()
        assert d1 is not d2

    def test_singleton_with_custom_db(self):
        d = get_config_drift_detector(db_path=":memory:")
        assert d is get_config_drift_detector()


# =====================================================================
# Test edge cases
# =====================================================================

class TestEdgeCases:

    def test_empty_string_value(self, detector):
        detector.set_baseline("mod-1", "k", "")
        result = detector.check_drift("mod-1", "k", "")
        assert result["is_drift"] is False

    def test_none_value_converted_to_string(self, detector):
        detector.set_baseline("mod-1", "k", "None")
        result = detector.check_drift("mod-1", "k", None)
        assert result["is_drift"] is False

    def test_special_characters_in_value(self, detector):
        val = "host=localhost;port=5432;ssl=true"
        detector.set_baseline("mod-1", "conn_str", val)
        result = detector.check_drift("mod-1", "conn_str", val)
        assert result["is_drift"] is False

    def test_bool_value(self, detector):
        detector.set_baseline("mod-1", "flag", "True")
        result = detector.check_drift("mod-1", "flag", True)
        assert result["is_drift"] is False

    def test_float_value(self, detector):
        detector.set_baseline("mod-1", "ratio", "0.75")
        result = detector.check_drift("mod-1", "ratio", 0.75)
        assert result["is_drift"] is False

    def test_check_without_set_baseline_no_crash(self, detector):
        result = detector.check_drift("ghost", "key", "val")
        assert result["is_drift"] is False

    def test_run_full_check_no_baselines(self, detector):
        report = detector.run_full_check("ghost")
        assert report["drift_count"] == 0
        assert report["severity"] == "info"

    def test_multiple_check_drifts_same_key(self, detector):
        detector.set_baseline("mod-1", "k", "v1")
        detector.check_drift("mod-1", "k", "v2")
        detector.check_drift("mod-1", "k", "v3")
        # Only the latest check is stored
        baselines = detector.get_baselines("mod-1")
        assert baselines[0]["actual_value"] == "v3"

    def test_large_number_of_baselines(self, detector):
        for i in range(100):
            detector.set_baseline("mod-1", f"key_{i}", f"val_{i}")
        baselines = detector.get_baselines("mod-1")
        assert len(baselines) == 100


# =====================================================================
# Test thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_set_baselines(self, detector):
        errors: list[Exception] = []

        def worker(wid):
            try:
                for i in range(10):
                    detector.set_baseline(
                        f"mod_{wid}", f"key_{i}", f"val_{i}",
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stats = detector.get_stats()
        assert stats["total_baselines"] == 100  # 10 workers * 10 keys

    def test_concurrent_check_drift(self, detector):
        detector.set_baseline("race_mod", "k", "v")
        errors: list[Exception] = []
        barrier = threading.Barrier(5)

        def checker():
            try:
                barrier.wait(timeout=5)
                detector.check_drift("race_mod", "k", "changed")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=checker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        baselines = detector.get_baselines("race_mod")
        assert baselines[0]["is_drift"] == 1

    def test_concurrent_resolve(self, detector):
        detector.set_baseline("mod-1", "k", "v")
        detector.check_drift("mod-1", "k", "changed")
        report = detector.run_full_check("mod-1")

        results: list[bool] = []
        barrier = threading.Barrier(3)

        def resolver():
            barrier.wait(timeout=5)
            results.append(detector.resolve_drift(report["report_id"]))

        threads = [threading.Thread(target=resolver) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert any(results)
        fetched = detector.get_drift_report(report["report_id"])
        assert fetched["status"] == "resolved"

    def test_concurrent_mixed_operations(self, detector):
        detector.set_baseline("mixed_mod", "k1", "v1")
        detector.set_baseline("mixed_mod", "k2", "v2")
        errors: list[Exception] = []

        def op(i):
            try:
                if i % 4 == 0:
                    detector.check_drift("mixed_mod", "k1", "changed")
                elif i % 4 == 1:
                    detector.get_baselines("mixed_mod")
                elif i % 4 == 2:
                    detector.get_stats()
                else:
                    detector.run_full_check("mixed_mod")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=op, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_full_checks(self, detector):
        for i in range(5):
            detector.set_baseline("mod-1", f"key_{i}", f"val_{i}")
            detector.check_drift("mod-1", f"key_{i}", "changed")

        errors: list[Exception] = []
        barrier = threading.Barrier(5)

        def full_check():
            try:
                barrier.wait(timeout=5)
                detector.run_full_check("mod-1")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=full_check) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        reports = detector.list_drift_reports(module_id="mod-1")
        assert len(reports) == 5
