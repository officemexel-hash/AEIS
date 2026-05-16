"""
SYLION Quality — Quality Gate

Quality gate management with metric thresholds and evaluation history.
Supports defining gates with metrics/thresholds, evaluating measurements
against them, tracking results over time, and generating regression reports.

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

log = logging.getLogger("sylion.quality.quality_gate")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QualityGateDef:
    """Definition of a quality gate."""
    gate_id: str = ""
    module_id: str = ""
    metrics: str = "{}"          # JSON: {"metric_name": {"type": "gte|min|max|eq", "threshold": value}}
    thresholds: str = "{}"       # JSON: {"metric_name": threshold_value} — shorthand alias
    active: int = 1
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class QualityResult:
    """Result of a quality gate evaluation."""
    result_id: str = ""
    gate_id: str = ""
    measurements: str = "{}"     # JSON: {"metric_name": measured_value}
    passed: int = 0
    details: str = "{}"          # JSON: {"metric_name": {"passed": bool, "value": ..., "threshold": ...}}
    score: float = 0.0           # fraction of metrics that passed
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.result_id:
            self.result_id = uuid.uuid4().hex
        if not self.timestamp:
            self.timestamp = time.time()


# ---------------------------------------------------------------------------
# Comparison operators
# ---------------------------------------------------------------------------

def _compare(metric_type: str, value: Any, threshold: Any) -> bool:
    """Compare a measured value against a threshold using the given operator."""
    try:
        if metric_type == "gte":
            return float(value) >= float(threshold)
        elif metric_type == "min":
            return float(value) >= float(threshold)
        elif metric_type == "max":
            return float(value) <= float(threshold)
        elif metric_type == "lte":
            return float(value) <= float(threshold)
        elif metric_type == "gt":
            return float(value) > float(threshold)
        elif metric_type == "lt":
            return float(value) < float(threshold)
        elif metric_type == "eq":
            return value == threshold
        elif metric_type == "neq":
            return value != threshold
        else:
            # Default: greater-than-or-equal
            return float(value) >= float(threshold)
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------

class QualityGate:
    """Quality gate management with metric thresholds and evaluation history.

    Thread-safe. SQLite-backed. Emits events on define / evaluate.
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
            CREATE TABLE IF NOT EXISTS sylion_quality_gates (
                gate_id     TEXT PRIMARY KEY,
                module_id   TEXT NOT NULL DEFAULT '',
                metrics     TEXT NOT NULL DEFAULT '{}',
                thresholds  TEXT NOT NULL DEFAULT '{}',
                active      INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_quality_results (
                result_id    TEXT PRIMARY KEY,
                gate_id      TEXT NOT NULL,
                measurements TEXT NOT NULL DEFAULT '{}',
                passed       INTEGER NOT NULL DEFAULT 0,
                details      TEXT NOT NULL DEFAULT '{}',
                score        REAL NOT NULL DEFAULT 0.0,
                timestamp    REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qg_module ON sylion_quality_gates(module_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qg_active ON sylion_quality_gates(active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qr_gate ON sylion_quality_results(gate_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qr_ts ON sylion_quality_results(timestamp)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_qr_passed ON sylion_quality_results(passed)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Define gate
    # ------------------------------------------------------------------

    def define_gate(self, gate_id: str, module_id: str = "",
                    metrics: dict[str, Any] | None = None,
                    thresholds: dict[str, Any] | None = None) -> dict:
        """Define a quality gate with metrics and thresholds.

        metrics: {"metric_name": {"type": "gte|max|min|eq", "threshold": value}, ...}
        thresholds: shorthand {"metric_name": threshold_value} — auto-wrapped as {"type": "gte"}

        If both are provided, metrics takes precedence for type info.
        """
        metrics = metrics or {}
        thresholds = thresholds or {}

        # Merge thresholds into metrics if not already specified there
        for name, thr_value in thresholds.items():
            if name not in metrics:
                metrics[name] = {"type": "gte", "threshold": thr_value}
            elif "threshold" not in metrics[name]:
                metrics[name]["threshold"] = thr_value

        metrics_json = json.dumps(metrics, default=str)
        thresholds_json = json.dumps(thresholds, default=str)

        gate = QualityGateDef(
            gate_id=gate_id,
            module_id=module_id,
            metrics=metrics_json,
            thresholds=thresholds_json,
        )

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO sylion_quality_gates
                (gate_id, module_id, metrics, thresholds, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (
                gate.gate_id, gate.module_id, gate.metrics,
                gate.thresholds, gate.created_at,
            ))
            self._conn.commit()

        self._emit("quality_gate.defined", {
            "gate_id": gate_id, "module_id": module_id,
            "metric_count": len(metrics),
        })
        log.info("defined quality gate %s for module %s (%d metrics)",
                 gate_id, module_id, len(metrics))
        return {
            "gate_id": gate_id,
            "module_id": module_id,
            "metrics": metrics,
            "metric_count": len(metrics),
        }

    # ------------------------------------------------------------------
    # Evaluate
    # ------------------------------------------------------------------

    def evaluate(self, gate_id: str, measurements: dict[str, Any]) -> dict:
        """Evaluate measurements against a gate's thresholds.

        Returns evaluation result with per-metric details and overall pass/fail.
        """
        row = self._conn.execute(
            "SELECT * FROM sylion_quality_gates WHERE gate_id = ? AND active = 1",
            (gate_id,),
        ).fetchone()
        if not row:
            return {
                "evaluated": False,
                "message": f"Quality gate '{gate_id}' not found or inactive",
            }

        metrics = json.loads(row["metrics"])
        details: dict[str, dict] = {}
        passed_count = 0
        total_metrics = 0

        for metric_name, metric_cfg in metrics.items():
            total_metrics += 1
            metric_type = metric_cfg.get("type", "gte")
            threshold = metric_cfg.get("threshold")

            measured = measurements.get(metric_name)

            if measured is None:
                details[metric_name] = {
                    "passed": False,
                    "value": None,
                    "threshold": threshold,
                    "message": "metric not measured",
                }
                continue

            ok = _compare(metric_type, measured, threshold)
            if ok:
                passed_count += 1

            details[metric_name] = {
                "passed": ok,
                "value": measured,
                "threshold": threshold,
                "type": metric_type,
            }

        overall_passed = passed_count == total_metrics and total_metrics > 0
        score = passed_count / total_metrics if total_metrics > 0 else 0.0

        result = QualityResult(
            gate_id=gate_id,
            measurements=json.dumps(measurements, default=str),
            passed=1 if overall_passed else 0,
            details=json.dumps(details),
            score=score,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO sylion_quality_results
                (result_id, gate_id, measurements, passed, details, score, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.result_id, result.gate_id, result.measurements,
                result.passed, result.details, result.score, result.timestamp,
            ))
            self._conn.commit()

        eval_result = {
            "evaluated": True,
            "result_id": result.result_id,
            "gate_id": gate_id,
            "passed": overall_passed,
            "score": round(score, 4),
            "passed_metrics": passed_count,
            "total_metrics": total_metrics,
            "details": details,
        }

        self._emit("quality_gate.evaluated", {
            "gate_id": gate_id, "passed": overall_passed,
            "score": round(score, 4),
        })
        log.info("evaluated gate %s: passed=%s score=%.4f (%d/%d)",
                 gate_id, overall_passed, score, passed_count, total_metrics)
        return eval_result

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_gate(self, gate_id: str) -> dict | None:
        """Retrieve a gate definition by ID."""
        row = self._conn.execute(
            "SELECT * FROM sylion_quality_gates WHERE gate_id = ?", (gate_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["metrics"] = json.loads(result["metrics"])
        result["thresholds"] = json.loads(result["thresholds"])
        return result

    def list_gates(self, module_id: str | None = None,
                   active_only: bool = True) -> list[dict]:
        """List quality gates, optionally filtered by module."""
        q = "SELECT * FROM sylion_quality_gates WHERE 1=1"
        params: list[Any] = []
        if module_id:
            q += " AND module_id = ?"
            params.append(module_id)
        if active_only:
            q += " AND active = 1"
        q += " ORDER BY created_at DESC"
        rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["metrics"] = json.loads(d["metrics"])
            d["thresholds"] = json.loads(d["thresholds"])
            results.append(d)
        return results

    def get_results(self, gate_id: str, limit: int = 20) -> list[dict]:
        """Get evaluation history for a gate."""
        rows = self._conn.execute(
            "SELECT * FROM sylion_quality_results WHERE gate_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (gate_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["measurements"] = json.loads(d["measurements"])
            d["details"] = json.loads(d["details"])
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Regression report
    # ------------------------------------------------------------------

    def get_regression_report(self, module_id: str) -> dict:
        """Check for regressions across all gates for a module.

        Compares the most recent evaluation to the best historical score
        for each gate. Flags gates where the latest score dropped.
        """
        gates = self.list_gates(module_id=module_id, active_only=True)
        if not gates:
            return {
                "module_id": module_id,
                "regressions": [],
                "regression_count": 0,
                "gates_checked": 0,
            }

        regressions = []
        for gate in gates:
            gate_id = gate["gate_id"]
            rows = self._conn.execute(
                "SELECT result_id, score, passed, timestamp "
                "FROM sylion_quality_results WHERE gate_id = ? "
                "ORDER BY timestamp ASC",
                (gate_id,),
            ).fetchall()

            if len(rows) < 2:
                continue

            scores = [r["score"] for r in rows]
            best_score = max(scores)
            latest_score = scores[-1]

            if latest_score < best_score:
                # Find when the best was achieved
                best_row = rows[scores.index(best_score)]
                latest_row = rows[-1]

                regressions.append({
                    "gate_id": gate_id,
                    "best_score": round(best_score, 4),
                    "latest_score": round(latest_score, 4),
                    "drop": round(best_score - latest_score, 4),
                    "best_at": best_row["timestamp"],
                    "latest_at": latest_row["timestamp"],
                    "latest_passed": bool(latest_row["passed"]),
                })

        return {
            "module_id": module_id,
            "regressions": regressions,
            "regression_count": len(regressions),
            "gates_checked": len(gates),
        }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Aggregate quality gate statistics."""
        gate_count = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_quality_gates WHERE active = 1"
        ).fetchone()["cnt"]

        total_evals = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_quality_results"
        ).fetchone()["cnt"]

        passed_evals = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sylion_quality_results WHERE passed = 1"
        ).fetchone()["cnt"]

        pass_rate = passed_evals / total_evals if total_evals > 0 else 0.0

        # Per-module breakdown
        module_rows = self._conn.execute("""
            SELECT qg.module_id,
                   COUNT(qr.result_id) as eval_count,
                   SUM(CASE WHEN qr.passed = 1 THEN 1 ELSE 0 END) as passed_count
            FROM sylion_quality_gates qg
            LEFT JOIN sylion_quality_results qr ON qg.gate_id = qr.gate_id
            WHERE qg.active = 1
            GROUP BY qg.module_id
            ORDER BY qg.module_id
        """).fetchall()

        by_module = {}
        for r in module_rows:
            mid = r["module_id"] or "(unassigned)"
            ec = r["eval_count"]
            pc = r["passed_count"] or 0
            by_module[mid] = {
                "eval_count": ec,
                "passed_count": pc,
                "pass_rate": round(pc / ec, 4) if ec > 0 else 0.0,
            }

        return {
            "total_gates": gate_count,
            "total_evaluations": total_evals,
            "passed_evaluations": passed_evals,
            "pass_rate": round(pass_rate, 4),
            "by_module": by_module,
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def deactivate_gate(self, gate_id: str) -> bool:
        """Deactivate a quality gate."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE sylion_quality_gates SET active = 0 WHERE gate_id = ?",
                (gate_id,),
            ).rowcount
            self._conn.commit()
        if n:
            self._emit("quality_gate.deactivated", {"gate_id": gate_id})
            log.info("deactivated quality gate %s", gate_id)
        return bool(n)

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="quality.quality_gate",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_gate: QualityGate | None = None


def get_quality_gate(db_path: str | Path | None = None,
                     event_bus: EventBus | None = None) -> QualityGate:
    """Get or create the global QualityGate singleton."""
    global _gate
    if _gate is None:
        _gate = QualityGate(db_path=db_path, event_bus=event_bus)
    return _gate
