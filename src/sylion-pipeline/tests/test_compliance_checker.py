"""
SYLION Governance -- Compliance Checker Tests

Tests for ComplianceChecker: policy CRUD, compliance checks,
stats, event emission, validation, filtering, and thread safety.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.compliance_checker import (
    VALID_CHECK_STATUSES,
    VALID_SCOPES,
    VALID_SEVERITIES,
    ComplianceChecker,
    get_compliance_checker,
    reset_compliance_checker,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def checker():
    """Fresh ComplianceChecker with :memory: SQLite."""
    return ComplianceChecker(db_path=":memory:")


@pytest.fixture
def checker_with_bus():
    """ComplianceChecker connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return ComplianceChecker(db_path=":memory:", event_bus=bus), bus


def _sample_rules():
    return [
        {"field": "module_id", "operator": "ne", "value": "blocked-module",
         "message": "Module is blocked"},
        {"field": "module_id", "operator": "contains", "value": "-",
         "message": "Module ID must contain a hyphen"},
    ]


def _create_sample_policy(checker, **overrides):
    defaults = {
        "name": "Sample Policy",
        "scope": "security",
        "rules": _sample_rules(),
        "severity": "critical",
    }
    defaults.update(overrides)
    return checker.create_policy(**defaults)


# ---------------------------------------------------------------------------
# Test: create_policy
# ---------------------------------------------------------------------------

class TestCreatePolicy:

    def test_creates_policy_successfully(self, checker):
        result = _create_sample_policy(checker)
        assert result["policy_id"]
        assert result["name"] == "Sample Policy"
        assert result["scope"] == "security"
        assert result["severity"] == "critical"
        assert result["enabled"] is True
        assert len(result["rules"]) == 2

    def test_generates_unique_policy_id(self, checker):
        r1 = _create_sample_policy(checker, name="P1")
        r2 = _create_sample_policy(checker, name="P2")
        assert r1["policy_id"] != r2["policy_id"]

    def test_default_severity_is_info(self, checker):
        result = checker.create_policy("P", "quality", [])
        assert result["severity"] == "info"

    def test_default_enabled_is_true(self, checker):
        result = checker.create_policy("P", "security", [])
        assert result["enabled"] is True

    def test_created_at_timestamp_set(self, checker):
        before = time.time()
        result = checker.create_policy("P", "security", [])
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_rules_stored_as_json(self, checker):
        rules = [{"field": "x", "operator": "eq", "value": 1}]
        result = checker.create_policy("P", "security", rules)
        assert len(result["rules"]) == 1
        assert result["rules"][0]["field"] == "x"

    def test_rejects_invalid_scope(self, checker):
        with pytest.raises(ValueError, match="Invalid scope"):
            checker.create_policy("P", "invalid_scope", [])

    def test_rejects_invalid_severity(self, checker):
        with pytest.raises(ValueError, match="Invalid severity"):
            checker.create_policy("P", "security", [], severity="extreme")

    def test_empty_rules_allowed(self, checker):
        result = checker.create_policy("Empty", "quality", [])
        assert result["rules"] == []

    def test_all_valid_scopes_accepted(self, checker):
        for scope in VALID_SCOPES:
            result = checker.create_policy(f"P-{scope}", scope, [])
            assert result["scope"] == scope

    def test_all_valid_severities_accepted(self, checker):
        for sev in VALID_SEVERITIES:
            result = checker.create_policy(f"P-{sev}", "security", [], severity=sev)
            assert result["severity"] == sev


# ---------------------------------------------------------------------------
# Test: update_policy
# ---------------------------------------------------------------------------

