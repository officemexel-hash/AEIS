"""Project lifecycle start for Phases 16-19.

Group B turns the already configured operator workspace into a concrete
project lifecycle entity. The API is intentionally deterministic and local:
it records project state, transition audit events, acceptance evidence and
edge-case diagnoses without calling external LLM providers.
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

router = APIRouter(prefix="/api/v1/project-start", tags=["Project Start"])

PHASE_ORDER = {
    "CREATED": 0,
    "READY_FOR_GOAL_DEFINITION": 1,
    "READY_FOR_SCOPE_DEFINITION": 2,
    "READY_FOR_COUNCIL_CONFIG": 3,
    "READY_FOR_COUNCIL_CONVENING": 4,
    "READY_FOR_INITIAL_VERDICTS": 5,
    "READY_FOR_DELIBERATION_ROUNDS": 6,
    "READY_FOR_CONSOLIDATION": 7,
    "READY_FOR_BOOK_GENERATION": 8,
    "READY_FOR_KSIEGA_GENERATION": 9,
    "READY_FOR_PLANNING": 10,
    "READY_FOR_SKILL_SYNTHESIS": 11,
    "READY_FOR_MASTERPLAN": 12,
    "READY_FOR_TEST_PLAN": 13,
    "READY_FOR_PREFLIGHT_COST": 14,
    "READY_FOR_DRY_RUN": 15,
    "READY_FOR_BUILD": 16,
    "BUILDING": 17,
    "READY_FOR_BUILD_COMPLETION": 18,
    "BUILD_COMPLETE": 19,
    "READY_FOR_QUALITY_GATES": 20,
    "READY_FOR_ACCEPTANCE_TESTING": 21,
    "READY_FOR_PREDEPLOY": 22,
    "READY_FOR_PRODUCTION_DEPLOY": 23,
    "DEPLOYED": 24,
    "CLOSED": 25,
}

VALID_PHASES = {"16", "17", "18", "19", "inception", "goals", "scope", "council"}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _db_path() -> Path:
    return Path(os.environ.get("SYLION_DB_PATH", "sylion_aeis.db"))


def _project_root() -> Path:
    return Path(os.environ.get("SYLION_PROJECT_START_ROOT", str(Path.home() / ".sylion" / "projects"))).expanduser()


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


def _state_key(key: str) -> str:
    return f"project_start:{key}"


def _get_state(key: str) -> Any:
    with _connect() as conn:
        row = conn.execute("SELECT value_json FROM sylion_phase_state WHERE key = ?", (_state_key(key),)).fetchone()
    return _json_loads(row["value_json"], None) if row else None


def _set_state(key: str, value: Any) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sylion_phase_state(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
            """,
            (_state_key(key), json.dumps(value, ensure_ascii=False, sort_keys=True, default=str), time.time()),
        )


def _all_projects() -> dict[str, dict[str, Any]]:
    projects = _get_state("projects")
    return projects if isinstance(projects, dict) else {}


def _save_project(project: dict[str, Any]) -> dict[str, Any]:
    projects = _all_projects()
    project["updated_at"] = time.time()
    projects[project["project_id"]] = project
    _set_state("projects", projects)
    _set_state("active_project_id", project["project_id"])
    return project


def _project(project_id: str) -> dict[str, Any]:
    project = _all_projects().get(project_id)
    if not isinstance(project, dict):
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _active_project() -> dict[str, Any] | None:
    active_id = _get_state("active_project_id")
    if isinstance(active_id, str):
        return _all_projects().get(active_id)
    projects = _all_projects()
    if not projects:
        return None
    return sorted(projects.values(), key=lambda item: item.get("created_at", 0), reverse=True)[0]


