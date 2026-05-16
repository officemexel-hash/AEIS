"""
SYLION Memory -- Self-Model Store

Persistent self-model storage for AEIS self-awareness.
Tracks capabilities, constraints, health, and autonomy level over time
with snapshot history for introspection.
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

log = logging.getLogger("sylion.memory.self_model_store")


@dataclass
class SelfModel:
    """A single self-model entry."""
    model_id: str = ""
    version: int = 1
    capabilities: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    health: str = "healthy"
    autonomy_level: int = 0
    updated_at: float = 0.0
    created_at: float = 0.0

    def __post_init__(self):
        if not self.model_id:
            self.model_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class ModelSnapshot:
    """A point-in-time snapshot of a self-model."""
    snapshot_id: str = ""
    model_id: str = ""
    version: int = 1
    data: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


class SelfModelStore:
    """Persistent self-model store for AEIS self-awareness.

    Thread-safe. SQLite-backed. Emits events on model changes.
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
            CREATE TABLE IF NOT EXISTS self_models (
                model_id       TEXT PRIMARY KEY,
                version        INTEGER NOT NULL DEFAULT 1,
                capabilities   TEXT NOT NULL DEFAULT '{}',
                constraints    TEXT NOT NULL DEFAULT '{}',
                health         TEXT NOT NULL DEFAULT 'healthy',
                autonomy_level INTEGER NOT NULL DEFAULT 0,
                updated_at     REAL NOT NULL,
                created_at     REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS model_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                model_id    TEXT NOT NULL,
                version     INTEGER NOT NULL,
                data        TEXT NOT NULL DEFAULT '{}',
                reason      TEXT NOT NULL DEFAULT '',
                timestamp   REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_model ON model_snapshots(model_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON model_snapshots(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def initialize(self, model_id: str, capabilities: dict | None = None,
                   constraints: dict | None = None) -> dict:
        """Initialize a new self-model. Returns the model dict."""
        if capabilities is None:
            capabilities = {}
        if constraints is None:
            constraints = {}

        now = time.time()
        model = SelfModel(
            model_id=model_id,
            capabilities=capabilities,
            constraints=constraints,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO self_models
                (model_id, version, capabilities, constraints, health,
                 autonomy_level, updated_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model.model_id, model.version,
                json.dumps(model.capabilities, default=str),
                json.dumps(model.constraints, default=str),
                model.health, model.autonomy_level,
                model.updated_at, model.created_at,
            ))
            self._conn.commit()

        self._emit("self_model.initialized", {
            "model_id": model.model_id,
            "version": model.version,
        })

        log.info("initialized self-model %s", model_id)
        return self._to_dict(model)

    def update(self, model_id: str, capabilities: dict | None = None,
               constraints: dict | None = None, health: str = "healthy",
               autonomy_level: int = 0) -> dict | None:
        """Update an existing self-model. Returns updated model or None."""
        if capabilities is None:
            capabilities = {}
        if constraints is None:
            constraints = {}

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM self_models WHERE model_id = ?",
                (model_id,),
            ).fetchone()
            if not row:
                log.warning("self-model %s not found for update", model_id)
                return None

            new_version = row["version"] + 1
            now = time.time()

            self._conn.execute("""
                UPDATE self_models
                SET capabilities = ?, constraints = ?, health = ?,
                    autonomy_level = ?, version = ?, updated_at = ?
                WHERE model_id = ?
            """, (
                json.dumps(capabilities, default=str),
                json.dumps(constraints, default=str),
                health, autonomy_level, new_version, now,
                model_id,
            ))
            self._conn.commit()

        self._emit("self_model.updated", {
            "model_id": model_id,
            "version": new_version,
            "health": health,
        })

        log.info("updated self-model %s to version %d", model_id, new_version)
        return self.get(model_id)

    def get(self, model_id: str) -> dict | None:
        """Retrieve a self-model by ID."""
        row = self._conn.execute(
            "SELECT * FROM self_models WHERE model_id = ?",
            (model_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot(self, model_id: str, reason: str = "") -> dict | None:
        """Create a point-in-time snapshot of a self-model."""
        model_row = self._conn.execute(
            "SELECT * FROM self_models WHERE model_id = ?",
            (model_id,),
        ).fetchone()
        if not model_row:
            log.warning("self-model %s not found for snapshot", model_id)
            return None

        snap = ModelSnapshot(
            model_id=model_id,
            version=model_row["version"],
            data=self._row_to_dict(model_row),
            reason=reason,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO model_snapshots
                (snapshot_id, model_id, version, data, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                snap.snapshot_id, snap.model_id, snap.version,
                json.dumps(snap.data, default=str), snap.reason,
                snap.timestamp,
            ))
            self._conn.commit()

        self._emit("self_model.snapshotted", {
            "snapshot_id": snap.snapshot_id,
            "model_id": model_id,
            "version": snap.version,
        })

        log.info("snapshotted self-model %s (version %d)", model_id, snap.version)
        return {
            "snapshot_id": snap.snapshot_id,
            "model_id": model_id,
            "version": snap.version,
            "timestamp": snap.timestamp,
        }

    def get_history(self, model_id: str, limit: int = 20) -> list[dict]:
        """Get snapshot history for a self-model."""
        rows = self._conn.execute(
            "SELECT * FROM model_snapshots WHERE model_id = ? ORDER BY timestamp DESC LIMIT ?",
            (model_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["data"] = json.loads(d.get("data", "{}"))
            results.append(d)
        return results

    def get_latest(self, model_id: str) -> dict | None:
        """Get the latest snapshot for a self-model."""
        row = self._conn.execute(
            "SELECT * FROM model_snapshots WHERE model_id = ? ORDER BY timestamp DESC LIMIT 1",
            (model_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["data"] = json.loads(d.get("data", "{}"))
        return d

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(model: SelfModel) -> dict:
        return {
            "model_id": model.model_id,
            "version": model.version,
            "capabilities": model.capabilities,
            "constraints": model.constraints,
            "health": model.health,
            "autonomy_level": model.autonomy_level,
            "updated_at": model.updated_at,
            "created_at": model.created_at,
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["capabilities"] = json.loads(d.get("capabilities", "{}"))
        d["constraints"] = json.loads(d.get("constraints", "{}"))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="memory.self_model_store",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_store: SelfModelStore | None = None


def get_self_model_store(event_bus: EventBus | None = None,
                         db_path: str | Path | None = None) -> SelfModelStore:
    global _store
    if _store is None:
        _store = SelfModelStore(event_bus, db_path)
    return _store


def reset_self_model_store() -> None:
    global _store
    _store = None
