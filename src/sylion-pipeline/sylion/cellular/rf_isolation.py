import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.cellular.rf_isolation")


class RFIsolationValidator:
    """Critical gate: validates RF isolation for cellular experiments.

    Thresholds:
        < -90 dBm  = PASS
        -90 to -80 dBm = WARN
        >= -80 dBm = FAIL

    Results are valid for max 60 minutes.
    """

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
                CREATE TABLE IF NOT EXISTS isolation_checks (
                    check_id TEXT PRIMARY KEY,
                    experiment_freq REAL NOT NULL,
                    measurement_dbm REAL DEFAULT -120,
                    harmonics TEXT DEFAULT '[]',
                    result TEXT DEFAULT 'PASS',
                    monitor_sdr TEXT DEFAULT '',
                    valid_until REAL DEFAULT 0
                )
            """)
            self._conn.commit()

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cellular.rf_isolation"
            ))

    @staticmethod
    def _classify(measurement_dbm: float) -> str:
        if measurement_dbm < -90:
            return "PASS"
        elif measurement_dbm < -80:
            return "WARN"
        else:
            return "FAIL"

    def validate(self, frequency: float, measurement_dbm: float,
                 monitor_sdr: str = '', harmonics: list | None = None) -> dict:
        check_id = uuid.uuid4().hex[:12]
        result = self._classify(measurement_dbm)
        harmonics_json = json.dumps(harmonics if harmonics is not None else [])
        valid_until = time.time() + 3600  # 60 minutes from now

        with self._lock:
            self._conn.execute("""
                INSERT INTO isolation_checks
                    (check_id, experiment_freq, measurement_dbm, harmonics,
                     result, monitor_sdr, valid_until)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (check_id, frequency, measurement_dbm, harmonics_json,
                  result, monitor_sdr, valid_until))
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM isolation_checks WHERE check_id = ?", (check_id,)
        ).fetchone()
        data = dict(row)
        data["harmonics"] = json.loads(data["harmonics"])

        self._emit("cellular.rf.isolation.checked", {
            "check_id": check_id, "frequency": frequency,
            "measurement_dbm": measurement_dbm, "result": result,
        })
        return data

    def get(self, check_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM isolation_checks WHERE check_id = ?", (check_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["harmonics"] = json.loads(data["harmonics"])
        return data

    def latest(self) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM isolation_checks ORDER BY valid_until DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["harmonics"] = json.loads(data["harmonics"])
        return data

    def is_valid(self, frequency: float) -> bool:
        """True only if latest check for this frequency is < 60 min old and PASS."""
        row = self._conn.execute(
            "SELECT * FROM isolation_checks WHERE experiment_freq = ? "
            "ORDER BY valid_until DESC LIMIT 1",
            (frequency,)
        ).fetchone()
        if not row:
            return False
        data = dict(row)
        now = time.time()
        if data["valid_until"] < now:
            return False
        return data["result"] == "PASS"

    def list_checks(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM isolation_checks ORDER BY valid_until DESC LIMIT ?",
            (limit,)
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["harmonics"] = json.loads(d["harmonics"])
            results.append(d)
        return results


_var: RFIsolationValidator | None = None


def get_rf_isolation_validator(db_path=None, event_bus=None) -> RFIsolationValidator:
    global _var
    if _var is None:
        _var = RFIsolationValidator(db_path, event_bus)
    return _var
