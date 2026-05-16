import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.cellular.evidence_writer")


class CellularEvidenceWriter:
    def __init__(self, db_path: str | Path | None = None, event_bus=None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS cellular_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    attack_vector TEXT DEFAULT '',
                    isolation TEXT DEFAULT '{}',
                    governance TEXT DEFAULT '{}',
                    findings TEXT DEFAULT '',
                    pcap_cp TEXT DEFAULT '',
                    pcap_up TEXT DEFAULT '',
                    iq_recording TEXT DEFAULT '',
                    created_at REAL
                )
            """)
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cellular.evidence_writer"
            ))

    def write(self, evidence_id: str, experiment_id: str,
              attack_vector: str = '', isolation: dict | None = None,
              governance: dict | None = None, findings: str = '',
              pcap_cp: str = '', pcap_up: str = '',
              iq_recording: str = '') -> dict:
        now = time.time()
        isolation_json = json.dumps(isolation if isolation is not None else {})
        governance_json = json.dumps(governance if governance is not None else {})

        with self._lock:
            self._conn.execute("""
                INSERT INTO cellular_evidence
                    (evidence_id, experiment_id, attack_vector, isolation,
                     governance, findings, pcap_cp, pcap_up, iq_recording, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (evidence_id, experiment_id, attack_vector, isolation_json,
                  governance_json, findings, pcap_cp, pcap_up, iq_recording, now))
            self._conn.commit()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cellular_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
            data = dict(row)
        data["isolation"] = json.loads(data["isolation"])
        data["governance"] = json.loads(data["governance"])
        return data

    def get(self, evidence_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cellular_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["isolation"] = json.loads(data["isolation"])
        data["governance"] = json.loads(data["governance"])
        return data

    def list_evidence(self, experiment_id: str | None = None,
                      limit: int = 100) -> list[dict]:
        with self._lock:
            if experiment_id:
                rows = self._conn.execute(
                    "SELECT * FROM cellular_evidence WHERE experiment_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (experiment_id, limit)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM cellular_evidence ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["isolation"] = json.loads(d["isolation"])
            d["governance"] = json.loads(d["governance"])
            results.append(d)
        return results

    def validate(self, evidence_id: str) -> dict:
        """Check required fields present."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM cellular_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        if not row:
            return {"valid": False, "error": "evidence not found"}
        data = dict(row)
        data["isolation"] = json.loads(data["isolation"])
        data["governance"] = json.loads(data["governance"])
        missing = []
        if not data["experiment_id"]:
            missing.append("experiment_id")
        if not data["attack_vector"]:
            missing.append("attack_vector")
        if not data["findings"]:
            missing.append("findings")
        isolation = data["isolation"]
        if not isolation or not isinstance(isolation, dict) or len(isolation) == 0:
            missing.append("isolation")
        governance = data["governance"]
        if not governance or not isinstance(governance, dict) or len(governance) == 0:
            missing.append("governance")
        if missing:
            return {"valid": False, "missing_fields": missing}
        return {"valid": True, "evidence_id": evidence_id}


_var: CellularEvidenceWriter | None = None


def get_cellular_evidence_writer(db_path=None, event_bus=None) -> CellularEvidenceWriter:
    global _var
    if _var is None:
        _var = CellularEvidenceWriter(db_path, event_bus)
    return _var
