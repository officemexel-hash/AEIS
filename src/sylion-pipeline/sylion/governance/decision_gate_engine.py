"""
SYLION Governance — Decision Gate Engine

Governance-layer gate engine with approval/voting workflow.
Extends the core D0-D5 classification with multi-approval gates,
auto-approve criteria, and full audit trail.

Gate lifecycle: registered -> pending -> approved/blocked
Approval workflow: request -> votes cast -> threshold reached -> resolved

Thread-safe via threading.Lock, SQLite-backed with WAL mode, singleton pattern.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.governance.decision_gate_engine")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GateStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    BLOCKED = "blocked"


class VoteValue(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AutoApproveCriterion:
    """A criterion that, if all matched, auto-approves a gate evaluation."""
    field: str                # context key to check
    operator: str             # eq | ne | in | gt | lt | gte | lte | contains | exists
    value: Any = None


# ---------------------------------------------------------------------------
# DecisionGateEngine
# ---------------------------------------------------------------------------

class DecisionGateEngine:
    """Governance-layer gate engine with approval/voting workflow.

    SQLite-backed, thread-safe, singleton-capable, EventBus integration.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_decision_gates (
                gate_id               TEXT PRIMARY KEY,
                decision_class        TEXT NOT NULL DEFAULT 'D2',
                required_approvals    INTEGER NOT NULL DEFAULT 1,
                auto_approve_criteria TEXT NOT NULL DEFAULT '[]',
                description           TEXT NOT NULL DEFAULT '',
                created_at            REAL NOT NULL DEFAULT 0,
                enabled               INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_gate_evaluations (
                eval_id      TEXT PRIMARY KEY,
                gate_id      TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                context      TEXT NOT NULL DEFAULT '{}',
                auto_approved INTEGER NOT NULL DEFAULT 0,
                timestamp    REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_approval_requests (
                request_id    TEXT PRIMARY KEY,
                gate_id       TEXT NOT NULL,
                requester     TEXT NOT NULL,
                justification TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'open',
                created_at    REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_approval_votes (
                vote_id     TEXT PRIMARY KEY,
                request_id  TEXT NOT NULL,
                approver    TEXT NOT NULL,
                vote        TEXT NOT NULL,
                timestamp   REAL NOT NULL
            )
        """)
        # Indexes
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_gate ON sylion_gate_evaluations(gate_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eval_ts ON sylion_gate_evaluations(timestamp)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ar_gate ON sylion_approval_requests(gate_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ar_status ON sylion_approval_requests(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_votes_req ON sylion_approval_votes(request_id)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Gate registration
    # ------------------------------------------------------------------

    def register_gate(
        self,
        gate_id: str,
        decision_class: str = "D2",
        required_approvals: int = 1,
        auto_approve_criteria: list[dict] | None = None,
        description: str = "",
    ) -> dict:
        """Register a decision gate.

        Args:
            gate_id: Unique gate identifier (e.g. "G-CFG-01").
            decision_class: D0-D5 decision class for this gate.
            required_approvals: Number of approvals needed to pass.
            auto_approve_criteria: List of criterion dicts with
                keys (field, operator, value). If ALL match context,
                the gate auto-passes during evaluate_gate.
            description: Human-readable description.

        Returns:
            dict with gate_id and registration confirmation.
        """
        criteria_json = json.dumps(auto_approve_criteria or [], default=str)

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_decision_gates
                (gate_id, decision_class, required_approvals,
                 auto_approve_criteria, description, created_at, enabled)
                VALUES (?,?,?,?,?,?,1)
            """, (
                gate_id, decision_class, required_approvals,
                criteria_json, description, time.time(),
            ))
            self._conn.commit()

        self._emit("gate.registered", {
            "gate_id": gate_id,
            "decision_class": decision_class,
            "required_approvals": required_approvals,
        })

        log.info("registered gate %s (class=%s, approvals=%d)",
                 gate_id, decision_class, required_approvals)
        return {
            "gate_id": gate_id,
            "decision_class": decision_class,
            "required_approvals": required_approvals,
            "registered": True,
        }

    # ------------------------------------------------------------------
    # Gate evaluation
    # ------------------------------------------------------------------

    def evaluate_gate(self, gate_id: str, context: dict | None = None) -> dict:
        """Evaluate a gate against the given context.

        Checks auto-approve criteria first. If all criteria match the
        context, the gate auto-passes. Otherwise, checks active approval
        requests for this gate to determine status.

        Returns:
            dict with gate_id, status (passed/pending/blocked), and details.
        """
        context = context or {}
        eval_id = uuid.uuid4().hex
        ts = time.time()

        with self._lock:
            # Look up gate definition
            row = self._conn.execute(
                "SELECT * FROM sylion_decision_gates WHERE gate_id = ? AND enabled = 1",
                (gate_id,),
            ).fetchone()

            if not row:
                result = {
                    "gate_id": gate_id,
                    "status": "blocked",
                    "message": f"Gate {gate_id} not registered or disabled",
                    "auto_approved": False,
                }
                self._conn.execute("""
                    INSERT INTO sylion_gate_evaluations
                    (eval_id, gate_id, status, context, auto_approved, timestamp)
                    VALUES (?,?,?,?,?,?)
                """, (eval_id, gate_id, "blocked",
                      json.dumps(context, default=str), 0, ts))
                self._conn.commit()
                self._emit("gate.evaluated", result)

                # Capture snapshot for blocked evaluation
                try:
                    from sylion.governance.decision_snapshot import get_decision_snapshot
                    snapshot_engine = get_decision_snapshot()
                    snapshot_engine.capture_snapshot(
                        decision_id=eval_id,
                        gate_id=gate_id,
                        choice_made="blocked",
                        consequences={"evaluation_details": result},
                    )
                except Exception:
                    pass

                return result

            # Parse auto-approve criteria
            criteria_raw = json.loads(row["auto_approve_criteria"])
            auto_approved = self._check_auto_approve_unlocked(criteria_raw, context)

            if auto_approved:
                status = GateStatus.PASSED.value
            else:
                approved_request = self._conn.execute("""
                    SELECT request_id FROM sylion_approval_requests
                    WHERE gate_id = ? AND status = 'approved'
                    ORDER BY created_at DESC LIMIT 1
                """, (gate_id,)).fetchone()

                if approved_request:
                    status = GateStatus.PASSED.value
                else:
                    rejected_request = self._conn.execute("""
                        SELECT request_id FROM sylion_approval_requests
                        WHERE gate_id = ? AND status = 'rejected'
                        ORDER BY created_at DESC LIMIT 1
                    """, (gate_id,)).fetchone()

                    open_request = self._conn.execute("""
                        SELECT request_id FROM sylion_approval_requests
                        WHERE gate_id = ? AND status = 'open'
                        ORDER BY created_at DESC LIMIT 1
                    """, (gate_id,)).fetchone()

                    if open_request:
                        status = GateStatus.PENDING.value
                    elif rejected_request:
                        status = GateStatus.BLOCKED.value
                    else:
                        status = GateStatus.PENDING.value

            self._conn.execute("""
                INSERT INTO sylion_gate_evaluations
                (eval_id, gate_id, status, context, auto_approved, timestamp)
                VALUES (?,?,?,?,?,?)
            """, (eval_id, gate_id, status,
                  json.dumps(context, default=str), int(auto_approved), ts))
            self._conn.commit()

            result = {
                "gate_id": gate_id,
                "status": status,
                "auto_approved": auto_approved,
                "decision_class": row["decision_class"],
                "required_approvals": row["required_approvals"],
            }
        self._emit("gate.evaluated", result)

        # Capture snapshot after evaluation
        try:
            from sylion.governance.decision_snapshot import get_decision_snapshot
            snapshot_engine = get_decision_snapshot()
            snapshot_engine.capture_snapshot(
                decision_id=eval_id,
                gate_id=gate_id,
                choice_made=result.get("status", ""),
                consequences={"evaluation_details": result},
            )
        except Exception:
            pass  # Don't break evaluation if snapshot fails

        return result

    def _check_auto_approve_unlocked(
        self, criteria: list[dict], context: dict,
    ) -> bool:
        """Return True if all auto-approve criteria match the context."""
        if not criteria:
            return False

        for c in criteria:
            f = c.get("field", "")
            op = c.get("operator", "eq")
            val = c.get("value")

            ctx_val = context.get(f)

            if op == "eq":
                if ctx_val != val:
                    return False
            elif op == "ne":
                if ctx_val == val:
                    return False
            elif op == "in":
                if ctx_val not in (val if isinstance(val, list) else [val]):
                    return False
            elif op == "gt":
                if not (ctx_val is not None and ctx_val > val):
                    return False
            elif op == "lt":
                if not (ctx_val is not None and ctx_val < val):
                    return False
            elif op == "gte":
                if not (ctx_val is not None and ctx_val >= val):
                    return False
            elif op == "lte":
                if not (ctx_val is not None and ctx_val <= val):
                    return False
            elif op == "contains":
                if not (isinstance(ctx_val, (list, str)) and val in ctx_val):
                    return False
            elif op == "exists":
                if (val is True and f not in context) or \
                   (val is False and f in context):
                    return False
            else:
                return False

        return True

    _check_auto_approve = _check_auto_approve_unlocked

    # ------------------------------------------------------------------
    # Approval workflow
    # ------------------------------------------------------------------

    def request_approval(
        self,
        gate_id: str,
        requester: str,
        justification: str = "",
    ) -> dict:
        """Create an approval request for a gate.

        Returns:
            dict with request_id and status.
        """
        # Check gate exists
        gate = self._conn.execute(
            "SELECT gate_id FROM sylion_decision_gates WHERE gate_id = ? AND enabled = 1",
            (gate_id,),
        ).fetchone()

        if not gate:
            return {
                "created": False,
                "message": f"Gate {gate_id} not registered",
            }

        request_id = uuid.uuid4().hex
        ts = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO sylion_approval_requests
                (request_id, gate_id, requester, justification, status, created_at)
                VALUES (?,?,?,?,?,?)
            """, (request_id, gate_id, requester, justification,
                  ApprovalStatus.OPEN.value, ts))
            self._conn.commit()

        self._emit("gate.approval_requested", {
            "request_id": request_id,
            "gate_id": gate_id,
            "requester": requester,
        })

        log.info("approval request %s for gate %s by %s",
                 request_id[:12], gate_id, requester)
        return {
            "created": True,
            "request_id": request_id,
            "gate_id": gate_id,
            "status": ApprovalStatus.OPEN.value,
        }

    def approve(self, request_id: str, approver: str, vote: str) -> dict:
        """Cast a vote (approve/reject) on an approval request.

        If the number of approving votes reaches required_approvals, the
        request is auto-resolved as approved. If rejecting votes make
        approval impossible, the request is auto-resolved as rejected.

        Args:
            request_id: The approval request ID.
            approver: Identifier of the approver.
            vote: "approve" or "reject".

        Returns:
            dict with vote confirmation and updated request status.
        """
        if vote not in (VoteValue.APPROVE.value, VoteValue.REJECT.value):
            return {"cast": False, "message": f"Invalid vote: {vote}"}

        # Look up request
        req = self._conn.execute(
            "SELECT * FROM sylion_approval_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()

        if not req:
            return {"cast": False, "message": f"Request {request_id} not found"}

        if req["status"] != ApprovalStatus.OPEN.value:
            return {"cast": False, "message": f"Request is {req['status']}, not open"}

        # Check duplicate vote
        existing = self._conn.execute(
            "SELECT vote_id FROM sylion_approval_votes WHERE request_id = ? AND approver = ?",
            (request_id, approver),
        ).fetchone()
        if existing:
            return {"cast": False, "message": f"Approver {approver} already voted"}

        vote_id = uuid.uuid4().hex
        ts = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO sylion_approval_votes
                (vote_id, request_id, approver, vote, timestamp)
                VALUES (?,?,?,?,?)
            """, (vote_id, request_id, approver, vote, ts))

            # Tally votes
            tally = self._tally_votes(request_id)

            # Get required_approvals from gate
            gate = self._conn.execute(
                "SELECT required_approvals FROM sylion_decision_gates WHERE gate_id = ?",
                (req["gate_id"],),
            ).fetchone()
            required = gate["required_approvals"] if gate else 1

            new_status = ApprovalStatus.OPEN.value
            if tally["for"] >= required:
                new_status = ApprovalStatus.APPROVED.value
            elif tally["against"] > 0 and (tally["for"] + tally["against"]) >= required:
                # If enough votes cast and not all approve, reject
                if tally["for"] < required:
                    new_status = ApprovalStatus.REJECTED.value

            if new_status != ApprovalStatus.OPEN.value:
                self._conn.execute(
                    "UPDATE sylion_approval_requests SET status = ? WHERE request_id = ?",
                    (new_status, request_id),
                )

            self._conn.commit()

        self._emit("gate.vote_cast", {
            "request_id": request_id,
            "approver": approver,
            "vote": vote,
            "request_status": new_status,
        })

        log.info("vote %s by %s on %s -> request %s",
                 vote, approver, request_id[:12], new_status)

        return {
            "cast": True,
            "vote_id": vote_id,
            "request_status": new_status,
            "votes_for": tally["for"],
            "votes_against": tally["against"],
            "required": required,
        }

    def _tally_votes(self, request_id: str) -> dict:
        """Count votes for a request."""
        rows = self._conn.execute("""
            SELECT vote, COUNT(*) as cnt FROM sylion_approval_votes
            WHERE request_id = ? GROUP BY vote
        """, (request_id,)).fetchall()
        counts = {r["vote"]: r["cnt"] for r in rows}
        return {
            "for": counts.get(VoteValue.APPROVE.value, 0),
            "against": counts.get(VoteValue.REJECT.value, 0),
        }

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def check_gate_status(self, gate_id: str) -> dict:
        """Check current status of a gate.

        Returns:
            dict with status, votes_for, votes_against, required.
        """
        gate = self._conn.execute(
            "SELECT * FROM sylion_decision_gates WHERE gate_id = ?",
            (gate_id,),
        ).fetchone()

        if not gate:
            return {
                "gate_id": gate_id,
                "status": "unknown",
                "votes_for": 0,
                "votes_against": 0,
                "required": 0,
            }

        # Get the latest request for this gate
        latest_req = self._conn.execute("""
            SELECT * FROM sylion_approval_requests
            WHERE gate_id = ?
            ORDER BY created_at DESC LIMIT 1
        """, (gate_id,)).fetchone()

        if not latest_req:
            return {
                "gate_id": gate_id,
                "status": GateStatus.PENDING.value,
                "votes_for": 0,
                "votes_against": 0,
                "required": gate["required_approvals"],
            }

        tally = self._tally_votes(latest_req["request_id"])

        return {
            "gate_id": gate_id,
            "status": latest_req["status"],
            "votes_for": tally["for"],
            "votes_against": tally["against"],
            "required": gate["required_approvals"],
            "request_id": latest_req["request_id"],
        }

    def list_gates(self) -> list[dict]:
        """List all registered gates.

        Returns:
            List of dicts with gate details.
        """
        rows = self._conn.execute(
            "SELECT * FROM sylion_decision_gates ORDER BY gate_id"
        ).fetchall()
        return [
            {
                "gate_id": r["gate_id"],
                "decision_class": r["decision_class"],
                "required_approvals": r["required_approvals"],
                "auto_approve_criteria": json.loads(r["auto_approve_criteria"]),
                "description": r["description"],
                "enabled": bool(r["enabled"]),
            }
            for r in rows
        ]

    def get_gate_history(self, gate_id: str, limit: int = 20) -> list[dict]:
        """Get evaluation history for a gate.

        Args:
            gate_id: The gate identifier.
            limit: Maximum number of records to return.

        Returns:
            List of evaluation records, most recent first.
        """
        rows = self._conn.execute("""
            SELECT * FROM sylion_gate_evaluations
            WHERE gate_id = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (gate_id, limit)).fetchall()
        return [
            {
                "eval_id": r["eval_id"],
                "gate_id": r["gate_id"],
                "status": r["status"],
                "context": json.loads(r["context"]),
                "auto_approved": bool(r["auto_approved"]),
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]

    def get_stats(self) -> dict:
        """Get aggregate statistics.

        Returns:
            dict with total_gates, total_evaluations, pass_rate,
            average_time_to_decision.
        """
        total_gates = self._conn.execute(
            "SELECT COUNT(*) as c FROM sylion_decision_gates WHERE enabled = 1"
        ).fetchone()["c"]

        total_evals = self._conn.execute(
            "SELECT COUNT(*) as c FROM sylion_gate_evaluations"
        ).fetchone()["c"]

        passed = self._conn.execute(
            "SELECT COUNT(*) as c FROM sylion_gate_evaluations WHERE status = 'passed'"
        ).fetchone()["c"]

        pass_rate = (passed / total_evals * 100) if total_evals > 0 else 0.0

        # Average time from approval request to resolution
        avg_time = 0.0
        resolved = self._conn.execute("""
            SELECT
                r.created_at,
                (
                    SELECT MIN(v.timestamp)
                    FROM sylion_approval_votes v
                    WHERE v.request_id = r.request_id
                ) as first_vote_ts,
                (
                    SELECT MAX(v.timestamp)
                    FROM sylion_approval_votes v
                    WHERE v.request_id = r.request_id
                ) as last_vote_ts
            FROM sylion_approval_requests r
            WHERE r.status IN ('approved', 'rejected')
        """).fetchall()

        if resolved:
            times = []
            for r in resolved:
                if r["created_at"] and r["last_vote_ts"]:
                    times.append(r["last_vote_ts"] - r["created_at"])
            if times:
                avg_time = sum(times) / len(times)

        return {
            "total_gates": total_gates,
            "total_evaluations": total_evals,
            "pass_rate": round(pass_rate, 2),
            "average_time_to_decision": round(avg_time, 4),
        }

    # ------------------------------------------------------------------
    # Snapshot integration
    # ------------------------------------------------------------------

    def get_decision_with_snapshots(self, decision_id: str) -> dict | None:
        """Return decision evaluation record plus all related snapshots.

        Args:
            decision_id: The eval_id (decision_id) to look up.

        Returns:
            dict with "evaluation" and "snapshots" keys, or None if not found.
        """
        evaluation = self._conn.execute(
            "SELECT * FROM sylion_gate_evaluations WHERE eval_id = ?",
            (decision_id,),
        ).fetchone()

        if not evaluation:
            return None

        eval_dict = {
            "eval_id": evaluation["eval_id"],
            "gate_id": evaluation["gate_id"],
            "status": evaluation["status"],
            "context": json.loads(evaluation["context"]),
            "auto_approved": bool(evaluation["auto_approved"]),
            "timestamp": evaluation["timestamp"],
        }

        try:
            from sylion.governance.decision_snapshot import get_decision_snapshot
            snapshots = get_decision_snapshot().get_decision_timeline(
                decision_id=decision_id
            )
        except Exception:
            snapshots = []

        return {"evaluation": eval_dict, "snapshots": snapshots}

    # ------------------------------------------------------------------
    # EventBus integration
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.decision_gate_engine",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: DecisionGateEngine | None = None


def get_governance_gate_engine(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> DecisionGateEngine:
    """Get or create the global DecisionGateEngine singleton."""
    global _engine
    if _engine is None:
        _engine = DecisionGateEngine(db_path, event_bus)
    return _engine
