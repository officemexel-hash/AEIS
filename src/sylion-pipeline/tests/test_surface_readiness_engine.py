"""Comprehensive tests for sylion.surface.readiness_engine module.

Covers: register_check, run_check, run_all_checks, generate_report,
        get_report, list_reports, get_latest_report, ml_advisory,
        stats, edge cases, thread safety, event emission.
"""
import threading

import pytest

from sylion.core.event_bus import EventBus
from sylion.surface.readiness_engine import (
    ReadinessCheck,
    ReadinessEngine,
    ReadinessReport,
    get_readiness_engine,
)
import sylion.surface.readiness_engine as mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pass_check():
    return "PASS", "all good", {"latency_ms": 12}


def _fail_check():
    return "FAIL", "connection refused", {"port": 5432}


def _warn_check():
    return "WARN", "high memory", {"pct": 85}


def _error_check():
    raise RuntimeError("check exploded")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    mod._engine = None
    yield
    mod._engine = None


@pytest.fixture
def engine():
    return ReadinessEngine()


@pytest.fixture
def engine_with_events():
    eb = EventBus()
    collected = []
    eb.subscribe("*", lambda e: collected.append(e))
    eng = ReadinessEngine(event_bus=eb)
    return eng, collected


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

class TestReadinessCheckDataclass:
    def test_auto_id(self):
        c = ReadinessCheck()
        assert len(c.check_id) == 32

    def test_auto_timestamp(self):
        c = ReadinessCheck()
        assert c.checked_at > 0

    def test_defaults(self):
        c = ReadinessCheck()
        assert c.check_type == "DEPENDENCY"
        assert c.status == "SKIP"
        assert c.details == {}


class TestReadinessReportDataclass:
    def test_auto_id(self):
        r = ReadinessReport()
        assert len(r.report_id) == 32

    def test_auto_timestamp(self):
        r = ReadinessReport()
        assert r.generated_at > 0

    def test_defaults(self):
        r = ReadinessReport()
        assert r.overall_status == "NOT_READY"
        assert r.deterministic_score == 0.0


# ---------------------------------------------------------------------------
# Register check
# ---------------------------------------------------------------------------

