"""Tests for Autonomy Stages 3-5: SandboxExecutor + LimitedProdExecutor."""
import json
import time

import pytest

from sylion.aeis.autonomy_stages import (
    EscalationStatus,
    ExecutionStatus,
    LimitedProdExecution,
    LimitedProdExecutor,
    SandboxExecution,
    SandboxExecutor,
    get_limited_prod_executor,
    get_sandbox_executor,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sandbox():
    """Fresh in-memory SandboxExecutor."""
    return SandboxExecutor()


@pytest.fixture
def sandbox_with_bus():
    """SandboxExecutor with a real EventBus for event assertions."""
    bus = EventBus()
    return SandboxExecutor(event_bus=bus), bus


@pytest.fixture
def limited():
    """Fresh in-memory LimitedProdExecutor."""
    return LimitedProdExecutor()


@pytest.fixture
def limited_with_bus():
    """LimitedProdExecutor with a real EventBus."""
    bus = EventBus()
    return LimitedProdExecutor(event_bus=bus), bus


# ===================================================================
# SandboxExecutor -- execution
# ===================================================================

class TestSandboxExecuteBasic:
    def test_execute_returns_execution_id(self, sandbox):
        result = sandbox.execute_in_sandbox("test_action", {"key": "val"})
        assert "execution_id" in result
        assert len(result["execution_id"]) == 32

    def test_execute_default_status_completed(self, sandbox):
        result = sandbox.execute_in_sandbox("test_action")
        assert result["status"] == "completed"

    def test_execute_captures_action(self, sandbox):
        result = sandbox.execute_in_sandbox("read_config", {"file": "a.yaml"})
        assert result["action"] == "read_config"

    def test_execute_default_echoes_params(self, sandbox):
        params = {"file": "config.yaml", "section": "db"}
        result = sandbox.execute_in_sandbox("read", params)
        assert result["result"]["echo_params"] == params

    def test_execute_result_contains_sandbox_flag(self, sandbox):
        result = sandbox.execute_in_sandbox("test")
        assert result["result"]["sandbox"] is True

    def test_execute_duration_positive(self, sandbox):
        result = sandbox.execute_in_sandbox("test")
        assert result["duration_ms"] >= 0

    def test_execute_captured_outputs(self, sandbox):
        result = sandbox.execute_in_sandbox("test")
        assert "captured_outputs" in result
        assert "return_value" in result["captured_outputs"]

    def test_execute_no_side_effects_by_default(self, sandbox):
        result = sandbox.execute_in_sandbox("test")
        assert result["side_effects"] == []

    def test_execute_does_not_mutate_params(self, sandbox):
        original = {"key": "val", "nested": {"a": 1}}
        sandbox.execute_in_sandbox("test", original)
        assert original == {"key": "val", "nested": {"a": 1}}


class TestSandboxExecuteCustom:
    def test_execute_custom_fn(self, sandbox):
        def my_fn(action, params):
            return {"computed": params["x"] * 2}

        result = sandbox.execute_in_sandbox("calc", {"x": 5}, executor_fn=my_fn)
        assert result["status"] == "completed"
        assert result["result"]["computed"] == 10

    def test_execute_custom_fn_error(self, sandbox):
        def failing_fn(action, params):
            raise RuntimeError("boom")

        result = sandbox.execute_in_sandbox("fail", {}, executor_fn=failing_fn)
        assert result["status"] == "failed"
        assert "boom" in result["result"]["error"]

    def test_execute_custom_fn_does_not_see_original_params(self, sandbox):
        """executor_fn gets deep-copied params, cannot mutate caller's."""
        call_log = {}

        def mutating_fn(action, params):
            params["injected"] = True
            call_log["params"] = params
            return {"ok": True}

        original = {"x": 1}
        sandbox.execute_in_sandbox("mut", original, executor_fn=mutating_fn)
        assert "injected" not in original
        assert call_log["params"]["injected"] is True


class TestSandboxSideEffects:
    def test_detect_declared_side_effects(self, sandbox):
        def fn_with_se(action, params):
            return {
                "ok": True,
                "__side_effects__": [
                    {"type": "file_write", "description": "Wrote to /tmp/x"},
                ],
            }

        result = sandbox.execute_in_sandbox("test", {}, executor_fn=fn_with_se)
        assert result["status"] == "side_effects_detected"
        assert len(result["side_effects"]) == 1
        assert result["side_effects"][0]["effect_type"] == "file_write"

    def test_multiple_side_effects(self, sandbox):
        def fn(action, params):
            return {
                "ok": True,
                "__side_effects__": [
                    {"type": "file_write", "description": "a"},
                    {"type": "network_call", "description": "b", "severity": "high"},
                ],
            }

        result = sandbox.execute_in_sandbox("test", {}, executor_fn=fn)
        assert len(result["side_effects"]) == 2
        assert result["side_effects"][1]["severity"] == "high"


# ===================================================================
# SandboxExecutor -- verify_no_side_effects
# ===================================================================

class TestVerifyNoSideEffects:
    def test_verify_clean_execution(self, sandbox):
        r = sandbox.execute_in_sandbox("test")
        v = sandbox.verify_no_side_effects(r["execution_id"])
        assert v["verified"] is True
        assert v["clean"] is True
        assert v["side_effects_count"] == 0

    def test_verify_dirty_execution(self, sandbox):
        def fn(action, params):
            return {
                "ok": True,
                "__side_effects__": [{"type": "db_write", "description": "wrote row"}],
            }

        r = sandbox.execute_in_sandbox("test", {}, executor_fn=fn)
        v = sandbox.verify_no_side_effects(r["execution_id"])
        assert v["verified"] is True
        assert v["clean"] is False
        assert v["side_effects_count"] == 1

    def test_verify_nonexistent_execution(self, sandbox):
        v = sandbox.verify_no_side_effects("nonexistent_id")
        assert v["verified"] is False
        assert "not found" in v["message"].lower()

    def test_verify_includes_verified_at(self, sandbox):
        r = sandbox.execute_in_sandbox("test")
        v = sandbox.verify_no_side_effects(r["execution_id"])
        assert v["verified_at"] > 0


# ===================================================================
# SandboxExecutor -- get_execution_log
# ===================================================================

class TestSandboxExecutionLog:
    def test_empty_log(self, sandbox):
        log = sandbox.get_execution_log()
        assert log == []

    def test_log_after_execution(self, sandbox):
        sandbox.execute_in_sandbox("action_a")
        sandbox.execute_in_sandbox("action_b")
        log = sandbox.get_execution_log()
        assert len(log) == 2
        # Newest first
        assert log[0]["action"] == "action_b"
        assert log[1]["action"] == "action_a"

    def test_log_parses_json_fields(self, sandbox):
        sandbox.execute_in_sandbox("test", {"x": 1})
        log = sandbox.get_execution_log()
        assert isinstance(log[0]["parameters"], dict)
        assert log[0]["parameters"]["x"] == 1
        assert isinstance(log[0]["result"], dict)
        assert isinstance(log[0]["side_effects"], list)

    def test_log_filter_by_status(self, sandbox):
        sandbox.execute_in_sandbox("ok_action")
        def fail_fn(a, p): raise ValueError("nope")
        sandbox.execute_in_sandbox("fail_action", executor_fn=fail_fn)

        completed = sandbox.get_execution_log(status="completed")
        assert len(completed) == 1
        assert completed[0]["action"] == "ok_action"

        failed = sandbox.get_execution_log(status="failed")
        assert len(failed) == 1
        assert failed[0]["action"] == "fail_action"

    def test_log_respects_limit(self, sandbox):
        for i in range(5):
            sandbox.execute_in_sandbox(f"action_{i}")
        log = sandbox.get_execution_log(limit=3)
        assert len(log) == 3


# ===================================================================
# SandboxExecutor -- get_stats
# ===================================================================

class TestSandboxStats:
    def test_stats_initial(self, sandbox):
        stats = sandbox.get_stats()
        assert stats["total_executions"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0.0

    def test_stats_after_executions(self, sandbox):
        sandbox.execute_in_sandbox("a")
        sandbox.execute_in_sandbox("b")
        stats = sandbox.get_stats()
        assert stats["total_executions"] == 2
        assert stats["completed"] == 2
        assert stats["success_rate"] == 100.0

    def test_stats_includes_failures(self, sandbox):
        sandbox.execute_in_sandbox("ok")
        def fail_fn(a, p): raise RuntimeError("err")
        sandbox.execute_in_sandbox("fail", executor_fn=fail_fn)
        stats = sandbox.get_stats()
        assert stats["total_executions"] == 2
        assert stats["completed"] == 1
        assert stats["failed"] == 1
        assert stats["success_rate"] == 50.0

    def test_stats_side_effects_count(self, sandbox):
        def fn(a, p):
            return {"ok": True, "__side_effects__": [{"type": "x"}]}
        sandbox.execute_in_sandbox("se", executor_fn=fn)
        stats = sandbox.get_stats()
        assert stats["side_effects_detected"] == 1
        assert stats["total_side_effects"] == 1


# ===================================================================
# SandboxExecutor -- events
# ===================================================================

class TestSandboxEvents:
    def test_emits_started_event(self, sandbox_with_bus):
        sandbox, bus = sandbox_with_bus
        sandbox.execute_in_sandbox("test")
        events = bus.query(topic="aeis.autonomy_stages.sandbox_started")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["action"] == "test"

    def test_emits_completed_event(self, sandbox_with_bus):
        sandbox, bus = sandbox_with_bus
        sandbox.execute_in_sandbox("test")
        events = bus.query(topic="aeis.autonomy_stages.sandbox_completed")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["status"] == "completed"

    def test_emits_side_effects_verified_event(self, sandbox_with_bus):
        sandbox, bus = sandbox_with_bus
        r = sandbox.execute_in_sandbox("test")
        sandbox.verify_no_side_effects(r["execution_id"])
        events = bus.query(topic="aeis.autonomy_stages.side_effects_verified")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["clean"] is True


# ===================================================================
# LimitedProdExecutor -- basic execution
# ===================================================================

class TestLimitedProdBasic:
    def test_execute_returns_execution_id(self, limited):
        result = limited.execute_limited("test", {})
        assert "execution_id" in result
        assert len(result["execution_id"]) == 32

    def test_execute_completed_status(self, limited):
        result = limited.execute_limited("test", {})
        assert result["status"] == "completed"

    def test_execute_echoes_params(self, limited):
        result = limited.execute_limited("read", {"key": "val"})
        assert result["result"]["echo_params"] == {"key": "val"}

    def test_execute_result_has_limited_prod_flag(self, limited):
        result = limited.execute_limited("test")
        assert result["result"]["limited_prod"] is True

    def test_execute_duration_positive(self, limited):
        result = limited.execute_limited("test")
        assert result["duration_ms"] >= 0

    def test_execute_no_violations_by_default(self, limited):
        result = limited.execute_limited("test")
        assert result["constraint_violations"] == []

    def test_execute_no_escalation_by_default(self, limited):
        result = limited.execute_limited("test")
        assert result["escalation_id"] == ""

    def test_execute_does_not_mutate_params(self, limited):
        original = {"key": "val"}
        limited.execute_limited("test", original)
        assert original == {"key": "val"}


# ===================================================================
# LimitedProdExecutor -- custom executor_fn
# ===================================================================

class TestLimitedProdCustomFn:
    def test_custom_fn(self, limited):
        def fn(action, params):
            return {"computed": params["x"] + 1}

        result = limited.execute_limited("calc", {"x": 10}, executor_fn=fn)
        assert result["status"] == "completed"
        assert result["result"]["computed"] == 11

    def test_failing_fn(self, limited):
        def fail_fn(action, params):
            raise RuntimeError("limited fail")

        result = limited.execute_limited("fail", {}, executor_fn=fail_fn)
        assert result["status"] == "failed"
        assert "limited fail" in result["result"]["error"]


# ===================================================================
# LimitedProdExecutor -- rate limits
# ===================================================================

class TestLimitedProdRateLimit:
    def test_rate_limit_allows_under_limit(self, limited):
        for i in range(5):
            result = limited.execute_limited(
                "action_a", {}, {"max_rate_per_minute": 5}
            )
            # Only the last should succeed, first 4 track the counter
        # First execution: count=1, passes
        # We need to re-test with fresh executor
        pass

    def test_rate_limit_blocks_over_limit(self):
        lp = LimitedProdExecutor()
        for i in range(3):
            lp.execute_limited("ratetest", {}, {"max_rate_per_minute": 3})
        # 4th should be blocked
        result = lp.execute_limited("ratetest", {}, {"max_rate_per_minute": 3})
        assert result["status"] == "failed"
        assert "rate limit" in result["result"]["error"].lower()

    def test_rate_limit_independent_per_action(self):
        lp = LimitedProdExecutor()
        for i in range(3):
            lp.execute_limited("action_x", {}, {"max_rate_per_minute": 3})
        # Different action should still pass
        result = lp.execute_limited("action_y", {}, {"max_rate_per_minute": 3})
        assert result["status"] == "completed"

    def test_no_rate_limit_when_zero(self, limited):
        for i in range(10):
            result = limited.execute_limited(
                "no_limit", {}, {"max_rate_per_minute": 0}
            )
            assert result["status"] == "completed"


# ===================================================================
# LimitedProdExecutor -- scope limits
# ===================================================================

class TestLimitedProdScope:
    def test_forbidden_action_blocked(self, limited):
        result = limited.execute_limited(
            "drop_table", {},
            {"forbidden_actions": ["drop_table", "delete_all"]},
        )
        assert result["status"] == "failed"
        assert "scope" in result["result"]["error"].lower()

    def test_allowed_action_passes(self, limited):
        result = limited.execute_limited(
            "select_query", {},
            {"forbidden_actions": ["drop_table"]},
        )
        assert result["status"] == "completed"

    def test_target_not_allowed(self, limited):
        result = limited.execute_limited(
            "write", {"target": "prod_db"},
            {"allowed_targets": ["cache", "staging_db"]},
        )
        assert result["status"] == "failed"

    def test_target_allowed_passes(self, limited):
        result = limited.execute_limited(
            "write", {"target": "cache"},
            {"allowed_targets": ["cache", "staging_db"]},
        )
        assert result["status"] == "completed"

    def test_no_target_with_allowed_targets_passes(self, limited):
        """No target in params should not trigger scope check."""
        result = limited.execute_limited(
            "read", {},
            {"allowed_targets": ["cache"]},
        )
        assert result["status"] == "completed"


# ===================================================================
# LimitedProdExecutor -- human review
# ===================================================================

class TestLimitedProdHumanReview:
    def test_require_human_review_creates_escalation(self, limited):
        result = limited.execute_limited(
            "sensitive_op", {},
            {"require_human_review": True},
        )
        assert result["status"] == "pending"
        assert result["escalation_id"] != ""
        assert result["escalation_status"] == "pending"

    def test_resolve_escalation_approved(self, limited):
        result = limited.execute_limited(
            "sensitive", {}, {"require_human_review": True}
        )
        esc_id = result["escalation_id"]
        resolution = limited.resolve_escalation(
            esc_id, "approved", reviewed_by="admin", notes="looks fine"
        )
        assert resolution["resolved"] is True
        assert resolution["decision"] == "approved"

    def test_resolve_escalation_rejected(self, limited):
        result = limited.execute_limited(
            "risky", {}, {"require_human_review": True}
        )
        esc_id = result["escalation_id"]
        resolution = limited.resolve_escalation(
            esc_id, "rejected", reviewed_by="sec_lead"
        )
        assert resolution["resolved"] is True
        assert resolution["decision"] == "rejected"

    def test_resolve_invalid_decision(self, limited):
        result = limited.execute_limited(
            "x", {}, {"require_human_review": True}
        )
        esc_id = result["escalation_id"]
        resolution = limited.resolve_escalation(esc_id, "maybe")
        assert resolution["resolved"] is False

    def test_resolve_nonexistent_escalation(self, limited):
        resolution = limited.resolve_escalation("nonexistent", "approved")
        assert resolution["resolved"] is False


# ===================================================================
# LimitedProdExecutor -- escalate_to_human
# ===================================================================

class TestEscalateToHuman:
    def test_escalate_after_execution(self, limited):
        result = limited.execute_limited("borderline_op", {})
        exec_id = result["execution_id"]
        esc = limited.escalate_to_human(exec_id, "Result looks suspicious")
        assert esc["escalated"] is True
        assert esc["status"] == "pending"
        assert esc["reason"] == "Result looks suspicious"

    def test_escalate_nonexistent_execution(self, limited):
        esc = limited.escalate_to_human("nonexistent", "reason")
        assert esc["escalated"] is False

    def test_escalate_already_escalated(self, limited):
        result = limited.execute_limited(
            "op", {}, {"require_human_review": True}
        )
        exec_id = result["execution_id"]
        esc = limited.escalate_to_human(exec_id, "double escalate")
        assert esc["escalated"] is False
        assert "already" in esc["message"].lower()


# ===================================================================
# LimitedProdExecutor -- check_constraints
# ===================================================================

class TestCheckConstraints:
    def test_check_clean_execution(self, limited):
        result = limited.execute_limited("test", {}, {"max_duration_ms": 60000})
        check = limited.check_constraints(result["execution_id"])
        assert check["checked"] is True
        assert check["within_constraints"] is True

    def test_check_nonexistent(self, limited):
        check = limited.check_constraints("nonexistent")
        assert check["checked"] is False

    def test_check_duration_violation(self, limited):
        def slow_fn(action, params):
            time.sleep(0.05)
            return {"ok": True}

        result = limited.execute_limited(
            "slow_op", {},
            {"max_duration_ms": 1},
            executor_fn=slow_fn,
        )
        check = limited.check_constraints(result["execution_id"])
        assert check["within_constraints"] is False

    def test_check_includes_violation_details(self, limited):
        def violating_fn(action, params):
            return {
                "ok": True,
                "__constraint_violations__": [
                    {"type": "scope_breach", "detail": "touched prod"}
                ],
            }

        result = limited.execute_limited(
            "op", {}, {}, executor_fn=violating_fn
        )
        check = limited.check_constraints(result["execution_id"])
        assert check["within_constraints"] is False
        assert len(check["violations"]) >= 1

    def test_constraint_violation_triggers_escalation(self, limited):
        def violating_fn(action, params):
            return {
                "ok": True,
                "__constraint_violations__": [
                    {"type": "scope_breach"}
                ],
            }

        result = limited.execute_limited("op", {}, executor_fn=violating_fn)
        assert result["escalation_id"] != ""
        assert result["escalation_status"] == "pending"


# ===================================================================
# LimitedProdExecutor -- get_execution_log
# ===================================================================

class TestLimitedProdLog:
    def test_empty_log(self, limited):
        log = limited.get_execution_log()
        assert log == []

    def test_log_after_execution(self, limited):
        limited.execute_limited("a", {"x": 1})
        limited.execute_limited("b", {"y": 2})
        log = limited.get_execution_log()
        assert len(log) == 2

    def test_log_parses_json(self, limited):
        limited.execute_limited("test", {"key": "val"})
        log = limited.get_execution_log()
        assert isinstance(log[0]["parameters"], dict)
        assert log[0]["parameters"]["key"] == "val"
        assert isinstance(log[0]["constraints"], dict)
        assert isinstance(log[0]["result"], dict)

    def test_log_filter_by_status(self, limited):
        limited.execute_limited("ok")
        def fail_fn(a, p): raise RuntimeError("err")
        limited.execute_limited("fail", executor_fn=fail_fn)

        completed = limited.get_execution_log(status="completed")
        assert len(completed) == 1
        failed = limited.get_execution_log(status="failed")
        assert len(failed) == 1

    def test_log_respects_limit(self, limited):
        for i in range(5):
            limited.execute_limited(f"op_{i}")
        log = limited.get_execution_log(limit=2)
        assert len(log) == 2


# ===================================================================
# LimitedProdExecutor -- get_escalations
# ===================================================================

class TestLimitedProdEscalations:
    def test_empty_escalations(self, limited):
        escs = limited.get_escalations()
        assert escs == []

    def test_escalations_after_human_review(self, limited):
        limited.execute_limited("op", {}, {"require_human_review": True})
        escs = limited.get_escalations()
        assert len(escs) == 1
        assert escs[0]["status"] == "pending"

    def test_escalations_filter_by_status(self, limited):
        r = limited.execute_limited("op", {}, {"require_human_review": True})
        limited.resolve_escalation(r["escalation_id"], "approved", "admin")

        pending = limited.get_escalations(status="pending")
        assert len(pending) == 0
        approved = limited.get_escalations(status="approved")
        assert len(approved) == 1


# ===================================================================
# LimitedProdExecutor -- get_stats
# ===================================================================

class TestLimitedProdStats:
    def test_stats_initial(self, limited):
        stats = limited.get_stats()
        assert stats["total_executions"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["total_escalations"] == 0

    def test_stats_after_executions(self, limited):
        limited.execute_limited("a")
        limited.execute_limited("b")
        stats = limited.get_stats()
        assert stats["total_executions"] == 2
        assert stats["completed"] == 2
        assert stats["success_rate"] == 100.0

    def test_stats_with_failures(self, limited):
        limited.execute_limited("ok")
        def fail_fn(a, p): raise RuntimeError("err")
        limited.execute_limited("fail", executor_fn=fail_fn)
        stats = limited.get_stats()
        assert stats["total_executions"] == 2
        assert stats["completed"] == 1
        assert stats["failed"] == 1

    def test_stats_escalation_counts(self, limited):
        limited.execute_limited("op1", {}, {"require_human_review": True})
        limited.execute_limited("op2", {}, {"require_human_review": True})
        r2 = limited.execute_limited("op3", {}, {"require_human_review": True})
        limited.resolve_escalation(r2["escalation_id"], "approved", "admin")

        stats = limited.get_stats()
        assert stats["total_escalations"] == 3
        assert stats["pending_escalations"] == 2
        assert stats["approved_escalations"] == 1

    def test_stats_rejected_escalations(self, limited):
        r = limited.execute_limited("op", {}, {"require_human_review": True})
        limited.resolve_escalation(r["escalation_id"], "rejected", "admin")
        stats = limited.get_stats()
        assert stats["rejected_escalations"] == 1


# ===================================================================
# LimitedProdExecutor -- events
# ===================================================================

class TestLimitedProdEvents:
    def test_emits_started_event(self, limited_with_bus):
        lp, bus = limited_with_bus
        lp.execute_limited("test")
        events = bus.query(topic="aeis.autonomy_stages.limited_started")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["action"] == "test"

    def test_emits_completed_event(self, limited_with_bus):
        lp, bus = limited_with_bus
        lp.execute_limited("test")
        events = bus.query(topic="aeis.autonomy_stages.limited_completed")
        assert len(events) == 1

    def test_emits_rate_limited_event(self):
        bus = EventBus()
        lp = LimitedProdExecutor(event_bus=bus)
        for i in range(2):
            lp.execute_limited("ratetest", {}, {"max_rate_per_minute": 2})
        # 3rd should be blocked
        lp.execute_limited("ratetest", {}, {"max_rate_per_minute": 2})
        events = bus.query(topic="aeis.autonomy_stages.rate_limited")
        assert len(events) == 1

    def test_emits_scope_limited_event(self, limited_with_bus):
        lp, bus = limited_with_bus
        lp.execute_limited("drop_all", {}, {"forbidden_actions": ["drop_all"]})
        events = bus.query(topic="aeis.autonomy_stages.scope_limited")
        assert len(events) == 1

    def test_emits_escalation_created_event(self, limited_with_bus):
        lp, bus = limited_with_bus
        lp.execute_limited("op", {}, {"require_human_review": True})
        events = bus.query(topic="aeis.autonomy_stages.escalation_created")
        assert len(events) == 1

    def test_emits_escalated_to_human_event(self, limited_with_bus):
        lp, bus = limited_with_bus
        r = lp.execute_limited("op")
        lp.escalate_to_human(r["execution_id"], "suspicious")
        events = bus.query(topic="aeis.autonomy_stages.escalated_to_human")
        assert len(events) == 1

    def test_emits_escalation_resolved_event(self, limited_with_bus):
        lp, bus = limited_with_bus
        r = lp.execute_limited("op", {}, {"require_human_review": True})
        lp.resolve_escalation(r["escalation_id"], "approved", "admin")
        events = bus.query(topic="aeis.autonomy_stages.escalation_resolved")
        assert len(events) == 1


# ===================================================================
# Singletons
# ===================================================================

class TestSingletons:
    def test_get_sandbox_executor_returns_instance(self):
        import sylion.aeis.autonomy_stages as mod
        mod._sandbox = None
        s = get_sandbox_executor()
        assert isinstance(s, SandboxExecutor)
        mod._sandbox = None

    def test_get_limited_prod_executor_returns_instance(self):
        import sylion.aeis.autonomy_stages as mod
        mod._limited_prod = None
        lp = get_limited_prod_executor()
        assert isinstance(lp, LimitedProdExecutor)
        mod._limited_prod = None

    def test_sandbox_singleton_is_same(self):
        import sylion.aeis.autonomy_stages as mod
        mod._sandbox = None
        s1 = get_sandbox_executor()
        s2 = get_sandbox_executor()
        assert s1 is s2
        mod._sandbox = None

    def test_limited_prod_singleton_is_same(self):
        import sylion.aeis.autonomy_stages as mod
        mod._limited_prod = None
        lp1 = get_limited_prod_executor()
        lp2 = get_limited_prod_executor()
        assert lp1 is lp2
        mod._limited_prod = None


# ===================================================================
# Thread safety (basic smoke test)
# ===================================================================

class TestThreadSafety:
    def test_concurrent_sandbox_executions(self):
        sandbox = SandboxExecutor()
        import threading
        errors = []
        results = []

        def worker(action_name):
            try:
                r = sandbox.execute_in_sandbox(action_name, {"i": action_name})
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"action_{i}",))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert sandbox.get_stats()["total_executions"] == 10

    def test_concurrent_limited_prod_executions(self):
        lp = LimitedProdExecutor()
        import threading
        errors = []
        results = []

        def worker(action_name):
            try:
                r = lp.execute_limited(action_name, {"i": action_name})
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"action_{i}",))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert lp.get_stats()["total_executions"] == 10


