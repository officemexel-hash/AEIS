"""
SYLION Governance -- Risk Scorer

Calculates composite risk scores for modules and changes.
Uses weighted factors to produce normalized 0.0-1.0 scores and maps them
to configurable risk levels via thresholds.

Thread-safe. SQLite-backed. EventBus integration.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.governance.risk_scorer")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_RISK_TYPES: tuple[str, ...] = (
    "security", "quality", "operational", "dependency", "compliance",
)

VALID_LEVELS: tuple[str, ...] = (
    "low", "medium", "high", "critical",
)

DEFAULT_THRESHOLDS: list[dict[str, Any]] = [
    {"risk_type": "*", "level": "low",      "min_score": 0.0, "max_score": 0.3, "action": "accept"},
    {"risk_type": "*", "level": "medium",   "min_score": 0.3, "max_score": 0.6, "action": "monitor"},
    {"risk_type": "*", "level": "high",     "min_score": 0.6, "max_score": 0.8, "action": "escalate"},
    {"risk_type": "*", "level": "critical", "min_score": 0.8, "max_score": 1.0, "action": "block"},
]


# ---------------------------------------------------------------------------
# RiskScorer
# ---------------------------------------------------------------------------

class RiskScorer:
    """Composite risk score calculator with configurable thresholds.

    Computes risk scores from weighted factor dictionaries, stores them in
    SQLite, and emits events when scores exceed the "high" threshold.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()
        self._seed_default_thresholds()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_scores (
                    score_id    TEXT PRIMARY KEY,
                    module_id   TEXT NOT NULL,
                    risk_type   TEXT NOT NULL,
                    score       REAL NOT NULL,
                    factors     TEXT NOT NULL DEFAULT '{}',
                    computed_at REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_thresholds (
                    threshold_id TEXT PRIMARY KEY,
                    risk_type    TEXT NOT NULL,
                    level        TEXT NOT NULL,
                    min_score    REAL NOT NULL,
                    max_score    REAL NOT NULL,
                    action       TEXT NOT NULL DEFAULT ''
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk_scores_module ON risk_scores(module_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk_scores_type ON risk_scores(risk_type)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk_scores_ts ON risk_scores(computed_at)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_risk_thresholds_type ON risk_thresholds(risk_type)"
            )
            self._conn.commit()

    def _seed_default_thresholds(self):
        """Insert default thresholds if table is empty."""
        with self._lock:
            count = self._conn.execute("SELECT COUNT(*) FROM risk_thresholds").fetchone()[0]
            if count > 0:
                return
            for t in DEFAULT_THRESHOLDS:
                tid = uuid.uuid4().hex
                self._conn.execute("""
                    INSERT INTO risk_thresholds
                    (threshold_id, risk_type, level, min_score, max_score, action)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (tid, t["risk_type"], t["level"],
                      t["min_score"], t["max_score"], t["action"]))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_composite(factors: dict[str, float]) -> float:
        """Compute a weighted average from a factors dict.

        Each key is a factor name and each value is a float in [0, 1].
        If no factors are provided the score defaults to 0.0.
        Values are clamped to [0, 1].
        """
        if not factors:
            return 0.0
        total = 0.0
        for v in factors.values():
            if isinstance(v, (int, float)):
                total += max(0.0, min(1.0, float(v)))
            else:
                total += 0.0
        score = total / len(factors)
        return round(max(0.0, min(1.0, score)), 6)

    def compute_risk(self, module_id: str, risk_type: str,
                     factors: dict[str, float] | None = None) -> dict:
        """Compute and persist a composite risk score.

        Args:
            module_id: Target module identifier.
            risk_type: One of VALID_RISK_TYPES.
            factors: Dict of factor_name -> value (0.0-1.0).

        Returns:
            Dict with score_id, module_id, risk_type, score, level, factors.
        """
        if risk_type not in VALID_RISK_TYPES:
            raise ValueError(
                f"Invalid risk_type '{risk_type}'. "
                f"Must be one of {VALID_RISK_TYPES}"
            )

        if factors is None:
            factors = {}

        score_id = uuid.uuid4().hex
        now = time.time()
        score = self._compute_composite(factors)

        with self._lock:
            self._conn.execute("""
                INSERT INTO risk_scores
                (score_id, module_id, risk_type, score, factors, computed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (score_id, module_id, risk_type, score,
                  json.dumps(factors), now))
            self._conn.commit()

        level_info = self.get_risk_level(risk_type, score)

        # Emit event if score exceeds "high" threshold
        if level_info["level"] in ("high", "critical"):
            self._emit("risk.score_computed", {
                "score_id": score_id,
                "module_id": module_id,
                "risk_type": risk_type,
                "score": score,
                "level": level_info["level"],
                "action": level_info.get("action", ""),
                "factors": factors,
            })

        log.info("computed risk %s/%s = %.4f (%s)",
                 module_id, risk_type, score, level_info["level"])

        return {
            "score_id": score_id,
            "module_id": module_id,
            "risk_type": risk_type,
            "score": score,
            "level": level_info["level"],
            "action": level_info.get("action", ""),
            "factors": factors,
            "computed_at": now,
        }

    # ------------------------------------------------------------------
    # Score retrieval
    # ------------------------------------------------------------------

    def get_score(self, score_id: str) -> dict | None:
        """Retrieve a single score by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM risk_scores WHERE score_id = ?",
                (score_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_scores(self, module_id: str | None = None,
                    risk_type: str | None = None,
                    limit: int = 100) -> list[dict]:
        """List scores with optional filters, newest first."""
        with self._lock:
            q = "SELECT * FROM risk_scores WHERE 1=1"
            params: list[Any] = []
            if module_id is not None:
                q += " AND module_id = ?"
                params.append(module_id)
            if risk_type is not None:
                q += " AND risk_type = ?"
                params.append(risk_type)
            q += " ORDER BY computed_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_latest_score(self, module_id: str, risk_type: str) -> dict | None:
        """Get the most recent score for a module/risk_type pair."""
        with self._lock:
            row = self._conn.execute("""
                SELECT * FROM risk_scores
                WHERE module_id = ? AND risk_type = ?
                ORDER BY computed_at DESC LIMIT 1
            """, (module_id, risk_type)).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    # ------------------------------------------------------------------
    # Threshold management
    # ------------------------------------------------------------------

    def set_threshold(self, risk_type: str, level: str,
                      min_score: float, max_score: float,
                      action: str = "") -> dict:
        """Configure a risk threshold level.

        Args:
            risk_type: Risk type or '*' for wildcard.
            level: One of VALID_LEVELS.
            min_score: Lower bound (inclusive).
            max_score: Upper bound (inclusive).
            action: Recommended action when score falls in this range.

        Returns:
            Dict with threshold details.
        """
        if risk_type != "*" and risk_type not in VALID_RISK_TYPES:
            raise ValueError(
                f"Invalid risk_type '{risk_type}'. "
                f"Must be one of {VALID_RISK_TYPES} or '*'."
            )
        if level not in VALID_LEVELS:
            raise ValueError(
                f"Invalid level '{level}'. Must be one of {VALID_LEVELS}."
            )
        if min_score < 0 or max_score > 1 or min_score >= max_score:
            raise ValueError(
                f"Invalid score range [{min_score}, {max_score}]. "
                "Must satisfy 0 <= min < max <= 1."
            )

        threshold_id = uuid.uuid4().hex
        with self._lock:
            # Remove any existing threshold for this risk_type+level combo
            self._conn.execute(
                "DELETE FROM risk_thresholds WHERE risk_type = ? AND level = ?",
                (risk_type, level),
            )
            self._conn.execute("""
                INSERT INTO risk_thresholds
                (threshold_id, risk_type, level, min_score, max_score, action)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (threshold_id, risk_type, level, min_score, max_score, action))
            self._conn.commit()

        self._emit("risk.threshold_set", {
            "threshold_id": threshold_id,
            "risk_type": risk_type,
            "level": level,
            "min_score": min_score,
            "max_score": max_score,
            "action": action,
        })

        log.info("set threshold %s/%s: [%.1f, %.1f] -> %s",
                 risk_type, level, min_score, max_score, action)

        return {
            "threshold_id": threshold_id,
            "risk_type": risk_type,
            "level": level,
            "min_score": min_score,
            "max_score": max_score,
            "action": action,
        }

    def list_thresholds(self, risk_type: str | None = None) -> list[dict]:
        """List configured thresholds, optionally filtered by risk_type."""
        with self._lock:
            if risk_type is not None:
                rows = self._conn.execute(
                    "SELECT * FROM risk_thresholds WHERE risk_type = ? OR risk_type = '*' "
                    "ORDER BY min_score",
                    (risk_type,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM risk_thresholds ORDER BY risk_type, min_score"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_risk_level(self, risk_type: str, score: float) -> dict:
        """Determine risk level for a given score.

        First checks risk_type-specific thresholds, then falls back to
        wildcard ('*') thresholds. Returns the level, min_score, max_score,
        and action for the matching band.
        """
        with self._lock:
            # Try specific thresholds first
            rows = self._conn.execute(
                "SELECT * FROM risk_thresholds WHERE risk_type = ? "
                "ORDER BY min_score",
                (risk_type,),
            ).fetchall()

            if not rows:
                # Fall back to wildcard
                rows = self._conn.execute(
                    "SELECT * FROM risk_thresholds WHERE risk_type = '*' "
                    "ORDER BY min_score",
                ).fetchall()

            for row in rows:
                # Use half-open intervals: [min, max) for all except the last
                # band (critical) which is fully inclusive [min, max].
                if row["level"] == "critical":
                    match = row["min_score"] <= score <= row["max_score"]
                else:
                    match = row["min_score"] <= score < row["max_score"]
                if match:
                    return {
                        "level": row["level"],
                        "min_score": row["min_score"],
                        "max_score": row["max_score"],
                        "action": row["action"],
                    }

        # Fallback: derive level from score
        if score < 0.3:
            level = "low"
        elif score < 0.6:
            level = "medium"
        elif score < 0.8:
            level = "high"
        else:
            level = "critical"
        return {"level": level, "min_score": score, "max_score": score, "action": ""}

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics about risk scores and thresholds."""
        with self._lock:
            total_scores = self._conn.execute(
                "SELECT COUNT(*) FROM risk_scores"
            ).fetchone()[0]

            # Count by risk type
            by_type_rows = self._conn.execute(
                "SELECT risk_type, COUNT(*) as cnt FROM risk_scores GROUP BY risk_type"
            ).fetchall()
            by_type = {r["risk_type"]: r["cnt"] for r in by_type_rows}

            # Count by level (need to resolve each score's level)
            by_level: dict[str, int] = {lv: 0 for lv in VALID_LEVELS}
            all_scores = self._conn.execute(
                "SELECT risk_type, score FROM risk_scores"
            ).fetchall()
            for r in all_scores:
                level = self.get_risk_level(r["risk_type"], r["score"])["level"]
                by_level[level] = by_level.get(level, 0) + 1

            # Average score
            avg_row = self._conn.execute(
                "SELECT AVG(score) as avg FROM risk_scores"
            ).fetchone()
            avg_score = round(avg_row["avg"], 6) if avg_row["avg"] is not None else 0.0

            # Max score
            max_row = self._conn.execute(
                "SELECT MAX(score) as mx FROM risk_scores"
            ).fetchone()
            max_score = round(max_row["mx"], 6) if max_row["mx"] is not None else 0.0

            # Unique modules
            modules_row = self._conn.execute(
                "SELECT COUNT(DISTINCT module_id) as cnt FROM risk_scores"
            ).fetchone()
            unique_modules = modules_row["cnt"]

            # Threshold count
            threshold_count = self._conn.execute(
                "SELECT COUNT(*) FROM risk_thresholds"
            ).fetchone()[0]

        return {
            "total_scores": total_scores,
            "unique_modules": unique_modules,
            "average_score": avg_score,
            "max_score": max_score,
            "by_risk_type": by_type,
            "by_level": by_level,
            "threshold_count": threshold_count,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["factors"] = json.loads(d.get("factors", "{}"))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.risk_scorer",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_scorer: RiskScorer | None = None


def get_risk_scorer(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> RiskScorer:
    """Return the global RiskScorer singleton."""
    global _scorer
    if _scorer is None:
        _scorer = RiskScorer(db_path, event_bus)
    return _scorer


def reset_risk_scorer() -> None:
    """Reset the global singleton (for testing)."""
    global _scorer
    _scorer = None
