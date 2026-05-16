"""
Tests for sylion.security.execution_guard -- ExecutionGuard

Covers policy CRUD, approval workflow, execution checking,
execution log, EventBus integration, singleton, and concurrency.
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.execution_guard import (
    VALID_POLICY_SCOPES,
    ExecutionGuard,
    get_execution_guard,
    reset_execution_guard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_guard(event_bus: EventBus | None = None) -> ExecutionGuard:
    return ExecutionGuard(db_path=":memory:", event_bus=event_bus)


def _make_policy(guard: ExecutionGuard, name: str = "test_policy",
                 scope: str = "global",
                 rules: dict | None = None) -> dict:
    return guard.create_policy(name, scope, rules)


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_valid_scopes(self):
        assert "global" in VALID_POLICY_SCOPES
        assert "module" in VALID_POLICY_SCOPES
        assert "operation" in VALID_POLICY_SCOPES
        assert "resource" in VALID_POLICY_SCOPES


# ===========================================================================
# 2. Policy CRUD -- Create
# ===========================================================================


class TestCreatePolicy:
    def test_basic_create(self):
        guard = _make_guard()
        p = guard.create_policy("allow_all")
        assert p["policy_id"] != ""
        assert p["name"] == "allow_all"
        assert p["scope"] == "global"
        assert p["is_active"] == 1
        assert p["created_at"] > 0

    def test_with_scope(self):
        guard = _make_guard()
        p = guard.create_policy("mod_policy", scope="module")
        assert p["scope"] == "module"

    def test_with_rules_dict(self):
        guard = _make_guard()
        rules = {"action": "allow", "required_key": "module", "required_value": "auth"}
        p = guard.create_policy("rule_policy", rules_json=rules)
        assert p["rules_json"] == rules

    def test_with_rules_string(self):
        guard = _make_guard()
        rules_str = '{"action": "deny"}'
        p = guard.create_policy("str_policy", rules_json=rules_str)
        assert isinstance(p["rules_json"], dict)
        assert p["rules_json"]["action"] == "deny"

    def test_default_rules_empty(self):
        guard = _make_guard()
        p = guard.create_policy("empty_rules")
        assert p["rules_json"] == {}

    def test_rejects_invalid_scope(self):
        guard = _make_guard()
        with pytest.raises(ValueError, match="Invalid scope"):
            guard.create_policy("bad", scope="invalid_scope")

    def test_unique_policy_ids(self):
        guard = _make_guard()
        p1 = guard.create_policy("p1")
        p2 = guard.create_policy("p2")
        assert p1["policy_id"] != p2["policy_id"]


# ===========================================================================
# 3. Policy CRUD -- Get / List
# ===========================================================================


class TestGetPolicy:
    def test_get_existing(self):
        guard = _make_guard()
        p = _make_policy(guard)
        fetched = guard.get_policy(p["policy_id"])
        assert fetched is not None
        assert fetched["name"] == "test_policy"

    def test_get_nonexistent(self):
        guard = _make_guard()
        assert guard.get_policy("nope") is None

    def test_rules_json_parsed(self):
        guard = _make_guard()
        p = guard.create_policy("p1", rules_json={"action": "allow"})
        fetched = guard.get_policy(p["policy_id"])
        assert isinstance(fetched["rules_json"], dict)
        assert fetched["rules_json"]["action"] == "allow"


class TestListPolicies:
    def test_list_all(self):
        guard = _make_guard()
        guard.create_policy("p1")
        guard.create_policy("p2")
        policies = guard.list_policies()
        assert len(policies) == 2

    def test_filter_by_scope(self):
        guard = _make_guard()
        guard.create_policy("g1", scope="global")
        guard.create_policy("m1", scope="module")
        result = guard.list_policies(scope="module")
        assert len(result) == 1
        assert result[0]["scope"] == "module"

    def test_empty_list(self):
        guard = _make_guard()
        assert guard.list_policies() == []


# ===========================================================================
# 4. Policy CRUD -- Update / Delete
# ===========================================================================


class TestUpdatePolicy:
    def test_update_name(self):
        guard = _make_guard()
        p = _make_policy(guard)
        updated = guard.update_policy(p["policy_id"], name="new_name")
        assert updated["name"] == "new_name"

    def test_update_scope(self):
        guard = _make_guard()
        p = _make_policy(guard)
        updated = guard.update_policy(p["policy_id"], scope="module")
        assert updated["scope"] == "module"

    def test_update_rules(self):
        guard = _make_guard()
        p = _make_policy(guard)
        updated = guard.update_policy(p["policy_id"], rules_json={"action": "deny"})
        assert updated["rules_json"]["action"] == "deny"

    def test_update_active_status(self):
        guard = _make_guard()
        p = _make_policy(guard)
        updated = guard.update_policy(p["policy_id"], is_active=0)
        assert updated["is_active"] == 0

    def test_update_nonexistent_returns_none(self):
        guard = _make_guard()
        assert guard.update_policy("nope", name="x") is None

    def test_update_rejects_invalid_scope(self):
        guard = _make_guard()
        p = _make_policy(guard)
        with pytest.raises(ValueError, match="Invalid scope"):
            guard.update_policy(p["policy_id"], scope="bad")

    def test_update_no_fields_returns_policy(self):
        guard = _make_guard()
        p = _make_policy(guard)
        result = guard.update_policy(p["policy_id"])
        assert result is not None


class TestDeletePolicy:
    def test_delete_existing(self):
        guard = _make_guard()
        p = _make_policy(guard)
        assert guard.delete_policy(p["policy_id"]) is True

    def test_delete_nonexistent(self):
        guard = _make_guard()
        assert guard.delete_policy("nope") is False

    def test_deleted_not_listed(self):
        guard = _make_guard()
        p = _make_policy(guard)
        guard.delete_policy(p["policy_id"])
        assert guard.list_policies() == []


# ===========================================================================
# 5. Approval workflow
# ===========================================================================


class TestApprovalWorkflow:
    def test_request_approval(self):
        guard = _make_guard()
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {"action": "deploy"})
        assert req["request_id"] != ""
        assert req["status"] == "pending"
        assert req["policy_id"] == p["policy_id"]

    def test_approve_request(self):
        guard = _make_guard()
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {"action": "deploy"})
        result = guard.approve_request(req["request_id"], "admin")
        assert result["status"] == "approved"
        assert result["approver"] == "admin"

    def test_deny_request(self):
        guard = _make_guard()
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {"action": "deploy"})
        result = guard.deny_request(req["request_id"], "admin", "not allowed")
        assert result["status"] == "denied"
        assert result["reason"] == "not allowed"

    def test_approve_already_resolved_returns_none(self):
        guard = _make_guard()
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {})
        guard.approve_request(req["request_id"], "admin")
        result = guard.approve_request(req["request_id"], "admin2")
        assert result is None

    def test_deny_already_resolved_returns_none(self):
        guard = _make_guard()
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {})
        guard.deny_request(req["request_id"], "admin", "no")
        result = guard.deny_request(req["request_id"], "admin", "no")
        assert result is None

    def test_approve_nonexistent_returns_none(self):
        guard = _make_guard()
        assert guard.approve_request("nope", "admin") is None

    def test_request_with_dict_context(self):
        guard = _make_guard()
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {"module": "auth", "op": "write"})
        assert req["status"] == "pending"

    def test_request_with_string_context(self):
        guard = _make_guard()
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], "raw_context_string")
        assert req["status"] == "pending"

    def test_request_approval_creates_governance_ticket(self):
        from sylion.governance.tickets import fetch_by_id, reset_ticket_store

        reset_ticket_store(":memory:")
        guard = reset_execution_guard(db_path=":memory:")
        p = _make_policy(guard)
        req = guard.request_approval(
            p["policy_id"],
            {
                "action": "production_deploy",
                "project_id": "p_exec",
                "decision_class": "D4",
                "actor": "operator",
            },
        )
        ticket = fetch_by_id(req["governance_ticket_id"])
        assert ticket is not None
        assert ticket.origin == "execution_guard"
        assert ticket.project_id == "p_exec"
        assert ticket.decision_class == "D4"
        assert ticket.gate_type == "production"
        assert ticket.priority == "P1"
        assert ticket.payload["execution_guard_request_id"] == req["request_id"]

    def test_governance_ticket_resolution_updates_approval_request(self):
        from sylion.governance.tickets import resolve, reset_ticket_store

        reset_ticket_store(":memory:")
        guard = reset_execution_guard(db_path=":memory:")
        p = _make_policy(guard)
        req = guard.request_approval(
            p["policy_id"],
            {
                "action": "deploy",
                "project_id": "p_exec",
                "decision_class": "D3",
                "actor": "operator",
            },
        )
        assert resolve(
            req["governance_ticket_id"],
            "approved",
            reason="operator approved execution guard request",
            reviewer="operator",
        )
        stored = guard.get_approval_request(req["request_id"])
        assert stored is not None
        assert stored["status"] == "approved"
        assert stored["approver"] == "operator"


# ===========================================================================
# 6. Execution checking
# ===========================================================================


class TestCheckExecution:
    def test_default_deny_no_policies(self):
        guard = _make_guard()
        result = guard.check_execution({"module": "test"})
        assert result["allowed"] is False
        assert "no matching policy" in result["reason"]

    def test_global_allow_policy(self):
        guard = _make_guard()
        guard.create_policy("allow_all", rules_json={
            "action": "allow", "match_scope": "global", "reason": "all allowed",
        })
        result = guard.check_execution({"anything": "goes"})
        assert result["allowed"] is True
        assert result["reason"] == "all allowed"

    def test_global_deny_policy(self):
        guard = _make_guard()
        guard.create_policy("deny_all", rules_json={
            "action": "deny", "match_scope": "global", "reason": "all denied",
        })
        result = guard.check_execution({"anything": "goes"})
        assert result["allowed"] is False

    def test_scope_match_module(self):
        guard = _make_guard()
        guard.create_policy("mod_policy", scope="module", rules_json={
            "action": "allow", "match_scope": "module",
            "required_key": "module", "required_value": "auth",
        })
        result_match = guard.check_execution({"module": "auth"})
        result_no_match = guard.check_execution({"module": "other"})
        assert result_match["allowed"] is True
        assert result_no_match["allowed"] is False

    def test_inactive_policy_ignored(self):
        guard = _make_guard()
        p = guard.create_policy("inactive", rules_json={
            "action": "allow", "match_scope": "global",
        })
        guard.update_policy(p["policy_id"], is_active=0)
        result = guard.check_execution({})
        assert result["allowed"] is False

    def test_logs_execution(self):
        guard = _make_guard()
        guard.create_policy("allow", rules_json={"action": "allow", "match_scope": "global"})
        guard.check_execution({"test": 1})
        log_entries = guard.get_execution_log()
        assert len(log_entries) == 1
        assert log_entries[0]["result"] == "allowed"


class TestGetExecutionLog:
    def test_empty_log(self):
        guard = _make_guard()
        assert guard.get_execution_log() == []

    def test_log_limit(self):
        guard = _make_guard()
        guard.create_policy("allow", rules_json={"action": "allow", "match_scope": "global"})
        for i in range(10):
            guard.check_execution({"i": i})
        entries = guard.get_execution_log(limit=5)
        assert len(entries) == 5

    def test_log_order_desc(self):
        guard = _make_guard()
        guard.create_policy("allow", rules_json={"action": "allow", "match_scope": "global"})
        guard.check_execution({"first": True})
        guard.check_execution({"second": True})
        entries = guard.get_execution_log()
        assert entries[0]["timestamp"] >= entries[1]["timestamp"]


# ===========================================================================
# 7. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_policy_created_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("policy_created", lambda e: collected.append(e))
        guard = _make_guard(event_bus=bus)
        guard.create_policy("ev_policy")
        assert len(collected) == 1
        assert collected[0].payload["name"] == "ev_policy"

    def test_approval_requested_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("approval_requested", lambda e: collected.append(e))
        guard = _make_guard(event_bus=bus)
        p = _make_policy(guard)
        guard.request_approval(p["policy_id"], {})
        assert len(collected) == 1

    def test_approval_granted_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("approval_granted", lambda e: collected.append(e))
        guard = _make_guard(event_bus=bus)
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {})
        guard.approve_request(req["request_id"], "admin")
        assert len(collected) == 1
        assert collected[0].payload["approver"] == "admin"

    def test_approval_denied_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("approval_denied", lambda e: collected.append(e))
        guard = _make_guard(event_bus=bus)
        p = _make_policy(guard)
        req = guard.request_approval(p["policy_id"], {})
        guard.deny_request(req["request_id"], "admin", "nope")
        assert len(collected) == 1

    def test_execution_checked_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("execution_checked", lambda e: collected.append(e))
        guard = _make_guard(event_bus=bus)
        guard.check_execution({"test": 1})
        assert len(collected) == 1
        assert "allowed" in collected[0].payload

    def test_no_event_without_bus(self):
        guard = _make_guard(event_bus=None)
        guard.create_policy("test")
        # Should not raise


# ===========================================================================
# 8. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_execution_guard(self):
        import sylion.security.execution_guard as mod
        mod._guard = None
        g = get_execution_guard(db_path=":memory:")
        assert isinstance(g, ExecutionGuard)
        mod._guard = None

    def test_reset_execution_guard(self):
        import sylion.security.execution_guard as mod
        mod._guard = None
        g1 = get_execution_guard(db_path=":memory:")
        g2 = reset_execution_guard(db_path=":memory:")
        assert g2 is not g1
        mod._guard = None

    def test_get_returns_same_instance(self):
        import sylion.security.execution_guard as mod
        mod._guard = None
        g1 = get_execution_guard(db_path=":memory:")
        g2 = get_execution_guard()
        assert g1 is g2
        mod._guard = None


# ===========================================================================
# 9. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_policy_creation(self):
        guard = _make_guard()
        results = []
        errors = []

        def create(i):
            try:
                p = guard.create_policy(f"p_{i}")
                results.append(p["policy_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_check(self):
        guard = _make_guard()
        guard.create_policy("allow", rules_json={"action": "allow", "match_scope": "global"})
        results = []
        errors = []

        def check():
            try:
                r = guard.check_execution({"test": True})
                results.append(r["allowed"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)
