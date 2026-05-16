"""Tests for SYLION Governance -- Decision Boundaries Manager.

Covers: CRUD, rule evaluation, evaluation history, EventBus integration,
thread safety, validation, and singleton management.
"""
import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.decision_boundaries import (
    VALID_SCOPES,
    DecisionBoundariesManager,
    get_decision_boundaries_manager,
    reset_decision_boundaries_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr():
    """Fresh DecisionBoundariesManager with :memory: SQLite."""
    return DecisionBoundariesManager(db_path=":memory:")


@pytest.fixture
def mgr_with_bus():
    """DecisionBoundariesManager connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return DecisionBoundariesManager(db_path=":memory:", event_bus=bus), bus


# ---------------------------------------------------------------------------
# Test: create_boundary
# ---------------------------------------------------------------------------

class TestCreateBoundary:
    def test_creates_with_basic_params(self, mgr):
        result = mgr.create_boundary("max-risk", "global")
        assert "boundary_id" in result
        assert result["name"] == "max-risk"
        assert result["scope"] == "global"
        assert result["is_active"] is True
        assert result["rules"] == []

    def test_creates_with_rules_list(self, mgr):
        rules = [{"field": "risk_score", "operator": "lt", "value": 0.8}]
        result = mgr.create_boundary("risk-limit", "pipeline", rules)
        assert result["rules"] == rules

    def test_creates_with_rules_json_string(self, mgr):
        rules_json = json.dumps([{"field": "x", "operator": "eq", "value": 1}])
        result = mgr.create_boundary("json-b", "module", rules_json)
        assert len(result["rules"]) == 1

    def test_default_rules_empty(self, mgr):
        result = mgr.create_boundary("empty-rules", "decision")
        assert result["rules"] == []

    def test_rejects_empty_name(self, mgr):
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.create_boundary("", "global")

    def test_rejects_whitespace_name(self, mgr):
        with pytest.raises(ValueError, match="must not be empty"):
            mgr.create_boundary("   ", "global")

    def test_rejects_invalid_scope(self, mgr):
        with pytest.raises(ValueError, match="Invalid scope"):
            mgr.create_boundary("test", "invalid_scope")

    def test_all_valid_scopes(self, mgr):
        for scope in VALID_SCOPES:
            result = mgr.create_boundary(f"b-{scope}", scope)
            assert result["scope"] == scope

    def test_boundary_id_is_unique(self, mgr):
        r1 = mgr.create_boundary("b1", "global")
        r2 = mgr.create_boundary("b2", "global")
        assert r1["boundary_id"] != r2["boundary_id"]

    def test_timestamps_set(self, mgr):
        before = time.time()
        result = mgr.create_boundary("ts-b", "global")
        after = time.time()
        assert before <= result["created_at"] <= after
        assert result["created_at"] == result["updated_at"]


# ---------------------------------------------------------------------------
# Test: update_boundary
# ---------------------------------------------------------------------------

class TestUpdateBoundary:
    def test_updates_name(self, mgr):
        b = mgr.create_boundary("old-name", "global")
        updated = mgr.update_boundary(b["boundary_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_updates_scope(self, mgr):
        b = mgr.create_boundary("scope-test", "global")
        updated = mgr.update_boundary(b["boundary_id"], scope="pipeline")
        assert updated["scope"] == "pipeline"

    def test_updates_rules(self, mgr):
        b = mgr.create_boundary("rules-test", "global")
        new_rules = [{"field": "x", "operator": "gt", "value": 5}]
        updated = mgr.update_boundary(b["boundary_id"], rules_json=new_rules)
        assert updated["rules"] == new_rules

    def test_updates_is_active(self, mgr):
        b = mgr.create_boundary("active-test", "global")
        updated = mgr.update_boundary(b["boundary_id"], is_active=False)
        assert updated["is_active"] is False

    def test_returns_none_for_missing(self, mgr):
        result = mgr.update_boundary("nonexistent", name="x")
        assert result is None

    def test_rejects_invalid_scope(self, mgr):
        b = mgr.create_boundary("inv-scope", "global")
        with pytest.raises(ValueError, match="Invalid scope"):
            mgr.update_boundary(b["boundary_id"], scope="bad")

    def test_preserves_existing_on_partial_update(self, mgr):
        rules = [{"field": "a", "operator": "eq", "value": 1}]
        b = mgr.create_boundary("partial", "global", rules)
        updated = mgr.update_boundary(b["boundary_id"], name="renamed")
        assert updated["name"] == "renamed"
        assert updated["rules"] == rules
        assert updated["scope"] == "global"

    def test_updated_at_changes(self, mgr):
        b = mgr.create_boundary("ts-update", "global")
        time.sleep(0.01)
        updated = mgr.update_boundary(b["boundary_id"], name="changed")
        assert updated["updated_at"] > b["created_at"]


# ---------------------------------------------------------------------------
# Test: delete_boundary
# ---------------------------------------------------------------------------

class TestDeleteBoundary:
    def test_deletes_existing(self, mgr):
        b = mgr.create_boundary("del-me", "global")
        assert mgr.delete_boundary(b["boundary_id"]) is True

    def test_returns_false_for_missing(self, mgr):
        assert mgr.delete_boundary("nonexistent") is False

    def test_get_returns_none_after_delete(self, mgr):
        b = mgr.create_boundary("del-get", "global")
        mgr.delete_boundary(b["boundary_id"])
        assert mgr.get_boundary(b["boundary_id"]) is None

    def test_deletes_related_evaluations(self, mgr):
        b = mgr.create_boundary("del-eval", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        mgr.evaluate_boundary(b["boundary_id"], {"x": 1})
        mgr.delete_boundary(b["boundary_id"])
        history = mgr.get_evaluation_history(b["boundary_id"])
        assert history == []


# ---------------------------------------------------------------------------
# Test: get_boundary
# ---------------------------------------------------------------------------

class TestGetBoundary:
    def test_returns_created_boundary(self, mgr):
        rules = [{"field": "a", "operator": "eq", "value": 1}]
        b = mgr.create_boundary("get-test", "module", rules)
        fetched = mgr.get_boundary(b["boundary_id"])
        assert fetched is not None
        assert fetched["name"] == "get-test"
        assert fetched["rules_json"] == rules

    def test_returns_none_for_missing(self, mgr):
        assert mgr.get_boundary("nonexistent") is None

    def test_is_active_deserialized(self, mgr):
        b = mgr.create_boundary("active-ser", "global")
        fetched = mgr.get_boundary(b["boundary_id"])
        assert fetched["is_active"] is True


# ---------------------------------------------------------------------------
# Test: list_boundaries
# ---------------------------------------------------------------------------

class TestListBoundaries:
    def test_lists_all(self, mgr):
        mgr.create_boundary("b1", "global")
        mgr.create_boundary("b2", "module")
        assert len(mgr.list_boundaries()) == 2

    def test_filter_by_scope(self, mgr):
        mgr.create_boundary("s1", "global")
        mgr.create_boundary("s2", "module")
        result = mgr.list_boundaries(scope="global")
        assert len(result) == 1
        assert result[0]["scope"] == "global"

    def test_active_only(self, mgr):
        b1 = mgr.create_boundary("a1", "global")
        mgr.create_boundary("a2", "global")
        mgr.update_boundary(b1["boundary_id"], is_active=False)
        result = mgr.list_boundaries(active_only=True)
        assert len(result) == 1
        assert result[0]["name"] == "a2"

    def test_empty_list(self, mgr):
        assert mgr.list_boundaries() == []


# ---------------------------------------------------------------------------
# Test: evaluate_boundary
# ---------------------------------------------------------------------------

class TestEvaluateBoundary:
    def test_passes_when_all_rules_met(self, mgr):
        rules = [{"field": "risk", "operator": "lt", "value": 0.8}]
        b = mgr.create_boundary("pass-test", "global", rules)
        result = mgr.evaluate_boundary(b["boundary_id"], {"risk": 0.5})
        assert result["passed"] is True
        assert result["violations"] == []

    def test_fails_when_rule_violated(self, mgr):
        rules = [{"field": "risk", "operator": "lt", "value": 0.8}]
        b = mgr.create_boundary("fail-test", "global", rules)
        result = mgr.evaluate_boundary(b["boundary_id"], {"risk": 0.9})
        assert result["passed"] is False
        assert len(result["violations"]) == 1

    def test_eq_operator(self, mgr):
        b = mgr.create_boundary("eq", "global",
                                [{"field": "status", "operator": "eq", "value": "ok"}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"status": "ok"})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"status": "bad"})["passed"] is False

    def test_neq_operator(self, mgr):
        b = mgr.create_boundary("neq", "global",
                                [{"field": "x", "operator": "neq", "value": "bad"}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"x": "good"})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"x": "bad"})["passed"] is False

    def test_gt_operator(self, mgr):
        b = mgr.create_boundary("gt", "global",
                                [{"field": "score", "operator": "gt", "value": 5}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"score": 10})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"score": 3})["passed"] is False
        assert mgr.evaluate_boundary(b["boundary_id"], {"score": 5})["passed"] is False

    def test_lt_operator(self, mgr):
        b = mgr.create_boundary("lt", "global",
                                [{"field": "risk", "operator": "lt", "value": 0.8}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"risk": 0.5})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"risk": 0.8})["passed"] is False

    def test_gte_operator(self, mgr):
        b = mgr.create_boundary("gte", "global",
                                [{"field": "conf", "operator": "gte", "value": 0.5}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"conf": 0.5})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"conf": 0.3})["passed"] is False

    def test_lte_operator(self, mgr):
        b = mgr.create_boundary("lte", "global",
                                [{"field": "count", "operator": "lte", "value": 10}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"count": 10})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"count": 11})["passed"] is False

    def test_in_operator(self, mgr):
        b = mgr.create_boundary("in", "global",
                                [{"field": "env", "operator": "in", "value": ["prod", "staging"]}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"env": "prod"})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"env": "dev"})["passed"] is False

    def test_not_in_operator(self, mgr):
        b = mgr.create_boundary("not_in", "global",
                                [{"field": "env", "operator": "not_in", "value": ["dev", "test"]}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"env": "prod"})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"env": "dev"})["passed"] is False

    def test_contains_operator(self, mgr):
        b = mgr.create_boundary("contains", "global",
                                [{"field": "tags", "operator": "contains", "value": "safe"}])
        assert mgr.evaluate_boundary(b["boundary_id"], {"tags": ["safe", "fast"]})["passed"] is True
        assert mgr.evaluate_boundary(b["boundary_id"], {"tags": ["fast"]})["passed"] is False

    def test_missing_field_violates(self, mgr):
        b = mgr.create_boundary("missing", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        result = mgr.evaluate_boundary(b["boundary_id"], {})
        assert result["passed"] is False

    def test_unknown_operator_violates(self, mgr):
        b = mgr.create_boundary("unk-op", "global",
                                [{"field": "x", "operator": "unknown", "value": 1}])
        result = mgr.evaluate_boundary(b["boundary_id"], {"x": 1})
        assert result["passed"] is False

    def test_multiple_rules_all_pass(self, mgr):
        rules = [
            {"field": "a", "operator": "gt", "value": 0},
            {"field": "b", "operator": "lt", "value": 10},
        ]
        b = mgr.create_boundary("multi-pass", "global", rules)
        result = mgr.evaluate_boundary(b["boundary_id"], {"a": 5, "b": 5})
        assert result["passed"] is True

    def test_multiple_rules_one_fails(self, mgr):
        rules = [
            {"field": "a", "operator": "gt", "value": 0},
            {"field": "b", "operator": "lt", "value": 10},
        ]
        b = mgr.create_boundary("multi-fail", "global", rules)
        result = mgr.evaluate_boundary(b["boundary_id"], {"a": 5, "b": 15})
        assert result["passed"] is False
        assert len(result["violations"]) == 1

    def test_raises_for_missing_boundary(self, mgr):
        with pytest.raises(ValueError, match="not found"):
            mgr.evaluate_boundary("nonexistent", {})

    def test_empty_rules_always_pass(self, mgr):
        b = mgr.create_boundary("no-rules", "global")
        result = mgr.evaluate_boundary(b["boundary_id"], {"anything": 1})
        assert result["passed"] is True

    def test_violation_details(self, mgr):
        rules = [{"field": "risk", "operator": "lt", "value": 0.8}]
        b = mgr.create_boundary("detail", "global", rules)
        result = mgr.evaluate_boundary(b["boundary_id"], {"risk": 0.9})
        v = result["violations"][0]
        assert v["field"] == "risk"
        assert v["operator"] == "lt"
        assert v["expected"] == 0.8
        assert v["actual"] == 0.9


# ---------------------------------------------------------------------------
# Test: get_evaluation_history
# ---------------------------------------------------------------------------

class TestGetEvaluationHistory:
    def test_returns_history(self, mgr):
        b = mgr.create_boundary("hist", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        mgr.evaluate_boundary(b["boundary_id"], {"x": 1})
        mgr.evaluate_boundary(b["boundary_id"], {"x": 2})
        history = mgr.get_evaluation_history(b["boundary_id"])
        assert len(history) == 2

    def test_newest_first(self, mgr):
        b = mgr.create_boundary("hist-ord", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        mgr.evaluate_boundary(b["boundary_id"], {"x": 1})
        time.sleep(0.01)
        mgr.evaluate_boundary(b["boundary_id"], {"x": 2})
        history = mgr.get_evaluation_history(b["boundary_id"])
        assert history[0]["passed"] is False
        assert history[1]["passed"] is True

    def test_empty_for_no_evaluations(self, mgr):
        b = mgr.create_boundary("no-eval", "global")
        assert mgr.get_evaluation_history(b["boundary_id"]) == []

    def test_respects_limit(self, mgr):
        b = mgr.create_boundary("lim", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        for i in range(10):
            mgr.evaluate_boundary(b["boundary_id"], {"x": i % 2})
        history = mgr.get_evaluation_history(b["boundary_id"], limit=3)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_boundary_created_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("boundary_created", lambda e: events.append(e))
        mgr.create_boundary("ev-create", "global")
        assert len(events) == 1
        assert events[0].payload["name"] == "ev-create"

    def test_boundary_updated_event(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("boundary_updated", lambda e: events.append(e))
        b = mgr.create_boundary("ev-update", "global")
        mgr.update_boundary(b["boundary_id"], name="renamed")
        assert len(events) == 1

    def test_boundary_evaluated_event_on_pass(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("boundary_evaluated", lambda e: events.append(e))
        b = mgr.create_boundary("ev-pass", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        mgr.evaluate_boundary(b["boundary_id"], {"x": 1})
        assert len(events) == 1
        assert events[0].payload["passed"] is True

    def test_boundary_violated_event_on_fail(self, mgr_with_bus):
        mgr, bus = mgr_with_bus
        events = []
        bus.subscribe("boundary_violated", lambda e: events.append(e))
        b = mgr.create_boundary("ev-fail", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        mgr.evaluate_boundary(b["boundary_id"], {"x": 2})
        assert len(events) == 1
        assert events[0].payload["passed"] is False

    def test_no_event_without_bus(self, mgr):
        # Should not raise
        mgr.create_boundary("no-bus", "global")
        b = mgr.create_boundary("no-bus2", "global",
                                [{"field": "x", "operator": "eq", "value": 1}])
        mgr.evaluate_boundary(b["boundary_id"], {"x": 2})


# ---------------------------------------------------------------------------
# Test: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_creates(self, mgr):
        errors = []

        def create(i):
            try:
                mgr.create_boundary(f"concurrent-{i}", "global")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(mgr.list_boundaries()) == 20

    def test_concurrent_evaluates(self, mgr):
        b = mgr.create_boundary("conc-eval", "global",
                                [{"field": "x", "operator": "lt", "value": 100}])
        errors = []

        def evaluate(i):
            try:
                mgr.evaluate_boundary(b["boundary_id"], {"x": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=evaluate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(mgr.get_evaluation_history(b["boundary_id"])) == 20

    def test_concurrent_read_write(self, mgr):
        b = mgr.create_boundary("rw", "global")
        errors = []

        def reader():
            try:
                for _ in range(50):
                    mgr.get_boundary(b["boundary_id"])
                    mgr.list_boundaries()
                    mgr.get_evaluation_history(b["boundary_id"])
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    mgr.evaluate_boundary(b["boundary_id"], {"x": i})
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
# Test: singleton management
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        reset_decision_boundaries_manager()
        s1 = get_decision_boundaries_manager(db_path=":memory:")
        s2 = get_decision_boundaries_manager()
        assert s1 is s2
        reset_decision_boundaries_manager()

    def test_reset_clears_singleton(self):
        s1 = get_decision_boundaries_manager(db_path=":memory:")
        reset_decision_boundaries_manager()
        s2 = get_decision_boundaries_manager(db_path=":memory:")
        assert s1 is not s2
        reset_decision_boundaries_manager()
