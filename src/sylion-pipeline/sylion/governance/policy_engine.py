"""
SYLION Governance -- Policy Engine

Evaluates governance policies against operational context.
Supports rule-based compliance checking, audit trails, and scope-based policy
management with full change history tracking.

SQLite-backed with WAL mode, thread-safe via threading.Lock, singleton pattern.
"""

from __future__ import annotations

import json
import logging
import operator
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.governance.policy_engine")

# ---------------------------------------------------------------------------
# Rule evaluation operators
# ---------------------------------------------------------------------------

OPERATORS: dict[str, Any] = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
    "not_contains": lambda a, b: b not in a,
    "exists": lambda a, b: a is not None,
    "not_exists": lambda a, b: a is None,
    "regex": None,  # handled specially below
}

VALID_DECISION_CLASSES = {"D0", "D1", "D2", "D3", "D4", "D5"}


def _evaluate_single_rule(rule: dict, context: dict) -> dict:
    """Evaluate a single rule against a context dict.

    A rule has the shape:
        {
            "field": "blast_radius",
            "operator": "eq",
            "value": "high",
            "message": "Blast radius must be 'high'"
        }

    Returns {"passed": bool, "rule": dict, "message": str}.
    """
    field_name = rule.get("field", "")
    op_name = rule.get("operator", "eq")
    expected = rule.get("value")
    message = rule.get("message", f"Rule failed: {field_name} {op_name} {expected}")

    actual = context.get(field_name)

    if op_name == "regex":
        import re
        try:
            pattern = re.compile(str(expected))
            passed = bool(pattern.search(str(actual) if actual is not None else ""))
        except re.error:
            passed = False
            message = f"Invalid regex pattern: {expected}"
        return {"passed": passed, "rule": rule, "message": message}

    op_fn = OPERATORS.get(op_name)
    if op_fn is None:
        return {
            "passed": False,
            "rule": rule,
            "message": f"Unknown operator: {op_name}",
        }

    try:
        passed = op_fn(actual, expected)
    except (TypeError, ValueError):
        passed = False
        message = f"Type error evaluating {field_name}: cannot compare {type(actual).__name__} with {type(expected).__name__}"

    return {"passed": passed, "rule": rule, "message": message}


def _evaluate_rules(rules: list[dict], context: dict) -> list[dict]:
    """Evaluate all rules against context. Returns list of evaluation results."""
    return [_evaluate_single_rule(rule, context) for rule in rules]


