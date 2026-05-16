"""
SYLION Governance -- Gates Registry

Centralised governance gate definitions and evaluation pipeline.
Gates are approval checkpoints that must pass before lifecycle transitions.
Each gate has a type, scope, and JSON criteria used for evaluation.

SQLite tables: governance_gates, gate_evaluations
Thread-safe via RLock.  EventBus integration via _emit().

Singleton: get_gates_registry() / reset_gates_registry()
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

log = logging.getLogger("sylion.governance.gates_registry")


class GatesRegistry:
    """Centralised governance gate definitions and evaluation history.

    Gates are approval checkpoints defined by name, type, criteria (JSON),
    and scope.  Evaluations check a context against the gate's criteria
    and record pass/fail results.

    Thread-safe. SQLite-backed. Emits events on gate creation and evaluation.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS governance_gates (
                gate_id    TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                gate_type  TEXT NOT NULL DEFAULT 'quality',
                criteria_json TEXT NOT NULL DEFAULT '{}',
                scope      TEXT NOT NULL DEFAULT '',
                enabled    INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS gate_evaluations (
                evaluation_id TEXT PRIMARY KEY,
                gate_id       TEXT NOT NULL,
                context_json  TEXT NOT NULL DEFAULT '{}',
                result        TEXT NOT NULL DEFAULT '',
                message       TEXT NOT NULL DEFAULT '',
                details_json  TEXT NOT NULL DEFAULT '{}',
                evaluated_at  REAL NOT NULL,
                FOREIGN KEY (gate_id) REFERENCES governance_gates(gate_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gg_type "
            "ON governance_gates(gate_type)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gg_scope "
            "ON governance_gates(scope)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ge_gate "
            "ON gate_evaluations(gate_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ge_result "
            "ON gate_evaluations(result)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.gates_registry",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    def _evaluate_criteria(self, criteria: dict, context: dict) -> tuple[bool, str]:
        """Evaluate context against criteria.

        Criteria is a dict of checks. Each key maps to an expected value.
        Context is checked against each criterion.
        Returns (passed: bool, message: str).
        """
        if not criteria:
            return True, "no criteria defined"

        failed_checks = []
        for key, expected in criteria.items():
            actual = context.get(key)
            if actual != expected:
                failed_checks.append(
                    f"{key}: expected {expected!r}, got {actual!r}"
                )

        if failed_checks:
            return False, "; ".join(failed_checks)
        return True, "all criteria met"

    # ------------------------------------------------------------------
    # Gate CRUD
    # ------------------------------------------------------------------

    def create_gate(self, name: str, gate_type: str = "quality",
                    criteria_json: Any = None,
                    scope: str = "") -> dict:
        """Create a new governance gate. Returns the gate record."""
        gate_id = self._uid()
        now = time.time()
        criteria_s = json.dumps(criteria_json, default=str) \
            if criteria_json is not None else "{}"

        with self._lock:
            self._conn.execute("""
                INSERT INTO governance_gates
                    (gate_id, name, gate_type, criteria_json, scope,
                     enabled, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (gate_id, name, gate_type, criteria_s, scope, now))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM governance_gates WHERE gate_id = ?",
                (gate_id,),
            ).fetchone()

        result = dict(row)
        result["criteria_json"] = self._parse_json(result.get("criteria_json"), {})
        self._emit("governance.gate_created", {
            "gate_id": gate_id, "name": name, "gate_type": gate_type,
        })
        log.info("created gate %s: %s (%s)", gate_id, name, gate_type)
        return result

    def register_gate(self, gate_def: Any, severity: Any = "blocking") -> dict:
        """Register a legacy GateDefinition using its caller-provided ID.

        Older API routes use the decision-gate vocabulary where the caller
        supplies ``gate_id`` and ``severity`` values such as ``blocking``.
        The registry stores the same record as a governance gate so later
        evaluations can address it by that stable ID.
        """
        gate_id = getattr(gate_def, "gate_id", "") or self._uid()
        name = getattr(gate_def, "name", "") or gate_id
        description = getattr(gate_def, "description", "") or ""
        severity_value = getattr(severity, "value", severity) or "blocking"
        decision_class = getattr(gate_def, "decision_class_min", "")
        decision_class_value = getattr(decision_class, "value", decision_class)
        criteria = {
            "description": description,
            "fail_condition": getattr(gate_def, "fail_condition", "") or "",
            "blocks": getattr(gate_def, "blocks", "") or "",
            "decision_class_min": decision_class_value or "",
            "severity": str(severity_value),
        }
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT OR REPLACE INTO governance_gates
                    (gate_id, name, gate_type, criteria_json, scope,
                     enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1,
                        COALESCE((SELECT created_at FROM governance_gates WHERE gate_id = ?), ?),
                        ?)
            """, (
                gate_id,
                name,
                str(severity_value),
                json.dumps(criteria, default=str),
                str(getattr(gate_def, "blocks", "") or ""),
                gate_id,
                now,
                now,
            ))
            self._conn.commit()

        result = self.get_gate(gate_id) or {"gate_id": gate_id, "name": name}
        result["severity"] = str(severity_value)
        self._emit("governance.gate_registered", {
            "gate_id": gate_id,
            "name": name,
            "severity": str(severity_value),
        })
        return result

    def update_gate(self, gate_id: str, **fields) -> dict | None:
        """Update mutable fields on a gate.

        Accepts: name, gate_type, criteria_json, scope, enabled.
        Returns updated record or None.
        """
        allowed = {"name", "gate_type", "scope", "enabled"}
        updates: dict[str, Any] = {}
        if "name" in fields:
            updates["name"] = fields["name"]
        if "gate_type" in fields:
            updates["gate_type"] = fields["gate_type"]
        if "scope" in fields:
            updates["scope"] = fields["scope"]
        if "enabled" in fields:
            updates["enabled"] = int(fields["enabled"])
        if "criteria_json" in fields:
            updates["criteria_json"] = json.dumps(
                fields["criteria_json"], default=str)

        if not updates:
            return self.get_gate(gate_id)

        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [gate_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE governance_gates SET {set_clause} WHERE gate_id = ?",
                values,
            ).rowcount
            self._conn.commit()
            if not n:
                return None

        return self.get_gate(gate_id)

    def delete_gate(self, gate_id: str) -> bool:
        """Delete a gate and its evaluations."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM gate_evaluations WHERE gate_id = ?",
                (gate_id,),
            )
            n = self._conn.execute(
                "DELETE FROM governance_gates WHERE gate_id = ?",
                (gate_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def get_gate(self, gate_id: str) -> dict | None:
        """Return a gate record by ID with parsed criteria."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM governance_gates WHERE gate_id = ?",
                (gate_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["criteria_json"] = self._parse_json(d.get("criteria_json"), {})
        return d

    def list_gates(self, gate_type: str | None = None,
                   scope: str | None = None) -> list[dict]:
        """List gates, optionally filtered by type and scope."""
        with self._lock:
            q = "SELECT * FROM governance_gates WHERE 1=1"
            params: list[Any] = []
            if gate_type:
                q += " AND gate_type = ?"
                params.append(gate_type)
            if scope:
                q += " AND scope = ?"
                params.append(scope)
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["criteria_json"] = self._parse_json(d.get("criteria_json"), {})
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_gate(self, gate_id: str,
                      context_json: Any = None) -> dict | None:
        """Evaluate context against a gate's criteria.

        Returns the evaluation record or None if the gate does not exist.
        """
        gate = self.get_gate(gate_id)
        if not gate:
            return None

        if not gate.get("enabled", 1):
            return None

        criteria = gate.get("criteria_json", {})
        if isinstance(criteria, str):
            criteria = self._parse_json(criteria, {})

        context = context_json if isinstance(context_json, dict) else {}
        if isinstance(context_json, str):
            context = self._parse_json(context_json, {})

        passed, message = self._evaluate_criteria(criteria, context)
        result = "passed" if passed else "failed"
        evaluation_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO gate_evaluations
                    (evaluation_id, gate_id, context_json, result,
                     message, details_json, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                evaluation_id, gate_id,
                json.dumps(context, default=str),
                result, message,
                json.dumps({"criteria": criteria}, default=str),
                now,
            ))
            self._conn.commit()

        eval_record = {
            "evaluation_id": evaluation_id,
            "gate_id": gate_id,
            "result": result,
            "message": message,
            "passed": passed,
            "evaluated_at": now,
        }

        self._emit("governance.gate_evaluated", {
            "evaluation_id": evaluation_id,
            "gate_id": gate_id, "result": result,
        })
        if passed:
            self._emit("governance.gate_passed", {
                "evaluation_id": evaluation_id, "gate_id": gate_id,
            })
        else:
            self._emit("governance.gate_failed", {
                "evaluation_id": evaluation_id, "gate_id": gate_id,
                "message": message,
            })

        log.info("gate %s evaluated: %s (%s)", gate_id, result, message)
        return eval_record

    def get_evaluations(self, gate_id: str | None = None,
                        module_id: str | None = None,
                        limit: int = 50) -> list[dict]:
        """Return recent evaluations, optionally filtered by gate/module."""
        clauses: list[str] = []
        params: list[Any] = []
        if gate_id is not None:
            clauses.append("gate_id = ?")
            params.append(gate_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM gate_evaluations {where} "
                "ORDER BY evaluated_at DESC",
                tuple(params),
            ).fetchall()
        results: list[dict] = []
        for r in rows:
            d = dict(r)
            ctx = self._parse_json(d.get("context_json"), {})
            d["context_json"] = ctx
            d["details_json"] = self._parse_json(d.get("details_json"), {})
            if module_id is not None and ctx.get("module_id") != module_id:
                continue
            results.append(d)
            if len(results) >= limit:
                break
        return results

    def get_gate_stats(self) -> dict[str, Any]:
        """Aggregate statistics across all gates and evaluations."""
        with self._lock:
            total_gates = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM governance_gates"
            ).fetchone()["cnt"]

            total_evals = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM gate_evaluations"
            ).fetchone()["cnt"]

            passed_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM gate_evaluations "
                "WHERE result = 'passed'"
            ).fetchone()
            passed_count = passed_row["cnt"] if passed_row else 0

            failed_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM gate_evaluations "
                "WHERE result = 'failed'"
            ).fetchone()
            failed_count = failed_row["cnt"] if failed_row else 0

        pass_rate = passed_count / total_evals if total_evals > 0 else 0.0
        return {
            "total_gates": total_gates,
            "total_evaluations": total_evals,
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": round(pass_rate, 4),
        }

    # ------------------------------------------------------------------
    # Legacy API methods (backward compatibility)
    # ------------------------------------------------------------------

    def evaluate(self, gate_eval: "GateEvaluation") -> dict:
        """Evaluate a gate using a GateEvaluation object (legacy API).

        Records the evaluation result and returns it.
        """
        now = time.time()
        evaluation_id = self._uid()
        result = gate_eval.result

        with self._lock:
            self._conn.execute("""
                INSERT INTO gate_evaluations
                    (evaluation_id, gate_id, context_json, result,
                     message, details_json, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                evaluation_id, gate_eval.gate_id,
                json.dumps({"module_id": gate_eval.module_id}),
                "passed" if result == "pass" else "failed",
                "",
                json.dumps({"module_id": gate_eval.module_id, "severity": gate_eval.severity}),
                now,
            ))
            self._conn.commit()

        self._emit("governance.gate_evaluated", {
            "evaluation_id": evaluation_id,
            "gate_id": gate_eval.gate_id,
            "result": result,
            "module_id": gate_eval.module_id,
        })

        return {
            "evaluation_id": evaluation_id,
            "gate_id": gate_eval.gate_id,
            "result": result,
            "module_id": gate_eval.module_id,
            "evaluated_at": now,
        }

    def check_blocking(self, module_id: str) -> dict:
        """Check if any gate blocks a module.

        Returns dict with 'blocked' (bool) and 'blocked_by' (list).
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM gate_evaluations "
                "WHERE context_json LIKE ? AND result = 'failed' "
                "ORDER BY evaluated_at DESC LIMIT 10",
                (f'%{module_id}%',),
            ).fetchall()

        blocked_by = []
        for row in rows:
            blocked_by.append({
                "gate_id": row["gate_id"],
                "evaluation_id": row["evaluation_id"],
            })

        return {
            "blocked": len(blocked_by) > 0,
            "blocked_by": blocked_by,
            "module_id": module_id,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_gates_reg: GatesRegistry | None = None


def get_gates_registry(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GatesRegistry:
    global _gates_reg
    if _gates_reg is None:
        _gates_reg = GatesRegistry(db_path, event_bus)
    return _gates_reg


def reset_gates_registry(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GatesRegistry:
    global _gates_reg
    _gates_reg = GatesRegistry(db_path, event_bus)
    return _gates_reg


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------
from dataclasses import dataclass as _dataclass
from enum import Enum


class GateSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@_dataclass
class GateEvaluation:
    gate_id: str = ""
    module_id: str = ""
    result: str = "pass"
    severity: str = "medium"
    message: str = ""
