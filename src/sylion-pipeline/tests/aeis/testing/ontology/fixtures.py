"""Minimal-valid fixture builders for the 25 W14 ontology objects.

Each ``make_<X>`` returns a freshly-constructed dataclass instance with the
smallest payload that satisfies its ``__post_init__`` validators. Tests then
mutate the result to exercise specific fields without restating every
required argument.
"""
from __future__ import annotations

import hashlib
from typing import Any

from sylion.aeis.testing.ontology.enums import (
    BranchState,
    BranchType,
    DLevel,
    EvidenceTier,
    GuardianClass,
    HumanErrorClass,
    PersonaCapability,
    ReleaseStatus,
    RStatus,
    Severity,
    TestClass,
)
from sylion.aeis.testing.ontology.objects import (
    Branch,
    EvaluationSuite,
    Finding,
    GuardianAlert,
    HumanDecisionTrace,
    HumanErrorInjection,
    HumanNearMiss,
    HumanPersona,
    HumanScenario,
    LoopReport,
    PatchProposal,
    RegressionRun,
    ReleaseCandidate,
    ReleaseDecision,
    ReleaseReadinessReport,
    RepairAttempt,
    Requirement,
    SimulationBranch,
    SimulationContract,
    SimulationEvidence,
    TestCase,
    TestCharter,
    TestPlan,
    TestRun,
    TestSuite,
)


_DUMMY_HASH = hashlib.sha256(b"snapshot").hexdigest()


def make_requirement(**overrides: Any) -> Requirement:
    base = dict(
        source="SoT",
        source_ref="sot://feature/login",
        criticality=DLevel.D2.value,
        description="users can log in via SSO",
    )
    base.update(overrides)
    return Requirement(**base)


def make_charter(**overrides: Any) -> TestCharter:
    base = dict(
        project_id="proj_abc123def456",
        source_of_truth_version="1.0.0",
        masterplan_version="1.0.0",
        scope={"surface": "login"},
        required_test_classes=[TestClass.UNIT.value, TestClass.SECURITY.value],
        required_personas=["operator_beginner"],
        required_evidence=["test_result"],
        release_blockers=["P0", "P1"],
        auto_repair_policy={"max_attempts": 2},
        approval={"d_level": DLevel.D3.value},
    )
    base.update(overrides)
    return TestCharter(**base)


def make_plan(**overrides: Any) -> TestPlan:
    base = dict(
        charter_id="tc_" + "a" * 12,
        suites=["ts_x"],
        execution_order=["ts_x"],
        estimated_duration_s=60,
    )
    base.update(overrides)
    return TestPlan(**base)


def make_suite(**overrides: Any) -> TestSuite:
    base = dict(
        name="commissioning_security_suite",
        test_class=TestClass.SECURITY.value,
        case_ids=["tc_x"],
    )
    base.update(overrides)
    return TestSuite(**base)


def make_case(**overrides: Any) -> TestCase:
    base = dict(
        requirement_id="req_" + "a" * 12,
        input_payload={"foo": "bar"},
        expected_output={"baz": 1},
        evaluator="exact_match",
    )
    base.update(overrides)
    return TestCase(**base)


def make_eval_suite(**overrides: Any) -> EvaluationSuite:
    base = dict(
        target_function="sylion.foo.bar",
        target_module="sylion.foo",
        test_case_ids=["tc_x"],
        evaluators=["exact_match"],
        metrics=["accuracy"],
    )
    base.update(overrides)
    return EvaluationSuite(**base)


def make_run(**overrides: Any) -> TestRun:
    base = dict(
        branch_id="br_" + "a" * 12,
        trace_id="trace_xyz",
    )
    base.update(overrides)
    return TestRun(**base)


def make_regression(**overrides: Any) -> RegressionRun:
    base = dict(
        finding_id="find_" + "a" * 12,
        pre_fix_run_id="tr_pre_xxx",
        post_fix_run_id="tr_post_xxx",
        neighbor_test_run_ids=["tr_n1"],
    )
    base.update(overrides)
    return RegressionRun(**base)


def make_finding(**overrides: Any) -> Finding:
    base = dict(
        title="login fails on weak password",
        description="System accepts password of length 3.",
        discovered_by="evaluator",
    )
    base.update(overrides)
    return Finding(**base)


def make_patch(**overrides: Any) -> PatchProposal:
    base = dict(
        finding_id="find_" + "a" * 12,
        branch_id="br_repair_xxxxxxxxxx",
        diff_text="--- a\n+++ b\n@@ +1 @@\n+line",
        files_touched=["src/foo.py"],
        diff_lines_added=1,
        diff_lines_removed=0,
        risk_assessment={"score": 0.1},
        tests_to_run=["pytest tests/foo.py"],
        proposed_by="auto_repair",
    )
    base.update(overrides)
    return PatchProposal(**base)


def make_attempt(**overrides: Any) -> RepairAttempt:
    base = dict(
        finding_id="find_" + "a" * 12,
        n=1,
        r_phase=RStatus.REPAIRING.value,
        result="success",
    )
    base.update(overrides)
    return RepairAttempt(**base)


def make_loop_report(**overrides: Any) -> LoopReport:
    base = dict(
        finding_id="find_" + "a" * 12,
        loop_type="same_failure",
        attempts_n=3,
        similarity_score=0.92,
        suspected_root_cause=["spec_drift"],
        blocked_actions=["apply_patch"],
        required_decision={
            "type": "human_gate",
            "suggested_d_level": DLevel.D3.value,
            "question": "Approve waiver?",
        },
    )
    base.update(overrides)
    return LoopReport(**base)


