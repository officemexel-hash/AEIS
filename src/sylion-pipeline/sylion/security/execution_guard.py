"""
SYLION Security -- Execution Guard

Policy-based execution approval system with rule evaluation.
Manages execution policies, approval workflows, and execution logging.

Tables:
  execution_policies   -- named policies with scope and rules (JSON)
  execution_approvals  -- approval/denial requests with context
  execution_log        -- audit log of all execution checks

Thread-safe via threading.RLock(). Singleton via get_execution_guard() /
reset_execution_guard().  Emits events via EventBus.
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

log = logging.getLogger("sylion.security.execution_guard")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_POLICY_SCOPES: tuple[str, ...] = ("global", "module", "operation", "resource")
VALID_DECISION_CLASSES: frozenset[str] = frozenset({"D0", "D1", "D2", "D3", "D4", "D5"})
VALID_GATE_TYPES: frozenset[str] = frozenset({
    "blocking", "non_blocking", "batch", "emergency",
    "financial", "legal", "production", "security",
    "external_action", "final", "direction_gate",
    "source_of_truth_gate", "masterplan_gate",
})
VALID_PRIORITIES: frozenset[str] = frozenset({"P0", "P1", "P2", "P3", "P4"})


_governance_hook_registered = False


# ---------------------------------------------------------------------------
# ExecutionGuard
# ---------------------------------------------------------------------------


class ExecutionGuard:
    """Policy-based execution approval and access control.

    Policies define rules (as JSON) scoped to different levels.
    Execution requests go through an approval workflow or are
    auto-evaluated against active policies.
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
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_policies (
                policy_id   TEXT PRIMARY KEY,
                name        TEXT NOT NULL DEFAULT '',
                scope       TEXT NOT NULL DEFAULT 'global',
                rules_json  TEXT NOT NULL DEFAULT '{}',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  REAL NOT NULL DEFAULT 0.0,
                updated_at  REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_approvals (
                request_id          TEXT PRIMARY KEY,
                policy_id           TEXT NOT NULL DEFAULT '',
                execution_context   TEXT NOT NULL DEFAULT '{}',
                status              TEXT NOT NULL DEFAULT 'pending',
                approver            TEXT NOT NULL DEFAULT '',
                reason              TEXT NOT NULL DEFAULT '',
                governance_ticket_id TEXT NOT NULL DEFAULT '',
                created_at          REAL NOT NULL DEFAULT 0.0,
                resolved_at         REAL
            )
        """)
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(execution_approvals)").fetchall()
        }
        if "governance_ticket_id" not in columns:
            self._conn.execute(
                "ALTER TABLE execution_approvals "
                "ADD COLUMN governance_ticket_id TEXT NOT NULL DEFAULT ''"
            )
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_log (
                log_id      TEXT PRIMARY KEY,
                context     TEXT NOT NULL DEFAULT '{}',
                result      TEXT NOT NULL DEFAULT 'denied',
                reason      TEXT NOT NULL DEFAULT '',
                matched_policy TEXT NOT NULL DEFAULT '',
                timestamp   REAL NOT NULL DEFAULT 0.0
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eg_policies_scope ON execution_policies(scope)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eg_policies_active ON execution_policies(is_active)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eg_approvals_status ON execution_approvals(status)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eg_approvals_ticket ON execution_approvals(governance_ticket_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_eg_log_ts ON execution_log(timestamp)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="security.execution_guard",
            ))

    # ------------------------------------------------------------------
    # Policy CRUD
    # ------------------------------------------------------------------

    def create_policy(self, name: str, scope: str = "global",
                      rules_json: dict | str | None = None) -> dict:
        """Create an execution policy. Returns policy dict.

        Raises ValueError if scope is invalid.
        """
        if scope not in VALID_POLICY_SCOPES:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of {VALID_POLICY_SCOPES}"
            )

        policy_id = uuid.uuid4().hex
        now = time.time()

        if isinstance(rules_json, dict):
            rules_str = json.dumps(rules_json, default=str)
        elif isinstance(rules_json, str):
            rules_str = rules_json
        else:
            rules_str = "{}"

        with self._lock:
            self._conn.execute("""
                INSERT INTO execution_policies
                    (policy_id, name, scope, rules_json, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (policy_id, name, scope, rules_str, now, now))
            self._conn.commit()

        self._emit("policy_created", {
            "policy_id": policy_id, "name": name, "scope": scope,
        })
        log.info("created policy %s (scope=%s)", name, scope)
        # Parse rules_json for the return value so callers get a dict
        try:
            rules_parsed = json.loads(rules_str)
        except (json.JSONDecodeError, TypeError):
            rules_parsed = {}
        return {
            "policy_id": policy_id,
            "name": name,
            "scope": scope,
            "rules_json": rules_parsed,
            "is_active": 1,
            "created_at": now,
            "updated_at": now,
        }

    def update_policy(self, policy_id: str, name: str | None = None,
                      scope: str | None = None,
                      rules_json: dict | str | None = None,
                      is_active: int | None = None) -> dict | None:
        """Update policy fields. Returns updated policy dict or None."""
        if scope is not None and scope not in VALID_POLICY_SCOPES:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of {VALID_POLICY_SCOPES}"
            )

        sets: list[str] = []
        params: list[Any] = []

        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if scope is not None:
            sets.append("scope = ?")
            params.append(scope)
        if rules_json is not None:
            rules_str = json.dumps(rules_json, default=str) if isinstance(rules_json, dict) else rules_json
            sets.append("rules_json = ?")
            params.append(rules_str)
        if is_active is not None:
            sets.append("is_active = ?")
            params.append(is_active)

        if not sets:
            return self.get_policy(policy_id)

        sets.append("updated_at = ?")
        params.append(time.time())
        params.append(policy_id)

        with self._lock:
            n = self._conn.execute(
                f"UPDATE execution_policies SET {', '.join(sets)} WHERE policy_id = ?",
                params,
            ).rowcount
            self._conn.commit()

        if not n:
            return None
        log.info("updated policy %s", policy_id[:12])
        return self.get_policy(policy_id)

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy. Returns True if deleted."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM execution_policies WHERE policy_id = ?",
                (policy_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def get_policy(self, policy_id: str) -> dict | None:
        """Get a policy by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM execution_policies WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()
        if not row:
            return None
        result = self._row_to_dict(row)
        try:
            result["rules_json"] = json.loads(result.get("rules_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            result["rules_json"] = {}
        return result

    def list_policies(self, scope: str | None = None) -> list[dict]:
        """List policies, optionally filtered by scope."""
        with self._lock:
            if scope is not None:
                rows = self._conn.execute(
                    "SELECT * FROM execution_policies WHERE scope = ? ORDER BY created_at",
                    (scope,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM execution_policies ORDER BY created_at",
                ).fetchall()
        results = []
        for r in rows:
            d = self._row_to_dict(r)
            try:
                d["rules_json"] = json.loads(d.get("rules_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["rules_json"] = {}
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Approval workflow
    # ------------------------------------------------------------------

    def request_approval(self, policy_id: str,
                         execution_context: dict | str) -> dict:
        """Request execution approval. Returns request dict."""
        ctx = self._context_to_dict(execution_context)
        ctx_str = json.dumps(ctx, default=str)
        request_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO execution_approvals
                    (request_id, policy_id, execution_context, status, approver, reason, created_at)
                VALUES (?, ?, ?, 'pending', '', '', ?)
            """, (request_id, policy_id, ctx_str, now))
            self._conn.commit()

        governance_ticket_id = self._submit_governance_ticket(
            request_id=request_id,
            policy_id=policy_id,
            context=ctx,
        )
        with self._lock:
            self._conn.execute(
                "UPDATE execution_approvals SET governance_ticket_id = ? WHERE request_id = ?",
                (governance_ticket_id, request_id),
            )
            self._conn.commit()

        self._emit("approval_requested", {
            "request_id": request_id, "policy_id": policy_id,
            "governance_ticket_id": governance_ticket_id,
        })
        log.info("approval requested %s for policy %s", request_id[:12], policy_id[:12])
        return {
            "request_id": request_id,
            "policy_id": policy_id,
            "status": "pending",
            "governance_ticket_id": governance_ticket_id,
            "created_at": now,
        }

    def approve_request(self, request_id: str, approver: str) -> dict | None:
        """Approve a pending request. Returns updated request or None."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT governance_ticket_id FROM execution_approvals "
                "WHERE request_id=? AND status='pending'",
                (request_id,),
            ).fetchone()
            n = self._conn.execute(
                "UPDATE execution_approvals SET status='approved', approver=?, resolved_at=? "
                "WHERE request_id=? AND status='pending'",
                (approver, now, request_id),
            ).rowcount
            self._conn.commit()

        if not n:
            return None
        governance_ticket_id = row["governance_ticket_id"] if row else ""
        if governance_ticket_id:
            self._resolve_governance_ticket(
                governance_ticket_id,
                decision="approved",
                reason="Execution Guard approval granted through execution guard endpoint.",
                reviewer=approver,
            )

        self._emit("approval_granted", {
            "request_id": request_id, "approver": approver,
            "governance_ticket_id": governance_ticket_id,
        })
        log.info("approved request %s by %s", request_id[:12], approver)
        return {
            "request_id": request_id,
            "status": "approved",
            "approver": approver,
            "governance_ticket_id": governance_ticket_id,
            "resolved_at": now,
        }

    def deny_request(self, request_id: str, approver: str,
                     reason: str = "") -> dict | None:
        """Deny a pending request. Returns updated request or None."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT governance_ticket_id FROM execution_approvals "
                "WHERE request_id=? AND status='pending'",
                (request_id,),
            ).fetchone()
            n = self._conn.execute(
                "UPDATE execution_approvals SET status='denied', approver=?, reason=?, resolved_at=? "
                "WHERE request_id=? AND status='pending'",
                (approver, reason, now, request_id),
            ).rowcount
            self._conn.commit()

        if not n:
            return None
        governance_ticket_id = row["governance_ticket_id"] if row else ""
        if governance_ticket_id:
            self._resolve_governance_ticket(
                governance_ticket_id,
                decision="rejected",
                reason=reason or "Execution Guard approval denied through execution guard endpoint.",
                reviewer=approver,
            )

        self._emit("approval_denied", {
            "request_id": request_id, "approver": approver, "reason": reason,
            "governance_ticket_id": governance_ticket_id,
        })
        log.info("denied request %s by %s: %s", request_id[:12], approver, reason)
        return {
            "request_id": request_id,
            "status": "denied",
            "approver": approver,
            "reason": reason,
            "governance_ticket_id": governance_ticket_id,
            "resolved_at": now,
        }

    def get_approval_request(self, request_id: str) -> dict | None:
        """Return one approval request with parsed context, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM execution_approvals WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if not row:
            return None
        result = self._row_to_dict(row)
        try:
            result["execution_context"] = json.loads(result.get("execution_context") or "{}")
        except (json.JSONDecodeError, TypeError):
            result["execution_context"] = {"raw": result.get("execution_context", "")}
        return result

    # ------------------------------------------------------------------
    # Execution checking
    # ------------------------------------------------------------------

    def check_execution(self, context: dict | str) -> dict:
        """Evaluate context against active policies.

        Returns dict with allowed (bool), reason, matched_policy.
        Default is denied if no policy matches.
        """
        ctx = context if isinstance(context, dict) else {"raw": context}
        ctx_str = json.dumps(ctx, default=str)

        with self._lock:
            policies = self._conn.execute(
                "SELECT * FROM execution_policies WHERE is_active = 1",
            ).fetchall()

        allowed = False
        reason = "no matching policy"
        matched_policy = ""

        for pol in policies:
            rules = {}
            try:
                rules = json.loads(pol["rules_json"])
            except (json.JSONDecodeError, TypeError):
                pass

            action = rules.get("action", "deny")
            match_scope = rules.get("match_scope", pol["scope"])

            if self._context_matches(ctx, match_scope, rules):
                allowed = action == "allow"
                reason = rules.get("reason", f"policy '{pol['name']}' matched")
                matched_policy = pol["policy_id"]
                break

        log_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._conn.execute("""
                INSERT INTO execution_log (log_id, context, result, reason, matched_policy, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (log_id, ctx_str, "allowed" if allowed else "denied",
                  reason, matched_policy, now))
            self._conn.commit()

        self._emit("execution_checked", {
            "log_id": log_id,
            "allowed": allowed,
            "reason": reason,
            "matched_policy": matched_policy,
        })
        return {
            "allowed": allowed,
            "reason": reason,
            "matched_policy": matched_policy,
            "log_id": log_id,
        }

    def get_execution_log(self, limit: int = 100) -> list[dict]:
        """Get execution log entries."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM execution_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Rule-style API (used by ``sylion.api.security_routes`` /guard/* routes)
    #
    # The rule-style surface is a thin facade over execution_policies: each
    # "rule" is a policy whose rules_json carries {action, resource_pattern,
    # priority}. We keep a separate methods set so the route layer can keep
    # its rule vocabulary without leaking policy-internals to clients.
    # ------------------------------------------------------------------

    def add_rule(self, rule_id_or_name: str, name: str | None = None,
                 *, action: str = "allow",
                 resource_pattern: str = "*", priority: int = 0,
                 rule_id: str | None = None) -> dict:
        """Register a guard rule.

        Two calling styles supported:
        - ``add_rule(rule_id, name, action=..., resource_pattern=..., priority=...)``
          (route style + tests/test_extra.py)
        - ``add_rule(name)`` -- legacy single-arg, uses name as both id and label.
        """
        import json as _json

        if name is None:
            actual_name = rule_id_or_name
            actual_rule_id = rule_id or rule_id_or_name
        else:
            actual_rule_id = rule_id or rule_id_or_name
            actual_name = name

        rules_json = _json.dumps({
            "action": action,
            "resource_pattern": resource_pattern,
            "priority": int(priority),
            "rule_id": actual_rule_id,
        })
        policy = self.create_policy(
            name=actual_name or actual_rule_id or "rule",
            scope="resource",
            rules_json=rules_json,
        )
        return {
            "rule_id": policy["policy_id"],
            "name": policy["name"],
            "action": action,
            "resource_pattern": resource_pattern,
            "priority": int(priority),
            "enabled": bool(policy.get("is_active", 1)),
            "created_at": policy["created_at"],
        }

    def list_rules(self, enabled_only: bool = True) -> list[dict]:
        import json as _json

        with self._lock:
            sql = "SELECT * FROM execution_policies"
            params: tuple = ()
            if enabled_only:
                sql += " WHERE is_active = 1"
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict] = []
        for r in rows:
            try:
                rules = _json.loads(r["rules_json"] or "{}")
            except Exception:
                rules = {}
            out.append({
                "rule_id": r["policy_id"],
                "name": r["name"],
                "action": rules.get("action", "allow"),
                "resource_pattern": rules.get("resource_pattern", "*"),
                "priority": int(rules.get("priority", 0)),
                "enabled": bool(r["is_active"]),
                "created_at": r["created_at"],
            })
        return out

    def delete_rule(self, rule_id: str) -> bool:
        """Remove a rule by id. Returns True if a row was deleted.

        Hard-delete from execution_policies; the prior soft-disable path
        (is_active=0) is still respected by check() but admin-driven
        removal needs a permanent operation so cleared rule sets stay clear.
        """
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM execution_policies WHERE policy_id = ?",
                (rule_id,),
            ).rowcount
            self._conn.commit()
        if n:
            self._emit("execution_guard.rule_deleted",
                       {"rule_id": rule_id})
        return bool(n)

    def disable_rule(self, rule_id: str) -> bool:
        """Soft-disable a rule (is_active=0). Reversible via enable_rule."""
        with self._lock:
            n = self._conn.execute(
                "UPDATE execution_policies SET is_active = 0 "
                "WHERE policy_id = ? AND is_active = 1",
                (rule_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def enable_rule(self, rule_id: str) -> bool:
        with self._lock:
            n = self._conn.execute(
                "UPDATE execution_policies SET is_active = 1 "
                "WHERE policy_id = ? AND is_active = 0",
                (rule_id,),
            ).rowcount
            self._conn.commit()
        return bool(n)

    def get_rule(self, rule_id: str) -> dict | None:
        import json as _json

        policy = self.get_policy(rule_id)
        if policy is None:
            return None
        try:
            rules = _json.loads(policy.get("rules_json") or "{}")
        except Exception:
            rules = {}
        return {
            "rule_id": policy["policy_id"],
            "name": policy["name"],
            "action": rules.get("action", "allow"),
            "resource_pattern": rules.get("resource_pattern", "*"),
            "priority": int(rules.get("priority", 0)),
            "enabled": bool(policy.get("is_active", 1)),
            "created_at": policy["created_at"],
        }

    def check(self, resource: str, action: str) -> dict:
        """Check whether (resource, action) is permitted by the active rules."""
        rules = self.list_rules(enabled_only=True)
        # Highest-priority deny wins; otherwise highest-priority allow wins;
        # default deny when no rule matches.
        rules_sorted = sorted(rules, key=lambda r: -int(r.get("priority", 0)))
        decision: str = "deny"
        matched: str = ""
        for rule in rules_sorted:
            pat = rule.get("resource_pattern", "*")
            if pat == "*" or pat == resource or (pat.endswith("*") and resource.startswith(pat[:-1])):
                if rule["action"] == "deny":
                    decision = "deny"
                    matched = rule["rule_id"]
                    break
                if decision == "deny" and rule["action"] == "allow":
                    decision = "allow"
                    matched = rule["rule_id"]

        log_id = uuid.uuid4().hex
        ts = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO execution_log (log_id, context, result, reason, matched_policy, timestamp) "
                "VALUES (?,?,?,?,?,?)",
                (log_id, f'{{"resource":"{resource}","action":"{action}"}}', decision, "rule-eval", matched, ts),
            )
            self._conn.commit()
        return {"decision": decision, "matched_rule_id": matched, "timestamp": ts}

    def get_checks(self, resource: str | None = None, limit: int = 50) -> list[dict]:
        with self._lock:
            if resource:
                rows = self._conn.execute(
                    "SELECT * FROM execution_log WHERE context LIKE ? ORDER BY timestamp DESC LIMIT ?",
                    (f'%"resource":"{resource}"%', limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM execution_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Governance ticket bridge
    # ------------------------------------------------------------------

    @staticmethod
    def _context_to_dict(context: dict | str) -> dict[str, Any]:
        if isinstance(context, dict):
            return dict(context)
        try:
            parsed = json.loads(context)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return {"raw": str(context)}

    @staticmethod
    def _decision_class_from_context(context: dict[str, Any]) -> str:
        value = str(
            context.get("decision_class")
            or context.get("decisionClass")
            or context.get("d_level")
            or context.get("dLevel")
            or "D3"
        ).upper()
        return value if value in VALID_DECISION_CLASSES else "D3"

    @staticmethod
    def _priority_from_context(context: dict[str, Any], decision_class: str) -> str:
        explicit = str(context.get("priority") or "").upper()
        if explicit in VALID_PRIORITIES:
            return explicit
        if decision_class == "D5":
            return "P0"
        if decision_class in {"D3", "D4"}:
            return "P1"
        if decision_class == "D2":
            return "P2"
        return "P3"

    @staticmethod
    def _gate_type_from_context(context: dict[str, Any]) -> str:
        explicit = str(context.get("gate_type") or context.get("gateType") or "").strip()
        if explicit in VALID_GATE_TYPES:
            return explicit
        haystack = " ".join(
            str(context.get(key, ""))
            for key in ("action", "operation", "resource", "module", "scope", "raw")
        ).lower()
        if any(token in haystack for token in ("deploy", "production", "prod")):
            return "production"
        if any(token in haystack for token in ("external", "network", "vps", "cloud")):
            return "external_action"
        if "security" in haystack:
            return "security"
        if any(token in haystack for token in ("cost", "budget", "funding", "payment")):
            return "financial"
        return "blocking"

    @staticmethod
    def _project_id_from_context(context: dict[str, Any]) -> str | None:
        value = (
            context.get("project_id")
            or context.get("projectId")
            or context.get("project")
        )
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _submit_governance_ticket(
        self,
        *,
        request_id: str,
        policy_id: str,
        context: dict[str, Any],
    ) -> str:
        from sylion.governance.tickets import GovernanceTicket, submit

        decision_class = self._decision_class_from_context(context)
        action = str(context.get("action") or context.get("operation") or "").strip()
        title = str(
            context.get("title")
            or f"Execution Guard approval: {action or policy_id[:12]}"
        )
        summary = str(
            context.get("summary")
            or f"Policy {policy_id} requested approval for {action or 'execution'}."
        )
        requested_by = str(
            context.get("requested_by")
            or context.get("actor")
            or context.get("operator_id")
            or "execution_guard"
        )
        ticket = GovernanceTicket(
            origin="execution_guard",
            project_id=self._project_id_from_context(context),
            decision_class=decision_class,
            gate_type=self._gate_type_from_context(context),
            priority=self._priority_from_context(context, decision_class),
            title=title,
            summary=summary,
            payload={
                "execution_guard_request_id": request_id,
                "policy_id": policy_id,
                "execution_context": context,
            },
            requested_by=requested_by,
        )
        return submit(ticket)

    @staticmethod
    def _resolve_governance_ticket(
        ticket_id: str,
        *,
        decision: str,
        reason: str,
        reviewer: str,
    ) -> None:
        try:
            from sylion.governance.tickets import fetch_by_id, resolve

            ticket = fetch_by_id(ticket_id)
            if ticket is None or ticket.state != "pending":
                return
            resolve(ticket_id, decision, reason=reason, reviewer=reviewer)
        except Exception:
            log.warning("execution guard governance ticket resolve failed", exc_info=True)

    def sync_approval_from_governance_ticket(
        self,
        ticket: Any,
        decision: str,
    ) -> None:
        if getattr(ticket, "origin", "") != "execution_guard":
            return
        payload = getattr(ticket, "payload", {}) or {}
        if not isinstance(payload, dict):
            return
        request_id = str(payload.get("execution_guard_request_id") or "")
        if not request_id:
            return
        status = {
            "approved": "approved",
            "rejected": "denied",
            "expired": "expired",
        }.get(decision)
        if status is None:
            return
        approver = getattr(ticket, "resolved_by", None) or "governance_ticket"
        reason = getattr(ticket, "resolution_reason", None) or ""
        resolved_at = getattr(ticket, "resolved_at", None) or time.time()
        with self._lock:
            self._conn.execute(
                """
                UPDATE execution_approvals
                SET status = ?, approver = ?, reason = ?, resolved_at = ?
                WHERE request_id = ? AND status = 'pending'
                """,
                (status, approver, reason, float(resolved_at), request_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _context_matches(ctx: dict, match_scope: str, rules: dict) -> bool:
        """Check if context matches the policy's scope and rules."""
        required_key = rules.get("required_key", "")
        required_value = rules.get("required_value", "")

        if match_scope == "global":
            return True
        elif match_scope == "module":
            return ctx.get("module", "") == required_value if required_key == "module" else True
        elif match_scope == "operation":
            return ctx.get("operation", "") == required_value if required_key == "operation" else True
        elif match_scope == "resource":
            return ctx.get("resource", "") == required_value if required_key == "resource" else True
        return False


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_guard: ExecutionGuard | None = None


def _governance_ticket_resolve_hook(ticket: Any, decision: str) -> None:
    if _guard is None:
        return
    _guard.sync_approval_from_governance_ticket(ticket, decision)


def _register_governance_bridge() -> None:
    global _governance_hook_registered
    try:
        from sylion.governance.tickets import register_post_resolve_hook

        register_post_resolve_hook(_governance_ticket_resolve_hook)
        _governance_hook_registered = True
    except Exception:
        log.warning("execution guard governance bridge registration failed", exc_info=True)


def get_execution_guard(db_path: str | Path | None = None,
                        event_bus: EventBus | None = None) -> ExecutionGuard:
    """Get or create the global ExecutionGuard singleton."""
    global _guard
    if _guard is None:
        _guard = ExecutionGuard(db_path, event_bus)
    _register_governance_bridge()
    return _guard


def reset_execution_guard(db_path: str | Path | None = None,
                          event_bus: EventBus | None = None) -> ExecutionGuard:
    """Reset the global ExecutionGuard singleton (for testing)."""
    global _guard
    _guard = ExecutionGuard(db_path, event_bus)
    _register_governance_bridge()
    return _guard
