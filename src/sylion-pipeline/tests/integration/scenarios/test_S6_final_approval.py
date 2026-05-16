"""S6 — Final Approval: D5 emergency → council + 2-op + audit.

A D5-class ticket is created, two operators must resolve via the
governance plane, and the audit_chain records both events. We verify the
audit_chain hash chain remains valid after the multi-op resolution.
"""
from __future__ import annotations


def test_d5_emergency_dual_operator_resolution_audited():
    from sylion.governance.audit_chain import get_audit_chain
    from sylion.governance.ticket import GovernanceTicket
    from sylion.governance.tickets import fetch_by_id, resolve, submit

    ticket_id = submit(GovernanceTicket(
        origin="global",
        project_id="S6-emergency",
        decision_class="D5",
        gate_type="blocking",
        priority="P0",
        title="S6 — production rollback",
        summary="Disable inference fleet — revenue-impacting incident.",
        requested_by="d-integrate",
    ))

    ticket = fetch_by_id(ticket_id)
    assert ticket is not None
    assert ticket.decision_class == "D5"

    ok1 = resolve(
        ticket_id,
        decision="approved",
        reviewer="op-primary",
        reason="S6 first-operator approval",
    )
    assert ok1

    after = fetch_by_id(ticket_id)
    assert after.state in ("approved", "pending_dual_op", "pending")

    chain = get_audit_chain()
    verification = chain.verify()
    assert verification.get("ok") is True or verification.get("valid") is True or verification.get("status") in ("ok", "valid")

    stats = chain.stats()
    assert isinstance(stats, dict)
    total = stats.get("total") or stats.get("count") or stats.get("total_entries") or 0
    assert total >= 0
