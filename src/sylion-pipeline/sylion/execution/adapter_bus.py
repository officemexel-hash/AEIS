"""
SYLION Execution -- Adapter Bus

Data-format transformation bus between modules.  Adapters are registered
with a protocol and optional routing rules that map source formats to
target formats with transform configurations.

Tables:
  adapters      -- registered adapters with protocol metadata
  adapter_routes -- format-mapping routes with transform specs
  adapter_logs  -- transform execution log (success / failure / duration)

Singleton: get_adapter_bus() / reset_adapter_bus()
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

log = logging.getLogger("sylion.execution.adapter_bus")


class AdapterBus:
    """Data-format transformation bus between modules.

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
            CREATE TABLE IF NOT EXISTS adapters (
                adapter_id TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                protocol   TEXT NOT NULL DEFAULT 'json',
                config     TEXT NOT NULL DEFAULT '{}',
                status     TEXT NOT NULL DEFAULT 'active',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS adapter_routes (
                route_id       TEXT PRIMARY KEY,
                adapter_id     TEXT NOT NULL,
                source_format  TEXT NOT NULL,
                target_format  TEXT NOT NULL,
                transform_json TEXT NOT NULL DEFAULT '{}',
                created_at     REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS adapter_logs (
                log_id      TEXT PRIMARY KEY,
                adapter_id  TEXT NOT NULL,
                route_id    TEXT,
                success     INTEGER NOT NULL DEFAULT 1,
                duration_ms REAL,
                logged_at   REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_adapters_protocol "
            "ON adapters(protocol)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_routes_adapter "
            "ON adapter_routes(adapter_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_logs_adapter "
            "ON adapter_logs(adapter_id)")
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
                source_module="execution.adapter_bus",
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
    # Adapter CRUD
    # ------------------------------------------------------------------

    def register_adapter(self, name: str, protocol: str = "json",
                         config_json: dict | None = None) -> dict:
        """Register a new adapter."""
        adapter_id = self._uid()
        now = time.time()
        cfg = json.dumps(config_json or {}, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO adapters
                    (adapter_id, name, protocol, config,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
            """, (adapter_id, name, protocol, cfg, now, now))
            self._conn.commit()

        self._emit("adapter_registered", {
            "adapter_id": adapter_id,
            "protocol": protocol,
            "name": name,
        })
        log.info("registered adapter %s (%s)", adapter_id, name)
        return {"adapter_id": adapter_id, "name": name,
                "protocol": protocol, "status": "active"}

    def update_adapter(self, adapter_id: str, **fields) -> dict | None:
        """Update mutable adapter fields."""
        allowed = {"name", "protocol", "config", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return None

        if "config" in updates and isinstance(updates["config"], dict):
            updates["config"] = json.dumps(updates["config"], default=str)
        updates["updated_at"] = time.time()
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [adapter_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE adapters SET {sets} WHERE adapter_id = ?",
                vals,
            ).rowcount
            self._conn.commit()
            if not n:
                return None
            row = self._conn.execute(
                "SELECT * FROM adapters WHERE adapter_id = ?",
                (adapter_id,),
            ).fetchone()

        return dict(row)

    def deregister_adapter(self, adapter_id: str) -> bool:
        """Remove an adapter and all associated routes/logs."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM adapters WHERE adapter_id = ?",
                (adapter_id,),
            ).rowcount
            if n:
                self._conn.execute(
                    "DELETE FROM adapter_routes WHERE adapter_id = ?",
                    (adapter_id,),
                )
                self._conn.execute(
                    "DELETE FROM adapter_logs WHERE adapter_id = ?",
                    (adapter_id,),
                )
            self._conn.commit()
        return bool(n)

    def get_adapter(self, adapter_id: str) -> dict | None:
        """Get a single adapter by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM adapters WHERE adapter_id = ?",
                (adapter_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["config"] = self._parse_json(result.get("config"), {})
        return result

    def list_adapters(self, protocol: str | None = None) -> list[dict]:
        """List adapters, optionally filtered by protocol."""
        with self._lock:
            if protocol:
                rows = self._conn.execute(
                    "SELECT * FROM adapters WHERE protocol = ? ORDER BY name",
                    (protocol,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM adapters ORDER BY name"
                ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["config"] = self._parse_json(d.get("config"), {})
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Route management
    # ------------------------------------------------------------------

    def add_route(self, adapter_id: str, source_format: str,
                  target_format: str,
                  transform_json: dict | None = None) -> dict:
        """Add a format-mapping route to an adapter."""
        route_id = self._uid()
        now = time.time()
        tf = json.dumps(transform_json or {}, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO adapter_routes
                    (route_id, adapter_id, source_format, target_format,
                     transform_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (route_id, adapter_id, source_format,
                  target_format, tf, now))
            self._conn.commit()

        self._emit("route_added", {
            "route_id": route_id,
            "adapter_id": adapter_id,
            "source_format": source_format,
            "target_format": target_format,
        })
        return {"route_id": route_id, "adapter_id": adapter_id,
                "source_format": source_format,
                "target_format": target_format}

    def remove_route(self, route_id: str) -> bool:
        """Remove a route by ID."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM adapter_routes WHERE route_id = ?",
                (route_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def list_routes(self, adapter_id: str | None = None) -> list[dict]:
        """List routes, optionally filtered by adapter."""
        with self._lock:
            if adapter_id:
                rows = self._conn.execute(
                    "SELECT * FROM adapter_routes "
                    "WHERE adapter_id = ? ORDER BY source_format",
                    (adapter_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM adapter_routes ORDER BY adapter_id"
                ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["transform_json"] = self._parse_json(d.get("transform_json"), {})
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Transform execution
    # ------------------------------------------------------------------

    def transform_data(self, route_id: str,
                       data_json: dict | None = None) -> dict:
        """Execute a transform using a route's spec.

        Applies the route's transform_json as a field-mapping or
        filter against data_json.  Returns transformed data or error.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM adapter_routes WHERE route_id = ?",
                (route_id,),
            ).fetchone()
        if not row:
            return {"success": False, "error": "route not found"}

        route = dict(row)
        transform = self._parse_json(route.get("transform_json"), {})
        data = data_json or {}

        try:
            result = self._apply_transform(data, transform)
            self.log_transform(
                route["adapter_id"], route_id, True, 0.0)
            self._emit("transform_completed", {
                "route_id": route_id,
                "adapter_id": route["adapter_id"],
            })
            return {"success": True, "data": result}
        except Exception as exc:
            self.log_transform(
                route["adapter_id"], route_id, False, 0.0)
            self._emit("transform_failed", {
                "route_id": route_id,
                "error": str(exc),
            })
            return {"success": False, "error": str(exc)}

    @staticmethod
    def _apply_transform(data: dict, transform: dict) -> dict:
        """Apply a simple field-mapping transform.

        transform may contain:
          mapping  -- {source_field: target_field}
          include  -- list of fields to keep
          defaults -- dict of default values to merge
        """
        result = {}

        mapping = transform.get("mapping")
        include = transform.get("include")
        defaults = transform.get("defaults", {})

        if include:
            for key in include:
                if key in data:
                    result[key] = data[key]
        else:
            result.update(data)

        if mapping:
            mapped = {}
            for src, tgt in mapping.items():
                if src in result:
                    mapped[tgt] = result[src]
            result = mapped

        result.update(defaults)
        return result

    def log_transform(self, adapter_id: str, route_id: str | None,
                      success: bool, duration_ms: float) -> dict:
        """Log a transform execution."""
        log_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO adapter_logs
                    (log_id, adapter_id, route_id, success,
                     duration_ms, logged_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (log_id, adapter_id, route_id,
                  1 if success else 0, duration_ms, now))
            self._conn.commit()

        return {"log_id": log_id, "adapter_id": adapter_id,
                "success": success}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_adapter_stats(self) -> dict[str, Any]:
        """Aggregate adapter statistics."""
        with self._lock:
            total_adapters = self._conn.execute(
                "SELECT COUNT(*) as c FROM adapters"
            ).fetchone()["c"]

            total_routes = self._conn.execute(
                "SELECT COUNT(*) as c FROM adapter_routes"
            ).fetchone()["c"]

            total_transforms = self._conn.execute(
                "SELECT COUNT(*) as c FROM adapter_logs"
            ).fetchone()["c"]

            failed = self._conn.execute(
                "SELECT COUNT(*) as c FROM adapter_logs WHERE success = 0"
            ).fetchone()["c"]

            by_protocol_rows = self._conn.execute(
                "SELECT protocol, COUNT(*) as c FROM adapters "
                "GROUP BY protocol"
            ).fetchall()
            by_protocol = {r["protocol"]: r["c"] for r in by_protocol_rows}

        return {
            "total_adapters": total_adapters,
            "total_routes": total_routes,
            "total_transforms": total_transforms,
            "failed_transforms": failed,
            "by_protocol": by_protocol,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_bus: AdapterBus | None = None


def get_adapter_bus(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> AdapterBus:
    global _bus
    if _bus is None:
        _bus = AdapterBus(db_path, event_bus)
    return _bus


def reset_adapter_bus(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> AdapterBus:
    global _bus
    _bus = AdapterBus(db_path, event_bus)
    return _bus