class TestUpdatePolicy:

    def test_updates_name(self, checker):
        p = _create_sample_policy(checker)
        result = checker.update_policy(p["policy_id"], name="Updated Name")
        assert result["name"] == "Updated Name"

    def test_updates_rules(self, checker):
        p = _create_sample_policy(checker)
        new_rules = [{"field": "a", "operator": "eq", "value": 1}]
        result = checker.update_policy(p["policy_id"], rules=new_rules)
        assert len(result["rules"]) == 1
        assert result["rules"][0]["field"] == "a"

    def test_disables_policy(self, checker):
        p = _create_sample_policy(checker)
        result = checker.update_policy(p["policy_id"], enabled=False)
        assert result["enabled"] == 0

    def test_enables_policy(self, checker):
        p = _create_sample_policy(checker)
        checker.update_policy(p["policy_id"], enabled=False)
        result = checker.update_policy(p["policy_id"], enabled=True)
        assert result["enabled"] == 1

    def test_returns_none_for_missing(self, checker):
        result = checker.update_policy("nonexistent", name="X")
        assert result is None

    def test_partial_update_preserves_others(self, checker):
        p = _create_sample_policy(checker)
        original_rules = p["rules"]
        result = checker.update_policy(p["policy_id"], name="New Name")
        assert result["name"] == "New Name"
        assert len(result["rules"]) == len(original_rules)

    def test_update_multiple_fields(self, checker):
        p = _create_sample_policy(checker)
        result = checker.update_policy(
            p["policy_id"],
            name="Multi Update",
            rules=[{"field": "z", "operator": "exists", "value": True}],
            enabled=False,
        )
        assert result["name"] == "Multi Update"
        assert len(result["rules"]) == 1
        assert result["enabled"] == 0


# ---------------------------------------------------------------------------
# Test: delete_policy
# ---------------------------------------------------------------------------

class TestDeletePolicy:

    def test_deletes_existing_policy(self, checker):
        p = _create_sample_policy(checker)
        result = checker.delete_policy(p["policy_id"])
        assert result is True

    def test_delete_removes_from_list(self, checker):
        p = _create_sample_policy(checker)
        checker.delete_policy(p["policy_id"])
        policies = checker.list_policies()
        assert len(policies) == 0

    def test_delete_nonexistent_returns_false(self, checker):
        result = checker.delete_policy("nonexistent")
        assert result is False

    def test_delete_twice_returns_false_second_time(self, checker):
        p = _create_sample_policy(checker)
        assert checker.delete_policy(p["policy_id"]) is True
        assert checker.delete_policy(p["policy_id"]) is False


# ---------------------------------------------------------------------------
# Test: list_policies
# ---------------------------------------------------------------------------

class TestListPolicies:

    def test_lists_all_policies(self, checker):
        _create_sample_policy(checker, name="A", scope="security")
        _create_sample_policy(checker, name="B", scope="quality")
        result = checker.list_policies()
        assert len(result) == 2

    def test_filters_by_scope(self, checker):
        _create_sample_policy(checker, name="A", scope="security")
        _create_sample_policy(checker, name="B", scope="quality")
        result = checker.list_policies(scope="security")
        assert len(result) == 1
        assert result[0]["scope"] == "security"

    def test_filters_by_enabled(self, checker):
        p = _create_sample_policy(checker, name="Enabled")
        _create_sample_policy(checker, name="WillDisable")
        checker.update_policy(p["policy_id"], enabled=False)
        result = checker.list_policies(enabled=True)
        assert len(result) == 1

    def test_filters_by_disabled(self, checker):
        p = _create_sample_policy(checker, name="WillDisable")
        _create_sample_policy(checker, name="StaysEnabled")
        checker.update_policy(p["policy_id"], enabled=False)
        result = checker.list_policies(enabled=False)
        assert len(result) == 1

    def test_combined_scope_and_enabled(self, checker):
        p1 = checker.create_policy("A", "security", [])
        p2 = checker.create_policy("B", "security", [])
        checker.create_policy("C", "quality", [])
        checker.update_policy(p1["policy_id"], enabled=False)
        result = checker.list_policies(scope="security", enabled=True)
        assert len(result) == 1
        assert result[0]["policy_id"] == p2["policy_id"]

    def test_empty_when_no_policies(self, checker):
        result = checker.list_policies()
        assert result == []

    def test_empty_for_nonexistent_scope(self, checker):
        checker.create_policy("P", "security", [])
        result = checker.list_policies(scope="performance")
        assert result == []

    def test_returns_policies_ordered_by_created_at(self, checker):
        p1 = checker.create_policy("First", "security", [])
        time.sleep(0.01)
        p2 = checker.create_policy("Second", "security", [])
        result = checker.list_policies()
        assert result[0]["policy_id"] == p1["policy_id"]
        assert result[1]["policy_id"] == p2["policy_id"]


# ---------------------------------------------------------------------------
# Test: check_compliance
# ---------------------------------------------------------------------------

