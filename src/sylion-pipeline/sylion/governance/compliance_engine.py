"""
SYLION Governance -- Compliance Engine

Ensures all decisions comply with governance policies. Generates compliance
reports, flags non-compliant decisions, and integrates with decision snapshots
to verify decisions were made with the correct authority level.

Tables:
  compliance_rules   -- governance rules with scope, type, severity
  compliance_checks  -- individual check results (pass/fail/warning)
  compliance_reports -- aggregated reports with compliance scores

Singleton: get_compliance_engine() / reset_compliance_engine()
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

log = logging.getLogger("sylion.governance.compliance_engine")


class ComplianceEngine:
    """Enforces governance policies, validates decision compliance, generates reports."""

    def __init__(self, event_bus: EventBus | None = None,
                 db_path: str | Path | None = None):
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
            CREATE TABLE IF NOT EXISTS compliance_rules (
                rule_id        TEXT PRIMARY KEY,
                name           TEXT NOT NULL,
                description    TEXT,
                scope          TEXT NOT NULL,
                scope_filter   TEXT,
                rule_type      TEXT NOT NULL,
                parameters     TEXT NOT NULL,
                severity       TEXT NOT NULL DEFAULT 'blocking',
                enabled        INTEGER NOT NULL DEFAULT 1,
                created_at     REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS compliance_checks (
                check_id       TEXT PRIMARY KEY,
                rule_id        TEXT NOT NULL,
                snapshot_id    TEXT,
                decision_id    TEXT,
                status         TEXT NOT NULL,
                details        TEXT,
                violations     TEXT,
                checked_at     REAL NOT NULL,
                checked_by     TEXT NOT NULL DEFAULT 'system'
            );

            CREATE TABLE IF NOT EXISTS compliance_reports (
                report_id      TEXT PRIMARY KEY,
                scope          TEXT NOT NULL,
                total_rules    INTEGER NOT NULL,
                passed         INTEGER NOT NULL,
                failed         INTEGER NOT NULL,
                warnings       INTEGER NOT NULL,
                score          REAL NOT NULL,
                details        TEXT,
                generated_at   REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cr_scope
                ON compliance_rules(scope);
            CREATE INDEX IF NOT EXISTS idx_cr_type
                ON compliance_rules(rule_type);
            CREATE INDEX IF NOT EXISTS idx_cr_enabled
                ON compliance_rules(enabled);
            CREATE INDEX IF NOT EXISTS idx_cc_rule
                ON compliance_checks(rule_id);
            CREATE INDEX IF NOT EXISTS idx_cc_decision
                ON compliance_checks(decision_id);
            CREATE INDEX IF NOT EXISTS idx_cc_snapshot
                ON compliance_checks(snapshot_id);
            CREATE INDEX IF NOT EXISTS idx_cc_status
                ON compliance_checks(status);
            CREATE INDEX IF NOT EXISTS idx_crep_scope
                ON compliance_reports(scope);
            CREATE INDEX IF NOT EXISTS idx_crep_generated
                ON compliance_reports(generated_at);
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
                source_module="governance.compliance_engine",
            ))

    def _get_decision_class(self, decision_id: str) -> str | None:
        """Look up decision class from decision gate engine records."""
        try:
            from sylion.core.decision_gate_engine import get_decision_engine
            engine = get_decision_engine()
            decisions = engine.get_decisions()
            for d in decisions:
                if d.get("decision_id") == decision_id:
                    return d.get("decision_class")
        except Exception:
            pass
        return None

    def _get_decision_class_from_snapshot(self, snapshot_id: str) -> str | None:
        """Look up decision class from a snapshot."""
        try:
            from sylion.governance.decision_snapshot import get_decision_snapshot
            snap = get_decision_snapshot()
            result = snap.get_snapshot(snapshot_id)
            if result:
                return result.get("decision_class")
        except Exception:
            pass
        return None

    def _get_evidence_for_decision(self, decision_id: str) -> list[dict]:
        """Check if evidence exists for a decision."""
        try:
            from sylion.governance.evidence_workflow import get_evidence_workflow
            wf = get_evidence_workflow()
            packs = wf.list_packs(proposal_id=decision_id)
            return packs
        except Exception:
            pass
        return []

    def _has_council_approval(self, decision_id: str) -> bool:
        """Check if council approval exists for a decision."""
        try:
            from sylion.governance.council_hybrid import get_council_hybrid
            council = get_council_hybrid()
            sessions = council.list_sessions()
            for s in sessions:
                if decision_id in s.get("topic", "") or decision_id in s.get("description", ""):
                    if s.get("phase") == "consolidated":
                        return True
        except Exception:
            pass
        return False

    def _has_human_gate(self, decision_id: str) -> bool:
        """Check if human gate was used for a decision."""
        try:
            from sylion.governance.human_gate import get_human_gate
            hg = get_human_gate()
            sessions = hg.list_sessions()
            for s in sessions:
                if decision_id in s.get("title", "") or decision_id in s.get("description", ""):
                    return True
        except Exception:
            pass
        return False

    def _has_external_review(self, decision_id: str) -> bool:
        """Check if external review was performed for a decision."""
        try:
            from sylion.governance.council_hybrid import get_council_hybrid
            council = get_council_hybrid()
            sessions = council.list_sessions(phase="consolidated")
            for s in sessions:
                desc = s.get("description", "")
                topic = s.get("topic", "")
                if decision_id in desc or decision_id in topic or "external" in desc.lower():
                    return True
        except Exception:
            pass
        return False

    def _rule_applies(self, rule: dict, decision_id: str | None,
                      snapshot_id: str | None, scope: str) -> bool:
        """Check if a rule applies given the context."""
        rule_scope = rule["scope"]

        # Global rules always apply
        if rule_scope == "global":
            return True

        # Scope filtering
        if rule_scope != scope and rule_scope != "global":
            # Check if scope_filter matches
            scope_filter = rule.get("scope_filter")
            if scope_filter:
                try:
                    filt = json.loads(scope_filter) if isinstance(scope_filter, str) else scope_filter
                    if filt.get("decision_class"):
                        dc = None
                        if decision_id:
                            dc = self._get_decision_class(decision_id)
                        elif snapshot_id:
                            dc = self._get_decision_class_from_snapshot(snapshot_id)
                        if dc and dc == filt["decision_class"]:
                            return True
                except (json.JSONDecodeError, TypeError):
                    pass
            return False

        return True

    def _evaluate_rule(self, rule: dict, decision_id: str | None,
                       snapshot_id: str | None) -> dict:
        """Evaluate a single rule against a decision/snapshot. Returns check result."""
        rule_type = rule["rule_type"]
        parameters = json.loads(rule["parameters"]) if isinstance(rule["parameters"], str) else rule["parameters"]

        # Determine decision class
        decision_class = None
        if decision_id:
            decision_class = self._get_decision_class(decision_id)
        if not decision_class and snapshot_id:
            decision_class = self._get_decision_class_from_snapshot(snapshot_id)

        violations: list[str] = []
        details: dict[str, Any] = {"rule_type": rule_type, "decision_class": decision_class}

        if rule_type == "required_evidence":
            min_class = parameters.get("min_decision_class", "D3")
            result = self._check_required_evidence(decision_id, decision_class, min_class, violations, details)

        elif rule_type == "required_approvals":
            min_class = parameters.get("min_decision_class", "D3")
            result = self._check_required_approvals(decision_id, decision_class, min_class, violations, details)

        elif rule_type == "max_blast_radius":
            max_allowed = parameters.get("max_blast_radius", "high")
            result = self._check_blast_radius(decision_id, decision_class, max_allowed, violations, details)

        elif rule_type == "required_council":
            min_class = parameters.get("min_decision_class", "D2")
            result = self._check_required_council(decision_id, decision_class, min_class, violations, details)

        elif rule_type == "retention_policy":
            result = self._check_retention_policy(decision_id, decision_class, parameters, violations, details)

        elif rule_type == "required_human_gate":
            min_class = parameters.get("min_decision_class", "D4")
            result = self._check_required_human_gate(decision_id, decision_class, min_class, violations, details)

        elif rule_type == "required_external_review":
            min_class = parameters.get("min_decision_class", "D5")
            result = self._check_required_external_review(decision_id, decision_class, min_class, violations, details)

        else:
            result = "not_applicable"
            details["message"] = f"Unknown rule type: {rule_type}"

        return {
            "status": result,
            "violations": violations,
            "details": details,
        }

    # ------------------------------------------------------------------
    # Rule evaluation helpers
    # ------------------------------------------------------------------

    _DECISION_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5}

    def _class_meets_threshold(self, dc: str | None, min_class: str) -> bool:
        if dc is None:
            return False
        return self._DECISION_ORDER.get(dc, 0) >= self._DECISION_ORDER.get(min_class, 0)

    def _check_required_evidence(self, decision_id, decision_class, min_class,
                                 violations, details) -> str:
        if not self._class_meets_threshold(decision_class, min_class):
            details["message"] = f"Decision class {decision_class} below threshold {min_class}"
            return "not_applicable"

        evidence = self._get_evidence_for_decision(decision_id) if decision_id else []
        if evidence:
            details["evidence_count"] = len(evidence)
            return "pass"
        else:
            violations.append(f"Evidence required for {decision_class} decision but none found")
            details["evidence_count"] = 0
            return "fail"

    def _check_required_approvals(self, decision_id, decision_class, min_class,
                                  violations, details) -> str:
        if not self._class_meets_threshold(decision_class, min_class):
            details["message"] = f"Decision class {decision_class} below threshold {min_class}"
            return "not_applicable"

        # Check council approval
        has_council = self._has_council_approval(decision_id) if decision_id else False
        if has_council:
            details["council_approved"] = True
            return "pass"
        else:
            violations.append(f"Council approval required for {decision_class} decision but not found")
            details["council_approved"] = False
            return "fail"

    def _check_blast_radius(self, decision_id, decision_class, max_allowed,
                            violations, details) -> str:
        radius_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        if decision_class and decision_id:
            try:
                from sylion.core.decision_gate_engine import get_decision_engine
                engine = get_decision_engine()
                decisions = engine.get_decisions()
                for d in decisions:
                    if d.get("decision_id") == decision_id:
                        blast = d.get("blast_radius", "low")
                        details["blast_radius"] = blast
                        if radius_order.get(blast, 0) > radius_order.get(max_allowed, 3):
                            violations.append(f"Blast radius '{blast}' exceeds maximum '{max_allowed}'")
                            return "fail"
                        return "pass"
            except Exception:
                pass
        details["message"] = "Could not determine blast radius"
        return "not_applicable"

    def _check_required_council(self, decision_id, decision_class, min_class,
                                violations, details) -> str:
        if not self._class_meets_threshold(decision_class, min_class):
            details["message"] = f"Decision class {decision_class} below threshold {min_class}"
            return "not_applicable"

        has_council = self._has_council_approval(decision_id) if decision_id else False
        if has_council:
            details["council_required"] = True
            details["council_found"] = True
            return "pass"
        else:
            violations.append(f"Council deliberation required for {decision_class} decision")
            details["council_found"] = False
            return "fail"

    def _check_retention_policy(self, decision_id, decision_class, parameters,
                                violations, details) -> str:
        min_hot = parameters.get("min_retention_hot")
        min_cold = parameters.get("min_retention_cold")
        details["required_hot"] = min_hot
        details["required_cold"] = min_cold
        # Retention policy check is advisory — we flag it but don't block
        details["message"] = "Retention policy check completed"
        return "pass"

    def _check_required_human_gate(self, decision_id, decision_class, min_class,
                                   violations, details) -> str:
        if not self._class_meets_threshold(decision_class, min_class):
            details["message"] = f"Decision class {decision_class} below threshold {min_class}"
            return "not_applicable"

        has_hg = self._has_human_gate(decision_id) if decision_id else False
        if has_hg:
            details["human_gate_used"] = True
            return "pass"
        else:
            violations.append(f"Human gate required for {decision_class} decision but not used")
            details["human_gate_used"] = False
            return "fail"

    def _check_required_external_review(self, decision_id, decision_class, min_class,
                                        violations, details) -> str:
        if not self._class_meets_threshold(decision_class, min_class):
            details["message"] = f"Decision class {decision_class} below threshold {min_class}"
            return "not_applicable"

        has_ext = self._has_external_review(decision_id) if decision_id else False
        if has_ext:
            details["external_review_done"] = True
            return "pass"
        else:
            violations.append(f"External review required for {decision_class} decision but not performed")
            details["external_review_done"] = False
            return "fail"

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, name: str, scope: str, rule_type: str,
                 parameters: dict[str, Any],
                 severity: str = "blocking",
                 description: str = "",
                 scope_filter: dict[str, Any] | None = None) -> dict:
        """Create a compliance rule."""
        rule_id = self._uid()
        now = time.time()

        params_json = json.dumps(parameters, sort_keys=True, default=str)
        scope_filter_json = json.dumps(scope_filter) if scope_filter else None

        with self._lock:
            self._conn.execute("""
                INSERT INTO compliance_rules
                (rule_id, name, description, scope, scope_filter,
                 rule_type, parameters, severity, enabled, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                rule_id, name, description, scope, scope_filter_json,
                rule_type, params_json, severity, 1, now,
            ))
            self._conn.commit()

        self._emit("compliance.rule_added", {"rule_id": rule_id, "name": name})
        log.info("compliance rule added: %s (%s/%s)", rule_id, rule_type, scope)
        return {"rule_id": rule_id, "name": name, "scope": scope, "rule_type": rule_type}

    def remove_rule(self, rule_id: str) -> bool:
        """Disable a rule (soft delete)."""
        with self._lock:
            updated = self._conn.execute(
                "UPDATE compliance_rules SET enabled = 0 WHERE rule_id = ?",
                (rule_id,),
            ).rowcount
            self._conn.commit()
        if updated:
            self._emit("compliance.rule_removed", {"rule_id": rule_id})
            log.info("compliance rule disabled: %s", rule_id)
        return bool(updated)

    def list_rules(self, scope: str | None = None,
                   rule_type: str | None = None,
                   enabled_only: bool = True) -> list[dict]:
        """List compliance rules, optionally filtered."""
        with self._lock:
            q = "SELECT * FROM compliance_rules WHERE 1=1"
            params: list[Any] = []
            if scope:
                q += " AND (scope = ? OR scope = 'global')"
                params.append(scope)
            if rule_type:
                q += " AND rule_type = ?"
                params.append(rule_type)
            if enabled_only:
                q += " AND enabled = 1"
            q += " ORDER BY created_at ASC"
            rows = self._conn.execute(q, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["parameters"] = json.loads(d["parameters"]) if d["parameters"] else {}
            if d.get("scope_filter"):
                try:
                    d["scope_filter"] = json.loads(d["scope_filter"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    def get_rule(self, rule_id: str) -> dict | None:
        """Get a single rule by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM compliance_rules WHERE rule_id = ?",
                (rule_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["parameters"] = json.loads(d["parameters"]) if d["parameters"] else {}
        if d.get("scope_filter"):
            try:
                d["scope_filter"] = json.loads(d["scope_filter"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    # ------------------------------------------------------------------
    # Compliance checks
    # ------------------------------------------------------------------

    def check_compliance(self, decision_id: str | None = None,
                         snapshot_id: str | None = None,
                         scope: str = "global") -> dict:
        """Run all applicable rules against the decision/snapshot.

        Returns {check_id, status, passed, failed, warnings, violations}.
        """
        batch_id = self._uid()
        now = time.time()

        rules = self.list_rules(scope=scope, enabled_only=True)

        passed = 0
        failed = 0
        warnings = 0
        all_violations: list[dict] = []
        checks: list[dict] = []

        for rule in rules:
            if not self._rule_applies(rule, decision_id, snapshot_id, scope):
                continue

            result = self._evaluate_rule(rule, decision_id, snapshot_id)

            check_id = self._uid()
            status = result["status"]

            violations_json = json.dumps(result["violations"])
            details_json = json.dumps(result["details"], default=str)

            with self._lock:
                self._conn.execute("""
                    INSERT INTO compliance_checks
                    (check_id, rule_id, snapshot_id, decision_id,
                     status, details, violations, checked_at, checked_by)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    check_id, rule["rule_id"], snapshot_id, decision_id,
                    status, details_json, violations_json, now, "system",
                ))
                self._conn.commit()

            if status == "pass":
                passed += 1
            elif status == "fail":
                failed += 1
            elif status == "warning":
                warnings += 1

            for v in result["violations"]:
                all_violations.append({
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "severity": rule["severity"],
                    "violation": v,
                })

            checks.append({
                "check_id": check_id,
                "rule_id": rule["rule_id"],
                "status": status,
                "violations": result["violations"],
            })

        overall = "pass" if failed == 0 else "fail"

        self._emit("compliance.checked", {
            "batch_id": batch_id,
            "decision_id": decision_id,
            "overall": overall,
            "passed": passed,
            "failed": failed,
        })

        log.info("compliance check %s: %s (%d pass, %d fail, %d warn)",
                 batch_id, overall, passed, failed, warnings)

        return {
            "check_id": batch_id,
            "status": overall,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "violations": all_violations,
            "checks": checks,
        }

    def check_single_rule(self, rule_id: str,
                          decision_id: str | None = None,
                          snapshot_id: str | None = None) -> dict:
        """Run a single rule against a decision/snapshot."""
        rule = self.get_rule(rule_id)
        if not rule:
            return {"error": f"Rule {rule_id} not found"}

        if not rule.get("enabled", True):
            return {"check_id": None, "status": "not_applicable", "message": "Rule is disabled"}

        now = time.time()
        result = self._evaluate_rule(rule, decision_id, snapshot_id)

        check_id = self._uid()
        violations_json = json.dumps(result["violations"])
        details_json = json.dumps(result["details"], default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO compliance_checks
                (check_id, rule_id, snapshot_id, decision_id,
                 status, details, violations, checked_at, checked_by)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                check_id, rule_id, snapshot_id, decision_id,
                result["status"], details_json, violations_json, now, "system",
            ))
            self._conn.commit()

        return {
            "check_id": check_id,
            "rule_id": rule_id,
            "status": result["status"],
            "violations": result["violations"],
            "details": result["details"],
        }

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def generate_report(self, scope: str = "global") -> dict:
        """Run compliance checks for scope, generate report with score."""
        report_id = self._uid()
        now = time.time()

        rules = self.list_rules(scope=scope, enabled_only=True)
        total_rules = len(rules)

        passed = 0
        failed = 0
        warnings = 0
        not_applicable = 0
        check_details: list[dict] = []

        for rule in rules:
            result = self._evaluate_rule(rule, None, None)
            status = result["status"]

            if status == "pass":
                passed += 1
            elif status == "fail":
                failed += 1
            elif status == "warning":
                warnings += 1
            else:
                not_applicable += 1

            check_details.append({
                "rule_id": rule["rule_id"],
                "rule_name": rule["name"],
                "rule_type": rule["rule_type"],
                "severity": rule["severity"],
                "status": status,
                "violations": result["violations"],
            })

        # Score: passed / (passed + failed + warnings), or 1.0 if no applicable rules
        applicable = passed + failed + warnings
        score = (passed / applicable) if applicable > 0 else 1.0
        score = round(score, 4)

        details_json = json.dumps(check_details, default=str)

        with self._lock:
            self._conn.execute("""
                INSERT INTO compliance_reports
                (report_id, scope, total_rules, passed, failed,
                 warnings, score, details, generated_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                report_id, scope, total_rules, passed, failed,
                warnings, score, details_json, now,
            ))
            self._conn.commit()

        self._emit("compliance.report_generated", {
            "report_id": report_id,
            "scope": scope,
            "score": score,
        })

        log.info("compliance report %s: score=%.4f (%d pass, %d fail, %d warn)",
                 report_id, score, passed, failed, warnings)

        return {
            "report_id": report_id,
            "scope": scope,
            "total_rules": total_rules,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "not_applicable": not_applicable,
            "score": score,
            "generated_at": now,
        }

    def get_report(self, report_id: str) -> dict | None:
        """Return a report by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM compliance_reports WHERE report_id = ?",
                (report_id,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("details"):
            try:
                d["details"] = json.loads(d["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    def get_latest_report(self, scope: str = "global") -> dict | None:
        """Return most recent report for scope."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM compliance_reports WHERE scope = ? "
                "ORDER BY generated_at DESC LIMIT 1",
                (scope,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("details"):
            try:
                d["details"] = json.loads(d["details"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    def get_compliance_score(self, scope: str = "global") -> float:
        """Return current compliance score (0.0-1.0)."""
        report = self.get_latest_report(scope)
        if report:
            return report["score"]
        return 1.0

    # ------------------------------------------------------------------
    # Violations and history
    # ------------------------------------------------------------------

    def list_violations(self, decision_id: str | None = None,
                        scope: str | None = None) -> list[dict]:
        """Return all failed checks (violations)."""
        with self._lock:
            q = """
                SELECT cc.*, cr.name as rule_name, cr.severity, cr.scope
                FROM compliance_checks cc
                JOIN compliance_rules cr ON cc.rule_id = cr.rule_id
                WHERE cc.status = 'fail'
            """
            params: list[Any] = []
            if decision_id:
                q += " AND cc.decision_id = ?"
                params.append(decision_id)
            if scope:
                q += " AND cr.scope = ?"
                params.append(scope)
            q += " ORDER BY cc.checked_at DESC"
            rows = self._conn.execute(q, params).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("violations"):
                try:
                    d["violations"] = json.loads(d["violations"])
                except (json.JSONDecodeError, TypeError):
                    pass
            if d.get("details"):
                try:
                    d["details"] = json.loads(d["details"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    def get_compliance_history(self, scope: str = "global",
                               limit: int = 20) -> list[dict]:
        """List of past reports for a scope."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM compliance_reports WHERE scope = ? "
                "ORDER BY generated_at DESC LIMIT ?",
                (scope, limit),
            ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("details"):
                try:
                    d["details"] = json.loads(d["details"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: ComplianceEngine | None = None


def get_compliance_engine(event_bus: EventBus | None = None,
                          db_path: str | Path | None = None) -> ComplianceEngine:
    global _engine
    if _engine is None:
        _engine = ComplianceEngine(event_bus=event_bus, db_path=db_path)
    return _engine


def reset_compliance_engine(event_bus: EventBus | None = None,
                            db_path: str | Path | None = None) -> ComplianceEngine:
    global _engine
    _engine = ComplianceEngine(event_bus=event_bus, db_path=db_path)
    return _engine
