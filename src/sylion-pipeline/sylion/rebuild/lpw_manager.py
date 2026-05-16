"""
SYLION Rebuild -- Last Previous Working (LPW) Version Manager

Tracks the last known-working version of each module for rollback support.
Records snapshots and version history for rebuild operations.

SQLite-backed. Thread-safe. Emits events via EventBus.
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.rebuild.lpw_manager")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class LPWVersion:
    """Last Previous Working version record."""
    module_id: str = ""
    version: str = ""
    snapshot_hash: str = ""
    status: str = "stable"
    recorded_at: float = 0.0
    restored_at: float = 0.0

    def __post_init__(self):
        if not self.recorded_at:
            self.recorded_at = time.time()


@dataclass
class LPWSnapshot:
    """A snapshot of a module version."""
    snapshot_id: str = ""
    module_id: str = ""
    version: str = ""
    content_hash: str = ""
    description: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# LPW Manager
# ---------------------------------------------------------------------------

class LPWManager:
    """Last Previous Working version manager.

    Thread-safe. SQLite-backed. Emits events to EventBus.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS lpw_versions (
                module_id     TEXT PRIMARY KEY,
                version       TEXT NOT NULL DEFAULT '',
                snapshot_hash TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'stable',
                recorded_at   REAL NOT NULL,
                restored_at   REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS lpw_snapshots (
                snapshot_id   TEXT PRIMARY KEY,
                module_id     TEXT NOT NULL DEFAULT '',
                version       TEXT NOT NULL DEFAULT '',
                content_hash  TEXT NOT NULL DEFAULT '',
                description   TEXT NOT NULL DEFAULT '',
                created_at    REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_lpw_snap_mod ON lpw_snapshots(module_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Record / LPW
    # ------------------------------------------------------------------

    def record(self, module_id: str, version: str,
               snapshot_hash: str = "", status: str = "stable") -> dict:
        """Record a version as the last previous working version."""
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO lpw_versions
                    (module_id, version, snapshot_hash, status, recorded_at, restored_at)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (module_id, version, snapshot_hash, status, now))
            self._conn.commit()

        self._emit("rebuild.lpw.recorded", {
            "module_id": module_id, "version": version, "status": status,
        })

        log.info("recorded LPW for %s: version=%s", module_id, version)
        return {"module_id": module_id, "version": version, "status": status}

    def get_lpw(self, module_id: str) -> dict | None:
        """Get the Last Previous Working version for a module."""
        row = self._conn.execute(
            "SELECT * FROM lpw_versions WHERE module_id = ?", (module_id,),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot(self, module_id: str, version: str,
                 content_hash: str = "", description: str = "") -> dict:
        """Create a version snapshot for a module."""
        snap = LPWSnapshot(
            module_id=module_id,
            version=version,
            content_hash=content_hash,
            description=description,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO lpw_snapshots
                    (snapshot_id, module_id, version, content_hash, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                snap.snapshot_id, snap.module_id, snap.version,
                snap.content_hash, snap.description, snap.created_at,
            ))
            self._conn.commit()

        self._emit("rebuild.lpw.snapshot_created", {
            "snapshot_id": snap.snapshot_id, "module_id": module_id,
            "version": version,
        })

        log.info("created snapshot %s for %s@%s",
                 snap.snapshot_id[:12], module_id, version)
        return {
            "snapshot_id": snap.snapshot_id,
            "module_id": module_id,
            "version": version,
        }

    def restore(self, module_id: str) -> dict:
        """Restore module to its Last Previous Working version (stub).

        Returns the LPW version info, marking restored_at timestamp.
        """
        row = self._conn.execute(
            "SELECT * FROM lpw_versions WHERE module_id = ?", (module_id,),
        ).fetchone()
        if not row:
            log.warning("no LPW found for module %s", module_id)
            return {"module_id": module_id, "error": "no LPW recorded"}

        now = time.time()
        version = row["version"]

        with self._lock:
            self._conn.execute("""
                UPDATE lpw_versions SET restored_at = ? WHERE module_id = ?
            """, (now, module_id))
            self._conn.commit()

        self._emit("rebuild.lpw.restored", {
            "module_id": module_id, "version": version,
        })

        log.info("restored %s to LPW version %s", module_id, version)
        return {"module_id": module_id, "version": version, "restored_at": now}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_lpw(self, status: str | None = None,
                 limit: int = 100) -> list[dict]:
        """List all LPW versions, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM lpw_versions WHERE status = ? ORDER BY recorded_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM lpw_versions ORDER BY recorded_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_history(self, module_id: str, limit: int = 50) -> list[dict]:
        """Get snapshot history for a module."""
        rows = self._conn.execute(
            "SELECT * FROM lpw_snapshots WHERE module_id = ? ORDER BY created_at DESC LIMIT ?",
            (module_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="rebuild.lpw_manager",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: LPWManager | None = None


def get_lpw_manager(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> LPWManager:
    global _manager
    if _manager is None:
        _manager = LPWManager(db_path, event_bus)
    return _manager
