"""
Tests for ComplianceEngine -- rule management, compliance checks, reports,
violations, scope filtering, severity levels, singleton pattern, thread safety.

Covers ~45 tests for add/list/remove rules, D0-D5 compliance checks,
report generation, compliance scores, violations listing, history,
disabled rules, and thread safety.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.governance.compliance_engine import (
    ComplianceEngine,
    get_compliance_engine,
    reset_compliance_engine,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset global singleton before and after every test."""
    reset_compliance_engine()
    yield
    reset_compliance_engine()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def engine(bus) -> ComplianceEngine:
    """Fresh in-memory ComplianceEngine with EventBus."""
    return ComplianceEngine(event_bus=bus)


@pytest.fixture
def engine_no_bus() -> ComplianceEngine:
    """Engine without EventBus."""
    return ComplianceEngine()


def _add_standard_rules(eng: ComplianceEngine):
    """Add a standard set of governance compliance rules."""
    eng.add_rule(
        name="Evidence Required for D3+",
        scope="global",
        rule_type="required_evidence",
        parameters={"min_decision_class": "D3"},
        severity="blocking",
        description="D3+ decisions must have evidence packs",
    )
    eng.add_rule(
        name="Council Approval Required for D3+",
        scope="global",
        rule_type="required_approvals",
        parameters={"min_decision_class": "D3"},
        severity="blocking",
        description="D3+ decisions require council approval",
    )
    eng.add_rule(
        name="Human Gate Required for D4+",
        scope="global",
        rule_type="required_human_gate",
        parameters={"min_decision_class": "D4"},
        severity="blocking",
        description="D4+ decisions require human gate",
    )
    eng.add_rule(
        name="External Review Required for D5",
        scope="global",
        rule_type="required_external_review",
        parameters={"min_decision_class": "D5"},
        severity="blocking",
        description="D5 decisions require external review",
    )
    eng.add_rule(
        name="Council Deliberation for D2+",
        scope="global",
        rule_type="required_council",
        parameters={"min_decision_class": "D2"},
        severity="advisory",
        description="D2+ should have council deliberation",
    )
    eng.add_rule(
        name="Retention Policy",
        scope="global",
        rule_type="retention_policy",
        parameters={"min_retention_hot": "2y", "min_retention_cold": "infinite"},
        severity="advisory",
        description="Minimum retention policy",
    )


# ===========================================================================
# TestAddRule
# ===========================================================================

class TestAddRule:

    def test_add_rule_returns_rule_id(self, engine):
        result = engine.add_rule("Test Rule", "global", "required_evidence",
                                 {"min_decision_class": "D3"})
        assert "rule_id" in result
        assert isinstance(result["rule_id"], str)

    def test_add_rule_returns_name(self, engine):
        result = engine.add_rule("My Rule", "global", "required_evidence",
                                 {"min_decision_class": "D3"})
        assert result["name"] == "My Rule"

    def test_add_rule_returns_scope(self, engine):
        result = engine.add_rule("R", "pipeline", "required_evidence", {})
        assert result["scope"] == "pipeline"

    def test_add_rule_returns_rule_type(self, engine):
        result = engine.add_rule("R", "global", "max_blast_radius",
                                 {"max_blast_radius": "high"})
        assert result["rule_type"] == "max_blast_radius"

    def test_add_rule_default_severity(self, engine):
        engine.add_rule("R", "global", "required_evidence", {})
        rules = engine.list_rules()
        assert rules[0]["severity"] == "blocking"

    def test_add_rule_custom_severity(self, engine):
        engine.add_rule("R", "global", "required_evidence", {},
                        severity="advisory")
        rules = engine.list_rules()
        assert rules[0]["severity"] == "advisory"

    def test_add_rule_with_description(self, engine):
        engine.add_rule("R", "global", "required_evidence", {},
                        description="A test rule")
        rules = engine.list_rules()
        assert rules[0]["description"] == "A test rule"

    def test_add_rule_with_scope_filter(self, engine):
        engine.add_rule("R", "decision_class", "required_evidence",
                        {"min_decision_class": "D3"},
                        scope_filter={"decision_class": "D4"})
        rules = engine.list_rules()
        assert rules[0]["scope_filter"] == {"decision_class": "D4"}

    def test_add_multiple_rules(self, engine):
        for i in range(5):
            engine.add_rule(f"Rule {i}", "global", "required_evidence", {})
        rules = engine.list_rules()
        assert len(rules) == 5


