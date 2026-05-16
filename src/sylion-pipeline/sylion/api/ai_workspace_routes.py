"""
SYLION API -- AI Workspace routes.

Endpoints for: chat sessions, messages, file uploads, hybrid council,
settings (API keys, model hierarchy, council members), prompt templates,
and book generation.
"""

import json
import time
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Any, Optional

router = APIRouter(prefix="/api/v1/workspace", tags=["ai_workspace"])


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "workspace",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: str
    model_ids: list[str] = []
    system_prompt: str = ""
    team_id: str = ""
    project_id: str = ""

class SendMessageRequest(BaseModel):
    role: str = "user"
    content: str
    model_id: str = ""
    attachments: list[str] = []
    parent_message_id: str = ""

class OpenCouncilRequest(BaseModel):
    topic: str
    description: str = ""
    model_ids: list[str]

class DiscussRequest(BaseModel):
    rounds_per_model: int = 2

class AddParticipantRequest(BaseModel):
    model_id: str
    role: str
    rank: str = "primary"
    weight: float | None = None

class CriticSignatureRequest(BaseModel):
    model_id: str
    signed_decision: str
    rationale: str = ""

class SentinelEvaluationRequest(BaseModel):
    sentinel_role: str
    model_id: str
    verdict: str
    score: float = 0.0
    details: str = ""

class ConsolidateWithGatesRequest(BaseModel):
    consolidated_text: str
    require_critic: bool = True
    require_sentinels_pass: bool = True

class StoreKeyRequest(BaseModel):
    provider: str
    encrypted_key: str
    display_name: str | None = None
    metadata: dict | None = None

class SaveHierarchyRequest(BaseModel):
    name: str
    levels: list[dict]

class UpdateHierarchyRequest(BaseModel):
    name: str | None = None
    levels: list[dict] | None = None
    is_active: bool | None = None

class AutoArrangeCouncilRequest(BaseModel):
    force: bool = False
    max_members: int = 7
    activate_hierarchy: bool = True

class ConfigureMemberRequest(BaseModel):
    member_id: str
    model_id: str
    role: str = "analyst"
    priority: int = 0
    system_prompt: str | None = None
    rank: str = "primary"
    voting_weight: float = 1.0
    specialization: str = ""
    max_tokens: int = 0

class CreatePromptRequest(BaseModel):
    name: str
    category: str
    content: str
    team_id: str = ""
    project_id: str = ""

class CreateBookRequest(BaseModel):
    title: str
    description: str = ""
    team_id: str = ""
    project_id: str = ""

class GenerateFromChatRequest(BaseModel):
    session_ids: list[str]
    chapter_structure: str = ""

class GenerateFromCouncilRequest(BaseModel):
    council_session_ids: list[str]

class SubmitIdeaRequest(BaseModel):
    content: str
    category: str = ""
    priority: str | int = "normal"
    source: str = "manual"
    tags: list[str] = []

class UpdateIdeaRequest(BaseModel):
    content: str | None = None
    category: str | None = None
    priority: str | int | None = None
    tags: list[str] | None = None

class ImportLocalIdeaAttachmentRequest(BaseModel):
    file_path: str
    idea_id: str = ""


# F-032: idea -> project promotion (generic, non-funding-specific)
class PromoteIdeaRequest(BaseModel):
    project_name: str = ""           # optional rename; falls back to idea title
    constraints: str = ""
    preferred_stack: list[str] = []
    attachments: list[dict] = []
    auto_execute: bool = False
    owner_id: str = "workspace-default"
    team_id: str = ""

# F-032: idea-level discussion (mini council/chat) BEFORE promotion to project
class IdeaDiscussRequest(BaseModel):
    prompt: str = ""                  # user's question/angle to debate
    model_ids: list[str] = []         # which models to engage (defaults to advisor pick)
    rounds: int = 1                   # number of discussion rounds


# ---------------------------------------------------------------------------
# Lazy subsystem accessors
# ---------------------------------------------------------------------------

_chat_engine = None
def _get_chat():
    global _chat_engine
    if _chat_engine is not None:
        return _chat_engine
    from sylion.cognitive.chat_engine import get_chat_engine
    from sylion.core.event_bus import get_event_bus
    _chat_engine = get_chat_engine(event_bus=get_event_bus())
    return _chat_engine

_council = None
def _get_council():
    global _council
    if _council is not None:
        return _council
    from sylion.governance.council_hybrid import get_council_hybrid
    from sylion.core.event_bus import get_event_bus
    from sylion.aeis_v2.audit_profile import resolve_db_path

    _council = get_council_hybrid(
        db_path=resolve_db_path("sylion_aeis.db"),
        event_bus=get_event_bus(),
    )
    return _council

_vault = None
def _get_vault():
    global _vault
    if _vault is not None:
        return _vault
    from sylion.security.key_vault import get_key_vault
    from sylion.core.event_bus import get_event_bus
    _vault = get_key_vault(event_bus=get_event_bus())
    return _vault

_registry = None
def _get_registry():
    global _registry
    if _registry is not None:
        return _registry
    from sylion.cognitive.model_registry import get_model_registry
    from sylion.core.event_bus import get_event_bus
    _registry = get_model_registry(event_bus=get_event_bus())
    return _registry

_prompts = None
def _get_prompts():
    global _prompts
    if _prompts is not None:
        return _prompts
    from sylion.cognitive.prompt_templates import get_prompt_template_manager
    from sylion.core.event_bus import get_event_bus
    _prompts = get_prompt_template_manager(event_bus=get_event_bus())
    return _prompts

_books = None
_workspace_state_conn = None
_workspace_state_loaded = False
_project_store = None
_workspace_notifications = []
_project_kickoffs = []
_hg_workflows = []
_project_launch_futures = []


def _default_discussion_model_ids(limit: int = 4) -> list[str]:
    model_ids: list[str] = []
    try:
        for member in _get_vault().list_council_members():
            model_id = str(member.get("model_id") or "").strip()
            if model_id and model_id not in model_ids:
                model_ids.append(model_id)
            if len(model_ids) >= limit:
                return model_ids
    except Exception:
        pass
    try:
        from sylion.cognitive.model_registry import get_model_registry

        preferred = ["gpt-4o-mini", "claude-haiku-4-5", "glm-4-plus", "sonar", "qwen2.5:7b-instruct"]
        available = {str(item.get("model_id") or "") for item in get_model_registry().list_models()}
        for model_id in preferred:
            if model_id in available and model_id not in model_ids:
                model_ids.append(model_id)
            if len(model_ids) >= limit:
                return model_ids
    except Exception:
        pass
    return model_ids or ["gpt-4o-mini", "claude-haiku-4-5"]


def _idea_discussion_prompt(
    *,
    title: str,
    idea_text: str,
    user_prompt: str,
    model_id: str,
    round_no: int,
    prior_round: list[str],
) -> str:
    prior = "\n\n".join(prior_round[-6:])
    return (
        "ROLA SYSTEMOWA: uczestnik Rady AEIS oceniajacej pomysl przed projektem.\n"
        "JEZYK: odpowiedz wylacznie po polsku. Nie tlumacz nazw modeli, API ani nazw wlasnych.\n"
        f"MODEL WYWOLYWANY: {model_id}\n"
        f"RUNDA: {round_no}\n"
        "ZADANIE: omow pomysl jak realny czlonek rady przedprojektowej. Badz konkretny: "
        "wskaz braki wejscia, ryzyka, wymagane HumanGate, potrzebne skills, routing modeli "
        "oraz decyzje, czy pomysl promowac do projektu.\n\n"
        f"TYTUL POMYSLU: {title}\n"
        f"OPIS POMYSLU:\n{idea_text}\n\n"
        f"PYTANIE OPERATORA:\n{user_prompt}\n\n"
        f"FRAGMENTY POPRZEDNIEJ RUNDY:\n{prior or '(brak)'}\n\n"
        "Zwroc zwiezla odpowiedz z sekcjami: WERDYKT, BRAKUJACE_PYTANIA, RYZYKA, "
        "PROPONOWANY_STACK, POTRZEBNE_SKILLS, HUMANGATE, NASTEPNY_KROK_OPERATORA."
    )


