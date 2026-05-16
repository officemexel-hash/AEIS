"""Dataclass models substituting for generated proto stubs.

When proto codegen is wired in, these fields map 1:1 to the AdvisorCardEnvelope
contract documented in docs/claude_parallel/aeis_advisor/00_architecture/01_advisor_card_schema.md.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Enums (string-typed for JSON friendliness)
# ---------------------------------------------------------------------------

CARD_TYPES = ("decision", "funding", "security", "scaling", "onboarding")
RISK_LEVELS = ("low", "medium", "high", "critical")
CONFIDENCE_LABELS = ("low", "med", "high", "very_high", "certain")
CARD_SOURCES = ("rule_engine", "llm_judge", "history_match", "council_vote", "hybrid")
DECISION_LEVELS = ("D0", "D1", "D2", "D3", "D4", "D5")
PRIORITIES = ("low", "normal", "high", "urgent")
PUSH_PRIORITIES = ("silent", "low", "normal", "high", "urgent")
IMPACT_CONFIDENCES = ("assumption", "profile", "measured")
CARD_ACTIONS = (
    "accept",
    "reject",
    "modify",
    "remind_later",
    "not_useful",
    "convert_to_human_gate",
    "convert_to_masterplan_change",
    "save_as_preference",
    "dont_learn_from_this",
)
GATE_DECISIONS = ("proceed", "block", "defer_to_human_gate")


def confidence_label_for(score: float) -> str:
    if score < 0.50:
        return "low"
    if score < 0.75:
        return "med"
    if score < 0.90:
        return "high"
    if score < 0.98:
        return "very_high"
    return "certain"


def new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Impact / Money / Alternative
# ---------------------------------------------------------------------------


@dataclass
class Money:
    amount: str = "0"
    currency: str = "USD"


@dataclass
class Impact:
    absolute_value: str = "0"
    unit: str = "USD"
    delta_vs_baseline_pct: float = 0.0
    baseline_label: str = ""
    estimate_confidence: str = "assumption"
    is_assumption: bool = True
    source_label: str = "assumption"


@dataclass
class Alternative:
    title: str = ""
    short_description: str = ""
    cost_delta_vs_primary: Impact = field(default_factory=Impact)
    time_delta_vs_primary: Impact = field(default_factory=lambda: Impact(unit="seconds"))
    risk_level: str = "low"
    confidence_score: float = 0.5
    trade_off_summary: str = ""


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


@dataclass
class AdvisorCardHeader:
    card_id: str = field(default_factory=new_uuid)
    schema_version: str = "1.0.0"
    card_type: str = "decision"
    parent_card_id: str = ""

    title: str = ""
    rationale: str = ""

    confidence_score: float = 0.0
    confidence_label: str = "low"

    sources: list[str] = field(default_factory=list)

    risk_level: str = "low"
    risk_explanation: str = ""

    project_domain: str = ""
    project_type: str = ""
    project_id: str = ""
    idea_id: str = ""

    d_level: str = "D0"
    evidence_pack_id: str = ""

    history_based: bool = False
    related_history_card_ids: list[str] = field(default_factory=list)
    historical_acceptance_rate: float = 0.0

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    priority: str = "normal"
    tags: list[str] = field(default_factory=list)

    dont_learn: bool = False
    human_gate_required: bool = False

    mobile_allowed: bool = True
    requires_biometric: bool = False
    push_priority: str = "normal"

    audit_trail_id: str = field(default_factory=new_uuid)
    llm_judge_audit_id: str = ""
    operator_id: str = ""
    emitting_module: str = "sylion.aeis.advisor.engine"

    used_local_fallback: bool = False
    local_fallback_reason: str = ""

    d_level_assignment_trace: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Bodies
# ---------------------------------------------------------------------------


@dataclass
class DecisionCard:
    recommendation: str = ""
    expected_benefit: str = ""
    expected_downside: str = ""
    quality_impact: str = ""

    cost_impact: Impact = field(default_factory=Impact)
    token_impact: Impact = field(default_factory=lambda: Impact(unit="tokens"))
    time_impact: Impact = field(default_factory=lambda: Impact(unit="seconds"))

    alternatives: list[Alternative] = field(default_factory=list)

    recommendation_type: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    source_data_ids: list[str] = field(default_factory=list)
    assumption_note: str = ""


@dataclass
class FundingCard:
    suggestion_type: str = ""
    headline_recommendation: str = ""
    grant_program_id: str = ""
    grant_program_name: str = ""
    grant_source: str = ""
    country: str = ""
    region: str = ""

    grant_amount_min: Money = field(default_factory=Money)
    grant_amount_max: Money = field(default_factory=Money)

    eligibility_score: float = 0.0
    eligibility_breakdown: list[dict[str, Any]] = field(default_factory=list)
    eligibility_floor_breached: bool = False

    current_match_summary: str = ""
    gaps_to_qualify: list[str] = field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)

    consortium_required: bool = False
    consortium_suggestions: list[dict[str, Any]] = field(default_factory=list)

    application_deadline: float = 0.0
    time_to_prepare_seconds: int = 0
    deadline_at_risk: bool = False

    static_simulations: list[dict[str, Any]] = field(default_factory=list)
    dynamic_simulations: list[dict[str, Any]] = field(default_factory=list)
    auto_simulations: list[dict[str, Any]] = field(default_factory=list)

    match_confidence: float = 0.0
    scoring_profile_id: str = ""


@dataclass
class SecurityCard:
    vulnerability_summary: str = ""
    severity: str = "low"
    remediation_summary: str = ""


@dataclass
class ScalingCard:
    recommended_topology: str = "local_only"
    alternatives: list[str] = field(default_factory=list)
    staging_plan: str = ""
    speed_gain: Impact = field(default_factory=Impact)
    local_load_change: Impact = field(default_factory=Impact)
    infrastructure_cost: Impact = field(default_factory=Impact)
    token_cost: Impact = field(default_factory=lambda: Impact(unit="tokens"))
    coordination_complexity: str = "low"
    module_conflict_risk: str = "low"
    recommended_env_count: int = 1
    should_be_staged: bool = False


@dataclass
class OnboardingCard:
    wizard_step: str = ""
    smart_default_value: str = ""
    smart_default_rationale: str = ""
    can_skip: bool = True


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


@dataclass
class AdvisorCardEnvelope:
    envelope_version: str = "1.0.0"
    header: AdvisorCardHeader = field(default_factory=AdvisorCardHeader)
    decision: DecisionCard | None = None
    funding: FundingCard | None = None
    security: SecurityCard | None = None
    scaling: ScalingCard | None = None
    onboarding: OnboardingCard | None = None

    def body(self) -> Any:
        for attr in ("decision", "funding", "security", "scaling", "onboarding"):
            v = getattr(self, attr)
            if v is not None:
                return v
        return None


# ---------------------------------------------------------------------------
# Evidence Pack
# ---------------------------------------------------------------------------


@dataclass
class EvidencePack:
    evidence_pack_id: str = field(default_factory=new_uuid)
    card_id: str = ""
    d_level: str = "D3"
    pack_template: str = "d3_light"
    decision_class: str = ""
    domain: str = ""
    rationale: str = ""
    rollback_plan: str = ""
    fidelity_test: str = ""
    confidence_breakdown: dict[str, Any] = field(default_factory=dict)
    historical_acceptance_rate: float = 0.0
    llm_judge_audit_ids: list[str] = field(default_factory=list)
    simulation_results: list[dict[str, Any]] = field(default_factory=list)
    council_vote_id: str = ""
    risk_analysis: dict[str, Any] = field(default_factory=dict)
    compliance_check: dict[str, Any] = field(default_factory=dict)
    sentinel_signoffs: dict[str, Any] = field(default_factory=dict)
    attachments: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: float = field(default_factory=time.time)
    finalized_at: float = 0.0
    status: str = "draft"


# ---------------------------------------------------------------------------
# Rule + firing
# ---------------------------------------------------------------------------


@dataclass
class Rule:
    rule_id: str
    description: str
    hook_event_pattern: str
    precondition: dict[str, Any]
    recommendation_type: str
    default_d_level: str = "D1"
    is_active: bool = True
    version: int = 1


@dataclass
class RuleFiring:
    firing_id: str = field(default_factory=new_uuid)
    rule_id: str = ""
    rule_version: int = 1
    triggering_event_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    produced_card_id: str = ""
    decision_taken: str = "skipped"
    fired_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Card context (passed through the pipeline)
# ---------------------------------------------------------------------------


@dataclass
class CardContext:
    """Context the engine builds before invoking judge / d-ladder / builder."""

    operator_id: str
    triggering_event_topic: str
    triggering_event_payload: dict[str, Any]
    triggering_event_id: str = ""
    project_id: str = ""
    project_type: str = ""
    project_domain: str = ""
    idea_id: str = ""
    rule: Rule | None = None
    preferences: dict[str, Any] = field(default_factory=dict)
    pricing_snapshot: dict[str, Any] = field(default_factory=dict)
    history_snapshot: dict[str, Any] = field(default_factory=dict)
    council_snapshot: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    cost_estimate_usd: float = 0.0
    affects_production: bool = False
    affects_multiple_projects: bool = False
    rollback_takes_days: float = 0.0
    rollback_data_loss: bool = False
    autonomy_level: str = "suggest"
