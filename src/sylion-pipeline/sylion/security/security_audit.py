"""
SYLION Security -- Security Auditor (DEPRECATED)

DEPRECATED 2026-04-24 — use security.audit_trail_aggregator for audit
logging; security findings/scans domain will be consolidated in Faza 2.
Tracks security findings, scans, and remediations.
SQLite-backed storage with thread-safe access.

Tables:
  security_findings    -- identified security issues
  security_scans       -- scan execution records
  remediation_actions  -- remediation tasks for findings

Thread-safe via threading.RLock(). Singleton via get_security_auditor() /
reset_security_auditor().  Emits events via EventBus.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
import warnings
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

warnings.warn(
    "security_audit is deprecated; use audit_trail_aggregator for audit trails",
    DeprecationWarning,
    stacklevel=2,
)

log = logging.getLogger("sylion.security.security_audit")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SEVERITIES: tuple[str, ...] = ("info", "low", "medium", "high", "critical")
VALID_FINDING_STATUSES: tuple[str, ...] = ("open", "acknowledged", "in_progress", "resolved", "dismissed")
VALID_SCAN_STATUSES: tuple[str, ...] = ("running", "completed", "failed", "cancelled")
VALID_REMEDIATION_STATUSES: tuple[str, ...] = ("pending", "in_progress", "completed", "failed")


# ---------------------------------------------------------------------------
# SecurityAuditor
# ---------------------------------------------------------------------------


class SecurityAuditor:
    """Security findings, scans, and remediation tracking.

    SQLite-backed with RLock for thread safety.  Findings are created by
    scans or manual reports, each with severity and status.  Remediations
    track the resolution of findings.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS security_findings (
                finding_id     TEXT PRIMARY KEY,
                title          TEXT NOT NULL,
                severity       TEXT NOT NULL DEFAULT 'medium',
                description    TEXT NOT NULL DEFAULT '',
                module         TEXT NOT NULL DEFAULT '',
                recommendation TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'open',
                scan_id        TEXT NOT NULL DEFAULT '',
                created_at     REAL NOT NULL DEFAULT 0.0,
                updated_at     REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS security_scans (
                scan_id        TEXT PRIMARY KEY,
                scope          TEXT NOT NULL,
                scan_type      TEXT NOT NULL DEFAULT 'full',
                status         TEXT NOT NULL DEFAULT 'running',
                findings_count INTEGER NOT NULL DEFAULT 0,
                started_at     REAL NOT NULL DEFAULT 0.0,
                completed_at   REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS remediation_actions (
                remediation_id TEXT PRIMARY KEY,
                finding_id     TEXT NOT NULL,
                action_type    TEXT NOT NULL DEFAULT '',
                assignee       TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'pending',
                result         TEXT NOT NULL DEFAULT '',
                created_at     REAL NOT NULL DEFAULT 0.0,
                completed_at   REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_findings_severity ON security_findings(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_findings_status ON security_findings(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_findings_module ON security_findings(module)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_scans_status ON security_scans(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_remediation_finding ON remediation_actions(finding_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_remediation_status ON remediation_actions(status)"
        )
        # Audit-trail tables for routes /audit/events, /audit/alerts,
        # /audit/access, /audit/timeline -- distinct from findings/scans
        # and intentionally additive (no migration risk on existing DBs).
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                event_id     TEXT PRIMARY KEY,
                event_type   TEXT NOT NULL DEFAULT '',
                severity     TEXT NOT NULL DEFAULT 'info',
                source       TEXT NOT NULL DEFAULT '',
                description  TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                logged_at    REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS security_alerts (
                alert_id        TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL DEFAULT '',
                severity        TEXT NOT NULL DEFAULT 'medium',
                source          TEXT NOT NULL DEFAULT '',
                acknowledged    INTEGER NOT NULL DEFAULT 0,
                acknowledged_by TEXT NOT NULL DEFAULT '',
                created_at      REAL NOT NULL DEFAULT 0.0,
                acknowledged_at REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS security_access_log (
                access_id   TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL DEFAULT '',
                resource    TEXT NOT NULL DEFAULT '',
                action      TEXT NOT NULL DEFAULT '',
                allowed     INTEGER NOT NULL DEFAULT 0,
                ip_address  TEXT NOT NULL DEFAULT '',
                logged_at   REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_events_type ON security_events(event_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_events_sev ON security_events(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_alerts_sev ON security_alerts(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_alerts_ack ON security_alerts(acknowledged)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sa_access_user ON security_access_log(user_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.security_audit",
            ))

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def create_finding(self, title: str, severity: str = "medium",
                       description: str = "", module: str = "",
                       recommendation: str = "") -> dict:
        """Create a new security finding. Returns finding dict.

        Raises ValueError if severity is invalid.
        """
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. Must be one of {VALID_SEVERITIES}"
            )

        finding_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO security_findings
                    (finding_id, title, severity, description, module,
                     recommendation, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """, (finding_id, title, severity, description, module,
                  recommendation, now, now))
            self._conn.commit()

        self._emit("finding_created", {
            "finding_id": finding_id,
            "severity": severity,
            "module": module,
        })
        log.info("created finding %s (severity=%s)", title, severity)
        return {
            "finding_id": finding_id,
            "title": title,
            "severity": severity,
            "description": description,
            "module": module,
            "recommendation": recommendation,
            "status": "open",
            "scan_id": "",
            "created_at": now,
            "updated_at": now,
        }

    def update_finding(self, finding_id: str, title: str | None = None,
                       severity: str | None = None,
                       description: str | None = None,
                       module: str | None = None,
                       recommendation: str | None = None,
                       status: str | None = None) -> dict | None:
        """Update a finding. Returns updated finding dict or None."""
        if severity is not None and severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. Must be one of {VALID_SEVERITIES}"
            )
        if status is not None and status not in VALID_FINDING_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. Must be one of {VALID_FINDING_STATUSES}"
            )

        sets: list[str] = []
        params: list[Any] = []

        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if severity is not None:
            sets.append("severity = ?")
            params.append(severity)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if module is not None:
            sets.append("module = ?")
            params.append(module)
        if recommendation is not None:
            sets.append("recommendation = ?")
            params.append(recommendation)
        if status is not None:
            sets.append("status = ?")
            params.append(status)

        if not sets:
            return self.get_finding(finding_id)

        sets.append("updated_at = ?")
        params.append(time.time())
        params.append(finding_id)

        with self._lock:
            n = self._conn.execute(
                f"UPDATE security_findings SET {', '.join(sets)} WHERE finding_id = ?",
                params,
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        log.info("updated finding %s", finding_id[:12])
        return self.get_finding(finding_id)

    def get_finding(self, finding_id: str) -> dict | None:
        """Retrieve a finding by finding_id. Returns dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM security_findings WHERE finding_id = ?",
                (finding_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_findings(self, severity: str | None = None,
                      status: str | None = None,
                      module: str | None = None) -> list[dict]:
        """List findings, optionally filtered by severity, status, and/or module."""
        conditions: list[str] = []
        params: list[Any] = []

        if severity is not None:
            conditions.append("severity = ?")
            params.append(severity)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if module is not None:
            conditions.append("module = ?")
            params.append(module)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM security_findings {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Scans
    # ------------------------------------------------------------------

    def start_scan(self, scope: str, scan_type: str = "full") -> dict:
        """Start a new security scan. Returns scan dict."""
        scan_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO security_scans
                    (scan_id, scope, scan_type, status, findings_count,
                     started_at, completed_at)
                VALUES (?, ?, ?, 'running', 0, ?, 0.0)
            """, (scan_id, scope, scan_type, now))
            self._conn.commit()

        self._emit("scan_started", {
            "scan_id": scan_id,
            "scope": scope,
            "scan_type": scan_type,
        })
        log.info("started scan %s (scope=%s)", scan_id[:12], scope)
        return {
            "scan_id": scan_id,
            "scope": scope,
            "scan_type": scan_type,
            "status": "running",
            "findings_count": 0,
            "started_at": now,
            "completed_at": 0.0,
        }

    def complete_scan(self, scan_id: str, findings_count: int = 0) -> dict | None:
        """Complete a running scan. Returns updated scan dict or None.

        Raises ValueError if scan is not in running status.
        """
        scan = self.get_scan(scan_id)
        if scan is None:
            return None
        if scan["status"] != "running":
            raise ValueError(
                f"Scan '{scan_id}' is not running (status={scan['status']})"
            )

        now = time.time()
        with self._lock:
            n = self._conn.execute("""
                UPDATE security_scans
                SET status = 'completed', findings_count = ?, completed_at = ?
                WHERE scan_id = ? AND status = 'running'
            """, (findings_count, now, scan_id)).rowcount
            self._conn.commit()

        if not n:
            return None

        self._emit("scan_completed", {
            "scan_id": scan_id,
            "findings_count": findings_count,
        })
        log.info("completed scan %s with %d findings", scan_id[:12], findings_count)
        return self.get_scan(scan_id)

    def get_scan(self, scan_id: str) -> dict | None:
        """Retrieve a scan by scan_id. Returns dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM security_scans WHERE scan_id = ?",
                (scan_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_scans(self, status: str | None = None) -> list[dict]:
        """List scans, optionally filtered by status."""
        conditions: list[str] = []
        params: list[Any] = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM security_scans {where} ORDER BY started_at DESC",
                params,
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Remediations
    # ------------------------------------------------------------------

    def create_remediation(self, finding_id: str, action_type: str = "",
                           assignee: str = "") -> dict:
        """Create a remediation for a finding. Returns remediation dict.

        Raises ValueError if finding does not exist.
        """
        finding = self.get_finding(finding_id)
        if finding is None:
            raise ValueError(f"Finding '{finding_id}' does not exist")

        remediation_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO remediation_actions
                    (remediation_id, finding_id, action_type, assignee,
                     status, result, created_at, completed_at)
                VALUES (?, ?, ?, ?, 'pending', '', ?, 0.0)
            """, (remediation_id, finding_id, action_type, assignee, now))
            self._conn.commit()

        self._emit("remediation_created", {
            "remediation_id": remediation_id,
            "finding_id": finding_id,
            "assignee": assignee,
        })
        log.info("created remediation for finding %s", finding_id[:12])
        return {
            "remediation_id": remediation_id,
            "finding_id": finding_id,
            "action_type": action_type,
            "assignee": assignee,
            "status": "pending",
            "result": "",
            "created_at": now,
            "completed_at": 0.0,
        }

    def complete_remediation(self, remediation_id: str,
                             result: str = "") -> dict | None:
        """Complete a pending remediation. Returns updated dict or None.

        Raises ValueError if remediation is not in pending status.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM remediation_actions WHERE remediation_id = ?",
                (remediation_id,),
            ).fetchone()
            if not row:
                return None
            remediation = self._row_to_dict(row)

        if remediation["status"] != "pending":
            raise ValueError(
                f"Remediation '{remediation_id}' is not pending "
                f"(status={remediation['status']})"
            )

        now = time.time()
        with self._lock:
            n = self._conn.execute("""
                UPDATE remediation_actions
                SET status = 'completed', result = ?, completed_at = ?
                WHERE remediation_id = ? AND status = 'pending'
            """, (result, now, remediation_id)).rowcount
            self._conn.commit()

        if not n:
            return None

        log.info("completed remediation %s", remediation_id[:12])
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM remediation_actions WHERE remediation_id = ?",
                (remediation_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Audit-trail: events
    # ------------------------------------------------------------------

    def log_event(self, event_type: str, severity: str = "info",
                  source: str = "", description: str | None = None,
                  metadata: dict | None = None) -> dict:
        """Append a security event. Returns event dict.

        Permissive on severity; the route layer accepts free-form severity.
        """
        import json as _json
        event_id = uuid.uuid4().hex
        now = time.time()
        meta_str = _json.dumps(metadata or {}, default=str)
        with self._lock:
            self._conn.execute("""
                INSERT INTO security_events
                    (event_id, event_type, severity, source, description,
                     metadata_json, logged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (event_id, event_type, severity, source,
                  description or "", meta_str, now))
            self._conn.commit()
        self._emit("security.event_logged", {
            "event_id": event_id, "event_type": event_type,
            "severity": severity,
        })
        return {"event_id": event_id, "event_type": event_type,
                "severity": severity, "source": source,
                "description": description or "", "metadata": metadata or {},
                "logged_at": now}

    def get_event(self, event_id: str) -> dict | None:
        import json as _json
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM security_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        if not row:
            return None
        d = self._row_to_dict(row)
        try:
            d["metadata"] = _json.loads(d.pop("metadata_json", "{}") or "{}")
        except (ValueError, TypeError):
            d["metadata"] = {}
            d.pop("metadata_json", None)
        return d

    def get_events(self, event_type: str | None = None,
                   severity: str | None = None,
                   source: str | None = None,
                   limit: int = 100) -> list[dict]:
        import json as _json
        sql = "SELECT * FROM security_events WHERE 1=1"
        params: list[Any] = []
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if source:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY logged_at DESC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict] = []
        for r in rows:
            d = self._row_to_dict(r)
            try:
                d["metadata"] = _json.loads(d.pop("metadata_json", "{}") or "{}")
            except (ValueError, TypeError):
                d["metadata"] = {}
                d.pop("metadata_json", None)
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # Audit-trail: alerts
    # ------------------------------------------------------------------

    def create_alert(self, title: str, description: str = "",
                     severity: str = "medium",
                     source: str | None = None) -> dict:
        alert_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO security_alerts
                    (alert_id, title, description, severity, source,
                     acknowledged, acknowledged_by, created_at, acknowledged_at)
                VALUES (?, ?, ?, ?, ?, 0, '', ?, 0.0)
            """, (alert_id, title, description, severity,
                  source or "", now))
            self._conn.commit()
        self._emit("security.alert_created",
                   {"alert_id": alert_id, "severity": severity})
        return {"alert_id": alert_id, "title": title,
                "description": description, "severity": severity,
                "source": source or "", "acknowledged": False,
                "acknowledged_by": "", "created_at": now,
                "acknowledged_at": 0.0}

    def get_alerts(self, severity: str | None = None,
                   acknowledged: bool | None = None) -> list[dict]:
        sql = "SELECT * FROM security_alerts WHERE 1=1"
        params: list[Any] = []
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if acknowledged is not None:
            sql += " AND acknowledged = ?"
            params.append(1 if acknowledged else 0)
        sql += " ORDER BY created_at DESC LIMIT 500"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict] = []
        for r in rows:
            d = self._row_to_dict(r)
            d["acknowledged"] = bool(d.get("acknowledged", 0))
            out.append(d)
        return out

    def acknowledge_alert(self, alert_id: str,
                          acknowledged_by: str = "") -> dict | None:
        now = time.time()
        with self._lock:
            n = self._conn.execute(
                "UPDATE security_alerts SET acknowledged = 1, "
                "acknowledged_by = ?, acknowledged_at = ? "
                "WHERE alert_id = ? AND acknowledged = 0",
                (acknowledged_by, now, alert_id),
            ).rowcount
            self._conn.commit()
            if not n:
                # Already acknowledged or unknown -- return current state
                row = self._conn.execute(
                    "SELECT * FROM security_alerts WHERE alert_id = ?",
                    (alert_id,),
                ).fetchone()
                if not row:
                    return None
                d = self._row_to_dict(row)
                d["acknowledged"] = bool(d.get("acknowledged", 0))
                return d
            row = self._conn.execute(
                "SELECT * FROM security_alerts WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
        d = self._row_to_dict(row)
        d["acknowledged"] = bool(d.get("acknowledged", 0))
        self._emit("security.alert_acknowledged",
                   {"alert_id": alert_id, "by": acknowledged_by})
        return d

    # ------------------------------------------------------------------
    # Audit-trail: access log
    # ------------------------------------------------------------------

    def log_access(self, user_id: str, resource: str, action: str,
                   allowed: bool = True,
                   ip_address: str | None = None) -> dict:
        access_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO security_access_log
                    (access_id, user_id, resource, action, allowed,
                     ip_address, logged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (access_id, user_id, resource, action,
                  1 if allowed else 0, ip_address or "", now))
            self._conn.commit()
        self._emit("security.access_logged",
                   {"user_id": user_id, "resource": resource,
                    "action": action, "allowed": bool(allowed)})
        return {"access_id": access_id, "user_id": user_id,
                "resource": resource, "action": action,
                "allowed": bool(allowed),
                "ip_address": ip_address or "", "logged_at": now}

    def get_access_log(self, user_id: str | None = None,
                       resource: str | None = None,
                       limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM security_access_log WHERE 1=1"
        params: list[Any] = []
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if resource:
            sql += " AND resource = ?"
            params.append(resource)
        sql += " ORDER BY logged_at DESC LIMIT ?"
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict] = []
        for r in rows:
            d = self._row_to_dict(r)
            d["allowed"] = bool(d.get("allowed", 0))
            out.append(d)
        return out

    # ------------------------------------------------------------------
    # Audit-trail: timeline (merged event/alert/access stream)
    # ------------------------------------------------------------------

    def get_timeline(self, limit: int = 50) -> list[dict]:
        """Return a merged time-sorted list of recent events+alerts+access."""
        out: list[dict] = []
        with self._lock:
            for r in self._conn.execute(
                "SELECT event_id as id, event_type as kind, severity, "
                "logged_at as ts, description as text "
                "FROM security_events ORDER BY logged_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall():
                d = dict(r)
                d["category"] = "event"
                out.append(d)
            for r in self._conn.execute(
                "SELECT alert_id as id, title as kind, severity, "
                "created_at as ts, description as text "
                "FROM security_alerts ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall():
                d = dict(r)
                d["category"] = "alert"
                out.append(d)
            for r in self._conn.execute(
                "SELECT access_id as id, action as kind, "
                "CASE WHEN allowed = 1 THEN 'info' ELSE 'high' END as severity, "
                "logged_at as ts, resource as text "
                "FROM security_access_log ORDER BY logged_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall():
                d = dict(r)
                d["category"] = "access"
                out.append(d)
        out.sort(key=lambda x: x.get("ts", 0.0), reverse=True)
        return out[:int(limit)]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_security_stats(self) -> dict:
        """Return aggregate statistics about findings, scans, and remediations."""
        with self._lock:
            total_findings = self._conn.execute(
                "SELECT COUNT(*) FROM security_findings"
            ).fetchone()[0]

            sev_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM security_findings GROUP BY severity"
            ).fetchall()
            findings_by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM security_findings GROUP BY status"
            ).fetchall()
            findings_by_status = {r["status"]: r["cnt"] for r in status_rows}

            total_scans = self._conn.execute(
                "SELECT COUNT(*) FROM security_scans"
            ).fetchone()[0]

            total_remediations = self._conn.execute(
                "SELECT COUNT(*) FROM remediation_actions"
            ).fetchone()[0]

            rem_status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM remediation_actions GROUP BY status"
            ).fetchall()
            remediations_by_status = {r["status"]: r["cnt"] for r in rem_status_rows}

        return {
            "total_findings": total_findings,
            "findings_by_severity": findings_by_severity,
            "findings_by_status": findings_by_status,
            "total_scans": total_scans,
            "total_remediations": total_remediations,
            "remediations_by_status": remediations_by_status,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: SecurityAuditor | None = None


def get_security_auditor(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> SecurityAuditor:
    """Get or create the global SecurityAuditor singleton."""
    global _manager
    if _manager is None:
        _manager = SecurityAuditor(db_path, event_bus)
    return _manager


def reset_security_auditor(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> SecurityAuditor:
    """Reset the global SecurityAuditor singleton (for testing)."""
    global _manager
    _manager = SecurityAuditor(db_path, event_bus)
    return _manager


# Backward-compatible alias (was get_security_audit in older worktrees)
get_security_audit = get_security_auditor
