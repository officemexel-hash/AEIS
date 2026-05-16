"""
SYLION Governance -- Policy Evaluator

Evaluates contexts against policy rules. Manages policies, their evaluations,
and exception grants. Supports scoped policies with configurable priority.

Schema:
  policies           - policy definitions with scope, rules, priority
  policy_evaluations - evaluation records (policy applied to context)
  policy_exceptions  - exception grants (target exempted from policy)

Thread-safe. SQLite-backed. Emits events via EventBus.
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

log = logging.getLogger("sylion.governance.policy_evaluator")

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

VALID_SCOPES = ("global", "module", "user", "session", "pipeline")

VALID_POLICY_STATUSES = ("active", "disabled", "archived")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Policy:
    """A policy definition with rules and scope."""
    policy_id: str = ""
    name: str = ""
    scope: str = "global"
    rules_json: str = "{}"
    priority: int = 50
    status: str = "active"
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.policy_id:
            self.policy_id = uuid.uuid4().hex
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class PolicyEvaluation:
    """Result of evaluating a context against a policy."""
    evaluation_id: str = ""
    policy_id: str = ""
    context_json: str = "{}"
    result: str = "pending"
    details_json: str = "{}"
    evaluated_at: float = 0.0

    def __post_init__(self):
        if not self.evaluation_id:
            self.evaluation_id = uuid.uuid4().hex
        if not self.evaluated_at:
            self.evaluated_at = time.time()


@dataclass
class PolicyException:
    """An exception grant exempting a target from a policy."""
    exception_id: str = ""
    policy_id: str = ""
    target_id: str = ""
    reason: str = ""
    expires_at: float = 0.0
    created_at: float = 0.0

    def __post_init__(self):
        if not self.exception_id:
            self.exception_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class PolicyEvaluator:
    """Evaluates contexts against policy rules.

    SQLite-backed, thread-safe. Integrates with EventBus for policy
    lifecycle events.
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS policies (
                policy_id    TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                scope        TEXT NOT NULL DEFAULT 'global',
                rules_json   TEXT NOT NULL DEFAULT '{}',
                priority     INTEGER NOT NULL DEFAULT 50,
                status       TEXT NOT NULL DEFAULT 'active',
                created_at   REAL NOT NULL,
                updated_at   REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS policy_evaluations (
                evaluation_id TEXT PRIMARY KEY,
                policy_id     TEXT NOT NULL,
                context_json  TEXT NOT NULL DEFAULT '{}',
                result        TEXT NOT NULL DEFAULT 'pending',
                details_json  TEXT NOT NULL DEFAULT '{}',
                evaluated_at  REAL NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
            );
            CREATE TABLE IF NOT EXISTS policy_exceptions (
                exception_id TEXT PRIMARY KEY,
                policy_id    TEXT NOT NULL,
                target_id    TEXT NOT NULL DEFAULT '',
                reason       TEXT NOT NULL DEFAULT '',
                expires_at   REAL NOT NULL DEFAULT 0,
                created_at   REAL NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
            );
            CREATE INDEX IF NOT EXISTS idx_pol_scope   ON policies(scope);
            CREATE INDEX IF NOT EXISTS idx_pol_status  ON policies(status);
            CREATE INDEX IF NOT EXISTS idx_pev_policy  ON policy_evaluations(policy_id);
            CREATE INDEX IF NOT EXISTS idx_pex_policy  ON policy_exceptions(policy_id);
            CREATE INDEX IF NOT EXISTS idx_pex_target  ON policy_exceptions(target_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def create_policy(self, name: str, scope: str = "global",
                      rules_json: str = "{}", priority: int = 50) -> dict:
        """Create a new policy."""
        if scope not in VALID_SCOPES:
            raise ValueError(
                f"Invalid scope: {scope!r}. Must be one of {VALID_SCOPES}"
            )
        policy = Policy(
            name=name, scope=scope,
            rules_json=rules_json, priority=priority,
        )
        with self._lock:
            self._conn.execute("""
                INSERT INTO policies
                    (policy_id, name, scope, rules_json, priority,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                policy.policy_id, policy.name, policy.scope,
                policy.rules_json, policy.priority, policy.status,
                policy.created_at, policy.updated_at,
            ))
            self._conn.commit()

        self._emit("policy_created", {
            "policy_id": policy.policy_id,
            "name": name,
            "scope": scope,
            "priority": priority,
        })
        log.info("policy created: %s (%s, scope=%s, prio=%d)",
                 policy.policy_id[:12], name, scope, priority)
        return self._row_to_policy_dict({
            "policy_id": policy.policy_id, "name": policy.name,
            "scope": policy.scope, "rules_json": policy.rules_json,
            "priority": policy.priority, "status": policy.status,
            "created_at": policy.created_at, "updated_at": policy.updated_at,
        })

    def update_policy(self, policy_id: str, **kwargs) -> dict | None:
        """Update policy fields. Accepts name, scope, rules_json, priority, status."""
        allowed = {"name", "scope", "rules_json", "priority", "status"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get_policy(policy_id)

        if "scope" in updates and updates["scope"] not in VALID_SCOPES:
            raise ValueError(
                f"Invalid scope: {updates['scope']!r}. Must be one of {VALID_SCOPES}"
            )
        if "status" in updates and updates["status"] not in VALID_POLICY_STATUSES:
            raise ValueError(
                f"Invalid status: {updates['status']!r}. "
                f"Must be one of {VALID_POLICY_STATUSES}"
            )

        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [policy_id]

        with self._lock:
            row = self._conn.execute(
                "SELECT policy_id FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                f"UPDATE policies SET {set_clause} WHERE policy_id = ?",
                values,
            )
            self._conn.commit()

        return self.get_policy(policy_id)

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy and its associated evaluations and exceptions."""
        with self._lock:
            row = self._conn.execute(
                "SELECT policy_id FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                return False
            self._conn.execute(
                "DELETE FROM policy_evaluations WHERE policy_id = ?",
                (policy_id,),
            )
            self._conn.execute(
                "DELETE FROM policy_exceptions WHERE policy_id = ?",
                (policy_id,),
            )
            self._conn.execute(
                "DELETE FROM policies WHERE policy_id = ?",
                (policy_id,),
            )
            self._conn.commit()
        return True

    def get_policy(self, policy_id: str) -> dict | None:
        """Retrieve a policy by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_policy_dict(row)

    def list_policies(self, scope: str | None = None,
                      active_only: bool = False) -> list[dict]:
        """List policies with optional filters."""
        q = "SELECT * FROM policies WHERE 1=1"
        params: list[Any] = []
        if scope:
            q += " AND scope = ?"
            params.append(scope)
        if active_only:
            q += " AND status = 'active'"
        q += " ORDER BY priority DESC, created_at DESC"

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_policy_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, policy_id: str, context_json: str = "{}") -> dict:
        """Evaluate a context against a policy's rules.

        Returns the evaluation result. The evaluation applies the policy
        rules (JSON) against the context (JSON). Simple key-match: if all
        keys in rules exist in context with matching values, result is
        'pass', otherwise 'fail'.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Policy not found: {policy_id}")
            if row["status"] != "active":
                raise ValueError(f"Policy is not active: {policy_id}")
            rules_raw = row["rules_json"]

        try:
            rules = json.loads(rules_raw)
            context = json.loads(context_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        # Simple rule evaluation: all rule key-values must match context
        result = "pass"
        details: dict[str, Any] = {}
        if rules:
            for key, expected in rules.items():
                actual = context.get(key)
                if actual != expected:
                    result = "fail"
                    details[key] = {
                        "expected": expected,
                        "actual": actual,
                    }

        evaluation = PolicyEvaluation(
            policy_id=policy_id,
            context_json=context_json,
            result=result,
            details_json=json.dumps(details, default=str),
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO policy_evaluations
                    (evaluation_id, policy_id, context_json, result,
                     details_json, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                evaluation.evaluation_id, evaluation.policy_id,
                evaluation.context_json, evaluation.result,
                evaluation.details_json, evaluation.evaluated_at,
            ))
            self._conn.commit()

        self._emit("policy_evaluated", {
            "evaluation_id": evaluation.evaluation_id,
            "policy_id": policy_id,
            "result": result,
        })
        log.info("policy evaluated: %s -> %s", policy_id[:12], result)
        return {
            "evaluation_id": evaluation.evaluation_id,
            "policy_id": policy_id,
            "result": result,
            "details": details,
            "evaluated_at": evaluation.evaluated_at,
        }

    # ------------------------------------------------------------------
    # Exceptions
    # ------------------------------------------------------------------

    def grant_exception(self, policy_id: str, target_id: str,
                        reason: str, expires_at: float = 0.0) -> dict:
        """Grant an exception for a target, exempting it from a policy."""
        with self._lock:
            row = self._conn.execute(
                "SELECT policy_id FROM policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Policy not found: {policy_id}")

        exc = PolicyException(
            policy_id=policy_id, target_id=target_id,
            reason=reason, expires_at=expires_at,
        )

        with self._lock:
            self._conn.execute("""
                INSERT INTO policy_exceptions
                    (exception_id, policy_id, target_id, reason,
                     expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                exc.exception_id, exc.policy_id, exc.target_id,
                exc.reason, exc.expires_at, exc.created_at,
            ))
            self._conn.commit()

        self._emit("exception_granted", {
            "exception_id": exc.exception_id,
            "policy_id": policy_id,
            "target_id": target_id,
        })
        log.info("exception granted: policy %s target %s",
                 policy_id[:12], target_id[:12])
        return {
            "exception_id": exc.exception_id,
            "policy_id": policy_id,
            "target_id": target_id,
            "reason": reason,
            "expires_at": expires_at,
            "created_at": exc.created_at,
        }

    def list_exceptions(self, policy_id: str | None = None) -> list[dict]:
        """List exceptions, optionally filtered by policy."""
        q = "SELECT * FROM policy_exceptions WHERE 1=1"
        params: list[Any] = []
        if policy_id:
            q += " AND policy_id = ?"
            params.append(policy_id)
        q += " ORDER BY created_at DESC"

        with self._lock:
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_evaluator_stats(self) -> dict[str, Any]:
        """Return policy and evaluation statistics."""
        with self._lock:
            total_policies = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM policies"
            ).fetchone()["cnt"]

            status_rows = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM policies "
                "GROUP BY status ORDER BY status"
            ).fetchall()

            scope_rows = self._conn.execute(
                "SELECT scope, COUNT(*) as cnt FROM policies "
                "GROUP BY scope ORDER BY scope"
            ).fetchall()

            total_evals = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM policy_evaluations"
            ).fetchone()["cnt"]

            eval_result_rows = self._conn.execute(
                "SELECT result, COUNT(*) as cnt FROM policy_evaluations "
                "GROUP BY result ORDER BY result"
            ).fetchall()

            total_exceptions = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM policy_exceptions"
            ).fetchone()["cnt"]

        by_status = {r["status"]: r["cnt"] for r in status_rows}
        by_scope = {r["scope"]: r["cnt"] for r in scope_rows}
        by_result = {r["result"]: r["cnt"] for r in eval_result_rows}

        return {
            "total_policies": total_policies,
            "policies_by_status": by_status,
            "policies_by_scope": by_scope,
            "total_evaluations": total_evals,
            "evaluations_by_result": by_result,
            "total_exceptions": total_exceptions,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_policy_dict(row: sqlite3.Row | dict) -> dict:
        d = dict(row)
        d["rules"] = json.loads(d.get("rules_json", "{}"))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.policy_evaluator",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_evaluator: PolicyEvaluator | None = None


def get_policy_evaluator(event_bus: EventBus | None = None,
                         db_path: str | Path | None = None
                         ) -> PolicyEvaluator:
    global _evaluator
    if _evaluator is None:
        _evaluator = PolicyEvaluator(db_path=db_path, event_bus=event_bus)
    return _evaluator


def reset_policy_evaluator() -> None:
    global _evaluator
    _evaluator = None
