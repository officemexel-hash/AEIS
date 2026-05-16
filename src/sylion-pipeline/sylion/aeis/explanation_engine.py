"""
SYLION AEIS -- Explanation Engine

Generates explanations for decisions using registered templates per D-level.
Tracks explanation accuracy through human ratings and provides per-decision-class
statistics.

SQLite-backed with WAL mode, thread-safe via threading.Lock, singleton pattern.
Emits events via EventBus.
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

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.aeis.explanation_engine")


# ---------------------------------------------------------------------------
# ExplanationEngine
# ---------------------------------------------------------------------------

class ExplanationEngine:
    """Template-based explanation generation with accuracy tracking.

    Thread-safe. SQLite-backed. Emits events on generate / record / evaluate.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_explanation_templates (
                template_id     TEXT PRIMARY KEY,
                decision_class  TEXT NOT NULL,
                required_fields TEXT NOT NULL DEFAULT '[]',
                format_string   TEXT NOT NULL,
                created_at      REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_explanations (
                explanation_id   TEXT PRIMARY KEY,
                decision_id      TEXT NOT NULL DEFAULT '',
                decision_class   TEXT NOT NULL DEFAULT '',
                explanation_text TEXT NOT NULL DEFAULT '',
                confidence_score REAL NOT NULL DEFAULT 0.0,
                context_snapshot TEXT NOT NULL DEFAULT '{}',
                template_id      TEXT NOT NULL DEFAULT '',
                accuracy_rating  REAL,
                rated_at         REAL,
                created_at       REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expl_tpl_class "
            "ON sylion_explanation_templates(decision_class)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expl_decision_id "
            "ON sylion_explanations(decision_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_expl_class "
            "ON sylion_explanations(decision_class)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Template management
    # ------------------------------------------------------------------

    def register_template(self, template_id: str, decision_class: str,
                          required_fields: list[str],
                          format_string: str) -> dict:
        """Register (or replace) an explanation template for a decision class.

        Emits ``aeis.explanation_engine.template_registered``.
        """
        now = time.time()
        fields_json = json.dumps(required_fields)

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_explanation_templates
                    (template_id, decision_class, required_fields,
                     format_string, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (template_id, decision_class, fields_json,
                  format_string, now))
            self._conn.commit()

        self._emit("aeis.explanation_engine.template_registered", {
            "template_id": template_id,
            "decision_class": decision_class,
        })

        log.info("registered template %s for class %s",
                 template_id, decision_class)
        return {
            "template_id": template_id,
            "decision_class": decision_class,
        }

    # ------------------------------------------------------------------
    # Generate explanation
    # ------------------------------------------------------------------

    def generate_explanation(self, decision_class: str,
                             context: dict[str, Any]) -> dict:
        """Generate an explanation from the best matching template + context.

        Looks up a template whose ``decision_class`` matches, validates that
        all ``required_fields`` are present in *context*, then formats the
        ``format_string`` using ``str.format_map``.

        Returns a dict with ``explanation_id``, ``explanation_text``,
        ``confidence_score``, ``template_id``, and ``warnings``.

        Emits ``aeis.explanation_engine.generated``.
        """
        warnings: list[str] = []
        explanation_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_explanation_templates "
                "WHERE decision_class = ? ORDER BY created_at DESC LIMIT 1",
                (decision_class,),
            ).fetchone()

            if not row:
                explanation_text = f"No template registered for decision class '{decision_class}'."
                template_id = ""
                confidence_score = 0.0
                warnings.append("no_template")
            else:
                template_id = row["template_id"]
                required = json.loads(row["required_fields"])
                format_string = row["format_string"]

                missing = [f for f in required if f not in context]
                if missing:
                    explanation_text = (
                        f"Missing required context fields: {', '.join(missing)}."
                    )
                    confidence_score = 0.0
                    warnings.append("missing_fields")
                else:
                    try:
                        explanation_text = format_string.format_map(context)
                        confidence_score = 1.0
                    except (KeyError, IndexError, ValueError) as exc:
                        explanation_text = (
                            f"Template formatting error: {exc}"
                        )
                        confidence_score = 0.0
                        warnings.append("format_error")

            self._conn.execute("""
                INSERT INTO sylion_explanations
                    (explanation_id, decision_id, decision_class,
                     explanation_text, confidence_score, context_snapshot,
                     template_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                explanation_id,
                context.get("decision_id", ""),
                decision_class,
                explanation_text,
                confidence_score,
                json.dumps(context, default=str),
                template_id,
                now,
            ))
            self._conn.commit()

        self._emit("aeis.explanation_engine.generated", {
            "explanation_id": explanation_id,
            "decision_class": decision_class,
            "confidence_score": confidence_score,
        })

        log.info("generated explanation %s for class %s (confidence=%.2f)",
                 explanation_id[:12], decision_class, confidence_score)

        return {
            "explanation_id": explanation_id,
            "explanation_text": explanation_text,
            "confidence_score": confidence_score,
            "template_id": template_id,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Record explanation (manual)
    # ------------------------------------------------------------------

    def record_explanation(self, decision_id: str,
                           explanation_text: str,
                           confidence_score: float,
                           decision_class: str = "") -> dict:
        """Store a pre-generated explanation.

        Emits ``aeis.explanation_engine.recorded``.
        """
        explanation_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO sylion_explanations
                    (explanation_id, decision_id, decision_class,
                     explanation_text, confidence_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                explanation_id,
                decision_id,
                decision_class,
                explanation_text,
                confidence_score,
                now,
            ))
            self._conn.commit()

        self._emit("aeis.explanation_engine.recorded", {
            "explanation_id": explanation_id,
            "decision_id": decision_id,
            "confidence_score": confidence_score,
        })

        log.info("recorded explanation %s for decision %s",
                 explanation_id[:12], decision_id[:12])

        return {
            "explanation_id": explanation_id,
            "decision_id": decision_id,
            "confidence_score": confidence_score,
        }

    # ------------------------------------------------------------------
    # Evaluate accuracy
    # ------------------------------------------------------------------

    def evaluate_accuracy(self, explanation_id: str,
                          human_rating: float) -> dict:
        """Record a human accuracy rating (0-1) for an explanation.

        Emits ``aeis.explanation_engine.evaluated``.
        """
        human_rating = max(0.0, min(1.0, human_rating))
        now = time.time()

        with self._lock:
            updated = self._conn.execute("""
                UPDATE sylion_explanations
                SET accuracy_rating = ?, rated_at = ?
                WHERE explanation_id = ?
            """, (human_rating, now, explanation_id))
            self._conn.commit()

        if updated.rowcount == 0:
            log.warning("evaluate_accuracy: explanation %s not found",
                        explanation_id[:12])
            return {
                "explanation_id": explanation_id,
                "accuracy_rating": human_rating,
                "updated": False,
            }

        self._emit("aeis.explanation_engine.evaluated", {
            "explanation_id": explanation_id,
            "accuracy_rating": human_rating,
        })

        log.info("evaluated explanation %s accuracy=%.2f",
                 explanation_id[:12], human_rating)

        return {
            "explanation_id": explanation_id,
            "accuracy_rating": human_rating,
            "updated": True,
        }

    # ------------------------------------------------------------------
    # Accuracy statistics
    # ------------------------------------------------------------------

    def get_accuracy_stats(self) -> dict:
        """Return average accuracy and per-decision-class breakdown.

        Only considers explanations that have been rated.
        """
        # Overall average
        row = self._conn.execute(
            "SELECT AVG(accuracy_rating) as avg_accuracy, "
            "       COUNT(*) as rated_count "
            "FROM sylion_explanations "
            "WHERE accuracy_rating IS NOT NULL"
        ).fetchone()

        avg_accuracy = row["avg_accuracy"] if row["avg_accuracy"] is not None else 0.0
        rated_count = row["rated_count"]

        # Per-decision-class breakdown
        class_rows = self._conn.execute(
            "SELECT decision_class, "
            "       AVG(accuracy_rating) as avg_accuracy, "
            "       COUNT(*) as rated_count "
            "FROM sylion_explanations "
            "WHERE accuracy_rating IS NOT NULL "
            "GROUP BY decision_class"
        ).fetchall()

        by_class = {}
        for r in class_rows:
            by_class[r["decision_class"]] = {
                "avg_accuracy": round(r["avg_accuracy"], 4) if r["avg_accuracy"] is not None else 0.0,
                "rated_count": r["rated_count"],
            }

        return {
            "avg_accuracy": round(avg_accuracy, 4),
            "rated_count": rated_count,
            "by_decision_class": by_class,
        }

    # ------------------------------------------------------------------
    # List / query
    # ------------------------------------------------------------------

    def list_explanations(self, limit: int = 20) -> list[dict]:
        """Return recent explanations (newest first)."""
        rows = self._conn.execute(
            "SELECT * FROM sylion_explanations "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["context_snapshot"] = json.loads(d.get("context_snapshot", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Overall stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate statistics: total explanations, avg confidence, accuracy rate."""
        total = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_explanations"
        ).fetchone()["cnt"]

        avg_conf_row = self._conn.execute(
            "SELECT AVG(confidence_score) as avg_conf "
            "FROM sylion_explanations"
        ).fetchone()
        avg_confidence = avg_conf_row["avg_conf"] if avg_conf_row["avg_conf"] is not None else 0.0

        rated_row = self._conn.execute(
            "SELECT AVG(accuracy_rating) as avg_accuracy "
            "FROM sylion_explanations WHERE accuracy_rating IS NOT NULL"
        ).fetchone()
        accuracy_rate = rated_row["avg_accuracy"] if rated_row["avg_accuracy"] is not None else 0.0

        rated_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_explanations "
            "WHERE accuracy_rating IS NOT NULL"
        ).fetchone()["cnt"]

        return {
            "total_explanations": total,
            "avg_confidence": round(avg_confidence, 4),
            "accuracy_rate": round(accuracy_rate, 4),
            "rated_count": rated_count,
            "unrated_count": total - rated_count,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.explanation_engine",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: ExplanationEngine | None = None


def get_explanation_engine(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> ExplanationEngine:
    global _engine
    if _engine is None:
        _engine = ExplanationEngine(db_path, event_bus)
    return _engine
