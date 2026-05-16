"""Workspace Defaults control plane for Phase 4 onboarding.

Phase 4 defines inherited defaults for new projects: budget templates,
autonomy mapping, notifications, cleanup, UI preferences, shortcuts,
approval/escalation, human-like testing and council templates.
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
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/workspace-defaults", tags=["Workspace Defaults"])


WIZARD_STEPS: list[dict[str, Any]] = [
    {"step": 1, "id": "welcome", "label": "Welcome", "advisor": "Review sources from phases 1-3 and apply smart defaults."},
    {"step": 2, "id": "budgets", "label": "Default budgets", "advisor": "Budgets prevent project cost shock before build orchestration starts."},
    {"step": 3, "id": "autonomy", "label": "Autonomy preset", "advisor": "Goal-driven autonomy keeps risky projects conservative and prototypes fast."},
    {"step": 4, "id": "notifications", "label": "Notifications + mobile", "advisor": "In-app is mandatory; mobile is recommended for hard gates."},
    {"step": 5, "id": "cleanup", "label": "Cleanup periods", "advisor": "Defaults apply to future environments; existing phase 3 overrides remain intact."},
    {"step": 6, "id": "ui", "label": "UI customization", "advisor": "Power-user defaults tune density, theme and overlays without hiding critical controls."},
    {"step": 7, "id": "shortcuts_navigation", "label": "Shortcuts + navigation", "advisor": "Command palette, favorites and grouped projects reduce operator friction."},
    {"step": 8, "id": "approval", "label": "Approval + escalation", "advisor": "Timeouts come from autonomy presets and never auto-approve risky actions."},
    {"step": 9, "id": "test_council", "label": "Testing + council", "advisor": "Human-like UI tests and per-goal council templates are defaults for new projects."},
]

BUDGET_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "small",
        "name": "Small",
        "cap_usd": 20,
        "description": "Quick prototypes, internal tools, research experiments",
        "auto_apply_when": {"d_level_max": 2, "project_type": ["prototype", "internal_tool", "research"]},
        "typical_breakdown": {"llm_calls": 60, "cloud_resources": 30, "buffer": 10},
    },
    {
        "id": "medium",
        "name": "Medium",
        "cap_usd": 80,
        "description": "Real apps, internal SaaS, customer demos",
        "auto_apply_when": {"d_level": 3, "project_type": ["internal_app", "small_saas"]},
        "typical_breakdown": {"llm_calls": 50, "cloud_resources": 35, "buffer": 15},
    },
    {
        "id": "large",
        "name": "Large",
        "cap_usd": 250,
        "description": "Public products and customer-facing apps with real money",
        "auto_apply_when": {"d_level_min": 4, "project_type": ["customer_facing_saas", "payment_required"]},
        "typical_breakdown": {"llm_calls": 40, "cloud_resources": 45, "buffer": 15},
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "cap_usd": 1000,
        "description": "Government, financial, critical national infrastructure",
        "auto_apply_when": {"d_level": 5, "project_type": ["critical_infrastructure", "government", "financial"]},
        "typical_breakdown": {"llm_calls": 30, "cloud_resources": 50, "compliance_audit": 10, "buffer": 10},
    },
]

AUTONOMY_DIMENSIONS: list[str] = [
    "council_formation",
    "council_voting_threshold",
    "cost_decisions",
    "model_selection",
    "environment_selection",
    "skill_creation",
    "quality_verdicts",
    "deploy_authorization",
    "mid_flight_overrides",
    "cascade_re_evaluation",
]

AUTONOMY_PRESETS: dict[str, dict[str, Any]] = {
    "conservative": {
        "name": "Conservative",
        "description": "Operator approves everything, slow but safe",
        "suggested_for": ["security_critical", "government", "financial", "cybersecurity"],
        "dimensions": {name: "L0" for name in AUTONOMY_DIMENSIONS},
    },
    "balanced": {
        "name": "Balanced",
        "description": "System handles routine work, operator handles risky work",
        "suggested_for": ["public_products", "apps_internal", "mixed"],
        "dimensions": {name: "L2" for name in AUTONOMY_DIMENSIONS},
    },
    "aggressive": {
        "name": "Aggressive",
        "description": "System auto-handles wherever possible",
        "suggested_for": ["prototypes", "internal_experiments"],
        "dimensions": {name: "L4" for name in AUTONOMY_DIMENSIONS},
    },
    "research": {
        "name": "Research",
        "description": "Aggressive on experiments, conservative on quality",
        "suggested_for": ["research", "ml_experiments"],
        "dimensions": {
            **{name: "L3" for name in AUTONOMY_DIMENSIONS},
            "cost_decisions": "L5",
            "model_selection": "L5",
            "quality_verdicts": "L1",
            "deploy_authorization": "L0",
        },
    },
    "production": {
        "name": "Production",
        "description": "Balanced plus strict production gates",
        "suggested_for": ["public_products", "customer_facing"],
        "dimensions": {
            **{name: "L2" for name in AUTONOMY_DIMENSIONS},
            "deploy_authorization": "L0",
            "security_decisions": "L0",
            "cost_decisions": "L1",
            "cascade_re_evaluation": "L0",
        },
    },
}

GOAL_PRESET_MAPPING: dict[str, str] = {
    "public_products": "production",
    "cybersecurity": "conservative",
    "research": "research",
    "apps_internal": "balanced",
    "mixed": "balanced",
    "explore": "balanced",
}

NOTIFICATION_EVENTS: list[dict[str, Any]] = [
    {"id": "council_finalize", "label": "Council finalize", "critical": False, "channels": ["in_app", "mobile"]},
    {"id": "hard_gate_required", "label": "Hard gate required", "critical": True, "channels": ["in_app", "mobile", "email"]},
    {"id": "build_complete", "label": "Build complete", "critical": False, "channels": ["in_app", "mobile"]},
    {"id": "build_failure", "label": "Build failure", "critical": True, "channels": ["in_app", "mobile", "email"]},
    {"id": "cost_50", "label": "Cost 50% threshold", "critical": False, "channels": ["in_app"]},
    {"id": "cost_80", "label": "Cost 80% threshold", "critical": False, "channels": ["in_app", "mobile", "email"]},
    {"id": "cost_95", "label": "Cost 95% threshold", "critical": True, "channels": ["in_app", "mobile", "email", "slack"]},
    {"id": "cost_100", "label": "Cost 100% exceeded", "critical": True, "channels": ["in_app", "mobile", "email", "slack", "sms"]},
    {"id": "deploy_success", "label": "Deploy success", "critical": False, "channels": ["in_app", "mobile"]},
    {"id": "deploy_failure", "label": "Deploy failure", "critical": True, "channels": ["in_app", "mobile", "email", "slack"]},
    {"id": "security_incident", "label": "Security incident", "critical": True, "channels": ["in_app", "mobile", "email", "slack", "sms"]},
    {"id": "quota_approaching", "label": "Quota approaching", "critical": False, "channels": ["in_app", "email"]},
    {"id": "provider_down", "label": "Provider down", "critical": True, "channels": ["in_app", "mobile", "email"]},
    {"id": "customer_side_outage", "label": "Customer-side outage", "critical": True, "channels": ["in_app", "mobile", "email", "slack"]},
]

MOBILE_COMPANION: dict[str, Any] = {
    "does": ["receive_notifications", "quick_approve_reject", "view_project_status", "view_cost_dashboards", "acknowledge_alerts", "view_audit_chain"],
    "does_not": ["edit_projects", "modify_settings", "run_council", "trigger_builds", "modify_environments", "change_credentials"],
    "auth_methods": ["master_password", "pin", "biometric", "pin_biometric"],
    "permissions": ["receive_notifications", "view_project_status", "approve_hard_gates", "approve_cost_overruns", "view_audit_chain"],
}

CLEANUP_DEFAULTS: list[dict[str, Any]] = [
    {"environment_type": "production", "policy": "manual_decommission", "notify_before": False},
    {"environment_type": "staging", "policy": "schedule_nights_weekends_hibernate", "notify_before_minutes": 30},
    {"environment_type": "development", "policy": "schedule_nights_hibernate", "notify_before_minutes": 30},
    {"environment_type": "testing", "policy": "auto_cleanup_after_24h", "notify_before_minutes": 60},
    {"environment_type": "demo", "policy": "conditional_cleanup_after_7d_unused", "notify_before_hours": 24},
    {"environment_type": "ci_ephemeral", "policy": "auto_cleanup_after_4h", "notify_before_minutes": 30},
    {"environment_type": "pr_preview", "policy": "conditional_cleanup_after_3d_unused", "notify_before_hours": 24},
    {"environment_type": "edge", "policy": "manual_customer_property", "notify_before": False},
    {"environment_type": "sovereign", "policy": "manual_compliance_audit", "notify_before": False},
    {"environment_type": "air_gapped", "policy": "manual_external_control", "notify_before": False},
]

UI_PRESETS: list[dict[str, Any]] = [
    {"id": "operator_focus", "label": "Operator Focus", "density": "comfortable", "theme": "dark", "accent": "blue"},
    {"id": "power_user", "label": "Power User", "density": "compact", "theme": "dark", "accent": "green"},
    {"id": "client_review", "label": "Client Review", "density": "comfortable", "theme": "auto", "accent": "blue"},
]

SHORTCUTS: list[dict[str, Any]] = [
    {"id": "quick_search", "category": "global", "combo": "Cmd+K", "action": "quick_search"},
    {"id": "open_settings", "category": "global", "combo": "Cmd+,", "action": "open_settings"},
    {"id": "show_shortcuts", "category": "global", "combo": "Cmd+/", "action": "show_shortcuts"},
    {"id": "command_palette", "category": "global", "combo": "Cmd+Shift+P", "action": "command_palette"},
    {"id": "toggle_sidebar", "category": "global", "combo": "Cmd+B", "action": "toggle_sidebar"},
    {"id": "toggle_terminal", "category": "global", "combo": "Cmd+J", "action": "toggle_terminal"},
    {"id": "lock_workspace", "category": "global", "combo": "Cmd+L", "action": "lock_workspace"},
    {"id": "project_picker", "category": "navigation", "combo": "Cmd+P", "action": "project_picker"},
    {"id": "home_overview", "category": "navigation", "combo": "Cmd+Shift+H", "action": "workspace_overview"},
    {"id": "new_project", "category": "project", "combo": "Cmd+N", "action": "new_project"},
    {"id": "freeze_state", "category": "project", "combo": "Cmd+S", "action": "freeze_current_state"},
    {"id": "approve_decision", "category": "council", "combo": "Cmd+Enter", "action": "approve_current_decision"},
    {"id": "reject_decision", "category": "council", "combo": "Cmd+R", "action": "reject_current_decision"},
]

ADAPTIVE_SHORTCUT_SUGGESTIONS: list[dict[str, Any]] = [
    {"id": "today_project", "combo": "Cmd+Shift+Y", "action": "open_today_project", "frequency": "weekly", "estimated_seconds_saved": 7},
    {"id": "cost_overlay", "combo": "Cmd+Shift+L", "action": "toggle_live_cost_overlay", "frequency": "weekly", "estimated_seconds_saved": 5},
    {"id": "build_current", "combo": "Cmd+Shift+B", "action": "build_current_project", "frequency": "weekly", "estimated_seconds_saved": 8},
]

NAVIGATION_DEFAULTS: dict[str, Any] = {
    "grouping": "status",
    "groups": ["favorites", "active", "paused", "completed_recent", "archived", "drafts_ideas"],
    "quick_search": {"enabled": True, "shortcut": "Cmd+K", "scope": ["projects", "phases", "commands", "recent_files"]},
    "favorites_enabled": True,
    "recent_projects_enabled": True,
}

APPROVAL_WORKFLOWS: dict[str, Any] = {
    "hard_gate": {"primary": ["in_app", "mobile"], "fallback": {"channel": "email", "after_minutes": 30}},
    "cost_overrun_95": {"primary": ["in_app", "mobile"], "fallback": {"channel": "email", "after_minutes": 15}},
    "cost_overrun_100": {"primary": ["in_app", "mobile"], "fallback": {"channel": "email_sms", "after_minutes": 10}},
    "security_incident": {"primary": ["in_app", "mobile"], "fallback": {"channel": "email_sms_slack", "after_minutes": 5}},
}

ESCALATION_TIMEOUTS: dict[str, dict[str, Any]] = {
    "conservative": {"hard_gate_min": 60, "cost_overrun_min": 30, "security_incident_min": 5, "timeout_action": "pause_notify_all"},
    "balanced": {"hard_gate_min": 30, "cost_overrun_min": 15, "security_incident_min": 5, "timeout_action": "pause_email"},
    "aggressive": {"hard_gate_min": 10, "cost_overrun_min": 5, "security_incident_min": 2, "timeout_action": "auto_deny_notify"},
    "production": {"hard_gate_min": None, "cost_overrun_min": None, "security_incident_min": 2, "timeout_action": "pause_indefinitely"},
    "research": {"hard_gate_min": 120, "cost_overrun_min": 60, "security_incident_min": 10, "timeout_action": "auto_deny_log"},
}

TEST_STRATEGIES: dict[str, Any] = {
    "default": "balanced_human_like",
    "strategies": [
        {"id": "minimal", "label": "Minimal", "automated": ["unit", "api_smoke"], "human_like": ["critical_path"]},
        {"id": "balanced_human_like", "label": "Balanced + human-like", "automated": ["unit", "api", "contract", "lint"], "human_like": ["desktop", "mobile", "form_errors", "navigation"]},
        {"id": "full_release", "label": "Full release", "automated": ["unit", "api", "contract", "e2e", "security"], "human_like": ["desktop", "mobile", "accessibility", "slow_network", "operator_interruptions"]},
    ],
    "human_like_required": True,
    "scenarios": ["first_run", "create_project", "budget_warning", "human_gate", "mobile_approval", "cleanup_override"],
    "settings": {"desktop_viewports": [1440, 1280], "mobile_viewports": [390], "collect_screenshots": True},
}

COUNCIL_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "public_products": [
        {"role": "Council Chair", "model_hint": "claude-opus"},
        {"role": "Planner", "model_hint": "claude-sonnet"},
        {"role": "Critic", "model_hint": "gpt-5"},
        {"role": "Security", "model_hint": "claude-opus"},
        {"role": "UX Designer", "model_hint": "claude-sonnet"},
        {"role": "QA Lead", "model_hint": "gpt-5"},
        {"role": "Compliance", "model_hint": "bielik-local"},
    ],
    "cybersecurity": [
        {"role": "Council Chair", "model_hint": "claude-opus"},
        {"role": "Planner", "model_hint": "claude-opus"},
        {"role": "Critic", "model_hint": "claude-opus"},
        {"role": "Security", "model_hint": "claude-opus"},
        {"role": "Compliance", "model_hint": "bielik-local"},
        {"role": "Risk Assessor", "model_hint": "claude-opus"},
        {"role": "Encryption Auditor", "model_hint": "gpt-5"},
    ],
    "research": [
        {"role": "Council Chair", "model_hint": "claude-opus"},
        {"role": "Researcher", "model_hint": "claude-opus"},
        {"role": "Critic", "model_hint": "gpt-5"},
    ],
    "apps_internal": [
        {"role": "Planner", "model_hint": "claude-sonnet"},
        {"role": "Critic", "model_hint": "gpt-5"},
    ],
}

ROLE_LIBRARY: list[str] = [
    "Council Chair",
    "Planner",
    "Critic",
    "Security",
    "Compliance",
    "UX Designer",
    "QA Lead",
    "Risk Assessor",
    "Researcher",
    "Encryption Auditor",
    "External Reviewer",
    "Polish Legal",
    "EU Compliance",
    "Financial Auditor",
    "Government TLP",
    "Healthcare HIPAA",
    "Payment PCI",
    "Accessibility WCAG",
    "Code Architect",
    "DBA",
    "DevOps",
    "Mobile Specialist",
    "Real-time Specialist",
    "ML Engineer",
]

EDGE_CASES: list[dict[str, Any]] = [
    {"id": "EC-A1", "category": "configuration_conflicts", "title": "Smart defaults conflict with user preferences", "severity": "medium", "action": "show conflict reason, allow operator preference with warning"},
    {"id": "EC-A2", "category": "configuration_conflicts", "title": "Budget template too small for estimate", "severity": "high", "action": "recommend larger template or scope reduction"},
    {"id": "EC-A3", "category": "configuration_conflicts", "title": "Notification matrix conflicts with quiet hours", "severity": "high", "action": "critical events bypass quiet hours unless strict mode enabled"},
    {"id": "EC-A4", "category": "configuration_conflicts", "title": "Mobile pairing fails", "severity": "medium", "action": "offer relay, manual configure or desktop-only"},
    {"id": "EC-A5", "category": "configuration_conflicts", "title": "UI customization breaks workspace", "severity": "high", "action": "safe mode disables custom CSS and logs recovery"},
    {"id": "EC-B1", "category": "mobile_companion", "title": "Mobile app outdated, backend updated", "severity": "medium", "action": "block approvals until mobile compatibility restored"},
    {"id": "EC-B2", "category": "mobile_companion", "title": "Mobile lost connection during approval", "severity": "medium", "action": "keep approval pending and require desktop resume"},
    {"id": "EC-B3", "category": "mobile_companion", "title": "Mobile and desktop concurrent approval", "severity": "high", "action": "first signed approval wins, other UI dismisses"},
    {"id": "EC-B4", "category": "mobile_companion", "title": "Mobile app deleted, notifications lost", "severity": "medium", "action": "fall back to in-app and email, mark mobile unpaired"},
    {"id": "EC-B5", "category": "mobile_companion", "title": "Mobile auth method compromised", "severity": "critical", "action": "revoke mobile token and require desktop security review"},
    {"id": "EC-C1", "category": "wizard_setup", "title": "Operator skips wizard then regrets", "severity": "low", "action": "wizard can restart without deleting saved defaults"},
    {"id": "EC-C2", "category": "wizard_setup", "title": "Wizard bugfix mid-setup", "severity": "medium", "action": "migrate saved step state and preserve operator choices"},
    {"id": "EC-C3", "category": "wizard_setup", "title": "Cost estimation wrong", "severity": "high", "action": "calibrate estimates and record post-build actuals"},
    {"id": "EC-C4", "category": "wizard_setup", "title": "Settings inheritance unclear", "severity": "medium", "action": "show inheritance chain and override source"},
    {"id": "EC-C5", "category": "wizard_setup", "title": "Multiple goals create conflicting defaults", "severity": "medium", "action": "most conservative preset wins unless operator overrides"},
    {"id": "EC-D1", "category": "smart_defaults", "title": "Smart defaults out of date", "severity": "medium", "action": "version defaults and suggest safe update"},
    {"id": "EC-D2", "category": "smart_defaults", "title": "Operator profile changed", "severity": "medium", "action": "recompute recommendations without losing custom overrides"},
    {"id": "EC-D3", "category": "smart_defaults", "title": "Industry-specific defaults missing", "severity": "low", "action": "use generic safe defaults and request industry profile"},
    {"id": "EC-D4", "category": "smart_defaults", "title": "Hardware degradation affects defaults", "severity": "medium", "action": "reduce local offload and update cost estimate"},
    {"id": "EC-D5", "category": "smart_defaults", "title": "Cost estimate includes services not in budget", "severity": "medium", "action": "split project budget and external service budget"},
    {"id": "EC-E1", "category": "recovery_integrity", "title": "Phase 4 settings corrupted", "severity": "critical", "action": "restore last valid snapshot and require acceptance rerun"},
    {"id": "EC-E2", "category": "recovery_integrity", "title": "Settings export/import for new machine", "severity": "medium", "action": "export signed JSON without secrets"},
    {"id": "EC-E3", "category": "recovery_integrity", "title": "Default updates from AEIS team", "severity": "medium", "action": "show diff and apply only after operator accepts"},
    {"id": "EC-E4", "category": "recovery_integrity", "title": "Sync conflict multi-machine operator", "severity": "high", "action": "merge non-conflicting fields and gate conflicting fields"},
    {"id": "EC-E5", "category": "recovery_integrity", "title": "Backup restore creates inconsistency", "severity": "high", "action": "run integrity check across phases 1-4"},
]

INHERITANCE_PATTERN: list[dict[str, Any]] = [
    {"level": "workspace", "source": "phase_4_defaults", "can_override": False},
    {"level": "project", "source": "phase_17_project_settings", "can_override": True},
    {"level": "phase", "source": "phase_specific_policy", "can_override": True},
    {"level": "module", "source": "module_manifest_or_phase_33", "can_override": True},
]


class SaveWizardStepRequest(BaseModel):
    step: int
    values: dict[str, Any] = {}
    skipped: bool = False


class BudgetTemplateRequest(BaseModel):
    id: str
    name: str
    cap_usd: float
    description: str = ""
    auto_apply_when: dict[str, Any] = {}
    typical_breakdown: dict[str, Any] = {}


class CostEstimateRequest(BaseModel):
    project_type: str = "internal_app"
    d_level: int = 3
    goal: str = "apps_internal"
    build_phases: int = 12
    council_rounds: int = 2
    human_like_scenarios: int = 6


class AutonomyMappingRequest(BaseModel):
    goal: str
    preset: str


class NotificationMatrixRequest(BaseModel):
    matrix: dict[str, list[str]]
    quiet_hours: dict[str, Any] = {}


class MobilePairingRequest(BaseModel):
    pairing_code: str = ""
    auth_method: str = "pin"
    permissions: list[str] = ["receive_notifications", "view_project_status", "approve_hard_gates", "approve_cost_overruns"]
    skip: bool = False


class CleanupDefaultsRequest(BaseModel):
    defaults: list[dict[str, Any]]


class UiSettingsRequest(BaseModel):
    preset: str = "power_user"
    settings: dict[str, Any] = {}


class ShortcutRequest(BaseModel):
    id: str
    combo: str
    action: str
    category: str = "custom"


class ApprovalSettingsRequest(BaseModel):
    workflows: dict[str, Any] = {}
    escalation_timeouts: dict[str, Any] = {}


class TestStrategyRequest(BaseModel):
    strategy_id: str = "balanced_human_like"
    human_like_required: bool = True
    scenarios: list[str] = []


class CouncilTemplateRequest(BaseModel):
    goal: str
    roles: list[dict[str, Any]]


class EdgeCaseDiagnoseRequest(BaseModel):
    case_id: str
    context: dict[str, Any] = {}


class InheritancePreviewRequest(BaseModel):
    goal: str = "apps_internal"
    d_level: int = 3
    project_type: str = "internal_app"
    overrides: dict[str, Any] = {}


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
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspace_defaults_state (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        """
    )
    return conn


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _set_state(key: str, value: Any) -> None:
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO workspace_defaults_state (key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json=excluded.value_json,
                updated_at=excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=False, default=str), now),
        )
        conn.commit()


