"""
SYLION Governance -- Unified Audit Chain (Wave A2).

Single hash-chained log for ALL governance-relevant events across origins:
  - GovernanceTicket lifecycle (submitted/resolved/withdrawn/escalated)
  - Workspace lifecycle (launch, approve_masterplan, freeze_canon, iterate, reject)
  - Project lifecycle transitions

This module is a *facade* over `GovernanceSpine` (evidence_spine.py).
GovernanceSpine provides the underlying SHA-256 hash chain (prev_hash -> entry_hash).
GovernanceAuditChain provides governance-flavored entry-points so workspace
approvals and global decisions land in the SAME ordered, tamper-evident log.

The DoD for Wave A2 is satisfied because:
  1. Every TicketStore.submit/resolve/withdraw/escalate appends to this chain.
  2. The chain is shared by ALL origins (workspace/global/funding/mobile/skill/council).
  3. `audit_chain_ref` on each GovernanceTicket points back to its first entry.
  4. `verify()` confirms tamper integrity across the entire chain.

Hook v1.0 (2026-04-25 -- Wave A2).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus
from sylion.governance.evidence_spine import (
    GovernanceSpine,
    get_governance_spine,
    reset_governance_spine,
)

log = logging.getLogger("sylion.governance.audit_chain")


# Whitelisted event types so callers can't drift into typos silently.
TICKET_EVENT_TYPES: frozenset[str] = frozenset({
    "submitted", "resolved", "withdrawn", "escalated", "audit_attached",
})
WORKSPACE_EVENT_TYPES: frozenset[str] = frozenset({
    "launch", "approve_masterplan", "reject_masterplan", "iterate_masterplan",
    "freeze_canon", "freeze_section", "pause", "resume",
})
PROJECT_EVENT_TYPES: frozenset[str] = frozenset({
    "create", "transition", "autonomy_update", "audit_recorded",
})


def _content_hash(payload: dict[str, Any] | None) -> str:
    """Deterministic SHA-256 hash of a payload dict (or empty)."""
    raw = json.dumps(payload or {}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class GovernanceAuditChain:
    """Facade over GovernanceSpine providing governance-domain entry-points.

    All methods write to ONE underlying hash chain; entries can be retrieved
    by decision_id (ticket_id / workspace_id / project_id) or globally.
    """

    def __init__(self,
                 spine: GovernanceSpine | None = None,
                 db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._spine = spine if spine is not None else get_governance_spine(
            db_path=db_path, event_bus=event_bus,
        )
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Tickets
    # ------------------------------------------------------------------

    def append_ticket_event(
        self,
        ticket_id: str,
        event_type: str,
        actor: str = "",
        payload: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
    ) -> str:
        """Append a ticket lifecycle event to the unified chain.

        Returns the spine entry_id, which is what becomes
        `GovernanceTicket.audit_chain_ref` for the initial submit.
        """
        if event_type not in TICKET_EVENT_TYPES:
            raise ValueError(
                f"invalid ticket event_type '{event_type}', "
                f"must be one of {sorted(TICKET_EVENT_TYPES)}"
            )
        body = {
            "surface": "ticket",
            "event_type": event_type,
            "actor": actor,
            "ticket_id": ticket_id,
            "payload": payload or {},
        }
        with self._lock:
            entry = self._spine.append_entry(
                decision_id=ticket_id,
                entry_type="decision",
                content_hash=_content_hash(body),
                snapshot_id=snapshot_id,
                evidence_pack=body,
                metadata={"surface": "ticket", "event_type": event_type},
            )
        return entry["entry_id"]

    # ------------------------------------------------------------------
    # Workspace
    # ------------------------------------------------------------------

    def append_workspace_event(
        self,
        workspace_id: str,
        event_type: str,
        actor: str = "",
        project_id: str | None = None,
        payload: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
    ) -> str:
        """Append a workspace lifecycle event to the unified chain."""
        if event_type not in WORKSPACE_EVENT_TYPES:
            raise ValueError(
                f"invalid workspace event_type '{event_type}', "
                f"must be one of {sorted(WORKSPACE_EVENT_TYPES)}"
            )
        body = {
            "surface": "workspace",
            "event_type": event_type,
            "actor": actor,
            "workspace_id": workspace_id,
            "project_id": project_id,
            "payload": payload or {},
        }
        with self._lock:
            entry = self._spine.append_entry(
                decision_id=workspace_id,
                entry_type="decision",
                content_hash=_content_hash(body),
                snapshot_id=snapshot_id,
                evidence_pack=body,
                metadata={
                    "surface": "workspace",
                    "event_type": event_type,
                    "project_id": project_id,
                },
            )
        return entry["entry_id"]

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def append_project_event(
        self,
        project_id: str,
        event_type: str,
        actor: str = "",
        payload: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
    ) -> str:
        """Append a project lifecycle event to the unified chain."""
        if event_type not in PROJECT_EVENT_TYPES:
            raise ValueError(
                f"invalid project event_type '{event_type}', "
                f"must be one of {sorted(PROJECT_EVENT_TYPES)}"
            )
        body = {
            "surface": "project",
            "event_type": event_type,
            "actor": actor,
            "project_id": project_id,
            "payload": payload or {},
        }
        with self._lock:
            entry = self._spine.append_entry(
                decision_id=project_id,
                entry_type="decision",
                content_hash=_content_hash(body),
                snapshot_id=snapshot_id,
                evidence_pack=body,
                metadata={"surface": "project", "event_type": event_type},
            )
        return entry["entry_id"]

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def verify(self) -> dict[str, Any]:
        """Verify the whole hash chain integrity."""
        return self._spine.verify_chain()

    def entries_for(self, decision_id: str) -> list[dict[str, Any]]:
        """All chain entries for a given decision_id (ticket/workspace/project id)."""
        return self._spine.get_entries_for_decision(decision_id)

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        return self._spine.get_entry(entry_id)

    def all_entries(self, from_seq: int | None = None,
                    to_seq: int | None = None) -> list[dict[str, Any]]:
        """Walk the entire chain (optionally bounded by sequence number)."""
        return self._spine.get_spine(from_seq=from_seq, to_seq=to_seq)

    def stats(self) -> dict[str, Any]:
        return self._spine.get_chain_stats()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: GovernanceAuditChain | None = None
_singleton_lock = threading.Lock()


def get_audit_chain(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GovernanceAuditChain:
    """Return process-wide singleton GovernanceAuditChain.

    First call decides db_path/event_bus; subsequent calls ignore args.
    Use reset_audit_chain() to swap the instance (tests, app startup).
    """
    global _instance
    with _singleton_lock:
        if _instance is None:
            _instance = GovernanceAuditChain(db_path=db_path, event_bus=event_bus)
        return _instance


def reset_audit_chain(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GovernanceAuditChain:
    """Replace singleton AND the underlying GovernanceSpine.

    Tests should call this in a fixture so each test starts with a
    fresh in-memory chain. App startup should call this with a real
    SQLite path BEFORE TicketStore is initialized.
    """
    global _instance
    with _singleton_lock:
        spine = reset_governance_spine(db_path=db_path, event_bus=event_bus)
        _instance = GovernanceAuditChain(spine=spine)
        return _instance
