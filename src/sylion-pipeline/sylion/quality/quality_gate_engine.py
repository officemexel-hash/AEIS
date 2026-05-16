"""
SYLION Quality -- Quality Gate Engine

Quality gate management for module transitions.
Defines configurable quality gates (entry, exit, transition, deployment)
that modules must pass before moving between lifecycle stages.

SQLite-backed, thread-safe, event-emitting.
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

log = logging.getLogger("sylion.quality.quality_gate_engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_GATE_TYPES = ("entry", "exit", "transition", "deployment")
VALID_RESULTS = ("pass", "fail", "warning", "error")

DEFAULT_CRITERIA = {
    "test_coverage": {"operator": ">=", "value": 0.8},
    "no_critical_violations": {"operator": "==", "value": True},
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QualityGate:
    """A single quality gate definition."""
    gate_id: str = ""
    name: str = ""
    description: str = ""
    gate_type: str = "entry"
    criteria: str = ""          # JSON string of criteria dict
    enabled: int = 1
    created_at: float = 0.0

    def __post_init__(self):
        if not self.gate_id:
            self.gate_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()
        if not self.criteria:
            self.criteria = json.dumps(DEFAULT_CRITERIA)


@dataclass
class GateEvaluation:
    """Result of evaluating a gate against a module."""
    evaluation_id: str = ""
    gate_id: str = ""
    module_id: str = ""
    result: str = ""            # pass | fail | warning | error
    score: float = 0.0
    details: str = ""           # JSON string with evaluation details
    evaluated_at: float = 0.0

    def __post_init__(self):
        if not self.evaluation_id:
            self.evaluation_id = uuid.uuid4().hex
        if not self.evaluated_at:
            self.evaluated_at = time.time()


# ---------------------------------------------------------------------------
# QualityGateEngine
# ---------------------------------------------------------------------------

class QualityGateEngine:
    """Quality gate management for module transitions.

    Thread-safe. SQLite-backed. Emits events on evaluation.
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

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS quality_gates (
                gate_id      TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                gate_type    TEXT NOT NULL DEFAULT 'entry',
                criteria     TEXT NOT NULL DEFAULT '',
                enabled      INTEGER NOT NULL DEFAULT 1,
                created_at   REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS gate_evaluations (
                evaluation_id TEXT PRIMARY KEY,
                gate_id       TEXT NOT NULL,
                module_id     TEXT NOT NULL DEFAULT '',
                result        TEXT NOT NULL,
                score         REAL NOT NULL DEFAULT 0.0,
                details       TEXT NOT NULL DEFAULT '',
                evaluated_at  REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qg_type ON quality_gates(gate_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qg_enabled ON quality_gates(enabled)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ge_gate ON gate_evaluations(gate_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ge_module ON gate_evaluations(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ge_result ON gate_evaluations(result)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ge_ts ON gate_evaluations(evaluated_at)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Gate CRUD
    # ------------------------------------------------------------------

    def create_gate(self, name: str, gate_type: str,
                    description: str = "",
                    criteria: dict | None = None) -> dict:
        """Create a new quality gate. Returns gate dict."""
        if gate_type not in VALID_GATE_TYPES:
            raise ValueError(
                f"Invalid gate_type '{gate_type}'. Must be one of {VALID_GATE_TYPES}"
            )

        gate = QualityGate(
            name=name,
            gate_type=gate_type,
            description=description,
            criteria=json.dumps(criteria if criteria is not None else DEFAULT_CRITERIA),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO quality_gates
                (gate_id, name, description, gate_type, criteria, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                gate.gate_id, gate.name, gate.description,
                gate.gate_type, gate.criteria, gate.enabled, gate.created_at,
            ))
            self._conn.commit()

        log.info("created quality gate %s: %s (type=%s)", gate.gate_id, name, gate_type)
        return {
            "gate_id": gate.gate_id,
            "name": gate.name,
            "gate_type": gate.gate_type,
            "description": gate.description,
            "criteria": gate.criteria,
            "enabled": gate.enabled,
            "created_at": gate.created_at,
        }

    def get_gate(self, gate_id: str) -> dict | None:
        """Retrieve a single quality gate by ID."""
        row = self._conn.execute(
            "SELECT * FROM quality_gates WHERE gate_id = ?", (gate_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_gates(self, gate_type: str | None = None,
                   enabled: bool | None = None) -> list[dict]:
        """List quality gates with optional filters."""
        q = "SELECT * FROM quality_gates WHERE 1=1"
        params: list[Any] = []
        if gate_type is not None:
            q += " AND gate_type = ?"
            params.append(gate_type)
        if enabled is not None:
            q += " AND enabled = ?"
            params.append(1 if enabled else 0)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def update_gate(self, gate_id: str, name: str | None = None,
                    criteria: dict | None = None,
                    enabled: bool | None = None) -> dict:
        """Update a quality gate. Returns updated dict or error."""
        existing = self.get_gate(gate_id)
        if existing is None:
            return {"updated": False, "message": f"Gate {gate_id} not found"}

        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if criteria is not None:
            sets.append("criteria = ?")
            params.append(json.dumps(criteria))
        if enabled is not None:
            sets.append("enabled = ?")
            params.append(1 if enabled else 0)

        if not sets:
            return {"updated": False, "message": "No fields to update"}

        params.append(gate_id)
        with self._lock:
            self._conn.execute(
                f"UPDATE quality_gates SET {', '.join(sets)} WHERE gate_id = ?",
                params,
            )
            self._conn.commit()

        updated = self.get_gate(gate_id)
        log.info("updated quality gate %s", gate_id)
        return {"updated": True, **updated}

    def delete_gate(self, gate_id: str) -> dict:
        """Delete a quality gate. Returns deletion status."""
        existing = self.get_gate(gate_id)
        if existing is None:
            return {"deleted": False, "message": f"Gate {gate_id} not found"}

        with self._lock:
            self._conn.execute(
                "DELETE FROM gate_evaluations WHERE gate_id = ?", (gate_id,),
            )
            self._conn.execute(
                "DELETE FROM quality_gates WHERE gate_id = ?", (gate_id,),
            )
            self._conn.commit()

        log.info("deleted quality gate %s and its evaluations", gate_id)
        return {"deleted": True, "gate_id": gate_id}

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_gate(self, gate_id: str, module_id: str,
                      context: dict | None = None) -> dict:
        """Evaluate a quality gate against a module.

        The context dict provides actual metric values (e.g. test_coverage).
        Criteria are compared against context to produce a score and result.

        Returns evaluation dict with score, result, and details.
        """
        gate = self.get_gate(gate_id)
        if gate is None:
            return {"evaluated": False, "message": f"Gate {gate_id} not found"}

        if not gate["enabled"]:
            evaluation = GateEvaluation(
                gate_id=gate_id,
                module_id=module_id,
                result="warning",
                score=0.0,
                details=json.dumps({"message": "Gate is disabled, skipped"}),
            )
            self._store_evaluation(evaluation)
            return {
                "evaluated": True,
                "evaluation_id": evaluation.evaluation_id,
                "gate_id": gate_id,
                "module_id": module_id,
                "result": "warning",
                "score": 0.0,
                "message": "Gate is disabled, skipped",
            }

        criteria = json.loads(gate["criteria"])
        ctx = context or {}

        details, score = self._evaluate_criteria(criteria, ctx)

        # Determine result from score
        if score >= 1.0:
            result = "pass"
        elif score >= 0.5:
            result = "warning"
        else:
            result = "fail"

        evaluation = GateEvaluation(
            gate_id=gate_id,
            module_id=module_id,
            result=result,
            score=round(score, 4),
            details=json.dumps(details),
        )

        self._store_evaluation(evaluation)

        self._emit("quality_gate.evaluated", {
            "evaluation_id": evaluation.evaluation_id,
            "gate_id": gate_id,
            "module_id": module_id,
            "result": result,
            "score": round(score, 4),
        })

        log.info("evaluated gate %s for module %s: result=%s score=%.4f",
                 gate_id, module_id, result, score)

        return {
            "evaluated": True,
            "evaluation_id": evaluation.evaluation_id,
            "gate_id": gate_id,
            "module_id": module_id,
            "result": result,
            "score": round(score, 4),
            "details": details,
        }

    def _evaluate_criteria(self, criteria: dict,
                           context: dict) -> tuple[dict, float]:
        """Evaluate criteria against context. Returns (details, score)."""
        details: dict[str, Any] = {}
        total_checks = 0
        passed_checks = 0

        for metric_name, rule in criteria.items():
            total_checks += 1
            operator = rule.get("operator", ">=")
            threshold = rule.get("value")

            actual = context.get(metric_name)

            if actual is None:
                details[metric_name] = {
                    "status": "missing",
                    "operator": operator,
                    "threshold": threshold,
                    "actual": None,
                    "check_passed": False,
                }
                continue

            check_passed = self._compare(actual, operator, threshold)
            if check_passed:
                passed_checks += 1

            details[metric_name] = {
                "status": "checked",
                "operator": operator,
                "threshold": threshold,
                "actual": actual,
                "check_passed": check_passed,
            }

        score = passed_checks / total_checks if total_checks > 0 else 0.0
        return details, score

    @staticmethod
    def _compare(actual: Any, operator: str, threshold: Any) -> bool:
        """Compare actual value against threshold using operator."""
        try:
            if operator == ">=":
                return actual >= threshold
            elif operator == ">":
                return actual > threshold
            elif operator == "<=":
                return actual <= threshold
            elif operator == "<":
                return actual < threshold
            elif operator == "==":
                return actual == threshold
            elif operator == "!=":
                return actual != threshold
            else:
                return False
        except (TypeError, ValueError):
            return False

    def _store_evaluation(self, evaluation: GateEvaluation):
        """Persist an evaluation record."""
        with self._lock:
            self._conn.execute("""
                INSERT INTO gate_evaluations
                (evaluation_id, gate_id, module_id, result, score, details, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                evaluation.evaluation_id, evaluation.gate_id,
                evaluation.module_id, evaluation.result, evaluation.score,
                evaluation.details, evaluation.evaluated_at,
            ))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Evaluation queries
    # ------------------------------------------------------------------

    def get_evaluation(self, evaluation_id: str) -> dict | None:
        """Retrieve a single evaluation by ID."""
        row = self._conn.execute(
            "SELECT * FROM gate_evaluations WHERE evaluation_id = ?",
            (evaluation_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_evaluations(self, gate_id: str | None = None,
                         module_id: str | None = None,
                         result: str | None = None,
                         limit: int = 100) -> list[dict]:
        """List evaluations with optional filters."""
        if result is not None and result not in VALID_RESULTS:
            raise ValueError(
                f"Invalid result '{result}'. Must be one of {VALID_RESULTS}"
            )

        q = "SELECT * FROM gate_evaluations WHERE 1=1"
        params: list[Any] = []
        if gate_id is not None:
            q += " AND gate_id = ?"
            params.append(gate_id)
        if module_id is not None:
            q += " AND module_id = ?"
            params.append(module_id)
        if result is not None:
            q += " AND result = ?"
            params.append(result)
        q += " ORDER BY evaluated_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get aggregate statistics: counts by gate type and evaluation result."""
        gate_type_counts: dict[str, int] = {}
        for row in self._conn.execute(
            "SELECT gate_type, COUNT(*) as cnt FROM quality_gates GROUP BY gate_type"
        ).fetchall():
            gate_type_counts[row["gate_type"]] = row["cnt"]

        result_counts: dict[str, int] = {}
        for row in self._conn.execute(
            "SELECT result, COUNT(*) as cnt FROM gate_evaluations GROUP BY result"
        ).fetchall():
            result_counts[row["result"]] = row["cnt"]

        total_gates = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM quality_gates"
        ).fetchone()["cnt"]

        total_evaluations = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM gate_evaluations"
        ).fetchone()["cnt"]

        enabled_gates = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM quality_gates WHERE enabled = 1"
        ).fetchone()["cnt"]

        return {
            "total_gates": total_gates,
            "enabled_gates": enabled_gates,
            "total_evaluations": total_evaluations,
            "gates_by_type": gate_type_counts,
            "evaluations_by_result": result_counts,
        }

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="quality.quality_gate_engine",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: QualityGateEngine | None = None


def get_quality_gate_engine(db_path: str | Path | None = None,
                            event_bus: EventBus | None = None) -> QualityGateEngine:
    global _engine
    if _engine is None:
        _engine = QualityGateEngine(db_path=db_path, event_bus=event_bus)
    return _engine


def reset_quality_gate_engine() -> None:
    global _engine
    _engine = None