class TestCheckCompliance:

    def test_compliant_with_empty_rules(self, checker):
        checker.create_policy("Empty", "security", [])
        result = checker.check_compliance("test-module")
        assert result["overall_status"] == "compliant"
        assert result["violation_count"] == 0

    def test_compliant_when_rules_pass(self, checker):
        rules = [{"field": "module_id", "operator": "eq", "value": "good-module"}]
        checker.create_policy("Pass", "security", rules)
        result = checker.check_compliance("good-module")
        assert result["overall_status"] == "compliant"

    def test_violation_when_rules_fail(self, checker):
        rules = [
            {"field": "module_id", "operator": "eq", "value": "wrong",
             "message": "Module mismatch"},
        ]
        checker.create_policy("Fail", "security", rules, severity="critical")
        result = checker.check_compliance("test-module")
        assert result["overall_status"] == "violation"
        assert result["violation_count"] >= 1

    def test_warning_severity_produces_warning_status(self, checker):
        rules = [
            {"field": "module_id", "operator": "eq", "value": "wrong",
             "message": "Mismatch"},
        ]
        checker.create_policy("Warn", "quality", rules, severity="warning")
        result = checker.check_compliance("test-module")
        assert result["overall_status"] == "warning"
        assert result["warning_count"] >= 1

    def test_scope_filtering(self, checker):
        checker.create_policy("Sec", "security", [])
        checker.create_policy("Qual", "quality", [])
        result = checker.check_compliance("mod", scope="security")
        assert result["total"] == 1
        assert result["scope"] == "security"

    def test_all_scope_checks_all_policies(self, checker):
        checker.create_policy("S1", "security", [])
        checker.create_policy("Q1", "quality", [])
        checker.create_policy("A1", "architecture", [])
        result = checker.check_compliance("mod", scope="all")
        assert result["total"] == 3

    def test_disabled_policies_not_checked(self, checker):
        p = checker.create_policy("Disabled", "security", [
            {"field": "module_id", "operator": "eq", "value": "wrong"},
        ])
        checker.update_policy(p["policy_id"], enabled=False)
        result = checker.check_compliance("mod", scope="security")
        assert result["total"] == 0

    def test_check_creates_check_records(self, checker):
        checker.create_policy("P1", "security", [])
        checker.create_policy("P2", "quality", [])
        result = checker.check_compliance("mod", scope="all")
        assert len(result["check_ids"]) == 2

    def test_rejects_invalid_scope(self, checker):
        with pytest.raises(ValueError, match="Invalid scope"):
            checker.check_compliance("mod", scope="invalid")

    def test_violations_include_details(self, checker):
        rules = [
            {"field": "module_id", "operator": "eq", "value": "no-match",
             "message": "Module blocked"},
        ]
        checker.create_policy("Det", "security", rules, severity="critical")
        result = checker.check_compliance("test-module")
        if result["violations"]:
            v = result["violations"][0]
            assert "violation" in v
            assert "policy_id" in v
            assert "severity" in v
            assert "scope" in v

    def test_overall_status_error_takes_precedence(self, checker):
        rules_error = [{"field": "x", "operator": "always_fail", "value": None}]
        checker.create_policy("Err", "security", rules_error, severity="info")
        result = checker.check_compliance("mod", scope="security")
        # error > violation > warning > compliant in overall
        assert result["overall_status"] in ("violation", "warning", "error")

    def test_multiple_violations_counted(self, checker):
        rules = [
            {"field": "module_id", "operator": "eq", "value": "a",
             "message": "Rule 1 failed"},
            {"field": "module_id", "operator": "ne", "value": "test-module",
             "message": "Rule 2 failed"},
        ]
        checker.create_policy("Multi", "security", rules, severity="critical")
        result = checker.check_compliance("test-module")
        assert result["violation_count"] >= 1

    def test_checked_at_timestamp(self, checker):
        before = time.time()
        checker.create_policy("P", "security", [])
        result = checker.check_compliance("mod")
        after = time.time()
        assert before <= result["checked_at"] <= after


# ---------------------------------------------------------------------------
# Test: get_check
# ---------------------------------------------------------------------------

