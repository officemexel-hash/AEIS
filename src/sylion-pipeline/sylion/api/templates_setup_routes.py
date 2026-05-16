"""Operator building-block setup for Phases 11-15.

This module covers Skills Library bootstrap and the four template/policy
families that must be ready before project inception starts in Phase 16.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.skills.executor import get_skills_executor
from sylion.skills.registry import get_skills_registry

router = APIRouter(prefix="/api/v1/templates-setup", tags=["Templates Setup"])


VALID_PHASES = {"skills", "council", "test-strategy", "deployment", "cost-policies"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _edge_cases(groups: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group_index, (category, titles) in enumerate(groups):
        letter = chr(ord("A") + group_index)
        for item_index, title in enumerate(titles, start=1):
            severity = "high" if any(word in title.lower() for word in ["lost", "corruption", "security", "hard cap", "timeout", "rollback fails"]) else "medium"
            items.append(
                {
                    "id": f"EC-{letter}{item_index}",
                    "category": category,
                    "title": title,
                    "severity": severity,
                    "runbook": ["classify impact", "choose closest baseline artifact", "apply operator override if needed", "write audit evidence"],
                }
            )
    return items


BASELINE_SKILLS = [
    ("skill.codegen.fastapi_route_from_openapi", "Generate FastAPI route from OpenAPI spec", "code_generation"),
    ("skill.codegen.react_component_from_props", "Generate React component from props spec", "code_generation"),
    ("skill.codegen.sql_to_sqlalchemy", "Convert SQL schema to SQLAlchemy ORM", "code_generation"),
    ("skill.codegen.migration_from_schema_diff", "Generate database migration from schema diff", "code_generation"),
    ("skill.codegen.rest_client_from_openapi", "Generate REST API client from OpenAPI", "code_generation"),
    ("skill.codegen.docker_container", "Generate Docker container from application", "code_generation"),
    ("skill.testing.pytest_from_signature", "Generate pytest unit tests from function signature", "testing"),
    ("skill.testing.playwright_from_story", "Generate Playwright E2E from user story", "testing"),
    ("skill.testing.fixtures_from_schema", "Generate test fixtures from schema", "testing"),
    ("skill.testing.human_ui_from_book", "Generate human-like UI scenario from Księga", "testing"),
    ("skill.testing.load_from_behavior", "Generate load test from user behavior model", "testing"),
    ("skill.eu.validate_polish_identifiers", "Validate Polish identifiers PESEL NIP REGON", "polish_eu"),
    ("skill.eu.generate_ksef_invoice", "Generate KSeF-compliant invoice", "polish_eu"),
    ("skill.eu.validate_gdpr_flow", "Validate GDPR data flow", "polish_eu"),
    ("skill.eu.translate_pl_en_de_fr_uk", "Translate between PL EN DE FR UK", "polish_eu"),
    ("skill.deploy.terraform_manifest", "Generate Terraform manifest for cloud", "deployment"),
    ("skill.deploy.kubernetes_manifests", "Generate Kubernetes manifests", "deployment"),
    ("skill.deploy.cicd_pipeline", "Generate CI/CD pipeline", "deployment"),
    ("skill.deploy.monitoring_alerting_config", "Generate monitoring and alerting config", "deployment"),
    ("skill.integration.stripe_payment", "Generate Stripe payment integration", "integration"),
    ("skill.integration.oauth2_flow", "Generate OAuth2 authentication flow", "integration"),
    ("skill.integration.secure_webhook_handler", "Generate webhook handler with security", "integration"),
    ("skill.docs.api_from_code", "Generate API documentation from code", "documentation"),
    ("skill.docs.changelog_from_commits", "Generate user-facing changelog from commits", "documentation"),
    ("skill.docs.operator_runbook", "Generate operator runbook from architecture", "documentation"),
]


PHASE_EDGE_CASES = {
    "skills": _edge_cases(
        [
            ("skill_creation_issues", ["Skill prompt too generic", "Skill output schema mismatch", "Skill cost spikes", "Skill conflicts with another skill"]),
            ("skill_discovery_issues", ["Discovery noise too many suggestions", "Discovery missing obvious patterns", "Discovery suggests wrong abstraction", "Marketplace skill better than auto-suggested"]),
            ("versioning_updates", ["Auto-update breaks projects", "Pinned skill incompatible with new AEIS", "Deprecated skill still in use", "Marketplace skill author abandoned"]),
            ("skill_execution", ["Skill output validation fails", "Skill timeout", "Skill cost over budget", "Skill output triggers Security Guard"]),
            ("recovery_migration", ["Skills library lost", "Workspace import skills", "Skill rollback", "Marketplace offline"]),
        ]
    ),
    "council": _edge_cases(
        [
            ("template_fit", ["No template matches project", "Template too heavy for project", "Template missing role", "Template applies but operator disagrees"]),
            ("voting_issues", ["Quorum not met", "Tied vote no tie-breaker", "Critic veto unexpected", "Specialist override disagreement"]),
            ("template_management", ["Template version conflict", "Custom template lost after AEIS update", "Template dependencies skills knowledge bases", "Template testing on sample fails"]),
            ("recovery", ["Template database corruption", "Workspace import templates", "Cross-workspace template sharing"]),
        ]
    ),
    "test-strategy": _edge_cases(
        [
            ("strategy_fit", ["No strategy matches", "Strategy too heavy for project", "Strategy too light for customer requirements"]),
            ("coverage_issues", ["Coverage target unrealistic", "Coverage gaming low-quality tests", "Critical paths uncovered", "Coverage tool inconsistencies"]),
            ("test_execution", ["Flaky tests", "Test environment unavailable", "Test data corruption", "Tests slow"]),
            ("human_like_ui", ["Customer-side data needed", "Visual regression false positives"]),
            ("recovery", ["Strategy lost after update", "Migration test history"]),
        ]
    ),
    "deployment": _edge_cases(
        [
            ("deploy_stages", ["Canary stage fails", "Pre-deploy gate timeout", "Full rollout slow", "DNS propagation issue"]),
            ("rollback", ["Automatic rollback triggered", "Rollback fails", "Rollback after data migration", "Customer-facing impact"]),
            ("edge_fleet", ["Mixed update results", "Customer-side network issues", "Hardware diversity different Pi versions"]),
            ("air_gapped", ["Manual transfer delays", "Sync conflicts"]),
            ("recovery", ["Template corruption", "Customer-specific deployment requirements"]),
        ]
    ),
    "cost-policies": _edge_cases(
        [
            ("budget_caps", ["Hard cap reached mid-deploy", "Customer-funded overrun", "Annual budget exhausted", "Currency fluctuation EUR USD"]),
            ("approval_workflows", ["Customer does not respond", "Operator absent customer needs approval", "Approval timeout during critical work", "Multi-party approvals conflict"]),
            ("customer_specific", ["Customer dispute charges", "Customer requests refund", "Multi-customer project", "Customer-side credentials issues"]),
            ("reporting_issues", ["Customer report shows incorrect data", "Vendor pass-through delayed"]),
            ("recovery", ["Policy corruption"]),
        ]
    ),
}


PHASE_CATALOG: dict[str, dict[str, Any]] = {
    "skills": {
        "phase": "11",
        "title": "Skills Library Bootstrap",
        "route_title": "Skills Library - Faza 11",
        "summary": "4 skill types, 25 baseline system skills, creation workflows, discovery, versioning and marketplace settings.",
        "artifact_label": "skills",
        "baseline_target": 25,
        "artifact_groups": [
            {"id": "code_generation", "label": "Code Generation", "items": [item[1] for item in BASELINE_SKILLS if item[2] == "code_generation"]},
            {"id": "testing", "label": "Testing", "items": [item[1] for item in BASELINE_SKILLS if item[2] == "testing"]},
            {"id": "polish_eu", "label": "Polish/EU Specific", "items": [item[1] for item in BASELINE_SKILLS if item[2] == "polish_eu"]},
            {"id": "deployment", "label": "Deployment", "items": [item[1] for item in BASELINE_SKILLS if item[2] == "deployment"]},
            {"id": "integration", "label": "Integration", "items": [item[1] for item in BASELINE_SKILLS if item[2] == "integration"]},
            {"id": "documentation", "label": "Documentation", "items": [item[1] for item in BASELINE_SKILLS if item[2] == "documentation"]},
        ],
        "artifacts": [
            {
                "id": skill_id,
                "name": name,
                "category": category,
                "type": "system",
                "version": "1.0.0",
                "trigger": "operator_or_council_task_match",
                "implementation": "llm_prompt_plus_schema",
                "cost_profile": "predictable",
                "quality_metrics": {"target_success_rate": 0.9, "schema_validated": True},
            }
            for skill_id, name, category in BASELINE_SKILLS
        ],
        "capabilities": [
            {"id": "skill_types", "label": "4 skill types", "items": ["system", "project", "personal", "imported"]},
            {"id": "creation_mechanisms", "label": "4 creation mechanisms", "items": ["from_scratch", "extract_project_pattern", "promote_project_skill", "import_or_fork_marketplace"]},
            {"id": "discovery_triggers", "label": "6 discovery triggers", "items": ["3+ repeated prompts", "3+ cross-project patterns", "single ad-hoc cost > $5", "low quality ad-hoc", "marketplace match", "library gap"]},
            {"id": "versioning", "label": "Versioning policy", "items": ["SemVer", "auto-update PATCH", "pin support", "deprecation workflow"]},
            {"id": "marketplace", "label": "Marketplace settings", "items": ["search enabled", "ratings visible", "import suggestions opt-in", "anonymous stats opt-in"]},
        ],
        "acceptance": [
            ("system_skills_available", "System skills baseline available", "25 skills"),
            ("creation_workflow_configured", "Skill creation workflow configured", "4 mechanisms"),
            ("discovery_enabled", "Discovery enabled", "6 triggers"),
            ("versioning_policy_set", "Versioning policy set", "SemVer + deprecation"),
            ("audit_complete", "Audit chain entry phase_11.complete", "phase_11.complete"),
        ],
        "optional": [
            ("marketplace_settings", "Marketplace settings", "search enabled"),
            ("personal_skills_count", "Personal skills count", "operator library accepts personal skills"),
            ("imported_skills_count", "Imported skills count", "marketplace import path enabled"),
        ],
    },
    "council": {
        "phase": "12",
        "title": "Council Templates",
        "route_title": "Council Templates - Faza 12",
        "summary": "8 council templates, voting structure, composition wizard and per-D-level scaling.",
        "artifact_label": "templates",
        "baseline_target": 8,
        "artifact_groups": [
            {"id": "d_level", "label": "D-level coverage", "items": ["D1-D2", "D3", "D3-D4", "D4-D5", "D5"]},
            {"id": "wizard", "label": "Composition wizard", "items": ["project_type", "industry", "compliance", "payment", "multilanguage", "D-level"]},
            {"id": "voting", "label": "Voting structure", "items": ["quorum", "chair tie-break", "critic veto", "specialist override"]},
        ],
        "artifacts": [
            {"id": "ct_minimal", "name": "Minimal", "d_levels": ["D1", "D2"], "roles": ["Planner", "Critic"], "cost_per_round_usd": 0.4, "applies_to": ["prototypes", "internal experiments"]},
            {"id": "ct_balanced_standard", "name": "Balanced Standard", "d_levels": ["D3"], "roles": ["Chair", "Planner", "Critic", "Security", "QA"], "cost_per_round_usd": 1.2, "applies_to": ["most projects"]},
            {"id": "ct_public_saas", "name": "Public SaaS", "d_levels": ["D3", "D4"], "roles": ["Chair", "Planner", "Critic", "Security", "UX", "QA", "Compliance GDPR"], "cost_per_round_usd": 1.8, "applies_to": ["customer-facing SaaS"]},
            {"id": "ct_public_saas_payment", "name": "Public SaaS with payment", "d_levels": ["D4", "D5"], "roles": ["Chair", "Planner", "Critic", "Security", "Payment Specialist", "UX", "Compliance GDPR", "Compliance PCI", "QA"], "cost_per_round_usd": 2.4, "applies_to": ["SaaS with Stripe/payment"]},
            {"id": "ct_cybersecurity", "name": "Cybersecurity", "d_levels": ["D4", "D5"], "roles": ["Chair", "Planner", "Critic", "Security", "Compliance", "Risk Assessor", "Encryption Auditor"], "cost_per_round_usd": 2.8, "applies_to": ["SYLION-style projects"]},
            {"id": "ct_research", "name": "Research", "d_levels": ["D1", "D2", "D3"], "roles": ["Chair", "Researcher", "Critic"], "cost_per_round_usd": 1.0, "applies_to": ["research", "ML experiments"]},
            {"id": "ct_internal_tool", "name": "Internal Tool", "d_levels": ["D1", "D2"], "roles": ["Planner", "QA"], "cost_per_round_usd": 0.3, "applies_to": ["internal tools", "low stakes"]},
            {"id": "ct_government_classified", "name": "Government/Classified", "d_levels": ["D5"], "roles": ["Chair", "Planner", "Critic", "Security deep", "Compliance KRI-PL", "Risk Assessor", "External Reviewer simulated", "Encryption Auditor"], "cost_per_round_usd": 4.2, "applies_to": ["TLP:RED workloads"], "hard_gated": True},
        ],
        "capabilities": [
            {"id": "template_mapping", "label": "Template-to-project mapping", "items": ["goal", "project_type", "D-level", "special_requirements"]},
            {"id": "d_level_scaling", "label": "Per-D-level scaling", "items": ["D1-D2 light", "D3 standard", "D4 production", "D5 hard gated"]},
            {"id": "composition_wizard", "label": "Composition wizard", "items": ["role recommendation", "cost estimate", "save as template", "sample test"]},
        ],
        "acceptance": [
            ("templates_configured", "Templates configured", "8 baseline"),
            ("template_mapping", "Template-to-project mapping", "goal/type/D-level"),
            ("d_level_scaling", "Per-D-level scaling", "D1-D5"),
            ("audit_complete", "Audit chain entry phase_12.complete", "phase_12.complete"),
        ],
        "optional": [
            ("custom_templates_count", "Custom templates count", "3 demo custom templates"),
            ("composition_wizard_tested", "Composition wizard tested", "sample fintech SaaS"),
        ],
    },
    "test-strategy": {
        "phase": "13",
        "title": "Test Strategy Templates",
        "route_title": "Test Strategy Templates - Faza 13",
        "summary": "5 baseline test strategies with mandatory L5 human-like UI coverage preserved.",
        "artifact_label": "strategies",
        "baseline_target": 5,
        "artifact_groups": [
            {"id": "levels", "label": "Test levels", "items": ["L1", "L2", "L3", "L4", "L5 mandatory"]},
            {"id": "quality_gates", "label": "Quality gates", "items": ["L5 fail blocks deploy", "coverage minimum", "P95 latency budget", "customer-specific tests"]},
        ],
        "artifacts": [
            {"id": "ts_minimal", "name": "Minimal", "levels": ["L1", "L2", "L5"], "coverage_pct": 60, "cost_per_build_usd": 3.5, "for": "internal tools"},
            {"id": "ts_standard", "name": "Standard", "levels": ["L1", "L2", "L3", "L5"], "coverage_pct": 80, "cost_per_build_usd": 8, "for": "most projects"},
            {"id": "ts_comprehensive", "name": "Comprehensive", "levels": ["L1", "L2", "L3", "L5", "L4 pre-prod"], "coverage_pct": 85, "cost_per_build_usd": 15, "for": "production"},
            {"id": "ts_critical", "name": "Critical", "levels": ["L1", "L2", "L3", "L4", "L5"], "coverage_pct": 90, "critical_paths_pct": 95, "cost_per_build_usd": 30, "mutation_testing": True, "for": "D4-D5 production"},
            {"id": "ts_research", "name": "Research", "levels": ["L1 light", "L5"], "coverage_pct": 50, "cost_per_build_usd": 5, "for": "research and experiments"},
        ],
        "capabilities": [
            {"id": "custom_strategy_builder", "label": "Custom strategy builder", "items": ["project type", "D-level", "customer-specific", "levels", "quality gates"]},
            {"id": "mandatory_human_like", "label": "Mandatory human-like UI", "items": ["L5 preserved in every strategy", "25-40 scenarios", "AEIS observation engine"]},
            {"id": "project_mapping", "label": "Strategy-to-project mapping", "items": ["minimal", "standard", "comprehensive", "critical", "research"]},
        ],
        "acceptance": [
            ("strategies_configured", "Strategies configured", "5 baseline"),
            ("mandatory_human_like_preserved", "Mandatory human-like preserved", "L5 in all strategies"),
            ("strategy_project_mapping", "Strategy-to-project mapping", "project type + D-level"),
            ("audit_complete", "Audit chain entry phase_13.complete", "phase_13.complete"),
        ],
        "optional": [],
    },
    "deployment": {
        "phase": "14",
        "title": "Deployment Templates",
        "route_title": "Deployment Templates - Faza 14",
        "summary": "6 deployment templates with per-environment patterns, rollback and production hard gates.",
        "artifact_label": "deployment templates",
        "baseline_target": 6,
        "artifact_groups": [
            {"id": "environment_patterns", "label": "Per-environment patterns", "items": ["dev/staging", "small production", "customer traffic", "zero downtime", "sovereign", "edge fleet"]},
            {"id": "rollback", "label": "Rollback strategies", "items": ["automatic triggers", "manual trigger", "restore previous version", "notify operator", "audit"]},
            {"id": "hard_gates", "label": "Hard gates", "items": ["production deploy", "operator approval", "security clean", "tests pass"]},
        ],
        "artifacts": [
            {"id": "dt_simple", "name": "Simple Deploy", "for": "dev/staging environments", "time": "5-15 min", "rollback": "previous release restore"},
            {"id": "dt_rolling", "name": "Rolling Deploy", "for": "small production, no canary infrastructure", "time": "15-45 min", "rollback": "rolling reverse"},
            {"id": "dt_canary", "name": "Canary Deploy", "for": "production with customer traffic", "time": "90-180 min", "rollback": "automatic rollback on metrics"},
            {"id": "dt_blue_green", "name": "Blue-Green", "for": "zero-downtime requirements", "time": "30-60 min", "rollback": "traffic swap back"},
            {"id": "dt_air_gapped", "name": "Air-Gapped Deploy", "for": "sovereign environments without internet", "time": "operator-dependent", "rollback": "manual package restore"},
            {"id": "dt_edge_fleet", "name": "Edge Fleet Deploy", "for": "customer-side RPi/edge updates", "time": "fleet-size dependent", "rollback": "per-device staged restore"},
        ],
        "capabilities": [
            {"id": "stages", "label": "Deploy stages", "items": ["pre_deploy", "canary_5pct", "canary_25pct", "canary_50pct", "full_rollout", "post_deploy"]},
            {"id": "rollback_triggers", "label": "Rollback triggers", "items": ["error_rate > 1%", "latency_p95 > 2x", "critical_alert", "operator command"]},
            {"id": "production_gate", "label": "Production hard gate", "items": ["operator_approval", "operator_final_approval"]},
        ],
        "acceptance": [
            ("templates_configured", "Templates configured", "6 baseline"),
            ("environment_patterns", "Per-environment patterns", "phase 3 environments"),
            ("rollback_strategies", "Rollback strategies", "automatic + manual"),
            ("production_hard_gate", "Hard gate preserved", "production deploy"),
            ("audit_complete", "Audit chain entry phase_14.complete", "phase_14.complete"),
        ],
        "optional": [],
    },
    "cost-policies": {
        "phase": "15",
        "title": "Cost & Budget Policies",
        "route_title": "Cost & Budget Policies - Faza 15",
        "summary": "5 policies connecting Phase 4 budget templates with Phase 7 Cost Guard enforcement.",
        "artifact_label": "cost policies",
        "baseline_target": 5,
        "artifact_groups": [
            {"id": "budget_rules", "label": "Budget rules", "items": ["hard cap", "soft cap", "customer visible", "currency"]},
            {"id": "approvals", "label": "Approval workflows", "items": ["spike approval", "overrun approval", "customer notification"]},
            {"id": "reporting", "label": "Reporting integration", "items": ["daily monitoring", "weekly trend", "closure report", "customer-facing"]},
        ],
        "artifacts": [
            {"id": "cp_internal", "name": "Internal", "hard_cap": "workspace budget", "approval": "operator only", "reporting": "operator-internal"},
            {"id": "cp_strict_customer", "name": "Strict Customer", "hard_cap": "contracted amount", "approval": "operator + customer notify", "reporting": "customer-facing transparent"},
            {"id": "cp_flexible_customer", "name": "Flexible Customer", "hard_cap": "contracted amount x1.5", "approval": "operator + customer override", "reporting": "customer-facing summary"},
            {"id": "cp_research", "name": "Research", "hard_cap": "monthly research allocation", "approval": "operator only", "reporting": "monthly research summary"},
            {"id": "cp_experimental", "name": "Experimental", "hard_cap": "$20 per project", "approval": "auto for spike <$2", "reporting": "aggregate weekly"},
        ],
        "capabilities": [
            {"id": "customer_specific", "label": "Customer-specific policies", "items": ["annual budget", "per-project cap", "overrun policy", "currency", "EU data residency"]},
            {"id": "cost_guard_integration", "label": "Cost Guard integration", "items": ["limits", "anomaly thresholds", "closure reports", "vendor pass-through"]},
            {"id": "approval_workflows", "label": "Approval workflows", "items": ["operator", "customer notify", "timeout", "fallback"]},
        ],
        "acceptance": [
            ("policies_configured", "Policies configured", "5 baseline"),
            ("customer_specific_policies", "Customer-specific policies", "Acme sample policy"),
            ("approval_workflows", "Approval workflows defined", "spike + overrun + notification"),
            ("reporting_integrated", "Cost reporting integrated", "daily/weekly/closure"),
            ("audit_complete", "Audit chain entry phase_15.complete", "phase_15.complete"),
        ],
        "optional": [],
    },
}


class ApplyDefaultsRequest(BaseModel):
    operator_id: str = "operator"
    goal: str = "apps_internal"


class ReviewRequest(BaseModel):
    accepted_artifact_ids: list[str] = Field(default_factory=list)
    disabled_artifact_ids: list[str] = Field(default_factory=list)


class CustomArtifactRequest(BaseModel):
    name: str = ""
    category: str = "custom"
    notes: str = ""


class SimulationRequest(BaseModel):
    project_type: str = "public_saas"
    d_level: int = 3
    customer_specific: bool = False


class EdgeDiagnosisRequest(BaseModel):
    case_id: str
    context: dict[str, Any] = Field(default_factory=dict)


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


def _state_key(phase_id: str, key: str) -> str:
    return f"templates_setup:{phase_id}:{key}"


def _get_state(phase_id: str, key: str) -> Any:
    with _connect() as conn:
        row = conn.execute("SELECT value_json FROM sylion_phase_state WHERE key = ?", (_state_key(phase_id, key),)).fetchone()
    return _json_loads(row["value_json"], None) if row else None


def _set_state(phase_id: str, key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sylion_phase_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (_state_key(phase_id, key), json.dumps(value, ensure_ascii=False, sort_keys=True, default=str), time.time()),
        )


def _state_list(phase_id: str, key: str) -> list[dict[str, Any]]:
    value = _get_state(phase_id, key)
    return value if isinstance(value, list) else []


def _append_audit(phase_id: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
    chain = _state_list(phase_id, "audit_chain")
    previous_hash = str(chain[-1].get("hash") or "") if chain else ""
    entry = {"event_id": _uid("audit"), "event": event, "payload": payload, "created_at": time.time(), "previous_hash": previous_hash}
    entry["hash"] = hashlib.sha256(json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    chain.append(entry)
    _set_state(phase_id, "audit_chain", chain)
    return entry


def _catalog(phase_id: str) -> dict[str, Any]:
    if phase_id not in VALID_PHASES:
        raise HTTPException(status_code=404, detail="template setup phase not found")
    return PHASE_CATALOG[phase_id]


def _default_settings(phase_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    catalog = _catalog(phase_id)
    return {
        "phase_id": phase_id,
        "phase": catalog["phase"],
        "goal": goal,
        "artifacts": {item["id"]: {**_clone(item), "enabled": True, "reviewed": False, "source": "baseline"} for item in catalog["artifacts"]},
        "capabilities": {item["id"]: {"enabled": False, "items": item["items"]} for item in catalog["capabilities"]},
        "flags": {item[0]: False for item in catalog["acceptance"] + catalog.get("optional", []) if item[0] != "audit_complete"},
        "custom_artifacts": [],
        "simulations": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }


def _settings(phase_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    _catalog(phase_id)
    existing = _get_state(phase_id, "settings")
    if isinstance(existing, dict):
        return existing
    settings = _default_settings(phase_id, goal=goal)
    _set_state(phase_id, "settings", settings)
    return settings


def _save_settings(phase_id: str, settings: dict[str, Any], event: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings["updated_at"] = time.time()
    _set_state(phase_id, "settings", settings)
    _append_audit(phase_id, event, payload)
    return settings


def _enabled_artifacts(settings: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (settings.get("artifacts") or {}).values() if item.get("enabled")]


def _bootstrap_skills_registry(settings: dict[str, Any], operator_id: str) -> dict[str, Any]:
    reg = get_skills_registry()
    executor = get_skills_executor()
    created = 0
    published = 0
    executed = 0
    for skill in PHASE_CATALOG["skills"]["artifacts"]:
        if not reg.get(skill["id"]):
            reg.register_skill(
                {
                    "skill_id": skill["id"],
                    "name": skill["name"],
                    "domain": skill["category"],
                    "owner_role": operator_id,
                    "description": f"Phase 11 baseline system skill: {skill['name']}",
                    "inputs": [{"name": "context", "type": "object"}],
                    "outputs": [{"name": "result", "type": "object"}],
                    "quality_gates": ["schema_validated", "cost_profile_defined", "provenance_logged"],
                    "cost_profile": skill["cost_profile"],
                },
                persist=True,
            )
            created += 1
        current = reg.get(skill["id"])
        if current and current.get("lifecycle") != "PUBLISHED":
            try:
                reg.publish(skill["id"])
                published += 1
            except ValueError:
                pass
    if PHASE_CATALOG["skills"]["artifacts"]:
        executor.execute(PHASE_CATALOG["skills"]["artifacts"][0]["id"], {"phase": 11, "smoke": True})
        executed += 1
    stats = reg.get_stats()
    settings["registry_stats"] = stats
    settings["executor_stats"] = executor.get_stats()
    return {"created": created, "published": published, "executed": executed, "registry_stats": stats}


def _apply_default_flags(phase_id: str, settings: dict[str, Any], operator_id: str = "operator") -> dict[str, Any]:
    catalog = _catalog(phase_id)
    for artifact in settings["artifacts"].values():
        artifact["enabled"] = True
        artifact["reviewed"] = True
    for capability in settings["capabilities"].values():
        capability["enabled"] = True
    for key in list(settings["flags"]):
        settings["flags"][key] = True
    if phase_id == "skills":
        bootstrap = _bootstrap_skills_registry(settings, operator_id)
        settings["flags"]["system_skills_available"] = len(_enabled_artifacts(settings)) >= 25
        settings["flags"]["marketplace_settings"] = True
        settings["flags"]["personal_skills_count"] = True
        settings["flags"]["imported_skills_count"] = True
        settings["custom_artifacts"] = [
            {"id": "skill.personal.formal_polish_letter", "name": "Generate Polish formal letter", "source": "personal", "enabled": True},
            {"id": "skill.imported.stripe_webhook_verified", "name": "Stripe webhook handler verified", "source": "imported", "enabled": True},
        ]
        return bootstrap
    if phase_id == "council":
        settings["custom_artifacts"] = [
            {"id": "ct_customer_industrial_monitoring", "name": "Customer industrial monitoring", "source": "custom", "enabled": True},
            {"id": "ct_fintech_multilingual", "name": "Fintech multilingual", "source": "custom", "enabled": True},
            {"id": "ct_pl_accessibility_public", "name": "Polish accessibility public portal", "source": "custom", "enabled": True},
        ]
    if phase_id == "cost-policies":
        settings["customer_policy"] = {
            "id": "customer_acme",
            "annual_budget_eur": 5000,
            "per_project_cap_eur": 500,
            "overrun_policy": "customer approves above 110 percent",
            "visibility": ["real_time_dashboard", "weekly_summary", "project_breakdown", "detailed_invoice_items"],
        }
    return {}


def _hard_blocks(phase_id: str, settings: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    catalog = _catalog(phase_id)

    def add(block_id: str, label: str, condition: bool, evidence: str) -> None:
        if condition:
            blocks.append({"id": block_id, "label": label, "status": "fail", "evidence": evidence, "hard": True})

    add("baseline_missing", "Hard block: baseline artifacts missing", len(_enabled_artifacts(settings)) < catalog["baseline_target"], f"{len(_enabled_artifacts(settings))}/{catalog['baseline_target']}")
    for requirement_id, label, evidence in catalog["acceptance"]:
        if requirement_id == "audit_complete":
            continue
        add(f"missing_{requirement_id}", f"Hard block: {label}", not bool((settings.get("flags") or {}).get(requirement_id)), evidence)
    if phase_id == "test-strategy":
        missing_l5 = any("L5" not in ",".join(item.get("levels", [])) for item in _enabled_artifacts(settings))
        add("l5_missing", "Hard block: mandatory L5 human-like UI missing", missing_l5, "every strategy must preserve L5")
    if phase_id == "deployment":
        add("production_gate_missing", "Hard block: production deploy hard gate missing", not bool(settings.get("flags", {}).get("production_hard_gate")), "operator approval must stay hard gate")
    return blocks


def _build_acceptance(phase_id: str, settings: dict[str, Any], finalize: bool = False) -> dict[str, Any]:
    catalog = _catalog(phase_id)
    completion_event = f"phase_{catalog['phase']}.complete"
    audit_complete = any(entry.get("event") == completion_event for entry in _state_list(phase_id, "audit_chain"))
    checks: list[dict[str, Any]] = []
    for requirement_id, label, evidence in catalog["acceptance"]:
        if requirement_id == "audit_complete":
            ok = audit_complete or finalize
        else:
            ok = bool((settings.get("flags") or {}).get(requirement_id))
        checks.append({"id": requirement_id, "label": label, "status": "pass" if ok else "fail", "evidence": evidence if ok else "missing", "hard": True})
    for requirement_id, label, evidence in catalog.get("optional", []):
        ok = bool((settings.get("flags") or {}).get(requirement_id))
        checks.append({"id": requirement_id, "label": label, "status": "pass" if ok else "info", "evidence": evidence, "hard": False})
    hard_blocks = [item for item in checks if item["status"] == "fail" and item.get("hard")]
    hard_blocks.extend(_hard_blocks(phase_id, settings))
    if finalize and not hard_blocks and not audit_complete:
        entry = _append_audit(
            phase_id,
            completion_event,
            {
                "enabled_artifacts": len(_enabled_artifacts(settings)),
                "custom_artifacts": len(settings.get("custom_artifacts") or []),
                "simulations": len(settings.get("simulations") or []),
            },
        )
        audit_complete = True
        for check in checks:
            if check["id"] == "audit_complete":
                check["status"] = "pass"
                check["evidence"] = entry["event_id"]
    passed = len([item for item in checks if item["status"] == "pass"])
    return {
        "phase": catalog["phase"],
        "phase_id": phase_id,
        "accepted": not hard_blocks,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "dod": {
            "required": len(catalog["acceptance"]),
            "passed_required": len([item for item in checks[: len(catalog["acceptance"])] if item["status"] == "pass"]),
            "all": len(checks),
            "passed_all": passed,
        },
        "audit_chain": {
            "entries": len(_state_list(phase_id, "audit_chain")),
            f"phase_{catalog['phase']}_complete": audit_complete,
            "last_hash": (_state_list(phase_id, "audit_chain")[-1].get("hash") if _state_list(phase_id, "audit_chain") else ""),
        },
    }


def _snapshot(phase_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    settings = _settings(phase_id, goal=goal)
    catalog = _catalog(phase_id)
    return {
        "phase": catalog["phase"],
        "phase_id": phase_id,
        "settings": settings,
        "templates": {
            "catalog": catalog,
            "artifact_groups": catalog["artifact_groups"],
            "artifacts": catalog["artifacts"],
            "capabilities": catalog["capabilities"],
            "edge_cases": PHASE_EDGE_CASES[phase_id],
        },
        "acceptance": _build_acceptance(phase_id, settings),
    }


def _overview() -> dict[str, Any]:
    rows = []
    for phase_id in ["skills", "council", "test-strategy", "deployment", "cost-policies"]:
        settings = _settings(phase_id)
        acceptance = _build_acceptance(phase_id, settings)
        catalog = _catalog(phase_id)
        rows.append(
            {
                "phase_id": phase_id,
                "phase": catalog["phase"],
                "title": catalog["title"],
                "baseline_target": catalog["baseline_target"],
                "enabled_artifacts": len(_enabled_artifacts(settings)),
                "edge_cases": len(PHASE_EDGE_CASES[phase_id]),
                "accepted": acceptance["accepted"],
                "complete": acceptance["audit_chain"].get(f"phase_{catalog['phase']}_complete"),
            }
        )
    return {"phases": rows, "group": {"id": "A2", "label": "Templates Setup", "complete": all(item["complete"] for item in rows), "edge_cases": sum(item["edge_cases"] for item in rows)}}


@router.get("")
def get_templates_setup_overview() -> dict[str, Any]:
    return _overview()


@router.get("/{phase_id}")
def get_templates_setup_phase(phase_id: str, goal: str = "apps_internal") -> dict[str, Any]:
    return _snapshot(phase_id, goal=goal)


@router.post("/{phase_id}/defaults/apply")
def apply_templates_setup_defaults(phase_id: str, body: ApplyDefaultsRequest) -> dict[str, Any]:
    settings = _default_settings(phase_id, goal=body.goal)
    bootstrap = _apply_default_flags(phase_id, settings, operator_id=body.operator_id)
    _set_state(phase_id, "settings", settings)
    _append_audit(phase_id, f"phase{_catalog(phase_id)['phase']}.defaults_applied", {"goal": body.goal, "operator_id": body.operator_id, "bootstrap": bootstrap})
    return _snapshot(phase_id, goal=body.goal)


@router.post("/{phase_id}/review")
def review_templates_setup_artifacts(phase_id: str, body: ReviewRequest) -> dict[str, Any]:
    settings = _settings(phase_id)
    known = set(settings.get("artifacts") or {})
    accepted = set(body.accepted_artifact_ids or known)
    disabled = set(body.disabled_artifact_ids)
    unknown = sorted((accepted | disabled) - known)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown artifacts: {', '.join(unknown)}")
    for artifact_id, artifact in settings["artifacts"].items():
        artifact["reviewed"] = artifact_id in accepted
        artifact["enabled"] = artifact_id not in disabled
    if phase_id == "skills":
        settings["flags"]["system_skills_available"] = len(_enabled_artifacts(settings)) >= 25
    if phase_id in {"council", "deployment"}:
        settings["flags"]["templates_configured"] = len(_enabled_artifacts(settings)) >= _catalog(phase_id)["baseline_target"]
    if phase_id == "test-strategy":
        settings["flags"]["strategies_configured"] = len(_enabled_artifacts(settings)) >= 5
    if phase_id == "cost-policies":
        settings["flags"]["policies_configured"] = len(_enabled_artifacts(settings)) >= 5
    _save_settings(phase_id, settings, f"phase{_catalog(phase_id)['phase']}.artifacts_reviewed", {"accepted": len(accepted), "disabled": len(disabled)})
    return {"settings": settings, "snapshot": _snapshot(phase_id, goal=settings.get("goal", "apps_internal"))}


@router.post("/{phase_id}/custom-artifacts")
def create_templates_setup_custom_artifact(phase_id: str, body: CustomArtifactRequest) -> dict[str, Any]:
    settings = _settings(phase_id)
    name = body.name or f"Custom {str(_catalog(phase_id)['artifact_label']).title()}"
    artifact = {"id": _slug(f"custom_{name}_{uuid.uuid4().hex[:6]}"), "name": name, "category": body.category, "notes": body.notes, "source": "custom", "enabled": True, "created_at": time.time()}
    settings.setdefault("custom_artifacts", []).append(artifact)
    if phase_id == "council":
        settings["flags"]["custom_templates_count"] = True
    if phase_id == "skills":
        settings["flags"]["personal_skills_count"] = True
    _save_settings(phase_id, settings, f"phase{_catalog(phase_id)['phase']}.custom_artifact_created", {"artifact_id": artifact["id"]})
    return {"artifact": artifact, "snapshot": _snapshot(phase_id, goal=settings.get("goal", "apps_internal"))}


@router.post("/{phase_id}/simulate")
def simulate_templates_setup_phase(phase_id: str, body: SimulationRequest) -> dict[str, Any]:
    settings = _settings(phase_id)
    catalog = _catalog(phase_id)
    artifacts = _enabled_artifacts(settings)
    recommendation = artifacts[0] if artifacts else None
    if phase_id == "council":
        recommendation = next((item for item in artifacts if body.d_level in [int(str(level).replace("D", "")) for level in item.get("d_levels", []) if str(level).replace("D", "").isdigit()]), recommendation)
        settings["flags"]["composition_wizard_tested"] = True
    if phase_id == "test-strategy":
        if body.d_level >= 4:
            recommendation = next((item for item in artifacts if item["id"] == "ts_critical"), recommendation)
        settings["flags"]["strategy_project_mapping"] = True
    if phase_id == "deployment":
        if body.project_type in {"public_saas", "customer_facing"}:
            recommendation = next((item for item in artifacts if item["id"] == "dt_canary"), recommendation)
    if phase_id == "cost-policies":
        if body.customer_specific:
            recommendation = next((item for item in artifacts if item["id"] == "cp_strict_customer"), recommendation)
    simulation = {"id": _uid("sim"), "project_type": body.project_type, "d_level": body.d_level, "customer_specific": body.customer_specific, "recommendation": recommendation, "created_at": time.time()}
    settings.setdefault("simulations", []).append(simulation)
    _save_settings(phase_id, settings, f"phase{catalog['phase']}.simulation_run", {"simulation_id": simulation["id"], "recommendation": (recommendation or {}).get("id")})
    return {"simulation": simulation, "snapshot": _snapshot(phase_id, goal=settings.get("goal", "apps_internal"))}


@router.get("/{phase_id}/edge-cases")
def list_templates_setup_edge_cases(phase_id: str) -> dict[str, Any]:
    _catalog(phase_id)
    edge_cases = PHASE_EDGE_CASES[phase_id]
    return {"phase": _catalog(phase_id)["phase"], "count": len(edge_cases), "categories": sorted({item["category"] for item in edge_cases}), "edge_cases": edge_cases}


@router.post("/{phase_id}/edge-cases/diagnose")
def diagnose_templates_setup_edge_case(phase_id: str, body: EdgeDiagnosisRequest) -> dict[str, Any]:
    case = next((item for item in PHASE_EDGE_CASES[_catalog(phase_id) and phase_id] if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    diagnosis = {
        "case": case,
        "context": body.context,
        "requires_operator_review": case["severity"] in {"medium", "high"},
        "action_plan": case["runbook"] + [f"write phase{_catalog(phase_id)['phase']} audit entry"],
        "created_at": time.time(),
    }
    _append_audit(phase_id, f"phase{_catalog(phase_id)['phase']}.edge_case_diagnosed", {"case_id": case["id"], "severity": case["severity"]})
    return diagnosis


@router.get("/{phase_id}/acceptance")
def get_templates_setup_acceptance(phase_id: str) -> dict[str, Any]:
    return _build_acceptance(phase_id, _settings(phase_id), finalize=False)


@router.get("/{phase_id}/acceptance-test")
def run_templates_setup_acceptance_test(phase_id: str) -> dict[str, Any]:
    return _build_acceptance(phase_id, _settings(phase_id), finalize=True)


@router.post("/{phase_id}/complete")
def complete_templates_setup_phase(phase_id: str) -> dict[str, Any]:
    result = _build_acceptance(phase_id, _settings(phase_id), finalize=True)
    if result["hard_blocks"]:
        raise HTTPException(status_code=400, detail=result)
    return result
