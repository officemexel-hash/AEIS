"""Tests for sylion.monitoring.sla_monitor -- SLAMonitor

~45 tests covering:
  SLA definition CRUD, compliance checks, breach lifecycle,
  stats, EventBus integration, singleton, thread safety, edge cases.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.monitoring.sla_monitor import (
    BREACH_STATUSES,
    TARGET_METRICS,
    SLAMonitor,
    get_sla_monitor,
    reset_sla_monitor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh EventBus per test."""
    return EventBus()


@pytest.fixture
def monitor(bus):
    """Fresh SLAMonitor with EventBus attached."""
    return SLAMonitor(db_path=":memory:", event_bus=bus)


@pytest.fixture
def monitor_no_bus():
    """Fresh SLAMonitor without EventBus."""
    return SLAMonitor(db_path=":memory:")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_target_metrics_tuple(self):
        assert "latency_p50" in TARGET_METRICS
        assert "latency_p99" in TARGET_METRICS
        assert "availability" in TARGET_METRICS
        assert "error_rate" in TARGET_METRICS
        assert "throughput" in TARGET_METRICS
        assert len(TARGET_METRICS) == 5

    def test_breach_statuses_tuple(self):
        assert "active" in BREACH_STATUSES
        assert "resolved" in BREACH_STATUSES
        assert "escalated" in BREACH_STATUSES
        assert len(BREACH_STATUSES) == 3


# ---------------------------------------------------------------------------
# Define SLA
# ---------------------------------------------------------------------------

class TestDefineSLA:
    def test_define_returns_sla_id(self, monitor):
        result = monitor.define_sla("API Latency P99", "latency_p99",
                                     target_value=200.0, threshold=500.0)
        assert "sla_id" in result
        assert isinstance(result["sla_id"], str) and len(result["sla_id"]) == 32

    def test_define_stores_all_fields(self, monitor):
        result = monitor.define_sla("Availability", "availability",
                                     target_value=99.9, threshold=99.5,
                                     window_seconds=600)
        assert result["name"] == "Availability"
        assert result["target_metric"] == "availability"
        assert result["target_value"] == 99.9
        assert result["threshold"] == 99.5
        assert result["window_seconds"] == 600
        assert result["enabled"] is True
        assert result["created_at"] > 0

    def test_define_default_window(self, monitor):
        result = monitor.define_sla("P50", "latency_p50",
                                     target_value=100.0, threshold=200.0)
        assert result["window_seconds"] == 300

    def test_define_invalid_metric_raises(self, monitor):
        with pytest.raises(ValueError, match="Invalid target_metric"):
            monitor.define_sla("Bad", "invalid_metric",
                               target_value=1.0, threshold=2.0)

    def test_define_multiple_slas(self, monitor):
        monitor.define_sla("SLA 1", "latency_p50", 100.0, 200.0)
        monitor.define_sla("SLA 2", "error_rate", 0.01, 0.05)
        monitor.define_sla("SLA 3", "availability", 99.9, 99.0)
        slas = monitor.list_slas()
        assert len(slas) == 3


# ---------------------------------------------------------------------------
# Get SLA
# ---------------------------------------------------------------------------

class TestGetSLA:
    def test_get_existing_sla(self, monitor):
        created = monitor.define_sla("Get Test", "latency_p99",
                                      target_value=200.0, threshold=500.0)
        fetched = monitor.get_sla(created["sla_id"])
        assert fetched is not None
        assert fetched["sla_id"] == created["sla_id"]
        assert fetched["name"] == "Get Test"

    def test_get_nonexistent_returns_none(self, monitor):
        result = monitor.get_sla("nonexistent_id")
        assert result is None


# ---------------------------------------------------------------------------
# List SLAs
# ---------------------------------------------------------------------------