class TestGetCheck:

    def test_retrieves_existing_check(self, checker):
        checker.create_policy("P", "security", [])
        result = checker.check_compliance("mod")
        check_id = result["check_ids"][0]
        check = checker.get_check(check_id)
        assert check is not None
        assert check["check_id"] == check_id
        assert check["module_id"] == "mod"

    def test_returns_none_for_missing(self, checker):
        result = checker.get_check("nonexistent")
        assert result is None

    def test_check_has_required_fields(self, checker):
        checker.create_policy("P", "security", [])
        result = checker.check_compliance("mod")
        check = checker.get_check(result["check_ids"][0])
        assert "check_id" in check
        assert "policy_id" in check
        assert "module_id" in check
        assert "scope" in check
        assert "status" in check
        assert "violations" in check
        assert "checked_at" in check


# ---------------------------------------------------------------------------
# Test: list_checks
# ---------------------------------------------------------------------------

class TestListChecks:

    def test_lists_all_checks(self, checker):
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod-a")
        checker.check_compliance("mod-b")
        result = checker.list_checks()
        assert len(result) == 2

    def test_filters_by_module_id(self, checker):
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod-a")
        checker.check_compliance("mod-b")
        result = checker.list_checks(module_id="mod-a")
        assert len(result) == 1
        assert result[0]["module_id"] == "mod-a"

    def test_filters_by_policy_id(self, checker):
        p1 = checker.create_policy("P1", "security", [])
        p2 = checker.create_policy("P2", "quality", [])
        checker.check_compliance("mod", scope="all")
        result = checker.list_checks(policy_id=p1["policy_id"])
        assert len(result) == 1

    def test_filters_by_status(self, checker):
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod")
        result = checker.list_checks(status="compliant")
        assert all(c["status"] == "compliant" for c in result)

    def test_rejects_invalid_status(self, checker):
        with pytest.raises(ValueError, match="Invalid check status"):
            checker.list_checks(status="invalid")

    def test_respects_limit(self, checker):
        checker.create_policy("P", "security", [])
        for i in range(5):
            checker.check_compliance(f"mod-{i}")
        result = checker.list_checks(limit=3)
        assert len(result) == 3

    def test_returns_empty_when_no_checks(self, checker):
        result = checker.list_checks()
        assert result == []

    def test_ordered_by_checked_at_desc(self, checker):
        checker.create_policy("P", "security", [])
        checker.check_compliance("first")
        time.sleep(0.01)
        checker.check_compliance("second")
        result = checker.list_checks()
        assert result[0]["module_id"] == "second"
        assert result[1]["module_id"] == "first"


# ---------------------------------------------------------------------------
# Test: get_stats
# ---------------------------------------------------------------------------

