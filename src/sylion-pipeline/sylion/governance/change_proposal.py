"""
SYLION Governance -- Change Proposal Manager

Manages RFC-style change proposals for modifications to the system.
Tracks proposals through a full lifecycle: draft -> submitted -> under_review
-> approved/rejected -> implemented/withdrawn. Supports multi-reviewer
workflow with verdicts and comments.

Schema:
  change_proposals  - proposal metadata, status, priority
  proposal_reviews  - reviewer verdicts and comments

Thread-safe. SQLite-backed. Emits events via EventBus.
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.governance.change_proposal")

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_CHANGE_TYPES = (
    "feature",
    "bugfix",
    "refactor",
    "migration",
    "config_change",
    "api_change",
)

VALID_STATUSES = (
    "draft",
    "submitted",
    "under_review",
    "approved",
    "rejected",
    "implemented",
    "withdrawn",
)

VALID_PRIORITIES = ("low", "medium", "high", "critical")

VALID_VERDICTS = ("approve", "reject", "request_changes", "abstain")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ChangeProposal:
    """A change proposal (RFC) for a system modification."""
    proposal_id: str = ""
    title: str = ""
    description: str = ""
    change_type: str = "feature"
    module_id: str = ""
    proposer: str = ""
    status: str = "draft"
    priority: str = "medium"
    created_at: float = 0.0
    updated_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    # W14 E3 append-only: optional link to a sandbox branch. None for legacy
    # proposals; populated when a proposal originates from a repair/test/release
    # branch so the auditor can trace back to the isolated workspace.
    branch_id: str | None = None

    def __post_init__(self):
        if not self.proposal_id:
            self.proposal_id = uuid.uuid4().hex
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class ProposalReview:
    """A review verdict on a change proposal."""
    review_id: str = ""
    proposal_id: str = ""
    reviewer: str = ""
    verdict: str = ""
    comment: str = ""
    reviewed_at: float = 0.0

    def __post_init__(self):
        if not self.review_id:
            self.review_id = uuid.uuid4().hex
        if not self.reviewed_at:
            self.reviewed_at = time.time()


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class ChangeProposalManager:
    """Manages change proposals (RFCs) for system modifications.

    SQLite-backed, thread-safe. Integrates with EventBus for proposal
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
            CREATE TABLE IF NOT EXISTS change_proposals (
                proposal_id  TEXT PRIMARY KEY,
                title        TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                change_type  TEXT NOT NULL DEFAULT 'feature',
                module_id    TEXT NOT NULL DEFAULT '',
                proposer     TEXT NOT NULL DEFAULT '',
                status       TEXT NOT NULL DEFAULT 'draft',
                priority     TEXT NOT NULL DEFAULT 'medium',
                created_at   REAL NOT NULL,
                updated_at   REAL NOT NULL DEFAULT 0,
                metadata     TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS proposal_reviews (
                review_id    TEXT PRIMARY KEY,
                proposal_id  TEXT NOT NULL,
                reviewer     TEXT NOT NULL DEFAULT '',
                verdict      TEXT NOT NULL DEFAULT '',
                comment      TEXT NOT NULL DEFAULT '',
                reviewed_at  REAL NOT NULL,
                FOREIGN KEY (proposal_id) REFERENCES change_proposals(proposal_id)
            );
            CREATE INDEX IF NOT EXISTS idx_cp_status ON change_proposals(status);
            CREATE INDEX IF NOT EXISTS idx_cp_module ON change_proposals(module_id);
            CREATE INDEX IF NOT EXISTS idx_cp_type   ON change_proposals(change_type);
            CREATE INDEX IF NOT EXISTS idx_cp_priority ON change_proposals(priority);
            CREATE INDEX IF NOT EXISTS idx_pr_proposal ON proposal_reviews(proposal_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def create_proposal(self, title: str, change_type: str, module_id: str,
                        description: str = "", proposer: str = "",
                        priority: str = "medium") -> dict:
        """Create a new change proposal in draft status."""
        if change_type not in VALID_CHANGE_TYPES:
            raise ValueError(
                f"Invalid change_type: {change_type!r}. "
                f"Must be one of {VALID_CHANGE_TYPES}"
            )
        if priority not in VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority: {priority!r}. "
                f"Must be one of {VALID_PRIORITIES}"
            )

        proposal = ChangeProposal(
            title=title,
            description=description,
            change_type=change_type,
            module_id=module_id,
            proposer=proposer,
            status="draft",
            priority=priority,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO change_proposals
                    (proposal_id, title, description, change_type, module_id,
                     proposer, status, priority, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                proposal.proposal_id, proposal.title, proposal.description,
                proposal.change_type, proposal.module_id, proposal.proposer,
                proposal.status, proposal.priority,
                proposal.created_at, proposal.updated_at,
                json.dumps(proposal.metadata, default=str),
            ))
            self._conn.commit()

        self._emit("proposal.created", {
            "proposal_id": proposal.proposal_id,
            "title": title,
            "change_type": change_type,
            "module_id": module_id,
            "priority": priority,
        })

        log.info("proposal created: %s (%s, %s, %s)",
                 proposal.proposal_id[:12], title, change_type, priority)
        return self._proposal_to_dict(proposal)

    def get_proposal(self, proposal_id: str) -> dict | None:
        """Retrieve a proposal by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM change_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_proposal_dict(row)

    def list_proposals(self, status: str | None = None,
                       module_id: str | None = None,
                       change_type: str | None = None,
                       limit: int = 100) -> list[dict]:
        """List proposals with optional filters."""
        q = "SELECT * FROM change_proposals WHERE 1=1"
        params: list[Any] = []
        if status:
            q += " AND status = ?"
            params.append(status)
        if module_id:
            q += " AND module_id = ?"
            params.append(module_id)
        if change_type:
            q += " AND change_type = ?"
            params.append(change_type)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_proposal_dict(r) for r in rows]

    def update_proposal(self, proposal_id: str, status: str | None = None,
                        priority: str | None = None) -> dict | None:
        """Update a proposal's status and/or priority."""
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {status!r}. Must be one of {VALID_STATUSES}"
            )
        if priority is not None and priority not in VALID_PRIORITIES:
            raise ValueError(
                f"Invalid priority: {priority!r}. Must be one of {VALID_PRIORITIES}"
            )

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM change_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                log.warning("proposal %s not found for update", proposal_id)
                return None

            old_status = row["status"]
            new_status = status if status is not None else old_status
            new_priority = priority if priority is not None else row["priority"]
            now = time.time()

            self._conn.execute("""
                UPDATE change_proposals
                SET status = ?, priority = ?, updated_at = ?
                WHERE proposal_id = ?
            """, (new_status, new_priority, now, proposal_id))
            self._conn.commit()

        if status is not None and status != old_status:
            self._emit("proposal.status_changed", {
                "proposal_id": proposal_id,
                "old_status": old_status,
                "new_status": new_status,
            })
            log.info("proposal %s status: %s -> %s",
                     proposal_id[:12], old_status, new_status)

        return self.get_proposal(proposal_id)

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def add_review(self, proposal_id: str, reviewer: str, verdict: str,
                   comment: str = "") -> dict:
        """Add a review verdict to a proposal."""
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"Invalid verdict: {verdict!r}. Must be one of {VALID_VERDICTS}"
            )

        with self._lock:
            row = self._conn.execute(
                "SELECT proposal_id FROM change_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Proposal not found: {proposal_id}")

        review = ProposalReview(
            proposal_id=proposal_id,
            reviewer=reviewer,
            verdict=verdict,
            comment=comment,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO proposal_reviews
                    (review_id, proposal_id, reviewer, verdict, comment, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                review.review_id, review.proposal_id, review.reviewer,
                review.verdict, review.comment, review.reviewed_at,
            ))
            self._conn.commit()

        self._emit("proposal.reviewed", {
            "review_id": review.review_id,
            "proposal_id": proposal_id,
            "reviewer": reviewer,
            "verdict": verdict,
        })

        log.info("review added: %s on proposal %s (%s: %s)",
                 review.review_id[:12], proposal_id[:12], reviewer, verdict)
        return {
            "review_id": review.review_id,
            "proposal_id": proposal_id,
            "reviewer": reviewer,
            "verdict": verdict,
            "comment": comment,
            "reviewed_at": review.reviewed_at,
        }

    def list_reviews(self, proposal_id: str) -> list[dict]:
        """List all reviews for a proposal, ordered chronologically."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM proposal_reviews WHERE proposal_id = ? "
                "ORDER BY reviewed_at ASC",
                (proposal_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return counts by status and by change type."""
        with self._lock:
            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM change_proposals "
                "GROUP BY status ORDER BY status"
            ).fetchall()

            type_rows = self._conn.execute(
                "SELECT change_type, COUNT(*) as cnt FROM change_proposals "
                "GROUP BY change_type ORDER BY change_type"
            ).fetchall()

            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM change_proposals"
            ).fetchone()["cnt"]

        by_status = {r["status"]: r["cnt"] for r in status_rows}
        by_type = {r["change_type"]: r["cnt"] for r in type_rows}

        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _proposal_to_dict(proposal: ChangeProposal) -> dict:
        return {
            "proposal_id": proposal.proposal_id,
            "title": proposal.title,
            "description": proposal.description,
            "change_type": proposal.change_type,
            "module_id": proposal.module_id,
            "proposer": proposal.proposer,
            "status": proposal.status,
            "priority": proposal.priority,
            "created_at": proposal.created_at,
            "updated_at": proposal.updated_at,
            "metadata": proposal.metadata,
        }

    @staticmethod
    def _row_to_proposal_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.change_proposal",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: ChangeProposalManager | None = None


def get_change_proposal_manager(event_bus: EventBus | None = None,
                                db_path: str | Path | None = None
                                ) -> ChangeProposalManager:
    global _manager
    if _manager is None:
        _manager = ChangeProposalManager(db_path=db_path, event_bus=event_bus)
    return _manager


def reset_change_proposal_manager() -> None:
    global _manager
    _manager = None
