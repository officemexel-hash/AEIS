"""
SYLION AEIS -- Adaptation Engine

Evaluates system feedback and generates adaptation strategies.
Tracks adaptation history and outcomes for learning.

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

log = logging.getLogger("sylion.aeis.adaptation_engine")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

VALID_ADAPTATION_TYPES = (
    "parameter_tune", "strategy_change", "model_swap",
    "resource_rebalance", "threshold_adjust", "behavior_mod",
)

VALID_ADAPTATION_STATES = ("PENDING", "ACTIVE", "COMPLETED", "FAILED", "CANCELLED")


@dataclass
class Adaptation:
    """A system adaptation."""
    adaptation_id: str = ""
    adaptation_type: str = ""
    trigger_metric: str = ""
    trigger_value: float = 0.0
    target_value: float = 0.0
    strategy: str = ""
    affected_modules: list[str] = field(default_factory=list)
    state: str = "PENDING"
    outcome: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    applied_at: float = 0.0

    def __post_init__(self):
        if not self.adaptation_id:
            self.adaptation_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class FeedbackSignal:
    """A feedback signal from the system."""
    signal_id: str = ""
    source: str = ""
    metric: str = ""
    value: float = 0.0
    threshold: float = 0.0
    severity: str = "info"
    message: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Adaptation Engine
# ---------------------------------------------------------------------------

class AdaptationEngine:
    """Feedback-driven adaptation engine.

    Thread-safe. SQLite-backed. Emits events on adaptations.
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
            CREATE TABLE IF NOT EXISTS adaptations (
                adaptation_id    TEXT PRIMARY KEY,
                adaptation_type  TEXT    NOT NULL,
                trigger_metric   TEXT    NOT NULL,
                trigger_value    REAL    NOT NULL DEFAULT 0,
                target_value     REAL    NOT NULL DEFAULT 0,
                strategy         TEXT    NOT NULL DEFAULT '',
                affected_modules TEXT    NOT NULL DEFAULT '[]',
                state            TEXT    NOT NULL DEFAULT 'PENDING',
                outcome          TEXT    NOT NULL DEFAULT '',
                confidence       REAL    NOT NULL DEFAULT 0,
                metadata         TEXT    NOT NULL DEFAULT '{}',
                created_at       REAL    NOT NULL,
                applied_at       REAL    NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback_signals (
                signal_id  TEXT PRIMARY KEY,
                source     TEXT    NOT NULL,
                metric     TEXT    NOT NULL,
                value      REAL    NOT NULL,
                threshold  REAL    NOT NULL DEFAULT 0,
                severity   TEXT    NOT NULL DEFAULT 'info',
                message    TEXT    NOT NULL DEFAULT '',
                timestamp  REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS adaptation_rules (
                rule_id        TEXT PRIMARY KEY,
                name           TEXT    NOT NULL,
                trigger_metric TEXT    NOT NULL,
                condition_op   TEXT    NOT NULL DEFAULT '>',
                threshold      REAL    NOT NULL,
                adaptation_type TEXT   NOT NULL,
                strategy       TEXT    NOT NULL DEFAULT '',
                priority       INTEGER NOT NULL DEFAULT 0,
                enabled        INTEGER NOT NULL DEFAULT 1,
                created_at     REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_adapt_type ON adaptations(adaptation_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_adapt_state ON adaptations(state)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fb_metric ON feedback_signals(metric)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_fb_ts ON feedback_signals(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rule_metric ON adaptation_rules(trigger_metric)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Feedback ingestion
    # ------------------------------------------------------------------

    def ingest_feedback(self, source: str, metric: str, value: float,
                        threshold: float = 0.0, severity: str = "info",
                        message: str = "") -> dict:
        """Ingest a feedback signal and evaluate rules.

        Emits ``aeis.adaptation.feedback``.
        """
        signal = FeedbackSignal(
            source=source,
            metric=metric,
            value=value,
            threshold=threshold,
            severity=severity,
            message=message,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO feedback_signals
                    (signal_id, source, metric, value, threshold, severity, message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.signal_id, signal.source, signal.metric,
                signal.value, signal.threshold, signal.severity,
                signal.message, signal.timestamp,
            ))
            self._conn.commit()

        # Evaluate rules
        adaptations = self._evaluate_rules(signal)

        self._emit("aeis.adaptation.feedback", {
            "signal_id": signal.signal_id,
            "metric": metric,
            "value": value,
            "triggered_adaptations": len(adaptations),
        })

        return {
            "signal_id": signal.signal_id,
            "metric": metric,
            "value": value,
            "triggered_adaptations": len(adaptations),
            "adaptation_ids": [a["adaptation_id"] for a in adaptations],
        }

    def _evaluate_rules(self, signal: FeedbackSignal) -> list[dict]:
        """Evaluate adaptation rules against a feedback signal."""
        rules = self._conn.execute(
            "SELECT * FROM adaptation_rules WHERE trigger_metric = ? AND enabled = 1",
            (signal.metric,),
        ).fetchall()

        adaptations = []
        for rule in rules:
            triggered = False
            if rule["condition_op"] == ">" and signal.value > rule["threshold"]:
                triggered = True
            elif rule["condition_op"] == "<" and signal.value < rule["threshold"]:
                triggered = True
            elif rule["condition_op"] == ">=" and signal.value >= rule["threshold"]:
                triggered = True
            elif rule["condition_op"] == "<=" and signal.value <= rule["threshold"]:
                triggered = True
            elif rule["condition_op"] == "==" and signal.value == rule["threshold"]:
                triggered = True

            if triggered:
                adapt = self.create_adaptation(
                    adaptation_type=rule["adaptation_type"],
                    trigger_metric=signal.metric,
                    trigger_value=signal.value,
                    target_value=rule["threshold"],
                    strategy=rule["strategy"],
                )
                adaptations.append(adapt)

        return adaptations

    # ------------------------------------------------------------------
    # Adaptation management
    # ------------------------------------------------------------------

    def create_adaptation(self, adaptation_type: str, trigger_metric: str,
                          trigger_value: float = 0.0, target_value: float = 0.0,
                          strategy: str = "",
                          affected_modules: list[str] | None = None,
                          confidence: float = 0.0,
                          metadata: dict | None = None) -> dict:
        """Create a new adaptation.

        Emits ``aeis.adaptation.created``.
        """
        if adaptation_type not in VALID_ADAPTATION_TYPES:
            raise ValueError(f"Invalid adaptation type: {adaptation_type}")

        if affected_modules is None:
            affected_modules = []
        if metadata is None:
            metadata = {}

        adapt = Adaptation(
            adaptation_type=adaptation_type,
            trigger_metric=trigger_metric,
            trigger_value=trigger_value,
            target_value=target_value,
            strategy=strategy,
            affected_modules=affected_modules,
            confidence=confidence,
            metadata=metadata,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO adaptations
                    (adaptation_id, adaptation_type, trigger_metric, trigger_value,
                     target_value, strategy, affected_modules, state, outcome,
                     confidence, metadata, created_at, applied_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                adapt.adaptation_id, adapt.adaptation_type,
                adapt.trigger_metric, adapt.trigger_value,
                adapt.target_value, adapt.strategy,
                json.dumps(affected_modules), adapt.state, adapt.outcome,
                adapt.confidence, json.dumps(metadata, default=str),
                adapt.created_at, adapt.applied_at,
            ))
            self._conn.commit()

        self._emit("aeis.adaptation.created", {
            "adaptation_id": adapt.adaptation_id,
            "adaptation_type": adaptation_type,
            "trigger_metric": trigger_metric,
        })

        log.info("created adaptation %s: %s on %s",
                 adapt.adaptation_id[:12], adaptation_type, trigger_metric)
        return {
            "adaptation_id": adapt.adaptation_id,
            "adaptation_type": adaptation_type,
            "trigger_metric": trigger_metric,
            "state": "PENDING",
        }

    def apply(self, adaptation_id: str, outcome: str = "") -> dict:
        """Mark an adaptation as applied.

        Emits ``aeis.adaptation.applied``.
        """
        row = self._conn.execute(
            "SELECT state FROM adaptations WHERE adaptation_id = ?",
            (adaptation_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Adaptation {adaptation_id} not found")
        if row["state"] != "PENDING":
            raise ValueError(f"Can only apply PENDING adaptations, got {row['state']}")

        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE adaptations SET state = 'ACTIVE', outcome = ?, applied_at = ? WHERE adaptation_id = ?",
                (outcome, now, adaptation_id),
            )
            self._conn.commit()

        self._emit("aeis.adaptation.applied", {
            "adaptation_id": adaptation_id,
            "outcome": outcome,
        })

        return {"adaptation_id": adaptation_id, "state": "ACTIVE"}

    def complete(self, adaptation_id: str, outcome: str = "") -> dict:
        """Mark an adaptation as completed."""
        row = self._conn.execute(
            "SELECT state FROM adaptations WHERE adaptation_id = ?",
            (adaptation_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"Adaptation {adaptation_id} not found")
        if row["state"] != "ACTIVE":
            raise ValueError(f"Can only complete ACTIVE adaptations, got {row['state']}")

        with self._lock:
            self._conn.execute(
                "UPDATE adaptations SET state = 'COMPLETED', outcome = ? WHERE adaptation_id = ?",
                (outcome, adaptation_id),
            )
            self._conn.commit()

        return {"adaptation_id": adaptation_id, "state": "COMPLETED"}

    def fail(self, adaptation_id: str, reason: str = "") -> dict:
        """Mark an adaptation as failed."""
        with self._lock:
            self._conn.execute(
                "UPDATE adaptations SET state = 'FAILED', outcome = ? WHERE adaptation_id = ?",
                (reason, adaptation_id),
            )
            self._conn.commit()

        return {"adaptation_id": adaptation_id, "state": "FAILED"}

    # ------------------------------------------------------------------
    # Rules management
    # ------------------------------------------------------------------

    def add_rule(self, name: str, trigger_metric: str, condition_op: str = ">",
                 threshold: float = 0.0, adaptation_type: str = "threshold_adjust",
                 strategy: str = "", priority: int = 0) -> dict:
        """Add an adaptation rule."""
        rule_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO adaptation_rules
                    (rule_id, name, trigger_metric, condition_op, threshold,
                     adaptation_type, strategy, priority, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule_id, name, trigger_metric, condition_op, threshold,
                adaptation_type, strategy, priority, 1, now,
            ))
            self._conn.commit()

        return {"rule_id": rule_id, "name": name, "trigger_metric": trigger_metric}

    def list_rules(self, enabled_only: bool = False) -> list[dict]:
        """List adaptation rules."""
        q = "SELECT * FROM adaptation_rules"
        if enabled_only:
            q += " WHERE enabled = 1"
        q += " ORDER BY priority DESC"
        return [dict(r) for r in self._conn.execute(q).fetchall()]

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, adaptation_id: str) -> dict | None:
        """Return a single adaptation."""
        row = self._conn.execute(
            "SELECT * FROM adaptations WHERE adaptation_id = ?",
            (adaptation_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["affected_modules"] = json.loads(d.get("affected_modules", "[]"))
        d["metadata"] = json.loads(d.get("metadata", "{}"))
        return d

    def list_adaptations(self, adaptation_type: str | None = None,
                         state: str | None = None,
                         limit: int = 100) -> list[dict]:
        """List adaptations with optional filters."""
        q = "SELECT * FROM adaptations WHERE 1=1"
        params: list[Any] = []
        if adaptation_type:
            q += " AND adaptation_type = ?"
            params.append(adaptation_type)
        if state:
            q += " AND state = ?"
            params.append(state)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["affected_modules"] = json.loads(d.get("affected_modules", "[]"))
            d["metadata"] = json.loads(d.get("metadata", "{}"))
            results.append(d)
        return results

    def get_feedback(self, metric: str | None = None,
                     limit: int = 100) -> list[dict]:
        """Return recent feedback signals."""
        q = "SELECT * FROM feedback_signals WHERE 1=1"
        params: list[Any] = []
        if metric:
            q += " AND metric = ?"
            params.append(metric)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def get_stats(self) -> dict:
        """Aggregate adaptation statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM adaptations"
        ).fetchone()["cnt"]

        total_feedback = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM feedback_signals"
        ).fetchone()["cnt"]

        by_state_rows = self._conn.execute(
            "SELECT state, COUNT(*) as cnt FROM adaptations GROUP BY state"
        ).fetchall()
        by_state = {r["state"]: r["cnt"] for r in by_state_rows}

        by_type_rows = self._conn.execute(
            "SELECT adaptation_type, COUNT(*) as cnt FROM adaptations GROUP BY adaptation_type"
        ).fetchall()
        by_type = {r["adaptation_type"]: r["cnt"] for r in by_type_rows}

        return {
            "total_adaptations": total,
            "total_feedback_signals": total_feedback,
            "by_state": by_state,
            "by_type": by_type,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.adaptation_engine",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: AdaptationEngine | None = None


def get_adaptation_engine(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> AdaptationEngine:
    global _engine
    if _engine is None:
        _engine = AdaptationEngine(db_path, event_bus)
    return _engine