class TestRegisterCheck:
    def test_register_basic(self, engine):
        result = engine.register_check("mod-a", "HEALTH", _pass_check, "health check")
        assert result["module_id"] == "mod-a"
        assert result["check_type"] == "HEALTH"
        assert len(result["check_id"]) == 32

    def test_register_multiple_checks(self, engine):
        engine.register_check("mod-a", "HEALTH", _pass_check)
        engine.register_check("mod-a", "CONFIG", _warn_check)
        results = engine.run_all_checks("mod-a")
        assert len(results) == 2

    def test_register_replaces(self, engine):
        engine.register_check("mod-x", "HEALTH", _pass_check)
        engine.register_check("mod-x", "HEALTH", _fail_check)
        result = engine.run_check("mod-x", "HEALTH")
        assert result["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Run check
# ---------------------------------------------------------------------------

class TestRunCheck:
    def test_run_pass(self, engine):
        engine.register_check("mod-b", "CONNECTIVITY", _pass_check)
        result = engine.run_check("mod-b", "CONNECTIVITY")
        assert result["status"] == "PASS"
        assert result["message"] == "all good"
        assert result["details"] == {"latency_ms": 12}

    def test_run_fail(self, engine):
        engine.register_check("mod-c", "HEALTH", _fail_check)
        result = engine.run_check("mod-c", "HEALTH")
        assert result["status"] == "FAIL"
        assert result["message"] == "connection refused"

    def test_run_warn(self, engine):
        engine.register_check("mod-w", "MEMORY", _warn_check)
        result = engine.run_check("mod-w", "MEMORY")
        assert result["status"] == "WARN"

    def test_run_unregistered_check(self, engine):
        result = engine.run_check("mod-z", "NONEXISTENT")
        assert result["status"] == "SKIP"
        assert "not registered" in result["message"]

    def test_run_check_exception(self, engine):
        engine.register_check("mod-err", "BOMB", _error_check)
        result = engine.run_check("mod-err", "BOMB")
        assert result["status"] == "FAIL"
        assert "check exploded" in result["message"]


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

class TestRunAllChecks:
    def test_run_all_mixed(self, engine):
        engine.register_check("mod-d", "HEALTH", _pass_check)
        engine.register_check("mod-d", "CONFIG", _warn_check)
        results = engine.run_all_checks("mod-d")
        assert len(results) == 2
        statuses = {r["status"] for r in results}
        assert statuses == {"PASS", "WARN"}

    def test_run_all_no_checks(self, engine):
        results = engine.run_all_checks("empty-mod")
        assert results == []


# ---------------------------------------------------------------------------
# Generate report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_all_pass_ready(self, engine):
        engine.register_check("mod-e", "HEALTH", _pass_check)
        engine.register_check("mod-e", "CONFIG", _pass_check)
        report = engine.generate_report("mod-e")
        assert report["overall_status"] == "READY"
        assert report["deterministic_score"] == 1.0

    def test_all_fail_not_ready(self, engine):
        engine.register_check("mod-f", "HEALTH", _fail_check)
        engine.register_check("mod-f", "CONFIG", _fail_check)
        report = engine.generate_report("mod-f")
        assert report["overall_status"] == "NOT_READY"
        assert report["deterministic_score"] == 0.0

    def test_mixed_degraded(self, engine):
        engine.register_check("mod-g", "A", _pass_check)
        engine.register_check("mod-g", "B", _warn_check)
        report = engine.generate_report("mod-g")
        assert report["overall_status"] == "DEGRADED"
        assert 0 < report["deterministic_score"] < 1.0

    def test_no_checks_not_ready(self, engine):
        report = engine.generate_report("mod-empty")
        assert report["overall_status"] == "NOT_READY"
        assert report["deterministic_score"] == 0.0
        assert report["checks"] == 0

    def test_half_pass_half_fail(self, engine):
        engine.register_check("mod-hf", "A", _pass_check)
        engine.register_check("mod-hf", "B", _fail_check)
        report = engine.generate_report("mod-hf")
        assert report["deterministic_score"] == 0.5
        assert report["overall_status"] == "DEGRADED"

    def test_single_warn(self, engine):
        engine.register_check("mod-sw", "MEM", _warn_check)
        report = engine.generate_report("mod-sw")
        assert report["deterministic_score"] == 0.5
        assert report["overall_status"] == "DEGRADED"


# ---------------------------------------------------------------------------
# Get report
# ---------------------------------------------------------------------------

class TestGetReport:
    def test_get_report_found(self, engine):
        engine.register_check("mod-g", "HEALTH", _pass_check)
        report = engine.generate_report("mod-g")
        fetched = engine.get_report(report["report_id"])
        assert fetched is not None
        assert fetched["overall_status"] == "READY"
        assert len(fetched["check_results"]) >= 1

    def test_get_report_not_found(self, engine):
        assert engine.get_report("nonexistent") is None

    def test_report_includes_check_details(self, engine):
        engine.register_check("mod-detail", "HEALTH", _pass_check)
        report = engine.generate_report("mod-detail")
        fetched = engine.get_report(report["report_id"])
        cr = fetched["check_results"][0]
        assert cr["status"] == "PASS"
        assert cr["details"] == {"latency_ms": 12}

    def test_report_ml_advisory_included(self, engine):
        engine.set_ml_advisory("mod-ml", {"prediction": "healthy"})
        engine.register_check("mod-ml", "HEALTH", _pass_check)
        report = engine.generate_report("mod-ml")
        fetched = engine.get_report(report["report_id"])
        assert fetched["ml_advisory"]["prediction"] == "healthy"


# ---------------------------------------------------------------------------
# List reports
# ---------------------------------------------------------------------------

class TestListReports:
    def test_list_all_reports(self, engine):
        engine.register_check("mod-j", "HEALTH", _pass_check)
        engine.generate_report("mod-j")
        engine.generate_report("mod-j")
        reports = engine.list_reports()
        assert len(reports) >= 2

    def test_list_reports_by_module(self, engine):
        engine.register_check("mod-j", "HEALTH", _pass_check)
        engine.register_check("mod-k", "HEALTH", _pass_check)
        engine.generate_report("mod-j")
        engine.generate_report("mod-k")
        reports_j = engine.list_reports(module_id="mod-j")
        assert all(r["module_id"] == "mod-j" for r in reports_j)

    def test_list_reports_limit(self, engine):
        engine.register_check("mod-lim", "HEALTH", _pass_check)
        for _ in range(5):
            engine.generate_report("mod-lim")
        reports = engine.list_reports(limit=2)
        assert len(reports) == 2


# ---------------------------------------------------------------------------
# Get latest report
# ---------------------------------------------------------------------------

class TestGetLatestReport:
    def test_get_latest(self, engine):
        engine.register_check("mod-lt", "HEALTH", _pass_check)
        engine.generate_report("mod-lt")
        import time; time.sleep(0.01)
        report2 = engine.generate_report("mod-lt")
        latest = engine.get_latest_report("mod-lt")
        assert latest["report_id"] == report2["report_id"]

    def test_get_latest_no_reports(self, engine):
        assert engine.get_latest_report("no-module") is None


# ---------------------------------------------------------------------------
# ML advisory
# ---------------------------------------------------------------------------

class TestMLAdvisory:
    def test_set_ml_advisory(self, engine):
        result = engine.set_ml_advisory("mod-h", {"confidence": 0.92})
        assert result["advisory_set"] is True
        assert result["module_id"] == "mod-h"

    def test_ml_advisory_in_report(self, engine):
        engine.set_ml_advisory("mod-h2", {"risk": "low"})
        engine.register_check("mod-h2", "HEALTH", _pass_check)
        report = engine.generate_report("mod-h2")
        fetched = engine.get_report(report["report_id"])
        assert fetched["ml_advisory"]["risk"] == "low"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_empty_stats(self, engine):
        stats = engine.get_stats()
        assert stats["total_reports"] == 0
        assert stats["total_registered_checks"] == 0
        assert stats["by_status"] == {}

    def test_stats_with_data(self, engine):
        engine.register_check("mod-i", "HEALTH", _pass_check)
        engine.generate_report("mod-i")
        stats = engine.get_stats()
        assert stats["total_reports"] >= 1
        assert stats["total_registered_checks"] >= 1
        assert "READY" in stats["by_status"]


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_report_generates_event(self, engine_with_events):
        engine, events = engine_with_events
        engine.register_check("mod-ev", "HEALTH", _pass_check)
        engine.generate_report("mod-ev")
        assert any("report_generated" in e.topic for e in events)

    def test_no_event_bus_no_crash(self, engine):
        engine.register_check("mod-x", "HEALTH", _pass_check)
        engine.generate_report("mod-x")


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_get_engine_returns_same(self):
        e1 = get_readiness_engine()
        e2 = get_readiness_engine()
        assert e1 is e2


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_reports(self, engine):
        errors = []

        def gen_report(module_id):
            try:
                engine.register_check(module_id, "HEALTH", _pass_check)
                engine.generate_report(module_id)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=gen_report, args=(f"mod-t{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = engine.get_stats()
        assert stats["total_reports"] == 10

    def test_concurrent_run_checks(self, engine):
        engine.register_check("shared", "HEALTH", _pass_check)
        errors = []

        def run_check():
            try:
                engine.run_check("shared", "HEALTH")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
