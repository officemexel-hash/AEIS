"""
SYLION Governance -- Tickets public Hook API.

Module-level facade for the unified governance ticket plane.
Other namespaces (skills, memory, funding_autopilot, operator_mobile,
project_mode, autonomy, execution_guard) MUST go through this module instead
of building their own HG / approval planes.

Hook v1.0 (2026-04-24).
Changes:
  - 2026-04-24 initial -- exposes submit/fetch_pending/resolve/withdraw.
  - 2026-04-25 (A5) -- VALID_ORIGINS extended with "autonomy".
  - 2026-04-28 (BE-8.2) -- VALID_ORIGINS extended with "round_meta" so
    FE wave-4 round_meta wizards can submit governance tickets without
    falling back to a misleading "workspace" origin.
  - 2026-05-13 (R3.4) -- VALID_ORIGINS extended with "execution_guard" so
    policy-based execution approvals land in the unified ticket plane.

Owner: A-GOV. Read-only for B / K / D.

Valid origins (re-exported from `sylion.governance.ticket.VALID_ORIGINS`):
  workspace | global | funding | mobile | skill | council |
  autonomy | round_meta | execution_guard

Valid gate_type (re-exported from `sylion.governance.ticket.VALID_GATE_TYPES`):
  blocking | non_blocking | batch | emergency | financial | legal |
  production | security | external_action | final

Caller cheatsheet (Hook v1.0):
  B-ADAPT (skills runtime):
      submit(GovernanceTicket(origin="skill",
                              decision_class="D2",
                              gate_type="non_blocking",
                              payload={"skill_id": ..., "manifest_hash": ...}))
  B-ADAPT (mobile bridge):
      submit(GovernanceTicket(origin="mobile",
                              decision_class="D1",
                              gate_type="non_blocking",
                              payload={"device_id": ..., "intent": ...}))
  K-SURF (funding bridge):
      submit(GovernanceTicket(origin="funding",
                              decision_class="D3",
                              gate_type="financial",
                              payload={"application_id": ..., "amount": ...}))
  A-GOV (autonomy stage machine, internal):
      submit(GovernanceTicket(origin="autonomy",
                              decision_class="D2..D5",
                              gate_type="blocking",
                              payload={"transition_id": ..., "from_phase": ...}))
  A-GOV (execution guard approvals):
      submit(GovernanceTicket(origin="execution_guard",
                              decision_class="D3",
                              gate_type="production",
                              payload={"execution_guard_request_id": ...}))

Example:
    from sylion.governance.tickets import submit, GovernanceTicket

    ticket_id = submit(GovernanceTicket(
        origin="funding",
        project_id="proj_123",
        decision_class="D3",
        gate_type="financial",
        priority="P1",
        title="Submit Horizon Europe application",
        payload={"application_id": "app_456", "portal": "EC", "amount": 250000},
        requested_by="funding_autopilot",
    ))
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sylion.governance.ticket import (
    GovernanceTicket,
    TicketStore,
    VALID_DECISION_CLASSES,
    VALID_GATE_TYPES,
    VALID_ORIGINS,
    VALID_PRIORITIES,
    VALID_STATES,
    get_ticket_store,
    reset_ticket_store,
)

log = logging.getLogger("sylion.governance.tickets")

__all__ = [
    "GovernanceTicket",
    "TicketStore",
    "VALID_DECISION_CLASSES",
    "VALID_GATE_TYPES",
    "VALID_ORIGINS",
    "VALID_PRIORITIES",
    "VALID_STATES",
    "get_ticket_store",
    "reset_ticket_store",
    "submit",
    "fetch_pending",
    "fetch_by_id",
    "resolve",
    "withdraw",
    "escalate",
    "stats",
    "register_post_resolve_hook",
    "clear_post_resolve_hooks",
]


# ---------------------------------------------------------------------------
# W14 BE-6 — post-resolve hook registry
# ---------------------------------------------------------------------------
# Listeners that need to mutate downstream state when a ticket is resolved
# (e.g. project_mode mark canon_frozen_at on approval) register a callable
# here. Hooks are exception-isolated: a faulty hook MUST NOT prevent other
# hooks from firing or surface back to the caller of resolve().

_PostResolveHook = Callable[[GovernanceTicket, str], None]
_POST_RESOLVE_HOOKS: list[_PostResolveHook] = []


def register_post_resolve_hook(fn: _PostResolveHook) -> None:
    """Register a callable invoked after a ticket transitions to a final state.

    The hook receives ``(ticket, decision)`` where ``decision`` is one of
    {approved, rejected, expired}. Hooks should be idempotent — they may
    fire after a no-op resolve in pathological retry scenarios.
    """
    if fn in _POST_RESOLVE_HOOKS:
        return
    _POST_RESOLVE_HOOKS.append(fn)


def clear_post_resolve_hooks() -> None:
    """Drop all registered hooks. Test helper — production code never calls."""
    _POST_RESOLVE_HOOKS.clear()


def _fire_post_resolve_hooks(ticket: GovernanceTicket, decision: str) -> None:
    """Fire each registered hook under its own try/except so one bad hook
    cannot crash the others or the resolve() return value."""
    for hook in list(_POST_RESOLVE_HOOKS):
        try:
            hook(ticket, decision)
        except Exception:                              # noqa: BLE001
            log.warning(
                "governance.tickets post-resolve hook %s raised; continuing",
                getattr(hook, "__name__", repr(hook)),
                exc_info=True,
            )


def submit(ticket: GovernanceTicket) -> str:
    """Submit a new governance ticket.

    Hook v1.0 (2026-04-24).
    Changes: initial.

    Args:
        ticket: GovernanceTicket. ticket_id auto-generated if empty.
                origin must be one of VALID_ORIGINS.

    Returns:
        ticket_id (uuid hex).

    Raises:
        ValueError on invalid origin/decision_class/gate_type/priority/state.
    """
    return get_ticket_store().submit(ticket)


def fetch_pending(
    operator_id: str | None = None,
    origin: str | None = None,
    project_id: str | None = None,
    priority: str | None = None,
) -> list[GovernanceTicket]:
    """List pending tickets, optionally filtered.

    Hook v1.0 (2026-04-24).
    Changes: initial.

    Args:
        operator_id: reserved for per-operator routing (currently unused).
        origin: filter by origin enum.
        project_id: filter by project.
        priority: filter by P0..P4.

    Returns:
        list of GovernanceTicket sorted by priority ASC then created_at ASC.
    """
    return get_ticket_store().fetch_pending(
        operator_id=operator_id, origin=origin,
        project_id=project_id, priority=priority,
    )


def fetch_by_id(ticket_id: str) -> GovernanceTicket | None:
    """Return a single ticket or None.

    Hook v1.0 (2026-04-24).
    Changes: initial.
    """
    return get_ticket_store().get(ticket_id)


def resolve(ticket_id: str, decision: str,
            reason: str | None = None, reviewer: str = "") -> bool:
    """Resolve a pending ticket.

    Hook v1.0 (2026-04-24).
    Changes:
      - initial.
      - 2026-04-28 (BE-6) — fire ``register_post_resolve_hook`` listeners
        after a successful resolve so downstream planes (project_mode
        round_meta freeze completion, …) can mutate their own state.

    Args:
        ticket_id: target ticket.
        decision: 'approved' | 'rejected' | 'expired'.
        reason: free-text rationale.
        reviewer: operator id.

    Returns:
        True if state transitioned, False if missing/already-final.

    Raises:
        ValueError on invalid decision.
    """
    transitioned = get_ticket_store().resolve(ticket_id, decision, reason, reviewer)
    if transitioned and _POST_RESOLVE_HOOKS:
        ticket = get_ticket_store().get(ticket_id)
        if ticket is not None:
            _fire_post_resolve_hooks(ticket, decision)
    return transitioned


def withdraw(ticket_id: str, reason: str = "", actor: str = "") -> bool:
    """Withdraw a pending ticket (creator-side cancel).

    Hook v1.0 (2026-04-24).
    Changes: initial.

    Returns True if state transitioned.
    """
    return get_ticket_store().withdraw(ticket_id, reason, actor)


def escalate(ticket_id: str, reason: str = "", actor: str = "") -> bool:
    """Escalate a pending ticket to higher review tier.

    Hook v1.0 (2026-04-24).
    Changes: initial.
    """
    return get_ticket_store().escalate(ticket_id, reason, actor)


def stats() -> dict[str, Any]:
    """Return aggregate counts (total, by_state, by_origin, by_priority).

    Hook v1.0 (2026-04-24).
    Changes: initial.
    """
    return get_ticket_store().stats()
