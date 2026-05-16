"""Funding module dataclass models.

These dataclasses mirror the canonical PG schema (`advisor_funding.*`) and the
funding-specific proto messages from `01_advisor_card_schema.md`. They are the
in-memory representation used by the funding service before envelope hand-off
to the engine.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


GRANT_SOURCES = (
    "pl_national",
    "pl_regional",
    "eu",
    "other_country",
    "private",
    "custom",
)

ACTION_DIFFICULTIES = ("trivial", "easy", "moderate", "hard", "very_hard")

SIMULATION_MODES = ("static", "dynamic", "auto_generated")

FUNDING_SUGGESTION_TYPES = (
    "FUNDING_GRANT_FIT",
    "FUNDING_HOW_TO_QUALIFY",
    "FUNDING_FORM_COMPANY",
    "FUNDING_CHANGE_LEGAL_FORM",
    "FUNDING_REGIONAL_RELOCATION",
    "FUNDING_FIND_CONSORTIUM",
    "FUNDING_ADJUST_IDEA_FOR_GRANT",
    "FUNDING_DEADLINE_WARNING",
    "FUNDING_GAP_CLOSURE_PLAN",
    "FUNDING_SCOPE_ADJUSTMENT",
)

UNIVERSAL_COMPONENT_IDS = (
    "eligibility",
    "thematic_alignment",
    "capacity",
    "competitive_position",
    "regional_fit",
    "consortium_readiness",
    "timeline_fit",
)

DEFAULT_COMPONENT_WEIGHTS = {
    "eligibility": 30.0,
    "thematic_alignment": 20.0,
    "capacity": 15.0,
    "competitive_position": 10.0,
    "regional_fit": 10.0,
    "consortium_readiness": 10.0,
    "timeline_fit": 5.0,
}

DEFAULT_HARD_FLOORS = {"eligibility": 50.0}

RESEARCH_PURPOSES = (
    "grant_discovery",
    "scoring_assessment",
    "consortium_search",
    "simulation",
)


def new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Money:
    amount: str = "0"
    currency: str = "USD"


@dataclass
class Company:
    company_id: str = field(default_factory=new_uuid)
    operator_id: str = ""
    is_own: bool = True
    legal_name: str = ""
    legal_form: str = ""
    registration_number: str = ""
    tax_id: str = ""
    statistical_id: str = ""
    pkd_codes: list[str] = field(default_factory=list)
    country: str = ""
    region: str = ""
    size_category: str = ""
    employee_count: int = 0
    annual_revenue_usd: float = 0.0
    founding_date: str = ""
    is_msme: bool = False
    description: str = ""
    rd_budget_history: list[dict[str, Any]] = field(default_factory=list)
    innovation_certifications: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class CompanyPerson:
    person_id: str = field(default_factory=new_uuid)
    company_id: str = ""
    full_name: str = ""
    role: str = ""
    ownership_pct: float = 0.0
    experience_summary: str = ""
    experience_years: int = 0
    qualifications: list[dict[str, Any]] = field(default_factory=list)
    team_role: str = ""
    is_kp: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class GrantProgram:
    program_id: str = field(default_factory=new_uuid)
    program_code: str = ""
    display_name: str = ""
    source: str = "pl_national"
    country: str = ""
    region: str = ""
    managing_body: str = ""
    description: str = ""
    amount_min_usd: float = 0.0
    amount_max_usd: float = 0.0
    call_open_at: float = 0.0
    call_close_at: float = 0.0
    source_url: str = ""
    source_documents: list[dict[str, Any]] = field(default_factory=list)
    scoring_profile_id: str = ""
    custom_criteria: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    is_user_loaded: bool = False
    loaded_by: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ScoringComponent:
    component_id: str = ""
    display_name: str = ""
    description: str = ""
    measurement_dsl: dict[str, Any] = field(default_factory=dict)
    is_system: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass
class ProfileComponentEntry:
    component_id: str = ""
    weight: float = 0.0
    hard_floor: float = 0.0


@dataclass
class ScoringProfile:
    profile_id: str = field(default_factory=new_uuid)
    program_id: str = ""
    version: int = 1
    components: list[ProfileComponentEntry] = field(default_factory=list)
    custom_criteria: dict[str, Any] = field(default_factory=dict)
    total_weight: float = 100.0
    is_active: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass
class ComponentScore:
    component_id: str = ""
    component_name: str = ""
    weight_in_grant: float = 0.0
    score: float = 0.0
    hard_floor: float = 0.0
    floor_breached: bool = False
    explanation: str = ""
    driving_factors: list[str] = field(default_factory=list)


@dataclass
class ScoringHistoryEntry:
    scoring_id: str = field(default_factory=new_uuid)
    operator_id: str = ""
    company_id: str = ""
    idea_id: str = ""
    program_id: str = ""
    scoring_profile_id: str = ""
    total_score: float = 0.0
    component_breakdown: list[ComponentScore] = field(default_factory=list)
    eligibility_floor_breached: bool = False
    triggering_event: str = "manual_recalc"
    card_id: str = ""
    llm_judge_audit_id: str = ""
    computed_at: float = field(default_factory=time.time)


@dataclass
class ConsortiumPartner:
    partner_id: str = field(default_factory=new_uuid)
    display_name: str = ""
    entity_type: str = ""
    country: str = ""
    region: str = ""
    qualifications: list[str] = field(default_factory=list)
    contact_info: dict[str, Any] = field(default_factory=dict)
    added_by: str = ""
    notes: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass
class FundingResearchLog:
    log_id: str = field(default_factory=new_uuid)
    operator_id: str = ""
    research_purpose: str = "grant_discovery"
    prompt_tokens: int = 0
    response_tokens: int = 0
    cost_usd: float = 0.0
    model_id: str = "stub"
    external_research: bool = False
    related_card_id: str = ""
    performed_at: float = field(default_factory=time.time)


@dataclass
class RecommendedAction:
    action_id: str = field(default_factory=new_uuid)
    description: str = ""
    difficulty: str = "easy"
    estimated_time_seconds: int = 0
    estimated_cost: Money = field(default_factory=Money)
    expected_score_delta: float = 0.0
    requires_third_party: bool = False
    third_party_type: str = ""


@dataclass
class ConsortiumSuggestion:
    suggestion_id: str = field(default_factory=new_uuid)
    entity_type: str = ""
    suggested_name: str = ""
    required_qualifications: list[str] = field(default_factory=list)
    region_constraint: str = ""
    rationale: str = ""


@dataclass
class SimulationChange:
    field_path: str = ""
    from_value: str = ""
    to_value: str = ""
    explanation: str = ""


@dataclass
class SimulationScenario:
    scenario_id: str = field(default_factory=new_uuid)
    label: str = ""
    mode: str = "static"
    changes: list[SimulationChange] = field(default_factory=list)
    resulting_eligibility_score: float = 0.0
    resulting_breakdown: list[ComponentScore] = field(default_factory=list)
    cost_to_implement: Money = field(default_factory=Money)
    time_to_implement_seconds: int = 0


@dataclass
class IdeaContext:
    """Lightweight idea projection used for scoring (decoupled from IdeaVault)."""

    idea_id: str = ""
    title: str = ""
    description: str = ""
    domain: str = ""
    keywords: list[str] = field(default_factory=list)
    rd_share_pct: float = 0.0
    target_country: str = ""
    target_region: str = ""
    requires_consortium: bool = False
    expected_duration_months: int = 0
    target_budget_usd: float = 0.0
