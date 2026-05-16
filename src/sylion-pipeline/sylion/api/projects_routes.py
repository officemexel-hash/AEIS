from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from sylion.aeis.advisor.events.lifecycle import publish_lifecycle_event
from sylion.governance.tickets import GovernanceTicket, fetch_pending, submit
from sylion.project_mode import get_project_mode_store
from sylion.security.rbac import requires_role

router = APIRouter(tags=["project_mode"])
log = logging.getLogger("sylion.api.projects_routes")

_DEFAULT_ADVISOR_OPERATOR = "00000000-0000-0000-0000-000000000001"
_D_LEVEL_RANK = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5}
_KICKOFF_LOCK = threading.RLock()
_KICKOFF_IN_FLIGHT: set[str] = set()
_KICKOFF_THREADS: dict[str, threading.Thread] = {}


class CreateProjectRequest(BaseModel):
    name: str = ""
    idea_raw: str
    constraints: str = ""
    canonical_book: str = ""
    preferred_stack: list[str] = []
    attachments: list[dict[str, Any]] = []
    onboarding_config: dict[str, Any] = {}
    project_kind: str = ""
    project_domain: str = ""
    team_id: str = ""
    project_id: str = ""
    owner_id: str = "workspace-default"
    auto_execute: bool = False


class AnswerProjectQuestionRequest(BaseModel):
    choice_id: str = ""
    custom_response: str = ""
    rationale: str = ""
    source: str = "human"


class UpdateAutonomyRequest(BaseModel):
    level: str
    overrides: dict[str, Any] = {}


class UpdateCouncilRequest(BaseModel):
    members: list[dict[str, Any]]
    plan: dict[str, Any] | None = None


class UpdateHierarchyRequest(BaseModel):
    layers: list[dict[str, Any]]


class UpdateWorkersRequest(BaseModel):
    workers: list[dict[str, Any]]


class UpdateExecutionModelsRequest(BaseModel):
    assignments: list[dict[str, Any]]
    catalog_source: str = "project_orchestration_ui"


class RunAuditRequest(BaseModel):
    scope: str = "masterplan"
    parallel: bool | None = None
    module_id: str = ""


class LaunchProjectRequest(BaseModel):
    auto_execute: bool = True
    wait_for_completion: bool = False


class UpdateBudgetRequest(BaseModel):
    hard_limit_usd: float
    soft_warn_usd: float = 0.0


class QueueLoraTrainRequest(BaseModel):
    project_id: str
    base_model: str


class AddProjectAttachmentRequest(BaseModel):
    attachment: dict[str, Any]
    source: str = "project_council_question"


def _workspace_helpers():
    from sylion.api import ai_workspace_routes as workspace_routes

    return workspace_routes


def _store():
    return get_project_mode_store()


def _project_start_project(project_id: str) -> dict[str, Any] | None:
    try:
        from sylion.api import project_start_routes

        return project_start_routes._project(project_id)
    except HTTPException:
        return None
    except Exception:
        log.exception("Failed to load project-start lifecycle project %s", project_id)
        return None


def _project_start_projects() -> list[dict[str, Any]]:
    try:
        from sylion.api import project_start_routes

        return [
            project
            for project in project_start_routes._all_projects().values()
            if isinstance(project, dict) and project.get("project_id")
        ]
    except Exception:
        log.exception("Failed to list project-start lifecycle projects")
        return []


def _project_start_phase(project: dict[str, Any]) -> str:
    state = str(project.get("state") or "").upper()
    if state == "CLOSED":
        return "stable"
    if "EXECUTION" in state or "BUILD" in state:
        return "build"
    if "PLANNING" in state or "MASTERPLAN" in state:
        return "masterplan"
    if "COUNCIL" in state or "KSIEGA" in state or "KSIEGA" in state:
        return "council"
    if "SCOPE" in state or "GOAL" in state:
        return "canon"
    return "idea"


