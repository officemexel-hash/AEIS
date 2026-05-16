"""
SYLION Skills -- Demand Signal Analysis

Tracks and analyses demand signals for skills.
Records signal occurrences and generates demand reports.

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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.skills.demand_signal")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class DemandSignal:
    """A single demand signal occurrence."""
    signal_id: str = ""
    signal_type: str = ""
    source: str = ""
    skill_id: str = ""
    frequency: int = 1
    confidence: float = 0.5
    details: dict[str, Any] = field(default_factory=dict)
    first_seen: float = 0.0
    last_seen: float = 0.0

    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = uuid.uuid4().hex
        if not self.first_seen:
            self.first_seen = time.time()
        if not self.last_seen:
            self.last_seen = self.first_seen


@dataclass
class DemandReport:
    """A generated demand analysis report."""
    report_id: str = ""
    period: str = "daily"
    signals: list[str] = field(default_factory=list)
    top_demands: list[dict[str, Any]] = field(default_factory=list)
    generated_at: float = 0.0

    def __post_init__(self):
        if not self.report_id:
            self.report_id = uuid.uuid4().hex
        if not self.generated_at:
            self.generated_at = time.time()


# ---------------------------------------------------------------------------
# Demand Signal Analyzer
# ---------------------------------------------------------------------------

class DemandSignalAnalyzer:
    """Skill demand signal analysis.

    Thread-safe. SQLite-backed. Emits events on record and analyze.
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
            CREATE TABLE IF NOT EXISTS demand_signals (
                signal_id   TEXT PRIMARY KEY,
                signal_type TEXT    NOT NULL,
                source      TEXT    NOT NULL DEFAULT '',
                skill_id    TEXT    NOT NULL DEFAULT '',
                frequency   INTEGER NOT NULL DEFAULT 1,
                confidence  REAL    NOT NULL DEFAULT 0.5,
                details     TEXT    NOT NULL DEFAULT '{}',
                first_seen  REAL    NOT NULL,
                last_seen   REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS demand_reports (
                report_id     TEXT PRIMARY KEY,
                period        TEXT    NOT NULL DEFAULT 'daily',
                signals       TEXT    NOT NULL DEFAULT '[]',
                top_demands   TEXT    NOT NULL DEFAULT '[]',
                generated_at  REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sig_type ON demand_signals(signal_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sig_skill ON demand_signals(skill_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sig_freq ON demand_signals(frequency DESC)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rep_ts ON demand_reports(generated_at)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(self, signal_type: str, source: str = "",
               skill_id: str = "", confidence: float = 0.5,
               details: dict | None = None) -> dict:
        """Record a demand signal occurrence.

        If a matching signal (same type + source + skill_id) exists,
        increments its frequency and updates last_seen. Otherwise creates
        a new signal. Emits ``skill.demand_signal.recorded``.
        """
        if details is None:
            details = {}

        now = time.time()

        with self._lock:
            # Check for existing signal with same type+source+skill
            existing = self._conn.execute(
                "SELECT * FROM demand_signals WHERE signal_type = ? AND source = ? AND skill_id = ?",
                (signal_type, source, skill_id),
            ).fetchone()

            if existing:
                new_freq = existing["frequency"] + 1
                # Weighted confidence update
                new_confidence = (existing["confidence"] * existing["frequency"] + confidence) / new_freq
                self._conn.execute("""
                    UPDATE demand_signals
                    SET frequency = ?, confidence = ?, last_seen = ?, details = ?
                    WHERE signal_id = ?
                """, (
                    new_freq, round(new_confidence, 4), now,
                    json.dumps(details, default=str),
                    existing["signal_id"],
                ))
                self._conn.commit()

                self._emit("skill.demand_signal.recorded", {
                    "signal_id": existing["signal_id"],
                    "signal_type": signal_type,
                    "frequency": new_freq,
                })

                log.info("updated signal %s: freq=%d conf=%.2f",
                         existing["signal_id"][:12], new_freq, new_confidence)
                return {
                    "signal_id": existing["signal_id"],
                    "signal_type": signal_type,
                    "frequency": new_freq,
                    "updated": True,
                }

            # New signal
            sig = DemandSignal(
                signal_type=signal_type,
                source=source,
                skill_id=skill_id,
                confidence=confidence,
                details=details,
                first_seen=now,
                last_seen=now,
            )

            self._conn.execute("""
                INSERT INTO demand_signals
                    (signal_id, signal_type, source, skill_id,
                     frequency, confidence, details, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sig.signal_id, sig.signal_type, sig.source, sig.skill_id,
                sig.frequency, sig.confidence,
                json.dumps(details, default=str),
                sig.first_seen, sig.last_seen,
            ))
            self._conn.commit()

            self._emit("skill.demand_signal.recorded", {
                "signal_id": sig.signal_id,
                "signal_type": signal_type,
                "frequency": 1,
            })

            log.info("recorded signal %s: type=%s source=%s",
                     sig.signal_id[:12], signal_type, source)
            return {
                "signal_id": sig.signal_id,
                "signal_type": signal_type,
                "frequency": 1,
                "updated": False,
            }

    # ------------------------------------------------------------------
    # Analyze
    # ------------------------------------------------------------------

    def analyze(self) -> dict:
        """Generate a demand analysis report.

        Aggregates signals by type and skill, ranking by frequency.
        Stores the report for historical tracking. Emits
        ``skill.demand_signal.analyzed``.
        """
        now = time.time()

        # Top demands by frequency
        top_rows = self._conn.execute(
            "SELECT signal_type, skill_id, SUM(frequency) as total_freq, AVG(confidence) as avg_conf "
            "FROM demand_signals GROUP BY signal_type, skill_id "
            "ORDER BY total_freq DESC LIMIT 20"
        ).fetchall()

        top_demands = []
        for r in top_rows:
            top_demands.append({
                "signal_type": r["signal_type"],
                "skill_id": r["skill_id"],
                "total_frequency": r["total_freq"],
                "avg_confidence": round(r["avg_conf"], 4),
            })

        # All signal IDs
        signal_rows = self._conn.execute(
            "SELECT signal_id FROM demand_signals ORDER BY frequency DESC"
        ).fetchall()
        signal_ids = [r["signal_id"] for r in signal_rows]

        # Create report
        report = DemandReport(
            period="daily",
            signals=signal_ids,
            top_demands=top_demands,
            generated_at=now,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO demand_reports
                    (report_id, period, signals, top_demands, generated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                report.report_id, report.period,
                json.dumps(signal_ids),
                json.dumps(top_demands, default=str),
                report.generated_at,
            ))
            self._conn.commit()

        self._emit("skill.demand_signal.analyzed", {
            "report_id": report.report_id,
            "signal_count": len(signal_ids),
            "top_demands": len(top_demands),
        })

        log.info("generated demand report %s: %d signals, %d top demands",
                 report.report_id[:12], len(signal_ids), len(top_demands))
        return {
            "report_id": report.report_id,
            "signal_count": len(signal_ids),
            "top_demands": top_demands,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_signals(self, skill_id: str | None = None,
                    limit: int = 100) -> list[dict]:
        """Return demand signals, optionally filtered by skill."""
        if skill_id:
            rows = self._conn.execute(
                "SELECT * FROM demand_signals WHERE skill_id = ? ORDER BY frequency DESC LIMIT ?",
                (skill_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM demand_signals ORDER BY frequency DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d.get("details", "{}"))
            results.append(d)
        return results

    def get_latest_report(self) -> dict | None:
        """Return the most recent demand report."""
        row = self._conn.execute(
            "SELECT * FROM demand_reports ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["signals"] = json.loads(d.get("signals", "[]"))
        d["top_demands"] = json.loads(d.get("top_demands", "[]"))
        return d

    def get_stats(self) -> dict:
        """Aggregate demand signal statistics."""
        total_signals = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM demand_signals"
        ).fetchone()["cnt"]

        total_frequency = self._conn.execute(
            "SELECT COALESCE(SUM(frequency), 0) as cnt FROM demand_signals"
        ).fetchone()["cnt"]

        by_type_rows = self._conn.execute(
            "SELECT signal_type, COUNT(*) as cnt, SUM(frequency) as freq FROM demand_signals GROUP BY signal_type"
        ).fetchall()
        by_type = {}
        for r in by_type_rows:
            by_type[r["signal_type"]] = {
                "unique_signals": r["cnt"],
                "total_frequency": r["freq"],
            }

        by_skill_rows = self._conn.execute(
            "SELECT skill_id, COUNT(*) as cnt, SUM(frequency) as freq FROM demand_signals GROUP BY skill_id"
        ).fetchall()
        by_skill = {}
        for r in by_skill_rows:
            by_skill[r["skill_id"] or "(unassigned)"] = {
                "unique_signals": r["cnt"],
                "total_frequency": r["freq"],
            }

        report_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM demand_reports"
        ).fetchone()["cnt"]

        return {
            "total_unique_signals": total_signals,
            "total_frequency": total_frequency,
            "total_reports": report_count,
            "by_type": by_type,
            "by_skill": by_skill,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="skills.demand_signal",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_analyzer: DemandSignalAnalyzer | None = None


def get_demand_signal_analyzer(db_path: str | Path | None = None,
                               event_bus: EventBus | None = None) -> DemandSignalAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = DemandSignalAnalyzer(db_path, event_bus)
    return _analyzer
