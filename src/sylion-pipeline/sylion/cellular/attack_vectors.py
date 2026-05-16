import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.cellular.attack_vectors")


class AttackVectorLibrary:
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
                CREATE TABLE IF NOT EXISTS attack_vectors (
                    vector_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    technology TEXT DEFAULT '4G',
                    decision_class TEXT DEFAULT 'D3',
                    preconditions TEXT DEFAULT '[]',
                    steps TEXT DEFAULT '[]',
                    legal_basis TEXT DEFAULT '',
                    lifecycle TEXT DEFAULT 'DRAFT',
                    created_at REAL
                )
            """)
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cellular.attack_vectors"
            ))

    def register(self, vector_id: str, name: str, technology: str = '4G',
                 decision_class: str = 'D3', preconditions: list | None = None,
                 steps: list | None = None, legal_basis: str = '') -> dict:
        now = time.time()
        pre_json = json.dumps(preconditions if preconditions is not None else [])
        steps_json = json.dumps(steps if steps is not None else [])
        with self._lock:
            self._conn.execute("""
                INSERT INTO attack_vectors
                    (vector_id, name, technology, decision_class, preconditions,
                     steps, legal_basis, lifecycle, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?)
            """, (vector_id, name, technology, decision_class,
                  pre_json, steps_json, legal_basis, now))
            self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM attack_vectors WHERE vector_id = ?", (vector_id,)
        ).fetchone()
        data = dict(row)
        data["preconditions"] = json.loads(data["preconditions"])
        data["steps"] = json.loads(data["steps"])
        return data

    def get(self, vector_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM attack_vectors WHERE vector_id = ?", (vector_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["preconditions"] = json.loads(data["preconditions"])
        data["steps"] = json.loads(data["steps"])
        return data

    def list_vectors(self, technology: str | None = None,
                     lifecycle: str | None = None) -> list[dict]:
        q = "SELECT * FROM attack_vectors WHERE 1=1"
        params: list[Any] = []
        if technology:
            q += " AND technology = ?"
            params.append(technology)
        if lifecycle:
            q += " AND lifecycle = ?"
            params.append(lifecycle)
        q += " ORDER BY created_at DESC"
        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["preconditions"] = json.loads(d["preconditions"])
            d["steps"] = json.loads(d["steps"])
            results.append(d)
        return results

    def publish(self, vector_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM attack_vectors WHERE vector_id = ?", (vector_id,)
        ).fetchone()
        if not row:
            return {"error": "vector not found"}
        data = dict(row)
        if data["lifecycle"] != "DRAFT":
            return {"error": f"cannot publish from lifecycle state: {data['lifecycle']}"}
        with self._lock:
            self._conn.execute(
                "UPDATE attack_vectors SET lifecycle = 'PUBLISHED' WHERE vector_id = ?",
                (vector_id,)
            )
            self._conn.commit()
        data["lifecycle"] = "PUBLISHED"
        data["preconditions"] = json.loads(data["preconditions"])
        data["steps"] = json.loads(data["steps"])
        return data

    def deprecate(self, vector_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM attack_vectors WHERE vector_id = ?", (vector_id,)
        ).fetchone()
        if not row:
            return {"error": "vector not found"}
        data = dict(row)
        if data["lifecycle"] != "PUBLISHED":
            return {"error": f"cannot deprecate from lifecycle state: {data['lifecycle']}"}
        with self._lock:
            self._conn.execute(
                "UPDATE attack_vectors SET lifecycle = 'DEPRECATED' WHERE vector_id = ?",
                (vector_id,)
            )
            self._conn.commit()
        data["lifecycle"] = "DEPRECATED"
        data["preconditions"] = json.loads(data["preconditions"])
        data["steps"] = json.loads(data["steps"])
        return data

    def get_stats(self) -> dict:
        rows = self._conn.execute(
            "SELECT lifecycle, COUNT(*) as cnt FROM attack_vectors GROUP BY lifecycle"
        ).fetchall()
        stats = {"total": 0, "DRAFT": 0, "PUBLISHED": 0, "DEPRECATED": 0}
        for r in rows:
            stats[r["lifecycle"]] = r["cnt"]
            stats["total"] += r["cnt"]
        return stats


_var: AttackVectorLibrary | None = None


def get_attack_vector_library(db_path=None, event_bus=None) -> AttackVectorLibrary:
    global _var
    if _var is None:
        _var = AttackVectorLibrary(db_path, event_bus)
    return _var
