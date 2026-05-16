import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.cellular.ue_emulator")


class UEEmulator:
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
                CREATE TABLE IF NOT EXISTS ue_devices (
                    ue_id TEXT PRIMARY KEY,
                    stack_name TEXT DEFAULT '',
                    technology TEXT DEFAULT '4G',
                    imsi TEXT DEFAULT '',
                    status TEXT DEFAULT 'detached',
                    ran_id TEXT DEFAULT '',
                    core_id TEXT DEFAULT '',
                    created_at REAL
                )
            """)
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cellular.ue_emulator"
            ))

    @staticmethod
    def _generate_test_imsi() -> str:
        """Generate a test IMSI with MCC=001, MNC=01, random MSIN."""
        msin = uuid.uuid4().hex[:10]
        return f"00101{msin}"

    def create(self, stack_name: str = '', technology: str = '4G',
               imsi: str = '') -> dict:
        ue_id = uuid.uuid4().hex[:12]
        if not imsi:
            imsi = self._generate_test_imsi()
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO ue_devices
                    (ue_id, stack_name, technology, imsi, status,
                     ran_id, core_id, created_at)
                VALUES (?, ?, ?, ?, 'detached', '', '', ?)
            """, (ue_id, stack_name, technology, imsi, now))
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM ue_devices WHERE ue_id = ?", (ue_id,)
            ).fetchone()
        return dict(row)

    def attach(self, ue_id: str, ran_id: str, core_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM ue_devices WHERE ue_id = ?", (ue_id,)
        ).fetchone()
        if not row:
            return {"error": "UE not found"}
        with self._lock:
            self._conn.execute("""
                UPDATE ue_devices
                SET status = 'attached', ran_id = ?, core_id = ?
                WHERE ue_id = ?
            """, (ran_id, core_id, ue_id))
            self._conn.commit()
        data = dict(row)
        data["status"] = "attached"
        data["ran_id"] = ran_id
        data["core_id"] = core_id
        self._emit("cellular.ue.attached", {
            "ue_id": ue_id, "ran_id": ran_id, "core_id": core_id,
            "imsi": data["imsi"],
        })
        return data

    def detach(self, ue_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM ue_devices WHERE ue_id = ?", (ue_id,)
        ).fetchone()
        if not row:
            return {"error": "UE not found"}
        with self._lock:
            self._conn.execute("""
                UPDATE ue_devices SET status = 'detached', ran_id = '', core_id = ''
                WHERE ue_id = ?
            """, (ue_id,))
            self._conn.commit()
        data = dict(row)
        data["status"] = "detached"
        data["ran_id"] = ""
        data["core_id"] = ""
        return data

    def get(self, ue_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM ue_devices WHERE ue_id = ?", (ue_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_ues(self, status: str | None = None, limit: int = 100) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM ue_devices WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM ue_devices ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


_var: UEEmulator | None = None


def get_ue_emulator(db_path=None, event_bus=None) -> UEEmulator:
    global _var
    if _var is None:
        _var = UEEmulator(db_path, event_bus)
    return _var
