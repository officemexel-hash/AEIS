"""Tests for sylion.security.security_audit -- SecurityAuditor.

Covers: findings CRUD, scans lifecycle, remediations, stats,
EventBus integration, concurrency, singleton, and edge cases.
~40 tests.
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.security_audit import (
    VALID_FINDING_STATUSES,
    VALID_REMEDIATION_STATUSES,
    VALID_SCAN_STATUSES,
    VALID_SEVERITIES,
    SecurityAuditor,
    get_security_auditor,
    reset_security_auditor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auditor(event_bus: EventBus | None = None) -> SecurityAuditor:
    return SecurityAuditor(db_path=":memory:", event_bus=event_bus)


def _make_finding(mgr: SecurityAuditor, title: str = "SQL Injection",
                  severity: str = "high") -> dict:
    return mgr.create_finding(title, severity, "A vulnerability", "web", "Fix it")


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_valid_severities(self):
        assert "info" in VALID_SEVERITIES
        assert "low" in VALID_SEVERITIES
        assert "medium" in VALID_SEVERITIES
        assert "high" in VALID_SEVERITIES
        assert "critical" in VALID_SEVERITIES
        assert len(VALID_SEVERITIES) == 5

    def test_valid_finding_statuses(self):
        expected = {"open", "acknowledged", "in_progress", "resolved", "dismissed"}
        assert set(VALID_FINDING_STATUSES) == expected

    def test_valid_scan_statuses(self):
        expected = {"running", "completed", "failed", "cancelled"}
        assert set(VALID_SCAN_STATUSES) == expected

    def test_valid_remediation_statuses(self):
        expected = {"pending", "in_progress", "completed", "failed"}
        assert set(VALID_REMEDIATION_STATUSES) == expected


# ===========================================================================
# 2. Findings CRUD
# ===========================================================================


class TestCreateFinding:
    def test_basic_create(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        assert f["finding_id"] != ""
        assert f["title"] == "SQL Injection"
        assert f["severity"] == "high"
        assert f["status"] == "open"
        assert f["created_at"] > 0

    def test_default_severity_is_medium(self):
        mgr = _make_auditor()
        f = mgr.create_finding("Test")
        assert f["severity"] == "medium"

    def test_rejects_invalid_severity(self):
        mgr = _make_auditor()
        with pytest.raises(ValueError, match="Invalid severity"):
            mgr.create_finding("Bad", severity="extreme")

    def test_all_severities_accepted(self):
        mgr = _make_auditor()
        for sev in VALID_SEVERITIES:
            f = mgr.create_finding(f"F-{sev}", severity=sev)
            assert f["severity"] == sev

    def test_default_status_is_open(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        assert f["status"] == "open"

    def test_with_all_fields(self):
        mgr = _make_auditor()
        f = mgr.create_finding(
            "XSS", "critical", "Cross-site scripting", "frontend",
            "Sanitize input",
        )
        assert f["title"] == "XSS"
        assert f["severity"] == "critical"
        assert f["description"] == "Cross-site scripting"
        assert f["module"] == "frontend"
        assert f["recommendation"] == "Sanitize input"


class TestGetFinding:
    def test_get_existing(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        fetched = mgr.get_finding(f["finding_id"])
        assert fetched is not None
        assert fetched["title"] == "SQL Injection"

    def test_get_nonexistent(self):
        mgr = _make_auditor()
        assert mgr.get_finding("no-such-id") is None


class TestListFindings:
    def test_list_all(self):
        mgr = _make_auditor()
        _make_finding(mgr, "F1", "high")
        _make_finding(mgr, "F2", "low")
        assert len(mgr.list_findings()) == 2

    def test_filter_by_severity(self):
        mgr = _make_auditor()
        _make_finding(mgr, "F1", "high")
        _make_finding(mgr, "F2", "low")
        result = mgr.list_findings(severity="high")
        assert len(result) == 1
        assert result[0]["severity"] == "high"

    def test_filter_by_status(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        mgr.update_finding(f["finding_id"], status="resolved")
        result = mgr.list_findings(status="resolved")
        assert len(result) == 1

    def test_filter_by_module(self):
        mgr = _make_auditor()
        mgr.create_finding("M1", "medium", module="web")
        mgr.create_finding("M2", "medium", module="api")
        result = mgr.list_findings(module="web")
        assert len(result) == 1

    def test_combined_filters(self):
        mgr = _make_auditor()
        mgr.create_finding("F1", "high", module="web")
        mgr.create_finding("F2", "low", module="web")
        mgr.create_finding("F3", "high", module="api")
        result = mgr.list_findings(severity="high", module="web")
        assert len(result) == 1

    def test_empty_list(self):
        mgr = _make_auditor()
        assert mgr.list_findings() == []


class TestUpdateFinding:
    def test_update_title(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        updated = mgr.update_finding(f["finding_id"], title="Updated Title")
        assert updated["title"] == "Updated Title"

    def test_update_severity(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        updated = mgr.update_finding(f["finding_id"], severity="critical")
        assert updated["severity"] == "critical"

    def test_update_status(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        updated = mgr.update_finding(f["finding_id"], status="in_progress")
        assert updated["status"] == "in_progress"

    def test_update_multiple_fields(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        updated = mgr.update_finding(
            f["finding_id"], title="New", severity="low", status="resolved",
        )
        assert updated["title"] == "New"
        assert updated["severity"] == "low"
        assert updated["status"] == "resolved"

    def test_update_nonexistent_returns_none(self):
        mgr = _make_auditor()
        assert mgr.update_finding("nope", title="x") is None

    def test_update_rejects_invalid_severity(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        with pytest.raises(ValueError, match="Invalid severity"):
            mgr.update_finding(f["finding_id"], severity="bad")

    def test_update_rejects_invalid_status(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        with pytest.raises(ValueError, match="Invalid status"):
            mgr.update_finding(f["finding_id"], status="unknown")

    def test_update_no_fields_returns_finding(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        result = mgr.update_finding(f["finding_id"])
        assert result is not None


# ===========================================================================
# 3. Scans
# ===========================================================================


class TestStartScan:
    def test_basic_start(self):
        mgr = _make_auditor()
        scan = mgr.start_scan("web-module", "full")
        assert scan["scan_id"] != ""
        assert scan["scope"] == "web-module"
        assert scan["scan_type"] == "full"
        assert scan["status"] == "running"
        assert scan["findings_count"] == 0
        assert scan["started_at"] > 0

    def test_default_scan_type(self):
        mgr = _make_auditor()
        scan = mgr.start_scan("scope")
        assert scan["scan_type"] == "full"


class TestCompleteScan:
    def test_complete_running(self):
        mgr = _make_auditor()
        scan = mgr.start_scan("scope")
        result = mgr.complete_scan(scan["scan_id"], findings_count=3)
        assert result is not None
        assert result["status"] == "completed"
        assert result["findings_count"] == 3
        assert result["completed_at"] > 0

    def test_complete_nonexistent(self):
        mgr = _make_auditor()
        assert mgr.complete_scan("no-scan") is None

    def test_complete_non_running_raises(self):
        mgr = _make_auditor()
        scan = mgr.start_scan("scope")
        mgr.complete_scan(scan["scan_id"], 0)
        with pytest.raises(ValueError, match="not running"):
            mgr.complete_scan(scan["scan_id"], 0)

    def test_default_findings_count_zero(self):
        mgr = _make_auditor()
        scan = mgr.start_scan("scope")
        result = mgr.complete_scan(scan["scan_id"])
        assert result["findings_count"] == 0


class TestGetScan:
    def test_get_existing(self):
        mgr = _make_auditor()
        scan = mgr.start_scan("scope")
        fetched = mgr.get_scan(scan["scan_id"])
        assert fetched is not None
        assert fetched["scan_id"] == scan["scan_id"]

    def test_get_nonexistent(self):
        mgr = _make_auditor()
        assert mgr.get_scan("no-scan") is None


class TestListScans:
    def test_list_all(self):
        mgr = _make_auditor()
        mgr.start_scan("s1")
        mgr.start_scan("s2")
        assert len(mgr.list_scans()) == 2

    def test_filter_by_status(self):
        mgr = _make_auditor()
        scan = mgr.start_scan("s1")
        mgr.complete_scan(scan["scan_id"], 0)
        running = mgr.list_scans(status="running")
        completed = mgr.list_scans(status="completed")
        assert len(running) == 0
        assert len(completed) == 1


# ===========================================================================
# 4. Remediations
# ===========================================================================


class TestCreateRemediation:
    def test_basic_create(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        rem = mgr.create_remediation(f["finding_id"], "patch", "alice")
        assert rem["remediation_id"] != ""
        assert rem["finding_id"] == f["finding_id"]
        assert rem["action_type"] == "patch"
        assert rem["assignee"] == "alice"
        assert rem["status"] == "pending"
        assert rem["created_at"] > 0

    def test_rejects_nonexistent_finding(self):
        mgr = _make_auditor()
        with pytest.raises(ValueError, match="does not exist"):
            mgr.create_remediation("no-finding")

    def test_default_values(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        rem = mgr.create_remediation(f["finding_id"])
        assert rem["action_type"] == ""
        assert rem["assignee"] == ""


class TestCompleteRemediation:
    def test_complete_pending(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        rem = mgr.create_remediation(f["finding_id"], "fix", "bob")
        result = mgr.complete_remediation(rem["remediation_id"], "Fixed in v2")
        assert result is not None
        assert result["status"] == "completed"
        assert result["result"] == "Fixed in v2"
        assert result["completed_at"] > 0

    def test_complete_nonexistent(self):
        mgr = _make_auditor()
        assert mgr.complete_remediation("no-rem") is None

    def test_complete_non_pending_raises(self):
        mgr = _make_auditor()
        f = _make_finding(mgr)
        rem = mgr.create_remediation(f["finding_id"])
        mgr.complete_remediation(rem["remediation_id"], "done")
        with pytest.raises(ValueError, match="not pending"):
            mgr.complete_remediation(rem["remediation_id"], "again")


# ===========================================================================
# 5. Stats
# ===========================================================================


class TestGetSecurityStats:
    def test_empty_stats(self):
        mgr = _make_auditor()
        stats = mgr.get_security_stats()
        assert stats["total_findings"] == 0
        assert stats["findings_by_severity"] == {}
        assert stats["findings_by_status"] == {}
        assert stats["total_scans"] == 0
        assert stats["total_remediations"] == 0
        assert stats["remediations_by_status"] == {}

    def test_with_data(self):
        mgr = _make_auditor()
        f1 = mgr.create_finding("F1", "high", module="web")
        mgr.create_finding("F2", "low", module="api")
        mgr.create_remediation(f1["finding_id"], "fix", "alice")
        scan = mgr.start_scan("all")
        mgr.complete_scan(scan["scan_id"], 2)
        stats = mgr.get_security_stats()
        assert stats["total_findings"] == 2
        assert stats["total_scans"] == 1
        assert stats["total_remediations"] == 1
        assert stats["findings_by_severity"]["high"] == 1


# ===========================================================================
# 6. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_finding_created_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("finding_created", lambda e: collected.append(e))
        mgr = _make_auditor(event_bus=bus)
        mgr.create_finding("Test", "high")
        assert len(collected) == 1
        assert collected[0].payload["severity"] == "high"

    def test_scan_started_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("scan_started", lambda e: collected.append(e))
        mgr = _make_auditor(event_bus=bus)
        mgr.start_scan("scope")
        assert len(collected) == 1

    def test_scan_completed_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("scan_completed", lambda e: collected.append(e))
        mgr = _make_auditor(event_bus=bus)
        scan = mgr.start_scan("scope")
        mgr.complete_scan(scan["scan_id"], 5)
        assert len(collected) == 1
        assert collected[0].payload["findings_count"] == 5

    def test_remediation_created_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("remediation_created", lambda e: collected.append(e))
        mgr = _make_auditor(event_bus=bus)
        f = mgr.create_finding("F1")
        mgr.create_remediation(f["finding_id"], "fix", "alice")
        assert len(collected) == 1

    def test_no_event_without_bus(self):
        mgr = _make_auditor(event_bus=None)
        mgr.create_finding("No bus test")
        # Should not raise


# ===========================================================================
# 7. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_security_auditor(self):
        import sylion.security.security_audit as mod
        mod._manager = None
        mgr = get_security_auditor(db_path=":memory:")
        assert isinstance(mgr, SecurityAuditor)
        mod._manager = None

    def test_reset_security_auditor(self):
        import sylion.security.security_audit as mod
        mod._manager = None
        mgr1 = get_security_auditor(db_path=":memory:")
        mgr2 = reset_security_auditor(db_path=":memory:")
        assert mgr2 is not mgr1
        mod._manager = None

    def test_get_returns_same_instance(self):
        import sylion.security.security_audit as mod
        mod._manager = None
        mgr1 = get_security_auditor(db_path=":memory:")
        mgr2 = get_security_auditor()
        assert mgr1 is mgr2
        mod._manager = None


# ===========================================================================
# 8. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_finding_creation(self):
        mgr = _make_auditor()
        results = []
        errors = []

        def create(i):
            try:
                f = mgr.create_finding(f"F-{i}", "medium")
                results.append(f["finding_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_scan_and_findings(self):
        mgr = _make_auditor()
        errors = []

        def create_findings():
            try:
                for i in range(10):
                    mgr.create_finding(f"F-{i}", "high")
            except Exception as e:
                errors.append(e)

        def create_scans():
            try:
                for i in range(10):
                    scan = mgr.start_scan(f"scope-{i}")
                    mgr.complete_scan(scan["scan_id"], i)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=create_findings),
            threading.Thread(target=create_scans),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = mgr.get_security_stats()
        assert stats["total_findings"] == 10
        assert stats["total_scans"] == 10
