"""W14 Testing Ontology — 25 canonical dataclasses.

Spec: docs/w14_workplan/ontology_spec.yaml (FROZEN, E0 HG approved 2026-04-26).

Groups:
    Core testing       (8): Requirement, TestCharter, TestPlan, TestSuite,
                            TestCase, EvaluationSuite, TestRun, RegressionRun
    Findings & Repair  (5): Finding, PatchProposal, RepairAttempt, LoopReport,
                            GuardianAlert
    Simulation         (8): SimulationContract, SimulationBranch,
                            SimulationEvidence, HumanPersona, HumanScenario,
                            HumanErrorInjection, HumanDecisionTrace,
                            HumanNearMiss
    Branches & Release (4): Branch, ReleaseCandidate, ReleaseDecision,
                            ReleaseReadinessReport

All IDs follow `<prefix>_<uuid4-hex-12>` convention. All timestamps are float
epoch seconds (UTC). All durations carry an explicit suffix (_ms, _s, _min).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sylion.aeis.testing.ontology._validators import (
    require_branch_not_main,
    require_enum_subset,
    require_enum_value,
    require_in_range,
    require_positive,
    require_prefix,
    require_uuid_hex,
)
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


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# Status transition graphs --------------------------------------------------

CHARTER_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"proposed", "rejected"},
    "proposed": {"approved", "rejected"},
    "approved": {"archived"},
    "rejected": {"archived"},
    "archived": set(),
}

CHARTER_STATUSES: tuple[str, ...] = (
    "draft", "proposed", "approved", "rejected", "archived",
)

PATCH_STATUSES: tuple[str, ...] = (
    "draft", "proposed", "approved", "rejected", "applied", "reverted",
)

REPAIR_RESULTS: tuple[str, ...] = (
    "success", "failed_same", "failed_new",
    "regression_failed", "blocked_by_loop",
)

LOOP_TYPES: tuple[str, ...] = (
    "same_failure", "no_progress", "new_failures",
    "test_modification", "scope_drift", "semantic_repeat",
)

REQUIREMENT_SOURCES: tuple[str, ...] = (
    "SoT", "Masterplan", "HumanDecision", "CouncilDecision",
)

TESTRUN_STATUSES: tuple[str, ...] = (
    "running", "passed", "failed", "skipped", "error",
)

REGRESSION_STATUSES: tuple[str, ...] = ("pending", "passed", "failed")

RELEASE_OUTCOMES: tuple[str, ...] = (
    "approved", "rejected", "deferred", "rollback",
)

DIFFICULTY_LEVELS: tuple[str, ...] = ("easy", "medium", "hard")

RISK_TOLERANCE_LEVELS: tuple[str, ...] = ("low", "medium", "high")


# ---------------------------------------------------------------------------
# Core testing (8)
# ---------------------------------------------------------------------------


@dataclass
class Requirement:
    """A testable assertion derived from SoT/Masterplan/HumanDecision/CouncilDecision."""

    req_id: str = field(default_factory=lambda: _new_id("req"))
    source: str = ""
    source_ref: str = ""
    criticality: str = DLevel.D0.value
    test_required: bool = True
    description: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.req_id, "req_", "req_id")
        if self.source not in REQUIREMENT_SOURCES:
            raise ValueError(
                f"source must be one of {REQUIREMENT_SOURCES}, got {self.source!r}"
            )
        if not self.source_ref:
            raise ValueError("source_ref is required")
        require_enum_value(self.criticality, DLevel, "criticality")
        if not self.description:
            raise ValueError("description is required")


@dataclass
class TestCharter:
    """Per-project testing strategy approved before Masterplan execution."""

    __test__ = False  # pytest collection hint: this is a W14 dataclass

    charter_id: str = field(default_factory=lambda: _new_id("tc"))
    project_id: str = ""
    idea_id: str | None = None
    source_of_truth_version: str = ""
    masterplan_version: str = ""
    scope: dict[str, Any] = field(default_factory=dict)
    required_test_classes: list[str] = field(default_factory=list)
    required_personas: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    release_blockers: list[str] = field(default_factory=list)
    auto_repair_policy: dict[str, Any] = field(default_factory=dict)
    approval: dict[str, Any] = field(default_factory=dict)
    hg_ticket_id: str | None = None
    council_session_id: str | None = None
    status: str = "draft"
    created_at: float = field(default_factory=time.time)
    approved_at: float | None = None

    def __post_init__(self) -> None:
        require_prefix(self.charter_id, "tc_", "charter_id")
        require_uuid_hex(self.charter_id, "charter_id")
        if not self.project_id:
            raise ValueError("project_id is required")
        if not (
            isinstance(self.project_id, str)
            and (
                self.project_id.startswith("proj_")
                or self.project_id.startswith("project_")
            )
        ):
            raise ValueError(
                "project_id must start with 'proj_' or 'project_', "
                f"got: {self.project_id!r}"
            )
        if not self.source_of_truth_version:
            raise ValueError("source_of_truth_version is required")
        if not self.masterplan_version:
            raise ValueError("masterplan_version is required")
        require_enum_subset(
            self.required_test_classes, TestClass, "required_test_classes"
        )
        if self.status not in CHARTER_STATUSES:
            raise ValueError(
                f"status must be in {CHARTER_STATUSES}, got {self.status!r}"
            )
        if not isinstance(self.approval, dict):
            raise ValueError("approval must be a dict")
        approval_d = self.approval.get("d_level")
        if approval_d is not None:
            require_enum_value(approval_d, DLevel, "approval.d_level")


@dataclass
class TestPlan:
    """Detailed plan derived from charter — concrete test suites + schedule."""

    __test__ = False

    plan_id: str = field(default_factory=lambda: _new_id("tp"))
    charter_id: str = ""
    suites: list[str] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    parallelization_groups: list[list[str]] = field(default_factory=list)
    estimated_duration_s: int = 0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.plan_id, "tp_", "plan_id")
        require_prefix(self.charter_id, "tc_", "charter_id")
        if self.estimated_duration_s < 0:
            raise ValueError("estimated_duration_s must be >= 0")


@dataclass
class TestSuite:
    """Logical grouping of TestCases."""

    __test__ = False

    suite_id: str = field(default_factory=lambda: _new_id("ts"))
    plan_id: str | None = None
    name: str = ""
    test_class: str = TestClass.UNIT.value
    case_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    enabled: bool = True

    def __post_init__(self) -> None:
        require_prefix(self.suite_id, "ts_", "suite_id")
        if not self.name:
            raise ValueError("name is required")
        require_enum_value(self.test_class, TestClass, "test_class")


@dataclass
class TestCase:
    """Single test case with input, expected output, evaluator."""

    __test__ = False

    case_id: str = field(default_factory=lambda: _new_id("tc"))
    requirement_id: str = ""
    suite_id: str | None = None
    input_payload: dict[str, Any] = field(default_factory=dict)
    expected_output: dict[str, Any] = field(default_factory=dict)
    evaluator: str = ""
    persona_id: str | None = None
    real_example_id: str | None = None
    tags: list[str] = field(default_factory=list)
    enabled: bool = True

    def __post_init__(self) -> None:
        require_prefix(self.case_id, "tc_", "case_id")
        require_prefix(self.requirement_id, "req_", "requirement_id")
        if not self.evaluator:
            raise ValueError("evaluator is required")


@dataclass
class EvaluationSuite:
    """AIP Evals-like: target function + test cases + evaluators + metrics."""

    suite_id: str = field(default_factory=lambda: _new_id("es"))
    target_function: str = ""
    target_module: str = ""
    test_case_ids: list[str] = field(default_factory=list)
    evaluators: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    baseline_run_id: str | None = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.suite_id, "es_", "suite_id")
        if not self.target_function:
            raise ValueError("target_function is required")
        if not self.target_module:
            raise ValueError("target_module is required")
        if not self.test_case_ids:
            raise ValueError("test_case_ids must be non-empty")
        if not self.evaluators:
            raise ValueError("evaluators must be non-empty")
        if not self.metrics:
            raise ValueError("metrics must be non-empty")


@dataclass
class TestRun:
    """Single execution of suite or case (in branch context)."""

    __test__ = False

    run_id: str = field(default_factory=lambda: _new_id("tr"))
    suite_id: str | None = None
    case_id: str | None = None
    branch_id: str = ""
    charter_id: str | None = None
    status: str = "running"
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    duration_ms: int | None = None
    cost_usd: float = 0.0
    evidence_pack_id: str | None = None
    trace_id: str = ""
    result_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_prefix(self.run_id, "tr_", "run_id")
        if not self.branch_id:
            raise ValueError("branch_id is required")
        if not self.trace_id:
            raise ValueError("trace_id is required")
        if self.status not in TESTRUN_STATUSES:
            raise ValueError(
                f"status must be in {TESTRUN_STATUSES}, got {self.status!r}"
            )
        if self.cost_usd < 0:
            raise ValueError("cost_usd must be >= 0")


@dataclass
class RegressionRun:
    """Specialized TestRun comparing pre-fix vs post-fix behavior."""

    regression_id: str = field(default_factory=lambda: _new_id("rr"))
    finding_id: str = ""
    pre_fix_run_id: str = ""
    post_fix_run_id: str = ""
    neighbor_test_run_ids: list[str] = field(default_factory=list)
    status: str = "pending"
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def __post_init__(self) -> None:
        require_prefix(self.regression_id, "rr_", "regression_id")
        require_prefix(self.finding_id, "find_", "finding_id")
        if not self.pre_fix_run_id:
            raise ValueError("pre_fix_run_id is required")
        if not self.post_fix_run_id:
            raise ValueError("post_fix_run_id is required")
        if self.status not in REGRESSION_STATUSES:
            raise ValueError(
                f"status must be in {REGRESSION_STATUSES}, got {self.status!r}"
            )


# ---------------------------------------------------------------------------
# Findings & Repair (5)
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """Detected defect, drift, or violation requiring action."""

    finding_id: str = field(default_factory=lambda: _new_id("find"))
    severity: str = Severity.P2.value
    requirement_id: str | None = None
    test_run_id: str | None = None
    guardian_alert_id: str | None = None
    r_status: str = RStatus.OPEN.value
    d_level: str = DLevel.D2.value
    title: str = ""
    description: str = ""
    discovered_by: str = ""
    ticket_id: str | None = None
    created_at: float = field(default_factory=time.time)
    closed_at: float | None = None

    def __post_init__(self) -> None:
        require_prefix(self.finding_id, "find_", "finding_id")
        require_enum_value(self.severity, Severity, "severity")
        require_enum_value(self.r_status, RStatus, "r_status")
        require_enum_value(self.d_level, DLevel, "d_level")
        if not self.title:
            raise ValueError("title is required")
        if not self.description:
            raise ValueError("description is required")
        if not self.discovered_by:
            raise ValueError("discovered_by is required")


@dataclass
class PatchProposal:
    """Proposed fix for a finding (always on a branch, never on main)."""

    proposal_id: str = field(default_factory=lambda: _new_id("patch"))
    finding_id: str = ""
    branch_id: str = ""
    diff_text: str = ""
    files_touched: list[str] = field(default_factory=list)
    diff_lines_added: int = 0
    diff_lines_removed: int = 0
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    tests_to_run: list[str] = field(default_factory=list)
    status: str = "draft"
    proposed_by: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.proposal_id, "patch_", "proposal_id")
        require_prefix(self.finding_id, "find_", "finding_id")
        if not self.branch_id:
            raise ValueError("branch_id is required")
        require_branch_not_main(self.branch_id, "branch_id")
        if not self.files_touched:
            raise ValueError("files_touched must be non-empty")
        if self.diff_lines_added < 0 or self.diff_lines_removed < 0:
            raise ValueError("diff_lines_added/removed must be >= 0")
        if (self.diff_lines_added + self.diff_lines_removed) <= 0:
            raise ValueError("diff_lines_added + diff_lines_removed must be > 0")
        if self.status not in PATCH_STATUSES:
            raise ValueError(
                f"status must be in {PATCH_STATUSES}, got {self.status!r}"
            )
        if not self.proposed_by:
            raise ValueError("proposed_by is required")


@dataclass
class RepairAttempt:
    """Single iteration of Auto-Repair Controller; tracked by Loop Governor."""

    attempt_id: str = field(default_factory=lambda: _new_id("ra"))
    finding_id: str = ""
    n: int = 1
    patch_proposal_id: str | None = None
    r_phase: str = RStatus.REPAIRING.value
    result: str = "success"
    files_touched_count: int = 0
    diff_lines: int = 0
    time_in_phase_s: float = 0.0
    cost_usd: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def __post_init__(self) -> None:
        require_prefix(self.attempt_id, "ra_", "attempt_id")
        require_prefix(self.finding_id, "find_", "finding_id")
        require_positive(self.n, "n")
        require_enum_value(self.r_phase, RStatus, "r_phase")
        if self.result not in REPAIR_RESULTS:
            raise ValueError(
                f"result must be in {REPAIR_RESULTS}, got {self.result!r}"
            )
        if self.files_touched_count < 0:
            raise ValueError("files_touched_count must be >= 0")
        if self.diff_lines < 0:
            raise ValueError("diff_lines must be >= 0")
        if self.time_in_phase_s < 0:
            raise ValueError("time_in_phase_s must be >= 0")
        if self.cost_usd < 0:
            raise ValueError("cost_usd must be >= 0")


@dataclass
class LoopReport:
    """Generated when Loop Governor blocks repair after limit."""

    report_id: str = field(default_factory=lambda: _new_id("lr"))
    finding_id: str = ""
    loop_type: str = "same_failure"
    attempts_n: int = 0
    similarity_score: float = 0.0
    suspected_root_cause: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    required_decision: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.report_id, "lr_", "report_id")
        require_prefix(self.finding_id, "find_", "finding_id")
        if self.loop_type not in LOOP_TYPES:
            raise ValueError(
                f"loop_type must be in {LOOP_TYPES}, got {self.loop_type!r}"
            )
        if self.attempts_n < 0:
            raise ValueError("attempts_n must be >= 0")
        require_in_range(self.similarity_score, 0.0, 1.0, "similarity_score")
        if not self.required_decision:
            raise ValueError("required_decision is required")


@dataclass
class GuardianAlert:
    """Alert raised by one of 13 guardians; may convert to Finding."""

    alert_id: str = field(default_factory=lambda: _new_id("ga"))
    guardian: str = GuardianClass.SOT_GUARDIAN.value
    severity: str = Severity.P3.value
    source_event_id: str | None = None
    evidence_link: dict[str, Any] = field(default_factory=dict)
    finding_id: str | None = None
    reason: str = ""
    acknowledged: bool = False
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.alert_id, "ga_", "alert_id")
        require_enum_value(self.guardian, GuardianClass, "guardian")
        require_enum_value(self.severity, Severity, "severity")
        if not self.evidence_link:
            raise ValueError("evidence_link is required")
        if not self.reason:
            raise ValueError("reason is required")


# ---------------------------------------------------------------------------
# Simulation (8)
# ---------------------------------------------------------------------------


@dataclass
class SimulationContract:
    """L0 of Simulation Engine — defines isolation, mode, persistence, safety."""

    contract_id: str = field(default_factory=lambda: _new_id("sc"))
    simulation_id: str = ""
    branch_id: str = ""
    source_project_id: str = ""
    sot_version: str = ""
    masterplan_version: str = ""
    test_charter_id: str | None = None
    isolation: dict[str, Any] = field(default_factory=dict)
    model_mode: dict[str, Any] = field(default_factory=dict)
    persistence: dict[str, Any] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.contract_id, "sc_", "contract_id")
        if not self.simulation_id:
            raise ValueError("simulation_id is required")
        if not self.branch_id:
            raise ValueError("branch_id is required")
        if not self.source_project_id:
            raise ValueError("source_project_id is required")
        if not self.sot_version:
            raise ValueError("sot_version is required")
        if not self.masterplan_version:
            raise ValueError("masterplan_version is required")

        if not isinstance(self.isolation, dict) or not self.isolation:
            raise ValueError("isolation is required and must be a dict")
        if not isinstance(self.safety, dict) or not self.safety:
            raise ValueError("safety is required and must be a dict")

        # Hard safety constraints (per ontology_spec.yaml validators)
        if self.isolation.get("main_mutation_allowed") is True:
            d_level = self.safety.get("approved_d_level")
            council_ok = self.safety.get("council_approved", False)
            if d_level != DLevel.D5.value or not council_ok:
                raise ValueError(
                    "isolation.main_mutation_allowed=true requires "
                    "safety.approved_d_level=D5 + safety.council_approved=true"
                )
        if self.isolation.get("external_network_allowed") is True:
            d_level = self.safety.get("approved_d_level")
            sentinel_ok = self.safety.get("sentinel_approved", False)
            if d_level not in (DLevel.D4.value, DLevel.D5.value) or not sentinel_ok:
                raise ValueError(
                    "isolation.external_network_allowed=true requires "
                    "safety.approved_d_level in [D4,D5] + safety.sentinel_approved=true"
                )

        max_runtime = self.safety.get("max_runtime_seconds")
        if max_runtime is not None and max_runtime > 3600:
            raise ValueError(
                f"safety.max_runtime_seconds must be <= 3600, got {max_runtime}"
            )
        max_cost = self.safety.get("max_cost_usd")
        if max_cost is not None and max_cost > 10.0:
            raise ValueError(
                f"safety.max_cost_usd must be <= 10.0, got {max_cost}"
            )


@dataclass
class SimulationBranch:
    """Specialized Branch for L1-L4 simulations; auto-discard after run."""

    sim_branch_id: str = field(default_factory=lambda: _new_id("simb"))
    parent_branch_id: str | None = None
    contract_id: str = ""
    state: str = BranchState.OPEN.value
    discard_reason: str | None = None
    snapshot_db_path: str | None = None
    created_at: float = field(default_factory=time.time)
    discarded_at: float | None = None

    def __post_init__(self) -> None:
        require_prefix(self.sim_branch_id, "simb_", "sim_branch_id")
        require_prefix(self.contract_id, "sc_", "contract_id")
        require_enum_value(self.state, BranchState, "state")


@dataclass
class SimulationEvidence:
    """Persisted evidence from simulation (trace, logs, screenshots, hashes)."""

    evidence_id: str = field(default_factory=lambda: _new_id("se"))
    simulation_id: str = ""
    sim_branch_id: str = ""
    trace_id: str = ""
    layer_executed: int = 1
    screenshots_uri: list[str] = field(default_factory=list)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    branch_snapshot_hash: str = ""
    evaluator_outputs: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.evidence_id, "se_", "evidence_id")
        if not self.simulation_id:
            raise ValueError("simulation_id is required")
        require_prefix(self.sim_branch_id, "simb_", "sim_branch_id")
        if not self.trace_id:
            raise ValueError("trace_id is required")
        if self.layer_executed not in (1, 2, 3, 4):
            raise ValueError(
                f"layer_executed must be in [1,2,3,4], got {self.layer_executed}"
            )
        if not isinstance(self.event_log, list):
            raise ValueError("event_log must be a list")
        if not self.branch_snapshot_hash or len(self.branch_snapshot_hash) != 64:
            raise ValueError(
                "branch_snapshot_hash must be a 64-char SHA256 hex string"
            )
        if not isinstance(self.evaluator_outputs, dict):
            raise ValueError("evaluator_outputs must be a dict")


@dataclass
class HumanPersona:
    """Simulated human actor with baseline + dynamic state."""

    persona_id: str = field(default_factory=lambda: _new_id("persona"))
    name: str = ""
    capability_level: str = PersonaCapability.INTERMEDIATE.value
    expertise_domains: list[str] = field(default_factory=list)
    error_proneness: float = 0.0
    attention_span_min: int = 30
    trust_in_ai_baseline: float = 0.5
    risk_tolerance: str = "medium"
    dynamic_state: dict[str, Any] = field(default_factory=dict)
    behavior_modifiers: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.persona_id, "persona_", "persona_id")
        if not self.name:
            raise ValueError("name is required")
        require_enum_value(self.capability_level, PersonaCapability, "capability_level")
        require_in_range(self.error_proneness, 0.0, 1.0, "error_proneness")
        require_in_range(self.trust_in_ai_baseline, 0.0, 1.0, "trust_in_ai_baseline")
        if self.attention_span_min < 1:
            raise ValueError("attention_span_min must be >= 1")
        if self.risk_tolerance not in RISK_TOLERANCE_LEVELS:
            raise ValueError(
                f"risk_tolerance must be in {RISK_TOLERANCE_LEVELS}, "
                f"got {self.risk_tolerance!r}"
            )
        if not isinstance(self.dynamic_state, dict):
            raise ValueError("dynamic_state must be a dict")
        if not isinstance(self.behavior_modifiers, dict):
            raise ValueError("behavior_modifiers must be a dict")


@dataclass
class HumanScenario:
    """Workflow scenario for a persona to execute."""

    scenario_id: str = field(default_factory=lambda: _new_id("scn"))
    persona_id: str = ""
    domain: str = ""
    workflow_steps: list[dict[str, Any]] = field(default_factory=list)
    decision_points: list[dict[str, Any]] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    comprehension_check: dict[str, Any] = field(default_factory=dict)
    difficulty: str = "medium"
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.scenario_id, "scn_", "scenario_id")
        require_prefix(self.persona_id, "persona_", "persona_id")
        if not self.domain:
            raise ValueError("domain is required")
        if not self.workflow_steps:
            raise ValueError("workflow_steps must be non-empty")
        if not self.decision_points:
            raise ValueError("decision_points must be non-empty")
        if not self.success_criteria:
            raise ValueError("success_criteria must be non-empty")
        if not self.comprehension_check:
            raise ValueError("comprehension_check is required")
        if self.difficulty not in DIFFICULTY_LEVELS:
            raise ValueError(
                f"difficulty must be in {DIFFICULTY_LEVELS}, got {self.difficulty!r}"
            )


@dataclass
class HumanErrorInjection:
    """Scripted human error injection for L4 simulation."""

    injection_id: str = field(default_factory=lambda: _new_id("hei"))
    error_class: str = HumanErrorClass.WRONG_CLICK.value
    target_action: str = ""
    timing: str = ""
    context: str = ""
    expected_system_response: list[str] = field(default_factory=list)
    severity_if_system_allows_error: str = DLevel.D2.value
    simulated_target_d_level: str = DLevel.D2.value
    action_d_level: str = DLevel.D2.value
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.injection_id, "hei_", "injection_id")
        require_enum_value(self.error_class, HumanErrorClass, "error_class")
        if not self.target_action:
            raise ValueError("target_action is required")
        if not self.timing:
            raise ValueError("timing is required")
        if not self.expected_system_response:
            raise ValueError("expected_system_response must be non-empty")
        require_enum_value(
            self.severity_if_system_allows_error, DLevel, "severity_if_system_allows_error"
        )
        require_enum_value(
            self.simulated_target_d_level, DLevel, "simulated_target_d_level"
        )
        require_enum_value(self.action_d_level, DLevel, "action_d_level")


@dataclass
class HumanDecisionTrace:
    """Record of persona's actions, perception, and behavior metrics."""

    trace_id: str = field(default_factory=lambda: _new_id("hdt"))
    persona_id: str = ""
    scenario_id: str | None = None
    simulation_id: str = ""
    decisions_made: list[dict[str, Any]] = field(default_factory=list)
    visible_state_snapshot: dict[str, Any] = field(default_factory=dict)
    perception_model: dict[str, Any] = field(default_factory=dict)
    behavior_metrics: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.trace_id, "hdt_", "trace_id")
        require_prefix(self.persona_id, "persona_", "persona_id")
        if not self.simulation_id:
            raise ValueError("simulation_id is required")
        if not isinstance(self.decisions_made, list):
            raise ValueError("decisions_made must be a list")
        if not self.visible_state_snapshot:
            raise ValueError("visible_state_snapshot is required")
        if not self.perception_model:
            raise ValueError("perception_model is required")
        if not self.behavior_metrics:
            raise ValueError("behavior_metrics is required")


