"""
SYLION Cognitive -- Evaluation Framework

Multi-criteria model evaluation with weighted scoring, side-by-side
comparison, and aggregate statistics.

Thread-safe. SQLite-backed with WAL mode. Singleton pattern.
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

log = logging.getLogger("sylion.cognitive.evaluation_framework")


# ---------------------------------------------------------------------------
# EvaluationFramework
# ---------------------------------------------------------------------------

class EvaluationFramework:
    """Multi-criteria model evaluation framework.

    Supports weighted criteria, per-criterion result recording, weighted
    score computation, model comparison, and aggregate statistics.

    Thread-safe via threading.Lock. SQLite-backed.
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
            CREATE TABLE IF NOT EXISTS sylion_evaluations (
                eval_id    TEXT PRIMARY KEY,
                model_id   TEXT NOT NULL DEFAULT '',
                dataset    TEXT NOT NULL DEFAULT '',
                status     TEXT NOT NULL DEFAULT 'open',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_evaluation_criteria (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                eval_id     TEXT NOT NULL,
                name        TEXT NOT NULL,
                weight      REAL NOT NULL DEFAULT 1.0,
                metric      TEXT NOT NULL DEFAULT '',
                score       REAL,
                details     TEXT,
                recorded_at REAL,
                FOREIGN KEY (eval_id) REFERENCES sylion_evaluations(eval_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ef_eval_model "
            "ON sylion_evaluations(model_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ef_eval_status "
            "ON sylion_evaluations(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ef_crit_eval "
            "ON sylion_evaluation_criteria(eval_id)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Create evaluation
    # ------------------------------------------------------------------

    def create_evaluation(
        self,
        eval_id: str,
        model_id: str,
        criteria: list[dict[str, Any]],
        dataset: str = "",
    ) -> dict:
        """Create a new evaluation with criteria.

        Parameters
        ----------
        eval_id : str
            Unique evaluation identifier.
        model_id : str
            Identifier of the model being evaluated.
        criteria : list[dict]
            Each dict must have ``name`` and ``weight``; ``metric`` is optional.
        dataset : str
            Name of the dataset used for evaluation.

        Returns
        -------
        dict with eval_id, model_id, dataset, criteria list, status.

        Raises
        ------
        ValueError
            If eval_id already exists or criteria are invalid.
        """
        if not eval_id:
            raise ValueError("eval_id must not be empty")
        if not model_id:
            raise ValueError("model_id must not be empty")
        if not criteria:
            raise ValueError("criteria must not be empty")

        for c in criteria:
            if "name" not in c:
                raise ValueError("each criterion must have a 'name'")
            if "weight" not in c:
                raise ValueError(f"criterion '{c.get('name', '?')}' missing 'weight'")
            if c["weight"] < 0:
                raise ValueError(f"criterion '{c['name']}' weight must be >= 0")

        now = time.time()

        with self._lock:
            # Check uniqueness
            existing = self._conn.execute(
                "SELECT eval_id FROM sylion_evaluations WHERE eval_id = ?",
                (eval_id,),
            ).fetchone()
            if existing:
                raise ValueError(f"eval_id '{eval_id}' already exists")

            self._conn.execute(
                "INSERT INTO sylion_evaluations "
                "(eval_id, model_id, dataset, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'open', ?, ?)",
                (eval_id, model_id, dataset, now, now),
            )

            for c in criteria:
                self._conn.execute(
                    "INSERT INTO sylion_evaluation_criteria "
                    "(eval_id, name, weight, metric) VALUES (?, ?, ?, ?)",
                    (eval_id, c["name"], c["weight"], c.get("metric", "")),
                )

            self._conn.commit()

        self._emit("evaluation.created", {
            "eval_id": eval_id,
            "model_id": model_id,
            "dataset": dataset,
            "criteria_count": len(criteria),
        })
        log.info("created evaluation %s for model %s with %d criteria",
                 eval_id, model_id, len(criteria))

        return self.get_evaluation(eval_id)

    # ------------------------------------------------------------------
    # Record result
    # ------------------------------------------------------------------

    def record_result(
        self,
        eval_id: str,
        criterion_name: str,
        score: float,
        details: str | dict | None = None,
    ) -> dict:
        """Record a criterion result for an evaluation.

        Parameters
        ----------
        eval_id : str
            Evaluation identifier.
        criterion_name : str
            Name of the criterion.
        score : float
            Numeric score (typically 0-1 or 0-100).
        details : str | dict | None
            Optional details about this result.

        Returns
        -------
        dict with the recorded result.

        Raises
        ------
        ValueError
            If evaluation or criterion not found.
        """
        now = time.time()
        details_str = ""
        if isinstance(details, dict):
            details_str = json.dumps(details, default=str)
        elif details is not None:
            details_str = str(details)

        with self._lock:
            ev = self._conn.execute(
                "SELECT eval_id, status FROM sylion_evaluations WHERE eval_id = ?",
                (eval_id,),
            ).fetchone()
            if not ev:
                raise ValueError(f"evaluation '{eval_id}' not found")
            if ev["status"] == "closed":
                raise ValueError(f"evaluation '{eval_id}' is closed")

            crit = self._conn.execute(
                "SELECT id FROM sylion_evaluation_criteria "
                "WHERE eval_id = ? AND name = ?",
                (eval_id, criterion_name),
            ).fetchone()
            if not crit:
                raise ValueError(
                    f"criterion '{criterion_name}' not found in evaluation '{eval_id}'"
                )

            self._conn.execute(
                "UPDATE sylion_evaluation_criteria "
                "SET score = ?, details = ?, recorded_at = ? "
                "WHERE eval_id = ? AND name = ?",
                (score, details_str, now, eval_id, criterion_name),
            )
            self._conn.execute(
                "UPDATE sylion_evaluations SET updated_at = ? WHERE eval_id = ?",
                (now, eval_id),
            )
            self._conn.commit()

        self._emit("evaluation.result_recorded", {
            "eval_id": eval_id,
            "criterion": criterion_name,
            "score": score,
        })
        log.info("recorded result for %s/%s: score=%.4f", eval_id, criterion_name, score)

        return {"eval_id": eval_id, "criterion": criterion_name,
                "score": score, "recorded_at": now}

    # ------------------------------------------------------------------
    # Get evaluation
    # ------------------------------------------------------------------

    def get_evaluation(self, eval_id: str) -> dict | None:
        """Retrieve an evaluation with all its criteria and results."""
        row = self._conn.execute(
            "SELECT * FROM sylion_evaluations WHERE eval_id = ?",
            (eval_id,),
        ).fetchone()
        if not row:
            return None

        criteria_rows = self._conn.execute(
            "SELECT * FROM sylion_evaluation_criteria WHERE eval_id = ? "
            "ORDER BY id",
            (eval_id,),
        ).fetchall()

        criteria = []
        for cr in criteria_rows:
            c = {
                "name": cr["name"],
                "weight": cr["weight"],
                "metric": cr["metric"],
            }
            if cr["score"] is not None:
                c["score"] = cr["score"]
            if cr["details"] is not None:
                try:
                    c["details"] = json.loads(cr["details"])
                except (json.JSONDecodeError, TypeError):
                    c["details"] = cr["details"]
            if cr["recorded_at"] is not None:
                c["recorded_at"] = cr["recorded_at"]
            criteria.append(c)

        return {
            "eval_id": row["eval_id"],
            "model_id": row["model_id"],
            "dataset": row["dataset"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "criteria": criteria,
        }

    # ------------------------------------------------------------------
    # List evaluations
    # ------------------------------------------------------------------

    def list_evaluations(
        self,
        model_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List evaluations, optionally filtered by model_id and/or status."""
        q = "SELECT eval_id FROM sylion_evaluations WHERE 1=1"
        params: list[Any] = []
        if model_id is not None:
            q += " AND model_id = ?"
            params.append(model_id)
        if status is not None:
            q += " AND status = ?"
            params.append(status)
        q += " ORDER BY created_at DESC"

        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            ev = self.get_evaluation(r["eval_id"])
            if ev is not None:
                results.append(ev)
        return results

    # ------------------------------------------------------------------
    # Compute weighted score
    # ------------------------------------------------------------------

    def compute_score(self, eval_id: str) -> dict:
        """Compute weighted average score for an evaluation.

        Returns
        -------
        dict with eval_id, weighted_score, total_weight, scored_criteria,
        total_criteria, per_criterion breakdown.

        Raises
        ------
        ValueError
            If evaluation not found.
        """
        ev = self.get_evaluation(eval_id)
        if ev is None:
            raise ValueError(f"evaluation '{eval_id}' not found")

        total_weight = 0.0
        weighted_sum = 0.0
        scored = 0
        per_criterion: list[dict] = []

        for c in ev["criteria"]:
            w = c["weight"]
            total_weight += w
            entry: dict[str, Any] = {"name": c["name"], "weight": w}
            if "score" in c:
                weighted_sum += c["score"] * w
                scored += 1
                entry["score"] = c["score"]
                entry["weighted"] = c["score"] * w
            else:
                entry["score"] = None
                entry["weighted"] = None
            per_criterion.append(entry)

        weighted_score = (
            round(weighted_sum / total_weight, 6) if total_weight > 0 else 0.0
        )

        return {
            "eval_id": eval_id,
            "model_id": ev["model_id"],
            "weighted_score": weighted_score,
            "total_weight": total_weight,
            "scored_criteria": scored,
            "total_criteria": len(ev["criteria"]),
            "per_criterion": per_criterion,
        }

    # ------------------------------------------------------------------
    # Compare models
    # ------------------------------------------------------------------

    def compare_models(self, eval_ids: list[str]) -> dict:
        """Compare evaluations side by side.

        Returns
        -------
        dict with evaluations list (each with computed score), winner, and
        ranking sorted by weighted_score descending.
        """
        if not eval_ids:
            raise ValueError("eval_ids must not be empty")

        comparisons = []
        for eid in eval_ids:
            ev = self.get_evaluation(eid)
            if ev is None:
                raise ValueError(f"evaluation '{eid}' not found")
            score_data = self.compute_score(eid)
            comparisons.append({
                "eval_id": eid,
                "model_id": ev["model_id"],
                "dataset": ev["dataset"],
                "status": ev["status"],
                "weighted_score": score_data["weighted_score"],
                "scored_criteria": score_data["scored_criteria"],
                "total_criteria": score_data["total_criteria"],
                "criteria": ev["criteria"],
            })

        # Rank by weighted_score descending
        ranked = sorted(comparisons, key=lambda x: x["weighted_score"], reverse=True)
        for i, entry in enumerate(ranked):
            entry["rank"] = i + 1

        winner = ranked[0]["model_id"] if ranked else None

        return {
            "winner": winner,
            "ranking": ranked,
            "evaluations": comparisons,
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Aggregate statistics: total evaluations, average score, by model."""
        rows = self._conn.execute(
            "SELECT eval_id FROM sylion_evaluations"
        ).fetchall()

        total = len(rows)
        scores: list[float] = []
        by_model: dict[str, dict[str, Any]] = {}

        for r in rows:
            eid = r["eval_id"]
            try:
                score_data = self.compute_score(eid)
            except ValueError:
                continue
            ws = score_data["weighted_score"]
            if score_data["scored_criteria"] > 0:
                scores.append(ws)

            ev = self.get_evaluation(eid)
            if ev is None:
                continue
            mid = ev["model_id"]
            if mid not in by_model:
                by_model[mid] = {"count": 0, "scores": []}
            by_model[mid]["count"] += 1
            if score_data["scored_criteria"] > 0:
                by_model[mid]["scores"].append(ws)

        avg_score = round(sum(scores) / len(scores), 6) if scores else 0.0

        # Summarize by model
        model_breakdown: dict[str, dict] = {}
        for mid, data in by_model.items():
            model_breakdown[mid] = {
                "count": data["count"],
                "avg_score": (
                    round(sum(data["scores"]) / len(data["scores"]), 6)
                    if data["scores"] else 0.0
                ),
                "min_score": min(data["scores"]) if data["scores"] else None,
                "max_score": max(data["scores"]) if data["scores"] else None,
            }

        return {
            "total_evaluations": total,
            "avg_score": avg_score,
            "scored_evaluations": len(scores),
            "by_model": model_breakdown,
        }

    # ------------------------------------------------------------------
    # Close evaluation
    # ------------------------------------------------------------------

    def close_evaluation(self, eval_id: str) -> dict:
        """Close an evaluation so no more results can be recorded."""
        now = time.time()
        with self._lock:
            updated = self._conn.execute(
                "UPDATE sylion_evaluations SET status = 'closed', updated_at = ? "
                "WHERE eval_id = ? AND status = 'open'",
                (now, eval_id),
            ).rowcount
            self._conn.commit()

        if not updated:
            raise ValueError(f"evaluation '{eval_id}' not found or already closed")

        self._emit("evaluation.closed", {"eval_id": eval_id})
        log.info("closed evaluation %s", eval_id)
        return {"eval_id": eval_id, "status": "closed", "closed_at": now}

    # ------------------------------------------------------------------
    # Delete evaluation
    # ------------------------------------------------------------------

    def delete_evaluation(self, eval_id: str) -> bool:
        """Delete an evaluation and all its criteria/results."""
        with self._lock:
            ev = self._conn.execute(
                "SELECT eval_id FROM sylion_evaluations WHERE eval_id = ?",
                (eval_id,),
            ).fetchone()
            if not ev:
                return False

            self._conn.execute(
                "DELETE FROM sylion_evaluation_criteria WHERE eval_id = ?",
                (eval_id,),
            )
            self._conn.execute(
                "DELETE FROM sylion_evaluations WHERE eval_id = ?",
                (eval_id,),
            )
            self._conn.commit()

        self._emit("evaluation.deleted", {"eval_id": eval_id})
        log.info("deleted evaluation %s", eval_id)
        return True

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="cognitive.evaluation_framework",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: EvaluationFramework | None = None


def get_evaluation_framework(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> EvaluationFramework:
    """Get or create the global EvaluationFramework singleton."""
    global _instance
    if _instance is None:
        _instance = EvaluationFramework(db_path, event_bus)
    return _instance
