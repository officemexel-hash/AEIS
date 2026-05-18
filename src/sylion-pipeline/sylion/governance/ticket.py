"""
SYLION Governance -- Unified Governance Ticket plane.

One canonical decision/HG ticket shape for ALL origins:
- workspace (project-scoped HG sessions)
- global (legacy /api/v1/gates/human/*)
- funding (funding_autopilot submission gates)
- mobile (operator-mobile push approvals)
- skill (skills.runtime gated invocations)
- council (multi-model voting gate)
- execution_guard (policy-based execution approvals)

SQLite tables:
  governance_tickets       -- unified ticket store (1 row per decision request)
  governance_ticket_events -- append-only state transitions (created/resolved/withdrawn/escalated)

Thread-safe via RLock. Emits events via EventBus.

Singleton: get_ticket_store() / reset_ticket_store()

Wave A1 (2026-04-24).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.governance.ticket")


# ---------------------------------------------------------------------------
# Type literals
# ---------------------------------------------------------------------------

TicketOrigin = Literal[
    "workspace", "global", "funding", "mobile", "skill", "council",
    "autonomy", "round_meta", "execution_guard",
]
DecisionClass = Literal["D0", "D1", "D2", "D3", "D4", "D5"]
GateType = Literal[
    "blocking", "non_blocking", "batch", "emergency",
    "financial", "legal", "production", "security",
    "external_action", "final", "direction_gate",
    "source_of_truth_gate", "masterplan_gate",
]
Priority = Literal["P0", "P1", "P2", "P3", "P4"]
TicketState = Literal[
    "pending", "approved", "rejected", "expired", "withdrawn", "escalated"
]

VALID_ORIGINS: frozenset[str] = frozenset({
    "workspace", "global", "funding", "mobile", "skill", "council",
    "autonomy", "round_meta", "execution_guard",
})
VALID_DECISION_CLASSES: frozenset[str] = frozenset({
    "D0", "D1", "D2", "D3", "D4", "D5",
})
VALID_GATE_TYPES: frozenset[str] = frozenset({
    "blocking", "non_blocking", "batch", "emergency",
    "financial", "legal", "production", "security",
    "external_action", "final", "direction_gate",
    "source_of_truth_gate", "masterplan_gate",
})
VALID_PRIORITIES: frozenset[str] = frozenset({"P0", "P1", "P2", "P3", "P4"})
VALID_STATES: frozenset[str] = frozenset({
    "pending", "approved", "rejected", "expired", "withdrawn", "escalated",
})
REASON_REQUIRED_DECISION_CLASSES: frozenset[str] = frozenset({"D3", "D4", "D5"})
REASON_REQUIRED_DECISIONS: frozenset[str] = frozenset({"approved", "rejected"})

# Default SLA per priority (seconds).
_DEFAULT_SLA_SECONDS: dict[str, float] = {
    "P0": 15 * 60,         # 15 min
    "P1": 60 * 60,         # 1 h
    "P2": 4 * 60 * 60,     # 4 h
    "P3": 24 * 60 * 60,    # 1 d
    "P4": 7 * 24 * 60 * 60,  # 1 w
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class GovernanceTicket:
    """Canonical governance/HG ticket shape.

    Hook v1.0 (2026-04-24).
    Changes: initial — unifies workspace/global/funding/mobile/skill/council.
    """
    ticket_id: str = ""
    origin: str = "global"
    project_id: str | None = None
    decision_class: str = "D2"
    gate_type: str = "blocking"
    priority: str = "P2"
    title: str = ""
    summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    requested_by: str = ""
    audit_chain_ref: str | None = None
    created_at: float = 0.0
    sla_deadline: float = 0.0
    state: str = "pending"
    resolved_by: str | None = None
    resolved_at: float | None = None
    resolution_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.ticket_id:
            self.ticket_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.sla_deadline:
            self.sla_deadline = self.created_at + _DEFAULT_SLA_SECONDS.get(
                self.priority, _DEFAULT_SLA_SECONDS["P2"],
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row | dict[str, Any]) -> "GovernanceTicket":
        d = dict(row)
        payload_raw = d.get("payload_json") or "{}"
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
        except (json.JSONDecodeError, TypeError):
            payload = {}
        return cls(
            ticket_id=d.get("ticket_id", ""),
            origin=d.get("origin", "global"),
            project_id=d.get("project_id"),
            decision_class=d.get("decision_class", "D2"),
            gate_type=d.get("gate_type", "blocking"),
            priority=d.get("priority", "P2"),
            title=d.get("title", ""),
            summary=d.get("summary", ""),
            payload=payload if isinstance(payload, dict) else {},
            requested_by=d.get("requested_by", ""),
            audit_chain_ref=d.get("audit_chain_ref"),
            created_at=float(d.get("created_at") or 0.0),
            sla_deadline=float(d.get("sla_deadline") or 0.0),
            state=d.get("state", "pending"),
            resolved_by=d.get("resolved_by"),
            resolved_at=float(d["resolved_at"]) if d.get("resolved_at") else None,
            resolution_reason=d.get("resolution_reason"),
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_ticket(ticket: GovernanceTicket) -> None:
    if ticket.origin not in VALID_ORIGINS:
        raise ValueError(
            f"invalid origin '{ticket.origin}', must be one of {sorted(VALID_ORIGINS)}"
        )
    if ticket.decision_class not in VALID_DECISION_CLASSES:
        raise ValueError(
            f"invalid decision_class '{ticket.decision_class}'"
        )
    if ticket.gate_type not in VALID_GATE_TYPES:
        raise ValueError(f"invalid gate_type '{ticket.gate_type}'")
    if ticket.priority not in VALID_PRIORITIES:
        raise ValueError(f"invalid priority '{ticket.priority}'")
    if ticket.state not in VALID_STATES:
        raise ValueError(f"invalid state '{ticket.state}'")


def validate_resolution_policy(
    *,
    decision_class: str,
    decision: str,
    reason: str | None,
) -> None:
    """Enforce the global D0-D5 Human Gate resolution matrix."""
    if (
        decision_class in REASON_REQUIRED_DECISION_CLASSES
        and decision in REASON_REQUIRED_DECISIONS
        and not str(reason or "").strip()
    ):
        raise ValueError("reason is required for D3+ governance ticket resolution")


def _record_ticket_audit(
    ticket: GovernanceTicket,
    event_type: str,
    *,
    actor: str = "",
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Mirror governance tickets into the operator-facing unified audit trail."""
    try:
        from sylion.security.audit_trail_aggregator import get_audit_trail_aggregator

        get_audit_trail_aggregator().record(
            source="governance",
            action=f"governance.ticket.{event_type}",
            actor=actor or ticket.requested_by or "",
            resource=f"ticket:{ticket.ticket_id}",
            outcome=outcome,
            metadata={
                "ticket_id": ticket.ticket_id,
                "origin": ticket.origin,
                "project_id": ticket.project_id,
                "decision_class": ticket.decision_class,
                "gate_type": ticket.gate_type,
                "priority": ticket.priority,
                "state": ticket.state,
                "title": ticket.title,
                "audit_chain_ref": ticket.audit_chain_ref,
                **(metadata or {}),
            },
            entry_id=f"governance.ticket.{ticket.ticket_id}.{event_type}",
        )
    except Exception:                              # noqa: BLE001
        log.warning("ticket audit trail mirror failed", exc_info=True)


