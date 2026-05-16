"""Tests for SelfHealingOrchestrator -- rule management, event processing,
session lifecycle, statistics, EventBus integration, and thread safety.

~45 tests.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.aeis.self_healing_orchestrator import (
    ACTION_TYPES,
    SESSION_STATUSES,
    TRIGGER_TYPES,
    SelfHealingOrchestrator,
    get_self_healing_orchestrator,
    reset_self_healing_orchestrator,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset global singleton before and after every test."""
    reset_self_healing_orchestrator()
    yield
    reset_self_healing_orchestrator()


@pytest.fixture
def orch():
    """Fresh in-memory SelfHealingOrchestrator."""
    return SelfHealingOrchestrator()


@pytest.fixture
def orch_with_bus():
    """Fresh orchestrator with a real EventBus attached."""
    bus = EventBus()
    return SelfHealingOrchestrator(event_bus=bus), bus


def _make_rule(orch, **overrides):
    """Helper to create a rule with sensible defaults."""
    defaults = {
        "name": "test-rule",
        "trigger_type": "anomaly",
        "trigger_pattern": ".*",
        "action_type": "restart",
    }
    defaults.update(overrides)
    return orch.create_rule(**defaults)


# ===========================================================================
# 1. Constants
# ===========================================================================

class TestConstants:
    def test_trigger_types(self):
        assert "anomaly" in TRIGGER_TYPES
        assert "error" in TRIGGER_TYPES
        assert "threshold_breach" in TRIGGER_TYPES
        assert "health_check_failure" in TRIGGER_TYPES
        assert len(TRIGGER_TYPES) == 4

    def test_action_types(self):
        assert "restart" in ACTION_TYPES
        assert "rollback" in ACTION_TYPES
        assert "scale_up" in ACTION_TYPES
        assert "notify" in ACTION_TYPES
        assert "circuit_break" in ACTION_TYPES
        assert len(ACTION_TYPES) == 5

    def test_session_statuses(self):
        assert "pending" in SESSION_STATUSES
        assert "in_progress" in SESSION_STATUSES
        assert "completed" in SESSION_STATUSES
        assert "failed" in SESSION_STATUSES
        assert "skipped" in SESSION_STATUSES
        assert len(SESSION_STATUSES) == 5


# ===========================================================================
# 2. Rule creation
# ===========================================================================

class TestCreateRule:
    def test_returns_rule_id(self, orch):
        r = _make_rule(orch)
        assert "rule_id" in r
        assert isinstance(r["rule_id"], str)
        assert len(r["rule_id"]) > 0

    def test_returns_name(self, orch):
        r = orch.create_rule("My Rule", "anomaly", ".*", "restart")
        assert r["name"] == "My Rule"

    def test_returns_trigger_type(self, orch):
        r = _make_rule(orch, trigger_type="error")
        assert r["trigger_type"] == "error"

    def test_returns_trigger_pattern(self, orch):
        r = _make_rule(orch, trigger_pattern="OOM.*")
        assert r["trigger_pattern"] == "OOM.*"

    def test_returns_action_type(self, orch):
        r = _make_rule(orch, action_type="rollback")
        assert r["action_type"] == "rollback"

    def test_action_params_dict_serialized(self, orch):
        r = orch.create_rule(
            "p", "anomaly", ".*", "restart",
            action_params={"service": "api"},
        )
        assert r["action_params"] == '{"service": "api"}'

    def test_action_params_string(self, orch):
        r = orch.create_rule(
            "p", "anomaly", ".*", "restart",
            action_params="raw-params",
        )
        assert r["action_params"] == "raw-params"

    def test_action_params_none_is_empty(self, orch):
        r = orch.create_rule("p", "anomaly", ".*", "restart")
        assert r["action_params"] == ""

    def test_priority_default_zero(self, orch):
        r = _make_rule(orch)
        assert r["priority"] == 0

    def test_priority_custom(self, orch):
        r = _make_rule(orch, priority=10)
        assert r["priority"] == 10

    def test_enabled_by_default(self, orch):
        r = _make_rule(orch)
        assert r["enabled"] is True

    def test_created_at_set(self, orch):
        r = _make_rule(orch)
        assert r["created_at"] > 0
        assert r["created_at"] <= time.time()

    def test_invalid_trigger_type_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid trigger_type"):
            orch.create_rule("r", "bogus", ".*", "restart")

    def test_invalid_action_type_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid action_type"):
            orch.create_rule("r", "anomaly", ".*", "explode")


