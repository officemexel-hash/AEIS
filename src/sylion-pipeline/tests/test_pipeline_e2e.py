"""End-to-end pipeline tests: idea → plan → generate → review → complete."""

import time

import pytest

from sylion.cognitive.planner import Planner
from sylion.cognitive.code_agent import CodeAgent
from sylion.core.decision_gate_engine import DecisionGateEngine
from sylion.core.pipeline_controller import PipelineController, reset_pipeline_controller


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset():
    reset_pipeline_controller()
    yield
    reset_pipeline_controller()


def _make_controller(code_agent=None, planner=None, decision_gate=None):
    return PipelineController(
        planner=planner or Planner(),
        code_agent=code_agent or CodeAgent(),
        decision_gate=decision_gate or DecisionGateEngine(),
    )


# ---------------------------------------------------------------------------
# Happy path: idea → plan → generate → complete
# ---------------------------------------------------------------------------

class TestPipelineE2E:
    def test_submit_and_execute(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Build a Fibonacci calculator")
        assert result["status"] == "pending"
        assert "run_id" in result

        run = ctrl.execute_run(result["run_id"])
        assert run["status"] == "complete"
        assert run["idea"] == "Build a Fibonacci calculator"
        assert len(run["steps"]) == 5  # analyze, design, implement, test, review

    def test_plan_generated_from_idea(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Create a REST API")
        run = ctrl.execute_run(result["run_id"])
        assert "plan" in run
        assert "steps" in run["plan"]
        assert len(run["plan"]["steps"]) == 5

    def test_steps_have_code_output(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Hello world function")
        run = ctrl.execute_run(result["run_id"])
        for step in run["steps"]:
            assert step["status"] == "complete"
            assert "result" in step

    def test_get_run_returns_full_state(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Test idea")
        ctrl.execute_run(result["run_id"])

        run = ctrl.get_run(result["run_id"])
        assert run is not None
        assert run["status"] == "complete"
        assert run["idea"] == "Test idea"

    def test_list_runs(self):
        ctrl = _make_controller()
        ctrl.submit_idea("Idea 1")
        ctrl.submit_idea("Idea 2")
        ctrl.submit_idea("Idea 3")

        runs = ctrl.list_runs()
        assert len(runs) == 3

    def test_list_runs_filter_by_status(self):
        ctrl = _make_controller()
        r1 = ctrl.submit_idea("Idea 1")
        r2 = ctrl.submit_idea("Idea 2")
        ctrl.execute_run(r1["run_id"])

        pending = ctrl.list_runs(status="pending")
        assert len(pending) == 1
        assert pending[0]["run_id"] == r2["run_id"]

    def test_cancel_pending_run(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Will cancel this")
        cancel_result = ctrl.cancel_run(result["run_id"])
        assert cancel_result["status"] == "cancelled"

        run = ctrl.get_run(result["run_id"])
        assert run["status"] == "cancelled"

    def test_cannot_cancel_completed_run(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Done already")
        ctrl.execute_run(result["run_id"])

        cancel = ctrl.cancel_run(result["run_id"])
        assert cancel["status"] == "complete"
        assert "already finished" in cancel["message"]

    def test_get_run_steps(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Step test")
        ctrl.execute_run(result["run_id"])

        run = ctrl.get_run(result["run_id"])
        steps = run["steps"]
        assert len(steps) > 0
        assert all("step_id" in s for s in steps)
        assert all("name" in s for s in steps)
        assert all("status" in s for s in steps)

    def test_get_nonexistent_run(self):
        ctrl = _make_controller()
        assert ctrl.get_run("nonexistent") is None

    def test_execute_nonexistent_run(self):
        ctrl = _make_controller()
        result = ctrl.execute_run("nonexistent")
        assert "error" in result

    def test_completed_at_set(self):
        ctrl = _make_controller()
        result = ctrl.submit_idea("Timing test")
        run = ctrl.execute_run(result["run_id"])
        assert run["completed_at"] > 0
        assert run["completed_at"] >= run["created_at"]


# ---------------------------------------------------------------------------
# Without subsystems (graceful degradation)
# ---------------------------------------------------------------------------

class TestPipelineNoSubsystems:
    def test_submit_no_subsystems(self):
        ctrl = PipelineController()
        result = ctrl.submit_idea("No subsystems")
        assert result["status"] == "pending"

    def test_execute_no_subsystems(self):
        ctrl = PipelineController()
        result = ctrl.submit_idea("No subsystems")
        run = ctrl.execute_run(result["run_id"])
        assert run["status"] == "complete"
        # Single step since no planner
        assert len(run["steps"]) == 1
        assert run["steps"][0]["result"]["output"] == "skipped (no code_agent)"


# ---------------------------------------------------------------------------
# Planner decompose_idea integration
# ---------------------------------------------------------------------------

class TestPlannerDecomposeIdea:
    def test_decompose_idea_returns_plan(self):
        planner = Planner()
        result = planner.decompose_idea("Build a web scraper")
        assert "plan_id" in result
        assert "steps" in result
        assert len(result["steps"]) == 5

    def test_decompose_idea_creates_plan_record(self):
        planner = Planner()
        result = planner.decompose_idea("Test idea")
        plan = planner.get_plan(result["plan_id"])
        assert plan is not None
        assert plan["title"] == "Test idea"

    def test_decompose_idea_creates_tasks(self):
        planner = Planner()
        result = planner.decompose_idea("Test idea")
        tasks = planner.get_tasks(result["plan_id"])
        assert len(tasks) == 5

    def test_decompose_idea_step_structure(self):
        planner = Planner()
        result = planner.decompose_idea("Test")
        for step in result["steps"]:
            assert "step_id" in step
            assert "name" in step
            assert "description" in step

    def test_decompose_idea_truncates_long_title(self):
        planner = Planner()
        long_idea = "A" * 200
        result = planner.decompose_idea(long_idea)
        assert len(result["title"]) == 80


# ---------------------------------------------------------------------------
# Decision gate integration
# ---------------------------------------------------------------------------

class TestDecisionGateInPipeline:
    def test_gate_approves_steps(self):
        gate = DecisionGateEngine()
        ctrl = _make_controller(decision_gate=gate)
        result = ctrl.submit_idea("Gate test")
        run = ctrl.execute_run(result["run_id"])
        assert run["status"] == "complete"
        for step in run["steps"]:
            assert "gate" in step.get("result", {})

    def test_gate_reject_step_marks_failed(self):
        """Decision gate that always rejects."""
        class RejectGate:
            def evaluate_gate(self, gate_id, context=None):
                return {"gate_id": gate_id, "result": "fail", "message": "quality too low"}

        ctrl = _make_controller(decision_gate=RejectGate())
        result = ctrl.submit_idea("Will fail")
        run = ctrl.execute_run(result["run_id"])
        assert run["status"] == "failed"
        assert all(s["status"] == "failed" for s in run["steps"])


# ---------------------------------------------------------------------------
# Multiple runs concurrency
# ---------------------------------------------------------------------------

class TestMultipleRuns:
    def test_sequential_runs(self):
        ctrl = _make_controller()
        r1 = ctrl.submit_idea("Idea A")
        r2 = ctrl.submit_idea("Idea B")

        ctrl.execute_run(r1["run_id"])
        ctrl.execute_run(r2["run_id"])

        run1 = ctrl.get_run(r1["run_id"])
        run2 = ctrl.get_run(r2["run_id"])
        assert run1["status"] == "complete"
        assert run2["status"] == "complete"
        assert run1["run_id"] != run2["run_id"]

    def test_mixed_statuses(self):
        ctrl = _make_controller()
        r1 = ctrl.submit_idea("Execute me")
        r2 = ctrl.submit_idea("Leave pending")
        r3 = ctrl.submit_idea("Cancel me")

        ctrl.execute_run(r1["run_id"])
        ctrl.cancel_run(r3["run_id"])

        runs = ctrl.list_runs()
        statuses = {r["run_id"]: r["status"] for r in runs}
        assert statuses[r1["run_id"]] == "complete"
        assert statuses[r2["run_id"]] == "pending"
        assert statuses[r3["run_id"]] == "cancelled"