def _run_idea_model_discussion(
    *,
    title: str,
    idea_text: str,
    user_prompt: str,
    model_id: str,
    round_no: int,
    prior_round: list[str],
) -> dict[str, Any]:
    from sylion.cognitive.llm_runtime import LLMUnavailable, call_llm, infer_provider_for_model

    provider = infer_provider_for_model(model_id)
    prompt = _idea_discussion_prompt(
        title=title,
        idea_text=idea_text,
        user_prompt=user_prompt,
        model_id=model_id,
        round_no=round_no,
        prior_round=prior_round,
    )
    try:
        result = call_llm(
            prompt,
            provider=provider,
            model=model_id,
            role="planner" if round_no == 1 else "critic",
            max_tokens=700,
        )
    except LLMUnavailable as exc:
        return {
            "ok": False,
            "model_id": model_id,
            "provider_requested": provider,
            "error": str(exc)[:500],
            "content": f"REAL_LLM_UNAVAILABLE model={model_id}. Discussion cannot rely on this member. Error: {str(exc)[:500]}",
        }
    payload = result.to_dict()
    return {
        "ok": True,
        "model_id": model_id,
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "latency_ms": payload.get("latency_ms"),
        "prompt_tokens": payload.get("prompt_tokens"),
        "completion_tokens": payload.get("completion_tokens"),
        "estimated_cost_usd": payload.get("estimated_cost_usd"),
        "fallback_used": payload.get("fallback_used"),
        "content": payload.get("text") or "",
        "llm": payload,
    }


def _chat_response_prompt(*, session: dict[str, Any], messages: list[dict[str, Any]], user_text: str) -> str:
    history = []
    for message in messages[-12:]:
        role = str(message.get("role") or "message")
        content = str(message.get("content") or "").strip()
        if content:
            history.append(f"{role}: {content[:1200]}")
    return (
        "ROLA SYSTEMOWA: asystent roboczy AEIS w panelu Workspace/Czat.\n"
        "JEZYK: odpowiadaj po polsku.\n"
        "ZASADA: badz konkretny. Jesli operator pyta o stan systemu, oddziel fakty runtime od wnioskow.\n"
        f"TYTUL SESJI: {session.get('title') or 'Workspace chat'}\n"
        f"SYSTEM PROMPT SESJI: {session.get('system_prompt') or ''}\n\n"
        "HISTORIA:\n"
        + ("\n".join(history) if history else "- brak")
        + "\n\n"
        f"WIADOMOSC OPERATORA:\n{user_text}\n\n"
        "ODPOWIEDZ:"
    )


def _resolve_chat_model(session: dict[str, Any], requested_model: str = "") -> str:
    if str(requested_model or "").strip():
        return str(requested_model).strip()
    session_models = [
        item.strip()
        for item in str(session.get("model_id") or "").split(",")
        if item.strip()
    ]
    if session_models:
        return session_models[0]
    return _default_discussion_model_ids(limit=1)[0]


def _append_chat_assistant_response(
    *,
    chat: Any,
    session_id: str,
    user_text: str,
    requested_model: str = "",
) -> dict[str, Any]:
    session = chat.get_session(session_id) or {}
    prior_messages = chat.list_messages(session_id, limit=20)
    model_id = _resolve_chat_model(session, requested_model)
    try:
        from sylion.cognitive.llm_runtime import LLMUnavailable, call_llm, infer_provider_for_model

        provider = infer_provider_for_model(model_id)
        result = call_llm(
            _chat_response_prompt(session=session, messages=prior_messages, user_text=user_text),
            provider=provider,
            model=model_id,
            role="planner",
            max_tokens=500,
        )
        payload = result.to_dict()
        return chat.send_message(
            session_id=session_id,
            role="assistant",
            content=result.text or "(model nie zwrocil tresci)",
            model_id=str(payload.get("model") or model_id),
            metadata={
                "source": "real_llm",
                "provider": payload.get("provider", ""),
                "model": payload.get("model", model_id),
                "latency_ms": payload.get("latency_ms", 0),
                "prompt_tokens": payload.get("prompt_tokens", 0),
                "completion_tokens": payload.get("completion_tokens", 0),
                "estimated_cost_usd": payload.get("estimated_cost_usd", 0.0),
                "fallback_used": bool(payload.get("fallback_used")),
            },
        )
    except LLMUnavailable as exc:
        return chat.send_message(
            session_id=session_id,
            role="assistant",
            content=f"REAL_LLM_UNAVAILABLE model={model_id}: {str(exc)[:500]}",
            model_id=model_id,
            metadata={"source": "llm_error", "error": str(exc)[:500]},
        )
    except Exception as exc:  # noqa: BLE001
        return chat.send_message(
            session_id=session_id,
            role="assistant",
            content=f"REAL_LLM_CALL_ERROR model={model_id}: {type(exc).__name__}: {str(exc)[:500]}",
            model_id=model_id,
            metadata={"source": "llm_error", "error": f"{type(exc).__name__}: {str(exc)[:500]}"},
        )


def _workspace_council_members(session_id: str) -> list[dict[str, Any]]:
    council = _get_council()
    session = council.get_session(session_id)
    if not session:
        raise HTTPException(404, "Council session not found")
    participants = council.list_participants(session_id)
    if participants:
        return participants
    models = session.get("models") or []
    return [
        {
            "participant_id": f"{session_id}:model:{index}",
            "session_id": session_id,
            "model_id": str(model_id),
            "role": "planner" if index == 0 else "critic" if index == 1 else "verifier",
            "rank": "primary" if index < 2 else "support",
            "weight": 1.0 if index < 2 else 0.7,
        }
        for index, model_id in enumerate(models)
        if str(model_id or "").strip()
    ]


def _workspace_council_analysis_is_usable(analysis: dict[str, Any]) -> bool:
    text = f"{analysis.get('analysis_text') or ''}\n{analysis.get('rationale') or ''}"
    if str(analysis.get("source") or "") == "llm_error":
        return False
    if "REAL_LLM_UNAVAILABLE" in text or "REAL_LLM_CALL_ERROR" in text:
        return False
    return bool(str(analysis.get("analysis_text") or analysis.get("rationale") or "").strip())