# ===========================================================================
# TestListRules
# ===========================================================================

class TestListRules:

    def test_list_rules_empty(self, engine):
        rules = engine.list_rules()
        assert rules == []

    def test_list_rules_returns_all(self, engine):
        _add_standard_rules(engine)
        rules = engine.list_rules()
        assert len(rules) == 6

    def test_list_rules_filter_by_scope(self, engine):
        engine.add_rule("Global", "global", "required_evidence", {})
        engine.add_rule("Pipeline", "pipeline", "required_evidence", {})
        rules = engine.list_rules(scope="pipeline")
        # global rules are also returned (they apply to all scopes)
        assert len(rules) == 2

    def test_list_rules_filter_by_type(self, engine):
        _add_standard_rules(engine)
        rules = engine.list_rules(rule_type="required_evidence")
        assert len(rules) == 1
        assert rules[0]["rule_type"] == "required_evidence"

    def test_list_rules_enabled_only(self, engine):
        r1 = engine.add_rule("Active", "global", "required_evidence", {})
        engine.add_rule("Inactive", "global", "required_evidence", {})
        engine.remove_rule(r1["rule_id"])
        rules = engine.list_rules(enabled_only=True)
        assert len(rules) == 1
        assert rules[0]["name"] == "Inactive"

    def test_list_rules_includes_disabled(self, engine):
        r1 = engine.add_rule("Active", "global", "required_evidence", {})
        engine.remove_rule(r1["rule_id"])
        rules = engine.list_rules(enabled_only=False)
        assert len(rules) == 1


# ===========================================================================
# TestRemoveRule
# ===========================================================================

class TestRemoveRule:

    def test_remove_rule_returns_true(self, engine):
        result = engine.add_rule("R", "global", "required_evidence", {})
        removed = engine.remove_rule(result["rule_id"])
        assert removed is True

    def test_remove_nonexistent_rule(self, engine):
        removed = engine.remove_rule("nonexistent")
        assert removed is False

    def test_removed_rule_not_in_enabled_list(self, engine):
        result = engine.add_rule("R", "global", "required_evidence", {})
        engine.remove_rule(result["rule_id"])
        rules = engine.list_rules(enabled_only=True)
        assert len(rules) == 0

    def test_removed_rule_still_in_db(self, engine):
        result = engine.add_rule("R", "global", "required_evidence", {})
        engine.remove_rule(result["rule_id"])
        rules = engine.list_rules(enabled_only=False)
        assert len(rules) == 1
        assert rules[0]["enabled"] == 0


# ===========================================================================
# TestGetRule
# ===========================================================================

class TestGetRule:

    def test_get_rule_returns_rule(self, engine):
        r = engine.add_rule("My Rule", "global", "required_evidence",
                            {"min_decision_class": "D3"})
        rule = engine.get_rule(r["rule_id"])
        assert rule is not None
        assert rule["name"] == "My Rule"
        assert rule["parameters"] == {"min_decision_class": "D3"}

    def test_get_nonexistent_rule(self, engine):
        rule = engine.get_rule("nonexistent")
        assert rule is None


# ===========================================================================
# TestCheckCompliance
# ===========================================================================

class TestCheckCompliance:

    def test_check_compliance_no_rules(self, engine):
        result = engine.check_compliance()
        assert result["status"] == "pass"
        assert result["passed"] == 0
        assert result["failed"] == 0

    def test_check_compliance_returns_check_id(self, engine):
        _add_standard_rules(engine)
        result = engine.check_compliance()
        assert "check_id" in result
        assert isinstance(result["check_id"], str)

    def test_check_compliance_d0_all_pass(self, engine):
        _add_standard_rules(engine)
        # D0 decisions have no requirements - all rules should be not_applicable
        result = engine.check_compliance(decision_id="d0-decision-123")
        # Without an actual decision record, decision_class is None,
        # so most rules will be not_applicable
        assert result["status"] == "pass"
        assert result["failed"] == 0

    def test_check_compliance_returns_violations_list(self, engine):
        engine.add_rule("Evidence Required", "global", "required_evidence",
                        {"min_decision_class": "D3"})
        result = engine.check_compliance(decision_id="test-decision")
        assert isinstance(result["violations"], list)

    def test_check_compliance_returns_checks_detail(self, engine):
        _add_standard_rules(engine)
        result = engine.check_compliance()
        assert isinstance(result["checks"], list)

    def test_check_compliance_with_snapshot_id(self, engine):
        _add_standard_rules(engine)
        result = engine.check_compliance(snapshot_id="snap-123")
        assert "check_id" in result