@dataclass
class HumanNearMiss:
    """Error correctly blocked by system, but UX improvement may be needed."""

    near_miss_id: str = field(default_factory=lambda: _new_id("nm"))
    scenario_id: str | None = None
    error_injection_id: str = ""
    blocked_successfully: bool = True
    operator_message_quality_score: float = 1.0
    future_risk: str = "low"
    suggested_ui_improvement: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.near_miss_id, "nm_", "near_miss_id")
        require_prefix(self.error_injection_id, "hei_", "error_injection_id")
        require_in_range(
            self.operator_message_quality_score, 0.0, 1.0,
            "operator_message_quality_score",
        )
        if self.future_risk not in RISK_TOLERANCE_LEVELS:
            raise ValueError(
                f"future_risk must be in {RISK_TOLERANCE_LEVELS}, "
                f"got {self.future_risk!r}"
            )


# ---------------------------------------------------------------------------
# Branches & Release (4)
# ---------------------------------------------------------------------------


@dataclass
class Branch:
    """Generic branch for repair, test, or release work."""

    branch_id: str = field(default_factory=lambda: _new_id("br"))
    branch_type: str = BranchType.TEST.value
    parent_branch_id: str | None = "main"
    project_id: str = ""
    sot_version: str = ""
    masterplan_version: str = ""
    state: str = BranchState.OPEN.value
    created_by: str = ""
    created_at: float = field(default_factory=time.time)
    merged_at: float | None = None
    discarded_at: float | None = None

    def __post_init__(self) -> None:
        require_prefix(self.branch_id, "br_", "branch_id")
        require_enum_value(self.branch_type, BranchType, "branch_type")
        require_enum_value(self.state, BranchState, "state")
        if not self.project_id:
            raise ValueError("project_id is required")
        if not self.sot_version:
            raise ValueError("sot_version is required")
        if not self.masterplan_version:
            raise ValueError("masterplan_version is required")
        if not self.created_by:
            raise ValueError("created_by is required")


