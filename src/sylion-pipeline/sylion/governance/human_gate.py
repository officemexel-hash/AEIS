"""
SYLION Governance -- Human Gate

Human-in-the-loop approval system.  Creates review requests that require
human approval before proceeding.  Tracks reviewer decisions, rationales,
and escalation status.

SQLite tables: human_gate_requests, human_gate_reviews
Thread-safe via RLock.  EventBus integration via _emit().

Singleton: get_human_gate() / reset_human_gate()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.governance.human_gate")


# Map legacy priority strings to unified priority enum (P0..P4).
_LEGACY_PRIORITY_MAP: dict[str, str] = {
    "critical": "P0",
    "urgent": "P0",
    "high": "P1",
    "normal": "P2",
    "medium": "P2",
    "low": "P3",
    "deferred": "P4",
}

_DECISION_CLASS_PRIORITY_MAP: dict[str, str] = {
    "D5": "P0",
    "D4": "P1",
    "D3": "P1",
    "D2": "P2",
    "D1": "P3",
    "D0": "P4",
}


def _mirror_priority(priority: str) -> str:
    raw = (priority or "normal").strip()
    if raw.upper() in {"P0", "P1", "P2", "P3", "P4"}:
        return raw.upper()
    p = raw.lower()
    if p.startswith("attachment_d"):
        cls = p.removeprefix("attachment_").upper()
        return _DECISION_CLASS_PRIORITY_MAP.get(cls, "P2")
    if p.upper() in _DECISION_CLASS_PRIORITY_MAP:
        return _DECISION_CLASS_PRIORITY_MAP[p.upper()]
    return _LEGACY_PRIORITY_MAP.get(p, "P2")


def _mirror_decision_class(context: Any) -> str:
    if isinstance(context, dict):
        raw = str(context.get("decision_class") or "").upper().strip()
        if raw in _DECISION_CLASS_PRIORITY_MAP:
            return raw
    return "D2"


def _mirror_decision(decision: str) -> str | None:
    """Translate human_gate review decision to unified ticket decision.

    Returns None for 'needs_info' since it's not a terminal state in the
    unified plane (ticket stays pending).
    """
    mapping = {"approved": "approved", "rejected": "rejected"}
    return mapping.get(decision)


class HumanGate:
    """Human-in-the-loop approval system.

    Manages review requests that require human approval.  Each request is
    linked to a governance gate and must be reviewed by a designated reviewer.
    Reviews can approve, reject, or request more information.

    Thread-safe. SQLite-backed. Emits events on request/review lifecycle.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
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
            CREATE TABLE IF NOT EXISTS human_gate_requests (
                request_id    TEXT PRIMARY KEY,
                gate_id       TEXT NOT NULL DEFAULT '',
                title         TEXT NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                context_json  TEXT NOT NULL DEFAULT '{}',
                requested_by  TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'pending',
                priority      TEXT NOT NULL DEFAULT 'normal',
                escalated     INTEGER NOT NULL DEFAULT 0,
                escalation_reason TEXT DEFAULT '',
                created_at    REAL NOT NULL,
                updated_at    REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS human_gate_reviews (
                review_id     TEXT PRIMARY KEY,
                request_id    TEXT NOT NULL,
                reviewer      TEXT NOT NULL,
                decision      TEXT NOT NULL,
                rationale     TEXT NOT NULL DEFAULT '',
                reviewed_at   REAL NOT NULL,
                FOREIGN KEY (request_id) REFERENCES human_gate_requests(request_id)
            )
        """)
        # Session + decision-tree subsystem (added 2026-04-25 to close
        # workspace split-plane gap surfaced by Codex audit).
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS hg_sessions (
                session_id      TEXT PRIMARY KEY,
                title           TEXT NOT NULL DEFAULT '',
                description     TEXT NOT NULL DEFAULT '',
                status          TEXT NOT NULL DEFAULT 'active',
                current_node_id TEXT NOT NULL DEFAULT '',
                created_at      REAL NOT NULL,
                updated_at      REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS hg_decision_nodes (
                node_id            TEXT PRIMARY KEY,
                session_id         TEXT NOT NULL,
                parent_node_id     TEXT NOT NULL DEFAULT '',
                phase              TEXT NOT NULL DEFAULT '',
                context_json       TEXT NOT NULL DEFAULT '{}',
                choices_json       TEXT NOT NULL DEFAULT '[]',
                chosen_choice_id   TEXT NOT NULL DEFAULT '',
                chosen_at          REAL,
                seq                INTEGER NOT NULL DEFAULT 0,
                created_at         REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES hg_sessions(session_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgr_status "
            "ON human_gate_requests(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgr_gate "
            "ON human_gate_requests(gate_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgr_requested_by "
            "ON human_gate_requests(requested_by)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgrv_request "
            "ON human_gate_reviews(request_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgrv_reviewer "
            "ON human_gate_reviews(reviewer)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgs_status "
            "ON hg_sessions(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgdn_session "
            "ON hg_decision_nodes(session_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hgdn_session_seq "
            "ON hg_decision_nodes(session_id, seq)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.human_gate",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    # ------------------------------------------------------------------
    # Request management
    # ------------------------------------------------------------------

    def create_request(self, gate_id: str = "", title: str = "",
                       description: str = "",
                       context_json: Any = None,
                       requested_by: str = "") -> dict:
        """Create a new human review request.

        Returns the request record.
        """
        request_id = self._uid()
        now = time.time()
        context_s = json.dumps(context_json, default=str) \
            if context_json is not None else "{}"

        with self._lock:
            self._conn.execute("""
                INSERT INTO human_gate_requests
                    (request_id, gate_id, title, description,
                     context_json, requested_by, status,
                     priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 'normal', ?)
            """, (
                request_id, gate_id, title, description,
                context_s, requested_by, now,
            ))
            self._conn.commit()

        self._emit("human_gate.review_requested", {
            "request_id": request_id, "gate_id": gate_id,
            "title": title, "requested_by": requested_by,
        })
        log.info("created review request %s: %s", request_id, title)

        self._mirror_create(
            request_id=request_id, gate_id=gate_id, title=title,
            description=description, context=context_json,
            requested_by=requested_by, created_at=now,
        )
        return {
            "request_id": request_id,
            "gate_id": gate_id,
            "title": title,
            "status": "pending",
            "requested_by": requested_by,
            "created_at": now,
        }

    def submit_review(self, request_id: str, reviewer: str,
                      decision: str, rationale: str = "") -> dict | None:
        """Submit a review for a request.

        Decision must be one of: approved, rejected, needs_info.
        Returns the review record or None if request not found.
        """
        valid_decisions = {"approved", "rejected", "needs_info"}
        if decision not in valid_decisions:
            return None

        with self._lock:
            req = self._conn.execute(
                "SELECT * FROM human_gate_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if not req:
                return None

            review_id = self._uid()
            now = time.time()

            self._conn.execute("""
                INSERT INTO human_gate_reviews
                    (review_id, request_id, reviewer, decision,
                     rationale, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (review_id, request_id, reviewer, decision, rationale, now))

            # Update request status
            status_map = {
                "approved": "approved",
                "rejected": "rejected",
                "needs_info": "needs_info",
            }
            new_status = status_map[decision]
            self._conn.execute("""
                UPDATE human_gate_requests
                SET status = ?, updated_at = ?
                WHERE request_id = ?
            """, (new_status, now, request_id))
            self._conn.commit()

        result = {
            "review_id": review_id,
            "request_id": request_id,
            "reviewer": reviewer,
            "decision": decision,
            "rationale": rationale,
            "reviewed_at": now,
        }

        self._emit("human_gate.review_submitted", {
            "review_id": review_id,
            "request_id": request_id,
            "decision": decision,
            "reviewer": reviewer,
        })
        log.info("review %s for request %s: %s by %s",
                 review_id, request_id, decision, reviewer)

        self._mirror_resolve(request_id=request_id, decision=decision,
                             rationale=rationale, reviewer=reviewer)
        return result

    def get_request(self, request_id: str) -> dict | None:
        """Return a request record with parsed JSON fields."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM human_gate_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["context_json"] = self._parse_json(d.get("context_json"), {})
        d["escalated"] = bool(d.get("escalated", 0))
        return d

    def list_requests(self, status: str | None = None,
                      reviewer: str | None = None) -> list[dict]:
        """List requests, optionally filtered by status or reviewer."""
        with self._lock:
            q = "SELECT * FROM human_gate_requests WHERE 1=1"
            params: list[Any] = []
            if status:
                q += " AND status = ?"
                params.append(status)
            if reviewer:
                q += (
                    " AND request_id IN (SELECT request_id "
                    "FROM human_gate_reviews WHERE reviewer = ?)"
                )
                params.append(reviewer)
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["context_json"] = self._parse_json(d.get("context_json"), {})
            d["escalated"] = bool(d.get("escalated", 0))
            results.append(d)
        return results

    def get_reviews(self, request_id: str) -> list[dict]:
        """Return all reviews for a request."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM human_gate_reviews WHERE request_id = ? "
                "ORDER BY reviewed_at",
                (request_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def escalate_request(self, request_id: str,
                         reason: str = "") -> dict | None:
        """Escalate a pending request.

        Returns updated request or None if not found or not in a
        reviewable state.
        """
        with self._lock:
            req = self._conn.execute(
                "SELECT * FROM human_gate_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if not req:
                return None

            now = time.time()
            self._conn.execute("""
                UPDATE human_gate_requests
                SET escalated = 1,
                    escalation_reason = ?,
                    status = 'escalated',
                    updated_at = ?
                WHERE request_id = ?
            """, (reason, now, request_id))
            self._conn.commit()

        self._emit("human_gate.review_escalated", {
            "request_id": request_id, "reason": reason,
        })
        log.info("escalated request %s: %s", request_id, reason)

        self._mirror_escalate(request_id=request_id, reason=reason)
        return self.get_request(request_id)

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics across all requests."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM human_gate_requests"
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM human_gate_requests "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            review_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM human_gate_reviews"
            ).fetchone()["cnt"]

            escalated_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM human_gate_requests "
                "WHERE escalated = 1"
            ).fetchone()["cnt"]

        return {
            "total_requests": total,
            "total_reviews": review_count,
            "escalated": escalated_count,
            "by_status": by_status,
        }

    # ------------------------------------------------------------------
    # Decision-session subsystem (workspace plane, 2026-04-25)
    # ------------------------------------------------------------------
    #
    # Workspace UI flows decisions as a tree: a session has nodes, each
    # node presents a context with N choices, the user picks one, and
    # a new frontier node is generated. Undo/rollback let the user
    # backtrack. The /api/v1/workspace/humangate/* routes assume this
    # vocabulary; before this method block the engine had only the
    # request/review model and every workspace call raised AttributeError.

    def _row_to_node_dict(self, row) -> dict:
        d = dict(row)
        d["context"] = self._parse_json(d.pop("context_json"), {})
        d["choices"] = self._parse_json(d.pop("choices_json"), [])
        return d

    def _row_to_session_dict(self, row) -> dict:
        return dict(row)

    def create_session(self, title: str, description: str = "") -> dict:
        """Create a new decision-tree session.

        The session starts empty. The first frontier node_id is the
        same as session_id; subsequent frontier nodes get fresh uuids.
        """
        session_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO hg_sessions "
                "(session_id, title, description, status, "
                "current_node_id, created_at) "
                "VALUES (?, ?, ?, 'active', ?, ?)",
                (session_id, title, description, session_id, now),
            )
            self._conn.commit()
        self._emit("hg_session.created", {
            "session_id": session_id, "title": title,
        })
        return {
            "session_id": session_id,
            "title": title,
            "description": description,
            "status": "active",
            "current_node_id": session_id,
            "created_at": now,
        }

    def get_session(self, session_id: str) -> dict | None:
        """Return a decision-tree session record (None if not found)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hg_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return self._row_to_session_dict(row) if row else None

    def list_sessions(self, status: str | None = None) -> list[dict]:
        """List decision-tree sessions, optionally filtered by status."""
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM hg_sessions WHERE status = ? "
                    "ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hg_sessions ORDER BY created_at DESC",
                ).fetchall()
        return [self._row_to_session_dict(r) for r in rows]

    def _resolve_node_session(self, node_id: str) -> str | None:
        """Return the session_id that owns node_id, or None.

        node_id may be:
          - the session.current_node_id (frontier node not yet persisted)
          - an existing hg_decision_nodes.node_id
        """
        with self._lock:
            sess = self._conn.execute(
                "SELECT session_id FROM hg_sessions "
                "WHERE current_node_id = ?",
                (node_id,),
            ).fetchone()
            if sess:
                return sess["session_id"]
            node = self._conn.execute(
                "SELECT session_id FROM hg_decision_nodes "
                "WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            return node["session_id"] if node else None

    def present_decision(self, node_id: str, context: Any,
                         choices: list[dict],
                         phase: str = "") -> dict:
        """Present (or re-present) a decision on a node.

        Creates the node row if it doesn't exist yet (first decision in a
        session). Re-presenting an unchosen node overwrites its context
        and choices. Re-presenting a chosen node raises ValueError --
        chosen nodes are immutable; use rollback_to to backtrack.
        """
        if not isinstance(choices, list) or not choices:
            raise ValueError("choices must be a non-empty list")
        for c in choices:
            if not isinstance(c, dict) or "id" not in c:
                raise ValueError("each choice must be a dict with an 'id'")

        session_id = self._resolve_node_session(node_id)
        if session_id is None:
            raise ValueError(
                f"node_id '{node_id}' is not bound to any session "
                f"-- call create_session() first")

        ctx_s = json.dumps(context, default=str)
        choices_s = json.dumps(choices, default=str)
        now = time.time()

        with self._lock:
            existing = self._conn.execute(
                "SELECT chosen_choice_id FROM hg_decision_nodes "
                "WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            if existing and existing["chosen_choice_id"]:
                raise ValueError(
                    f"node {node_id} already has a chosen choice; "
                    f"use rollback_to() to backtrack")
            if existing:
                self._conn.execute(
                    "UPDATE hg_decision_nodes "
                    "SET context_json = ?, choices_json = ?, phase = ? "
                    "WHERE node_id = ?",
                    (ctx_s, choices_s, phase, node_id),
                )
            else:
                seq_row = self._conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) AS m "
                    "FROM hg_decision_nodes WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                seq = (seq_row["m"] or 0) + 1
                parent = self._conn.execute(
                    "SELECT node_id FROM hg_decision_nodes "
                    "WHERE session_id = ? AND chosen_choice_id != '' "
                    "ORDER BY seq DESC LIMIT 1",
                    (session_id,),
                ).fetchone()
                parent_id = parent["node_id"] if parent else ""
                self._conn.execute(
                    "INSERT INTO hg_decision_nodes "
                    "(node_id, session_id, parent_node_id, phase, "
                    "context_json, choices_json, seq, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (node_id, session_id, parent_id, phase,
                     ctx_s, choices_s, seq, now),
                )
            self._conn.execute(
                "UPDATE hg_sessions SET current_node_id = ?, updated_at = ? "
                "WHERE session_id = ?",
                (node_id, now, session_id),
            )
            self._conn.commit()
        self._emit("hg_decision.presented", {
            "session_id": session_id, "node_id": node_id, "phase": phase,
        })
        return self.get_node(node_id)

    def get_node(self, node_id: str) -> dict | None:
        """Return a decision node by id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hg_decision_nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
        return self._row_to_node_dict(row) if row else None

    def make_choice(self, node_id: str, choice_id: str) -> dict:
        """Record a choice on the given node.

        Generates a new frontier node_id and updates the session pointer.
        Returns dict with chosen_node and next_node_id (the new frontier).
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hg_decision_nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"node {node_id} does not exist")
            node = self._row_to_node_dict(row)
            if node.get("chosen_choice_id"):
                raise ValueError(
                    f"node {node_id} already chose "
                    f"'{node['chosen_choice_id']}'")
            valid_ids = {c.get("id") for c in node.get("choices", [])}
            if choice_id not in valid_ids:
                raise ValueError(
                    f"choice_id '{choice_id}' not in node's choices "
                    f"({sorted(valid_ids)})")
            now = time.time()
            self._conn.execute(
                "UPDATE hg_decision_nodes "
                "SET chosen_choice_id = ?, chosen_at = ? "
                "WHERE node_id = ?",
                (choice_id, now, node_id),
            )
            next_node_id = uuid.uuid4().hex
            self._conn.execute(
                "UPDATE hg_sessions "
                "SET current_node_id = ?, updated_at = ? "
                "WHERE session_id = ?",
                (next_node_id, now, node["session_id"]),
            )
            self._conn.commit()
        self._emit("hg_decision.chosen", {
            "session_id": node["session_id"], "node_id": node_id,
            "choice_id": choice_id, "next_node_id": next_node_id,
        })
        return {
            "chosen_node": self.get_node(node_id),
            "next_node_id": next_node_id,
            "session_id": node["session_id"],
        }

    def undo_choice(self, session_id: str) -> dict | None:
        """Revert the most recently chosen node in a session.

        Clears its chosen_choice_id and resets the session pointer to
        that node. Returns the unchosen node, or None if no choice
        exists in the session.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hg_decision_nodes "
                "WHERE session_id = ? AND chosen_choice_id != '' "
                "ORDER BY chosen_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            node_id = row["node_id"]
            self._conn.execute(
                "UPDATE hg_decision_nodes "
                "SET chosen_choice_id = '', chosen_at = NULL "
                "WHERE node_id = ?",
                (node_id,),
            )
            now = time.time()
            self._conn.execute(
                "UPDATE hg_sessions "
                "SET current_node_id = ?, updated_at = ? "
                "WHERE session_id = ?",
                (node_id, now, session_id),
            )
            # Drop any frontier-only descendants (no choices made)
            self._conn.execute(
                "DELETE FROM hg_decision_nodes "
                "WHERE session_id = ? AND seq > ?",
                (session_id, row["seq"]),
            )
            self._conn.commit()
        self._emit("hg_decision.undone", {
            "session_id": session_id, "node_id": node_id,
        })
        return self.get_node(node_id)

    def rollback_to(self, session_id: str, node_id: str) -> dict | None:
        """Roll back a session to the named node.

        Clears choices on every later node and removes any nodes whose
        sequence is strictly greater than the target's. The session
        pointer is reset to node_id.
        """
        with self._lock:
            target = self._conn.execute(
                "SELECT seq FROM hg_decision_nodes "
                "WHERE node_id = ? AND session_id = ?",
                (node_id, session_id),
            ).fetchone()
            if not target:
                return None
            target_seq = target["seq"]
            self._conn.execute(
                "DELETE FROM hg_decision_nodes "
                "WHERE session_id = ? AND seq > ?",
                (session_id, target_seq),
            )
            self._conn.execute(
                "UPDATE hg_decision_nodes "
                "SET chosen_choice_id = '', chosen_at = NULL "
                "WHERE node_id = ?",
                (node_id,),
            )
            now = time.time()
            self._conn.execute(
                "UPDATE hg_sessions "
                "SET current_node_id = ?, updated_at = ? "
                "WHERE session_id = ?",
                (node_id, now, session_id),
            )
            self._conn.commit()
        self._emit("hg_decision.rolled_back", {
            "session_id": session_id, "node_id": node_id,
        })
        return self.get_node(node_id)

    def get_tree(self, session_id: str) -> dict:
        """Return the full decision tree of a session."""
        with self._lock:
            sess = self._conn.execute(
                "SELECT * FROM hg_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not sess:
                return {"session_id": session_id, "nodes": []}
            rows = self._conn.execute(
                "SELECT * FROM hg_decision_nodes "
                "WHERE session_id = ? ORDER BY seq",
                (session_id,),
            ).fetchall()
        return {
            "session": self._row_to_session_dict(sess),
            "nodes": [self._row_to_node_dict(r) for r in rows],
        }

    def get_current_decision(self, session_id: str) -> dict | None:
        """Return the current frontier decision (None when idle).

        The frontier is the most recent unchosen node. If the session has
        no nodes yet (caller hasn't called present_decision), returns None.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hg_decision_nodes "
                "WHERE session_id = ? AND chosen_choice_id = '' "
                "ORDER BY seq DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return self._row_to_node_dict(row) if row else None

    def get_history(self, session_id: str) -> list[dict]:
        """Return chosen nodes in chronological order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM hg_decision_nodes "
                "WHERE session_id = ? AND chosen_choice_id != '' "
                "ORDER BY chosen_at",
                (session_id,),
            ).fetchall()
        return [self._row_to_node_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Unified ticket plane mirror (Wave A1, 2026-04-24)
    # ------------------------------------------------------------------
    #
    # Every human_gate request also lands in the unified governance.tickets
    # plane (origin="global"). This way `governance.tickets.fetch_pending`
    # sees workspace, global, funding, mobile, skill, council in one query.
    # Failures in the mirror MUST NOT break legacy human_gate flow.

    def _mirror_create(self, request_id: str, gate_id: str, title: str,
                       description: str, context: Any, requested_by: str,
                       created_at: float) -> None:
        try:
            from sylion.governance.ticket import (
                GovernanceTicket, get_ticket_store,
            )
            payload: dict[str, Any] = {
                "legacy_gate_id": gate_id,
                "description": description,
                "context": context if isinstance(context, (dict, list)) else {},
            }
            project_id = None
            if isinstance(context, dict):
                project_id = context.get("project_id") or context.get("workspace_project_id")
            decision_class = _mirror_decision_class(context)
            priority = (
                str(context.get("governance_priority") or "")
                if isinstance(context, dict)
                else ""
            )
            ticket = GovernanceTicket(
                ticket_id=request_id,
                origin="global",
                project_id=project_id,
                decision_class=decision_class,
                gate_type="blocking",
                priority=_mirror_priority(priority or decision_class),
                title=title,
                summary=description[:200] if description else "",
                payload=payload,
                requested_by=requested_by,
                created_at=created_at,
            )
            get_ticket_store().submit(ticket)
        except Exception as exc:  # pragma: no cover -- defensive
            log.warning("ticket mirror submit failed for %s: %s",
                        request_id, exc)

    def _mirror_resolve(self, request_id: str, decision: str,
                        rationale: str, reviewer: str) -> None:
        unified = _mirror_decision(decision)
        if unified is None:
            return  # needs_info not terminal
        try:
            from sylion.governance.ticket import get_ticket_store
            get_ticket_store().resolve(
                request_id, unified, reason=rationale, reviewer=reviewer,
            )
        except Exception as exc:  # pragma: no cover -- defensive
            log.warning("ticket mirror resolve failed for %s: %s",
                        request_id, exc)

    def _mirror_escalate(self, request_id: str, reason: str) -> None:
        try:
            from sylion.governance.ticket import get_ticket_store
            get_ticket_store().escalate(request_id, reason=reason)
        except Exception as exc:  # pragma: no cover -- defensive
            log.warning("ticket mirror escalate failed for %s: %s",
                        request_id, exc)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: HumanGate | None = None


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    """W14 BE-7: redirect onto audit-isolated DB when SYLION_AUDIT_PROFILE_ID set."""
    if db_path is None or str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path))


def get_human_gate(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> HumanGate:
    global _instance
    if _instance is None:
        _instance = HumanGate(_audit_redirect(db_path), event_bus)
    return _instance


def reset_human_gate(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> HumanGate:
    global _instance
    _instance = HumanGate(_audit_redirect(db_path), event_bus)
    return _instance
