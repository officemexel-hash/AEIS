"""Tests for SYLION Execution -- Deployment Orchestrator.

Covers:
  - Deployment creation with auto-generated steps
  - Validation of strategies, statuses, stages
  - Getting and listing deployments
  - Step advancement lifecycle
  - Deployment completion, failure, rollback
  - Statistics aggregation
  - EventBus emission
  - Thread safety
  - Singleton pattern
  - Edge cases and error handling
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.deployment_orchestrator import (
    DEFAULT_STEPS,
    VALID_STAGES,
    VALID_STATUSES,
    VALID_STRATEGIES,
    DeploymentOrchestrator,
    get_deployment_orchestrator,
    reset_deployment_orchestrator,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton before and after each test."""
    reset_deployment_orchestrator()
    yield
    reset_deployment_orchestrator()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def orch(bus):
    return DeploymentOrchestrator(db_path=":memory:", event_bus=bus)


@pytest.fixture
def orch_no_bus():
    return DeploymentOrchestrator(db_path=":memory:", event_bus=None)


def _create_basic_deployment(orch, **kwargs):
    """Helper to create a basic deployment with sensible defaults."""
    defaults = {
        "module_id": "mod.test",
        "from_stage": "draft",
        "to_stage": "build",
        "strategy": "blue_green",
    }
    defaults.update(kwargs)
    return orch.create_deployment(**defaults)


def _advance_all_steps(orch, deployment_id):
    """Advance all steps to completed: pending->in_progress then in_progress->completed."""
    for step_name in DEFAULT_STEPS:
        orch.advance_step(deployment_id, step_name)  # pending -> in_progress
        orch.advance_step(deployment_id, step_name)  # in_progress -> completed


# ---------------------------------------------------------------------------
# 1. Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_valid_strategies(self):
        assert "blue_green" in VALID_STRATEGIES
        assert "canary" in VALID_STRATEGIES
        assert "rolling" in VALID_STRATEGIES
        assert "recreate" in VALID_STRATEGIES
        assert "shadow" in VALID_STRATEGIES
        assert len(VALID_STRATEGIES) == 5

    def test_valid_statuses(self):
        assert "pending" in VALID_STATUSES
        assert "in_progress" in VALID_STATUSES
        assert "completed" in VALID_STATUSES
        assert "failed" in VALID_STATUSES
        assert "rolled_back" in VALID_STATUSES
        assert len(VALID_STATUSES) == 5

    def test_valid_stages(self):
        assert "draft" in VALID_STAGES
        assert "build" in VALID_STAGES
        assert "validate" in VALID_STAGES
        assert "shadow" in VALID_STAGES
        assert "dual" in VALID_STAGES
        assert "cutover" in VALID_STAGES
        assert "stable" in VALID_STAGES
        assert "deprecated" in VALID_STAGES
        assert len(VALID_STAGES) == 8

    def test_default_steps(self):
        assert DEFAULT_STEPS == ("prepare", "validate", "deploy", "verify", "complete")
        assert len(DEFAULT_STEPS) == 5


# ---------------------------------------------------------------------------
# 2. Deployment creation
# ---------------------------------------------------------------------------

