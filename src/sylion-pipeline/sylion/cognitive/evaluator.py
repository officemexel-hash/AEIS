"""
SYLION Cognitive -- Evaluator

Weighted multi-criteria evaluation framework. Records evaluations against
arbitrary targets (plans, ideas, tasks, code, etc.) with weighted scoring
across configurable criteria.

Tables:
  evaluation_criteria, evaluations, evaluation_results

Singleton: get_evaluator() / reset_evaluator()
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.cognitive.evaluator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EVAL_STATUSES = ("pending", "in_progress", "completed")


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class Evaluator:
    """Multi-criteria evaluation with weighted scoring.

    Thread-safe. SQLite-backed. Emits events on mutations.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS evaluation_criteria (
                criteria_id  TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                weight       REAL NOT NULL DEFAULT 1.0,
                rubric       TEXT NOT NULL DEFAULT '{}',
                created_at   REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evaluations (
                evaluation_id  TEXT PRIMARY KEY,
                target_id      TEXT NOT NULL DEFAULT '',
                target_type    TEXT NOT NULL DEFAULT '',
                status         TEXT NOT NULL DEFAULT 'pending',
                weighted_score REAL,
                created_at     REAL NOT NULL,
                completed_at   REAL
            );
            CREATE TABLE IF NOT EXISTS evaluation_results (
                result_id      TEXT PRIMARY KEY,
                evaluation_id  TEXT NOT NULL,
                criteria_id    TEXT NOT NULL,
                score          REAL NOT NULL DEFAULT 0.0,
                notes          TEXT NOT NULL DEFAULT '',
                scored_at      REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_criteria_name ON evaluation_criteria(name);
            CREATE INDEX IF NOT EXISTS idx_eval_target ON evaluations(target_type, target_id);
            CREATE INDEX IF NOT EXISTS idx_eval_status ON evaluations(status);
            CREATE INDEX IF NOT EXISTS idx_results_eval ON evaluation_results(evaluation_id);
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.evaluator",
            ))

    # ------------------------------------------------------------------
    # Criteria CRUD
    # ------------------------------------------------------------------

    def create_criteria(self, name: str, description: str = "",
                        weight: float = 1.0,
                        rubric: dict | None = None) -> dict:
        """Create a new evaluation criterion. Returns criteria dict."""
        if not name:
            raise ValueError("name must not be empty")
        if weight < 0:
            raise ValueError("weight must be non-negative")

        criteria_id = self._uid()
        now = time.time()
        import json
        rubric_json = json.dumps(rubric or {})

        with self._lock:
            self._conn.execute(
                "INSERT INTO evaluation_criteria "
                "(criteria_id, name, description, weight, rubric, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (criteria_id, name, description, weight, rubric_json, now),
            )
            self._conn.commit()

        self._emit("criteria_created", {
            "criteria_id": criteria_id, "name": name, "weight": weight,
        })
        log.info("create_criteria %s: %s (weight=%.2f)",
                 criteria_id[:12], name, weight)
        return self._get_criteria_row(criteria_id)

    def update_criteria(self, criteria_id: str, name: str | None = None,
                        description: str | None = None,
                        weight: float | None = None,
                        rubric: dict | None = None) -> dict | None:
        """Update a criterion. Returns updated dict or None."""
        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if description is not None:
            sets.append("description = ?")
            params.append(description)
        if weight is not None:
            if weight < 0:
                raise ValueError("weight must be non-negative")
            sets.append("weight = ?")
            params.append(weight)
        if rubric is not None:
            import json
            sets.append("rubric = ?")
            params.append(json.dumps(rubric))

        if not sets:
            return self._get_criteria_row(criteria_id)

        params.append(criteria_id)
        with self._lock:
            n = self._conn.execute(
                f"UPDATE evaluation_criteria SET {', '.join(sets)} "
                f"WHERE criteria_id = ?",
                params,
            ).rowcount
            self._conn.commit()
            if not n:
                return None

        return self._get_criteria_row(criteria_id)

    def delete_criteria(self, criteria_id: str) -> bool:
        """Delete a criterion. Returns True if deleted."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM evaluation_criteria WHERE criteria_id = ?",
                (criteria_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def list_criteria(self) -> list[dict]:
        """List all criteria."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evaluation_criteria ORDER BY created_at",
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def _get_criteria_row(self, criteria_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM evaluation_criteria WHERE criteria_id = ?",
            (criteria_id,),
        ).fetchone()
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Evaluations
    # ------------------------------------------------------------------

    def create_evaluation(self, target_id: str, target_type: str,
                          criteria_ids: list[str] | None = None) -> dict:
        """Create a new evaluation for a target. Returns evaluation dict."""
        evaluation_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute(
                "INSERT INTO evaluations "
                "(evaluation_id, target_id, target_type, status, "
                "weighted_score, created_at, completed_at) "
                "VALUES (?, ?, ?, 'pending', NULL, ?, NULL)",
                (evaluation_id, target_id, target_type, now),
            )

            for cid in (criteria_ids or []):
                self._conn.execute(
                    "INSERT INTO evaluation_results "
                    "(result_id, evaluation_id, criteria_id, score, notes, scored_at) "
                    "VALUES (?, ?, ?, 0.0, '', ?)",
                    (self._uid(), evaluation_id, cid, now),
                )
            self._conn.commit()

        self._emit("evaluation_created", {
            "evaluation_id": evaluation_id,
            "target_id": target_id,
            "target_type": target_type,
        })
        log.info("create_evaluation %s for %s/%s",
                 evaluation_id[:12], target_type, target_id[:12])
        return self.get_evaluation(evaluation_id)

    def evaluate(self, target_type: str, target_id: str,
                 score: float, verdict: str,
                 details: dict | None = None) -> dict:
        """Record a completed single-score evaluation.

        This is the flat API used by the REST compatibility route. It stores
        the aggregate score directly and keeps the verdict/details on a single
        result row so the richer criteria-based evaluator remains intact.
        """
        if score < 0:
            raise ValueError("score must be non-negative")

        evaluation_id = self._uid()
        result_id = self._uid()
        now = time.time()
        import json

        notes = json.dumps({
            "verdict": verdict,
            "details": details or {},
        }, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO evaluations "
                "(evaluation_id, target_id, target_type, status, "
                "weighted_score, created_at, completed_at) "
                "VALUES (?, ?, ?, 'completed', ?, ?, ?)",
                (evaluation_id, target_id, target_type, float(score), now, now),
            )
            self._conn.execute(
                "INSERT INTO evaluation_results "
                "(result_id, evaluation_id, criteria_id, score, notes, scored_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (result_id, evaluation_id, "direct", float(score), notes, now),
            )
            self._conn.commit()

        self._emit("evaluation_completed", {
            "evaluation_id": evaluation_id,
            "target_id": target_id,
            "target_type": target_type,
            "weighted_score": float(score),
            "verdict": verdict,
        })
        result = self.get_evaluation(evaluation_id) or {}
        result["score"] = float(score)
        result["verdict"] = verdict
        result["details"] = details or {}
        return result

    def score_criterion(self, evaluation_id: str, criteria_id: str,
                        score: float, notes: str = "") -> dict | None:
        """Score a single criterion within an evaluation. Returns result dict."""
        if score < 0:
            raise ValueError("score must be non-negative")

        now = time.time()
        with self._lock:
            ev = self._conn.execute(
                "SELECT evaluation_id FROM evaluations WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchone()
            if not ev:
                return None

            existing = self._conn.execute(
                "SELECT result_id FROM evaluation_results "
                "WHERE evaluation_id = ? AND criteria_id = ?",
                (evaluation_id, criteria_id),
            ).fetchone()

            if existing:
                self._conn.execute(
                    "UPDATE evaluation_results SET score = ?, notes = ?, "
                    "scored_at = ? WHERE result_id = ?",
                    (score, notes, now, existing["result_id"]),
                )
            else:
                self._conn.execute(
                    "INSERT INTO evaluation_results "
                    "(result_id, evaluation_id, criteria_id, score, notes, scored_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (self._uid(), evaluation_id, criteria_id, score, notes, now),
                )

            # Update status to in_progress if still pending
            self._conn.execute(
                "UPDATE evaluations SET status = 'in_progress' "
                "WHERE evaluation_id = ? AND status = 'pending'",
                (evaluation_id,),
            )
            self._conn.commit()

        return {"evaluation_id": evaluation_id, "criteria_id": criteria_id,
                "score": score, "notes": notes}

    def complete_evaluation(self, evaluation_id: str) -> dict | None:
        """Complete an evaluation: compute weighted score. Returns evaluation dict."""
        with self._lock:
            ev = self._conn.execute(
                "SELECT * FROM evaluations WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchone()
            if not ev:
                return None

            now = time.time()

            # Compute weighted score
            results = self._conn.execute(
                "SELECT er.criteria_id, er.score, ec.weight "
                "FROM evaluation_results er "
                "JOIN evaluation_criteria ec ON er.criteria_id = ec.criteria_id "
                "WHERE er.evaluation_id = ?",
                (evaluation_id,),
            ).fetchall()

            total_weight = sum(r["weight"] for r in results) or 1.0
            weighted_sum = sum(r["score"] * r["weight"] for r in results)
            weighted_score = round(weighted_sum / total_weight, 4)

            self._conn.execute(
                "UPDATE evaluations SET status = 'completed', "
                "weighted_score = ?, completed_at = ? WHERE evaluation_id = ?",
                (weighted_score, now, evaluation_id),
            )
            self._conn.commit()

        self._emit("evaluation_completed", {
            "evaluation_id": evaluation_id,
            "weighted_score": weighted_score,
        })
        log.info("complete_evaluation %s: weighted_score=%.4f",
                 evaluation_id[:12], weighted_score)
        return self.get_evaluation(evaluation_id)

    def get_evaluation(self, evaluation_id: str) -> dict | None:
        """Retrieve an evaluation with its results."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM evaluations WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchone()
            if not row:
                return None

            result_rows = self._conn.execute(
                "SELECT * FROM evaluation_results WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchall()

        ev = dict(row)
        ev["results"] = [dict(r) for r in result_rows]
        return ev

    def list_evaluations(self, target_id: str | None = None,
                         status: str | None = None,
                         limit: int = 100) -> list[dict]:
        """List evaluations with optional filters."""
        with self._lock:
            clauses: list[str] = []
            params: list[Any] = []

            if target_id is not None:
                clauses.append("target_id = ?")
                params.append(target_id)
            if status is not None:
                if status not in VALID_EVAL_STATUSES:
                    raise ValueError(
                        f"Invalid status '{status}'. "
                        f"Must be one of {VALID_EVAL_STATUSES}"
                    )
                clauses.append("status = ?")
                params.append(status)

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM evaluations{where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        return [self.get_evaluation(r["evaluation_id"]) for r in rows]

    def get_evaluation_summary(self, evaluation_id: str) -> dict | None:
        """Get a summary of an evaluation with per-criterion breakdown."""
        ev = self.get_evaluation(evaluation_id)
        if not ev:
            return None

        import json
        criteria_map = {c["criteria_id"]: c for c in self.list_criteria()}

        breakdown = []
        for result in ev.get("results", []):
            cid = result["criteria_id"]
            crit = criteria_map.get(cid, {})
            breakdown.append({
                "criteria_id": cid,
                "name": crit.get("name", "unknown"),
                "weight": crit.get("weight", 1.0),
                "score": result["score"],
                "notes": result["notes"],
            })

        return {
            "evaluation_id": evaluation_id,
            "target_id": ev["target_id"],
            "target_type": ev["target_type"],
            "status": ev["status"],
            "weighted_score": ev["weighted_score"],
            "breakdown": breakdown,
            "created_at": ev["created_at"],
            "completed_at": ev["completed_at"],
        }

    # ------------------------------------------------------------------
    # Target queries (workspace vocabulary)
    # ------------------------------------------------------------------

    def query_by_target(self, target_type: str, target_id: str,
                        limit: int = 100) -> list[dict]:
        """Return evaluations matching a target (type, id)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM evaluations "
                "WHERE target_type = ? AND target_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (target_type, target_id, limit),
            ).fetchall()
        return [self.get_evaluation(r["evaluation_id"]) for r in rows]

    def get_average_score(self, target_type: str) -> dict:
        """Aggregate weighted_score across completed evaluations of a type."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT weighted_score FROM evaluations "
                "WHERE target_type = ? AND status = 'completed' "
                "AND weighted_score IS NOT NULL",
                (target_type,),
            ).fetchall()
        scores = [r["weighted_score"] for r in rows
                  if r["weighted_score"] is not None]
        avg = sum(scores) / len(scores) if scores else 0.0
        return {
            "target_type": target_type,
            "evaluations_count": len(scores),
            "average_score": avg,
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        import json
        d = dict(row)
        if "rubric" in d and isinstance(d["rubric"], str):
            d["rubric"] = json.loads(d["rubric"])
        return d


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_evaluator: Evaluator | None = None


def get_evaluator(db_path: str | Path | None = None,
                  event_bus: EventBus | None = None) -> Evaluator:
    global _evaluator
    if _evaluator is None:
        _evaluator = Evaluator(db_path, event_bus)
    return _evaluator


def reset_evaluator(db_path: str | Path | None = None,
                    event_bus: EventBus | None = None) -> Evaluator:
    global _evaluator
    _evaluator = Evaluator(db_path, event_bus)
    return _evaluator
