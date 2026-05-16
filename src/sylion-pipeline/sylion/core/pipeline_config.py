"""
SYLION Core -- Pipeline Config Manager

Manages pipeline configurations, versioning, and validation.
SQLite-backed, thread-safe.

Tables:
  - pipeline_configs: pipeline configuration definitions
  - config_versions: version history for each config
  - config_validations: validation results per config
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

log = logging.getLogger("sylion.core.pipeline_config")


class PipelineConfigManager:
    """Manages pipeline configurations, versions, and validation.
    SQLite-backed, thread-safe."""

    def __init__(self, db_path: str | Path | None = None, event_bus: Any = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS pipeline_configs (
                config_id      TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                pipeline_type  TEXT NOT NULL,
                config_json    TEXT NOT NULL DEFAULT '{}',
                status         TEXT NOT NULL DEFAULT 'active',
                created_at     REAL NOT NULL,
                updated_at     REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS config_versions (
                version_id   TEXT PRIMARY KEY,
                config_id    TEXT NOT NULL,
                version      TEXT NOT NULL,
                changes_json TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS config_validations (
                validation_id TEXT PRIMARY KEY,
                config_id     TEXT NOT NULL,
                rules_json    TEXT NOT NULL DEFAULT '{}',
                result        TEXT NOT NULL DEFAULT 'pending',
                errors_json   TEXT NOT NULL DEFAULT '[]',
                created_at    REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pc_type
                ON pipeline_configs(pipeline_type);
            CREATE INDEX IF NOT EXISTS idx_pc_status
                ON pipeline_configs(status);
            CREATE INDEX IF NOT EXISTS idx_cv_config
                ON config_versions(config_id);
            CREATE INDEX IF NOT EXISTS idx_cval_config
                ON config_validations(config_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Config CRUD
    # ------------------------------------------------------------------

    def create_config(self, name: str, pipeline_type: str,
                      config_json: str = "{}") -> dict:
        config_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO pipeline_configs
                    (config_id, name, pipeline_type, config_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
            """, (config_id, name, pipeline_type, config_json, now, now))
            self._conn.commit()

        result = {
            "config_id": config_id,
            "name": name,
            "pipeline_type": pipeline_type,
            "config_json": config_json,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        self._emit("config.created", {
            "config_id": config_id, "name": name, "pipeline_type": pipeline_type,
        })
        log.info("created config %s (%s / %s)", config_id[:12], name, pipeline_type)
        return result

    def update_config(self, config_id: str, **kwargs: Any) -> dict | None:
        allowed = {"name", "pipeline_type", "config_json", "status"}
        updates: dict[str, Any] = {}
        for k, v in kwargs.items():
            if k not in allowed:
                raise ValueError(f"unknown field: {k}")
            updates[k] = v

        if not updates:
            return self.get_config(config_id)

        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [config_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE pipeline_configs SET {set_clause} WHERE config_id = ?",
                values,
            ).rowcount
            self._conn.commit()

        if not n:
            return None

        self._emit("config.updated", {
            "config_id": config_id, "fields": list(kwargs.keys()),
        })
        log.info("updated config %s", config_id[:12])
        return self.get_config(config_id)

    def get_config(self, config_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pipeline_configs WHERE config_id = ?",
                (config_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_configs(self, pipeline_type: str | None = None) -> list[dict]:
        with self._lock:
            if pipeline_type:
                rows = self._conn.execute(
                    "SELECT * FROM pipeline_configs WHERE pipeline_type = ? ORDER BY created_at DESC",
                    (pipeline_type,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM pipeline_configs ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Versioning
    # ------------------------------------------------------------------

    def create_version(self, config_id: str, version: str,
                       changes_json: str = "{}") -> dict | None:
        cfg = self.get_config(config_id)
        if cfg is None:
            return None

        version_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO config_versions
                    (version_id, config_id, version, changes_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (version_id, config_id, version, changes_json, now))
            self._conn.commit()

        self._emit("config.version_created", {
            "version_id": version_id, "config_id": config_id, "version": version,
        })
        return {
            "version_id": version_id,
            "config_id": config_id,
            "version": version,
            "changes_json": changes_json,
            "created_at": now,
        }

    def get_version(self, version_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM config_versions WHERE version_id = ?",
                (version_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_versions(self, config_id: str | None = None) -> list[dict]:
        with self._lock:
            if config_id:
                rows = self._conn.execute(
                    "SELECT * FROM config_versions WHERE config_id = ? ORDER BY created_at DESC",
                    (config_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM config_versions ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_config(self, config_id: str, rules_json: str = "{}") -> dict | None:
        cfg = self.get_config(config_id)
        if cfg is None:
            return None

        validation_id = uuid.uuid4().hex
        now = time.time()

        # Simple validation: parse rules and config, check required keys
        errors: list[str] = []
        try:
            rules = json.loads(rules_json) if rules_json else {}
            config_data = json.loads(cfg["config_json"]) if cfg["config_json"] else {}
        except json.JSONDecodeError as exc:
            errors.append(f"JSON parse error: {exc}")
            rules = {}
            config_data = {}

        required_keys = rules.get("required_keys", [])
        for key in required_keys:
            if key not in config_data:
                errors.append(f"missing required key: {key}")

        result_status = "valid" if not errors else "invalid"

        with self._lock:
            self._conn.execute("""
                INSERT INTO config_validations
                    (validation_id, config_id, rules_json, result, errors_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (validation_id, config_id, rules_json, result_status,
                  json.dumps(errors), now))
            self._conn.commit()

        self._emit("config.validated", {
            "validation_id": validation_id,
            "config_id": config_id,
            "result": result_status,
        })
        return {
            "validation_id": validation_id,
            "config_id": config_id,
            "result": result_status,
            "errors": errors,
            "created_at": now,
        }

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_config_stats(self) -> dict:
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as c FROM pipeline_configs"
            ).fetchone()["c"]
            by_type_rows = self._conn.execute(
                "SELECT pipeline_type, COUNT(*) as c FROM pipeline_configs GROUP BY pipeline_type"
            ).fetchall()
            total_versions = self._conn.execute(
                "SELECT COUNT(*) as c FROM config_versions"
            ).fetchone()["c"]
            total_validations = self._conn.execute(
                "SELECT COUNT(*) as c FROM config_validations"
            ).fetchone()["c"]
            valid_count = self._conn.execute(
                "SELECT COUNT(*) as c FROM config_validations WHERE result = 'valid'"
            ).fetchone()["c"]

        by_type = {r["pipeline_type"]: r["c"] for r in by_type_rows}
        return {
            "total_configs": total,
            "by_pipeline_type": by_type,
            "total_versions": total_versions,
            "total_validations": total_validations,
            "valid_rate": round(valid_count / total_validations * 100, 2) if total_validations else 0.0,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="core.pipeline_config",
            ))

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: PipelineConfigManager | None = None


def get_pipeline_config_manager(db_path: str | Path | None = None,
                                event_bus: Any = None) -> PipelineConfigManager:
    global _manager
    if _manager is None:
        _manager = PipelineConfigManager(db_path=db_path, event_bus=event_bus)
    return _manager


def reset_pipeline_config_manager() -> None:
    global _manager
    _manager = None