class TestCreateDeployment:
    def test_create_returns_deployment_dict(self, orch):
        d = _create_basic_deployment(orch)
        assert "deployment_id" in d
        assert d["module_id"] == "mod.test"
        assert d["from_stage"] == "draft"
        assert d["to_stage"] == "build"
        assert d["strategy"] == "blue_green"
        assert d["status"] == "pending"
        assert d["started_at"] is not None
        assert d["completed_at"] is None
        assert d["rollback_at"] is None
        assert d["metadata"] == {}

    def test_create_auto_generates_steps(self, orch):
        d = _create_basic_deployment(orch)
        steps = orch.get_steps(d["deployment_id"])
        assert len(steps) == 5
        names = [s["step_name"] for s in steps]
        assert names == ["prepare", "validate", "deploy", "verify", "complete"]

    def test_create_steps_all_pending(self, orch):
        d = _create_basic_deployment(orch)
        steps = orch.get_steps(d["deployment_id"])
        for step in steps:
            assert step["status"] == "pending"
            assert step["started_at"] is None
            assert step["completed_at"] is None

    def test_create_steps_ordered(self, orch):
        d = _create_basic_deployment(orch)
        steps = orch.get_steps(d["deployment_id"])
        orders = [s["step_order"] for s in steps]
        assert orders == [0, 1, 2, 3, 4]

    def test_create_with_each_strategy(self, orch):
        for strategy in VALID_STRATEGIES:
            d = orch.create_deployment(
                module_id=f"mod.{strategy}",
                from_stage="draft", to_stage="build",
                strategy=strategy,
            )
            assert d["strategy"] == strategy

    def test_create_with_metadata(self, orch):
        meta = {"owner": "alice", "ticket": "JIRA-123"}
        d = _create_basic_deployment(orch, metadata=meta)
        assert d["metadata"]["owner"] == "alice"
        assert d["metadata"]["ticket"] == "JIRA-123"

    def test_create_default_strategy_is_blue_green(self, orch):
        d = orch.create_deployment("mod.x", "draft", "build")
        assert d["strategy"] == "blue_green"

    def test_create_invalid_strategy_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid strategy"):
            orch.create_deployment("mod.x", "draft", "build", strategy="invalid")

    def test_create_invalid_from_stage_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid stage"):
            orch.create_deployment("mod.x", "invalid_stage", "build")

    def test_create_invalid_to_stage_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid stage"):
            orch.create_deployment("mod.x", "draft", "invalid_stage")

    def test_create_deployment_id_is_unique(self, orch):
        d1 = _create_basic_deployment(orch)
        d2 = _create_basic_deployment(orch)
        assert d1["deployment_id"] != d2["deployment_id"]

    def test_create_with_empty_metadata(self, orch):
        d = _create_basic_deployment(orch, metadata={})
        assert d["metadata"] == {}

    def test_create_with_none_metadata(self, orch):
        d = orch.create_deployment("mod.x", "draft", "build", metadata=None)
        assert d["metadata"] == {}


# ---------------------------------------------------------------------------
# 3. Get deployment
# ---------------------------------------------------------------------------

