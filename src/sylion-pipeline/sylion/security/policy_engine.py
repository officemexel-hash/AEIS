"""
SYLION Security -- Policy Engine

Policy definitions and evaluation engine.
SQLite-backed policy storage with evaluation audit trail.
Thread-safe. Emits events via EventBus.
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.security.policy_engine")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    """A security policy definition."""
    policy_id: str = ""
    name: str = ""
    description: str = ""
    policy_type: str = "access"
    rules: list = field(default_factory=list)
    severity: str = "warning"
    enabled: int = 1
    created_at: float = 0.0

    def __post_init__(self):
        if not self.policy_id:
            self.policy_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class PolicyEvaluation:
    """Result of a policy evaluation."""
    eval_id: str = ""
    policy_id: str = ""
    target: str = ""
    result: str = "pass"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.eval_id:
            self.eval_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Policy definitions and evaluation.

    Stores policies and their evaluation history in SQLite.
    Evaluation is stub-based (returns 'pass') for dev-light profile.
    Full evaluation logic will be added in production phase.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
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
            CREATE TABLE IF NOT EXISTS policies (
                policy_id   TEXT PRIMARY KEY,
                name        TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                policy_type TEXT NOT NULL DEFAULT 'access',
                rules       TEXT NOT NULL DEFAULT '[]',
                severity    TEXT NOT NULL DEFAULT 'warning',
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_evaluations (
                eval_id    TEXT PRIMARY KEY,
                policy_id  TEXT NOT NULL DEFAULT '',
                target     TEXT NOT NULL DEFAULT '',
                result     TEXT NOT NULL DEFAULT 'pass',
                details    TEXT NOT NULL DEFAULT '{}',
                timestamp  REAL NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_pol_type ON policies(policy_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_pol_enabled ON policies(enabled)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_policy ON policy_evaluations(policy_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_ts ON policy_evaluations(timestamp)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def create_policy(self, policy_id: str, name: str,
                      description: str = "", policy_type: str = "access",
                      rules: list | None = None,
                      severity: str = "warning") -> dict:
        """Create a new policy."""
        if not policy_id:
            policy_id = uuid.uuid4().hex
        if rules is None:
            rules = []

        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO policies
                    (policy_id, name, description, policy_type, rules, severity, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                policy_id, name, description, policy_type,
                json.dumps(rules, default=str), severity, now,
            ))
            self._conn.commit()

        self._emit("security.policy.created", {
            "policy_id": policy_id, "name": name, "policy_type": policy_type,
        })
        log.info("created policy %s (%s)", name, policy_type)
        return {
            "policy_id": policy_id, "name": name, "description": description,
            "policy_type": policy_type, "rules": rules,
            "severity": severity, "enabled": 1, "created_at": now,
        }

    def get_policy(self, policy_id: str) -> dict | None:
        """Get a policy by ID."""
        row = self._conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?", (policy_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["rules"] = json.loads(result.get("rules", "[]"))
        except (json.JSONDecodeError, TypeError):
            result["rules"] = []
        return result

    def list_policies(self, policy_type: str | None = None,
                      enabled_only: bool = True) -> list[dict]:
        """List policies, optionally filtered by type and enabled status."""
        q = "SELECT * FROM policies WHERE 1=1"
        params: list[Any] = []
        if policy_type:
            q += " AND policy_type = ?"
            params.append(policy_type)
        if enabled_only:
            q += " AND enabled = 1"
        q += " ORDER BY created_at"

        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["rules"] = json.loads(d.get("rules", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["rules"] = []
            results.append(d)
        return results

    def enable_policy(self, policy_id: str) -> bool:
        """Enable a policy."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE policies SET enabled = 1 WHERE policy_id = ?",
                (policy_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def disable_policy(self, policy_id: str) -> bool:
        """Disable a policy."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE policies SET enabled = 0 WHERE policy_id = ?",
                (policy_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, policy_id: str, target: str,
                 context: dict | None = None) -> dict:
        """Evaluate a policy against a target.

        Dev-light stub: always returns 'pass'.
        Returns evaluation result dict.
        """
        if context is None:
            context = {}

        eval_id = uuid.uuid4().hex
        now = time.time()
        result = "pass"
        details = {
            "target": target,
            "context": context,
            "note": "dev-light stub evaluation",
        }

        with self._lock:
            self._conn.execute("""
                INSERT INTO policy_evaluations
                    (eval_id, policy_id, target, result, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                eval_id, policy_id, target, result,
                json.dumps(details, default=str), now,
            ))
            self._conn.commit()

        self._emit("security.policy.evaluated", {
            "eval_id": eval_id, "policy_id": policy_id,
            "target": target, "result": result,
        })
        log.info("evaluated policy %s on %s -> %s", policy_id[:12], target, result)
        return {
            "eval_id": eval_id, "policy_id": policy_id,
            "target": target, "result": result,
            "details": details, "timestamp": now,
        }

    def get_evaluations(self, policy_id: str, limit: int = 50) -> list[dict]:
        """Get evaluation history for a policy."""
        rows = self._conn.execute(
            "SELECT * FROM policy_evaluations WHERE policy_id = ? ORDER BY timestamp DESC LIMIT ?",
            (policy_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d.get("details", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["details"] = {}
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.policy_engine",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: PolicyEngine | None = None


def get_policy_engine(db_path: str | Path | None = None,
                      event_bus: EventBus | None = None) -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine(db_path, event_bus)
    return _engine
