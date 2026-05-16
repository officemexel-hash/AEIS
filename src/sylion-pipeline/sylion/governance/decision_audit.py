"""
SYLION Governance -- Decision Audit Trail

Central audit trail that captures ALL decision-related events: snapshots,
changes, cascades, conflicts, compliance checks, gate evaluations.  Provides
a single queryable source of truth for "what happened and why".

Event types:
  snapshot_captured    -- a decision snapshot was taken
  decision_changed     -- an existing decision was modified
  cascade_triggered    -- a cascading impact was detected
  conflict_detected    -- a conflict between decisions was found
  conflict_resolved    -- a conflict was resolved
  compliance_checked   -- compliance rules were evaluated
  gate_evaluated       -- a decision gate was evaluated
  compliance_report    -- a compliance report was generated

Tables:
  decision_audit_log   -- append-only audit trail with full context

Singleton: get_decision_audit() / reset_decision_audit()
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

log = logging.getLogger("sylion.governance.decision_audit")


class DecisionAudit:
    """Queryable audit trail for all decision-related events."""

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
            CREATE TABLE IF NOT EXISTS decision_audit_log (
                audit_id        TEXT PRIMARY KEY,
                event_type      TEXT NOT NULL,
                decision_id     TEXT,
                snapshot_id     TEXT,

                actor           TEXT DEFAULT 'system',
                description     TEXT NOT NULL,

                before_state    TEXT,
                after_state     TEXT,

                related_ids     TEXT,
                metadata        TEXT,

                severity        TEXT DEFAULT 'info',
                source_module   TEXT,

                created_at      REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_event_type "
            "ON decision_audit_log(event_type)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_decision_id "
            "ON decision_audit_log(decision_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_severity "
            "ON decision_audit_log(severity)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_created_at "
            "ON decision_audit_log(created_at)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_source_module "
            "ON decision_audit_log(source_module)")
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
                source_module="decision_audit",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _json_dumps(value: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value, sort_keys=True, default=str)

    @staticmethod
    def _json_loads(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        """Parse an audit row, decoding JSON fields."""
        d = dict(row)
        for key in ("before_state", "after_state", "related_ids", "metadata"):
            if d.get(key) is not None:
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_event(
        self,
        event_type: str,
        description: str,
        decision_id: str | None = None,
        snapshot_id: str | None = None,
        actor: str = "system",
        before_state: dict | None = None,
        after_state: dict | None = None,
        related_ids: dict | None = None,
        metadata: dict | None = None,
        severity: str = "info",
        source_module: str | None = None,
    ) -> dict:
        """Create an audit entry and return it.

        Parameters
        ----------
        event_type : str
            One of the recognized event type constants.
        description : str
            Human-readable description of what happened.
        decision_id : str, optional
            Related decision identifier.
        snapshot_id : str, optional
            Related snapshot identifier.
        actor : str
            Who or what triggered this event (default ``'system'``).
        before_state : dict, optional
            JSON-serializable state *before* the event.
        after_state : dict, optional
            JSON-serializable state *after* the event.
        related_ids : dict, optional
            Related identifiers (conflict_id, compliance_check_id, etc.).
        metadata : dict, optional
            Additional context.
        severity : str
            ``'info'``, ``'warning'``, or ``'critical'``.
        source_module : str, optional
            Which module emitted this event.

        Returns
        -------
        dict
            The created audit record with all fields parsed.
        """
        audit_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO decision_audit_log
                (audit_id, event_type, decision_id, snapshot_id,
                 actor, description,
                 before_state, after_state,
                 related_ids, metadata,
                 severity, source_module,
                 created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                audit_id, event_type, decision_id, snapshot_id,
                actor, description,
                self._json_dumps(before_state),
                self._json_dumps(after_state),
                self._json_dumps(related_ids),
                self._json_dumps(metadata),
                severity, source_module,
                now,
            ))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM decision_audit_log WHERE audit_id = ?",
                (audit_id,),
            ).fetchone()

        result = self._parse_row(row) if row else {"audit_id": audit_id}

        self._emit("decision.audit.logged", {
            "audit_id": audit_id,
            "event_type": event_type,
            "decision_id": decision_id,
            "severity": severity,
        })

        log.info("audit %s: %s [%s] %s",
                 audit_id, event_type, severity,
                 description[:80] if description else "")
        return result

    def get_audit_entry(self, audit_id: str) -> dict | None:
        """Return a single audit entry by ID, with JSON fields parsed."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_audit_log WHERE audit_id = ?",
                (audit_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_row(row)

    def get_audit_log(
        self,
        decision_id: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        source_module: str | None = None,
        from_time: float | None = None,
        to_time: float | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Filtered query of audit entries, ordered newest-first."""
        with self._lock:
            q = "SELECT * FROM decision_audit_log WHERE 1=1"
            params: list[Any] = []
            if decision_id:
                q += " AND decision_id = ?"
                params.append(decision_id)
            if event_type:
                q += " AND event_type = ?"
                params.append(event_type)
            if severity:
                q += " AND severity = ?"
                params.append(severity)
            if source_module:
                q += " AND source_module = ?"
                params.append(source_module)
            if from_time is not None:
                q += " AND created_at >= ?"
                params.append(from_time)
            if to_time is not None:
                q += " AND created_at <= ?"
                params.append(to_time)
            q += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()

        return [self._parse_row(r) for r in rows]

    def get_audit_timeline(self, decision_id: str) -> list[dict]:
        """All events for a decision, chronological (oldest-first)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM decision_audit_log "
                "WHERE decision_id = ? "
                "ORDER BY created_at ASC",
                (decision_id,),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    def get_audit_stats(self) -> dict[str, Any]:
        """Aggregate statistics: {total, by_event_type, by_severity, by_source_module}."""
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_audit_log"
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            type_rows = self._conn.execute(
                "SELECT event_type, COUNT(*) as cnt "
                "FROM decision_audit_log GROUP BY event_type"
            ).fetchall()
            by_event_type = {r["event_type"]: r["cnt"] for r in type_rows}

            sev_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt "
                "FROM decision_audit_log GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

            mod_rows = self._conn.execute(
                "SELECT source_module, COUNT(*) as cnt "
                "FROM decision_audit_log GROUP BY source_module"
            ).fetchall()
            by_source_module = {r["source_module"]: r["cnt"] for r in mod_rows}

        return {
            "total": total,
            "by_event_type": by_event_type,
            "by_severity": by_severity,
            "by_source_module": by_source_module,
        }

    def export_audit_log(
        self,
        format: str = "json",
        from_time: float | None = None,
        to_time: float | None = None,
    ) -> str:
        """Export matching entries as a JSON string.

        Parameters
        ----------
        format : str
            Only ``'json'`` is currently supported.
        from_time : float, optional
            Unix timestamp lower bound (inclusive).
        to_time : float, optional
            Unix timestamp upper bound (inclusive).

        Returns
        -------
        str
            JSON-encoded list of audit entries.
        """
        entries = self.get_audit_log(
            from_time=from_time,
            to_time=to_time,
            limit=1_000_000,
        )
        return json.dumps(entries, indent=2, default=str)

    def purge_old_entries(self, older_than_days: int = 365) -> int:
        """Remove entries older than *older_than_days* days.

        Default retention is 1 year for compliance purposes.

        Returns
        -------
        int
            Number of rows deleted.
        """
        cutoff = time.time() - (older_than_days * 86400)
        with self._lock:
            count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM decision_audit_log "
                "WHERE created_at < ?",
                (cutoff,),
            ).fetchone()
            deleted = count["cnt"] if count else 0

            self._conn.execute(
                "DELETE FROM decision_audit_log WHERE created_at < ?",
                (cutoff,),
            )
            self._conn.commit()

        if deleted:
            self._emit("decision.audit.purged", {
                "deleted_count": deleted,
                "older_than_days": older_than_days,
            })
            log.info("purged %d audit entries older than %d days",
                     deleted, older_than_days)

        return deleted


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_audit: DecisionAudit | None = None


def get_decision_audit(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> DecisionAudit:
    global _audit
    if _audit is None:
        _audit = DecisionAudit(db_path, event_bus)
    return _audit


def reset_decision_audit(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> DecisionAudit:
    global _audit
    _audit = DecisionAudit(db_path, event_bus)
    return _audit
