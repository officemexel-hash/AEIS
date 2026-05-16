"""
SYLION AEIS -- Self-Evolution Engine

Tracks evolution proposals, mutations, and fitness outcomes.
Manages the self-improvement lifecycle: PROPOSE -> EVALUATE -> APPLY -> VERIFY.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.self_evolution")


# ---------------------------------------------------------------------------
# Lifecycle states
# ---------------------------------------------------------------------------

VALID_EVOLUTION_STATES = ("PROPOSED", "EVALUATING", "APPROVED", "APPLYING", "VERIFIED", "REJECTED", "ROLLED_BACK")

EVOLUTION_TRANSITIONS: dict[str, set[str]] = {
    "PROPOSED": {"EVALUATING", "REJECTED"},
    "EVALUATING": {"APPROVED", "REJECTED"},
    "APPROVED": {"APPLYING", "REJECTED"},
    "APPLYING": {"VERIFIED", "ROLLED_BACK"},
    "VERIFIED": set(),
    "REJECTED": set(),
    "ROLLED_BACK": {"PROPOSED"},
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EvolutionProposal:
    """A self-evolution proposal."""
    proposal_id: str = ""
    target_module: str = ""
    mutation_type: str = ""
    description: str = ""
    rationale: str = ""
    expected_fitness_delta: float = 0.0
    risk_level: str = "low"
    state: str = "PROPOSED"
    fitness_before: float = 0.0
    fitness_after: float = 0.0
    rollback_plan: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.proposal_id:
            self.proposal_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at


# ---------------------------------------------------------------------------
# Self-Evolution Engine
# ---------------------------------------------------------------------------

class SelfEvolution:
    """Self-evolution lifecycle management.

    Thread-safe. SQLite-backed. Emits events on state transitions.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_proposals (
                proposal_id          TEXT PRIMARY KEY,
                target_module        TEXT    NOT NULL,
                mutation_type        TEXT    NOT NULL,
                description          TEXT    NOT NULL DEFAULT '',
                rationale            TEXT    NOT NULL DEFAULT '',
                expected_fitness_delta REAL  NOT NULL DEFAULT 0,
                risk_level           TEXT    NOT NULL DEFAULT 'low',
                state                TEXT    NOT NULL DEFAULT 'PROPOSED',
                fitness_before       REAL    NOT NULL DEFAULT 0,
                fitness_after        REAL    NOT NULL DEFAULT 0,
                rollback_plan        TEXT    NOT NULL DEFAULT '',
                metadata             TEXT    NOT NULL DEFAULT '{}',
                created_at           REAL    NOT NULL,
                updated_at           REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_events (
                event_id     TEXT PRIMARY KEY,
                proposal_id  TEXT    NOT NULL,
                from_state   TEXT    NOT NULL,
                to_state     TEXT    NOT NULL,
                reason       TEXT    NOT NULL DEFAULT '',
                timestamp    REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evo_module ON evolution_proposals(target_module)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evo_state ON evolution_proposals(state)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evo_type ON evolution_proposals(mutation_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evoev_proposal ON evolution_events(proposal_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Propose
    # ------------------------------------------------------------------

    def propose(self, target_module: str, mutation_type: str,
                description: str = "", rationale: str = "",
                expected_fitness_delta: float = 0.0,
                risk_level: str = "low",
                rollback_plan: str = "",
                metadata: dict | None = None) -> dict:
        """Submit a new evolution proposal.

        Emits ``aeis.self_evolution.proposed``.
        """
        if metadata is None:
            metadata = {}

        proposal = EvolutionProposal(
            target_module=target_module,
            mutation_type=mutation_type,
            description=description,
            rationale=rationale,
            expected_fitness_delta=expected_fitness_delta,
            risk_level=risk_level,
            rollback_plan=rollback_plan,
            metadata=metadata,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO evolution_proposals
                    (proposal_id, target_module, mutation_type, description,
                     rationale, expected_fitness_delta, risk_level, state,
                     fitness_before, fitness_after, rollback_plan,
                     metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                proposal.proposal_id, proposal.target_module,
                proposal.mutation_type, proposal.description,
                proposal.rationale, proposal.expected_fitness_delta,
                proposal.risk_level, proposal.state,
                proposal.fitness_before, proposal.fitness_after,
                proposal.rollback_plan,
                json.dumps(metadata, default=str),
                proposal.created_at, proposal.updated_at,
            ))
            self._conn.commit()

        self._emit("aeis.self_evolution.proposed", {
            "proposal_id": proposal.proposal_id,
            "target_module": target_module,
            "mutation_type": mutation_type,
        })

        log.info("proposed evolution %s: %s on %s",
                 proposal.proposal_id[:12], mutation_type, target_module)
        return {
            "proposal_id": proposal.proposal_id,
            "target_module": target_module,
            "mutation_type": mutation_type,
            "state": "PROPOSED",
        }

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def transition(self, proposal_id: str, new_state: str,
                   reason: str = "") -> dict:
        """Transition proposal to a new state.

        Validates the transition is allowed. Records the event.
        Emits ``aeis.self_evolution.transitioned``.
        """
        row = self._conn.execute(
            "SELECT state FROM evolution_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Proposal {proposal_id} not found")

        current = row["state"]
        allowed = EVOLUTION_TRANSITIONS.get(current, set())
        if new_state not in allowed:
            raise ValueError(
                f"Cannot transition {proposal_id} from {current} to {new_state}. "
                f"Allowed: {allowed}"
            )

        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE evolution_proposals SET state = ?, updated_at = ? WHERE proposal_id = ?",
                (new_state, now, proposal_id),
            )
            self._conn.execute("""
                INSERT INTO evolution_events (event_id, proposal_id, from_state, to_state, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (uuid.uuid4().hex, proposal_id, current, new_state, reason, now))
            self._conn.commit()

        self._emit("aeis.self_evolution.transitioned", {
            "proposal_id": proposal_id,
            "from_state": current,
            "to_state": new_state,
        })

        log.info("evolution %s: %s -> %s", proposal_id[:12], current, new_state)
        return {
            "proposal_id": proposal_id,
            "from_state": current,
            "to_state": new_state,
        }

    def record_fitness(self, proposal_id: str, fitness_before: float,
                       fitness_after: float) -> dict:
        """Record fitness measurements for a proposal."""
        row = self._conn.execute(
            "SELECT proposal_id FROM evolution_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Proposal {proposal_id} not found")

        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE evolution_proposals SET fitness_before = ?, fitness_after = ?, updated_at = ? WHERE proposal_id = ?",
                (fitness_before, fitness_after, now, proposal_id),
            )
            self._conn.commit()

        delta = fitness_after - fitness_before
        return {
            "proposal_id": proposal_id,
            "fitness_before": fitness_before,
            "fitness_after": fitness_after,
            "delta": delta,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, proposal_id: str) -> dict | None:
        """Return a single proposal."""
        row = self._conn.execute(
            "SELECT * FROM evolution_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        return d

    def list_proposals(self, target_module: str | None = None,
                       state: str | None = None,
                       mutation_type: str | None = None,
                       limit: int = 100) -> list[dict]:
        """List proposals with optional filters."""
        q = "SELECT * FROM evolution_proposals WHERE 1=1"
        params: list[Any] = []
        if target_module:
            q += " AND target_module = ?"
            params.append(target_module)
        if state:
            q += " AND state = ?"
            params.append(state)
        if mutation_type:
            q += " AND mutation_type = ?"
            params.append(mutation_type)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            results.append(d)
        return results

    def get_events(self, proposal_id: str) -> list[dict]:
        """Return event history for a proposal."""
        rows = self._conn.execute(
            "SELECT * FROM evolution_events WHERE proposal_id = ? ORDER BY timestamp",
            (proposal_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Aggregate evolution statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM evolution_proposals"
        ).fetchone()["cnt"]

        by_state_rows = self._conn.execute(
            "SELECT state, COUNT(*) as cnt FROM evolution_proposals GROUP BY state"
        ).fetchall()
        by_state = {r["state"]: r["cnt"] for r in by_state_rows}

        by_type_rows = self._conn.execute(
            "SELECT mutation_type, COUNT(*) as cnt FROM evolution_proposals GROUP BY mutation_type"
        ).fetchall()
        by_type = {r["mutation_type"]: r["cnt"] for r in by_type_rows}

        by_module_rows = self._conn.execute(
            "SELECT target_module, COUNT(*) as cnt FROM evolution_proposals GROUP BY target_module"
        ).fetchall()
        by_module = {r["target_module"]: r["cnt"] for r in by_module_rows}

        return {
            "total_proposals": total,
            "by_state": by_state,
            "by_type": by_type,
            "by_module": by_module,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.self_evolution",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_evolution: SelfEvolution | None = None


def get_self_evolution(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> SelfEvolution:
    global _evolution
    if _evolution is None:
        _evolution = SelfEvolution(db_path, event_bus)
    return _evolution