class TestListSLAs:
    def test_list_empty(self, monitor):
        assert monitor.list_slas() == []

    def test_list_all_slas(self, monitor):
        monitor.define_sla("A", "latency_p50", 50.0, 100.0)
        monitor.define_sla("B", "error_rate", 0.01, 0.05)
        result = monitor.list_slas()
        assert len(result) == 2

    def test_list_filter_by_metric(self, monitor):
        monitor.define_sla("Lat", "latency_p50", 50.0, 100.0)
        monitor.define_sla("Err", "error_rate", 0.01, 0.05)
        monitor.define_sla("Lat2", "latency_p99", 200.0, 500.0)
        result = monitor.list_slas(target_metric="latency_p50")
        assert len(result) == 1
        assert result[0]["name"] == "Lat"

    def test_list_filter_by_enabled(self, monitor):
        s1 = monitor.define_sla("On", "latency_p50", 50.0, 100.0)
        s2 = monitor.define_sla("Off", "latency_p99", 200.0, 500.0)
        monitor.update_sla(s2["sla_id"], enabled=False)
        result = monitor.list_slas(enabled=True)
        assert len(result) == 1
        assert result[0]["sla_id"] == s1["sla_id"]

    def test_list_filter_disabled(self, monitor):
        s1 = monitor.define_sla("On", "latency_p50", 50.0, 100.0)
        s2 = monitor.define_sla("Off", "latency_p99", 200.0, 500.0)
        monitor.update_sla(s2["sla_id"], enabled=False)
        result = monitor.list_slas(enabled=False)
        assert len(result) == 1
        assert result[0]["sla_id"] == s2["sla_id"]

    def test_list_combined_filter(self, monitor):
        monitor.define_sla("A", "latency_p50", 50.0, 100.0)
        s2 = monitor.define_sla("B", "latency_p50", 60.0, 120.0)
        monitor.define_sla("C", "error_rate", 0.01, 0.05)
        monitor.update_sla(s2["sla_id"], enabled=False)
        result = monitor.list_slas(target_metric="latency_p50", enabled=True)
        assert len(result) == 1
        assert result[0]["name"] == "A"


# ---------------------------------------------------------------------------
# Update SLA
# ---------------------------------------------------------------------------

class TestUpdateSLA:
    def test_update_enabled_to_false(self, monitor):
        created = monitor.define_sla("Upd", "latency_p50", 50.0, 100.0)
        updated = monitor.update_sla(created["sla_id"], enabled=False)
        assert updated["enabled"] is False

    def test_update_enabled_to_true(self, monitor):
        created = monitor.define_sla("Upd2", "latency_p50", 50.0, 100.0)
        monitor.update_sla(created["sla_id"], enabled=False)
        updated = monitor.update_sla(created["sla_id"], enabled=True)
        assert updated["enabled"] is True

    def test_update_nonexistent_returns_none(self, monitor):
        result = monitor.update_sla("nonexistent", enabled=False)
        assert result is None

    def test_update_no_fields_returns_current(self, monitor):
        created = monitor.define_sla("NoChange", "latency_p50", 50.0, 100.0)
        updated = monitor.update_sla(created["sla_id"])
        assert updated is not None
        assert updated["sla_id"] == created["sla_id"]


# ---------------------------------------------------------------------------
# Check SLA
# ---------------------------------------------------------------------------

