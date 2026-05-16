"""
tests/test_policy_evaluator.py -- Policy Evaluator tests

Covers:
- Policy CRUD (create, update, delete, get, list)
- Policy evaluation (pass/fail, context matching)
- Exception management (grant, list)
- Statistics aggregation
- EventBus integration
- Thread safety (concurrent operations)
- Singleton get/reset
- Validation errors
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.policy_evaluator import (
    VALID_POLICY_STATUSES,
    VALID_SCOPES,
    PolicyEvaluator,
    get_policy_evaluator,
    reset_policy_evaluator,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def evaluator(bus):
    return PolicyEvaluator(event_bus=bus)


@pytest.fixture(autouse=True)
def _reset_singleton():
    yield
    reset_policy_evaluator()


# =====================================================================
# Constants
# =====================================================================

class TestConstants:

    def test_valid_scopes(self):
        assert "global" in VALID_SCOPES
        assert "module" in VALID_SCOPES
        assert "pipeline" in VALID_SCOPES

    def test_valid_policy_statuses(self):
        assert "active" in VALID_POLICY_STATUSES
        assert "disabled" in VALID_POLICY_STATUSES
        assert "archived" in VALID_POLICY_STATUSES


# =====================================================================
# Policy CRUD
# =====================================================================

class TestCreatePolicy:

    def test_create_basic(self, evaluator):
        result = evaluator.create_policy(name="Max tokens", scope="global")
        assert result["policy_id"]
        assert result["name"] == "Max tokens"
        assert result["scope"] == "global"
        assert result["status"] == "active"
        assert result["priority"] == 50
        assert result["rules"] == {}
        assert result["created_at"] > 0

    def test_create_with_rules(self, evaluator):
        rules = '{"max_tokens": 4096}'
        result = evaluator.create_policy(
            name="Token limit", scope="pipeline",
            rules_json=rules, priority=90,
        )
        assert result["rules"] == {"max_tokens": 4096}
        assert result["scope"] == "pipeline"
        assert result["priority"] == 90

    @pytest.mark.parametrize("scope", VALID_SCOPES)
    def test_create_all_scopes(self, evaluator, scope):
        result = evaluator.create_policy(name=f"Pol-{scope}", scope=scope)
        assert result["scope"] == scope

    def test_create_invalid_scope(self, evaluator):
        with pytest.raises(ValueError, match="Invalid scope"):
            evaluator.create_policy(name="Bad", scope="invalid")

    def test_create_default_scope_is_global(self, evaluator):
        result = evaluator.create_policy(name="Default")
        assert result["scope"] == "global"

    def test_create_default_priority_is_50(self, evaluator):
        result = evaluator.create_policy(name="Prio")
        assert result["priority"] == 50

    def test_create_unique_ids(self, evaluator):
        r1 = evaluator.create_policy(name="A")
        r2 = evaluator.create_policy(name="B")
        assert r1["policy_id"] != r2["policy_id"]


class TestGetPolicy:

    def test_get_existing(self, evaluator):
        created = evaluator.create_policy(name="Get test")
        result = evaluator.get_policy(created["policy_id"])
        assert result is not None
        assert result["policy_id"] == created["policy_id"]
        assert result["name"] == "Get test"

    def test_get_nonexistent(self, evaluator):
        assert evaluator.get_policy("nonexistent") is None

    def test_get_returns_rules_parsed(self, evaluator):
        created = evaluator.create_policy(
            name="Rules", rules_json='{"key": "value"}',
        )
        result = evaluator.get_policy(created["policy_id"])
        assert result["rules"] == {"key": "value"}


class TestUpdatePolicy:

    def test_update_name(self, evaluator):
        created = evaluator.create_policy(name="Old")
        result = evaluator.update_policy(created["policy_id"], name="New")
        assert result["name"] == "New"

    def test_update_scope(self, evaluator):
        created = evaluator.create_policy(name="S")
        result = evaluator.update_policy(created["policy_id"], scope="module")
        assert result["scope"] == "module"

    def test_update_priority(self, evaluator):
        created = evaluator.create_policy(name="P")
        result = evaluator.update_policy(created["policy_id"], priority=99)
        assert result["priority"] == 99

    def test_update_status(self, evaluator):
        created = evaluator.create_policy(name="St")
        result = evaluator.update_policy(created["policy_id"], status="disabled")
        assert result["status"] == "disabled"

    def test_update_invalid_scope(self, evaluator):
        created = evaluator.create_policy(name="Bad scope")
        with pytest.raises(ValueError, match="Invalid scope"):
            evaluator.update_policy(created["policy_id"], scope="bad")

    def test_update_invalid_status(self, evaluator):
        created = evaluator.create_policy(name="Bad status")
        with pytest.raises(ValueError, match="Invalid status"):
            evaluator.update_policy(created["policy_id"], status="unknown")

    def test_update_nonexistent(self, evaluator):
        result = evaluator.update_policy("nonexistent", name="X")
        assert result is None

    def test_update_no_args_returns_existing(self, evaluator):
        created = evaluator.create_policy(name="No change")
        result = evaluator.update_policy(created["policy_id"])
        assert result["name"] == "No change"

    def test_update_updates_timestamp(self, evaluator):
        created = evaluator.create_policy(name="TS")
        original = created["updated_at"]
        time.sleep(0.01)
        result = evaluator.update_policy(created["policy_id"], name="TS2")
        assert result["updated_at"] >= original


class TestDeletePolicy:

    def test_delete_existing(self, evaluator):
        created = evaluator.create_policy(name="Del")
        assert evaluator.delete_policy(created["policy_id"]) is True
        assert evaluator.get_policy(created["policy_id"]) is None

    def test_delete_nonexistent(self, evaluator):
        assert evaluator.delete_policy("nonexistent") is False

    def test_delete_removes_evaluations_and_exceptions(self, evaluator):
        created = evaluator.create_policy(
            name="Cascade", rules_json='{"a": 1}',
        )
        pid = created["policy_id"]
        evaluator.evaluate(pid, '{"a": 1}')
        evaluator.grant_exception(pid, "target-1", "reason")
        evaluator.delete_policy(pid)
        assert evaluator.list_exceptions(policy_id=pid) == []


class TestListPolicies:

    def test_list_empty(self, evaluator):
        assert evaluator.list_policies() == []

    def test_list_all(self, evaluator):
        evaluator.create_policy(name="A")
        evaluator.create_policy(name="B")
        result = evaluator.list_policies()
        assert len(result) == 2

    def test_list_filter_by_scope(self, evaluator):
        evaluator.create_policy(name="A", scope="global")
        evaluator.create_policy(name="B", scope="module")
        result = evaluator.list_policies(scope="module")
        assert len(result) == 1
        assert result[0]["scope"] == "module"

    def test_list_active_only(self, evaluator):
        r1 = evaluator.create_policy(name="Active")
        evaluator.create_policy(name="Inactive")
        evaluator.update_policy(r1["policy_id"], status="disabled")
        result = evaluator.list_policies(active_only=True)
        assert len(result) == 1
        assert result[0]["status"] == "active"

    def test_list_ordered_by_priority_desc(self, evaluator):
        evaluator.create_policy(name="Low", priority=10)
        evaluator.create_policy(name="High", priority=90)
        result = evaluator.list_policies()
        assert result[0]["name"] == "High"
        assert result[1]["name"] == "Low"


# =====================================================================
# Evaluation
# =====================================================================

class TestEvaluate:

    def test_evaluate_pass(self, evaluator):
        created = evaluator.create_policy(
            name="Pass", rules_json='{"role": "admin"}',
        )
        result = evaluator.evaluate(created["policy_id"], '{"role": "admin"}')
        assert result["result"] == "pass"
        assert result["details"] == {}
        assert result["evaluation_id"]

    def test_evaluate_fail(self, evaluator):
        created = evaluator.create_policy(
            name="Fail", rules_json='{"role": "admin"}',
        )
        result = evaluator.evaluate(created["policy_id"], '{"role": "user"}')
        assert result["result"] == "fail"
        assert "role" in result["details"]
        assert result["details"]["role"]["expected"] == "admin"
        assert result["details"]["role"]["actual"] == "user"

    def test_evaluate_empty_rules_always_pass(self, evaluator):
        created = evaluator.create_policy(name="Empty", rules_json="{}")
        result = evaluator.evaluate(created["policy_id"], '{"any": "thing"}')
        assert result["result"] == "pass"

    def test_evaluate_nonexistent_policy(self, evaluator):
        with pytest.raises(ValueError, match="Policy not found"):
            evaluator.evaluate("nonexistent", "{}")

    def test_evaluate_disabled_policy(self, evaluator):
        created = evaluator.create_policy(name="Disabled")
        evaluator.update_policy(created["policy_id"], status="disabled")
        with pytest.raises(ValueError, match="not active"):
            evaluator.evaluate(created["policy_id"], "{}")

    def test_evaluate_invalid_context_json(self, evaluator):
        created = evaluator.create_policy(name="Bad ctx")
        with pytest.raises(ValueError, match="Invalid JSON"):
            evaluator.evaluate(created["policy_id"], "not json")

    def test_evaluate_multiple_rules(self, evaluator):
        created = evaluator.create_policy(
            name="Multi", rules_json='{"a": 1, "b": 2}',
        )
        # Partial match
        r1 = evaluator.evaluate(created["policy_id"], '{"a": 1, "b": 3}')
        assert r1["result"] == "fail"
        assert "b" in r1["details"]
        assert "a" not in r1["details"]

    def test_evaluate_context_missing_key(self, evaluator):
        created = evaluator.create_policy(
            name="Missing", rules_json='{"required": true}',
        )
        result = evaluator.evaluate(created["policy_id"], '{"other": true}')
        assert result["result"] == "fail"
        assert result["details"]["required"]["actual"] is None


# =====================================================================
# Exceptions
# =====================================================================

class TestExceptions:

    def test_grant_exception(self, evaluator):
        created = evaluator.create_policy(name="Exc")
        result = evaluator.grant_exception(
            created["policy_id"], "user-123", "Legacy system", 9999999.0,
        )
        assert result["exception_id"]
        assert result["policy_id"] == created["policy_id"]
        assert result["target_id"] == "user-123"
        assert result["reason"] == "Legacy system"
        assert result["expires_at"] == 9999999.0
        assert result["created_at"] > 0

    def test_grant_exception_nonexistent_policy(self, evaluator):
        with pytest.raises(ValueError, match="Policy not found"):
            evaluator.grant_exception("nonexistent", "t1", "r")

    def test_list_exceptions_all(self, evaluator):
        p = evaluator.create_policy(name="E")
        evaluator.grant_exception(p["policy_id"], "t1", "r1")
        evaluator.grant_exception(p["policy_id"], "t2", "r2")
        result = evaluator.list_exceptions()
        assert len(result) == 2

    def test_list_exceptions_by_policy(self, evaluator):
        p1 = evaluator.create_policy(name="E1")
        p2 = evaluator.create_policy(name="E2")
        evaluator.grant_exception(p1["policy_id"], "t1", "r1")
        evaluator.grant_exception(p2["policy_id"], "t2", "r2")
        result = evaluator.list_exceptions(policy_id=p1["policy_id"])
        assert len(result) == 1
        assert result[0]["target_id"] == "t1"

    def test_list_exceptions_empty(self, evaluator):
        result = evaluator.list_exceptions()
        assert result == []


# =====================================================================
# Statistics
# =====================================================================

class TestStats:

    def test_stats_empty(self, evaluator):
        stats = evaluator.get_evaluator_stats()
        assert stats["total_policies"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["total_exceptions"] == 0

    def test_stats_after_create(self, evaluator):
        evaluator.create_policy(name="A", scope="global")
        evaluator.create_policy(name="B", scope="module")
        stats = evaluator.get_evaluator_stats()
        assert stats["total_policies"] == 2
        assert stats["policies_by_scope"]["global"] == 1
        assert stats["policies_by_scope"]["module"] == 1

    def test_stats_after_evaluations(self, evaluator):
        p = evaluator.create_policy(name="S", rules_json='{"x": 1}')
        evaluator.evaluate(p["policy_id"], '{"x": 1}')
        evaluator.evaluate(p["policy_id"], '{"x": 2}')
        stats = evaluator.get_evaluator_stats()
        assert stats["total_evaluations"] == 2
        assert stats["evaluations_by_result"]["pass"] == 1
        assert stats["evaluations_by_result"]["fail"] == 1

    def test_stats_after_exceptions(self, evaluator):
        p = evaluator.create_policy(name="Ex")
        evaluator.grant_exception(p["policy_id"], "t1", "r")
        stats = evaluator.get_evaluator_stats()
        assert stats["total_exceptions"] == 1


# =====================================================================
# Events
# =====================================================================

class TestEvents:

    def test_event_policy_created(self, evaluator, bus):
        events = []
        bus.subscribe("policy_created", lambda e: events.append(e))
        evaluator.create_policy(name="Ev")
        assert len(events) == 1
        assert events[0].payload["name"] == "Ev"
        assert events[0].source_module == "governance.policy_evaluator"

    def test_event_policy_evaluated(self, evaluator, bus):
        events = []
        bus.subscribe("policy_evaluated", lambda e: events.append(e))
        p = evaluator.create_policy(name="Ev")
        evaluator.evaluate(p["policy_id"], '{}')
        assert len(events) == 1
        assert events[0].payload["result"] == "pass"

    def test_event_exception_granted(self, evaluator, bus):
        events = []
        bus.subscribe("exception_granted", lambda e: events.append(e))
        p = evaluator.create_policy(name="Ev")
        evaluator.grant_exception(p["policy_id"], "t1", "r")
        assert len(events) == 1
        assert events[0].payload["target_id"] == "t1"

    def test_no_events_without_bus(self):
        ev = PolicyEvaluator(event_bus=None)
        p = ev.create_policy(name="NoEv")
        ev.evaluate(p["policy_id"], '{}')
        ev.grant_exception(p["policy_id"], "t1", "r")


# =====================================================================
# Thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_creates(self, evaluator):
        results = []
        errors = []

        def create(idx):
            try:
                r = evaluator.create_policy(name=f"P-{idx}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        assert len(evaluator.list_policies()) == 20

    def test_concurrent_evaluations(self, evaluator):
        p = evaluator.create_policy(name="ConcEval", rules_json='{"v": 1}')
        errors = []

        def evaluate(idx):
            try:
                evaluator.evaluate(p["policy_id"], f'{{"v": {idx}}}')
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=evaluate, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = evaluator.get_evaluator_stats()
        assert stats["total_evaluations"] == 10


# =====================================================================
# Singleton
# =====================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        ev = get_policy_evaluator()
        assert isinstance(ev, PolicyEvaluator)

    def test_get_returns_same_instance(self):
        e1 = get_policy_evaluator()
        e2 = get_policy_evaluator()
        assert e1 is e2

    def test_reset_clears_singleton(self):
        e1 = get_policy_evaluator()
        reset_policy_evaluator()
        e2 = get_policy_evaluator()
        assert e1 is not e2

    def test_get_with_params(self, bus):
        ev = get_policy_evaluator(event_bus=bus)
        assert isinstance(ev, PolicyEvaluator)
