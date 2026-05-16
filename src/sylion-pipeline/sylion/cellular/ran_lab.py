import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.cellular.ran_lab")


class RANLabOrchestrator:
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
                CREATE TABLE IF NOT EXISTS ran_stacks (
                    stack_id TEXT PRIMARY KEY,
                    technology TEXT NOT NULL,
                    stack_name TEXT DEFAULT '',
                    status TEXT DEFAULT 'created',
                    frequency REAL DEFAULT 0,
                    power_dbm REAL DEFAULT -30,
                    plmn_mcc TEXT DEFAULT '001',
                    plmn_mnc TEXT DEFAULT '01',
                    isolation_mode TEXT DEFAULT 'conducted',
                    created_at REAL
                )
            """)
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cellular.ran_lab"
            ))

    def create_stack(self, technology: str, stack_name: str = '',
                     frequency: float = 0, power_dbm: float = -30,
                     plmn_mcc: str = '001', plmn_mnc: str = '01',
                     isolation_mode: str = 'conducted') -> dict:
        stack_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO ran_stacks
                    (stack_id, technology, stack_name, status, frequency,
                     power_dbm, plmn_mcc, plmn_mnc, isolation_mode, created_at)
                VALUES (?, ?, ?, 'created', ?, ?, ?, ?, ?, ?)
            """, (stack_id, technology, stack_name, frequency,
                  power_dbm, plmn_mcc, plmn_mnc, isolation_mode, now))
            self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM ran_stacks WHERE stack_id = ?", (stack_id,)
        ).fetchone()
        return dict(row)

    def start(self, stack_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM ran_stacks WHERE stack_id = ?", (stack_id,)
        ).fetchone()
        if not row:
            return {"error": "stack not found"}
        data = dict(row)
        mcc = data["plmn_mcc"]
        # Validate PLMN is test: MCC must be 001 or 999
        if mcc not in ("001", "999"):
            return {"error": f"non-test PLMN rejected: MCC={mcc}"}
        with self._lock:
            self._conn.execute(
                "UPDATE ran_stacks SET status = 'running' WHERE stack_id = ?",
                (stack_id,)
            )
            self._conn.commit()
        data["status"] = "running"
        self._emit("cellular.ran.started", {
            "stack_id": stack_id, "technology": data["technology"],
            "frequency": data["frequency"], "plmn_mcc": mcc,
            "plmn_mnc": data["plmn_mnc"],
        })
        return data

    def stop(self, stack_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM ran_stacks WHERE stack_id = ?", (stack_id,)
        ).fetchone()
        if not row:
            return {"error": "stack not found"}
        with self._lock:
            self._conn.execute(
                "UPDATE ran_stacks SET status = 'stopped' WHERE stack_id = ?",
                (stack_id,)
            )
            self._conn.commit()
        data = dict(row)
        data["status"] = "stopped"
        self._emit("cellular.ran.stopped", {
            "stack_id": stack_id, "technology": data["technology"],
        })
        return data

    def get(self, stack_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM ran_stacks WHERE stack_id = ?", (stack_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_stacks(self, status: str | None = None, limit: int = 100) -> list[dict]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM ran_stacks WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM ran_stacks ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


_var: RANLabOrchestrator | None = None


def get_ran_lab(db_path=None, event_bus=None) -> RANLabOrchestrator:
    global _var
    if _var is None:
        _var = RANLabOrchestrator(db_path, event_bus)
    return _var
