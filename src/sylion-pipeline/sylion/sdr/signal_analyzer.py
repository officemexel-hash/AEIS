"""
SYLION SDR -- SignalAnalyzer (N3)

Performs signal analysis on captured SDR data: spectrum analysis,
modulation classification, and signal detection.
SQLite-backed. Thread-safe. Emits events via EventBus.
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

log = logging.getLogger("sylion.sdr.signal_analyzer")


class SignalAnalyzer:
    """Signal analysis on captured SDR data."""

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
                CREATE TABLE IF NOT EXISTS analysis_results (
                    analysis_id   TEXT PRIMARY KEY,
                    capture_id    TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    params        TEXT NOT NULL DEFAULT '{}',
                    findings      TEXT NOT NULL DEFAULT '{}',
                    created_at    REAL NOT NULL
                )
            """)
            self._conn.commit()

    def _store(self, capture_id: str, analysis_type: str,
               params: dict, findings: dict) -> dict:
        """Store an analysis result and return it."""
        analysis_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO analysis_results
                    (analysis_id, capture_id, analysis_type, params, findings, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (analysis_id, capture_id, analysis_type,
                  json.dumps(params), json.dumps(findings), now))
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM analysis_results WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        result = dict(row)
        # Deserialize JSON fields
        result["params"] = json.loads(result["params"])
        result["findings"] = json.loads(result["findings"])

        self._emit("sdr.analysis.completed", {
            "analysis_id": analysis_id, "capture_id": capture_id,
            "analysis_type": analysis_type,
        })
        return result

    def analyze_spectrum(self, capture_id: str,
                         fft_size: int = 4096) -> dict:
        """Perform spectrum analysis on capture data. Returns stub result."""
        params = {"fft_size": fft_size}
        findings = {
            "type": "spectrum",
            "bandwidth_hz": 2e6,
            "center_frequency_hz": 0,
            "peak_power_dbm": -42.5,
            "noise_floor_dbm": -110.0,
            "num_bins": fft_size,
            "status": "stub",
        }
        log.info("spectrum analysis for capture %s (fft=%d)", capture_id, fft_size)
        return self._store(capture_id, "spectrum", params, findings)

    def classify_modulation(self, capture_id: str) -> dict:
        """Classify modulation of captured signal. Returns stub result."""
        params = {}
        findings = {
            "type": "modulation_classification",
            "detected_modulation": "QPSK",
            "confidence": 0.87,
            "candidates": [
                {"modulation": "QPSK", "confidence": 0.87},
                {"modulation": "16-QAM", "confidence": 0.09},
                {"modulation": "BPSK", "confidence": 0.04},
            ],
            "status": "stub",
        }
        log.info("modulation classification for capture %s", capture_id)
        return self._store(capture_id, "modulation", params, findings)

    def detect_signals(self, capture_id: str,
                       threshold_db: float = -80) -> dict:
        """Detect signals above threshold. Returns stub result."""
        params = {"threshold_db": threshold_db}
        findings = {
            "type": "signal_detection",
            "signals_found": 2,
            "signals": [
                {"frequency_hz": 100e6, "power_dbm": -55.2, "bandwidth_hz": 200e3},
                {"frequency_hz": 100.5e6, "power_dbm": -72.1, "bandwidth_hz": 50e3},
            ],
            "threshold_db": threshold_db,
            "status": "stub",
        }
        log.info("signal detection for capture %s (threshold=%.1f dB)", capture_id, threshold_db)
        return self._store(capture_id, "detection", params, findings)

    def get(self, analysis_id: str) -> dict | None:
        """Get an analysis result by ID."""
        row = self._conn.execute(
            "SELECT * FROM analysis_results WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["params"] = json.loads(result["params"])
        result["findings"] = json.loads(result["findings"])
        return result

    def list_analyses(self, capture_id: str | None = None,
                      limit: int = 100) -> list[dict]:
        """List analysis results, optionally filtered by capture."""
        if capture_id:
            rows = self._conn.execute(
                "SELECT * FROM analysis_results WHERE capture_id = ? ORDER BY created_at DESC LIMIT ?",
                (capture_id, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM analysis_results ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["params"] = json.loads(d["params"])
            d["findings"] = json.loads(d["findings"])
            results.append(d)
        return results

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="sdr.signal_analyzer",
            ))


_var: SignalAnalyzer | None = None


def get_signal_analyzer(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = SignalAnalyzer(db_path, event_bus)
    return _var