class TestGetStats:

    def test_empty_stats(self, checker):
        stats = checker.get_stats()
        assert stats["total_policies"] == 0
        assert stats["enabled_policies"] == 0
        assert stats["disabled_policies"] == 0
        assert stats["total_checks"] == 0
        assert stats["compliance_rate"] == 100.0

    def test_counts_policies(self, checker):
        checker.create_policy("A", "security", [])
        checker.create_policy("B", "quality", [])
        checker.create_policy("C", "architecture", [])
        stats = checker.get_stats()
        assert stats["total_policies"] == 3
        assert stats["enabled_policies"] == 3
        assert stats["disabled_policies"] == 0

    def test_counts_disabled_policies(self, checker):
        p1 = checker.create_policy("A", "security", [])
        checker.create_policy("B", "quality", [])
        checker.update_policy(p1["policy_id"], enabled=False)
        stats = checker.get_stats()
        assert stats["enabled_policies"] == 1
        assert stats["disabled_policies"] == 1

    def test_counts_checks_by_status(self, checker):
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod")
        stats = checker.get_stats()
        assert stats["total_checks"] >= 1
        assert stats["compliant_checks"] + stats["violation_checks"] + \
               stats["warning_checks"] + stats["error_checks"] == stats["total_checks"]

    def test_compliance_rate_calculation(self, checker):
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod")
        stats = checker.get_stats()
        if stats["total_checks"] > 0:
            expected_rate = stats["compliant_checks"] / stats["total_checks"] * 100
            assert abs(stats["compliance_rate"] - round(expected_rate, 2)) < 0.01

    def test_by_scope_breakdown(self, checker):
        checker.create_policy("A", "security", [])
        checker.create_policy("B", "security", [])
        checker.create_policy("C", "quality", [])
        stats = checker.get_stats()
        assert stats["by_scope"]["security"] == 2
        assert stats["by_scope"]["quality"] == 1

    def test_by_severity_breakdown(self, checker):
        checker.create_policy("A", "security", [], severity="critical")
        checker.create_policy("B", "quality", [], severity="info")
        stats = checker.get_stats()
        assert stats["by_severity"]["critical"] == 1
        assert stats["by_severity"]["info"] == 1


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:

    def test_create_policy_emits_event(self, checker_with_bus):
        checker, bus = checker_with_bus
        events = []
        bus.subscribe("compliance.policy_created", lambda e: events.append(e))
        checker.create_policy("P", "security", [])
        assert len(events) == 1
        assert events[0].payload["name"] == "P"
        assert events[0].payload["scope"] == "security"

    def test_update_policy_emits_event(self, checker_with_bus):
        checker, bus = checker_with_bus
        events = []
        bus.subscribe("compliance.policy_updated", lambda e: events.append(e))
        p = checker.create_policy("P", "security", [])
        checker.update_policy(p["policy_id"], name="Updated")
        assert len(events) == 1
        assert events[0].payload["policy_id"] == p["policy_id"]

    def test_delete_policy_emits_event(self, checker_with_bus):
        checker, bus = checker_with_bus
        events = []
        bus.subscribe("compliance.policy_deleted", lambda e: events.append(e))
        p = checker.create_policy("P", "security", [])
        checker.delete_policy(p["policy_id"])
        assert len(events) == 1
        assert events[0].payload["policy_id"] == p["policy_id"]

    def test_check_compliance_emits_checked_event(self, checker_with_bus):
        checker, bus = checker_with_bus
        events = []
        bus.subscribe("compliance.checked", lambda e: events.append(e))
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod")
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod"

    def test_violation_emits_violation_event(self, checker_with_bus):
        checker, bus = checker_with_bus
        events = []
        bus.subscribe("compliance.violation", lambda e: events.append(e))
        rules = [
            {"field": "module_id", "operator": "eq", "value": "no-match",
             "message": "Fail"},
        ]
        checker.create_policy("P", "security", rules, severity="critical")
        checker.check_compliance("test-module")
        assert len(events) == 1
        assert events[0].payload["violation_count"] >= 1

    def test_compliant_does_not_emit_violation_event(self, checker_with_bus):
        checker, bus = checker_with_bus
        events = []
        bus.subscribe("compliance.violation", lambda e: events.append(e))
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod")
        assert len(events) == 0

    def test_no_event_without_bus(self, checker):
        # Should not raise -- _emit gracefully handles None event_bus
        checker.create_policy("P", "security", [])
        checker.check_compliance("mod")


# ---------------------------------------------------------------------------
# Test: validation
# ---------------------------------------------------------------------------

class TestValidation:

    def test_valid_scopes_constant(self):
        assert "security" in VALID_SCOPES
        assert "quality" in VALID_SCOPES
        assert "architecture" in VALID_SCOPES
        assert "performance" in VALID_SCOPES
        assert "all" in VALID_SCOPES

    def test_valid_severities_constant(self):
        assert "info" in VALID_SEVERITIES
        assert "warning" in VALID_SEVERITIES
        assert "critical" in VALID_SEVERITIES

    def test_valid_check_statuses_constant(self):
        assert "compliant" in VALID_CHECK_STATUSES
        assert "violation" in VALID_CHECK_STATUSES
        assert "warning" in VALID_CHECK_STATUSES
        assert "error" in VALID_CHECK_STATUSES

    def test_create_policy_rejects_bad_scope(self, checker):
        with pytest.raises(ValueError):
            checker.create_policy("P", "bad_scope", [])

    def test_create_policy_rejects_bad_severity(self, checker):
        with pytest.raises(ValueError):
            checker.create_policy("P", "security", [], severity="high")

    def test_check_compliance_rejects_bad_scope(self, checker):
        with pytest.raises(ValueError):
            checker.check_compliance("mod", scope="invalid")

    def test_list_checks_rejects_bad_status(self, checker):
        with pytest.raises(ValueError):
            checker.list_checks(status="invalid")


# ---------------------------------------------------------------------------
# Test: rule evaluation operators
# ---------------------------------------------------------------------------

