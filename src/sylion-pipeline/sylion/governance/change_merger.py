"""
SYLION Governance -- Change Merger

Handles merge conflict detection and resolution between branches.
Tracks merge requests, detects conflicts, and supports manual and
automatic resolution workflows.

Schema:
  merge_requests   - merge request metadata and status
  merge_conflicts  - detected conflicts within a merge request
  merge_resolutions - resolutions applied to conflicts

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

log = logging.getLogger("sylion.governance.change_merger")

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_MERGE_STATUSES = (
    "pending", "conflicts_detected", "in_progress",
    "merged", "failed", "aborted",
)

VALID_CONFLICT_STATUSES = ("unresolved", "resolving", "resolved", "skipped")

VALID_RESOLUTION_TYPES = ("manual", "auto_ours", "auto_theirs", "custom")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MergeRequest:
    """A request to merge one branch into another."""
    merge_id: str = ""
    source_branch: str = ""
    target_branch: str = ""
    description: str = ""
    status: str = "pending"
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.merge_id:
            self.merge_id = uuid.uuid4().hex
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class MergeConflict:
    """A detected conflict within a merge request."""
    conflict_id: str = ""
    merge_id: str = ""
    file_path: str = ""
    conflict_type: str = ""
    description: str = ""
    status: str = "unresolved"
    detected_at: float = 0.0

    def __post_init__(self):
        if not self.conflict_id:
            self.conflict_id = uuid.uuid4().hex
        if not self.detected_at:
            self.detected_at = time.time()


@dataclass
class MergeResolution:
    """A resolution applied to a merge conflict."""
    resolution_id: str = ""
    conflict_id: str = ""
    merge_id: str = ""
    resolution_type: str = "manual"
    resolution_json: str = "{}"
    resolver: str = ""
    resolved_at: float = 0.0

    def __post_init__(self):
        if not self.resolution_id:
            self.resolution_id = uuid.uuid4().hex
        if not self.resolved_at:
            self.resolved_at = time.time()


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class ChangeMerger:
    """Handles merge conflict detection and resolution.

    SQLite-backed, thread-safe. Integrates with EventBus for merge
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
            CREATE TABLE IF NOT EXISTS merge_requests (
                merge_id       TEXT PRIMARY KEY,
                source_branch  TEXT NOT NULL,
                target_branch  TEXT NOT NULL,
                description    TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'pending',
                created_at     REAL NOT NULL,
                updated_at     REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS merge_conflicts (
                conflict_id   TEXT PRIMARY KEY,
                merge_id      TEXT NOT NULL,
                file_path     TEXT NOT NULL DEFAULT '',
                conflict_type TEXT NOT NULL DEFAULT '',
                description   TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'unresolved',
                detected_at   REAL NOT NULL,
                FOREIGN KEY (merge_id) REFERENCES merge_requests(merge_id)
            );
            CREATE TABLE IF NOT EXISTS merge_resolutions (
                resolution_id   TEXT PRIMARY KEY,
                conflict_id     TEXT NOT NULL,
                merge_id        TEXT NOT NULL,
                resolution_type TEXT NOT NULL DEFAULT 'manual',
                resolution_json TEXT NOT NULL DEFAULT '{}',
                resolver        TEXT NOT NULL DEFAULT '',
                resolved_at     REAL NOT NULL,
                FOREIGN KEY (conflict_id) REFERENCES merge_conflicts(conflict_id),
                FOREIGN KEY (merge_id) REFERENCES merge_requests(merge_id)
            );
            CREATE INDEX IF NOT EXISTS idx_mr_status  ON merge_requests(status);
            CREATE INDEX IF NOT EXISTS idx_mr_source  ON merge_requests(source_branch);
            CREATE INDEX IF NOT EXISTS idx_mc_merge    ON merge_conflicts(merge_id);
            CREATE INDEX IF NOT EXISTS idx_mc_status   ON merge_conflicts(status);
            CREATE INDEX IF NOT EXISTS idx_mres_merge  ON merge_resolutions(merge_id);
            CREATE INDEX IF NOT EXISTS idx_mres_conflict ON merge_resolutions(conflict_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Merge requests
    # ------------------------------------------------------------------

    def create_merge_request(self, source_branch: str, target_branch: str,
                             description: str = "") -> dict:
        """Create a new merge request."""
        mr = MergeRequest(
            source_branch=source_branch,
            target_branch=target_branch,
            description=description,
        )
        with self._lock:
            self._conn.execute("""
                INSERT INTO merge_requests
                    (merge_id, source_branch, target_branch, description,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                mr.merge_id, mr.source_branch, mr.target_branch,
                mr.description, mr.status, mr.created_at, mr.updated_at,
            ))
            self._conn.commit()

        self._emit("merge_requested", {
            "merge_id": mr.merge_id,
            "source_branch": source_branch,
            "target_branch": target_branch,
        })
        log.info("merge request created: %s (%s -> %s)",
                 mr.merge_id[:12], source_branch, target_branch)
        return dict(mr.__dict__)

    def get_merge_request(self, merge_id: str) -> dict | None:
        """Retrieve a merge request by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM merge_requests WHERE merge_id = ?",
                (merge_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_merge_requests(self, status: str | None = None) -> list[dict]:
        """List merge requests, optionally filtered by status."""
        q = "SELECT * FROM merge_requests WHERE 1=1"
        params: list[Any] = []
        if status:
            if status not in VALID_MERGE_STATUSES:
                raise ValueError(
                    f"Invalid status: {status!r}. "
                    f"Must be one of {VALID_MERGE_STATUSES}"
                )
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC"

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def detect_conflicts(self, merge_id: str) -> list[dict]:
        """Detect conflicts for a merge request.

        This is a simplified simulation that marks the merge as having
        conflicts for demonstration purposes. In production this would
        integrate with a VCS.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM merge_requests WHERE merge_id = ?",
                (merge_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Merge request not found: {merge_id}")

        # Check for existing unresolved conflicts
        with self._lock:
            existing = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM merge_conflicts "
                "WHERE merge_id = ? AND status = 'unresolved'",
                (merge_id,),
            ).fetchone()["cnt"]

        if existing > 0:
            with self._lock:
                conflicts = self._conn.execute(
                    "SELECT * FROM merge_conflicts WHERE merge_id = ? "
                    "ORDER BY detected_at ASC",
                    (merge_id,),
                ).fetchall()
            return [dict(c) for c in conflicts]

        # Simulate conflict detection: create a sample conflict
        conflict = MergeConflict(
            merge_id=merge_id,
            file_path=f"{row['target_branch']}/config.json",
            conflict_type="content",
            description=f"Content conflict in {row['target_branch']}/config.json",
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO merge_conflicts
                    (conflict_id, merge_id, file_path, conflict_type,
                     description, status, detected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                conflict.conflict_id, conflict.merge_id,
                conflict.file_path, conflict.conflict_type,
                conflict.description, conflict.status,
                conflict.detected_at,
            ))
            self._conn.execute(
                "UPDATE merge_requests SET status = ?, updated_at = ? "
                "WHERE merge_id = ?",
                ("conflicts_detected", time.time(), merge_id),
            )
            self._conn.commit()

        self._emit("conflict_detected", {
            "conflict_id": conflict.conflict_id,
            "merge_id": merge_id,
            "file_path": conflict.file_path,
        })
        log.info("conflict detected: %s in merge %s",
                 conflict.file_path, merge_id[:12])
        return [dict(conflict.__dict__)]

    def get_conflicts(self, merge_id: str,
                      status: str | None = None) -> list[dict]:
        """List conflicts for a merge request."""
        q = "SELECT * FROM merge_conflicts WHERE merge_id = ?"
        params: list[Any] = [merge_id]
        if status:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY detected_at ASC"

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------

    def resolve_conflict(self, conflict_id: str,
                         resolution_type: str = "manual",
                         resolution_json: str = "{}",
                         resolver: str = "") -> dict:
        """Resolve a conflict with a specific resolution."""
        if resolution_type not in VALID_RESOLUTION_TYPES:
            raise ValueError(
                f"Invalid resolution_type: {resolution_type!r}. "
                f"Must be one of {VALID_RESOLUTION_TYPES}"
            )

        with self._lock:
            conflict_row = self._conn.execute(
                "SELECT * FROM merge_conflicts WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
            if not conflict_row:
                raise ValueError(f"Conflict not found: {conflict_id}")

            merge_id = conflict_row["merge_id"]

        resolution = MergeResolution(
            conflict_id=conflict_id,
            merge_id=merge_id,
            resolution_type=resolution_type,
            resolution_json=resolution_json,
            resolver=resolver,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO merge_resolutions
                    (resolution_id, conflict_id, merge_id, resolution_type,
                     resolution_json, resolver, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                resolution.resolution_id, resolution.conflict_id,
                resolution.merge_id, resolution.resolution_type,
                resolution.resolution_json, resolution.resolver,
                resolution.resolved_at,
            ))
            self._conn.execute(
                "UPDATE merge_conflicts SET status = ? WHERE conflict_id = ?",
                ("resolved", conflict_id),
            )
            self._conn.commit()

        self._emit("conflict_resolved", {
            "conflict_id": conflict_id,
            "merge_id": merge_id,
            "resolution_type": resolution_type,
            "resolver": resolver,
        })
        log.info("conflict resolved: %s via %s by %s",
                 conflict_id[:12], resolution_type, resolver)
        return {
            "resolution_id": resolution.resolution_id,
            "conflict_id": conflict_id,
            "merge_id": merge_id,
            "resolution_type": resolution_type,
            "resolution_json": resolution_json,
            "resolver": resolver,
            "resolved_at": resolution.resolved_at,
        }

    def auto_merge(self, merge_id: str) -> dict:
        """Attempt automatic merge by resolving all conflicts with auto_theirs."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM merge_requests WHERE merge_id = ?",
                (merge_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Merge request not found: {merge_id}")

            conflicts = self._conn.execute(
                "SELECT * FROM merge_conflicts WHERE merge_id = ? "
                "AND status = 'unresolved'",
                (merge_id,),
            ).fetchall()

        for conflict in conflicts:
            self.resolve_conflict(
                conflict["conflict_id"],
                resolution_type="auto_theirs",
                resolver="auto_merge",
            )

        with self._lock:
            self._conn.execute(
                "UPDATE merge_requests SET status = ?, updated_at = ? "
                "WHERE merge_id = ?",
                ("merged", time.time(), merge_id),
            )
            self._conn.commit()

        self._emit("merge_completed", {
            "merge_id": merge_id,
            "status": "merged",
            "conflicts_resolved": len(conflicts),
        })
        log.info("auto merge completed: %s (%d conflicts resolved)",
                 merge_id[:12], len(conflicts))
        return self.get_merge_request(merge_id) or {}

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_merger_stats(self) -> dict[str, Any]:
        """Return merge request and conflict statistics."""
        with self._lock:
            total_merges = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM merge_requests"
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM merge_requests "
                "GROUP BY status ORDER BY status"
            ).fetchall()

            total_conflicts = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM merge_conflicts"
            ).fetchone()["cnt"]

            conflict_status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM merge_conflicts "
                "GROUP BY status ORDER BY status"
            ).fetchall()

            total_resolutions = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM merge_resolutions"
            ).fetchone()["cnt"]

            resolution_type_rows = self._conn.execute(
                "SELECT resolution_type, COUNT(*) as cnt FROM merge_resolutions "
                "GROUP BY resolution_type ORDER BY resolution_type"
            ).fetchall()

        by_merge_status = {r["status"]: r["cnt"] for r in status_rows}
        by_conflict_status = {r["status"]: r["cnt"] for r in conflict_status_rows}
        by_resolution_type = {r["resolution_type"]: r["cnt"] for r in resolution_type_rows}

        return {
            "total_merges": total_merges,
            "merges_by_status": by_merge_status,
            "total_conflicts": total_conflicts,
            "conflicts_by_status": by_conflict_status,
            "total_resolutions": total_resolutions,
            "resolutions_by_type": by_resolution_type,
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
                source_module="governance.change_merger",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_merger: ChangeMerger | None = None


def get_change_merger(event_bus: EventBus | None = None,
                      db_path: str | Path | None = None
                      ) -> ChangeMerger:
    global _merger
    if _merger is None:
        _merger = ChangeMerger(db_path=db_path, event_bus=event_bus)
    return _merger


def reset_change_merger() -> None:
    global _merger
    _merger = None
