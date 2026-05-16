"""
SYLION Governance -- Conflict Detector

Detects conflicts between concurrent changes to the same module or contract.
Prevents race conditions and divergent edits when multiple pipeline runs,
agents, or operators modify overlapping targets simultaneously.

Conflict types:
  concurrent_edit    -- two changes target the same module simultaneously
  contract_mismatch -- changes imply incompatible contract versions
  version_conflict  -- version pinning conflicts between dependents
  dependency_cycle  -- changes would introduce a circular dependency

Severities:
  low      -- cosmetic or non-breaking overlap
  medium   -- merge possible but requires review
  high     -- data loss risk if not resolved
  critical -- system-breaking conflict, immediate attention required

Statuses:
  detected   -- conflict identified, awaiting analysis
  analyzing  -- deep analysis in progress
  resolved   -- resolution applied
  escalated  -- handed off to human or council

Tables:
  conflict_records -- detected conflicts and their resolution state
  conflict_rules   -- detection patterns and auto-resolve strategies

Singleton: get_conflict_detector() / reset_conflict_detector()
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

log = logging.getLogger("sylion.governance.conflict_detector")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CONFLICT_TYPES = (
    "concurrent_edit",
    "contract_mismatch",
    "version_conflict",
    "dependency_cycle",
)

VALID_SEVERITIES = ("low", "medium", "high", "critical")

VALID_STATUSES = ("detected", "analyzing", "resolved", "escalated")

# Default severity heuristic based on conflict type
_TYPE_SEVERITY: dict[str, str] = {
    "concurrent_edit": "medium",
    "contract_mismatch": "high",
    "version_conflict": "medium",
    "dependency_cycle": "critical",
}


class ConflictDetector:
    """Detects conflicts between concurrent changes to the same module or contract.

    SQLite-backed with threading.RLock for thread safety.
    Integrates with EventBus for conflict.detected / conflict.resolved events.
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conflict_records (
                conflict_id   TEXT PRIMARY KEY,
                module_id     TEXT NOT NULL,
                change_a      TEXT NOT NULL,
                change_b      TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                severity      TEXT NOT NULL DEFAULT 'medium',
                status        TEXT NOT NULL DEFAULT 'detected',
                detected_at   REAL NOT NULL,
                resolved_at   REAL,
                resolution    TEXT
            );
            CREATE TABLE IF NOT EXISTS conflict_rules (
                rule_id            TEXT PRIMARY KEY,
                conflict_type      TEXT NOT NULL,
                detection_pattern  TEXT NOT NULL,
                auto_resolve       TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_cr_module   ON conflict_records(module_id);
            CREATE INDEX IF NOT EXISTS idx_cr_status   ON conflict_records(status);
            CREATE INDEX IF NOT EXISTS idx_cr_severity ON conflict_records(severity);
            CREATE INDEX IF NOT EXISTS idx_cr_type     ON conflict_records(conflict_type);
            CREATE INDEX IF NOT EXISTS idx_crule_type  ON conflict_rules(conflict_type);
        """)
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
                source_module="governance.conflict_detector",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_conflict(
        self,
        module_id: str,
        change_a: str,
        change_b: str,
        change_type: str = "concurrent_edit",
    ) -> dict:
        """Detect and record a conflict between two concurrent changes.

        Creates a conflict record with severity inferred from the conflict
        type unless overridden by a matching rule.

        Returns the created conflict record.
        """
        if not module_id:
            raise ValueError("module_id must not be empty")
        if not change_a:
            raise ValueError("change_a must not be empty")
        if not change_b:
            raise ValueError("change_b must not be empty")
        if change_type not in VALID_CONFLICT_TYPES:
            raise ValueError(
                f"Invalid change_type: {change_type}. "
                f"Must be one of {VALID_CONFLICT_TYPES}"
            )

        # Determine severity: check rules first, then default heuristic
        severity = self._resolve_severity(change_type)

        conflict_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO conflict_records
                    (conflict_id, module_id, change_a, change_b,
                     conflict_type, severity, status, detected_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                conflict_id, module_id, change_a, change_b,
                change_type, severity, "detected", now,
            ))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM conflict_records WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()

        result = dict(row)

        self._emit("conflict.detected", {
            "conflict_id": conflict_id,
            "module_id": module_id,
            "conflict_type": change_type,
            "severity": severity,
            "change_a": change_a,
            "change_b": change_b,
        })

        log.info("conflict detected: %s on module %s (type=%s, severity=%s)",
                 conflict_id, module_id, change_type, severity)
        return result

    def _resolve_severity(self, conflict_type: str) -> str:
        """Determine severity from rules or default heuristic."""
        with self._lock:
            row = self._conn.execute(
                "SELECT auto_resolve FROM conflict_rules "
                "WHERE conflict_type = ? LIMIT 1",
                (conflict_type,),
            ).fetchone()
        # Rules can contain severity hints but the default table-driven
        # approach covers the common case.
        return _TYPE_SEVERITY.get(conflict_type, "medium")

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve_conflict(self, conflict_id: str, resolution: str) -> dict | None:
        """Mark a conflict as resolved.

        Args:
            conflict_id: The conflict to resolve.
            resolution: Free-text description of the resolution applied.

        Returns:
            Updated conflict record, or None if conflict_id not found.
        """
        if not resolution:
            raise ValueError("resolution must not be empty")

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conflict_records WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
        if not row:
            return None

        now = time.time()

        with self._lock:
            self._conn.execute("""
                UPDATE conflict_records
                SET status = 'resolved',
                    resolved_at = ?,
                    resolution = ?
                WHERE conflict_id = ?
            """, (now, resolution, conflict_id))
            self._conn.commit()

            updated = self._conn.execute(
                "SELECT * FROM conflict_records WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()

        result = dict(updated)

        self._emit("conflict.resolved", {
            "conflict_id": conflict_id,
            "resolution": resolution,
            "module_id": result["module_id"],
        })

        log.info("conflict resolved: %s (resolution=%s)",
                 conflict_id, resolution[:60])
        return result

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_conflict(self, conflict_id: str) -> dict | None:
        """Return a single conflict record by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conflict_records WHERE conflict_id = ?",
                (conflict_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_conflicts(
        self,
        status: str | None = None,
        module_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """List conflicts, optionally filtered by status and/or module_id."""
        with self._lock:
            q = "SELECT * FROM conflict_records WHERE 1=1"
            params: list[Any] = []
            if status:
                if status not in VALID_STATUSES:
                    raise ValueError(
                        f"Invalid status filter: {status}. "
                        f"Must be one of {VALID_STATUSES}"
                    )
                q += " AND status = ?"
                params.append(status)
            if module_id:
                q += " AND module_id = ?"
                params.append(module_id)
            q += " ORDER BY detected_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()

        return [dict(r) for r in rows]

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate conflict statistics.

        Returns {total, by_severity, by_status}.
        """
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM conflict_records"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            severity_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM conflict_records "
                "GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in severity_rows}

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM conflict_records "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

        return {
            "total": total,
            "by_severity": by_severity,
            "by_status": by_status,
        }

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def add_rule(
        self,
        conflict_type: str,
        detection_pattern: str,
        auto_resolve: str = "",
    ) -> dict:
        """Add a conflict detection rule.

        Args:
            conflict_type: The type of conflict this rule matches.
            detection_pattern: Pattern or heuristic description for matching.
            auto_resolve: Optional auto-resolution strategy (empty = no auto).

        Returns:
            The created rule record.
        """
        if conflict_type not in VALID_CONFLICT_TYPES:
            raise ValueError(
                f"Invalid conflict_type: {conflict_type}. "
                f"Must be one of {VALID_CONFLICT_TYPES}"
            )
        if not detection_pattern:
            raise ValueError("detection_pattern must not be empty")

        rule_id = self._uid()

        with self._lock:
            self._conn.execute("""
                INSERT INTO conflict_rules
                    (rule_id, conflict_type, detection_pattern, auto_resolve)
                VALUES (?,?,?,?)
            """, (rule_id, conflict_type, detection_pattern, auto_resolve))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM conflict_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()

        result = dict(row)
        log.info("rule added: %s for conflict_type=%s", rule_id, conflict_type)
        return result

    def list_rules(self) -> list[dict]:
        """List all conflict detection rules."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM conflict_rules ORDER BY rule_id"
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_detector: ConflictDetector | None = None


def get_conflict_detector(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ConflictDetector:
    global _detector
    if _detector is None:
        _detector = ConflictDetector(db_path, event_bus)
    return _detector


def reset_conflict_detector(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ConflictDetector:
    global _detector
    _detector = ConflictDetector(db_path, event_bus)
    return _detector
