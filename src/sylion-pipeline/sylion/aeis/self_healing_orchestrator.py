"""
SYLION AEIS -- Self-Healing Orchestrator

Orchestrates self-healing actions when anomalies or failures are detected.

Matches incoming events against configurable healing rules by trigger type
and pattern.  Creates healing sessions, tracks attempts, and emits events
on the EventBus for downstream consumers.

SQLite-backed. Thread-safe. Emits events via EventBus.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.self_healing_orchestrator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRIGGER_TYPES = ("anomaly", "error", "threshold_breach", "health_check_failure")
ACTION_TYPES = ("restart", "rollback", "scale_up", "notify", "circuit_break")
SESSION_STATUSES = ("pending", "in_progress", "completed", "failed", "skipped")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class HealingRule:
    """A single self-healing rule definition."""
    rule_id: str = ""
    name: str = ""
    trigger_type: str = ""
    trigger_pattern: str = ""
    action_type: str = ""
    action_params: str = ""
    enabled: int = 1
    priority: int = 0
    created_at: float = 0.0

    def __post_init__(self):
        if not self.rule_id:
            self.rule_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class HealingSession:
    """A single self-healing session."""
    session_id: str = ""
    rule_id: str = ""
    trigger_event: str = ""
    status: str = "pending"
    started_at: float = 0.0
    completed_at: float = 0.0
    result: str = ""
    attempts: int = 1

    def __post_init__(self):
        if not self.session_id:
            self.session_id = uuid.uuid4().hex
        if not self.started_at:
            self.started_at = time.time()


# ---------------------------------------------------------------------------
# Self-Healing Orchestrator
# ---------------------------------------------------------------------------

class SelfHealingOrchestrator:
    """Orchestrates self-healing actions based on configurable rules.

    Thread-safe. SQLite-backed. Emits events on rule triggers, session
    completion, and failures.
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
            CREATE TABLE IF NOT EXISTS healing_rules (
                rule_id         TEXT PRIMARY KEY,
                name            TEXT    NOT NULL,
                trigger_type    TEXT    NOT NULL,
                trigger_pattern TEXT    NOT NULL DEFAULT '',
                action_type     TEXT    NOT NULL,
                action_params   TEXT    NOT NULL DEFAULT '',
                enabled         INTEGER NOT NULL DEFAULT 1,
                priority        INTEGER NOT NULL DEFAULT 0,
                created_at      REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS healing_sessions (
                session_id    TEXT PRIMARY KEY,
                rule_id       TEXT    NOT NULL,
                trigger_event TEXT    NOT NULL DEFAULT '',
                status        TEXT    NOT NULL DEFAULT 'pending',
                started_at    REAL    NOT NULL,
                completed_at  REAL    NOT NULL DEFAULT 0,
                result        TEXT    NOT NULL DEFAULT '',
                attempts      INTEGER NOT NULL DEFAULT 1
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hr_trigger_type "
            "ON healing_rules(trigger_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hr_enabled "
            "ON healing_rules(enabled)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hs_rule_id "
            "ON healing_sessions(rule_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_hs_status "
            "ON healing_sessions(status)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Rule CRUD
    # ------------------------------------------------------------------

    def create_rule(self, name: str, trigger_type: str,
                    trigger_pattern: str, action_type: str,
                    action_params: str | dict | None = None,
                    priority: int = 0) -> dict:
        """Create a new healing rule.

        Args:
            name: Human-readable rule name.
            trigger_type: One of TRIGGER_TYPES.
            trigger_pattern: Regex pattern to match against event data.
            action_type: One of ACTION_TYPES.
            action_params: Optional parameters for the action (dict or JSON str).
            priority: Higher-priority rules are evaluated first.

        Returns:
            dict with all rule fields.
        """
        if trigger_type not in TRIGGER_TYPES:
            raise ValueError(
                f"Invalid trigger_type '{trigger_type}'. "
                f"Must be one of {TRIGGER_TYPES}"
            )
        if action_type not in ACTION_TYPES:
            raise ValueError(
                f"Invalid action_type '{action_type}'. "
                f"Must be one of {ACTION_TYPES}"
            )

        if action_params is None:
            params_str = ""
        elif isinstance(action_params, dict):
            params_str = json.dumps(action_params)
        else:
            params_str = str(action_params)

        rule = HealingRule(
            name=name,
            trigger_type=trigger_type,
            trigger_pattern=trigger_pattern,
            action_type=action_type,
            action_params=params_str,
            enabled=1,
            priority=priority,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO healing_rules
                    (rule_id, name, trigger_type, trigger_pattern,
                     action_type, action_params, enabled, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule.rule_id, rule.name, rule.trigger_type,
                rule.trigger_pattern, rule.action_type, rule.action_params,
                rule.enabled, rule.priority, rule.created_at,
            ))
            self._conn.commit()

        result = self._rule_to_dict(rule)
        log.info("created healing rule %s: %s [%s -> %s]",
                 rule.rule_id[:8], name, trigger_type, action_type)
        return result

    def get_rule(self, rule_id: str) -> dict | None:
        """Return a single rule by ID, or None."""
        row = self._conn.execute(
            "SELECT * FROM healing_rules WHERE rule_id = ?",
            (rule_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_rule_dict(row)

    def list_rules(self, trigger_type: str | None = None,
                   enabled: bool | None = None) -> list[dict]:
        """List rules, optionally filtered by trigger_type and/or enabled."""
        conditions: list[str] = []
        params: list[Any] = []

        if trigger_type is not None:
            conditions.append("trigger_type = ?")
            params.append(trigger_type)
        if enabled is not None:
            conditions.append("enabled = ?")
            params.append(1 if enabled else 0)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        rows = self._conn.execute(
            f"SELECT * FROM healing_rules {where} "
            f"ORDER BY priority DESC, created_at ASC",
            params,
        ).fetchall()
        return [self._row_to_rule_dict(r) for r in rows]

    def update_rule(self, rule_id: str, enabled: bool | None = None) -> dict | None:
        """Update a rule. Currently supports toggling enabled/disabled.

        Returns the updated rule dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM healing_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()
            if row is None:
                return None

            if enabled is not None:
                self._conn.execute(
                    "UPDATE healing_rules SET enabled = ? WHERE rule_id = ?",
                    (1 if enabled else 0, rule_id),
                )
                self._conn.commit()

        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule by ID.

        Returns True if the rule was deleted, False if not found.
        """
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM healing_rules WHERE rule_id = ?",
                (rule_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    def process_event(self, trigger_type: str,
                      event_data: dict | str) -> list[dict]:
        """Match an incoming event against healing rules.

        Finds all enabled rules matching the trigger_type whose
        trigger_pattern matches the serialised event data.  Creates a
        healing session for each match, ordered by rule priority.

        Emits ``healing.triggered`` for each session created.

        Returns a list of session dicts.
        """
        if trigger_type not in TRIGGER_TYPES:
            raise ValueError(
                f"Invalid trigger_type '{trigger_type}'. "
                f"Must be one of {TRIGGER_TYPES}"
            )

        if isinstance(event_data, dict):
            event_str = json.dumps(event_data, default=str)
        else:
            event_str = str(event_data)

        # Fetch matching enabled rules
        rules = self._conn.execute(
            "SELECT * FROM healing_rules "
            "WHERE trigger_type = ? AND enabled = 1 "
            "ORDER BY priority DESC, created_at ASC",
            (trigger_type,),
        ).fetchall()

        sessions: list[dict] = []
        for rule_row in rules:
            pattern = rule_row["trigger_pattern"]
            if pattern:
                try:
                    if not re.search(pattern, event_str):
                        continue
                except re.error:
                    log.warning("invalid regex pattern in rule %s: %s",
                                rule_row["rule_id"][:8], pattern)
                    continue

            session = HealingSession(
                rule_id=rule_row["rule_id"],
                trigger_event=event_str,
                status="pending",
            )

            with self._lock:
                self._conn.execute("""
                    INSERT INTO healing_sessions
                        (session_id, rule_id, trigger_event, status,
                         started_at, completed_at, result, attempts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id, session.rule_id,
                    session.trigger_event, session.status,
                    session.started_at, session.completed_at,
                    session.result, session.attempts,
                ))
                self._conn.commit()

            session_dict = self._session_to_dict(session)
            session_dict["rule_name"] = rule_row["name"]
            session_dict["action_type"] = rule_row["action_type"]
            sessions.append(session_dict)

            self._emit("healing.triggered", {
                "session_id": session.session_id,
                "rule_id": session.rule_id,
                "trigger_type": trigger_type,
                "action_type": rule_row["action_type"],
            })

            log.info("healing session %s triggered by rule %s "
                     "[%s -> %s]",
                     session.session_id[:8], rule_row["rule_id"][:8],
                     trigger_type, rule_row["action_type"])

        return sessions

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> dict | None:
        """Return a single session by ID, or None."""
        row = self._conn.execute(
            "SELECT * FROM healing_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_session_dict(row)

    def list_sessions(self, rule_id: str | None = None,
                      status: str | None = None,
                      limit: int = 100) -> list[dict]:
        """List sessions, optionally filtered by rule_id and/or status."""
        conditions: list[str] = []
        params: list[Any] = []

        if rule_id is not None:
            conditions.append("rule_id = ?")
            params.append(rule_id)
        if status is not None:
            if status not in SESSION_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. "
                    f"Must be one of {SESSION_STATUSES}"
                )
            conditions.append("status = ?")
            params.append(status)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        rows = self._conn.execute(
            f"SELECT * FROM healing_sessions {where} "
            f"ORDER BY started_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [self._row_to_session_dict(r) for r in rows]

    def complete_session(self, session_id: str,
                         result: str = "success") -> dict | None:
        """Mark a session as completed (or failed/skipped).

        Sets status based on the result string:
        - "success" -> completed
        - anything else -> failed

        Emits ``healing.completed`` on success, ``healing.failed`` otherwise.

        Returns the updated session dict, or None if not found.
        """
        if result == "success":
            new_status = "completed"
        else:
            new_status = "failed"

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM healing_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                return None

            now = time.time()
            self._conn.execute("""
                UPDATE healing_sessions
                SET status = ?, completed_at = ?, result = ?,
                    attempts = attempts
                WHERE session_id = ?
            """, (new_status, now, result, session_id))
            self._conn.commit()

        if new_status == "completed":
            self._emit("healing.completed", {
                "session_id": session_id,
                "rule_id": row["rule_id"],
                "result": result,
            })
            log.info("healing session %s completed: %s",
                     session_id[:8], result)
        else:
            self._emit("healing.failed", {
                "session_id": session_id,
                "rule_id": row["rule_id"],
                "result": result,
            })
            log.warning("healing session %s failed: %s",
                        session_id[:8], result)

        return self.get_session(session_id)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate self-healing orchestrator statistics.

        Returns counts by session status and by action_type.
        """
        total_rules = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM healing_rules"
        ).fetchone()["cnt"]

        enabled_rules = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM healing_rules WHERE enabled = 1"
        ).fetchone()["cnt"]

        total_sessions = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM healing_sessions"
        ).fetchone()["cnt"]

        # By status
        status_rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM healing_sessions "
            "GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in status_rows}

        # Ensure all statuses appear
        for s in SESSION_STATUSES:
            by_status.setdefault(s, 0)

        # By action_type (join sessions with rules)
        action_rows = self._conn.execute(
            "SELECT r.action_type, COUNT(*) as cnt "
            "FROM healing_sessions s "
            "JOIN healing_rules r ON s.rule_id = r.rule_id "
            "GROUP BY r.action_type"
        ).fetchall()
        by_action_type = {r["action_type"]: r["cnt"] for r in action_rows}

        return {
            "total_rules": total_rules,
            "enabled_rules": enabled_rules,
            "disabled_rules": total_rules - enabled_rules,
            "total_sessions": total_sessions,
            "by_status": by_status,
            "by_action_type": by_action_type,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_to_dict(rule: HealingRule) -> dict:
        return {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "trigger_type": rule.trigger_type,
            "trigger_pattern": rule.trigger_pattern,
            "action_type": rule.action_type,
            "action_params": rule.action_params,
            "enabled": bool(rule.enabled),
            "priority": rule.priority,
            "created_at": rule.created_at,
        }

    @staticmethod
    def _session_to_dict(session: HealingSession) -> dict:
        return {
            "session_id": session.session_id,
            "rule_id": session.rule_id,
            "trigger_event": session.trigger_event,
            "status": session.status,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "result": session.result,
            "attempts": session.attempts,
        }

    @staticmethod
    def _row_to_rule_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        return d

    @staticmethod
    def _row_to_session_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.self_healing_orchestrator",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_orchestrator: SelfHealingOrchestrator | None = None


def get_self_healing_orchestrator(
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None) -> SelfHealingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SelfHealingOrchestrator(db_path, event_bus)
    return _orchestrator


def reset_self_healing_orchestrator() -> None:
    global _orchestrator
    _orchestrator = None