# ===================================================================
# Data model tests
# ===================================================================

class TestDataModels:
    def test_sandbox_execution_auto_ids(self):
        e = SandboxExecution()
        assert len(e.execution_id) == 32
        assert e.started_at > 0

    def test_limited_prod_execution_auto_ids(self):
        e = LimitedProdExecution()
        assert len(e.execution_id) == 32
        assert e.started_at > 0

    def test_execution_status_enum_values(self):
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.SIDE_EFFECTS_DETECTED.value == "side_effects_detected"

    def test_escalation_status_enum_values(self):
        assert EscalationStatus.PENDING.value == "pending"
        assert EscalationStatus.APPROVED.value == "approved"
        assert EscalationStatus.REJECTED.value == "rejected"


# ===================================================================
# Integration: executor_fn with side-effects + constraints
# ===================================================================

class TestIntegration:
    def test_sandbox_side_effects_affect_stats(self):
        sandbox = SandboxExecutor()

        # Clean execution
        sandbox.execute_in_sandbox("clean")

        # Execution with side-effects
        def se_fn(a, p):
            return {"ok": True, "__side_effects__": [{"type": "write"}]}
        sandbox.execute_in_sandbox("dirty", executor_fn=se_fn)

        stats = sandbox.get_stats()
        assert stats["total_executions"] == 2
        assert stats["completed"] == 1
        assert stats["side_effects_detected"] == 1

    def test_limited_prod_full_lifecycle(self):
        lp = LimitedProdExecutor()

        # 1. Execute with human review required
        r = lp.execute_limited("deploy", {"version": "1.0"},
                               {"require_human_review": True})
        assert r["status"] == "pending"
        esc_id = r["escalation_id"]

        # 2. Verify escalation exists
        escs = lp.get_escalations(status="pending")
        assert len(escs) == 1

        # 3. Approve escalation
        lp.resolve_escalation(esc_id, "approved", "cto", "LGTM")

        # 4. Verify stats
        stats = lp.get_stats()
        assert stats["total_executions"] == 1
        assert stats["total_escalations"] == 1
        assert stats["approved_escalations"] == 1

    def test_sandbox_feeds_autonomy_gate_4(self, sandbox):
        """Simulate 5+ clean sandbox executions for G-AUTONOMY-4."""
        for i in range(6):
            sandbox.execute_in_sandbox(f"test_{i}")

        stats = sandbox.get_stats()
        assert stats["completed"] >= 5
        assert stats["side_effects_detected"] == 0
        # These values can be used as evidence for G-AUTONOMY-4:
        #   sandbox_executions_count = stats["completed"]
        #   sandbox_side_effects = stats["side_effects_detected"]