@dataclass
class ReleaseCandidate:
    """Branch promoted as candidate for production release."""

    rc_id: str = field(default_factory=lambda: _new_id("rc"))
    branch_id: str = ""
    project_id: str = ""
    test_run_summary: dict[str, Any] = field(default_factory=dict)
    unresolved_findings: list[str] = field(default_factory=list)
    evidence_pack_id: str | None = None
    gate_status: str = ReleaseStatus.NOT_TESTED.value
    blockers: list[str] = field(default_factory=list)
    promoted_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.rc_id, "rc_", "rc_id")
        require_prefix(self.branch_id, "br_", "branch_id")
        if not self.project_id:
            raise ValueError("project_id is required")
        if not self.test_run_summary:
            raise ValueError("test_run_summary is required")
        require_enum_value(self.gate_status, ReleaseStatus, "gate_status")


@dataclass
class ReleaseDecision:
    """Final decision (Council + HG) for production promotion or rollback."""

    decision_id: str = field(default_factory=lambda: _new_id("rd"))
    rc_id: str = ""
    charter_id: str | None = None
    hg_ticket_id: str = ""
    council_session_id: str | None = None
    outcome: str = "deferred"
    rollback_plan: dict[str, Any] = field(default_factory=dict)
    signatures: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.decision_id, "rd_", "decision_id")
        require_prefix(self.rc_id, "rc_", "rc_id")
        if not self.hg_ticket_id:
            raise ValueError("hg_ticket_id is required")
        if self.outcome not in RELEASE_OUTCOMES:
            raise ValueError(
                f"outcome must be in {RELEASE_OUTCOMES}, got {self.outcome!r}"
            )
        if not self.rollback_plan:
            raise ValueError("rollback_plan is required")
        if not self.signatures:
            raise ValueError("signatures must be non-empty")


