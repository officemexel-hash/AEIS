"""
SYLION Monitoring -- Self-Healing Engine

Manages automated incident response rules.  Incidents are reported by
monitoring sources, evaluated against healing rules (condition + action),
and may be auto-resolved without human intervention.

Rules have priority ordering and configurable severity levels.
All incidents and healing actions are persisted in SQLite for audit.

SQLite-backed with WAL mode.  Thread-safe via threading.RLock().
Singleton via get_self_healing() / reset_self_healing().
Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.monitoring.self_healing")

# ---------------------------------------------------------------------------
# Valid values
# ---------------------------------------------------------------------------

VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES = {"open", "investigating", "resolved", "auto_resolved"}
VALID_ACTIONS = {"restart", "throttle", "fallback", "alert", "disable"}


# ---------------------------------------------------------------------------
# SelfHealingEngine
# ---------------------------------------------------------------------------

class SelfHealingEngine:
    """Rule-based self-healing engine backed by SQLite.

    Manages healing rules, incident reporting, and auto-resolution.
    Thread-safe via RLock.  Singleton-capable.
    EventBus-integrated.
    """

    def __init__(self, db_path: str = ":memory:",
                 event_bus: EventBus | None = None):
        self._db_path = db_path
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
            CREATE TABLE IF NOT EXISTS healing_rules (
                rule_id       TEXT PRIMARY KEY,
                name          TEXT    NOT NULL,
                condition_json TEXT   NOT NULL DEFAULT '{}',
                action_json   TEXT    NOT NULL DEFAULT '{}',
                priority      INTEGER NOT NULL DEFAULT 0,
                enabled       INTEGER NOT NULL DEFAULT 1,
                created_at    REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS healing_incidents (
                incident_id   TEXT PRIMARY KEY,
                source        TEXT    NOT NULL,
                metric        TEXT    NOT NULL DEFAULT '',
                value         REAL    NOT NULL DEFAULT 0,
                severity      TEXT    NOT NULL DEFAULT 'medium',
                status        TEXT    NOT NULL DEFAULT 'open',
                resolution    TEXT,
                created_at    REAL    NOT NULL,
                resolved_at   REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS healing_actions (
                action_id     TEXT PRIMARY KEY,
                incident_id   TEXT    NOT NULL,
                rule_id       TEXT    NOT NULL,
                action_type   TEXT    NOT NULL,
                action_detail TEXT,
                success       INTEGER NOT NULL DEFAULT 0,
                created_at    REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hr_enabled "
            "ON healing_rules(enabled)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hr_priority "
            "ON healing_rules(priority)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hi_status "
            "ON healing_incidents(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hi_severity "
            "ON healing_incidents(severity)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ha_incident "
            "ON healing_actions(incident_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="monitoring.self_healing",
            ))

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        return dict(row)

    # ------------------------------------------------------------------
    # Rule CRUD
    # ------------------------------------------------------------------

    def create_rule(self, name: str, condition_json: dict,
                    action_json: dict,
                    priority: int = 0) -> dict:
        """Create a new healing rule.

        Args:
            name: Human-readable rule name.
            condition_json: Condition to match (metric, operator, threshold).
            action_json: Action to take when condition matches.
            priority: Higher priority rules are evaluated first.

        Returns:
            Dict with rule_id and rule details.

        Raises:
            ValueError: If required fields are missing.
        """
        if not name:
            raise ValueError("Rule name must not be empty")

        rule_id = self._uid()
        now = time.time()
        cond = json.dumps(condition_json)
        act = json.dumps(action_json)

        with self._lock:
            self._conn.execute("""
                INSERT INTO healing_rules
                    (rule_id, name, condition_json, action_json,
                     priority, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (rule_id, name, cond, act, priority, now))
            self._conn.commit()

        result = {
            "rule_id": rule_id,
            "name": name,
            "condition_json": condition_json,
            "action_json": action_json,
            "priority": priority,
            "enabled": True,
            "created_at": now,
        }

        self._emit("rule_created", {
            "rule_id": rule_id, "name": name, "priority": priority,
        })
        log.info("healing rule created: %s (%s) priority=%d",
                 name, rule_id[:12], priority)
        return result

    def update_rule(self, rule_id: str, *,
                    name: str | None = None,
                    condition_json: dict | None = None,
                    action_json: dict | None = None,
                    priority: int | None = None) -> dict | None:
        """Update an existing rule.

        Returns updated rule dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM healing_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()
            if row is None:
                return None

            new_name = name if name is not None else row["name"]
            new_cond = (json.dumps(condition_json)
                        if condition_json is not None
                        else row["condition_json"])
            new_act = (json.dumps(action_json)
                       if action_json is not None
                       else row["action_json"])
            new_priority = (priority if priority is not None
                            else row["priority"])

            self._conn.execute("""
                UPDATE healing_rules
                SET name = ?, condition_json = ?, action_json = ?, priority = ?
                WHERE rule_id = ?
            """, (new_name, new_cond, new_act, new_priority, rule_id))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM healing_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()

        d = self._row_to_dict(row)
        try:
            d["condition_json"] = json.loads(d["condition_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            d["action_json"] = json.loads(d["action_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        return d

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule.

        Returns True if the rule existed and was deleted.
        """
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM healing_rules WHERE rule_id = ?",
                (rule_id,),
            ).rowcount
            self._conn.commit()
        return n > 0

    def list_rules(self,
                   priority: int | None = None) -> list[dict]:
        """List rules, optionally filtered by priority.

        Returns rules ordered by priority descending.
        """
        with self._lock:
            if priority is not None:
                rows = self._conn.execute(
                    "SELECT * FROM healing_rules "
                    "WHERE priority = ? ORDER BY priority DESC, created_at",
                    (priority,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM healing_rules "
                    "ORDER BY priority DESC, created_at"
                ).fetchall()

        result = []
        for r in rows:
            d = self._row_to_dict(r)
            try:
                d["condition_json"] = json.loads(d["condition_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                d["action_json"] = json.loads(d["action_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Incident management
    # ------------------------------------------------------------------

    def report_incident(self, source: str, metric: str,
                        value: float,
                        severity: str = "medium") -> dict:
        """Report a new incident.

        Evaluates enabled rules against the incident. If a matching rule
        is found, an auto-heal action is triggered and the incident may
        be auto-resolved.

        Args:
            source: Source system that detected the incident.
            metric: Metric name that triggered the incident.
            value: Current metric value.
            severity: Incident severity (low, medium, high, critical).

        Returns:
            Dict with incident_id and auto-heal results.
        """
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. "
                f"Must be one of {VALID_SEVERITIES}"
            )

        incident_id = self._uid()
        now = time.time()
        auto_resolved = False
        auto_actions: list[dict] = []

        with self._lock:
            self._conn.execute("""
                INSERT INTO healing_incidents
                    (incident_id, source, metric, value, severity,
                     status, resolution, created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, 'open', NULL, ?, NULL)
            """, (incident_id, source, metric, value, severity, now))

            # Evaluate rules (highest priority first)
            rules = self._conn.execute(
                "SELECT * FROM healing_rules WHERE enabled = 1 "
                "ORDER BY priority DESC"
            ).fetchall()

            for rule in rules:
                try:
                    condition = json.loads(rule["condition_json"])
                except (json.JSONDecodeError, TypeError):
                    continue

                if self._condition_matches(condition, metric, value):
                    action = json.loads(rule["action_json"])
                    action_result = self._execute_healing_action(
                        incident_id, rule["rule_id"], action
                    )
                    auto_actions.append(action_result)

                    if action_result["success"]:
                        auto_resolved = True
                        self._conn.execute("""
                            UPDATE healing_incidents
                            SET status = 'auto_resolved',
                                resolution = ?,
                                resolved_at = ?
                            WHERE incident_id = ?
                        """, (f"auto_resolved by rule {rule['rule_id']}",
                              now, incident_id))
                        break  # First matching rule wins

            self._conn.commit()

        result = {
            "incident_id": incident_id,
            "source": source,
            "metric": metric,
            "value": value,
            "severity": severity,
            "auto_resolved": auto_resolved,
            "auto_actions": auto_actions,
            "created_at": now,
        }

        self._emit("incident_reported", {
            "incident_id": incident_id, "source": source,
            "metric": metric, "severity": severity,
        })
        if auto_resolved:
            self._emit("auto_heal_triggered", {
                "incident_id": incident_id,
                "actions_count": len(auto_actions),
            })
            self._emit("incident_resolved", {
                "incident_id": incident_id,
                "resolution": "auto_resolved",
            })

        log.info("incident reported: %s metric=%s value=%.2f severity=%s "
                 "auto_resolved=%s", incident_id[:12], metric, value,
                 severity, auto_resolved)
        return result

    def _condition_matches(self, condition: dict,
                           metric: str, value: float) -> bool:
        """Check if a condition matches the given metric/value pair."""
        cond_metric = condition.get("metric", "")
        if cond_metric != metric:
            return False

        operator = condition.get("operator", ">=")
        threshold = condition.get("threshold", 0)

        try:
            v = float(value)
            t = float(threshold)
        except (TypeError, ValueError):
            return False

        if operator == ">":
            return v > t
        elif operator == ">=":
            return v >= t
        elif operator == "<":
            return v < t
        elif operator == "<=":
            return v <= t
        elif operator in ("==", "="):
            return v == t
        elif operator == "!=":
            return v != t
        return False

    def _execute_healing_action(self, incident_id: str, rule_id: str,
                                action: dict) -> dict:
        """Execute a healing action and record it."""
        action_id = self._uid()
        now = time.time()
        action_type = action.get("type", "alert")
        detail = json.dumps(action)

        with self._lock:
            self._conn.execute("""
                INSERT INTO healing_actions
                    (action_id, incident_id, rule_id, action_type,
                     action_detail, success, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (action_id, incident_id, rule_id, action_type,
                  detail, now))
            self._conn.commit()

        return {
            "action_id": action_id,
            "incident_id": incident_id,
            "rule_id": rule_id,
            "action_type": action_type,
            "success": True,
        }

    def get_incident(self, incident_id: str) -> dict | None:
        """Get a single incident by ID, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM healing_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def list_incidents(self, status: str | None = None,
                       severity: str | None = None) -> list[dict]:
        """List incidents with optional status and severity filters."""
        clauses: list[str] = []
        params: list[Any] = []

        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if severity is not None:
            clauses.append("severity = ?")
            params.append(severity)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (f"SELECT * FROM healing_incidents{where} "
               f"ORDER BY created_at DESC")

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def resolve_incident(self, incident_id: str,
                         resolution: str) -> dict | None:
        """Manually resolve an incident.

        Returns updated incident dict, or None if not found.
        """
        now = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM healing_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
            if row is None:
                return None

            self._conn.execute("""
                UPDATE healing_incidents
                SET status = 'resolved', resolution = ?, resolved_at = ?
                WHERE incident_id = ?
            """, (resolution, now, incident_id))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM healing_incidents WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()

        result = self._row_to_dict(row)
        self._emit("incident_resolved", {
            "incident_id": incident_id,
            "resolution": resolution,
        })
        log.info("incident resolved: %s (%s)", incident_id[:12], resolution)
        return result

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_healing_stats(self) -> dict:
        """Return aggregate healing statistics."""
        with self._lock:
            total_rules = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM healing_rules"
            ).fetchone()["cnt"]

            enabled_rules = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM healing_rules WHERE enabled = 1"
            ).fetchone()["cnt"]

            total_incidents = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM healing_incidents"
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM healing_incidents "
                "GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in status_rows}

            sev_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM healing_incidents "
                "GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in sev_rows}

            total_actions = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM healing_actions"
            ).fetchone()["cnt"]

        auto_resolved = by_status.get("auto_resolved", 0)
        resolved = by_status.get("resolved", 0)
        open_count = by_status.get("open", 0)

        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "total_incidents": total_incidents,
            "incidents_by_status": by_status,
            "incidents_by_severity": by_severity,
            "total_healing_actions": total_actions,
            "auto_resolved_count": auto_resolved,
            "manually_resolved_count": resolved,
            "open_count": open_count,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: SelfHealingEngine | None = None


def get_self_healing(db_path: str = ":memory:",
                     event_bus: EventBus | None = None
                     ) -> SelfHealingEngine:
    """Get or create the global SelfHealingEngine singleton."""
    global _instance
    if _instance is None:
        _instance = SelfHealingEngine(db_path, event_bus)
    return _instance


def reset_self_healing() -> None:
    """Reset the global singleton (for testing)."""
    global _instance
    _instance = None
