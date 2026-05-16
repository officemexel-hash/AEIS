"""Wave A5 -- autonomy stage machine attached to governance spine (RB-013).

DoD: Autonomy is no longer an isolated endpoint. Every transition with
decision_class > D0 submits a GovernanceTicket (origin='autonomy') AND
appends a project.autonomy_update entry to the unified audit chain. The
state machine cycles deterministically rather than getting stuck on
'observe'.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.governance.audit_chain as _chain_mod
import sylion.governance.evidence_spine as _spine_mod
import sylion.governance.ticket as _ticket_mod
from sylion.api.autonomy_routes import router as autonomy_router
from sylion.autonomy.stage_machine import (
    AutonomyPhase,
    PHASE_ORDER,
    reset_autonomy_machine,
)


@pytest.fixture(autouse=True)
def _reset(tmp_path):
    # Reset spine/audit_chain/ticket_store/autonomy machine in dependency order.
    _spine_mod.reset_governance_spine(":memory:")
    _chain_mod.reset_audit_chain(":memory:")
    _ticket_mod.reset_ticket_store(":memory:")
    reset_autonomy_machine(":memory:", event_threshold=5)
    yield
    _spine_mod.reset_governance_spine(":memory:")
    _chain_mod.reset_audit_chain(":memory:")
    _ticket_mod.reset_ticket_store(":memory:")
    reset_autonomy_machine(":memory:", event_threshold=5)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(autonomy_router)
    return TestClient(app)


def _ev_n(machine, project_id: str, n: int) -> None:
    for _ in range(n):
        machine.record_event(project_id)


# ---------------------------------------------------------------------------
# State machine basics
# ---------------------------------------------------------------------------

class TestInitialState:

    def test_unknown_project_starts_in_observe(self):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        state = get_autonomy_machine().get_state("p_new")
        assert state["phase"] == "observe"
        assert state["event_count"] == 0
        assert state["ready_to_advance"] is False

    def test_observe_blocks_advance_below_threshold(self):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        machine = get_autonomy_machine()
        machine.record_event("p")
        machine.record_event("p")
        with pytest.raises(RuntimeError):
            machine.advance("p")

    def test_observe_unblocks_at_threshold(self):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        machine = get_autonomy_machine()
        _ev_n(machine, "p", 5)
        state = machine.get_state("p")
        assert state["ready_to_advance"] is True
        # Now advance succeeds.
        t = machine.advance("p")
        assert t.from_phase == "observe"
        assert t.to_phase == "propose"


# ---------------------------------------------------------------------------
# Loop traversal -- advance cycles through phases
# ---------------------------------------------------------------------------

class TestPhaseLoop:

    def test_low_risk_loop_observe_propose_simulate_execute_observe(self):
        """5 events -> propose -> simulate -> execute_low_risk -> observe."""
        from sylion.autonomy.stage_machine import get_autonomy_machine
        machine = get_autonomy_machine()
        _ev_n(machine, "p", 5)
        seq = []
        # First leaves observe -> propose.
        seq.append(machine.advance("p").to_phase)
        # propose -> simulate.
        seq.append(machine.advance("p").to_phase)
        # simulate -> execute_low_risk.
        seq.append(machine.advance("p").to_phase)
        # execute_low_risk -> observe (loop closed).
        seq.append(machine.advance("p").to_phase)
        assert seq == ["propose", "simulate", "execute_low_risk", "observe"]

    def test_state_phase_advances_after_each_step(self):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        machine = get_autonomy_machine()
        _ev_n(machine, "p", 5)
        machine.advance("p")
        assert machine.get_state("p")["phase"] == "propose"
        machine.advance("p")
        assert machine.get_state("p")["phase"] == "simulate"


# ---------------------------------------------------------------------------
# Decision class > D0 -> ticket + escalate
# ---------------------------------------------------------------------------

class TestDecisionClassEscalation:

    @pytest.mark.parametrize("dc", ["D2", "D3", "D4", "D5"])
    def test_d2_plus_forces_escalate_and_ticket(self, dc):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        machine = get_autonomy_machine()
        _ev_n(machine, "p", 5)
        t = machine.advance("p", decision_class=dc, reason=f"sim says {dc}")
        assert t.to_phase == "escalate"
        assert t.ticket_id is not None
        # Ticket exists in the unified store.
        ticket = _ticket_mod.get_ticket_store().get(t.ticket_id)
        assert ticket is not None
        assert ticket.origin == "autonomy"
        assert ticket.project_id == "p"
        assert ticket.decision_class == dc
        assert ticket.gate_type == "blocking"

    @pytest.mark.parametrize("dc", ["D0", "D1"])
    def test_d0_d1_no_ticket(self, dc):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        machine = get_autonomy_machine()
        _ev_n(machine, "p", 5)
        t = machine.advance("p", decision_class=dc)
        assert t.ticket_id is None
        assert t.to_phase == "propose"  # normal next-phase, not escalate


# ---------------------------------------------------------------------------
# Audit chain integration
# ---------------------------------------------------------------------------

class TestAuditChainEntries:

    def test_every_transition_writes_audit_entry(self):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        from sylion.governance import get_audit_chain
        machine = get_autonomy_machine()
        _ev_n(machine, "p", 5)
        t1 = machine.advance("p")
        t2 = machine.advance("p", decision_class="D3", reason="bug detected")
        # Both transitions produced audit entries.
        assert t1.audit_entry_id is not None
        assert t2.audit_entry_id is not None
        # Chain has both entries on this project_id.
        chain = get_audit_chain()
        entries = chain.entries_for("p")
        assert len(entries) >= 2

    def test_chain_remains_verifiable_after_autonomy_runs(self):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        from sylion.governance import get_audit_chain
        machine = get_autonomy_machine()
        _ev_n(machine, "p", 5)
        machine.advance("p")
        machine.advance("p", decision_class="D2", reason="risk")
        machine.advance("p")
        result = get_audit_chain().verify()
        assert result["valid"] is True
        assert result["tampered_count"] == 0


# ---------------------------------------------------------------------------
# Steer (operator override)
# ---------------------------------------------------------------------------

class TestSteer:

    def test_steer_jumps_directly_and_tickets(self):
        from sylion.autonomy.stage_machine import get_autonomy_machine
        machine = get_autonomy_machine()
        # No need to satisfy event_threshold for steer.
        t = machine.steer("p", AutonomyPhase.REVIEW, actor="op-1",
                          reason="bypass for incident")
        assert t.from_phase == "observe"
        assert t.to_phase == "review"
        assert t.ticket_id is not None
        # Ticket has D2 default for steers.
        ticket = _ticket_mod.get_ticket_store().get(t.ticket_id)
        assert ticket.decision_class == "D2"
        assert ticket.requested_by == "op-1"


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

class TestEndpoints:

    def test_state_endpoint_returns_initial(self, client):
        r = client.get("/api/v1/autonomy/p_alpha/state")
        assert r.status_code == 200
        body = r.json()
        assert body["phase"] == "observe"
        assert body["event_count"] == 0

    def test_event_endpoint_increments_counter(self, client):
        for _ in range(3):
            r = client.post("/api/v1/autonomy/p_alpha/event")
            assert r.status_code == 200
        body = client.get("/api/v1/autonomy/p_alpha/state").json()
        assert body["event_count"] == 3
        assert body["ready_to_advance"] is False

    def test_advance_endpoint_409_below_threshold(self, client):
        r = client.post(
            "/api/v1/autonomy/p_beta/advance",
            json={"decision_class": "D0"},
        )
        assert r.status_code == 409

    def test_advance_endpoint_after_threshold(self, client):
        for _ in range(5):
            client.post("/api/v1/autonomy/p_gamma/event")
        r = client.post(
            "/api/v1/autonomy/p_gamma/advance",
            json={"decision_class": "D0", "reason": "ok"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["from_phase"] == "observe"
        assert body["to_phase"] == "propose"
        assert body["ticket_id"] is None

    def test_advance_endpoint_d2_creates_ticket(self, client):
        for _ in range(5):
            client.post("/api/v1/autonomy/p_delta/event")
        r = client.post(
            "/api/v1/autonomy/p_delta/advance",
            json={"decision_class": "D2", "reason": "risky"},
        )
        body = r.json()
        assert body["to_phase"] == "escalate"
        assert body["ticket_id"] is not None

    def test_steer_endpoint(self, client):
        r = client.post(
            "/api/v1/autonomy/p_eps/steer",
            json={"target_phase": "review", "actor": "op-1",
                  "reason": "incident"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["to_phase"] == "review"
        assert body["ticket_id"] is not None

    def test_steer_unknown_phase_400(self, client):
        r = client.post(
            "/api/v1/autonomy/p_eps/steer",
            json={"target_phase": "not_a_phase", "actor": "op-1"},
        )
        assert r.status_code == 400

    def test_transitions_endpoint_returns_history(self, client):
        for _ in range(5):
            client.post("/api/v1/autonomy/p_h/event")
        client.post("/api/v1/autonomy/p_h/advance", json={"decision_class": "D0"})
        client.post("/api/v1/autonomy/p_h/advance", json={"decision_class": "D2"})
        r = client.get("/api/v1/autonomy/p_h/transitions")
        body = r.json()
        assert len(body) == 2
        # Ordered DESC by timestamp -> first is the D2 one.
        assert body[0]["decision_class"] == "D2"