@dataclass
class ReleaseReadinessReport:
    """Summary report for operator: 12+6 checklist results + recommendations."""

    report_id: str = field(default_factory=lambda: _new_id("rrr"))
    rc_id: str = ""
    checklist_results: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    cost_summary: dict[str, Any] = field(default_factory=dict)
    latency_summary: dict[str, Any] = field(default_factory=dict)
    evidence_tier_used: str = EvidenceTier.H1.value
    human_comprehension_score: float = 1.0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        require_prefix(self.report_id, "rrr_", "report_id")
        require_prefix(self.rc_id, "rc_", "rc_id")
        if not self.checklist_results:
            raise ValueError("checklist_results is required")
        if not self.cost_summary:
            raise ValueError("cost_summary is required")
        if not self.latency_summary:
            raise ValueError("latency_summary is required")
        require_enum_value(self.evidence_tier_used, EvidenceTier, "evidence_tier_used")
        require_in_range(
            self.human_comprehension_score, 0.0, 1.0, "human_comprehension_score"
        )


# ---------------------------------------------------------------------------
# Public registry (used by store + tests + migration)
# ---------------------------------------------------------------------------


OBJECT_TABLE_MAP: dict[type, str] = {
    Requirement: "w14_requirements",
    TestCharter: "w14_test_charters",
    TestPlan: "w14_test_plans",
    TestSuite: "w14_test_suites",
    TestCase: "w14_test_cases",
    EvaluationSuite: "w14_evaluation_suites",
    TestRun: "w14_test_runs",
    RegressionRun: "w14_regression_runs",
    Finding: "w14_findings",
    PatchProposal: "w14_patch_proposals",
    RepairAttempt: "w14_repair_attempts",
    LoopReport: "w14_loop_reports",
    GuardianAlert: "w14_guardian_alerts",
    SimulationContract: "w14_simulation_contracts",
    SimulationBranch: "w14_simulation_branches",
    SimulationEvidence: "w14_simulation_evidence",
    HumanPersona: "w14_human_personas",
    HumanScenario: "w14_human_scenarios",
    HumanErrorInjection: "w14_human_error_injections",
    HumanDecisionTrace: "w14_human_decision_traces",
    HumanNearMiss: "w14_human_near_misses",
    Branch: "w14_branches",
    ReleaseCandidate: "w14_release_candidates",
    ReleaseDecision: "w14_release_decisions",
    ReleaseReadinessReport: "w14_release_readiness_reports",
}


