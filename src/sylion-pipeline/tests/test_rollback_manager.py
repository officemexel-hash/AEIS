"""
Tests for RollbackManager -- checkpoints, operations, approval, stats,
singleton, thread safety.

Covers all public methods: create_checkpoint, create_auto_checkpoint,
list_rollback_points, get_rollback_point, invalidate_point,
request_rollback, approve_rollback, execute_rollback,
get_rollback_operations, get_rollback_operation, get_rollback_stats.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.governance.rollback_manager import (
    RollbackManager,
    get_rollback_manager,
    reset_rollback_manager,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset global singleton before and after every test."""
    reset_rollback_manager()
    yield
    reset_rollback_manager()


@pytest.fixture
def rm() -> RollbackManager:
    """Fresh in-memory RollbackManager instance."""
    return RollbackManager()


@pytest.fixture
def rm_bus(bus) -> RollbackManager:
    """RollbackManager with EventBus attached."""
    return RollbackManager(event_bus=bus)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _checkpoint(rm, name="test-point", **kwargs):
    """Shorthand to create a rollback point."""
    return rm.create_checkpoint(name=name, **kwargs)


def _states(modules=None):
    """Build a module_states dict for testing."""
    if modules is None:
        modules = {
            "mod_a": {"lifecycle": "stable", "status": "stable", "last_event": 100},
            "mod_b": {"lifecycle": "draft", "status": "draft", "last_event": 50},
        }
    return modules


# ===========================================================================
# TestCreateCheckpoint
# ===========================================================================

class TestCreateCheckpoint:

    def test_returns_point_id(self, rm):
        result = _checkpoint(rm)
        assert "point_id" in result
        assert isinstance(result["point_id"], str)
        assert len(result["point_id"]) == 12

    def test_stores_name(self, rm):
        result = _checkpoint(rm, name="my-checkpoint")
        assert result["name"] == "my-checkpoint"

    def test_stores_description(self, rm):
        result = _checkpoint(rm, description="before risky change")
        assert result["description"] == "before risky change"

    def test_default_description_empty(self, rm):
        result = _checkpoint(rm)
        assert result["description"] == ""

    def test_stores_pipeline_run_id(self, rm):
        result = _checkpoint(rm, pipeline_run_id="RUN-001")
        assert result["pipeline_run_id"] == "RUN-001"

    def test_stores_snapshot_id(self, rm):
        result = _checkpoint(rm, snapshot_id="SNAP-001")
        assert result["snapshot_id"] == "SNAP-001"

    def test_stores_module_states_json(self, rm):
        states = _states()
        result = _checkpoint(rm, module_states=states)
        assert isinstance(result["module_states"], dict)
        assert "mod_a" in result["module_states"]

    def test_stores_config_state(self, rm):
        config = {"threshold": 0.9, "mode": "strict"}
        result = _checkpoint(rm, config_state=config)
        assert isinstance(result["config_state"], dict)
        assert result["config_state"]["threshold"] == 0.9

    def test_point_type_manual_default(self, rm):
        result = _checkpoint(rm)
        assert result["point_type"] == "manual"

    def test_point_type_custom(self, rm):
        result = _checkpoint(rm, point_type="pre_decision")
        assert result["point_type"] == "pre_decision"

    def test_is_valid_default_true(self, rm):
        result = _checkpoint(rm)
        assert result["is_valid"] == 1

    def test_created_at_present(self, rm):
        before = time.time()
        result = _checkpoint(rm)
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_created_by_default_system(self, rm):
        result = _checkpoint(rm)
        assert result["created_by"] == "system"

    def test_emits_created_event(self, bus):
        rm = RollbackManager(event_bus=bus)
        events = []
        bus.subscribe("rollback.point.created", lambda e: events.append(e))
        rm.create_checkpoint(name="ev-test")
        assert len(events) == 1
        assert events[0].payload["name"] == "ev-test"

    def test_multiple_unique_ids(self, rm):
        r1 = _checkpoint(rm, name="cp1")
        r2 = _checkpoint(rm, name="cp2")
        assert r1["point_id"] != r2["point_id"]


# ===========================================================================
# TestCreateAutoCheckpoint
# ===========================================================================