# ---------------------------------------------------------------------------
# PolicyEngine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Governance policy engine with rule evaluation and compliance checking.

    Thread-safe. SQLite-backed. Emits events on policy lifecycle changes.
    Maintains full change history for audit.
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
            CREATE TABLE IF NOT EXISTS sylion_policies (
                policy_id      TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                description    TEXT NOT NULL DEFAULT '',
                rules          TEXT NOT NULL DEFAULT '[]',
                scope          TEXT NOT NULL DEFAULT 'global',
                decision_class TEXT NOT NULL DEFAULT 'D2',
                active         INTEGER NOT NULL DEFAULT 1,
                version        INTEGER NOT NULL DEFAULT 1,
                created_at     REAL NOT NULL,
                updated_at     REAL NOT NULL DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sylion_policy_history (
                history_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id    TEXT NOT NULL,
                action       TEXT NOT NULL,
                old_rules    TEXT NOT NULL DEFAULT '[]',
                new_rules    TEXT NOT NULL DEFAULT '[]',
                changelog    TEXT NOT NULL DEFAULT '',
                version      INTEGER NOT NULL DEFAULT 1,
                timestamp    REAL NOT NULL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_policies_scope ON sylion_policies(scope)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_policies_active ON sylion_policies(active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_policy ON sylion_policy_history(policy_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_ts ON sylion_policy_history(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def create_policy(self, policy_id: str, name: str, description: str = "",
                      rules: list[dict] | None = None, scope: str = "global",
                      decision_class: str = "D2") -> dict:
        """Create a new governance policy.

        Args:
            policy_id: Unique identifier for the policy.
            name: Human-readable policy name.
            description: Policy description.
            rules: List of rule dicts with field/operator/value/message keys.
            scope: Scope tag for grouping (e.g. 'security', 'quality').
            decision_class: Minimum decision class required (D0-D5).

        Returns:
            The created policy dict.
        """
        if rules is None:
            rules = []

        now = time.time()

        with self._lock:
            # Check for duplicate
            existing = self._conn.execute(
                "SELECT policy_id FROM sylion_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if existing:
                raise ValueError(f"Policy '{policy_id}' already exists")

            self._conn.execute("""
                INSERT INTO sylion_policies
                (policy_id, name, description, rules, scope, decision_class,
                 active, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """, (
                policy_id, name, description,
                json.dumps(rules, default=str),
                scope, decision_class,
                now, now,
            ))
            self._conn.commit()

        self._emit("policy_engine.created", {
            "policy_id": policy_id, "name": name, "scope": scope,
        })

        log.info("created policy %s: %s (scope=%s, dc=%s)",
                 policy_id, name, scope, decision_class)
        return self._get_policy_dict(policy_id)

    def update_policy(self, policy_id: str, rules: list[dict] | None = None,
                      changelog: str = "") -> dict | None:
        """Update a policy's rules with audit trail.

        Args:
            policy_id: Policy to update.
            rules: New rules list. If None, no rule update occurs.
            changelog: Description of the change for audit.

        Returns:
            Updated policy dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                log.warning("policy %s not found for update", policy_id)
                return None

            old_rules = json.loads(row["rules"])
            new_rules = rules if rules is not None else old_rules
            new_version = row["version"] + 1
            now = time.time()

            # Record history
            self._conn.execute("""
                INSERT INTO sylion_policy_history
                (policy_id, action, old_rules, new_rules, changelog, version, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                policy_id, "update",
                json.dumps(old_rules, default=str),
                json.dumps(new_rules, default=str),
                changelog, new_version, now,
            ))

            # Update policy
            self._conn.execute("""
                UPDATE sylion_policies
                SET rules = ?, version = ?, updated_at = ?
                WHERE policy_id = ?
            """, (
                json.dumps(new_rules, default=str),
                new_version, now, policy_id,
            ))
            self._conn.commit()

        self._emit("policy_engine.updated", {
            "policy_id": policy_id, "version": new_version, "changelog": changelog,
        })

        log.info("updated policy %s to version %d: %s",
                 policy_id, new_version, changelog)
        return self._get_policy_dict(policy_id)

    def activate_policy(self, policy_id: str) -> dict | None:
        """Activate a policy (set active=1).

        Returns:
            Updated policy dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                return None

            now = time.time()
            self._conn.execute(
                "UPDATE sylion_policies SET active = 1, updated_at = ? WHERE policy_id = ?",
                (now, policy_id),
            )

            # Record history
            self._conn.execute("""
                INSERT INTO sylion_policy_history
                (policy_id, action, old_rules, new_rules, changelog, version, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                policy_id, "activate",
                row["rules"], row["rules"],
                "Policy activated", row["version"], now,
            ))
            self._conn.commit()

        self._emit("policy_engine.activated", {"policy_id": policy_id})
        log.info("activated policy %s", policy_id)
        return self._get_policy_dict(policy_id)

    def deactivate_policy(self, policy_id: str) -> dict | None:
        """Deactivate a policy (set active=0).

        Returns:
            Updated policy dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                return None

            now = time.time()
            self._conn.execute(
                "UPDATE sylion_policies SET active = 0, updated_at = ? WHERE policy_id = ?",
                (now, policy_id),
            )

            # Record history
            self._conn.execute("""
                INSERT INTO sylion_policy_history
                (policy_id, action, old_rules, new_rules, changelog, version, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                policy_id, "deactivate",
                row["rules"], row["rules"],
                "Policy deactivated", row["version"], now,
            ))
            self._conn.commit()

        self._emit("policy_engine.deactivated", {"policy_id": policy_id})
        log.info("deactivated policy %s", policy_id)
        return self._get_policy_dict(policy_id)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate_policy(self, policy_id: str, context: dict) -> dict:
        """Evaluate a single policy's rules against the given context.

        Args:
            policy_id: The policy to evaluate.
            context: Dict with field values to check against rules.

        Returns:
            {
                "policy_id": str,
                "compliant": bool,
                "violations": list[dict],
                "passed": list[dict],
                "total_rules": int,
            }
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                return {
                    "policy_id": policy_id,
                    "compliant": False,
                    "violations": [{"message": f"Policy '{policy_id}' not found"}],
                    "passed": [],
                    "total_rules": 0,
                }

            rules = json.loads(row["rules"])

        results = _evaluate_rules(rules, context)

        violations = [r for r in results if not r["passed"]]
        passed = [r for r in results if r["passed"]]

        compliant = len(violations) == 0

        return {
            "policy_id": policy_id,
            "compliant": compliant,
            "violations": violations,
            "passed": passed,
            "total_rules": len(rules),
        }

    def check_compliance(self, scope: str, context: dict) -> dict:
        """Check all active policies in a scope against the context.

        Args:
            scope: The scope to filter policies by.
            context: Dict with field values to check.

        Returns:
            {
                "scope": str,
                "compliant": bool,
                "evaluations": list[dict],
                "total_policies": int,
                "violations_count": int,
            }
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT policy_id FROM sylion_policies WHERE scope = ? AND active = 1",
                (scope,),
            ).fetchall()

        evaluations = []
        violations_count = 0

        for row in rows:
            result = self.evaluate_policy(row["policy_id"], context)
            evaluations.append(result)
            if not result["compliant"]:
                violations_count += 1

        return {
            "scope": scope,
            "compliant": violations_count == 0,
            "evaluations": evaluations,
            "total_policies": len(evaluations),
            "violations_count": violations_count,
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_policies(self, scope: str | None = None,
                      active_only: bool = False) -> list[dict]:
        """List policies with optional filtering.

        Args:
            scope: Filter by scope tag.
            active_only: Only return active policies.

        Returns:
            List of policy dicts.
        """
        q = "SELECT * FROM sylion_policies WHERE 1=1"
        params: list[Any] = []

        if scope:
            q += " AND scope = ?"
            params.append(scope)
        if active_only:
            q += " AND active = 1"

        q += " ORDER BY name"
        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_policy_history(self, policy_id: str) -> list[dict]:
        """Get full change history for a policy.

        Args:
            policy_id: The policy to query history for.

        Returns:
            List of history entries ordered by timestamp ascending.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sylion_policy_history WHERE policy_id = ? ORDER BY timestamp ASC",
                (policy_id,),
            ).fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            entry["old_rules"] = json.loads(entry.get("old_rules", "[]"))
            entry["new_rules"] = json.loads(entry.get("new_rules", "[]"))
            result.append(entry)
        return result

    def get_stats(self) -> dict:
        """Get aggregate statistics about policies.

        Returns:
            {
                "total": int,
                "active": int,
                "inactive": int,
                "by_scope": dict[str, int],
                "compliance_rate": float,
            }
        """
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as c FROM sylion_policies"
            ).fetchone()["c"]

            active = self._conn.execute(
                "SELECT COUNT(*) as c FROM sylion_policies WHERE active = 1"
            ).fetchone()["c"]

            scope_rows = self._conn.execute(
                "SELECT scope, COUNT(*) as c FROM sylion_policies GROUP BY scope"
            ).fetchall()
        by_scope = {r["scope"]: r["c"] for r in scope_rows}

        # Calculate compliance rate from evaluations stored in history
        # For a meaningful metric: ratio of active to total policies
        compliance_rate = (active / total * 100.0) if total > 0 else 100.0

        return {
            "total": total,
            "active": active,
            "inactive": total - active,
            "by_scope": by_scope,
            "compliance_rate": round(compliance_rate, 2),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_policy_dict(self, policy_id: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sylion_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else {}

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["rules"] = json.loads(d.get("rules", "[]"))
        d["active"] = bool(d.get("active", 0))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.policy_engine",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: PolicyEngine | None = None


def get_policy_engine(db_path: str | Path | None = None,
                      event_bus: EventBus | None = None) -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine(db_path, event_bus)
    return _engine
