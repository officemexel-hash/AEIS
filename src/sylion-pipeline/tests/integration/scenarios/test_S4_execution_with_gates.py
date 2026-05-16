"""S4 — Execution with Gates: D3 task → blocking HG → mobile approve → execute.

Submit a D3 governance ticket from workspace, push through the operator
mobile bridge, resolve as approved, verify the ticket transitions to
'approved' state and that mobile bridge knows about the notification.
"""
from __future__ import annotations


def test_d3_ticket_blocked_then_mobile_approved_then_resolved():
    from sylion.governance.ticket import GovernanceTicket
    from sylion.governance.tickets import (
        fetch_by_id,
        fetch_pending,
        resolve,
        submit,
    )
    from sylion.operator_mobile import (
        get_operator_mobile_bridge,
    )

    bridge = get_operator_mobile_bridge()

    ticket_id = submit(GovernanceTicket(
        origin="workspace",
        project_id="S4-exec",
        decision_class="D3",
        gate_type="blocking",
        priority="P1",
        title="S4 — execute migration step",
        summary="Migrate user-events table; requires HG approval.",
        requested_by="d-integrate",
    ))
    ticket = fetch_by_id(ticket_id)
    assert ticket is not None
    assert ticket.state == "pending"
    assert ticket.gate_type == "blocking"

    pending_before = fetch_pending()
    assert any(t.ticket_id == ticket_id for t in pending_before)

    payload = bridge.build_payload_from_ticket(ticket, operator_id="op-1")
    bridge.notify_pending_ticket(payload)
    state = bridge.get_notification_state(ticket_id)
    assert state is not None
    assert state["ticket_id"] == ticket_id

    ok = resolve(
        ticket_id,
        decision="approved",
        reviewer="op-1",
        reason="S4 mobile-approved by operator",
    )
    assert ok

    after = fetch_by_id(ticket_id)
    assert after.state == "approved"
    pending_after = fetch_pending()
    assert all(t.ticket_id != ticket_id for t in pending_after)
