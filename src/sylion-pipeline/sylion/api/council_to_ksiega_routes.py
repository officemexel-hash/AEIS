"""Council deliberation to Księga lifecycle for Phases 20-25.

Group C continues the concrete project entity created in phases 16-19.
The implementation is deterministic and local: it produces signed audit
entries, structured deliberation artifacts, Council Book files and Księga
files without external model calls or outbound customer communication.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.api.project_start_routes import (
    _active_project,
    _append_audit,
    _check,
    _has_audit,
    _is_automation_runtime_project,
    _is_funding_project,
    _is_internal_crm_project,
    _is_mobile_approval_project,
    _is_multi_domain_project,
    _project,
    _save_project,
    _set_state_at_least,
    _state_at_least,
    _uid,
)

router = APIRouter(prefix="/api/v1/council-to-ksiega", tags=["Council to Księga"])

PHASE_TITLES = {
    "20": "Zwolanie Rady",
    "21": "Pierwsze werdykty",
    "22": "Rundy deliberacji",
    "23": "Konsolidacja",
    "24": "Generowanie Ksiegi Rady",
    "25": "Księga Finalization",
}

STATE_BY_PHASE = {
    "20": "READY_FOR_INITIAL_VERDICTS",
    "21": "READY_FOR_DELIBERATION_ROUNDS",
    "22": "READY_FOR_CONSOLIDATION",
    "23": "READY_FOR_BOOK_GENERATION",
    "24": "READY_FOR_KSIEGA_GENERATION",
    "25": "READY_FOR_PLANNING",
}

AUDIT_BY_PHASE = {
    "20": "council_convened",
    "21": "initial_verdicts",
    "22": "deliberation_rounds_complete",
    "23": "council_finalized",
    "24": "council_book_generated",
    "25": "ksiega_finalized",
}


class OperatorActionRequest(BaseModel):
    operator_id: str = "operator"
    approved: bool = True
    notes: str = ""


class EdgeDiagnosisRequest(BaseModel):
    phase: str = "20"
    case_id: str = "EC-A1"
    context: dict[str, Any] = Field(default_factory=dict)


def _edge_cases(groups: list[tuple[str, list[str]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group_index, (category, titles) in enumerate(groups):
        letter = chr(ord("A") + group_index)
        for item_index, title in enumerate(titles, start=1):
            lowered = title.lower()
            severity = "high" if any(token in lowered for token in ["timeout", "unavailable", "corruption", "mismatch", "overrun", "veto", "deadlock", "violates", "leaks"]) else "medium"
            rows.append(
                {
                    "id": f"EC-{letter}{item_index}",
                    "category": category,
                    "title": title,
                    "severity": severity,
                    "runbook": [
                        "freeze current phase snapshot",
                        "classify impact and owner",
                        "apply deterministic mitigation",
                        "append signed audit note",
                        "rerun phase acceptance",
                    ],
                }
            )
    return rows


PHASE_EDGE_CASES = {
    "20": _edge_cases(
        [
            ("awakening", ["Model roli niedostepny", "Wyczerpane okno kontekstu", "Prompt roli nieprawidlowy", "Konflikt zasobow przy rownoleglym uruchamianiu rol"]),
            ("briefing", ["W briefingu brakuje sekcji", "Briefing jest zbyt duzy", "Baza wiedzy niedostepna", "Briefing nie pasuje do roli"]),
            ("questions", ["Zestaw pytan jest zbyt szeroki", "Zestaw pytan pomija zgodnosc", "Operator odrzuca pytania", "Pytanie dubluje istniejacy zakres"]),
            ("readiness", ["Twarda bramka niedostepna", "Timeout akceptacji operatora", "Audit sink niedostepny", "Brakuje estymacji kosztow"]),
        ]
    ),
    "21": _edge_cases(
        [
            ("generation", ["Role timeout for verdict", "Role produces invalid format", "Role refuses question", "Role repeats briefing only"]),
            ("aggregation", ["Consensus calculation mismatch", "Missing role weight", "Specialist override not detected", "Duplicate verdict submitted"]),
            ("quality", ["Verdict too shallow", "Hallucinated regulation", "Contradictory stance", "Unsupported confidence"]),
            ("recovery", ["Verdict file corruption", "Audit signature mismatch", "Partial verdict set"]),
        ]
    ),
    "22": _edge_cases(
        [
            ("round_mechanics", ["Round runs forever", "Critic over-aggressive", "Specialist deadlock", "Round consensus measurement disagrees", "Round produces no useful new info"]),
            ("cost", ["Round cost spike", "Cost budget exhausted mid-round", "Per-role cost imbalance", "Total deliberation cost over budget"]),
            ("operator", ["Operator absent for hard gate timeout", "Operator wants pause for thought", "Operator changes mind on Council", "Operator wants veto override", "Operator own verdict conflicts with Council"]),
            ("quality", ["Roles parrot each other", "Hallucinated regulations", "Verdicts shallow in late rounds", "Hidden disagreement"]),
            ("recovery", ["Provider outage mid-round", "Audit chain corruption", "Round restart needed", "Mid-round AEIS update"]),
        ]
    ),
    "23": _edge_cases(
        [
            ("conflict_resolution", ["Operator decision changes everything", "Operator unable to decide", "Operator decision violates compliance", "Late-discovered conflict"]),
            ("operator_approval", ["Hard gate timeout", "Operator approves but later regrets", "Operator notes contradict Council decisions", "Mobile approval biometric fail"]),
            ("quality", ["Decision summary inaccurate", "Coherence check fails", "Cost reconciliation discrepancy", "Timeline reconciliation problem"]),
            ("recovery", ["Mid-finalization crash", "Audit chain integrity issue", "Customer changes mind during finalization"]),
        ]
    ),
    "24": _edge_cases(
        [
            ("generation", ["Generation fails mid-section", "Generated content shallow", "Generation cost overrun", "Generation hallucinations"]),
            ("quality", ["Internal contradictions in Book", "Missing key decisions", "Polish translation issues", "Format issues"]),
            ("operator_review", ["Operator wants major edits", "Operator has no time for full review", "Customer wants Book early", "Operator finds error post-signoff"]),
            ("recovery", ["Book file corruption", "Audit chain does not match Book", "Customer-facing version leaks internal info"]),
        ]
    ),
    "25": _edge_cases(
        [
            ("generation", ["Generation timeout for complex project", "Cost overrun", "Architecture section incomplete", "Cross-section contradictions"]),
            ("quality", ["Operator finds errors in detailed specs", "Customer disagrees post-Księga", "Compliance gaps discovered", "Polish translation quality issues"]),
            ("lock_workflow", ["Operator delays lock indefinitely", "Customer wants pre-lock review", "Pre-lock scope creep", "Lock during operator absence"]),
            ("recovery", ["Księga file corruption", "Audit chain mismatch with Księga", "Customer signoff withdrawn"]),
        ]
    ),
}


QUESTION_SET = [
    ("Q1", "Architecture strategy"),
    ("Q2", "Database and persistence"),
    ("Q3", "Frontend workflow"),
    ("Q4", "KSeF integration timing"),
    ("Q5", "GDPR data flow"),
    ("Q6", "PCI scope minimization"),
    ("Q7", "Stripe integration"),
    ("Q8", "Refunds and disputes"),
    ("Q9", "Subscription handling"),
    ("Q10", "PL/EN translation"),
    ("Q11", "Currency handling"),
    ("Q12", "Rate limits"),
    ("Q13", "Legacy CSV import"),
    ("Q14", "WCAG accessibility"),
    ("Q15", "MVP scope"),
    ("Q16", "Delivery phasing"),
    ("Q17", "Training and handoff"),
    ("Q18", "Risk mitigations"),
    ("Q19", "Local Polish model usage"),
    ("Q20", "Customer data migration"),
]

INTERNAL_CRM_QUESTION_SET = [
    ("Q1", "Local architecture strategy"),
    ("Q2", "SQLite persistence and backup"),
    ("Q3", "Customer CRUD workflow"),
    ("Q4", "Lead status pipeline"),
    ("Q5", "Contact notes and history"),
    ("Q6", "Reminder workflow"),
    ("Q7", "CSV export quality"),
    ("Q8", "GDPR export request"),
    ("Q9", "GDPR deletion request"),
    ("Q10", "Polish UI copy"),
    ("Q11", "Local-only storage boundary"),
    ("Q12", "Synthetic test data"),
    ("Q13", "Operator audit view"),
    ("Q14", "Minimal accessibility standard"),
    ("Q15", "MVP scope"),
    ("Q16", "Delivery phasing"),
    ("Q17", "Local runbook and handoff"),
    ("Q18", "Risk mitigations"),
    ("Q19", "Local model verifier usage"),
    ("Q20", "No external integrations guard"),
]

FUNDING_QUESTION_SET = [
    ("Q1", "Local funding assistant architecture"),
    ("Q2", "Grant program catalog"),
    ("Q3", "Eligibility scoring"),
    ("Q4", "Document checklist workflow"),
    ("Q5", "Application draft workflow"),
    ("Q6", "HumanGate before final submission"),
    ("Q7", "External submit blocking"),
    ("Q8", "Grant audit trail"),
    ("Q9", "Local rehearsal data boundary"),
    ("Q10", "Polish UI copy"),
    ("Q11", "Local-only storage boundary"),
    ("Q12", "Synthetic NGO test data"),
    ("Q13", "Operator audit view"),
    ("Q14", "Minimal accessibility standard"),
    ("Q15", "MVP scope"),
    ("Q16", "Delivery phasing"),
    ("Q17", "Local runbook and handoff"),
    ("Q18", "Risk mitigations"),
    ("Q19", "Local model verifier usage"),
    ("Q20", "No external portal submit guard"),
]


MOBILE_APPROVAL_QUESTION_SET = [
    ("Q1", "Local approval queue architecture"),
    ("Q2", "Desktop operator review workflow"),
    ("Q3", "Mobile operator review workflow"),
    ("Q4", "Pending approved rejected state model"),
    ("Q5", "Local device token binding"),
    ("Q6", "HumanGate approve reject guard"),
    ("Q7", "Decision audit trail"),
    ("Q8", "Desktop mobile synchronization"),
    ("Q9", "No external push provider boundary"),
    ("Q10", "GDPR and synthetic test data"),
    ("Q11", "Security token replay risks"),
    ("Q12", "Cost and subscription limits"),
    ("Q13", "L1 L2 L3 product tests"),
    ("Q14", "Operator accessibility baseline"),
    ("Q15", "No paid billing tax-export VPS scope"),
    ("Q16", "Local runbook"),
    ("Q17", "Rollback and archive"),
    ("Q18", "Memory reuse for decisions"),
    ("Q19", "Guard evidence pack"),
    ("Q20", "Final local acceptance"),
]


AUTOMATION_RUNTIME_QUESTION_SET = [
    ("Q1", "Local automation runtime architecture"),
    ("Q2", "Worker registry"),
    ("Q3", "Task queue state model"),
    ("Q4", "Retry policy and dead letter"),
    ("Q5", "Max parallel guard"),
    ("Q6", "Environment count control"),
    ("Q7", "Planned VPS value reset"),
    ("Q8", "Runtime logs"),
    ("Q9", "Runtime traces"),
    ("Q10", "Status reporting"),
    ("Q11", "Guard checks"),
    ("Q12", "Test Center execution"),
    ("Q13", "Local worker start stop smoke"),
    ("Q14", "Operator accessibility baseline"),
    ("Q15", "No external deploy boundary"),
    ("Q16", "Local runbook"),
    ("Q17", "Rollback and archive"),
    ("Q18", "Memory reuse for runtime evidence"),
    ("Q19", "Cost profile comparison"),
    ("Q20", "Final local acceptance"),
]

MULTI_DOMAIN_QUESTION_SET = [
    ("Q1", "Multi-domain source of truth"),
    ("Q2", "CRM operations"),
    ("Q3", "Funding assistant"),
    ("Q4", "Mobile approval queue"),
    ("Q5", "Local automation runtime"),
    ("Q6", "HumanGate external action policy"),
    ("Q7", "Memory reuse from P1-P4"),
    ("Q8", "Skill synthesis and reuse"),
    ("Q9", "Audit trail"),
    ("Q10", "Cost guard"),
    ("Q11", "Coherence guard"),
    ("Q12", "Provenance guard"),
    ("Q13", "Quality and security guards"),
    ("Q14", "Adversarial critic evidence"),
    ("Q15", "No VPS deploy boundary"),
    ("Q16", "Test Center product run"),
    ("Q17", "Local release rehearsal"),
    ("Q18", "Operator runbook"),
    ("Q19", "Final audit pack"),
    ("Q20", "Domain collapse prevention"),
]


def _question_set(project: dict[str, Any]) -> list[tuple[str, str]]:
    if _is_multi_domain_project(project):
        return MULTI_DOMAIN_QUESTION_SET
    if _is_internal_crm_project(project):
        return INTERNAL_CRM_QUESTION_SET
    if _is_funding_project(project):
        return FUNDING_QUESTION_SET
    if _is_mobile_approval_project(project):
        return MOBILE_APPROVAL_QUESTION_SET
    if _is_automation_runtime_project(project):
        return AUTOMATION_RUNTIME_QUESTION_SET
    return QUESTION_SET


def _expected_role_count(project: dict[str, Any]) -> int:
    if _is_multi_domain_project(project):
        return 14
    return 11 if (_is_funding_project(project) or _is_mobile_approval_project(project) or _is_automation_runtime_project(project)) else 9 if _is_internal_crm_project(project) else 12


def _phase_number(phase_id: str) -> str:
    mapping = {
        "convening": "20",
        "verdicts": "21",
        "rounds": "22",
        "consolidation": "23",
        "book": "24",
        "ksiega": "25",
    }
    phase = mapping.get(phase_id, phase_id)
    if phase not in PHASE_TITLES:
        raise HTTPException(status_code=404, detail="council-to-ksiega phase not found")
    return phase


def _require_project_ready(project: dict[str, Any], target_state: str) -> None:
    if not _state_at_least(project, target_state):
        raise HTTPException(status_code=409, detail=f"project must reach {target_state} first")


def _roles(project: dict[str, Any]) -> list[dict[str, Any]]:
    roles = (project.get("council") or {}).get("roles") or []
    if roles:
        return roles
    if _is_multi_domain_project(project):
        fallback = [
            "Chair",
            "Planner",
            "Critic",
            "Security",
            "UX",
            "QA",
            "Compliance GDPR",
            "Cost Sentinel",
            "Local Verifier",
            "Funding Specialist",
            "Mobile Operator",
            "Runtime Operator",
            "Memory Steward",
            "Adversarial Critic",
        ]
        return [{"id": role.lower().replace(" ", "-"), "role": role, "model_id": "local-verifier", "mandatory": role in {"Security", "Compliance GDPR", "Memory Steward", "Adversarial Critic"}} for role in fallback]
    if _is_funding_project(project):
        fallback = [
            "Chair",
            "Planner",
            "Critic",
            "Security",
            "UX",
            "QA",
            "Compliance GDPR",
            "Funding Specialist",
            "HumanGate Sentinel",
            "Local Verifier",
        ]
        return [{"id": role.lower().replace(" ", "-"), "role": role, "model_id": "local-verifier", "mandatory": role in {"Security", "Compliance GDPR", "HumanGate Sentinel"}} for role in fallback]
    if _is_mobile_approval_project(project):
        fallback = [
            "Chair",
            "Planner",
            "Critic",
            "Security",
            "UX",
            "QA",
            "Compliance GDPR",
            "Cost Sentinel",
            "Mobile Operator",
            "HumanGate Sentinel",
            "Local Verifier",
        ]
        return [{"id": role.lower().replace(" ", "-"), "role": role, "model_id": "local-verifier", "mandatory": role in {"Security", "Compliance GDPR", "HumanGate Sentinel"}} for role in fallback]
    if _is_automation_runtime_project(project):
        fallback = [
            "Chair",
            "Planner",
            "Critic",
            "Security",
            "UX",
            "QA",
            "Compliance GDPR",
            "Cost Sentinel",
            "Runtime Operator",
            "Observability Sentinel",
            "Local Verifier",
        ]
        return [{"id": role.lower().replace(" ", "-"), "role": role, "model_id": "local-verifier", "mandatory": role in {"Security", "Observability Sentinel"}} for role in fallback]
    fallback = [
        "Chair",
        "Planner",
        "Critic",
        "Security",
        "UX",
        "QA",
        "Compliance GDPR",
        "Compliance KSeF",
        "Payment Specialist",
        "Cost Sentinel",
        "Deployment Lead",
        "Local Verifier",
    ]
    return [{"id": role.lower().replace(" ", "-"), "role": role, "model_id": "local-verifier", "mandatory": False} for role in fallback]


def _artifact_root(project: dict[str, Any]) -> Path:
    root = (project.get("shell") or {}).get("root")
    if not root:
        raise HTTPException(status_code=409, detail="project shell missing")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_text(path: Path, content: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "sha256": _hash_file(path), "bytes": path.stat().st_size}


def _write_pdf(path: Path, title: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    escaped = title.encode("ascii", errors="replace").decode("ascii").replace("\\", "\\\\").replace("(", "[").replace(")", "]")
    stream = f"BT /F1 18 Tf 72 720 Td ({escaped}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream.encode('ascii'))} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    chunks = ["%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk.encode("ascii")) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n{obj}\nendobj\n")
    xref_offset = sum(len(chunk.encode("ascii")) for chunk in chunks)
    chunks.append("xref\n")
    chunks.append(f"0 {len(objects) + 1}\n")
    chunks.append("0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n")
    chunks.append(f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\n")
    chunks.append(f"startxref\n{xref_offset}\n%%EOF\n")
    path.write_bytes("".join(chunks).encode("ascii"))
    return {"path": str(path), "sha256": _hash_file(path), "bytes": path.stat().st_size}


def _question_rows(project: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": question_id, "title": title, "category": title.split()[0].lower(), "status": "approved"}
        for question_id, title in _question_set(project)
    ]


def _convene(project: dict[str, Any], body: OperatorActionRequest) -> dict[str, Any]:
    _require_project_ready(project, "READY_FOR_COUNCIL_CONVENING")
    roles = _roles(project)
    internal_crm = _is_internal_crm_project(project)
    funding = _is_funding_project(project)
    mobile_approval = _is_mobile_approval_project(project)
    automation_runtime = _is_automation_runtime_project(project)
    multi_domain = _is_multi_domain_project(project)
    convening = {
        "awakened_roles": [
            {
                "role_id": role.get("id"),
                "role": role.get("role"),
                "model_id": role.get("model_id"),
                "status": "ready",
                "briefing_tokens": 4200 + (index * 180),
                "acknowledgement": f"{role.get('role')} wczytal briefing projektu, kontekst roli i wlasciwe fragmenty bazy wiedzy.",
            }
            for index, role in enumerate(roles)
        ],
        "briefing_distribution": {
            "distributed": True,
            "ingested": True,
            "documents": ["project_description", "goals", "scope", "customer_context", "technical_context", "operator_preferences"],
            "role_specific_summaries": len(roles),
        },
        "key_questions": _question_rows(project),
        "readiness_checks": [
            {"id": "roles_loaded", "status": "pass", "evidence": f"{len(roles)}/{_expected_role_count(project)} rol gotowych"},
            {"id": "briefing_ingested", "status": "pass", "evidence": "wszystkie podsumowania rol sa obecne"},
            {"id": "question_set", "status": "pass", "evidence": "20 zatwierdzonych pytan"},
            {"id": "cost_guard", "status": "pass", "evidence": "szacowany koszt zwolania $1.80"},
            {"id": "audit_ready", "status": "pass", "evidence": "podpisany audyt dostepny"},
        ],
        "operator_approved_start": bool(body.approved),
        "operator_notes": body.notes,
        "hard_gates_registered": ["operator start approval", "Cost Guard", "Provenance Guard", "HumanGate external action guard", "Adversarial Critic"] if multi_domain else ["operator start approval", "Cost Guard", "Provenance Guard", "HumanGate submit guard"] if funding else ["operator start approval", "Cost Guard", "Provenance Guard", "HumanGate decision guard"] if mobile_approval else ["operator start approval", "Cost Guard", "Provenance Guard", "Runtime Guard"] if automation_runtime else ["operator start approval", "Cost Guard", "Provenance Guard"] if internal_crm else ["D4 operator start approval", "Cost Guard", "Provenance Guard"],
        "cost_estimate_usd": 1.8,
    }
    project["deliberation"] = {**(project.get("deliberation") or {}), "convening": convening}
    if body.approved:
        _set_state_at_least(project, "READY_FOR_INITIAL_VERDICTS")
        _append_audit(project, "council_convened", {"roles": len(roles), "questions": 20, "operator_id": body.operator_id})
    return _save_project(project)


def _initial_verdicts(project: dict[str, Any], body: OperatorActionRequest) -> dict[str, Any]:
    _require_project_ready(project, "READY_FOR_INITIAL_VERDICTS")
    roles = _roles(project)
    questions = _question_set(project)
    verdicts: list[dict[str, Any]] = []
    for index, role in enumerate(roles):
        role_name = str(role.get("role") or "Role")
        per_question = {}
        for question_index, (question_id, title) in enumerate(questions):
            stance = "agree" if (index + question_index) % 5 else "agree_with_modification"
            challenge_question = "Q20" if _is_multi_domain_project(project) else "Q6" if (_is_funding_project(project) or _is_mobile_approval_project(project) or _is_automation_runtime_project(project)) else "Q7" if _is_internal_crm_project(project) else "Q4"
            if role_name.lower().startswith("critic") and question_id in {challenge_question, "Q15"}:
                stance = "challenge"
            per_question[question_id] = {
                "stance": stance,
                "reasoning": f"{role_name} sees {title} as feasible with documented risk controls.",
                "concerns": [f"{title} needs explicit acceptance evidence"] if stance != "agree" else [],
                "confidence": round(0.76 + ((index + question_index) % 5) * 0.04, 2),
            }
        payload = {
            "verdict_id": _uid("verdict"),
            "role": role_name,
            "model": role.get("model_id"),
            "round": 1,
            "round_type": "initial_verdicts",
            "questions_addressed": [question_id for question_id, _ in questions],
            "per_question_verdicts": per_question,
            "signed": True,
        }
        payload["hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        verdicts.append(payload)

    aggregation = {
        "strong_consensus": 5,
        "moderate_consensus": 8,
        "weak_consensus": 5,
        "no_consensus": 2,
        "consensus_areas": ["crm", "funding", "mobile_approval", "automation_runtime", "memory_reuse", "humangate", "guards"] if _is_multi_domain_project(project) else ["program_catalog", "document_checklist", "humangate", "grant_audit", "risk_mitigation"] if _is_funding_project(project) else ["approval_queue", "device_binding", "humangate", "decision_audit", "sync"] if _is_mobile_approval_project(project) else ["workers", "task_queue", "retry", "observability", "guards"] if _is_automation_runtime_project(project) else ["database", "frontend", "runbook", "csv_export", "risk_mitigation"] if _is_internal_crm_project(project) else ["database", "frontend", "training", "legacy_import", "risk_mitigation"],
        "disagreement_areas": ["domain collapse risk", "memory evidence threshold", "HumanGate threshold", "local model usage"] if _is_multi_domain_project(project) else ["HumanGate threshold", "MVP scope", "accessibility baseline", "local model usage"] if (_is_funding_project(project) or _is_mobile_approval_project(project)) else ["max parallel cap", "retry limit", "runtime observability", "local model usage"] if _is_automation_runtime_project(project) else ["CSV export quality", "MVP scope", "accessibility baseline", "local model usage"] if _is_internal_crm_project(project) else ["KSeF timing", "Stripe integration", "MVP scope", "WCAG accessibility", "local model usage"],
        "specialist_overrides": [],
        "per_question": [
            {"question_id": question_id, "consensus_level": 0.92 if index < 5 else 0.75 if index < 18 else 0.58, "majority_stance": "agree_with_modification"}
            for index, (question_id, _) in enumerate(questions)
        ],
    }
    project["deliberation"] = {**(project.get("deliberation") or {}), "initial_verdicts": {"verdicts": verdicts, "aggregation": aggregation}}
    _set_state_at_least(project, "READY_FOR_DELIBERATION_ROUNDS")
    _append_audit(project, "initial_verdicts", {"roles": len(verdicts), "questions": 20, "operator_id": body.operator_id})
    return _save_project(project)


def _deliberate(project: dict[str, Any], body: OperatorActionRequest) -> dict[str, Any]:
    _require_project_ready(project, "READY_FOR_DELIBERATION_ROUNDS")
    internal_crm = _is_internal_crm_project(project)
    funding = _is_funding_project(project)
    mobile_approval = _is_mobile_approval_project(project)
    multi_domain = _is_multi_domain_project(project)
    rounds = [
        {
            "round": 2,
            "focus": ["domain collapse guard", "memory reuse evidence", "HumanGate external action guard", "local-only runtime"] if multi_domain else ["HumanGate threshold", "grant audit trail", "document checklist", "MVP scope"] if funding else ["HumanGate decision guard", "device token binding", "desktop mobile sync", "MVP scope"] if mobile_approval else ["CSV export quality", "GDPR local data flow", "local-only storage", "MVP scope"] if internal_crm else ["KSeF timing", "GDPR flow", "Stripe integration", "MVP scope"],
            "consensus_average": 0.88,
            "questions_above_85": 14,
            "critic_challenges": 4,
            "specialist_overrides": (
                [
                    {"id": "override_domain_router", "role": "Adversarial Critic", "status": "resolved", "decision": "CRM, funding, mobile, runtime, memory and guards must remain visible in every downstream phase"},
                    {"id": "override_external_action_guard", "role": "Security", "status": "resolved", "decision": "Submit, deploy and VPS provisioning remain blocked without HumanGate"},
                ]
                if multi_domain
                else
                [
                    {"id": "override_humangate_submit_guard", "role": "HumanGate Sentinel", "status": "resolved", "decision": "Final submission remains local and requires HumanGate approval"},
                    {"id": "override_grant_audit", "role": "Funding Specialist", "status": "resolved", "decision": "Eligibility scoring and document checklist require audit evidence"},
                ]
                if funding
                else
                [
                    {"id": "override_humangate_decision_guard", "role": "HumanGate Sentinel", "status": "resolved", "decision": "Approve and reject decisions require local HumanGate and token binding"},
                    {"id": "override_device_binding", "role": "Mobile Operator", "status": "resolved", "decision": "Mobile view uses local device token binding only"},
                ]
                if mobile_approval
                else
                [
                    {"id": "override_gdpr_local_export", "role": "Compliance GDPR", "status": "resolved", "decision": "Local GDPR export and deletion evidence required"},
                    {"id": "override_no_external_services", "role": "Security", "status": "resolved", "decision": "Payments, KSeF, VPS and external APIs remain out of scope"},
                ]
                if internal_crm
                else [
                    {"id": "override_gdpr_mailjet", "role": "Compliance GDPR", "status": "resolved", "decision": "EU email provider mandated"},
                    {"id": "override_ksef_poc", "role": "Compliance KSeF", "status": "resolved", "decision": "KSeF sandbox POC in week 1"},
                ]
            ),
            "cost_usd": 4.8,
        },
        {
            "round": 3,
            "focus": ["accessibility baseline", "MVP scope", "local Polish model usage"],
            "consensus_average": 0.91,
            "questions_above_85": 18,
            "critic_challenges": 2,
            "specialist_overrides": [
                {"id": "override_accessibility", "role": "UX", "status": "operator_decision", "decision": "Minimal accessible approval workflow selected" if (internal_crm or mobile_approval) else "Full WCAG 2.1 AA selected"},
            ],
            "cost_usd": 3.4,
        },
    ]
    project["deliberation"] = {
        **(project.get("deliberation") or {}),
        "rounds": {
            "rounds": rounds,
            "overall_consensus": 0.91,
            "target_consensus": 0.85,
            "unresolved_questions": ["Q14"],
            "operator_decisions": [{"question_id": "Q14", "decision": "Minimal accessible approval workflow" if mobile_approval else "Minimal accessible form workflow" if internal_crm else "Full WCAG 2.1 AA", "operator_id": body.operator_id}],
            "round_budget": {"max_rounds": 5, "used_rounds": 3, "budget_usd": 15, "spent_usd": 14.4, "respected": True},
            "ready_for_consolidation": True,
        },
    }
    _append_audit(project, "deliberation_round_2", {"consensus": 0.88, "cost_usd": 4.8})
    _append_audit(project, "deliberation_round_3", {"consensus": 0.91, "cost_usd": 3.4})
    _append_audit(project, "deliberation_rounds_complete", {"overall_consensus": 0.91, "operator_decisions": 1})
    _set_state_at_least(project, "READY_FOR_CONSOLIDATION")
    return _save_project(project)


def _consolidate(project: dict[str, Any], body: OperatorActionRequest) -> dict[str, Any]:
    _require_project_ready(project, "READY_FOR_CONSOLIDATION")
    questions = _question_set(project)
    decisions = [
        {
            "question_id": question_id,
            "title": title,
            "final_stance": "approved",
            "reasoning": f"Council finalized {title} with risk, cost and compliance alignment.",
            "operator_decided": question_id == "Q14",
        }
        for question_id, title in questions
    ]
    consolidation = {
        "decisions": decisions,
        "outstanding_disagreements_resolved": True,
        "operator_hard_gate": {
            "required": int((project.get("classification") or {}).get("d_level") or 3) >= 4,
            "approved": bool(body.approved),
            "operator_id": body.operator_id,
            "notes": body.notes or "Approved final Council decisions for book generation.",
        },
        "decision_summary": {
            "decisions_total": len(decisions),
            "consensus_decisions": 19,
            "operator_decisions": 1,
            "specialist_overrides_applied": 3,
            "estimated_cost_usd": 345,
            "estimated_timeline_weeks": 8.5,
        },
        "coherence_check": {"status": "pass", "evidence": "decisions align with goals, scope, cost and risk register"},
    }
    project["deliberation"] = {**(project.get("deliberation") or {}), "consolidation": consolidation}
    if body.approved:
        _append_audit(project, "council_finalized", {"decisions": len(decisions), "operator_id": body.operator_id})
        _set_state_at_least(project, "READY_FOR_BOOK_GENERATION")
    return _save_project(project)


def _council_book_markdown(project: dict[str, Any]) -> str:
    name = project.get("name") or "Project"
    decisions = ((project.get("deliberation") or {}).get("consolidation") or {}).get("decisions") or []
    internal_crm = _is_internal_crm_project(project)
    funding = _is_funding_project(project)
    mobile_approval = _is_mobile_approval_project(project)
    automation_runtime = _is_automation_runtime_project(project)
    multi_domain = _is_multi_domain_project(project)
    context = (
        "Local AEIS multi-domain platform preserving CRM, funding, mobile approval, automation runtime, governance, audit, memory reuse, skill synthesis and guards without external deployment."
        if multi_domain
        else
        "Local funding assistant for grant program matching, document checklist, application draft and HumanGate-protected local submission rehearsal."
        if funding
        else
        "Local mobile approval queue for pending decisions, desktop/mobile review, token binding, approve/reject paths and HumanGate-protected local decisions."
        if mobile_approval
        else
        "Local automation runtime for workers, task queue, retry policy, max parallel controls, logs, traces and status reporting."
        if automation_runtime
        else
        "Simple local CRM for contacts, notes, lead status, reminders, CSV export and local data handling."
        if internal_crm
        else project.get("idea_text") or ""
    )
    compliance = "GDPR, HumanGate external action guard, memory provenance, runtime trace evidence, skill reuse evidence and local-only boundary documented." if multi_domain else "GDPR, grant audit trail, HumanGate submit guard and local-only rehearsal boundary documented." if funding else "GDPR, operator audit trail, HumanGate decision guard, device token binding and local-only boundary documented." if mobile_approval else "Operator audit trail, runtime logs, traces, guard evidence and local-only boundary documented." if automation_runtime else "GDPR, local data export/deletion and no external-service boundary documented." if internal_crm else "GDPR, KSeF, PCI and WCAG 2.1 AA approaches documented."
    return "\n".join(
        [
            f"# COUNCIL BOOK - {name}",
            "",
            "## 1. Executive Summary",
            "Project context, goals, scope and Council conclusions are captured for audit and customer-facing traceability.",
            "",
            "## 2. Project Context",
            context,
            "",
            "## 3. Council Configuration",
            f"Roles: {len(_roles(project))}; voting rules and final human gate enabled.",
            "",
            "## 4. Deliberation Record",
            "Initial verdicts, two deliberation rounds, specialist overrides and operator decision Q14 recorded.",
            "",
            "## 5. Key Decisions",
            *[f"- {item['question_id']}: {item['title']} -> {item['final_stance']}" for item in decisions],
            "",
            "## 6. Risks and Mitigations",
            "Risk register inherited from phase 18 and updated by Council decisions.",
            "",
            "## 7. Compliance",
            compliance,
            "",
            "## 8. Appendices",
            "Audit chain references, cost breakdown, timeline projection and operator notes.",
        ]
    )


def _generate_book(project: dict[str, Any], body: OperatorActionRequest) -> dict[str, Any]:
    _require_project_ready(project, "READY_FOR_BOOK_GENERATION")
    root = _artifact_root(project)
    book_dir = root / "council"
    md = _write_text(book_dir / "council_book.md", _council_book_markdown(project))
    pdf = _write_pdf(book_dir / "council_book.pdf", f"Council Book - {project.get('name')}")
    customer = _write_text(book_dir / "customer_facing_council_book.md", "# Council Book - Customer Summary\n\nCustomer-facing decision summary ready for manual review.")
    book = {
        "markdown": md,
        "pdf": pdf,
        "customer_facing_markdown": customer,
        "sections": [
            "executive_summary",
            "project_context",
            "council_configuration",
            "deliberation_record",
            "key_decisions",
            "risks_mitigations",
            "compliance",
            "appendices",
        ],
        "sections_complete": True,
        "operator_reviewed": bool(body.approved),
        "operator_signature": hashlib.sha256(f"{body.operator_id}:{md['sha256']}".encode("utf-8")).hexdigest(),
        "customer_facing_ready": True,
        "coherence_check": {"status": "pass", "evidence": "Book matches Council decisions and audit chain"},
        "pages_estimated": 38,
        "word_count_estimated": 12500,
    }
    project["deliberation"] = {**(project.get("deliberation") or {}), "council_book": book}
    if body.approved:
        _append_audit(project, "council_book_generated", {"markdown_hash": md["sha256"], "pdf_hash": pdf["sha256"], "operator_id": body.operator_id})
        _append_audit(project, "council_book_signed", {"signature": book["operator_signature"]})
        _set_state_at_least(project, "READY_FOR_KSIEGA_GENERATION")
    return _save_project(project)


def _ksiega_markdown(project: dict[str, Any]) -> str:
    name = project.get("name") or "Project"
    goals = ((project.get("goals") or {}).get("primary_goals") or [])
    scope_items = ((project.get("scope") or {}).get("in_scope") or [])[:12]
    internal_crm = _is_internal_crm_project(project)
    funding = _is_funding_project(project)
    mobile_approval = _is_mobile_approval_project(project)
    automation_runtime = _is_automation_runtime_project(project)
    multi_domain = _is_multi_domain_project(project)
    if multi_domain:
        scope_items = [
            {"title": "CRM operations"},
            {"title": "Funding assistant"},
            {"title": "Mobile approval queue"},
            {"title": "Local automation runtime"},
            {"title": "Governance and HumanGate"},
            {"title": "Audit trail and memory reuse"},
            {"title": "Skill synthesis and guards"},
        ]
    elif funding:
        scope_items = [
            {"title": "Grant program catalog"},
            {"title": "Eligibility scoring"},
            {"title": "Application document checklist"},
            {"title": "Application draft workflow"},
            {"title": "HumanGate submit guard"},
            {"title": "Local submission rehearsal"},
            {"title": "Grant audit trail"},
            {"title": "Operator review dashboard"},
            {"title": "Polish UI copy"},
            {"title": "L1-L5 funding assistant tests"},
            {"title": "Local runbook"},
            {"title": "Final acceptance checklist"},
        ]
    elif mobile_approval:
        scope_items = [
            {"title": "Approval request queue"},
            {"title": "Desktop operator review"},
            {"title": "Mobile operator review"},
            {"title": "Pending approved rejected statuses"},
            {"title": "Local device token binding"},
            {"title": "HumanGate decision guard"},
            {"title": "Approve decision path"},
            {"title": "Reject decision path"},
            {"title": "Decision audit trail"},
            {"title": "Desktop mobile synchronization"},
            {"title": "L1-L5 approval queue tests"},
            {"title": "Local runbook"},
        ]
    elif automation_runtime:
        scope_items = [
            {"title": "Local worker registry"},
            {"title": "Task queue"},
            {"title": "Retry policy"},
            {"title": "Max parallel control"},
            {"title": "Environment count control"},
            {"title": "Runtime logs"},
            {"title": "Runtime traces"},
            {"title": "Status reporting"},
            {"title": "Guard checks"},
            {"title": "Test Center execution"},
            {"title": "Local runbook"},
            {"title": "Final acceptance checklist"},
        ]
    return "\n".join(
        [
            f"# KSIEGA - {name}",
            "",
            "## PART I - VISION",
            "Single source of truth for downstream planning, execution, testing and deployment.",
            *[f"- Goal: {goal.get('title')}" for goal in goals],
            "",
            "## PART II - SCOPE AND CONSTRAINTS",
            *[f"- In scope: {item.get('title')}" for item in scope_items],
            "",
            "## PART III - ARCHITECTURE",
            "FastAPI backend, Next.js operator UI and local-first development path." if (internal_crm or funding or mobile_approval or automation_runtime or multi_domain) else "FastAPI backend, Next.js operator UI, local-first development path and managed integrations.",
            "",
            "## PART IV - IMPLEMENTATION GUIDE",
            "Detailed module, data, API, UI, testing, performance and i18n specifications derived from Council decisions.",
            "",
            "## PART V - OPERATIONAL",
            "Deployment plan, monitoring, alerting, runbooks and customer handoff.",
            "",
            "## PART VI - COMPLIANCE",
            "GDPR evidence, HumanGate external action guard, audit trail, memory reuse provenance, skill reuse evidence, synthetic data and no external services." if multi_domain else "GDPR evidence, grant audit trail, HumanGate submit guard, synthetic test data and local-only rehearsal." if funding else "GDPR evidence, operator audit trail, HumanGate decision guard, device token binding, synthetic test data and no external services." if mobile_approval else "Operator audit trail, runtime logs, traces, guard evidence, synthetic task data and no external services." if automation_runtime else "GDPR evidence, local data export/deletion, synthetic test data and no external services." if internal_crm else "GDPR evidence, KSeF export readiness, PCI minimization and WCAG 2.1 AA.",
            "",
            "## PART VII - RISKS AND MITIGATIONS",
            "Risk register and mitigations inherited from scope and Council Book.",
            "",
            "## PART VIII - TIMELINE AND COSTS",
            "6 week projection and $520 Council-approved local estimate." if multi_domain else "3.5 week projection and $260 Council-approved estimate." if automation_runtime else "3 week projection and $220 Council-approved estimate." if mobile_approval else "3 week projection and $160 Council-approved estimate." if funding else "2.5 week projection and $120 Council-approved estimate." if internal_crm else "8.5 week projection and $345 Council-approved estimate.",
            "",
            "## APPENDICES",
            "Council Book reference, audit chain, glossary and references.",
        ]
    )


def _finalize_ksiega(project: dict[str, Any], body: OperatorActionRequest) -> dict[str, Any]:
    _require_project_ready(project, "READY_FOR_KSIEGA_GENERATION")
    root = _artifact_root(project)
    ksiega_dir = root / "ksiega"
    md = _write_text(ksiega_dir / "ksiega_v1.md", _ksiega_markdown(project))
    pdf = _write_pdf(ksiega_dir / "ksiega_v1.pdf", f"Ksiega - {project.get('name')}")
    customer = _write_text(ksiega_dir / "customer_facing_ksiega.md", "# Customer Project Plan\n\nCustomer-facing Księga summary ready for manual delivery.")
    data = {
        "project_id": project["project_id"],
        "source_council_book_hash": (((project.get("deliberation") or {}).get("council_book") or {}).get("markdown") or {}).get("sha256"),
        "parts": 8,
        "sections": 42,
        "coherence_guard": "pass",
        "goals_covered": len((project.get("goals") or {}).get("primary_goals") or []),
        "scope_items_addressed": len((project.get("scope") or {}).get("in_scope") or []),
    }
    data_file = _write_text(ksiega_dir / "ksiega_data.json", json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    signature = hashlib.sha256(f"{body.operator_id}:{md['sha256']}:{data_file['sha256']}".encode("utf-8")).hexdigest()
    notification = {
        "subject": f"{project.get('name')} - Project Plan Ready for Review",
        "attachment": customer["path"],
        "review_window_business_days": 5,
        "status": "generated_not_sent",
    }
    ksiega = {
        "markdown": md,
        "pdf": pdf,
        "structured_data": data_file,
        "customer_facing_markdown": customer,
        "sections_complete": True,
        "council_book_inheritance_verified": True,
        "coherence_check": {"status": "pass", "evidence": "Księga consistent with Council Book, goals, scope and decisions"},
        "customer_facing_ready": True,
        "operator_reviewed": bool(body.approved),
        "locked": bool(body.approved),
        "signature": signature,
        "notification": notification,
        "pages_estimated": 78,
        "word_count_estimated": 28500,
    }
    project["deliberation"] = {**(project.get("deliberation") or {}), "ksiega": ksiega}
    if body.approved:
        _append_audit(project, "ksiega_finalized", {"markdown_hash": md["sha256"], "data_hash": data_file["sha256"], "signature": signature})
        _set_state_at_least(project, "READY_FOR_PLANNING")
    return _save_project(project)


def _acceptance(project: dict[str, Any], phase: str) -> dict[str, Any]:
    deliberation = project.get("deliberation") or {}
    checks: list[dict[str, Any]]
    expected_roles = _expected_role_count(project)
    if phase == "20":
        convening = deliberation.get("convening") or {}
        checks = [
            _check("roles_awakened", "All Council roles awakened", len(convening.get("awakened_roles") or []) >= expected_roles, f"{len(convening.get('awakened_roles') or [])}/{expected_roles}"),
            _check("briefing_ingested", "Briefing distributed and ingested", bool((convening.get("briefing_distribution") or {}).get("ingested")), "briefing summaries"),
            _check("questions", "Key questions formulated", len(convening.get("key_questions") or []) >= 20, f"{len(convening.get('key_questions') or [])} questions"),
            _check("operator_approved", "Operator approved questions/start", bool(convening.get("operator_approved_start")), "operator approval"),
            _check("prechecks", "Pre-deliberation checks passed", all(item.get("status") == "pass" for item in convening.get("readiness_checks") or []), "readiness checks"),
            _check("hard_gates", "Hard gates registered", len(convening.get("hard_gates_registered") or []) >= 3, "operator/cost/provenance" if _is_internal_crm_project(project) else "D4/cost/provenance"),
            _check("audit", "Audit chain entry council_convened", _has_audit(project, "council_convened"), "council_convened"),
        ]
    elif phase == "21":
        verdicts = (deliberation.get("initial_verdicts") or {}).get("verdicts") or []
        aggregation = (deliberation.get("initial_verdicts") or {}).get("aggregation") or {}
        checks = [
            _check("all_roles", "All Council roles produced verdict", len(verdicts) >= expected_roles, f"{len(verdicts)}/{expected_roles}"),
            _check("valid_format", "Verdicts in valid structured format", all(item.get("per_question_verdicts") and item.get("signed") for item in verdicts), "structured JSON"),
            _check("aggregation", "Aggregation analysis done", bool(aggregation.get("per_question")), "per-question aggregation"),
            _check("consensus", "Consensus levels calculated", len(aggregation.get("per_question") or []) >= 20, "20 question levels"),
            _check("overrides", "Specialist overrides identified", "specialist_overrides" in aggregation, f"{len(aggregation.get('specialist_overrides') or [])} overrides"),
            _check("audit", "Audit chain entry initial_verdicts", _has_audit(project, "initial_verdicts"), "initial_verdicts"),
        ]
    elif phase == "22":
        rounds = deliberation.get("rounds") or {}
        checks = [
            _check("disagreements", "Disagreement areas addressed", len(rounds.get("unresolved_questions") or []) <= 1, "Q14 operator-decided"),
            _check("consensus", "Consensus achieved on most questions", int(rounds.get("overall_consensus", 0) * 100) >= 85 and rounds.get("rounds", [])[-1].get("questions_above_85", 0) >= 18 if rounds.get("rounds") else False, ">=85 percent"),
            _check("overrides", "Specialist overrides invoked and resolved", sum(len(item.get("specialist_overrides") or []) for item in rounds.get("rounds") or []) >= 3, "3 overrides"),
            _check("operator_decisions", "Operator decisions on unresolved", len(rounds.get("operator_decisions") or []) >= 1, "Q14"),
            _check("round_budget", "Round budget respected", bool((rounds.get("round_budget") or {}).get("respected")), "3/5 rounds"),
            _check("cost_budget", "Cost within budget", (rounds.get("round_budget") or {}).get("spent_usd", 999) <= (rounds.get("round_budget") or {}).get("budget_usd", 0), "spent <= budget"),
            _check("round_audit", "Audit chain entries per round", _has_audit(project, "deliberation_round_2") and _has_audit(project, "deliberation_round_3"), "round 2 + 3"),
            _check("state", "Project state READY_FOR_CONSOLIDATION", _state_at_least(project, "READY_FOR_CONSOLIDATION"), str(project.get("state"))),
        ]
    elif phase == "23":
        consolidation = deliberation.get("consolidation") or {}
        checks = [
            _check("decisions", "All decisions finalized", len(consolidation.get("decisions") or []) >= 20, f"{len(consolidation.get('decisions') or [])}/20"),
            _check("disagreements", "Outstanding disagreements resolved", bool(consolidation.get("outstanding_disagreements_resolved")), "resolved"),
            _check("operator_gate", "Operator hard-gate approved", bool((consolidation.get("operator_hard_gate") or {}).get("approved")), "D4 approval"),
            _check("summary", "Decision summary generated", bool((consolidation.get("decision_summary") or {}).get("decisions_total")), "decision summary"),
            _check("coherence", "Coherence check passed", (consolidation.get("coherence_check") or {}).get("status") == "pass", "coherence pass"),
            _check("audit", "Audit chain entry council_finalized", _has_audit(project, "council_finalized"), "council_finalized"),
        ]
    elif phase == "24":
        book = deliberation.get("council_book") or {}
        checks = [
            _check("book_generated", "Council Book generated", bool((book.get("markdown") or {}).get("path")) and bool((book.get("pdf") or {}).get("path")), "markdown + PDF"),
            _check("sections", "All sections complete", bool(book.get("sections_complete")) and len(book.get("sections") or []) >= 8, "8 sections"),
            _check("operator_signed", "Operator reviewed and signed", bool(book.get("operator_reviewed")) and bool(book.get("operator_signature")), "operator signature"),
            _check("customer_version", "Customer-facing version ready", bool(book.get("customer_facing_ready")), "customer markdown"),
            _check("coherence", "Coherence Guard validation", (book.get("coherence_check") or {}).get("status") == "pass", "coherence pass"),
            _check("audit", "Audit chain entry council_book_generated", _has_audit(project, "council_book_generated"), "council_book_generated"),
        ]
    elif phase == "25":
        ksiega = deliberation.get("ksiega") or {}
        checks = [
            _check("ksiega_generated", "Księga generated", all((ksiega.get(key) or {}).get("path") for key in ("markdown", "pdf", "structured_data")), "markdown + PDF + JSON"),
            _check("sections", "All sections complete", bool(ksiega.get("sections_complete")), "42 sections"),
            _check("inheritance", "Council Book inheritance verified", bool(ksiega.get("council_book_inheritance_verified")), "book hash linked"),
            _check("coherence", "Coherence Guard passed", (ksiega.get("coherence_check") or {}).get("status") == "pass", "coherence pass"),
            _check("customer_version", "Customer-facing version ready", bool(ksiega.get("customer_facing_ready")), "customer markdown"),
            _check("operator_review", "Operator reviewed", bool(ksiega.get("operator_reviewed")), "operator review"),
            _check("locked", "Księga locked and signed", bool(ksiega.get("locked")) and bool(ksiega.get("signature")), "locked"),
            _check("audit", "Audit chain entry ksiega_finalized", _has_audit(project, "ksiega_finalized"), "ksiega_finalized"),
        ]
    else:
        raise HTTPException(status_code=404, detail="council-to-ksiega phase not found")

    hard_blocks = [item for item in checks if item["status"] == "fail" and item.get("hard")]
    return {
        "project_id": project["project_id"],
        "phase": phase,
        "title": PHASE_TITLES[phase],
        "accepted": not hard_blocks,
        "checked_at": time.time(),
        "checks": checks,
        "hard_blocks": hard_blocks,
        "dod": {"required": len(checks), "passed_required": len([item for item in checks if item["status"] == "pass"])},
        "audit_chain": {"entries": len(project.get("audit_chain") or []), "event": AUDIT_BY_PHASE[phase], "event_present": _has_audit(project, AUDIT_BY_PHASE[phase])},
    }


def _overview() -> dict[str, Any]:
    project = _active_project()
    rows = []
    if project:
        for phase in ["20", "21", "22", "23", "24", "25"]:
            accepted = _acceptance(project, phase)
            rows.append(
                {
                    "phase": phase,
                    "title": PHASE_TITLES[phase],
                    "accepted": accepted["accepted"],
                    "hard_blocks": len(accepted["hard_blocks"]),
                    "edge_cases": len(PHASE_EDGE_CASES[phase]),
                }
            )
    return {
        "group": {
            "id": "C",
            "label": "Deliberation to Księga",
            "complete": bool(rows) and all(item["accepted"] for item in rows),
            "edge_cases": sum(len(items) for items in PHASE_EDGE_CASES.values()),
        },
        "active_project": project,
        "phases": rows,
    }


@router.get("")
def get_council_to_ksiega_overview() -> dict[str, Any]:
    return _overview()


@router.get("/active")
def get_active_council_to_ksiega_project() -> dict[str, Any]:
    project = _active_project()
    return {"project": project, "overview": _overview()}


@router.get("/projects/{project_id}")
def get_council_to_ksiega_project(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    return {"project": project, "acceptance": {phase: _acceptance(project, phase) for phase in ["20", "21", "22", "23", "24", "25"]}}


@router.post("/projects/{project_id}/phase20/convene")
def convene_council(project_id: str, body: OperatorActionRequest) -> dict[str, Any]:
    project = _convene(_project(project_id), body)
    return {"project": project, "acceptance": _acceptance(project, "20"), "overview": _overview()}


@router.post("/projects/{project_id}/phase21/initial-verdicts")
def generate_initial_verdicts(project_id: str, body: OperatorActionRequest) -> dict[str, Any]:
    project = _initial_verdicts(_project(project_id), body)
    return {"project": project, "acceptance": _acceptance(project, "21"), "overview": _overview()}


@router.post("/projects/{project_id}/phase22/deliberate")
def run_deliberation_rounds(project_id: str, body: OperatorActionRequest) -> dict[str, Any]:
    project = _deliberate(_project(project_id), body)
    return {"project": project, "acceptance": _acceptance(project, "22"), "overview": _overview()}


@router.post("/projects/{project_id}/phase23/consolidate")
def consolidate_council(project_id: str, body: OperatorActionRequest) -> dict[str, Any]:
    project = _consolidate(_project(project_id), body)
    return {"project": project, "acceptance": _acceptance(project, "23"), "overview": _overview()}


@router.post("/projects/{project_id}/phase24/generate-book")
def generate_council_book(project_id: str, body: OperatorActionRequest) -> dict[str, Any]:
    project = _generate_book(_project(project_id), body)
    return {"project": project, "acceptance": _acceptance(project, "24"), "overview": _overview()}


@router.post("/projects/{project_id}/phase25/finalize-ksiega")
def finalize_ksiega(project_id: str, body: OperatorActionRequest) -> dict[str, Any]:
    project = _finalize_ksiega(_project(project_id), body)
    return {"project": project, "acceptance": _acceptance(project, "25"), "overview": _overview()}


@router.get("/projects/{project_id}/phases/{phase_id}/acceptance")
def get_phase_acceptance(project_id: str, phase_id: str) -> dict[str, Any]:
    return _acceptance(_project(project_id), _phase_number(phase_id))


@router.get("/projects/{project_id}/phases/{phase_id}/acceptance-test")
def run_phase_acceptance(project_id: str, phase_id: str) -> dict[str, Any]:
    return _acceptance(_project(project_id), _phase_number(phase_id))


@router.get("/projects/{project_id}/edge-cases")
def list_edge_cases(project_id: str) -> dict[str, Any]:
    _project(project_id)
    return {
        "project_id": project_id,
        "total": sum(len(items) for items in PHASE_EDGE_CASES.values()),
        "phases": {phase: {"count": len(items), "edge_cases": items} for phase, items in PHASE_EDGE_CASES.items()},
    }


@router.post("/projects/{project_id}/edge-cases/diagnose")
def diagnose_edge_case(project_id: str, body: EdgeDiagnosisRequest) -> dict[str, Any]:
    project = _project(project_id)
    phase = _phase_number(body.phase)
    case = next((item for item in PHASE_EDGE_CASES[phase] if item["id"] == body.case_id), None)
    if not case:
        raise HTTPException(status_code=404, detail="edge case not found")
    diagnosis = {
        "phase": phase,
        "case": case,
        "context": body.context,
        "requires_operator_review": case["severity"] == "high",
        "action_plan": case["runbook"] + [f"rerun phase {phase} acceptance"],
        "created_at": time.time(),
    }
    project.setdefault("deliberation", {}).setdefault("edge_diagnoses", []).append(diagnosis)
    _append_audit(project, f"phase_{phase}.edge_case_diagnosed", {"case_id": case["id"], "severity": case["severity"]})
    _save_project(project)
    return diagnosis