def _workspace_council_analysis_prompt(
    *,
    session: dict[str, Any],
    member: dict[str, Any],
) -> str:
    return (
        "ROLA SYSTEMOWA: czlonek Rady AEIS.\n"
        "JEZYK: odpowiedz po polsku, ale pola JSON zostaw po angielsku.\n"
        f"ROLA: {member.get('role')}  RANGA: {member.get('rank')}  WAGA: {member.get('weight')}\n"
        f"TEMAT: {session.get('topic')}\n"
        f"KONTEKST:\n{session.get('context') or '(brak)'}\n\n"
        "ZADANIE: wykonaj niezalezna analize decyzji, funkcjonalnosci i dolaczonych zalacznikow. "
        "Jezeli kontekst zawiera AEIS_ATTACHMENT_AUDIT_V2 albo sekcje zalacznikow, "
        "musisz traktowac raport plikow jako material zrodlowy: odwolaj sie do nazw plikow, "
        "katalogow, manifestu, preview tresci, pominiętych zaleznosci oraz luk pokrycia. "
        "Najpierw opisz do czego sluzy projekt i jak ma dzialac: dokumentacja, ekrany UI, API, workflow uzytkownika, "
        "moduly domenowe, integracje, testy, deploy i mozliwosc uruchomienia w sandboxie. Oddziel funkcje potwierdzone plikami/testami "
        "od funkcji tylko domniemanych z nazw katalogow. "
        "Nie wolno napisac ogolnej opinii bez project_purpose, how_it_works, documentation_findings, "
        "functional_inventory, runtime_deploy_assessment i file_observations. Jezeli digest jest niepelny, "
        "powiedz dokladnie czego brakuje i jakie lokalne kroki analizy sa wymagane.\n"
        "STANDARD JAKOSCI: zero ogolnikow. Kazdy istotny claim ma miec dowod plikowy, katalogowy, testowy "
        "albo jawna etykiete inferred/missing. Dla archiwum programu wskaz minimum 8 konkretnych obserwacji plikowych, "
        "minimum 5 funkcji/workflow, minimum 3 blokery runtime/test/deploy oraz minimum 3 pytania/decyzje dla operatora. "
        "Nie powtarzaj tylko 'brak pelnej analizy'; napisz co trzeba zbadac, po co i jakim bezpiecznym krokiem.\n"
        "Wskaz ryzyka, brakujace dane, guardy, HumanGate, propozycje kierunku i material do Ksiegi Source of Truth. Zwroc TYLKO JSON:\n"
        "{\"verdict\":\"approve|conditional|reject\",\"confidence\":0.0,"
        "\"reasoning\":\"konkretne uzasadnienie\","
        "\"attachment_coverage\":\"co dokladnie bylo widoczne z zalacznikow\","
        "\"project_purpose\":\"do czego sluzy projekt wedlug dokumentacji i kodu\","
        "\"how_it_works\":[\"warstwa albo workflow -> jak dziala i jaki plik to pokazuje\"],"
        "\"documentation_findings\":[\"dokumentacja/ADR/runbook/openapi -> co mowi o systemie\"],"
        "\"functional_inventory\":[\"funkcja lub workflow -> dowod w plikach\"],"
        "\"module_map\":[\"modul/domena -> odpowiedzialnosc -> dowod\"],"
        "\"evidence_matrix\":[{\"claim\":\"wniosek\",\"evidence\":[\"plik albo katalog\"],\"status\":\"confirmed|inferred|missing\"}],"
        "\"runtime_deploy_assessment\":[\"czy da sie uruchomic/testowac -> dowod, komenda, blocker\"],"
        "\"sandbox_test_plan\":[\"krok bezpiecznego uruchomienia/testu w sandboxie\"],"
        "\"runtime_blockers\":[\"brak env/dependency/service/test failure risk\"],"
        "\"implemented_vs_unclear\":[\"potwierdzone albo niepewne -> dlaczego\"],"
        "\"functionality_gaps\":[\"brak funkcjonalny albo brak dowodu\"],"
        "\"file_observations\":[\"konkret: plik/katalog -> wniosek\"],"
        "\"decision_options\":[\"wariant decyzji operatora -> plusy/minusy/warunki\"],"
        "\"council_questions\":[\"pytanie do operatora, ktore zmienia kierunek projektu\"],"
        "\"source_of_truth_candidates\":[\"fakt lub decyzja gotowa do Ksiegi, jesli operator potwierdzi\"],"
        "\"risks\":[\"...\"],\"missing_evidence\":[\"...\"],"
        "\"next_steps\":[\"...\"],\"dissents\":[\"...\"],"
        "\"sentinel_blocks\":[\"cost|security|legal|none\"]}"
    )


def _extract_workspace_json(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _workspace_council_analysis_digest(item: dict[str, Any], limit: int = 1800) -> str:
    text = str(item.get("analysis_text") or item.get("rationale") or "")
    parsed = _extract_workspace_json(text)
    if parsed:
        fields = [
            "reasoning",
            "project_purpose",
            "functional_inventory",
            "module_map",
            "evidence_matrix",
            "runtime_deploy_assessment",
            "runtime_blockers",
            "decision_options",
            "council_questions",
            "source_of_truth_candidates",
            "file_observations",
            "risks",
            "missing_evidence",
        ]
        chunks = [f"{field}: {parsed.get(field)}" for field in fields if parsed.get(field)]
        text = "\n".join(chunks) or text
    return text[:limit]


def _workspace_string_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                result.append(json.dumps(item, ensure_ascii=False))
            else:
                text = str(item or "").strip()
                if text:
                    result.append(text)
        return result
    text = str(value or "").strip()
    return [text] if text else []


def _workspace_council_discussion_prompt(
    *,
    session: dict[str, Any],
    member: dict[str, Any],
    analyses: list[dict[str, Any]],
    prior_discussion: list[dict[str, Any]],
) -> str:
    other_claims = []
    for item in analyses:
        if item.get("model_id") == member.get("model_id"):
            continue
        other_claims.append(
            f"- {item.get('model_id')} verdict={item.get('verdict')}: "
            f"{_workspace_council_analysis_digest(item)}"
        )
    prior = [
        f"- {item.get('model_id')}: {str(item.get('contribution') or '')[:900]}"
        for item in prior_discussion[-6:]
    ]
    return (
        "ROLA SYSTEMOWA: czlonek Rady AEIS w rundzie cross-review.\n"
        "JEZYK: polski.\n"
        f"ROLA: {member.get('role')}  MODEL: {member.get('model_id')}\n"
        f"TEMAT: {session.get('topic')}\n\n"
        "Wypowiedzi innych modeli do skrytykowania lub przyjecia:\n"
        + ("\n".join(other_claims) if other_claims else "- brak innych analiz")
        + "\n\nPoprzednia dyskusja:\n"
        + ("\n".join(prior) if prior else "- brak")
        + "\n\nZADANIE: odnieś sie konkretnie do minimum dwoch cudzych claimow, "
        "napisz co zmienia twoj werdykt i jakie guardy/HumanGate sa wymagane. "
        "Odpowiedz zwiezle, bez markdown. "
        "ALE nie moze to byc streszczenie. Wymagany format: "
        "1. Przyjmuje z analiz; 2. Kwestionuje; 3. Propozycje kierunku; "
        "4. Pytania do operatora; 5. Do Ksiegi Source of Truth; 6. Guardy/HumanGate. "
        "Odnies sie do minimum trzech cudzych claimow i dwoch dowodow plikowych. "
        "Jesli nie masz dowodu, napisz BRAK DOWODU i zaproponuj lokalny krok weryfikacji."
    )


def _call_workspace_council_model(
    prompt: str,
    member: dict[str, Any],
    role: str,
    max_tokens: int = 900,
) -> dict[str, Any]:
    from sylion.cognitive.llm_runtime import LLMUnavailable, call_llm, extract_json_object, infer_provider_for_model

    model_id = str(member.get("model_id") or "").strip()
    provider = infer_provider_for_model(model_id)
    try:
        result = call_llm(prompt, provider=provider, model=model_id, role=role, max_tokens=max_tokens)
    except LLMUnavailable as exc:
        return {
            "ok": False,
            "model_id": model_id,
            "provider": provider,
            "verdict": "conditional",
            "confidence": 0.0,
            "reasoning": f"REAL_LLM_UNAVAILABLE: {str(exc)[:500]}",
            "text": f"REAL_LLM_UNAVAILABLE model={model_id}: {str(exc)[:500]}",
            "llm": {"ok": False, "error": str(exc)[:500], "model_requested": model_id, "provider_requested": provider},
        }
    parsed = extract_json_object(result.text)
    return {
        "ok": True,
        "model_id": result.model or model_id,
        "provider": result.provider,
        "verdict": str(parsed.get("verdict") or "conditional").lower() if parsed else "conditional",
        "confidence": float(parsed.get("confidence", 0.7) or 0.7) if parsed else 0.45,
        "reasoning": str(parsed.get("reasoning") or result.text[:900]) if parsed else result.text[:900],
        "dissents": parsed.get("dissents", []) if isinstance(parsed, dict) else [],
        "sentinel_blocks": parsed.get("sentinel_blocks", []) if isinstance(parsed, dict) else [],
        "text": result.text,
        "llm": result.to_dict(),
    }


def _get_books():
    global _books
    if _books is not None:
        return _books
    from sylion.memory.book_generator import get_book_generator
    from sylion.core.event_bus import get_event_bus
    _books = get_book_generator(event_bus=get_event_bus())
    return _books


# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------

@router.post("/sessions")
async def create_session(body: CreateSessionRequest):
    chat = _get_chat()
    model_id = ",".join(body.model_ids) if body.model_ids else ""
    return chat.create_session(body.title, model_id, body.system_prompt)

@router.get("/sessions")
async def list_sessions(status: str = None, team_id: str = None, limit: int = 50):
    archived = (status == "archived") if status else False
    return {"sessions": _get_chat().list_sessions(archived=archived, limit=limit)}

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    result = _get_chat().get_session(session_id)
    if not result:
        raise HTTPException(404, "Session not found")
    return result

@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, body: SendMessageRequest):
    metadata = {}
    if body.attachments:
        metadata["attachments"] = body.attachments
    if body.parent_message_id:
        metadata["parent_message_id"] = body.parent_message_id
    chat = _get_chat()
    user_message = chat.send_message(session_id, body.role, body.content, body.model_id, metadata or None)
    if body.role == "user" and str(body.content or "").strip():
        user_message["assistant_message"] = _append_chat_assistant_response(
            chat=chat,
            session_id=session_id,
            user_text=body.content,
            requested_model=body.model_id,
        )
    return user_message

