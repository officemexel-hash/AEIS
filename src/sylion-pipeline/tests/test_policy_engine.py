"""Tests for PolicyEngine -- rule evaluation, compliance checking, audit trail."""
import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.policy_engine import (
    PolicyEngine,
    _evaluate_rules,
    _evaluate_single_rule,
    get_policy_engine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Fresh PolicyEngine with :memory: SQLite."""
    return PolicyEngine(db_path=":memory:")


@pytest.fixture
def engine_with_bus():
    """PolicyEngine connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return PolicyEngine(db_path=":memory:", event_bus=bus), bus


def _sample_rules():
    return [
        {"field": "blast_radius", "operator": "eq", "value": "low", "message": "Must be low blast radius"},
        {"field": "reversible", "operator": "eq", "value": True, "message": "Must be reversible"},
    ]


def _create_sample_policy(engine, policy_id="pol-001", **overrides):
    defaults = {
        "policy_id": policy_id,
        "name": "Sample Policy",
        "description": "A test policy",
        "rules": _sample_rules(),
        "scope": "security",
        "decision_class": "D2",
    }
    defaults.update(overrides)
    return engine.create_policy(**defaults)


# ---------------------------------------------------------------------------
# Test: create_policy
# ---------------------------------------------------------------------------

class TestCreatePolicy:
    def test_creates_policy_successfully(self, engine):
        result = _create_sample_policy(engine)
        assert result["policy_id"] == "pol-001"
        assert result["name"] == "Sample Policy"
        assert result["description"] == "A test policy"
        assert result["scope"] == "security"
        assert result["decision_class"] == "D2"
        assert result["active"] is True
        assert result["version"] == 1

    def test_creates_with_defaults(self, engine):
        result = engine.create_policy("pol-min", "Minimal Policy")
        assert result["policy_id"] == "pol-min"
        assert result["rules"] == []
        assert result["scope"] == "global"
        assert result["decision_class"] == "D2"
        assert result["active"] is True

    def test_rejects_duplicate_policy_id(self, engine):
        _create_sample_policy(engine, policy_id="dup")
        with pytest.raises(ValueError, match="already exists"):
            _create_sample_policy(engine, policy_id="dup")

    def test_stores_rules_as_json(self, engine):
        rules = [{"field": "x", "operator": "gt", "value": 10}]
        result = engine.create_policy("pol-json", "JSON Policy", rules=rules)
        assert len(result["rules"]) == 1
        assert result["rules"][0]["field"] == "x"

    def test_created_at_timestamp_set(self, engine):
        before = time.time()
        result = engine.create_policy("pol-ts", "TS Policy")
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_updated_at_equals_created_at_on_create(self, engine):
        result = engine.create_policy("pol-eq", "EQ Policy")
        assert result["created_at"] == result["updated_at"]

    def test_active_by_default(self, engine):
        result = engine.create_policy("pol-act", "Active Policy")
        assert result["active"] is True


# ---------------------------------------------------------------------------
# Test: update_policy
# ---------------------------------------------------------------------------

class TestUpdatePolicy:
    def test_updates_rules(self, engine):
        _create_sample_policy(engine, policy_id="pol-upd")
        new_rules = [{"field": "severity", "operator": "lte", "value": 3}]
        result = engine.update_policy("pol-upd", rules=new_rules, changelog="Updated rules")
        assert len(result["rules"]) == 1
        assert result["rules"][0]["field"] == "severity"
        assert result["version"] == 2

    def test_records_history_on_update(self, engine):
        _create_sample_policy(engine, policy_id="pol-hist")
        engine.update_policy("pol-hist", rules=[], changelog="Cleared rules")
        history = engine.get_policy_history("pol-hist")
        assert len(history) == 1
        assert history[0]["action"] == "update"
        assert history[0]["changelog"] == "Cleared rules"
        assert history[0]["version"] == 2

    def test_preserves_old_rules_in_history(self, engine):
        _create_sample_policy(engine, policy_id="pol-old")
        old_rules = engine.list_policies()[0]["rules"]
        engine.update_policy("pol-old", rules=[], changelog="Cleared")
        history = engine.get_policy_history("pol-old")
        assert history[0]["old_rules"] == old_rules
        assert history[0]["new_rules"] == []

    def test_returns_none_for_missing_policy(self, engine):
        result = engine.update_policy("nonexistent", rules=[])
        assert result is None

    def test_no_rules_update_when_rules_is_none(self, engine):
        _create_sample_policy(engine, policy_id="pol-none")
        result = engine.update_policy("pol-none", rules=None, changelog="No change to rules")
        assert len(result["rules"]) == 2  # unchanged

    def test_version_increments_on_each_update(self, engine):
        _create_sample_policy(engine, policy_id="pol-ver")
        r1 = engine.update_policy("pol-ver", rules=[], changelog="v2")
        r2 = engine.update_policy("pol-ver", rules=[{"field": "a", "operator": "eq", "value": 1}], changelog="v3")
        assert r1["version"] == 2
        assert r2["version"] == 3

    def test_updated_at_changes_on_update(self, engine):
        _create_sample_policy(engine, policy_id="pol-uts")
        time.sleep(0.01)
        result = engine.update_policy("pol-uts", rules=[], changelog="update")
        policy = engine.list_policies()[0]
        assert policy["updated_at"] > policy["created_at"]


# ---------------------------------------------------------------------------
# Test: activate_policy / deactivate_policy
# ---------------------------------------------------------------------------

class TestActivateDeactivate:
    def test_deactivate_sets_inactive(self, engine):
        _create_sample_policy(engine, policy_id="pol-deact")
        result = engine.deactivate_policy("pol-deact")
        assert result["active"] is False

    def test_activate_sets_active(self, engine):
        _create_sample_policy(engine, policy_id="pol-react")
        engine.deactivate_policy("pol-react")
        result = engine.activate_policy("pol-react")
        assert result["active"] is True

    def test_activate_returns_none_for_missing(self, engine):
        result = engine.activate_policy("ghost")
        assert result is None

    def test_deactivate_returns_none_for_missing(self, engine):
        result = engine.deactivate_policy("ghost")
        assert result is None

    def test_deactivate_records_history(self, engine):
        _create_sample_policy(engine, policy_id="pol-dhist")
        engine.deactivate_policy("pol-dhist")
        history = engine.get_policy_history("pol-dhist")
        assert len(history) == 1
        assert history[0]["action"] == "deactivate"

    def test_activate_records_history(self, engine):
        _create_sample_policy(engine, policy_id="pol-ahist")
        engine.deactivate_policy("pol-ahist")
        engine.activate_policy("pol-ahist")
        history = engine.get_policy_history("pol-ahist")
        assert len(history) == 2
        assert history[0]["action"] == "deactivate"
        assert history[1]["action"] == "activate"

    def test_toggle_multiple_times(self, engine):
        _create_sample_policy(engine, policy_id="pol-tog")
        engine.deactivate_policy("pol-tog")   # history: deactivate
        engine.activate_policy("pol-tog")      # history: activate
        engine.deactivate_policy("pol-tog")    # history: deactivate
        result = engine.deactivate_policy("pol-tog")  # already inactive, still records
        assert result["active"] is False
        history = engine.get_policy_history("pol-tog")
        # 3 explicit toggles + 1 redundant deactivate = 4
        assert len(history) == 4


# ---------------------------------------------------------------------------
# Test: evaluate_policy
# ---------------------------------------------------------------------------

class TestEvaluatePolicy:
    def test_compliant_when_all_rules_pass(self, engine):
        rules = [
            {"field": "blast_radius", "operator": "eq", "value": "low"},
            {"field": "reversible", "operator": "eq", "value": True},
        ]
        engine.create_policy("pol-comp", "Compliant", rules=rules)
        ctx = {"blast_radius": "low", "reversible": True}
        result = engine.evaluate_policy("pol-comp", ctx)
        assert result["compliant"] is True
        assert len(result["violations"]) == 0
        assert len(result["passed"]) == 2
        assert result["total_rules"] == 2

    def test_non_compliant_when_rule_fails(self, engine):
        rules = [
            {"field": "blast_radius", "operator": "eq", "value": "low"},
        ]
        engine.create_policy("pol-fail", "Fail", rules=rules)
        ctx = {"blast_radius": "high"}
        result = engine.evaluate_policy("pol-fail", ctx)
        assert result["compliant"] is False
        assert len(result["violations"]) == 1
        assert result["violations"][0]["passed"] is False

    def test_missing_policy_returns_not_found(self, engine):
        result = engine.evaluate_policy("nonexistent", {})
        assert result["compliant"] is False
        assert len(result["violations"]) == 1
        assert "not found" in result["violations"][0]["message"]

    def test_empty_rules_always_compliant(self, engine):
        engine.create_policy("pol-empty", "Empty Rules", rules=[])
        result = engine.evaluate_policy("pol-empty", {"anything": "value"})
        assert result["compliant"] is True
        assert result["total_rules"] == 0

    def test_missing_context_field_fails_rule(self, engine):
        rules = [{"field": "required_field", "operator": "eq", "value": "expected"}]
        engine.create_policy("pol-miss", "Missing Field", rules=rules)
        result = engine.evaluate_policy("pol-miss", {"other_field": "value"})
        assert result["compliant"] is False

    def test_multiple_rules_partial_violation(self, engine):
        rules = [
            {"field": "a", "operator": "eq", "value": 1},
            {"field": "b", "operator": "eq", "value": 2},
            {"field": "c", "operator": "eq", "value": 3},
        ]
        engine.create_policy("pol-partial", "Partial", rules=rules)
        ctx = {"a": 1, "b": 99, "c": 3}
        result = engine.evaluate_policy("pol-partial", ctx)
        assert result["compliant"] is False
        assert len(result["passed"]) == 2
        assert len(result["violations"]) == 1


# ---------------------------------------------------------------------------
# Test: _evaluate_single_rule (all operators)
# ---------------------------------------------------------------------------

class TestRuleOperators:
    def test_eq(self):
        r = {"field": "x", "operator": "eq", "value": 10}
        assert _evaluate_single_rule(r, {"x": 10})["passed"] is True
        assert _evaluate_single_rule(r, {"x": 5})["passed"] is False

    def test_ne(self):
        r = {"field": "x", "operator": "ne", "value": 10}
        assert _evaluate_single_rule(r, {"x": 5})["passed"] is True
        assert _evaluate_single_rule(r, {"x": 10})["passed"] is False

    def test_gt(self):
        r = {"field": "x", "operator": "gt", "value": 5}
        assert _evaluate_single_rule(r, {"x": 10})["passed"] is True
        assert _evaluate_single_rule(r, {"x": 3})["passed"] is False

    def test_gte(self):
        r = {"field": "x", "operator": "gte", "value": 5}
        assert _evaluate_single_rule(r, {"x": 5})["passed"] is True
        assert _evaluate_single_rule(r, {"x": 4})["passed"] is False

    def test_lt(self):
        r = {"field": "x", "operator": "lt", "value": 10}
        assert _evaluate_single_rule(r, {"x": 5})["passed"] is True
        assert _evaluate_single_rule(r, {"x": 15})["passed"] is False

    def test_lte(self):
        r = {"field": "x", "operator": "lte", "value": 10}
        assert _evaluate_single_rule(r, {"x": 10})["passed"] is True
        assert _evaluate_single_rule(r, {"x": 11})["passed"] is False

    def test_in(self):
        r = {"field": "color", "operator": "in", "value": ["red", "blue"]}
        assert _evaluate_single_rule(r, {"color": "red"})["passed"] is True
        assert _evaluate_single_rule(r, {"color": "green"})["passed"] is False

    def test_not_in(self):
        r = {"field": "color", "operator": "not_in", "value": ["red", "blue"]}
        assert _evaluate_single_rule(r, {"color": "green"})["passed"] is True
        assert _evaluate_single_rule(r, {"color": "red"})["passed"] is False

    def test_contains(self):
        r = {"field": "text", "operator": "contains", "value": "hello"}
        assert _evaluate_single_rule(r, {"text": "say hello world"})["passed"] is True
        assert _evaluate_single_rule(r, {"text": "goodbye"})["passed"] is False

    def test_not_contains(self):
        r = {"field": "text", "operator": "not_contains", "value": "bad"}
        assert _evaluate_single_rule(r, {"text": "good"})["passed"] is True
        assert _evaluate_single_rule(r, {"text": "bad actor"})["passed"] is False

    def test_exists(self):
        r = {"field": "x", "operator": "exists", "value": True}
        assert _evaluate_single_rule(r, {"x": 42})["passed"] is True
        assert _evaluate_single_rule(r, {"y": 42})["passed"] is False

    def test_not_exists(self):
        r = {"field": "x", "operator": "not_exists", "value": True}
        assert _evaluate_single_rule(r, {"y": 42})["passed"] is True
        assert _evaluate_single_rule(r, {"x": 42})["passed"] is False

    def test_regex(self):
        r = {"field": "email", "operator": "regex", "value": r"^[\w.]+@[\w]+\.[\w]+$"}
        assert _evaluate_single_rule(r, {"email": "test@example.com"})["passed"] is True
        assert _evaluate_single_rule(r, {"email": "not-an-email"})["passed"] is False

    def test_regex_invalid_pattern(self):
        r = {"field": "x", "operator": "regex", "value": "[invalid"}
        result = _evaluate_single_rule(r, {"x": "anything"})
        assert result["passed"] is False
        assert "Invalid regex" in result["message"]

    def test_unknown_operator(self):
        r = {"field": "x", "operator": "bogus", "value": 1}
        result = _evaluate_single_rule(r, {"x": 1})
        assert result["passed"] is False
        assert "Unknown operator" in result["message"]

    def test_type_mismatch_handled(self):
        r = {"field": "x", "operator": "gt", "value": 10}
        result = _evaluate_single_rule(r, {"x": "not_a_number"})
        assert result["passed"] is False

    def test_custom_message_in_violation(self):
        r = {"field": "x", "operator": "eq", "value": 1, "message": "X must be 1!"}
        result = _evaluate_single_rule(r, {"x": 2})
        assert result["passed"] is False
        assert result["message"] == "X must be 1!"


# ---------------------------------------------------------------------------
# Test: check_compliance
# ---------------------------------------------------------------------------

class TestCheckCompliance:
    def test_compliant_scope(self, engine):
        rules = [{"field": "status", "operator": "eq", "value": "ok"}]
        engine.create_policy("p1", "P1", rules=rules, scope="security")
        result = engine.check_compliance("security", {"status": "ok"})
        assert result["compliant"] is True
        assert result["total_policies"] == 1
        assert result["violations_count"] == 0

    def test_non_compliant_scope(self, engine):
        rules = [{"field": "status", "operator": "eq", "value": "ok"}]
        engine.create_policy("p1", "P1", rules=rules, scope="security")
        result = engine.check_compliance("security", {"status": "error"})
        assert result["compliant"] is False
        assert result["violations_count"] == 1

    def test_empty_scope_compliant(self, engine):
        result = engine.check_compliance("nonexistent", {})
        assert result["compliant"] is True
        assert result["total_policies"] == 0

    def test_only_checks_active_policies(self, engine):
        rules = [{"field": "x", "operator": "eq", "value": 1}]
        engine.create_policy("p-active", "Active", rules=rules, scope="scope1")
        engine.create_policy("p-inactive", "Inactive", rules=rules, scope="scope1")
        engine.deactivate_policy("p-inactive")
        result = engine.check_compliance("scope1", {"x": 99})
        assert result["total_policies"] == 1

    def test_multiple_policies_in_scope(self, engine):
        engine.create_policy("pa", "A", rules=[{"field": "a", "operator": "eq", "value": 1}], scope="sc")
        engine.create_policy("pb", "B", rules=[{"field": "b", "operator": "eq", "value": 2}], scope="sc")
        engine.create_policy("pc", "C", rules=[{"field": "c", "operator": "eq", "value": 3}], scope="sc")
        result = engine.check_compliance("sc", {"a": 1, "b": 2, "c": 3})
        assert result["compliant"] is True
        assert result["total_policies"] == 3

    def test_different_scopes_isolated(self, engine):
        engine.create_policy("ps1", "S1", rules=[{"field": "x", "operator": "eq", "value": 1}], scope="scope_a")
        engine.create_policy("ps2", "S2", rules=[{"field": "x", "operator": "eq", "value": 2}], scope="scope_b")
        result_a = engine.check_compliance("scope_a", {"x": 1})
        result_b = engine.check_compliance("scope_b", {"x": 1})
        assert result_a["compliant"] is True
        assert result_b["compliant"] is False


# ---------------------------------------------------------------------------
# Test: list_policies
# ---------------------------------------------------------------------------

class TestListPolicies:
    def test_lists_all_policies(self, engine):
        engine.create_policy("p1", "First", scope="s1")
        engine.create_policy("p2", "Second", scope="s2")
        result = engine.list_policies()
        assert len(result) == 2

    def test_filters_by_scope(self, engine):
        engine.create_policy("p1", "First", scope="security")
        engine.create_policy("p2", "Second", scope="quality")
        result = engine.list_policies(scope="security")
        assert len(result) == 1
        assert result[0]["policy_id"] == "p1"

    def test_active_only_filter(self, engine):
        engine.create_policy("p1", "Active", scope="s1")
        engine.create_policy("p2", "WillBeInactive", scope="s1")
        engine.deactivate_policy("p2")
        result = engine.list_policies(active_only=True)
        assert len(result) == 1
        assert result[0]["policy_id"] == "p1"

    def test_combined_scope_and_active(self, engine):
        engine.create_policy("pa", "A", scope="sc1")
        engine.create_policy("pb", "B", scope="sc1")
        engine.create_policy("pc", "C", scope="sc2")
        engine.deactivate_policy("pb")
        result = engine.list_policies(scope="sc1", active_only=True)
        assert len(result) == 1
        assert result[0]["policy_id"] == "pa"

    def test_empty_result(self, engine):
        result = engine.list_policies()
        assert result == []

    def test_nonexistent_scope_returns_empty(self, engine):
        engine.create_policy("p1", "P1", scope="real")
        result = engine.list_policies(scope="fake")
        assert result == []


# ---------------------------------------------------------------------------
# Test: get_policy_history
# ---------------------------------------------------------------------------

class TestGetPolicyHistory:
    def test_empty_history_on_new_policy(self, engine):
        engine.create_policy("p1", "P1")
        history = engine.get_policy_history("p1")
        assert history == []

    def test_history_records_updates(self, engine):
        engine.create_policy("p1", "P1", rules=[{"field": "x", "operator": "eq", "value": 1}])
        engine.update_policy("p1", rules=[], changelog="Cleared rules")
        history = engine.get_policy_history("p1")
        assert len(history) == 1
        assert history[0]["action"] == "update"

    def test_history_ordering_ascending(self, engine):
        engine.create_policy("p1", "P1")
        engine.update_policy("p1", rules=[], changelog="First update")
        engine.update_policy("p1", rules=[{"field": "a", "operator": "eq", "value": 1}], changelog="Second update")
        history = engine.get_policy_history("p1")
        assert len(history) == 2
        assert history[0]["changelog"] == "First update"
        assert history[1]["changelog"] == "Second update"

    def test_history_includes_rule_snapshots(self, engine):
        original_rules = [{"field": "x", "operator": "eq", "value": 1}]
        engine.create_policy("p1", "P1", rules=original_rules)
        new_rules = [{"field": "y", "operator": "gt", "value": 5}]
        engine.update_policy("p1", rules=new_rules, changelog="Changed")
        history = engine.get_policy_history("p1")
        assert history[0]["old_rules"] == original_rules
        assert history[0]["new_rules"] == new_rules

    def test_history_for_nonexistent_policy(self, engine):
        history = engine.get_policy_history("ghost")
        assert history == []


# ---------------------------------------------------------------------------
# Test: get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty_stats(self, engine):
        stats = engine.get_stats()
        assert stats["total"] == 0
        assert stats["active"] == 0
        assert stats["inactive"] == 0
        assert stats["compliance_rate"] == 100.0

    def test_counts_policies(self, engine):
        engine.create_policy("p1", "P1", scope="s1")
        engine.create_policy("p2", "P2", scope="s2")
        engine.create_policy("p3", "P3", scope="s1")
        stats = engine.get_stats()
        assert stats["total"] == 3
        assert stats["active"] == 3
        assert stats["inactive"] == 0

    def test_counts_inactive(self, engine):
        engine.create_policy("p1", "P1")
        engine.create_policy("p2", "P2")
        engine.deactivate_policy("p2")
        stats = engine.get_stats()
        assert stats["active"] == 1
        assert stats["inactive"] == 1

    def test_by_scope_breakdown(self, engine):
        engine.create_policy("p1", "P1", scope="security")
        engine.create_policy("p2", "P2", scope="quality")
        engine.create_policy("p3", "P3", scope="security")
        stats = engine.get_stats()
        assert stats["by_scope"]["security"] == 2
        assert stats["by_scope"]["quality"] == 1

    def test_compliance_rate(self, engine):
        engine.create_policy("p1", "P1")
        engine.create_policy("p2", "P2")
        engine.deactivate_policy("p1")
        stats = engine.get_stats()
        assert stats["compliance_rate"] == 50.0


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_create_emits_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        events = []
        bus.subscribe("policy_engine.created", lambda e: events.append(e))
        engine.create_policy("p1", "Test")
        assert len(events) == 1
        assert events[0].payload["policy_id"] == "p1"

    def test_update_emits_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        events = []
        bus.subscribe("policy_engine.updated", lambda e: events.append(e))
        engine.create_policy("p1", "Test")
        engine.update_policy("p1", rules=[], changelog="changed")
        assert len(events) == 1
        assert events[0].payload["version"] == 2

    def test_activate_emits_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        events = []
        bus.subscribe("policy_engine.activated", lambda e: events.append(e))
        engine.create_policy("p1", "Test")
        engine.deactivate_policy("p1")
        engine.activate_policy("p1")
        assert len(events) == 1
        assert events[0].payload["policy_id"] == "p1"

    def test_deactivate_emits_event(self, engine_with_bus):
        engine, bus = engine_with_bus
        events = []
        bus.subscribe("policy_engine.deactivated", lambda e: events.append(e))
        engine.create_policy("p1", "Test")
        engine.deactivate_policy("p1")
        assert len(events) == 1

    def test_no_event_without_bus(self, engine):
        # Should not raise -- _emit gracefully handles None event_bus
        engine.create_policy("p1", "No Bus")
        engine.update_policy("p1", rules=[], changelog="safe")


# ---------------------------------------------------------------------------
# Test: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_creates(self, engine):
        errors = []

        def create(idx):
            try:
                engine.create_policy(f"concurrent-{idx}", f"Policy {idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(engine.list_policies()) == 20

    def test_concurrent_read_write(self, engine):
        engine.create_policy("rw-base", "Base", rules=[{"field": "x", "operator": "eq", "value": 1}])
        errors = []

        def reader():
            try:
                for _ in range(50):
                    engine.evaluate_policy("rw-base", {"x": 1})
                    engine.list_policies()
                    engine.get_stats()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    engine.update_policy("rw-base", rules=[{"field": "x", "operator": "eq", "value": i}],
                                         changelog=f"Update {i}")
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
    def test_get_policy_engine_returns_same_instance(self):
        # Reset global singleton
        import sylion.governance.policy_engine as mod
        mod._engine = None
        e1 = get_policy_engine(db_path=":memory:")
        e2 = get_policy_engine()
        assert e1 is e2
        mod._engine = None  # cleanup


# ---------------------------------------------------------------------------
# Test: _evaluate_rules helper
# ---------------------------------------------------------------------------

class TestEvaluateRulesHelper:
    def test_all_pass(self):
        rules = [
            {"field": "a", "operator": "eq", "value": 1},
            {"field": "b", "operator": "gt", "value": 0},
        ]
        results = _evaluate_rules(rules, {"a": 1, "b": 5})
        assert all(r["passed"] for r in results)

    def test_all_fail(self):
        rules = [
            {"field": "a", "operator": "eq", "value": 1},
            {"field": "b", "operator": "gt", "value": 100},
        ]
        results = _evaluate_rules(rules, {"a": 0, "b": 1})
        assert not any(r["passed"] for r in results)

    def test_empty_rules(self):
        results = _evaluate_rules([], {"x": 1})
        assert results == []
