"""
SYLION Governance -- Decision Boundaries

Defines and enforces decision boundaries that constrain automated decisions.
Each boundary has a name, scope, and a set of rules encoded as JSON.
evaluate_boundary() checks if a given context violates any boundary rules.

Thread-safe. SQLite-backed. EventBus integration.
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

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.governance.decision_boundaries")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SCOPES: tuple[str, ...] = (
    "global", "module", "pipeline", "decision", "deployment",
)


# ---------------------------------------------------------------------------
# DecisionBoundariesManager
# ---------------------------------------------------------------------------

class DecisionBoundariesManager:
    """Manages decision boundaries with rule-based evaluation.

    Boundaries define constraints that decisions must not violate.
    Each boundary has rules encoded as JSON that are evaluated against
    a context dictionary.
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

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_boundaries (
                    boundary_id  TEXT PRIMARY KEY,
                    name         TEXT NOT NULL,
                    scope        TEXT NOT NULL,
                    rules_json   TEXT NOT NULL DEFAULT '[]',
                    is_active    INTEGER NOT NULL DEFAULT 1,
                    created_at   REAL NOT NULL,
                    updated_at   REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS boundary_evaluations (
                    evaluation_id  TEXT PRIMARY KEY,
                    boundary_id    TEXT NOT NULL,
                    context_json   TEXT NOT NULL DEFAULT '{}',
                    passed         INTEGER NOT NULL,
                    violations     TEXT NOT NULL DEFAULT '[]',
                    evaluated_at   REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_boundaries_scope "
                "ON decision_boundaries(scope)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_boundaries_name "
                "ON decision_boundaries(name)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evaluations_boundary "
                "ON boundary_evaluations(boundary_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_evaluations_ts "
                "ON boundary_evaluations(evaluated_at)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_boundary(self, name: str, scope: str,
                        rules_json: list[dict] | str | None = None) -> dict:
        """Create a new decision boundary.

        Args:
            name: Human-readable boundary name.
            scope: One of VALID_SCOPES.
            rules_json: List of rule dicts or JSON string.

        Returns:
            Dict with boundary details.
        """
        if not name or not name.strip():
            raise ValueError("Boundary name must not be empty.")
        if scope not in VALID_SCOPES:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of {VALID_SCOPES}."
            )

        if rules_json is None:
            rules = []
        elif isinstance(rules_json, str):
            rules = json.loads(rules_json)
        else:
            rules = rules_json

        boundary_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO decision_boundaries
                (boundary_id, name, scope, rules_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (boundary_id, name, scope, json.dumps(rules), now, now))
            self._conn.commit()

        self._emit("boundary_created", {
            "boundary_id": boundary_id,
            "name": name,
            "scope": scope,
        })

        log.info("created boundary %s (%s/%s)", boundary_id, name, scope)

        return {
            "boundary_id": boundary_id,
            "name": name,
            "scope": scope,
            "rules": rules,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

    def update_boundary(self, boundary_id: str, *,
                        name: str | None = None,
                        scope: str | None = None,
                        rules_json: list[dict] | str | None = None,
                        is_active: bool | None = None) -> dict | None:
        """Update an existing boundary. Returns updated dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_boundaries WHERE boundary_id = ?",
                (boundary_id,),
            ).fetchone()
            if not row:
                return None

            if scope is not None and scope not in VALID_SCOPES:
                raise ValueError(
                    f"Invalid scope '{scope}'. Must be one of {VALID_SCOPES}."
                )

            new_name = name if name is not None else row["name"]
            new_scope = scope if scope is not None else row["scope"]
            new_active = 1 if (is_active if is_active is not None else row["is_active"]) else 0

            if rules_json is None:
                new_rules = json.loads(row["rules_json"])
            elif isinstance(rules_json, str):
                new_rules = json.loads(rules_json)
            else:
                new_rules = rules_json

            now = time.time()
            self._conn.execute("""
                UPDATE decision_boundaries
                SET name = ?, scope = ?, rules_json = ?, is_active = ?, updated_at = ?
                WHERE boundary_id = ?
            """, (new_name, new_scope, json.dumps(new_rules), new_active, now, boundary_id))
            self._conn.commit()

        self._emit("boundary_updated", {
            "boundary_id": boundary_id,
            "name": new_name,
            "scope": new_scope,
        })

        return {
            "boundary_id": boundary_id,
            "name": new_name,
            "scope": new_scope,
            "rules": new_rules,
            "is_active": bool(new_active),
            "created_at": row["created_at"],
            "updated_at": now,
        }

    def delete_boundary(self, boundary_id: str) -> bool:
        """Delete a boundary. Returns True if deleted."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM decision_boundaries WHERE boundary_id = ?",
                (boundary_id,),
            )
            self._conn.execute(
                "DELETE FROM boundary_evaluations WHERE boundary_id = ?",
                (boundary_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def get_boundary(self, boundary_id: str, registry: Any | None = None) -> dict | None:
        """Retrieve a boundary by ID or derive a module decision boundary."""
        if registry is not None:
            module = registry.get(boundary_id)
            if not module:
                return {"allowed": False, "module_id": boundary_id, "reason": "module_not_found"}
            decision_class = str(module.get("decision_cls") or module.get("decision_class_entry") or "D3")
            rank = int(decision_class[1:]) if decision_class.startswith("D") and decision_class[1:].isdigit() else 3
            return {
                "allowed": True,
                "module_id": boundary_id,
                "decision_class": decision_class,
                "requires_council": rank >= 3,
                "requires_human": rank >= 4,
            }
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_boundaries WHERE boundary_id = ?",
                (boundary_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def validate_decision(
        self,
        module_id: str,
        decision_class: str,
        registry: Any,
        *,
        council_approved: bool = False,
        human_approved: bool = False,
    ) -> dict[str, Any]:
        """Validate D-level decision requirements for a module."""
        boundary = self.get_boundary(module_id, registry)
        if not boundary or not boundary.get("allowed"):
            return {"valid": False, "missing_requirements": ["module_boundary"], "boundary": boundary}
        rank = int(decision_class[1:]) if decision_class.startswith("D") and decision_class[1:].isdigit() else 0
        missing: list[str] = []
        if rank >= 3 and not council_approved:
            missing.append("council_approval")
        if rank >= 4 and not human_approved:
            missing.append("human_approval")
        return {"valid": not missing, "missing_requirements": missing, "boundary": boundary}

    def list_boundaries(self, scope: str | None = None,
                        active_only: bool = False) -> list[dict]:
        """List boundaries, optionally filtered by scope."""
        with self._lock:
            q = "SELECT * FROM decision_boundaries WHERE 1=1"
            params: list[Any] = []
            if scope is not None:
                q += " AND scope = ?"
                params.append(scope)
            if active_only:
                q += " AND is_active = 1"
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_boundary(self, boundary_id: str,
                          context: dict[str, Any]) -> dict:
        """Evaluate a boundary against a context dict.

        Checks each rule in the boundary against the context.
        A rule is a dict with 'field', 'operator', and 'value' keys.
        Supported operators: eq, neq, gt, lt, gte, lte, in, not_in, contains.

        Returns:
            Dict with evaluation_id, passed, violations, evaluated_at.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM decision_boundaries WHERE boundary_id = ?",
                (boundary_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Boundary '{boundary_id}' not found.")

            rules = json.loads(row["rules_json"])

        violations = []
        for idx, rule in enumerate(rules):
            field = rule.get("field", "")
            operator = rule.get("operator", "eq")
            expected = rule.get("value")

            actual = context.get(field)

            violated = False
            if operator == "eq":
                violated = actual != expected
            elif operator == "neq":
                violated = actual == expected
            elif operator == "gt":
                violated = actual is None or actual <= expected
            elif operator == "lt":
                violated = actual is None or actual >= expected
            elif operator == "gte":
                violated = actual is None or actual < expected
            elif operator == "lte":
                violated = actual is None or actual > expected
            elif operator == "in":
                violated = actual not in (expected or [])
            elif operator == "not_in":
                violated = actual in (expected or [])
            elif operator == "contains":
                violated = expected not in (actual or [])
            else:
                violated = True

            if violated:
                violations.append({
                    "rule_index": idx,
                    "field": field,
                    "operator": operator,
                    "expected": expected,
                    "actual": actual,
                })

        passed = len(violations) == 0
        evaluation_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO boundary_evaluations
                (evaluation_id, boundary_id, context_json, passed, violations, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (evaluation_id, boundary_id, json.dumps(context),
                  1 if passed else 0, json.dumps(violations), now))
            self._conn.commit()

        event_payload = {
            "evaluation_id": evaluation_id,
            "boundary_id": boundary_id,
            "passed": passed,
            "violation_count": len(violations),
        }

        if passed:
            self._emit("boundary_evaluated", event_payload)
        else:
            self._emit("boundary_violated", {
                **event_payload,
                "violations": violations,
            })

        log.info("evaluated boundary %s: passed=%s violations=%d",
                 boundary_id, passed, len(violations))

        return {
            "evaluation_id": evaluation_id,
            "boundary_id": boundary_id,
            "passed": passed,
            "violations": violations,
            "evaluated_at": now,
        }

    def get_evaluation_history(self, boundary_id: str,
                               limit: int = 100) -> list[dict]:
        """Get evaluation history for a boundary, newest first."""
        with self._lock:
            rows = self._conn.execute("""
                SELECT * FROM boundary_evaluations
                WHERE boundary_id = ?
                ORDER BY evaluated_at DESC LIMIT ?
            """, (boundary_id, limit)).fetchall()
        return [self._eval_row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["rules_json"] = json.loads(d.get("rules_json", "[]"))
        d["is_active"] = bool(d.get("is_active", 1))
        return d

    @staticmethod
    def _eval_row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["context_json"] = json.loads(d.get("context_json", "{}"))
        d["violations"] = json.loads(d.get("violations", "[]"))
        d["passed"] = bool(d.get("passed", 0))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.decision_boundaries",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: DecisionBoundariesManager | None = None


def get_decision_boundaries_manager(db_path: str | Path | None = None,
                                    event_bus: EventBus | None = None) -> DecisionBoundariesManager:
    """Return the global DecisionBoundariesManager singleton."""
    global _manager
    if _manager is None:
        _manager = DecisionBoundariesManager(db_path, event_bus)
    return _manager


def reset_decision_boundaries_manager() -> None:
    """Reset the global singleton (for testing)."""
    global _manager
    _manager = None


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------
DecisionBoundaryMap = DecisionBoundariesManager
get_decision_boundary_map = get_decision_boundaries_manager
reset_decision_boundary_map = reset_decision_boundaries_manager