@router.get("/sessions/{session_id}/messages")
async def list_messages(session_id: str, limit: int = 100, before: str = None):
    return {"messages": _get_chat().list_messages(session_id, limit=limit)}

@router.post("/sessions/{session_id}/archive")
async def archive_session(session_id: str):
    return _get_chat().archive_session(session_id)

@router.post("/sessions/{session_id}/upload")
async def upload_file(session_id: str, file: UploadFile = File(...)):
    content = await file.read()
    result = _get_chat().upload_attachment(session_id, file.filename, file.content_type or "application/octet-stream", content)
    return result


# ---------------------------------------------------------------------------
# Council routes
# ---------------------------------------------------------------------------

@router.post("/council/sessions")
async def open_council(body: OpenCouncilRequest):
    return _get_council().open_session(body.topic, body.model_ids, context=body.description)

@router.post("/council/sessions/{session_id}/analyze")
def run_analysis(session_id: str):
    council = _get_council()
    session = council.get_session(session_id)
    if not session:
        raise HTTPException(404, "Council session not found")
    members = _workspace_council_members(session_id)
    if not members:
        raise HTTPException(409, "Council session has no models or participants")

    existing = council.get_analyses(session_id)
    existing_models = {str(item.get("model_id")) for item in existing}
    to_run = [m for m in members if str(m.get("model_id")) not in existing_models]
    created: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max(1, min(len(to_run), 5))) as pool:
        futures = {
            pool.submit(
                _call_workspace_council_model,
                _workspace_council_analysis_prompt(session=session, member=member),
                member,
                str(member.get("role") or "planner"),
                2600,
            ): member
            for member in to_run
        }
        for future in as_completed(futures):
            member = futures[future]
            try:
                payload = future.result()
            except Exception as exc:  # noqa: BLE001
                payload = {
                    "ok": False,
                    "model_id": str(member.get("model_id") or ""),
                    "verdict": "conditional",
                    "confidence": 0.0,
                    "reasoning": f"REAL_LLM_CALL_ERROR: {type(exc).__name__}: {str(exc)[:500]}",
                    "text": f"REAL_LLM_CALL_ERROR: {type(exc).__name__}: {str(exc)[:500]}",
                }
            if not payload.get("ok"):
                created.append({
                    "model_id": str(member.get("model_id") or payload.get("model_id") or ""),
                    "participant": member,
                    "source": "llm_error",
                    "llm": payload.get("llm", {}),
                    "error": str(payload.get("reasoning") or payload.get("text") or payload.get("error") or "")[:700],
                })
                continue
            verdict = str(payload.get("verdict") or "conditional").lower()
            if verdict not in {"approve", "conditional", "reject"}:
                verdict = "conditional"
            analysis = council.add_analysis(
                session_id,
                str(member.get("model_id") or payload.get("model_id") or ""),
                str(payload.get("text") or payload.get("reasoning") or ""),
                verdict,
                max(0.0, min(1.0, float(payload.get("confidence") or 0.0))),
                str(payload.get("reasoning") or ""),
            )
            analysis["participant"] = member
            analysis["llm"] = payload.get("llm", {})
            analysis["source"] = "real_llm"
            created.append(analysis)
    analyses = council.get_analyses(session_id)
    usable = [item for item in analyses if _workspace_council_analysis_is_usable(item)]
    if len(usable) < 2:
        raise HTTPException(
            503,
            {
                "message": "Council analysis failed: fewer than two usable model analyses were produced.",
                "created": created,
                "usable_count": len(usable),
            },
        )
    return {"analyses": analyses, "created": created}

@router.get("/council/sessions/{session_id}/analyses")
async def get_analyses(session_id: str):
    return {"analyses": _get_council().get_analyses(session_id)}

@router.post("/council/sessions/{session_id}/discuss")
def run_discussion(session_id: str, body: DiscussRequest = None):
    council = _get_council()
    session = council.get_session(session_id)
    if not session:
        raise HTTPException(404, "Council session not found")
    members = _workspace_council_members(session_id)
    analyses = [item for item in council.get_analyses(session_id) if _workspace_council_analysis_is_usable(item)]
    if len(analyses) < 2:
        raise HTTPException(409, "At least two usable real model analyses are required before cross-review discussion")
    existing = council.get_discussion(session_id)
    created: list[dict[str, Any]] = []
    rounds_per_model = max(1, min(3, int((body.rounds_per_model if body else 1) or 1)))
    start_round = 1 + max([int(item.get("round_number") or 0) for item in existing] or [0])

    for offset in range(rounds_per_model):
        round_no = start_round + offset
        with ThreadPoolExecutor(max_workers=max(1, min(len(members), 5))) as pool:
            futures = {
                pool.submit(
                    _call_workspace_council_model,
                    _workspace_council_discussion_prompt(
                        session=session,
                        member=member,
                        analyses=analyses,
                        prior_discussion=existing + created,
                    ),
                    member,
                    "critic",
                    1800,
                ): member
                for member in members
            }
            for future in as_completed(futures):
                member = futures[future]
                try:
                    payload = future.result()
                    contribution = str(payload.get("text") or payload.get("reasoning") or "")
                except Exception as exc:  # noqa: BLE001
                    contribution = f"REAL_LLM_CALL_ERROR: {type(exc).__name__}: {str(exc)[:500]}"
                target = next(
                    (item for item in analyses if item.get("model_id") != member.get("model_id")),
                    analyses[0],
                )
                created.append(council.add_discussion_round(
                    session_id,
                    round_no,
                    str(member.get("model_id") or ""),
                    contribution,
                    reaction_to=str(target.get("analysis_id") or target.get("model_id") or ""),
                ))
    return {"rounds": council.get_discussion(session_id), "created": created}

