"""W14 charter actions (4): propose / approve / create_eval / run_eval."""
from __future__ import annotations

import time

from sylion.aeis.testing.actions.base import TestingActionHandler
from sylion.aeis.testing.ontology.enums import (
    DLevel, GateType, TestClass,
)
from sylion.aeis.testing.ontology.objects import (
    EvaluationSuite, TestCharter, TestRun,
)


class ProposeTestCharterHandler(TestingActionHandler):
    target_action: str = "propose_test_charter"
    d_level: DLevel = DLevel.D2
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.NON_BLOCKING

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload,
            "project_id", "source_of_truth_version", "masterplan_version",
            "scope", "required_test_classes",
        )
        project_id = payload.get("project_id")
        if not (
            isinstance(project_id, str)
            and (project_id.startswith("proj_") or project_id.startswith("project_"))
        ):
            raise ValueError(
                "propose_test_charter: project_id must start with "
                "'proj_' or 'project_'"
            )
        rtc = payload["required_test_classes"]
        if not isinstance(rtc, list) or len(rtc) == 0:
            raise ValueError("propose_test_charter: required_test_classes must be non-empty list")
        valid = set(TestClass.values())
        bad = [c for c in rtc if c not in valid]
        if bad:
            raise ValueError(f"propose_test_charter: invalid test classes: {bad}")

    def execute(self, payload: dict, intent_id: str) -> dict:
        charter = TestCharter(
            project_id=payload["project_id"],
            source_of_truth_version=payload["source_of_truth_version"],
            masterplan_version=payload["masterplan_version"],
            scope=payload["scope"],
            required_test_classes=list(payload["required_test_classes"]),
            required_personas=list(payload.get("required_personas", ["operator_beginner"])),
            required_evidence=list(payload.get("required_evidence", [])),
            release_blockers=list(payload.get("release_blockers", [])),
            auto_repair_policy=payload.get("auto_repair_policy", {}),
            approval={"d_level": "D3", "human_gate_required": True},
            status="proposed",
        )
        if self.ontology is not None:
            self.ontology.create(charter)
        ticket_id = self._mirror_ticket(
            project_id=payload["project_id"],
            title=f"Propose test charter for {payload['project_id']}",
            summary=f"Charter scope: {len(payload['required_test_classes'])} test classes",
            payload={"charter_id": charter.charter_id, "intent_id": intent_id},
            requested_by=payload.get("requested_by", "system"),
        )
        self._emit("aeis.testing.charter.proposed", {
            "charter_id": charter.charter_id,
            "project_id": payload["project_id"],
        }, trace_id=intent_id)
        return {
            "charter_id": charter.charter_id,
            "ticket_id": ticket_id,
            "status": "proposed",
        }


class ApproveTestCharterHandler(TestingActionHandler):
    target_action: str = "approve_test_charter"
    d_level: DLevel = DLevel.D3
    phase: str = "TWO_PHASE"
    mirror_to_ticket: bool = True
    gate_type: GateType = GateType.PRODUCTION

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "charter_id", "hg_ticket_id", "approver", "rationale")
        self._require_prefix(payload, "charter_id", "tc_")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("approve_test_charter: ontology not configured")
        charter = self.ontology.get(TestCharter, payload["charter_id"])
        if charter is None:
            raise ValueError(f"charter not found: {payload['charter_id']}")
        # Charter must already be in 'proposed' before D3 approval (audit trail).
        if charter.status != "proposed":
            raise ValueError(
                f"approve_test_charter: charter status must be 'proposed', "
                f"got: {charter.status}"
            )
        charter.status = "approved"
        charter.approved_at = time.time()
        charter.hg_ticket_id = payload["hg_ticket_id"]
        if payload.get("council_session_id"):
            charter.council_session_id = payload["council_session_id"]
        self.ontology.update(charter)
        ticket_id = self._mirror_ticket(
            project_id=charter.project_id,
            title=f"Approve test charter {charter.charter_id}",
            summary=payload["rationale"][:200],
            payload={
                "charter_id": charter.charter_id,
                "hg_ticket_id": payload["hg_ticket_id"],
                "council_session_id": payload.get("council_session_id"),
                "intent_id": intent_id,
            },
            requested_by=payload["approver"],
        )
        self._emit("aeis.testing.charter.approved", {
            "charter_id": charter.charter_id,
            "approver": payload["approver"],
            "trace_id": intent_id,
        })
        return {
            "charter_id": charter.charter_id,
            "status": "approved",
            "approved_at": charter.approved_at,
            "ticket_id": ticket_id,
        }