class TestGetDeployment:
    def test_get_existing(self, orch):
        created = _create_basic_deployment(orch)
        fetched = orch.get_deployment(created["deployment_id"])
        assert fetched is not None
        assert fetched["deployment_id"] == created["deployment_id"]
        assert fetched["module_id"] == "mod.test"

    def test_get_nonexistent_returns_none(self, orch):
        assert orch.get_deployment("ghost_id") is None

    def test_get_parses_metadata_json(self, orch):
        meta = {"key": "value", "nested": {"a": 1}}
        created = _create_basic_deployment(orch, metadata=meta)
        fetched = orch.get_deployment(created["deployment_id"])
        assert isinstance(fetched["metadata"], dict)
        assert fetched["metadata"]["key"] == "value"
        assert fetched["metadata"]["nested"]["a"] == 1

    def test_get_returns_all_fields(self, orch):
        created = _create_basic_deployment(orch, metadata={"x": 1})
        fetched = orch.get_deployment(created["deployment_id"])
        expected_keys = {
            "deployment_id", "module_id", "from_stage", "to_stage",
            "strategy", "status", "started_at", "completed_at",
            "rollback_at", "metadata",
        }
        assert set(fetched.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 4. List deployments
# ---------------------------------------------------------------------------

class TestListDeployments:
    def test_list_empty(self, orch):
        assert orch.list_deployments() == []

    def test_list_all(self, orch):
        _create_basic_deployment(orch, module_id="mod.a")
        _create_basic_deployment(orch, module_id="mod.b")
        results = orch.list_deployments()
        assert len(results) == 2

    def test_list_filter_by_module_id(self, orch):
        _create_basic_deployment(orch, module_id="mod.a")
        _create_basic_deployment(orch, module_id="mod.b")
        _create_basic_deployment(orch, module_id="mod.a")
        results = orch.list_deployments(module_id="mod.a")
        assert len(results) == 2
        assert all(r["module_id"] == "mod.a" for r in results)

    def test_list_filter_by_status(self, orch):
        d = _create_basic_deployment(orch)
        _create_basic_deployment(orch)
        # Advance first deployment to trigger in_progress
        orch.advance_step(d["deployment_id"], "prepare")
        results = orch.list_deployments(status="in_progress")
        assert len(results) == 1
        assert results[0]["deployment_id"] == d["deployment_id"]

    def test_list_filter_by_module_and_status(self, orch):
        d1 = _create_basic_deployment(orch, module_id="mod.target")
        _create_basic_deployment(orch, module_id="mod.other")
        _create_basic_deployment(orch, module_id="mod.target")
        orch.advance_step(d1["deployment_id"], "prepare")
        results = orch.list_deployments(module_id="mod.target", status="in_progress")
        assert len(results) == 1

    def test_list_respects_limit(self, orch):
        for i in range(5):
            _create_basic_deployment(orch, module_id=f"mod.{i}")
        results = orch.list_deployments(limit=3)
        assert len(results) == 3

    def test_list_invalid_status_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid status"):
            orch.list_deployments(status="nonexistent")

    def test_list_ordered_by_started_at_desc(self, orch):
        ids = []
        for i in range(3):
            d = _create_basic_deployment(orch, module_id=f"mod.{i}")
            ids.append(d["deployment_id"])
        results = orch.list_deployments()
        # Most recent first
        assert results[0]["deployment_id"] == ids[2]
        assert results[2]["deployment_id"] == ids[0]


# ---------------------------------------------------------------------------
# 5. Step advancement
# ---------------------------------------------------------------------------

class TestAdvanceStep:
    def test_advance_pending_to_in_progress(self, orch):
        d = _create_basic_deployment(orch)
        result = orch.advance_step(d["deployment_id"], "prepare")
        assert result["previous_status"] == "pending"
        assert result["new_status"] == "in_progress"

    def test_advance_in_progress_to_completed(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")  # -> in_progress
        result = orch.advance_step(d["deployment_id"], "prepare")  # -> completed
        assert result["previous_status"] == "in_progress"
        assert result["new_status"] == "completed"

    def test_advance_sets_started_at(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        steps = orch.get_steps(d["deployment_id"])
        prepare = [s for s in steps if s["step_name"] == "prepare"][0]
        assert prepare["started_at"] is not None

    def test_advance_sets_completed_at(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.advance_step(d["deployment_id"], "prepare")
        steps = orch.get_steps(d["deployment_id"])
        prepare = [s for s in steps if s["step_name"] == "prepare"][0]
        assert prepare["completed_at"] is not None

    def test_advance_with_output(self, orch):
        d = _create_basic_deployment(orch)
        result = orch.advance_step(d["deployment_id"], "prepare", output="OK")
        assert result["output"] == "OK"

    def test_advance_sets_deployment_in_progress(self, orch):
        d = _create_basic_deployment(orch)
        assert d["status"] == "pending"
        orch.advance_step(d["deployment_id"], "prepare")
        fetched = orch.get_deployment(d["deployment_id"])
        assert fetched["status"] == "in_progress"

    def test_advance_completed_step_raises(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.advance_step(d["deployment_id"], "prepare")
        with pytest.raises(ValueError, match="Cannot advance step"):
            orch.advance_step(d["deployment_id"], "prepare")

    def test_advance_nonexistent_step_raises(self, orch):
        d = _create_basic_deployment(orch)
        with pytest.raises(ValueError, match="not found"):
            orch.advance_step(d["deployment_id"], "nonexistent_step")

    def test_advance_nonexistent_deployment_raises(self, orch):
        with pytest.raises(ValueError, match="not found"):
            orch.advance_step("ghost_id", "prepare")

    def test_advance_sequential_steps(self, orch):
        d = _create_basic_deployment(orch)
        for step_name in DEFAULT_STEPS:
            orch.advance_step(d["deployment_id"], step_name)
            orch.advance_step(d["deployment_id"], step_name)
        steps = orch.get_steps(d["deployment_id"])
        assert all(s["status"] == "completed" for s in steps)


# ---------------------------------------------------------------------------
# 6. Complete deployment
# ---------------------------------------------------------------------------

class TestCompleteDeployment:
    def test_complete_after_all_steps_done(self, orch):
        d = _create_basic_deployment(orch)
        _advance_all_steps(orch, d["deployment_id"])
        result = orch.complete_deployment(d["deployment_id"])
        assert result["status"] == "completed"
        assert result["completed_at"] is not None

    def test_complete_sets_completed_at(self, orch):
        d = _create_basic_deployment(orch)
        _advance_all_steps(orch, d["deployment_id"])
        orch.complete_deployment(d["deployment_id"])
        fetched = orch.get_deployment(d["deployment_id"])
        assert fetched["completed_at"] is not None

    def test_complete_with_incomplete_steps_raises(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        with pytest.raises(ValueError, match="not completed"):
            orch.complete_deployment(d["deployment_id"])

    def test_complete_already_completed_raises(self, orch):
        d = _create_basic_deployment(orch)
        _advance_all_steps(orch, d["deployment_id"])
        orch.complete_deployment(d["deployment_id"])
        with pytest.raises(ValueError, match="Cannot complete"):
            orch.complete_deployment(d["deployment_id"])

    def test_complete_failed_raises(self, orch):
        d = _create_basic_deployment(orch)
        orch.fail_deployment(d["deployment_id"], "test")
        with pytest.raises(ValueError, match="Cannot complete"):
            orch.complete_deployment(d["deployment_id"])

    def test_complete_rolled_back_raises(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.rollback_deployment(d["deployment_id"])
        with pytest.raises(ValueError, match="Cannot complete"):
            orch.complete_deployment(d["deployment_id"])

    def test_complete_nonexistent_raises(self, orch):
        with pytest.raises(ValueError, match="not found"):
            orch.complete_deployment("ghost_id")


# ---------------------------------------------------------------------------
# 7. Fail deployment
# ---------------------------------------------------------------------------

class TestFailDeployment:
    def test_fail_pending_deployment(self, orch):
        d = _create_basic_deployment(orch)
        result = orch.fail_deployment(d["deployment_id"], "bad config")
        assert result["status"] == "failed"
        assert result["reason"] == "bad config"

    def test_fail_in_progress_deployment(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        result = orch.fail_deployment(d["deployment_id"], "timeout")
        assert result["status"] == "failed"

    def test_fail_records_reason_in_metadata(self, orch):
        d = _create_basic_deployment(orch, metadata={"key": "val"})
        orch.fail_deployment(d["deployment_id"], "network error")
        fetched = orch.get_deployment(d["deployment_id"])
        assert fetched["metadata"]["failure_reason"] == "network error"
        assert fetched["metadata"]["key"] == "val"

    def test_fail_completed_raises(self, orch):
        d = _create_basic_deployment(orch)
        _advance_all_steps(orch, d["deployment_id"])
        orch.complete_deployment(d["deployment_id"])
        with pytest.raises(ValueError, match="Cannot fail"):
            orch.fail_deployment(d["deployment_id"])

    def test_fail_rolled_back_raises(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.rollback_deployment(d["deployment_id"])
        with pytest.raises(ValueError, match="Cannot fail"):
            orch.fail_deployment(d["deployment_id"])

    def test_fail_with_empty_reason(self, orch):
        d = _create_basic_deployment(orch)
        result = orch.fail_deployment(d["deployment_id"])
        assert result["reason"] == ""

    def test_fail_nonexistent_raises(self, orch):
        with pytest.raises(ValueError, match="not found"):
            orch.fail_deployment("ghost_id")

    def test_fail_already_failed_is_idempotent(self, orch):
        d = _create_basic_deployment(orch)
        orch.fail_deployment(d["deployment_id"], "first")
        result = orch.fail_deployment(d["deployment_id"], "second")
        assert result["status"] == "failed"
        assert result["reason"] == "second"


# ---------------------------------------------------------------------------
# 8. Rollback deployment
# ---------------------------------------------------------------------------

class TestRollbackDeployment:
    def test_rollback_in_progress(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        result = orch.rollback_deployment(d["deployment_id"])
        assert result["status"] == "rolled_back"
        assert result["rollback_at"] is not None
        assert result["from_stage"] == "draft"
        assert result["to_stage"] == "build"

    def test_rollback_failed(self, orch):
        d = _create_basic_deployment(orch)
        orch.fail_deployment(d["deployment_id"], "error")
        result = orch.rollback_deployment(d["deployment_id"])
        assert result["status"] == "rolled_back"

    def test_rollback_sets_rollback_at(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.rollback_deployment(d["deployment_id"])
        fetched = orch.get_deployment(d["deployment_id"])
        assert fetched["rollback_at"] is not None

    def test_rollback_pending_raises(self, orch):
        d = _create_basic_deployment(orch)
        with pytest.raises(ValueError, match="Cannot rollback"):
            orch.rollback_deployment(d["deployment_id"])

    def test_rollback_completed_raises(self, orch):
        d = _create_basic_deployment(orch)
        _advance_all_steps(orch, d["deployment_id"])
        orch.complete_deployment(d["deployment_id"])
        with pytest.raises(ValueError, match="Cannot rollback"):
            orch.rollback_deployment(d["deployment_id"])

    def test_rollback_already_rolled_back_raises(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.rollback_deployment(d["deployment_id"])
        with pytest.raises(ValueError, match="Cannot rollback"):
            orch.rollback_deployment(d["deployment_id"])

    def test_rollback_nonexistent_raises(self, orch):
        with pytest.raises(ValueError, match="not found"):
            orch.rollback_deployment("ghost_id")


# ---------------------------------------------------------------------------
# 9. Get steps
# ---------------------------------------------------------------------------

class TestGetSteps:
    def test_get_steps_returns_all(self, orch):
        d = _create_basic_deployment(orch)
        steps = orch.get_steps(d["deployment_id"])
        assert len(steps) == 5

    def test_get_steps_ordered_by_step_order(self, orch):
        d = _create_basic_deployment(orch)
        steps = orch.get_steps(d["deployment_id"])
        orders = [s["step_order"] for s in steps]
        assert orders == sorted(orders)

    def test_get_steps_after_advancement(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.advance_step(d["deployment_id"], "prepare")
        steps = orch.get_steps(d["deployment_id"])
        prepare = [s for s in steps if s["step_name"] == "prepare"][0]
        assert prepare["status"] == "completed"
        # Other steps still pending
        others = [s for s in steps if s["step_name"] != "prepare"]
        assert all(s["status"] == "pending" for s in others)

    def test_get_steps_nonexistent_deployment(self, orch):
        with pytest.raises(ValueError):
            orch.get_steps("ghost_id")

    def test_get_steps_contains_expected_fields(self, orch):
        d = _create_basic_deployment(orch)
        steps = orch.get_steps(d["deployment_id"])
        step = steps[0]
        expected_keys = {
            "step_id", "deployment_id", "step_name", "step_order",
            "status", "started_at", "completed_at", "output",
        }
        assert set(step.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 10. Statistics
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty(self, orch):
        stats = orch.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"]["pending"] == 0
        assert stats["by_strategy"]["blue_green"] == 0

    def test_stats_counts_by_status(self, orch):
        d1 = _create_basic_deployment(orch)
        d2 = _create_basic_deployment(orch)
        _create_basic_deployment(orch)

        orch.fail_deployment(d1["deployment_id"], "error")
        orch.advance_step(d2["deployment_id"], "prepare")

        stats = orch.get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["failed"] == 1
        assert stats["by_status"]["in_progress"] == 1
        assert stats["by_status"]["pending"] == 1

    def test_stats_counts_by_strategy(self, orch):
        orch.create_deployment("m1", "draft", "build", strategy="blue_green")
        orch.create_deployment("m2", "draft", "build", strategy="canary")
        orch.create_deployment("m3", "draft", "build", strategy="blue_green")

        stats = orch.get_stats()
        assert stats["by_strategy"]["blue_green"] == 2
        assert stats["by_strategy"]["canary"] == 1

    def test_stats_includes_all_statuses(self, orch):
        stats = orch.get_stats()
        for s in VALID_STATUSES:
            assert s in stats["by_status"]

    def test_stats_includes_all_strategies(self, orch):
        stats = orch.get_stats()
        for s in VALID_STRATEGIES:
            assert s in stats["by_strategy"]


# ---------------------------------------------------------------------------
# 11. EventBus emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_create_emits_deployment_created(self, orch, bus):
        events = []
        bus.subscribe("deployment.created", events.append)
        _create_basic_deployment(orch)
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod.test"
        assert events[0].payload["strategy"] == "blue_green"

    def test_create_event_contains_stages(self, orch, bus):
        events = []
        bus.subscribe("deployment.created", events.append)
        orch.create_deployment("mod.x", "validate", "shadow")
        assert events[0].payload["from_stage"] == "validate"
        assert events[0].payload["to_stage"] == "shadow"

    def test_complete_emits_deployment_completed(self, orch, bus):
        events = []
        bus.subscribe("deployment.completed", events.append)
        d = _create_basic_deployment(orch)
        _advance_all_steps(orch, d["deployment_id"])
        orch.complete_deployment(d["deployment_id"])
        assert len(events) == 1
        assert events[0].payload["deployment_id"] == d["deployment_id"]

    def test_fail_emits_deployment_failed(self, orch, bus):
        events = []
        bus.subscribe("deployment.failed", events.append)
        d = _create_basic_deployment(orch)
        orch.fail_deployment(d["deployment_id"], "timeout")
        assert len(events) == 1
        assert events[0].payload["reason"] == "timeout"

    def test_rollback_emits_deployment_rolled_back(self, orch, bus):
        events = []
        bus.subscribe("deployment.rolled_back", events.append)
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare")
        orch.rollback_deployment(d["deployment_id"])
        assert len(events) == 1
        assert events[0].payload["from_stage"] == "draft"

    def test_no_bus_does_not_crash(self, orch_no_bus):
        d = orch_no_bus.create_deployment("m1", "draft", "build")
        orch_no_bus.fail_deployment(d["deployment_id"], "ok")
        # No crash means event emission was safely skipped


# ---------------------------------------------------------------------------
# 12. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_creations(self, orch):
        results = []
        errors = []

        def create(i):
            try:
                r = orch.create_deployment(
                    f"mod.thread.{i}", "draft", "build",
                    strategy="rolling",
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert len(set(r["deployment_id"] for r in results)) == 10

    def test_concurrent_advance_step(self, orch):
        d = _create_basic_deployment(orch)
        errors = []

        def advance_step(step_name):
            try:
                orch.advance_step(d["deployment_id"], step_name)
                orch.advance_step(d["deployment_id"], step_name)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=advance_step, args=(step,))
            for step in DEFAULT_STEPS
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        steps = orch.get_steps(d["deployment_id"])
        assert all(s["status"] == "completed" for s in steps)

    def test_concurrent_reads_and_writes(self, orch):
        d = _create_basic_deployment(orch)
        errors = []
        read_results = []

        def writer():
            try:
                orch.advance_step(d["deployment_id"], "prepare")
                orch.advance_step(d["deployment_id"], "prepare")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                r = orch.get_deployment(d["deployment_id"])
                read_results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer)]
        threads += [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r is not None for r in read_results)


# ---------------------------------------------------------------------------
# 13. Singleton pattern
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        a = get_deployment_orchestrator(db_path=":memory:")
        b = get_deployment_orchestrator(db_path=":memory:")
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_deployment_orchestrator(db_path=":memory:")
        reset_deployment_orchestrator(db_path=":memory:")
        b = get_deployment_orchestrator(db_path=":memory:")
        assert a is not b

    def test_reset_returns_orchestrator(self):
        orch = reset_deployment_orchestrator(db_path=":memory:")
        assert isinstance(orch, DeploymentOrchestrator)

    def test_get_after_reset_returns_new(self):
        a = get_deployment_orchestrator(db_path=":memory:")
        reset_deployment_orchestrator(db_path=":memory:")
        b = get_deployment_orchestrator(db_path=":memory:")
        assert b is not a


# ---------------------------------------------------------------------------
# 14. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_metadata_with_complex_types(self, orch):
        meta = {"list": [1, 2, 3], "nested": {"a": {"b": True}}, "null": None}
        d = _create_basic_deployment(orch, metadata=meta)
        fetched = orch.get_deployment(d["deployment_id"])
        assert fetched["metadata"]["list"] == [1, 2, 3]
        assert fetched["metadata"]["nested"]["a"]["b"] is True

    def test_multiple_deployments_same_module(self, orch):
        d1 = _create_basic_deployment(orch, module_id="mod.dup")
        d2 = _create_basic_deployment(orch, module_id="mod.dup")
        assert d1["deployment_id"] != d2["deployment_id"]
        results = orch.list_deployments(module_id="mod.dup")
        assert len(results) == 2

    def test_all_stage_transitions(self, orch):
        stage_list = list(VALID_STAGES)
        for i in range(len(stage_list) - 1):
            d = orch.create_deployment(
                "mod.x", stage_list[i], stage_list[i + 1],
            )
            assert d["from_stage"] == stage_list[i]
            assert d["to_stage"] == stage_list[i + 1]

    def test_step_output_preserved(self, orch):
        d = _create_basic_deployment(orch)
        orch.advance_step(d["deployment_id"], "prepare", output="started")
        orch.advance_step(d["deployment_id"], "prepare", output="done")
        steps = orch.get_steps(d["deployment_id"])
        prepare = [s for s in steps if s["step_name"] == "prepare"][0]
        assert prepare["output"] == "done"

    def test_complete_deployment_from_pending_after_all_steps(self, orch):
        """A deployment that is still 'pending' can be completed if all steps are done."""
        d = _create_basic_deployment(orch)
        # Manually advance all steps without touching deployment status
        for step_name in DEFAULT_STEPS:
            orch.advance_step(d["deployment_id"], step_name)
            orch.advance_step(d["deployment_id"], step_name)
        # Deployment should now be in_progress (first advance set it)
        result = orch.complete_deployment(d["deployment_id"])
        assert result["status"] == "completed"

    def test_no_bus_singleton(self):
        orch = reset_deployment_orchestrator(db_path=":memory:", event_bus=None)
        d = orch.create_deployment("m1", "draft", "build")
        # Should not crash even without event bus
        orch.fail_deployment(d["deployment_id"], "test")
        assert orch.get_deployment(d["deployment_id"])["status"] == "failed"
