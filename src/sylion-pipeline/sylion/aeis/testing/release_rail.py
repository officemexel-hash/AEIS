"""W14 Release Rail — checklist evaluator + state machine for releases.

Per docs/CLAUDE_AEIS_W14_TESTING.md sec 17.

Release lifecycle (10 statuses):
  NOT_TESTED -> TESTING_IN_PROGRESS ->
    BLOCKED_BY_FINDINGS / BLOCKED_BY_GOVERNANCE
  -> READY_FOR_RELEASE_CANDIDATE -> RELEASE_CANDIDATE
  -> READY_FOR_PRODUCTION -> PRODUCTION_RELEASED
  -> ROLLBACK_REQUIRED -> ARCHIVED

Two checklist tiers:
  RC_CHECKLIST    : 12 items required for RELEASE_CANDIDATE
  PROD_CHECKLIST  : 6 additional items for READY_FOR_PRODUCTION
"""
from __future__ import annotations

import logging
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.aeis.testing.ontology.enums import ReleaseStatus, RStatus, Severity
from sylion.aeis.testing.ontology.objects import (
    Finding, ReleaseCandidate, ReleaseDecision, ReleaseReadinessReport,
    TestCharter, TestRun, TestSuite,
)
from sylion.aeis.testing.ontology.store import OntologyStore

log = logging.getLogger("sylion.aeis.testing.release_rail")


# 12 RC items (sec 17.2). ``CHECKLIST`` is the canonical C6 alias —
# kept alongside the legacy ``RC_CHECKLIST`` name for backward compat.
RC_CHECKLIST: tuple[str, ...] = (
    "sot_approved",
    "masterplan_approved",
    "test_charter_approved",
    "all_mandatory_tests_passed",
    "every_pass_has_evidence",
    "no_p0_p1_findings",
    "d3_findings_decided",
    "regression_passed",
    "human_like_passed",
    "audit_chain_intact",
    "no_mock_as_live",
    "artifact_hashes_present",
)
CHECKLIST: tuple[str, ...] = RC_CHECKLIST

# 6 additional production items (sec 17.3)
PROD_CHECKLIST: tuple[str, ...] = (
    "release_rehearsal_passed",
    "rollback_tested_within_7d",
    "final_approval_signed",
    "council_completed_d4_d5",
    "sentinels_pass",
    "operator_signed_final_gate",
)


@dataclass
class EvaluationContext:
    """Caller-provided hints. ReleaseRail also queries the OntologyStore."""
    project_id: str = ""
    rc_id: str | None = None
    charter_id: str | None = None
    sot_approved: bool = False
    masterplan_approved: bool = False
    audit_chain_intact: bool = True  # default true; auditor sets false if broken
    artifact_hashes_present: bool = True
    human_like_passed: bool = True  # E5/E8 will set this realistically
    regression_passed: bool = True
    every_pass_has_evidence: bool = True
    no_mock_as_live: bool = True
    # Promoted out of extras (was caller-trust-only); E7 will replace this
    # default with a real ontology query against TestRun/TestSuite.
    all_mandatory_tests_passed: bool = False

    # Production-only
    release_rehearsal_passed: bool = False
    rollback_tested_within_7d: bool = False
    final_approval_signed: bool = False
    council_completed_d4_d5: bool = False
    sentinels_pass: bool = False
    operator_signed_final_gate: bool = False

    extras: dict = field(default_factory=dict)