# ===========================================================================
# 3. Get rule
# ===========================================================================

class TestGetRule:
    def test_get_existing_rule(self, orch):
        created = _make_rule(orch)
        fetched = orch.get_rule(created["rule_id"])
        assert fetched is not None
        assert fetched["rule_id"] == created["rule_id"]
        assert fetched["name"] == "test-rule"

    def test_get_nonexistent_returns_none(self, orch):
        assert orch.get_rule("nonexistent") is None


# ===========================================================================
# 4. List rules
# ===========================================================================

class TestListRules:
    def test_empty_list(self, orch):
        assert orch.list_rules() == []

    def test_returns_created_rules(self, orch):
        _make_rule(orch, name="a")
        _make_rule(orch, name="b")
        rules = orch.list_rules()
        assert len(rules) == 2

    def test_filter_by_trigger_type(self, orch):
        _make_rule(orch, trigger_type="anomaly")
        _make_rule(orch, trigger_type="error")
        rules = orch.list_rules(trigger_type="anomaly")
        assert len(rules) == 1
        assert rules[0]["trigger_type"] == "anomaly"

    def test_filter_by_enabled(self, orch):
        r = _make_rule(orch, name="disabled")
        orch.update_rule(r["rule_id"], enabled=False)
        rules = orch.list_rules(enabled=True)
        assert len(rules) == 0

    def test_filter_disabled(self, orch):
        r = _make_rule(orch, name="disabled")
        orch.update_rule(r["rule_id"], enabled=False)
        rules = orch.list_rules(enabled=False)
        assert len(rules) == 1
        assert rules[0]["name"] == "disabled"

    def test_priority_ordering(self, orch):
        _make_rule(orch, name="low", priority=0)
        _make_rule(orch, name="high", priority=10)
        rules = orch.list_rules()
        assert rules[0]["name"] == "high"
        assert rules[1]["name"] == "low"


# ===========================================================================
# 5. Update rule
# ===========================================================================

class TestUpdateRule:
    def test_enable_toggle(self, orch):
        r = _make_rule(orch)
        assert r["enabled"] is True
        updated = orch.update_rule(r["rule_id"], enabled=False)
        assert updated["enabled"] is False

    def test_re_enable(self, orch):
        r = _make_rule(orch)
        orch.update_rule(r["rule_id"], enabled=False)
        updated = orch.update_rule(r["rule_id"], enabled=True)
        assert updated["enabled"] is True

    def test_update_nonexistent_returns_none(self, orch):
        assert orch.update_rule("nonexistent", enabled=False) is None

    def test_update_no_fields_returns_rule(self, orch):
        r = _make_rule(orch)
        updated = orch.update_rule(r["rule_id"])
        assert updated is not None
        assert updated["rule_id"] == r["rule_id"]


# ===========================================================================
# 6. Delete rule
# ===========================================================================

class TestDeleteRule:
    def test_delete_existing(self, orch):
        r = _make_rule(orch)
        assert orch.delete_rule(r["rule_id"]) is True

    def test_delete_nonexistent(self, orch):
        assert orch.delete_rule("nonexistent") is False

    def test_delete_removes_from_list(self, orch):
        r = _make_rule(orch)
        orch.delete_rule(r["rule_id"])
        assert orch.get_rule(r["rule_id"]) is None

    def test_delete_does_not_affect_other_rules(self, orch):
        r1 = _make_rule(orch, name="keep")
        r2 = _make_rule(orch, name="remove")
        orch.delete_rule(r2["rule_id"])
        assert orch.get_rule(r1["rule_id"]) is not None


