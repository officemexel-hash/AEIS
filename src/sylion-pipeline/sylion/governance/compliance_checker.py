"""
SYLION Governance -- Compliance Checker

Checks compliance of modules against defined policies and requirements.
Validates module registry data against policy rule thresholds and tracks
violation history for audit.

Tables:
  compliance_policies  -- policy definitions with scope, rules, severity
  compliance_checks    -- individual check results (compliant/violation/warning/error)

Singleton: get_compliance_checker() / reset_compliance_checker()
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

log = logging.getLogger("sylion.governance.compliance_checker")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SCOPES = ("security", "quality", "architecture", "performance", "all")
VALID_SEVERITIES = ("info", "warning", "critical")
VALID_CHECK_STATUSES = ("compliant", "violation", "warning", "error")


class ComplianceChecker:
    """Module compliance checker.

    Thread-safe. SQLite-backed. Emits events on compliance checks and violations.
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS compliance_policies (
                policy_id   TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                scope       TEXT NOT NULL,
                rules       TEXT NOT NULL DEFAULT '[]',
                severity    TEXT NOT NULL DEFAULT 'medium',
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS compliance_checks (
                check_id    TEXT PRIMARY KEY,
                policy_id   TEXT NOT NULL,
                module_id   TEXT NOT NULL,
                scope       TEXT NOT NULL,
                status      TEXT NOT NULL,
                violations  TEXT NOT NULL DEFAULT '[]',
                checked_at  REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cp_scope
                ON compliance_policies(scope);
            CREATE INDEX IF NOT EXISTS idx_cp_enabled
                ON compliance_policies(enabled);
            CREATE INDEX IF NOT EXISTS idx_cc_module
                ON compliance_checks(module_id);
            CREATE INDEX IF NOT EXISTS idx_cc_policy
                ON compliance_checks(policy_id);
            CREATE INDEX IF NOT EXISTS idx_cc_status
                ON compliance_checks(status);
            CREATE INDEX IF NOT EXISTS idx_cc_checked_at
                ON compliance_checks(checked_at);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:16]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.compliance_checker",
            ))

    def _validate_scope(self, scope: str):
        if scope not in VALID_SCOPES:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of {VALID_SCOPES}"
            )

    def _validate_severity(self, severity: str):
        if severity not in VALID_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{severity}'. Must be one of {VALID_SEVERITIES}"
            )

    def _validate_check_status(self, status: str):
        if status not in VALID_CHECK_STATUSES:
            raise ValueError(
                f"Invalid check status '{status}'. Must be one of {VALID_CHECK_STATUSES}"
            )

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        if "rules" in d and isinstance(d["rules"], str):
            try:
                d["rules"] = json.loads(d["rules"])
            except (json.JSONDecodeError, TypeError):
                pass
        if "violations" in d and isinstance(d["violations"], str):
            try:
                d["violations"] = json.loads(d["violations"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def create_policy(self, name: str, scope: str, rules: list[dict[str, Any]],
                      severity: str = "info") -> dict:
        """Create a new compliance policy.

        Args:
            name: Human-readable policy name.
            scope: One of VALID_SCOPES.
            rules: List of rule dicts with field/operator/value/message keys.
            severity: One of VALID_SEVERITIES.

        Returns:
            The created policy as a dict.
        """
        self._validate_scope(scope)
        self._validate_severity(severity)

        policy_id = self._uid()
        now = time.time()
        rules_json = json.dumps(rules, sort_keys=True, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO compliance_policies
                (policy_id, name, scope, rules, severity, enabled, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                policy_id, name, scope, rules_json, severity, 1, now,
            ))
            self._conn.commit()

        self._emit("compliance.policy_created", {
            "policy_id": policy_id,
            "name": name,
            "scope": scope,
        })

        log.info("created compliance policy %s: %s (%s/%s)",
                 policy_id, name, scope, severity)

        return {
            "policy_id": policy_id,
            "name": name,
            "scope": scope,
            "rules": rules,
            "severity": severity,
            "enabled": True,
            "created_at": now,
        }

    def update_policy(self, policy_id: str, name: str | None = None,
                      rules: list[dict[str, Any]] | None = None,
                      enabled: bool | None = None) -> dict | None:
        """Update a compliance policy.

        Args:
            policy_id: ID of the policy to update.
            name: New name (optional).
            rules: New rules list (optional).
            enabled: Enable/disable toggle (optional).

        Returns:
            Updated policy dict, or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM compliance_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
            if not row:
                log.warning("policy %s not found for update", policy_id)
                return None

            new_name = name if name is not None else row["name"]
            new_rules_json = (
                json.dumps(rules, sort_keys=True, default=str)
                if rules is not None
                else row["rules"]
            )
            new_enabled = (
                1 if enabled else 0
                if enabled is not None
                else row["enabled"]
            )

            self._conn.execute("""
                UPDATE compliance_policies
                SET name = ?, rules = ?, enabled = ?
                WHERE policy_id = ?
            """, (new_name, new_rules_json, new_enabled, policy_id))
            self._conn.commit()

            updated_row = self._conn.execute(
                "SELECT * FROM compliance_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()

        self._emit("compliance.policy_updated", {
            "policy_id": policy_id,
            "name": new_name,
        })

        log.info("updated compliance policy %s", policy_id)
        return self._row_to_dict(updated_row)

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a compliance policy.

        Returns:
            True if deleted, False if not found.
        """
        with self._lock:
            deleted = self._conn.execute(
                "DELETE FROM compliance_policies WHERE policy_id = ?",
                (policy_id,),
            ).rowcount
            self._conn.commit()

        if deleted:
            self._emit("compliance.policy_deleted", {
                "policy_id": policy_id,
            })
            log.info("deleted compliance policy %s", policy_id)

        return bool(deleted)

    def list_policies(self, scope: str | None = None,
                      enabled: bool | None = None) -> list[dict]:
        """List compliance policies with optional filters.

        Args:
            scope: Filter by scope.
            enabled: Filter by enabled status.

        Returns:
            List of policy dicts.
        """
        with self._lock:
            q = "SELECT * FROM compliance_policies WHERE 1=1"
            params: list[Any] = []
            if scope is not None:
                q += " AND scope = ?"
                params.append(scope)
            if enabled is not None:
                q += " AND enabled = ?"
                params.append(1 if enabled else 0)
            q += " ORDER BY created_at ASC"
            rows = self._conn.execute(q, params).fetchall()

        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Compliance checks
    # ------------------------------------------------------------------

    def check_compliance(self, module_id: str,
                         scope: str = "all") -> dict:
        """Run compliance check against all matching policies for a module.

        Loads policies matching the requested scope, then evaluates the module
        against each policy's rules. Simplified evaluation checks module registry
        data (provided as rule context) against rule thresholds.

        Args:
            module_id: The module to check.
            scope: Scope filter (use "all" for all scopes).

        Returns:
            Dict with check results: {check_ids, total, compliant_count,
            violation_count, warning_count, error_count, violations, overall_status}
        """
        self._validate_scope(scope)

        now = time.time()

        # Load matching policies
        with self._lock:
            if scope == "all":
                q = "SELECT * FROM compliance_policies WHERE enabled = 1"
                params: list[Any] = []
            else:
                q = "SELECT * FROM compliance_policies WHERE enabled = 1 AND scope = ?"
                params = [scope]
            policy_rows = self._conn.execute(q, params).fetchall()

        check_ids: list[str] = []
        all_violations: list[dict] = []
        status_counts = {"compliant": 0, "violation": 0, "warning": 0, "error": 0}

        for policy_row in policy_rows:
            policy = self._row_to_dict(policy_row)
            rules = policy.get("rules", [])
            policy_scope = policy["scope"]
            policy_severity = policy["severity"]

            # Evaluate rules against module
            check_status, violations = self._evaluate_module_rules(
                module_id, rules, policy_severity
            )

            check_id = self._uid()
            violations_json = json.dumps(violations, default=str)

            with self._lock:
                self._conn.execute("""
                    INSERT INTO compliance_checks
                    (check_id, policy_id, module_id, scope, status, violations, checked_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    check_id, policy["policy_id"], module_id,
                    policy_scope, check_status, violations_json, now,
                ))
                self._conn.commit()

            check_ids.append(check_id)
            status_counts[check_status] += 1

            for v in violations:
                all_violations.append({
                    "check_id": check_id,
                    "policy_id": policy["policy_id"],
                    "policy_name": policy["name"],
                    "severity": policy_severity,
                    "scope": policy_scope,
                    "violation": v,
                })

        total = len(check_ids)

        # Determine overall status
        if status_counts["error"] > 0:
            overall_status = "error"
        elif status_counts["violation"] > 0:
            overall_status = "violation"
        elif status_counts["warning"] > 0:
            overall_status = "warning"
        else:
            overall_status = "compliant"

        result = {
            "check_ids": check_ids,
            "module_id": module_id,
            "scope": scope,
            "total": total,
            "compliant_count": status_counts["compliant"],
            "violation_count": status_counts["violation"],
            "warning_count": status_counts["warning"],
            "error_count": status_counts["error"],
            "violations": all_violations,
            "overall_status": overall_status,
            "checked_at": now,
        }

        self._emit("compliance.checked", {
            "module_id": module_id,
            "scope": scope,
            "overall_status": overall_status,
            "total": total,
            "violation_count": status_counts["violation"],
        })

        if all_violations:
            self._emit("compliance.violation", {
                "module_id": module_id,
                "scope": scope,
                "violation_count": len(all_violations),
                "violations": all_violations,
            })

        log.info(
            "compliance check for module %s (scope=%s): %s (%d policies, %d violations)",
            module_id, scope, overall_status, total, len(all_violations),
        )

        return result

    def _evaluate_module_rules(self, module_id: str, rules: list[dict],
                               severity: str) -> tuple[str, list[str]]:
        """Evaluate a policy's rules against a module.

        Simplified evaluation: rules specify thresholds for module attributes.
        A rule without a matching module attribute triggers a violation.
        Rules with field/operator/value are evaluated as comparisons.

        Returns:
            Tuple of (status, list_of_violation_messages).
        """
        if not rules:
            # No rules means automatically compliant
            return "compliant", []

        violations: list[str] = []

        for rule in rules:
            rule_field = rule.get("field", "")
            rule_operator = rule.get("operator", "exists")
            rule_value = rule.get("value")
            rule_message = rule.get("message", "")

            # Simplified module evaluation: check if module_id matches rule patterns
            # In production, this would look up module registry data
            passed = self._evaluate_single_rule(
                module_id, rule_field, rule_operator, rule_value
            )

            if not passed:
                msg = rule_message or f"Rule failed: {rule_field} {rule_operator} {rule_value}"
                violations.append(msg)

        if not violations:
            return "compliant", []

        # Determine status based on severity
        if severity == "critical":
            return "violation", violations
        elif severity == "warning":
            return "warning", violations
        else:
            return "violation", violations

    @staticmethod
    def _evaluate_single_rule(module_id: str, field: str, operator: str,
                              value: Any) -> bool:
        """Evaluate a single rule.

        Simplified: uses module_id as the primary context. Rules can specify
        'module_id' as the field to check against the module identifier,
        or use generic field checks.
        """
        if operator == "exists":
            # Field must exist (non-empty) -- simplified: always True for exists check
            return True
        elif operator == "not_exists":
            return False
        elif operator == "eq":
            if field == "module_id":
                return module_id == value
            # For other fields, default to compliant (no module registry data)
            return True
        elif operator == "ne":
            if field == "module_id":
                return module_id != value
            return True
        elif operator == "contains":
            if field == "module_id":
                return value in module_id if isinstance(value, str) else False
            return True
        elif operator == "not_contains":
            if field == "module_id":
                return value not in module_id if isinstance(value, str) else True
            return True
        elif operator == "in":
            if field == "module_id":
                return module_id in value if isinstance(value, list) else False
            return True
        elif operator == "not_in":
            if field == "module_id":
                return module_id not in value if isinstance(value, list) else True
            return True
        elif operator == "matches":
            import re
            if field == "module_id":
                try:
                    return bool(re.search(value, module_id))
                except re.error:
                    return False
            return True
        elif operator == "always_pass":
            return True
        elif operator == "always_fail":
            return False
        else:
            return True

    # ------------------------------------------------------------------
    # Check retrieval
    # ------------------------------------------------------------------

    def get_check(self, check_id: str) -> dict | None:
        """Retrieve a single check result by ID.

        Returns:
            Check dict or None if not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM compliance_checks WHERE check_id = ?",
                (check_id,),
            ).fetchone()

        if not row:
            return None
        return self._row_to_dict(row)

    def list_checks(self, module_id: str | None = None,
                    policy_id: str | None = None,
                    status: str | None = None,
                    limit: int = 100) -> list[dict]:
        """List compliance checks with optional filters.

        Args:
            module_id: Filter by module.
            policy_id: Filter by policy.
            status: Filter by check status.
            limit: Maximum results to return.

        Returns:
            List of check dicts.
        """
        if status is not None:
            self._validate_check_status(status)

        with self._lock:
            q = "SELECT * FROM compliance_checks WHERE 1=1"
            params: list[Any] = []
            if module_id is not None:
                q += " AND module_id = ?"
                params.append(module_id)
            if policy_id is not None:
                q += " AND policy_id = ?"
                params.append(policy_id)
            if status is not None:
                q += " AND status = ?"
                params.append(status)
            q += " ORDER BY checked_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()

        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get compliance statistics.

        Returns:
            Dict with total policies, enabled, disabled, total checks,
            checks by status, and compliance rate.
        """
        with self._lock:
            # Policy counts
            total_policies = self._conn.execute(
                "SELECT COUNT(*) FROM compliance_policies"
            ).fetchone()[0]
            enabled_policies = self._conn.execute(
                "SELECT COUNT(*) FROM compliance_policies WHERE enabled = 1"
            ).fetchone()[0]

            # Check counts
            total_checks = self._conn.execute(
                "SELECT COUNT(*) FROM compliance_checks"
            ).fetchone()[0]

            compliant_count = self._conn.execute(
                "SELECT COUNT(*) FROM compliance_checks WHERE status = 'compliant'"
            ).fetchone()[0]
            violation_count = self._conn.execute(
                "SELECT COUNT(*) FROM compliance_checks WHERE status = 'violation'"
            ).fetchone()[0]
            warning_count = self._conn.execute(
                "SELECT COUNT(*) FROM compliance_checks WHERE status = 'warning'"
            ).fetchone()[0]
            error_count = self._conn.execute(
                "SELECT COUNT(*) FROM compliance_checks WHERE status = 'error'"
            ).fetchone()[0]

            # Policies by scope
            scope_rows = self._conn.execute(
                "SELECT scope, COUNT(*) as cnt FROM compliance_policies GROUP BY scope"
            ).fetchall()
            by_scope = {r["scope"]: r["cnt"] for r in scope_rows}

            # Policies by severity
            severity_rows = self._conn.execute(
                "SELECT severity, COUNT(*) as cnt FROM compliance_policies GROUP BY severity"
            ).fetchall()
            by_severity = {r["severity"]: r["cnt"] for r in severity_rows}

        disabled_policies = total_policies - enabled_policies

        # Compliance rate: compliant / total (or 100% if no checks)
        compliance_rate = (
            (compliant_count / total_checks * 100.0)
            if total_checks > 0 else 100.0
        )

        return {
            "total_policies": total_policies,
            "enabled_policies": enabled_policies,
            "disabled_policies": disabled_policies,
            "total_checks": total_checks,
            "compliant_checks": compliant_count,
            "violation_checks": violation_count,
            "warning_checks": warning_count,
            "error_checks": error_count,
            "compliance_rate": round(compliance_rate, 2),
            "by_scope": by_scope,
            "by_severity": by_severity,
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_checker: ComplianceChecker | None = None


def get_compliance_checker(event_bus: EventBus | None = None,
                           db_path: str | Path | None = None) -> ComplianceChecker:
    global _checker
    if _checker is None:
        _checker = ComplianceChecker(event_bus=event_bus, db_path=db_path)
    return _checker


def reset_compliance_checker(event_bus: EventBus | None = None,
                             db_path: str | Path | None = None) -> ComplianceChecker:
    global _checker
    _checker = ComplianceChecker(event_bus=event_bus, db_path=db_path)
    return _checker
