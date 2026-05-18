"""Production deployment Human Gate helpers.

Keeps production deploy gating consistent across deployment surfaces.
"""

from __future__ import annotations

from typing import Any

from sylion.governance.tickets import GovernanceTicket, fetch_by_id, submit

PRODUCTION_TARGETS = {
    "prod",
    "production",
    "live",
    "release",
    "stable",
    "cutover",
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def requires_production_gate(target: str) -> bool:
    return _norm(target) in PRODUCTION_TARGETS


def _ticket_matches_deployment(
    *,
    ticket: Any,
    action: str,
    target: str,
    payload: dict[str, Any],
) -> tuple[bool, str]:
    if not ticket:
        return False, "ticket_missing"
    if ticket.state != "approved":
        return False, f"ticket_state_{ticket.state}"
    if ticket.gate_type != "production":
        return False, "ticket_not_production_gate"

    ticket_payload = ticket.payload or {}
    if _norm(ticket_payload.get("action")) != _norm(action):
        return False, "action_mismatch"

    ticket_target = (
        ticket_payload.get("target")
        or ticket_payload.get("to_stage")
        or ticket_payload.get("target_env")
    )
    if _norm(ticket_target) != _norm(target):
        return False, "target_mismatch"

    for identity_key in ("module_id", "bundle_id", "project_id", "run_id"):
        expected = payload.get(identity_key)
        if expected in (None, ""):
            continue
        actual = ticket_payload.get(identity_key)
        if actual in (None, ""):
            return False, f"{identity_key}_missing"
        if str(actual) != str(expected):
            return False, f"{identity_key}_mismatch"

    return True, "matched"


def ensure_production_deployment_gate(
    *,
    action: str,
    target: str,
    approval_ticket_id: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return allowed state for a production deployment action.

    If no ticket is supplied, a D4 production ticket is created and the caller
    must block. If a ticket is supplied, it must already be approved.
    """
    payload = dict(payload or {})
    if approval_ticket_id:
        ticket = fetch_by_id(approval_ticket_id)
        matched, validation_reason = _ticket_matches_deployment(
            ticket=ticket,
            action=action,
            target=target,
            payload=payload,
        )
        return {
            "allowed": matched,
            "requires_human_gate": True,
            "governance_ticket_id": approval_ticket_id,
            "ticket_state": ticket.state if ticket else "missing",
            "ticket_validation_reason": validation_reason,
            "gate_created": False,
        }

    ticket_id = submit(GovernanceTicket(
        origin="workspace",
        decision_class="D4",
        gate_type="production",
        priority="P0",
        title=f"Production deployment approval required: {action}",
        summary=f"Target '{target}' is production-like and requires explicit Human Gate approval.",
        payload={
            "action": action,
            "target": target,
            "requires_human_gate": True,
            **payload,
        },
        requested_by="deployment_gate",
    ))
    return {
        "allowed": False,
        "requires_human_gate": True,
        "governance_ticket_id": ticket_id,
        "ticket_state": "pending",
        "gate_created": True,
    }
