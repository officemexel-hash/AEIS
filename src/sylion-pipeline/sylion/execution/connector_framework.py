"""
SYLION Execution -- Connector Framework

External connector management with health tracking.  Registers, queries,
and deregisters connectors to external systems (APIs, databases, message
queues).  Each connector carries a configuration payload and a rolling
health history.

Tables:
  connectors       -- registered connectors and their metadata
  connector_configs -- versioned config blobs per connector
  connector_health -- rolling health-check records (status, latency)

Singleton: get_connector_framework() / reset_connector_framework()
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

log = logging.getLogger("sylion.execution.connector_framework")


class ConnectorFramework:
    """External connector management with health tracking.

    Thread-safe.  SQLite-backed.  Emits events to EventBus.
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
            CREATE TABLE IF NOT EXISTS connectors (
                connector_id   TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                connector_type TEXT NOT NULL DEFAULT 'api',
                status         TEXT NOT NULL DEFAULT 'active',
                created_at     REAL NOT NULL,
                updated_at     REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS connector_configs (
                config_id    TEXT PRIMARY KEY,
                connector_id TEXT NOT NULL,
                config_json  TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS connector_health (
                health_id    TEXT PRIMARY KEY,
                connector_id TEXT NOT NULL,
                status       TEXT NOT NULL,
                latency_ms   REAL,
                checked_at   REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conn_type "
            "ON connectors(connector_type)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_conn_status "
            "ON connectors(status)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cfg_conn "
            "ON connector_configs(connector_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_health_conn "
            "ON connector_health(connector_id)")
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
                source_module="execution.connector_framework",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    # ------------------------------------------------------------------
    # Connector CRUD
    # ------------------------------------------------------------------

    def register_connector(self, name: str, connector_type: str = "api",
                           config_json: dict | None = None) -> dict:
        """Register a new external connector with optional config."""
        connector_id = self._uid()
        now = time.time()
        cfg = json.dumps(config_json or {}, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO connectors
                    (connector_id, name, connector_type, status,
                     created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?)
            """, (connector_id, name, connector_type, now, now))
            self._conn.execute("""
                INSERT INTO connector_configs
                    (config_id, connector_id, config_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (self._uid(), connector_id, cfg, now))
            self._conn.commit()

        self._emit("connector_registered", {
            "connector_id": connector_id,
            "connector_type": connector_type,
            "name": name,
        })
        log.info("registered connector %s (%s)", connector_id, name)
        return {"connector_id": connector_id, "name": name,
                "connector_type": connector_type, "status": "active"}

    def update_connector(self, connector_id: str, **fields) -> dict | None:
        """Update mutable connector fields (name, connector_type, status)."""
        allowed = {"name", "connector_type", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return None

        updates["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [connector_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE connectors SET {sets} WHERE connector_id = ?",
                vals,
            ).rowcount
            self._conn.commit()
            if not n:
                return None
            row = self._conn.execute(
                "SELECT * FROM connectors WHERE connector_id = ?",
                (connector_id,),
            ).fetchone()

        self._emit("connector_updated", {
            "connector_id": connector_id,
            "updated_fields": list(updates.keys()),
        })
        return dict(row)

    def deregister_connector(self, connector_id: str) -> bool:
        """Remove a connector and all associated data."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM connectors WHERE connector_id = ?",
                (connector_id,),
            ).rowcount
            if n:
                self._conn.execute(
                    "DELETE FROM connector_configs WHERE connector_id = ?",
                    (connector_id,),
                )
                self._conn.execute(
                    "DELETE FROM connector_health WHERE connector_id = ?",
                    (connector_id,),
                )
            self._conn.commit()

        if n:
            self._emit("connector_deregistered", {
                "connector_id": connector_id,
            })
            log.info("deregistered connector %s", connector_id)
        return bool(n)

    def get_connector(self, connector_id: str) -> dict | None:
        """Get a single connector by ID with its current config."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM connectors WHERE connector_id = ?",
                (connector_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        config = self.get_config(connector_id)
        result["config"] = config
        return result

    def list_connectors(self, connector_type: str | None = None) -> list[dict]:
        """List connectors, optionally filtered by type."""
        with self._lock:
            if connector_type:
                rows = self._conn.execute(
                    "SELECT * FROM connectors WHERE connector_type = ? "
                    "ORDER BY name",
                    (connector_type,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM connectors ORDER BY name"
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Config management
    # ------------------------------------------------------------------

    def get_config(self, connector_id: str) -> dict | None:
        """Get the latest config for a connector."""
        with self._lock:
            row = self._conn.execute(
                "SELECT config_json FROM connector_configs "
                "WHERE connector_id = ? ORDER BY created_at DESC LIMIT 1",
                (connector_id,),
            ).fetchone()
        if not row:
            return None
        return self._parse_json(row["config_json"], {})

    def update_config(self, connector_id: str,
                      config_json: dict) -> bool:
        """Create a new config version for a connector."""
        now = time.time()
        with self._lock:
            exists = self._conn.execute(
                "SELECT 1 FROM connectors WHERE connector_id = ?",
                (connector_id,),
            ).fetchone()
            if not exists:
                return False
            self._conn.execute("""
                INSERT INTO connector_configs
                    (config_id, connector_id, config_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (self._uid(), connector_id,
                  json.dumps(config_json, default=str), now))
            self._conn.execute(
                "UPDATE connectors SET updated_at = ? WHERE connector_id = ?",
                (now, connector_id),
            )
            self._conn.commit()
        return True

    # ------------------------------------------------------------------
    # Health tracking
    # ------------------------------------------------------------------

    def check_health(self, connector_id: str) -> dict | None:
        """Return the most recent health record for a connector."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM connector_health "
                "WHERE connector_id = ? ORDER BY checked_at DESC LIMIT 1",
                (connector_id,),
            ).fetchone()
        return dict(row) if row else None

    def record_health(self, connector_id: str, status: str,
                      latency_ms: float = 0.0) -> dict:
        """Record a health-check result for a connector."""
        now = time.time()
        health_id = self._uid()

        with self._lock:
            self._conn.execute("""
                INSERT INTO connector_health
                    (health_id, connector_id, status, latency_ms, checked_at)
                VALUES (?, ?, ?, ?, ?)
            """, (health_id, connector_id, status, latency_ms, now))
            self._conn.commit()

        if status != "healthy":
            self._emit("connector_unhealthy", {
                "connector_id": connector_id,
                "health_status": status,
                "latency_ms": latency_ms,
            })

        return {"health_id": health_id, "connector_id": connector_id,
                "status": status, "latency_ms": latency_ms}

    def get_health_history(self, connector_id: str,
                           limit: int = 50) -> list[dict]:
        """Return recent health records for a connector."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM connector_health "
                "WHERE connector_id = ? ORDER BY checked_at DESC LIMIT ?",
                (connector_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_connector_stats(self) -> dict[str, Any]:
        """Aggregate connector statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as c FROM connectors"
            ).fetchone()["c"]

            by_type_rows = self._conn.execute(
                "SELECT connector_type, COUNT(*) as c FROM connectors "
                "GROUP BY connector_type"
            ).fetchall()
            by_type = {r["connector_type"]: r["c"] for r in by_type_rows}

            unhealthy = self._conn.execute("""
                SELECT COUNT(DISTINCT ch.connector_id) as c
                FROM connector_health ch
                WHERE ch.status != 'healthy'
                  AND ch.checked_at = (
                      SELECT MAX(checked_at) FROM connector_health
                      WHERE connector_id = ch.connector_id
                  )
            """).fetchone()["c"]

        return {
            "total": total,
            "by_type": by_type,
            "unhealthy": unhealthy,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_framework: ConnectorFramework | None = None


def get_connector_framework(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ConnectorFramework:
    global _framework
    if _framework is None:
        _framework = ConnectorFramework(db_path, event_bus)
    return _framework


def reset_connector_framework(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ConnectorFramework:
    global _framework
    _framework = ConnectorFramework(db_path, event_bus)
    return _framework