class TestCheckSLA:
    def test_check_compliant_latency(self, monitor):
        sla = monitor.define_sla("Lat Check", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        result = monitor.check_sla(sla["sla_id"], 150.0)
        assert result["compliant"] is True
        assert result["actual_value"] == 150.0
        assert result["target_value"] == 200.0
        assert "breach_id" not in result

    def test_check_noncompliant_latency(self, monitor):
        sla = monitor.define_sla("Lat Breach", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        result = monitor.check_sla(sla["sla_id"], 600.0)
        assert result["compliant"] is False
        assert "breach_id" in result

    def test_check_compliant_availability(self, monitor):
        sla = monitor.define_sla("Avail", "availability",
                                  target_value=99.9, threshold=99.0)
        result = monitor.check_sla(sla["sla_id"], 99.95)
        assert result["compliant"] is True

    def test_check_noncompliant_availability(self, monitor):
        sla = monitor.define_sla("Avail Low", "availability",
                                  target_value=99.9, threshold=99.0)
        result = monitor.check_sla(sla["sla_id"], 98.5)
        assert result["compliant"] is False

    def test_check_compliant_throughput(self, monitor):
        sla = monitor.define_sla("TP", "throughput",
                                  target_value=1000.0, threshold=500.0)
        result = monitor.check_sla(sla["sla_id"], 1200.0)
        assert result["compliant"] is True

    def test_check_noncompliant_throughput(self, monitor):
        sla = monitor.define_sla("TP Low", "throughput",
                                  target_value=1000.0, threshold=500.0)
        result = monitor.check_sla(sla["sla_id"], 800.0)
        assert result["compliant"] is False

    def test_check_compliant_error_rate(self, monitor):
        sla = monitor.define_sla("Err", "error_rate",
                                  target_value=0.01, threshold=0.05)
        result = monitor.check_sla(sla["sla_id"], 0.03)
        assert result["compliant"] is True

    def test_check_noncompliant_error_rate(self, monitor):
        sla = monitor.define_sla("Err High", "error_rate",
                                  target_value=0.01, threshold=0.05)
        result = monitor.check_sla(sla["sla_id"], 0.08)
        assert result["compliant"] is False

    def test_check_unknown_sla_raises(self, monitor):
        with pytest.raises(ValueError, match="not found"):
            monitor.check_sla("nonexistent", 100.0)

    def test_check_disabled_sla_raises(self, monitor):
        sla = monitor.define_sla("Disabled", "latency_p50",
                                  target_value=100.0, threshold=200.0)
        monitor.update_sla(sla["sla_id"], enabled=False)
        with pytest.raises(ValueError, match="disabled"):
            monitor.check_sla(sla["sla_id"], 150.0)

    def test_check_exact_threshold_is_compliant(self, monitor):
        sla = monitor.define_sla("Exact", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        result = monitor.check_sla(sla["sla_id"], 500.0)
        assert result["compliant"] is True

    def test_check_creates_breach_on_failure(self, monitor):
        sla = monitor.define_sla("Breach", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        monitor.check_sla(sla["sla_id"], 600.0)
        breaches = monitor.list_breaches(sla_id=sla["sla_id"])
        assert len(breaches) == 1
        assert breaches[0]["status"] == "active"

    def test_check_returns_check_id(self, monitor):
        sla = monitor.define_sla("CID", "latency_p50",
                                  target_value=100.0, threshold=200.0)
        result = monitor.check_sla(sla["sla_id"], 50.0)
        assert "check_id" in result
        assert isinstance(result["check_id"], str) and len(result["check_id"]) == 32


# ---------------------------------------------------------------------------
# List Checks
# ---------------------------------------------------------------------------

class TestListChecks:
    def test_list_checks_empty(self, monitor):
        assert monitor.list_checks() == []

    def test_list_checks_returns_all(self, monitor):
        sla = monitor.define_sla("LC", "latency_p50",
                                  target_value=100.0, threshold=200.0)
        monitor.check_sla(sla["sla_id"], 50.0)
        monitor.check_sla(sla["sla_id"], 80.0)
        checks = monitor.list_checks()
        assert len(checks) == 2

    def test_list_checks_filter_by_sla(self, monitor):
        s1 = monitor.define_sla("S1", "latency_p50", 100.0, 200.0)
        s2 = monitor.define_sla("S2", "error_rate", 0.01, 0.05)
        monitor.check_sla(s1["sla_id"], 50.0)
        monitor.check_sla(s2["sla_id"], 0.02)
        checks = monitor.list_checks(sla_id=s1["sla_id"])
        assert len(checks) == 1
        assert checks[0]["sla_id"] == s1["sla_id"]

    def test_list_checks_filter_compliant(self, monitor):
        sla = monitor.define_sla("FC", "latency_p50", 100.0, 200.0)
        monitor.check_sla(sla["sla_id"], 50.0)   # compliant
        monitor.check_sla(sla["sla_id"], 300.0)   # non-compliant
        compliant = monitor.list_checks(compliant=True)
        non_compliant = monitor.list_checks(compliant=False)
        assert len(compliant) == 1
        assert len(non_compliant) == 1

    def test_list_checks_respects_limit(self, monitor):
        sla = monitor.define_sla("Lim", "latency_p50", 100.0, 200.0)
        for _ in range(10):
            monitor.check_sla(sla["sla_id"], 50.0)
        checks = monitor.list_checks(limit=3)
        assert len(checks) == 3

    def test_list_checks_ordered_by_checked_at_desc(self, monitor):
        sla = monitor.define_sla("Ord", "latency_p50", 100.0, 200.0)
        monitor.check_sla(sla["sla_id"], 50.0)
        time.sleep(0.01)
        monitor.check_sla(sla["sla_id"], 60.0)
        checks = monitor.list_checks()
        assert checks[0]["actual_value"] == 60.0
        assert checks[1]["actual_value"] == 50.0


# ---------------------------------------------------------------------------
# List Breaches
# ---------------------------------------------------------------------------

class TestListBreaches:
    def test_list_breaches_empty(self, monitor):
        assert monitor.list_breaches() == []

    def test_list_breaches_returns_active(self, monitor):
        sla = monitor.define_sla("BList", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        monitor.check_sla(sla["sla_id"], 600.0)
        breaches = monitor.list_breaches()
        assert len(breaches) == 1
        assert breaches[0]["status"] == "active"

    def test_list_breaches_filter_by_sla(self, monitor):
        s1 = monitor.define_sla("B1", "latency_p99", 200.0, 500.0)
        s2 = monitor.define_sla("B2", "error_rate", 0.01, 0.05)
        monitor.check_sla(s1["sla_id"], 600.0)
        monitor.check_sla(s2["sla_id"], 0.1)
        breaches = monitor.list_breaches(sla_id=s1["sla_id"])
        assert len(breaches) == 1
        assert breaches[0]["sla_id"] == s1["sla_id"]

    def test_list_breaches_filter_by_status(self, monitor):
        sla = monitor.define_sla("BStat", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        monitor.check_sla(sla["sla_id"], 600.0)
        active = monitor.list_breaches(status="active")
        resolved = monitor.list_breaches(status="resolved")
        assert len(active) == 1
        assert len(resolved) == 0

    def test_list_breaches_invalid_status_raises(self, monitor):
        with pytest.raises(ValueError, match="Invalid status"):
            monitor.list_breaches(status="invalid_status")

    def test_list_breaches_respects_limit(self, monitor):
        sla = monitor.define_sla("BLim", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        for i in range(10):
            monitor.check_sla(sla["sla_id"], 600.0 + i)
        breaches = monitor.list_breaches(limit=3)
        assert len(breaches) == 3


# ---------------------------------------------------------------------------
# Resolve Breach
# ---------------------------------------------------------------------------

class TestResolveBreach:
    def test_resolve_active_breach(self, monitor):
        sla = monitor.define_sla("Res", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        check = monitor.check_sla(sla["sla_id"], 600.0)
        breach_id = check["breach_id"]
        result = monitor.resolve_breach(breach_id)
        assert result["status"] == "resolved"
        assert result["breach_id"] == breach_id

    def test_resolve_updates_db(self, monitor):
        sla = monitor.define_sla("ResDB", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        check = monitor.check_sla(sla["sla_id"], 600.0)
        monitor.resolve_breach(check["breach_id"])
        resolved = monitor.list_breaches(status="resolved")
        assert len(resolved) == 1

    def test_resolve_nonexistent_returns_none(self, monitor):
        result = monitor.resolve_breach("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty(self, monitor):
        stats = monitor.get_stats()
        assert stats["total_slas"] == 0
        assert stats["enabled_slas"] == 0
        assert stats["total_checks"] == 0
        assert stats["compliant_checks"] == 0
        assert stats["compliance_rate"] == 1.0
        assert stats["total_breaches"] == 0
        assert stats["active_breaches"] == 0
        assert stats["resolved_breaches"] == 0
        assert stats["escalated_breaches"] == 0

    def test_stats_counts_slas(self, monitor):
        monitor.define_sla("S1", "latency_p50", 100.0, 200.0)
        monitor.define_sla("S2", "latency_p99", 200.0, 500.0)
        s3 = monitor.define_sla("S3", "error_rate", 0.01, 0.05)
        monitor.update_sla(s3["sla_id"], enabled=False)
        stats = monitor.get_stats()
        assert stats["total_slas"] == 3
        assert stats["enabled_slas"] == 2

    def test_stats_compliance_rate(self, monitor):
        sla = monitor.define_sla("Rate", "latency_p50",
                                  target_value=100.0, threshold=200.0)
        monitor.check_sla(sla["sla_id"], 50.0)    # compliant
        monitor.check_sla(sla["sla_id"], 80.0)    # compliant
        monitor.check_sla(sla["sla_id"], 300.0)   # non-compliant
        stats = monitor.get_stats()
        assert stats["total_checks"] == 3
        assert stats["compliant_checks"] == 2
        assert abs(stats["compliance_rate"] - 2.0 / 3.0) < 1e-9

    def test_stats_breach_counts(self, monitor):
        sla = monitor.define_sla("BC", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        c1 = monitor.check_sla(sla["sla_id"], 600.0)
        monitor.check_sla(sla["sla_id"], 700.0)
        monitor.resolve_breach(c1["breach_id"])
        stats = monitor.get_stats()
        assert stats["total_breaches"] == 2
        assert stats["active_breaches"] == 1
        assert stats["resolved_breaches"] == 1


# ---------------------------------------------------------------------------
# EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_define_emits_event(self, monitor, bus):
        events: list[SylionEvent] = []
        bus.subscribe("monitoring.sla_monitor.defined", events.append)
        monitor.define_sla("EvDef", "latency_p50", 100.0, 200.0)
        assert len(events) == 1
        assert events[0].payload["name"] == "EvDef"

    def test_update_emits_event(self, monitor, bus):
        events: list[SylionEvent] = []
        bus.subscribe("monitoring.sla_monitor.updated", events.append)
        sla = monitor.define_sla("EvUpd", "latency_p50", 100.0, 200.0)
        monitor.update_sla(sla["sla_id"], enabled=False)
        assert len(events) == 1
        assert events[0].payload["sla_id"] == sla["sla_id"]

    def test_breach_emits_event(self, monitor, bus):
        events: list[SylionEvent] = []
        bus.subscribe("sla.breach", events.append)
        sla = monitor.define_sla("EvBreach", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        monitor.check_sla(sla["sla_id"], 600.0)
        assert len(events) == 1
        assert events[0].payload["sla_id"] == sla["sla_id"]
        assert events[0].payload["actual_value"] == 600.0

    def test_resolve_emits_breach_resolved(self, monitor, bus):
        events: list[SylionEvent] = []
        bus.subscribe("sla.breach_resolved", events.append)
        sla = monitor.define_sla("EvRes", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        check = monitor.check_sla(sla["sla_id"], 600.0)
        monitor.resolve_breach(check["breach_id"])
        assert len(events) == 1
        assert events[0].payload["breach_id"] == check["breach_id"]

    def test_compliant_check_emits_no_breach(self, monitor, bus):
        events: list[SylionEvent] = []
        bus.subscribe("sla.breach", events.append)
        sla = monitor.define_sla("EvNoBreach", "latency_p50",
                                  target_value=100.0, threshold=200.0)
        monitor.check_sla(sla["sla_id"], 50.0)
        assert len(events) == 0

    def test_no_events_without_bus(self, monitor_no_bus):
        """Operations succeed without EventBus (no crash)."""
        sla = monitor_no_bus.define_sla("NoBus", "latency_p50",
                                         target_value=100.0, threshold=200.0)
        monitor_no_bus.check_sla(sla["sla_id"], 50.0)
        monitor_no_bus.update_sla(sla["sla_id"], enabled=False)
        # Just verifying no exceptions


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_sla_monitor_returns_instance(self):
        import sylion.monitoring.sla_monitor as mod
        mod._instance = None
        instance = get_sla_monitor()
        assert isinstance(instance, SLAMonitor)
        assert instance is get_sla_monitor()
        mod._instance = None

    def test_singleton_reuses_same_instance(self):
        import sylion.monitoring.sla_monitor as mod
        mod._instance = None
        a = get_sla_monitor()
        b = get_sla_monitor()
        assert a is b
        mod._instance = None

    def test_reset_sla_monitor_clears(self):
        import sylion.monitoring.sla_monitor as mod
        mod._instance = None
        a = get_sla_monitor()
        reset_sla_monitor()
        b = get_sla_monitor()
        assert a is not b
        mod._instance = None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_define(self, monitor):
        errors: list[Exception] = []

        def define(i):
            try:
                monitor.define_sla(f"SLA-{i}", "latency_p50",
                                   target_value=100.0, threshold=200.0)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=define, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(monitor.list_slas()) == 20

    def test_concurrent_checks(self, monitor):
        sla = monitor.define_sla("Concurrent", "latency_p50",
                                  target_value=100.0, threshold=200.0)
        errors: list[Exception] = []

        def check(val):
            try:
                monitor.check_sla(sla["sla_id"], val)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check, args=(50.0,)) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        checks = monitor.list_checks(sla_id=sla["sla_id"])
        assert len(checks) == 20

    def test_concurrent_mixed_operations(self, monitor):
        sla = monitor.define_sla("Mixed", "latency_p99",
                                  target_value=200.0, threshold=500.0)
        errors: list[Exception] = []

        def do_check():
            try:
                monitor.check_sla(sla["sla_id"], 300.0)
            except Exception as e:
                errors.append(e)

        def do_resolve():
            try:
                breaches = monitor.list_breaches(sla_id=sla["sla_id"],
                                                  status="active", limit=1)
                if breaches:
                    monitor.resolve_breach(breaches[0]["breach_id"])
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(15):
            threads.append(threading.Thread(target=do_check))
            threads.append(threading.Thread(target=do_resolve))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
