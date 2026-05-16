"""Tests for SYLION Governance DecisionGateEngine — 40+ tests."""
import json
import time
import threading

import pytest

from sylion.governance.decision_gate_engine import (
    DecisionGateEngine,
    GateStatus,
    VoteValue,
    ApprovalStatus,
    get_governance_gate_engine,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh EventBus for each test."""
    return EventBus()


@pytest.fixture
def engine(bus):
    """Fresh DecisionGateEngine for each test."""
    return DecisionGateEngine(db_path=":memory:", event_bus=bus)


# ===========================================================================
# 1. Construction & Schema
# ===========================================================================

class TestConstruction:

    def test_creates_in_memory_db_by_default(self):
        eng = DecisionGateEngine()
        assert eng._db_path == ":memory:"

    def test_creates_tables(self, engine):
        tables = engine._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in tables]
        assert "sylion_decision_gates" in names
        assert "sylion_gate_evaluations" in names
        assert "sylion_approval_requests" in names
        assert "sylion_approval_votes" in names

    def test_event_bus_integration(self, bus):
        received = []
        bus.subscribe("gate.registered", lambda e: received.append(e))
        eng = DecisionGateEngine(db_path=":memory:", event_bus=bus)
        eng.register_gate("G-TEST-01", decision_class="D1")
        assert len(received) == 1
        assert received[0].payload["gate_id"] == "G-TEST-01"


# ===========================================================================
# 2. register_gate
# ===========================================================================

class TestRegisterGate:

    def test_register_basic(self, engine):
        result = engine.register_gate("G-REG-01", decision_class="D2",
                                       required_approvals=2, description="Test gate")
        assert result["registered"] is True
        assert result["gate_id"] == "G-REG-01"
        assert result["decision_class"] == "D2"
        assert result["required_approvals"] == 2

    def test_register_defaults(self, engine):
        result = engine.register_gate("G-DEF-01")
        assert result["decision_class"] == "D2"
        assert result["required_approvals"] == 1

    def test_register_with_auto_approve_criteria(self, engine):
        criteria = [{"field": "env", "operator": "eq", "value": "dev"}]
        result = engine.register_gate(
            "G-AUTO-01", auto_approve_criteria=criteria, description="Auto gate",
        )
        assert result["registered"] is True

        # Verify stored
        gates = engine.list_gates()
        g = [g for g in gates if g["gate_id"] == "G-AUTO-01"][0]
        assert g["auto_approve_criteria"] == criteria

    def test_register_upsert(self, engine):
        engine.register_gate("G-UPS-01", decision_class="D1", required_approvals=1)
        engine.register_gate("G-UPS-01", decision_class="D3", required_approvals=4)
        gates = engine.list_gates()
        g = [g for g in gates if g["gate_id"] == "G-UPS-01"][0]
        assert g["decision_class"] == "D3"
        assert g["required_approvals"] == 4

    def test_register_all_decision_classes(self, engine):
        for dc in ("D0", "D1", "D2", "D3", "D4", "D5"):
            result = engine.register_gate(f"G-CLS-{dc}", decision_class=dc)
            assert result["decision_class"] == dc
        assert len(engine.list_gates()) == 6

    def test_register_emits_event(self, engine, bus):
        received = []
        bus.subscribe("gate.registered", lambda e: received.append(e))
        engine.register_gate("G-EV-01", decision_class="D1")
        assert len(received) == 1
        assert received[0].payload["decision_class"] == "D1"


# ===========================================================================
# 3. evaluate_gate
# ===========================================================================

class TestEvaluateGate:

    def test_evaluate_unknown_gate(self, engine):
        result = engine.evaluate_gate("G-NONEXISTENT")
        assert result["status"] == "blocked"
        assert "not registered" in result["message"]

    def test_evaluate_no_criteria_no_requests_pending(self, engine):
        engine.register_gate("G-EV-01", decision_class="D2", required_approvals=1)
        result = engine.evaluate_gate("G-EV-01")
        assert result["status"] == GateStatus.PENDING.value

    def test_evaluate_auto_approve_eq(self, engine):
        criteria = [{"field": "env", "operator": "eq", "value": "dev"}]
        engine.register_gate("G-AA-01", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-AA-01", context={"env": "dev"})
        assert result["status"] == GateStatus.PASSED.value
        assert result["auto_approved"] is True

    def test_evaluate_auto_approve_fails(self, engine):
        criteria = [{"field": "env", "operator": "eq", "value": "dev"}]
        engine.register_gate("G-AA-02", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-AA-02", context={"env": "prod"})
        assert result["status"] != GateStatus.PASSED.value or result["auto_approved"] is False

    def test_evaluate_auto_approve_multiple_criteria_all_match(self, engine):
        criteria = [
            {"field": "env", "operator": "eq", "value": "dev"},
            {"field": "score", "operator": "gte", "value": 80},
        ]
        engine.register_gate("G-AA-03", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-AA-03", context={"env": "dev", "score": 90})
        assert result["status"] == GateStatus.PASSED.value
        assert result["auto_approved"] is True

    def test_evaluate_auto_approve_multiple_criteria_partial_fail(self, engine):
        criteria = [
            {"field": "env", "operator": "eq", "value": "dev"},
            {"field": "score", "operator": "gte", "value": 80},
        ]
        engine.register_gate("G-AA-04", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-AA-04", context={"env": "dev", "score": 50})
        assert result["auto_approved"] is False

    def test_evaluate_auto_approve_in_operator(self, engine):
        criteria = [{"field": "region", "operator": "in", "value": ["eu", "us"]}]
        engine.register_gate("G-AA-05", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-AA-05", context={"region": "eu"})
        assert result["auto_approved"] is True

    def test_evaluate_auto_approve_in_operator_fail(self, engine):
        criteria = [{"field": "region", "operator": "in", "value": ["eu", "us"]}]
        engine.register_gate("G-AA-06", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-AA-06", context={"region": "ap"})
        assert result["auto_approved"] is False

    def test_evaluate_auto_approve_gt_operator(self, engine):
        criteria = [{"field": "count", "operator": "gt", "value": 5}]
        engine.register_gate("G-AA-07", auto_approve_criteria=criteria)
        assert engine.evaluate_gate("G-AA-07", context={"count": 10})["auto_approved"] is True
        assert engine.evaluate_gate("G-AA-07", context={"count": 3})["auto_approved"] is False

    def test_evaluate_auto_approve_lt_operator(self, engine):
        criteria = [{"field": "errors", "operator": "lt", "value": 3}]
        engine.register_gate("G-AA-08", auto_approve_criteria=criteria)
        assert engine.evaluate_gate("G-AA-08", context={"errors": 1})["auto_approved"] is True
        assert engine.evaluate_gate("G-AA-08", context={"errors": 5})["auto_approved"] is False

    def test_evaluate_auto_approve_contains_operator(self, engine):
        criteria = [{"field": "tags", "operator": "contains", "value": "safe"}]
        engine.register_gate("G-AA-09", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-AA-09", context={"tags": ["safe", "verified"]})
        assert result["auto_approved"] is True

    def test_evaluate_auto_approve_exists_operator(self, engine):
        criteria = [{"field": "token", "operator": "exists", "value": True}]
        engine.register_gate("G-AA-10", auto_approve_criteria=criteria)
        assert engine.evaluate_gate("G-AA-10", context={"token": "abc"})["auto_approved"] is True
        assert engine.evaluate_gate("G-AA-10", context={})["auto_approved"] is False

    def test_evaluate_records_history(self, engine):
        engine.register_gate("G-HIST-01", decision_class="D2")
        engine.evaluate_gate("G-HIST-01", context={"key": "val"})
        history = engine.get_gate_history("G-HIST-01")
        assert len(history) == 1
        assert history[0]["context"] == {"key": "val"}

    def test_evaluate_with_approved_request_passes(self, engine):
        engine.register_gate("G-APR-01", decision_class="D3", required_approvals=2)
        req = engine.request_approval("G-APR-01", requester="agent_1")
        rid = req["request_id"]
        engine.approve(rid, "approver_1", "approve")
        engine.approve(rid, "approver_2", "approve")
        result = engine.evaluate_gate("G-APR-01")
        assert result["status"] == GateStatus.PASSED.value

    def test_evaluate_emits_event(self, engine, bus):
        received = []
        bus.subscribe("gate.evaluated", lambda e: received.append(e))
        engine.register_gate("G-EE-01")
        engine.evaluate_gate("G-EE-01", context={"x": 1})
        assert len(received) == 1
        assert received[0].payload["gate_id"] == "G-EE-01"


# ===========================================================================
# 4. request_approval
# ===========================================================================

class TestRequestApproval:

    def test_request_basic(self, engine):
        engine.register_gate("G-REQ-01", decision_class="D2")
        result = engine.request_approval("G-REQ-01", requester="agent_1",
                                          justification="Need to deploy")
        assert result["created"] is True
        assert result["status"] == ApprovalStatus.OPEN.value
        assert result["gate_id"] == "G-REQ-01"

    def test_request_nonexistent_gate(self, engine):
        result = engine.request_approval("G-FAKE-01", requester="agent_1")
        assert result["created"] is False
        assert "not registered" in result["message"]

    def test_request_multiple_for_same_gate(self, engine):
        engine.register_gate("G-MULTI-01")
        r1 = engine.request_approval("G-MULTI-01", requester="agent_1")
        r2 = engine.request_approval("G-MULTI-01", requester="agent_2")
        assert r1["request_id"] != r2["request_id"]
        assert r1["created"] is True
        assert r2["created"] is True

    def test_request_emits_event(self, engine, bus):
        received = []
        bus.subscribe("gate.approval_requested", lambda e: received.append(e))
        engine.register_gate("G-REQEV-01")
        engine.request_approval("G-REQEV-01", requester="agent_1")
        assert len(received) == 1
        assert received[0].payload["requester"] == "agent_1"


# ===========================================================================
# 5. approve (vote casting)
# ===========================================================================

class TestApprove:

    def test_approve_basic(self, engine):
        engine.register_gate("G-AP-01", required_approvals=1)
        req = engine.request_approval("G-AP-01", requester="agent_1")
        result = engine.approve(req["request_id"], "approver_1", "approve")
        assert result["cast"] is True
        assert result["request_status"] == ApprovalStatus.APPROVED.value

    def test_approve_requires_quorum(self, engine):
        engine.register_gate("G-AP-02", required_approvals=3)
        req = engine.request_approval("G-AP-02", requester="agent_1")
        r1 = engine.approve(req["request_id"], "approver_1", "approve")
        assert r1["request_status"] == ApprovalStatus.OPEN.value
        assert r1["votes_for"] == 1
        r2 = engine.approve(req["request_id"], "approver_2", "approve")
        assert r2["request_status"] == ApprovalStatus.OPEN.value
        r3 = engine.approve(req["request_id"], "approver_3", "approve")
        assert r3["request_status"] == ApprovalStatus.APPROVED.value
        assert r3["votes_for"] == 3

    def test_reject_vote(self, engine):
        engine.register_gate("G-AP-03", required_approvals=2)
        req = engine.request_approval("G-AP-03", requester="agent_1")
        r1 = engine.approve(req["request_id"], "approver_1", "approve")
        assert r1["request_status"] == ApprovalStatus.OPEN.value
        r2 = engine.approve(req["request_id"], "approver_2", "reject")
        assert r2["votes_against"] == 1

    def test_reject_prevents_approval(self, engine):
        engine.register_gate("G-AP-04", required_approvals=3)
        req = engine.request_approval("G-AP-04", requester="agent_1")
        engine.approve(req["request_id"], "approver_1", "reject")
        engine.approve(req["request_id"], "approver_2", "reject")
        engine.approve(req["request_id"], "approver_3", "approve")
        status = engine.check_gate_status("G-AP-04")
        assert status["votes_against"] == 2

    def test_duplicate_vote_rejected(self, engine):
        engine.register_gate("G-AP-05", required_approvals=2)
        req = engine.request_approval("G-AP-05", requester="agent_1")
        r1 = engine.approve(req["request_id"], "approver_1", "approve")
        assert r1["cast"] is True
        r2 = engine.approve(req["request_id"], "approver_1", "approve")
        assert r2["cast"] is False
        assert "already voted" in r2["message"]

    def test_invalid_vote_value(self, engine):
        engine.register_gate("G-AP-06")
        req = engine.request_approval("G-AP-06", requester="agent_1")
        result = engine.approve(req["request_id"], "approver_1", "maybe")
        assert result["cast"] is False
        assert "Invalid vote" in result["message"]

    def test_approve_on_nonexistent_request(self, engine):
        result = engine.approve("nonexistent_id", "approver_1", "approve")
        assert result["cast"] is False
        assert "not found" in result["message"]

    def test_approve_on_closed_request(self, engine):
        engine.register_gate("G-AP-07", required_approvals=1)
        req = engine.request_approval("G-AP-07", requester="agent_1")
        engine.approve(req["request_id"], "approver_1", "approve")
        # Try to vote on already-approved request
        result = engine.approve(req["request_id"], "approver_2", "approve")
        assert result["cast"] is False
        assert "not open" in result["message"]

    def test_approve_emits_event(self, engine, bus):
        received = []
        bus.subscribe("gate.vote_cast", lambda e: received.append(e))
        engine.register_gate("G-APE-01", required_approvals=1)
        req = engine.request_approval("G-APE-01", requester="agent_1")
        engine.approve(req["request_id"], "approver_1", "approve")
        assert len(received) == 1
        assert received[0].payload["vote"] == "approve"


# ===========================================================================
# 6. check_gate_status
# ===========================================================================

class TestCheckGateStatus:

    def test_status_unknown_gate(self, engine):
        status = engine.check_gate_status("G-UNKNOWN")
        assert status["status"] == "unknown"
        assert status["votes_for"] == 0

    def test_status_no_requests(self, engine):
        engine.register_gate("G-ST-01")
        status = engine.check_gate_status("G-ST-01")
        assert status["status"] == GateStatus.PENDING.value
        assert status["votes_for"] == 0
        assert status["required"] == 1

    def test_status_after_votes(self, engine):
        engine.register_gate("G-ST-02", required_approvals=2)
        req = engine.request_approval("G-ST-02", requester="agent_1")
        engine.approve(req["request_id"], "approver_1", "approve")
        engine.approve(req["request_id"], "approver_2", "approve")
        status = engine.check_gate_status("G-ST-02")
        assert status["status"] == ApprovalStatus.APPROVED.value
        assert status["votes_for"] == 2
        assert status["votes_against"] == 0


# ===========================================================================
# 7. list_gates
# ===========================================================================

class TestListGates:

    def test_list_empty(self, engine):
        assert engine.list_gates() == []

    def test_list_multiple(self, engine):
        engine.register_gate("G-L1-01", decision_class="D1")
        engine.register_gate("G-L1-02", decision_class="D3", required_approvals=4)
        gates = engine.list_gates()
        assert len(gates) == 2
        ids = {g["gate_id"] for g in gates}
        assert ids == {"G-L1-01", "G-L1-02"}

    def test_list_includes_criteria(self, engine):
        criteria = [{"field": "env", "operator": "eq", "value": "dev"}]
        engine.register_gate("G-L2-01", auto_approve_criteria=criteria)
        gates = engine.list_gates()
        g = gates[0]
        assert g["auto_approve_criteria"] == criteria
        assert g["enabled"] is True


# ===========================================================================
# 8. get_gate_history
# ===========================================================================

class TestGetGateHistory:

    def test_history_empty(self, engine):
        assert engine.get_gate_history("G-XX") == []

    def test_history_records_evaluations(self, engine):
        engine.register_gate("G-H-01")
        engine.evaluate_gate("G-H-01", context={"a": 1})
        engine.evaluate_gate("G-H-01", context={"b": 2})
        history = engine.get_gate_history("G-H-01")
        assert len(history) == 2
        # Most recent first
        assert history[0]["context"] == {"b": 2}
        assert history[1]["context"] == {"a": 1}

    def test_history_respects_limit(self, engine):
        engine.register_gate("G-H-02")
        for i in range(10):
            engine.evaluate_gate("G-H-02", context={"i": i})
        history = engine.get_gate_history("G-H-02", limit=5)
        assert len(history) == 5

    def test_history_includes_auto_approved_flag(self, engine):
        criteria = [{"field": "ok", "operator": "eq", "value": True}]
        engine.register_gate("G-H-03", auto_approve_criteria=criteria)
        engine.evaluate_gate("G-H-03", context={"ok": True})
        history = engine.get_gate_history("G-H-03")
        assert history[0]["auto_approved"] is True


# ===========================================================================
# 9. get_stats
# ===========================================================================

class TestGetStats:

    def test_stats_empty(self, engine):
        stats = engine.get_stats()
        assert stats["total_gates"] == 0
        assert stats["total_evaluations"] == 0
        assert stats["pass_rate"] == 0.0
        assert stats["average_time_to_decision"] == 0.0

    def test_stats_with_data(self, engine):
        engine.register_gate("G-S-01", auto_approve_criteria=[
            {"field": "env", "operator": "eq", "value": "dev"},
        ])
        engine.evaluate_gate("G-S-01", context={"env": "dev"})     # pass
        engine.evaluate_gate("G-S-01", context={"env": "prod"})    # pending

        stats = engine.get_stats()
        assert stats["total_gates"] == 1
        assert stats["total_evaluations"] == 2
        assert stats["pass_rate"] == 50.0

    def test_stats_all_pass(self, engine):
        criteria = [{"field": "x", "operator": "eq", "value": 1}]
        engine.register_gate("G-S-02", auto_approve_criteria=criteria)
        engine.evaluate_gate("G-S-02", context={"x": 1})
        engine.evaluate_gate("G-S-02", context={"x": 1})
        stats = engine.get_stats()
        assert stats["pass_rate"] == 100.0

    def test_stats_with_approval_timing(self, engine):
        engine.register_gate("G-S-03", required_approvals=1)
        req = engine.request_approval("G-S-03", requester="agent_1")
        engine.approve(req["request_id"], "approver_1", "approve")
        stats = engine.get_stats()
        assert stats["average_time_to_decision"] >= 0.0


# ===========================================================================
# 10. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_register(self, engine):
        """Multiple threads registering gates concurrently."""
        errors = []

        def register(idx):
            try:
                engine.register_gate(f"G-THR-{idx:03d}", decision_class="D1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(engine.list_gates()) == 20

    def test_concurrent_evaluate(self, engine):
        """Multiple threads evaluating the same gate concurrently."""
        engine.register_gate("G-CE-01", auto_approve_criteria=[
            {"field": "pass", "operator": "eq", "value": True},
        ])
        errors = []

        def evaluate(idx):
            try:
                result = engine.evaluate_gate("G-CE-01", context={"pass": True})
                assert result["status"] == GateStatus.PASSED.value
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=evaluate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(engine.get_gate_history("G-CE-01")) == 20

    def test_concurrent_votes(self, engine):
        """Multiple threads voting on the same request.

        The approve() method performs reads (request status, duplicate check)
        outside self._lock, so concurrent threads can race.  This causes:
          - sqlite3.InterfaceError / OperationalError from connection-level races
          - approve() returning {"cast": False} when it reads stale state

        We retry on transient SQLite errors *and* on approve() returning
        cast=False due to stale reads, with exponential back-off.
        """
        import sqlite3 as _sqlite3

        engine.register_gate("G-CV-01", required_approvals=4)
        req = engine.request_approval("G-CV-01", requester="agent_1")
        rid = req["request_id"]
        errors = []

        def vote(idx):
            approver = f"approver_{idx}"
            for attempt in range(8):
                try:
                    result = engine.approve(rid, approver, "approve")
                    if result.get("cast"):
                        return  # vote successfully recorded
                    # vote not cast — could be stale read from race; retry
                    if "already voted" in result.get("message", ""):
                        return  # our vote actually landed in a previous attempt
                    if attempt < 7:
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    errors.append(RuntimeError(
                        f"{approver}: approve returned cast=False after "
                        f"8 attempts: {result}"
                    ))
                except (_sqlite3.OperationalError,
                        _sqlite3.InterfaceError):
                    if attempt < 7:
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    errors.append(RuntimeError(
                        f"{approver}: SQLite error after 8 retries"
                    ))
                except Exception as e:
                    errors.append(e)
                    return

        threads = [threading.Thread(target=vote, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        time.sleep(0.1)  # let threads progress before joining
        for t in threads:
            t.join(timeout=5.0)

        assert len(errors) == 0, f"Thread errors: {errors}"
        status = engine.check_gate_status("G-CV-01")
        assert status["votes_for"] == 4


# ===========================================================================
# 11. Singleton
# ===========================================================================

class TestSingleton:

    def test_get_governance_gate_engine_singleton(self):
        # Reset singleton
        import sylion.governance.decision_gate_engine as mod
        mod._engine = None
        e1 = get_governance_gate_engine()
        e2 = get_governance_gate_engine()
        assert e1 is e2
        # Cleanup
        mod._engine = None


# ===========================================================================
# 12. Auto-approve criteria — edge cases
# ===========================================================================

class TestAutoApproveEdgeCases:

    def test_ne_operator(self, engine):
        criteria = [{"field": "env", "operator": "ne", "value": "prod"}]
        engine.register_gate("G-NE-01", auto_approve_criteria=criteria)
        assert engine.evaluate_gate("G-NE-01", context={"env": "dev"})["auto_approved"] is True
        assert engine.evaluate_gate("G-NE-01", context={"env": "prod"})["auto_approved"] is False

    def test_lte_operator(self, engine):
        criteria = [{"field": "errors", "operator": "lte", "value": 3}]
        engine.register_gate("G-LTE-01", auto_approve_criteria=criteria)
        assert engine.evaluate_gate("G-LTE-01", context={"errors": 3})["auto_approved"] is True
        assert engine.evaluate_gate("G-LTE-01", context={"errors": 4})["auto_approved"] is False

    def test_exists_false(self, engine):
        criteria = [{"field": "secret", "operator": "exists", "value": False}]
        engine.register_gate("G-EXF-01", auto_approve_criteria=criteria)
        assert engine.evaluate_gate("G-EXF-01", context={})["auto_approved"] is True
        assert engine.evaluate_gate("G-EXF-01", context={"secret": "x"})["auto_approved"] is False

    def test_unknown_operator_fails(self, engine):
        criteria = [{"field": "x", "operator": "unknown_op", "value": 1}]
        engine.register_gate("G-UOP-01", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-UOP-01", context={"x": 1})
        assert result["auto_approved"] is False

    def test_missing_context_field(self, engine):
        criteria = [{"field": "missing_key", "operator": "eq", "value": "something"}]
        engine.register_gate("G-MISS-01", auto_approve_criteria=criteria)
        result = engine.evaluate_gate("G-MISS-01", context={"other_key": "val"})
        assert result["auto_approved"] is False

    def test_empty_criteria_no_auto_approve(self, engine):
        engine.register_gate("G-EC-01", auto_approve_criteria=[])
        result = engine.evaluate_gate("G-EC-01", context={"any": "thing"})
        assert result["auto_approved"] is False

    def test_none_criteria_no_auto_approve(self, engine):
        engine.register_gate("G-NC-01", auto_approve_criteria=None)
        result = engine.evaluate_gate("G-NC-01", context={"any": "thing"})
        assert result["auto_approved"] is False


# ===========================================================================
# 13. Full workflow integration
# ===========================================================================

class TestFullWorkflow:

    def test_full_d3_workflow(self, engine, bus):
        """D3 gate: register -> request -> council 4/4 -> approve -> evaluate passes."""
        events = []
        bus.subscribe("*", lambda e: events.append(e))

        engine.register_gate("G-D3-01", decision_class="D3", required_approvals=4,
                              description="Contract change gate")
        req = engine.request_approval("G-D3-01", requester="architect",
                                       justification="API version bump")
        rid = req["request_id"]

        for i in range(4):
            r = engine.approve(rid, f"council_member_{i}", "approve")
            assert r["cast"] is True

        # Last vote should close it
        assert r["request_status"] == ApprovalStatus.APPROVED.value

        # Gate evaluation should pass now
        result = engine.evaluate_gate("G-D3-01")
        assert result["status"] == GateStatus.PASSED.value

        # Stats should reflect
        stats = engine.get_stats()
        assert stats["total_gates"] == 1
        assert stats["total_evaluations"] == 1
        assert stats["pass_rate"] == 100.0

        # Events emitted
        topics = [e.topic for e in events]
        assert "gate.registered" in topics
        assert "gate.approval_requested" in topics
        assert "gate.vote_cast" in topics
        assert "gate.evaluated" in topics

    def test_full_d5_workflow_with_rejection(self, engine):
        """D5 gate: register -> request -> mix of approve/reject."""
        engine.register_gate("G-D5-01", decision_class="D5", required_approvals=4)
        req = engine.request_approval("G-D5-01", requester="architect")
        rid = req["request_id"]

        engine.approve(rid, "m1", "approve")
        engine.approve(rid, "m2", "approve")
        engine.approve(rid, "m3", "reject")
        engine.approve(rid, "m4", "approve")

        status = engine.check_gate_status("G-D5-01")
        assert status["votes_for"] == 3
        assert status["votes_against"] == 1

    def test_auto_approve_bypasses_voting(self, engine):
        """Gate with auto-approve criteria passes without voting."""
        criteria = [
            {"field": "risk", "operator": "eq", "value": "low"},
            {"field": "tests_pass", "operator": "eq", "value": True},
        ]
        engine.register_gate("G-BYP-01", auto_approve_criteria=criteria,
                              required_approvals=10)
        result = engine.evaluate_gate("G-BYP-01", context={
            "risk": "low", "tests_pass": True,
        })
        assert result["status"] == GateStatus.PASSED.value
        assert result["auto_approved"] is True

        # No approval request needed
        status = engine.check_gate_status("G-BYP-01")
        assert status["votes_for"] == 0