@router.post("/council/sessions/{session_id}/consolidate")
def consolidate(session_id: str):
    council = _get_council()
    summary = council.get_session_summary(session_id)
    if not summary:
        raise HTTPException(404, "Council session not found")

    analyses = summary.get("analyses") or []
    discussion = summary.get("discussion") or []
    verdict_counts: dict[str, int] = {}
    for item in analyses:
        verdict = str(item.get("verdict") or "conditional").lower()
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1

    approve_count = verdict_counts.get("approve", 0)
    reject_count = verdict_counts.get("reject", 0)
    conditional_count = verdict_counts.get("conditional", 0)
    total = max(1, len(analyses))
    consensus_level = max(approve_count, reject_count, conditional_count) / total

    if reject_count:
        direction = "Nie iść dalej bez doprecyzowania. Najpierw rozwiązać zastrzeżenia modeli odrzucających."
    elif conditional_count:
        direction = "Iść dalej warunkowo. Wybrać wariant ostrożny i zapisać warunki operatora przed zamrożeniem kanonu lub Masterplanu."
    elif approve_count:
        direction = "Można iść dalej. Rada nie zgłosiła blokujących zastrzeżeń w dostępnych analizach."
    else:
        direction = "Brak wystarczających głosów. Uruchom analizę modeli przed wyborem kierunku."

    lines = [
        f"Wniosek Rady dla: {summary.get('topic') or session_id}",
        f"Głosy: akceptacja {approve_count}, warunkowo {conditional_count}, odrzucenie {reject_count}.",
        f"Rekomendowany kierunek: {direction}",
    ]

    parsed_analyses = [
        _extract_workspace_json(str(item.get("analysis_text") or item.get("rationale") or ""))
        for item in analyses
    ]
    parsed_analyses = [item for item in parsed_analyses if item]

    def append_collected_section(title: str, keys: list[str], limit: int = 8) -> None:
        collected: list[str] = []
        for parsed in parsed_analyses:
            for key in keys:
                collected.extend(_workspace_string_items(parsed.get(key)))
        if not collected:
            return
        lines.append("")
        lines.append(title)
        for item in collected[:limit]:
            clean = item.replace("\n", " ").strip()
            if len(clean) > 420:
                clean = clean[:417].rstrip() + "..."
            lines.append(f"- {clean}")

    append_collected_section("Warianty decyzji operatora:", ["decision_options", "next_steps"])
    append_collected_section(
        "Pytania do operatora przed kolejna runda albo zamrozeniem Ksiegi:",
        ["council_questions", "missing_evidence", "runtime_blockers"],
    )
    append_collected_section(
        "Kandydaci do Ksiegi / Source of Truth:",
        ["source_of_truth_candidates", "project_purpose", "implemented_vs_unclear"],
    )
    append_collected_section(
        "Blokery, ryzyka i HumanGate:",
        ["risks", "sentinel_blocks", "functionality_gaps"],
    )

    if analyses:
        lines.append("")
        lines.append("Najważniejsze argumenty modeli:")
        for item in analyses[:5]:
            model_id = str(item.get("model_id") or "model")
            verdict = str(item.get("verdict") or "conditional")
            text = str(item.get("rationale") or item.get("analysis_text") or "").strip()
            digest = _workspace_council_analysis_digest(item, limit=700)
            text = digest or text
            if len(text) > 700:
                text = text[:697].rstrip() + "..."
            lines.append(f"- {model_id} ({verdict}): {text or 'brak uzasadnienia w zapisie analizy'}")

    if discussion:
        lines.append("")
        lines.append("Uwagi z dyskusji modeli:")
        for item in discussion[:8]:
            model_id = str(item.get("model_id") or "model")
            text = str(item.get("contribution") or "").strip()
            if len(text) > 650:
                text = text[:647].rstrip() + "..."
            lines.append(f"- {model_id}: {text or 'brak treści rundy'}")

    consolidated_text = "\n".join(lines)
    consolidated = council.set_consolidated(session_id, consolidated_text, consensus_level)
    return {**consolidated, "consolidated": consolidated, "consolidated_suggestion": consolidated_text}

@router.get("/council/sessions/{session_id}")
async def get_council_session(session_id: str):
    result = _get_council().get_session(session_id)
    if not result:
        raise HTTPException(404, "Council session not found")
    return result

@router.get("/council/sessions/{session_id}/summary")
async def get_council_session_summary(session_id: str):
    result = _get_council().get_session_summary(session_id)
    if not result:
        raise HTTPException(404, "Council session not found")
    return result

@router.get("/council/sessions")
async def list_council_sessions(phase: str = None, limit: int = 50):
    return {"sessions": _get_council().list_sessions(status=phase, limit=limit)}


# ---------------------------------------------------------------------------
# Council canonical roles / ranks / weights
# ---------------------------------------------------------------------------

