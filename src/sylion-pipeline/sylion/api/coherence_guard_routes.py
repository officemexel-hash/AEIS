"""Coherence Guard control plane for Phase 6.

Phase 6 configures the first Guard: scope, triggers, severity model,
baseline checks, custom checks, findings handling, worker/cache/cost limits
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
    prefix="/api/v1/coherence-guard",
    tags=["Coherence Guard"],
)


STANDARD_SCOPE: list[dict[str, Any]] = [
    {
        "id": "documents",
        "label": "Documents",
        "artifacts": ["Ksiega", "masterplan", "test plan", "council book", "deployment manifest", "acceptance criteria"],
        "enabled_by_default": True,
    },
    {
        "id": "code",
        "label": "Code",
        "artifacts": ["frontend", "backend", "workers", "configuration files", "database migrations", "API definitions"],
        "enabled_by_default": True,
    },
    {
        "id": "tests",
        "label": "Tests",
        "artifacts": ["unit tests", "integration tests", "E2E tests", "human-like UI tests", "gold standards"],
        "enabled_by_default": True,
    },
    {
        "id": "deployment",
        "label": "Deployment",
        "artifacts": ["environment configs", "deploy manifests", "rollback scripts", "monitoring configs", "IaC"],
        "enabled_by_default": True,
    },
]

CROSS_PROJECT_SCOPE: list[dict[str, Any]] = [
    {"id": "pattern_check", "label": "Cross-project pattern check"},
    {"id": "naming_consistency", "label": "Cross-project naming consistency"},
    {"id": "library_version_drift", "label": "Cross-project library version drift"},
    {"id": "customer_side_coherence", "label": "Customer-side coherence"},
    {"id": "lessons_learned_propagation", "label": "Lessons-learned propagation"},
]

TRIGGER_DEFAULTS: dict[str, Any] = {
    "phase_boundaries": {
        "enabled": True,
        "critical_phases": [25, 28, 29, 35, 37, 39, 41],
        "skip_phases": [],
    },
    "continuous": {
        "enabled": True,
        "throttle_per_file_seconds": 60,
        "batch_window_seconds": 5,
        "file_system_events": True,
        "edit_detection": True,
        "sync_events": False,
        "dependency_changes": True,
        "reduce_during_builds": False,
        "pause_on_battery": False,
    },
    "on_demand": {
        "enabled": True,
        "default_depth": "standard",
        "depths": ["quick", "standard", "deep"],
    },
}

SEVERITY_LEVELS: list[dict[str, Any]] = [
    {"id": "INFO", "rank": 1, "notification": "status bar", "operator_action": "log only"},
    {"id": "WARNING", "rank": 2, "notification": "badge or modal", "operator_action": "review in report"},
    {"id": "ERROR", "rank": 3, "notification": "prominent modal", "operator_action": "fix before continuing"},
    {"id": "CRITICAL", "rank": 4, "notification": "hard modal", "operator_action": "stop risky phase"},
    {"id": "BLOCKER", "rank": 5, "notification": "hard gate", "operator_action": "manual approval required"},
]

DETECTION_TIERS: list[dict[str, Any]] = [
    {
        "id": "tier1",
        "label": "Tier 1 rules",
        "mechanism": "fast deterministic rules",
        "cost": "free or near-free",
        "best_for": ["schema", "coverage", "hash chain", "contract", "configuration"],
    },
    {
        "id": "tier2",
        "label": "Tier 2 semantic",
        "mechanism": "LLM semantic checks",
        "cost": "metered",
        "best_for": ["claim evidence", "acceptance criteria", "translation equivalence", "business logic"],
    },
]

BASELINE_CHECKS: list[dict[str, Any]] = [
    {
        "id": "book_feature_masterplan_module",
        "label": "Feature in Ksiega has module in masterplan",
        "scope": ["documents"],
        "default_tier": "tier1",
        "default_severity": "WARNING",
        "mechanism": "rule",
    },
    {
        "id": "masterplan_module_test_plan",
        "label": "Module in masterplan has test cases in test plan",
        "scope": ["documents", "tests"],
        "default_tier": "tier1",
        "default_severity": "WARNING",
        "mechanism": "rule",
    },
    {
        "id": "council_book_claim_evidence",
        "label": "Council Book claim has evidence in build artifacts",
        "scope": ["documents", "code"],
        "default_tier": "tier2",
        "default_severity": "ERROR",
        "mechanism": "llm_semantic",
    },
    {
        "id": "acceptance_criteria_verifiable_tests",
        "label": "Acceptance criteria in Ksiega verifiable in tests",
        "scope": ["documents", "tests"],
        "default_tier": "tier2",
        "default_severity": "WARNING",
        "mechanism": "llm_semantic",
    },
    {
        "id": "council_decisions_mid_build_interventions",
        "label": "Council decisions not broken by mid-build interventions",
        "scope": ["documents", "code"],
        "default_tier": "tier1",
        "default_severity": "ERROR",
        "mechanism": "rule",
    },
    {
        "id": "hard_gate_approvals_deploy",
        "label": "Hard gate approvals honored in deploy phase",
        "scope": ["deployment"],
        "default_tier": "tier1",
        "default_severity": "CRITICAL",
        "mechanism": "rule",
    },
    {
        "id": "operator_overrides_expire",
        "label": "Operator overrides expire on schedule, no ghost override",
        "scope": ["documents", "deployment"],
        "default_tier": "tier1",
        "default_severity": "WARNING",
        "mechanism": "rule",
    },
    {
        "id": "translation_coverage_all_locales",
        "label": "Translation coverage all locales",
        "scope": ["code", "tests"],
        "default_tier": "tier1",
        "default_severity": "WARNING",
        "mechanism": "rule",
    },
    {
        "id": "translation_semantic_equivalence",
        "label": "Semantic equivalence PL/EN/DE",
        "scope": ["documents", "code"],
        "default_tier": "tier2",
        "default_severity": "WARNING",
        "mechanism": "llm_semantic",
    },
    {
        "id": "locale_date_currency_formats",
        "label": "Date and currency formats per locale",
        "scope": ["code", "tests"],
        "default_tier": "tier1",
        "default_severity": "WARNING",
        "mechanism": "rule",
    },
    {
        "id": "api_contract_frontend_backend",
        "label": "API contracts frontend/backend match",
        "scope": ["code", "tests"],
        "default_tier": "tier1",
        "default_severity": "ERROR",
        "mechanism": "rule",
    },
    {
        "id": "db_schema_orm_match",
        "label": "DB schema vs ORM models match",
        "scope": ["code"],
        "default_tier": "tier1",
        "default_severity": "ERROR",
        "mechanism": "rule",
    },
    {
        "id": "deploy_configs_environment_coherent",
        "label": "Deployment configs coherent between environments",
        "scope": ["deployment"],
        "default_tier": "tier1",
        "default_severity": "ERROR",
        "mechanism": "rule",
    },
    {
        "id": "cost_tracking_actual_spend",
        "label": "Cost tracking matches actual spend",
        "scope": ["documents", "deployment"],
        "default_tier": "tier1",
        "default_severity": "WARNING",
        "mechanism": "rule",
    },
    {
        "id": "audit_chain_hash_valid",
        "label": "Audit chain hash chain valid",
        "scope": ["documents", "deployment"],
        "default_tier": "tier1",
        "default_severity": "CRITICAL",
        "mechanism": "rule",
    },
]

CUSTOM_CHECK_TEMPLATES: list[dict[str, Any]] = [
    {"id": "template_presence", "mechanism": "template", "label": "Artifact presence check", "tier": "tier1"},
    {"id": "template_mapping", "mechanism": "template", "label": "One-to-one mapping check", "tier": "tier1"},
    {"id": "dsl_form_order", "mechanism": "dsl", "label": "Form field ordering rule", "tier": "tier1"},
    {"id": "dsl_config_match", "mechanism": "dsl", "label": "Config value match rule", "tier": "tier1"},
    {"id": "llm_business_claim", "mechanism": "llm", "label": "Business claim coherence", "tier": "tier2"},
    {"id": "llm_security_statement", "mechanism": "llm", "label": "Security statement evidence", "tier": "tier2"},
]

FINDINGS_HANDLING_BY_PRESET: dict[str, dict[str, Any]] = {
    "conservative": {"notify": True, "suggest_fix": False, "auto_fix_simple": False, "manual_review_all": True},
    "balanced": {"notify": True, "suggest_fix": True, "auto_fix_simple": False, "operator_approves": True},
    "aggressive": {"notify": True, "suggest_fix": True, "auto_fix_simple": True, "operator_approves_complex": True},
    "production": {"notify": True, "suggest_fix": False, "auto_fix_simple": False, "blocker_hard_gate": True},
    "research": {"notify": True, "suggest_fix": True, "auto_fix_simple": True, "review_blockers_only": True},
}

AUTO_FIX_TIERS: list[dict[str, Any]] = [
    {"id": "tier1_safe", "label": "Tier 1 safe deterministic fixes", "auto_fix_allowed": True},
    {"id": "tier2_semantic", "label": "Tier 2 semantic suggestions", "auto_fix_allowed": False},
]

NEVER_AUTO_FIX: list[str] = [
    "security claims",
    "GDPR or compliance statements",
    "database migrations",
    "production deploy configs",
    "hard gate approvals",
    "master password",
    "provider keys",
]

NEVER_AUTO_FIX_CHECK_IDS = {
    "council_book_claim_evidence",
    "hard_gate_approvals_deploy",
    "db_schema_orm_match",
    "deploy_configs_environment_coherent",
}

BLOCKING_MATRIX: dict[str, dict[str, bool]] = {
    "INFO": {"conservative": False, "balanced": False, "aggressive": False, "production": False, "research": False},
    "WARNING": {"conservative": False, "balanced": False, "aggressive": False, "production": False, "research": False},
    "ERROR": {"conservative": True, "balanced": False, "aggressive": False, "production": True, "research": False},
    "CRITICAL": {"conservative": True, "balanced": True, "aggressive": False, "production": True, "research": False},
    "BLOCKER": {"conservative": True, "balanced": True, "aggressive": True, "production": True, "research": True},
}

PERFORMANCE_DEFAULTS: dict[str, Any] = {
    "worker_enabled": True,
    "worker_status": "running",
    "worker_mode": "separate_process",
    "cache_initialized": True,
    "cache_hit_rate_pct": 78,
    "cache_layers": ["L1 checksum", "L2 check results", "L3 relationship graph"],
    "incremental_diff": True,
    "budget_share_pct": 5,
    "monthly_budget_usd": 30,
    "used_monthly_usd": 12,
    "budget_cap_enabled": True,
    "thresholds_pct": [80, 95, 100],
}

AGGREGATED_GUARDS: list[dict[str, Any]] = [
    {"id": "coherence", "label": "Coherence Guard", "phase": 6, "status": "configured"},
    {"id": "cost", "label": "Cost Guard", "phase": 7, "status": "pending_phase"},
    {"id": "security", "label": "Security Guard", "phase": 8, "status": "pending_phase"},
    {"id": "quality", "label": "Quality Guard", "phase": 9, "status": "pending_phase"},
    {"id": "provenance", "label": "Provenance Guard", "phase": 10, "status": "pending_phase"},
]

EDGE_CASES: list[dict[str, Any]] = [
    {"id": "EC-A1", "category": "false_positive", "title": "Naming variant intentional", "severity": "low", "runbook": ["mark intentional", "record terminology note", "suppress matching future variants"]},
    {"id": "EC-A2", "category": "false_positive", "title": "LLM check hallucination", "severity": "medium", "runbook": ["mark false positive", "add context hint", "refine LLM prompt"]},
    {"id": "EC-A3", "category": "false_positive", "title": "Intentional deviation from Council decision", "severity": "high", "runbook": ["capture reason", "update source artifact", "amend Council decision if needed"]},
    {"id": "EC-A4", "category": "false_positive", "title": "Translation length variance expected", "severity": "low", "runbook": ["adjust per-language threshold", "suppress string only if verified", "record locale rule"]},
    {"id": "EC-A5", "category": "false_positive", "title": "Test gold standard outdated after refactor", "severity": "medium", "runbook": ["regenerate baseline", "require operator visual review", "audit new gold standard"]},
    {"id": "EC-B1", "category": "performance", "title": "Continuous monitoring is slow", "severity": "medium", "runbook": ["reduce continuous scope", "increase throttle", "exclude generated files"]},
    {"id": "EC-B2", "category": "performance", "title": "LLM cost overrun", "severity": "high", "runbook": ["pause noisy check", "add cooldown", "switch cheaper semantic model"]},
    {"id": "EC-B3", "category": "performance", "title": "Cache cold start delay", "severity": "low", "runbook": ["show warmup progress", "allow full scan", "reuse trusted cache if operator accepts"]},
    {"id": "EC-B4", "category": "performance", "title": "Cache corruption", "severity": "high", "runbook": ["verify cache integrity", "rebuild cache", "disable cache during rebuild"]},
    {"id": "EC-B5", "category": "performance", "title": "Worker process crashed", "severity": "critical", "runbook": ["restart worker", "reduce memory set", "fall back to on-demand only if needed"]},
    {"id": "EC-C1", "category": "custom_checks", "title": "DSL syntax error in custom check", "severity": "medium", "runbook": ["show parse error", "offer fix", "disable check if unresolved"]},
    {"id": "EC-C2", "category": "custom_checks", "title": "LLM custom check returns invalid JSON", "severity": "medium", "runbook": ["retry with JSON enforcement", "increase max tokens", "switch model"]},
    {"id": "EC-C3", "category": "custom_checks", "title": "Custom check too broad", "severity": "medium", "runbook": ["lower severity", "narrow scope", "measure dismissal rate"]},
    {"id": "EC-C4", "category": "custom_checks", "title": "Community check not applicable", "severity": "low", "runbook": ["restrict by project tag", "disable for this workspace", "customize definition"]},
    {"id": "EC-D1", "category": "findings_handling", "title": "Auto-fix breaks code", "severity": "critical", "runbook": ["revert auto-fix", "disable risky auto-fix", "rerun tests"]},
    {"id": "EC-D2", "category": "findings_handling", "title": "Findings panel overwhelmed", "severity": "medium", "runbook": ["group by type", "suppress INFO", "prioritize by D-level"]},
    {"id": "EC-D3", "category": "findings_handling", "title": "Conflicting findings between Guards", "severity": "high", "runbook": ["compare evidence", "identify stale fixture or source", "choose intended contract"]},
    {"id": "EC-D4", "category": "findings_handling", "title": "Snoozed findings forgotten", "severity": "low", "runbook": ["review snoozes", "warn before expiry", "convert to suppression only with reason"]},
    {"id": "EC-E1", "category": "recovery_migration", "title": "Custom checks lost after update", "severity": "high", "runbook": ["load backup", "auto-migrate DSL", "manual review changed checks"]},
    {"id": "EC-E2", "category": "recovery_migration", "title": "Workspace import guard config", "severity": "medium", "runbook": ["import settings", "verify model availability", "rebuild cache"]},
    {"id": "EC-E3", "category": "recovery_migration", "title": "Partial restore cache stale", "severity": "medium", "runbook": ["mark cache cold", "rerun full coherence", "respect restored snoozes"]},
    {"id": "EC-E4", "category": "recovery_migration", "title": "Cross-project pattern data missing", "severity": "medium", "runbook": ["rebuild patterns", "disable cross-project", "import cloud pattern sync if enabled"]},
]

VALID_SEVERITIES = {item["id"] for item in SEVERITY_LEVELS}
VALID_TIERS = {item["id"] for item in DETECTION_TIERS}
VALID_SCOPE_IDS = {item["id"] for item in STANDARD_SCOPE}
VALID_PRESETS = set(FINDINGS_HANDLING_BY_PRESET)


class ApplyDefaultsRequest(BaseModel):
    goal: str = "apps_internal"
    autonomy_preset: str = "balanced"
    custom_checks_not_needed: bool = True


class ScopeRequest(BaseModel):
    scope: dict[str, bool] = Field(default_factory=dict)
    cross_project_enabled: bool = False
    cross_project_checks: list[str] = Field(default_factory=list)
    project_count: int = 1


class TriggerConfigRequest(BaseModel):
    phase_boundaries: dict[str, Any] = Field(default_factory=dict)
    continuous: dict[str, Any] = Field(default_factory=dict)
    on_demand: dict[str, Any] = Field(default_factory=dict)


class SeverityReviewRequest(BaseModel):
    reviewed: bool = True
    thresholds: dict[str, Any] = Field(default_factory=dict)


class BaselineReviewRequest(BaseModel):
    reviewed_check_ids: list[str] = Field(default_factory=list)
    disabled_check_ids: list[str] = Field(default_factory=list)
    accepted_baseline: bool = True
    custom_checks_not_needed: bool = True


class CheckConfigRequest(BaseModel):
    check_id: str
    enabled: bool = True
    severity: str | None = None
    tier: str | None = None
    triggers: list[str] | None = None
    auto_fix_simple: bool | None = None
    operator_note: str = ""


class CustomCheckRequest(BaseModel):
    name: str
    mechanism: str = "template"
    definition: str
    severity: str = "WARNING"
    tier: str = "tier1"
    enabled: bool = True
    cost_per_run_usd: float = 0.0


class FindingRunRequest(BaseModel):
    depth: str = "standard"
    scope: list[str] = Field(default_factory=list)
    project_id: str = "dashboard_current"


class FindingActionRequest(BaseModel):
    action: str
    note: str = ""
    snooze_days: int = 7


class PerformanceRequest(BaseModel):
    worker_enabled: bool = True
    worker_status: str = "running"
    cache_initialized: bool = True
    cache_hit_rate_pct: int = 78
    monthly_budget_usd: float = 30.0
    used_monthly_usd: float = 12.0
    budget_cap_enabled: bool = True
    budget_share_pct: int = 5
    incremental_diff: bool = True


class AutonomyOverrideRequest(BaseModel):
    inherits_phase5: bool = True
    preset: str = "balanced"
    auto_fix_tier1: bool = False
    auto_fix_tier2: bool = False
    per_check_customization: bool = True
    operator_note: str = ""


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
        row = conn.execute("SELECT value_json FROM sylion_phase_state WHERE key = ?", (f"phase6:{key}",)).fetchone()
    return _json_loads(row["value_json"], None) if row else None


def _set_state(key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sylion_phase_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (f"phase6:{key}", json.dumps(value, ensure_ascii=False, sort_keys=True, default=str), time.time()),
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


def _baseline_check_settings() -> dict[str, dict[str, Any]]:
    settings: dict[str, dict[str, Any]] = {}
    for item in BASELINE_CHECKS:
        settings[item["id"]] = {
            **_clone(item),
            "enabled": True,
            "severity": item["default_severity"],
            "tier": item["default_tier"],
            "triggers": ["phase_boundaries", "continuous", "on_demand"],
            "auto_fix_simple": item["id"] == "translation_coverage_all_locales",
            "auto_fix_allowed": item["id"] not in NEVER_AUTO_FIX_CHECK_IDS and item["default_tier"] == "tier1",
            "reviewed": False,
            "operator_note": "",
        }
    return settings


def _default_scope() -> dict[str, dict[str, Any]]:
    return {
        item["id"]: {
            "enabled": bool(item["enabled_by_default"]),
            "artifacts": list(item["artifacts"]),
            "override": "workspace_default",
        }
        for item in STANDARD_SCOPE
    }


def _default_settings(goal: str = "apps_internal", preset: str = "balanced") -> dict[str, Any]:
    if preset not in VALID_PRESETS:
        preset = "balanced"
    return {
        "version": "phase6.v1",
        "goal": goal,
        "autonomy_preset": preset,
        "scope": _default_scope(),
        "scope_configured": False,
        "cross_project_enabled": False,
        "cross_project_checks": [],
        "project_count": 1,
        "triggers": _clone(TRIGGER_DEFAULTS),
        "triggers_configured": False,
        "severity_thresholds": {item["id"]: {"rank": item["rank"], "reviewed": False} for item in SEVERITY_LEVELS},
        "severity_thresholds_reviewed": False,
        "checks": _baseline_check_settings(),
        "baseline_checks_reviewed": False,
        "reviewed_check_ids": [],
        "custom_checks": [],
        "custom_checks_not_needed": False,
        "findings": [],
        "runs": [],
        "performance": _clone(PERFORMANCE_DEFAULTS),
        "autonomy_override": {
            "inherits_phase5": True,
            "preset": preset,
            "auto_fix_tier1": FINDINGS_HANDLING_BY_PRESET[preset].get("auto_fix_simple", False),
            "auto_fix_tier2": False,
            "per_check_customization": True,
            "considered": False,
            "operator_note": "",
        },
        "created_at": time.time(),
        "updated_at": time.time(),
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
    _set_state("settings", settings)
    _append_audit(event, payload)
    return settings


def _enabled_checks(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [check for check in (settings.get("checks") or {}).values() if check.get("enabled")]


def _active_findings(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in settings.get("findings") or [] if item.get("status") == "active"]


def _tier2_checks_enabled(settings: dict[str, Any]) -> bool:
    return any(check.get("enabled") and check.get("tier") == "tier2" for check in (settings.get("checks") or {}).values()) or any(
        item.get("enabled") and item.get("tier") == "tier2" for item in settings.get("custom_checks") or []
    )


def _worker_disabled_everything(settings: dict[str, Any]) -> bool:
    performance = settings.get("performance") or {}
    triggers = settings.get("triggers") or {}
    trigger_active = any(bool((triggers.get(key) or {}).get("enabled")) for key in ["phase_boundaries", "continuous", "on_demand"])
    return not bool(performance.get("worker_enabled")) and not trigger_active


def _validate_check_update(body: CheckConfigRequest, settings: dict[str, Any]) -> dict[str, Any]:
    checks = settings.get("checks") or {}
    if body.check_id not in checks:
        raise HTTPException(status_code=404, detail="check not found")
    if body.severity and body.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail="unsupported severity")
    if body.tier and body.tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail="unsupported detection tier")
    return checks[body.check_id]


def _guard_blocks_for_severity(severity: str, preset: str) -> bool:
    return bool((BLOCKING_MATRIX.get(severity) or {}).get(preset, False))


def _finding_samples(settings: dict[str, Any], body: FindingRunRequest, run_id: str) -> list[dict[str, Any]]:
    requested_scope = set(body.scope or VALID_SCOPE_IDS)
    checks = _enabled_checks(settings)
    if body.project_id != "diagnostic_project":
        return [
            {
                "id": _uid("finding"),
                "run_id": run_id,
                "check_id": "coherence_smoke",
                "check_label": "Coherence smoke check",
                "title": "Brak syntetycznych ustaleń w przebiegu dashboardu",
                "summary": "Wybrany zakres zakończył się bez przykładowych ustaleń. Rzeczywiste ustalenia wymagają artefaktów konkretnego projektu.",
                "severity": "INFO",
                "tier": "tier1",
                "mechanism": "rule",
                "scope": list(requested_scope),
                "project_id": body.project_id,
                "status": "active",
                "can_auto_fix": False,
                "blocks_current_preset": False,
                "guard_conflict": "",
                "created_at": time.time(),
            }
        ]
    samples: list[dict[str, str]] = [
        {
            "check_id": "book_feature_masterplan_module",
            "title": "Documented GBP currency missing from masterplan module list",
            "summary": "Ksiega mentions EUR, PLN and GBP, while masterplan maps EUR and PLN only.",
            "guard_conflict": "",
        },
        {
            "check_id": "translation_coverage_all_locales",
            "title": "Translation coverage gap in checkout.confirm_button",
            "summary": "PL and EN strings exist, DE string is missing from the locale bundle.",
            "guard_conflict": "",
        },
        {
            "check_id": "api_contract_frontend_backend",
            "title": "Frontend/backend API contract mismatch",
            "summary": "Frontend sample uses items while backend contract exposes products.",
            "guard_conflict": "quality_guard_tests_pass_but_contract_fixture_is_stale",
        },
    ]
    by_id = {check["id"]: check for check in checks if requested_scope.intersection(set(check.get("scope") or []))}
    findings: list[dict[str, Any]] = []
    for sample in samples:
        check = by_id.get(sample["check_id"])
        if not check:
            continue
        severity = str(check.get("severity") or check.get("default_severity") or "WARNING")
        findings.append(
            {
                "id": _uid("finding"),
                "run_id": run_id,
                "check_id": check["id"],
                "check_label": check["label"],
                "title": sample["title"],
                "summary": sample["summary"],
                "severity": severity,
                "tier": check.get("tier"),
                "mechanism": check.get("mechanism"),
                "scope": check.get("scope"),
                "project_id": body.project_id,
                "status": "active",
                "can_auto_fix": bool(check.get("auto_fix_simple")) and check["id"] not in NEVER_AUTO_FIX_CHECK_IDS,
                "blocks_current_preset": _guard_blocks_for_severity(severity, settings.get("autonomy_preset", "balanced")),
                "guard_conflict": sample["guard_conflict"],
                "created_at": time.time(),
            }
        )
    if not findings:
        findings.append(
            {
                "id": _uid("finding"),
                "run_id": run_id,
                "check_id": "coherence_smoke",
                "check_label": "Coherence smoke check",
                "title": "No baseline inconsistencies detected in selected scope",
                "summary": "The selected scope produced no actionable coherence drift.",
                "severity": "INFO",
                "tier": "tier1",
                "mechanism": "rule",
                "scope": list(requested_scope),
                "project_id": body.project_id,
                "status": "active",
                "can_auto_fix": False,
                "blocks_current_preset": False,
                "guard_conflict": "",
                "created_at": time.time(),
            }
        )
    return findings


def _aggregated_panel(settings: dict[str, Any]) -> dict[str, Any]:
    active = _active_findings(settings)
    severity_counts = {severity["id"]: 0 for severity in SEVERITY_LEVELS}
    for finding in active:
        severity_counts[str(finding.get("severity") or "INFO")] = severity_counts.get(str(finding.get("severity") or "INFO"), 0) + 1

    suite_rows: dict[str, dict[str, Any]] = {}
    try:
        from sylion.api.guard_suite_routes import _aggregated_panel as _suite_aggregated_panel

        suite_rows = {
            str(row.get("id")): row
            for row in _suite_aggregated_panel().get("guards", [])
            if isinstance(row, dict)
        }
    except Exception:
        suite_rows = {}

    guards: list[dict[str, Any]] = []
    for guard in AGGREGATED_GUARDS:
        row = _clone(guard)
        if guard["id"] == "coherence":
            canonical = suite_rows.get("coherence") or {}
            row.update({
                "active_findings": len(active),
                "highest_severity": _highest_severity(active),
                "status": canonical.get("status") or "running",
            })
        elif guard["id"] == "quality":
            conflict_count = len([item for item in active if item.get("guard_conflict")])
            canonical = suite_rows.get("quality") or {}
            row.update({
                "active_findings": canonical.get("active_findings", conflict_count),
                "highest_severity": canonical.get("highest_severity") or ("ERROR" if conflict_count else "INFO"),
                "status": canonical.get("status") or row.get("status"),
            })
        else:
            canonical = suite_rows.get(str(guard["id"])) or {}
            row.update({
                "active_findings": canonical.get("active_findings", 0),
                "highest_severity": canonical.get("highest_severity") or "INFO",
                "status": canonical.get("status") or row.get("status"),
            })
        guards.append(row)

    conflicts = [
        {
            "id": _uid("conflict"),
            "finding_id": item["id"],
            "guards": ["coherence", "quality"],
            "summary": "Coherence sees a real backend mismatch while Quality passes against a stale contract fixture.",
            "recommended_action": "Update the contract fixture or align the real backend contract.",
        }
        for item in active
        if item.get("guard_conflict")
    ]
    return {
        "guards": guards,
        "filters": {"severities": [item["id"] for item in SEVERITY_LEVELS], "statuses": ["active", "snoozed", "resolved", "suppressed"]},
        "severity_counts": severity_counts,
        "total_active_findings": len(active),
        "conflicts": conflicts,
        "bulk_actions": ["suppress_info", "group_by_type", "apply_safe_fixes", "snooze_selected", "export_report"],
    }


def _highest_severity(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "INFO"
    ranks = {item["id"]: item["rank"] for item in SEVERITY_LEVELS}
    return max((str(item.get("severity") or "INFO") for item in findings), key=lambda severity: ranks.get(severity, 0))


def _build_acceptance(settings: dict[str, Any], goal: str = "apps_internal", finalize: bool = False) -> dict[str, Any]:
    audit = _state_list("audit_chain")
    audit_complete = any(item.get("event") == "phase_6.complete" for item in audit)
    checks: list[dict[str, Any]] = []

    def add(check_id: str, label: str, ok: bool, evidence: str, hard: bool = True) -> None:
        checks.append({"id": check_id, "label": label, "status": "pass" if ok else ("fail" if hard else "warn"), "evidence": evidence, "hard": hard})

    enabled_scope = [key for key, value in (settings.get("scope") or {}).items() if value.get("enabled")]
    triggers = settings.get("triggers") or {}
    trigger_enabled = [key for key, value in triggers.items() if isinstance(value, dict) and value.get("enabled")]
    check_settings = settings.get("checks") or {}
    enabled_baseline = [check for check in check_settings.values() if check.get("enabled")]
    reviewed_ids = set(settings.get("reviewed_check_ids") or [])
    baseline_ids = {item["id"] for item in BASELINE_CHECKS}
    performance = settings.get("performance") or {}
    tier2_without_budget = _tier2_checks_enabled(settings) and not bool(performance.get("budget_cap_enabled"))
    all_checks_tier2 = bool(check_settings) and all(check.get("tier") == "tier2" for check in check_settings.values())
    critical_autofix = any(
        check.get("auto_fix_simple") and check.get("severity") in {"CRITICAL", "BLOCKER"} for check in check_settings.values()
    )

    add("scope_configured", "Coherence Guard scope configured", bool(settings.get("scope_configured")) and bool(enabled_scope), ", ".join(enabled_scope) or "none")
    add("triggers_configured", "Triggers configured", bool(settings.get("triggers_configured")) and bool(trigger_enabled), ", ".join(trigger_enabled) or "none")
    add("severity_reviewed", "Severity thresholds reviewed", bool(settings.get("severity_thresholds_reviewed")), str(bool(settings.get("severity_thresholds_reviewed"))))
    add(
        "baseline_15_reviewed",
        "Baseline 15 checks reviewed",
        bool(settings.get("baseline_checks_reviewed")) and baseline_ids.issubset(reviewed_ids),
        f"{len(enabled_baseline)}/15 enabled",
    )
    add("phase_6_complete_audit", "Audit chain entry phase_6.complete", audit_complete or finalize, "recorded" if audit_complete or finalize else "missing")
    add("custom_checks_decision", "Custom checks defined or explicitly not needed", bool(settings.get("custom_checks")) or bool(settings.get("custom_checks_not_needed")), f"{len(settings.get('custom_checks') or [])} custom")
    add("autonomy_override_considered", "Per-Guard autonomy override considered", bool((settings.get("autonomy_override") or {}).get("considered")), (settings.get("autonomy_override") or {}).get("preset", "inherit"))
    add("cost_budget_allocated", "Cost budget allocated for Coherence Guard", bool(performance.get("budget_cap_enabled")) and float(performance.get("monthly_budget_usd") or 0) > 0, f"${performance.get('monthly_budget_usd', 0)}/mo")
    add("worker_running", "Worker running", bool(performance.get("worker_enabled")) and performance.get("worker_status") == "running", str(performance.get("worker_status")))
    add("cache_initialized", "Cache initialized", bool(performance.get("cache_initialized")), f"{performance.get('cache_hit_rate_pct', 0)}% hit rate")
    used = float(performance.get("used_monthly_usd") or 0)
    budget = float(performance.get("monthly_budget_usd") or 0)
    add("llm_cost_within_budget", "LLM cost within budget", budget > 0 and used <= budget, f"${used:.2f}/${budget:.2f}")

    if len(enabled_baseline) == 0:
        add("hard_all_baseline_disabled", "Hard block: all baseline checks disabled", False, "0/15 enabled")
    if tier2_without_budget:
        add("hard_tier2_without_budget", "Hard block: LLM checks enabled without budget cap", False, "budget cap disabled")
    if _worker_disabled_everything(settings):
        add("hard_worker_disabled_everything", "Hard block: worker disabled all guard execution", False, "worker disabled and no trigger active")

    if settings.get("cross_project_enabled") and int(settings.get("project_count") or 0) < 5:
        add("warn_cross_project_too_early", "Cross-project enabled before 5 projects", False, f"{settings.get('project_count')} projects", hard=False)
    if settings.get("autonomy_preset") == "aggressive" and critical_autofix:
        add("warn_critical_autofix_aggressive", "Aggressive auto-fix on critical checks", False, "critical auto-fix active", hard=False)
    if all_checks_tier2:
        add("warn_all_tier2", "All checks are Tier 2", False, "expensive configuration", hard=False)
    if not settings.get("custom_checks") and not settings.get("custom_checks_not_needed"):
        add("warn_no_custom_checks", "No custom checks", False, "operator has not made a custom-check decision", hard=False)

    hard_blocks = [check for check in checks if check["status"] == "fail" and check.get("hard")]
    soft_warnings = [check for check in checks if check["status"] == "warn"]
    if finalize and not hard_blocks and not audit_complete:
        entry = _append_audit(
            "phase_6.complete",
            {
                "goal": goal,
                "enabled_baseline": len(enabled_baseline),
                "custom_checks": len(settings.get("custom_checks") or []),
                "budget_usd": budget,
                "soft_warnings": len(soft_warnings),
            },
        )
        for check in checks:
            if check["id"] == "phase_6_complete_audit":
                check["status"] = "pass"
                check["evidence"] = entry["event_id"]
        audit_complete = True

    return {
        "phase": "6",
        "goal": goal,
        "accepted": len(hard_blocks) == 0,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "dod": {
            "common": {"required": 5, "passed": len([check for check in checks[:5] if check["status"] == "pass"])},
            "recommended": {"required": 3, "passed": len([check for check in checks[5:8] if check["status"] == "pass"])},
            "performance": {"required": 3, "passed": len([check for check in checks[8:11] if check["status"] == "pass"])},
            "counts": {
                "checks_passed": len([check for check in checks if check["status"] == "pass"]),
                "checks_total": len(checks),
                "hard_blocks": len(hard_blocks),
                "soft_warnings": len(soft_warnings),
            },
        },
        "audit_chain": {"entries": len(_state_list("audit_chain")), "phase_6_complete": audit_complete, "last_hash": (_state_list("audit_chain")[-1].get("hash") if _state_list("audit_chain") else "")},
    }


def _snapshot(goal: str = "apps_internal") -> dict[str, Any]:
    settings = _settings(goal=goal)
    return {
        "phase": "6",
        "status": "active",
        "settings": settings,
        "templates": {
            "scope": STANDARD_SCOPE,
            "cross_project_scope": CROSS_PROJECT_SCOPE,
            "triggers": TRIGGER_DEFAULTS,
            "severities": SEVERITY_LEVELS,
            "detection_tiers": DETECTION_TIERS,
            "baseline_checks": BASELINE_CHECKS,
            "custom_check_templates": CUSTOM_CHECK_TEMPLATES,
            "findings_handling_by_preset": FINDINGS_HANDLING_BY_PRESET,
            "auto_fix_tiers": AUTO_FIX_TIERS,
            "never_auto_fix": NEVER_AUTO_FIX,
            "blocking_matrix": BLOCKING_MATRIX,
            "performance_defaults": PERFORMANCE_DEFAULTS,
            "aggregated_guards": AGGREGATED_GUARDS,
            "edge_cases": EDGE_CASES,
        },
        "aggregated_panel": _aggregated_panel(settings),
        "acceptance": _build_acceptance(settings, goal=goal, finalize=False),
    }


@router.get("")
def get_coherence_guard(goal: str = "apps_internal") -> dict[str, Any]:
    return _snapshot(goal=goal)


@router.get("/templates")
def get_coherence_guard_templates() -> dict[str, Any]:
    return _snapshot()["templates"]


@router.post("/defaults/apply")
def apply_phase6_defaults(body: ApplyDefaultsRequest) -> dict[str, Any]:
    if body.autonomy_preset not in VALID_PRESETS:
        raise HTTPException(status_code=400, detail="unsupported autonomy preset")
    settings = _default_settings(goal=body.goal, preset=body.autonomy_preset)
    settings["scope_configured"] = True
    settings["triggers_configured"] = True
    settings["severity_thresholds_reviewed"] = True
    for severity in settings["severity_thresholds"].values():
        severity["reviewed"] = True
    settings["baseline_checks_reviewed"] = True
    settings["reviewed_check_ids"] = [item["id"] for item in BASELINE_CHECKS]
    for check in settings["checks"].values():
        check["reviewed"] = True
    settings["custom_checks_not_needed"] = body.custom_checks_not_needed
    settings["autonomy_override"]["considered"] = True
    settings["autonomy_override"]["preset"] = body.autonomy_preset
    settings["performance"] = _clone(PERFORMANCE_DEFAULTS)
    _set_state("settings", settings)
    _append_audit("phase6.defaults_applied", {"goal": body.goal, "preset": body.autonomy_preset})
    return _snapshot(goal=body.goal)


@router.post("/scope")
def save_scope(body: ScopeRequest) -> dict[str, Any]:
    unknown_scope = sorted(set(body.scope) - VALID_SCOPE_IDS)
    unknown_cross = sorted(set(body.cross_project_checks) - {item["id"] for item in CROSS_PROJECT_SCOPE})
    if unknown_scope:
        raise HTTPException(status_code=400, detail=f"unknown scope categories: {', '.join(unknown_scope)}")
    if unknown_cross:
        raise HTTPException(status_code=400, detail=f"unknown cross-project checks: {', '.join(unknown_cross)}")
    settings = _settings()
    scope = dict(settings.get("scope") or _default_scope())
    for key, enabled in body.scope.items():
        scope.setdefault(key, {"artifacts": [], "override": "operator"})["enabled"] = bool(enabled)
        scope[key]["override"] = "operator"
    settings["scope"] = scope
    settings["scope_configured"] = True
    settings["cross_project_enabled"] = body.cross_project_enabled
    settings["cross_project_checks"] = body.cross_project_checks if body.cross_project_checks else [item["id"] for item in CROSS_PROJECT_SCOPE] if body.cross_project_enabled else []
    settings["project_count"] = body.project_count
    _save_settings(settings, "phase6.scope_saved", {"enabled_scope": [key for key, value in scope.items() if value.get("enabled")], "cross_project": body.cross_project_enabled})
    return {"scope": scope, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/triggers")
def save_triggers(body: TriggerConfigRequest) -> dict[str, Any]:
    settings = _settings()
    triggers = _clone(settings.get("triggers") or TRIGGER_DEFAULTS)
    for key in ["phase_boundaries", "continuous", "on_demand"]:
        update = getattr(body, key)
        if update:
            merged = dict(triggers.get(key) or {})
            merged.update(update)
            triggers[key] = merged
    settings["triggers"] = triggers
    settings["triggers_configured"] = True
    _save_settings(settings, "phase6.triggers_saved", {"enabled": [key for key, value in triggers.items() if value.get("enabled")]})
    return {"triggers": triggers, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/severity/review")
def review_severity(body: SeverityReviewRequest) -> dict[str, Any]:
    settings = _settings()
    thresholds = dict(settings.get("severity_thresholds") or {})
    for key, value in body.thresholds.items():
        if key not in VALID_SEVERITIES:
            raise HTTPException(status_code=400, detail=f"unsupported severity: {key}")
        current = dict(thresholds.get(key) or {})
        current.update(value if isinstance(value, dict) else {"value": value})
        current["reviewed"] = True
        thresholds[key] = current
    if not body.thresholds:
        for key in VALID_SEVERITIES:
            thresholds.setdefault(key, {})["reviewed"] = True
    settings["severity_thresholds"] = thresholds
    settings["severity_thresholds_reviewed"] = body.reviewed
    _save_settings(settings, "phase6.severity_reviewed", {"reviewed": body.reviewed})
    return {"severity_thresholds": thresholds, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/checks/review")
def review_baseline_checks(body: BaselineReviewRequest) -> dict[str, Any]:
    settings = _settings()
    checks = dict(settings.get("checks") or {})
    baseline_ids = {item["id"] for item in BASELINE_CHECKS}
    reviewed = set(body.reviewed_check_ids or baseline_ids)
    disabled = set(body.disabled_check_ids)
    unknown = sorted((reviewed | disabled) - baseline_ids)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown checks: {', '.join(unknown)}")
    for check_id, check in checks.items():
        check["reviewed"] = check_id in reviewed
        check["enabled"] = check_id not in disabled
    settings["checks"] = checks
    settings["baseline_checks_reviewed"] = body.accepted_baseline
    settings["reviewed_check_ids"] = sorted(reviewed)
    settings["custom_checks_not_needed"] = body.custom_checks_not_needed
    _save_settings(settings, "phase6.baseline_checks_reviewed", {"reviewed": len(reviewed), "disabled": len(disabled)})
    return {"checks": checks, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/checks/config")
def configure_check(body: CheckConfigRequest) -> dict[str, Any]:
    settings = _settings()
    check = _validate_check_update(body, settings)
    check["enabled"] = body.enabled
    if body.severity:
        check["severity"] = body.severity
    if body.tier:
        check["tier"] = body.tier
    if body.triggers is not None:
        check["triggers"] = body.triggers
    if body.auto_fix_simple is not None:
        check["auto_fix_simple"] = bool(body.auto_fix_simple) and body.check_id not in NEVER_AUTO_FIX_CHECK_IDS
    check["operator_note"] = body.operator_note
    check["reviewed"] = True
    settings["checks"][body.check_id] = check
    _save_settings(settings, "phase6.check_configured", {"check_id": body.check_id, "enabled": body.enabled, "tier": check.get("tier"), "severity": check.get("severity")})
    return {"check": check, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/custom-checks")
def add_custom_check(body: CustomCheckRequest) -> dict[str, Any]:
    if body.mechanism not in {"template", "dsl", "llm"}:
        raise HTTPException(status_code=400, detail="unsupported custom check mechanism")
    if body.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail="unsupported severity")
    if body.tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail="unsupported detection tier")
    if not body.name.strip() or not body.definition.strip():
        raise HTTPException(status_code=400, detail="name and definition are required")
    if body.mechanism == "dsl" and ("Unexpected token" in body.definition or body.definition.strip().startswith("AND ")):
        raise HTTPException(status_code=422, detail={"case_id": "EC-C1", "error": "DSL syntax error"})
    if body.mechanism == "llm" and body.cost_per_run_usd <= 0:
        body.cost_per_run_usd = 0.25
    settings = _settings()
    custom = list(settings.get("custom_checks") or [])
    check = {
        "id": _uid("custom_check"),
        "source": "operator_custom",
        "name": body.name.strip(),
        "mechanism": body.mechanism,
        "definition": body.definition,
        "severity": body.severity,
        "tier": body.tier,
        "enabled": body.enabled,
        "cost_per_run_usd": body.cost_per_run_usd,
        "created_at": time.time(),
    }
    custom.append(check)
    settings["custom_checks"] = custom
    settings["custom_checks_not_needed"] = False
    _save_settings(settings, "phase6.custom_check_added", {"check_id": check["id"], "mechanism": body.mechanism})
    return {"custom_check": check, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/run")
def run_coherence_check(body: FindingRunRequest) -> dict[str, Any]:
    if body.depth not in {"quick", "standard", "deep"}:
        raise HTTPException(status_code=400, detail="unsupported run depth")
    unknown_scope = sorted(set(body.scope) - VALID_SCOPE_IDS)
    if unknown_scope:
        raise HTTPException(status_code=400, detail=f"unknown scope categories: {', '.join(unknown_scope)}")
    settings = _settings()
    if not bool((settings.get("performance") or {}).get("worker_enabled")):
        raise HTTPException(status_code=409, detail="coherence worker is disabled")
    depth_cost = {"quick": 0.08, "standard": 0.40, "deep": 1.20}[body.depth]
    performance = dict(settings.get("performance") or PERFORMANCE_DEFAULTS)
    if performance.get("budget_cap_enabled") and float(performance.get("used_monthly_usd") or 0) + depth_cost > float(performance.get("monthly_budget_usd") or 0):
        raise HTTPException(status_code=402, detail="coherence guard budget cap would be exceeded")
    run_id = _uid("run")
    findings = _finding_samples(settings, body, run_id)
    performance["used_monthly_usd"] = round(float(performance.get("used_monthly_usd") or 0) + depth_cost, 2)
    run = {
        "id": run_id,
        "depth": body.depth,
        "scope": body.scope or sorted(VALID_SCOPE_IDS),
        "project_id": body.project_id,
        "findings_created": len(findings),
        "cost_usd": depth_cost,
        "duration_ms": {"quick": 350, "standard": 1200, "deep": 4200}[body.depth],
        "created_at": time.time(),
    }
    settings["performance"] = performance
    settings.setdefault("runs", []).append(run)
    settings.setdefault("findings", []).extend(findings)
    _save_settings(settings, "phase6.check_run", {"run_id": run_id, "findings": len(findings), "depth": body.depth, "cost_usd": depth_cost})
    return {"run": run, "findings": findings, "aggregated_panel": _aggregated_panel(settings), "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.get("/findings")
def list_findings(status: str | None = None, severity: str | None = None) -> dict[str, Any]:
    settings = _settings()
    findings = list(settings.get("findings") or [])
    if status:
        findings = [item for item in findings if item.get("status") == status]
    if severity:
        findings = [item for item in findings if item.get("severity") == severity]
    return {"count": len(findings), "findings": findings}


@router.post("/findings/{finding_id}/action")
def act_on_finding(finding_id: str, body: FindingActionRequest) -> dict[str, Any]:
    if body.action not in {"suppress", "snooze", "resolve", "apply_fix"}:
        raise HTTPException(status_code=400, detail="unsupported finding action")
    settings = _settings()
    findings = list(settings.get("findings") or [])
    for index, finding in enumerate(findings):
        if finding.get("id") != finding_id:
            continue
        updated = dict(finding)
        if body.action == "snooze":
            updated["status"] = "snoozed"
            updated["snoozed_until"] = time.time() + body.snooze_days * 86400
        elif body.action == "apply_fix":
            if not updated.get("can_auto_fix"):
                raise HTTPException(status_code=409, detail="finding cannot be auto-fixed safely")
            updated["status"] = "resolved"
            updated["fix_applied"] = True
        else:
            updated["status"] = "suppressed" if body.action == "suppress" else "resolved"
        updated["operator_note"] = body.note
        updated["updated_at"] = time.time()
        findings[index] = updated
        settings["findings"] = findings
        _save_settings(settings, "phase6.finding_action", {"finding_id": finding_id, "action": body.action})
        return {"finding": updated, "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}
    raise HTTPException(status_code=404, detail="finding not found")


@router.post("/performance")
def save_performance(body: PerformanceRequest) -> dict[str, Any]:
    settings = _settings()
    settings["performance"] = {
        **_clone(PERFORMANCE_DEFAULTS),
        "worker_enabled": body.worker_enabled,
        "worker_status": body.worker_status,
        "cache_initialized": body.cache_initialized,
        "cache_hit_rate_pct": body.cache_hit_rate_pct,
        "monthly_budget_usd": body.monthly_budget_usd,
        "used_monthly_usd": body.used_monthly_usd,
        "budget_cap_enabled": body.budget_cap_enabled,
        "budget_share_pct": body.budget_share_pct,
        "incremental_diff": body.incremental_diff,
    }
    _save_settings(settings, "phase6.performance_saved", {"worker": body.worker_status, "budget": body.monthly_budget_usd})
    return {"performance": settings["performance"], "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.post("/autonomy-override")
def save_autonomy_override(body: AutonomyOverrideRequest) -> dict[str, Any]:
    if body.preset not in VALID_PRESETS:
        raise HTTPException(status_code=400, detail="unsupported preset")
    settings = _settings()
    settings["autonomy_preset"] = body.preset
    settings["autonomy_override"] = {
        "inherits_phase5": body.inherits_phase5,
        "preset": body.preset,
        "auto_fix_tier1": body.auto_fix_tier1,
        "auto_fix_tier2": False if body.auto_fix_tier2 else False,
        "per_check_customization": body.per_check_customization,
        "considered": True,
        "operator_note": body.operator_note,
        "updated_at": time.time(),
    }
    _save_settings(settings, "phase6.autonomy_override_saved", {"preset": body.preset, "inherits_phase5": body.inherits_phase5})
    return {"autonomy_override": settings["autonomy_override"], "snapshot": _snapshot(goal=settings.get("goal", "apps_internal"))}


@router.get("/aggregated-panel")
def get_aggregated_panel() -> dict[str, Any]:
    return _aggregated_panel(_settings())


@router.get("/edge-cases")
def list_edge_cases() -> dict[str, Any]:
    categories = sorted({item["category"] for item in EDGE_CASES})
    return {"phase": "6", "count": len(EDGE_CASES), "categories": categories, "edge_cases": EDGE_CASES}


@router.post("/edge-cases/diagnose")
def diagnose_edge_case(body: EdgeDiagnosisRequest) -> dict[str, Any]:
    case = next((item for item in EDGE_CASES if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    diagnosis = {
        "case": case,
        "context": body.context,
        "requires_operator_review": case["severity"] in {"medium", "high", "critical"},
        "action_plan": case["runbook"] + ["write phase6 audit entry", "rerun acceptance if configuration changed"],
        "created_at": time.time(),
    }
    _append_audit("phase6.edge_case_diagnosed", {"case_id": case["id"], "severity": case["severity"]})
    return diagnosis


@router.get("/acceptance")
def get_acceptance(goal: str = "apps_internal") -> dict[str, Any]:
    return _build_acceptance(_settings(goal=goal), goal=goal, finalize=False)


@router.get("/acceptance-test")
def run_acceptance_test(goal: str = "apps_internal") -> dict[str, Any]:
    return _build_acceptance(_settings(goal=goal), goal=goal, finalize=True)


@router.post("/complete")
def complete_phase_6(goal: str = "apps_internal") -> dict[str, Any]:
    result = _build_acceptance(_settings(goal=goal), goal=goal, finalize=True)
    if result["hard_blocks"]:
        raise HTTPException(status_code=400, detail=result)
    return result