class CreateEvalSuiteHandler(TestingActionHandler):
    target_action: str = "create_eval_suite"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False
    gate_type: GateType | None = None

    def validate(self, payload: dict) -> None:
        self._require_keys(
            payload, "target_function", "target_module",
            "test_case_ids", "evaluators", "metrics",
        )
        for k in ("test_case_ids", "evaluators", "metrics"):
            v = payload[k]
            if not isinstance(v, list) or len(v) == 0:
                raise ValueError(f"create_eval_suite: {k} must be non-empty list")

    def execute(self, payload: dict, intent_id: str) -> dict:
        suite = EvaluationSuite(
            target_function=payload["target_function"],
            target_module=payload["target_module"],
            test_case_ids=list(payload["test_case_ids"]),
            evaluators=list(payload["evaluators"]),
            metrics=list(payload["metrics"]),
            baseline_run_id=payload.get("baseline_run_id"),
        )
        if self.ontology is not None:
            self.ontology.create(suite)
        self._emit("aeis.testing.eval_suite.created", {
            "suite_id": suite.suite_id,
            "target_function": suite.target_function,
        }, trace_id=intent_id)
        return {"suite_id": suite.suite_id, "status": "created"}


class RunEvalSuiteHandler(TestingActionHandler):
    target_action: str = "run_eval_suite"
    d_level: DLevel = DLevel.D1
    phase: str = "IMMEDIATE"
    mirror_to_ticket: bool = False
    gate_type: GateType | None = None

    def validate(self, payload: dict) -> None:
        self._require_keys(payload, "suite_id", "branch_id")
        self._require_prefix(payload, "suite_id", "es_")
        self._require_not_main(payload, "branch_id")

    def execute(self, payload: dict, intent_id: str) -> dict:
        if self.ontology is None:
            raise RuntimeError("run_eval_suite: ontology not configured")
        suite = self.ontology.get(EvaluationSuite, payload["suite_id"])
        if suite is None:
            raise ValueError(f"suite not found: {payload['suite_id']}")

        branch_id = payload.get("branch_id")
        if not branch_id:
            raise ValueError(
                "run_eval_suite: branch_id is required (no implicit 'main' default)"
            )
        if branch_id == "main":
            raise ValueError(
                "run_eval_suite: branch_id MUST NOT be 'main' "
                "(W14 prohibits running tests against main directly)"
            )
        runs_started: list[str] = []

        # E2 stub: create TestRun records, status="running" (real exec in E3 SimulationEngine)
        for case_id in suite.test_case_ids:
            run = TestRun(
                suite_id=suite.suite_id,
                case_id=case_id,
                branch_id=branch_id,
                charter_id=payload.get("charter_id"),
                status="running",
                trace_id=intent_id,
            )
            self.ontology.create(run)
            runs_started.append(run.run_id)
            self._emit("aeis.testing.run.started", {
                "run_id": run.run_id,
                "case_id": case_id,
                "branch_id": branch_id,
            }, trace_id=intent_id)

        self._emit("aeis.testing.eval_suite.run", {
            "suite_id": suite.suite_id,
            "runs_started": len(runs_started),
        }, trace_id=intent_id)
        return {
            "suite_id": suite.suite_id,
            "runs_started": runs_started,
            "total": len(runs_started),
            "note": "E2 stub: TestRun records created with status=running. "
                    "Real execution requires E3 SimulationEngine.",
        }


CHARTER_HANDLERS = (
    ProposeTestCharterHandler,
    ApproveTestCharterHandler,
    CreateEvalSuiteHandler,
    RunEvalSuiteHandler,
)