@router.post("/council/sessions/{session_id}/participants")
async def add_council_participant(session_id: str, body: AddParticipantRequest):
    try:
        return _get_council().add_participant(
            session_id, body.model_id, body.role,
            rank=body.rank, weight=body.weight,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/council/sessions/{session_id}/participants")
async def list_council_participants(session_id: str,
                                    role: str | None = None,
                                    rank: str | None = None):
    return {
        "participants": _get_council().list_participants(
            session_id, role=role, rank=rank,
        ),
    }

@router.delete("/council/sessions/{session_id}/participants/{participant_id}")
async def remove_council_participant(session_id: str, participant_id: str):
    removed = _get_council().remove_participant(session_id, participant_id)
    if not removed:
        raise HTTPException(404, "Participant not found")
    return {"removed": True, "participant_id": participant_id}

@router.get("/council/roles")
async def list_council_roles():
    from sylion.governance.council_hybrid import (
        VALID_ROLES, VALID_RANKS,
        DEFAULT_ROLE_WEIGHTS, RANK_MULTIPLIER, SENTINEL_ROLES,
    )
    return {
        "roles": list(VALID_ROLES),
        "ranks": list(VALID_RANKS),
        "default_role_weights": DEFAULT_ROLE_WEIGHTS,
        "rank_multiplier": RANK_MULTIPLIER,
        "sentinel_roles": list(SENTINEL_ROLES),
    }


# ---------------------------------------------------------------------------
# Council critic signature
# ---------------------------------------------------------------------------

@router.post("/council/sessions/{session_id}/critic/sign")
async def record_critic_signature(session_id: str, body: CriticSignatureRequest):
    try:
        return _get_council().record_critic_signature(
            session_id, body.model_id, body.signed_decision,
            rationale=body.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/council/sessions/{session_id}/critic/signatures")
async def list_critic_signatures(session_id: str):
    return {
        "signatures": _get_council().get_critic_signatures(session_id),
        "signed": _get_council().has_critic_signature(session_id),
    }


# ---------------------------------------------------------------------------
# Council sentinel evaluations (cost / security)
# ---------------------------------------------------------------------------

@router.post("/council/sessions/{session_id}/sentinels/evaluate")
async def record_sentinel_evaluation(session_id: str, body: SentinelEvaluationRequest):
    try:
        return _get_council().record_sentinel_evaluation(
            session_id, body.sentinel_role, body.model_id,
            body.verdict, score=body.score, details=body.details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/council/sessions/{session_id}/sentinels")
async def list_sentinel_evaluations(session_id: str,
                                    sentinel_role: str | None = None):
    return {
        "evaluations": _get_council().get_sentinel_evaluations(
            session_id, sentinel_role=sentinel_role,
        ),
    }


# ---------------------------------------------------------------------------
# Council weighted consensus + gated consolidation
# ---------------------------------------------------------------------------

@router.get("/council/sessions/{session_id}/consensus")
async def compute_council_consensus(session_id: str):
    try:
        return _get_council().compute_weighted_consensus(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.post("/council/sessions/{session_id}/consolidate-gated")
async def consolidate_council_gated(session_id: str,
                                    body: ConsolidateWithGatesRequest):
    try:
        return _get_council().consolidate_with_signatures(
            session_id, body.consolidated_text,
            require_critic=body.require_critic,
            require_sentinels_pass=body.require_sentinels_pass,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Settings routes
# ---------------------------------------------------------------------------

@router.get("/settings/keys")
async def list_keys(provider: str = None):
    return {"keys": _get_vault().list_keys(provider=provider)}

@router.post("/settings/keys")
async def store_key(body: StoreKeyRequest):
    return _get_vault().store_key(
        body.provider, body.encrypted_key,
        display_name=body.display_name,
        metadata=body.metadata,
    )

@router.post("/settings/keys/{key_id}/activate")
async def activate_key(key_id: str):
    return _get_vault().activate_key(key_id)

@router.post("/settings/keys/{key_id}/validate")
async def validate_key(key_id: str):
    return _get_vault().validate_key(key_id)

@router.get("/settings/hierarchies")
async def list_hierarchies():
    return {"hierarchies": _get_vault().list_hierarchies()}

@router.post("/settings/hierarchies")
async def save_hierarchy(body: SaveHierarchyRequest):
    return _get_vault().save_hierarchy(body.name, body.levels)

@router.get("/settings/council-members")
async def list_council_members():
    return {"members": _get_vault().list_council_members()}

@router.post("/settings/council-members")
async def configure_member(body: ConfigureMemberRequest):
    return _get_vault().configure_council_member(
        body.member_id, body.model_id, body.role,
        body.priority, body.system_prompt,
        rank=body.rank,
        voting_weight=body.voting_weight,
        specialization=body.specialization,
        max_tokens=body.max_tokens,
    )


# ---------------------------------------------------------------------------
# Prompt templates routes
# ---------------------------------------------------------------------------

@router.get("/prompts")
async def list_prompts(category: str = None, team_id: str = None, project_id: str = None):
    return {"templates": _get_prompts().list_templates(category=category, team_id=team_id, project_id=project_id)}

@router.post("/prompts")
async def create_prompt(body: CreatePromptRequest):
    return _get_prompts().create_template(body.name, body.content, category=body.category, team_id=body.team_id, project_id=body.project_id)

@router.put("/prompts/{template_id}")
async def update_prompt(template_id: str, body: CreatePromptRequest):
    return _get_prompts().update_template(template_id, content=body.content, name=body.name, category=body.category)

@router.post("/prompts/{template_id}/resolve")
async def resolve_prompt(template_id: str, variables: dict = None):
    resolved = _get_prompts().resolve_template(template_id, variables or {})
    return {"resolved": resolved}


# ---------------------------------------------------------------------------
# Book routes
# ---------------------------------------------------------------------------

@router.post("/books")
async def create_book(body: CreateBookRequest):
    return _get_books().create_book(body.title, body.description, body.team_id, body.project_id)

@router.post("/books/{book_id}/generate/chat")
async def generate_from_chat(book_id: str, body: GenerateFromChatRequest):
    return _get_books().generate_from_chat(book_id, body.session_ids)

@router.post("/books/{book_id}/generate/council")
async def generate_from_council(book_id: str, body: GenerateFromCouncilRequest):
    return _get_books().generate_from_council(book_id, body.council_session_ids)

@router.get("/books")
async def list_books(status: str = None, team_id: str = None):
    return {"books": _get_books().list_books(status=status, team_id=team_id)}

@router.get("/books/{book_id}")
async def get_book(book_id: str):
    result = _get_books().get_book(book_id)
    if not result:
        raise HTTPException(404, "Book not found")
    return result

@router.get("/books/{book_id}/export")
async def export_book(book_id: str, format: str = "markdown"):
    content = _get_books().export_book(book_id, format)
    return {"content": content, "format": format}


# ---------------------------------------------------------------------------
# HumanGate routes
# ---------------------------------------------------------------------------

class CreateHGSessionRequest(BaseModel):
    title: str
    description: str = ""

class PresentDecisionRequest(BaseModel):
    context: str
    choices: list[dict]
    phase: str = ""

class MakeChoiceRequest(BaseModel):
    choice_id: str

class RollbackRequest(BaseModel):
    node_id: str

_hg = None
def _get_hg():
    global _hg
    if _hg is not None:
        return _hg
    from sylion.governance.human_gate import get_human_gate
    _hg = get_human_gate()
    return _hg

def _normalize_hg_choices(choices: list[dict]) -> list[dict]:
    normalized = []
    for index, choice in enumerate(choices or []):
        item = dict(choice or {})
        choice_id = str(item.get("choice_id") or item.get("id") or f"choice_{index + 1}")
        item["id"] = choice_id
        item["choice_id"] = choice_id
        normalized.append(item)
    return normalized

_idea_vault = None
def _get_idea_vault():
    global _idea_vault
    if _idea_vault is not None:
        return _idea_vault
    from sylion.cognitive.idea_vault import get_idea_vault
    _idea_vault = get_idea_vault()
    return _idea_vault

@router.post("/humangate/sessions")
async def create_hg_session(body: CreateHGSessionRequest):
    session = _get_hg().create_session(body.title, body.description)
    session["root_node_id"] = session.get("current_node_id") or session.get("session_id")
    return session

@router.post("/humangate/nodes/{node_id}/present")
async def present_hg_decision(node_id: str, body: PresentDecisionRequest):
    try:
        node = _get_hg().present_decision(
            node_id,
            body.context,
            _normalize_hg_choices(body.choices),
            body.phase,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    node["choices"] = _normalize_hg_choices(node.get("choices") or [])
    return node

@router.post("/humangate/nodes/{node_id}/choose")
async def make_hg_choice(node_id: str, body: MakeChoiceRequest):
    try:
        result = _get_hg().make_choice(node_id, body.choice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    chosen_node = result.get("chosen_node") or {}
    choices = _normalize_hg_choices(chosen_node.get("choices") or [])
    selected = next((choice for choice in choices if choice.get("choice_id") == body.choice_id), None)
    result["child_node_id"] = result.get("next_node_id")
    result["selected_choice"] = selected or {"choice_id": body.choice_id}
    return result

@router.post("/humangate/sessions/{session_id}/undo")
async def undo_hg_choice(session_id: str):
    node = _get_hg().undo_choice(session_id)
    if not node:
        raise HTTPException(404, "No chosen node to undo")
    node["rolled_back_to_node_id"] = node.get("node_id")
    return node

@router.post("/humangate/sessions/{session_id}/rollback")
async def rollback_hg(session_id: str, body: RollbackRequest):
    node = _get_hg().rollback_to(session_id, body.node_id)
    if not node:
        raise HTTPException(404, "Rollback node not found")
    node["rolled_back_to_node_id"] = node.get("node_id")
    return node

@router.get("/humangate/sessions/{session_id}/tree")
async def get_hg_tree(session_id: str):
    tree = _get_hg().get_tree(session_id)
    session = tree.get("session") or {}
    nodes = tree.get("nodes") or []
    tree["current_node_id"] = session.get("current_node_id", "")
    edges = []
    for node in nodes:
        parent = node.get("parent_node_id")
        if parent:
            edges.append({"from": parent, "to": node.get("node_id")})
    tree["edges"] = edges
    return tree

@router.get("/humangate/sessions/{session_id}/current")
async def get_hg_current(session_id: str):
    result = _get_hg().get_current_decision(session_id)
    if not result:
        raise HTTPException(404, "No current decision")
    return result

@router.get("/humangate/sessions/{session_id}/history")
async def get_hg_history(session_id: str):
    history = _get_hg().get_history(session_id)
    if not history:
        history = (_get_hg().get_tree(session_id).get("nodes") or [])
    return {"history": history}

@router.get("/humangate/sessions")
async def list_hg_sessions(status: str = None):
    return {"sessions": _get_hg().list_sessions(status=status)}

@router.get("/humangate/sessions/{session_id}")
async def get_hg_session(session_id: str):
    result = _get_hg().get_session(session_id)
    if not result:
        raise HTTPException(404, "HumanGate session not found")
    return result


# ---------------------------------------------------------------------------
# Idea Vault routes
# ---------------------------------------------------------------------------

@router.post("/ideas")
async def submit_idea(body: SubmitIdeaRequest):
    if not str(body.content or "").strip():
        raise HTTPException(status_code=422, detail="idea content must not be empty")
    return _get_idea_vault().submit_idea(
        content=body.content,
        category=body.category,
        priority=str(body.priority or "normal"),
        source=body.source,
        tags=body.tags,
    )

@router.put("/ideas/{idea_id}")
async def update_idea(idea_id: str, body: UpdateIdeaRequest):
    return _get_idea_vault().update_idea_workspace(
        idea_id,
        content=body.content,
        category=body.category,
        priority=str(body.priority) if body.priority is not None else None,
        tags=body.tags,
    )

@router.post("/ideas/{idea_id}/submit-pipeline")
async def submit_idea_to_pipeline(idea_id: str):
    idea = _get_idea_vault().submit_to_pipeline(idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")
    return {
        **idea,
        "pipeline_run_id": f"pipeline-{idea_id[:12]}",
        "status": "submitted",
    }


# F-032: generic idea -> project promotion. Reuses project_mode store
# so that the resulting project is fully-defaulted (questions, council plan,
# worker plan, audit plan etc.). This is the path the IdeaVault UI calls
# after a user has discussed an idea with the council and is ready to
# turn it into an actual project.
@router.post("/ideas/{idea_id}/promote-to-project")
async def promote_idea_to_project(idea_id: str, body: PromoteIdeaRequest):
    vault = _get_idea_vault()
    idea = vault.get_idea(idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")
    if bool(idea.get("human_gate_required")) and str(idea.get("human_gate_decision") or "").lower() != "approved":
        raise HTTPException(
            status_code=409,
            detail=(
                "Idea requires approved HumanGate before promotion to project. "
                f"request_id={idea.get('human_gate_request_id') or ''}"
            ),
        )

    # Build idea_raw from the canonical fields. The vault stores ideas in
    # two slightly different shapes depending on the entry path; cover both.
    idea_text = (
        idea.get("description")
        or idea.get("content")
        or idea.get("idea")
        or ""
    ).strip()
    idea_title = (idea.get("title") or "").strip()
    project_name = (body.project_name or idea_title or idea_text[:72] or "Projekt z pomyslu").strip()

    # Late import to avoid circular deps (projects_routes imports workspace
    # already through the FastAPI app aggregation).
    from sylion.project_mode import get_project_mode_store
    from sylion.api.projects_routes import (
        _classify_project_kind,
        _apply_domain_profile_to_blueprint,
        _apply_domain_profile_to_documents,
        _blueprint_for_project,
        _project_documents,
        _default_project_questions,
    )

    store = get_project_mode_store()
    kind = _classify_project_kind(idea_text)
    blueprint = _apply_domain_profile_to_blueprint(
        _blueprint_for_project(kind, list(body.preferred_stack or [])),
        idea_text,
        kind,
    )
    modules = list((blueprint.get("worker_plan") or {}).get("modules") or [])
    canonical_book, masterplan, canon_snapshot = _project_documents(
        project_name, idea_text, kind, modules,
    )
    canonical_book, masterplan, canon_snapshot = _apply_domain_profile_to_documents(
        canonical_book,
        masterplan,
        canon_snapshot,
        blueprint.get("domain_profile") if isinstance(blueprint.get("domain_profile"), dict) else None,
    )
    project: dict = {
        "title": project_name,
        "idea": idea_text,
        "constraints": body.constraints,
        "canonical_book_input": "",
        "preferred_stack": list(body.preferred_stack or []),
        "attachments": list(body.attachments or []),
        "team_id": body.team_id,
        "owner_id": body.owner_id or "workspace-default",
        "project_kind": kind,
        "canonical_book": canonical_book,
        "masterplan": masterplan,
        "canon_snapshot": canon_snapshot,
        "memory_policy": blueprint["memory_policy"],
        "worker_plan": blueprint["worker_plan"],
        "council_plan": blueprint["council_plan"],
        "execution_plan": blueprint["execution_plan"],
        "governance_policy": blueprint["governance_policy"],
        "audit_plan": blueprint["audit_plan"],
        "questions": _default_project_questions(kind, canon_snapshot.get("runtime_constraints") if isinstance(canon_snapshot, dict) else None),
        # Provenance: link back to the idea so the UI can show it.
        "source_idea_id": idea_id,
    }
    project = store.upsert_project(project)
    store.add_event(project["project_id"], "project.created", {
        "owner_id": project.get("owner_id"),
        "auto_execute": bool(body.auto_execute),
        "from_idea_id": idea_id,
    })
    if body.auto_execute:
        project["launch"] = {**(project.get("launch") or {}), "auto_execute": True}
        project = store.upsert_project(project)

    # Mark the idea as implemented so it disappears from the active backlog.
    # "promoted" is not a valid IdeaVault status, so use the canonical terminal
    # state and keep the project link in the project record.
    try:
        vault.mark_implemented(idea_id, actor=body.owner_id or "workspace-default")
    except Exception:
        # A stuck idea status is recoverable; do not roll back an already
        # created project.
        try:
            vault.update_idea(idea_id, status="implemented")
        except Exception:
            pass

    return {"idea_id": idea_id, "project": project}


# F-032: idea-level discussion thread. Lets the user kick off a small
# council deliberation against the idea description BEFORE deciding to
# promote it to a project. Stores conversation in the AI workspace chat
# engine (so it shows up under /workspace/sessions like any other talk).
@router.post("/ideas/{idea_id}/discuss")
async def discuss_idea(idea_id: str, body: IdeaDiscussRequest):
    vault = _get_idea_vault()
    idea = vault.get_idea(idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")

    title = (idea.get("title") or "Pomysl").strip()[:60]
    idea_text = (idea.get("description") or idea.get("content") or "").strip()
    user_prompt = (body.prompt or "").strip() or (
        "Przedyskutujmy ten pomysl: ryzyka, brakujace elementy, sugerowany stack, "
        "decyzja czy nadaje sie na projekt."
    )

    # Default to a small mixed-vendor lineup if user didn't pick models.
    model_ids = list(body.model_ids or [])
    if not model_ids:
        # Conservative defaults — always-available + cheap-but-strong.
        model_ids = _default_discussion_model_ids()
    model_ids = [str(model_id).strip() for model_id in model_ids if str(model_id).strip()]
    model_ids = list(dict.fromkeys(model_ids))[:4]

    chat = _get_chat()
    primary_model_id = model_ids[0] if model_ids else ""
    session = chat.create_session(
        title=f"Dyskusja: {title}",
        model_id=primary_model_id,
        system_prompt=(
            "Jestes czlonkiem rady doradczej rozwazajacej swiezy pomysl projektu. "
            "Bedz konkretny, wskaz: (1) silne strony, (2) ryzyka, (3) braki w opisie "
            "ktore trzeba uzupelnic, (4) sugerowany stack/podejscie, (5) czy warto "
            "promowac do pelnego projektu (TAK/NIE + uzasadnienie)."
        ),
    )
    session_id = session.get("session_id") if isinstance(session, dict) else None

    # Seed the session with idea context so each model has the same brief.
    if session_id:
        try:
            chat.send_message(
                session_id=session_id,
                role="user",
                content=(
                    f"Pomysl: {title}\n\nOpis:\n{idea_text}\n\n"
                    f"Pytanie/aspekt do dyskusji: {user_prompt}"
                ),
            )
        except TypeError:
            try:
                chat.send_message(session_id, (
                    f"Pomysl: {title}\n\nOpis:\n{idea_text}\n\n"
                    f"Pytanie/aspekt do dyskusji: {user_prompt}"
                ))
            except Exception:
                pass

    rounds = max(1, min(int(body.rounds or 1), 3))
    round_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    prior_round: list[str] = []
    if session_id:
        for round_no in range(1, rounds + 1):
            ordered: list[dict[str, Any] | None] = [None for _ in model_ids]
            with ThreadPoolExecutor(max_workers=max(1, min(len(model_ids), 4))) as pool:
                future_to_index = {
                    pool.submit(
                        _run_idea_model_discussion,
                        title=title,
                        idea_text=idea_text,
                        user_prompt=user_prompt,
                        model_id=model_id,
                        round_no=round_no,
                        prior_round=prior_round,
                    ): index
                    for index, model_id in enumerate(model_ids)
                }
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        ordered[index] = future.result()
                    except Exception as exc:  # noqa: BLE001
                        model_id = model_ids[index]
                        ordered[index] = {
                            "ok": False,
                            "model_id": model_id,
                            "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                            "content": f"REAL_LLM_CALL_ERROR model={model_id}: {type(exc).__name__}: {str(exc)[:500]}",
                        }

            current_round_snippets: list[str] = []
            for result in [item for item in ordered if item is not None]:
                metadata = {
                    "source": "real_llm" if result.get("ok") else "llm_error",
                    "idea_id": idea_id,
                    "discussion_round": round_no,
                    "provider": result.get("provider", result.get("provider_requested", "")),
                    "model": result.get("model", result.get("model_id", "")),
                    "latency_ms": result.get("latency_ms", 0),
                    "prompt_tokens": result.get("prompt_tokens", 0),
                    "completion_tokens": result.get("completion_tokens", 0),
                    "estimated_cost_usd": result.get("estimated_cost_usd", 0.0),
                    "fallback_used": bool(result.get("fallback_used")),
                    "error": result.get("error", ""),
                }
                content = str(result.get("content") or "")
                chat.send_message(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    model_id=str(result.get("model") or result.get("model_id") or ""),
                    metadata=metadata,
                )
                record = {**result, "round": round_no}
                round_results.append(record)
                if not result.get("ok"):
                    errors.append(record)
                else:
                    current_round_snippets.append(
                        f"{result.get('model') or result.get('model_id')}: {content[:1200]}"
                    )
            prior_round.extend(current_round_snippets)

    successful = [item for item in round_results if item.get("ok")]
    if errors and successful:
        status = "partial_failure"
    elif errors and not successful:
        status = "failed"
    else:
        status = "completed"

    return {
        "idea_id": idea_id,
        "session_id": session_id,
        "model_ids": model_ids,
        "rounds": rounds,
        "status": status,
        "responses": round_results,
        "errors": errors,
    }


# F-032: read-back of any discussions the user has had against this idea.
@router.get("/ideas/{idea_id}/discussion")
async def get_idea_discussion(idea_id: str):
    chat = _get_chat()
    sessions = []
    try:
        # ChatEngine.list_sessions filters by title prefix isn't standard;
        # fallback to whatever the engine supports. We tag created sessions
        # with title 'Dyskusja: <ideaTitle>' so a string-match works.
        all_sessions = chat.list_sessions() if hasattr(chat, "list_sessions") else []
    except Exception:
        all_sessions = []
    for s in all_sessions:
        title = (s.get("title") or "") if isinstance(s, dict) else ""
        if title.startswith("Dyskusja:"):
            sessions.append(s)
    return {"idea_id": idea_id, "sessions": sessions}

@router.get("/ideas")
async def list_ideas(status: str = None, category: str = None, limit: int = 50):
    return {"ideas": _get_idea_vault().list_ideas(status=status, category=category, limit=limit)}

@router.get("/ideas/stats")
async def idea_stats():
    return _get_idea_vault().get_stats()

@router.get("/ideas/search")
async def search_ideas(q: str = ""):
    return {"ideas": _get_idea_vault().search_ideas(q)}

@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: str):
    result = _get_idea_vault().get_idea(idea_id)
    if not result:
        raise HTTPException(404, "Idea not found")
    return result

@router.delete("/ideas/{idea_id}")
async def delete_idea(idea_id: str):
    deleted = _get_idea_vault().delete_idea(idea_id)
    if not deleted:
        raise HTTPException(404, "Idea not found")
    return {"idea_id": idea_id, "status": "deleted", "deleted": True}


# ---------------------------------------------------------------------------
# Idea Attachments routes
# ---------------------------------------------------------------------------

_idea_attachments = None
def _get_idea_attachments():
    global _idea_attachments
    if _idea_attachments is not None:
        return _idea_attachments
    from sylion.cognitive.idea_attachments import get_idea_attachments
    from sylion.core.event_bus import get_event_bus
    from sylion.aeis_v2.audit_profile import resolve_db_path

    _idea_attachments = get_idea_attachments(
        db_path=resolve_db_path("idea_attachments.db"),
        event_bus=get_event_bus(),
    )
    return _idea_attachments

@router.post("/ideas/upload")
async def upload_idea_attachment(
    file: UploadFile = File(...),
    idea_id: str = "",
):
    """Upload a file as an attachment to an idea.

    Accepts multipart form with file and optional idea_id.
    Supports any binary content (PDF, DOCX, ZIP, JPG, source code, etc.)
    up to 50MB. If ``idea_id`` is empty an auto-generated ``draft-`` id
    is used so users can attach files before promoting the idea to the
    Idea Vault.

    F-016 fix (post-audit user-reported gap): backend method name was
    ``add_attachment`` while the endpoint called ``upload_file`` and used
    a mismatched ``content_type`` kwarg. Now wires correctly + auto idea_id.
    """
    content = await file.read()

    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50MB)")

    effective_idea_id = idea_id or f"draft-{int(time.time() * 1000)}"
    file_type = file.content_type or "application/octet-stream"

    try:
        record = _get_idea_attachments().add_attachment(
            idea_id=effective_idea_id,
            filename=file.filename or "unnamed",
            file_type=file_type,
            content_bytes=content,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc))

    if not record:
        raise HTTPException(500, "attachment created but record not retrievable")

    record["idea_id_used"] = effective_idea_id
    record["draft_idea"] = bool(not idea_id)
    return record

@router.post("/ideas/import-local")
async def import_local_idea_attachment(body: ImportLocalIdeaAttachmentRequest):
    """Import a local workstation file through an explicit dashboard form.

    This is the operator-visible fallback for browser runtimes where the system
    file picker cannot be automated. It still goes through the normal idea
    attachment store and audit events; callers must provide a concrete path.
    """
    raw_path = str(body.file_path or "").strip().strip('"')
    if not raw_path:
        raise HTTPException(422, "file_path must not be empty")
    try:
        source_path = Path(raw_path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise HTTPException(404, f"local file not found: {exc}")
    if not source_path.is_file():
        raise HTTPException(400, "file_path must point to a regular file")
    file_size = source_path.stat().st_size
    if file_size > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 50MB)")

    effective_idea_id = body.idea_id or f"draft-{int(time.time() * 1000)}"
    file_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
    try:
        record = _get_idea_attachments().add_attachment(
            idea_id=effective_idea_id,
            filename=source_path.name,
            file_type=file_type,
            content_bytes=source_path.read_bytes(),
        )
    except (ValueError, TypeError, OSError) as exc:
        raise HTTPException(400, str(exc))
    return {**record, "source": "local_path_import"}

@router.get("/ideas/{idea_id}/attachments")
async def list_idea_attachments(idea_id: str):
    """List all attachments for an idea (or draft idea_id)."""
    attachments = _get_idea_attachments().get_attachments(idea_id)
    return {"attachments": attachments}

@router.post("/ideas/attachments/{attachment_id}/analyze")
async def analyze_idea_attachment(attachment_id: str):
    """Analyze one uploaded idea attachment.

    Produces a persisted summary with extracted preview, risks, missing
    information, suggested skills, decision class and HumanGate requirement.
    """
    try:
        return _get_idea_attachments().analyze_attachment(attachment_id)
    except KeyError:
        raise HTTPException(404, f"attachment '{attachment_id}' not found")

@router.post("/ideas/{idea_id}/attachments/analyze")
async def analyze_all_idea_attachments(idea_id: str):
    """Analyze all attachments linked to an idea/draft idea id."""
    return {"idea_id": idea_id, "analyses": _get_idea_attachments().analyze_idea_attachments(idea_id)}

@router.get("/ideas/{idea_id}/attachments/analysis")
async def list_idea_attachment_analysis(idea_id: str):
    """Return persisted attachment-analysis rows for an idea/draft."""
    return {"idea_id": idea_id, "analyses": _get_idea_attachments().list_attachment_analysis(idea_id)}

@router.delete("/ideas/attachments/{attachment_id}")
async def delete_idea_attachment(attachment_id: str):
    """Delete an attachment and its file from disk."""
    deleted = _get_idea_attachments().delete_attachment(attachment_id)
    if not deleted:
        raise HTTPException(404, f"attachment '{attachment_id}' not found")
    return {"deleted": True, "attachment_id": attachment_id}