class ReleaseRail:
    """Evaluates release readiness; produces ReleaseReadinessReport."""

    # C6 contract surface: callers can read the canonical 12-item checklist
    # off the class without importing module constants.
    CHECKLIST: tuple[str, ...] = CHECKLIST

    def __init__(self, ontology: OntologyStore, event_bus: Any | None = None) -> None:
        self._ontology = ontology
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # C6-compatible entrypoint (project_id-keyed)
    # ------------------------------------------------------------------

    def evaluate_for_project(
        self,
        project_id: str,
        rc_id: str | None = None,
        charter_id: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict:
        """C6 contract entrypoint: evaluate readiness for a single project.

        Returns ``{"status": "release_candidate"|"production_ready"|"blocked",
        "checklist_results": {...}, "blockers": [...]}`` exactly as required
        by ``W14_INTEGRATION_CONTRACTS.md`` C6.

        ``project_id`` is normalized + validated against the ``proj_`` prefix
        invariant from E1, so injection / path-traversal / cross-project
        leakage attempts are rejected before the ontology is consulted.
        """
        pid = self._normalize_project_id(project_id)
        if not pid:
            return {
                "status": "blocked",
                "checklist_results": {},
                "blockers": ["invalid_project_id"],
            }
        ctx = self._context_from_project(
            pid, rc_id=rc_id, charter_id=charter_id, overrides=overrides,
        )
        verdict = self.evaluate(ctx)
        # Project-scoped finding evaluation closes the cross-project leak
        # that the legacy ``evaluate(ctx)`` path was vulnerable to.
        scoped_results = dict(verdict["checklist_results"])
        scoped_results["no_p0_p1_findings"] = self._no_p0_p1_findings_for_project(pid)
        scoped_results["d3_findings_decided"] = self._d3_findings_decided_for_project(pid)
        # Caller-supplied overrides for items that don't have an ontology
        # source yet (test_charter_approved when no charter is present in
        # the store, the seven canonical bool flags). Project-scoped
        # finding checks above are NOT overridable — those always come
        # from the ontology so a malicious caller cannot mark a release
        # green while P0 findings are open in their project.
        ov = overrides or {}
        protected = {"no_p0_p1_findings", "d3_findings_decided", "no_mock_as_live"}
        for item in (*self.CHECKLIST, *PROD_CHECKLIST):
            if item in protected:
                continue
            if item in ov:
                scoped_results[item] = bool(ov[item])
        rc_blockers = [k for k in self.CHECKLIST if not scoped_results.get(k)]
        prod_blockers = [
            k for k in PROD_CHECKLIST if not scoped_results.get(k, False)
        ]
        if rc_blockers:
            status = "blocked"
        elif prod_blockers:
            status = "release_candidate"
        else:
            status = "production_ready"
        return {
            "status": status,
            "checklist_results": scoped_results,
            "blockers": rc_blockers + prod_blockers,
        }

    @staticmethod
    def _normalize_project_id(value: Any) -> str:
        """Reject non-string / path-traversal / non-prefix project ids."""
        if not isinstance(value, str):
            return ""
        cleaned = value.strip()
        if not cleaned:
            return ""
        # Defensive: no separators / control chars / traversal sequences.
        forbidden = ("/", "\\", "..", "\x00", "\n", "\r")
        if any(token in cleaned for token in forbidden):
            return ""
        if not (cleaned.startswith("proj_") or cleaned.startswith("project_")):
            return ""
        return cleaned

    def _context_from_project(
        self,
        project_id: str,
        rc_id: str | None,
        charter_id: str | None,
        overrides: dict[str, Any] | None,
    ) -> EvaluationContext:
        """Hydrate an EvaluationContext from Project Mode + caller overrides."""
        project_defaults = self._ontology_context_defaults(project_id)
        project_defaults.update(self._project_mode_context_defaults(project_id))
        project_defaults.update(self._production_context_defaults(project_id))
        ov = overrides or {}
        protected_context_keys = {"no_mock_as_live"}
        safe_overrides = {
            key: value for key, value in ov.items()
            if key not in protected_context_keys
        }
        values = {**project_defaults, **safe_overrides}
        ctx = EvaluationContext(
            project_id=project_id,
            rc_id=rc_id,
            charter_id=charter_id,
            sot_approved=bool(values.get("sot_approved", False)),
            masterplan_approved=bool(values.get("masterplan_approved", False)),
            audit_chain_intact=bool(values.get("audit_chain_intact", True)),
            artifact_hashes_present=bool(values.get("artifact_hashes_present", True)),
            human_like_passed=bool(values.get("human_like_passed", True)),
            regression_passed=bool(values.get("regression_passed", True)),
            every_pass_has_evidence=bool(values.get("every_pass_has_evidence", True)),
            no_mock_as_live=bool(values.get("no_mock_as_live", True)),
            all_mandatory_tests_passed=bool(values.get("all_mandatory_tests_passed", False)),
            release_rehearsal_passed=bool(values.get("release_rehearsal_passed", False)),
            rollback_tested_within_7d=bool(values.get("rollback_tested_within_7d", False)),
            final_approval_signed=bool(values.get("final_approval_signed", False)),
            council_completed_d4_d5=bool(values.get("council_completed_d4_d5", False)),
            sentinels_pass=bool(values.get("sentinels_pass", False)),
            operator_signed_final_gate=bool(values.get("operator_signed_final_gate", False)),
        )
        # extras allowed but stripped of any keys that overlap canonical
        # checklist names so callers cannot smuggle "no_p0_p1_findings=True".
        canonical = set(CHECKLIST) | set(PROD_CHECKLIST)
        ctx.extras = {
            k: v for k, v in (ov.get("extras") or {}).items()
            if k not in canonical
        }
        return ctx

    def _project_mode_context_defaults(self, project_id: str) -> dict[str, bool]:
        """Derive release-gate facts from the Project Mode record.

        The test-center route evaluates real AEIS projects whose IDs use the
        ``project_`` prefix. Without this hydration the gate treats a completed
        Project Mode build as an empty ontology-only candidate and reports false
        SoT/Masterplan blockers. Only persisted evidence is promoted here; final
        production approvals still require their own HumanGate/Council records.
        """
        try:
            from sylion.api.projects_routes import _load_project_or_404

            project = _load_project_or_404(project_id)
        except Exception:  # noqa: BLE001
            log.warning(
                "release gate could not load project record for %s",
                project_id,
                exc_info=True,
            )
            return {}
        if not isinstance(project, dict):
            return {}

        launch = project.get("launch") or {}
        validation = launch.get("validation") or {}
        audit = launch.get("audit") or {}
        events = project.get("events") or project.get("audit_chain") or []
        approvals = project.get("approvals") or {}

        event_names = self._project_event_names(events)
        validation_success = self._project_validation_success(validation) or (
            "quality_gates_passed" in event_names
            and "customer_signoff_received" in event_names
        )
        audit_success = self._project_audit_success(audit) or (
            "audit_truth_map_generated" in event_names
            and "build_complete" in event_names
            and "project_closed" in event_names
        )
        has_audit_chain = self._project_audit_chain_present(events)
        artifact_hash = str(launch.get("artifact_sha256") or "")
        artifact_path = str(launch.get("artifact_path") or "")
        if not artifact_hash and artifact_path:
            artifact_hash = self._file_sha256(artifact_path)

        values = {
            "sot_approved": bool(
                (
                    project.get("canon_frozen_at")
                    and project.get("canon_hash")
                    and project.get("canonical_book")
                )
                or (
                    approvals.get("book")
                    and {"council_book_signed", "ksiega_finalized"}.issubset(event_names)
                )
            ),
            "masterplan_approved": bool(
                (
                    project.get("masterplan_frozen_at")
                    and project.get("masterplan_hash")
                    and project.get("masterplan")
                )
                or (
                    approvals.get("operating_model")
                    and {"masterplan_finalized", "test_plan_finalized"}.issubset(event_names)
                )
            ),
            "all_mandatory_tests_passed": validation_success and audit_success,
            "regression_passed": validation_success,
            "audit_chain_intact": has_audit_chain,
            "artifact_hashes_present": bool(
                artifact_hash and artifact_path
            ),
            "every_pass_has_evidence": bool(
                validation_success and audit_success and artifact_hash
            ),
            "human_like_passed": bool(validation_success),
            "no_mock_as_live": bool(validation_success and audit_success),
        }
        return values

    def _ontology_context_defaults(self, project_id: str) -> dict[str, bool]:
        """Derive release-gate facts from W14 ontology records."""
        charters = [
            c for c in self._ontology.list(TestCharter, limit=2000)
            if c.project_id == project_id and c.status == "approved"
        ]
        if not charters:
            return {}
        charter = sorted(
            charters, key=lambda c: getattr(c, "approved_at", 0.0) or getattr(c, "created_at", 0.0),
            reverse=True,
        )[0]
        return {
            "sot_approved": bool(getattr(charter, "source_of_truth_version", "")),
            "masterplan_approved": bool(getattr(charter, "masterplan_version", "")),
            "all_mandatory_tests_passed": self._mandatory_tests_passed_for_project(project_id, charter),
        }

    @staticmethod
    def _project_event_names(events: Any) -> set[str]:
        if not isinstance(events, list):
            return set()
        return {
            str(event.get("event_type") or event.get("event") or "")
            for event in events
            if isinstance(event, dict)
        }

    @staticmethod
    def _file_sha256(path: str) -> str:
        try:
            p = Path(path)
            if not p.is_file():
                return ""
            return hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:  # noqa: BLE001
            return ""

    def _production_context_defaults(self, project_id: str) -> dict[str, bool]:
        """Derive production-gate facts from W14 release ontology evidence."""
        latest_rc = self._latest_release_candidate(project_id)
        if latest_rc is None:
            return {}

        runs = self._project_test_runs(project_id)
        release_rehearsal_passed = self._has_passed_rehearsal(runs)
        rollback_tested = self._has_recent_rollback_test(runs)
        governance = latest_rc.test_run_summary.get("production_governance", {})
        sentinels = governance.get("sentinels", {}) if isinstance(governance, dict) else {}
        council_completed = bool(
            isinstance(governance, dict)
            and governance.get("council_session_id")
            and governance.get("d_level") in ("D4", "D5")
            and governance.get("critic_signature")
        )
        sentinels_pass = bool(
            isinstance(sentinels, dict)
            and sentinels.get("cost") == "pass"
            and sentinels.get("security") == "pass"
        )
        approved_decision = self._approved_release_decision(latest_rc.rc_id)
        signatures = approved_decision.signatures if approved_decision else []
        signature_roles = {
            str(sig.get("role", ""))
            for sig in signatures
            if isinstance(sig, dict)
        }
        return {
            "release_rehearsal_passed": release_rehearsal_passed,
            "rollback_tested_within_7d": rollback_tested,
            "final_approval_signed": bool(
                approved_decision
                and {"operator_1", "operator_2", "dpo"}.issubset(signature_roles)
            ),
            "council_completed_d4_d5": council_completed,
            "sentinels_pass": sentinels_pass,
            "operator_signed_final_gate": bool(
                approved_decision and "operator_final_gate" in signature_roles
            ),
        }

    def _latest_release_candidate(self, project_id: str) -> ReleaseCandidate | None:
        candidates = [
            rc for rc in self._ontology.list(ReleaseCandidate, limit=2000)
            if rc.project_id == project_id
        ]
        if not candidates:
            return None
        return sorted(
            candidates, key=lambda rc: getattr(rc, "promoted_at", 0.0),
            reverse=True,
        )[0]

    def _approved_release_decision(self, rc_id: str) -> ReleaseDecision | None:
        decisions = [
            decision for decision in self._ontology.list(ReleaseDecision, limit=2000)
            if decision.rc_id == rc_id and decision.outcome == "approved"
        ]
        if not decisions:
            return None
        return sorted(
            decisions, key=lambda decision: getattr(decision, "created_at", 0.0),
            reverse=True,
        )[0]

    def _project_test_runs(self, project_id: str) -> list[tuple[TestRun, str | None]]:
        charter_ids = {
            c.charter_id for c in self._ontology.list(TestCharter, limit=2000)
            if c.project_id == project_id
        }
        if not charter_ids:
            return []
        suite_by_id = {
            s.suite_id: s for s in self._ontology.list(TestSuite, limit=2000)
        }
        rows: list[tuple[TestRun, str | None]] = []
        for run in self._ontology.list(TestRun, limit=4000):
            if run.charter_id not in charter_ids:
                continue
            suite = suite_by_id.get(run.suite_id or "")
            rows.append((run, getattr(suite, "test_class", None)))
        return rows

    @staticmethod
    def _has_passed_rehearsal(runs: list[tuple[TestRun, str | None]]) -> bool:
        for run, test_class in runs:
            if run.status != "passed":
                continue
            payload = run.result_payload or {}
            if (
                test_class == "T15"
                or payload.get("release_gate_item") == "release_rehearsal_passed"
            ):
                return True
        return False

    @staticmethod
    def _has_recent_rollback_test(runs: list[tuple[TestRun, str | None]]) -> bool:
        threshold = time.time() - 7 * 24 * 60 * 60
        for run, _test_class in runs:
            if run.status != "passed":
                continue
            payload = run.result_payload or {}
            completed_at = run.completed_at or run.started_at
            if (
                payload.get("release_gate_item") == "rollback_tested_within_7d"
                and completed_at >= threshold
            ):
                return True
        return False

    @staticmethod
    def _project_validation_success(validation: Any) -> bool:
        if not isinstance(validation, dict) or not validation.get("success"):
            return False
        stages = validation.get("stages") or {}
        if not isinstance(stages, dict) or not stages:
            return False
        return all(
            isinstance(stage, dict) and bool(stage.get("success"))
            for stage in stages.values()
        )

    @staticmethod
    def _project_audit_success(audit: Any) -> bool:
        if not isinstance(audit, dict):
            return False
        results = audit.get("results") or []
        if not isinstance(results, list) or not results:
            return False
        return all(
            isinstance(result, dict) and result.get("status") == "pass"
            for result in results
        )

    @staticmethod
    def _project_audit_chain_present(events: Any) -> bool:
        if not isinstance(events, list):
            return False
        event_types = ReleaseRail._project_event_names(events)
        project_mode_required = {
            "project.created",
            "project.canon.frozen",
            "project.masterplan.frozen",
            "project.build.completed",
            "project.validation.completed",
            "project.audit.completed",
            "project.execution.completed",
        }
        project_start_required = {
            "project_inception",
            "ksiega_finalized",
            "masterplan_finalized",
            "test_plan_finalized",
            "build_complete",
            "quality_gates_passed",
            "project_closed",
        }
        return (
            project_mode_required.issubset(event_types)
            or project_start_required.issubset(event_types)
        )

    def _no_p0_p1_findings_for_project(self, project_id: str) -> bool:
        """Project-scoped variant of _no_p0_p1_findings.

        Iterates over ``Finding`` rows but only counts those whose
        ``ticket_id`` carries the project's ``proj_`` prefix or whose
        related TestCharter belongs to the project. Findings from other
        projects can no longer block this release (Kimi attack #1).
        """
        findings = self._ontology.list(Finding, limit=1000)
        for f in findings:
            if not self._finding_in_project(f, project_id):
                continue
            if f.severity in (Severity.P0.value, Severity.P1.value):
                if f.r_status not in (
                    RStatus.VERIFIED.value,
                    RStatus.WAIVED_BY_HUMAN.value,
                    RStatus.CLOSED.value,
                ):
                    return False
        return True

    def _d3_findings_decided_for_project(self, project_id: str) -> bool:
        findings = self._ontology.list(Finding, limit=1000)
        for f in findings:
            if not self._finding_in_project(f, project_id):
                continue
            if f.d_level in ("D3", "D4", "D5"):
                if f.r_status not in (
                    RStatus.VERIFIED.value,
                    RStatus.WAIVED_BY_HUMAN.value,
                    RStatus.CLOSED.value,
                ):
                    return False
        return True

    @staticmethod
    def _finding_in_project(finding: Finding, project_id: str) -> bool:
        """Best-effort link: finding.ticket_id often carries the project tag."""
        ticket = getattr(finding, "ticket_id", "") or ""
        if isinstance(ticket, str) and project_id in ticket:
            return True
        # Also accept when the finding description embeds the project_id
        # marker — not bulletproof, but better than the previous
        # cross-project leak which counted EVERY finding.
        desc = getattr(finding, "description", "") or ""
        return isinstance(desc, str) and project_id in desc

    # ------------------------------------------------------------------
    # Legacy entrypoint (kept for backward compatibility with E5/E7)
    # ------------------------------------------------------------------

    def evaluate(self, ctx: EvaluationContext) -> dict:
        """Evaluate all 12+6 checklist items.

        Returns dict:
          {
            "status": ReleaseStatus.value,
            "checklist_results": {item_name: bool},
            "blockers": [item_name, ...],
            "warnings": [...],
            "rc_pass": bool, "prod_pass": bool,
          }
        """
        rc_results = self._evaluate_rc(ctx)
        prod_results = self._evaluate_prod(ctx)

        rc_blockers = [k for k, v in rc_results.items() if not v]
        prod_blockers = [k for k, v in prod_results.items() if not v]

        rc_pass = not rc_blockers
        prod_pass = rc_pass and not prod_blockers

        # Determine status
        if prod_pass:
            status = ReleaseStatus.READY_FOR_PRODUCTION.value
        elif rc_pass:
            status = ReleaseStatus.READY_FOR_RELEASE_CANDIDATE.value
        elif rc_blockers and self._has_governance_blocker(rc_results):
            status = ReleaseStatus.BLOCKED_BY_GOVERNANCE.value
        elif rc_blockers:
            status = ReleaseStatus.BLOCKED_BY_FINDINGS.value
        else:
            status = ReleaseStatus.TESTING_IN_PROGRESS.value

        return {
            "status": status,
            "checklist_results": {**rc_results, **prod_results},
            "blockers": rc_blockers + prod_blockers,
            "warnings": [],
            "rc_pass": rc_pass,
            "prod_pass": prod_pass,
        }

    def generate_report(self, ctx: EvaluationContext) -> ReleaseReadinessReport:
        """Run evaluate() + persist ReleaseReadinessReport object."""
        verdict = self.evaluate(ctx)
        report = ReleaseReadinessReport(
            rc_id=ctx.rc_id or "",
            checklist_results=verdict["checklist_results"],
            blockers=verdict["blockers"],
            warnings=verdict["warnings"],
            recommendations=self._recommend(verdict),
            cost_summary={"total_cost_usd": 0.0},  # E10 wires real cost data
            latency_summary={"p95_ms": 0},
            evidence_tier_used="H1",
            human_comprehension_score=0.85 if ctx.human_like_passed else 0.4,
        )
        self._ontology.create(report)
        self._emit("aeis.testing.release.report_generated", {
            "report_id": report.report_id,
            "rc_id": ctx.rc_id,
            "status": verdict["status"],
            "blockers": verdict["blockers"],
        })
        return report

    # ------------------------------------------------------------------
    # Checklist evaluators
    # ------------------------------------------------------------------

    def _evaluate_rc(self, ctx: EvaluationContext) -> dict[str, bool]:
        return {
            "sot_approved": ctx.sot_approved,
            "masterplan_approved": ctx.masterplan_approved,
            "test_charter_approved": self._charter_approved(ctx),
            "all_mandatory_tests_passed": self._mandatory_tests_passed(ctx),
            "every_pass_has_evidence": ctx.every_pass_has_evidence,
            "no_p0_p1_findings": self._no_p0_p1_findings(ctx),
            "d3_findings_decided": self._d3_findings_decided(ctx),
            "regression_passed": ctx.regression_passed,
            "human_like_passed": ctx.human_like_passed,
            "audit_chain_intact": ctx.audit_chain_intact,
            "no_mock_as_live": bool(
                ctx.no_mock_as_live and self._no_mock_scan_passes()
            ),
            "artifact_hashes_present": ctx.artifact_hashes_present,
        }

    def _evaluate_prod(self, ctx: EvaluationContext) -> dict[str, bool]:
        return {
            "release_rehearsal_passed": ctx.release_rehearsal_passed,
            "rollback_tested_within_7d": ctx.rollback_tested_within_7d,
            "final_approval_signed": ctx.final_approval_signed,
            "council_completed_d4_d5": ctx.council_completed_d4_d5,
            "sentinels_pass": ctx.sentinels_pass,
            "operator_signed_final_gate": ctx.operator_signed_final_gate,
        }

    # ------------------------------------------------------------------
    # Per-item checks (consult ontology)
    # ------------------------------------------------------------------

    def _charter_approved(self, ctx: EvaluationContext) -> bool:
        if not ctx.charter_id:
            return any(
                c.status == "approved"
                for c in self._ontology.list(TestCharter, limit=2000)
                if c.project_id == ctx.project_id
            )
        charter = self._ontology.get(TestCharter, ctx.charter_id)
        return charter is not None and charter.status == "approved"

    def _no_p0_p1_findings(self, ctx: EvaluationContext) -> bool:
        """No open (non-closed) P0/P1 findings for this project's RC."""
        findings = self._ontology.list(Finding, limit=1000)
        for f in findings:
            if f.severity in (Severity.P0.value, Severity.P1.value):
                if f.r_status not in (
                    RStatus.VERIFIED.value,
                    RStatus.WAIVED_BY_HUMAN.value,
                    RStatus.CLOSED.value,
                ):
                    return False
        return True

    def _d3_findings_decided(self, ctx: EvaluationContext) -> bool:
        """All D3+ findings have closed/waived/verified state."""
        findings = self._ontology.list(Finding, limit=1000)
        for f in findings:
            if f.d_level in ("D3", "D4", "D5"):
                if f.r_status not in (
                    RStatus.VERIFIED.value,
                    RStatus.WAIVED_BY_HUMAN.value,
                    RStatus.CLOSED.value,
                ):
                    return False
        return True

    def _mandatory_tests_passed(self, ctx: EvaluationContext) -> bool:
        """All mandatory tests (T0-T11 for D3+) passed.

        E6 stub: assumes caller has verified via TestRun records.
        Real ontology query lands in E7 with full Finding/TestRun lifecycle.
        Reads ``ctx.all_mandatory_tests_passed`` (canonical field) and
        falls back to ``ctx.extras`` for backward compat.
        """
        if ctx.all_mandatory_tests_passed:
            return True
        charters = [
            c for c in self._ontology.list(TestCharter, limit=2000)
            if c.project_id == ctx.project_id and c.status == "approved"
        ]
        if charters:
            charter = sorted(
                charters, key=lambda c: getattr(c, "approved_at", 0.0) or getattr(c, "created_at", 0.0),
                reverse=True,
            )[0]
            if self._mandatory_tests_passed_for_project(ctx.project_id, charter):
                return True
        return bool(ctx.extras.get("all_mandatory_tests_passed", False))

    def _mandatory_tests_passed_for_project(self, project_id: str, charter: TestCharter) -> bool:
        required = set(getattr(charter, "required_test_classes", []) or [])
        if not required:
            return False
        passed: set[str] = set()
        for run, test_class in self._project_test_runs(project_id):
            if run.status == "passed" and test_class in required:
                passed.add(str(test_class))
        return required.issubset(passed)

    @staticmethod
    def _no_mock_scan_passes() -> bool:
        """Fail closed if production UI/API contains live mock/demo/stub fallbacks."""
        try:
            from sylion.aeis.testing.no_mock_scan import run_no_mock_scan

            result = run_no_mock_scan(limit=2000)
        except Exception:  # noqa: BLE001
            log.warning("release gate no-mock scan failed", exc_info=True)
            return False
        return result.status == "PASS" and result.blocking_count == 0

    def _has_governance_blocker(self, rc_results: dict[str, bool]) -> bool:
        gov_items = (
            "sot_approved", "masterplan_approved",
            "test_charter_approved", "audit_chain_intact",
            "d3_findings_decided",
        )
        return any(not rc_results.get(k, True) for k in gov_items)

    @staticmethod
    def _recommend(verdict: dict) -> list[str]:
        recs: list[str] = []
        for blocker in verdict["blockers"]:
            recs.append(f"resolve_{blocker}")
        if not verdict["rc_pass"]:
            recs.append("focus_on_rc_checklist_first")
        if verdict["rc_pass"] and not verdict["prod_pass"]:
            recs.append("rc_ready_proceed_to_production_checklist")
        return recs

    def _emit(self, topic: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        try:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="aeis.testing.release_rail",
            ))
        except Exception as e:  # pragma: no cover
            log.debug("event emit failed: %s", e)


__all__ = [
    "ReleaseRail",
    "EvaluationContext",
    "RC_CHECKLIST",
    "PROD_CHECKLIST",
]