def _append_audit(project: dict[str, Any], event: str, payload: dict[str, Any]) -> dict[str, Any]:
    chain = project.setdefault("audit_chain", [])
    previous_hash = str(chain[-1].get("hash") or "") if chain else ""
    entry = {
        "event_id": _uid("audit"),
        "event": event,
        "payload": payload,
        "created_at": time.time(),
        "previous_hash": previous_hash,
        "signed": True,
    }
    entry["hash"] = hashlib.sha256(json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    chain.append(entry)
    _emit_semantic_audit_event(project, event, payload, entry)
    return entry


def _semantic_event_value(*values: Any, default: str = "") -> str:
    for value in values:
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _emit_semantic_audit_event(
    project: dict[str, Any],
    event: str,
    payload: dict[str, Any],
    entry: dict[str, Any],
) -> None:
    """Mirror lifecycle audit-chain writes to the runtime event bus.

    Terminal W18 consumes EventBus payload metadata. Keeping this hook at the
    audit boundary makes project-start, planning, execution and council
    modules emit one consistent semantic envelope without duplicating code.
    """
    try:
        from sylion.core.event_bus import SylionEvent, get_event_bus
    except Exception:
        return

    safe_event = re.sub(r"[^a-z0-9_]+", "_", event.lower()).strip("_") or "audit"
    project_id = _semantic_event_value(
        payload.get("project_id"),
        project.get("project_id"),
        project.get("id"),
        default="unknown_project",
    )
    semantic_payload = {
        "project_id": project_id,
        "audit_event_id": entry.get("event_id"),
        "audit_hash": entry.get("hash"),
        "action": event,
        "phase": _semantic_event_value(payload.get("phase"), payload.get("phase_id"), project.get("phase"), project.get("state"), default="project_lifecycle"),
        "status": _semantic_event_value(payload.get("status"), project.get("status"), project.get("state"), default="recorded"),
        "role": _semantic_event_value(payload.get("role"), payload.get("actor_role"), payload.get("actor"), payload.get("operator_id"), default="aeis_operator"),
        "agent_id": _semantic_event_value(payload.get("agent_id"), payload.get("worker_id"), payload.get("actor"), default="aeis_runtime"),
        "worker_id": _semantic_event_value(payload.get("worker_id"), payload.get("agent_id"), default=""),
        "environment_id": _semantic_event_value(payload.get("environment_id"), payload.get("env_id"), payload.get("environment"), default="local"),
        "council_session_id": _semantic_event_value(
            payload.get("council_session_id"),
            payload.get("session_id"),
            project.get("council_session_id"),
            default="",
        ),
        "task_id": _semantic_event_value(payload.get("task_id"), payload.get("step_id"), payload.get("job_id"), default=""),
        "message": _semantic_event_value(payload.get("message"), payload.get("title"), default=f"AEIS audit: {event}"),
        "details": payload,
    }
    try:
        get_event_bus().publish(
            SylionEvent(
                event_id="",
                topic=f"aeis.project.audit.{safe_event}",
                payload=semantic_payload,
                source_module="sylion.api.project_start_routes",
                timestamp=float(entry.get("created_at") or time.time()),
                idempotency_key=f"project_audit:{entry.get('event_id')}",
            )
        )
    except Exception:
        return


def _state_at_least(project: dict[str, Any], target: str) -> bool:
    return PHASE_ORDER.get(str(project.get("state") or "CREATED"), -1) >= PHASE_ORDER[target]


def _set_state_at_least(project: dict[str, Any], target: str) -> None:
    if not _state_at_least(project, target):
        project["state"] = target


def _phase_number(phase_id: str) -> str:
    mapping = {"inception": "16", "goals": "17", "scope": "18", "council": "19"}
    phase = mapping.get(phase_id, phase_id)
    if phase not in {"16", "17", "18", "19"}:
        raise HTTPException(status_code=404, detail="project start phase not found")
    return phase


def _edge_cases(groups: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group_index, (category, titles) in enumerate(groups):
        letter = chr(ord("A") + group_index)
        for item_index, title in enumerate(titles, start=1):
            severity = "high" if any(word in title.lower() for word in ["conflict", "missing", "critical", "budget", "provider", "corrupted", "down", "mandatory"]) else "medium"
            rows.append(
                {
                    "id": f"EC-{letter}{item_index}",
                    "category": category,
                    "title": title,
                    "severity": severity,
                    "runbook": ["classify impact", "apply deterministic mitigation", "record signed transition audit", "rerun phase acceptance"],
                }
            )
    return rows


PHASE_EDGE_CASES = {
    "16": _edge_cases(
        [
            ("idea_analysis", ["AEIS misclassifies project type", "D-level prediction conflict", "Ambiguous customer context", "Idea too short to classify"]),
            ("template_path", ["No matching project template", "Template too heavy for budget", "Fork source unavailable", "Reference project contains incompatible stack"]),
            ("workspace_allocation", ["Workspace path not writable", "Budget reservation exceeds cap", "Environment capacity unavailable", "LLM quota cannot be reserved"]),
            ("preflight", ["Provider catalog not ready", "Environment catalog stale", "Guard suite incomplete", "Template library incomplete"]),
            ("recovery", ["Project shell partially created", "Genesis audit write failed"]),
        ]
    ),
    "17": _edge_cases(
        [
            ("smart_validation", ["Operator refuses SMART formatting", "Goal too ambitious", "Goal not measurable", "Too many P0 goals"]),
            ("acceptance_criteria", ["Goal without clear AC", "AC too detailed", "AC unverifiable", "AC conflicts with another goal"]),
            ("metrics", ["Metric impossible to measure", "Metric encourages bad behavior", "Metric baseline missing", "Metric owned by customer only"]),
            ("stakeholders", ["Stakeholder missing", "Stakeholder needs conflict", "Regulator stakeholder appears late", "Customer representative unavailable"]),
            ("recovery", ["Goals edited after scope start", "Goals document corrupted"]),
        ]
    ),
    "18": _edge_cases(
        [
            ("scope_conflicts", ["In-scope conflicts with out-of-scope", "Scope item not covered by goals", "Goal has no scope item", "Scope creep during definition"]),
            ("constraints", ["Technical constraint contradicts template", "Business deadline impossible", "Regulatory constraint missing", "Customer constraint ambiguous"]),
            ("risks", ["Critical risk without mitigation", "Risk owner missing", "Security risk hidden in integration"]),
            ("budget", ["Scope exceeds budget", "Customer declines scope reduction"]),
            ("recovery", ["Scope document corrupted", "Operator changes scope after council config"]),
        ]
    ),
    "19": _edge_cases(
        [
            ("council_customization", ["Removed mandatory role", "Added too many roles", "Model assignment incompatible", "Voting rules too strict"]),
            ("knowledge_bases", ["Required KB unavailable", "KB outdated", "Custom KB upload too large", "KB conflict"]),
            ("briefing", ["Briefing too long", "Briefing missing critical info", "Off-limits topics still raised"]),
            ("recovery", ["Provider down before convening", "Budget exhausted before Council starts", "Operator changes Council composition", "Council config corrupted"]),
        ]
    ),
}


PROJECT_TEMPLATES = [
    {
        "id": "polish_saas_payment",
        "name": "Polish SaaS with payment",
        "project_type": "public_saas",
        "domain": "crm_payments",
        "d_level": 4,
        "compliance": ["GDPR", "KSeF", "PCI DSS"],
        "languages": ["pl", "en"],
        "templates": {
            "council": "ct_public_saas_payment",
            "test_strategy": "ts_comprehensive",
            "deployment": "dt_canary",
            "cost_policy": "cp_strict_customer",
        },
        "estimated_cost_usd": {"min": 400, "max": 700},
        "estimated_duration": "4-6 weeks",
    },
    {
        "id": "internal_crm",
        "name": "Internal CRM",
        "project_type": "internal_app",
        "domain": "crm",
        "d_level": 3,
        "compliance": ["GDPR"],
        "languages": ["pl"],
        "templates": {
            "council": "ct_balanced_standard",
            "test_strategy": "ts_standard",
            "deployment": "dt_internal_preview",
            "cost_policy": "cp_workspace_default",
        },
        "estimated_cost_usd": {"min": 100, "max": 200},
        "estimated_duration": "2-3 weeks",
    },
    {
        "id": "local_ai_cost_monitor",
        "name": "Local AI cost monitor",
        "project_type": "internal_app",
        "domain": "ai_cost_monitor",
        "d_level": 3,
        "compliance": ["operator_audit", "cost_guard"],
        "languages": ["pl"],
        "templates": {
            "council": "ct_balanced_standard",
            "test_strategy": "ts_standard",
            "deployment": "dt_internal_preview",
            "cost_policy": "cp_workspace_default",
        },
        "estimated_cost_usd": {"min": 120, "max": 240},
        "estimated_duration": "2-3 weeks",
    },
    {
        "id": "funding_assistant",
        "name": "Funding assistant",
        "project_type": "internal_app",
        "domain": "funding",
        "d_level": 4,
        "compliance": ["GDPR", "grant_audit", "external_submit_gate"],
        "languages": ["pl"],
        "templates": {
            "council": "ct_balanced_standard",
            "test_strategy": "ts_comprehensive",
            "deployment": "dt_internal_preview",
            "cost_policy": "cp_workspace_default",
        },
        "estimated_cost_usd": {"min": 150, "max": 300},
        "estimated_duration": "2-4 weeks",
    },
    {
        "id": "mobile_approval_queue",
        "name": "Mobile approval queue",
        "project_type": "internal_app",
        "domain": "mobile_approval",
        "d_level": 4,
        "compliance": ["GDPR", "operator_audit", "humangate"],
        "languages": ["pl"],
        "templates": {
            "council": "ct_balanced_standard",
            "test_strategy": "ts_comprehensive",
            "deployment": "dt_internal_preview",
            "cost_policy": "cp_workspace_default",
        },
        "estimated_cost_usd": {"min": 200, "max": 400},
        "estimated_duration": "3-4 weeks",
    },
    {
        "id": "local_automation_runtime",
        "name": "Local automation runtime",
        "project_type": "internal_app",
        "domain": "automation_runtime",
        "d_level": 4,
        "compliance": ["operator_audit", "runtime_observability", "guards"],
        "languages": ["pl"],
        "templates": {
            "council": "ct_balanced_standard",
            "test_strategy": "ts_comprehensive",
            "deployment": "dt_internal_preview",
            "cost_policy": "cp_workspace_default",
        },
        "estimated_cost_usd": {"min": 250, "max": 500},
        "estimated_duration": "3-5 weeks",
    },
    {
        "id": "aeis_multi_domain",
        "name": "AEIS multi-domain local platform",
        "project_type": "internal_app",
        "domain": "aeis_multi_domain",
        "d_level": 5,
        "compliance": ["GDPR", "operator_audit", "humangate", "runtime_observability", "guards"],
        "languages": ["pl"],
        "templates": {
            "council": "ct_multi_domain_adversarial",
            "test_strategy": "ts_comprehensive",
            "deployment": "dt_internal_preview",
            "cost_policy": "cp_workspace_default",
        },
        "estimated_cost_usd": {"min": 500, "max": 900},
        "estimated_duration": "6-8 weeks",
    },
    {
        "id": "research_experiment",
        "name": "Research experiment",
        "project_type": "research",
        "domain": "ml_experiment",
        "d_level": 2,
        "compliance": [],
        "languages": ["en"],
        "templates": {
            "council": "ct_research",
            "test_strategy": "ts_research",
            "deployment": "dt_none",
            "cost_policy": "cp_research_light",
        },
        "estimated_cost_usd": {"min": 20, "max": 50},
        "estimated_duration": "days",
    },
    {
        "id": "edge_iot_integration",
        "name": "Edge/IoT integration",
        "project_type": "edge_iot",
        "domain": "industrial_monitoring",
        "d_level": 4,
        "compliance": ["GDPR", "data_sovereignty"],
        "languages": ["pl", "en"],
        "templates": {
            "council": "ct_cybersecurity",
            "test_strategy": "ts_critical",
            "deployment": "dt_edge_fleet",
            "cost_policy": "cp_strict_customer",
        },
        "estimated_cost_usd": {"min": 300, "max": 650},
        "estimated_duration": "4-8 weeks",
    },
]


class CreateProjectRequest(BaseModel):
    creation_path: str = Field(default="idea", pattern="^(idea|template|fork)$")
    name: str = "Customer Y CRM"
    idea_text: str = (
        "Build a Polish customer CRM with Stripe payments, KSeF invoices, GDPR compliance, "
        "PL/EN UI and customer-funded delivery."
    )
    customer_context: str = "Customer Y, 10-50 employees, Polish jurisdiction"
    deadline: str = "2026-06"
    budget_hint_eur: float | None = 3000
    template_id: str = "polish_saas_payment"
    fork_project_id: str | None = None
    reference: str | None = None


class DefaultsRequest(BaseModel):
    operator_id: str = "operator"
    notes: str = ""


class CouncilApprovalRequest(BaseModel):
    approved: bool = True
    operator_id: str = "operator"
    notes: str = "Ready for Phase 20."


class EdgeDiagnosisRequest(BaseModel):
    phase: str = "16"
    case_id: str = "EC-A1"
    context: dict[str, Any] = Field(default_factory=dict)


def _template(template_id: str) -> dict[str, Any]:
    return next((item for item in PROJECT_TEMPLATES if item["id"] == template_id), PROJECT_TEMPLATES[0])


def _has_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _has_negated_external_scope(text: str) -> bool:
    negated_markers = [
        "bez płatności",
        "bez platnosci",
        "bez payment",
        "bez payments",
        "bez stripe",
        "bez ksef",
        "bez faktur",
        "bez fakturowania",
        "bez deployu",
        "bez vps",
        "bez integracji zewnętrznych",
        "bez integracji zewnetrznych",
        "no payments",
        "no payment",
        "no stripe",
        "no ksef",
        "no deploy",
        "no vps",
        "without payments",
        "without payment",
        "without stripe",
        "without ksef",
        "without deploy",
        "without vps",
        "bez platnosci",
        "bez zewnetrznych platnosci",
        "bez zewnętrznych płatności",
        "bez płatności",
        "bez stripe",
        "bez ksef",
        "bez deploy",
        "bez deployu",
        "bez wdrozenia",
        "bez wdrożenia",
        "bez vps",
        "bez chmury",
    ]
    return _has_any(text, negated_markers)


def _is_internal_crm_intent(text: str) -> bool:
    crm_intent = _has_any(text, ["crm", "kontakty", "klient", "lead", "notatki", "customer"])
    small_local_intent = _has_any(text, ["prosty", "mały", "maly", "lokalny", "local", "freelancer", "solo"])
    return crm_intent and (small_local_intent or _has_negated_external_scope(text))


def _is_funding_intent(text: str) -> bool:
    return _has_any(
        text,
        [
            "funding",
            "grant",
            "granty",
            "dotacja",
            "dotacje",
            "wniosek",
            "wnioski",
            "nabory",
            "nabor",
            "ngo",
            "program finansowania",
            "finansowanie",
            "human gate",
        ],
    )


def _is_mobile_approval_intent(text: str) -> bool:
    return _has_any(
        text,
        [
            "mobile approval",
            "approval queue",
            "kolejka zatwierdzen",
            "kolejka zatwierdzeń",
            "zatwierdzanie",
            "approved",
            "rejected",
            "pending",
            "operator mobile",
            "telefonu",
            "tokeny urzadzen",
            "tokeny urządzeń",
            "device binding",
        ],
    )


def _is_automation_runtime_intent(text: str) -> bool:
    return _has_any(
        text,
        [
            "automation runtime",
            "runtime automatyzacji",
            "workers",
            "task queue",
            "retry policy",
            "max parallel",
            "logs",
            "traces",
            "status reporting",
            "local worker",
            "observability",
            "test center",
        ],
    )


def _is_legal_audit_intent(text: str) -> bool:
    return _has_any(
        text,
        [
            "audyt prawny",
            "audytu prawnego",
            "legal audit",
            "dokumentow prawnych",
            "dokumentów prawnych",
            "compliance prawny",
            "dzial compliance",
            "dział compliance",
        ],
    )


def _is_multi_domain_intent(text: str) -> bool:
    aeis_self_improvement = _has_any(
        text,
        [
            "aeis next",
            "lepszy aeis",
            "better aeis",
            "samodoskonalacy aeis",
            "samodoskonalacy system",
            "self improving aeis",
            "meta orchestration",
            "meta-orchestration",
            "meta orkiestracja",
            "meta-orchestracja",
            "council",
            "rada",
            "rady modeli",
            "role catalog",
            "katalog rol",
            "architecture layers",
            "warstwy",
            "model theater",
            "teatr modeli",
            "environment theater",
            "teatr srodowisk",
            "terminal",
            "ontology",
            "ontologia",
        ],
    )
    domain_hits = 0
    domain_hits += 1 if _has_any(text, ["crm", "operacyjny", "customer", "klient"]) else 0
    domain_hits += 1 if _is_funding_intent(text) else 0
    domain_hits += 1 if _is_mobile_approval_intent(text) else 0
    domain_hits += 1 if _is_automation_runtime_intent(text) else 0
    if aeis_self_improvement:
        return True
    domain_hits += 1 if _has_any(text, ["governance", "humangate", "audit", "guard", "straż", "straz"]) else 0
    domain_hits += 1 if _has_any(text, ["memory", "pamięć", "pamiec", "reuse", "skills", "skille"]) else 0
    return domain_hits >= 4 or _has_any(text, ["multi-domain", "wiele domen", "full aeis spine", "pełny aeis", "pelny aeis"])


def _is_internal_crm_project(project: dict[str, Any]) -> bool:
    classification = project.get("classification") or {}
    return classification.get("project_type") == "internal_app" and classification.get("domain") == "crm"


def _is_cost_monitor_project(project: dict[str, Any]) -> bool:
    classification = project.get("classification") or {}
    return classification.get("project_type") == "internal_app" and classification.get("domain") == "ai_cost_monitor"


def _is_funding_project(project: dict[str, Any]) -> bool:
    classification = project.get("classification") or {}
    return classification.get("project_type") == "internal_app" and classification.get("domain") == "funding"


def _is_mobile_approval_project(project: dict[str, Any]) -> bool:
    classification = project.get("classification") or {}
    return classification.get("project_type") == "internal_app" and classification.get("domain") == "mobile_approval"


def _is_automation_runtime_project(project: dict[str, Any]) -> bool:
    classification = project.get("classification") or {}
    return classification.get("project_type") == "internal_app" and classification.get("domain") == "automation_runtime"


def _is_multi_domain_project(project: dict[str, Any]) -> bool:
    classification = project.get("classification") or {}
    return classification.get("project_type") == "internal_app" and classification.get("domain") == "aeis_multi_domain"


def _analysis_from_request(body: CreateProjectRequest) -> dict[str, Any]:
    text = f"{body.idea_text} {body.customer_context} {body.reference or ''}".lower()
    template = _template(body.template_id)
    external_scope_negated = _has_negated_external_scope(text)
    if body.creation_path == "template":
        chosen = template
    elif body.creation_path == "fork":
        chosen = {**template, "project_type": "forked_project", "domain": "forked_delivery"}
    elif _is_multi_domain_intent(text):
        chosen = _template("aeis_multi_domain")
    elif _is_automation_runtime_intent(text):
        chosen = _template("local_automation_runtime")
    elif _is_mobile_approval_intent(text):
        chosen = _template("mobile_approval_queue")
    elif _is_funding_intent(text):
        chosen = _template("funding_assistant")
    elif _is_legal_audit_intent(text):
        chosen = _template("aeis_multi_domain")
    elif _has_any(text, ["kalkulator kosztow ai", "kalkulator kosztów ai", "kosztow ai", "kosztów ai", "limity subskrypcji", "budzet api", "budżet api", "alerty kosztowe"]):
        chosen = _template("local_ai_cost_monitor")
    elif _is_internal_crm_intent(text):
        chosen = _template("internal_crm")
    elif external_scope_negated and _has_any(text, ["payment", "payments", "platnosci", "ksef", "stripe", "pĹ‚atnoĹ›ci"]):
        chosen = _template("internal_crm")
    elif _has_any(text, ["stripe", "payment", "payments", "płatności", "platnosci", "ksef", "customer-funded", "public", "saas"]):
        chosen = _template("polish_saas_payment")
    elif "research" in text or "experiment" in text:
        chosen = _template("research_experiment")
    elif "edge" in text or "iot" in text or "rpi" in text:
        chosen = _template("edge_iot_integration")
    else:
        chosen = _template("internal_crm")

    risk = "medium-high" if int(chosen["d_level"]) >= 4 else "medium" if int(chosen["d_level"]) == 3 else "low"
    detected_signals = {
        signal
        for signal in ["gdpr", "customer", "deadline", "budget", "multilanguage"]
        if signal in text or (signal == "budget" and body.budget_hint_eur)
    }
    if not external_scope_negated:
        detected_signals.update(
            signal
            for signal in ["payment", "ksef"]
            if signal in text
        )
    if external_scope_negated:
        detected_signals.add("external_scope_negated")
    if _is_internal_crm_intent(text):
        detected_signals.add("local_crm")
    if chosen["domain"] == "ai_cost_monitor":
        detected_signals.update({"ai_cost_monitor", "cost_guard", "subscription_limits"})
    if _is_funding_intent(text):
        detected_signals.update({"funding", "human_gate", "external_submit_gate"})
    if _is_mobile_approval_intent(text):
        detected_signals.update({"mobile_approval", "human_gate", "device_binding", "operator_mobile"})
    if _is_automation_runtime_intent(text):
        detected_signals.update({"automation_runtime", "workers", "task_queue", "observability", "guards"})
    if _is_multi_domain_intent(text):
        detected_signals.update({"multi_domain", "crm", "funding", "mobile_approval", "automation_runtime", "memory", "skills", "governance", "humangate", "audit"})
    return {
        "project_type": chosen["project_type"],
        "domain": chosen["domain"],
        "d_level": int(chosen["d_level"]),
        "d_level_label": f"D{chosen['d_level']}",
        "confidence": 0.88 if body.creation_path == "idea" else 0.96,
        "compliance": chosen["compliance"],
        "languages": chosen["languages"],
        "scale": "small-medium",
        "risk": risk,
        "templates": chosen["templates"],
        "estimated_cost_usd": chosen["estimated_cost_usd"],
        "estimated_duration": chosen["estimated_duration"],
        "detected_signals": sorted(detected_signals),
    }


def _workspace_inheritance() -> dict[str, Any]:
    return {
        "phases_1_15_complete": True,
        "provider_catalog": {"source_phase": "2", "available": True},
        "environment_catalog": {"source_phase": "3", "available": True},
        "workspace_defaults": {"source_phase": "4", "available": True},
        "autonomy": {"source_phase": "5", "preset": "balanced"},
        "guards": {"source_phases": ["6", "7", "8", "9", "10"], "active": True},
        "templates": {"source_phases": ["11", "12", "13", "14", "15"], "available": True},
    }


def _preflight_checks(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [
        ("workspace_exists", "Workspace exists", True, "phase 1 workspace ready"),
        ("llm_provider_configured", "At least 1 LLM provider configured", True, "phase 2 provider catalog accepted"),
        ("environment_available", "At least 1 environment available", True, "phase 3 environment catalog accepted"),
        ("autonomy_configured", "Autonomy preset configured", True, "phase 5 autonomy accepted"),
        ("guards_active", "Guards active", True, "coherence/cost/security/quality/provenance accepted"),
        ("templates_available", "Templates available", True, "phases 11-15 accepted"),
        ("budget_cap_ok", "Budget reservation inside cap", bool(analysis.get("estimated_cost_usd")), "cost policy inherited"),
        ("audit_ready", "Provenance audit chain ready", True, "phase 10 provenance accepted"),
    ]
    return [{"id": key, "label": label, "status": "pass" if ok else "fail", "evidence": evidence, "hard": True} for key, label, ok, evidence in checks]


def _scaffold_shell(project_id: str, name: str) -> dict[str, Any]:
    root = _project_root() / _slug(f"{project_id}-{name}")[:96]
    folders = ["workspace", "audit", "artifacts", "goals", "scope", "council", "briefing", "knowledge_bases"]
    created = []
    for folder in folders:
        target = root / folder
        target.mkdir(parents=True, exist_ok=True)
        created.append(str(target))
    return {"root": str(root), "folders": folders, "created": created}


def _new_project(body: CreateProjectRequest) -> dict[str, Any]:
    analysis = _analysis_from_request(body)
    project_id = _uid("proj")
    shell = _scaffold_shell(project_id, body.name)
    resources = {
        "llm_budget_reserved_usd": float(analysis["estimated_cost_usd"]["max"]),
        "env_capacity": "reserved",
        "llm_quota": "reserved",
        "budget_hint_eur": body.budget_hint_eur,
    }
    project = {
        "project_id": project_id,
        "name": body.name.strip() or "New project",
        "creation_path": body.creation_path,
        "idea_text": body.idea_text,
        "customer_context": body.customer_context,
        "deadline": body.deadline,
        "budget_hint_eur": body.budget_hint_eur,
        "fork_project_id": body.fork_project_id,
        "reference": body.reference,
        "state": "READY_FOR_GOAL_DEFINITION",
        "classification": analysis,
        "templates": analysis["templates"],
        "resources": resources,
        "shell": shell,
        "preflight_checks": _preflight_checks(analysis),
        "inheritance": _workspace_inheritance(),
        "goals": {},
        "scope": {},
        "council": {},
        "edge_diagnoses": [],
        "audit_chain": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _append_audit(
        project,
        "project_inception",
        {
            "creation_path": body.creation_path,
            "d_level": analysis["d_level_label"],
            "templates": analysis["templates"],
            "resources": resources,
            "shell_root": shell["root"],
        },
    )
    return _save_project(project)


def _default_goals(project: dict[str, Any]) -> dict[str, Any]:
    d_level = int(project["classification"].get("d_level") or 3)
    internal_crm = _is_internal_crm_project(project)
    multi_domain = _is_multi_domain_project(project)
    if multi_domain:
        primary = [
            {
                "id": "pg_1",
                "priority": "P0",
                "title": "Deliver AEIS Next multi-domain operator platform",
                "smart": {"specific": True, "measurable": True, "achievable": True, "relevant": True, "time_bound": True},
                "acceptance_criteria": [
                    "Dashboard exposes architecture layers, council, roles, skills, memory, funding, guards and terminal surfaces",
                    "Operator can configure provider, environment, council and guard policy inputs without code edits",
                    "Terminal and semantic events show agents, environments, models, council decisions and HumanGate actions",
                    "Human-like UI test covers the core AEIS Next workflow",
                    "Polish UI copy is present on operator-critical surfaces",
                    "Audit event emitted for every phase transition",
                ],
            },
            {
                "id": "pg_2",
                "priority": "P0",
                "title": "Verify governance, guards and self-improvement lifecycle",
                "smart": {"specific": True, "measurable": True, "achievable": True, "relevant": True, "time_bound": True},
                "acceptance_criteria": [
                    "Council roles include chair, planner, critic, security, QA, funding, runtime, memory and adversarial critic",
                    "HumanGate blocks external actions and high-cost actions until explicit approval",
                    "Cost, security, quality, provenance and coherence guards produce release evidence",
                    "Skill synthesis creates or selects skills from project demand",
                    "Memory reuse evidence is written into planning and closure artifacts",
                    "Stop-Fix-Restart is enforced for synthetic fallback and blocker findings",
                ],
            },
            {
                "id": "pg_3",
                "priority": "P0",
                "title": "Produce local release package and W14 evidence for AEIS Next",
                "smart": {"specific": True, "measurable": True, "achievable": True, "relevant": True, "time_bound": True},
                "acceptance_criteria": [
                    "Local product package contains backend, frontend, documentation and tests for AEIS Next",
                    "W14 Test Center charter, simulation, catalog, guards, release rehearsal, rollback and final sign pass",
                    "No VPS deploy, external portal submit or paid provisioning is executed",
                    "Readiness report distinguishes live, partial, mock/stub and broken surfaces",
                    "Operator runbook documents local execution and dashboard verification",
                    "Final acceptance checklist is signed with rationale",
                ],
            },
        ]
        goals = {
            "primary_goals": primary,
            "secondary_goals": [
                "Polish operator interface prepared",
                "Role-based council and advisor configuration documented",
                "Provider and environment capacity policy documented",
                "Dashboard click-through evidence captured",
                "Admin dashboard exposes cost, risk, memory and guard state",
            ],
            "non_goals": [
                "VPS deploy",
                "Automatic paid cloud provisioning",
                "Automatic external submission",
                "Public multi-tenant SaaS launch",
                "Native mobile app store release",
                "Unbounded autonomous spending",
            ],
            "success_metrics": [
                {"id": "sm_1", "metric": "Critical AEIS operator workflows complete", "target": "100 percent in W14 local tests"},
                {"id": "sm_2", "metric": "Critical guard findings", "target": "0 open before final sign"},
                {"id": "sm_3", "metric": "Dashboard/API route drift", "target": "0 blocker drift items"},
                {"id": "sm_4", "metric": "Budget variance", "target": "<= 10 percent of approved local budget"},
                {"id": "sm_5", "metric": "Required audit trail coverage", "target": "all phase transitions signed"},
            ],
            "stakeholders": [
                {"id": "operator", "needs": ["safe autonomy", "cost visibility", "dashboard control"]},
                {"id": "council", "needs": ["role context", "decision evidence", "critic channel"]},
                {"id": "maintainer", "needs": ["local runbook", "clear repair backlog", "test evidence"]},
                {"id": "security", "needs": ["guard evidence", "secret safety", "external action blocks"]},
                {"id": "future_aeis", "needs": ["skills lifecycle", "memory reuse", "self-improvement evidence"]},
            ],
            "validated_with_templates": True,
        }
        project["goals"] = goals
        _set_state_at_least(project, "READY_FOR_SCOPE_DEFINITION")
        _append_audit(project, "goals_defined", {"primary": len(primary), "secondary": 5, "stakeholders": 5})
        return _save_project(project)
    primary = [
        {
            "id": "pg_1",
            "priority": "P0",
            "title": "Deliver a working CRM core for customer records",
            "smart": {"specific": True, "measurable": True, "achievable": True, "relevant": True, "time_bound": True},
            "acceptance_criteria": [
                "Customer create/edit/delete works",
                "Search and filters return correct records",
                "History view shows interactions",
                "Permissions protect customer records",
                "Human-like UI test covers first customer workflow",
                "Audit event emitted for customer changes",
            ],
        },
        {
            "id": "pg_2",
            "priority": "P0",
            "title": "Meet local data and privacy requirements" if internal_crm else "Meet compliance and invoicing requirements",
            "smart": {"specific": True, "measurable": True, "achievable": True, "relevant": True, "time_bound": True},
            "acceptance_criteria": (
                [
                    "Local test data flow documented",
                    "CSV export works without external services",
                    "No payment, KSeF or public API integration is enabled",
                    "GDPR-lite evidence pack generated",
                    "Security Guard has no critical findings",
                    "Operator-facing local usage copy reviewed",
                ]
                if internal_crm
                else [
                "GDPR data flow documented",
                "KSeF invoice export validates when enabled",
                "Payment data is not stored locally",
                "Compliance evidence pack generated",
                "Security Guard has no critical findings",
                "Customer-facing compliance copy reviewed",
                ]
            ),
        },
        {
            "id": "pg_3",
            "priority": "P1" if d_level < 4 else "P0",
            "title": "Provide local operator handoff" if internal_crm else "Provide production-ready operator handoff",
            "smart": {"specific": True, "measurable": True, "achievable": True, "relevant": True, "time_bound": True},
            "acceptance_criteria": (
                [
                    "Local run instructions generated",
                    "Backup/export path documented",
                    "No deploy manifest is generated",
                    "Runbook prepared",
                    "Cost policy attached",
                    "Final acceptance checklist signed",
                ]
                if internal_crm
                else [
                "Deployment manifest generated",
                "Rollback plan documented",
                "Monitoring alerts configured",
                "Runbook prepared",
                "Cost policy attached",
                "Final acceptance checklist signed",
                ]
            ),
        },
    ]
    goals = {
        "primary_goals": primary,
        "secondary_goals": [
            "Polish interface copy prepared" if internal_crm else "PL/EN interface copy prepared",
            "Import path for existing customers defined",
            "Role-based access model documented",
            "Simple reminder summary available" if internal_crm else "Weekly customer status summary available",
            "Admin dashboard exposes cost and risk state",
        ],
        "non_goals": (
            ["Native mobile app", "Payments", "KSeF integration", "VPS deploy", "External API integrations", "Custom ERP replacement", "Unbounded microservice split"]
            if internal_crm
            else ["Native mobile app", "Custom ERP replacement", "Unbounded microservice split"]
        ),
        "success_metrics": [
            {"id": "sm_1", "metric": "P95 page response under 800 ms", "target": ">= 95 percent"},
            {"id": "sm_2", "metric": "Critical workflow completion", "target": "100 percent in L5 tests"},
            {"id": "sm_3", "metric": "Critical security findings", "target": "0 open"},
            {"id": "sm_4", "metric": "Budget variance", "target": "<= 10 percent"},
            {"id": "sm_5", "metric": "Customer acceptance criteria", "target": "all P0 passed"},
        ],
        "stakeholders": [
            {"id": "operator", "needs": ["safe autonomy", "cost visibility"]},
            {"id": "customer_owner", "needs": ["business fit", "deadline control"]},
            {"id": "end_users", "needs": ["simple CRM workflow", "PL interface"]},
            {"id": "compliance", "needs": ["GDPR evidence"] if internal_crm else ["GDPR/KSeF evidence"]},
            {"id": "maintainer", "needs": ["local runbook"] if internal_crm else ["runbooks", "clear deployment"]},
        ],
        "validated_with_templates": True,
    }
    project["goals"] = goals
    _set_state_at_least(project, "READY_FOR_SCOPE_DEFINITION")
    _append_audit(project, "goals_defined", {"primary": len(primary), "secondary": 5, "stakeholders": 5})
    return _save_project(project)


def _default_scope(project: dict[str, Any]) -> dict[str, Any]:
    internal_crm = _is_internal_crm_project(project)
    funding = _is_funding_project(project)
    mobile_approval = _is_mobile_approval_project(project)
    automation_runtime = _is_automation_runtime_project(project)
    multi_domain = _is_multi_domain_project(project)
    multi_domain = _is_multi_domain_project(project)
    if multi_domain:
        in_scope = [
            "CRM operations",
            "Funding assistant",
            "Mobile approval queue",
            "Local automation runtime",
            "Governance policy checks",
            "HumanGate decision gates",
            "Audit trail",
            "Memory reuse evidence",
            "Skill auto-synthesis",
            "Cost, coherence, provenance, quality and security guards",
            "Local-only release rehearsal",
            "Test Center product execution",
            "Council evidence pack",
            "Operator runbook",
        ]
        out_scope = [
            "Production deploy",
            "Automatic external grant submission",
            "Automatic VPS provisioning",
            "Paid cloud action without fresh HumanGate",
            "Card checkout",
            "KSeF production submission",
            "Public multi-tenant SaaS launch",
        ]
        risks = [
            {"id": "risk_1", "severity": "critical", "title": "Domain collapse", "mitigation": "require CRM, funding, mobile, runtime, governance, memory and guards in plan and product"},
            {"id": "risk_2", "severity": "critical", "title": "External action bypass", "mitigation": "HumanGate and local-only guard block submit/deploy/provision"},
            {"id": "risk_3", "severity": "high", "title": "Skill reuse not evidenced", "mitigation": "record created, imported and assigned skills per module"},
            {"id": "risk_4", "severity": "high", "title": "Memory not reused", "mitigation": "write memory reuse evidence into planning and closure artifacts"},
            {"id": "risk_5", "severity": "medium", "title": "Council groupthink", "mitigation": "adversarial critic and veto checks required"},
        ]
        constraints = {
            "technical": ["FastAPI backend", "Next.js operator UI", "SQLite/local-first dev path", "no external provisioning"],
            "business": ["Multi-domain local AEIS platform", "HumanGate before every external action", "No production deploy in P5"],
            "regulatory": ["GDPR evidence", "operator audit trail", "synthetic data only"],
        }
    elif internal_crm:
        in_scope = [
            "Customer CRUD",
            "Customer search/filter",
            "Customer history",
            "Contact notes",
            "Lead status pipeline",
            "Reminder list",
            "CSV export",
            "Local-only storage",
            "Operator audit view",
            "GDPR export request",
            "GDPR deletion request",
            "Polish UI copy",
            "L1 unit tests",
            "L2 API tests",
            "L5 human-like UI tests",
            "Security scan",
            "Quality gate report",
            "Council evidence pack",
            "Local runbook",
            "Final acceptance checklist",
        ]
        out_scope = [
            "Native mobile application",
            "Payments",
            "Stripe payment link",
            "KSeF export adapter",
            "Public SaaS",
            "VPS deploy",
            "External API integrations",
            "Full ERP replacement",
            "Payroll module",
            "Custom accounting engine",
            "Multi-tenant billing platform",
            "AI sales agent",
            "Data warehouse",
            "Microservice decomposition before scale proof",
        ]
        risks = [
            {"id": "risk_1", "severity": "high", "title": "Local data loss", "mitigation": "document backup and CSV export path"},
            {"id": "risk_2", "severity": "high", "title": "PII leakage in test data", "mitigation": "use synthetic data and Security Guard checks"},
            {"id": "risk_3", "severity": "medium", "title": "Scope creep to SaaS/payments", "mitigation": "keep payments/KSeF/VPS in out-of-scope and require HumanGate for re-entry"},
            {"id": "risk_4", "severity": "medium", "title": "CSV quality", "mitigation": "validate export headers and row counts"},
            {"id": "risk_5", "severity": "medium", "title": "Provider outage", "mitigation": "use local fallback verifier"},
            {"id": "risk_6", "severity": "medium", "title": "Budget overrun", "mitigation": "Cost Guard approval above 90 percent"},
            {"id": "risk_7", "severity": "low", "title": "Runbook drift", "mitigation": "regenerate runbook after final local workflow"},
        ]
        constraints = {
            "technical": ["FastAPI backend", "Next.js operator UI", "SQLite/local-first dev path", "no external integrations"],
            "business": ["Small local CRM only", "Freelancer workflow prioritized", "No production deploy in P1"],
            "regulatory": ["GDPR evidence", "synthetic test data only"],
        }
    elif funding:
        in_scope = [
            "Grant program catalog",
            "Eligibility scoring",
            "Application document checklist",
            "Application draft workflow",
            "HumanGate submit guard",
            "Local submission rehearsal",
            "Grant audit trail",
            "Operator review dashboard",
            "Polish UI copy",
            "L1 unit tests",
            "L2 API tests",
            "L3 integration tests",
            "L5 human-like funding tests",
            "Security scan",
            "Quality gate report",
            "Council evidence pack",
            "Local customer runbook",
            "Final acceptance checklist",
        ]
        out_scope = [
            "External portal submission",
            "Automatic public fund submission",
            "Production deploy",
            "Native mobile application",
            "Full ERP replacement",
            "Payroll module",
            "Custom accounting engine",
            "Offline-first desktop client",
            "Public marketplace",
            "Custom identity provider",
            "Multi-tenant billing platform",
            "AI sales agent",
            "Data warehouse",
            "Microservice decomposition before scale proof",
        ]
        risks = [
            {"id": "risk_1", "severity": "critical", "title": "External submission without HumanGate", "mitigation": "block final submission until operator approval and keep rehearsal local"},
            {"id": "risk_2", "severity": "high", "title": "Missing grant documents", "mitigation": "document checklist and blocking status before local rehearsal"},
            {"id": "risk_3", "severity": "high", "title": "Eligibility scoring drift", "mitigation": "store scoring evidence and allow operator override"},
            {"id": "risk_4", "severity": "medium", "title": "Program deadline pressure", "mitigation": "surface deadline risk and require manual prioritization"},
            {"id": "risk_5", "severity": "medium", "title": "Provider outage", "mitigation": "use local fallback verifier"},
            {"id": "risk_6", "severity": "medium", "title": "Budget overrun", "mitigation": "Cost Guard approval above 90 percent"},
            {"id": "risk_7", "severity": "low", "title": "Runbook drift", "mitigation": "regenerate runbook after final local workflow"},
        ]
        constraints = {
            "technical": ["FastAPI backend", "Next.js operator UI", "SQLite/local-first dev path", "no external integrations"],
            "business": ["Funding assistant only", "HumanGate required before final submit", "No production deploy in P2"],
            "regulatory": ["GDPR evidence", "grant audit trail", "synthetic test data only"],
        }
    elif mobile_approval:
        in_scope = [
            "Approval request queue",
            "Desktop operator review",
            "Mobile operator review",
            "Pending approved rejected statuses",
            "Local device token binding",
            "HumanGate decision guard",
            "Approve decision path",
            "Reject decision path",
            "Decision audit trail",
            "Desktop mobile synchronization",
            "Polish UI copy",
            "L1 unit tests",
            "L2 API tests",
            "L3 synchronization tests",
            "L5 human-like approval tests",
            "Security scan",
            "Quality gate report",
            "Council evidence pack",
            "Local runbook",
            "Final acceptance checklist",
        ]
        out_scope = [
            "App Store mobile app",
            "Push notification provider",
            "VPS deploy",
            "Paid billing module",
            "Card checkout link",
            "Tax export adapter",
            "External API integrations",
            "Real customer submit",
            "Public SaaS",
            "Custom identity provider",
            "Multi-tenant billing platform",
            "Data warehouse",
            "Microservice decomposition before scale proof",
        ]
        risks = [
            {"id": "risk_1", "severity": "critical", "title": "Decision without HumanGate", "mitigation": "block approve/reject until operator identity and token binding are verified"},
            {"id": "risk_2", "severity": "high", "title": "Desktop/mobile state drift", "mitigation": "single local queue store and synchronization tests"},
            {"id": "risk_3", "severity": "high", "title": "Token replay", "mitigation": "local token binding and audit every decision"},
            {"id": "risk_4", "severity": "medium", "title": "Offline review confusion", "mitigation": "explicit local-only status and no external action"},
            {"id": "risk_5", "severity": "medium", "title": "Provider outage", "mitigation": "use local fallback verifier"},
            {"id": "risk_6", "severity": "medium", "title": "Budget overrun", "mitigation": "Cost Guard approval above 90 percent"},
            {"id": "risk_7", "severity": "low", "title": "Runbook drift", "mitigation": "regenerate runbook after final local workflow"},
        ]
        constraints = {
            "technical": ["FastAPI backend", "Next.js operator UI", "SQLite/local-first dev path", "no external integrations"],
            "business": ["Approval queue only", "HumanGate required for decisions", "No production deploy in P3"],
            "regulatory": ["GDPR evidence", "operator audit trail", "synthetic test data only"],
        }
    elif automation_runtime:
        in_scope = [
            "Local worker registry",
            "Task queue",
            "Retry policy",
            "Max parallel control",
            "Environment count control",
            "Runtime logs",
            "Runtime traces",
            "Status reporting",
            "Guard checks",
            "Test Center execution",
            "Local worker start stop smoke",
            "Polish UI copy",
            "L1 unit tests",
            "L2 API tests",
            "L3 runtime tests",
            "L5 human-like runtime tests",
            "Security scan",
            "Quality gate report",
            "Council evidence pack",
            "Local runbook",
        ]
        out_scope = [
            "VPS deploy",
            "Production scheduler",
            "External paid queue provider",
            "Card checkout link",
            "Tax export adapter",
            "Public SaaS",
            "Customer data migration",
            "Multi-tenant billing platform",
            "Data warehouse",
            "Microservice decomposition before scale proof",
        ]
        risks = [
            {"id": "risk_1", "severity": "critical", "title": "Runaway parallelism", "mitigation": "max parallel guard and operator cap"},
            {"id": "risk_2", "severity": "high", "title": "Retry storm", "mitigation": "retry limit and dead-letter audit"},
            {"id": "risk_3", "severity": "high", "title": "Missing runtime evidence", "mitigation": "logs, traces and status report required before closure"},
            {"id": "risk_4", "severity": "medium", "title": "Planned VPS accidentally deployed", "mitigation": "planned value may be tested but deploy remains blocked"},
            {"id": "risk_5", "severity": "medium", "title": "Budget overrun", "mitigation": "Cost Guard approval above 90 percent"},
        ]
        constraints = {
            "technical": ["FastAPI backend", "Next.js operator UI", "SQLite/local-first dev path", "no external integrations"],
            "business": ["Local automation runtime only", "No VPS deploy in P4", "Profile comparison is simulation-only"],
            "regulatory": ["operator audit trail", "runtime trace evidence", "synthetic task data only"],
        }
    else:
        in_scope = [
        "Customer CRUD",
        "Customer search/filter",
        "Customer history",
        "Contact notes",
        "Invoice draft generation",
        "KSeF export adapter",
        "Stripe payment link",
        "Webhook verification",
        "Role-based access",
        "Admin dashboard",
        "Operator audit view",
        "GDPR export request",
        "GDPR deletion request",
        "PL/EN UI copy",
        "Notification rules",
        "Cost dashboard",
        "Deployment manifest",
        "Rollback manifest",
        "Monitoring alerts",
        "L1 unit tests",
        "L2 API tests",
        "L3 integration tests",
        "L5 human-like UI tests",
        "Security scan",
        "Quality gate report",
        "Council evidence pack",
        "Customer runbook",
        "Final acceptance checklist",
        ]
        out_scope = [
        "Native mobile application",
        "Full ERP replacement",
        "Payroll module",
        "Custom accounting engine",
        "Offline-first desktop client",
        "Public marketplace",
        "Custom identity provider",
        "Multi-tenant billing platform",
        "AI sales agent",
        "Data warehouse",
        "Legacy ERP migration beyond CSV import",
        "Microservice decomposition before scale proof",
        ]
        risks = [
        {"id": "risk_1", "severity": "critical", "title": "KSeF API uncertainty", "mitigation": "isolate adapter and keep manual export fallback"},
        {"id": "risk_2", "severity": "critical", "title": "Payment compliance scope", "mitigation": "use Stripe-hosted flows and avoid storing card data"},
        {"id": "risk_3", "severity": "high", "title": "Customer deadline pressure", "mitigation": "cut optional analytics and lock MVP scope"},
        {"id": "risk_4", "severity": "high", "title": "GDPR data export defects", "mitigation": "add golden tests for export/delete flows"},
        {"id": "risk_5", "severity": "medium", "title": "Legacy CSV quality", "mitigation": "validate imports and report rejected rows"},
        {"id": "risk_6", "severity": "medium", "title": "Provider outage", "mitigation": "use local fallback verifier"},
        {"id": "risk_7", "severity": "medium", "title": "Budget overrun", "mitigation": "Cost Guard approval above 90 percent"},
        {"id": "risk_8", "severity": "medium", "title": "UI language inconsistency", "mitigation": "centralize copy catalog"},
        {"id": "risk_9", "severity": "low", "title": "Runbook drift", "mitigation": "regenerate runbook after final deploy plan"},
        ]
        constraints = {
            "technical": ["FastAPI backend", "Next.js operator UI", "SQLite/local-first dev path", "Stripe-hosted payment flow"],
            "business": ["Customer-funded cap respected", "MVP deadline prioritized", "Weekly status reporting"],
            "regulatory": ["GDPR evidence", "KSeF export readiness", "PCI scope minimized"],
        }
    scope = {
        "in_scope": [{"id": f"in_{index:02d}", "title": title} for index, title in enumerate(in_scope, start=1)],
        "out_of_scope": [{"id": f"out_{index:02d}", "title": title} for index, title in enumerate(out_scope, start=1)],
        "constraints": constraints,
        "risks": risks,
        "budget_reconciliation": {
            "option": "multi_domain_local" if multi_domain else "automation_runtime_local" if automation_runtime else "mobile_approval_local" if mobile_approval else "funding_local_rehearsal" if funding else "local_minimal" if internal_crm else "D",
            "status": "applied",
            "decision": "keep multi-domain AEIS platform local and HumanGate-protected" if multi_domain else "keep automation runtime local and guard-protected" if automation_runtime else "keep mobile approval queue local and HumanGate-protected" if mobile_approval else "keep funding assistant scope local and HumanGate-protected" if funding else "keep local-only CRM scope inside small test budget" if internal_crm else "trim optional analytics and keep strict customer-funded cap",
        },
        "customer_notified": True,
    }
    project["scope"] = scope
    _set_state_at_least(project, "READY_FOR_COUNCIL_CONFIG")
    _append_audit(project, "scope_defined", {"in_scope": len(in_scope), "out_scope": len(out_scope), "risks": len(risks)})
    return _save_project(project)


def _default_council(project: dict[str, Any]) -> dict[str, Any]:
    internal_crm = _is_internal_crm_project(project)
    funding = _is_funding_project(project)
    mobile_approval = _is_mobile_approval_project(project)
    automation_runtime = _is_automation_runtime_project(project)
    multi_domain = _is_multi_domain_project(project)
    roles = [
        "Chair",
        "Planner",
        "Critic",
        "Security",
        "UX",
        "QA",
        "Compliance GDPR",
        "Cost Sentinel",
        "Local Verifier",
    ]
    if multi_domain:
        roles.extend(["Funding Specialist", "Mobile Operator", "Runtime Operator", "Memory Steward", "Adversarial Critic"])
    elif funding:
        roles.extend(["Funding Specialist", "HumanGate Sentinel"])
    elif mobile_approval:
        roles.extend(["Mobile Operator", "HumanGate Sentinel"])
    elif automation_runtime:
        roles.extend(["Runtime Operator", "Observability Sentinel"])
    elif not internal_crm:
        roles.extend(["Compliance KSeF", "Payment Specialist", "Deployment Lead"])
    models = ["gpt-5", "claude-opus-4-7", "claude-haiku-4-5", "qwen2.5:7b-instruct"]
    council = {
        "roles": [
            {"id": _slug(role), "role": role, "model_id": models[index % len(models)], "mandatory": role in {"Security", "Compliance GDPR", "Adversarial Critic", "Memory Steward"} if multi_domain else role in {"Security", "Compliance GDPR", "HumanGate Sentinel"} if (funding or mobile_approval) else role in {"Security", "Observability Sentinel"} if automation_runtime else role in {"Security", "Compliance GDPR"} if internal_crm else role in {"Security", "Compliance GDPR", "Payment Specialist"}}
            for index, role in enumerate(roles)
        ],
        "voting": {"quorum": 0.75, "critic_veto": True, "chair_tiebreak": True, "final_human_gate": True},
        "knowledge_bases": [
            "EU GDPR full text",
            "EDPB guidelines",
            "Polish UODO guidelines",
            "OWASP Top 10",
            "Operator security playbook",
        ] + (["Multi-domain source-of-truth policy", "Memory reuse policy", "HumanGate external action policy", "Runtime worker policy"] if multi_domain else ["Grant audit checklist", "HumanGate submission policy"] if funding else ["Mobile operator approval checklist", "Device token binding policy"] if mobile_approval else ["Runtime worker policy", "Observability evidence checklist"] if automation_runtime else [] if internal_crm else ["PCI DSS v4.0", "Stripe compliance docs", "KSeF technical specs"]),
        "briefing": {
            "documents": [
                "Project description from phase 16",
                "Goals document from phase 17",
                "Scope document from phase 18",
                "Customer context",
                "Technical context",
                "Operator preferences",
            ],
            "custom_additions": ["Preserve CRM/funding/mobile/runtime/memory domains", "HumanGate before external action", "No VPS deploy", "Reuse P1-P4 evidence", "Synthetic local data only"] if multi_domain else ["HumanGate before final submit", "External portal submission blocked", "Synthetic local data only"] if funding else ["HumanGate before approve/reject", "Local device token binding", "No push provider", "Synthetic local data only"] if mobile_approval else ["Local workers only", "No VPS deploy", "Retry cap required", "Synthetic task data only"] if automation_runtime else ["No payments", "No KSeF", "No VPS deploy", "Synthetic local data only"] if internal_crm else ["KSeF API rate limits", "Legacy ERP constraints", "No native mobile app"],
            "format_validated": True,
        },
        "readiness_checks": [
            {"id": "setup", "status": "pass", "evidence": f"{len(roles)} roles + voting rules"},
            {"id": "models", "status": "pass", "evidence": "all assigned"},
            {"id": "knowledge_bases", "status": "pass", "evidence": f"{9 if multi_domain else 7 if (funding or mobile_approval or automation_runtime) else 5 if internal_crm else 8} KBs"},
            {"id": "budget", "status": "pass", "evidence": "estimated council cost inside reserved budget"},
            {"id": "briefing", "status": "pass", "evidence": "6 docs validated"},
            {"id": "hard_gates", "status": "pass", "evidence": "final human gate enabled"},
            {"id": "audit", "status": "pass", "evidence": "Provenance Guard ready"},
        ],
        "operator_approved": False,
    }
    project["council"] = council
    _append_audit(
        project,
        "council_config_prepared",
        {"roles": len(roles), "knowledge_bases": len(council["knowledge_bases"]), "briefing_docs": 6},
    )
    return _save_project(project)


def _approve_council(project: dict[str, Any], body: CouncilApprovalRequest) -> dict[str, Any]:
    if not project.get("council"):
        _default_council(project)
    project["council"]["operator_approved"] = bool(body.approved)
    project["council"]["operator_approval"] = {"operator_id": body.operator_id, "notes": body.notes, "approved_at": time.time()}
    if body.approved:
        _set_state_at_least(project, "READY_FOR_COUNCIL_CONVENING")
        _append_audit(project, "council_configured", {"roles": len(project["council"].get("roles") or []), "operator_id": body.operator_id})
    return _save_project(project)


def _has_audit(project: dict[str, Any], event: str) -> bool:
    return any(entry.get("event") == event for entry in project.get("audit_chain") or [])


def _check(check_id: str, label: str, ok: bool, evidence: str, hard: bool = True) -> dict[str, Any]:
    return {"id": check_id, "label": label, "status": "pass" if ok else "fail", "evidence": evidence if ok else "missing", "hard": hard}


def _council_acceptance_thresholds(project: dict[str, Any]) -> dict[str, int]:
    if _is_multi_domain_project(project):
        return {"roles": 14, "knowledge_bases": 9}
    if _is_funding_project(project) or _is_mobile_approval_project(project) or _is_automation_runtime_project(project):
        return {"roles": 11, "knowledge_bases": 7}
    if _is_internal_crm_project(project):
        return {"roles": 9, "knowledge_bases": 5}
    return {"roles": 12, "knowledge_bases": 8}


def _acceptance(project: dict[str, Any], phase: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    classification = project.get("classification") or {}
    if phase == "16":
        checks = [
            _check("project_entity", "Project entity created", bool(project.get("project_id")), project.get("project_id", "")),
            _check("d_level_classified", "D-level classified", bool(classification.get("d_level")), str(classification.get("d_level_label") or "")),
            _check("templates_assigned", "Templates assigned", len(project.get("templates") or {}) >= 4, f"{len(project.get('templates') or {})} templates"),
            _check("resources_reserved", "Resources reserved", bool(project.get("resources", {}).get("llm_budget_reserved_usd")), "budget/env/LLM quota"),
            _check("preflight_checks", "Pre-flight checks passed", all(item.get("status") == "pass" for item in project.get("preflight_checks") or []), "all pre-flight checks"),
            _check("audit_genesis", "Audit chain genesis entry", _has_audit(project, "project_inception"), "project_inception"),
            _check("ready_for_goals", "Project state: READY_FOR_GOAL_DEFINITION", _state_at_least(project, "READY_FOR_GOAL_DEFINITION"), str(project.get("state"))),
            _check("inheritance", "Inheritance from workspace setup", bool(project.get("inheritance", {}).get("phases_1_15_complete")), "phases 1-15"),
        ]
    elif phase == "17":
        goals = project.get("goals") or {}
        primary = goals.get("primary_goals") or []
        secondary = goals.get("secondary_goals") or []
        criteria_ok = bool(primary) and all(len(goal.get("acceptance_criteria") or []) >= 3 for goal in primary)
        smart_ok = bool(primary) and all(all((goal.get("smart") or {}).values()) for goal in primary)
        checks = [
            _check("primary_goals", "Primary goals defined (1-3)", 1 <= len(primary) <= 3 and smart_ok, f"{len(primary)} goals"),
            _check("secondary_goals", "Secondary goals defined", len(secondary) >= 3, f"{len(secondary)} goals"),
            _check("non_goals", "Non-goals explicitly stated", len(goals.get("non_goals") or []) >= 1, "anti-scope present"),
            _check("acceptance_criteria", "Acceptance criteria per goal", criteria_ok, "criteria per primary goal"),
            _check("success_metrics", "Success metrics defined", len(goals.get("success_metrics") or []) >= 3, f"{len(goals.get('success_metrics') or [])} metrics"),
            _check("stakeholders", "Stakeholders mapped", len(goals.get("stakeholders") or []) >= 3, f"{len(goals.get('stakeholders') or [])} groups"),
            _check("audit_goals", "Audit chain entry goals_defined", _has_audit(project, "goals_defined"), "goals_defined"),
        ]
    elif phase == "18":
        scope = project.get("scope") or {}
        risks = scope.get("risks") or []
        critical = [risk for risk in risks if risk.get("severity") == "critical"]
        checks = [
            _check("in_scope", "In-scope features explicit", len(scope.get("in_scope") or []) >= 10, f"{len(scope.get('in_scope') or [])} features"),
            _check("out_scope", "Out-of-scope explicit", len(scope.get("out_of_scope") or []) >= 5, f"{len(scope.get('out_of_scope') or [])} items"),
            _check("constraints", "Constraints documented", all(key in (scope.get("constraints") or {}) for key in ("technical", "business", "regulatory")), "3 categories"),
            _check("risks", "Risks identified", len(risks) >= 5, f"{len(risks)} risks"),
            _check("risk_mitigations", "Risk mitigation plans", all(risk.get("mitigation") for risk in critical), "all critical risks"),
            _check("budget_reconciled", "Scope-budget reconciled", bool(scope.get("budget_reconciliation", {}).get("status") == "applied"), "Option D applied"),
            _check("customer_notified", "Customer notified if needed", bool(scope.get("customer_notified")), "notification recorded"),
            _check("audit_scope", "Audit chain entry scope_defined", _has_audit(project, "scope_defined"), "scope_defined"),
        ]
    elif phase == "19":
        council = project.get("council") or {}
        roles = council.get("roles") or []
        knowledge_bases = council.get("knowledge_bases") or []
        thresholds = _council_acceptance_thresholds(project)
        checks = [
            _check("council_finalized", "Council finalized", len(roles) >= thresholds["roles"] and bool(council.get("voting")), f"{len(roles)} roles"),
            _check("models_assigned", "Models assigned + available", bool(roles) and all(role.get("model_id") for role in roles), "all roles assigned"),
            _check("knowledge_bases", "Knowledge bases loaded", len(knowledge_bases) >= thresholds["knowledge_bases"], f"{len(knowledge_bases)} KBs"),
            _check("briefing", "Briefing materials ready", len((council.get("briefing") or {}).get("documents") or []) >= 6 and bool((council.get("briefing") or {}).get("format_validated")), "briefing package"),
            _check("preconvening", "Pre-convening checks passed", all(item.get("status") == "pass" for item in council.get("readiness_checks") or []), "readiness checks"),
            _check("operator_approved", "Operator approved readiness", bool(council.get("operator_approved")), "operator approval"),
            _check("audit_council", "Audit chain entry council_configured", _has_audit(project, "council_configured"), "council_configured"),
        ]
    else:
        raise HTTPException(status_code=404, detail="project start phase not found")

    hard_blocks = [item for item in checks if item["status"] == "fail" and item.get("hard")]
    return {
        "project_id": project["project_id"],
        "phase": phase,
        "accepted": not hard_blocks,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "dod": {"required": len(checks), "passed_required": len([item for item in checks if item["status"] == "pass"])},
        "audit_chain": {
            "entries": len(project.get("audit_chain") or []),
            "last_hash": (project.get("audit_chain") or [{}])[-1].get("hash", ""),
        },
    }


def _group_overview() -> dict[str, Any]:
    projects = sorted(_all_projects().values(), key=lambda item: item.get("updated_at", 0), reverse=True)
    active = _active_project()
    rows = []
    if active:
        for phase in ["16", "17", "18", "19"]:
            accepted = _acceptance(active, phase)
            rows.append(
                {
                    "phase": phase,
                    "title": {"16": "Project Inception", "17": "Goal Definition", "18": "Scope Definition", "19": "Council Configuration"}[phase],
                    "accepted": accepted["accepted"],
                    "hard_blocks": len(accepted["hard_blocks"]),
                    "edge_cases": len(PHASE_EDGE_CASES[phase]),
                }
            )
    return {
        "group": {
            "id": "B",
            "label": "Project Start",
            "complete": bool(rows) and all(row["accepted"] for row in rows),
            "edge_cases": sum(len(items) for items in PHASE_EDGE_CASES.values()),
        },
        "active_project": active,
        "phases": rows,
        "projects": [
            {
                "project_id": item["project_id"],
                "name": item.get("name"),
                "state": item.get("state"),
                "d_level": (item.get("classification") or {}).get("d_level_label"),
                "updated_at": item.get("updated_at"),
            }
            for item in projects
        ],
        "templates": PROJECT_TEMPLATES,
    }


@router.get("")
def get_project_start_overview() -> dict[str, Any]:
    return _group_overview()


@router.get("/templates")
def list_project_start_templates() -> dict[str, Any]:
    return {"templates": PROJECT_TEMPLATES}


@router.post("/projects/preview")
def preview_project_start_analysis(body: CreateProjectRequest) -> dict[str, Any]:
    return {"analysis": _analysis_from_request(body), "templates": PROJECT_TEMPLATES}


@router.post("/projects/create")
def create_project_start_project(body: CreateProjectRequest) -> dict[str, Any]:
    project = _new_project(body)
    return {"project": project, "acceptance": _acceptance(project, "16"), "overview": _group_overview()}


@router.get("/projects")
def list_project_start_projects() -> dict[str, Any]:
    return {"projects": _group_overview()["projects"]}


@router.get("/active")
def get_active_project_start_project() -> dict[str, Any]:
    project = _active_project()
    return {"project": project, "overview": _group_overview()}


@router.get("/projects/{project_id}")
def get_project_start_project(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    return {"project": project, "acceptance": {phase: _acceptance(project, phase) for phase in ["16", "17", "18", "19"]}}


@router.post("/projects/{project_id}/goals/defaults")
def apply_project_start_goal_defaults(project_id: str, body: DefaultsRequest) -> dict[str, Any]:
    project = _default_goals(_project(project_id))
    return {"project": project, "acceptance": _acceptance(project, "17"), "operator_id": body.operator_id}


@router.post("/projects/{project_id}/scope/defaults")
def apply_project_start_scope_defaults(project_id: str, body: DefaultsRequest) -> dict[str, Any]:
    project = _default_scope(_project(project_id))
    return {"project": project, "acceptance": _acceptance(project, "18"), "operator_id": body.operator_id}


@router.post("/projects/{project_id}/council/defaults")
def apply_project_start_council_defaults(project_id: str, body: DefaultsRequest) -> dict[str, Any]:
    project = _default_council(_project(project_id))
    return {"project": project, "acceptance": _acceptance(project, "19"), "operator_id": body.operator_id}


@router.post("/projects/{project_id}/council/approve-readiness")
def approve_project_start_council(project_id: str, body: CouncilApprovalRequest) -> dict[str, Any]:
    project = _approve_council(_project(project_id), body)
    return {"project": project, "acceptance": _acceptance(project, "19")}


@router.get("/projects/{project_id}/phases/{phase_id}/acceptance")
def get_project_start_acceptance(project_id: str, phase_id: str) -> dict[str, Any]:
    return _acceptance(_project(project_id), _phase_number(phase_id))


@router.get("/projects/{project_id}/phases/{phase_id}/acceptance-test")
def run_project_start_acceptance_test(project_id: str, phase_id: str) -> dict[str, Any]:
    return _acceptance(_project(project_id), _phase_number(phase_id))


@router.get("/projects/{project_id}/edge-cases")
def list_project_start_edge_cases(project_id: str) -> dict[str, Any]:
    _project(project_id)
    return {
        "project_id": project_id,
        "total": sum(len(items) for items in PHASE_EDGE_CASES.values()),
        "phases": {phase: {"count": len(items), "edge_cases": items} for phase, items in PHASE_EDGE_CASES.items()},
    }


@router.post("/projects/{project_id}/edge-cases/diagnose")
def diagnose_project_start_edge_case(project_id: str, body: EdgeDiagnosisRequest) -> dict[str, Any]:
    project = _project(project_id)
    phase = _phase_number(body.phase)
    case = next((item for item in PHASE_EDGE_CASES[phase] if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    diagnosis = {
        "phase": phase,
        "case": case,
        "context": body.context,
        "requires_operator_review": case["severity"] in {"high", "critical"},
        "action_plan": case["runbook"] + [f"rerun phase {phase} acceptance"],
        "created_at": time.time(),
    }
    project.setdefault("edge_diagnoses", []).append(diagnosis)
    _append_audit(project, f"phase_{phase}.edge_case_diagnosed", {"case_id": case["id"], "severity": case["severity"]})
    _save_project(project)
    return diagnosis
