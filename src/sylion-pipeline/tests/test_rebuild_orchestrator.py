"""
Comprehensive tests for sylion.rebuild.orchestrator -- RebuildOrchestrator

Covers:
  - create_plan CRUD (create, get_plan, list_plans)
  - add_step to a plan, get_steps retrieval
  - execute_plan marks steps and plan as completed
  - execute_plan with no steps returns 0 executed
  - list_plans with status filter
  - modules field stored as JSON and parsed on read
  - get_plan returns None for unknown IDs
  - get_steps returns empty list for plan with no steps
  - plan_id auto-generation
  - strategy persistence
  - event emission via EventBus
  - thread safety under concurrent plan creation
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.rebuild.orchestrator import RebuildOrchestrator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orchestrator():
    """Fresh in-memory RebuildOrchestrator with no event bus."""
    return RebuildOrchestrator()


@pytest.fixture
def orchestrator_with_bus():
    """Orchestrator wired to a fresh EventBus."""
    bus = EventBus()
    orch = RebuildOrchestrator(event_bus=bus)
    return orch, bus


# ===========================================================================
# 1. create_plan() -- create
# ===========================================================================

class TestCreatePlan:

    def test_create_plan_returns_plan_id(self, orchestrator):
        result = orchestrator.create_plan("Test Plan", "A test rebuild plan")
        assert "plan_id" in result
        assert len(result["plan_id"]) == 32  # uuid hex
        assert result["name"] == "Test Plan"
        assert result["status"] == "draft"

    def test_create_plan_with_modules(self, orchestrator):
        result = orchestrator.create_plan(
            "Module Plan",
            modules=["mod-a", "mod-b", "mod-c"],
        )
        plan = orchestrator.get_plan(result["plan_id"])
        assert plan is not None
        assert plan["modules"] == ["mod-a", "mod-b", "mod-c"]

    def test_create_plan_default_modules_empty(self, orchestrator):
        result = orchestrator.create_plan("Empty Modules")
        plan = orchestrator.get_plan(result["plan_id"])
        assert plan["modules"] == []

    def test_create_plan_with_strategy(self, orchestrator):
        result = orchestrator.create_plan(
            "Strategy Plan", strategy="atomic",
        )
        plan = orchestrator.get_plan(result["plan_id"])
        assert plan["strategy"] == "atomic"

    def test_create_plan_default_strategy_is_progressive(self, orchestrator):
        result = orchestrator.create_plan("Default Strategy")
        plan = orchestrator.get_plan(result["plan_id"])
        assert plan["strategy"] == "progressive"


# ===========================================================================
# 2. get_plan() -- read
# ===========================================================================

class TestGetPlan:

    def test_get_plan_returns_full_record(self, orchestrator):
        orchestrator.create_plan(
            "Full Plan",
            description="Detailed description",
            modules=["x", "y"],
            strategy="atomic",
        )
        plans = orchestrator.list_plans()
        plan_id = plans[0]["plan_id"]

        plan = orchestrator.get_plan(plan_id)
        assert plan is not None
        assert plan["name"] == "Full Plan"
        assert plan["description"] == "Detailed description"
        assert plan["modules"] == ["x", "y"]
        assert plan["strategy"] == "atomic"
        assert plan["status"] == "draft"
        assert plan["created_at"] > 0

    def test_get_plan_nonexistent_returns_none(self, orchestrator):
        assert orchestrator.get_plan("nonexistent_plan_id") is None

    def test_get_plan_modules_parsed_as_list(self, orchestrator):
        orchestrator.create_plan("JSON Plan", modules=["alpha", "beta"])
        plans = orchestrator.list_plans()
        plan = orchestrator.get_plan(plans[0]["plan_id"])
        # modules must be a Python list, not a JSON string
        assert isinstance(plan["modules"], list)
        assert plan["modules"] == ["alpha", "beta"]


# ===========================================================================
# 3. list_plans() -- query
# ===========================================================================

class TestListPlans:

    def test_list_plans_returns_all(self, orchestrator):
        orchestrator.create_plan("Plan A")
        orchestrator.create_plan("Plan B")
        orchestrator.create_plan("Plan C")
        plans = orchestrator.list_plans()
        assert len(plans) == 3

    def test_list_plans_filter_by_status(self, orchestrator):
        orchestrator.create_plan("Draft Plan")
        result = orchestrator.create_plan("Exec Plan")
        orchestrator.add_step(result["plan_id"], "mod-x")
        orchestrator.execute_plan(result["plan_id"])

        draft_plans = orchestrator.list_plans(status="draft")
        assert len(draft_plans) == 1
        assert draft_plans[0]["name"] == "Draft Plan"

        completed_plans = orchestrator.list_plans(status="completed")
        assert len(completed_plans) == 1
        assert completed_plans[0]["name"] == "Exec Plan"

    def test_list_plans_respects_limit(self, orchestrator):
        for i in range(10):
            orchestrator.create_plan(f"Plan {i}")
        plans = orchestrator.list_plans(limit=3)
        assert len(plans) == 3

    def test_list_plans_ordered_by_created_at_desc(self, orchestrator):
        orchestrator.create_plan("First")
        time.sleep(0.01)
        orchestrator.create_plan("Second")
        time.sleep(0.01)
        orchestrator.create_plan("Third")
        plans = orchestrator.list_plans()
        # Most recent first
        assert plans[0]["name"] == "Third"
        assert plans[2]["name"] == "First"


# ===========================================================================
# 4. add_step() / get_steps()
# ===========================================================================

class TestSteps:

    def test_add_step_returns_step_id(self, orchestrator):
        plan = orchestrator.create_plan("Step Plan")
        step = orchestrator.add_step(plan["plan_id"], "mod-a")
        assert "step_id" in step
        assert len(step["step_id"]) == 32
        assert step["plan_id"] == plan["plan_id"]
        assert step["status"] == "pending"

    def test_get_steps_returns_ordered(self, orchestrator):
        plan = orchestrator.create_plan("Ordered Plan")
        orchestrator.add_step(plan["plan_id"], "mod-c", order_num=3)
        orchestrator.add_step(plan["plan_id"], "mod-a", order_num=1)
        orchestrator.add_step(plan["plan_id"], "mod-b", order_num=2)

        steps = orchestrator.get_steps(plan["plan_id"])
        assert len(steps) == 3
        assert steps[0]["module_id"] == "mod-a"
        assert steps[1]["module_id"] == "mod-b"
        assert steps[2]["module_id"] == "mod-c"

    def test_get_steps_empty_plan(self, orchestrator):
        plan = orchestrator.create_plan("Empty Steps Plan")
        steps = orchestrator.get_steps(plan["plan_id"])
        assert steps == []

    def test_add_step_preserves_action(self, orchestrator):
        plan = orchestrator.create_plan("Action Plan")
        step = orchestrator.add_step(plan["plan_id"], "mod-x", action="validate")
        steps = orchestrator.get_steps(plan["plan_id"])
        assert steps[0]["action"] == "validate"


# ===========================================================================
# 5. execute_plan()
# ===========================================================================

class TestExecutePlan:

    def test_execute_marks_steps_completed(self, orchestrator):
        plan = orchestrator.create_plan("Exec Plan")
        orchestrator.add_step(plan["plan_id"], "mod-a")
        orchestrator.add_step(plan["plan_id"], "mod-b")

        result = orchestrator.execute_plan(plan["plan_id"])
        assert result["steps_executed"] == 2
        assert result["status"] == "completed"

        steps = orchestrator.get_steps(plan["plan_id"])
        assert all(s["status"] == "completed" for s in steps)
        assert all(s["completed_at"] > 0 for s in steps)

    def test_execute_marks_plan_completed(self, orchestrator):
        plan = orchestrator.create_plan("Complete Plan")
        orchestrator.add_step(plan["plan_id"], "mod-x")
        orchestrator.execute_plan(plan["plan_id"])

        p = orchestrator.get_plan(plan["plan_id"])
        assert p["status"] == "completed"
        assert p["completed_at"] > 0

    def test_execute_plan_with_no_steps(self, orchestrator):
        plan = orchestrator.create_plan("No Steps Plan")
        result = orchestrator.execute_plan(plan["plan_id"])
        assert result["steps_executed"] == 0
        assert result["status"] == "completed"


# ===========================================================================
# 6. Event emission
# ===========================================================================

class TestEventEmission:

    def test_create_plan_emits_event(self, orchestrator_with_bus):
        orch, bus = orchestrator_with_bus
        events = []
        bus.subscribe("rebuild.orchestrator.plan_created", lambda e: events.append(e))

        orch.create_plan("Event Plan", strategy="atomic")
        assert len(events) == 1
        assert events[0].payload["name"] == "Event Plan"
        assert events[0].payload["strategy"] == "atomic"

    def test_add_step_emits_event(self, orchestrator_with_bus):
        orch, bus = orchestrator_with_bus
        events = []
        bus.subscribe("rebuild.orchestrator.step_added", lambda e: events.append(e))

        plan = orch.create_plan("Step Event Plan")
        orch.add_step(plan["plan_id"], "mod-z", action="rebuild")
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod-z"
        assert events[0].payload["action"] == "rebuild"

    def test_execute_plan_emits_event(self, orchestrator_with_bus):
        orch, bus = orchestrator_with_bus
        events = []
        bus.subscribe("rebuild.orchestrator.plan_executed", lambda e: events.append(e))

        plan = orch.create_plan("Exec Event Plan")
        orch.add_step(plan["plan_id"], "mod-a")
        orch.execute_plan(plan["plan_id"])
        assert len(events) == 1
        assert events[0].payload["steps_executed"] == 1

    def test_no_event_bus_does_not_raise(self):
        orch = RebuildOrchestrator(event_bus=None)
        plan = orch.create_plan("No Bus Plan")
        orch.add_step(plan["plan_id"], "mod-x")
        orch.execute_plan(plan["plan_id"])


# ===========================================================================
# 7. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_plan_creation(self):
        orch = RebuildOrchestrator()
        results = []
        results_lock = threading.Lock()

        def create_plan(idx):
            r = orch.create_plan(f"Concurrent Plan {idx}")
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=create_plan, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(results) == 20
        plan_ids = [r["plan_id"] for r in results]
        assert len(set(plan_ids)) == 20

        # Verify all 20 plans persisted in the orchestrator
        plans = orch.list_plans()
        assert len(plans) == 20
