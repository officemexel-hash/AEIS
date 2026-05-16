"""Tests for sylion.rebuild.orchestrator module."""
import pytest
from sylion.rebuild.orchestrator import RebuildOrchestrator


class TestRebuildOrchestrator:
    @pytest.fixture
    def orch(self):
        return RebuildOrchestrator()

    def test_create_plan(self, orch):
        result = orch.create_plan("Plan A", description="Test plan", modules=["m1", "m2"])
        assert "plan_id" in result
        assert result["name"] == "Plan A"
        assert result["status"] in ("draft", "created", "pending")

    def test_create_plan_default_strategy(self, orch):
        result = orch.create_plan("Plan B")
        assert "plan_id" in result

    def test_add_step(self, orch):
        plan = orch.create_plan("Step Plan")
        result = orch.add_step(plan["plan_id"], "mod-a", action="rebuild")
        assert "step_id" in result
        assert result["plan_id"] == plan["plan_id"]

    def test_get_plan(self, orch):
        plan = orch.create_plan("Get Plan")
        found = orch.get_plan(plan["plan_id"])
        assert found is not None
        assert found["plan_id"] == plan["plan_id"]
        assert found["name"] == "Get Plan"

    def test_get_plan_not_found(self, orch):
        assert orch.get_plan("nonexistent") is None

    def test_list_plans(self, orch):
        orch.create_plan("List A")
        orch.create_plan("List B")
        plans = orch.list_plans()
        assert len(plans) >= 2

    def test_list_plans_filter_status(self, orch):
        orch.create_plan("Filter Plan")
        plans = orch.list_plans(status="draft")
        assert isinstance(plans, list)

    def test_get_steps(self, orch):
        plan = orch.create_plan("Steps Plan")
        orch.add_step(plan["plan_id"], "s1", action="rebuild")
        orch.add_step(plan["plan_id"], "s2", action="validate")
        steps = orch.get_steps(plan["plan_id"])
        assert len(steps) >= 2

    def test_execute_plan(self, orch):
        plan = orch.create_plan("Exec Plan", modules=["m1"])
        orch.add_step(plan["plan_id"], "m1", action="rebuild")
        result = orch.execute_plan(plan["plan_id"])
        assert "plan_id" in result
        assert result["steps_executed"] >= 1
