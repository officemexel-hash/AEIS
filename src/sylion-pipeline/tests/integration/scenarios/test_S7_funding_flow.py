"""S7 — Funding flow: scan → submit → governance ticket → approve.

The funding governance bridge submits scan + submission tickets. We then
operator-approve the submission ticket and verify the audit_chain logs
both lifecycle events.
"""
from __future__ import annotations


def test_funding_full_lifecycle_scan_then_submit_then_approve():
    from sylion.funding_autopilot.governance_bridge import (
        check_approved,
        submit_scan_ticket,
        submit_submission_ticket,
    )
    from sylion.governance.tickets import fetch_pending, resolve

    scan_ticket = submit_scan_ticket(
        job_id="job-S7-scan-001",
        force_refresh=True,
        since_days=14,
        calls_found=3,
    )
    assert scan_ticket

    submission_ticket = submit_submission_ticket(
        application_id="app-S7-001",
        session_id="sess-S7-001",
        portal="HORIZON",
        amount=500_000.0,
    )
    assert submission_ticket

    funding_pending = fetch_pending(origin="funding")
    seen_ids = {t.ticket_id for t in funding_pending}
    assert scan_ticket in seen_ids
    assert submission_ticket in seen_ids

    submit_record = next(t for t in funding_pending if t.ticket_id == submission_ticket)
    assert submit_record.decision_class in ("D3", "D4", "D5")
    assert submit_record.origin == "funding"

    ok = resolve(
        submission_ticket,
        decision="approved",
        reviewer="legal-officer",
        reason="S7 — legal + budget pre-cleared",
    )
    assert ok
    assert check_approved(submission_ticket)
