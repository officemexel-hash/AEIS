import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.cellular.core_network")


class CoreNetworkEmulator:
    def __init__(self, db_path: str | Path | None = None, event_bus=None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS core_networks (
                    core_id TEXT PRIMARY KEY,
                    technology TEXT NOT NULL,
                    stack_name TEXT DEFAULT '',
                    status TEXT DEFAULT 'created',
                    has_internet INTEGER DEFAULT 0,
                    created_at REAL
                )
            """)
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cellular.core_network"
            ))

    def create(self, technology: str, stack_name: str = '',
               has_internet: bool = False) -> dict:
        # Validate: cellular cores must NOT have Internet access
        if has_internet:
            return {"error": "Internet access forbidden for cellular core emulators"}
        core_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO core_networks
                    (core_id, technology, stack_name, status, has_internet, created_at)
                VALUES (?, ?, ?, 'created', 0, ?)
            """, (core_id, technology, stack_name, now))
            self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM core_networks WHERE core_id = ?", (core_id,)
        ).fetchone()
        return dict(row)

    def start(self, core_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM core_networks WHERE core_id = ?", (core_id,)
        ).fetchone()
        if not row:
            return {"error": "core not found"}
        with self._lock:
            self._conn.execute(
                "UPDATE core_networks SET status = 'running' WHERE core_id = ?",
                (core_id,)
            )
            self._conn.commit()
        data = dict(row)
        data["status"] = "running"
        self._emit("cellular.core.started", {
            "core_id": core_id, "technology": data["technology"],
        })
        return data

    def stop(self, core_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM core_networks WHERE core_id = ?", (core_id,)
        ).fetchone()
        if not row:
            return {"error": "core not found"}
        with self._lock:
            self._conn.execute(
                "UPDATE core_networks SET status = 'stopped' WHERE core_id = ?",
                (core_id,)
            )
            self._conn.commit()
        data = dict(row)
        data["status"] = "stopped"
        return data

    def get(self, core_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM core_networks WHERE core_id = ?", (core_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_cores(self, status: str | None = None, limit: int = 100) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM core_networks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM core_networks ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


_var: CoreNetworkEmulator | None = None


def get_core_network_emulator(db_path=None, event_bus=None) -> CoreNetworkEmulator:
    global _var
    if _var is None:
        _var = CoreNetworkEmulator(db_path, event_bus)
    return _var