# ===========================================================================
# 7. Process event
# ===========================================================================

class TestProcessEvent:
    def test_matching_rule_creates_session(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "cpu spike"})
        assert len(sessions) == 1
        assert sessions[0]["status"] == "pending"

    def test_no_matching_rules_returns_empty(self, orch):
        _make_rule(orch, trigger_type="error", trigger_pattern="OOM.*")
        sessions = orch.process_event("anomaly", {"msg": "cpu spike"})
        assert len(sessions) == 0

    def test_pattern_match(self, orch):
        _make_rule(orch, trigger_type="error", trigger_pattern="OOM.*")
        sessions = orch.process_event("error", {"detail": "OOM killed"})
        assert len(sessions) == 1

    def test_pattern_no_match(self, orch):
        _make_rule(orch, trigger_type="error", trigger_pattern="OOM.*")
        sessions = orch.process_event("error", {"detail": "timeout"})
        assert len(sessions) == 0

    def test_disabled_rule_ignored(self, orch):
        r = _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        orch.update_rule(r["rule_id"], enabled=False)
        sessions = orch.process_event("anomaly", {"msg": "anything"})
        assert len(sessions) == 0

    def test_multiple_rules_match(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern="cpu",
                   name="r1", priority=1)
        _make_rule(orch, trigger_type="anomaly", trigger_pattern="spike",
                   name="r2", priority=10)
        sessions = orch.process_event("anomaly", {"msg": "cpu spike"})
        assert len(sessions) == 2
        # Higher priority first
        assert sessions[0]["rule_name"] == "r2"
        assert sessions[1]["rule_name"] == "r1"

    def test_empty_pattern_matches_everything(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern="")
        sessions = orch.process_event("anomaly", {"msg": "anything"})
        assert len(sessions) == 1

    def test_event_data_as_string(self, orch):
        _make_rule(orch, trigger_type="error", trigger_pattern="timeout")
        sessions = orch.process_event("error", "connection timeout detected")
        assert len(sessions) == 1

    def test_invalid_trigger_type_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid trigger_type"):
            orch.process_event("bogus", {})

    def test_session_has_rule_info(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*",
                   action_type="rollback")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        assert sessions[0]["action_type"] == "rollback"
        assert sessions[0]["rule_name"] == "test-rule"


# ===========================================================================
# 8. Get session
# ===========================================================================

