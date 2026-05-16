"""
SYLION Governance — Council Workflow

Council 4/4 voting mechanism for D3+ decisions.
Quorum: 4/4 Council members must vote.
D4+: additional Human Gate required.
D5: additional External approval required.

Vote lifecycle: open → cast votes → tally → resolve
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
from typing import Any

from sylion.core.decision_gate_engine import DecisionClass
from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus
from sylion.core.evidence_spine import EvidenceSpine, EvidenceEntry

log = logging.getLogger("sylion.governance.council_workflow")

COUNCIL_SIZE = 4


def _public_model_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    """Return the model policy payload without Python-only runtime objects."""
    if not isinstance(policy, dict):
        return {}
    public = dict(policy)
    public.pop("runtime_model", None)
    return public


def _preflight_council_vote(member_id: str) -> dict[str, Any]:
    """Apply the model runtime policy before a model/member can vote."""
    try:
        from sylion.cognitive.model_runtime_policy import preflight_model_call

        return _public_model_policy(
            preflight_model_call(
                member_id,
                operation="council_vote",
                action_type="council_vote",
                risk_level="medium",
                create_human_gate=True,
            )
        )
    except Exception as exc:  # noqa: BLE001 - council voting should surface policy failures cleanly.
        log.exception("council vote policy check failed member_id=%s", member_id)
        return {
            "allowed": False,
            "requires_human_gate": True,
            "reason": f"Council vote policy check failed: {str(exc)[:200]}",
            "model_id": member_id,
            "policy_error": True,
        }


def _invalidate_council_cache(session_id: str | None = None) -> None:
    """Phase 3 W1.3 — drop council.decision cache after a vote write.

    A wider invalidation (whole namespace) is correct here: the tally for
    one session does not depend on others, but the project-scoped state
    view (``get_council_state``) ignores ``session_id`` so we drop the
    full namespace. Failures must not block the write path.
    """
    try:
        from sylion.infra.cache import get_cache
        get_cache().invalidate("sylion:council.decision:*")
    except Exception:  # noqa: BLE001
        log.warning("council.decision cache invalidation failed", exc_info=True)


class VoteValue(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


class SessionStatus(str, Enum):
    OPEN = "open"
    VOTING = "voting"
    CLOSED_APPROVED = "closed_approved"
    CLOSED_REJECTED = "closed_rejected"
    CLOSED_EXPIRED = "closed_expired"


@dataclass
class CouncilMember:
    member_id: str = ""
    name: str = ""
    role: str = ""  # kernel_architect | security_engineer | ...
    department: str = ""


@dataclass
class Vote:
    vote_id: str = ""
    session_id: str = ""
    member_id: str = ""
    value: VoteValue = VoteValue.ABSTAIN
    rationale: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.vote_id:
            self.vote_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class CouncilSession:
    session_id: str = ""
    proposal_id: str = ""
    decision_class: DecisionClass = DecisionClass.D3
    title: str = ""
    description: str = ""
    evidence_ref: str = ""
    status: SessionStatus = SessionStatus.OPEN
    required_quorum: int = COUNCIL_SIZE
    human_gate_required: bool = False
    human_gate_status: str = ""  # pending | approved | rejected
    external_required: bool = False
    external_status: str = ""
    opened_at: float = 0.0
    closed_at: float = 0.0

    def __post_init__(self):
        if not self.session_id:
            self.session_id = uuid.uuid4().hex
        if not self.opened_at:
            self.opened_at = time.time()
        if self.decision_class in (DecisionClass.D4, DecisionClass.D5):
            self.human_gate_required = True
        if self.decision_class == DecisionClass.D5:
            self.external_required = True


class CouncilWorkflow:
    """Council 4/4 voting engine for D3+ decisions."""

    def __init__(self, evidence_spine: EvidenceSpine | None = None,
                 event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
        self._evidence_spine = evidence_spine
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS council_sessions (
                session_id       TEXT PRIMARY KEY,
                proposal_id      TEXT NOT NULL,
                decision_class   TEXT NOT NULL,
                title            TEXT NOT NULL DEFAULT '',
                description      TEXT NOT NULL DEFAULT '',
                evidence_ref     TEXT NOT NULL DEFAULT '',
                status           TEXT NOT NULL DEFAULT 'open',
                required_quorum  INTEGER NOT NULL DEFAULT 4,
                human_gate_req   INTEGER NOT NULL DEFAULT 0,
                human_gate_status TEXT NOT NULL DEFAULT '',
                external_req     INTEGER NOT NULL DEFAULT 0,
                external_status  TEXT NOT NULL DEFAULT '',
                opened_at        REAL NOT NULL,
                closed_at        REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS council_votes (
                vote_id    TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                member_id  TEXT NOT NULL,
                value      TEXT NOT NULL,
                rationale  TEXT NOT NULL DEFAULT '',
                timestamp  REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_votes_session ON council_votes(session_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_proposal ON council_sessions(proposal_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON council_sessions(status)")
        self._conn.commit()

    def open_session(self, session: CouncilSession) -> dict:
        with self._lock:
            self._conn.execute("""
                INSERT INTO council_sessions
                (session_id, proposal_id, decision_class, title, description, evidence_ref,
                 status, required_quorum, human_gate_req, human_gate_status,
                 external_req, external_status, opened_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                session.session_id, session.proposal_id, session.decision_class.value,
                session.title, session.description, session.evidence_ref,
                SessionStatus.OPEN.value, session.required_quorum,
                int(session.human_gate_required), session.human_gate_status,
                int(session.external_required), session.external_status,
                session.opened_at,
            ))
            self._conn.commit()

        self._emit(
            "aeis.council.formation_requested",
            {
                "decision_id": session.proposal_id,
                "proposed_d_level": session.decision_class.value,
                "proposed_council_size": session.required_quorum,
                "proposed_roles": [],
            },
        )
        self._emit("council.session_opened", {
            "session_id": session.session_id,
            "proposal_id": session.proposal_id,
            "decision_class": session.decision_class.value,
        })

        log.info("council session %s opened for proposal %s (D%s)",
                 session.session_id[:12], session.proposal_id[:12], session.decision_class.value)
        return {"session_id": session.session_id, "status": SessionStatus.OPEN.value}

    def cast_vote(self, vote: Vote) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM council_sessions WHERE session_id = ?",
                (vote.session_id,)
            ).fetchone()
            if not row:
                return {"cast": False, "message": "Session not found"}
            if row["status"] not in (SessionStatus.OPEN.value, SessionStatus.VOTING.value):
                return {"cast": False, "message": f"Session status is {row['status']}"}

            existing = self._conn.execute(
                "SELECT vote_id FROM council_votes WHERE session_id = ? AND member_id = ?",
                (vote.session_id, vote.member_id)
            ).fetchone()
            if existing:
                return {"cast": False, "message": "Member already voted"}

        policy = _preflight_council_vote(vote.member_id)
        if not policy.get("allowed", False):
            return {
                "cast": False,
                "message": policy.get("reason") or "Council vote blocked by model runtime policy",
                "policy": policy,
            }

        with self._lock:
            row = self._conn.execute(
                "SELECT status FROM council_sessions WHERE session_id = ?",
                (vote.session_id,)
            ).fetchone()
            if not row:
                return {"cast": False, "message": "Session not found", "policy": policy}
            if row["status"] not in (SessionStatus.OPEN.value, SessionStatus.VOTING.value):
                return {"cast": False, "message": f"Session status is {row['status']}", "policy": policy}

            existing = self._conn.execute(
                "SELECT vote_id FROM council_votes WHERE session_id = ? AND member_id = ?",
                (vote.session_id, vote.member_id)
            ).fetchone()
            if existing:
                return {"cast": False, "message": "Member already voted", "policy": policy}

            self._conn.execute("""
                INSERT INTO council_votes (vote_id, session_id, member_id, value, rationale, timestamp)
                VALUES (?,?,?,?,?,?)
            """, (vote.vote_id, vote.session_id, vote.member_id, vote.value.value,
                  vote.rationale, vote.timestamp))

            self._conn.execute(
                "UPDATE council_sessions SET status = ? WHERE session_id = ? AND status = ?",
                (SessionStatus.VOTING.value, vote.session_id, SessionStatus.OPEN.value)
            )
            self._conn.commit()

        _invalidate_council_cache(vote.session_id)

        self._emit("council.vote_cast", {
            "session_id": vote.session_id,
            "member_id": vote.member_id,
            "value": vote.value.value,
        })

        tally = self.tally(vote.session_id)
        return {"cast": True, "vote_id": vote.vote_id, "tally": tally, "policy": policy}

    def tally(self, session_id: str) -> dict:
        """Count votes and determine outcome.

        Phase 3 W1.3: cached under ``council.decision`` (TTL 1h). Cache is
        invalidated by ``cast_vote`` and ``human_gate_decide``.
        """
        cache_key: str | None = None
        try:
            from sylion.infra.cache import default_ttl, get_cache, make_key

            cache_key = make_key("council.decision", "tally", session_id)
            cached_payload = get_cache().get(cache_key)
            if cached_payload is not None:
                return cached_payload
        except Exception:  # noqa: BLE001
            log.warning("council.decision cache get failed", exc_info=True)
            cache_key = None

        result = self._tally_impl(session_id)

        if cache_key is not None:
            try:
                from sylion.infra.cache import default_ttl, get_cache

                get_cache().set(
                    cache_key,
                    result,
                    ttl=default_ttl("council.decision"),
                )
            except Exception:  # noqa: BLE001
                log.warning("council.decision cache set failed", exc_info=True)

        return result

    def _tally_impl(self, session_id: str) -> dict:
        """Uncached tally implementation. See ``tally`` for the public API."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM council_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not row:
                return {"tallied": False, "message": "Session not found"}

            votes = self._conn.execute(
                "SELECT value, COUNT(*) as cnt FROM council_votes WHERE session_id = ? GROUP BY value",
                (session_id,)
            ).fetchall()

        vote_counts = {r["value"]: r["cnt"] for r in votes}
        approves = vote_counts.get(VoteValue.APPROVE.value, 0)
        rejects = vote_counts.get(VoteValue.REJECT.value, 0)
        abstains = vote_counts.get(VoteValue.ABSTAIN.value, 0)
        total = approves + rejects + abstains
        quorum = row["required_quorum"]

        resolved = False
        outcome = ""

        if approves >= quorum:
            outcome = "approved"
            resolved = True
        elif rejects > (COUNCIL_SIZE - quorum):
            outcome = "rejected"
            resolved = True
        elif total >= COUNCIL_SIZE and approves < quorum:
            outcome = "rejected"
            resolved = True

        if resolved and row["status"] not in (SessionStatus.CLOSED_APPROVED.value, SessionStatus.CLOSED_REJECTED.value):
            new_status = SessionStatus.CLOSED_APPROVED.value if outcome == "approved" else SessionStatus.CLOSED_REJECTED.value
            with self._lock:
                self._conn.execute(
                    "UPDATE council_sessions SET status = ?, closed_at = ? WHERE session_id = ?",
                    (new_status, time.time(), session_id)
                )
                self._conn.commit()

            self._emit("council.resolved", {"session_id": session_id, "outcome": outcome})

        return {
            "session_id": session_id,
            "approves": approves, "rejects": rejects, "abstains": abstains,
            "total": total, "quorum": quorum,
            "resolved": resolved, "outcome": outcome,
        }

    def human_gate_decide(self, session_id: str, decision: str, by: str = "") -> dict:
        """Human gate decision for D4+ sessions."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM council_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not row:
                return {"decided": False, "message": "Session not found"}
            if not row["human_gate_req"]:
                return {"decided": False, "message": "No human gate required"}
            if row["status"] != SessionStatus.CLOSED_APPROVED.value:
                return {"decided": False, "message": "Council has not approved yet"}

            self._conn.execute(
                "UPDATE council_sessions SET human_gate_status = ? WHERE session_id = ?",
                (decision, session_id)
            )
            self._conn.commit()

        _invalidate_council_cache(session_id)

        self._emit("council.human_gate", {"session_id": session_id, "decision": decision, "by": by})
        return {"decided": True, "session_id": session_id, "human_gate": decision}

    def get_session(self, session_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM council_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, status: str | None = None) -> list[dict]:
        q = "SELECT * FROM council_sessions WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY opened_at DESC"
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.council_workflow",
            ))


_council: CouncilWorkflow | None = None


def get_council_workflow(evidence_spine: EvidenceSpine | None = None,
                         event_bus: EventBus | None = None,
                         db_path: str | Path | None = None) -> CouncilWorkflow:
    global _council
    if _council is None:
        _council = CouncilWorkflow(evidence_spine, event_bus, db_path)
    return _council