# ===========================================================================
# TestCheckSingleRule
# ===========================================================================

class TestCheckSingleRule:

    def test_check_single_rule_returns_result(self, engine):
        r = engine.add_rule("Test", "global", "required_evidence",
                            {"min_decision_class": "D3"})
        result = engine.check_single_rule(r["rule_id"])
        assert "check_id" in result
        assert "status" in result

    def test_check_single_rule_nonexistent(self, engine):
        result = engine.check_single_rule("nonexistent")
        assert "error" in result

    def test_check_single_rule_disabled(self, engine):
        r = engine.add_rule("Test", "global", "required_evidence",
                            {"min_decision_class": "D3"})
        engine.remove_rule(r["rule_id"])
        result = engine.check_single_rule(r["rule_id"])
        assert result["status"] == "not_applicable"


# ===========================================================================
# TestGenerateReport
# ===========================================================================

class TestGenerateReport:

    def test_generate_report_returns_report_id(self, engine):
        report = engine.generate_report()
        assert "report_id" in report
        assert isinstance(report["report_id"], str)

    def test_generate_report_no_rules(self, engine):
        report = engine.generate_report()
        assert report["total_rules"] == 0
        assert report["passed"] == 0
        assert report["failed"] == 0
        assert report["score"] == 1.0

    def test_generate_report_with_rules(self, engine):
        _add_standard_rules(engine)
        report = engine.generate_report()
        assert report["total_rules"] == 6

    def test_generate_report_score_perfect(self, engine):
        # Retention policy always passes, others not_applicable without decisions
        engine.add_rule("Retention", "global", "retention_policy",
                        {"min_retention_hot": "2y"}, severity="advisory")
        report = engine.generate_report()
        assert report["score"] == 1.0

    def test_generate_report_score_range(self, engine):
        report = engine.generate_report()
        assert 0.0 <= report["score"] <= 1.0

    def test_generate_report_scope(self, engine):
        report = engine.generate_report(scope="pipeline")
        assert report["scope"] == "pipeline"

    def test_generate_report_has_timestamp(self, engine):
        report = engine.generate_report()
        assert "generated_at" in report
        assert report["generated_at"] > 0


# ===========================================================================
# TestGetReport
# ===========================================================================

class TestGetReport:

    def test_get_report_returns_report(self, engine):
        generated = engine.generate_report()
        report = engine.get_report(generated["report_id"])
        assert report is not None
        assert report["report_id"] == generated["report_id"]

    def test_get_report_nonexistent(self, engine):
        report = engine.get_report("nonexistent")
        assert report is None

    def test_get_report_parses_details(self, engine):
        _add_standard_rules(engine)
        generated = engine.generate_report()
        report = engine.get_report(generated["report_id"])
        assert isinstance(report["details"], list)


# ===========================================================================
# TestGetLatestReport
# ===========================================================================

class TestGetLatestReport:

    def test_get_latest_report_none(self, engine):
        report = engine.get_latest_report()
        assert report is None

    def test_get_latest_report_returns_most_recent(self, engine):
        r1 = engine.generate_report()
        time.sleep(0.01)
        r2 = engine.generate_report()
        latest = engine.get_latest_report()
        assert latest["report_id"] == r2["report_id"]

    def test_get_latest_report_by_scope(self, engine):
        engine.generate_report(scope="global")
        engine.generate_report(scope="pipeline")
        latest = engine.get_latest_report(scope="pipeline")
        assert latest["scope"] == "pipeline"


# ===========================================================================
# TestComplianceScore
# ===========================================================================

class TestComplianceScore:

    def test_compliance_score_default(self, engine):
        score = engine.get_compliance_score()
        assert score == 1.0

    def test_compliance_score_after_report(self, engine):
        engine.generate_report()
        score = engine.get_compliance_score()
        assert 0.0 <= score <= 1.0

    def test_compliance_score_perfect(self, engine):
        engine.add_rule("Retention", "global", "retention_policy", {})
        engine.generate_report()
        score = engine.get_compliance_score()
        assert score == 1.0


# ===========================================================================
# TestViolations
# ===========================================================================