def make_alert(**overrides: Any) -> GuardianAlert:
    base = dict(
        guardian=GuardianClass.SOT_GUARDIAN.value,
        severity=Severity.P2.value,
        evidence_link={"trace_id": "t-1"},
        reason="SoT version mismatch",
    )
    base.update(overrides)
    return GuardianAlert(**base)


def make_simulation_contract(**overrides: Any) -> SimulationContract:
    base = dict(
        simulation_id="sim_x",
        branch_id="br_x",
        source_project_id="proj_x",
        sot_version="1.0",
        masterplan_version="1.0",
        isolation={"main_mutation_allowed": False, "external_network_allowed": False},
        model_mode={"llm_mode": "local"},
        persistence={"persist_human_decision_trace": True},
        safety={"max_runtime_seconds": 600, "max_cost_usd": 1.0},
    )
    base.update(overrides)
    return SimulationContract(**base)


def make_simulation_branch(**overrides: Any) -> SimulationBranch:
    base = dict(
        contract_id="sc_" + "a" * 12,
    )
    base.update(overrides)
    return SimulationBranch(**base)


def make_simulation_evidence(**overrides: Any) -> SimulationEvidence:
    base = dict(
        simulation_id="sim_x",
        sim_branch_id="simb_" + "a" * 12,
        trace_id="trace_x",
        layer_executed=2,
        event_log=[{"step": "click"}],
        branch_snapshot_hash=_DUMMY_HASH,
        evaluator_outputs={"accuracy": 0.99},
    )
    base.update(overrides)
    return SimulationEvidence(**base)


def make_persona(**overrides: Any) -> HumanPersona:
    base = dict(
        name="operator_beginner",
        capability_level=PersonaCapability.BEGINNER.value,
        expertise_domains=["operations"],
        error_proneness=0.2,
        attention_span_min=20,
        trust_in_ai_baseline=0.5,
        risk_tolerance="low",
        dynamic_state={"fatigue": 0.0},
        behavior_modifiers={"reads_warnings": True},
    )
    base.update(overrides)
    return HumanPersona(**base)


def make_scenario(**overrides: Any) -> HumanScenario:
    base = dict(
        persona_id="persona_" + "a" * 12,
        domain="commissioning",
        workflow_steps=[{"action": "open_panel"}],
        decision_points=[{"label": "approve"}],
        success_criteria=["panel_visible"],
        comprehension_check={"questions": ["why?"]},
        difficulty="easy",
    )
    base.update(overrides)
    return HumanScenario(**base)


def make_error_injection(**overrides: Any) -> HumanErrorInjection:
    base = dict(
        error_class=HumanErrorClass.WRONG_CLICK.value,
        target_action="approve_release",
        timing="step3",
        expected_system_response=["block", "show_warning"],
        severity_if_system_allows_error=DLevel.D4.value,
        simulated_target_d_level=DLevel.D3.value,
        action_d_level=DLevel.D2.value,
    )
    base.update(overrides)
    return HumanErrorInjection(**base)


def make_decision_trace(**overrides: Any) -> HumanDecisionTrace:
    base = dict(
        persona_id="persona_" + "a" * 12,
        simulation_id="sim_x",
        decisions_made=[{"label": "approve", "ts": 1.0}],
        visible_state_snapshot={"panel": "open"},
        perception_model={"noticed_badges": ["live"], "missed_badges": [], "comprehension_score": 0.9},
        behavior_metrics={"latency_s": 12.0},
    )
    base.update(overrides)
    return HumanDecisionTrace(**base)


def make_near_miss(**overrides: Any) -> HumanNearMiss:
    base = dict(
        error_injection_id="hei_" + "a" * 12,
        blocked_successfully=True,
        operator_message_quality_score=0.8,
        future_risk="low",
    )
    base.update(overrides)
    return HumanNearMiss(**base)


def make_branch(**overrides: Any) -> Branch:
    base = dict(
        branch_type=BranchType.TEST.value,
        project_id="proj_x",
        sot_version="1.0",
        masterplan_version="1.0",
        state=BranchState.OPEN.value,
        created_by="claude",
    )
    base.update(overrides)
    return Branch(**base)


def make_release_candidate(**overrides: Any) -> ReleaseCandidate:
    base = dict(
        branch_id="br_" + "a" * 12,
        project_id="proj_x",
        test_run_summary={"passed": 12, "failed": 0},
        gate_status=ReleaseStatus.RELEASE_CANDIDATE.value,
    )
    base.update(overrides)
    return ReleaseCandidate(**base)


def make_release_decision(**overrides: Any) -> ReleaseDecision:
    base = dict(
        rc_id="rc_" + "a" * 12,
        hg_ticket_id="hg_x",
        outcome="approved",
        rollback_plan={"steps": ["revert"]},
        signatures=[{"role": "operator", "user": "claude"}],
    )
    base.update(overrides)
    return ReleaseDecision(**base)


def make_readiness_report(**overrides: Any) -> ReleaseReadinessReport:
    base = dict(
        rc_id="rc_" + "a" * 12,
        checklist_results={"sot_approved": True},
        cost_summary={"total_cost_usd": 0.5},
        latency_summary={"p99_ms": 200},
        evidence_tier_used=EvidenceTier.H2.value,
        human_comprehension_score=0.95,
    )
    base.update(overrides)
    return ReleaseReadinessReport(**base)


ALL_FACTORIES = (
    make_requirement,
    make_charter,
    make_plan,
    make_suite,
    make_case,
    make_eval_suite,
    make_run,
    make_regression,
    make_finding,
    make_patch,
    make_attempt,
    make_loop_report,
    make_alert,
    make_simulation_contract,
    make_simulation_branch,
    make_simulation_evidence,
    make_persona,
    make_scenario,
    make_error_injection,
    make_decision_trace,
    make_near_miss,
    make_branch,
    make_release_candidate,
    make_release_decision,
    make_readiness_report,
)