# ---------------------------------------------------------------------------
# TicketStore
# ---------------------------------------------------------------------------

class TicketStore:
    """SQLite-backed unified governance ticket store.

    Single source of truth for all decision tickets across the system.
    Replaces the previous split between workspace humangate sessions,
    global gates/human/requests, and funding-local approvals.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA busy_timeout = 30000")
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS governance_tickets (
                ticket_id          TEXT PRIMARY KEY,
                origin             TEXT NOT NULL DEFAULT 'global',
                project_id         TEXT,
                decision_class     TEXT NOT NULL DEFAULT 'D2',
                gate_type          TEXT NOT NULL DEFAULT 'blocking',
                priority           TEXT NOT NULL DEFAULT 'P2',
                title              TEXT NOT NULL DEFAULT '',
                summary            TEXT NOT NULL DEFAULT '',
                payload_json       TEXT NOT NULL DEFAULT '{}',
                requested_by       TEXT NOT NULL DEFAULT '',
                audit_chain_ref    TEXT,
                created_at         REAL NOT NULL,
                sla_deadline       REAL NOT NULL DEFAULT 0,
                state              TEXT NOT NULL DEFAULT 'pending',
                resolved_by        TEXT,
                resolved_at        REAL,
                resolution_reason  TEXT
            );
            CREATE TABLE IF NOT EXISTS governance_ticket_events (
                event_id     TEXT PRIMARY KEY,
                ticket_id    TEXT NOT NULL,
                event_type   TEXT NOT NULL,
                actor        TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL,
                FOREIGN KEY (ticket_id) REFERENCES governance_tickets(ticket_id)
            );
            CREATE INDEX IF NOT EXISTS idx_gt_state    ON governance_tickets(state);
            CREATE INDEX IF NOT EXISTS idx_gt_origin   ON governance_tickets(origin);
            CREATE INDEX IF NOT EXISTS idx_gt_project  ON governance_tickets(project_id);
            CREATE INDEX IF NOT EXISTS idx_gt_priority ON governance_tickets(priority);
            CREATE INDEX IF NOT EXISTS idx_gt_created  ON governance_tickets(created_at);
            CREATE INDEX IF NOT EXISTS idx_gte_ticket  ON governance_ticket_events(ticket_id);
            CREATE INDEX IF NOT EXISTS idx_gte_type    ON governance_ticket_events(event_type);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(SylionEvent(
            event_id="",
            topic=topic,
            payload=payload,
            source_module="governance.ticket",
        ))

    def _record_event(self, ticket_id: str, event_type: str,
                      actor: str = "", payload: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            """INSERT INTO governance_ticket_events
                (event_id, ticket_id, event_type, actor, payload_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (self._uid(), ticket_id, event_type, actor,
             json.dumps(payload or {}, default=str), time.time()),
        )

    # ------------------------------------------------------------------
    # Public API — write
    # ------------------------------------------------------------------

    def submit(self, ticket: GovernanceTicket) -> str:
        """Submit a new ticket. Returns ticket_id.

        Idempotent on ticket_id: re-submit with same id is a no-op (returns id).
        Also appends a "submitted" entry to the unified governance audit chain
        and stores the chain entry_id in `ticket.audit_chain_ref` (Wave A2).
        """
        _validate_ticket(ticket)
        with self._lock:
            existing = self._conn.execute(
                "SELECT ticket_id FROM governance_tickets WHERE ticket_id = ?",
                (ticket.ticket_id,),
            ).fetchone()
            if existing:
                return ticket.ticket_id

            # Append to unified audit chain BEFORE INSERT so the chain ref is
            # written atomically with the row. Lazy import keeps governance/__init__
            # bootstrap order flexible.
            if ticket.audit_chain_ref is None:
                from sylion.governance.audit_chain import get_audit_chain
                chain = get_audit_chain()
                ticket.audit_chain_ref = chain.append_ticket_event(
                    ticket.ticket_id,
                    event_type="submitted",
                    actor=ticket.requested_by,
                    payload={
                        "origin": ticket.origin,
                        "decision_class": ticket.decision_class,
                        "gate_type": ticket.gate_type,
                        "priority": ticket.priority,
                        "title": ticket.title,
                        "project_id": ticket.project_id,
                    },
                )

            self._conn.execute(
                """INSERT INTO governance_tickets
                    (ticket_id, origin, project_id, decision_class, gate_type,
                     priority, title, summary, payload_json, requested_by,
                     audit_chain_ref, created_at, sla_deadline, state,
                     resolved_by, resolved_at, resolution_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ticket.ticket_id, ticket.origin, ticket.project_id,
                    ticket.decision_class, ticket.gate_type, ticket.priority,
                    ticket.title, ticket.summary,
                    json.dumps(ticket.payload, default=str),
                    ticket.requested_by, ticket.audit_chain_ref,
                    ticket.created_at, ticket.sla_deadline, ticket.state,
                    ticket.resolved_by, ticket.resolved_at,
                    ticket.resolution_reason,
                ),
            )
            self._record_event(
                ticket.ticket_id, "created", ticket.requested_by,
                {"origin": ticket.origin, "decision_class": ticket.decision_class,
                 "priority": ticket.priority,
                 "audit_chain_ref": ticket.audit_chain_ref},
            )
            self._conn.commit()

        self._emit("governance.ticket.submitted", {
            "ticket_id": ticket.ticket_id,
            "origin": ticket.origin,
            "project_id": ticket.project_id,
            "decision_class": ticket.decision_class,
            "priority": ticket.priority,
            "audit_chain_ref": ticket.audit_chain_ref,
        })
        _record_ticket_audit(ticket, "submitted")
        log.info(
            "ticket %s submitted (origin=%s class=%s pri=%s chain=%s)",
            ticket.ticket_id, ticket.origin, ticket.decision_class, ticket.priority,
            ticket.audit_chain_ref,
        )
        return ticket.ticket_id

    def resolve(self, ticket_id: str, decision: str,
                reason: str | None = None, reviewer: str = "") -> bool:
        """Resolve a ticket. decision must be 'approved' | 'rejected' | 'expired'.

        Returns True if state changed, False if ticket missing or already final.
        """
        if decision not in {"approved", "rejected", "expired"}:
            raise ValueError(f"invalid decision '{decision}'")
        with self._lock:
            row = self._conn.execute(
                "SELECT state, decision_class FROM governance_tickets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()
            if not row:
                return False
            if row["state"] not in {"pending", "escalated"}:
                return False
            validate_resolution_policy(
                decision_class=str(row["decision_class"] or "D2"),
                decision=decision,
                reason=reason,
            )
            previous_state = str(row["state"])

            from sylion.governance.audit_chain import get_audit_chain
            chain_entry = get_audit_chain().append_ticket_event(
                ticket_id,
                event_type="resolved",
                actor=reviewer or "",
                payload={"decision": decision, "reason": reason},
            )

            now = time.time()
            self._conn.execute(
                """UPDATE governance_tickets
                   SET state = ?, resolved_by = ?, resolved_at = ?,
                       resolution_reason = ?
                   WHERE ticket_id = ?""",
                (decision, reviewer or "", now, reason, ticket_id),
            )
            self._record_event(
                ticket_id, "resolved", reviewer or "",
                {"decision": decision, "reason": reason,
                 "previous_state": previous_state,
                 "audit_chain_entry": chain_entry},
            )
            self._conn.commit()

        self._emit("governance.ticket.resolved", {
            "ticket_id": ticket_id, "decision": decision,
            "reviewer": reviewer, "reason": reason,
            "audit_chain_entry": chain_entry,
        })
        ticket = self.get(ticket_id)
        if ticket is not None:
            _record_ticket_audit(
                ticket,
                "resolved",
                actor=reviewer or "",
                outcome="success" if decision == "approved" else "denied",
                metadata={
                    "decision": decision,
                    "reason": reason,
                    "audit_chain_entry": chain_entry,
                },
            )
        log.info("ticket %s resolved=%s by=%s chain=%s",
                 ticket_id, decision, reviewer, chain_entry)
        return True

    def withdraw(self, ticket_id: str, reason: str = "",
                 actor: str = "") -> bool:
        """Withdraw a pending ticket. Returns True if state changed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT state FROM governance_tickets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()
            if not row or row["state"] != "pending":
                return False

            from sylion.governance.audit_chain import get_audit_chain
            chain_entry = get_audit_chain().append_ticket_event(
                ticket_id,
                event_type="withdrawn",
                actor=actor,
                payload={"reason": reason},
            )

            now = time.time()
            self._conn.execute(
                """UPDATE governance_tickets
                   SET state = 'withdrawn', resolved_by = ?, resolved_at = ?,
                       resolution_reason = ?
                   WHERE ticket_id = ?""",
                (actor, now, reason, ticket_id),
            )
            self._record_event(
                ticket_id, "withdrawn", actor,
                {"reason": reason, "audit_chain_entry": chain_entry},
            )
            self._conn.commit()

        self._emit("governance.ticket.withdrawn", {
            "ticket_id": ticket_id, "reason": reason, "actor": actor,
            "audit_chain_entry": chain_entry,
        })
        ticket = self.get(ticket_id)
        if ticket is not None:
            _record_ticket_audit(
                ticket,
                "withdrawn",
                actor=actor,
                metadata={"reason": reason, "audit_chain_entry": chain_entry},
            )
        return True

    def escalate(self, ticket_id: str, reason: str = "",
                 actor: str = "") -> bool:
        """Mark a ticket as escalated (still pending review at higher tier)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT state FROM governance_tickets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()
            if not row or row["state"] not in {"pending", "escalated"}:
                return False

            from sylion.governance.audit_chain import get_audit_chain
            chain_entry = get_audit_chain().append_ticket_event(
                ticket_id,
                event_type="escalated",
                actor=actor,
                payload={"reason": reason},
            )

            self._conn.execute(
                "UPDATE governance_tickets SET state = 'escalated' WHERE ticket_id = ?",
                (ticket_id,),
            )
            self._record_event(
                ticket_id, "escalated", actor,
                {"reason": reason, "audit_chain_entry": chain_entry},
            )
            self._conn.commit()
        self._emit("governance.ticket.escalated", {
            "ticket_id": ticket_id, "reason": reason, "actor": actor,
            "audit_chain_entry": chain_entry,
        })
        ticket = self.get(ticket_id)
        if ticket is not None:
            _record_ticket_audit(
                ticket,
                "escalated",
                actor=actor,
                metadata={"reason": reason, "audit_chain_entry": chain_entry},
            )
        return True

    def attach_audit_chain(self, ticket_id: str, audit_chain_ref: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE governance_tickets SET audit_chain_ref = ? WHERE ticket_id = ?",
                (audit_chain_ref, ticket_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Public API — read
    # ------------------------------------------------------------------

    def get(self, ticket_id: str) -> GovernanceTicket | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM governance_tickets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()
        return GovernanceTicket.from_row(row) if row else None

    def fetch_pending(
        self,
        operator_id: str | None = None,
        origin: str | None = None,
        project_id: str | None = None,
        priority: str | None = None,
    ) -> list[GovernanceTicket]:
        """List pending tickets with optional filters.

        operator_id is reserved for routing logic (currently no per-operator
        assignment column -- returns all pending/escalated reviewable tickets).
        Filter by origin/project/priority for dashboards.
        """
        with self._lock:
            q = "SELECT * FROM governance_tickets WHERE state IN ('pending', 'escalated')"
            params: list[Any] = []
            if origin:
                if origin not in VALID_ORIGINS:
                    return []
                q += " AND origin = ?"
                params.append(origin)
            if project_id:
                q += " AND project_id = ?"
                params.append(project_id)
            if priority:
                if priority not in VALID_PRIORITIES:
                    return []
                q += " AND priority = ?"
                params.append(priority)
            q += " ORDER BY priority ASC, created_at ASC"
            rows = self._conn.execute(q, params).fetchall()
        return [GovernanceTicket.from_row(r) for r in rows]

    def list(
        self,
        states: Iterable[str] | None = None,
        origin: str | None = None,
        project_id: str | None = None,
        limit: int = 200,
    ) -> list[GovernanceTicket]:
        with self._lock:
            q = "SELECT * FROM governance_tickets WHERE 1=1"
            params: list[Any] = []
            if states:
                state_list = [s for s in states if s in VALID_STATES]
                if not state_list:
                    return []
                q += " AND state IN ({})".format(
                    ",".join("?" * len(state_list))
                )
                params.extend(state_list)
            if origin:
                q += " AND origin = ?"
                params.append(origin)
            if project_id:
                q += " AND project_id = ?"
                params.append(project_id)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(int(limit))
            rows = self._conn.execute(q, params).fetchall()
        return [GovernanceTicket.from_row(r) for r in rows]

    def events(self, ticket_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT event_id, ticket_id, event_type, actor,
                          payload_json, created_at
                     FROM governance_ticket_events
                    WHERE ticket_id = ?
                 ORDER BY created_at ASC""",
                (ticket_id,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.pop("payload_json", "{}") or "{}")
            except (json.JSONDecodeError, TypeError):
                d["payload"] = {}
            out.append(d)
        return out

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) AS c FROM governance_tickets"
            ).fetchone()["c"]
            by_state_rows = self._conn.execute(
                "SELECT state, COUNT(*) AS c FROM governance_tickets GROUP BY state"
            ).fetchall()
            by_origin_rows = self._conn.execute(
                "SELECT origin, COUNT(*) AS c FROM governance_tickets GROUP BY origin"
            ).fetchall()
            by_priority_rows = self._conn.execute(
                "SELECT priority, COUNT(*) AS c FROM governance_tickets GROUP BY priority"
            ).fetchall()
        return {
            "total": total,
            "by_state": {r["state"]: r["c"] for r in by_state_rows},
            "by_origin": {r["origin"]: r["c"] for r in by_origin_rows},
            "by_priority": {r["priority"]: r["c"] for r in by_priority_rows},
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: TicketStore | None = None
_singleton_lock = threading.Lock()


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    """W14 BE-7: redirect onto audit-isolated DB when SYLION_AUDIT_PROFILE_ID set.

    No-op when env unset or when caller passed ``:memory:``/None.
    """
    if db_path is None or str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path))


def get_ticket_store(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> TicketStore:
    """Return process-wide singleton TicketStore.

    First call decides db_path/event_bus; subsequent calls ignore args.
    Use reset_ticket_store() to swap the instance (tests, app startup).
    """
    global _instance
    with _singleton_lock:
        if _instance is None:
            _instance = TicketStore(_audit_redirect(db_path), event_bus)
        return _instance


def reset_ticket_store(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> TicketStore:
    """Replace singleton — used by tests and by app.py at startup."""
    global _instance
    with _singleton_lock:
        _instance = TicketStore(_audit_redirect(db_path), event_bus)
        return _instance
