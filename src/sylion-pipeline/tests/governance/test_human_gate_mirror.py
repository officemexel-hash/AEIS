"""Wave A1 -- Legacy human_gate.create_request mirrors to TicketStore.

Verifies that existing /api/v1/gates/human/* flow produces a corresponding
GovernanceTicket with origin='global', so the unified ticket plane
sees ALL human-gate decisions (not only newly-submitted ones).
"""

from __future__ import annotations

import pytest

from sylion.governance.human_gate import HumanGate, reset_human_gate
from sylion.governance.ticket import (
    TicketStore,
    get_ticket_store,
    reset_ticket_store,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_human_gate()
    reset_ticket_store()
    yield
    reset_human_gate()
    reset_ticket_store()


@pytest.fixture
def gate():
    # Bind both singletons to fresh in-memory stores.
    ts = reset_ticket_store(":memory:")
    hg = HumanGate(db_path=":memory:")
    return hg


def _ticket_for(request_id: str):
    return get_ticket_store().get(request_id)


class TestCreateRequestMirror:

    def test_create_request_creates_governance_ticket(self, gate):
        result = gate.create_request(title="Approve deploy")
        ticket = _ticket_for(result["request_id"])
        assert ticket is not None
        assert ticket.origin == "global"
        assert ticket.state == "pending"

    def test_mirrored_ticket_carries_title(self, gate):
        result = gate.create_request(title="Refactor pipeline")
        ticket = _ticket_for(result["request_id"])
        assert ticket.title == "Refactor pipeline"

    def test_mirrored_ticket_carries_requested_by(self, gate):
        result = gate.create_request(title="t", requested_by="alice")
        ticket = _ticket_for(result["request_id"])
        assert ticket.requested_by == "alice"

    def test_mirrored_ticket_payload_includes_legacy_gate_id(self, gate):
        result = gate.create_request(gate_id="G-007", title="t")
        ticket = _ticket_for(result["request_id"])
        assert ticket.payload.get("legacy_gate_id") == "G-007"

    def test_mirrored_ticket_picks_up_project_id_from_context(self, gate):
        result = gate.create_request(
            title="t", context_json={"project_id": "proj_xyz"},
        )
        ticket = _ticket_for(result["request_id"])
        assert ticket.project_id == "proj_xyz"

    def test_mirrored_ticket_picks_up_workspace_project_id(self, gate):
        result = gate.create_request(
            title="t",
            context_json={"workspace_project_id": "ws_proj_1"},
        )
        ticket = _ticket_for(result["request_id"])
        assert ticket.project_id == "ws_proj_1"

    def test_mirrored_ticket_preserves_canonical_priority(self, gate):
        result = gate.create_request(
            title="t",
            context_json={"decision_class": "D3", "governance_priority": "P1"},
        )
        ticket = _ticket_for(result["request_id"])
        assert ticket.priority == "P1"

    def test_request_id_equals_ticket_id(self, gate):
        result = gate.create_request(title="t")
        ticket = _ticket_for(result["request_id"])
        assert ticket.ticket_id == result["request_id"]


class TestSubmitReviewMirror:

    def test_approved_review_resolves_mirror(self, gate):
        result = gate.create_request(title="r")
        gate.submit_review(
            request_id=result["request_id"],
            reviewer="alice",
            decision="approved",
            rationale="LGTM",
        )
        ticket = _ticket_for(result["request_id"])
        assert ticket.state == "approved"
        assert ticket.resolved_by == "alice"
        assert ticket.resolution_reason == "LGTM"

    def test_rejected_review_resolves_mirror(self, gate):
        result = gate.create_request(title="r")
        gate.submit_review(
            request_id=result["request_id"],
            reviewer="bob",
            decision="rejected",
            rationale="bad design",
        )
        ticket = _ticket_for(result["request_id"])
        assert ticket.state == "rejected"

    def test_needs_info_keeps_mirror_pending(self, gate):
        # needs_info is NOT a terminal state in the unified plane.
        result = gate.create_request(title="r")
        gate.submit_review(
            request_id=result["request_id"],
            reviewer="carol",
            decision="needs_info",
            rationale="more context please",
        )
        ticket = _ticket_for(result["request_id"])
        assert ticket.state == "pending"


class TestEscalateMirror:

    def test_escalate_marks_mirror_escalated(self, gate):
        result = gate.create_request(title="r")
        gate.escalate_request(
            result["request_id"], reason="SLA breach",
        )
        ticket = _ticket_for(result["request_id"])
        assert ticket.state == "escalated"


class TestUnifiedView:

    def test_legacy_human_gate_visible_via_unified_pending(self, gate):
        # Submit via legacy human_gate.
        a = gate.create_request(title="legacy a")
        b = gate.create_request(title="legacy b")
        # Submit one resolved.
        gate.submit_review(a["request_id"], "alice", "approved", "ok")

        # Unified pending should show only b.
        pending = get_ticket_store().fetch_pending(origin="global")
        ids = {t.ticket_id for t in pending}
        assert b["request_id"] in ids
        assert a["request_id"] not in ids
