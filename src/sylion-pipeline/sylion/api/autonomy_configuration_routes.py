"""Workspace-level Autonomy Configuration control plane for Phase 5.

Phase 5 turns Phase 4 autonomy presets into an explicit operator-governed
configuration: 10 dimensions, L0-L5 semantics, baseline hard gates, custom
hard gates, per-D-level overrides, time-bounded overrides, inheritance traces
and acceptance evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/v1/autonomy/configuration",
    tags=["Autonomy Configuration"],
)


LEVELS: list[dict[str, Any]] = [
    {
        "id": "L0",
        "label": "Always manual",
        "behavior": "Operator approves every decision before execution.",
        "best_for": ["government", "classified", "financial critical", "new operator"],
        "operator_interactions": "50-150 per project",
        "hands_on_time": "2-8h",
        "speed_multiplier": 1.0,
        "risk_multiplier": 1.0,
        "cost_variance_pct": 0,
    },
    {
        "id": "L1",
        "label": "Notify only",
        "behavior": "System proposes or acts with immediate notification and operator override.",
        "best_for": ["audit-heavy", "operator visibility", "early trust building"],
        "operator_interactions": "30-80 notifications per project",
        "hands_on_time": "30-60m",
        "speed_multiplier": 2.0,
        "risk_multiplier": 1.1,
        "cost_variance_pct": 5,
    },
    {
        "id": "L2",
        "label": "Balanced",
        "behavior": "Routine decisions are automatic; risky decisions require operator review.",
        "best_for": ["standard production work", "most operators", "mixed workloads"],
        "operator_interactions": "8-15 per project",
        "hands_on_time": "25-45m",
        "speed_multiplier": 4.0,
        "risk_multiplier": 1.3,
        "cost_variance_pct": 10,
    },
    {
        "id": "L3",
        "label": "Auto with audit",
        "behavior": "System decides and records evidence; operator reviews after the fact.",
        "best_for": ["mature preset", "volume work", "trusted internal projects"],
        "operator_interactions": "3-8 post-review items per project",
        "hands_on_time": "15-30m",
        "speed_multiplier": 8.0,
        "risk_multiplier": 1.8,
        "cost_variance_pct": 20,
    },
    {
        "id": "L4",
        "label": "Auto with sampling",
        "behavior": "System decides; operator reviews samples or suspicious cases.",
        "best_for": ["research volume", "internal tooling", "experienced operators"],
        "operator_interactions": "0-2 per project",
        "hands_on_time": "5-15m",
        "speed_multiplier": 15.0,
        "risk_multiplier": 2.5,
        "cost_variance_pct": 35,
    },
    {
        "id": "L5",
        "label": "Fully autonomous",
        "behavior": "System operates without routine operator intervention; hard gates still apply.",
        "best_for": ["proven pipelines", "research labs", "high-volume mature setup"],
        "operator_interactions": "0 outside hard gates",
        "hands_on_time": "0-5m",
        "speed_multiplier": 30.0,
        "risk_multiplier": 4.0,
        "cost_variance_pct": 60,
    },
]


AUTONOMY_DIMENSIONS: list[dict[str, Any]] = [
    {
        "id": "council_formation",
        "code": "DIM-1",
        "name": "Council Formation",
        "regulates": "Which roles and models form a council for a project.",
        "decision_points": ["standard vs custom council", "role add/remove", "multi-model voting", "cross-project role pinning"],
        "default_level": "L2",
        "operator_range": "L2-L3",
        "risk_profile": "low",
    },
    {
        "id": "council_voting_threshold",
        "code": "DIM-2",
        "name": "Council Voting Threshold",
        "regulates": "Voting threshold, quorum, veto and tie-breaking rules.",
        "decision_points": ["majority vs supermajority", "critic veto", "tie-breaks", "quorum"],
        "default_level": "L2",
        "operator_range": "L2",
        "risk_profile": "medium",
    },
    {
        "id": "cost_decisions",
        "code": "DIM-3",
        "name": "Cost Decisions",
        "regulates": "Cost spike approval, cheaper-model switching, budget reservation and rebalancing.",
        "decision_points": ["cost spike approval", "model switching for cost", "continuous rebalancing", "budget reservation"],
        "default_level": "L2",
        "operator_range": "L1-L4",
        "risk_profile": "high",
    },
    {
        "id": "model_selection",
        "code": "DIM-4",
        "name": "Model Selection",
        "regulates": "Model choice per role, task, fallback and local/API preference.",
        "decision_points": ["preferred model per role", "fallback depth", "model upgrades", "local vs API"],
        "default_level": "L2",
        "operator_range": "L2-L3",
        "risk_profile": "medium",
    },
    {
        "id": "environment_selection",
        "code": "DIM-5",
        "name": "Environment Selection",
        "regulates": "Where code is built, tested and deployed.",
        "decision_points": ["auto-route environment", "parallel environments", "mid-build switching", "sovereign routing"],
        "default_level": "L2",
        "operator_range": "L1-L2",
        "risk_profile": "high",
    },
    {
        "id": "skill_creation",
        "code": "DIM-6",
        "name": "Skill Creation",
        "regulates": "Automatic creation, modification, deletion and sharing of skills.",
        "decision_points": ["auto-create skills", "modify skills", "delete unused skills", "cross-project sharing"],
        "default_level": "L2",
        "operator_range": "L3-L5",
        "risk_profile": "medium",
    },
    {
        "id": "quality_verdicts",
        "code": "DIM-7",
        "name": "Quality Verdicts",
        "regulates": "When test and quality results are accepted automatically.",
        "decision_points": ["coverage threshold", "failed tests", "security findings", "visual/accessibility checks"],
        "default_level": "L2",
        "operator_range": "L0-L2",
        "risk_profile": "high",
    },
    {
        "id": "deploy_authorization",
        "code": "DIM-8",
        "name": "Deploy Authorization",
        "regulates": "Authorization for dev, staging, production, rollback and canary deploys.",
        "decision_points": ["dev/staging deploy", "production deploy", "rollback authorization", "canary rollout"],
        "default_level": "L1",
        "operator_range": "L0-L2",
        "risk_profile": "critical",
    },
    {
        "id": "mid_flight_overrides",
        "code": "DIM-9",
        "name": "Mid-flight Overrides",
        "regulates": "What an operator can change while a build or council run is already active.",
        "decision_points": ["pause/resume", "cancel phase", "council modification", "model switching"],
        "default_level": "L2",
        "operator_range": "preset adaptive",
        "risk_profile": "medium",
    },
    {
        "id": "cascade_re_evaluation",
        "code": "DIM-10",
        "name": "Cascade Re-evaluation",
        "regulates": "Automatic replanning after failures, incidents, provider outages and cost overruns.",
        "decision_points": ["test failure replanning", "cost overrun scope cut", "provider failover", "security mitigation"],
        "default_level": "L2",
        "operator_range": "L1-L3",
        "risk_profile": "high",
    },
]

DIMENSION_IDS = {item["id"] for item in AUTONOMY_DIMENSIONS}
LEVEL_IDS = {item["id"] for item in LEVELS}


def _levels(level: str) -> dict[str, str]:
    return {item["id"]: level for item in AUTONOMY_DIMENSIONS}


PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "name": "Conservative",
        "description": "Everything important stays manual; best for learning and high-stakes work.",
        "dimensions": _levels("L0"),
    },
    "balanced": {
        "name": "Balanced",
        "description": "Routine work is automatic; risky work is operator-gated.",
        "dimensions": _levels("L2"),
    },
    "aggressive": {
        "name": "Aggressive",
        "description": "High throughput with sampling and audit review.",
        "dimensions": {**_levels("L4"), "cost_decisions": "L5"},
    },
    "research": {
        "name": "Research",
        "description": "Fast experimentation with quality kept visible.",
        "dimensions": {**_levels("L4"), "cost_decisions": "L5", "model_selection": "L5", "quality_verdicts": "L1", "deploy_authorization": "L0", "mid_flight_overrides": "L0"},
    },
    "production": {
        "name": "Production",
        "description": "Production-safe default: deploy/manual gates stay strict.",
        "dimensions": {**_levels("L2"), "cost_decisions": "L1", "deploy_authorization": "L0", "mid_flight_overrides": "L1", "cascade_re_evaluation": "L0"},
    },
}

GOAL_PRESET_MAPPING: dict[str, str] = {
    "apps_internal": "balanced",
    "public_products": "production",
    "cybersecurity": "conservative",
    "research": "research",
    "mixed": "balanced",
}

WIZARD_MODES: list[dict[str, Any]] = [
    {"id": "quick", "label": "Quick", "duration": "5 min", "description": "Accept the Phase 4 preset and baseline gates."},
    {"id": "sliders", "label": "Sliders", "duration": "15-30 min", "description": "10 levels on one screen with risk preview."},
    {"id": "wizard", "label": "Wizard", "duration": "30-60 min", "description": "Dimension-by-dimension explanations and choices."},
    {"id": "matrix", "label": "Matrix", "duration": "advanced", "description": "Compare all presets and override selected dimensions."},
    {"id": "hard_gates_focus", "label": "Hard gates focus", "duration": "10-20 min", "description": "Review and extend only irreversible-action gates."},
]

WIZARD_STEPS: list[dict[str, Any]] = [
    {"step": 1, "id": "mode", "label": "Mode selection"},
    {"step": 2, "id": "levels", "label": "L0-L5 semantics"},
    {"step": 3, "id": "dimensions", "label": "10 autonomy dimensions"},
    {"step": 4, "id": "deep_config", "label": "Per-dimension deep config"},
    {"step": 5, "id": "d_level_adaptive", "label": "Per-D-level adaptive levels"},
    {"step": 6, "id": "hard_gates", "label": "18 baseline hard gates"},
    {"step": 7, "id": "custom_gates", "label": "Custom hard gates"},
    {"step": 8, "id": "overrides", "label": "Time-bounded overrides"},
    {"step": 9, "id": "inheritance", "label": "Inheritance map"},
    {"step": 10, "id": "acceptance", "label": "Acceptance test"},
]

QUALITY_THRESHOLD_DEFAULTS: dict[str, Any] = {
    "coverage_min_pct": 80,
    "max_l1_l2_failed": 4,
    "security_p0_p1": 0,
    "visual_regression_max_pct": 5,
    "accessibility_required": True,
    "human_like_ui_required": True,
    "lint_errors": 0,
    "d_level_overrides": {"D1": "L4", "D2": "L3", "D3": "L2", "D4": "L1", "D5": "L0"},
}

COST_DECISION_DEFAULTS: dict[str, Any] = {
    "auto_approve_under_usd": 1,
    "operator_required_from_usd": 5,
    "budget_switch_threshold_pct": 70,
    "continuous_rebalancing": True,
    "reservation_buffer_pct": 10,
    "requires_budget_cap": True,
}

MID_FLIGHT_PERMISSIONS: dict[str, list[str]] = {
    "conservative": ["pause_resume", "cancel_phase", "modify_council", "skip_phase", "edit_book", "change_masterplan", "switch_models", "edit_artifact", "modify_autonomy"],
    "balanced": ["pause_resume", "cancel_phase", "modify_council_next_session", "skip_phase", "switch_models_next_call", "modify_autonomy_next_phase"],
    "aggressive": ["pause_resume", "cancel_project"],
    "production": ["emergency_pause", "emergency_cancel", "trigger_dr", "edit_hard_gate_timeout"],
    "research": ["pause_resume", "cancel_phase", "modify_council", "skip_phase", "edit_book", "change_masterplan", "switch_models", "experimental_prompt_injection", "model_swap_mid_call"],
}

BASELINE_HARD_GATES: list[dict[str, Any]] = [
    {"id": "deploy_production", "category": "production_deploy", "label": "Deploy to production environment", "default_condition": "enabled for D3+", "dimension_lock": "deploy_authorization"},
    {"id": "force_deploy_failed_tests", "category": "production_deploy", "label": "Force-deploy with failed tests", "default_condition": "enabled always", "dimension_lock": "deploy_authorization"},
    {"id": "rollback_production", "category": "production_deploy", "label": "Rollback to previous production version", "default_condition": "enabled always", "dimension_lock": "deploy_authorization"},
    {"id": "dns_cutover", "category": "production_deploy", "label": "DNS cutover / live traffic switch", "default_condition": "enabled always", "dimension_lock": "deploy_authorization"},
    {"id": "payment_live_mode", "category": "payment_financial", "label": "Payment integration trigger in live mode", "default_condition": "enabled always", "dimension_lock": "cost_decisions"},
    {"id": "customer_charge_refund", "category": "payment_financial", "label": "Customer credit charge or refund", "default_condition": "enabled always", "dimension_lock": "cost_decisions"},
    {"id": "gdpr_delete", "category": "data_privacy", "label": "GDPR data delete request", "default_condition": "enabled always", "dimension_lock": "cascade_re_evaluation"},
    {"id": "customer_data_export", "category": "data_privacy", "label": "Customer data export / GDPR Art. 15", "default_condition": "enabled always", "dimension_lock": "cascade_re_evaluation"},
    {"id": "production_backup_restore", "category": "data_privacy", "label": "Production data backup restore", "default_condition": "enabled always", "dimension_lock": "environment_selection"},
    {"id": "security_incident_response", "category": "security", "label": "Security incident response action", "default_condition": "enabled always", "dimension_lock": "cascade_re_evaluation"},
    {"id": "master_password_change", "category": "security", "label": "Master password change", "default_condition": "enabled always", "dimension_lock": "deploy_authorization"},
    {"id": "provider_key_rotation", "category": "security", "label": "Provider key rotation", "default_condition": "enabled for critical providers", "dimension_lock": "model_selection"},
    {"id": "classified_data_movement", "category": "classified_compliance", "label": "Classified data movement / TLP:RED+", "default_condition": "enabled if any TLP:RED project", "dimension_lock": "environment_selection"},
    {"id": "d5_council_finalization", "category": "classified_compliance", "label": "Council finalization for D5 projects", "default_condition": "enabled for D5", "dimension_lock": "council_voting_threshold"},
    {"id": "customer_onboarding", "category": "classified_compliance", "label": "Customer onboarding / first customer deploy", "default_condition": "enabled always", "dimension_lock": "deploy_authorization"},
    {"id": "schema_breaking_migration", "category": "workspace_management", "label": "Schema-breaking DB migration", "default_condition": "enabled always", "dimension_lock": "deploy_authorization"},
    {"id": "api_breaking_change", "category": "workspace_management", "label": "API breaking change publish", "default_condition": "enabled always", "dimension_lock": "deploy_authorization"},
    {"id": "workspace_export_with_secrets", "category": "workspace_management", "label": "Workspace export with secrets", "default_condition": "enabled always", "dimension_lock": "cascade_re_evaluation"},
]

CUSTOM_GATE_EXAMPLES: list[dict[str, str]] = [
    {"label": "Email to more than 100 customers", "condition": "email_recipients > 100"},
    {"label": "Auto-scale above N instances", "condition": "instances > threshold"},
    {"label": "Cost spike in one hour", "condition": "cost_spike_1h > configured_usd"},
    {"label": "High-value new customer signup", "condition": "initial_value_eur > 10000"},
    {"label": "Deploy to a named customer environment", "condition": "environment.customer_id in restricted_customers"},
]

OVERRIDE_SCOPES: list[dict[str, str]] = [
    {"id": "per_decision", "duration": "single decision", "applies_to": "current decision"},
    {"id": "per_round", "duration": "council round", "applies_to": "all decisions in this round"},
    {"id": "per_phase", "duration": "phase execution", "applies_to": "all decisions in this phase"},
    {"id": "per_build", "duration": "build cycle", "applies_to": "all decisions in this build"},
    {"id": "per_project", "duration": "until project closed", "applies_to": "all decisions in this project"},
    {"id": "per_workspace", "duration": "permanent until operator changes", "applies_to": "all projects"},
]

EDGE_CASES: list[dict[str, Any]] = [
    {"id": "EC-A1", "category": "inheritance_override", "title": "Override vs hard gate conflict", "severity": "high", "runbook": ["keep hard gate locked", "explain effective L0", "offer non-production override"]},
    {"id": "EC-A2", "category": "inheritance_override", "title": "Multi-level override conflict", "severity": "medium", "runbook": ["show all scopes", "use closest active scope", "record winning override"]},
    {"id": "EC-A3", "category": "inheritance_override", "title": "Operator override expired mid-build", "severity": "medium", "runbook": ["pause if risky", "ask extend or revert", "log expiry decision"]},
    {"id": "EC-A4", "category": "inheritance_override", "title": "Goal-driven preset conflict", "severity": "medium", "runbook": ["show phase 4 mapping", "allow phase 5 dimension override", "audit reason"]},
    {"id": "EC-A5", "category": "inheritance_override", "title": "Inheritance broken by partial restore", "severity": "critical", "runbook": ["re-establish overrides", "reset invalid references", "rerun acceptance"]},
    {"id": "EC-B1", "category": "hard_gate", "title": "Hard gate timeout during operator absence", "severity": "high", "runbook": ["retry channels", "keep pipeline paused", "offer rollback or alternate contact"]},
    {"id": "EC-B2", "category": "hard_gate", "title": "Hard gate approval with mobile auth failure", "severity": "high", "runbook": ["lock mobile temporarily", "offer desktop approval", "allow recovery seed path"]},
    {"id": "EC-B3", "category": "hard_gate", "title": "Hard gate approval race mobile plus desktop", "severity": "medium", "runbook": ["first timestamp wins", "record concurrent attempt", "deduplicate state"]},
    {"id": "EC-B4", "category": "hard_gate", "title": "Custom hard gate triggers too often", "severity": "medium", "runbook": ["analyze frequency", "raise threshold", "whitelist recurring workflow"]},
    {"id": "EC-B5", "category": "hard_gate", "title": "Hard gate disabled accidentally", "severity": "critical", "runbook": ["re-enable gate", "audit recent deploys", "require explicit reason"]},
    {"id": "EC-C1", "category": "dimension_config", "title": "Cost autonomy without budget caps", "severity": "critical", "runbook": ["pause autonomous projects", "apply emergency cap", "disable DIM-3 L5 without cap"]},
    {"id": "EC-C2", "category": "dimension_config", "title": "Quality threshold too restrictive", "severity": "low", "runbook": ["show approval history", "suggest relaxed threshold", "estimate saved operator time"]},
    {"id": "EC-C3", "category": "dimension_config", "title": "Mid-flight override complexity", "severity": "medium", "runbook": ["limit to L2", "add confirmation prompts", "block unsafe edit windows"]},
    {"id": "EC-C4", "category": "dimension_config", "title": "Cross-dimension dependency conflict", "severity": "medium", "runbook": ["align DIM-3 and DIM-4", "show effective slowdown", "offer paired levels"]},
    {"id": "EC-C5", "category": "dimension_config", "title": "Per-D-level adaptive levels confusing", "severity": "low", "runbook": ["show effective D-level", "explain selected row", "allow project override"]},
    {"id": "EC-D1", "category": "wizard_setup", "title": "Wizard mostly skipped", "severity": "low", "runbook": ["continue wizard", "switch to sliders", "accept preset explicitly"]},
    {"id": "EC-D2", "category": "wizard_setup", "title": "Operator misunderstands L4 vs L5", "severity": "high", "runbook": ["explain L5 means no routine intervention", "compare project interaction history", "suggest L2-L3"]},
    {"id": "EC-D3", "category": "wizard_setup", "title": "Advisor missing industry context", "severity": "medium", "runbook": ["show industry-specific manual notes", "add custom compliance gate", "request template review"]},
    {"id": "EC-D4", "category": "wizard_setup", "title": "Sliders mode disorienting", "severity": "low", "runbook": ["switch to wizard", "switch to matrix", "save partial progress"]},
    {"id": "EC-E1", "category": "recovery_migration", "title": "Workspace import autonomy mismatch", "severity": "high", "runbook": ["auto-migrate where possible", "manual review incompatible settings", "rerun acceptance"]},
    {"id": "EC-E2", "category": "recovery_migration", "title": "Backup restore breaks active overrides", "severity": "high", "runbook": ["recalculate per-project overrides", "reset stale references", "manual review affected projects"]},
    {"id": "EC-E3", "category": "recovery_migration", "title": "Custom hard gate condition lost after update", "severity": "high", "runbook": ["map old function to replacement", "disable temporarily if unsafe", "use nearest built-in gate"]},
]

COLOR_LEGEND: list[dict[str, str]] = [
    {"id": "phase4_default", "label": "Phase 4 default", "color": "blue"},
    {"id": "phase5_override", "label": "Phase 5 override", "color": "green"},
    {"id": "project_override", "label": "Project override", "color": "amber"},
    {"id": "round_override", "label": "Round override", "color": "orange"},
    {"id": "decision_override", "label": "Real-time decision override", "color": "red"},
    {"id": "hard_gate", "label": "Hard gate locked L0", "color": "black"},
]


class ApplyPresetRequest(BaseModel):
    goal: str = "apps_internal"
    preset: str | None = None
    mode: str = "quick"
    accept_phase4_preset: bool = True


class WizardModeRequest(BaseModel):
    mode: str


class WizardStepRequest(BaseModel):
    step: int = Field(..., ge=1, le=10)
    skipped: bool = False
    values: dict[str, Any] = Field(default_factory=dict)


class DimensionConfigRequest(BaseModel):
    dimension_id: str
    level: str
    settings: dict[str, Any] = Field(default_factory=dict)
    d_level_adaptive: dict[str, str] | None = None
    reason: str = ""


class DLevelOverridesRequest(BaseModel):
    dimension_id: str
    overrides: dict[str, str]
    enabled: bool = True


class HardGateReviewRequest(BaseModel):
    reviewed_gate_ids: list[str] = Field(default_factory=list)
    accepted_baseline: bool = True
    no_custom_needed: bool = True


class CustomHardGateRequest(BaseModel):
    label: str
    condition: str
    category: str = "operator_custom"
    dimension_lock: str | None = None
    timeout_minutes: int = 60
    enabled: bool = True


class ToggleHardGateRequest(BaseModel):
    enabled: bool
    reason: str = ""


class OverrideRequest(BaseModel):
    dimension_id: str
    level: str
    scope: str = "per_decision"
    reason: str = ""
    project_id: str | None = None
    expires_in_hours: int | None = None


class InheritanceTraceRequest(BaseModel):
    dimension_id: str = "cost_decisions"
    goal: str = "apps_internal"
    d_level: str = "D3"
    project_id: str = "operator_project"
    round_id: str | None = None
    decision_id: str | None = None


class EdgeDiagnosisRequest(BaseModel):
    case_id: str
    context: dict[str, Any] = Field(default_factory=dict)


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _db_path() -> Path:
    return Path(os.environ.get("SYLION_DB_PATH", "sylion_aeis.db"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sylion_phase_state (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    return conn


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _get_state(key: str) -> Any:
    with _connect() as conn:
        row = conn.execute("SELECT value_json FROM sylion_phase_state WHERE key = ?", (f"phase5:{key}",)).fetchone()
    return _json_loads(row["value_json"], None) if row else None


def _set_state(key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sylion_phase_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (f"phase5:{key}", json.dumps(value, ensure_ascii=False, sort_keys=True, default=str), time.time()),
        )


def _state_list(key: str) -> list[dict[str, Any]]:
    value = _get_state(key)
    return value if isinstance(value, list) else []


def _append_state_list(key: str, value: dict[str, Any]) -> None:
    items = _state_list(key)
    items.append(value)
    _set_state(key, items)


def _append_audit(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    chain = _state_list("audit_chain")
    previous_hash = str(chain[-1].get("hash") or "") if chain else ""
    entry = {
        "event_id": _uid("audit"),
        "event": event,
        "payload": payload,
        "created_at": time.time(),
        "previous_hash": previous_hash,
    }
    canonical = json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str)
    entry["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _append_state_list("audit_chain", entry)
    return entry


def _baseline_gates() -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    for gate in BASELINE_HARD_GATES:
        gates.append(
            {
                **_clone(gate),
                "source": "baseline",
                "enabled": True,
                "requires_explicit_click": True,
                "mobile_allowed": True,
                "desktop_allowed": True,
                "timeout_minutes": 60 if gate["category"] != "security" else 5,
                "fallback": "pause_notify_all" if gate["category"] in {"production_deploy", "security"} else "pause_until_operator",
            }
        )
    return gates


def _dimension_defaults(preset: str) -> dict[str, dict[str, Any]]:
    preset_dimensions = PRESETS[preset]["dimensions"]
    dimensions: dict[str, dict[str, Any]] = {}
    for dim in AUTONOMY_DIMENSIONS:
        dim_id = dim["id"]
        level = preset_dimensions.get(dim_id, dim["default_level"])
        settings: dict[str, Any] = {}
        if dim_id == "cost_decisions":
            settings = _clone(COST_DECISION_DEFAULTS)
        elif dim_id == "quality_verdicts":
            settings = _clone(QUALITY_THRESHOLD_DEFAULTS)
        elif dim_id == "mid_flight_overrides":
            settings = {"permissions_by_preset": _clone(MID_FLIGHT_PERMISSIONS), "active_permissions": MID_FLIGHT_PERMISSIONS.get(preset, [])}
        dimensions[dim_id] = {
            "level": level,
            "source": "phase4_preset",
            "inherited_from": preset,
            "settings": settings,
            "d_level_adaptive": _clone(QUALITY_THRESHOLD_DEFAULTS["d_level_overrides"]) if dim_id == "quality_verdicts" else {},
            "customized": False,
        }
    return dimensions


def _default_settings(goal: str = "apps_internal", preset: str | None = None) -> dict[str, Any]:
    selected_preset = preset or GOAL_PRESET_MAPPING.get(goal, "balanced")
    return {
        "version": "phase5.v1",
        "goal": goal,
        "selected_preset": selected_preset,
        "accepted_phase4_preset": False,
        "customization_skipped": False,
        "operator_understood_dimensions": False,
        "operator_understood_levels": False,
        "hard_gates_reviewed": False,
        "no_custom_hard_gate_needed": False,
        "inheritance_tested": False,
        "created_at": time.time(),
        "updated_at": time.time(),
        "wizard": {
            "mode": "quick",
            "current_step": 1,
            "completed_steps": [],
            "skipped_steps": [],
            "step_values": {},
            "started_at": time.time(),
            "mode_started_at": time.time(),
        },
        "dimensions": _dimension_defaults(selected_preset),
        "hard_gates": _baseline_gates(),
        "custom_hard_gates": [],
        "overrides": [],
        "inheritance_traces": [],
        "risk_preview": _risk_preview(_dimension_defaults(selected_preset)),
    }


def _settings(goal: str = "apps_internal") -> dict[str, Any]:
    existing = _get_state("settings")
    if isinstance(existing, dict):
        return existing
    settings = _default_settings(goal=goal)
    _set_state("settings", settings)
    return settings


def _save_settings(settings: dict[str, Any], event: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings["updated_at"] = time.time()
    settings["risk_preview"] = _risk_preview(settings.get("dimensions") or {})
    _set_state("settings", settings)
    _append_audit(event, payload)
    return settings


def _level_num(level: str) -> int:
    if isinstance(level, str) and level.startswith("L") and level[1:].isdigit():
        return int(level[1:])
    return 0


def _risk_preview(dimensions: dict[str, Any]) -> dict[str, Any]:
    nums = [_level_num((cfg or {}).get("level", "L0")) for cfg in dimensions.values()]
    if not nums:
        return {"average_level": 0, "speed_multiplier": 1.0, "risk_multiplier": 1.0, "cost_variance_pct": 0}
    level_lookup = {item["id"]: item for item in LEVELS}
    avg = sum(nums) / len(nums)
    speed = sum(level_lookup[f"L{num}"]["speed_multiplier"] for num in nums) / len(nums)
    risk = sum(level_lookup[f"L{num}"]["risk_multiplier"] for num in nums) / len(nums)
    cost = sum(level_lookup[f"L{num}"]["cost_variance_pct"] for num in nums) / len(nums)
    return {
        "average_level": round(avg, 2),
        "speed_multiplier": round(speed, 2),
        "risk_multiplier": round(risk, 2),
        "cost_variance_pct": round(cost, 1),
        "all_same_level": len(set(nums)) == 1,
        "l5_count": len([num for num in nums if num == 5]),
        "manual_count": len([num for num in nums if num <= 1]),
    }


def _active_gates(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [gate for gate in (settings.get("hard_gates") or []) + (settings.get("custom_hard_gates") or []) if gate.get("enabled")]


def _find_gate(settings: dict[str, Any], gate_id: str) -> tuple[str, int, dict[str, Any]] | None:
    for collection_name in ("hard_gates", "custom_hard_gates"):
        for idx, gate in enumerate(settings.get(collection_name) or []):
            if gate.get("id") == gate_id:
                return collection_name, idx, gate
    return None


def _has_active_gate(settings: dict[str, Any], gate_id: str) -> bool:
    match = _find_gate(settings, gate_id)
    return bool(match and match[2].get("enabled"))


def _check_conflicts(settings: dict[str, Any]) -> list[dict[str, Any]]:
    dimensions = settings.get("dimensions") or {}
    conflicts: list[dict[str, Any]] = []
    if dimensions.get("deploy_authorization", {}).get("level") == "L5" and not _has_active_gate(settings, "deploy_production"):
        conflicts.append({"id": "deploy_l5_without_gate", "severity": "hard", "message": "DIM-8 Deploy at L5 requires production deploy hard gate."})
    if dimensions.get("cost_decisions", {}).get("level") == "L0" and dimensions.get("model_selection", {}).get("level") == "L5":
        conflicts.append({"id": "cost_manual_model_l5", "severity": "soft", "message": "DIM-4 L5 will be slowed by DIM-3 L0 per-call approval."})
    if any(override.get("scope_parent") == override.get("id") for override in settings.get("overrides") or []):
        conflicts.append({"id": "circular_override", "severity": "hard", "message": "Circular override dependency detected."})
    return conflicts


def _dimension_level(settings: dict[str, Any], dim_id: str) -> str:
    return str((settings.get("dimensions") or {}).get(dim_id, {}).get("level") or "L0")


def _build_inheritance_trace(settings: dict[str, Any], body: InheritanceTraceRequest) -> dict[str, Any]:
    if body.dimension_id not in DIMENSION_IDS:
        raise HTTPException(status_code=400, detail="unsupported dimension")
    preset = settings.get("selected_preset") or GOAL_PRESET_MAPPING.get(body.goal, "balanced")
    phase4_level = PRESETS.get(preset, PRESETS["balanced"])["dimensions"].get(body.dimension_id, "L2")
    phase5_level = _dimension_level(settings, body.dimension_id)
    matching_overrides = [
        item for item in settings.get("overrides", [])
        if item.get("dimension_id") == body.dimension_id and item.get("status") == "active"
    ]
    scope_priority = {"per_workspace": 1, "per_project": 2, "per_build": 3, "per_phase": 4, "per_round": 5, "per_decision": 6}
    winning = sorted(matching_overrides, key=lambda item: scope_priority.get(str(item.get("scope")), 0), reverse=True)
    hard_gate_lock = body.dimension_id == "deploy_authorization" and _has_active_gate(settings, "deploy_production")
    effective_level = "L0" if hard_gate_lock and body.d_level in {"D3", "D4", "D5"} else (winning[0]["level"] if winning else phase5_level)
    trace = [
        {"scope": "phase4_default", "level": phase4_level, "source": preset, "color": "blue"},
        {"scope": "phase5_workspace", "level": phase5_level, "source": "operator_config", "color": "green"},
    ]
    for item in winning:
        trace.append({"scope": item.get("scope"), "level": item.get("level"), "source": item.get("reason") or "operator_override", "color": "amber"})
    if hard_gate_lock and body.d_level in {"D3", "D4", "D5"}:
        trace.append({"scope": "hard_gate", "level": "L0", "source": "deploy_production", "color": "black"})
    result = {
        "dimension_id": body.dimension_id,
        "goal": body.goal,
        "project_id": body.project_id,
        "d_level": body.d_level,
        "effective_level": effective_level,
        "hard_gate_locked": hard_gate_lock and body.d_level in {"D3", "D4", "D5"},
        "trace": trace,
        "legend": COLOR_LEGEND,
        "created_at": time.time(),
    }
    return result


def _goal_checks(goal: str, settings: dict[str, Any]) -> list[dict[str, Any]]:
    dims = settings.get("dimensions") or {}
    checks: list[dict[str, Any]] = []

    def add(check_id: str, label: str, ok: bool, evidence: str, hard: bool = True) -> None:
        checks.append({"id": check_id, "label": label, "status": "pass" if ok else ("fail" if hard else "warn"), "evidence": evidence, "hard": hard})

    if goal == "public_products":
        add("public_prod_gate", "Production deploy hard gate active", _has_active_gate(settings, "deploy_production"), "deploy_production")
        add("public_quality_notify", "Quality verdicts are L2 or stricter", _level_num(_dimension_level(settings, "quality_verdicts")) <= 2, _dimension_level(settings, "quality_verdicts"))
    elif goal == "cybersecurity":
        manualish = len([cfg for cfg in dims.values() if _level_num(cfg.get("level", "L0")) <= 1])
        add("cyber_manual_majority", "Most dimensions are L0-L1", manualish >= 6, f"{manualish}/10")
        add("cyber_security_gate", "Security incident hard gate active", _has_active_gate(settings, "security_incident_response"), "security_incident_response")
        add("cyber_extra_audit", "Audit chain extra strict", True, "hash chained")
    elif goal == "research":
        autonomous = len([cfg for cfg in dims.values() if _level_num(cfg.get("level", "L0")) >= 3])
        add("research_autonomous_majority", "Most dimensions are L3-L5", autonomous >= 6, f"{autonomous}/10")
        add("research_cost_fast", "Cost decisions are L4-L5", _level_num(_dimension_level(settings, "cost_decisions")) >= 4, _dimension_level(settings, "cost_decisions"))
        add("research_quality_visible", "Quality verdicts remain visible", _level_num(_dimension_level(settings, "quality_verdicts")) <= 2, _dimension_level(settings, "quality_verdicts"))
    else:
        add("apps_standard_preset", "Standard internal-app preset acceptable", settings.get("selected_preset") in {"balanced", "production", "conservative"}, str(settings.get("selected_preset")))
    return checks


def _build_acceptance(settings: dict[str, Any], goal: str = "apps_internal", finalize: bool = False) -> dict[str, Any]:
    audit = _state_list("audit_chain")
    audit_complete = any(item.get("event") == "phase_5.complete" for item in audit)
    dimensions = settings.get("dimensions") or {}
    hard_gates = settings.get("hard_gates") or []
    custom_gates = settings.get("custom_hard_gates") or []
    active_gates = _active_gates(settings)
    conflicts = _check_conflicts(settings)
    checks: list[dict[str, Any]] = []

    def add(check_id: str, label: str, ok: bool, evidence: str, hard: bool = True) -> None:
        checks.append({"id": check_id, "label": label, "status": "pass" if ok else ("fail" if hard else "warn"), "evidence": evidence, "hard": hard})

    add("dimensions_configured", "10 autonomy dimensions configured", len(dimensions) == 10 and set(dimensions) >= DIMENSION_IDS, f"{len(dimensions)}/10")
    add("levels_understood", "L0-L5 semantics verified", bool(settings.get("operator_understood_levels")), str(bool(settings.get("operator_understood_levels"))))
    add("dimensions_understood", "10 dimensions explanation reviewed", bool(settings.get("operator_understood_dimensions")), str(bool(settings.get("operator_understood_dimensions"))))
    add("hard_gates_reviewed", "Hard gates baseline reviewed", bool(settings.get("hard_gates_reviewed")) and len(hard_gates) >= 18, f"{len([g for g in hard_gates if g.get('enabled')])}/18 active")
    add("phase_5_complete_audit", "Audit chain entry phase_5.complete", audit_complete or finalize, "recorded" if audit_complete or finalize else "missing")
    add("preset_or_customized", "Preset accepted or per-dimension levels customized", bool(settings.get("accepted_phase4_preset")) or any(cfg.get("customized") for cfg in dimensions.values()), str(settings.get("selected_preset")))
    add("custom_gate_decision", "Custom hard gates added or explicitly not needed", bool(custom_gates) or bool(settings.get("no_custom_hard_gate_needed")), f"{len(custom_gates)} custom")
    add("inheritance_trace_tested", "Inheritance behavior tested", bool(settings.get("inheritance_tested")), f"{len(settings.get('inheritance_traces') or [])} traces")

    for goal_check in _goal_checks(goal, settings):
        checks.append(goal_check)

    all_l5 = dimensions and all(cfg.get("level") == "L5" for cfg in dimensions.values())
    add("not_all_l5_without_gates", "Not all dimensions are L5 without hard gates", not (all_l5 and not active_gates), f"l5={all_l5}, active_gates={len(active_gates)}")
    add("no_hard_conflicts", "No hard autonomy conflicts", not any(item["severity"] == "hard" for item in conflicts), json.dumps(conflicts, default=str))

    cost_cfg = dimensions.get("cost_decisions", {})
    cost_settings = cost_cfg.get("settings") or {}
    if _level_num(cost_cfg.get("level", "L0")) >= 4 and not cost_settings.get("requires_budget_cap", True):
        add("cost_l4_l5_budget_cap", "Cost L4-L5 has budget cap", False, "budget cap disabled", hard=False)
    if (settings.get("risk_preview") or {}).get("all_same_level"):
        add("dimension_variation", "Dimensions are not all the same level", False, "all dimensions same level", hard=False)
    if not any((cfg.get("d_level_adaptive") or {}) for cfg in dimensions.values()):
        add("d_level_adaptive", "At least one dimension uses per-D-level adaptive levels", False, "none", hard=False)
    if goal in {"cybersecurity", "public_products"} and not custom_gates:
        add("industry_custom_gate", "Industry-specific custom hard gate considered", bool(settings.get("no_custom_hard_gate_needed")), "no custom gates", hard=False)
    if settings.get("wizard", {}).get("mode") == "sliders":
        elapsed_min = (time.time() - float(settings.get("wizard", {}).get("mode_started_at") or time.time())) / 60
        if elapsed_min > 30:
            add("sliders_time", "Sliders mode under 30 minutes", False, f"{elapsed_min:.1f} min", hard=False)

    hard_blocks = [check for check in checks if check["status"] == "fail" and check.get("hard")]
    soft_warnings = [check for check in checks if check["status"] == "warn"]
    if finalize and not hard_blocks and not audit_complete:
        entry = _append_audit("phase_5.complete", {"goal": goal, "preset": settings.get("selected_preset"), "hard_gates": len(active_gates), "soft_warnings": len(soft_warnings)})
        for check in checks:
            if check["id"] == "phase_5_complete_audit":
                check["status"] = "pass"
                check["evidence"] = entry["event_id"]
        audit_complete = True

    return {
        "phase": "5",
        "goal": goal,
        "accepted": len(hard_blocks) == 0,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "dod": {
            "common": {"required": 5, "passed": len([check for check in checks[:5] if check["status"] == "pass"])},
            "customization": {"required": 3, "passed": len([check for check in checks[5:8] if check["status"] == "pass"])},
            "counts": {
                "checks_passed": len([check for check in checks if check["status"] == "pass"]),
                "checks_total": len(checks),
                "hard_blocks": len(hard_blocks),
                "soft_warnings": len(soft_warnings),
            },
        },
        "audit_chain": {"entries": len(_state_list("audit_chain")), "phase_5_complete": audit_complete, "last_hash": (_state_list("audit_chain")[-1].get("hash") if _state_list("audit_chain") else "")},
    }


def _snapshot(goal: str = "apps_internal") -> dict[str, Any]:
    settings = _settings(goal=goal)
    return {
        "phase": "5",
        "status": "active",
        "settings": settings,
        "templates": {
            "dimensions": AUTONOMY_DIMENSIONS,
            "levels": LEVELS,
            "presets": PRESETS,
            "goal_mapping": GOAL_PRESET_MAPPING,
            "wizard_modes": WIZARD_MODES,
            "wizard_steps": WIZARD_STEPS,
            "hard_gates": BASELINE_HARD_GATES,
            "custom_gate_examples": CUSTOM_GATE_EXAMPLES,
            "override_scopes": OVERRIDE_SCOPES,
            "edge_cases": EDGE_CASES,
            "color_legend": COLOR_LEGEND,
            "quality_threshold_defaults": QUALITY_THRESHOLD_DEFAULTS,
            "cost_decision_defaults": COST_DECISION_DEFAULTS,
            "mid_flight_permissions": MID_FLIGHT_PERMISSIONS,
        },
        "conflicts": _check_conflicts(settings),
        "acceptance": _build_acceptance(settings, goal=goal, finalize=False),
    }


@router.get("")
def get_autonomy_configuration(goal: str = "apps_internal") -> dict[str, Any]:
    return _snapshot(goal=goal)


@router.get("/templates")
def get_autonomy_configuration_templates() -> dict[str, Any]:
    return _snapshot()["templates"]


@router.post("/apply-preset")
def apply_phase4_preset(body: ApplyPresetRequest) -> dict[str, Any]:
    preset = body.preset or GOAL_PRESET_MAPPING.get(body.goal, "balanced")
    if preset not in PRESETS:
        raise HTTPException(status_code=400, detail="unsupported preset")
    if body.mode not in {mode["id"] for mode in WIZARD_MODES}:
        raise HTTPException(status_code=400, detail="unsupported wizard mode")
    settings = _default_settings(goal=body.goal, preset=preset)
    settings["accepted_phase4_preset"] = body.accept_phase4_preset
    settings["customization_skipped"] = body.mode == "quick"
    settings["operator_understood_dimensions"] = True
    settings["operator_understood_levels"] = True
    settings["hard_gates_reviewed"] = True
    settings["no_custom_hard_gate_needed"] = True
    settings["wizard"]["mode"] = body.mode
    settings["wizard"]["completed_steps"] = [1, 2, 3, 6, 9]
    settings["wizard"]["current_step"] = 10
    trace = _build_inheritance_trace(settings, InheritanceTraceRequest(goal=body.goal, dimension_id="deploy_authorization", d_level="D3"))
    settings["inheritance_traces"] = [trace]
    settings["inheritance_tested"] = True
    _set_state("settings", settings)
    _append_audit("phase5.preset_applied", {"goal": body.goal, "preset": preset, "mode": body.mode})
    return _snapshot(goal=body.goal)


@router.post("/wizard/mode")
def set_wizard_mode(body: WizardModeRequest) -> dict[str, Any]:
    if body.mode not in {mode["id"] for mode in WIZARD_MODES}:
        raise HTTPException(status_code=400, detail="unsupported wizard mode")
    settings = _settings()
    wizard = dict(settings.get("wizard") or {})
    wizard["mode"] = body.mode
    wizard["mode_started_at"] = time.time()
    settings["wizard"] = wizard
    _save_settings(settings, "phase5.wizard_mode_set", {"mode": body.mode})
    return {"wizard": wizard, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/wizard/step")
def save_wizard_step(body: WizardStepRequest) -> dict[str, Any]:
    settings = _settings()
    wizard = dict(settings.get("wizard") or {})
    completed = set(wizard.get("completed_steps") or [])
    skipped = set(wizard.get("skipped_steps") or [])
    if body.skipped:
        skipped.add(body.step)
    else:
        completed.add(body.step)
    wizard["completed_steps"] = sorted(completed)
    wizard["skipped_steps"] = sorted(skipped)
    wizard["current_step"] = min(10, body.step + 1)
    wizard.setdefault("step_values", {})[str(body.step)] = body.values
    if body.step == 2 and not body.skipped:
        settings["operator_understood_levels"] = True
    if body.step == 3 and not body.skipped:
        settings["operator_understood_dimensions"] = True
    if body.step == 6 and not body.skipped:
        settings["hard_gates_reviewed"] = True
    settings["wizard"] = wizard
    _save_settings(settings, "phase5.wizard_step_saved", {"step": body.step, "skipped": body.skipped})
    return {"wizard": wizard, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/dimensions")
def save_dimension_config(body: DimensionConfigRequest) -> dict[str, Any]:
    if body.dimension_id not in DIMENSION_IDS:
        raise HTTPException(status_code=400, detail="unsupported dimension")
    if body.level not in LEVEL_IDS:
        raise HTTPException(status_code=400, detail="unsupported level")
    settings = _settings()
    dimensions = dict(settings.get("dimensions") or {})
    current = dict(dimensions.get(body.dimension_id) or {})
    merged_settings = dict(current.get("settings") or {})
    merged_settings.update(body.settings)
    current.update(
        {
            "level": body.level,
            "settings": merged_settings,
            "customized": True,
            "source": "phase5_operator",
            "reason": body.reason,
            "updated_at": time.time(),
        }
    )
    if body.d_level_adaptive is not None:
        invalid = [level for level in body.d_level_adaptive.values() if level not in LEVEL_IDS]
        if invalid:
            raise HTTPException(status_code=400, detail="unsupported D-level override level")
        current["d_level_adaptive"] = body.d_level_adaptive
    dimensions[body.dimension_id] = current
    settings["dimensions"] = dimensions
    _save_settings(settings, "phase5.dimension_saved", {"dimension_id": body.dimension_id, "level": body.level})
    return {"dimension": current, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/d-level-overrides")
def save_d_level_overrides(body: DLevelOverridesRequest) -> dict[str, Any]:
    if body.dimension_id not in DIMENSION_IDS:
        raise HTTPException(status_code=400, detail="unsupported dimension")
    invalid_levels = [level for level in body.overrides.values() if level not in LEVEL_IDS]
    invalid_keys = [key for key in body.overrides if key not in {"D1", "D2", "D3", "D4", "D5"}]
    if invalid_levels or invalid_keys:
        raise HTTPException(status_code=400, detail="invalid D-level overrides")
    settings = _settings()
    dimensions = dict(settings.get("dimensions") or {})
    current = dict(dimensions.get(body.dimension_id) or {})
    current["d_level_adaptive"] = body.overrides if body.enabled else {}
    current["customized"] = True
    dimensions[body.dimension_id] = current
    settings["dimensions"] = dimensions
    _save_settings(settings, "phase5.d_level_overrides_saved", {"dimension_id": body.dimension_id, "enabled": body.enabled})
    return {"dimension": current, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/hard-gates/review")
def review_hard_gates(body: HardGateReviewRequest) -> dict[str, Any]:
    settings = _settings()
    known = {gate["id"] for gate in settings.get("hard_gates") or []}
    unknown = [gate_id for gate_id in body.reviewed_gate_ids if gate_id not in known]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown gates: {', '.join(unknown)}")
    settings["hard_gates_reviewed"] = body.accepted_baseline
    settings["no_custom_hard_gate_needed"] = body.no_custom_needed
    settings["reviewed_gate_ids"] = sorted(body.reviewed_gate_ids or known)
    _save_settings(settings, "phase5.hard_gates_reviewed", {"count": len(settings["reviewed_gate_ids"]), "no_custom_needed": body.no_custom_needed})
    return {"hard_gates": settings.get("hard_gates"), "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/hard-gates/custom")
def add_custom_hard_gate(body: CustomHardGateRequest) -> dict[str, Any]:
    if body.dimension_lock and body.dimension_lock not in DIMENSION_IDS:
        raise HTTPException(status_code=400, detail="unsupported dimension lock")
    if not body.label.strip() or not body.condition.strip():
        raise HTTPException(status_code=400, detail="label and condition are required")
    settings = _settings()
    custom = list(settings.get("custom_hard_gates") or [])
    gate = {
        "id": _uid("gate"),
        "source": "operator_custom",
        "category": body.category,
        "label": body.label,
        "condition": body.condition,
        "dimension_lock": body.dimension_lock,
        "timeout_minutes": body.timeout_minutes,
        "enabled": body.enabled,
        "requires_explicit_click": True,
        "created_at": time.time(),
    }
    custom.append(gate)
    settings["custom_hard_gates"] = custom
    settings["no_custom_hard_gate_needed"] = False
    _save_settings(settings, "phase5.custom_gate_added", {"gate_id": gate["id"], "label": body.label})
    return {"gate": gate, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/hard-gates/{gate_id}/toggle")
def toggle_hard_gate(gate_id: str, body: ToggleHardGateRequest) -> dict[str, Any]:
    settings = _settings()
    match = _find_gate(settings, gate_id)
    if not match:
        raise HTTPException(status_code=404, detail="gate not found")
    collection, idx, gate = match
    if gate_id == "deploy_production" and not body.enabled:
        deploy_level = _dimension_level(settings, "deploy_authorization")
        if _level_num(deploy_level) >= 3:
            raise HTTPException(status_code=409, detail="production deploy gate cannot be disabled while DIM-8 is L3+")
    updated = dict(gate)
    updated["enabled"] = body.enabled
    updated["last_toggle_reason"] = body.reason
    updated["updated_at"] = time.time()
    settings[collection][idx] = updated
    _save_settings(settings, "phase5.hard_gate_toggled", {"gate_id": gate_id, "enabled": body.enabled, "reason": body.reason})
    return {"gate": updated, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/overrides")
def create_override(body: OverrideRequest) -> dict[str, Any]:
    if body.dimension_id not in DIMENSION_IDS:
        raise HTTPException(status_code=400, detail="unsupported dimension")
    if body.level not in LEVEL_IDS:
        raise HTTPException(status_code=400, detail="unsupported level")
    if body.scope not in {scope["id"] for scope in OVERRIDE_SCOPES}:
        raise HTTPException(status_code=400, detail="unsupported scope")
    settings = _settings()
    expires_at = time.time() + body.expires_in_hours * 3600 if body.expires_in_hours else None
    conflict = body.dimension_id == "deploy_authorization" and _level_num(body.level) >= 3 and _has_active_gate(settings, "deploy_production")
    override = {
        "id": _uid("override"),
        "dimension_id": body.dimension_id,
        "level": body.level,
        "scope": body.scope,
        "reason": body.reason,
        "project_id": body.project_id,
        "expires_at": expires_at,
        "status": "active",
        "conflict": conflict,
        "conflict_resolution": "hard_gate_wins_effective_L0" if conflict else "none",
        "created_at": time.time(),
    }
    settings.setdefault("overrides", []).append(override)
    _save_settings(settings, "phase5.override_created", {"override_id": override["id"], "dimension_id": body.dimension_id, "level": body.level, "conflict": conflict})
    return {"override": override, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/inheritance/trace")
def trace_inheritance(body: InheritanceTraceRequest) -> dict[str, Any]:
    settings = _settings(goal=body.goal)
    trace = _build_inheritance_trace(settings, body)
    settings.setdefault("inheritance_traces", []).append(trace)
    settings["inheritance_tested"] = True
    _save_settings(settings, "phase5.inheritance_trace_created", {"dimension_id": body.dimension_id, "effective_level": trace["effective_level"]})
    return trace


@router.get("/edge-cases")
def list_edge_cases() -> dict[str, Any]:
    categories = sorted({item["category"] for item in EDGE_CASES})
    return {"phase": "5", "count": len(EDGE_CASES), "categories": categories, "edge_cases": EDGE_CASES}


@router.post("/edge-cases/diagnose")
def diagnose_edge_case(body: EdgeDiagnosisRequest) -> dict[str, Any]:
    case = next((item for item in EDGE_CASES if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    settings = _settings()
    diagnosis = {
        "case": case,
        "context": body.context,
        "requires_operator_review": case["severity"] in {"medium", "high", "critical"},
        "action_plan": case["runbook"] + ["write phase5 audit entry", "rerun acceptance if configuration changed"],
        "created_at": time.time(),
    }
    _append_audit("phase5.edge_case_diagnosed", {"case_id": case["id"], "severity": case["severity"]})
    return diagnosis


@router.get("/conflicts")
def get_conflicts() -> dict[str, Any]:
    settings = _settings()
    return {"conflicts": _check_conflicts(settings), "risk_preview": settings.get("risk_preview")}


@router.get("/acceptance")
def get_acceptance(goal: str = "apps_internal") -> dict[str, Any]:
    return _build_acceptance(_settings(goal=goal), goal=goal, finalize=False)


@router.get("/acceptance-test")
def run_acceptance_test(goal: str = "apps_internal") -> dict[str, Any]:
    settings = _settings(goal=goal)
    return _build_acceptance(settings, goal=goal, finalize=True)


@router.post("/complete")
def complete_phase_5(goal: str = "apps_internal") -> dict[str, Any]:
    settings = _settings(goal=goal)
    result = _build_acceptance(settings, goal=goal, finalize=True)
    if result["hard_blocks"]:
        raise HTTPException(status_code=400, detail=result)
    return result