class TestCreateAutoCheckpoint:

    def test_creates_point(self, rm):
        result = rm.create_auto_checkpoint("RUN-AUTO-1")
        assert "point_id" in result
        assert result["pipeline_run_id"] == "RUN-AUTO-1"

    def test_point_type_auto(self, rm):
        result = rm.create_auto_checkpoint("RUN-AUTO-2")
        assert result["point_type"] == "auto_checkpoint"

    def test_name_includes_trigger(self, rm):
        result = rm.create_auto_checkpoint("RUN-XYZ", trigger="pre_step")
        assert "pre_step" in result["name"]
        assert "RUN-XYZ" in result["name"]

    def test_description_includes_trigger(self, rm):
        result = rm.create_auto_checkpoint("RUN-DESC", trigger="post_step")
        assert "post_step" in result["description"]

    def test_custom_trigger(self, rm):
        result = rm.create_auto_checkpoint("RUN-T", trigger="pre_decision")
        assert "pre_decision" in result["name"]


# ===========================================================================
# TestListRollbackPoints
# ===========================================================================

class TestListRollbackPoints:

    def test_empty_list(self, rm):
        assert rm.list_rollback_points() == []

    def test_list_all(self, rm):
        _checkpoint(rm, name="p1")
        _checkpoint(rm, name="p2")
        _checkpoint(rm, name="p3")
        assert len(rm.list_rollback_points()) == 3

    def test_filter_by_type(self, rm):
        _checkpoint(rm, name="m1", point_type="manual")
        _checkpoint(rm, name="m2", point_type="manual")
        _checkpoint(rm, name="a1", point_type="auto_checkpoint")
        manual = rm.list_rollback_points(point_type="manual")
        assert len(manual) == 2
        assert all(p["point_type"] == "manual" for p in manual)

    def test_filter_by_pipeline(self, rm):
        _checkpoint(rm, name="p1", pipeline_run_id="RUN-A")
        _checkpoint(rm, name="p2", pipeline_run_id="RUN-B")
        result = rm.list_rollback_points(pipeline_run_id="RUN-A")
        assert len(result) == 1
        assert result[0]["pipeline_run_id"] == "RUN-A"

    def test_filter_by_valid(self, rm):
        r1 = _checkpoint(rm, name="valid")
        r2 = _checkpoint(rm, name="will-invalidate")
        rm.invalidate_point(r2["point_id"])
        valid = rm.list_rollback_points(is_valid=1)
        invalid = rm.list_rollback_points(is_valid=0)
        assert len(valid) == 1
        assert valid[0]["point_id"] == r1["point_id"]
        assert len(invalid) == 1
        assert invalid[0]["point_id"] == r2["point_id"]

    def test_combined_filters(self, rm):
        _checkpoint(rm, name="a", pipeline_run_id="RUN-X", point_type="manual")
        _checkpoint(rm, name="b", pipeline_run_id="RUN-X", point_type="auto_checkpoint")
        _checkpoint(rm, name="c", pipeline_run_id="RUN-Y", point_type="manual")
        result = rm.list_rollback_points(pipeline_run_id="RUN-X", point_type="manual")
        assert len(result) == 1
        assert result[0]["name"] == "a"


# ===========================================================================
# TestGetRollbackPoint
# ===========================================================================

class TestGetRollbackPoint:

    def test_returns_point(self, rm):
        created = _checkpoint(rm, name="fetch-me")
        fetched = rm.get_rollback_point(created["point_id"])
        assert fetched is not None
        assert fetched["point_id"] == created["point_id"]
        assert fetched["name"] == "fetch-me"

    def test_returns_none_for_missing(self, rm):
        assert rm.get_rollback_point("nonexistent") is None

    def test_json_fields_parsed(self, rm):
        states = {"mod_x": {"lifecycle": "stable"}}
        config = {"key": "val"}
        created = _checkpoint(rm, module_states=states, config_state=config)
        fetched = rm.get_rollback_point(created["point_id"])
        assert isinstance(fetched["module_states"], dict)
        assert isinstance(fetched["config_state"], dict)
        assert "mod_x" in fetched["module_states"]


