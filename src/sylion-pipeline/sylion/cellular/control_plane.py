import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.cellular.control_plane")


class ControlPlaneAnalyzer:
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
                CREATE TABLE IF NOT EXISTS cp_analyses (
                    analysis_id TEXT PRIMARY KEY,
                    pcap_source TEXT NOT NULL,
                    technology TEXT DEFAULT '4G',
                    protocol TEXT DEFAULT '',
                    messages TEXT DEFAULT '[]',
                    anomalies TEXT DEFAULT '[]',
                    created_at REAL
                )
            """)
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cellular.control_plane"
            ))

    def analyze(self, pcap_source: str, technology: str = '4G',
                protocol: str = '') -> dict:
        analysis_id = uuid.uuid4().hex[:12]
        now = time.time()
        # Stub analysis: return placeholder detected messages
        messages = [
            {"type": "ATTACH_REQUEST", "direction": "UL"},
            {"type": "ATTACH_ACCEPT", "direction": "DL"},
        ]
        messages_json = json.dumps(messages)
        anomalies_json = json.dumps([])

        with self._lock:
            self._conn.execute("""
                INSERT INTO cp_analyses
                    (analysis_id, pcap_source, technology, protocol,
                     messages, anomalies, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (analysis_id, pcap_source, technology, protocol,
                  messages_json, anomalies_json, now))
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM cp_analyses WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        data = dict(row)
        data["messages"] = json.loads(data["messages"])
        data["anomalies"] = json.loads(data["anomalies"])
        return data

    def get(self, analysis_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM cp_analyses WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["messages"] = json.loads(data["messages"])
        data["anomalies"] = json.loads(data["anomalies"])
        return data

    def list_analyses(self, technology: str | None = None,
                      limit: int = 100) -> list[dict]:
        if technology:
            rows = self._conn.execute(
                "SELECT * FROM cp_analyses WHERE technology = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (technology, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM cp_analyses ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["messages"] = json.loads(d["messages"])
            d["anomalies"] = json.loads(d["anomalies"])
            results.append(d)
        return results

    def detect_anomalies(self, analysis_id: str) -> dict:
        row = self._conn.execute(
            "SELECT * FROM cp_analyses WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        if not row:
            return {"error": "analysis not found"}
        data = dict(row)
        messages = json.loads(data["messages"])
        # Check for known anomaly patterns
        anomalies = []
        msg_types = [m.get("type", "") for m in messages]
        if "IDENTITY_REQUEST" in msg_types and "SECURITY_MODE_COMMAND" not in msg_types:
            anomalies.append({
                "pattern": "missing_security_mode",
                "severity": "HIGH",
                "description": "Identity request without subsequent security mode command",
            })
        if "REJECT" in msg_types:
            anomalies.append({
                "pattern": "reject_detected",
                "severity": "MEDIUM",
                "description": "Reject message detected in control plane",
            })

        anomalies_json = json.dumps(anomalies)
        with self._lock:
            self._conn.execute(
                "UPDATE cp_analyses SET anomalies = ? WHERE analysis_id = ?",
                (anomalies_json, analysis_id)
            )
            self._conn.commit()

        data["anomalies"] = anomalies
        data["messages"] = messages
        return data


_var: ControlPlaneAnalyzer | None = None


def get_control_plane_analyzer(db_path=None, event_bus=None) -> ControlPlaneAnalyzer:
    global _var
    if _var is None:
        _var = ControlPlaneAnalyzer(db_path, event_bus)
    return _var