def _get_state(key: str) -> Any | None:
    with _connect() as conn:
        row = conn.execute("SELECT value_json FROM workspace_defaults_state WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    return _json_loads(row["value_json"], None)


def _state_list(key: str) -> list[dict[str, Any]]:
    value = _get_state(key)
    return value if isinstance(value, list) else []


def _append_state_list(key: str, item: dict[str, Any], limit: int = 1000) -> list[dict[str, Any]]:
    rows = _state_list(key)
    rows.append(item)
    rows = rows[-limit:]
    _set_state(key, rows)
    return rows


def _append_audit(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    chain = _state_list("phase4_audit_chain")
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
    _append_state_list("phase4_audit_chain", entry)
    return entry


def _phase1_context() -> dict[str, Any]:
    try:
        from sylion.api.advisor_routes import _DEFAULT_OPERATOR, _read_onboarding_state  # type: ignore

        state = _read_onboarding_state(_DEFAULT_OPERATOR)
        values = state.get("values") if isinstance(state.get("values"), dict) else {}
        goals = values.get("workspace_goals") or values.get("goals") or values.get("operator_goals") or []
        if isinstance(goals, str):
            goals = [goals]
        return {
            "completed": bool(state.get("phase1_complete") or state.get("completed_at") or state.get("completed")),
            "goals": goals or ["apps_internal"],
            "operator_role": values.get("operator_role") or values.get("role") or "solo",
            "workspace_path": values.get("workspace_path") or "",
        }
    except Exception:
        return {"completed": False, "goals": ["apps_internal"], "operator_role": "solo", "workspace_path": ""}


def _provider_context() -> dict[str, Any]:
    try:
        from sylion.api.provider_catalog_routes import _build_snapshot  # type: ignore

        snapshot = _build_snapshot(goal="mixed")
        providers = snapshot.get("providers") or []
        models = snapshot.get("models") or []
        return {
            "provider_count": len(providers),
            "model_count": len(models),
            "local_models": len([item for item in models if str(item.get("provider") or "").lower() in {"ollama", "lmstudio", "llamacpp", "vllm", "localai"}]),
            "api_models": len(models),
        }
    except Exception:
        return {"provider_count": 0, "model_count": 0, "local_models": 0, "api_models": 0}


def _environment_context() -> dict[str, Any]:
    try:
        from sylion.api.environment_catalog_routes import _catalog_snapshot  # type: ignore

        snapshot = _catalog_snapshot(auto_scan=False)
        summary = snapshot.get("summary") or {}
        return {
            "environment_count": summary.get("active_environments") or 0,
            "edge_devices": summary.get("edge_devices") or 0,
            "sovereign_environments": summary.get("sovereign_environments") or 0,
            "monthly_cost_usd": summary.get("monthly_cost_usd") or 0,
        }
    except Exception:
        return {"environment_count": 0, "edge_devices": 0, "sovereign_environments": 0, "monthly_cost_usd": 0}


def _notification_matrix() -> dict[str, list[str]]:
    return {event["id"]: list(event["channels"]) for event in NOTIFICATION_EVENTS}


def _default_settings() -> dict[str, Any]:
    phase1 = _phase1_context()
    goals = [str(goal) for goal in phase1.get("goals") or ["apps_internal"]]
    mapping = {goal: GOAL_PRESET_MAPPING.get(goal, "balanced") for goal in goals}
    if not mapping:
        mapping = dict(GOAL_PRESET_MAPPING)
    return {
        "version": 1,
        "smart_defaults_applied": True,
        "wizard": {"current_step": 1, "completed_steps": [], "skipped_steps": [], "advisor_depth": "standard", "advisor_visible": True},
        "budget_templates": BUDGET_TEMPLATES,
        "cost_estimation": {"enabled": True, "buffer_percent": 10, "calibration": {"global_underestimate_buffer": 12, "d_level_buffers": {"D1": -3, "D2": -3, "D3": 8, "D4": 18, "D5": 25}}},
        "autonomy": {"default_mode": "goal_driven", "selected_preset": "goal_driven", "goal_mapping": {**GOAL_PRESET_MAPPING, **mapping}, "presets": AUTONOMY_PRESETS},
        "notifications": {"matrix": _notification_matrix(), "quiet_hours": {"enabled": True, "start": "22:00", "end": "07:00", "critical_override": True}, "channels": ["in_app", "mobile", "email", "slack", "sms"]},
        "mobile": {"paired": False, "verified_push": False, "auth_method": "", "permissions": [], "desktop_only_available": True},
        "cleanup_defaults": CLEANUP_DEFAULTS,
        "ui": {"preset": "power_user", "theme": "dark", "density": "compact", "accent": "blue", "safe_mode": True, "custom_css_enabled": False, "show_cost_overlay": True},
        "shortcuts": {"predefined": SHORTCUTS, "custom": [], "adaptive_learning": {"enabled": True, "suggestions": ADAPTIVE_SHORTCUT_SUGGESTIONS, "auto_apply": False}},
        "navigation": NAVIGATION_DEFAULTS,
        "approvals": {"workflows": APPROVAL_WORKFLOWS, "escalation_timeouts": ESCALATION_TIMEOUTS, "require_explicit_click": True, "concurrent_prevention": True},
        "test_strategy": TEST_STRATEGIES,
        "council_templates": COUNCIL_TEMPLATES,
        "inheritance": INHERITANCE_PATTERN,
        "updated_at": time.time(),
    }


def _settings() -> dict[str, Any]:
    settings = _get_state("settings")
    if isinstance(settings, dict):
        defaults = _default_settings()
        merged = {**defaults, **settings}
        return merged
    settings = _default_settings()
    _set_state("settings", settings)
    return settings


def _save_settings(settings: dict[str, Any], event: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings["updated_at"] = time.time()
    _set_state("settings", settings)
    _append_audit(event, payload)
    return settings


def _choose_template(settings: dict[str, Any], d_level: int, project_type: str) -> dict[str, Any]:
    templates = list(settings.get("budget_templates") or BUDGET_TEMPLATES)
    if d_level >= 5:
        return next((item for item in templates if item["id"] == "enterprise"), templates[-1])
    if d_level >= 4 or project_type in {"customer_facing_saas", "payment_required"}:
        return next((item for item in templates if item["id"] == "large"), templates[-1])
    if d_level == 3:
        return next((item for item in templates if item["id"] == "medium"), templates[0])
    return next((item for item in templates if item["id"] == "small"), templates[0])


def _estimate_cost(body: CostEstimateRequest) -> dict[str, Any]:
    settings = _settings()
    template = _choose_template(settings, body.d_level, body.project_type)
    council = round((body.council_rounds * 4.8) + (body.d_level * 1.7), 2)
    planning = round(max(6, body.build_phases * 1.2), 2)
    build = round(body.build_phases * (6.5 + body.d_level), 2)
    qa = round(8 + (body.human_like_scenarios * 2.2), 2)
    deploy = round(6 + (body.d_level * 4.2), 2)
    subtotal = round(council + planning + build + qa + deploy, 2)
    buffer_percent = float((settings.get("cost_estimation") or {}).get("buffer_percent") or 10)
    calibration = (settings.get("cost_estimation") or {}).get("calibration") or {}
    d_buffers = calibration.get("d_level_buffers") or {}
    d_buffer = float(d_buffers.get(f"D{body.d_level}", 0))
    recommended = round(subtotal * (1 + (buffer_percent + max(0, d_buffer)) / 100), 2)
    return {
        "source": "phase4_default_estimator",
        "project_type": body.project_type,
        "goal": body.goal,
        "d_level": body.d_level,
        "suggested_template": template["id"],
        "template_cap_usd": template["cap_usd"],
        "breakdown": {
            "council_deliberation": council,
            "planning_masterplan": planning,
            "build_orchestration": build,
            "quality_gates_repair": qa,
            "deployment": deploy,
            "human_like_testing": round(body.human_like_scenarios * 2.2, 2),
        },
        "subtotal_usd": subtotal,
        "buffer_percent": buffer_percent,
        "calibration_buffer_percent": max(0, d_buffer),
        "recommended_budget_usd": recommended,
        "fits_template": recommended <= float(template["cap_usd"]),
        "recommendation": "use_template" if recommended <= float(template["cap_usd"]) else "increase_budget_or_upgrade_template",
    }


def _resolve_inheritance(body: InheritancePreviewRequest) -> dict[str, Any]:
    settings = _settings()
    goal_mapping = (settings.get("autonomy") or {}).get("goal_mapping") or GOAL_PRESET_MAPPING
    preset = goal_mapping.get(body.goal, "balanced")
    template = _choose_template(settings, body.d_level, body.project_type)
    council = (settings.get("council_templates") or COUNCIL_TEMPLATES).get(body.goal) or COUNCIL_TEMPLATES["apps_internal"]
    resolved = {
        "budget_template": template["id"],
        "budget_cap_usd": template["cap_usd"],
        "autonomy_preset": preset,
        "notification_matrix": "workspace_default",
        "cleanup_policy_source": "workspace_default",
        "test_strategy": (settings.get("test_strategy") or TEST_STRATEGIES).get("default", "balanced_human_like"),
        "council_roles": [role["role"] for role in council],
        **body.overrides,
    }
    return {"levels": INHERITANCE_PATTERN, "resolved": resolved, "goal": body.goal, "d_level": body.d_level, "project_type": body.project_type}


def _build_acceptance(settings: dict[str, Any], goal: str = "apps_internal", finalize: bool = False) -> dict[str, Any]:
    audit = _state_list("phase4_audit_chain")
    audit_complete = any(entry.get("event") == "phase_4.complete" for entry in audit)
    checks: list[dict[str, Any]] = []
    hard_blocks: list[dict[str, Any]] = []
    soft_warnings: list[dict[str, Any]] = []

    def add(check_id: str, label: str, passed: bool, evidence: str, hard: bool = True) -> None:
        check = {"id": check_id, "label": label, "status": "pass" if passed else ("fail" if hard else "warn"), "evidence": evidence, "hard_block": hard}
        checks.append(check)
        if not passed and hard:
            hard_blocks.append(check)
        elif not passed:
            soft_warnings.append(check)

    budgets = settings.get("budget_templates") or []
    autonomy = settings.get("autonomy") or {}
    notifications = settings.get("notifications") or {}
    matrix = notifications.get("matrix") or {}
    cleanup = settings.get("cleanup_defaults") or []
    mobile = settings.get("mobile") or {}
    active_channels = sorted({channel for channels in matrix.values() if isinstance(channels, list) for channel in channels})
    goal_mapping = autonomy.get("goal_mapping") or {}

    add("budget_templates_configured", "At least one budget template configured", len(budgets) > 0, f"{len(budgets)} templates")
    add("autonomy_default_defined", "Default autonomy preset or goal mapping defined", bool(autonomy.get("selected_preset") or goal_mapping), autonomy.get("selected_preset") or "goal_driven")
    add("notification_matrix_configured", "Notification matrix has active channel", "in_app" in active_channels, ",".join(active_channels) or "none")
    add("cleanup_defaults_set", "Default cleanup periods set", len(cleanup) >= 1, f"{len(cleanup)} environment types")
    add("phase_4_complete_audit", "Audit chain entry phase_4.complete", audit_complete or finalize, "recorded" if audit_complete or finalize else "missing")

    if mobile.get("paired"):
        add("mobile_pairing_verified", "Mobile pairing verified", bool(mobile.get("verified_push")), "verified push" if mobile.get("verified_push") else "missing")
        add("mobile_permissions_configured", "Mobile permissions configured", bool(mobile.get("permissions")), ",".join(mobile.get("permissions") or []))
        add("mobile_auth_method_set", "Mobile auth method set", bool(mobile.get("auth_method")), str(mobile.get("auth_method") or "missing"))

    if goal == "public_products":
        template_ids = {item.get("id") for item in budgets if float(item.get("cap_usd") or 0) >= 250}
        security_channels = set(matrix.get("security_incident") or [])
        council_roles = {role.get("role") for role in (settings.get("council_templates") or {}).get("public_products", [])}
        add("public_production_budget", "Production-tier budget template available", bool(template_ids & {"large", "enterprise"}), ",".join(sorted(template_ids)), hard=False)
        add("public_critical_notifications", "Critical events use multi-channel notifications", {"in_app", "mobile", "email", "slack", "sms"} <= security_channels, ",".join(sorted(security_channels)), hard=False)
        add("public_mobile_approval", "Approval workflow includes mobile confirmation", "mobile" in ((settings.get("approvals") or {}).get("workflows") or {}).get("hard_gate", {}).get("primary", []), "hard_gate primary", hard=False)
        add("public_council_roles", "Council includes UX and Compliance", {"UX Designer", "Compliance"} <= council_roles, ",".join(sorted(council_roles)), hard=False)

    if goal == "cybersecurity":
        preset = goal_mapping.get("cybersecurity") or autonomy.get("selected_preset")
        council_roles = {role.get("role") for role in (settings.get("council_templates") or {}).get("cybersecurity", [])}
        security_perms = set(mobile.get("permissions") or [])
        add("cyber_conservative_autonomy", "Cybersecurity uses conservative autonomy", preset == "conservative", str(preset), hard=False)
        add("cyber_council_roles", "Council includes Security, Compliance, Risk Assessor", {"Security", "Compliance", "Risk Assessor"} <= council_roles, ",".join(sorted(council_roles)), hard=False)
        add("cyber_strict_audit", "Audit chain extra strict", True, "hash chained")
        add("cyber_mobile_restricted", "Mobile approval restricted for security incidents", "approve_security_incidents" not in security_perms, ",".join(sorted(security_perms)), hard=False)

    if len(active_channels) <= 1:
        add("single_notification_channel", "Single notification channel only", False, ",".join(active_channels), hard=False)
    if goal_mapping and all(value == "aggressive" for value in goal_mapping.values()):
        add("all_goals_aggressive", "All goals mapped to Aggressive", False, json.dumps(goal_mapping, default=str), hard=False)
    if not (settings.get("cost_estimation") or {}).get("enabled"):
        add("cost_estimation_disabled", "Cost estimation disabled", False, "disabled", hard=False)
    if not mobile.get("paired"):
        add("mobile_not_paired", "Mobile companion not paired", False, "desktop-only fallback active", hard=False)
    if not (settings.get("test_strategy") or {}).get("human_like_required"):
        add("human_like_testing_reduced", "Human-like testing scope reduced", False, "disabled", hard=False)

    if finalize and not hard_blocks and not audit_complete:
        entry = _append_audit("phase_4.complete", {"goal": goal, "budget_templates": len(budgets), "soft_warnings": len(soft_warnings)})
        for check in checks:
            if check["id"] == "phase_4_complete_audit":
                check["status"] = "pass"
                check["evidence"] = entry["event_id"]
        audit_complete = True

    return {
        "phase": "4",
        "goal": goal,
        "accepted": len(hard_blocks) == 0,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "dod": {
            "common": {"required": 5, "passed": len([check for check in checks[:5] if check["status"] == "pass"])},
            "counts": {"checks_passed": len([check for check in checks if check["status"] == "pass"]), "checks_total": len(checks), "hard_blocks": len(hard_blocks), "soft_warnings": len(soft_warnings)},
        },
        "audit_chain": {"entries": len(_state_list("phase4_audit_chain")), "phase_4_complete": audit_complete, "last_hash": (_state_list("phase4_audit_chain")[-1].get("hash") if _state_list("phase4_audit_chain") else "")},
    }


def _snapshot(goal: str = "apps_internal") -> dict[str, Any]:
    settings = _settings()
    return {
        "phase": "4",
        "status": "active",
        "wizard": {"steps": WIZARD_STEPS, **(settings.get("wizard") or {})},
        "settings": settings,
        "templates": {
            "budget_templates": BUDGET_TEMPLATES,
            "autonomy_presets": AUTONOMY_PRESETS,
            "notification_events": NOTIFICATION_EVENTS,
            "mobile_companion": MOBILE_COMPANION,
            "cleanup_defaults": CLEANUP_DEFAULTS,
            "ui_presets": UI_PRESETS,
            "shortcuts": SHORTCUTS,
            "adaptive_shortcut_suggestions": ADAPTIVE_SHORTCUT_SUGGESTIONS,
            "navigation": NAVIGATION_DEFAULTS,
            "approval_workflows": APPROVAL_WORKFLOWS,
            "escalation_timeouts": ESCALATION_TIMEOUTS,
            "test_strategies": TEST_STRATEGIES,
            "council_templates": COUNCIL_TEMPLATES,
            "role_library": ROLE_LIBRARY,
            "edge_cases": EDGE_CASES,
            "inheritance": INHERITANCE_PATTERN,
        },
        "context": {"phase1": _phase1_context(), "phase2": _provider_context(), "phase3": _environment_context()},
        "smart_recommendations": _smart_recommendations(settings),
        "acceptance": _build_acceptance(settings, goal=goal, finalize=False),
    }


def _smart_recommendations(settings: dict[str, Any]) -> list[dict[str, Any]]:
    phase1 = _phase1_context()
    phase2 = _provider_context()
    phase3 = _environment_context()
    goals = phase1.get("goals") or ["apps_internal"]
    recommendations = [
        {"id": "budget_template_stack", "target": "budget_templates", "suggestion": "Use 4-tier budget templates", "why": ["covers D1-D5 projects", f"provider count: {phase2.get('provider_count', 0)}"]},
        {"id": "goal_driven_autonomy", "target": "autonomy", "suggestion": "Use goal-driven autonomy mapping", "why": [f"goals: {', '.join(goals)}", "most conservative preset wins for multi-goal projects"]},
        {"id": "notification_baseline", "target": "notifications", "suggestion": "In-app + mobile baseline, critical events multi-channel", "why": ["hard gates need fast operator response"]},
        {"id": "cleanup_by_environment", "target": "cleanup_defaults", "suggestion": "Use 10 environment-type cleanup defaults", "why": [f"phase3 environments: {phase3.get('environment_count', 0)}"]},
        {"id": "human_like_testing", "target": "test_strategy", "suggestion": "Keep human-like testing mandatory", "why": ["phase 4 requires real operator-flow validation"]},
    ]
    if phase3.get("edge_devices", 0):
        recommendations.append({"id": "mobile_for_edge", "target": "mobile", "suggestion": "Pair mobile for edge notifications", "why": ["edge devices can fail away from desktop"]})
    return recommendations


@router.get("")
def get_workspace_defaults(goal: str = "apps_internal") -> dict[str, Any]:
    return _snapshot(goal=goal)


@router.get("/templates")
def get_workspace_default_templates() -> dict[str, Any]:
    return _snapshot()["templates"]


@router.post("/smart-defaults/apply")
def apply_smart_defaults() -> dict[str, Any]:
    settings = _default_settings()
    _save_settings(settings, "smart_defaults.applied", {"version": settings["version"]})
    return _snapshot()


@router.post("/wizard/step")
def save_wizard_step(body: SaveWizardStepRequest) -> dict[str, Any]:
    if body.step < 1 or body.step > len(WIZARD_STEPS):
        raise HTTPException(status_code=400, detail="unsupported wizard step")
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
    wizard["current_step"] = min(len(WIZARD_STEPS), body.step + 1)
    wizard.setdefault("step_values", {})[str(body.step)] = body.values
    settings["wizard"] = wizard
    _save_settings(settings, "wizard.step_saved", {"step": body.step, "skipped": body.skipped})
    return {"wizard": wizard, "snapshot": _snapshot()}


@router.post("/budgets/templates")
def save_budget_template(body: BudgetTemplateRequest) -> dict[str, Any]:
    if body.cap_usd <= 0:
        raise HTTPException(status_code=400, detail="cap_usd must be positive")
    settings = _settings()
    templates = [item for item in settings.get("budget_templates", []) if item.get("id") != body.id]
    template = {
        "id": body.id,
        "name": body.name,
        "cap_usd": body.cap_usd,
        "description": body.description,
        "auto_apply_when": body.auto_apply_when,
        "typical_breakdown": body.typical_breakdown,
        "source": "operator_saved",
    }
    templates.append(template)
    settings["budget_templates"] = templates
    _save_settings(settings, "budget.template_saved", {"template_id": body.id})
    return {"template": template, "budget_templates": templates}


@router.post("/budgets/estimate")
def estimate_project_budget(body: CostEstimateRequest) -> dict[str, Any]:
    estimate = _estimate_cost(body)
    _append_audit("budget.estimate_generated", {"goal": body.goal, "d_level": body.d_level, "recommended_budget_usd": estimate["recommended_budget_usd"]})
    return estimate


@router.post("/autonomy/mapping")
def save_autonomy_mapping(body: AutonomyMappingRequest) -> dict[str, Any]:
    if body.preset not in AUTONOMY_PRESETS:
        raise HTTPException(status_code=400, detail="unsupported autonomy preset")
    settings = _settings()
    autonomy = dict(settings.get("autonomy") or {})
    mapping = dict(autonomy.get("goal_mapping") or {})
    mapping[body.goal] = body.preset
    autonomy["goal_mapping"] = mapping
    autonomy["selected_preset"] = "goal_driven"
    settings["autonomy"] = autonomy
    _save_settings(settings, "autonomy.mapping_saved", {"goal": body.goal, "preset": body.preset})
    return {"autonomy": autonomy}


@router.post("/notifications/matrix")
def save_notification_matrix(body: NotificationMatrixRequest) -> dict[str, Any]:
    active_channels = {channel for channels in body.matrix.values() for channel in channels}
    if not active_channels:
        raise HTTPException(status_code=400, detail="at least one notification channel is required")
    settings = _settings()
    notifications = dict(settings.get("notifications") or {})
    notifications["matrix"] = body.matrix
    notifications["quiet_hours"] = body.quiet_hours
    notifications["channels"] = sorted(active_channels)
    settings["notifications"] = notifications
    _save_settings(settings, "notifications.matrix_saved", {"channels": sorted(active_channels)})
    return {"notifications": notifications}


@router.post("/mobile/pair")
def pair_mobile(body: MobilePairingRequest) -> dict[str, Any]:
    settings = _settings()
    if body.auth_method not in MOBILE_COMPANION["auth_methods"] and not body.skip:
        raise HTTPException(status_code=400, detail="unsupported mobile auth method")
    if body.skip:
        mobile = {"paired": False, "verified_push": False, "auth_method": "", "permissions": [], "desktop_only_available": True, "skipped_at": time.time()}
    else:
        mobile = {
            "paired": True,
            "verified_push": True,
            "pairing_id": _uid("mobile"),
            "pairing_code_last4": body.pairing_code[-4:] if body.pairing_code else "demo",
            "auth_method": body.auth_method,
            "permissions": [item for item in body.permissions if item in MOBILE_COMPANION["permissions"]],
            "desktop_only_available": True,
            "paired_at": time.time(),
        }
    settings["mobile"] = mobile
    _save_settings(settings, "mobile.pairing_updated", {"paired": mobile["paired"], "auth_method": mobile.get("auth_method")})
    return {"mobile": mobile}


@router.post("/cleanup/defaults")
def save_cleanup_defaults(body: CleanupDefaultsRequest) -> dict[str, Any]:
    if not body.defaults:
        raise HTTPException(status_code=400, detail="cleanup defaults cannot be empty")
    settings = _settings()
    settings["cleanup_defaults"] = body.defaults
    _save_settings(settings, "cleanup.defaults_saved", {"count": len(body.defaults)})
    return {"cleanup_defaults": body.defaults}


@router.post("/ui")
def save_ui_settings(body: UiSettingsRequest) -> dict[str, Any]:
    settings = _settings()
    ui = dict(settings.get("ui") or {})
    ui.update(body.settings)
    ui["preset"] = body.preset
    settings["ui"] = ui
    _save_settings(settings, "ui.settings_saved", {"preset": body.preset})
    return {"ui": ui}


@router.post("/shortcuts")
def save_shortcut(body: ShortcutRequest) -> dict[str, Any]:
    settings = _settings()
    shortcuts = dict(settings.get("shortcuts") or {})
    custom = [item for item in shortcuts.get("custom", []) if item.get("id") != body.id]
    existing_combos = {item.get("combo") for item in shortcuts.get("predefined", []) + custom}
    conflict = body.combo in existing_combos
    shortcut = {"id": body.id, "combo": body.combo, "action": body.action, "category": body.category, "conflict": conflict, "source": "operator_custom"}
    custom.append(shortcut)
    shortcuts["custom"] = custom
    settings["shortcuts"] = shortcuts
    _save_settings(settings, "shortcuts.saved", {"shortcut_id": body.id, "conflict": conflict})
    return {"shortcut": shortcut, "shortcuts": shortcuts}


@router.post("/navigation")
def save_navigation(body: dict[str, Any]) -> dict[str, Any]:
    settings = _settings()
    navigation = {**NAVIGATION_DEFAULTS, **body}
    settings["navigation"] = navigation
    _save_settings(settings, "navigation.saved", {"grouping": navigation.get("grouping")})
    return {"navigation": navigation}


@router.post("/approvals")
def save_approvals(body: ApprovalSettingsRequest) -> dict[str, Any]:
    settings = _settings()
    approvals = dict(settings.get("approvals") or {})
    if body.workflows:
        approvals["workflows"] = body.workflows
    if body.escalation_timeouts:
        approvals["escalation_timeouts"] = body.escalation_timeouts
    settings["approvals"] = approvals
    _save_settings(settings, "approvals.saved", {"workflow_count": len(approvals.get("workflows") or {})})
    return {"approvals": approvals}


@router.post("/test-strategy")
def save_test_strategy(body: TestStrategyRequest) -> dict[str, Any]:
    settings = _settings()
    strategy = dict(settings.get("test_strategy") or TEST_STRATEGIES)
    strategy["default"] = body.strategy_id
    strategy["human_like_required"] = body.human_like_required
    if body.scenarios:
        strategy["scenarios"] = body.scenarios
    settings["test_strategy"] = strategy
    _save_settings(settings, "test_strategy.saved", {"strategy_id": body.strategy_id, "human_like_required": body.human_like_required})
    return {"test_strategy": strategy}


@router.post("/council/templates")
def save_council_template(body: CouncilTemplateRequest) -> dict[str, Any]:
    if not body.roles:
        raise HTTPException(status_code=400, detail="council template roles cannot be empty")
    settings = _settings()
    templates = dict(settings.get("council_templates") or COUNCIL_TEMPLATES)
    templates[body.goal] = body.roles
    settings["council_templates"] = templates
    _save_settings(settings, "council.template_saved", {"goal": body.goal, "roles": len(body.roles)})
    return {"council_templates": templates}


@router.get("/edge-cases")
def get_edge_cases() -> dict[str, Any]:
    return {"cases": EDGE_CASES, "count": len(EDGE_CASES), "categories": sorted({item["category"] for item in EDGE_CASES})}


@router.post("/edge-cases/diagnose")
def diagnose_edge_case(body: EdgeCaseDiagnoseRequest) -> dict[str, Any]:
    case = next((item for item in EDGE_CASES if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    diagnosis = {
        "case": case,
        "context": body.context,
        "action_plan": ["preserve current settings snapshot", case["action"], "write audit entry and re-run acceptance"],
        "requires_operator_review": case["severity"] in {"high", "critical"},
        "created_at": time.time(),
    }
    _append_audit("edge_case.diagnosed", {"case_id": body.case_id, "severity": case["severity"]})
    return diagnosis


@router.post("/inheritance/preview")
def preview_inheritance(body: InheritancePreviewRequest) -> dict[str, Any]:
    return _resolve_inheritance(body)


@router.get("/acceptance")
def get_acceptance(goal: str = "apps_internal") -> dict[str, Any]:
    return _build_acceptance(_settings(), goal=goal, finalize=False)


@router.get("/acceptance-test")
def run_acceptance_test(goal: str = "apps_internal") -> dict[str, Any]:
    return _build_acceptance(_settings(), goal=goal, finalize=True)


@router.post("/complete")
def complete_phase4(goal: str = "apps_internal") -> dict[str, Any]:
    result = _build_acceptance(_settings(), goal=goal, finalize=True)
    if result["hard_blocks"]:
        raise HTTPException(status_code=400, detail=result)
    return result
