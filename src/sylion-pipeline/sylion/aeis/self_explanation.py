"""
SYLION AEIS -- Self-Explanation Generation and Validation

Generates and validates self-explanations for decisions.
Tracks explanation quality through validator feedback.

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

log = logging.getLogger("sylion.aeis.self_explanation")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Explanation:
    """A self-explanation for a decision."""
    explanation_id: str = ""
    decision_id: str = ""
    question: str = ""
    explanation: str = ""
    reasoning_steps: list[str] = field(default_factory=list)
    confidence: float = 0.0
    validated: int = 0
    created_at: float = 0.0

    def __post_init__(self):
        if not self.explanation_id:
            self.explanation_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class ExplanationValidation:
    """A validation record for an explanation."""
    validation_id: str = ""
    explanation_id: str = ""
    validator: str = ""
    verdict: str = "pending"
    feedback: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.validation_id:
            self.validation_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Self-Explanation Engine
# ---------------------------------------------------------------------------

class SelfExplanationEngine:
    """Self-explanation generation and validation.

    Thread-safe. SQLite-backed. Emits events on generate/validate.
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
            CREATE TABLE IF NOT EXISTS explanations (
                explanation_id   TEXT PRIMARY KEY,
                decision_id      TEXT    NOT NULL DEFAULT '',
                question         TEXT    NOT NULL,
                explanation      TEXT    NOT NULL DEFAULT '',
                reasoning_steps  TEXT    NOT NULL DEFAULT '[]',
                confidence       REAL    NOT NULL DEFAULT 0.0,
                validated        INTEGER NOT NULL DEFAULT 0,
                created_at       REAL    NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS explanation_validations (
                validation_id TEXT PRIMARY KEY,
                explanation_id TEXT    NOT NULL,
                validator     TEXT    NOT NULL DEFAULT '',
                verdict       TEXT    NOT NULL DEFAULT 'pending',
                feedback      TEXT    NOT NULL DEFAULT '',
                timestamp     REAL    NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expl_decision ON explanations(decision_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expl_validated ON explanations(validated)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_val_expl ON explanation_validations(explanation_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Generate
    # ------------------------------------------------------------------

    def generate(self, decision_id: str, question: str,
                 explanation: str = "",
                 reasoning_steps: list | None = None,
                 confidence: float = 0.0) -> dict:
        """Generate a self-explanation for a decision.

        Emits ``aeis.self_explanation.generated``.
        """
        if reasoning_steps is None:
            reasoning_steps = []

        expl = Explanation(
            decision_id=decision_id,
            question=question,
            explanation=explanation,
            reasoning_steps=reasoning_steps,
            confidence=confidence,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO explanations
                    (explanation_id, decision_id, question, explanation,
                     reasoning_steps, confidence, validated, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                expl.explanation_id, expl.decision_id, expl.question,
                expl.explanation, json.dumps(reasoning_steps),
                expl.confidence, expl.validated, expl.created_at,
            ))
            self._conn.commit()

        self._emit("aeis.self_explanation.generated", {
            "explanation_id": expl.explanation_id,
            "decision_id": decision_id,
            "confidence": confidence,
        })

        log.info("generated explanation %s for decision %s",
                 expl.explanation_id[:12], decision_id[:12])
        return {
            "explanation_id": expl.explanation_id,
            "decision_id": decision_id,
            "confidence": confidence,
        }

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, explanation_id: str, validator: str,
                 verdict: str, feedback: str = "") -> dict:
        """Validate an explanation.

        Emits ``aeis.self_explanation.validated``.
        """
        val = ExplanationValidation(
            explanation_id=explanation_id,
            validator=validator,
            verdict=verdict,
            feedback=feedback,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO explanation_validations
                    (validation_id, explanation_id, validator, verdict, feedback, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                val.validation_id, val.explanation_id, val.validator,
                val.verdict, val.feedback, val.timestamp,
            ))

            # Mark explanation as validated
            self._conn.execute(
                "UPDATE explanations SET validated = 1 WHERE explanation_id = ?",
                (explanation_id,),
            )
            self._conn.commit()

        self._emit("aeis.self_explanation.validated", {
            "validation_id": val.validation_id,
            "explanation_id": explanation_id,
            "verdict": verdict,
        })

        log.info("validated explanation %s: %s by %s",
                 explanation_id[:12], verdict, validator)
        return {
            "validation_id": val.validation_id,
            "explanation_id": explanation_id,
            "verdict": verdict,
        }

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_explanation(self, explanation_id: str) -> dict | None:
        """Return a single explanation by ID."""
        row = self._conn.execute(
            "SELECT * FROM explanations WHERE explanation_id = ?",
            (explanation_id,),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["reasoning_steps"] = json.loads(d.get("reasoning_steps", "[]"))
        return d

    def list_explanations(self, validated: int | None = None,
                          limit: int = 100) -> list[dict]:
        """List explanations with optional validation filter."""
        if validated is not None:
            rows = self._conn.execute(
                "SELECT * FROM explanations WHERE validated = ? ORDER BY created_at DESC LIMIT ?",
                (validated, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM explanations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["reasoning_steps"] = json.loads(d.get("reasoning_steps", "[]"))
            results.append(d)
        return results

    def get_stats(self) -> dict:
        """Aggregate explanation statistics."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM explanations"
        ).fetchone()["cnt"]

        validated_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM explanations WHERE validated = 1"
        ).fetchone()["cnt"]

        avg_confidence_row = self._conn.execute(
            "SELECT AVG(confidence) as avg_conf FROM explanations"
        ).fetchone()
        avg_confidence = avg_confidence_row["avg_conf"] if avg_confidence_row["avg_conf"] is not None else 0.0

        validation_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM explanation_validations"
        ).fetchone()["cnt"]

        verdict_rows = self._conn.execute(
            "SELECT verdict, COUNT(*) as cnt FROM explanation_validations GROUP BY verdict"
        ).fetchall()
        by_verdict = {r["verdict"]: r["cnt"] for r in verdict_rows}

        return {
            "total_explanations": total,
            "validated": validated_count,
            "unvalidated": total - validated_count,
            "avg_confidence": round(avg_confidence, 4),
            "total_validations": validation_count,
            "by_verdict": by_verdict,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.self_explanation",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: SelfExplanationEngine | None = None


def get_self_explanation_engine(db_path: str | Path | None = None,
                                event_bus: EventBus | None = None) -> SelfExplanationEngine:
    global _engine
    if _engine is None:
        _engine = SelfExplanationEngine(db_path, event_bus)
    return _engine
