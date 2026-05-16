"""
SYLION AEIS -- Evolution Tracker

Manages module evolution proposals and execution. Tracks proposals through
a lifecycle: proposed -> approved -> in_progress -> completed/failed.
Supports multi-step execution with per-step tracking.

Schema:
  evolution_proposals - proposal metadata, change type, status
  evolution_steps    - ordered steps within a proposal
  evolution_results  - execution results for completed proposals

Thread-safe. SQLite-backed. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.evolution_tracker")

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_CHANGE_TYPES = (
    "schema_migration", "behavior_change", "performance_tuning",
    "feature_addition", "deprecation", "security_patch",
)

VALID_PROPOSAL_STATUSES = (
    "proposed", "approved", "rejected", "in_progress",
    "completed", "failed", "rolled_back",
)

VALID_STEP_STATUSES = ("pending", "running", "completed", "failed", "skipped")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EvolutionProposal:
    """A proposal for evolving a module."""
    proposal_id: str = ""
    module_id: str = ""
    change_type: str = ""
    description: str = ""
    rationale: str = ""
    status: str = "proposed"
    approver: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.proposal_id:
            self.proposal_id = uuid.uuid4().hex
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class EvolutionStep:
    """A step within an evolution proposal."""
    step_id: str = ""
    proposal_id: str = ""
    step_name: str = ""
    step_order: int = 0
    config_json: str = "{}"
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.step_id:
            self.step_id = uuid.uuid4().hex


@dataclass
class EvolutionResult:
    """The result of executing an evolution proposal."""
    result_id: str = ""
    proposal_id: str = ""
    outcome: str = "pending"
    summary_json: str = "{}"
    metrics_json: str = "{}"
    completed_at: float = 0.0

    def __post_init__(self):
        if not self.result_id:
            self.result_id = uuid.uuid4().hex
        if not self.completed_at:
            self.completed_at = time.time()


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class EvolutionTracker:
    """Manages module evolution proposals and execution.

    SQLite-backed, thread-safe. Integrates with EventBus for evolution
    lifecycle events.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS evolution_proposals (
                proposal_id  TEXT PRIMARY KEY,
                module_id    TEXT NOT NULL,
                change_type  TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                rationale    TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'proposed',
                approver     TEXT NOT NULL DEFAULT '',
                created_at   REAL NOT NULL,
                updated_at   REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS evolution_steps (
                step_id      TEXT PRIMARY KEY,
                proposal_id  TEXT NOT NULL,
                step_name    TEXT NOT NULL,
                step_order   INTEGER NOT NULL DEFAULT 0,
                config_json  TEXT NOT NULL DEFAULT '{}',
                status       TEXT NOT NULL DEFAULT 'pending',
                started_at   REAL NOT NULL DEFAULT 0,
                completed_at REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (proposal_id) REFERENCES evolution_proposals(proposal_id)
            );
            CREATE TABLE IF NOT EXISTS evolution_results (
                result_id    TEXT PRIMARY KEY,
                proposal_id  TEXT NOT NULL,
                outcome      TEXT NOT NULL DEFAULT 'pending',
                summary_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                completed_at REAL NOT NULL,
                FOREIGN KEY (proposal_id) REFERENCES evolution_proposals(proposal_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ep_status   ON evolution_proposals(status);
            CREATE INDEX IF NOT EXISTS idx_ep_module   ON evolution_proposals(module_id);
            CREATE INDEX IF NOT EXISTS idx_ep_type     ON evolution_proposals(change_type);
            CREATE INDEX IF NOT EXISTS idx_es_proposal ON evolution_steps(proposal_id);
            CREATE INDEX IF NOT EXISTS idx_es_order    ON evolution_steps(proposal_id, step_order);
            CREATE INDEX IF NOT EXISTS idx_er_proposal ON evolution_results(proposal_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Proposals
    # ------------------------------------------------------------------

    def propose_evolution(self, module_id: str, change_type: str,
                          description: str = "",
                          rationale: str = "") -> dict:
        """Create a new evolution proposal."""
        if change_type not in VALID_CHANGE_TYPES:
            raise ValueError(
                f"Invalid change_type: {change_type!r}. "
                f"Must be one of {VALID_CHANGE_TYPES}"
            )
        proposal = EvolutionProposal(
            module_id=module_id, change_type=change_type,
            description=description, rationale=rationale,
        )
        with self._lock:
            self._conn.execute("""
                INSERT INTO evolution_proposals
                    (proposal_id, module_id, change_type, description,
                     rationale, status, approver, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                proposal.proposal_id, proposal.module_id,
                proposal.change_type, proposal.description,
                proposal.rationale, proposal.status, proposal.approver,
                proposal.created_at, proposal.updated_at,
            ))
            self._conn.commit()

        self._emit("proposal_created", {
            "proposal_id": proposal.proposal_id,
            "module_id": module_id,
            "change_type": change_type,
        })
        log.info("evolution proposed: %s for module %s (%s)",
                 proposal.proposal_id[:12], module_id, change_type)
        return dict(proposal.__dict__)

    def approve_proposal(self, proposal_id: str,
                         approver: str = "") -> dict | None:
        """Approve an evolution proposal."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evolution_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                return None
            if row["status"] != "proposed":
                raise ValueError(
                    f"Cannot approve proposal in status: {row['status']}"
                )
            now = time.time()
            self._conn.execute(
                "UPDATE evolution_proposals SET status = ?, approver = ?, "
                "updated_at = ? WHERE proposal_id = ?",
                ("approved", approver, now, proposal_id),
            )
            self._conn.commit()

        self._emit("proposal_approved", {
            "proposal_id": proposal_id,
            "approver": approver,
        })
        log.info("evolution approved: %s by %s",
                 proposal_id[:12], approver)
        return self.get_proposal(proposal_id)

    def get_proposal(self, proposal_id: str) -> dict | None:
        """Retrieve a proposal by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evolution_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_proposals(self, status: str | None = None,
                       module_id: str | None = None) -> list[dict]:
        """List proposals with optional filters."""
        q = "SELECT * FROM evolution_proposals WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        if module_id:
            q += " AND module_id = ?"
            params.append(module_id)
        q += " ORDER BY created_at DESC"

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def add_step(self, proposal_id: str, step_name: str,
                 step_order: int = 0,
                 config_json: str = "{}") -> dict:
        """Add an execution step to a proposal."""
        with self._lock:
            row = self._conn.execute(
                "SELECT proposal_id FROM evolution_proposals "
                "WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Proposal not found: {proposal_id}")

        step = EvolutionStep(
            proposal_id=proposal_id, step_name=step_name,
            step_order=step_order, config_json=config_json,
        )
        with self._lock:
            self._conn.execute("""
                INSERT INTO evolution_steps
                    (step_id, proposal_id, step_name, step_order,
                     config_json, status, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step.step_id, step.proposal_id, step.step_name,
                step.step_order, step.config_json, step.status,
                step.started_at, step.completed_at,
            ))
            self._conn.commit()

        return dict(step.__dict__)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_proposal(self, proposal_id: str) -> dict:
        """Execute all steps of an approved proposal."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evolution_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Proposal not found: {proposal_id}")
            if row["status"] not in ("approved", "in_progress"):
                raise ValueError(
                    f"Cannot execute proposal in status: {row['status']}"
                )

            steps = self._conn.execute(
                "SELECT * FROM evolution_steps WHERE proposal_id = ? "
                "ORDER BY step_order ASC",
                (proposal_id,),
            ).fetchall()

        if not steps:
            raise ValueError(
                f"No steps defined for proposal: {proposal_id}"
            )

        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE evolution_proposals SET status = ?, updated_at = ? "
                "WHERE proposal_id = ?",
                ("in_progress", now, proposal_id),
            )
            self._conn.commit()

        outcome = "success"
        completed_steps = 0
        for step in steps:
            step_now = time.time()
            with self._lock:
                self._conn.execute(
                    "UPDATE evolution_steps SET status = ?, started_at = ? "
                    "WHERE step_id = ?",
                    ("completed", step_now, step["step_id"]),
                )
                self._conn.commit()
            completed_steps += 1
            self._emit("step_completed", {
                "step_id": step["step_id"],
                "proposal_id": proposal_id,
                "step_name": step["step_name"],
            })

        result = EvolutionResult(
            proposal_id=proposal_id,
            outcome=outcome,
            summary_json=json.dumps({
                "steps_total": len(steps),
                "steps_completed": completed_steps,
            }),
            metrics_json=json.dumps({"execution_time": time.time() - now}),
        )

        final_status = "completed" if outcome == "success" else "failed"
        with self._lock:
            self._conn.execute("""
                INSERT INTO evolution_results
                    (result_id, proposal_id, outcome, summary_json,
                     metrics_json, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                result.result_id, result.proposal_id, result.outcome,
                result.summary_json, result.metrics_json,
                result.completed_at,
            ))
            self._conn.execute(
                "UPDATE evolution_proposals SET status = ?, updated_at = ? "
                "WHERE proposal_id = ?",
                (final_status, time.time(), proposal_id),
            )
            self._conn.commit()

        self._emit("evolution_completed", {
            "proposal_id": proposal_id,
            "outcome": outcome,
            "steps_completed": completed_steps,
        })
        log.info("evolution executed: %s -> %s (%d steps)",
                 proposal_id[:12], outcome, completed_steps)
        return {
            "result_id": result.result_id,
            "proposal_id": proposal_id,
            "outcome": outcome,
            "summary": json.loads(result.summary_json),
            "metrics": json.loads(result.metrics_json),
            "completed_at": result.completed_at,
        }

    def get_results(self, proposal_id: str) -> dict | None:
        """Get the execution result for a proposal."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evolution_results WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["summary"] = json.loads(d.get("summary_json", "{}"))
        d["metrics"] = json.loads(d.get("metrics_json", "{}"))
        return d

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_evolution_stats(self) -> dict[str, Any]:
        """Return evolution proposal and execution statistics."""
        with self._lock:
            total_proposals = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM evolution_proposals"
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM evolution_proposals "
                "GROUP BY status ORDER BY status"
            ).fetchall()

            type_rows = self._conn.execute(
                "SELECT change_type, COUNT(*) as cnt FROM evolution_proposals "
                "GROUP BY change_type ORDER BY change_type"
            ).fetchall()

            module_rows = self._conn.execute(
                "SELECT module_id, COUNT(*) as cnt FROM evolution_proposals "
                "GROUP BY module_id ORDER BY module_id"
            ).fetchall()

            total_steps = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM evolution_steps"
            ).fetchone()["cnt"]

            total_results = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM evolution_results"
            ).fetchone()["cnt"]

            outcome_rows = self._conn.execute(
                "SELECT outcome, COUNT(*) as cnt FROM evolution_results "
                "GROUP BY outcome ORDER BY outcome"
            ).fetchall()

        by_status = {r["status"]: r["cnt"] for r in status_rows}
        by_type = {r["change_type"]: r["cnt"] for r in type_rows}
        by_module = {r["module_id"]: r["cnt"] for r in module_rows}
        by_outcome = {r["outcome"]: r["cnt"] for r in outcome_rows}

        return {
            "total_proposals": total_proposals,
            "proposals_by_status": by_status,
            "proposals_by_type": by_type,
            "proposals_by_module": by_module,
            "total_steps": total_steps,
            "total_results": total_results,
            "results_by_outcome": by_outcome,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="aeis.evolution_tracker",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_tracker: EvolutionTracker | None = None


def get_evolution_tracker(event_bus: EventBus | None = None,
                          db_path: str | Path | None = None
                          ) -> EvolutionTracker:
    global _tracker
    if _tracker is None:
        _tracker = EvolutionTracker(db_path=db_path, event_bus=event_bus)
    return _tracker


def reset_evolution_tracker() -> None:
    global _tracker
    _tracker = None