# ===========================================================================
# TestInvalidatePoint
# ===========================================================================

class TestInvalidatePoint:

    def test_marks_invalid(self, rm):
        created = _checkpoint(rm)
        result = rm.invalidate_point(created["point_id"])
        assert result is not None
        assert result["is_valid"] == 0

    def test_returns_none_for_missing(self, rm):
        assert rm.invalidate_point("nonexistent") is None

    def test_invalid_point_not_listed_as_valid(self, rm):
        created = _checkpoint(rm)
        rm.invalidate_point(created["point_id"])
        valid = rm.list_rollback_points(is_valid=1)
        ids = {p["point_id"] for p in valid}
        assert created["point_id"] not in ids

    def test_emits_invalidated_event(self, bus):
        rm = RollbackManager(event_bus=bus)
        events = []
        bus.subscribe("rollback.point.invalidated", lambda e: events.append(e))
        r = rm.create_checkpoint(name="inv-ev")
        rm.invalidate_point(r["point_id"])
        assert len(events) == 1
        assert events[0].payload["point_id"] == r["point_id"]


# ===========================================================================
# TestRequestRollback
# ===========================================================================

class TestRequestRollback:

    def test_returns_operation(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        assert op is not None
        assert "operation_id" in op
        assert op["point_id"] == point["point_id"]

    def test_operation_type_default(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        assert op["operation_type"] == "full_restore"

    def test_operation_type_custom(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"], operation_type="module_restore")
        assert op["operation_type"] == "module_restore"

    def test_status_pending(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        assert op["status"] == "pending"

    def test_captures_before_state(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        assert isinstance(op["before_state"], dict)
        assert "current_module_states" in op["before_state"]

    def test_target_scope_stored(self, rm):
        point = _checkpoint(rm)
        scope = {"module_ids": ["mod_a", "mod_b"]}
        op = rm.request_rollback(
            point["point_id"],
            operation_type="module_restore",
            target_scope=scope,
        )
        assert isinstance(op["target_scope"], dict)
        assert "mod_a" in op["target_scope"]["module_ids"]

    def test_requires_approval_flag(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(
            point["point_id"],
            requires_approval=True,
        )
        assert op["requires_approval"] == 1

    def test_no_approval_flag(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"], requires_approval=False)
        assert op["requires_approval"] == 0

    def test_returns_none_for_missing_point(self, rm):
        assert rm.request_rollback("nonexistent") is None

    def test_returns_none_for_invalid_point(self, rm):
        point = _checkpoint(rm)
        rm.invalidate_point(point["point_id"])
        assert rm.request_rollback(point["point_id"]) is None

    def test_emits_requested_event(self, bus):
        rm = RollbackManager(event_bus=bus)
        events = []
        bus.subscribe("rollback.operation.requested", lambda e: events.append(e))
        r = rm.create_checkpoint(name="req-ev")
        rm.request_rollback(r["point_id"])
        assert len(events) == 1


# ===========================================================================
# TestApproveRollback
# ===========================================================================

class TestApproveRollback:

    def test_approves_pending(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"], requires_approval=True)
        result = rm.approve_rollback(op["operation_id"], "admin")
        assert result is not None
        assert result["approved_by"] == "admin"
        assert result["approved_at"] is not None

    def test_returns_none_for_missing(self, rm):
        assert rm.approve_rollback("nonexistent", "admin") is None

    def test_returns_none_for_non_pending(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        rm.execute_rollback(op["operation_id"])
        result = rm.approve_rollback(op["operation_id"], "admin")
        assert result is None

    def test_emits_approved_event(self, bus):
        rm = RollbackManager(event_bus=bus)
        events = []
        bus.subscribe("rollback.operation.approved", lambda e: events.append(e))
        r = rm.create_checkpoint(name="appr-ev")
        op = rm.request_rollback(r["point_id"], requires_approval=True)
        rm.approve_rollback(op["operation_id"], "council")
        assert len(events) == 1
        assert events[0].payload["approved_by"] == "council"


# ===========================================================================
# TestExecuteRollback
# ===========================================================================

class TestExecuteRollback:

    def test_full_restore_completes(self, rm):
        states = _states()
        point = _checkpoint(rm, module_states=states)
        op = rm.request_rollback(point["point_id"], operation_type="full_restore")
        result = rm.execute_rollback(op["operation_id"])
        assert result is not None
        assert result["status"] == "completed"
        assert result["after_state"]["restored_module_states"] == states

    def test_module_restore_completes(self, rm):
        states = _states()
        point = _checkpoint(rm, module_states=states)
        scope = {"module_ids": ["mod_a"]}
        op = rm.request_rollback(
            point["point_id"],
            operation_type="module_restore",
            target_scope=scope,
        )
        result = rm.execute_rollback(op["operation_id"])
        assert result["status"] == "completed"
        assert "mod_a" in result["after_state"]["restored_modules"]
        assert "mod_b" not in result["after_state"]["restored_modules"]

    def test_config_restore_completes(self, rm):
        config = {"threshold": 0.95, "mode": "strict"}
        point = _checkpoint(rm, config_state=config)
        op = rm.request_rollback(point["point_id"], operation_type="config_restore")
        result = rm.execute_rollback(op["operation_id"])
        assert result["status"] == "completed"
        assert result["after_state"]["restored_config"]["threshold"] == 0.95

    def test_decision_revert_no_snapshot_fails(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"], operation_type="decision_revert")
        result = rm.execute_rollback(op["operation_id"])
        assert result["status"] == "failed"
        assert result["error_message"] is not None

    def test_returns_none_for_missing(self, rm):
        assert rm.execute_rollback("nonexistent") is None

    def test_returns_none_if_not_pending(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        rm.execute_rollback(op["operation_id"])
        result = rm.execute_rollback(op["operation_id"])
        assert result is None

    def test_returns_none_if_approval_required_but_missing(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"], requires_approval=True)
        result = rm.execute_rollback(op["operation_id"])
        assert result is None

    def test_executes_after_approval(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"], requires_approval=True)
        rm.approve_rollback(op["operation_id"], "admin")
        result = rm.execute_rollback(op["operation_id"])
        assert result is not None
        assert result["status"] == "completed"

    def test_sets_completed_at(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        result = rm.execute_rollback(op["operation_id"])
        assert result["completed_at"] is not None

    def test_sets_started_at(self, rm):
        point = _checkpoint(rm)
        op = rm.request_rollback(point["point_id"])
        result = rm.execute_rollback(op["operation_id"])
        assert result["started_at"] is not None

    def test_module_restore_missing_module_empty(self, rm):
        states = _states()
        point = _checkpoint(rm, module_states=states)
        scope = {"module_ids": ["nonexistent_mod"]}
        op = rm.request_rollback(
            point["point_id"],
            operation_type="module_restore",
            target_scope=scope,
        )
        result = rm.execute_rollback(op["operation_id"])
        assert result["status"] == "completed"
        assert result["after_state"]["restored_modules"] == {}

    def test_emits_completed_event(self, bus):
        rm = RollbackManager(event_bus=bus)
        events = []
        bus.subscribe("rollback.operation.completed", lambda e: events.append(e))
        r = rm.create_checkpoint(name="exec-ev", module_states=_states())
        op = rm.request_rollback(r["point_id"])
        rm.execute_rollback(op["operation_id"])
        assert len(events) == 1
        assert events[0].payload["operation_type"] == "full_restore"


# ===========================================================================
# TestGetRollbackOperations
# ===========================================================================

class TestGetRollbackOperations:

    def test_empty_list(self, rm):
        assert rm.get_rollback_operations() == []

    def test_list_all(self, rm):
        p1 = _checkpoint(rm, name="p1")
        p2 = _checkpoint(rm, name="p2")
        rm.request_rollback(p1["point_id"])
        rm.request_rollback(p2["point_id"])
        assert len(rm.get_rollback_operations()) == 2

    def test_filter_by_point_id(self, rm):
        p1 = _checkpoint(rm, name="p1")
        p2 = _checkpoint(rm, name="p2")
        rm.request_rollback(p1["point_id"])
        rm.request_rollback(p2["point_id"])
        ops = rm.get_rollback_operations(point_id=p1["point_id"])
        assert len(ops) == 1
        assert ops[0]["point_id"] == p1["point_id"]

    def test_filter_by_status(self, rm):
        p1 = _checkpoint(rm, name="p1")
        p2 = _checkpoint(rm, name="p2")
        op1 = rm.request_rollback(p1["point_id"])
        rm.request_rollback(p2["point_id"])
        rm.execute_rollback(op1["operation_id"])
        completed = rm.get_rollback_operations(status="completed")
        pending = rm.get_rollback_operations(status="pending")
        assert len(completed) == 1
        assert len(pending) == 1


# ===========================================================================
# TestGetRollbackOperation
# ===========================================================================

class TestGetRollbackOperation:

    def test_returns_operation(self, rm):
        point = _checkpoint(rm)
        created = rm.request_rollback(point["point_id"])
        fetched = rm.get_rollback_operation(created["operation_id"])
        assert fetched is not None
        assert fetched["operation_id"] == created["operation_id"]

    def test_returns_none_for_missing(self, rm):
        assert rm.get_rollback_operation("nonexistent") is None


# ===========================================================================
# TestGetRollbackStats
# ===========================================================================

class TestGetRollbackStats:

    def test_empty_stats(self, rm):
        stats = rm.get_rollback_stats()
        assert stats["total_points"] == 0
        assert stats["total_operations"] == 0
        assert stats["by_status"] == {}
        assert stats["by_type"] == {}
        assert stats["success_rate"] == 0.0

    def test_counts_points(self, rm):
        _checkpoint(rm, name="s1")
        _checkpoint(rm, name="s2")
        _checkpoint(rm, name="s3")
        stats = rm.get_rollback_stats()
        assert stats["total_points"] == 3

    def test_counts_operations_by_status(self, rm):
        p1 = _checkpoint(rm, name="s1")
        p2 = _checkpoint(rm, name="s2")
        op1 = rm.request_rollback(p1["point_id"])
        rm.request_rollback(p2["point_id"])
        rm.execute_rollback(op1["operation_id"])
        stats = rm.get_rollback_stats()
        assert stats["total_operations"] == 2
        assert stats["by_status"]["completed"] == 1
        assert stats["by_status"]["pending"] == 1

    def test_counts_by_type(self, rm):
        p1 = _checkpoint(rm, name="s1")
        p2 = _checkpoint(rm, name="s2")
        rm.request_rollback(p1["point_id"], operation_type="full_restore")
        rm.request_rollback(p2["point_id"], operation_type="module_restore")
        stats = rm.get_rollback_stats()
        assert stats["by_type"]["full_restore"] == 1
        assert stats["by_type"]["module_restore"] == 1

    def test_success_rate_100(self, rm):
        p1 = _checkpoint(rm, name="s1")
        op = rm.request_rollback(p1["point_id"])
        rm.execute_rollback(op["operation_id"])
        stats = rm.get_rollback_stats()
        assert stats["success_rate"] == 100.0

    def test_success_rate_zero(self, rm):
        # Create a point without snapshot_id to force decision_revert failure
        p = _checkpoint(rm, name="fail-pt")
        op = rm.request_rollback(p["point_id"], operation_type="decision_revert")
        rm.execute_rollback(op["operation_id"])
        stats = rm.get_rollback_stats()
        assert stats["success_rate"] == 0.0

    def test_success_rate_mixed(self, rm):
        p1 = _checkpoint(rm, name="ok", module_states=_states())
        p2 = _checkpoint(rm, name="fail")
        op1 = rm.request_rollback(p1["point_id"])
        op2 = rm.request_rollback(p2["point_id"], operation_type="decision_revert")
        rm.execute_rollback(op1["operation_id"])
        rm.execute_rollback(op2["operation_id"])
        stats = rm.get_rollback_stats()
        assert stats["success_rate"] == 50.0


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        assert isinstance(get_rollback_manager(), RollbackManager)

    def test_idempotent(self):
        a = get_rollback_manager()
        b = get_rollback_manager()
        assert a is b

    def test_reset_creates_new(self):
        a = get_rollback_manager()
        b = reset_rollback_manager()
        assert a is not b
        assert isinstance(b, RollbackManager)


# ===========================================================================
# TestEndToEndRollbackFlow
# ===========================================================================

class TestEndToEndRollbackFlow:

    def test_full_lifecycle(self, rm):
        """Create checkpoint -> request -> approve -> execute -> verify stats."""
        states = {"auth": {"lifecycle": "stable"}, "db": {"lifecycle": "stable"}}
        config = {"timeout": 30, "retries": 3}

        # Create checkpoint
        point = rm.create_checkpoint(
            name="pre-deploy",
            description="before risky deployment",
            module_states=states,
            config_state=config,
            point_type="pre_change",
        )
        assert point["point_type"] == "pre_change"
        assert point["is_valid"] == 1

        # Request rollback with approval
        op = rm.request_rollback(
            point["point_id"],
            operation_type="full_restore",
            requires_approval=True,
        )
        assert op["status"] == "pending"
        assert op["requires_approval"] == 1

        # Approve
        approved = rm.approve_rollback(op["operation_id"], "council_lead")
        assert approved["approved_by"] == "council_lead"

        # Execute
        result = rm.execute_rollback(op["operation_id"])
        assert result["status"] == "completed"
        assert result["after_state"]["restored_module_states"] == states
        assert result["after_state"]["restored_config"] == config

        # Verify stats
        stats = rm.get_rollback_stats()
        assert stats["total_points"] == 1
        assert stats["total_operations"] == 1
        assert stats["by_status"]["completed"] == 1
        assert stats["success_rate"] == 100.0

    def test_selective_module_restore(self, rm):
        """Restore only specific modules from a checkpoint."""
        states = {
            "auth": {"lifecycle": "stable"},
            "db": {"lifecycle": "stable"},
            "cache": {"lifecycle": "draft"},
        }
        point = rm.create_checkpoint(
            name="selective",
            module_states=states,
        )
        scope = {"module_ids": ["auth", "cache"]}
        op = rm.request_rollback(
            point["point_id"],
            operation_type="module_restore",
            target_scope=scope,
        )
        result = rm.execute_rollback(op["operation_id"])
        assert result["status"] == "completed"
        restored = result["after_state"]["restored_modules"]
        assert "auth" in restored
        assert "cache" in restored
        assert "db" not in restored

    def test_auto_checkpoint_and_restore(self, rm):
        """Auto-checkpoint before pipeline step and rollback."""
        point = rm.create_auto_checkpoint("RUN-42", trigger="pre_step")
        assert point["point_type"] == "auto_checkpoint"

        op = rm.request_rollback(point["point_id"])
        result = rm.execute_rollback(op["operation_id"])
        assert result["status"] == "completed"

    def test_invalidate_prevents_rollback(self, rm):
        """Invalidating a point prevents new rollback requests."""
        point = _checkpoint(rm)
        rm.invalidate_point(point["point_id"])
        assert rm.request_rollback(point["point_id"]) is None


# ===========================================================================
# TestThreadSafety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_checkpoints(self):
        rm = RollbackManager()
        results = []
        errors = []

        def create(i):
            try:
                r = rm.create_checkpoint(name=f"cp-{i}", module_states={"m": {"v": i}})
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
        ids = {r["point_id"] for r in results}
        assert len(ids) == 20

    def test_concurrent_requests(self):
        rm = RollbackManager()
        point = rm.create_checkpoint(name="conc", module_states=_states())
        results = []
        errors = []

        def request(i):
            try:
                r = rm.request_rollback(
                    point["point_id"],
                    operation_type="full_restore",
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=request, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        ids = {r["operation_id"] for r in results}
        assert len(ids) == 10

    def test_concurrent_execute_and_read(self):
        rm = RollbackManager()
        point = rm.create_checkpoint(name="rw", module_states=_states())
        op = rm.request_rollback(point["point_id"])
        errors = []

        def execute():
            try:
                rm.execute_rollback(op["operation_id"])
            except Exception as e:
                errors.append(e)

        def read():
            try:
                rm.get_rollback_stats()
                rm.list_rollback_points()
                rm.get_rollback_operations()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=execute),
            threading.Thread(target=read),
            threading.Thread(target=read),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
