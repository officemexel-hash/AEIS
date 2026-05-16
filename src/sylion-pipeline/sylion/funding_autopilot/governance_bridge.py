"""
SYLION Funding Autopilot — Governance Bridge (K2)

Connects funding actions to the unified governance ticket plane.
Every significant mutating action in funding creates a governance ticket
so that the Council / Human Gate can approve before execution.

Hook v1.0 (2026-04-24)
Changes: initial
Owner: K-SURF

Decision-class mapping
----------------------
  D2  scan trigger, call/programme creation  (standard)
  D3  idea→project, application creation     (significant, financial)
  D4  final submission                        (critical, Human Gate)

Usage
-----
    from sylion.funding_autopilot.governance_bridge import (
        submit_scan_ticket,
        submit_call_creation_ticket,
        submit_application_creation_ticket,
        check_approved,
    )

    ticket_id = submit_scan_ticket(job_id="abc", force_refresh=True, calls_found=12)
    if check_approved(ticket_id):
        ... proceed ...
"""

from __future__ import annotations

import time
from typing import Any

from sylion.governance.tickets import submit, fetch_by_id, resolve
from sylion.governance.ticket import GovernanceTicket


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> float:
    return time.time()


def _base_ticket(
    title: str,
    decision_class: str,
    gate_type: str,
    priority: str,
    summary: str = "",
    payload: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> GovernanceTicket:
    """Build a GovernanceTicket with funding origin and sensible defaults."""
    return GovernanceTicket(
        origin="funding",
        project_id=project_id,
        decision_class=decision_class,
        gate_type=gate_type,
        priority=priority,
        title=title,
        summary=summary,
        payload=payload or {},
        requested_by="funding_autopilot",
    )


# ---------------------------------------------------------------------------
# Ticket submitters
# ---------------------------------------------------------------------------

def submit_scan_ticket(
    job_id: str,
    force_refresh: bool = False,
    since_days: int = 30,
    calls_found: int = 0,
) -> str:
    """Submit a governance ticket for funding scan trigger.

    Decision class: D2 (standard — mutates catalog but is exploratory).
    """
    return submit(_base_ticket(
        title=f"Funding scan triggered (job {job_id[:8]})",
        decision_class="D2",
        gate_type="non_blocking" if not force_refresh else "blocking",
        priority="P1" if force_refresh else "P2",
        summary=(
            f"Automatic funding call scan requested. "
            f"force_refresh={force_refresh}, since_days={since_days}. "
            f"Calls found: {calls_found}."
        ),
        payload={
            "job_id": job_id,
            "force_refresh": force_refresh,
            "since_days": since_days,
            "calls_found": calls_found,
            "action": "scan_trigger",
        },
    ))


def submit_call_creation_ticket(
    call_data: dict[str, Any],
) -> str:
    """Submit a governance ticket for manual funding call creation.

    Decision class: D2 (blocking — data integrity).
    """
    title = call_data.get("title", "Untitled call")
    code = call_data.get("code", "")
    return submit(_base_ticket(
        title=f"Create funding call: {title}",
        decision_class="D2",
        gate_type="blocking",
        priority="P2",
        summary=f"Manual creation of funding call (code={code}) in catalogue.",
        payload={
            "action": "call_creation",
            "call_data": call_data,
        },
    ))


def submit_programme_creation_ticket(
    programme_data: dict[str, Any],
) -> str:
    """Submit a governance ticket for manual funding programme creation.

    Decision class: D2 (blocking — data integrity).
    """
    name = programme_data.get("name", "Untitled programme")
    return submit(_base_ticket(
        title=f"Create funding programme: {name}",
        decision_class="D2",
        gate_type="blocking",
        priority="P2",
        summary="Manual creation of funding programme source.",
        payload={
            "action": "programme_creation",
            "programme_data": programme_data,
        },
    ))


def submit_idea_conversion_ticket(
    idea_id: str,
    project_id: str = "",
    call_id: str | None = None,
    company_id: str = "default",
    target_trl: int = 4,
    actor: str = "funding_autopilot",
) -> str:
    """Submit a governance ticket for idea → project conversion.

    Decision class: D3 (significant — commits organisational resources).
    """
    return submit(_base_ticket(
        title=f"Convert funding idea {idea_id[:8]} to project",
        decision_class="D3",
        gate_type="blocking",
        priority="P2",
        summary=(
            "Conversion of an AI-generated funding idea into a tracked project. "
            "Commits organisational resources and begins formal preparation."
        ),
        payload={
            "action": "idea_conversion",
            "idea_id": idea_id,
            "project_id": project_id,
            "call_id": call_id,
            "company_id": company_id,
            "target_trl": target_trl,
            "actor": actor,
        },
        project_id=project_id or None,
    ))


def submit_application_creation_ticket(
    application_id: str,
    project_id: str,
    call_id: str | None = None,
    amount: float = 0.0,
) -> str:
    """Submit a governance ticket for grant application creation.

    Decision class: D3 (financial — legal / budget commitment).
    """
    return submit(_base_ticket(
        title=f"Create grant application {application_id[:8]}",
        decision_class="D3",
        gate_type="financial",
        priority="P1" if amount > 500_000 else "P2",
        summary=(
            f"Formal grant application package creation. "
            f"Call={call_id}, requested amount ≈ {amount:,.0f} EUR."
        ),
        payload={
            "action": "application_creation",
            "application_id": application_id,
            "project_id": project_id,
            "call_id": call_id,
            "amount": amount,
        },
        project_id=project_id,
    ))


def submit_submission_ticket(
    application_id: str,
    session_id: str,
    portal: str = "",
    amount: float = 0.0,
) -> str:
    """Submit a governance ticket for final grant submission.

    Decision class: D4 (critical — Human Gate required).
    """
    return submit(_base_ticket(
        title=f"Final submission: application {application_id[:8]}",
        decision_class="D4",
        gate_type="financial",
        priority="P0" if amount > 1_000_000 else "P1",
        summary=(
            "Final portal submission of a grant application. "
            f"Portal={portal}, amount ≈ {amount:,.0f} EUR. "
            "Requires explicit legal, budget, and document confirmation."
        ),
        payload={
            "action": "final_submission",
            "application_id": application_id,
            "session_id": session_id,
            "portal": portal,
            "amount": amount,
        },
    ))


# ---------------------------------------------------------------------------
# Approval helpers
# ---------------------------------------------------------------------------

def check_approved(ticket_id: str) -> bool:
    """Return True if the governance ticket is in approved state."""
    ticket = fetch_by_id(ticket_id)
    if ticket is None:
        return False
    return ticket.state == "approved"


def check_pending(ticket_id: str) -> bool:
    """Return True if the governance ticket is still pending."""
    ticket = fetch_by_id(ticket_id)
    if ticket is None:
        return False
    return ticket.state == "pending"


def approve_for_test(ticket_id: str, reviewer: str = "test_operator") -> bool:
    """Resolve a ticket as approved (intended for tests only)."""
    return resolve(ticket_id, decision="approved", reviewer=reviewer)
