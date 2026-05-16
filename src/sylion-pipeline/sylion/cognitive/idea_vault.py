"""
SYLION Cognitive -- Idea Vault

Storage and lifecycle management of user ideas with tagging, voting,
full-text search, and status workflow.

Tables:
  ideas, idea_tags, idea_votes

Singleton: get_idea_vault() / reset_idea_vault()
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.idea_lifecycle_event import make_lifecycle_event

log = logging.getLogger("sylion.cognitive.idea_vault")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = (
    "draft", "submitted", "approved", "rejected", "implemented",
    "created", "clarification", "council_review", "awaiting_approval",
    "accepted", "stale", "abandoned", "archived",
    "deleted_soft", "deleted_hard",
)
VALID_VOTE_TYPES = ("upvote", "downvote")
HUMAN_GATE_PROTECTED_STATUSES = ("accepted", "approved", "implemented")

ACTIVE_STATUSES = (
    "draft", "created", "clarification", "submitted", "council_review",
    "awaiting_approval", "approved", "accepted", "implemented",
)
TERMINAL_STATUSES = (
    "rejected", "implemented", "abandoned", "archived",
    "deleted_soft", "deleted_hard",
)
DEFAULT_STALE_DAYS = 30


# ---------------------------------------------------------------------------
# IdeaVault
# ---------------------------------------------------------------------------

class IdeaVault:
    """Idea storage, tagging, voting, and lifecycle management.

    Thread-safe. SQLite-backed. Emits events on mutations.
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

    def _ensure_tables(self):
        # Step 1: tables only — IF NOT EXISTS will skip if old schema is present.
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS ideas (
                idea_id           TEXT PRIMARY KEY,
                title             TEXT NOT NULL DEFAULT '',
                description       TEXT NOT NULL DEFAULT '',
                author            TEXT NOT NULL DEFAULT '',
                status            TEXT NOT NULL DEFAULT 'draft',
                created_at        REAL NOT NULL,
                updated_at        REAL NOT NULL,
                last_activity_at  REAL,
                archived_at       REAL,
                deleted_at        REAL,
                stale_at          REAL,
                abandoned_at      REAL,
                previous_status   TEXT DEFAULT '',
                human_gate_required INTEGER NOT NULL DEFAULT 0,
                human_gate_request_id TEXT DEFAULT '',
                human_gate_decision   TEXT DEFAULT '',
                human_gate_decided_by TEXT DEFAULT '',
                human_gate_decided_at REAL,
                clarification_notes  TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS idea_tags (
                tag_id   TEXT PRIMARY KEY,
                idea_id  TEXT NOT NULL,
                tag      TEXT NOT NULL,
                UNIQUE(idea_id, tag)
            );
            CREATE TABLE IF NOT EXISTS idea_votes (
                vote_id   TEXT PRIMARY KEY,
                idea_id   TEXT NOT NULL,
                user_id   TEXT NOT NULL,
                vote_type TEXT NOT NULL,
                voted_at  REAL NOT NULL,
                UNIQUE(idea_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS idea_lifecycle_log (
                log_id      TEXT PRIMARY KEY,
                idea_id     TEXT NOT NULL,
                from_status TEXT NOT NULL DEFAULT '',
                to_status   TEXT NOT NULL,
                actor       TEXT NOT NULL DEFAULT '',
                rationale   TEXT NOT NULL DEFAULT '',
                logged_at   REAL NOT NULL
            );
        """)
        # Step 2: migrate older schemas (add missing columns) BEFORE indexing
        # so CREATE INDEX never references a column that doesn't yet exist.
        self._migrate_schema()
        # Step 3: indexes (safe now that all columns are guaranteed to exist).
        self._conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
            CREATE INDEX IF NOT EXISTS idx_ideas_author ON ideas(author);
            CREATE INDEX IF NOT EXISTS idx_ideas_created ON ideas(created_at);
            CREATE INDEX IF NOT EXISTS idx_ideas_activity ON ideas(last_activity_at);
            CREATE INDEX IF NOT EXISTS idx_ideas_archived ON ideas(archived_at);
            CREATE INDEX IF NOT EXISTS idx_ideas_deleted ON ideas(deleted_at);
            CREATE INDEX IF NOT EXISTS idx_tags_idea ON idea_tags(idea_id);
            CREATE INDEX IF NOT EXISTS idx_tags_tag ON idea_tags(tag);
            CREATE INDEX IF NOT EXISTS idx_votes_idea ON idea_votes(idea_id);
            CREATE INDEX IF NOT EXISTS idx_lifecycle_idea ON idea_lifecycle_log(idea_id);
            CREATE INDEX IF NOT EXISTS idx_lifecycle_at ON idea_lifecycle_log(logged_at);
        """)
        self._conn.commit()

    def _migrate_schema(self):
        """Add new lifecycle columns if upgrading from older schema."""
        cols = {r["name"] for r in self._conn.execute(
            "PRAGMA table_info(ideas)").fetchall()}
        new_cols = [
            ("last_activity_at", "REAL"),
            ("archived_at", "REAL"),
            ("deleted_at", "REAL"),
            ("stale_at", "REAL"),
            ("abandoned_at", "REAL"),
            ("previous_status", "TEXT DEFAULT ''"),
            ("human_gate_required", "INTEGER NOT NULL DEFAULT 0"),
            ("human_gate_request_id", "TEXT DEFAULT ''"),
            ("human_gate_decision", "TEXT DEFAULT ''"),
            ("human_gate_decided_by", "TEXT DEFAULT ''"),
            ("human_gate_decided_at", "REAL"),
            ("clarification_notes", "TEXT DEFAULT ''"),
            # workspace-plane fields (added 2026-04-25 to close split-plane gap)
            ("category", "TEXT NOT NULL DEFAULT ''"),
            ("priority", "TEXT NOT NULL DEFAULT 'normal'"),
            ("source", "TEXT NOT NULL DEFAULT ''"),
        ]
        for name, decl in new_cols:
            if name not in cols:
                self._conn.execute(
                    f"ALTER TABLE ideas ADD COLUMN {name} {decl}")
        self._conn.execute(
            "UPDATE ideas SET last_activity_at = COALESCE(last_activity_at, "
            "updated_at, created_at) WHERE last_activity_at IS NULL")

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.idea_vault",
            ))

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_status(status: str):
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of {VALID_STATUSES}"
            )

    @staticmethod
    def _has_pending_human_gate(row: sqlite3.Row, extra_sets: dict[str, Any] | None = None) -> bool:
        """Return True when a positive transition would bypass an open gate."""
        decision_override = (extra_sets or {}).get("human_gate_decision")
        decision = str(decision_override if decision_override is not None else row["human_gate_decision"] or "")
        return bool(row["human_gate_required"]) and decision.lower() != "approved"

    @staticmethod
    def _validate_vote_type(vote_type: str):
        if vote_type not in VALID_VOTE_TYPES:
            raise ValueError(
                f"Invalid vote_type '{vote_type}'. Must be one of {VALID_VOTE_TYPES}"
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_idea(self, title: str, description: str = "",
                    author: str = "", tags: list[str] | None = None) -> dict:
        """Create a new idea. Returns idea dict."""
        idea_id = self._uid()
        now = time.time()

        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO ideas (idea_id, title, description, author, "
                    "status, created_at, updated_at, last_activity_at) "
                    "VALUES (?, ?, ?, ?, 'draft', ?, ?, ?)",
                    (idea_id, title, description, author, now, now, now),
                )
                for tag in (tags or []):
                    self._conn.execute(
                        "INSERT OR IGNORE INTO idea_tags (tag_id, idea_id, tag) "
                        "VALUES (?, ?, ?)",
                        (self._uid(), idea_id, tag),
                    )
                self._log_lifecycle(idea_id, "", "draft", author, "created")
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise

        self._emit("idea_created", {
            "idea_id": idea_id, "title": title, "author": author,
        })
        log.info("create_idea %s: %.60s", idea_id[:12], title)
        return self.get_idea(idea_id)

    def _log_lifecycle(self, idea_id: str, from_status: str, to_status: str,
                       actor: str = "", rationale: str = ""):
        """Append-only lifecycle audit row. Caller manages commit."""
        row = make_lifecycle_event(idea_id, from_status, to_status, actor)
        self._conn.execute(
            "INSERT INTO idea_lifecycle_log "
            "(log_id, idea_id, from_status, to_status, actor, rationale, "
            "logged_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self._uid(),
                row["idea_id"],
                row["from_state"],
                row["to_state"],
                row["actor"],
                rationale,
                row["ts"],
            ),
        )

    def _touch(self, idea_id: str, *, status: str | None = None,
               extra_sets: dict[str, Any] | None = None,
               actor: str = "", rationale: str = "") -> dict | None:
        """Set status (optional) + bump activity + extra columns + log.

        Returns updated idea dict or None if idea_id not found.
        """
        if status is not None:
            self._validate_status(status)
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT status, human_gate_required, human_gate_decision FROM ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if not row:
                return None
            old_status = row["status"]
            if status in HUMAN_GATE_PROTECTED_STATUSES and self._has_pending_human_gate(row, extra_sets):
                raise ValueError(
                    "HumanGate approval required before changing this idea to "
                    f"'{status}'"
                )
            sets: list[str] = ["updated_at = ?", "last_activity_at = ?"]
            params: list[Any] = [now, now]
            if status is not None and status != old_status:
                sets.append("status = ?")
                params.append(status)
                sets.append("previous_status = ?")
                params.append(old_status)
            for k, v in (extra_sets or {}).items():
                sets.append(f"{k} = ?")
                params.append(v)
            params.append(idea_id)
            self._conn.execute(
                f"UPDATE ideas SET {', '.join(sets)} WHERE idea_id = ?",
                params,
            )
            if status is not None and status != old_status:
                self._log_lifecycle(idea_id, old_status, status, actor,
                                    rationale)
            self._conn.commit()
        if status is not None and status != old_status:
            self._emit("idea_status_changed", {
                "idea_id": idea_id,
                "old_status": old_status,
                "new_status": status,
                "actor": actor,
                "rationale": rationale,
            })
        return self.get_idea(idea_id)

    def update_idea(self, idea_id: str, title: str | None = None,
                    description: str | None = None,
                    author: str | None = None,
                    status: str | None = None) -> dict | None:
        """Update fields on an existing idea. Returns updated idea dict or None."""
        sets: list[str] = []
        params: list[Any] = []

        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if author is not None:
            sets.append("author = ?")
            params.append(author)
        if status is not None:
            self._validate_status(status)
            sets.append("status = ?")
            params.append(status)

        if not sets:
            return self.get_idea(idea_id)

        now = time.time()
        sets.append("updated_at = ?")
        params.append(now)
        sets.append("last_activity_at = ?")
        params.append(now)
        params.append(idea_id)

        old_status = None
        with self._lock:
            row = self._conn.execute(
                "SELECT status, human_gate_required, human_gate_decision FROM ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if not row:
                return None
            old_status = row["status"]
            if status in HUMAN_GATE_PROTECTED_STATUSES and self._has_pending_human_gate(row):
                raise ValueError(
                    "HumanGate approval required before changing this idea to "
                    f"'{status}'"
                )

            self._conn.execute(
                f"UPDATE ideas SET {', '.join(sets)} WHERE idea_id = ?",
                params,
            )
            if status is not None and status != old_status:
                self._log_lifecycle(idea_id, old_status, status, author or "",
                                    "update_idea")
            self._conn.commit()

        if status is not None and status != old_status:
            self._emit("idea_status_changed", {
                "idea_id": idea_id,
                "old_status": old_status,
                "new_status": status,
            })

        self._emit("idea_updated", {"idea_id": idea_id})
        log.info("update_idea %s", idea_id[:12])
        return self.get_idea(idea_id)

    def delete_idea(self, idea_id: str) -> bool:
        """Hard delete: remove idea and all its tags/votes. Returns True
        if deleted. Use soft_delete_idea() if recoverability is required.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT idea_id, status FROM ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if not row:
                return False
            old_status = row["status"]
            self._log_lifecycle(idea_id, old_status, "deleted_hard", "",
                                "hard delete")
            self._conn.execute(
                "DELETE FROM idea_votes WHERE idea_id = ?", (idea_id,),
            )
            self._conn.execute(
                "DELETE FROM idea_tags WHERE idea_id = ?", (idea_id,),
            )
            self._conn.execute(
                "DELETE FROM ideas WHERE idea_id = ?", (idea_id,),
            )
            self._conn.commit()
        self._emit("idea_deleted", {"idea_id": idea_id, "mode": "hard"})
        log.info("delete_idea %s (hard)", idea_id[:12])
        return True

    def hard_delete_idea(self, idea_id: str) -> bool:
        """Canonical name for hard-delete. Alias of delete_idea()."""
        return self.delete_idea(idea_id)

    # ------------------------------------------------------------------
    # Lifecycle transitions: clarification -> council -> approval -> accept
    # ------------------------------------------------------------------

    def submit_for_clarification(self, idea_id: str, notes: str = "",
                                 actor: str = "") -> dict | None:
        """Move idea to 'clarification' (questions outstanding)."""
        return self._touch(
            idea_id, status="clarification",
            extra_sets={"clarification_notes": notes},
            actor=actor, rationale="submitted for clarification",
        )

    def add_clarification_response(
        self,
        idea_id: str,
        response: str,
        responder: str = "operator",
    ) -> dict | None:
        """Append a timestamped operator response to ``clarification_notes``.

        W14 BE-8.1 (F-Idea1-2 P2). Preserves any existing notes by
        appending — never overwrites — and bumps ``last_activity_at``
        + writes an ``idea_lifecycle_log`` row so the response is
        replayable from the audit chain.
        """
        if not response or not str(response).strip():
            raise ValueError("response must be non-empty")
        with self._lock:
            row = self._conn.execute(
                "SELECT clarification_notes FROM ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
        if not row:
            return None
        existing = str(row["clarification_notes"] or "")
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        prefix = f"[{ts}] {responder}: "
        line = prefix + str(response).strip()
        merged = (existing + ("\n" if existing else "") + line)
        # _touch bumps last_activity_at + commits but only writes a
        # lifecycle log row when status changes — for a pure clarification
        # response the status stays the same, so we append the audit row
        # ourselves before delegating to _touch().
        with self._lock:
            status_row = self._conn.execute(
                "SELECT status FROM ideas WHERE idea_id = ?", (idea_id,),
            ).fetchone()
            if not status_row:
                return None
            current_status = str(status_row["status"])
            self._log_lifecycle(
                idea_id,
                from_status=current_status,
                to_status=current_status,
                actor=responder,
                rationale="clarification response appended",
            )
            self._conn.commit()
        return self._touch(
            idea_id,
            extra_sets={"clarification_notes": merged},
            actor=responder,
            rationale="clarification response appended",
        )

    def submit_for_council(self, idea_id: str,
                           actor: str = "") -> dict | None:
        """Send idea to council review."""
        return self._touch(
            idea_id, status="council_review", actor=actor,
            rationale="submitted to council",
        )

    def request_approval(self, idea_id: str, requested_by: str = "",
                         priority: str = "normal",
                         decision_class: str = "D2") -> dict | None:
        """Move idea to 'awaiting_approval' and create a Human Gate request.

        Stores the gate request_id on the idea row. Failures in the
        Human Gate plane do NOT block the status transition (mirror
        pattern; logged warning).
        """
        request_id = ""
        try:
            from sylion.governance.human_gate import get_human_gate
            gate = get_human_gate()
            current = self.get_idea(idea_id)
            if current is None:
                return None
            req = gate.create_request(
                gate_id=f"idea:{idea_id}",
                title=f"Idea approval: {current['title'][:80]}",
                description=current.get("description", "")[:500],
                context_json={
                    "idea_id": idea_id, "author": current.get("author", ""),
                    "tags": current.get("tags", []),
                    "decision_class": str(decision_class or "D2").upper(),
                    "governance_priority": priority,
                },
                requested_by=requested_by or current.get("author", ""),
            )
            request_id = req.get("request_id", "")
        except Exception as exc:  # pragma: no cover -- defensive
            log.warning("human_gate request failed for idea %s: %s",
                        idea_id, exc)
        return self._touch(
            idea_id, status="awaiting_approval",
            extra_sets={
                "human_gate_required": 1,
                "human_gate_request_id": request_id,
                "human_gate_decision": "",
                "human_gate_decided_by": "",
                "human_gate_decided_at": None,
            },
            actor=requested_by, rationale=f"approval requested ({priority})",
        )

    def record_human_gate_decision(self, idea_id: str, decision: str,
                                   reviewer: str = "",
                                   rationale: str = "") -> dict | None:
        """Mirror an external HumanGate review back onto the idea lifecycle.

        The HumanGate plane owns request/review rows. IdeaVault owns idea
        lifecycle state, so /gates review submissions must explicitly sync
        the linked idea rather than leaving it stuck in awaiting_approval.
        """
        status_map = {
            "approved": "accepted",
            "rejected": "rejected",
            "needs_info": "clarification",
        }
        if decision not in status_map:
            raise ValueError(
                "Invalid human gate decision. Must be approved, rejected, or needs_info"
            )
        now = time.time()
        return self._touch(
            idea_id,
            status=status_map[decision],
            extra_sets={
                "human_gate_required": 1 if decision == "needs_info" else 0,
                "human_gate_decision": decision,
                "human_gate_decided_by": reviewer,
                "human_gate_decided_at": now,
            },
            actor=reviewer,
            rationale=rationale or f"human gate {decision}",
        )

    def approve_idea(self, idea_id: str, approver: str = "",
                     rationale: str = "") -> dict | None:
        """Approve an idea and resolve the linked Human Gate request."""
        idea = self.get_idea(idea_id)
        if idea is None:
            return None
        gate_req = idea.get("human_gate_request_id") or ""
        if gate_req:
            try:
                from sylion.governance.human_gate import get_human_gate
                get_human_gate().submit_review(
                    gate_req, reviewer=approver or "system",
                    decision="approved", rationale=rationale,
                )
            except Exception as exc:  # pragma: no cover -- defensive
                log.warning("human_gate approve failed for %s: %s",
                            idea_id, exc)
        now = time.time()
        return self._touch(
            idea_id, status="accepted",
            extra_sets={
                "human_gate_decision": "approved",
                "human_gate_decided_by": approver,
                "human_gate_decided_at": now,
            },
            actor=approver, rationale=rationale or "approved",
        )

    def reject_idea(self, idea_id: str, approver: str = "",
                    rationale: str = "") -> dict | None:
        """Reject an idea and resolve the linked Human Gate request."""
        idea = self.get_idea(idea_id)
        if idea is None:
            return None
        gate_req = idea.get("human_gate_request_id") or ""
        if gate_req:
            try:
                from sylion.governance.human_gate import get_human_gate
                get_human_gate().submit_review(
                    gate_req, reviewer=approver or "system",
                    decision="rejected", rationale=rationale,
                )
            except Exception as exc:  # pragma: no cover -- defensive
                log.warning("human_gate reject failed for %s: %s",
                            idea_id, exc)
        now = time.time()
        return self._touch(
            idea_id, status="rejected",
            extra_sets={
                "human_gate_decision": "rejected",
                "human_gate_decided_by": approver,
                "human_gate_decided_at": now,
            },
            actor=approver, rationale=rationale or "rejected",
        )

    def mark_implemented(self, idea_id: str,
                         actor: str = "") -> dict | None:
        """Terminal state — idea was shipped."""
        return self._touch(
            idea_id, status="implemented", actor=actor,
            rationale="shipped",
        )

    # ------------------------------------------------------------------
    # Abandonment / archive / soft+hard delete / stale
    # ------------------------------------------------------------------

    def mark_abandoned(self, idea_id: str, reason: str = "",
                       actor: str = "") -> dict | None:
        """Mark explicitly abandoned by author or operator."""
        return self._touch(
            idea_id, status="abandoned",
            extra_sets={"abandoned_at": time.time()},
            actor=actor, rationale=reason or "abandoned",
        )

    def archive_idea(self, idea_id: str, actor: str = "",
                     reason: str = "") -> dict | None:
        """Archive an idea (out of active list, recoverable)."""
        return self._touch(
            idea_id, status="archived",
            extra_sets={"archived_at": time.time()},
            actor=actor, rationale=reason or "archived",
        )

    def unarchive_idea(self, idea_id: str,
                       actor: str = "") -> dict | None:
        """Restore from archive to its previous status (or 'draft')."""
        with self._lock:
            row = self._conn.execute(
                "SELECT previous_status FROM ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if not row:
                return None
            target = row["previous_status"] or "draft"
        if target not in VALID_STATUSES:
            target = "draft"
        return self._touch(
            idea_id, status=target,
            extra_sets={"archived_at": None},
            actor=actor, rationale="unarchived",
        )

    def soft_delete_idea(self, idea_id: str, actor: str = "",
                         reason: str = "") -> dict | None:
        """Hide an idea (recoverable). Uses status=deleted_soft."""
        return self._touch(
            idea_id, status="deleted_soft",
            extra_sets={"deleted_at": time.time()},
            actor=actor, rationale=reason or "soft delete",
        )

    def restore_idea(self, idea_id: str,
                     actor: str = "") -> dict | None:
        """Restore from soft-delete to the previous status."""
        with self._lock:
            row = self._conn.execute(
                "SELECT previous_status FROM ideas WHERE idea_id = ?",
                (idea_id,),
            ).fetchone()
            if not row:
                return None
            target = row["previous_status"] or "draft"
        if target not in VALID_STATUSES or target == "deleted_soft":
            target = "draft"
        return self._touch(
            idea_id, status=target,
            extra_sets={"deleted_at": None},
            actor=actor, rationale="restored from soft delete",
        )

    def mark_stale(self, idea_id: str,
                   actor: str = "system") -> dict | None:
        """Mark an idea as stale (no recent activity)."""
        return self._touch(
            idea_id, status="stale",
            extra_sets={"stale_at": time.time()},
            actor=actor, rationale="no recent activity",
        )

    def detect_stale(self, threshold_days: float = DEFAULT_STALE_DAYS,
                     dry_run: bool = False) -> list[dict]:
        """Find active ideas inactive for >= threshold_days.

        If dry_run is False, mark them stale. Returns the list of
        affected idea dicts.
        """
        cutoff = time.time() - (threshold_days * 86400.0)
        active_placeholder = ",".join("?" for _ in ACTIVE_STATUSES)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT idea_id FROM ideas "
                f"WHERE status IN ({active_placeholder}) "
                f"AND COALESCE(last_activity_at, updated_at, created_at) < ?",
                tuple(ACTIVE_STATUSES) + (cutoff,),
            ).fetchall()
            ids = [r["idea_id"] for r in rows]
        if dry_run:
            return [self.get_idea(i) for i in ids if self.get_idea(i)]
        results: list[dict] = []
        for iid in ids:
            updated = self.mark_stale(iid)
            if updated:
                results.append(updated)
        log.info("detect_stale: marked %d ideas stale (threshold=%.1fd)",
                 len(results), threshold_days)
        return results

    def get_lifecycle_history(self, idea_id: str) -> list[dict]:
        """Return the chronological lifecycle log for an idea."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM idea_lifecycle_log "
                "WHERE idea_id = ? ORDER BY logged_at",
                (idea_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_idea(self, idea_id: str) -> dict | None:
        """Retrieve a single idea by ID, with its tags and vote counts."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM ideas WHERE idea_id = ?", (idea_id,),
            ).fetchone()
            if not row:
                return None

            tag_rows = self._conn.execute(
                "SELECT tag FROM idea_tags WHERE idea_id = ?", (idea_id,),
            ).fetchall()
            tags = [r["tag"] for r in tag_rows]

            upvotes = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM idea_votes "
                "WHERE idea_id = ? AND vote_type = 'upvote'", (idea_id,),
            ).fetchone()["cnt"]
            downvotes = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM idea_votes "
                "WHERE idea_id = ? AND vote_type = 'downvote'", (idea_id,),
            ).fetchone()["cnt"]

        result = dict(row)
        result["tags"] = tags
        result["upvotes"] = upvotes
        result["downvotes"] = downvotes
        return result

    def list_ideas(self, status: str | None = None,
                   tag: str | None = None,
                   author: str | None = None,
                   limit: int = 100,
                   include_archived: bool = False,
                   include_deleted: bool = False,
                   include_stale: bool = True,
                   category: str | None = None,
                   priority: str | None = None) -> list[dict]:
        """List ideas with optional filters.

        By default soft-deleted ideas are hidden. Archived ideas are
        hidden unless include_archived=True. Stale ideas are included
        by default (set include_stale=False to hide).

        When `status` is supplied, the include_* flags are ignored
        (caller is asking for that exact status).
        """
        with self._lock:
            clauses: list[str] = []
            params: list[Any] = []

            if status is not None:
                self._validate_status(status)
                clauses.append("i.status = ?")
                params.append(status)
            else:
                excludes: list[str] = []
                if not include_deleted:
                    excludes.append("deleted_soft")
                    excludes.append("deleted_hard")
                if not include_archived:
                    excludes.append("archived")
                if not include_stale:
                    excludes.append("stale")
                if excludes:
                    placeholder = ",".join("?" for _ in excludes)
                    clauses.append(
                        f"i.status NOT IN ({placeholder})")
                    params.extend(excludes)
            if tag is not None:
                clauses.append(
                    "i.idea_id IN (SELECT idea_id FROM idea_tags WHERE tag = ?)"
                )
                params.append(tag)
            if author is not None:
                clauses.append("i.author = ?")
                params.append(author)
            if category is not None:
                clauses.append("i.category = ?")
                params.append(category)
            if priority is not None:
                clauses.append("i.priority = ?")
                params.append(priority)

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT i.* FROM ideas i{where} "
                f"ORDER BY i.created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        return [self.get_idea(r["idea_id"]) for r in rows]

    # ------------------------------------------------------------------
    # Voting
    # ------------------------------------------------------------------

    def vote_idea(self, idea_id: str, user_id: str,
                  vote_type: str = "upvote") -> dict | None:
        """Cast or update a vote on an idea. Returns vote dict or None."""
        self._validate_vote_type(vote_type)

        with self._lock:
            row = self._conn.execute(
                "SELECT idea_id FROM ideas WHERE idea_id = ?", (idea_id,),
            ).fetchone()
            if not row:
                return None

            now = time.time()
            existing = self._conn.execute(
                "SELECT vote_id FROM idea_votes WHERE idea_id = ? AND user_id = ?",
                (idea_id, user_id),
            ).fetchone()

            if existing:
                self._conn.execute(
                    "UPDATE idea_votes SET vote_type = ?, voted_at = ? "
                    "WHERE idea_id = ? AND user_id = ?",
                    (vote_type, now, idea_id, user_id),
                )
            else:
                vote_id = self._uid()
                self._conn.execute(
                    "INSERT INTO idea_votes (vote_id, idea_id, user_id, "
                    "vote_type, voted_at) VALUES (?, ?, ?, ?, ?)",
                    (vote_id, idea_id, user_id, vote_type, now),
                )
            self._conn.commit()

        self._emit("idea_voted", {
            "idea_id": idea_id, "user_id": user_id, "vote_type": vote_type,
        })
        log.info("vote_idea %s by %s: %s", idea_id[:12], user_id[:12], vote_type)
        return {"idea_id": idea_id, "user_id": user_id, "vote_type": vote_type}

    def get_votes(self, idea_id: str) -> list[dict]:
        """Get all votes for an idea."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM idea_votes WHERE idea_id = ? ORDER BY voted_at DESC",
                (idea_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_ideas(self, query: str) -> list[dict]:
        """Search ideas by title or description using LIKE."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM ideas "
                "WHERE title LIKE ? OR description LIKE ? "
                "ORDER BY created_at DESC",
                (f"%{query}%", f"%{query}%"),
            ).fetchall()
        return [self.get_idea(r["idea_id"]) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_idea_stats(self) -> dict:
        """Aggregate idea statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM ideas",
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM ideas GROUP BY status",
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            tag_rows = self._conn.execute(
                "SELECT tag, COUNT(*) as cnt FROM idea_tags GROUP BY tag "
                "ORDER BY cnt DESC LIMIT 20",
            ).fetchall()
            top_tags = [(r["tag"], r["cnt"]) for r in tag_rows]

            total_votes = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM idea_votes",
            ).fetchone()["cnt"]

        return {
            "total": total,
            "by_status": {s: by_status.get(s, 0) for s in VALID_STATUSES},
            "top_tags": top_tags,
            "total_votes": total_votes,
        }

    def get_stats(self) -> dict:
        """Workspace-route alias for get_idea_stats with extra rollups."""
        base = self.get_idea_stats()
        with self._lock:
            cat_rows = self._conn.execute(
                "SELECT category, COUNT(*) as cnt FROM ideas "
                "WHERE category != '' GROUP BY category ORDER BY cnt DESC",
            ).fetchall()
            pri_rows = self._conn.execute(
                "SELECT priority, COUNT(*) as cnt FROM ideas "
                "GROUP BY priority ORDER BY cnt DESC",
            ).fetchall()
            active = sum(base["by_status"].get(s, 0) for s in ACTIVE_STATUSES)
            terminal = sum(base["by_status"].get(s, 0) for s in TERMINAL_STATUSES)
        base["by_category"] = {r["category"]: r["cnt"] for r in cat_rows}
        base["by_priority"] = {r["priority"]: r["cnt"] for r in pri_rows}
        base["active"] = active
        base["terminal"] = terminal
        return base

    # ------------------------------------------------------------------
    # Workspace-plane shims (close split-plane gap with workspace_routes)
    # ------------------------------------------------------------------
    #
    # The /api/v1/workspace/ideas/* routes call submit_idea / update_idea
    # / submit_to_pipeline / list_ideas(category=...) / get_stats(). These
    # signatures use a workspace vocabulary (content/category/priority/source)
    # that historically didn't exist on the engine. Codex audit 2026-04-25
    # surfaced 4 hard AttributeError/TypeError on this surface; the methods
    # below close that gap without breaking the canonical create_idea/
    # update_idea contract used by 14 tests.

    def submit_idea(self, content: str, category: str = "",
                    priority: str = "normal", source: str = "",
                    tags: list[str] | None = None,
                    author: str = "") -> dict:
        """Workspace shortcut: create idea from a content blob.

        Maps content -> (title=first 80 chars, description=full content) and
        records category / priority / source on the row. Returns the idea
        dict (same shape as create_idea).
        """
        cleaned = (content or "").strip()
        if not cleaned:
            raise ValueError("idea content must not be empty")
        title = cleaned.split("\n", 1)[0][:80]
        idea = self.create_idea(
            title=title,
            description=content or "",
            author=author,
            tags=tags,
        )
        if idea is None:
            return idea
        idea_id = idea["idea_id"]
        with self._lock:
            self._conn.execute(
                "UPDATE ideas SET category = ?, priority = ?, source = ? "
                "WHERE idea_id = ?",
                (category or "", priority or "normal", source or "", idea_id),
            )
            self._conn.commit()
        self._emit("idea_submitted_workspace", {
            "idea_id": idea_id, "category": category, "priority": priority,
            "source": source,
        })
        return self.get_idea(idea_id)

    def update_idea_workspace(self, idea_id: str,
                              content: str | None = None,
                              category: str | None = None,
                              priority: str | None = None,
                              tags: list[str] | None = None) -> dict | None:
        """Workspace-vocabulary update: content/category/priority/tags.

        Distinct from canonical update_idea(title/description/author/status)
        to avoid signature collision.
        """
        sets: list[str] = []
        params: list[Any] = []
        if content is not None:
            sets.append("description = ?")
            params.append(content)
            sets.append("title = ?")
            params.append(content.strip().split("\n", 1)[0][:80] or "(untitled)")
        if category is not None:
            sets.append("category = ?")
            params.append(category)
        if priority is not None:
            sets.append("priority = ?")
            params.append(priority)
        if not sets and tags is None:
            return self.get_idea(idea_id)

        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT idea_id FROM ideas WHERE idea_id = ?", (idea_id,),
            ).fetchone()
            if not row:
                return None
            if sets:
                sets.append("updated_at = ?")
                params.append(now)
                sets.append("last_activity_at = ?")
                params.append(now)
                params.append(idea_id)
                self._conn.execute(
                    f"UPDATE ideas SET {', '.join(sets)} WHERE idea_id = ?",
                    params,
                )
            if tags is not None:
                self._conn.execute(
                    "DELETE FROM idea_tags WHERE idea_id = ?", (idea_id,),
                )
                for tag in tags:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO idea_tags "
                        "(tag_id, idea_id, tag) VALUES (?, ?, ?)",
                        (self._uid(), idea_id, tag),
                    )
            self._conn.commit()
        self._emit("idea_updated", {"idea_id": idea_id})
        return self.get_idea(idea_id)

    def submit_to_pipeline(self, idea_id: str,
                           actor: str = "") -> dict | None:
        """Move an idea into the pipeline (status=submitted)."""
        return self._touch(
            idea_id, status="submitted", actor=actor,
            rationale="submitted to pipeline",
        )


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_vault: IdeaVault | None = None


def _audit_redirect(db_path: str | Path | None) -> str | Path | None:
    """W14 BE-7: redirect onto audit-isolated DB when SYLION_AUDIT_PROFILE_ID is set.

    Pure pass-through when env unset (legacy behavior preserved). ``:memory:``
    and ``None`` (which the IdeaVault treats as ``:memory:``) bypass redirect
    so unit tests stay isolated.
    """
    if db_path is None or str(db_path) == ":memory:":
        return db_path
    from sylion.aeis_v2.audit_profile import is_audit_mode, resolve_db_path
    if not is_audit_mode():
        return db_path
    return resolve_db_path(Path(db_path))


def get_idea_vault(db_path: str | Path | None = None,
                   event_bus: EventBus | None = None) -> IdeaVault:
    global _vault
    if _vault is None:
        _vault = IdeaVault(_audit_redirect(db_path), event_bus)
    return _vault


def reset_idea_vault(db_path: str | Path | None = None,
                     event_bus: EventBus | None = None) -> IdeaVault:
    global _vault
    _vault = IdeaVault(_audit_redirect(db_path), event_bus)
    return _vault
