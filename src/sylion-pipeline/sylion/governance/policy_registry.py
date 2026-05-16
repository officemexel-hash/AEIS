"""
SYLION Governance -- Policy Registry

Centralized policy management for governance policies.
Stores policy definitions with rules and enforcement levels, and tracks
policy application history for audit.
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

log = logging.getLogger("sylion.governance.policy_registry")


@dataclass
class Policy:
    """A governance policy definition."""
    policy_id: str = ""
    name: str = ""
    category: str = "governance"
    description: str = ""
    rules: list[dict[str, Any]] = field(default_factory=list)
    enforcement: str = "advisory"
    version: int = 1
    enabled: int = 1
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class PolicyApplication:
    """A record of a policy being applied to a target."""
    application_id: str = ""
    policy_id: str = ""
    target_type: str = ""
    target_id: str = ""
    result: str = "pending"
    applied_by: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.application_id:
            self.application_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


class PolicyRegistry:
    """Centralized policy registry for governance policies.

    Thread-safe. SQLite-backed. Emits events on policy changes.
    """

    def __init__(self, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
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
                name        TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'governance',
                description TEXT NOT NULL DEFAULT '',
                rules       TEXT NOT NULL DEFAULT '[]',
                enforcement TEXT NOT NULL DEFAULT 'advisory',
                version     INTEGER NOT NULL DEFAULT 1,
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_applications (
                application_id TEXT PRIMARY KEY,
                policy_id      TEXT NOT NULL,
                target_type    TEXT NOT NULL DEFAULT '',
                target_id      TEXT NOT NULL DEFAULT '',
                result         TEXT NOT NULL DEFAULT 'pending',
                applied_by     TEXT NOT NULL DEFAULT '',
                timestamp      REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_policies_category ON policies(category)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_policy_app_policy ON policy_applications(policy_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_policy_app_ts ON policy_applications(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def register(self, policy_id: str, name: str,
                 category: str = "governance", description: str = "",
                 rules: list | None = None,
                 enforcement: str = "advisory") -> dict:
        """Register a new governance policy."""
        if rules is None:
            rules = []

        now = time.time()
        policy = Policy(
            policy_id=policy_id,
            name=name,
            category=category,
            description=description,
            rules=rules,
            enforcement=enforcement,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO policies
                (policy_id, name, category, description, rules,
                 enforcement, version, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy.policy_id, policy.name, policy.category,
                policy.description, json.dumps(policy.rules, default=str),
                policy.enforcement, policy.version, policy.enabled,
                policy.created_at, policy.updated_at,
            ))
            self._conn.commit()

        self._emit("policy.registered", {
            "policy_id": policy_id,
            "name": name,
            "category": category,
        })

        log.info("registered policy %s: %s", policy_id, name)
        return self._policy_to_dict(policy)

    def get(self, policy_id: str) -> dict | None:
        """Retrieve a policy by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
        if not row:
            return None
        return self._policy_row_to_dict(row)

    def list_policies(self, category: str | None = None,
                      enforcement: str | None = None,
                      enabled_only: bool = True) -> list[dict]:
        """List policies with optional filters."""
        q = "SELECT * FROM policies WHERE 1=1"
        params: list[Any] = []
        if category:
            q += " AND category = ?"
            params.append(category)
        if enforcement:
            q += " AND enforcement = ?"
            params.append(enforcement)
        if enabled_only:
            q += " AND enabled = 1"
        q += " ORDER BY name"
        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [self._policy_row_to_dict(r) for r in rows]

    def update_policy(self, policy_id: str, rules: list | None = None,
                      enforcement: str | None = None) -> dict | None:
        """Update a policy's rules and/or enforcement level."""
        if rules is None:
            rules = []

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                log.warning("policy %s not found for update", policy_id)
                return None

            new_version = row["version"] + 1
            now = time.time()
            new_enforcement = enforcement if enforcement is not None else row["enforcement"]

            self._conn.execute("""
                UPDATE policies
                SET rules = ?, enforcement = ?, version = ?, updated_at = ?
                WHERE policy_id = ?
            """, (
                json.dumps(rules, default=str),
                new_enforcement, new_version, now,
                policy_id,
            ))
            self._conn.commit()

        self._emit("policy.updated", {
            "policy_id": policy_id,
            "version": new_version,
        })

        log.info("updated policy %s to version %d", policy_id, new_version)
        return self.get(policy_id)

    def disable(self, policy_id: str) -> dict | None:
        """Disable a policy."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                return None

            self._conn.execute(
                "UPDATE policies SET enabled = 0, updated_at = ? WHERE policy_id = ?",
                (time.time(), policy_id),
            )
            self._conn.commit()

        self._emit("policy.disabled", {"policy_id": policy_id})
        log.info("disabled policy %s", policy_id)
        return self.get(policy_id)

    def enable(self, policy_id: str) -> dict | None:
        """Enable a policy."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                return None

            self._conn.execute(
                "UPDATE policies SET enabled = 1, updated_at = ? WHERE policy_id = ?",
                (time.time(), policy_id),
            )
            self._conn.commit()

        self._emit("policy.enabled", {"policy_id": policy_id})
        log.info("enabled policy %s", policy_id)
        return self.get(policy_id)

    # ------------------------------------------------------------------
    # Policy applications
    # ------------------------------------------------------------------

    def apply(self, policy_id: str, target_type: str, target_id: str,
              result: str = "applied", applied_by: str = "") -> dict:
        """Record a policy application against a target."""
        application = PolicyApplication(
            policy_id=policy_id,
            target_type=target_type,
            target_id=target_id,
            result=result,
            applied_by=applied_by,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO policy_applications
                (application_id, policy_id, target_type, target_id,
                 result, applied_by, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                application.application_id, application.policy_id,
                application.target_type, application.target_id,
                application.result, application.applied_by,
                application.timestamp,
            ))
            self._conn.commit()

        self._emit("policy.applied", {
            "application_id": application.application_id,
            "policy_id": policy_id,
            "target_type": target_type,
            "target_id": target_id,
            "result": result,
        })

        log.info("applied policy %s to %s:%s (result=%s)",
                 policy_id, target_type, target_id, result)
        return {
            "application_id": application.application_id,
            "policy_id": policy_id,
            "target_type": target_type,
            "target_id": target_id,
            "result": result,
        }

    def get_applications(self, policy_id: str, limit: int = 50) -> list[dict]:
        """Get application history for a policy."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM policy_applications WHERE policy_id = ? ORDER BY timestamp DESC LIMIT ?",
                (policy_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _policy_to_dict(policy: Policy) -> dict:
        return {
            "policy_id": policy.policy_id,
            "name": policy.name,
            "category": policy.category,
            "description": policy.description,
            "rules": policy.rules,
            "enforcement": policy.enforcement,
            "version": policy.version,
            "enabled": policy.enabled,
            "created_at": policy.created_at,
            "updated_at": policy.updated_at,
        }

    @staticmethod
    def _policy_row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["rules"] = json.loads(d.get("rules", "[]"))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.policy_registry",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry: PolicyRegistry | None = None


def get_policy_registry(event_bus: EventBus | None = None,
                        db_path: str | Path | None = None) -> PolicyRegistry:
    global _registry
    if _registry is None:
        _registry = PolicyRegistry(event_bus, db_path)
    return _registry