PRIMARY_KEY_MAP: dict[type, str] = {
    Requirement: "req_id",
    TestCharter: "charter_id",
    TestPlan: "plan_id",
    TestSuite: "suite_id",
    TestCase: "case_id",
    EvaluationSuite: "suite_id",
    TestRun: "run_id",
    RegressionRun: "regression_id",
    Finding: "finding_id",
    PatchProposal: "proposal_id",
    RepairAttempt: "attempt_id",
    LoopReport: "report_id",
    GuardianAlert: "alert_id",
    SimulationContract: "contract_id",
    SimulationBranch: "sim_branch_id",
    SimulationEvidence: "evidence_id",
    HumanPersona: "persona_id",
    HumanScenario: "scenario_id",
    HumanErrorInjection: "injection_id",
    HumanDecisionTrace: "trace_id",
    HumanNearMiss: "near_miss_id",
    Branch: "branch_id",
    ReleaseCandidate: "rc_id",
    ReleaseDecision: "decision_id",
    ReleaseReadinessReport: "report_id",
}


__all__ = [
    "Branch", "EvaluationSuite", "Finding", "GuardianAlert",
    "HumanDecisionTrace", "HumanErrorInjection", "HumanNearMiss",
    "HumanPersona", "HumanScenario", "LoopReport", "PatchProposal",
    "RegressionRun", "ReleaseCandidate", "ReleaseDecision",
    "ReleaseReadinessReport", "RepairAttempt", "Requirement",
    "SimulationBranch", "SimulationContract", "SimulationEvidence",
    "TestCase", "TestCharter", "TestPlan", "TestRun", "TestSuite",
    "OBJECT_TABLE_MAP", "PRIMARY_KEY_MAP",
    "CHARTER_TRANSITIONS", "CHARTER_STATUSES", "PATCH_STATUSES",
]
