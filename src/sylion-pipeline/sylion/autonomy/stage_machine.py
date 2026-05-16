"""SYLION Autonomy -- per-project state machine attached to governance spine.

Wave A5 (RB-013).

State diagram (one cycle per `advance` call once event_threshold is met):

    observe -> propose -> simulate -> execute_low_risk -> escalate -> review -> observe

Behaviour:
  - `record_event(project_id)` accumulates events. When `event_count >=
    event_threshold` AND the current phase is `observe`, the next `advance`
    call moves to `propose`. Subsequent advances cycle through the loop.
  - `advance(project_id, decision_class="D0", reason="")` performs one
    transition. `decision_class > D0` -> a `GovernanceTicket` is submitted
    (origin='autonomy') and `to_phase` is forced to `escalate`.
  - `steer(project_id, target_phase, actor)` is the operator hint:
    bypasses the normal flow and jumps directly to a chosen phase. ALWAYS
    submits a ticket so the spine sees the manual override.

Storage: SQLite `autonomy_phase_state`.
Spine integration: `get_audit_chain().append_project_event(project_id,
"autonomy_update", actor, payload)` is invoked on every transition.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.autonomy.stage_machine")


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

class AutonomyPhase(str, Enum):
    OBSERVE = "observe"
    PROPOSE = "propose"
    SIMULATE = "simulate"
    EXECUTE_LOW_RISK = "execute_low_risk"
    ESCALATE = "escalate"
    REVIEW = "review"


# Canonical loop ordering. ESCALATE / REVIEW are reachable only via D2+
# decisions or explicit operator steer.
PHASE_ORDER: list[AutonomyPhase] = [
    AutonomyPhase.OBSERVE,
    AutonomyPhase.PROPOSE,
    AutonomyPhase.SIMULATE,
    AutonomyPhase.EXECUTE_LOW_RISK,
    AutonomyPhase.ESCALATE,
    AutonomyPhase.REVIEW,
]

# After REVIEW the project re-enters the observe loop.
_NEXT_PHASE: dict[AutonomyPhase, AutonomyPhase] = {
    AutonomyPhase.OBSERVE: AutonomyPhase.PROPOSE,
    AutonomyPhase.PROPOSE: AutonomyPhase.SIMULATE,
    AutonomyPhase.SIMULATE: AutonomyPhase.EXECUTE_LOW_RISK,
    AutonomyPhase.EXECUTE_LOW_RISK: AutonomyPhase.OBSERVE,  # low-risk loops
    AutonomyPhase.ESCALATE: AutonomyPhase.REVIEW,
    AutonomyPhase.REVIEW: AutonomyPhase.OBSERVE,
}

# Decision classes whose transitions ALWAYS submit a governance ticket.
_TICKET_TRIGGERING_CLASSES = frozenset({"D2", "D3", "D4", "D5"})


@dataclass
class AutonomyTransition:
    project_id: str
    from_phase: str
    to_phase: str
    decision_class: str
    reason: str
    actor: str
    ticket_id: str | None
    audit_entry_id: str | None
    transition_id: str = ""
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.transition_id:
            self.transition_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class AutonomyStageMachine:
    """Thread-safe per-project autonomy loop.

    Hook v1.0 (2026-04-25). Every transition with decision_class > D0
    submits a `GovernanceTicket` (origin='autonomy'). All transitions
    append a `project.autonomy_update` entry to the unified audit chain.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_threshold: int = 5,
    ) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_threshold = max(1, int(event_threshold))
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS autonomy_phase_state (
                project_id          TEXT PRIMARY KEY,
                phase               TEXT NOT NULL DEFAULT 'observe',
                event_count         INTEGER NOT NULL DEFAULT 0,
                cycle_count         INTEGER NOT NULL DEFAULT 0,
                last_transition_at  REAL NOT NULL DEFAULT 0,
                created_at          REAL NOT NULL,
                updated_at          REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS autonomy_transitions (
                transition_id    TEXT PRIMARY KEY,
                project_id       TEXT NOT NULL,
                from_phase       TEXT NOT NULL,
                to_phase         TEXT NOT NULL,
                decision_class   TEXT NOT NULL,
                reason           TEXT NOT NULL DEFAULT '',
                actor            TEXT NOT NULL DEFAULT '',
                ticket_id        TEXT,
                audit_entry_id   TEXT,
                timestamp        REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_aut_trans_project
                ON autonomy_transitions(project_id);
            CREATE INDEX IF NOT EXISTS idx_aut_trans_ts
                ON autonomy_transitions(timestamp);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_state(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM autonomy_phase_state WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return {
                "project_id": project_id,
                "phase": AutonomyPhase.OBSERVE.value,
                "event_count": 0,
                "cycle_count": 0,
                "last_transition_at": 0.0,
                "ready_to_advance": False,
            }
        ready = (
            row["phase"] != AutonomyPhase.OBSERVE.value
            or int(row["event_count"]) >= self._event_threshold
        )
        return {
            "project_id": row["project_id"],
            "phase": row["phase"],
            "event_count": int(row["event_count"]),
            "cycle_count": int(row["cycle_count"]),
            "last_transition_at": float(row["last_transition_at"]),
            "ready_to_advance": ready,
        }

    def list_transitions(
        self, project_id: str, limit: int = 50,
    ) -> list[AutonomyTransition]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM autonomy_transitions
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (project_id, int(limit)),
            ).fetchall()
        return [self._row_to_transition(r) for r in rows]

    # ------------------------------------------------------------------
    # Mutation API
    # ------------------------------------------------------------------

    def record_event(self, project_id: str) -> int:
        """Increment the event counter for a project. Returns new count."""
        now = time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO autonomy_phase_state
                    (project_id, phase, event_count, cycle_count,
                     last_transition_at, created_at, updated_at)
                VALUES (?, ?, 1, 0, 0, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    event_count = event_count + 1,
                    updated_at = excluded.updated_at
                """,
                (project_id, AutonomyPhase.OBSERVE.value, now, now),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT event_count FROM autonomy_phase_state WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return int(row["event_count"]) if row else 0

    def advance(
        self,
        project_id: str,
        decision_class: str = "D0",
        reason: str = "",
        actor: str = "autonomy",
    ) -> AutonomyTransition:
        """Advance the project by one phase.

        - From `observe`, requires `event_count >= event_threshold`.
        - decision_class > D0 forces transition to `escalate` and submits a
          governance ticket.
        - All transitions append a project.autonomy_update entry to the
          unified audit chain.
        """
        decision_class = decision_class.upper()
        with self._lock:
            current = self.get_state(project_id)
            from_phase = AutonomyPhase(current["phase"])

            if from_phase == AutonomyPhase.OBSERVE and current["event_count"] < self._event_threshold:
                raise RuntimeError(
                    f"project '{project_id}' has {current['event_count']} events; "
                    f"need >= {self._event_threshold} to leave observe"
                )

            if decision_class in _TICKET_TRIGGERING_CLASSES:
                to_phase = AutonomyPhase.ESCALATE
            else:
                to_phase = _NEXT_PHASE[from_phase]

            ticket_id = self._maybe_submit_ticket(
                project_id, from_phase, to_phase, decision_class,
                reason, actor,
            )
            audit_entry_id = self._append_audit_entry(
                project_id, from_phase, to_phase, decision_class,
                reason, actor, ticket_id,
            )

            transition = AutonomyTransition(
                project_id=project_id,
                from_phase=from_phase.value,
                to_phase=to_phase.value,
                decision_class=decision_class,
                reason=reason,
                actor=actor,
                ticket_id=ticket_id,
                audit_entry_id=audit_entry_id,
            )
            self._persist_transition(transition)
            self._update_phase_state(
                project_id, to_phase, reset_events=(to_phase != from_phase),
            )
        return transition

    def steer(
        self,
        project_id: str,
        target_phase: AutonomyPhase | str,
        actor: str,
        reason: str = "operator_steer",
    ) -> AutonomyTransition:
        """Operator hint: jump directly to a target phase. Always tickets."""
        if isinstance(target_phase, str):
            target_phase = AutonomyPhase(target_phase)
        with self._lock:
            current = self.get_state(project_id)
            from_phase = AutonomyPhase(current["phase"])
            ticket_id = self._maybe_submit_ticket(
                project_id, from_phase, target_phase, "D2",
                reason, actor, force_ticket=True,
            )
            audit_entry_id = self._append_audit_entry(
                project_id, from_phase, target_phase, "D2",
                reason, actor, ticket_id,
            )
            transition = AutonomyTransition(
                project_id=project_id,
                from_phase=from_phase.value,
                to_phase=target_phase.value,
                decision_class="D2",
                reason=reason,
                actor=actor,
                ticket_id=ticket_id,
                audit_entry_id=audit_entry_id,
            )
            self._persist_transition(transition)
            self._update_phase_state(
                project_id, target_phase, reset_events=True,
            )
        return transition

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _maybe_submit_ticket(
        self,
        project_id: str,
        from_phase: AutonomyPhase,
        to_phase: AutonomyPhase,
        decision_class: str,
        reason: str,
        actor: str,
        force_ticket: bool = False,
    ) -> str | None:
        if not force_ticket and decision_class not in _TICKET_TRIGGERING_CLASSES:
            return None
        # Lazy import to avoid import-time circular dependency.
        from sylion.governance import GovernanceTicket, get_ticket_store

        priority = "P2" if decision_class == "D2" else "P1"
        ticket = GovernanceTicket(
            origin="autonomy",
            project_id=project_id,
            decision_class=decision_class,
            gate_type="blocking",
            priority=priority,
            title=f"autonomy: {from_phase.value} -> {to_phase.value}",
            summary=reason or f"autonomy transition {from_phase.value}->{to_phase.value}",
            payload={
                "from_phase": from_phase.value,
                "to_phase": to_phase.value,
                "decision_class": decision_class,
                "actor": actor,
            },
            requested_by=actor or "autonomy",
        )
        try:
            return get_ticket_store().submit(ticket)
        except Exception as exc:
            log.warning("autonomy ticket submission failed: %s", exc)
            return None

    def _append_audit_entry(
        self,
        project_id: str,
        from_phase: AutonomyPhase,
        to_phase: AutonomyPhase,
        decision_class: str,
        reason: str,
        actor: str,
        ticket_id: str | None,
    ) -> str | None:
        from sylion.governance import get_audit_chain

        try:
            return get_audit_chain().append_project_event(
                project_id=project_id,
                event_type="autonomy_update",
                actor=actor or "autonomy",
                payload={
                    "from_phase": from_phase.value,
                    "to_phase": to_phase.value,
                    "decision_class": decision_class,
                    "reason": reason,
                    "ticket_id": ticket_id,
                },
            )
        except Exception as exc:
            log.warning("autonomy audit append failed: %s", exc)
            return None

    def _persist_transition(self, t: AutonomyTransition) -> None:
        self._conn.execute(
            """
            INSERT INTO autonomy_transitions
                (transition_id, project_id, from_phase, to_phase,
                 decision_class, reason, actor, ticket_id, audit_entry_id,
                 timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                t.transition_id, t.project_id, t.from_phase, t.to_phase,
                t.decision_class, t.reason, t.actor, t.ticket_id,
                t.audit_entry_id, t.timestamp,
            ),
        )
        self._conn.commit()

    def _update_phase_state(
        self,
        project_id: str,
        new_phase: AutonomyPhase,
        reset_events: bool,
    ) -> None:
        now = time.time()
        if reset_events:
            self._conn.execute(
                """
                INSERT INTO autonomy_phase_state
                    (project_id, phase, event_count, cycle_count,
                     last_transition_at, created_at, updated_at)
                VALUES (?, ?, 0, 0, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    phase = excluded.phase,
                    event_count = 0,
                    cycle_count = cycle_count + CASE
                        WHEN excluded.phase = 'observe' THEN 1 ELSE 0 END,
                    last_transition_at = excluded.last_transition_at,
                    updated_at = excluded.updated_at
                """,
                (project_id, new_phase.value, now, now, now),
            )
        else:
            self._conn.execute(
                """
                UPDATE autonomy_phase_state
                SET phase = ?, last_transition_at = ?, updated_at = ?
                WHERE project_id = ?
                """,
                (new_phase.value, now, now, project_id),
            )
        self._conn.commit()

    def _row_to_transition(self, row: sqlite3.Row) -> AutonomyTransition:
        return AutonomyTransition(
            transition_id=row["transition_id"],
            project_id=row["project_id"],
            from_phase=row["from_phase"],
            to_phase=row["to_phase"],
            decision_class=row["decision_class"],
            reason=row["reason"] or "",
            actor=row["actor"] or "",
            ticket_id=row["ticket_id"],
            audit_entry_id=row["audit_entry_id"],
            timestamp=float(row["timestamp"]),
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_machine: AutonomyStageMachine | None = None


def get_autonomy_machine(
    db_path: str | Path | None = None,
    event_threshold: int = 5,
) -> AutonomyStageMachine:
    global _machine
    if _machine is None:
        _machine = AutonomyStageMachine(db_path, event_threshold)
    return _machine


def reset_autonomy_machine(
    db_path: str | Path | None = None,
    event_threshold: int = 5,
) -> AutonomyStageMachine:
    global _machine
    if _machine is not None:
        try:
            _machine.close()
        except Exception:
            pass
    _machine = AutonomyStageMachine(db_path, event_threshold)
    return _machine