def _adapt_project_start_project(project: dict[str, Any]) -> dict[str, Any]:
    classification = dict(project.get("classification") or {})
    scope = dict(project.get("scope") or {})
    council = dict(project.get("council") or {})
    resources = dict(project.get("resources") or {})
    templates = dict(project.get("templates") or {})
    phase = _project_start_phase(project)
    status = "completed" if phase == "stable" else "active"
    modules = []
    for item in scope.get("in_scope") or []:
        if isinstance(item, dict):
            name = str(item.get("title") or item.get("id") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            modules.append({"module_id": name.lower().replace(" ", "_")[:64], "name": name, "status": status})
    members = []
    for role in council.get("roles") or []:
        if isinstance(role, dict):
            members.append(
                {
                    "role": role.get("role") or role.get("title") or "",
                    "model_id": role.get("model_id") or role.get("preferred_model") or "",
                }
            )
    canonical_book = str(project.get("ksiega", {}).get("markdown") or project.get("council_book", {}).get("markdown") or "")
    masterplan = str(project.get("masterplan", {}).get("summary") or project.get("masterplan", {}).get("markdown") or "")
    return {
        "project_id": project.get("project_id", ""),
        "title": project.get("name") or project.get("project_id", ""),
        "name": project.get("name") or project.get("project_id", ""),
        "description": project.get("idea_text") or project.get("reference") or "",
        "idea": project.get("idea_text") or "",
        "project_kind": classification.get("project_type") or "project_start_lifecycle",
        "project_domain": classification.get("domain") or "",
        "source": "project_start_lifecycle",
        "status": status,
        "source_status": project.get("state") or status,
        "phase": phase,
        "risk": "low",
        "confidence": 0.86 if status == "completed" else 0.68,
        "created_at": project.get("created_at") or project.get("updated_at") or time.time(),
        "updated_at": project.get("updated_at") or project.get("created_at") or time.time(),
        "owner_id": "operator",
        "canonical_book": canonical_book,
        "masterplan": masterplan,
        "canon_snapshot": {
            "source": "project_start_lifecycle",
            "classification": classification,
            "runtime_constraints": project.get("runtime_constraints") or {},
            "modules": modules,
        },
        "worker_plan": {"modules": modules},
        "modules": modules,
        "council_plan": {"members": members},
        "execution_plan": {
            "budget_usd": resources.get("llm_budget_reserved_usd", 0),
            "hard_limit_usd": resources.get("llm_budget_reserved_usd", 0),
            "deployment_mode": templates.get("deployment", ""),
        },
        "cost_cap_usd": resources.get("llm_budget_reserved_usd", 0),
        "governance_policy": {"level": classification.get("d_level_label") or "D3"},
        "approvals": {"book": True, "operating_model": True},
        "launch": {
            "artifact_path": _project_start_artifact_path(project),
            "status": status,
        },
        "audit_chain": project.get("audit_chain") or [],
        "project_start": project,
    }


def _project_start_timeline(project: dict[str, Any]) -> dict[str, Any]:
    now = float(project.get("updated_at") or time.time())
    events = list(project.get("audit_chain") or [])
    return {
        "stages": [
            {
                "stage": str(event.get("event") or "lifecycle_event"),
                "status": "completed",
                "updated_at": float(event.get("created_at") or now),
                "started_at": float(event.get("created_at") or now),
                "completed_at": float(event.get("created_at") or now),
                "output_ref": str(event.get("event_id") or ""),
                "metadata": event.get("payload") or {},
            }
            for event in events
        ]
    }


def _project_start_artifact_path(project: dict[str, Any]) -> str:
    shell = dict(project.get("shell") or {})
    root = Path(str(shell.get("root") or ""))
    candidates = [
        root / "reports" / "closure" / "phase41_project_closure.json",
        root / "reports" / "progress" / "phase36_build_completion.json",
        root / "reports" / "testing" / "phase37_quality_gates.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def _is_project_start_backed(project_id: str) -> bool:
    return _store().get_project(project_id) is None and _project_start_project(project_id) is not None


def _load_project_or_404(project_id: str) -> dict[str, Any]:
    project = _store().get_project(project_id)
    if not project:
        project_start_project = _project_start_project(project_id)
        if project_start_project:
            return _adapt_project_start_project(project_start_project)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def _with_pending_governance(project: dict[str, Any]) -> dict[str, Any]:
    """Expose live HumanGate tickets on the project detail surface."""
    out = dict(project)
    project_id = str(out.get("project_id") or "")
    pending: list[dict[str, Any]] = []
    if project_id:
        try:
            from sylion.governance.tickets import fetch_pending

            pending = [ticket.to_dict() for ticket in fetch_pending(origin="workspace", project_id=project_id)]
        except Exception:
            pending = []
    approvals = dict(out.get("approvals") or {})
    for ticket in pending:
        payload = dict(ticket.get("payload") or {})
        if payload.get("action") == "project_freeze" and payload.get("target") == "canon":
            approvals["book_pending_ticket_id"] = ticket.get("ticket_id", "")
        elif payload.get("action") == "project_freeze" and payload.get("target") == "masterplan":
            approvals["operating_model_pending_ticket_id"] = ticket.get("ticket_id", "")
        elif payload.get("action") == "project_build_authorize" and payload.get("target") == "build":
            approvals["build_pending_ticket_id"] = ticket.get("ticket_id", "")
    if (
        out.get("masterplan_frozen_at")
        and not out.get("build_authorized_at")
        and out.get("phase") == "build_in_progress"
    ):
        out["phase"] = "build_authorization"
    out["approvals"] = approvals
    out["pending_governance_tickets"] = pending
    return out


def _has_any(text: str, tokens: list[str]) -> bool:
    return any(token in text for token in tokens)


def _has_word(text: str, token: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text))


def _normalize_intent_text(value: str) -> str:
    text = str(value or "").lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _project_intent_flags(idea: str) -> dict[str, bool]:
    text = str(idea or "").lower()
    saas_phrase = _has_any(
        text,
        ["saas", "platforma", "multi-tenant", "tenant", "dashboard", "panel", "operator console", "customer", "crm"],
    ) or _has_word(text, "erp")
    return {
        "funding": _has_any(text, ["dotac", "grant", "wniosek", "funding", "dofinans", "horizon", "eic", "feng"]),
        "finance": _has_any(text, ["ledger", "open banking", "open-banking", "invoice", "faktur", "cash-flow", "bank", "fraud"]),
        "marketplace": _has_any(text, ["marketplace", "multi-vendor", "multi vendor", "vendor", "white-label", "white label"]),
        "saas_platform": saas_phrase,
        "project_ops": _has_any(text, ["system projektowy", "zarzadzanie projekt", "zarzÄ…dzanie projekt", "portfolio projekt", "kanban", "gantt", "backlog", "sprint", "milestone", "roadmap", "resource capacity", "risk register", "harmonogram", "schedule", "raport", "report", "serviceops", "control tower", "audit trail", "source of truth", "masterplan", "human gate", "humangate", "rada modeli", "model council", "adversarial critic"]),
        "operator_mobile": _has_any(text, ["mobile", "mobiln", "telefon", "approval token", "deep link", "device binding", "secure token", "push", "follow-me", "offline"]),
        "runtime": _has_any(text, ["runtime", "local-first", "local first", "vps", "hetzner", "docker", "container", "kontener", "worktree", "workers", "worker", "deploy", "canary"]),
        "governance": _has_any(text, ["human gate", "humangate", "source of truth", "sot", "masterplan", "rada modeli", "model council", "council", "governance", "audit", "guards", "w18", "adversarial"]),
    }


def _has_project_ops_core(text: str) -> bool:
    return _has_any(
        text,
        [
            "system projektowy",
            "zarzadzanie projekt",
            "zarzÄ…dzanie projekt",
            "portfolio projekt",
            "portfel projekt",
            "kanban",
            "gantt",
            "backlog",
            "sprint",
            "milestone",
            "kamienie milowe",
            "roadmap",
            "resource capacity",
            "capacity planning",
            "risk register",
            "budzet projektu",
            "budÄąÄ˝et projektu",
            "budĹĽet projektu",
            "release gate",
            "canary",
            "serviceops",
            "control tower",
        ],
    )


def _project_runtime_constraints(idea: str) -> dict[str, Any]:
    text = _normalize_intent_text(idea)
    local_env_count: int | None = None
    number_words = {
        "jedno": 1,
        "jeden": 1,
        "jedna": 1,
        "dwa": 2,
        "dwie": 2,
        "trzy": 3,
        "trzema": 3,
        "trzech": 3,
        "cztery": 4,
        "czterema": 4,
        "czterech": 4,
        "piec": 5,
        "szesc": 6,
    }
    env_patterns = [
        r"(\d+)\s+(?:lokal\w*\s+)?(?:srodowisk|srodowiska|srodowiskami|środowisk|środowiska|środowiskami|environments?)",
        r"(\d+)\s+(?:srodowisk|srodowiska|srodowiskami|środowisk|środowiska|środowiskami|environments?)\s+(?:lokal|local)",
        r"(?:lokal|local)[\w\s-]{0,24}(\d+)\s+(?:srodowisk|srodowiska|srodowiskami|środowisk|środowiska|środowiskami|environments?)",
    ]
    for pattern in env_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                local_env_count = max(1, min(int(match.group(1)), 12))
                break
            except (TypeError, ValueError):
                local_env_count = None
    if local_env_count is None:
        word_env_match = re.search(
            r"\b(jedno|jeden|jedna|dwa|dwie|trzy|trzema|trzech|cztery|czterema|czterech|piec|szesc)\b\s+(?:lokal\w*\s+)?(?:srodowisk|srodowiska|srodowiskami)",
            text,
        )
        if word_env_match:
            local_env_count = number_words.get(word_env_match.group(1))
    explicit_environment_labels = _project_explicit_local_environment_labels(idea)
    if local_env_count is None and len(explicit_environment_labels) >= 2:
        local_env_count = max(1, min(len(explicit_environment_labels), 12))

    vps_mentioned = "vps" in text or "hetzner" in text
    blocked_markers = [
        "zablok",
        "zabron",
        "zakaz",
        "niedozwol",
        "bez human gate",
        "without human gate",
        "blocked",
        "forbidden",
        "poza zakresem",
    ]
    vps_explicit_block = any(
        marker in text
        for marker in [
            "zero vps",
            "zero hetzner",
            "0 vps",
            "0 hetzner",
            "vps=0",
            "hetzner=0",
            "vps: 0",
            "hetzner: 0",
            "bez vps",
            "bez hetzner",
            "brak vps",
            "brak hetzner",
            "no vps",
            "no hetzner",
        ]
    )
    vps_blocked_until_gate = bool(
        vps_mentioned
        and (
            vps_explicit_block
            or "bez vps" in text
            or "no vps" in text
            or "vps zablok" in text
            or "vps, produkcja" in text and ("zablok" in text or "blocked" in text)
            or "vps tylko przez human gate" in text
            or "vps tylko przez humangate" in text
            or "vps bez human gate" in text
            or "vps bez humangate" in text
        )
    )
    if vps_mentioned and any(marker in text for marker in blocked_markers):
        vps_blocked_until_gate = True
    if vps_explicit_block:
        vps_blocked_until_gate = True
    production_explicit_block = any(
        marker in text
        for marker in [
            "zero produkcji",
            "0 produkcji",
            "produkcja=0",
            "produkcja: 0",
            "bez produkcji",
            "brak produkcji",
            "no production",
            "zero production",
        ]
    )
    production_blocked_until_gate = bool(
        "produkcja" in text
        and ("zablok" in text or "human gate" in text or "humangate" in text or "blocked" in text)
    )
    if "produkcja" in text and any(marker in text for marker in blocked_markers):
        production_blocked_until_gate = True
    if production_explicit_block:
        production_blocked_until_gate = True
    external_explicit_block = any(
        marker in text
        for marker in [
            "zero wysylek",
            "zero wysylki",
            "zero upload",
            "zero external upload",
            "zero external submit",
            "zero external submission",
            "zero uploadow",
            "zero uploady",
            "0 wysylek",
            "0 upload",
            "0 external upload",
            "0 external submit",
            "bez wysylek",
            "bez wysylki",
            "bez upload",
            "bez external upload",
            "bez external submit",
            "brak wysylek",
            "brak upload",
            "no external actions",
            "no external upload",
            "no external submit",
            "no external submission",
            "zero external actions",
            "no uploads",
        ]
    )
    external_blocked_until_gate = bool(
        ("akcje zewnetrzne" in text or "akcje zewnętrzne" in text or "external action" in text or "external actions" in text)
        and ("zablok" in text or "human gate" in text or "humangate" in text or "blocked" in text)
    )
    if (
        "akcje zewnetrzne" in text
        or "wysylki" in text
        or "upload" in text
        or "external action" in text
        or "external actions" in text
    ) and any(marker in text for marker in blocked_markers):
        external_blocked_until_gate = True
    if external_explicit_block:
        external_blocked_until_gate = True
    return {
        "local_first": _has_any(text, ["local-first", "local first", "lokalnie najpierw", "local only", "local-only"]),
        "local_environment_count": local_env_count,
        "vps_mentioned": vps_mentioned,
        "vps_explicit_block": vps_explicit_block,
        "vps_blocked_until_human_gate": vps_blocked_until_gate,
        "production_blocked_until_human_gate": production_blocked_until_gate,
        "external_blocked_until_human_gate": external_blocked_until_gate,
}


def _project_explicit_local_environment_labels(idea: str) -> list[str]:
    text = _normalize_intent_text(idea).replace("_", "-")
    environment_token = (
        r"(?:dev|development|staging|qa-lab|qa|test-lab|test|release-lab|release|review|perf|security|prod-ready|prod)"
    )
    explicit = re.search(
        rf"\b({environment_token}(?:\s*(?:/|,|;|\+|\band\b|\bi\b)\s*{environment_token}){{1,}})\b",
        text,
    )
    labels: list[str] = []
    if explicit:
        for item in re.split(r"\s*(?:/|,|;|\+|\band\b|\bi\b)\s*", explicit.group(1)):
            label = item.strip().replace("prod-ready", "prod_ready")
            if label and label not in labels:
                labels.append(label)
    return labels


def _project_local_environment_labels(idea: str, count: int | None) -> list[str]:
    env_count = max(0, int(count or 0))
    if env_count <= 0:
        return []
    default_labels = ["dev", "staging", "qa-lab", "release-lab", "review", "perf", "security", "release"]
    labels = _project_explicit_local_environment_labels(idea)
    labels.extend(label for label in default_labels if label not in labels)
    return labels[:env_count]


def _primary_domain_for_kind(kind: str) -> str:
    return {
        "project_management_system": "project_operations",
        "marketplace_platform": "marketplace_platform",
        "operator_mobile": "operator_mobile",
        "funding": "funding",
        "dashboard": "operator_dashboard",
        "employee_portal": "employee_portal",
        "bioinformatics_workflow": "bioinformatics_workflow",
        "mental_health_safety": "mental_health_safety",
        "ecommerce_generator": "ecommerce_generator",
        "design_tool": "design_tool",
        "chat_app": "chat_app",
    }.get(kind, kind or "application")


def _detect_project_domain_profile(idea: str, primary_kind: str) -> dict[str, Any]:
    flags = _project_intent_flags(idea)
    primary_domain = _primary_domain_for_kind(primary_kind)
    domains: list[str] = []

    def add(domain: str) -> None:
        if domain not in domains:
            domains.append(domain)

    add(primary_domain)
    if flags["project_ops"] or primary_kind == "project_management_system" or (
        primary_kind in {"application", "dashboard"} and flags["saas_platform"]
    ):
        add("project_operations")
    if flags["marketplace"]:
        add("marketplace_platform")
    if flags["funding"] or flags["finance"]:
        add("funding")
    if flags["operator_mobile"]:
        add("operator_mobile")
    if flags["runtime"] and primary_kind in {"application", "dashboard", "project_management_system", "marketplace_platform"}:
        add("runtime")
    if flags["governance"] and primary_kind in {"application", "dashboard", "project_management_system", "marketplace_platform"}:
        add("governance")

    supporting = [domain for domain in domains if domain != primary_domain]
    return {
        "primary_kind": primary_kind,
        "primary_domain": primary_domain,
        "domains": domains,
        "supporting_domains": supporting,
        "is_multi_domain": len(domains) > 1,
        "flags": flags,
        "runtime_constraints": _project_runtime_constraints(idea),
        "funding_is_supporting": primary_kind != "funding" and "funding" in supporting,
        "operator_mobile_is_supporting": primary_kind != "operator_mobile" and "operator_mobile" in supporting,
        "runtime_is_supporting": primary_domain != "runtime" and "runtime" in supporting,
    }


def _classify_project_kind(idea: str) -> str:
    text = str(idea or "").lower()
    flags = _project_intent_flags(text)
    simple_crm_intent = (
        _has_any(text, ["crm", "customer", "klient", "customers"])
        and _has_any(text, ["simple", "prosty", "mały", "maly", "small", "mini"])
        and _has_any(text, ["local-only", "local only", "local-first", "lokalnie"])
        and not _has_any(
            text,
            [
                "portfolio projekt",
                "portfel projekt",
                "kanban",
                "gantt",
                "backlog",
                "sprint",
                "roadmap",
                "resource capacity",
                "capacity planning",
                "risk register",
            ],
        )
    )
    if simple_crm_intent:
        return "application"
    if (
        flags["marketplace"]
        and any(token in text for token in ["pĹ‚atno", "platno", "payment", "checkout", "koszyk", "shipping", "tax", "podat", "tenant", "saas"])
    ):
        return "marketplace_platform"
    if (
        any(token in text for token in ["allegro", "amazon", "marketplace", "ean", "e-commerce", "ecommerce"])
        and any(token in text for token in ["produkt", "opis", "csv", "zdjec", "obraz"])
    ):
        return "ecommerce_generator"
    mobile_tokens = [
        "mobile",
        "mobiln",
        "telefon",
        "approval token",
        "deep link",
        "offline",
        "technik",
        "checklist",
        "checklista",
        "firmware",
        ".ino",
        ".bin",
        "telemetri",
        "synchronizac",
        "sync",
        "urzadzen",
        "urzÄ…dzen",
        "urzÄ…dzeĹ„",
        "zdjec serwis",
        "zdjecia serwis",
        "zdjÄ™cia serwis",
    ]
    if any(token in text for token in mobile_tokens) and not flags["saas_platform"]:
        return "operator_mobile"
    bio_core_tokens = [
        "genom",
        "genomic",
        "genety",
        "bioinformat",
        "fastq",
        "vcf",
        "pseudonimiz",
        "klinicz",
        "clinical",
        "research-only",
        "patient",
        "pacjent",
    ]
    if _has_any(text, bio_core_tokens):
        return "bioinformatics_workflow"
    if (
        flags["funding"]
        and not flags["saas_platform"]
        and not flags["marketplace"]
        and not flags["operator_mobile"]
        and not _has_project_ops_core(text)
    ):
        return "funding"
    multi_domain_support_count = sum(
        1
        for key in ("funding", "finance", "operator_mobile", "runtime")
        if flags.get(key)
    )
    if flags["saas_platform"] and flags["project_ops"] and (multi_domain_support_count >= 1 or flags["governance"]):
        return "project_management_system"
    if (
        any(token in text for token in ["ledger", "open banking", "open-banking", "invoice", "faktur", "cash-flow", "bank", "fraud"])
        and any(token in text for token in ["grant", "funding", "dotac", "wniosek", "cash-flow", "invoice", "faktur"])
    ):
        return "funding"
    if (
        any(token in text for token in ["marketplace", "multi-vendor", "multi vendor", "vendor", "white-label", "white label"])
        and any(token in text for token in ["płatno", "platno", "payment", "checkout", "koszyk", "shipping", "tax", "podat", "tenant", "saas"])
    ):
        return "marketplace_platform"
    if any(
        token in text
        for token in [
            "wellbeing",
            "mental health",
            "mental-health",
            "psych",
            "psychoeduk",
            "nastroj",
            "nastr",
            "samoboj",
            "autoagres",
            "kryzys",
            "asystent wellbeing",
            "no medical advice",
            "bez diagnoz",
            "bez porad medycz",
        ]
    ):
        return "mental_health_safety"
    bio_ambiguous_tokens = ["wariant", "variant", "qc"]
    if _has_any(text, bio_core_tokens) or (
        not _has_project_ops_core(text)
        and not flags["governance"]
        and
        _has_any(text, bio_ambiguous_tokens)
        and (
            any(_has_word(text, token) for token in ["gen", "dna", "rna"])
            or _has_any(text, ["fastq", "vcf", "bioinformat", "klinicz", "clinical", "patient", "pacjent"])
        )
    ):
        return "bioinformatics_workflow"
    if flags["project_ops"] and (flags["saas_platform"] or flags["runtime"] or flags["governance"]):
        return "project_management_system"
    if any(
        token in text
        for token in [
            "system projektowy",
            "zarzadzanie projekt",
            "zarzÄ…dzanie projekt",
            "portfolio projekt",
            "portfel projekt",
            "kanban",
            "gantt",
            "backlog",
            "sprint",
            "milestone",
            "kamienie milowe",
            "roadmap",
            "resource capacity",
            "capacity planning",
            "risk register",
            "budzet projektu",
            "budĹĽet projektu",
            "release gate",
            "canary",
        ]
    ):
        return "project_management_system"
    if any(token in text for token in ["dotac", "grant", "wniosek", "funding"]):
        return "funding"
    employee_phrase_tokens = [
        "portal hr",
        "pracownic",
        "kadrow",
        "dokumenty kadrowe",
        "wnioski urlop",
        "urlop",
        "session timeout",
        "polityka has",
        "retencj",
    ]
    employee_word_tokens = ["hr", "dsr", "dpia", "dpo", "gdpr", "rodo", "ldap", "sso"]
    if _has_any(text, employee_phrase_tokens) or any(_has_word(text, token) for token in employee_word_tokens):
        return "employee_portal"
    if (
        any(token in text for token in ["allegro", "amazon", "marketplace", "ean", "e-commerce", "ecommerce"])
        and any(token in text for token in ["produkt", "opis", "csv", "zdjec", "obraz"])
    ):
        return "ecommerce_generator"
    mobile_tokens = [
        "mobile",
        "mobiln",
        "telefon",
        "approval token",
        "deep link",
        "offline",
        "technik",
        "checklist",
        "checklista",
        "firmware",
        ".ino",
        ".bin",
        "telemetri",
        "synchronizac",
        "sync",
        "urzadzen",
        "urządzen",
        "urządzeń",
        "zdjec serwis",
        "zdjecia serwis",
        "zdjęcia serwis",
    ]
    if any(token in text for token in mobile_tokens):
        return "operator_mobile"
    if any(
        token in text
        for token in [
            "system projektowy",
            "zarzadzanie projekt",
            "zarządzanie projekt",
            "portfolio projekt",
            "kanban",
            "gantt",
            "backlog",
            "sprint",
            "milestone",
            "kamienie milowe",
            "roadmap",
            "resource capacity",
            "capacity planning",
            "risk register",
            "budzet projektu",
            "budżet projektu",
            "release gate",
            "canary",
        ]
    ):
        return "project_management_system"
    if any(token in text for token in ["projektowanie wnetrz", "projektowanie wnętrz", "mebl", "pokoju 2d", "canvas"]):
        return "design_tool"
    if any(token in text for token in ["komunikator", "czat", "chat", "wiadomo", "rejestrac", "logow", "pokojami"]):
        return "chat_app"
    if any(token in text for token in ["dashboard", "panel", "operator console"]):
        return "dashboard"
    return "application"


def _council_weight(role: str, rank: str, explicit_weight: float | None = None) -> float:
    if explicit_weight is not None:
        return round(float(explicit_weight), 4)
    try:
        from sylion.governance.council_hybrid import DEFAULT_ROLE_WEIGHTS, RANK_MULTIPLIER
    except Exception:
        DEFAULT_ROLE_WEIGHTS = {}
        RANK_MULTIPLIER = {}
    canonical_rank = {"senior_specialist": "senior", "local_worker": "support"}.get(rank, rank)
    base = float(DEFAULT_ROLE_WEIGHTS.get(role, 0.8))
    multiplier = float(RANK_MULTIPLIER.get(canonical_rank, 1.0))
    return round(base * multiplier, 4)


def _council_member(
    role: str,
    responsibility: str,
    preferred_models: list[str],
    *,
    rank: str = "primary",
    voting_weight: float | None = None,
    required_signature: bool = False,
    approval_scope: str = "project_governance",
) -> dict[str, Any]:
    weight = _council_weight(role, rank, voting_weight)
    return {
        "role": role,
        "rank": rank,
        "voting_weight": weight,
        "responsibility": responsibility,
        "preferred_models": preferred_models,
        "required_signature": required_signature,
        "approval_scope": approval_scope,
    }


def _council_quorum_policy() -> dict[str, Any]:
    return {
        "type": "weighted_majority_with_adversarial_critic_signature",
        "minimum_weight_ratio": 0.6,
        "tie_breaker": "human_gate",
        "required_signatures": ["critic", "adversarial_critic"],
        "adversarial_critic_required": True,
    }


def _council_members_for_kind(kind: str) -> list[dict[str, Any]]:
    members = [
        _council_member("planner", "source of truth and masterplan coherence", ["gpt-4o-mini", "glm-4-plus", "qwen2.5:7b-instruct"], rank="primary"),
        _council_member("architect", "architecture, module boundaries and runtime topology", ["claude-haiku-4-5", "gpt-4o-mini", "glm-4-plus"], rank="primary"),
        _council_member("critic", "risk, scope drift and governance challenge", ["claude-haiku-4-5", "gpt-4o-mini"], rank="primary", required_signature=True),
        _council_member("adversarial_critic", "hard red-team role: challenge operator assumptions, model consensus, math, logic gaps and hidden failure modes", ["gpt-5", "claude-sonnet-4-6", "qwen2.5:7b-instruct"], rank="primary", required_signature=True),
        _council_member("governance", "Human Gate, cost, production and external-action policy", ["claude-haiku-4-5", "gpt-4o-mini"], rank="senior"),
        _council_member("verifier", "tests, evidence and operator-readiness", ["glm-4-plus", "sonar", "qwen2.5:7b-instruct"], rank="validation_only"),
    ]
    if kind == "funding":
        members.append(_council_member("funding_specialist", "grant fit, documents and submission governance", ["sonar", "claude-haiku-4-5", "gpt-4o-mini"], rank="senior"))
    elif kind == "mental_health_safety":
        members.append(_council_member("safety_clinician_reviewer", "crisis safety, no-diagnosis boundaries and professional hand-off policy", ["claude-haiku-4-5", "gpt-4o-mini", "pllum"], rank="primary", voting_weight=1.0, required_signature=True))
        members.append(_council_member("polish_context_specialist", "Polish wellbeing language, crisis phrasing and non-medical psychoeducation fit", ["pllum", "bielik:11b", "sonar"], rank="senior", voting_weight=0.85))
        members.append(_council_member("privacy_sentinel", "journal privacy, PII redaction, data minimization and local-only processing", ["bielik:11b", "pllum", "gpt-4o-mini"], rank="senior", voting_weight=0.85, required_signature=True))
        members.append(_council_member("source_sentinel", "current official emergency resources and source-backed safety copy", ["sonar", "gpt-4o-mini", "claude-haiku-4-5"], rank="support", voting_weight=0.55))
    elif kind == "bioinformatics_workflow":
        members.append(_council_member("domain_specialist", "bioinformatics QC, FASTQ/VCF workflow and research-only interpretation boundaries", ["pllum", "bielik:11b", "claude-haiku-4-5"], rank="senior", voting_weight=0.9))
        members.append(_council_member("clinical_safety_reviewer", "clinical safety, no-diagnosis guardrails and patient harm prevention", ["claude-haiku-4-5", "gpt-4o-mini", "pllum"], rank="primary", voting_weight=1.0, required_signature=True))
        members.append(_council_member("privacy_sentinel", "patient identifiers, PESEL, pseudonymization and local-only processing", ["bielik:11b", "pllum", "gpt-4o-mini"], rank="senior", voting_weight=0.85, required_signature=True))
        members.append(_council_member("funding_specialist", "Horizon Europe, EIC, FENG SMART and Digital Europe fit as supporting funding_scan", ["sonar", "pllum", "bielik:11b"], rank="support", voting_weight=0.55))
    elif kind == "marketplace_platform":
        members.append(_council_member("domain_specialist", "multi-tenant marketplace, vendor onboarding, catalog, checkout and operations fit", ["claude-haiku-4-5", "sonar", "gpt-4o-mini"], rank="senior", voting_weight=0.8))
        members.append(_council_member("payment_fraud_reviewer", "payment sandbox, refund, tax, shipping and fraud guardrails", ["gpt-4o-mini", "claude-haiku-4-5", "sonar"], rank="senior", voting_weight=0.9, required_signature=True))
        members.append(_council_member("security_sentinel", "tenant isolation, RBAC, checkout abuse, secret handling and release risk", ["claude-haiku-4-5", "gpt-4o-mini", "qwen2.5:7b-instruct"], rank="senior", voting_weight=0.8))
        members.append(_council_member("cost_sentinel", "Hetzner, payment sandbox, model and canary rollout budget guardrails", ["sonar", "qwen2.5:7b-instruct", "gpt-4.1-mini"], rank="support", voting_weight=0.5))
    elif kind == "ecommerce_generator":
        members.append(_council_member("domain_specialist", "marketplace, EAN, product-data and localization fit", ["sonar", "claude-haiku-4-5", "gpt-4o-mini"], rank="senior"))
        members.append(_council_member("legal_sentinel", "marketplace policy, claims, GPSR and publication guardrails", ["sonar", "claude-haiku-4-5", "gpt-4o-mini"], rank="support"))
    elif kind == "employee_portal":
        members.append(_council_member("security_sentinel", "PII, session policy, SSO/LDAP and abuse-case blocking", ["claude-haiku-4-5", "gpt-4o-mini", "bielik:11b"], rank="senior", voting_weight=0.8))
        members.append(_council_member("compliance_officer", "DPIA, GDPR DSR, retention and employee-data law evidence", ["sonar", "claude-haiku-4-5", "pllum"], rank="senior", voting_weight=0.9, required_signature=True))
        members.append(_council_member("red_team", "brute-force, session hijacking, access-control and injection challenge", ["gpt-4o-mini", "claude-haiku-4-5", "qwen2.5:7b-instruct"], rank="primary", voting_weight=1.0))
    elif kind == "operator_mobile":
        members.append(_council_member("security_sentinel", "device binding, firmware attachment guard, photo PII and mobile risk", ["claude-haiku-4-5", "gpt-4o-mini", "qwen2.5:7b-instruct"], rank="senior", voting_weight=0.8))
        members.append(_council_member("mobile_specialist", "offline-first UX, queue reconciliation and technician field workflow", ["kimi-k2", "glm-4-plus", "qwen2.5:7b-instruct"], rank="support", voting_weight=0.7))
        members.append(_council_member("red_team", "unsafe firmware upload, stale offline sync, device takeover and evidence tampering", ["gpt-4o-mini", "claude-haiku-4-5", "bielik:11b"], rank="primary", voting_weight=1.0))
    elif kind == "project_management_system":
        members.append(_council_member("domain_specialist", "portfolio, Kanban, Gantt, resource capacity and delivery workflow fit", ["claude-haiku-4-5", "kimi-k2", "qwen2.5:7b-instruct"], rank="senior", voting_weight=0.8))
        members.append(_council_member("security_sentinel", "multi-tenant RBAC, audit log, API integrations and production deployment risk", ["claude-haiku-4-5", "gpt-4o-mini", "bielik:11b"], rank="senior", voting_weight=0.8))
        members.append(_council_member("cost_sentinel", "Hetzner VPS cost, canary rollout spend and rollback budget guardrails", ["sonar", "qwen2.5:7b-instruct", "gpt-4.1-mini"], rank="support", voting_weight=0.5))
        members.append(_council_member("red_team", "permission bypass, dependency poisoning, bad release promotion and data leakage challenge", ["gpt-5", "claude-sonnet-4-6", "qwen2.5:7b-instruct"], rank="primary", voting_weight=1.0))
    elif kind in {"dashboard", "design_tool"}:
        members.append(_council_member("domain_specialist", f"{kind} domain alignment", ["claude-haiku-4-5", "glm-4-plus", "qwen2.5:7b-instruct"], rank="support"))
    return members


def _split_routing_models(raw: Any) -> list[str]:
    """Return model ids from a single or dual-judge routing value."""
    if raw is None:
        return []
    return [part.strip() for part in str(raw).split("+") if part and part.strip()]


def _provider_hint_for_model(model_id: str) -> str:
    lowered = str(model_id or "").strip().lower()
    if not lowered:
        return ""
    if ":" in lowered or "bielik" in lowered or "pllum" in lowered:
        return "ollama"
    if lowered.startswith("gpt") or lowered.startswith("o1") or lowered.startswith("o3") or lowered.startswith("o4"):
        return "openai"
    if lowered.startswith("claude"):
        return "anthropic"
    if lowered.startswith("sonar"):
        return "perplexity"
    if lowered.startswith("gemini"):
        return "google"
    if lowered.startswith("glm"):
        return "zai"
    if lowered.startswith("moonshot") or "kimi" in lowered:
        return "moonshot"
    if lowered.startswith("openrouter") or "/" in lowered:
        return "openrouter"
    if lowered.startswith("deepseek"):
        return "deepseek"
    return ""


def _safe_meta_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip().lower()
        if text:
            out.append(text)
    return sorted(set(out))


def _sanitize_project_onboarding_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Keep operator orchestration choices while dropping raw credentials."""
    if not isinstance(raw, dict):
        return {}
    allowed = {
        "operator_name",
        "goals",
        "usage_cadence",
        "configured_providers",
        "installed_local_models",
        "cost_ceilings",
        "subscriptions",
        "default_project_domain",
        "custom_domain_prefix",
        "autonomy_level",
        "council_size",
        "llm_judge_routing",
        "quality_speed_cost",
        "trusted_providers",
        "auto_trusted_providers",
        "blocked_providers",
        "funding_advisor_enabled",
        "funding_countries",
        "funding_pl_regions",
        "funding_model_profile",
    }
    sanitized: dict[str, Any] = {}
    for key in allowed:
        if key in raw:
            sanitized[key] = raw[key]
    return sanitized


def _routing_models_for_role(role: str, routing: dict[str, Any]) -> list[str]:
    role_to_risk = {
        "planner": "medium",
        "architect": "high",
        "critic": "critical",
        "adversarial_critic": "critical",
        "verifier": "low",
        "governance": "high",
        "compliance_officer": "high",
        "funding_specialist": "high",
        "domain_specialist": "medium",
        "safety_clinician_reviewer": "critical",
        "polish_context_specialist": "medium",
        "source_sentinel": "high",
        "clinical_safety_reviewer": "critical",
        "privacy_sentinel": "high",
        "bioinformatics_guard": "critical",
        "security_sentinel": "high",
        "cost_sentinel": "low",
        "legal_sentinel": "high",
        "finance": "medium",
        "red_team": "critical",
        "council_chair": "critical",
    }
    risk = role_to_risk.get(role, "medium")
    return _split_routing_models(routing.get(risk))


def _extend_council_roles(kind: str, members: list[dict[str, Any]], target_size: int) -> list[dict[str, Any]]:
    existing = {str(member.get("role") or "") for member in members}
    extras = [
        _council_member("cost_sentinel", "cost caps, prepaid limits and budget stop conditions", ["qwen2.5:7b-instruct", "sonar", "gpt-4.1-mini"], rank="support", voting_weight=0.4),
        _council_member("security_sentinel", "security, PII and abuse-case blocking", ["claude-haiku-4-5", "gpt-4.1-mini", "qwen2.5:7b-instruct"], rank="support", voting_weight=0.6),
        _council_member("legal_sentinel", "legal and regulatory guardrails", ["sonar", "claude-haiku-4-5", "gpt-4.1-mini"], rank="senior", voting_weight=0.7),
        _council_member("finance", "financial feasibility, cloud spend and grant-cost alignment", ["sonar", "gpt-4.1-mini", "qwen2.5:7b-instruct"], rank="support", voting_weight=0.5),
        _council_member("red_team", "adversarial misuse and failure-mode challenge", ["gpt-5", "claude-sonnet-4-6", "qwen2.5:7b-instruct"], rank="primary", voting_weight=1.0),
        _council_member("council_chair", "quorum, dissent handling and final consolidation", ["gpt-5", "claude-sonnet-4-6"], rank="primary", voting_weight=1.1, required_signature=True),
    ]
    for member in extras:
        if len(members) >= target_size:
            break
        if member["role"] in existing:
            continue
        members.append(member)
        existing.add(member["role"])
    return members[:target_size]


def _apply_onboarding_orchestration(
    blueprint: dict[str, Any],
    raw_config: dict[str, Any] | None,
    *,
    kind: str,
) -> dict[str, Any]:
    config = _sanitize_project_onboarding_config(raw_config)
    if not config:
        return blueprint

    governance = dict(blueprint.get("governance_policy") or {})
    execution = dict(blueprint.get("execution_plan") or {})
    audit = dict(blueprint.get("audit_plan") or {})
    council = dict(blueprint.get("council_plan") or {})

    autonomy = str(config.get("autonomy_level") or "").strip()
    if autonomy:
        governance["autonomy_mode"] = autonomy

    qsc = config.get("quality_speed_cost") if isinstance(config.get("quality_speed_cost"), dict) else {}
    if qsc:
        governance["quality_speed_cost"] = qsc
        execution["quality_speed_cost"] = qsc
        if float(qsc.get("speed") or 0) >= 0.5:
            execution["parallelism_policy"] = "speed_first"
            execution["local_docker_workers"] = max(int(execution.get("local_docker_workers") or 1), 4)
        if float(qsc.get("cost") or 0) >= 0.5:
            execution["cost_policy"] = "strict"
            execution["hard_stop"] = True
        if float(qsc.get("quality") or 0) >= 0.5:
            audit["masterplan_mode"] = "parallel"
            audit["critic_depth"] = "extended"

    ceilings = config.get("cost_ceilings") if isinstance(config.get("cost_ceilings"), dict) else {}
    if ceilings:
        try:
            hard_limit = float(ceilings.get("critical") or ceilings.get("high") or 0.0)
        except (TypeError, ValueError):
            hard_limit = 0.0
        if hard_limit > 0:
            execution["budget_usd"] = hard_limit
            execution["hard_limit_usd"] = hard_limit
            execution["soft_warn_usd"] = round(hard_limit * 0.8, 4)
            execution["hard_stop"] = True

    trusted = _safe_meta_list(config.get("trusted_providers"))
    auto_trusted = _safe_meta_list(config.get("auto_trusted_providers"))
    blocked = _safe_meta_list(config.get("blocked_providers"))
    configured = _safe_meta_list(config.get("configured_providers"))
    provider_policy = {
        "trusted": sorted(set(trusted + auto_trusted + configured) - set(blocked)),
        "auto_trusted": auto_trusted,
        "blocked": blocked,
    }
    governance["provider_policy"] = provider_policy

    routing = config.get("llm_judge_routing") if isinstance(config.get("llm_judge_routing"), dict) else {}
    if routing:
        governance["llm_judge_routing"] = routing

    base_members = list(council.get("members") or _council_members_for_kind(kind))
    try:
        target_size = int(config.get("council_size") or council.get("active_size") or len(base_members))
    except (TypeError, ValueError):
        target_size = len(base_members)
    target_size = max(len(base_members), min(11, target_size))
    members = _extend_council_roles(kind, base_members, target_size)

    for member in members:
        role = str(member.get("role") or "")
        routed = _routing_models_for_role(role, routing)
        if routed:
            allowed = [
                model_id
                for model_id in routed
                if _provider_hint_for_model(model_id) not in blocked
            ]
            if allowed:
                member["preferred_models"] = allowed + [
                    model_id
                    for model_id in list(member.get("preferred_models") or [])
                    if model_id not in allowed and _provider_hint_for_model(model_id) not in blocked
                ]
                member["model_id"] = allowed[0]
                provider = _provider_hint_for_model(allowed[0])
                if provider:
                    member["provider"] = provider
        elif blocked:
            member["preferred_models"] = [
                model_id
                for model_id in list(member.get("preferred_models") or [])
                if _provider_hint_for_model(model_id) not in blocked
            ]

    if config.get("funding_advisor_enabled") and kind == "funding":
        has_funding = any(str(member.get("role") or "") == "funding_specialist" for member in members)
        if not has_funding and len(members) < target_size:
            members.append(_council_member(
                "funding_specialist",
                "grant fit, Polish/EU call discovery and application evidence",
                ["sonar", "bielik", "pllum"],
                rank="senior",
                voting_weight=0.8,
            ))

    council["enabled"] = True
    council["suggested_size"] = target_size
    council["active_size"] = target_size
    council["members"] = members[:target_size]
    council["operator_configured"] = True
    council["llm_judge_routing"] = routing
    council["provider_policy"] = provider_policy

    governance["meta_orchestration_source"] = "advisor_onboarding"
    governance["funding_model_profile"] = config.get("funding_model_profile") or {}
    execution["trusted_provider_policy"] = provider_policy
    audit["operator_test_catalog_profile"] = {
        "quality_speed_cost": qsc,
        "funding_advisor_enabled": bool(config.get("funding_advisor_enabled")),
    }

    blueprint["governance_policy"] = governance
    blueprint["execution_plan"] = execution
    blueprint["audit_plan"] = audit
    blueprint["council_plan"] = council
    blueprint["onboarding_config"] = config
    return blueprint


def _blueprint_for_project(kind: str, preferred_stack: list[str]) -> dict[str, Any]:
    stack = preferred_stack or ["local-first", "FastAPI", "SQLite"]
    if kind == "chat_app":
        modules = ["kernel", "auth-and-rooms", "messaging-realtime", "integration_validation"]
        roles = ["frontend_builder", "backend_builder", "qa_validator", "governance_reviewer"]
    elif kind == "design_tool":
        modules = ["canvas_kernel", "layout_state", "furniture_tools", "integration_validation"]
        roles = ["ui_builder", "state_engineer", "interaction_builder", "qa_validator"]
    elif kind == "funding":
        modules = [
            "funding_intake",
            "official_source_search",
            "source_verification",
            "deadline_guard",
            "program_scoring",
            "eligibility_risk_matrix",
            "cost_budget_estimator",
            "polish_model_context_review",
            "document_package",
            "submission_governance",
            "audit_evidence_pack",
            "integration_validation",
        ]
        roles = [
            "funding_analyst",
            "source_verification_reviewer",
            "polish_context_reviewer",
            "document_builder",
            "governance_reviewer",
            "qa_validator",
        ]
    elif kind == "mental_health_safety":
        modules = [
            "wellbeing_intake",
            "crisis_classifier",
            "no_medical_advice_guard",
            "safe_response_generator",
            "emergency_handoff",
            "pii_minimization",
            "local_model_safety_review",
            "source_backed_resources",
            "release_safety_gate",
            "audit_evidence_pack",
            "integration_validation",
        ]
        roles = [
            "safety_product_builder",
            "crisis_safety_reviewer",
            "privacy_security_reviewer",
            "polish_language_reviewer",
            "qa_validator",
        ]
    elif kind == "bioinformatics_workflow":
        modules = [
            "synthetic_data_intake",
            "format_validation",
            "qc_pipeline",
            "sample_pseudonymization",
            "variant_research_scoring",
            "clinical_safety_guard",
            "funding_scan",
            "local_model_documentation",
            "audit_evidence_pack",
            "integration_validation",
        ]
        roles = [
            "bioinformatics_workflow_builder",
            "privacy_security_reviewer",
            "clinical_safety_reviewer",
            "funding_researcher",
            "qa_validator",
        ]
    elif kind == "marketplace_platform":
        modules = [
            "tenant_identity",
            "vendor_onboarding",
            "product_catalog",
            "cart_checkout",
            "payment_sandbox",
            "tax_shipping",
            "admin_console",
            "funding_scan",
            "release_governance",
            "integration_validation",
        ]
        roles = [
            "platform_architect",
            "backend_builder",
            "frontend_builder",
            "payments_reviewer",
            "security_reviewer",
            "release_manager",
            "qa_validator",
        ]
    elif kind == "ecommerce_generator":
        modules = [
            "image_brief_intake",
            "description_generation",
            "ean_validation",
            "marketplace_export",
            "human_review_gate",
            "integration_validation",
        ]
        roles = ["vision_builder", "copy_generation_builder", "marketplace_integrator", "governance_reviewer", "qa_validator"]
    elif kind == "employee_portal":
        modules = [
            "auth_users",
            "role_assignment",
            "document_workflow",
            "leave_request_workflow",
            "gdpr_dsr",
            "security_session_policy",
            "audit_evidence_pack",
            "integration_validation",
        ]
        roles = [
            "identity_builder",
            "workflow_builder",
            "gdpr_security_reviewer",
            "evidence_pack_builder",
            "qa_validator",
        ]
    elif kind == "operator_mobile":
        modules = [
            "mobile_shell",
            "offline_checklists",
            "firmware_attachment_guard",
            "photo_evidence_redaction",
            "sync_queue",
            "device_binding",
            "secure_approval",
            "audit_evidence_pack",
            "integration_validation",
        ]
        roles = [
            "mobile_builder",
            "offline_state_engineer",
            "firmware_security_reviewer",
            "sync_integrator",
            "qa_validator",
        ]
    elif kind == "project_management_system":
        modules = [
            "tenant_workspace",
            "portfolio_dashboard",
            "kanban_backlog",
            "gantt_roadmap",
            "resource_capacity",
            "risk_register",
            "budget_tracking",
            "notification_center",
            "api_integrations",
            "rbac_audit",
            "release_governance",
            "integration_validation",
        ]
        roles = [
            "workflow_architect",
            "frontend_builder",
            "security_reviewer",
            "finance_risk_reviewer",
            "release_manager",
            "qa_validator",
        ]
    elif kind == "dashboard":
        modules = ["api_contracts", "operator_console", "state_panels", "integration_validation"]
        roles = ["api_builder", "frontend_builder", "qa_validator", "governance_reviewer"]
    else:
        modules = ["application_core", "interface_layer", "integration_validation"]
        roles = ["builder", "reviewer", "qa_validator"]

    council_members = _council_members_for_kind(kind)
    governance_policy = {
        "autonomy_mode": "medium",
        "human_gate_required_for": [
            "source_of_truth_freeze",
            "masterplan_freeze",
            "production_deploy",
            "external_action",
            "final_approval",
        ],
        "decision_layers": ["operator", "planner_council", "engineer_council"],
    }
    if kind == "employee_portal":
        governance_policy.update(
            {
                "autonomy_mode": "low",
                "decision_class": "D4",
                "risk_class": "D4",
                "dpia_required": True,
                "pii_scope": "high",
                "human_gate_required_for": [
                    "source_of_truth_freeze",
                    "masterplan_freeze",
                    "dpia_required",
                    "gdpr_dsr",
                    "security_high",
                    "external_llm_processing",
                    "production_deploy",
                    "final_approval",
                ],
                "decision_layers": ["operator", "planner_council", "security_compliance_council", "engineer_council"],
            }
        )
    elif kind == "funding":
        governance_policy.update(
            {
                "autonomy_mode": "low",
                "decision_class": "D4",
                "risk_class": "D4",
                "source_truth_policy": "official_sources_required",
                "anti_hallucination_required": True,
                "funding_submission_allowed": False,
                "human_gate_required_for": [
                    "source_of_truth_freeze",
                    "masterplan_freeze",
                    "official_source_review",
                    "external_search_provider",
                    "budget_threshold",
                    "document_export",
                    "contact_institution",
                    "funding_submission",
                    "production_deploy",
                    "final_approval",
                ],
                "decision_layers": ["operator", "planner_council", "funding_source_council", "engineer_council"],
            }
        )
    elif kind == "marketplace_platform":
        governance_policy.update(
            {
                "autonomy_mode": "low",
                "decision_class": "D5",
                "risk_class": "D5",
                "multi_tenant": True,
                "money_flow_scope": "sandbox_only",
                "production_vps_scope": "hetzner",
                "human_gate_required_for": [
                    "source_of_truth_freeze",
                    "masterplan_freeze",
                    "payment_provider_choice",
                    "tax_shipping_policy",
                    "external_api_integration",
                    "budget_threshold",
                    "production_deploy",
                    "canary_promote",
                    "rollback_delete_cloud_resource",
                    "final_approval",
                ],
                "decision_layers": ["operator", "planner_council", "payment_security_council", "engineer_council"],
            }
        )
    elif kind == "mental_health_safety":
        governance_policy.update(
            {
                "autonomy_mode": "low",
                "decision_class": "D5",
                "risk_class": "D5",
                "medical_advice_allowed": False,
                "crisis_escalation_required": True,
                "processing_boundary": "local_only_until_humangate",
                "human_gate_required_for": [
                    "source_of_truth_freeze",
                    "masterplan_freeze",
                    "external_llm_processing",
                    "medical_or_therapy_claim",
                    "emergency_resource_update",
                    "public_release",
                    "production_deploy",
                    "final_approval",
                ],
                "decision_layers": ["operator", "planner_council", "privacy_crisis_safety_council", "engineer_council"],
            }
        )
    elif kind == "bioinformatics_workflow":
        governance_policy.update(
            {
                "autonomy_mode": "low",
                "decision_class": "D5",
                "risk_class": "D5",
                "pii_scope": "sensitive_health_research",
                "clinical_use_allowed": False,
                "processing_boundary": "local_only_until_humangate",
                "funding_scan_scope": "supporting_feature",
                "human_gate_required_for": [
                    "source_of_truth_freeze",
                    "masterplan_freeze",
                    "patient_data_import",
                    "external_llm_processing",
                    "clinical_claim_or_recommendation",
                    "report_export",
                    "funding_submission",
                    "production_deploy",
                    "final_approval",
                ],
                "decision_layers": ["operator", "planner_council", "privacy_clinical_safety_council", "engineer_council"],
            }
        )
    elif kind == "operator_mobile":
        governance_policy.update(
            {
                "autonomy_mode": "low",
                "decision_class": "D4",
                "risk_class": "D4",
                "offline_mode": True,
                "firmware_attachment_scope": "high",
                "photo_pii_scope": "possible_high",
                "human_gate_required_for": [
                    "source_of_truth_freeze",
                    "masterplan_freeze",
                    "firmware_upload",
                    "photo_pii_review",
                    "external_sync",
                    "device_binding",
                    "production_deploy",
                    "final_approval",
                ],
                "decision_layers": ["operator", "planner_council", "security_mobile_council", "engineer_council"],
            }
        )
    elif kind == "project_management_system":
        governance_policy.update(
            {
                "autonomy_mode": "low",
                "decision_class": "D4",
                "risk_class": "D4",
                "multi_tenant": True,
                "production_vps_scope": "hetzner",
                "human_gate_required_for": [
                    "source_of_truth_freeze",
                    "masterplan_freeze",
                    "rbac_policy_change",
                    "external_api_integration",
                    "budget_threshold",
                    "production_deploy",
                    "canary_promote",
                    "rollback_delete_cloud_resource",
                    "final_approval",
                ],
                "decision_layers": ["operator", "planner_council", "security_release_council", "engineer_council"],
            }
        )

    return {
        "worker_plan": {
            "modules": modules,
            "roles": roles,
            "scale_reason": "derived_from_project_intent",
        },
        "execution_plan": {
            "deployment_mode": "local_docker",
            "provisioning_mode": "local-first",
            "local_docker_workers": min(max(len(roles), 1), 3),
            "vps_workers": 0,
            "auto_provision": False,
        },
        "governance_policy": governance_policy,
        "council_plan": {
            "enabled": True,
            "suggested_size": len(council_members),
            "active_size": len(council_members),
            "members": council_members,
            "quorum_policy": _council_quorum_policy(),
        },
        "memory_policy": {
            "similarity_search": True,
            "reuse_successful_skills": True,
            "write_learning_snapshot": True,
        },
        "audit_plan": {
            "masterplan_mode": "parallel",
            "module_mode": "sequential",
            "override": "configurable",
            "auditors": ["security_officer", "quality_perf_reviewer", "compliance_officer", "dependency_guardian", "ux_reviewer", "doc_officer"],
        },
        "preferred_stack": stack,
    }


def _append_unique(items: list[str], additions: list[str]) -> list[str]:
    out = list(items)
    for item in additions:
        if item not in out:
            out.append(item)
    return out


def _apply_domain_profile_to_blueprint(blueprint: dict[str, Any], idea: str, kind: str) -> dict[str, Any]:
    """Keep a primary project type while adding multi-domain overlays."""
    profile = _detect_project_domain_profile(idea, kind)
    worker_plan = dict(blueprint.get("worker_plan") or {})
    execution_plan = dict(blueprint.get("execution_plan") or {})
    governance_policy = dict(blueprint.get("governance_policy") or {})
    council_plan = dict(blueprint.get("council_plan") or {})
    audit_plan = dict(blueprint.get("audit_plan") or {})
    modules = list(worker_plan.get("modules") or [])
    roles = list(worker_plan.get("roles") or [])
    human_gates = list(governance_policy.get("human_gate_required_for") or [])
    council_members = list(council_plan.get("members") or [])
    council_roles = {str(member.get("role") or "") for member in council_members if isinstance(member, dict)}
    runtime_constraints = profile.get("runtime_constraints") or {}
    strong_multi_domain = bool(
        profile.get("funding_is_supporting")
        or profile.get("operator_mobile_is_supporting")
        or "marketplace_platform" in profile.get("supporting_domains", [])
    )

    if profile.get("funding_is_supporting"):
        modules = _append_unique(modules, ["funding_scan", "official_source_review", "grant_evidence_pack"])
        roles = _append_unique(roles, ["funding_researcher", "source_verification_reviewer"])
        human_gates = _append_unique(human_gates, ["official_source_review", "document_export", "funding_submission"])
        governance_policy["funding_scan_scope"] = "supporting_feature"
        governance_policy["funding_submission_allowed"] = False
        if "funding_specialist" not in council_roles:
            council_members.append(_council_member("funding_specialist", "supporting funding scan, grant fit and no-submission governance", ["sonar", "claude-haiku-4-5", "gpt-4o-mini"], rank="support", voting_weight=0.55))
            council_roles.add("funding_specialist")

    if profile.get("operator_mobile_is_supporting"):
        modules = _append_unique(modules, ["mobile_approval_bridge", "device_binding", "secure_approval"])
        roles = _append_unique(roles, ["mobile_security_reviewer", "approval_flow_reviewer"])
        human_gates = _append_unique(human_gates, ["mobile_approval_token", "device_binding", "external_sync"])
        governance_policy["mobile_approval_scope"] = "bound_device_only"

    if profile.get("runtime_is_supporting") and strong_multi_domain:
        runtime_modules = ["runtime_environment_matrix"]
        if not runtime_constraints.get("vps_blocked_until_human_gate"):
            runtime_modules.append("vps_capacity_policy")
        modules = _append_unique(modules, runtime_modules)
        if runtime_constraints.get("vps_blocked_until_human_gate"):
            modules = [name for name in modules if name != "vps_capacity_policy"]
        roles = _append_unique(roles, ["runtime_reviewer"])
        human_gates = _append_unique(human_gates, ["runtime_expansion", "budget_threshold", "production_deploy"])
        execution_plan["runtime_expansion_requires_human_gate"] = True
        governance_policy["runtime_expansion_requires_human_gate"] = True
        if runtime_constraints.get("local_environment_count"):
            execution_plan["local_environment_count"] = runtime_constraints["local_environment_count"]
        if runtime_constraints.get("vps_blocked_until_human_gate"):
            execution_plan["provisioning_mode"] = "local-first"
            execution_plan["planned_runtime_expansion"] = "blocked_future_human_gate"
            governance_policy["vps_blocked_until_human_gate"] = True
            governance_policy["planned_runtime_expansion"] = "future_change_proposal_only"
        if "cost_sentinel" not in council_roles:
            council_members.append(_council_member("cost_sentinel", "runtime capacity, VPS worker count and prepaid budget guardrails", ["sonar", "qwen2.5:7b-instruct", "gpt-4.1-mini"], rank="support", voting_weight=0.5))
            council_roles.add("cost_sentinel")

    if "governance" in profile.get("supporting_domains", []) and strong_multi_domain:
        modules = _append_unique(modules, ["human_gate_queue", "source_of_truth_control", "council_decision_log"])
        roles = _append_unique(roles, ["governance_reviewer"])
        human_gates = _append_unique(human_gates, ["source_of_truth_freeze", "masterplan_freeze", "final_approval"])

    if profile.get("is_multi_domain") and strong_multi_domain:
        modules = _append_unique(modules, ["cross_domain_orchestration"])
        worker_plan["scale_reason"] = "multi_domain_project_intent"
        audit_plan["multi_domain_review"] = True
        audit_plan["domain_profile"] = profile
        council_plan["domain_profile"] = profile

    worker_plan["modules"] = modules
    worker_plan["roles"] = roles
    worker_plan["domain_profile"] = profile
    governance_policy["human_gate_required_for"] = human_gates
    governance_policy["domain_profile"] = profile
    execution_plan["domain_profile"] = profile
    council_plan["members"] = council_members
    council_plan["suggested_size"] = len(council_members)
    council_plan["active_size"] = len(council_members)
    council_plan["quorum_policy"] = _council_quorum_policy()

    blueprint["worker_plan"] = worker_plan
    blueprint["execution_plan"] = execution_plan
    blueprint["governance_policy"] = governance_policy
    blueprint["council_plan"] = council_plan
    blueprint["audit_plan"] = audit_plan
    blueprint["domain_profile"] = profile
    return blueprint


def _default_project_questions(kind: str, runtime_constraints: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    runtime_constraints = runtime_constraints or {}
    runtime_choices = [
        {
            "choice_id": "runtime_local_only",
            "label": "Local only",
            "rationale": "Brak platnych zasobow i brak ryzyka produkcyjnego.",
            "consequences": "VPS i zewnetrzne akcje pozostaja zablokowane do osobnej zgody.",
        }
    ]
    if runtime_constraints.get("vps_blocked_until_human_gate") and (
        runtime_constraints.get("vps_explicit_block") or runtime_constraints.get("production_blocked_until_human_gate")
    ):
        runtime_choices.append(
            {
                "choice_id": "runtime_change_proposal_only",
                "label": "Tylko Change Proposal",
                "rationale": "Nie planuje VPS ani Hetznera w tym Masterplanie; ewentualna ekspansja runtime wymaga nowej Rady i Human Gate.",
                "consequences": "Projekt pozostaje local-first, a produkcja i akcje zewnetrzne sa poza wykonaniem.",
            }
        )
    else:
        runtime_choices.append(
            {
                "choice_id": "runtime_hybrid_later",
                "label": "Hybrid later",
                "rationale": "Pozwala zaplanowac VPS, ale nie uruchamia go bez Human Gate.",
                "consequences": "Masterplan oznaczy runtime expansion jako przyszly approval.",
            }
        )
    if runtime_constraints.get("vps_blocked_until_human_gate"):
        return [
            {
                "key": "direction_approval",
                "phase": "canon",
                "context": "Potwierdz kierunek projektu przed budowa Source of Truth.",
                "choices": [
                    {
                        "choice_id": "direction_local_first",
                        "label": "MVP local-first",
                        "rationale": "Najbezpieczniejszy start bez produkcji i bez kosztow zewnetrznych.",
                        "consequences": "System przygotuje SoT i Masterplan w trybie lokalnym.",
                    },
                    {
                        "choice_id": "direction_full_scope",
                        "label": "Pelniejszy zakres",
                        "rationale": "Wiekszy zakres wymaga silniejszego governance i testow.",
                        "consequences": "System uwzgledni wiecej modulow oraz bramek Human Gate.",
                    },
                ],
                "source": "council",
                "sort_order": 0,
            },
            {
                "key": "runtime_policy",
                "phase": "masterplan",
                "context": f"Potwierdz topologie runtime dla projektu typu {kind}.",
                "choices": runtime_choices,
                "source": "council",
                "sort_order": 1,
            },
        ]

    return [
        {
            "key": "direction_approval",
            "phase": "canon",
            "context": "Potwierdź kierunek projektu przed budową Source of Truth.",
            "choices": [
                {
                    "choice_id": "direction_local_first",
                    "label": "MVP local-first",
                    "rationale": "Najbezpieczniejszy start bez produkcji i bez kosztów zewnętrznych.",
                    "consequences": "System przygotuje SoT i masterplan w trybie lokalnym.",
                },
                {
                    "choice_id": "direction_full_scope",
                    "label": "Pełniejszy zakres",
                    "rationale": "Większy zakres wymaga silniejszego governance i testów.",
                    "consequences": "System uwzględni więcej modułów oraz bramek Human Gate.",
                },
            ],
            "source": "council",
            "sort_order": 0,
        },
        {
            "key": "runtime_policy",
            "phase": "masterplan",
            "context": f"Potwierdź topologię runtime dla projektu typu {kind}.",
            "choices": [
                {
                    "choice_id": "runtime_local_only",
                    "label": "Local only",
                    "rationale": "Brak płatnych zasobów i brak ryzyka produkcyjnego.",
                    "consequences": "VPS i zewnętrzne akcje pozostają zablokowane do osobnej zgody.",
                },
                {
                    "choice_id": "runtime_hybrid_later",
                    "label": "Hybrid later",
                    "rationale": "Pozwala zaplanowac VPS, ale nie uruchamia go bez Human Gate.",
                    "consequences": "Masterplan oznaczy runtime expansion jako przyszly approval.",
                },
            ],
            "source": "council",
            "sort_order": 1,
        },
    ]


def _project_documents(title: str, idea: str, kind: str, modules: list[str]) -> tuple[str, str, dict[str, Any]]:
    module_lines = "\n".join(f"- {name}" for name in modules)
    if kind == "marketplace_platform":
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: marketplace_platform",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                "Platforma marketplace SaaS obsluguje wielu tenantow i vendorow, katalog produktow, koszyk, checkout, platnosci sandbox, podatki, shipping, panel admina, governance release oraz funding scan jako funkcje wspierajaca, nie jako glowny typ projektu.",
                "",
                "## Guardrails",
                "- Platnosci sa tylko sandbox do czasu osobnego HumanGate dla providera platnosci.",
                "- Izolacja tenantow, RBAC i panel admina wymagaja security review.",
                "- Tax/shipping policy wymaga jawnej decyzji operatora i evidence.",
                "- Deploy na Hetzner i canary wymagaja Production/External Action HumanGate.",
                "- Funding scan moze szukac grantow dla produktu, ale nie moze zmienic typu projektu na funding-only.",
                "",
                "## Kryteria sukcesu",
                "- Artefakt pokazuje tenant identity, vendor onboarding, katalog, koszyk i checkout sandbox.",
                "- Bledy czlowieka sa blokowane: brak tenant context, checkout bez HG, przekroczenie budzetu, release bez testow.",
                "- Evidence pack zawiera decyzje Council, HumanGate, koszt, testy, health check i rollback/cleanup.",
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zamroz Source of Truth D5 z critic signature, payment/fraud reviewer i sentinels.",
                "2. Zbuduj tenant_identity, vendor_onboarding, product_catalog oraz admin_console.",
                "3. Zbuduj cart_checkout z payment_sandbox oraz blokada realnych platnosci bez HumanGate.",
                "4. Dodaj tax_shipping i external API policy z jawna decyzja operatora.",
                "5. Dodaj funding_scan jako osobny modul wspierajacy grant discovery dla produktu.",
                "6. Dodaj release_governance: test catalog, canary steps, rollback plan, W18 reports i HumanGate.",
                "7. Po osobnej zgodzie operatora wykonaj Hetzner deploy, health-check, rollback albo cleanup.",
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "decision_class": "D5",
            "multi_tenant": True,
            "money_flow_scope": "sandbox_only",
            "production_vps_scope": "hetzner",
            "human_gate": [
                "direction",
                "source_of_truth",
                "masterplan",
                "payment_provider_choice",
                "tax_shipping_policy",
                "production_deploy",
                "canary_promote",
                "rollback_delete_cloud_resource",
                "final",
            ],
        }
        return canonical_book, masterplan, canon_snapshot
    if kind == "mental_health_safety":
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: mental_health_safety",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                "Aplikacja wellbeing obsluguje samoobserwacje nastroju, psychoedukacje i bezpieczne odpowiedzi po polsku. Nie diagnozuje, nie prowadzi terapii i nie udziela porad medycznych.",
                "",
                "## Guardrails D5",
                "- Kryzys, autoagresja, mysli samobojcze, przemoc albo pilne zagrozenie uruchamiaja crisis_classifier oraz emergency_handoff.",
                "- Diagnoza, plan terapii, dawkowanie, zalecenie medyczne i tresci kliniczne sa blokowane przez no_medical_advice_guard.",
                "- Notatki uzytkownika podlegaja pii_minimization i nie moga byc wysylane do zewnetrznego LLM bez HumanGate.",
                "- Aktualizacja zasobow pomocowych, publiczny release, deploy produkcyjny i finalna akceptacja wymagaja HumanGate.",
                "- Perplexity/Google moga sluzyc tylko do zrodel publicznych i aktualnych zasobow, nie do przetwarzania prywatnych wpisow.",
                "",
                "## Kryteria sukcesu",
                "- Artefakt blokuje puste wpisy, PII, diagnoze/terapie i zewnetrzny runtime bez HG.",
                "- Artefakt generuje normalna odpowiedz wellbeing bez medycznych roszczen.",
                "- Artefakt generuje odpowiedz kryzysowa z hand-off i bez eskalacji do modelu zewnetrznego.",
                "- Evidence pack pokazuje crisis_classifier, no_medical_advice_guard, pii_minimization, source_backed_resources, release_safety_gate i HumanGate.",
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zamroz Source of Truth D5 z podpisem safety_clinician_reviewer i privacy_sentinel.",
                "2. Zbuduj wellbeing_intake, pii_minimization i lokalny runtime safety-first.",
                "3. Zbuduj crisis_classifier, no_medical_advice_guard oraz safe_response_generator.",
                "4. Dodaj emergency_handoff i source_backed_resources z osobnym HumanGate dla zmian zrodel.",
                "5. Dodaj local_model_safety_review dla Bielik/PLLuM i blokade external LLM bez HG.",
                "6. Dodaj release_safety_gate, test catalog i audit_evidence_pack.",
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "decision_class": "D5",
            "medical_advice_allowed": False,
            "crisis_escalation_required": True,
            "processing_boundary": "local_only_until_humangate",
            "human_gate": [
                "direction",
                "source_of_truth",
                "masterplan",
                "external_llm_processing",
                "medical_or_therapy_claim",
                "emergency_resource_update",
                "public_release",
                "final",
            ],
        }
        return canonical_book, masterplan, canon_snapshot
    if kind == "bioinformatics_workflow":
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: bioinformatics_workflow",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                "Lokalny workflow bioinformatyczny obsluguje syntetyczny albo jawnie zatwierdzony import FASTQ/VCF, walidacje formatu, QC pipeline, pseudonimizacje probek, research-only scoring wariantow, clinical_safety_guard, funding_scan dla Horizon/EIC/FENG/Digital Europe oraz local_model_documentation dla Bielik/PLLuM/Ollama.",
                "",
                "## Guardrails D5",
                "- Dane pacjenta, PESEL, material kliniczny i import realnych probek wymagaja HumanGate.",
                "- System dziala local-only do czasu osobnego HumanGate dla zewnetrznego LLM/API.",
                "- Wyniki sa research-only i nie moga zawierac diagnozy, terapii ani zalecen klinicznych.",
                "- Eksport raportu, funding submission i produkcyjny deploy wymagaja osobnych bramek HumanGate.",
                "- Funding scan jest funkcja wspierajaca bioinformatics_workflow i nie moze zmienic typu projektu na funding-only.",
                "",
                "## Kryteria sukcesu",
                "- Artefakt blokuje zly format pliku, PESEL w opisie, hybrydowy runtime bez HG i eksport bez HG.",
                "- Artefakt przeprowadza poprawna sekwencje: import VCF/FASTQ, QC, pseudonimizacja, research scoring, funding scan, evidence pack.",
                "- Evidence pack pokazuje clinical_safety_guard, local_only, pii_guard, funding_scan, export_hg i brak uzycia klinicznego.",
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zamroz Source of Truth D5 z podpisem clinical_safety_reviewer i privacy_sentinel.",
                "2. Zbuduj synthetic_data_intake oraz format_validation dla FASTQ/VCF bez importu realnych danych bez HG.",
                "3. Zbuduj qc_pipeline oraz sample_pseudonymization z PESEL/PII guard.",
                "4. Zbuduj variant_research_scoring z twardym research-only/no clinical use guard.",
                "5. Dodaj funding_scan jako modul wspierajacy Horizon Europe, EIC, FENG SMART i Digital Europe.",
                "6. Dodaj local_model_documentation dla Bielik/PLLuM/Ollama oraz blokade external LLM bez HG.",
                "7. Dodaj audit_evidence_pack, test catalog i report_export HumanGate.",
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "decision_class": "D5",
            "pii_scope": "sensitive_health_research",
            "clinical_use_allowed": False,
            "funding_scan_scope": "supporting_feature",
            "human_gate": [
                "direction",
                "source_of_truth",
                "masterplan",
                "patient_data_import",
                "external_llm_processing",
                "clinical_claim_or_recommendation",
                "report_export",
                "funding_submission",
                "final",
            ],
        }
        return canonical_book, masterplan, canon_snapshot
    if kind == "ecommerce_generator":
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: ecommerce_generator",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                "Aplikacja lokalnie analizuje brief produktu i zalaczone obrazy, generuje opisy PL/EN/DE, sugeruje lub waliduje EAN, przygotowuje eksport CSV dla Allegro i Amazon oraz wymusza HumanGate przed kazda publikacja lub wysylka danych poza system.",
                "",
                "## Poza zakresem",
                "Automatyczna publikacja do marketplace, pobieranie oplat, wysylka danych produktowych do zewnetrznych API i finalne zatwierdzenie opisow bez operatora sa zablokowane do osobnego HumanGate.",
                "",
                "## Kryteria sukcesu",
                "- Formularz przyjmuje brief i pliki produktu.",
                "- Generator tworzy opisy w trzech jezykach z widocznym statusem jakosci.",
                "- EAN ma osobny status walidacji i nie moze byc wymyslany bez oznaczenia niepewnosci.",
                "- Eksport CSV dziala dopiero po HumanGate.",
                "- Evidence pack zawiera brief, decyzje, status EAN, eksport i timestamp.",
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zatwierdz pelny zakres e-commerce i zamroz Source of Truth.",
                "2. Zbuduj intake obrazow i briefow z lokalna walidacja danych.",
                "3. Zbuduj generator opisow PL/EN/DE z kontrola halucynacji i brakow.",
                "4. Zbuduj walidator EAN oraz eksport CSV Allegro/Amazon.",
                "5. Wymus HumanGate przed eksportem/publikacja i zapisz evidence pack.",
                "6. Zweryfikuj artefakt klikaniem: bledny EAN, brak briefu, proba eksportu bez HG, poprawny eksport po HG.",
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "human_gate": ["direction", "source_of_truth", "masterplan", "product_review", "external_export", "final"],
        }
        return canonical_book, masterplan, canon_snapshot
    if kind == "employee_portal":
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: employee_portal",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                "Portal HR obsluguje logowanie pracownikow, role HR/DPO/admin/pracownik, dokumenty kadrowe, wnioski urlopowe, DSR GDPR, retencje danych oraz audit evidence pack. Dane PII maja zakres high i wymagaja DPIA przed buildem produkcyjnym.",
                "",
                "## Guardrails",
                "- SSO/LDAP i lokalne konto awaryjne wymagaja polityki sesji.",
                "- Session timeout: 30 min, inactivity logout: 15 min.",
                "- Rate limit: 5 prob logowania / 15 min / user+IP.",
                "- Password policy: minimum 14 znakow, MFA dla HR/DPO/admin, lockout po 5 probach.",
                "- DSR export i erasure wymagaja HumanGate DPO.",
                "- Retencja: dokumenty kadrowe wedlug kategorii, logi audytowe 2 lata, dane robocze 90 dni.",
                "",
                "## Kryteria sukcesu",
                "- Artefakt pokazuje role i blokady dostepu.",
                "- Obieg dokumentow ma stany draft/review/approved/archived.",
                "- Wniosek urlopowy przechodzi przez akceptacje managera.",
                "- DSR export dziala lokalnie, a erasure jest blokowane do HumanGate DPO.",
                "- Evidence pack zapisuje decyzje, kontrole security i status DPIA.",
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zamroz Source of Truth z D4 HumanGate i podpisem compliance.",
                "2. Zbuduj auth_users oraz role_assignment dla pracownika, HR, DPO, admina i managera.",
                "3. Zbuduj document_workflow oraz leave_request_workflow z lokalnym evidence log.",
                "4. Zbuduj gdpr_dsr: export dostepny lokalnie, erasure blokowane do HumanGate DPO.",
                "5. Wdroż security_session_policy: session timeout, inactivity logout, rate limit i password policy.",
                "6. Wygeneruj audit_evidence_pack i uruchom testy: zla rola, bledny login, DSR bez DPO, poprawny obieg.",
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "decision_class": "D4",
            "pii_scope": "high",
            "dpia_required": True,
            "human_gate": ["direction", "source_of_truth", "masterplan", "dpia", "gdpr_dsr", "security_high", "final"],
        }
        return canonical_book, masterplan, canon_snapshot
    if kind == "operator_mobile":
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: operator_mobile",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                "Mobilny asystent serwisowy dziala offline-first dla technikow w terenie. Obsluguje checklisty, zalaczniki firmware (.ino/.bin/.hex), zdjecia dowodowe, lokalna redakcje PII, kolejke synchronizacji, device binding oraz evidence pack. Sync zewnetrzny i firmware wymagaja HumanGate.",
                "",
                "## Guardrails",
                "- Tryb offline nie moze tracic checklist ani zalacznikow.",
                "- Firmware upload wymaga walidacji rozszerzenia, hash proof i HumanGate.",
                "- Zdjecia dowodowe musza przejsc redakcje PII przed synchronizacja.",
                "- Synchronizacja z chmura jest blokowana, gdy urzadzenie nie jest powiazane albo HumanGate nie zostal zatwierdzony.",
                "- Evidence pack zapisuje klikniecia, status sync, firmware hash, redakcje zdjec i decyzje operatora.",
                "",
                "## Kryteria sukcesu",
                "- Artefakt pokazuje bledy czlowieka: sync offline, firmware bez HG, zdjecie bez redakcji.",
                "- Po poprawnej sekwencji device binding + redakcja + HumanGate + online sync przechodzi.",
                "- Worker outputs sa przypisane do modulow offline_checklists, firmware_attachment_guard, photo_evidence_redaction, sync_queue, device_binding, secure_approval i audit_evidence_pack.",
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zamroz Source of Truth z D4 HumanGate dla firmware, zdjec i sync.",
                "2. Zbuduj mobile_shell oraz offline_checklists z lokalna kolejka zdarzen.",
                "3. Zbuduj firmware_attachment_guard: typ pliku, hash, blokada bez HumanGate.",
                "4. Zbuduj photo_evidence_redaction i wymus redakcje PII przed sync.",
                "5. Zbuduj sync_queue, device_binding i secure_approval dla operatora mobilnego.",
                "6. Wygeneruj audit_evidence_pack i wykonaj testy klikaniem: bledny plik, brak HG, offline sync, redakcja zdjec, poprawny sync.",
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "decision_class": "D4",
            "offline_mode": True,
            "firmware_attachment_scope": "high",
            "photo_pii_scope": "possible_high",
            "human_gate": [
                "direction",
                "source_of_truth",
                "masterplan",
                "firmware_upload",
                "photo_pii_review",
                "device_binding",
                "external_sync",
                "production",
                "final",
            ],
        }
        return canonical_book, masterplan, canon_snapshot
    if kind == "project_management_system":
        runtime_constraints = _project_runtime_constraints(idea)
        vps_blocked_until_gate = bool(runtime_constraints.get("vps_blocked_until_human_gate"))
        local_env_count = runtime_constraints.get("local_environment_count")
        if vps_blocked_until_gate:
            modules = [name for name in modules if name != "vps_capacity_policy"]
            module_lines = "\n".join(f"- {name}" for name in modules)
        local_environment_label_list = _project_local_environment_labels(idea, local_env_count)
        local_environment_labels = ", ".join(local_environment_label_list)
        local_environment_short = "/".join(local_environment_label_list[:2]) if local_environment_label_list else "dev/staging"
        runtime_scope = (
            "System projektowy obsluguje wiele workspace'ow, portfolio projektow, backlog, Kanban, roadmap/Gantt, sprinty, capacity planning, budzet, ryzyka, integracje API, RBAC, audit trail oraz release governance. Runtime pozostaje local-first; produkcja, VPS i akcje zewnetrzne sa poza planem wykonawczym do osobnego HumanGate."
            if vps_blocked_until_gate
            else "System projektowy obsluguje wiele workspace'ow, portfolio projektow, backlog, Kanban, roadmap/Gantt, sprinty, capacity planning, budzet, ryzyka, integracje API, RBAC, audit trail oraz release governance. Produkcyjny deploy na Hetzner VPS wymaga HumanGate i jawnej zgody finansowej operatora."
        )
        vps_guardrail = (
            f"- VPS, produkcja i akcje zewnetrzne pozostaja zablokowane; mozna przygotowac tylko lokalne {local_environment_labels or local_environment_short} i future Change Proposal."
            if vps_blocked_until_gate
            else "- Utworzenie lub usuniecie VPS jest akcja finansowa i wymaga osobnego potwierdzenia."
        )
        runtime_success = (
            f"- Runtime ma dzialac lokalnie w {local_env_count} srodowiskach: {local_environment_labels}; zadna sciezka nie tworzy VPS bez nowej zgody."
            if vps_blocked_until_gate and local_env_count
            else "- Sciezka local-first jest gotowa, a VPS/produkcja sa tylko przyszla bramka HumanGate."
            if vps_blocked_until_gate
            else "- Deploy bundle jest gotowy, a tor Hetzner tworzy realny health-check HTTP dopiero po zgodzie operatora."
        )
        masterplan_runtime_step = (
            f"7. Oznacz VPS, produkcje i akcje zewnetrzne jako future Change Proposal; kontynuuj tylko lokalne {local_environment_labels or local_environment_short} po HumanGate dla SoT i Masterplanu."
            if vps_blocked_until_gate
            else "7. Po osobnej zgodzie operatora utworz Hetzner VPS z cloud-init, wystaw artefakt przez nginx, wykonaj health-check i zapisz evidence."
        )
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: project_management_system",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                runtime_scope,
                "",
                "## Guardrails",
                vps_guardrail,
                "- Zmiana RBAC, integracji API, budzetu lub release gate wymaga HumanGate.",
                "- Release przechodzi przez canary 0 -> 1 -> 5 -> 25 -> 50 -> 100 z auto-rollback przy error_rate > 1%.",
                "- Evidence pack musi zawierac SoT, Masterplan, decyzje rady, testy UI, wynik health-check i plan rollback.",
                "- System blokuje puste zadania, task bez wlasciciela, przekroczenie budzetu i release bez podpisu.",
                "",
                "## Kryteria sukcesu",
                "- Artefakt pozwala dodac projekt, sprint, zadania, zaleznosci, ryzyko i budzet.",
                "- Bledy czlowieka sa blokowane: puste zadanie, budzet ponad cap, release bez testow, akcja bez roli release_manager.",
                runtime_success,
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zamroz Source of Truth D4 z council critic signature i cost/security sentinel.",
                "2. Zbuduj tenant_workspace, portfolio_dashboard, kanban_backlog i gantt_roadmap.",
                "3. Dodaj resource_capacity, risk_register i budget_tracking z blokada przekroczenia cap.",
                "4. Dodaj notification_center, api_integrations i rbac_audit.",
                "5. Dodaj release_governance: test catalog, canary steps, rollback plan i HumanGate.",
                "6. Zbuduj artefakt HTML, testuj klikaniem bledy czlowieka, potem wygeneruj bundle deploy.",
                masterplan_runtime_step,
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "decision_class": "D4",
            "multi_tenant": True,
            "production_vps_scope": "blocked_future_human_gate" if vps_blocked_until_gate else "hetzner",
            "runtime_constraints": runtime_constraints,
            "human_gate": [
                "direction",
                "source_of_truth",
                "masterplan",
                "budget_threshold",
                "rbac_policy_change",
                "production_deploy",
                "canary_promote",
                "rollback_delete_cloud_resource",
                "final",
            ],
        }
        return canonical_book, masterplan, canon_snapshot
    if kind == "funding":
        canonical_book = "\n".join(
            [
                f"# Source of Truth: {title}",
                "",
                "Typ projektu: funding",
                f"Intencja operatora: {idea}",
                "",
                "## Zakres",
                "Modul funding wyszukuje i porownuje realne programy grantowe dla software/R&D: FENG SMART, PARP, NCBR, Horizon Europe, EIC Accelerator, Digital Europe i programy regionalne. Perplexity i Google sa tylko warstwa discovery; zrodlem prawdy musi byc oficjalny URL programu albo jawnie oznaczona notatka operatora.",
                "",
                "## Guardrails",
                "- Fikcyjny grant, brak URL, nieoficjalna domena bez potwierdzenia lub nieaktualny deadline blokuja scoring.",
                "- Bielik i PLLuM sluza do polskiego kontekstu jezykowo-prawnego, ale nie podpisuja kwalifikowalnosci bez zrodel.",
                "- Claude/GPT moga krytykowac dokumenty i ryzyka, ale nie moga wyslac wniosku ani kontaktu do instytucji.",
                "- Kontakt z PARP/NCBR/KE, eksport dokumentow i submission wymagaja HumanGate.",
                "",
                "## Kryteria sukcesu",
                "- Intake przyjmuje opis produktu, TRL, region, budzet, deadline i cytowane zrodla.",
                "- source_verification odrzuca brak zrodel i podejrzane/fikcyjne programy.",
                "- deadline_guard odrzuca terminy z przeszlosci albo bez daty.",
                "- program_scoring daje wynik tylko po HumanGate official_source_review.",
                "- evidence pack zawiera zrodla, scoring, ryzyka, modele PL i status bramek.",
                "",
                "## Moduly",
                module_lines,
            ]
        )
        masterplan = "\n".join(
            [
                f"# Masterplan: {title}",
                "",
                "1. Zamroz Source of Truth D4 z wymogiem official_source_review.",
                "2. Zbuduj funding_intake, official_source_search, source_verification i deadline_guard.",
                "3. Skonfiguruj routing: Perplexity/Google discovery, Bielik/PLLuM polski kontekst, Claude/GPT critic.",
                "4. Zbuduj program_scoring, eligibility_risk_matrix i cost_budget_estimator.",
                "5. Zbuduj document_package i submission_governance z blokada kontaktu/submission do HumanGate.",
                "6. Przetestuj klikaniem: brak zrodla, fikcyjny URL, deadline w przeszlosci, scoring bez HG, scoring po HG, eksport bez HG i evidence pack.",
                "",
                "## Moduly wykonawcze",
                module_lines,
            ]
        )
        canon_snapshot = {
            "project_kind": kind,
            "idea": idea,
            "modules": modules,
            "decision_class": "D4",
            "source_truth_policy": "official_sources_required",
            "models": ["Perplexity", "Google", "Bielik", "PLLuM", "Claude/GPT critic"],
            "human_gate": [
                "direction",
                "source_of_truth",
                "masterplan",
                "official_source_review",
                "external_search_provider",
                "document_export",
                "contact_institution",
                "funding_submission",
                "final",
            ],
        }
        return canonical_book, masterplan, canon_snapshot
    canonical_book = "\n".join(
        [
            f"# Source of Truth: {title}",
            "",
            f"Typ projektu: {kind}",
            f"Intencja operatora: {idea}",
            "",
            "## Zakres",
            "System ma przygotować lokalny, kontrolowany artefakt wykonawczy zgodny z intencją operatora.",
            "",
            "## Poza zakresem",
            "Produkcja, zewnętrzne wysyłki, płatne zasoby i finalne publikacje wymagają osobnego Human Gate.",
            "",
            "## Kryteria sukcesu",
            "Powstaje artefakt, modułowe outputy, walidacja, audit trail, deployment bundle oraz zapis do pamięci.",
            "",
            "## Moduły",
            module_lines,
        ]
    )
    masterplan = "\n".join(
        [
            f"# Masterplan: {title}",
            "",
            "1. Zatwierdź kierunek i Source of Truth przez Human Gate.",
            "2. Zbuduj modułowy plan wykonania z lokalnym runtime.",
            "3. Wykonaj build, walidację, audyt i paczkę deploymentową.",
            "4. Zapisz wynik do memory layer i wystaw operatorowi status gotowości.",
            "",
            "## Moduły wykonawcze",
            module_lines,
        ]
    )
    canon_snapshot = {
        "project_kind": kind,
        "idea": idea,
        "modules": modules,
        "human_gate": ["direction", "source_of_truth", "masterplan", "production", "external", "final"],
    }
    return canonical_book, masterplan, canon_snapshot


def _apply_domain_profile_to_documents(
    canonical_book: str,
    masterplan: str,
    canon_snapshot: dict[str, Any],
    domain_profile: dict[str, Any] | None,
) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(domain_profile, dict) or not domain_profile:
        return canonical_book, masterplan, canon_snapshot
    snapshot = dict(canon_snapshot)
    snapshot["domain_profile"] = domain_profile
    domains = ", ".join(domain_profile.get("domains") or [])
    supporting = ", ".join(domain_profile.get("supporting_domains") or []) or "brak"
    canon_lines = [
        "",
        "## Profil wielodomenowy AEIS",
        f"- Glowny typ projektu: {domain_profile.get('primary_kind', '')}",
        f"- Domena glowna: {domain_profile.get('primary_domain', '')}",
        f"- Domeny rozpoznane: {domains}",
        f"- Domeny wspierajace: {supporting}",
        "- Funding, mobile i runtime sa traktowane jako domeny wspierajace, jesli nie sa glownym typem projektu.",
        "- Zaden modul wspierajacy nie moze sam zmienic Source of Truth ani Masterplanu bez Human Gate.",
    ]
    plan_lines = [
        "",
        "## Orkiestracja wielodomenowa",
        "- Primary kind prowadzi backlog i modul bazowy projektu.",
        "- Domeny wspierajace dodaja moduly overlay, osobne bramki Human Gate i audit evidence.",
        "- Funding scan nie przejmuje projektu, dopoki operator nie zatwierdzi funding jako glowny kierunek.",
        "- Mobile approval i runtime expansion pozostaja zablokowane bez osobnej zgody operatora.",
        "- Adversarial critic musi zakwestionowac zalozenia przed akceptacja zmian strategicznych.",
    ]
    return canonical_book + "\n" + "\n".join(canon_lines), masterplan + "\n" + "\n".join(plan_lines), snapshot


def _operator_decisions_section(project: dict[str, Any]) -> str:
    decisions = list(project.get("decisions") or [])
    if not decisions:
        return ""
    lines = ["", "## Decyzje operatora i skutki"]
    for decision in decisions:
        lines.append(
            f"- {decision.get('key', '')}: {decision.get('label', '')} "
            f"({decision.get('consequences', '') or decision.get('description', '')})"
        )
    return "\n".join(lines)


def _refresh_project_planning_documents(project: dict[str, Any]) -> None:
    """Regenerate visible canon/masterplan after meta-orchestration decisions."""
    modules = [
        str(name)
        for name in (project.get("worker_plan") or {}).get("modules") or []
        if str(name).strip()
    ]
    if not modules:
        modules = [
            str(module.get("name") or "")
            for module in project.get("modules") or []
            if str(module.get("name") or "").strip()
        ]
    canonical_book, masterplan, refreshed_snapshot = _project_documents(
        str(project.get("title") or "Projekt"),
        str(project.get("idea") or ""),
        str(project.get("project_kind") or "application"),
        modules,
    )
    domain_profile = (
        (project.get("canon_snapshot") or {}).get("domain_profile")
        or (project.get("governance_policy") or {}).get("domain_profile")
        or (project.get("worker_plan") or {}).get("domain_profile")
    )
    canonical_book, masterplan, refreshed_snapshot = _apply_domain_profile_to_documents(
        canonical_book,
        masterplan,
        refreshed_snapshot,
        domain_profile if isinstance(domain_profile, dict) else None,
    )
    current_snapshot = dict(project.get("canon_snapshot") or {})
    refreshed_snapshot.update(current_snapshot)
    refreshed_snapshot["project_kind"] = project.get("project_kind", refreshed_snapshot.get("project_kind", "application"))
    refreshed_snapshot["modules"] = modules
    project["canon_snapshot"] = refreshed_snapshot

    governance = dict(project.get("governance_policy") or {})
    execution = dict(project.get("execution_plan") or {})
    runtime_lines = [
        "",
        "## Runtime i governance po meta-orkiestracji",
        f"- provisioning_mode: {execution.get('provisioning_mode', 'local-first')}",
        f"- deployment_mode: {execution.get('deployment_mode', 'local_docker')}",
        f"- auto_provision: {bool(execution.get('auto_provision'))}",
        f"- runtime_expansion_requires_human_gate: {bool(governance.get('runtime_expansion_requires_human_gate', True))}",
    ]
    if governance.get("planned_runtime_expansion"):
        runtime_lines.append(f"- planned_runtime_expansion: {governance.get('planned_runtime_expansion')}")

    project["canonical_book"] = canonical_book + _operator_decisions_section(project)
    project["masterplan"] = masterplan + "\n" + "\n".join(runtime_lines) + _operator_decisions_section(project)


def _project_attachment_analyses(project: dict[str, Any]) -> list[dict[str, Any]]:
    analyses: list[dict[str, Any]] = []
    for attachment in project.get("attachments") or []:
        if not isinstance(attachment, dict):
            continue
        raw = attachment.get("analysis")
        if isinstance(raw, list):
            analyses.extend(item for item in raw if isinstance(item, dict))
        elif isinstance(raw, dict):
            analyses.append(raw)
    return analyses


def _with_latest_attachment_analysis(project: dict[str, Any]) -> dict[str, Any]:
    """Overlay latest attachment analysis from the attachment store.

    Projects keep attachment metadata as a snapshot, but the attachment analyzer
    can be rerun later. The read-side detail endpoint should show the freshest
    analysis without rewriting the project row.
    """
    attachments = [dict(item) for item in (project.get("attachments") or []) if isinstance(item, dict)]
    if not attachments:
        return project
    idea_ids = {
        str(item.get("idea_id") or "").strip()
        for item in attachments
        if str(item.get("idea_id") or "").strip()
    }
    source_idea_id = str(project.get("source_idea_id") or "").strip()
    if source_idea_id:
        idea_ids.add(source_idea_id)
    if not idea_ids:
        return project
    try:
        from sylion.api.ai_workspace_routes import _get_idea_attachments

        attachment_store = _get_idea_attachments()
        latest_by_attachment: dict[str, dict[str, Any]] = {}
        for idea_id in idea_ids:
            for analysis in attachment_store.list_attachment_analysis(idea_id):
                attachment_id = str(analysis.get("attachment_id") or "")
                if attachment_id and attachment_id not in latest_by_attachment:
                    latest_by_attachment[attachment_id] = analysis
    except Exception as exc:  # noqa: BLE001
        log.debug("attachment analysis overlay skipped: %s", exc)
        return project

    refreshed = False
    for attachment in attachments:
        analysis = latest_by_attachment.get(str(attachment.get("attachment_id") or ""))
        if analysis:
            attachment["analysis"] = [analysis]
            refreshed = True
    if not refreshed:
        return project
    updated = dict(project)
    updated["attachments"] = attachments
    return updated


def _max_decision_class(analyses: list[dict[str, Any]]) -> str:
    level = "D0"
    for item in analyses:
        candidate = str(item.get("decision_class") or "D0").upper()
        if _D_LEVEL_RANK.get(candidate, -1) > _D_LEVEL_RANK.get(level, -1):
            level = candidate
    return level


def _project_kickoff_summary(project: dict[str, Any]) -> dict[str, Any]:
    analyses = _project_attachment_analyses(project)
    tags: set[str] = set()
    suggested_skills: set[str] = set()
    missing_info: list[str] = []
    risks: list[str] = []
    for item in analyses:
        tags.update(str(value) for value in item.get("tags") or [] if value)
        suggested_skills.update(str(value) for value in item.get("suggested_skills") or [] if value)
        missing_info.extend(str(value) for value in item.get("missing_info") or [] if value)
        risks.extend(str(value) for value in item.get("risks") or [] if value)

    max_class = _max_decision_class(analyses)
    council_members = list((project.get("council_plan") or {}).get("members") or [])
    return {
        "attachment_count": len(project.get("attachments") or []),
        "analysis_count": len(analyses),
        "max_decision_class": max_class,
        "human_gate_required": max_class in {"D3", "D4", "D5"} or any(
            bool(item.get("human_gate_required")) for item in analyses
        ),
        "tags": sorted(tags),
        "suggested_skills": sorted(suggested_skills),
        "suggested_skills_count": len(suggested_skills),
        "missing_info": missing_info[:12],
        "risks": risks[:12],
        "has_critic": any(str(member.get("role") or "") in {"critic", "adversarial_critic"} for member in council_members),
        "has_adversarial_critic": any(str(member.get("role") or "") == "adversarial_critic" for member in council_members),
    }


def _submit_advisor_event(
    topic: str,
    payload: dict[str, Any],
    *,
    triggering_event_id: str = "",
) -> int:
    """Submit a project event to AdvisorEngine without hiding runtime errors."""
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service

        cards = get_engine_service().submit_event(
            topic=topic,
            payload=payload,
            operator_id=_DEFAULT_ADVISOR_OPERATOR,
            triggering_event_id=triggering_event_id,
        )
        return len(cards)
    except Exception as exc:  # noqa: BLE001 - project creation must survive while the error is visible in logs.
        log.warning("advisor kickoff event failed topic=%s project_id=%s: %s", topic, payload.get("project_id"), exc, exc_info=True)
        return 0


def _advisor_project_card_topics(project_id: str) -> set[str]:
    try:
        from sylion.aeis.advisor.engine.service import get_engine_service

        cards = get_engine_service().list_recommendations(operator_id=_DEFAULT_ADVISOR_OPERATOR, limit=500)
        topics: set[str] = set()
        for card in cards:
            if (card.get("header", {}) or {}).get("project_id") != project_id:
                continue
            body = card.get("body", {}) or {}
            metadata = body.get("metadata", {}) if isinstance(body, dict) else {}
            topic = str(
                (card.get("header", {}) or {}).get("emitting_event_topic")
                or metadata.get("triggering_topic")
                or metadata.get("triggering_event_topic")
                or ""
            )
            if topic:
                topics.add(topic)
        return topics
    except Exception as exc:  # noqa: BLE001
        log.warning("advisor project card topics failed project_id=%s: %s", project_id, exc, exc_info=True)
        return set()


def _publish_and_submit_project_event(
    topic: str,
    payload: dict[str, Any],
    *,
    source_module: str = "sylion.api.projects_routes",
    primary_key: str = "",
) -> int:
    publish_lifecycle_event(
        topic,
        payload,
        source_module=source_module,
        primary_key=primary_key or str(payload.get("project_id") or ""),
    )
    return _submit_advisor_event(topic, payload, triggering_event_id=primary_key)


def _emit_project_kickoff(project: dict[str, Any], *, existing_topics: set[str] | None = None) -> dict[str, Any]:
    """Emit real AdvisorEngine kickoff cards for a newly created project."""
    project_id = str(project.get("project_id") or "")
    if not project_id:
        return {"emitted_topics": [], "cards_created": 0}

    summary = _project_kickoff_summary(project)
    base_payload = {
        "project_id": project_id,
        "idea_id": project_id,
        "project_type": project.get("project_kind") or "application",
        "project_domain": project.get("project_kind") or "application",
        "title": project.get("title", ""),
        "idea_preview": str(project.get("idea") or "")[:1200],
        "risk_level": "high" if summary["human_gate_required"] else "medium",
        "decision_class": summary["max_decision_class"],
        "attachment_count": summary["attachment_count"],
        "analysis_count": summary["analysis_count"],
        "tags": summary["tags"],
        "missing_info": summary["missing_info"],
        "risks": summary["risks"],
    }
    existing_topics = existing_topics or set()
    planned: list[str] = []
    emitted: list[str] = []
    cards_created = 0

    def emit(topic: str, payload: dict[str, Any]) -> None:
        nonlocal cards_created
        planned.append(topic)
        if topic in existing_topics:
            return
        emitted.append(topic)
        cards_created += _publish_and_submit_project_event(
            topic,
            payload,
            primary_key=f"{project_id}:{topic}",
        )

    emit("aeis.idea.intake.completed", base_payload)
    emit(
        "aeis.council.formation_requested",
        {
            **base_payload,
            "proposed_council_size": int((project.get("council_plan") or {}).get("active_size") or 0),
            "mandatory_roles": [
                member.get("role")
                for member in ((project.get("council_plan") or {}).get("members") or [])
                if isinstance(member, dict)
            ],
        },
    )
    if summary["suggested_skills_count"]:
        emit(
            "aeis.system.skill_selection_requested",
            {
                **base_payload,
                "suggested_skills": summary["suggested_skills"],
                "suggested_skills_count": summary["suggested_skills_count"],
                "has_critic": summary["has_critic"],
            },
        )
    if summary["human_gate_required"]:
        emit(
            "aeis.human_gate.ticket_pending",
            {
                **base_payload,
                "pending_count_user": 1,
                "gate_type": "project_kickoff",
                "reason": f"Attachment analysis reached {summary['max_decision_class']}",
            },
        )
    if len(str(project.get("canonical_book") or "").split()) > 120:
        emit(
            "aeis.idea.sot_drafted",
            {
                **base_payload,
                "word_count": len(str(project.get("canonical_book") or "").split()),
            },
        )
    skipped_topics = [topic for topic in planned if topic in existing_topics]
    missing_after_emit = [topic for topic in planned if topic not in existing_topics and topic not in emitted]
    return {
        "planned_topics": planned,
        "emitted_topics": emitted,
        "skipped_existing_topics": skipped_topics,
        "missing_topics": missing_after_emit,
        "cards_created": cards_created,
    }


def _kickoff_topic_plan(project: dict[str, Any]) -> list[str]:
    """Return kickoff topics without running expensive AdvisorEngine calls."""
    summary = _project_kickoff_summary(project)
    topics = [
        "aeis.idea.intake.completed",
        "aeis.council.formation_requested",
    ]
    if summary["suggested_skills_count"]:
        topics.append("aeis.system.skill_selection_requested")
    if summary["human_gate_required"]:
        topics.append("aeis.human_gate.ticket_pending")
    if len(str(project.get("canonical_book") or "").split()) > 120:
        topics.append("aeis.idea.sot_drafted")
    return topics


def _run_project_kickoff_background(project_id: str, *, force: bool = False) -> None:
    """Run real AdvisorEngine kickoff after the HTTP project create response."""
    try:
        store = _store()
        project = store.get_project(project_id)
        if not project:
            return
        existing_topics = set() if force else _advisor_project_card_topics(project_id)
        kickoff = _emit_project_kickoff(project, existing_topics=existing_topics)
        if kickoff.get("emitted_topics") or kickoff.get("skipped_existing_topics"):
            store.add_event(project_id, "project.kickoff.advisor_emitted", kickoff)
    except Exception as exc:  # noqa: BLE001 - background job must surface failure without crashing API.
        log.warning("background advisor kickoff failed project_id=%s: %s", project_id, exc, exc_info=True)
        try:
            _store().add_event(project_id, "project.kickoff.advisor_failed", {"error": str(exc)})
        except Exception:
            log.exception("failed to persist advisor kickoff failure project_id=%s", project_id)
    finally:
        with _KICKOFF_LOCK:
            _KICKOFF_IN_FLIGHT.discard(project_id)
            _KICKOFF_THREADS.pop(project_id, None)


def wait_for_project_kickoffs(timeout_s: float = 10.0) -> bool:
    """Wait for queued advisor kickoff threads to finish before teardown."""
    deadline = time.time() + max(0.0, timeout_s)
    while True:
        with _KICKOFF_LOCK:
            threads = [thread for thread in _KICKOFF_THREADS.values() if thread.is_alive()]
            for project_id, thread in list(_KICKOFF_THREADS.items()):
                if not thread.is_alive():
                    _KICKOFF_THREADS.pop(project_id, None)
                    _KICKOFF_IN_FLIGHT.discard(project_id)
        if not threads:
            return True
        remaining = deadline - time.time()
        if remaining <= 0:
            return False
        for thread in threads:
            thread.join(min(remaining, 0.25))


def _queue_project_kickoff(project: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Queue AdvisorEngine kickoff so onboarding never blocks on LLM latency."""
    project_id = str(project.get("project_id") or "")
    if not project_id:
        return {"status": "skipped", "reason": "missing_project_id", "planned_topics": []}

    planned_topics = _kickoff_topic_plan(project)
    summary = _project_kickoff_summary(project)
    with _KICKOFF_LOCK:
        if project_id in _KICKOFF_IN_FLIGHT:
            return {"status": "already_running", "planned_topics": planned_topics}
        _KICKOFF_IN_FLIGHT.add(project_id)

    reason = "async_after_project_create"
    if summary["human_gate_required"] or summary["analysis_count"] > 0:
        reason = "async_after_project_create_governance_or_attachment_analysis"

    _store().add_event(
        project_id,
        "project.kickoff.advisor_queued",
        {
            "planned_topics": planned_topics,
            "reason": reason,
            "force": force,
            "attachment_count": summary["attachment_count"],
            "analysis_count": summary["analysis_count"],
            "human_gate_required": summary["human_gate_required"],
            "max_decision_class": summary["max_decision_class"],
        },
    )

    if summary["human_gate_required"] or summary["analysis_count"] > 0:
        try:
            existing_topics = set() if force else _advisor_project_card_topics(project_id)
            kickoff = _emit_project_kickoff(project, existing_topics=existing_topics)
            if not kickoff.get("emitted_topics") and existing_topics and not force:
                kickoff = {
                    "skipped": True,
                    "reason": "advisor_cards_already_exist_for_planned_topics",
                    "existing_topics": sorted(existing_topics),
                    **kickoff,
                    "cards_created": 0,
                }
            else:
                kickoff["skipped"] = False
                kickoff["existing_topics_before"] = sorted(existing_topics)
            kickoff["status"] = "emitted_sync"
            kickoff["reason"] = "sync_after_project_create_governance_or_attachment_analysis"
            _store().add_event(project_id, "project.kickoff.advisor_emitted", kickoff)
            return kickoff
        finally:
            with _KICKOFF_LOCK:
                _KICKOFF_IN_FLIGHT.discard(project_id)

    thread = threading.Thread(
        target=_run_project_kickoff_background,
        args=(project_id,),
        kwargs={"force": force},
        name=f"advisor-kickoff-{project_id}",
        daemon=True,
    )
    with _KICKOFF_LOCK:
        _KICKOFF_THREADS[project_id] = thread
    thread.start()
    return {"status": "queued", "planned_topics": planned_topics}


def _attachment_identity(attachments: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    attachment_ids: set[str] = set()
    idea_ids: set[str] = set()
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        attachment_id = str(attachment.get("attachment_id") or "").strip()
        idea_id = str(attachment.get("idea_id") or "").strip()
        if attachment_id:
            attachment_ids.add(attachment_id)
        if idea_id:
            idea_ids.add(idea_id)
    return attachment_ids, idea_ids


def _find_existing_onboarding_project(
    store: Any,
    *,
    owner_id: str,
    title: str,
    idea_raw: str,
    attachments: list[dict[str, Any]],
    onboarding_config: dict[str, Any],
) -> dict[str, Any] | None:
    """Make onboarding project creation retry-safe after a lost HTTP response."""
    attachment_ids, idea_ids = _attachment_identity(attachments)
    if not onboarding_config and not attachment_ids and not idea_ids:
        return None
    normalized_title = title.strip()
    normalized_idea = str(idea_raw or "").strip()
    for existing in store.list_projects(owner_id=owner_id or None):
        if normalized_title and str(existing.get("title") or "").strip() != normalized_title:
            continue
        if normalized_idea and str(existing.get("idea") or "").strip() != normalized_idea:
            continue
        existing_attachment_ids, existing_idea_ids = _attachment_identity(
            list(existing.get("attachments") or [])
        )
        if attachment_ids and existing_attachment_ids.intersection(attachment_ids):
            return existing
        if idea_ids and existing_idea_ids.intersection(idea_ids):
            return existing
        for custom_input in existing.get("custom_inputs") or []:
            if (
                isinstance(custom_input, dict)
                and custom_input.get("source") == "advisor_onboarding"
                and onboarding_config
            ):
                return existing
    return None


def _project_freeze_ticket(project_id: str, target: str, approval_key: str) -> str:
    """Request Human Gate approval for strategic project freeze actions."""
    for ticket in fetch_pending(origin="workspace", project_id=project_id):
        payload = ticket.payload or {}
        if payload.get("action") == "project_freeze" and payload.get("target") == target:
            return ticket.ticket_id

    gate_type = "source_of_truth_gate" if target == "canon" else "masterplan_gate" if target == "masterplan" else "blocking"
    return submit(GovernanceTicket(
        origin="workspace",
        project_id=project_id,
        decision_class="D4",
        gate_type=gate_type,
        priority="P1",
        title=f"Approve project {target} freeze",
        summary=(
            f"Human Gate approval is required before freezing project {target}. "
            "This changes the canonical execution baseline."
        ),
        payload={
            "action": "project_freeze",
            "target": target,
            "approval_key": approval_key,
            "requires_human_gate": True,
            "semantic_gate_type": gate_type,
        },
        requested_by="project_mode",
    ))


def _project_masterplan_estimates(project: dict[str, Any]) -> tuple[int, float, int]:
    """Return best-effort masterplan estimates from the current project snapshot."""
    modules = list(project.get("modules") or [])
    total_loc_estimate = 0
    for module in modules:
        spec = dict(module.get("spec") or {})
        raw_loc = spec.get("loc_estimate", 0)
        try:
            total_loc_estimate += int(raw_loc or 0)
        except (TypeError, ValueError):
            continue

    execution_plan = dict(project.get("execution_plan") or {})
    audit_plan = dict(project.get("audit_plan") or {})
    estimated_cost_usd = float(execution_plan.get("budget_usd") or 0.0)
    estimated_duration_days = int(audit_plan.get("estimated_duration_days") or 0)
    return total_loc_estimate, estimated_cost_usd, estimated_duration_days


def _normalize_autonomy_level(value: str | None) -> str:
    """Return the canonical Round-3 autonomy level used by build authorize."""
    raw = str(value or "").strip()
    if raw in {"L0", "L1", "L2", "L3", "L4"}:
        return raw
    lowered = raw.lower()
    aliases = {
        "off": "L0",
        "manual": "L0",
        "none": "L0",
        "low": "L1",
        "safe": "L1",
        "medium": "L2",
        "med": "L2",
        "high": "L3",
        "supervised_high": "L3",
        "auto": "L4",
        "full": "L4",
        "autonomous": "L4",
    }
    return aliases.get(lowered, "L0")


def _project_budget_state(project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    execution = dict(project.get("execution_plan") or {})
    cost = _store().get_project_cost(project_id)
    cap = (
        project.get("cost_cap_usd")
        if project.get("cost_cap_usd") is not None
        else execution.get("budget_usd", execution.get("hard_limit_usd", execution.get("cap_usd", 0.0)))
    )
    try:
        cap_usd = float(cap or 0.0)
    except (TypeError, ValueError):
        cap_usd = 0.0
    spent_usd = float(cost.get("running_total") or 0.0)
    return {
        "project_id": project_id,
        "cap_usd": cap_usd,
        "spent_usd": spent_usd,
        "remaining_usd": max(0.0, cap_usd - spent_usd),
        "soft_warn_usd": float(execution.get("soft_warn_usd") or 0.0),
        "hard_stop": bool(execution.get("hard_stop", True)),
        "per_provider_cap": dict(execution.get("per_provider_cap") or {}),
        "ledger": cost.get("records") or [],
    }


def _project_autonomy_state(project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    governance = dict(project.get("governance_policy") or {})
    raw_level = (
        project.get("autonomy_level")
        or governance.get("autonomy_mode")
        or governance.get("level")
        or "L0"
    )
    level = _normalize_autonomy_level(str(raw_level))
    return {
        "project_id": project_id,
        "level": level,
        "raw_level": raw_level,
        "enabled": level != "L0",
        "approval_required": level in {"L0", "L1", "L2", "L3", "L4"},
        "overrides": dict(governance.get("autonomy_overrides") or {}),
    }


def _project_execution_models_state(project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    execution = dict(project.get("execution_plan") or {})
    return {
        "project_id": project_id,
        "assignments": list(execution.get("model_assignments") or []),
        "catalog_source": execution.get("model_assignment_source") or "",
        "updated_at": execution.get("model_assignment_updated_at"),
        "requires_masterplan": not bool(project.get("masterplan_frozen_at")),
        "module_count": len(project.get("modules") or []),
    }


def _emit_masterplan_created(project: dict[str, Any]) -> None:
    """Emit H09 once the masterplan has been finalized via freeze approval."""
    total_loc_estimate, estimated_cost_usd, estimated_duration_days = _project_masterplan_estimates(project)
    publish_lifecycle_event(
        "aeis.masterplan.created",
        {
            "masterplan_id": project.get("masterplan_id", ""),
            "project_id": project.get("project_id", ""),
            "module_count": len(project.get("modules") or []),
            "total_loc_estimate": total_loc_estimate,
            "estimated_cost_usd": estimated_cost_usd,
            "estimated_duration_days": estimated_duration_days,
        },
        source_module="sylion.api.projects_routes",
        primary_key=project.get("masterplan_id") or project.get("project_id", ""),
    )


def _apply_project_decision_effects(
    project: dict[str, Any],
    question: dict[str, Any],
    selected: dict[str, Any],
) -> dict[str, Any]:
    """Apply operator decisions to the project planning snapshot."""
    key = question.get("key", "")
    choice_id = selected.get("choice_id", "")
    effects: dict[str, Any] = {
        "choice_id": choice_id,
        "label": selected.get("label", ""),
    }
    if key == "direction_approval":
        if choice_id == "direction_full_scope":
            expanded_kind = _classify_project_kind(str(project.get("idea") or ""))
            if expanded_kind != "application":
                blueprint = _apply_domain_profile_to_blueprint(
                    _blueprint_for_project(expanded_kind, list(project.get("preferred_stack") or [])),
                    str(project.get("idea") or ""),
                    expanded_kind,
                )
                project["project_kind"] = expanded_kind
                project["worker_plan"] = blueprint["worker_plan"]
                project["council_plan"] = blueprint["council_plan"]
                project["audit_plan"] = blueprint["audit_plan"]
                project["execution_plan"] = blueprint["execution_plan"]
                project["governance_policy"] = blueprint["governance_policy"]
                # Force ProjectModeStore to rebuild project_modules from the
                # expanded worker plan instead of keeping the generic modules.
                project["modules"] = []
        canon_snapshot = dict(project.get("canon_snapshot") or {})
        canon_snapshot["approved_direction"] = {
            "choice_id": choice_id,
            "label": selected.get("label", ""),
            "rationale": selected.get("rationale", ""),
            "consequences": selected.get("consequences", ""),
        }
        canon_snapshot["direction_locked"] = True
        project["canon_snapshot"] = canon_snapshot
        effects["canon_snapshot"] = {
            "approved_direction": canon_snapshot["approved_direction"],
            "direction_locked": True,
        }
    elif key == "runtime_policy":
        execution_plan = dict(project.get("execution_plan") or {})
        governance_policy = dict(project.get("governance_policy") or {})
        if choice_id == "runtime_local_only":
            execution_plan["deployment_mode"] = "local_docker"
            execution_plan["provisioning_mode"] = "local-first"
            execution_plan["vps_workers"] = 0
            execution_plan["auto_provision"] = False
            governance_policy["runtime_expansion_requires_human_gate"] = True
        elif choice_id == "runtime_hybrid_later":
            execution_plan["provisioning_mode"] = "hybrid-later"
            execution_plan["auto_provision"] = False
            governance_policy["runtime_expansion_requires_human_gate"] = True
            governance_policy["planned_runtime_expansion"] = "requires_future_approval"
        project["execution_plan"] = execution_plan
        project["governance_policy"] = governance_policy
        effects["execution_plan"] = execution_plan
        effects["governance_policy"] = {
            "runtime_expansion_requires_human_gate": governance_policy.get("runtime_expansion_requires_human_gate"),
            "planned_runtime_expansion": governance_policy.get("planned_runtime_expansion", ""),
        }
    return effects


@router.post("/api/v1/projects")
def create_project(body: CreateProjectRequest,
                   _user: str = Depends(requires_role("operator"))):
    """Create a project directly via the project_mode store.

    Produces a fully-defaulted project record (questions, council plan,
    worker plan, audit plan, etc. all auto-derived inside upsert_project).
    """
    store = _store()
    title = body.name or (body.idea_raw[:72] if body.idea_raw else "Project Kickoff")
    kind = str(body.project_kind or "").strip() or _classify_project_kind(body.idea_raw)
    project_domain = str(body.project_domain or "").strip()
    owner_id = body.owner_id or "workspace-default"
    existing_project = _find_existing_onboarding_project(
        store,
        owner_id=owner_id,
        title=title,
        idea_raw=body.idea_raw,
        attachments=list(body.attachments or []),
        onboarding_config=dict(body.onboarding_config or {}),
    )
    if existing_project:
        kickoff = _queue_project_kickoff(existing_project)
        existing_project["kickoff"] = {
            "status": "reused_existing",
            "reused_existing": True,
            "reused_project_id": existing_project.get("project_id", ""),
            "advisor_kickoff": kickoff,
        }
        return {"project": existing_project, "reused_existing": True}
    base_blueprint = _apply_domain_profile_to_blueprint(
        _blueprint_for_project(kind, list(body.preferred_stack or [])),
        body.idea_raw,
        kind,
    )
    blueprint = _apply_onboarding_orchestration(
        base_blueprint,
        body.onboarding_config,
        kind=kind,
    )
    modules = list((blueprint.get("worker_plan") or {}).get("modules") or [])
    canonical_book, masterplan, canon_snapshot = _project_documents(title, body.idea_raw, kind, modules)
    canonical_book, masterplan, canon_snapshot = _apply_domain_profile_to_documents(
        canonical_book,
        masterplan,
        canon_snapshot,
        blueprint.get("domain_profile") if isinstance(blueprint.get("domain_profile"), dict) else None,
    )
    onboarding_config = blueprint.get("onboarding_config") or {}
    cost_cap = None
    execution_plan = dict(blueprint["execution_plan"])
    if execution_plan.get("hard_limit_usd") is not None:
        try:
            cost_cap = float(execution_plan.get("hard_limit_usd") or 0.0)
        except (TypeError, ValueError):
            cost_cap = None
    project: dict[str, Any] = {
        "title": title,
        "idea": body.idea_raw,
        "constraints": body.constraints,
        "canonical_book_input": body.canonical_book,
        "preferred_stack": list(body.preferred_stack or []),
        "attachments": list(body.attachments or []),
        "team_id": body.team_id,
        "owner_id": owner_id,
        "project_kind": kind,
        "canonical_book": body.canonical_book or canonical_book,
        "masterplan": masterplan,
        "canon_snapshot": canon_snapshot,
        "memory_policy": blueprint["memory_policy"],
        "worker_plan": blueprint["worker_plan"],
        "council_plan": blueprint["council_plan"],
        "execution_plan": blueprint["execution_plan"],
        "governance_policy": blueprint["governance_policy"],
        "audit_plan": blueprint["audit_plan"],
        "questions": _default_project_questions(kind, canon_snapshot.get("runtime_constraints") if isinstance(canon_snapshot, dict) else None),
        "custom_inputs": [
            {
                "input_id": "advisor_onboarding_meta_orchestration",
                "source": "advisor_onboarding",
                "payload": {
                    **onboarding_config,
                    "first_idea_project_kind": kind,
                    "first_idea_project_domain": project_domain,
                },
            }
        ] if onboarding_config else [],
    }
    if project_domain:
        project["canon_snapshot"]["project_domain"] = project_domain
        project["execution_plan"]["project_domain"] = project_domain
        project["governance_policy"]["project_domain"] = project_domain
    if onboarding_config:
        project["autonomy_level"] = str(onboarding_config.get("autonomy_level") or "")
    if cost_cap is not None and cost_cap > 0:
        project["cost_cap_usd"] = cost_cap
    if body.project_id:
        project["project_id"] = body.project_id
    project = store.upsert_project(project)
    store.add_event(project["project_id"], "project.created", {
        "owner_id": project.get("owner_id"),
        "auto_execute": bool(body.auto_execute),
        "meta_orchestration_source": "advisor_onboarding" if onboarding_config else "default_blueprint",
        "council_size": (project.get("council_plan") or {}).get("active_size"),
        "autonomy_level": project.get("autonomy_level"),
    })
    kickoff = _queue_project_kickoff(project)
    if body.auto_execute:
        project["launch"] = {**(project.get("launch") or {}), "auto_execute": True}
        project = store.upsert_project(project)
        project["kickoff"] = kickoff
    else:
        project["kickoff"] = kickoff
    return {"project": project}


@router.get("/api/v1/projects")
async def list_projects(owner_id: str | None = None):
    projects = list(_store().list_projects(owner_id=owner_id))
    seen = {str(project.get("project_id") or "") for project in projects}
    for lifecycle_project in _project_start_projects():
        project_id = str(lifecycle_project.get("project_id") or "")
        if project_id and project_id not in seen:
            projects.append(_adapt_project_start_project(lifecycle_project))
            seen.add(project_id)
    return {"projects": projects}


@router.get("/api/v1/projects/{project_id}")
async def get_project(project_id: str):
    return _with_pending_governance(_with_latest_attachment_analysis(_load_project_or_404(project_id)))


@router.post("/api/v1/projects/{project_id}/attachments")
async def add_project_attachment(project_id: str, body: AddProjectAttachmentRequest):
    """Persist an uploaded workspace attachment on the project surface.

    The file bytes stay in the idea attachment store. The project stores only
    metadata plus the latest analysis snapshot so Council questions can include
    the attachment context and the project detail page can render it later.
    """
    project = _load_project_or_404(project_id)
    raw = dict(body.attachment or {})
    attachment_id = str(raw.get("attachment_id") or "").strip()
    if not attachment_id:
        raise HTTPException(422, "attachment.attachment_id is required")
    idea_id = str(raw.get("idea_id") or raw.get("idea_id_used") or "").strip()
    attachment: dict[str, Any] = {
        "attachment_id": attachment_id,
        "idea_id": idea_id,
        "filename": str(raw.get("filename") or attachment_id),
        "file_type": str(raw.get("file_type") or "application/octet-stream"),
        "file_size": int(raw.get("file_size") or 0),
        "created_at": raw.get("created_at") or time.time(),
        "source": body.source or "project_council_question",
    }
    analysis = raw.get("analysis")
    if isinstance(analysis, dict):
        attachment["analysis"] = [analysis]
    elif isinstance(analysis, list):
        attachment["analysis"] = [item for item in analysis if isinstance(item, dict)]
    elif idea_id:
        try:
            from sylion.api.ai_workspace_routes import _get_idea_attachments

            for item in _get_idea_attachments().list_attachment_analysis(idea_id):
                if str(item.get("attachment_id") or "") == attachment_id:
                    attachment["analysis"] = [item]
                    break
        except Exception as exc:  # noqa: BLE001
            log.debug("project attachment analysis lookup skipped: %s", exc)

    attachments = [dict(item) for item in (project.get("attachments") or []) if isinstance(item, dict)]
    attachments = [item for item in attachments if str(item.get("attachment_id") or "") != attachment_id]
    attachments.append(attachment)
    project["attachments"] = attachments
    if idea_id and not str(project.get("source_idea_id") or "").strip():
        project["source_idea_id"] = idea_id
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.attachment.added", {
        "attachment_id": attachment_id,
        "idea_id": idea_id,
        "source": body.source,
        "filename": attachment.get("filename"),
    })
    return _with_pending_governance(_with_latest_attachment_analysis(project))


@router.post("/api/v1/projects/{project_id}/kickoff")
def kickoff_project(project_id: str, force: bool = Query(False), wait: bool = Query(False)):
    project = _load_project_or_404(project_id)
    if not wait:
        kickoff = _queue_project_kickoff(project, force=force)
        project["kickoff"] = kickoff
        project["updated_at"] = time.time()
        project = _store().upsert_project(project)
        return {"project_id": project_id, "kickoff": kickoff, "project": project}

    existing_topics = _advisor_project_card_topics(project_id)
    if existing_topics and not force:
        kickoff = _emit_project_kickoff(project, existing_topics=existing_topics)
    else:
        kickoff = _emit_project_kickoff(project)
    if not kickoff.get("emitted_topics") and existing_topics and not force:
        kickoff = {
            "skipped": True,
            "reason": "advisor_cards_already_exist_for_planned_topics",
            "existing_topics": sorted(existing_topics),
            **kickoff,
            "cards_created": 0,
        }
    else:
        kickoff["skipped"] = False
        kickoff["existing_topics_before"] = sorted(existing_topics)
    _store().add_event(project_id, "project.kickoff.advisor_emitted", kickoff)
    project["kickoff"] = kickoff
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    return {"project_id": project_id, "kickoff": kickoff, "project": project}


@router.delete("/api/v1/projects/{project_id}")
async def delete_project(project_id: str):
    project = _load_project_or_404(project_id)
    project["status"] = "deleted"
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.deleted", {})
    return project


@router.post("/api/v1/projects/{project_id}/pause")
async def pause_project(project_id: str):
    project = _load_project_or_404(project_id)
    project["status"] = "paused"
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.paused", {})
    return project


@router.post("/api/v1/projects/{project_id}/resume")
async def resume_project(project_id: str):
    project = _load_project_or_404(project_id)
    project["status"] = "running" if project.get("launch", {}).get("run_id") else "definition_in_progress"
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.resumed", {})
    return project


@router.put("/api/v1/projects/{project_id}/autonomy")
async def update_project_autonomy(project_id: str, body: UpdateAutonomyRequest):
    project = _load_project_or_404(project_id)
    governance = dict(project.get("governance_policy") or {})
    governance["autonomy_mode"] = _normalize_autonomy_level(body.level)
    governance["autonomy_overrides"] = body.overrides or {}
    project["governance_policy"] = governance
    project["autonomy_level"] = governance["autonomy_mode"]
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.autonomy.updated", {"level": governance["autonomy_mode"], "overrides": body.overrides or {}})
    return project


@router.get("/api/v1/projects/{project_id}/autonomy")
async def get_project_autonomy(project_id: str):
    project = _load_project_or_404(project_id)
    return _project_autonomy_state(project_id, project)


@router.get("/api/v1/projects/{project_id}/timeline")
async def get_project_timeline(project_id: str):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        return _project_start_timeline(project.get("project_start") or {})
    return _store().get_project_timeline(project_id)


@router.get("/api/v1/projects/{project_id}/events")
async def get_project_events(project_id: str, limit: int = 100):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        events = list(project.get("audit_chain") or [])[-int(limit):]
        return {
            "events": [
                {
                    "event_id": event.get("event_id", ""),
                    "project_id": project_id,
                    "event_type": event.get("event", "project_start.lifecycle"),
                    "payload": event.get("payload") or {},
                    "emitted_at": event.get("created_at") or project.get("updated_at") or time.time(),
                }
                for event in events
            ]
        }
    return _store().list_project_events(project_id, limit=limit)


@router.get("/api/v1/projects/{project_id}/questions")
async def get_project_questions(project_id: str, status: str | None = None):
    if _is_project_start_backed(project_id):
        return {"questions": []}
    _load_project_or_404(project_id)
    return _store().list_project_questions(project_id, status=status)


@router.get("/api/v1/projects/{project_id}/questions/{question_id}")
async def get_project_question(project_id: str, question_id: str):
    project = _load_project_or_404(project_id)
    question = next((item for item in project.get("questions", []) if item.get("question_id") == question_id), None)
    if not question:
        raise HTTPException(404, "Question not found")
    return question


@router.post("/api/v1/projects/{project_id}/questions/{question_id}/answer")
async def answer_project_question(project_id: str, question_id: str, body: AnswerProjectQuestionRequest):
    project = _load_project_or_404(project_id)
    question = next((item for item in project.get("questions", []) if item.get("question_id") == question_id), None)
    if not question:
        raise HTTPException(404, "Question not found")
    if body.custom_response.strip():
        selected = {
            "choice_id": f"custom-{question_id[:8]}",
            "label": body.custom_response.strip()[:120],
            "rationale": body.rationale or "operator custom response",
            "consequences": "",
        }
    else:
        selected = next(
            (choice for choice in question.get("choices", []) if choice.get("choice_id") == body.choice_id),
            None,
        )
    if not selected:
        raise HTTPException(400, "Choice not found")
    now = time.time()
    question["status"] = "answered"
    question["selected_choice_id"] = selected.get("choice_id", "")
    question["selected_value"] = selected.get("label", "")
    question["answered_at"] = now
    effects = _apply_project_decision_effects(project, question, selected)
    answers = project.setdefault("answers", [])
    answers.append({
        "question_id": question_id,
        "choice_id": selected.get("choice_id", ""),
        "value": selected.get("label", ""),
        "rationale": body.rationale or selected.get("consequences", ""),
        "source": body.source or "human",
        "answered_at": now,
    })
    decisions = [
        decision for decision in project.get("decisions", [])
        if decision.get("question_id") != question_id
    ]
    decisions.append({
        "question_id": question_id,
        "phase": question.get("phase", ""),
        "key": question.get("key", ""),
        "label": selected.get("label", ""),
        "description": body.rationale or selected.get("rationale", ""),
        "consequences": selected.get("consequences", ""),
        "evidence_ref": f"question:{question_id}",
        "effects": effects,
        "is_custom": bool(body.custom_response.strip()),
        "frozen": False,
        "selected_at": now,
    })
    project["decisions"] = decisions
    _refresh_project_planning_documents(project)
    next_question = next((item for item in project.get("questions", []) if item.get("status") == "pending"), None)
    if next_question:
        project["phase"] = next_question.get("phase", project.get("phase", "canon"))
    else:
        project["status"] = "definition_complete"
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(
        project_id,
        "project.question.answered",
        {
            "question_id": question_id,
            "source": body.source or "human",
            "choice_id": selected.get("choice_id", ""),
            "custom": bool(body.custom_response.strip()),
        },
    )
    return {
        "project": project,
        "answered_question_id": question_id,
        "next_question": next_question,
    }


@router.post("/api/v1/projects/{project_id}/questions/{question_id}/delegate-council")
async def delegate_question_to_council(project_id: str, question_id: str):
    project = _load_project_or_404(project_id)
    question = next((item for item in project.get("questions", []) if item.get("question_id") == question_id), None)
    if not question:
        raise HTTPException(404, "Question not found")
    choice = (question.get("choices") or [None])[0]
    if not choice:
        raise HTTPException(400, "Question has no selectable options")
    return await answer_project_question(
        project_id,
        question_id,
        AnswerProjectQuestionRequest(
            choice_id=choice.get("choice_id", ""),
            rationale="Council fallback selected the recommended option.",
            source="council_vote",
        ),
    )


@router.get("/api/v1/projects/{project_id}/canon")
async def get_project_canon(project_id: str):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        return {
            "project_id": project_id,
            "book": project.get("canonical_book", ""),
            "entries": [],
            "approved": True,
            "source": "project_start_lifecycle",
        }
    return _store().get_project_canon(project_id)


@router.get("/api/v1/projects/{project_id}/masterplan")
async def get_project_masterplan(project_id: str):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        return {
            "project_id": project_id,
            "summary": project.get("masterplan", ""),
            "modules": project.get("modules", []),
            "approved": True,
            "source": "project_start_lifecycle",
        }
    return _store().get_project_masterplan(project_id)


# /canon/freeze and /masterplan/freeze migrated to
# sylion.api.projects_freeze_routes (W14 round_meta BE-1/BE-2).
# _emit_masterplan_created remains for legacy callers that finalise
# masterplan via direct project mutations (e.g. fixture bootstrap).


@router.post("/api/v1/projects/{project_id}/launch")
async def launch_project(project_id: str, body: LaunchProjectRequest):
    project = _load_project_or_404(project_id)
    from sylion.project_mode import get_project_execution_engine

    engine = get_project_execution_engine(_store())
    execution = engine.run_project(project_id, auto_execute=bool(body.auto_execute))
    project = _store().get_project(project_id) or project
    run_id = f"run-{project_id[:8]}-{int(time.time())}"
    launch = dict(project.get("launch") or {})
    launch.update({
        "run_id": run_id,
        "auto_execute": bool(body.auto_execute),
        "launched_at": time.time(),
        "wait_for_completion": bool(body.wait_for_completion),
    })
    project["launch"] = launch
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.launched", {"run_id": run_id, "auto_execute": bool(body.auto_execute)})
    return {"project": project, "execution": execution}


@router.get("/api/v1/projects/{project_id}/artifact/raw")
async def get_project_artifact_raw(project_id: str):
    project = _load_project_or_404(project_id)
    launch = dict(project.get("launch") or {})
    artifact_path = Path(str(launch.get("artifact_path") or ""))
    if not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="project artifact is not available")

    expected_project_id = str(project.get("project_id") or "")
    lifecycle_root = ""
    lifecycle = project.get("project_start")
    if isinstance(lifecycle, dict):
        lifecycle_root = str((lifecycle.get("shell") or {}).get("root") or "")
    artifact_allowed = expected_project_id in artifact_path.parts or expected_project_id in str(artifact_path)
    if lifecycle_root:
        try:
            artifact_allowed = artifact_allowed or artifact_path.resolve().is_relative_to(Path(lifecycle_root).resolve())
        except Exception:
            artifact_allowed = artifact_allowed or str(artifact_path).startswith(lifecycle_root)
    if not artifact_allowed:
        raise HTTPException(status_code=403, detail="artifact path is outside the project workspace")

    suffix = artifact_path.suffix.lower()
    media_type = {
        ".html": "text/html; charset=utf-8",
        ".htm": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".py": "text/x-python; charset=utf-8",
    }.get(suffix, "text/plain; charset=utf-8")
    return FileResponse(artifact_path, media_type=media_type)


@router.get("/api/v1/projects/{project_id}/decisions")
async def list_project_decisions(project_id: str):
    _load_project_or_404(project_id)
    return _store().get_project_decisions(project_id)


@router.get("/api/v1/projects/{project_id}/council")
async def get_project_council(project_id: str):
    _load_project_or_404(project_id)
    return _store().get_project_council(project_id)


@router.put("/api/v1/projects/{project_id}/council")
async def update_project_council(project_id: str, body: UpdateCouncilRequest):
    _load_project_or_404(project_id)
    return _store().update_project_council(project_id, body.members, body.plan)


@router.get("/api/v1/projects/{project_id}/council/suggest")
@router.post("/api/v1/projects/{project_id}/council/suggest")
async def suggest_project_council(project_id: str):
    project = _load_project_or_404(project_id)
    project_kind = project.get("project_kind", "application")
    existing_plan = project.get("council_plan") if isinstance(project.get("council_plan"), dict) else {}
    members = list(existing_plan.get("members") or _council_members_for_kind(project_kind))
    roles = {str(member.get("role") or "") for member in members if isinstance(member, dict)}
    if "adversarial_critic" not in roles:
        members.insert(3, _council_member("adversarial_critic", "hard red-team role: challenge assumptions, math, logic gaps and hidden failure modes", ["gpt-5", "claude-sonnet-4-6", "qwen2.5:7b-instruct"], rank="primary", required_signature=True))
    suggested_size = len(members)
    events = project.get("events") or []
    model_probe_completed = any(
        event.get("event_type") == "project.council.model_probe.completed"
        for event in events
        if isinstance(event, dict)
    )
    suggestion_stage = "profiled" if model_probe_completed else "provisional"
    plan = {
        "enabled": True,
        "active_size": suggested_size,
        "suggested_size": suggested_size,
        "members": members,
        "operator_configured": True,
        "suggestion_source": "advisor_project_profile",
        "suggestion_stage": suggestion_stage,
        "requires_model_probe": not model_probe_completed,
        "confidence_basis": [
            "project_kind",
            "static_role_map",
            "model_probe_completed" if model_probe_completed else "no_project_model_probe",
        ],
        "model_probe": {
            "completed": model_probe_completed,
            "note": (
                "Skład Rady uwzględnia rozpoznanie modeli dla projektu."
                if model_probe_completed
                else "To jest wstępny skład z profilu projektu, przed porównaniem dostępnych modeli na danych projektu."
            ),
        },
        "quorum_policy": {
            **_council_quorum_policy(),
        },
    }
    project["council_plan"] = plan
    project["council_members"] = []
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(
        project_id,
        "project.council.suggested",
        {
            "suggested_size": plan.get("suggested_size", 0),
            "suggestion_stage": suggestion_stage,
            "requires_model_probe": not model_probe_completed,
        },
    )
    return {
        "project": project,
        "plan": plan,
        "suggestion_stage": suggestion_stage,
        "requires_model_probe": not model_probe_completed,
        "rationale": (
            "Skład Rady jest po rozpoznaniu modeli dla projektu."
            if model_probe_completed
            else "To jest wstępna rekomendacja z profilu projektu. Przed pierwszą analizą przez dostępne modele/API nie wolno traktować jej jako finalnego doboru modeli."
        ),
    }


@router.get("/api/v1/projects/{project_id}/hierarchy")
async def get_project_hierarchy(project_id: str):
    _load_project_or_404(project_id)
    return _store().get_project_hierarchy(project_id)


@router.put("/api/v1/projects/{project_id}/hierarchy")
async def update_project_hierarchy(project_id: str, body: UpdateHierarchyRequest):
    _load_project_or_404(project_id)
    return _store().update_project_hierarchy(project_id, body.layers)


@router.get("/api/v1/projects/{project_id}/workers")
async def get_project_workers(project_id: str):
    _load_project_or_404(project_id)
    return _store().get_project_workers(project_id)


@router.put("/api/v1/projects/{project_id}/workers")
async def update_project_workers(project_id: str, body: UpdateWorkersRequest):
    _load_project_or_404(project_id)
    return _store().update_project_workers(project_id, body.workers)


@router.get("/api/v1/projects/{project_id}/execution-models")
async def get_project_execution_models(project_id: str):
    project = _load_project_or_404(project_id)
    return _project_execution_models_state(project_id, project)


@router.put("/api/v1/projects/{project_id}/execution-models")
async def update_project_execution_models(project_id: str, body: UpdateExecutionModelsRequest):
    project = _load_project_or_404(project_id)
    execution = dict(project.get("execution_plan") or {})
    now = time.time()
    execution["model_assignments"] = list(body.assignments or [])
    execution["model_assignment_source"] = body.catalog_source or "project_orchestration_ui"
    execution["model_assignment_updated_at"] = now
    project["execution_plan"] = execution
    project["updated_at"] = now
    project = _store().upsert_project(project)
    _store().add_event(
        project_id,
        "project.execution_models.updated",
        {
            "assignment_count": len(execution["model_assignments"]),
            "catalog_source": execution["model_assignment_source"],
        },
    )
    return _project_execution_models_state(project_id, project)


@router.get("/api/v1/projects/{project_id}/modules")
async def get_project_modules(project_id: str):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        return {"modules": project.get("modules", []), "source": "project_start_lifecycle"}
    return _store().get_project_modules(project_id)


@router.get("/api/v1/projects/{project_id}/skills")
async def get_project_skills(project_id: str):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        lifecycle = project.get("project_start") or {}
        skills = []
        for skill in (lifecycle.get("skills") or {}).get("project_skills") or []:
            if isinstance(skill, dict):
                skills.append(skill)
        return {"project_id": project_id, "skills": skills, "reuse_log": [], "source": "project_start_lifecycle"}
    return _store().get_project_skill_bindings(project_id)


@router.get("/api/v1/projects/{project_id}/modules/{module_id}")
async def get_project_module(project_id: str, module_id: str):
    project = _load_project_or_404(project_id)
    module = next((item for item in project.get("modules", []) if item.get("module_id") == module_id), None)
    if not module:
        raise HTTPException(404, "Module not found")
    return module


@router.post("/api/v1/projects/{project_id}/modules/{module_id}/rebuild")
async def rebuild_project_module(project_id: str, module_id: str):
    project = _load_project_or_404(project_id)
    updated = False
    modules = []
    for module in project.get("modules", []):
        item = dict(module)
        if item.get("module_id") == module_id:
            item["status"] = "queued"
            item["updated_at"] = time.time()
            updated = True
        modules.append(item)
    if not updated:
        raise HTTPException(404, "Module not found")
    project["modules"] = modules
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.module.rebuild.requested", {"module_id": module_id})
    return project


@router.get("/api/v1/projects/{project_id}/audit")
async def get_project_audit(project_id: str):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        return {
            "project_id": project_id,
            "results": [
                {
                    "audit_result_id": event.get("event_id", ""),
                    "module_id": "project_start_lifecycle",
                    "audit_type": event.get("event", "lifecycle_event"),
                    "status": "pass",
                    "findings": [],
                    "executed_at": float(event.get("created_at") or project.get("updated_at") or time.time()),
                }
                for event in project.get("audit_chain") or []
            ],
            "source": "project_start_lifecycle",
        }
    return _store().get_project_audit(project_id)


@router.post("/api/v1/projects/{project_id}/audit/run")
async def run_project_audit(project_id: str, body: RunAuditRequest):
    _load_project_or_404(project_id)
    from sylion.project_mode import get_project_execution_engine

    engine = get_project_execution_engine(_store())
    result = engine.run_audit(
        project_id,
        scope=body.scope,
        module_id=body.module_id or "",
    )
    _store().add_event(
        project_id,
        "project.audit.completed",
        {"scope": body.scope, "parallel": body.parallel, "results": len(result.get("results", []))},
    )
    return result


@router.get("/api/v1/projects/{project_id}/cost")
async def get_project_cost(project_id: str):
    project = _load_project_or_404(project_id)
    if _is_project_start_backed(project_id):
        lifecycle = project.get("project_start") or {}
        cost = float(((lifecycle.get("execution") or {}).get("cost") or {}).get("total_usd") or 0.0)
        return {"project_id": project_id, "records": [], "running_total": cost, "source": "project_start_lifecycle"}
    return _store().get_project_cost(project_id)


@router.get("/api/v1/projects/{project_id}/budget")
async def get_project_budget(project_id: str):
    project = _load_project_or_404(project_id)
    return _project_budget_state(project_id, project)


@router.put("/api/v1/projects/{project_id}/budget")
async def update_project_budget(project_id: str, body: UpdateBudgetRequest):
    project = _load_project_or_404(project_id)
    execution = dict(project.get("execution_plan") or {})
    execution["budget_usd"] = body.hard_limit_usd
    execution["soft_warn_usd"] = body.soft_warn_usd
    execution["hard_stop"] = True
    project["cost_cap_usd"] = float(body.hard_limit_usd)
    project["execution_plan"] = execution
    project["updated_at"] = time.time()
    project = _store().upsert_project(project)
    _store().add_event(project_id, "project.budget.updated", {"hard_limit_usd": body.hard_limit_usd, "soft_warn_usd": body.soft_warn_usd})
    return project


@router.get("/api/v1/notifications")
async def list_project_notifications(unread: bool = False, owner_id: str | None = None, limit: int = 50):
    return _store().list_notifications(owner_id=owner_id, unread_only=unread, limit=limit)


@router.get("/api/v1/workspace/notifications/{owner_id}/unread-count")
async def workspace_notification_unread_count(owner_id: str):
    return {"count": _store().unread_count(owner_id)}


@router.post("/api/v1/notifications/{notification_id}/read")
async def read_project_notification(notification_id: str):
    item = _store().mark_notification_read(notification_id)
    if not item:
        raise HTTPException(404, "Notification not found")
    return item


@router.post("/api/v1/notifications/{notification_id}/unread")
async def unread_project_notification(notification_id: str):
    item = _store().mark_notification_unread(notification_id)
    if not item:
        raise HTTPException(404, "Notification not found")
    return item


@router.post("/api/v1/notifications/{notification_id}/ack")
async def ack_project_notification(notification_id: str):
    item = _store().acknowledge_notification(notification_id)
    if not item:
        raise HTTPException(404, "Notification not found")
    return item


@router.post("/api/v1/notifications/{notification_id}/action")
async def act_on_project_notification(notification_id: str, body: dict[str, Any]):
    item = _store().mark_notification_read(notification_id)
    if not item:
        raise HTTPException(404, "Notification not found")
    return {"notification": item, "action": body.get("action", "open")}


@router.post("/api/v1/brain/search")
async def search_brain(body: dict[str, Any]):
    return _store().search_brain(str(body.get("query", "")), int(body.get("top_k", 5) or 5))


@router.get("/api/v1/brain/memory/stats")
async def get_brain_stats():
    return _store().get_brain_stats()


@router.get("/api/v1/brain/prompts")
async def list_brain_prompts():
    return _store().list_brain_prompts()


@router.put("/api/v1/brain/prompts/{prompt_id}")
async def update_brain_prompt(prompt_id: str, body: dict[str, Any]):
    updated = _store().update_brain_prompt(prompt_id, str(body.get("template", "")))
    if not updated:
        raise HTTPException(404, "Prompt not found")
    return updated


@router.post("/api/v1/brain/lora/train")
async def queue_brain_lora_training(body: QueueLoraTrainRequest):
    _load_project_or_404(body.project_id)
    return _store().queue_lora_training(body.project_id, body.base_model)


@router.get("/api/v1/brain/lora/adapters")
async def list_brain_adapters():
    return _store().list_brain_lora_adapters()


@router.get("/api/v1/brain/models")
async def get_brain_models():
    return _store().get_brain_models()


@router.post("/api/v1/brain/models/pull")
async def pull_brain_model(body: dict[str, Any]):
    return {"requested": str(body.get("model", ""))}