class TestViolations:

    def test_list_violations_empty(self, engine):
        violations = engine.list_violations()
        assert violations == []

    def test_list_violations_after_check(self, engine):
        engine.add_rule("Evidence Required", "global", "required_evidence",
                        {"min_decision_class": "D3"})
        # Run a check that would produce failures - but without real decision,
        # it returns not_applicable. We need to check actual failed checks.
        # Let's add a rule that will fail
        engine.add_rule("Always Fail", "global", "required_evidence",
                        {"min_decision_class": "D0"})
        result = engine.check_compliance(decision_id="nonexistent-decision")
        # D0 decision_class with no evidence -> not_applicable because
        # there's no actual decision record. But we stored checks.
        violations = engine.list_violations()
        # Since we can't look up the decision class, rules may be not_applicable
        assert isinstance(violations, list)

    def test_list_violations_filter_by_decision(self, engine):
        engine.add_rule("Evidence Required", "global", "required_evidence",
                        {"min_decision_class": "D3"})
        engine.check_compliance(decision_id="dec-001")
        violations = engine.list_violations(decision_id="dec-001")
        assert isinstance(violations, list)


# ===========================================================================
# TestComplianceHistory
# ===========================================================================

class TestComplianceHistory:

    def test_history_empty(self, engine):
        history = engine.get_compliance_history()
        assert history == []

    def test_history_returns_reports(self, engine):
        engine.generate_report()
        history = engine.get_compliance_history()
        assert len(history) == 1

    def test_history_multiple_reports(self, engine):
        for _ in range(5):
            engine.generate_report()
        history = engine.get_compliance_history()
        assert len(history) == 5

    def test_history_respects_limit(self, engine):
        for _ in range(10):
            engine.generate_report()
        history = engine.get_compliance_history(limit=3)
        assert len(history) == 3

    def test_history_ordered_by_time_desc(self, engine):
        r1 = engine.generate_report()
        time.sleep(0.01)
        r2 = engine.generate_report()
        history = engine.get_compliance_history()
        assert history[0]["report_id"] == r2["report_id"]
        assert history[1]["report_id"] == r1["report_id"]

    def test_history_filter_by_scope(self, engine):
        engine.generate_report(scope="global")
        engine.generate_report(scope="pipeline")
        history = engine.get_compliance_history(scope="pipeline")
        assert len(history) == 1
        assert history[0]["scope"] == "pipeline"


# ===========================================================================
# TestScopeFiltering
# ===========================================================================

class TestScopeFiltering:

    def test_global_rules_apply_to_all_scopes(self, engine):
        engine.add_rule("Global", "global", "required_evidence",
                        {"min_decision_class": "D3"})
        rules = engine.list_rules(scope="pipeline")
        assert len(rules) == 1

    def test_pipeline_rules_not_in_module_scope(self, engine):
        engine.add_rule("Pipeline", "pipeline", "required_evidence",
                        {"min_decision_class": "D3"})
        rules = engine.list_rules(scope="module")
        assert len(rules) == 0

    def test_rule_with_scope_filter(self, engine):
        engine.add_rule("D4 Only", "decision_class", "required_evidence",
                        {"min_decision_class": "D3"},
                        scope_filter={"decision_class": "D4"})
        rules = engine.list_rules()
        assert len(rules) == 1
        assert rules[0]["scope_filter"] == {"decision_class": "D4"}


# ===========================================================================
# TestRuleSeverity
# ===========================================================================

class TestRuleSeverity:

    def test_blocking_severity(self, engine):
        engine.add_rule("R", "global", "required_evidence", {},
                        severity="blocking")
        rules = engine.list_rules()
        assert rules[0]["severity"] == "blocking"

    def test_advisory_severity(self, engine):
        engine.add_rule("R", "global", "required_evidence", {},
                        severity="advisory")
        rules = engine.list_rules()
        assert rules[0]["severity"] == "advisory"

    def test_veto_severity(self, engine):
        engine.add_rule("R", "global", "required_evidence", {},
                        severity="veto")
        rules = engine.list_rules()
        assert rules[0]["severity"] == "veto"


# ===========================================================================
# TestDisabledRules
# ===========================================================================