class TestGetSession:
    def test_get_existing_session(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        fetched = orch.get_session(sessions[0]["session_id"])
        assert fetched is not None
        assert fetched["session_id"] == sessions[0]["session_id"]

    def test_get_nonexistent_returns_none(self, orch):
        assert orch.get_session("nonexistent") is None


# ===========================================================================
# 9. List sessions
# ===========================================================================

class TestListSessions:
    def test_empty_list(self, orch):
        assert orch.list_sessions() == []

    def test_returns_sessions(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        orch.process_event("anomaly", {"msg": "a"})
        orch.process_event("anomaly", {"msg": "b"})
        assert len(orch.list_sessions()) == 2

    def test_filter_by_rule_id(self, orch):
        r1 = _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*",
                        name="r1")
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*",
                   name="r2")
        orch.process_event("anomaly", {"msg": "a"})
        sessions = orch.list_sessions(rule_id=r1["rule_id"])
        assert all(s["rule_id"] == r1["rule_id"] for s in sessions)

    def test_filter_by_status(self, orch):
        r = _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "a"})
        orch.complete_session(sessions[0]["session_id"], "success")
        pending = orch.list_sessions(status="pending")
        assert len(pending) == 0
        completed = orch.list_sessions(status="completed")
        assert len(completed) == 1

    def test_invalid_status_raises(self, orch):
        with pytest.raises(ValueError, match="Invalid status"):
            orch.list_sessions(status="bogus")

    def test_limit_respected(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        for i in range(10):
            orch.process_event("anomaly", {"msg": f"evt-{i}"})
        sessions = orch.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_ordered_by_started_at_desc(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        s1 = orch.process_event("anomaly", {"msg": "first"})[0]
        s2 = orch.process_event("anomaly", {"msg": "second"})[0]
        sessions = orch.list_sessions()
        assert sessions[0]["session_id"] == s2["session_id"]
        assert sessions[1]["session_id"] == s1["session_id"]


# ===========================================================================
# 10. Complete session
# ===========================================================================

class TestCompleteSession:
    def test_complete_success(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        sid = sessions[0]["session_id"]
        result = orch.complete_session(sid, "success")
        assert result["status"] == "completed"
        assert result["result"] == "success"
        assert result["completed_at"] > 0

    def test_complete_failure(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        sid = sessions[0]["session_id"]
        result = orch.complete_session(sid, "timeout exceeded")
        assert result["status"] == "failed"
        assert result["result"] == "timeout exceeded"

    def test_complete_nonexistent_returns_none(self, orch):
        assert orch.complete_session("nonexistent", "success") is None

    def test_default_result_is_success(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        result = orch.complete_session(sessions[0]["session_id"])
        assert result["status"] == "completed"
        assert result["result"] == "success"


# ===========================================================================
# 11. Statistics
# ===========================================================================

class TestGetStats:
    def test_empty_stats(self, orch):
        stats = orch.get_stats()
        assert stats["total_rules"] == 0
        assert stats["enabled_rules"] == 0
        assert stats["total_sessions"] == 0

    def test_rules_count(self, orch):
        _make_rule(orch, name="a")
        _make_rule(orch, name="b")
        _make_rule(orch, name="c")
        stats = orch.get_stats()
        assert stats["total_rules"] == 3
        assert stats["enabled_rules"] == 3
        assert stats["disabled_rules"] == 0

    def test_disabled_rules_count(self, orch):
        r = _make_rule(orch)
        orch.update_rule(r["rule_id"], enabled=False)
        stats = orch.get_stats()
        assert stats["disabled_rules"] == 1

    def test_sessions_by_status(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        s1 = orch.process_event("anomaly", {"msg": "a"})[0]
        s2 = orch.process_event("anomaly", {"msg": "b"})[0]
        orch.complete_session(s1["session_id"], "success")
        orch.complete_session(s2["session_id"], "error")

        stats = orch.get_stats()
        assert stats["by_status"]["completed"] == 1
        assert stats["by_status"]["failed"] == 1
        assert stats["by_status"]["pending"] == 0

    def test_all_statuses_present(self, orch):
        stats = orch.get_stats()
        for s in SESSION_STATUSES:
            assert s in stats["by_status"]

    def test_by_action_type(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*",
                   action_type="restart", name="r1")
        _make_rule(orch, trigger_type="error", trigger_pattern=".*",
                   action_type="notify", name="r2")
        orch.process_event("anomaly", {"msg": "a"})
        orch.process_event("error", {"msg": "b"})

        stats = orch.get_stats()
        assert stats["by_action_type"]["restart"] == 1
        assert stats["by_action_type"]["notify"] == 1


# ===========================================================================
# 12. EventBus integration
# ===========================================================================

class TestEventBusIntegration:
    def test_process_event_emits_triggered(self, orch_with_bus):
        orch, bus = orch_with_bus
        collected = []
        bus.subscribe("healing.triggered",
                      lambda e: collected.append(e))
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        orch.process_event("anomaly", {"msg": "x"})
        assert len(collected) == 1
        assert collected[0].payload["trigger_type"] == "anomaly"
        assert collected[0].payload["action_type"] == "restart"

    def test_complete_success_emits_completed(self, orch_with_bus):
        orch, bus = orch_with_bus
        collected = []
        bus.subscribe("healing.completed",
                      lambda e: collected.append(e))
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        orch.complete_session(sessions[0]["session_id"], "success")
        assert len(collected) == 1
        assert collected[0].payload["result"] == "success"

    def test_complete_failure_emits_failed(self, orch_with_bus):
        orch, bus = orch_with_bus
        collected = []
        bus.subscribe("healing.failed",
                      lambda e: collected.append(e))
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        orch.complete_session(sessions[0]["session_id"], "error")
        assert len(collected) == 1
        assert collected[0].payload["result"] == "error"

    def test_no_event_bus_does_not_crash(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        orch.complete_session(sessions[0]["session_id"], "success")
        # Should not raise


# ===========================================================================
# 13. Singleton
# ===========================================================================

class TestSingleton:
    def test_get_returns_instance(self):
        o = get_self_healing_orchestrator()
        assert isinstance(o, SelfHealingOrchestrator)

    def test_get_returns_same_instance(self):
        o1 = get_self_healing_orchestrator()
        o2 = get_self_healing_orchestrator()
        assert o1 is o2

    def test_reset_clears_singleton(self):
        o1 = get_self_healing_orchestrator()
        reset_self_healing_orchestrator()
        o2 = get_self_healing_orchestrator()
        assert o1 is not o2


# ===========================================================================
# 14. Concurrency
# ===========================================================================

class TestConcurrency:
    def test_concurrent_process_event(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        errors = []
        session_count = [0]

        def worker(idx):
            try:
                sessions = orch.process_event(
                    "anomaly", {"msg": f"concurrent-{idx}"})
                session_count[0] += len(sessions)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert session_count[0] == 10
        assert len(orch.list_sessions()) == 10

    def test_concurrent_create_and_delete(self, orch):
        errors = []
        rule_ids = []

        def creator():
            try:
                r = _make_rule(orch)
                rule_ids.append(r["rule_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=creator) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(rule_ids) == 5

        # Now delete them concurrently
        deleters = [
            threading.Thread(target=lambda rid=rid: orch.delete_rule(rid))
            for rid in rule_ids
        ]
        for t in deleters:
            t.start()
        for t in deleters:
            t.join()

        assert len(orch.list_rules()) == 0


# ===========================================================================
# 15. Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_invalid_regex_pattern_skips_rule(self, orch):
        _make_rule(orch, trigger_type="anomaly",
                   trigger_pattern="[invalid regex")
        sessions = orch.process_event("anomaly", {"msg": "test"})
        # Invalid regex should be skipped, not crash
        assert len(sessions) == 0

    def test_trigger_event_stored_in_session(self, orch):
        _make_rule(orch, trigger_type="error", trigger_pattern=".*")
        event = {"error_code": 500, "service": "api"}
        sessions = orch.process_event("error", event)
        fetched = orch.get_session(sessions[0]["session_id"])
        assert json.loads(fetched["trigger_event"])["error_code"] == 500

    def test_all_trigger_types_accepted(self, orch):
        for tt in TRIGGER_TYPES:
            _make_rule(orch, trigger_type=tt, trigger_pattern=".*",
                       name=f"rule-{tt}")
        for tt in TRIGGER_TYPES:
            sessions = orch.process_event(tt, {"msg": "x"})
            assert len(sessions) == 1

    def test_all_action_types_accepted(self, orch):
        for i, at in enumerate(ACTION_TYPES):
            r = orch.create_rule(f"r-{at}", "anomaly", ".*", at)
            assert r["action_type"] == at

    def test_complete_session_twice(self, orch):
        _make_rule(orch, trigger_type="anomaly", trigger_pattern=".*")
        sessions = orch.process_event("anomaly", {"msg": "x"})
        sid = sessions[0]["session_id"]
        r1 = orch.complete_session(sid, "success")
        assert r1["status"] == "completed"
        r2 = orch.complete_session(sid, "error")
        assert r2["status"] == "failed"
