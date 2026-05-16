"""SYLION API -- Council routes (Wave A3).

Project-scoped council semantics endpoints. Backed by the unified
ModelRegistry council methods (cognitive/model_registry.py) and
project_mode/store.py council helpers.

Endpoints:
  GET  /api/v1/council/{project_id}/state     -- enabled, active_size, members,
                                                  decision_hierarchy
  POST /api/v1/council/{project_id}/reconcile -- re-derive members so they
                                                  match council_plan exactly
  POST /api/v1/council/{project_id}/enable    -- toggle council on/off

These complement the per-project routes in projects_routes.py
(GET/PUT /api/v1/projects/{id}/council) by providing the canonical
truth-plane view used by governance and operator dashboards.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.cognitive.llm_runtime import LLMUnavailable, call_llm, extract_json_object
from sylion.cognitive.model_registry import (
    CouncilMember,
    get_model_registry,
)
from sylion.governance.council_hybrid import VALID_ROLES, get_council_hybrid
from sylion.governance.tickets import GovernanceTicket, fetch_pending, submit

log = logging.getLogger("sylion.api.council_routes")

router = APIRouter(prefix="/api/v1/council", tags=["council"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CouncilStateResponse(BaseModel):
    project_id: str
    enabled: bool
    active_size: int
    members: list[dict[str, Any]]
    decision_hierarchy: list[str]


class EnableRequest(BaseModel):
    enabled: bool = Field(..., description="True to enable, False to disable")


class DeliberationRequest(BaseModel):
    title: str
    description: str = ""
    change_type: str = "local_change"
    module_id: str = ""
    risk_level: str = "low"
    cost_delta_usd: float = 0.0
    monthly_cost_delta_usd: float = 0.0
    vps_workers: int = 0
    production_deploy: bool = False
    external_action: bool = False
    final_action: bool = False
    legal_or_financial_action: bool = False
    affects_source_of_truth: bool = False
    affects_masterplan: bool = False
    affects_architecture: bool = False
    force_tie: bool = False


RISKY_GATE_FIELDS = {
    "production_deploy",
    "external_action",
    "final_action",
    "legal_or_financial_action",
    "affects_source_of_truth",
    "affects_masterplan",
    "affects_architecture",
}

VALID_OUTPUT_VERDICTS = {"approve", "conditional", "reject"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_store():
    from sylion.project_mode.store import get_project_mode_store

    return get_project_mode_store()


def _serialize_member(m: CouncilMember) -> dict[str, Any]:
    return {
        "member_id": m.member_id,
        "project_id": m.project_id,
        "member_role": m.member_role,
        "provider": m.provider,
        "model_id": m.model_id,
        "voting_weight": m.voting_weight,
        "active": m.active,
        "config": m.config,
    }


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _canonical_role(role: str) -> str:
    role = str(role or "").strip()
    if role in VALID_ROLES:
        return role
    aliases = {
        "adversarial": "adversarial_critic",
        "adversarial critic": "adversarial_critic",
        "red_team_critic": "adversarial_critic",
        "red-team critic": "adversarial_critic",
        "cost": "cost_sentinel",
        "security": "security_sentinel",
        "sentinel": "governance",
        "reviewer": "verifier",
        "domain_expert": "domain_specialist",
    }
    return aliases.get(role, "domain_specialist")


def _rank(member: CouncilMember) -> str:
    return str((member.config or {}).get("rank") or "primary")


def _risk_flags(body: DeliberationRequest) -> list[str]:
    flags = [name for name in sorted(RISKY_GATE_FIELDS) if bool(getattr(body, name))]
    if float(body.cost_delta_usd or 0) > 25:
        flags.append("cost_delta_gt_25_usd")
    if float(body.monthly_cost_delta_usd or 0) > 100:
        flags.append("monthly_cost_delta_gt_100_usd")
    if int(body.vps_workers or 0) > 3:
        flags.append("vps_workers_gt_3")
    if str(body.risk_level or "").lower() in {"high", "critical"}:
        flags.append(f"risk_level_{body.risk_level.lower()}")
    return flags


def _decision_class(body: DeliberationRequest, flags: list[str]) -> str:
    if body.production_deploy or body.final_action or body.legal_or_financial_action:
        return "D5"
    if body.affects_source_of_truth or body.affects_masterplan or body.affects_architecture:
        return "D4"
    if body.external_action or body.monthly_cost_delta_usd > 100 or body.vps_workers > 3:
        return "D4"
    if body.cost_delta_usd > 25 or flags:
        return "D3"
    return "D1"


def _gate_type(body: DeliberationRequest, flags: list[str]) -> str:
    if body.production_deploy:
        return "production"
    if body.final_action:
        return "final"
    if body.legal_or_financial_action:
        return "legal"
    if body.cost_delta_usd > 25 or body.monthly_cost_delta_usd > 100:
        return "financial"
    if body.external_action:
        return "external_action"
    if body.affects_source_of_truth or body.affects_masterplan or body.affects_architecture:
        return "blocking"
    if body.vps_workers > 3:
        return "financial"
    if flags:
        return "blocking"
    return "non_blocking"


def _proposal_verdict(member: CouncilMember, body: DeliberationRequest, flags: list[str], index: int) -> str:
    role = _canonical_role(member.member_role)
    if body.force_tie:
        return "approve" if index % 2 == 0 else "reject"
    if not flags:
        return "approve"
    if role in {"critic", "adversarial_critic", "governance", "cost_sentinel", "security_sentinel"}:
        return "conditional"
    if role == "verifier" and (body.production_deploy or body.affects_architecture):
        return "conditional"
    return "approve"


def _analysis_text(member: CouncilMember, body: DeliberationRequest, flags: list[str]) -> str:
    role = _canonical_role(member.member_role)
    if role == "adversarial_critic":
        if not flags:
            return f"{role} zatwierdza lokalna zmiane niskiego ryzyka po zakwestionowaniu zalozen: {body.title}"
        return (
            f"{role} bezlitosnie kwestionuje propozycje '{body.title}'. "
            f"Flagi ryzyka: {', '.join(flags)}. Wymagana jest akceptacja HumanGate, "
            "bo zalozenia, koszt, runtime albo Source of Truth moga byc bledne."
        )
    if not flags:
        return f"{role} akceptuje lokalną zmianę niskiego ryzyka: {body.title}"
    return (
        f"{role} przeanalizował zmianę '{body.title}'. Flagi ryzyka: "
        f"{', '.join(flags)}. Przed wykonaniem wymagana jest akceptacja HumanGate."
    )


def _normalize_verdict(value: Any) -> str:
    verdict = str(value or "").strip().lower()
    aliases = {
        "approved": "approve",
        "pass": "approve",
        "ok": "approve",
        "needs_changes": "conditional",
        "needs_info": "conditional",
        "block": "reject",
        "blocked": "reject",
        "rejected": "reject",
    }
    verdict = aliases.get(verdict, verdict)
    return verdict if verdict in VALID_OUTPUT_VERDICTS else "conditional"


def _member_prompt(
    *,
    project: dict[str, Any],
    member: CouncilMember,
    body: DeliberationRequest,
    flags: list[str],
    decision_class: str,
    gate_type: str,
    session_context: dict[str, Any],
) -> str:
    role = _canonical_role(member.member_role)
    context = {
        "project": {
            "project_id": project.get("project_id"),
            "title": project.get("title"),
            "kind": project.get("project_kind"),
            "phase": project.get("phase"),
            "status": project.get("status"),
            "canonical_book_excerpt": str(project.get("canonical_book") or "")[:2400],
            "masterplan_excerpt": str(project.get("masterplan") or "")[:2400],
        },
        "change": _model_dump(body),
        "risk_flags": flags,
        "decision_class": decision_class,
        "gate_type": gate_type,
        "session_context": session_context,
    }
    return (
        f"ROLA SYSTEMOWA: członek Rady AEIS '{role}'.\n"
        f"RANGA: {_rank(member)}. WAGA_GŁOSU: {float(member.voting_weight or 1.0)}.\n"
        "ZADANIE: Oceń proponowaną zmianę projektu. Bądź rygorystyczny: wykryj dryf zakresu, "
        "brakujące bramki, ryzyka bezpieczeństwa/kosztów/prawne, obowiązki testowe oraz to, "
        "czy zmiana może iść dalej. Odpowiadaj po polsku; nie używaj angielskich uzasadnień.\n\n"
        f"JSON KONTEKSTU:\n{json.dumps(context, ensure_ascii=False, sort_keys=True)}\n\n"
        "Zwróć WYŁĄCZNIE jeden obiekt JSON o dokładnie takim kształcie:\n"
        "{\n"
        '  "verdict": "approve|conditional|reject",\n'
        '  "confidence": 0.0,\n'
        '  "reasoning": "krótkie konkretne uzasadnienie po polsku",\n'
        '  "dissents": ["brakujące wymaganie albo sprzeciw po polsku"],\n'
        '  "sentinel_blocks": ["cost|security|legal|none"]\n'
        "}\n"
    )


def _run_member_llm_analysis(
    *,
    project: dict[str, Any],
    member: CouncilMember,
    body: DeliberationRequest,
    flags: list[str],
    decision_class: str,
    gate_type: str,
    session_context: dict[str, Any],
) -> dict[str, Any]:
    role = _canonical_role(member.member_role)
    model_id = member.model_id or member.member_id or role
    prompt = _member_prompt(
        project=project,
        member=member,
        body=body,
        flags=flags,
        decision_class=decision_class,
        gate_type=gate_type,
        session_context=session_context,
    )
    max_tokens = int((member.config or {}).get("max_tokens") or 700)
    try:
        result = call_llm(
            prompt,
            provider=member.provider or "",
            model=model_id,
            role=role,
            max_tokens=max(256, min(max_tokens, 1200)),
        )
    except LLMUnavailable as exc:
        return {
            "model_id": model_id,
            "role": role,
            "verdict": "conditional",
            "confidence": 0.0,
            "analysis_text": (
                f"REAL_LLM_NIEDOSTEPNY dla roli={role}, model={model_id}. "
                f"Wymagana akceptacja HumanGate. Błąd: {str(exc)[:500]}"
            ),
            "rationale": "Nie udało się wywołać realnego modelu; nie wolno automatycznie akceptować.",
            "source": "llm_unavailable",
            "llm": {"ok": False, "error": str(exc)[:500], "model_requested": model_id, "provider_requested": member.provider or ""},
            "sentinel_blocks": [],
        }

    parsed = extract_json_object(result.text)
    if not parsed:
        verdict = "conditional"
        confidence = 0.35
        reasoning = "Model nie zwrócił wymaganego kontraktu JSON; wymagana jest kontrola HumanGate."
        dissents = ["invalid_json_contract"]
        sentinel_blocks = []
    else:
        verdict = _normalize_verdict(parsed.get("verdict"))
        try:
            confidence = float(parsed.get("confidence", 0.7) or 0.7)
        except (TypeError, ValueError):
            confidence = 0.7
        confidence = max(0.0, min(confidence, 1.0))
        reasoning = str(parsed.get("reasoning") or parsed.get("rationale") or "").strip()
        dissents = parsed.get("dissents") if isinstance(parsed.get("dissents"), list) else []
        sentinel_blocks = parsed.get("sentinel_blocks") if isinstance(parsed.get("sentinel_blocks"), list) else []

    analysis_parts = [
        f"source=real_llm provider={result.provider} model={result.model} latency_ms={result.latency_ms}",
        f"reasoning={reasoning or result.text[:900]}",
    ]
    if dissents:
        analysis_parts.append("dissents=" + "; ".join(str(item) for item in dissents[:6]))
    if sentinel_blocks:
        analysis_parts.append("sentinel_blocks=" + "; ".join(str(item) for item in sentinel_blocks[:6]))
    return {
        "model_id": model_id,
        "role": role,
        "verdict": verdict,
        "confidence": confidence,
        "analysis_text": "\n".join(analysis_parts),
        "rationale": reasoning or "Realna analiza modelu w Radzie.",
        "source": "real_llm",
        "llm": result.to_dict(),
        "sentinel_blocks": [str(item) for item in sentinel_blocks],
    }


def _existing_council_ticket(project_id: str, session_id: str) -> str:
    for ticket in fetch_pending(origin="council", project_id=project_id):
        payload = ticket.payload or {}
        if payload.get("council_session_id") == session_id:
            return ticket.ticket_id
    return ""


def _orchestration_council_policy(project: dict[str, Any]) -> dict[str, Any]:
    fallback_quorum = (project.get("council_plan") or {}).get("quorum_policy") or {}
    try:
        from sylion.aeis.advisor.orchestration_config.service import get_orchestration_service

        rules = get_orchestration_service().get_council_rules()
        return {
            "source": "orchestration_config",
            "quorum_min": rules.quorum_min,
            "quorum_type": rules.quorum_type,
            "critic_gate_enabled": rules.critic_gate_enabled,
            "critic_gate_threshold": rules.critic_gate_threshold,
            "minimum_weight_ratio": float(rules.critic_gate_threshold),
            "sentinel_requirements": [item.__dict__ for item in rules.sentinel_requirements],
        }
    except Exception:
        return {
            "source": "project_council_plan",
            "quorum_min": int(fallback_quorum.get("minimum_members") or 0),
            "quorum_type": fallback_quorum.get("type") or "project_default",
            "critic_gate_enabled": True,
            "critic_gate_threshold": float(fallback_quorum.get("minimum_weight_ratio") or 0.6),
            "minimum_weight_ratio": float(fallback_quorum.get("minimum_weight_ratio") or 0.6),
            "sentinel_requirements": [],
        }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{project_id}/state", response_model=CouncilStateResponse)
def get_council_state(project_id: str) -> CouncilStateResponse:
    """Return the full council truth-plane view for a project."""
    store = _project_store()
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"project '{project_id}' not found")

    registry = get_model_registry()
    enabled = registry.is_enabled(project_id)
    members = registry.get_active_members(project_id)
    hierarchy = registry.get_decision_hierarchy(project_id)
    plan = project.get("council_plan") or {}
    active_size = int(plan.get("active_size", plan.get("suggested_size", 0) or 0))
    if not enabled:
        # Disabled => no active members; active_size view collapses to 0.
        active_size = 0

    return CouncilStateResponse(
        project_id=project_id,
        enabled=enabled,
        active_size=active_size,
        members=[_serialize_member(m) for m in members],
        decision_hierarchy=hierarchy,
    )


@router.post("/{project_id}/reconcile", response_model=CouncilStateResponse)
def reconcile_council(project_id: str) -> CouncilStateResponse:
    """Re-derive council_members from council_plan to enforce consistency.

    After reconcile:
      - count of active members == active_size (when enabled)
      - all members inactive (when disabled)
    """
    store = _project_store()
    try:
        store.reconcile_council(project_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"project '{project_id}' not found")

    return get_council_state(project_id)


@router.post("/{project_id}/enable", response_model=CouncilStateResponse)
def set_council_enabled(project_id: str, body: EnableRequest) -> CouncilStateResponse:
    """Toggle council enabled state and re-derive members."""
    store = _project_store()
    try:
        store.set_council_enabled(project_id, body.enabled)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"project '{project_id}' not found")

    return get_council_state(project_id)


@router.post("/{project_id}/deliberate")
def deliberate_project_change(project_id: str, body: DeliberationRequest):
    """Run project-scoped model-council deliberation for a proposed change.

    This is the runtime bridge between the project council roster and Human
    Gate. It does not execute the change. It opens a weighted council session,
    records role-based analyses, computes consensus, and creates a council
    governance ticket when the change touches cost, production, external
    actions, canon/masterplan, architecture, or a forced tie.
    """
    store = _project_store()
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"project '{project_id}' not found")

    registry = get_model_registry()
    if not registry.is_enabled(project_id):
        ticket_id = submit(GovernanceTicket(
            origin="council",
            project_id=project_id,
            decision_class="D3",
            gate_type="blocking",
            priority="P1",
            title=f"Rada wyłączona dla zmiany: {body.title}",
            summary="Rada projektu jest wyłączona, więc operator musi ręcznie przejrzeć tę zmianę.",
            payload={
                "action": "project_change_review",
                "reason": "council_disabled",
                "proposal": _model_dump(body),
            },
            requested_by="project_council",
        ))
        store.add_event(project_id, "project.council.deliberation.blocked", {
            "ticket_id": ticket_id,
            "reason": "council_disabled",
            "title": body.title,
        })
        return {
            "project_id": project_id,
            "status": "requires_human_gate",
            "reason": "council_disabled",
            "human_gate_ticket_id": ticket_id,
            "consensus": None,
            "session": None,
        }

    members = registry.get_active_members(project_id)
    if not members:
        try:
            store.reconcile_council(project_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"project '{project_id}' not found")
        members = registry.get_active_members(project_id)
    if not members:
        raise HTTPException(status_code=409, detail="project has no active council members")

    flags = _risk_flags(body)
    decision_class = _decision_class(body, flags)
    gate_type = _gate_type(body, flags)
    council_policy = _orchestration_council_policy(project)
    topic = f"{project.get('title', project_id)} :: {body.title}"
    session_context = {
        "project_id": project_id,
        "project_kind": project.get("project_kind", ""),
        "change": _model_dump(body),
        "risk_flags": flags,
        "quorum_policy": council_policy,
    }

    council = get_council_hybrid(db_path=getattr(store, "db_path", None))
    session = council.open_session(
        topic=topic,
        models=[member.model_id or member.member_id for member in members],
        context=str(session_context),
        moderator_model="project_council_orchestrator",
    )

    participants: dict[int, dict[str, Any]] = {}
    for index, member in enumerate(members):
        role = _canonical_role(member.member_role)
        rank = _rank(member)
        model_id = member.model_id or member.member_id or f"{role}-{index}"
        participants[index] = council.add_participant(
            session["session_id"],
            model_id=model_id,
            role=role,
            rank=rank if rank in {"primary", "senior", "support", "review_only", "validation_only"} else "primary",
            weight=float(member.voting_weight or 1.0),
        )

    analysis_payloads: list[dict[str, Any] | None] = [None for _ in members]
    with ThreadPoolExecutor(max_workers=max(1, min(len(members), 6))) as pool:
        future_to_index = {
            pool.submit(
                _run_member_llm_analysis,
                project=project,
                member=member,
                body=body,
                flags=flags,
                decision_class=decision_class,
                gate_type=gate_type,
                session_context=session_context,
            ): index
            for index, member in enumerate(members)
        }
        try:
            for future in as_completed(future_to_index, timeout=120):
                index = future_to_index[future]
                try:
                    analysis_payloads[index] = future.result()
                except Exception as exc:  # noqa: BLE001
                    member = members[index]
                    role = _canonical_role(member.member_role)
                    model_id = member.model_id or member.member_id or f"{role}-{index}"
                    analysis_payloads[index] = {
                        "model_id": model_id,
                        "role": role,
                        "verdict": "conditional",
                        "confidence": 0.0,
                        "analysis_text": f"REAL_LLM_BLAD role={role} model={model_id}: {type(exc).__name__}: {str(exc)[:500]}",
                        "rationale": "Nie udało się wywołać realnego modelu; wymagana jest akceptacja HumanGate.",
                        "source": "llm_error",
                        "llm": {"ok": False, "error": str(exc)[:500], "model_requested": model_id, "provider_requested": member.provider or ""},
                        "sentinel_blocks": [],
                    }
        except FuturesTimeoutError:
            for index, item in enumerate(analysis_payloads):
                if item is not None:
                    continue
                member = members[index]
                role = _canonical_role(member.member_role)
                model_id = member.model_id or member.member_id or f"{role}-{index}"
                analysis_payloads[index] = {
                    "model_id": model_id,
                    "role": role,
                    "verdict": "conditional",
                    "confidence": 0.0,
                    "analysis_text": f"REAL_LLM_TIMEOUT role={role} model={model_id}. Wymagana akceptacja HumanGate.",
                    "rationale": "Timeout realnego modelu; wymagana jest akceptacja HumanGate.",
                    "source": "llm_timeout",
                    "llm": {"ok": False, "error": "timeout", "model_requested": model_id, "provider_requested": member.provider or ""},
                    "sentinel_blocks": [],
                }

    analyses: list[dict[str, Any]] = []
    critic_signature = None
    analysis_failures: list[dict[str, Any]] = []
    for index, member in enumerate(members):
        payload = analysis_payloads[index] or {}
        role = _canonical_role(member.member_role)
        if body.force_tie:
            payload["verdict"] = "approve" if index % 2 == 0 else "reject"
            payload["analysis_text"] = str(payload.get("analysis_text") or "") + "\nforce_tie test override applied"
        analysis = council.add_analysis(
            session["session_id"],
            model_id=str(payload.get("model_id") or member.model_id or member.member_id or f"{role}-{index}"),
            analysis_text=str(payload.get("analysis_text") or ""),
            verdict=_normalize_verdict(payload.get("verdict")),
            confidence=float(payload.get("confidence") or 0.0),
            rationale=str(payload.get("rationale") or ""),
        )
        analysis["participant"] = participants.get(index)
        analysis["source"] = payload.get("source")
        analysis["llm"] = payload.get("llm") or {}
        analysis["sentinel_blocks"] = payload.get("sentinel_blocks") or []
        analyses.append(analysis)
        llm_info = payload.get("llm") if isinstance(payload.get("llm"), dict) else {}
        if payload.get("source") != "real_llm" or not bool(llm_info.get("ok", payload.get("source") == "real_llm")):
            analysis_failures.append({
                "role": role,
                "model_id": payload.get("model_id") or member.model_id,
                "source": payload.get("source"),
                "error": llm_info.get("error", ""),
            })
        try:
            if project_id and isinstance(llm_info, dict) and llm_info.get("ok"):
                store.record_cost(
                    project_id,
                    str(llm_info.get("provider") or ""),
                    str(llm_info.get("model") or ""),
                    int(llm_info.get("prompt_tokens") or 0),
                    int(llm_info.get("completion_tokens") or 0),
                    float(llm_info.get("estimated_cost_usd") or 0.0),
                )
        except Exception:
            log.warning("failed to record council LLM cost project=%s", project_id, exc_info=True)
        if role in {"critic", "adversarial_critic"} and payload.get("source") == "real_llm" and _normalize_verdict(payload.get("verdict")) in {"approve", "conditional", "reject"}:
            critic_signature = council.record_critic_signature(
                session["session_id"],
                model_id=str(payload.get("model_id") or member.model_id or member.member_id),
                signed_decision=_normalize_verdict(payload.get("verdict")),
                rationale=str(payload.get("rationale") or "Krytyk przeanalizował decyzję realnym modelem."),
            )

    if body.cost_delta_usd > 25 or body.monthly_cost_delta_usd > 100:
        sentinel_model = next((m.model_id or m.member_id for m in members if _canonical_role(m.member_role) in {"cost_sentinel", "governance"}), members[0].model_id or members[0].member_id)
        council.record_sentinel_evaluation(
            session["session_id"],
            sentinel_role="cost_sentinel",
            model_id=sentinel_model,
            verdict="warn",
            score=max(float(body.cost_delta_usd or 0), float(body.monthly_cost_delta_usd or 0)),
            details="Próg kosztowy wymaga akceptacji HumanGate.",
        )
    if body.production_deploy or body.external_action or body.legal_or_financial_action:
        sentinel_model = next((m.model_id or m.member_id for m in members if _canonical_role(m.member_role) in {"security_sentinel", "governance"}), members[0].model_id or members[0].member_id)
        council.record_sentinel_evaluation(
            session["session_id"],
            sentinel_role="security_sentinel",
            model_id=sentinel_model,
            verdict="warn",
            score=1.0,
            details="Akcja zewnętrzna, produkcyjna albo prawna wymaga jawnej akceptacji operatora.",
        )

    consensus = council.compute_weighted_consensus(session["session_id"])
    quorum = council_policy
    minimum_ratio = float(quorum.get("minimum_weight_ratio") or 0.6)
    winning = consensus["weights"].get(consensus["verdict"], 0.0)
    ratio = round(winning / (consensus["total_weight"] or 1.0), 4)
    quorum_met = len(members) >= int(quorum.get("quorum_min") or 0)
    critic_gate_missing = bool(quorum.get("critic_gate_enabled", True)) and not consensus.get("critic_signed")
    requires_gate = bool(
        flags
        or analysis_failures
        or body.force_tie
        or consensus["verdict"] in {"tie", "reject", "no_data"}
        or critic_gate_missing
        or not quorum_met
        or ratio < minimum_ratio
    )

    status = "requires_human_gate" if requires_gate else "auto_approved"
    ticket_id = ""
    if requires_gate:
        priority = "P0" if decision_class == "D5" else "P1" if decision_class == "D4" else "P2"
        ticket_id = _existing_council_ticket(project_id, session["session_id"])
        if not ticket_id:
            ticket_id = submit(GovernanceTicket(
                origin="council",
                project_id=project_id,
                decision_class=decision_class,
                gate_type=gate_type,
                priority=priority,
                title=f"Przegląd propozycji zmiany przez Radę: {body.title}",
                summary=(
                    "Rada modeli wymaga akceptacji HumanGate przed wykonaniem tej zmiany. "
                    f"Konsensus={consensus['verdict']} ratio={ratio}; flagi={', '.join(flags) or 'brak'}."
                ),
                payload={
                    "action": "project_change_review",
                    "council_session_id": session["session_id"],
                    "proposal": _model_dump(body),
                    "risk_flags": flags,
                    "analysis_failures": analysis_failures,
                    "consensus": consensus,
                    "quorum_policy": quorum,
                    "quorum_met": quorum_met,
                },
                requested_by="project_council",
            ))

    consolidated_text = (
        f"Decyzja: {status}. Konsensus={consensus['verdict']} ratio={ratio}. "
        f"Ticket HumanGate={ticket_id or 'brak'}."
    )
    try:
        council.consolidate_with_signatures(
            session["session_id"],
            consolidated_text,
            require_critic=True,
            require_sentinels_pass=False,
        )
    except ValueError:
        council.set_consolidated(session["session_id"], consolidated_text, ratio)

    event_type = "project.council.deliberation.requires_human_gate" if requires_gate else "project.council.deliberation.auto_approved"
    store.add_event(project_id, event_type, {
        "session_id": session["session_id"],
        "title": body.title,
        "status": status,
        "decision_class": decision_class,
        "gate_type": gate_type,
        "risk_flags": flags,
        "analysis_failures": analysis_failures,
        "consensus": consensus,
        "ratio": ratio,
        "quorum_policy": quorum,
        "quorum_met": quorum_met,
        "ticket_id": ticket_id,
        "occurred_at": time.time(),
    })

    return {
        "project_id": project_id,
        "status": status,
        "decision_class": decision_class,
        "gate_type": gate_type,
        "risk_flags": flags,
        "human_gate_ticket_id": ticket_id,
        "session": council.get_session_summary(session["session_id"]),
        "consensus": consensus,
        "consensus_ratio": ratio,
        "minimum_ratio": minimum_ratio,
        "quorum_policy": quorum,
        "quorum_met": quorum_met,
        "critic_signature": critic_signature,
        "analyses": analyses,
    }