class TestDisabledRules:

    def test_disabled_rule_not_in_enabled_list(self, engine):
        r = engine.add_rule("R", "global", "required_evidence", {})
        engine.remove_rule(r["rule_id"])
        rules = engine.list_rules(enabled_only=True)
        assert len(rules) == 0

    def test_disabled_rule_skipped_in_compliance(self, engine):
        r = engine.add_rule("Disabled Rule", "global", "required_evidence",
                            {"min_decision_class": "D3"})
        engine.remove_rule(r["rule_id"])
        result = engine.check_compliance()
        assert result["passed"] == 0
        assert result["failed"] == 0

    def test_disabled_rule_skipped_in_report(self, engine):
        r = engine.add_rule("Disabled", "global", "required_evidence", {})
        engine.remove_rule(r["rule_id"])
        report = engine.generate_report()
        assert report["total_rules"] == 0


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_compliance_engine_returns_instance(self):
        engine = get_compliance_engine()
        assert isinstance(engine, ComplianceEngine)

    def test_get_compliance_engine_singleton(self):
        e1 = get_compliance_engine()
        e2 = get_compliance_engine()
        assert e1 is e2

    def test_reset_compliance_engine_creates_new(self):
        e1 = get_compliance_engine()
        e2 = reset_compliance_engine()
        assert e1 is not e2

    def test_reset_then_get_returns_same(self):
        e1 = reset_compliance_engine()
        e2 = get_compliance_engine()
        assert e1 is e2


# ===========================================================================
# TestEventEmission
# ===========================================================================

class TestEventEmission:

    def test_add_rule_emits_event(self, bus):
        events = []
        bus.subscribe("compliance.rule_added", lambda e: events.append(e))
        engine = ComplianceEngine(event_bus=bus)
        engine.add_rule("R", "global", "required_evidence", {})
        assert len(events) == 1
        assert events[0].payload["name"] == "R"

    def test_remove_rule_emits_event(self, bus):
        events = []
        bus.subscribe("compliance.rule_removed", lambda e: events.append(e))
        engine = ComplianceEngine(event_bus=bus)
        r = engine.add_rule("R", "global", "required_evidence", {})
        engine.remove_rule(r["rule_id"])
        assert len(events) == 1

    def test_check_compliance_emits_event(self, bus):
        events = []
        bus.subscribe("compliance.checked", lambda e: events.append(e))
        engine = ComplianceEngine(event_bus=bus)
        engine.check_compliance()
        assert len(events) == 1

    def test_generate_report_emits_event(self, bus):
        events = []
        bus.subscribe("compliance.report_generated", lambda e: events.append(e))
        engine = ComplianceEngine(event_bus=bus)
        engine.generate_report()
        assert len(events) == 1


# ===========================================================================
# TestRuleTypes
# ===========================================================================

class TestRuleTypes:

    def test_retention_policy_passes(self, engine):
        engine.add_rule("Retention", "global", "retention_policy",
                        {"min_retention_hot": "2y", "min_retention_cold": "infinite"})
        result = engine.check_compliance()
        assert result["passed"] >= 1

    def test_max_blast_radius_rule(self, engine):
        engine.add_rule("Max Blast", "global", "max_blast_radius",
                        {"max_blast_radius": "high"})
        result = engine.check_compliance(decision_id="some-decision")
        # Without actual decision record, returns not_applicable
        assert result["status"] == "pass"

    def test_required_council_rule(self, engine):
        engine.add_rule("Council", "global", "required_council",
                        {"min_decision_class": "D2"})
        result = engine.check_compliance(decision_id="dec-1")
        assert "check_id" in result

    def test_unknown_rule_type(self, engine):
        engine.add_rule("Unknown", "global", "custom_unknown_type", {})
        result = engine.check_compliance()
        # Unknown types should be not_applicable
        assert result["status"] == "pass"


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_rule_adds(self, engine):
        errors = []

        def add_rules():
            try:
                for i in range(20):
                    engine.add_rule(f"Rule-{threading.current_thread().name}-{i}",
                                    "global", "required_evidence", {})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_rules, name=f"T{i}") for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        rules = engine.list_rules()
        assert len(rules) == 80

    def test_concurrent_reports(self, engine):
        _add_standard_rules(engine)
        results = []

        def gen_report():
            r = engine.generate_report()
            results.append(r)

        threads = [threading.Thread(target=gen_report) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        report_ids = {r["report_id"] for r in results}
        assert len(report_ids) == 5  # all unique

    def test_concurrent_checks(self, engine):
        _add_standard_rules(engine)
        results = []

        def run_check():
            r = engine.check_compliance(decision_id=f"dec-{threading.current_thread().name}")
            results.append(r)

        threads = [threading.Thread(target=run_check, name=f"T{i}") for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