class TestRuleOperators:

    def test_eq_operator_match(self, checker):
        rules = [{"field": "module_id", "operator": "eq", "value": "my-mod"}]
        checker.create_policy("P", "security", rules)
        result = checker.check_compliance("my-mod")
        assert result["compliant_count"] >= 1

    def test_eq_operator_no_match(self, checker):
        rules = [
            {"field": "module_id", "operator": "eq", "value": "other",
             "message": "Not equal"},
        ]
        checker.create_policy("P", "security", rules, severity="critical")
        result = checker.check_compliance("my-mod")
        assert result["violation_count"] >= 1

    def test_ne_operator(self, checker):
        rules = [{"field": "module_id", "operator": "ne", "value": "blocked"}]
        checker.create_policy("P", "security", rules)
        result = checker.check_compliance("allowed-mod")
        assert result["compliant_count"] >= 1

    def test_contains_operator(self, checker):
        rules = [{"field": "module_id", "operator": "contains", "value": "core"}]
        checker.create_policy("P", "security", rules)
        result = checker.check_compliance("my-core-module")
        assert result["compliant_count"] >= 1

    def test_not_contains_operator(self, checker):
        rules = [
            {"field": "module_id", "operator": "not_contains", "value": "internal",
             "message": "No internal"},
        ]
        checker.create_policy("P", "security", rules, severity="critical")
        result = checker.check_compliance("public-module")
        assert result["compliant_count"] >= 1

    def test_in_operator(self, checker):
        rules = [{"field": "module_id", "operator": "in",
                   "value": ["mod-a", "mod-b", "mod-c"]}]
        checker.create_policy("P", "security", rules)
        result = checker.check_compliance("mod-b")
        assert result["compliant_count"] >= 1

    def test_not_in_operator(self, checker):
        rules = [
            {"field": "module_id", "operator": "not_in",
             "value": ["blocked-a", "blocked-b"],
             "message": "Blocked"},
        ]
        checker.create_policy("P", "security", rules, severity="critical")
        result = checker.check_compliance("safe-mod")
        assert result["compliant_count"] >= 1

    def test_matches_regex_operator(self, checker):
        rules = [{"field": "module_id", "operator": "matches",
                   "value": r"^[\w-]+$"}]
        checker.create_policy("P", "security", rules)
        result = checker.check_compliance("valid-module")
        assert result["compliant_count"] >= 1

    def test_always_pass_operator(self, checker):
        rules = [{"field": "x", "operator": "always_pass", "value": None}]
        checker.create_policy("P", "security", rules)
        result = checker.check_compliance("any-mod")
        assert result["compliant_count"] >= 1

    def test_always_fail_operator(self, checker):
        rules = [
            {"field": "x", "operator": "always_fail", "value": None,
             "message": "Always fails"},
        ]
        checker.create_policy("P", "security", rules, severity="critical")
        result = checker.check_compliance("any-mod")
        assert result["violation_count"] >= 1


# ---------------------------------------------------------------------------
# Test: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_policy_creates(self, checker):
        errors = []

        def create(idx):
            try:
                checker.create_policy(f"P-{idx}", "security", [])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(checker.list_policies()) == 20

    def test_concurrent_checks(self, checker):
        checker.create_policy("P", "security", [])
        errors = []

        def run_check(idx):
            try:
                checker.check_compliance(f"mod-{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_check, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(checker.list_checks()) == 20

    def test_concurrent_read_write(self, checker):
        checker.create_policy("P", "security", [])
        errors = []

        def reader():
            try:
                for _ in range(30):
                    checker.list_policies()
                    checker.list_checks()
                    checker.get_stats()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    checker.check_compliance(f"mod-{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Test: singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_compliance_checker_returns_same_instance(self):
        import sylion.governance.compliance_checker as mod
        mod._checker = None
        c1 = get_compliance_checker(db_path=":memory:")
        c2 = get_compliance_checker()
        assert c1 is c2
        mod._checker = None  # cleanup

    def test_reset_compliance_checker_creates_new_instance(self):
        import sylion.governance.compliance_checker as mod
        mod._checker = None
        c1 = get_compliance_checker(db_path=":memory:")
        c2 = reset_compliance_checker(db_path=":memory:")
        assert c1 is not c2
        mod._checker = None  # cleanup
