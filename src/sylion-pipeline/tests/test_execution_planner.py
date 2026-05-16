"""
Comprehensive tests for sylion.execution.execution_planner — ExecutionPlanner.
Tests: plan CRUD, step CRUD, dependencies, topological sort, execution lifecycle,
       events, progress, thread safety, edge cases.
"""
from __future__ import annotations

import threading
import time

import pytest

from sylion.execution.execution_planner import (
    ExecutionPlanner,
    get_execution_planner,
    reset_execution_planner,
    VALID_STEP_TYPES,
    VALID_PLAN_STATUSES,
    VALID_STEP_STATUSES,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _planner(bus: EventBus | None = None) -> ExecutionPlanner:
    return ExecutionPlanner(event_bus=bus)


def _make_plan(planner: ExecutionPlanner, name: str = "test-plan", **kw) -> dict:
    return planner.create_plan(name, **kw)


def _make_step(planner: ExecutionPlanner, plan_id: str, name: str = "step",
               step_type: str = "tool_call", **kw) -> dict:
    return planner.add_step(plan_id, name, step_type, **kw)


# ---------------------------------------------------------------------------
# Plan CRUD
# ---------------------------------------------------------------------------

class TestCreatePlan:

    def test_basic_create(self):
        p = _planner()
        plan = p.create_plan("my-plan")
        assert plan["plan_id"]
        assert plan["name"] == "my-plan"
        assert plan["status"] == "pending"

    def test_create_with_description(self):
        p = _planner()
        plan = p.create_plan("p", description="A test plan")
        assert plan["description"] == "A test plan"

    def test_create_with_created_by(self):
        p = _planner()
        plan = p.create_plan("p", created_by="alice")
        assert plan["created_by"] == "alice"

    def test_create_sets_timestamps(self):
        p = _planner()
        plan = p.create_plan("p")
        assert plan["created_at"] > 0
        assert plan["updated_at"] > 0

    def test_create_generates_unique_ids(self):
        p = _planner()
        p1 = p.create_plan("a")
        p2 = p.create_plan("b")
        assert p1["plan_id"] != p2["plan_id"]

    def test_create_emits_event(self):
        bus = EventBus()
        p = _planner(bus=bus)
        p.create_plan("my-plan", created_by="bob")
        events = bus.query(topic="plan.created")
        assert len(events) == 1
        assert events[0]["source_module"] == "execution.execution_planner"

    def test_create_event_payload(self):
        bus = EventBus()
        p = _planner(bus=bus)
        p.create_plan("my-plan", created_by="carol")
        events = bus.query(topic="plan.created")
        payload = events[0]
        import json
        data = json.loads(payload["payload"]) if isinstance(payload["payload"], str) else payload["payload"]
        assert data["name"] == "my-plan"
        assert data["created_by"] == "carol"


class TestGetPlan:

    def test_get_existing_plan(self):
        p = _planner()
        created = p.create_plan("test")
        fetched = p.get_plan(created["plan_id"])
        assert fetched is not None
        assert fetched["plan_id"] == created["plan_id"]
        assert fetched["name"] == "test"

    def test_get_nonexistent_plan(self):
        p = _planner()
        assert p.get_plan("no-such-id") is None

    def test_get_plan_includes_steps(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"], "s1")
        _make_step(p, plan["plan_id"], "s2")
        fetched = p.get_plan(plan["plan_id"])
        assert len(fetched["steps"]) == 2

    def test_get_plan_steps_ordered(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"], "s1")
        _make_step(p, plan["plan_id"], "s2")
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["steps"][0]["step_order"] <= fetched["steps"][1]["step_order"]


class TestListPlans:

    def test_list_empty(self):
        p = _planner()
        assert p.list_plans() == []

    def test_list_multiple(self):
        p = _planner()
        p.create_plan("a")
        p.create_plan("b")
        assert len(p.list_plans()) == 2

    def test_list_filter_by_status(self):
        p = _planner()
        p.create_plan("pending-plan")
        plans = p.list_plans(status="pending")
        assert len(plans) == 1
        assert plans[0]["status"] == "pending"

    def test_list_filter_no_match(self):
        p = _planner()
        p.create_plan("a")
        assert p.list_plans(status="completed") == []

    def test_list_limit(self):
        p = _planner()
        for i in range(10):
            p.create_plan(f"plan-{i}")
        assert len(p.list_plans(limit=3)) == 3

    def test_list_offset(self):
        p = _planner()
        for i in range(10):
            p.create_plan(f"plan-{i}")
        first = p.list_plans(limit=5, offset=0)
        second = p.list_plans(limit=5, offset=5)
        assert len(first) == 5
        assert len(second) == 5
        ids_first = {r["plan_id"] for r in first}
        ids_second = {r["plan_id"] for r in second}
        assert ids_first.isdisjoint(ids_second)


class TestDeletePlan:

    def test_delete_existing(self):
        p = _planner()
        plan = _make_plan(p)
        assert p.delete_plan(plan["plan_id"]) is True
        assert p.get_plan(plan["plan_id"]) is None

    def test_delete_nonexistent(self):
        p = _planner()
        assert p.delete_plan("no-id") is False

    def test_delete_removes_steps(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"])
        _make_step(p, plan["plan_id"])
        p.delete_plan(plan["plan_id"])
        # Plan should be gone
        assert p.get_plan(plan["plan_id"]) is None

    def test_delete_removes_dependencies(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        p.add_dependency(s2["step_id"], s1["step_id"])
        p.delete_plan(plan["plan_id"])
        # Dependencies should be gone (no crash on re-add)
        plan2 = _make_plan(p)
        s3 = _make_step(p, plan2["plan_id"], "s3")
        s4 = _make_step(p, plan2["plan_id"], "s4")
        # Should not raise - old deps are cleaned up
        p.add_dependency(s4["step_id"], s3["step_id"])


# ---------------------------------------------------------------------------
# Step CRUD
# ---------------------------------------------------------------------------

class TestAddStep:

    def test_basic_add(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"], "my-step", "tool_call")
        assert step["step_id"]
        assert step["name"] == "my-step"
        assert step["step_type"] == "tool_call"
        assert step["status"] == "pending"

    def test_all_valid_step_types(self):
        p = _planner()
        plan = _make_plan(p)
        for st in VALID_STEP_TYPES:
            step = p.add_step(plan["plan_id"], f"s-{st}", st)
            assert step["step_type"] == st

    def test_invalid_step_type_raises(self):
        p = _planner()
        plan = _make_plan(p)
        with pytest.raises(ValueError, match="Invalid step_type"):
            p.add_step(plan["plan_id"], "bad", "invalid_type")

    def test_add_with_config(self):
        p = _planner()
        plan = _make_plan(p)
        step = p.add_step(plan["plan_id"], "s", "tool_call",
                          config={"url": "http://x", "method": "GET"})
        assert step["config"] == {"url": "http://x", "method": "GET"}

    def test_add_with_explicit_order(self):
        p = _planner()
        plan = _make_plan(p)
        step = p.add_step(plan["plan_id"], "s", "tool_call", order=5)
        assert step["step_order"] == 5

    def test_auto_order_sequential(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        assert s1["step_order"] == 0
        assert s2["step_order"] == 1

    def test_add_to_nonexistent_plan_raises(self):
        p = _planner()
        with pytest.raises(ValueError, match="not found"):
            p.add_step("no-plan", "s", "tool_call")

    def test_add_step_sets_timestamps(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        assert step["created_at"] > 0
        assert step["updated_at"] > 0


class TestUpdateStep:

    def test_update_name(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        updated = p.update_step(step["step_id"], name="new-name")
        assert updated["name"] == "new-name"

    def test_update_config(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        updated = p.update_step(step["step_id"], config={"x": 1})
        assert updated["config"] == {"x": 1}

    def test_update_status(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        updated = p.update_step(step["step_id"], status="running")
        assert updated["status"] == "running"

    def test_update_step_order(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        updated = p.update_step(step["step_id"], step_order=10)
        assert updated["step_order"] == 10

    def test_update_invalid_status_raises(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        with pytest.raises(ValueError, match="Invalid step status"):
            p.update_step(step["step_id"], status="bogus")

    def test_update_invalid_step_type_raises(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        with pytest.raises(ValueError, match="Invalid step_type"):
            p.update_step(step["step_id"], step_type="nope")

    def test_update_nonexistent_returns_none(self):
        p = _planner()
        assert p.update_step("no-id", name="x") is None

    def test_update_no_allowed_keys_returns_none(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        assert p.update_step(step["step_id"], bogus="val") is None

    def test_update_sets_updated_at(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        time.sleep(0.01)
        updated = p.update_step(step["step_id"], name="new")
        assert updated["updated_at"] >= step["created_at"]


class TestRemoveStep:

    def test_remove_existing(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        assert p.remove_step(step["step_id"]) is True
        fetched = p.get_plan(plan["plan_id"])
        assert len(fetched["steps"]) == 0

    def test_remove_nonexistent(self):
        p = _planner()
        assert p.remove_step("no-id") is False

    def test_remove_also_removes_dependencies(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        p.add_dependency(s2["step_id"], s1["step_id"])
        # Remove s1, dependency should be cleaned up
        p.remove_step(s1["step_id"])
        deps = p.get_dependencies(s2["step_id"])
        assert len(deps) == 0


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

class TestAddDependency:

    def test_basic_add(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        dep = p.add_dependency(s2["step_id"], s1["step_id"])
        assert dep["dependency_id"]
        assert dep["step_id"] == s2["step_id"]
        assert dep["depends_on_step_id"] == s1["step_id"]

    def test_self_dependency_raises(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        with pytest.raises(ValueError, match="cannot depend on itself"):
            p.add_dependency(s1["step_id"], s1["step_id"])

    def test_duplicate_dependency_raises(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        p.add_dependency(s2["step_id"], s1["step_id"])
        with pytest.raises(ValueError, match="already exists"):
            p.add_dependency(s2["step_id"], s1["step_id"])

    def test_cross_plan_dependency_raises(self):
        p = _planner()
        plan1 = _make_plan(p)
        plan2 = _make_plan(p)
        s1 = _make_step(p, plan1["plan_id"], "s1")
        s2 = _make_step(p, plan2["plan_id"], "s2")
        with pytest.raises(ValueError, match="different plans"):
            p.add_dependency(s2["step_id"], s1["step_id"])

    def test_nonexistent_step_raises(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        with pytest.raises(ValueError, match="not found"):
            p.add_dependency(s1["step_id"], "no-step")
        with pytest.raises(ValueError, match="not found"):
            p.add_dependency("no-step", s1["step_id"])

    def test_cycle_detection_direct(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        p.add_dependency(s2["step_id"], s1["step_id"])
        with pytest.raises(ValueError, match="cycle"):
            p.add_dependency(s1["step_id"], s2["step_id"])

    def test_cycle_detection_transitive(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        p.add_dependency(s2["step_id"], s1["step_id"])
        p.add_dependency(s3["step_id"], s2["step_id"])
        with pytest.raises(ValueError, match="cycle"):
            p.add_dependency(s1["step_id"], s3["step_id"])


class TestRemoveDependency:

    def test_remove_existing(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        dep = p.add_dependency(s2["step_id"], s1["step_id"])
        assert p.remove_dependency(dep["dependency_id"]) is True

    def test_remove_nonexistent(self):
        p = _planner()
        assert p.remove_dependency("no-id") is False


class TestGetDependencies:

    def test_no_deps(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        assert p.get_dependencies(s1["step_id"]) == []

    def test_with_deps(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        p.add_dependency(s2["step_id"], s1["step_id"])
        p.add_dependency(s3["step_id"], s1["step_id"])
        deps = p.get_dependencies(s2["step_id"])
        assert len(deps) == 1
        assert deps[0]["depends_on_step_id"] == s1["step_id"]

    def test_multiple_deps(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        p.add_dependency(s3["step_id"], s1["step_id"])
        p.add_dependency(s3["step_id"], s2["step_id"])
        deps = p.get_dependencies(s3["step_id"])
        assert len(deps) == 2


# ---------------------------------------------------------------------------
# Execution order (topological sort)
# ---------------------------------------------------------------------------

class TestExecutionOrder:

    def test_empty_plan(self):
        p = _planner()
        plan = _make_plan(p)
        assert p.get_execution_order(plan["plan_id"]) == []

    def test_single_step(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        order = p.get_execution_order(plan["plan_id"])
        assert len(order) == 1
        assert order[0]["step_id"] == s1["step_id"]

    def test_linear_chain(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        p.add_dependency(s2["step_id"], s1["step_id"])
        p.add_dependency(s3["step_id"], s2["step_id"])
        order = p.get_execution_order(plan["plan_id"])
        ids = [s["step_id"] for s in order]
        assert ids.index(s1["step_id"]) < ids.index(s2["step_id"])
        assert ids.index(s2["step_id"]) < ids.index(s3["step_id"])

    def test_diamond_dependency(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        s4 = _make_step(p, plan["plan_id"], "s4")
        # s1 -> s2, s1 -> s3, s2 -> s4, s3 -> s4
        p.add_dependency(s2["step_id"], s1["step_id"])
        p.add_dependency(s3["step_id"], s1["step_id"])
        p.add_dependency(s4["step_id"], s2["step_id"])
        p.add_dependency(s4["step_id"], s3["step_id"])
        order = p.get_execution_order(plan["plan_id"])
        ids = [s["step_id"] for s in order]
        assert ids.index(s1["step_id"]) < ids.index(s2["step_id"])
        assert ids.index(s1["step_id"]) < ids.index(s3["step_id"])
        assert ids.index(s2["step_id"]) < ids.index(s4["step_id"])
        assert ids.index(s3["step_id"]) < ids.index(s4["step_id"])

    def test_no_deps_preserves_order(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        order = p.get_execution_order(plan["plan_id"])
        ids = [s["step_id"] for s in order]
        assert ids == [s1["step_id"], s2["step_id"], s3["step_id"]]

    def test_multiple_roots(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        p.add_dependency(s3["step_id"], s1["step_id"])
        p.add_dependency(s3["step_id"], s2["step_id"])
        order = p.get_execution_order(plan["plan_id"])
        ids = [s["step_id"] for s in order]
        # s1 and s2 come before s3
        assert ids.index(s1["step_id"]) < ids.index(s3["step_id"])
        assert ids.index(s2["step_id"]) < ids.index(s3["step_id"])


# ---------------------------------------------------------------------------
# Execution lifecycle
# ---------------------------------------------------------------------------

class TestStartPlan:

    def test_start_pending(self):
        p = _planner()
        plan = _make_plan(p)
        result = p.start_plan(plan["plan_id"])
        assert result["status"] == "running"
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["status"] == "running"

    def test_start_running_idempotent(self):
        p = _planner()
        plan = _make_plan(p)
        p.start_plan(plan["plan_id"])
        result = p.start_plan(plan["plan_id"])
        assert result["status"] == "running"

    def test_start_nonexistent_raises(self):
        p = _planner()
        with pytest.raises(ValueError, match="not found"):
            p.start_plan("no-id")

    def test_start_completed_raises(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        steps = p.get_plan(plan["plan_id"])["steps"]
        p.complete_step(steps[0]["step_id"])
        # Plan is now completed
        with pytest.raises(ValueError, match="Cannot start"):
            p.start_plan(plan["plan_id"])

    def test_start_emits_event(self):
        bus = EventBus()
        p = _planner(bus=bus)
        plan = _make_plan(p)
        p.start_plan(plan["plan_id"])
        events = bus.query(topic="plan.started")
        assert len(events) == 1


class TestCompleteStep:

    def test_complete_basic(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        result = p.complete_step(step["step_id"])
        assert result["status"] == "completed"

    def test_complete_with_result(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        p.complete_step(step["step_id"], result={"output": "ok"})
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["steps"][0]["result"] == {"output": "ok"}

    def test_complete_nonexistent_raises(self):
        p = _planner()
        with pytest.raises(ValueError, match="not found"):
            p.complete_step("no-step")

    def test_complete_emits_event(self):
        bus = EventBus()
        p = _planner(bus=bus)
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        p.complete_step(step["step_id"])
        events = bus.query(topic="step.completed")
        assert len(events) == 1

    def test_complete_all_steps_completes_plan(self):
        bus = EventBus()
        p = _planner(bus=bus)
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        p.start_plan(plan["plan_id"])
        r1 = p.complete_step(s1["step_id"])
        assert r1["plan_completed"] is False
        r2 = p.complete_step(s2["step_id"])
        assert r2["plan_completed"] is True
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["status"] == "completed"

    def test_complete_all_emits_plan_completed(self):
        bus = EventBus()
        p = _planner(bus=bus)
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        p.complete_step(step["step_id"])
        events = bus.query(topic="plan.completed")
        assert len(events) == 1


class TestFailStep:

    def test_fail_basic(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        result = p.fail_step(step["step_id"])
        assert result["status"] == "failed"

    def test_fail_with_error(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        p.fail_step(step["step_id"], error={"msg": "timeout"})
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["steps"][0]["error"] == {"msg": "timeout"}

    def test_fail_nonexistent_raises(self):
        p = _planner()
        with pytest.raises(ValueError, match="not found"):
            p.fail_step("no-step")

    def test_fail_emits_event(self):
        bus = EventBus()
        p = _planner(bus=bus)
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        p.fail_step(step["step_id"])
        events = bus.query(topic="step.failed")
        assert len(events) == 1


class TestCancelPlan:

    def test_cancel_pending(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"])
        result = p.cancel_plan(plan["plan_id"])
        assert result["status"] == "cancelled"

    def test_cancel_running(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        result = p.cancel_plan(plan["plan_id"])
        assert result["status"] == "cancelled"

    def test_cancel_marks_pending_steps_skipped(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        p.start_plan(plan["plan_id"])
        p.complete_step(s1["step_id"])
        p.cancel_plan(plan["plan_id"])
        fetched = p.get_plan(plan["plan_id"])
        by_id = {s["step_id"]: s["status"] for s in fetched["steps"]}
        assert by_id[s1["step_id"]] == "completed"
        assert by_id[s2["step_id"]] == "skipped"

    def test_cancel_nonexistent_raises(self):
        p = _planner()
        with pytest.raises(ValueError, match="not found"):
            p.cancel_plan("no-id")

    def test_cancel_completed_raises(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        steps = p.get_plan(plan["plan_id"])["steps"]
        p.complete_step(steps[0]["step_id"])
        with pytest.raises(ValueError, match="Cannot cancel"):
            p.cancel_plan(plan["plan_id"])

    def test_cancel_emits_event(self):
        bus = EventBus()
        p = _planner(bus=bus)
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"])
        p.cancel_plan(plan["plan_id"])
        events = bus.query(topic="plan.cancelled")
        assert len(events) == 1


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

class TestPlanProgress:

    def test_empty_plan(self):
        p = _planner()
        plan = _make_plan(p)
        prog = p.get_plan_progress(plan["plan_id"])
        assert prog["total"] == 0
        assert prog["completed"] == 0

    def test_all_pending(self):
        p = _planner()
        plan = _make_plan(p)
        _make_step(p, plan["plan_id"])
        _make_step(p, plan["plan_id"])
        prog = p.get_plan_progress(plan["plan_id"])
        assert prog["total"] == 2
        assert prog["pending"] == 2

    def test_mixed_status(self):
        p = _planner()
        plan = _make_plan(p)
        s1 = _make_step(p, plan["plan_id"], "s1")
        s2 = _make_step(p, plan["plan_id"], "s2")
        s3 = _make_step(p, plan["plan_id"], "s3")
        p.start_plan(plan["plan_id"])
        p.complete_step(s1["step_id"])
        p.fail_step(s2["step_id"])
        prog = p.get_plan_progress(plan["plan_id"])
        assert prog["total"] == 3
        assert prog["completed"] == 1
        assert prog["failed"] == 1
        assert prog["pending"] == 1

    def test_nonexistent_plan_raises(self):
        p = _planner()
        with pytest.raises(ValueError, match="not found"):
            p.get_plan_progress("no-id")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_returns_instance(self):
        import sylion.execution.execution_planner as mod
        mod._planner = None
        planner = get_execution_planner()
        assert isinstance(planner, ExecutionPlanner)
        mod._planner = None

    def test_reset_creates_new(self):
        import sylion.execution.execution_planner as mod
        mod._planner = None
        p1 = get_execution_planner()
        p2 = reset_execution_planner()
        assert p1 is not p2
        mod._planner = None

    def test_get_returns_same(self):
        import sylion.execution.execution_planner as mod
        mod._planner = None
        p1 = get_execution_planner()
        p2 = get_execution_planner()
        assert p1 is p2
        mod._planner = None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_create_plans(self):
        p = _planner()
        errors = []

        def create_n(prefix):
            try:
                for i in range(10):
                    p.create_plan(f"{prefix}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_n, args=(f"t{i}",))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(p.list_plans(limit=1000)) == 50

    def test_concurrent_add_steps(self):
        p = _planner()
        plan = _make_plan(p)
        errors = []

        def add_steps(n):
            try:
                for i in range(10):
                    p.add_step(plan["plan_id"], f"s-{n}-{i}", "tool_call")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_steps, args=(i,))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        fetched = p.get_plan(plan["plan_id"])
        assert len(fetched["steps"]) == 50

    def test_concurrent_complete_steps(self):
        p = _planner()
        plan = _make_plan(p)
        steps = [_make_step(p, plan["plan_id"]) for _ in range(20)]
        p.start_plan(plan["plan_id"])
        errors = []

        def complete_step(step_id):
            try:
                p.complete_step(step_id, result={"ok": True})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=complete_step, args=(s["step_id"],))
                   for s in steps]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        prog = p.get_plan_progress(plan["plan_id"])
        assert prog["completed"] == 20


# ---------------------------------------------------------------------------
# Config / JSON handling
# ---------------------------------------------------------------------------

class TestConfigJsonHandling:

    def test_config_stored_and_retrieved(self):
        p = _planner()
        plan = _make_plan(p)
        cfg = {"key": "value", "nested": {"a": [1, 2, 3]}}
        step = p.add_step(plan["plan_id"], "s", "tool_call", config=cfg)
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["steps"][0]["config"] == cfg

    def test_config_none_stored_as_null(self):
        p = _planner()
        plan = _make_plan(p)
        step = p.add_step(plan["plan_id"], "s", "tool_call")
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["steps"][0]["config"] is None

    def test_result_json_roundtrip(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        result_data = {"output": "done", "count": 42}
        p.complete_step(step["step_id"], result=result_data)
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["steps"][0]["result"] == result_data

    def test_error_json_roundtrip(self):
        p = _planner()
        plan = _make_plan(p)
        step = _make_step(p, plan["plan_id"])
        p.start_plan(plan["plan_id"])
        error_data = {"code": 500, "message": "internal"}
        p.fail_step(step["step_id"], error=error_data)
        fetched = p.get_plan(plan["plan_id"])
        assert fetched["steps"][0]["error"] == error_data
