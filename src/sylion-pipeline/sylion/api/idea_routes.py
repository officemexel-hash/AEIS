"""
SYLION API -- Idea Vault routes.

Endpoints for the IdeaVault module:
  create_idea, update_idea, delete_idea, get_idea,
  list_ideas, vote_idea, get_votes, search_ideas, get_idea_stats.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sylion.aeis.advisor.events.lifecycle import publish_lifecycle_event

router = APIRouter(prefix="/api/v1/ideas", tags=["Idea Vault"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_idea_vault = None

_DECISION_CLASS_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5}


def _highest_attachment_decision_class(attachment_analysis: list[dict]) -> str:
    highest = "D1"
    for item in attachment_analysis:
        if not isinstance(item, dict):
            continue
        decision_class = str(item.get("decision_class") or "").upper().strip()
        if _DECISION_CLASS_ORDER.get(decision_class, -1) > _DECISION_CLASS_ORDER[highest]:
            highest = decision_class
    return highest


def _attachment_requires_human_gate(attachment_analysis: list[dict]) -> bool:
    for item in attachment_analysis:
        if not isinstance(item, dict):
            continue
        decision_class = str(item.get("decision_class") or "").upper().strip()
        if bool(item.get("human_gate_required")):
            return True
        if _DECISION_CLASS_ORDER.get(decision_class, -1) >= _DECISION_CLASS_ORDER["D3"]:
            return True
    return False


def _get_idea_vault():
    global _idea_vault
    if _idea_vault is not None:
        return _idea_vault
    from sylion.cognitive.idea_vault import get_idea_vault
    _idea_vault = get_idea_vault()
    return _idea_vault


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateIdeaRequest(BaseModel):
    title: str
    description: str = ""
    author: str = ""
    tags: list[str] | None = None
    attachments: list[dict] | None = None


class UpdateIdeaRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    author: str | None = None
    status: str | None = None


class VoteIdeaRequest(BaseModel):
    user_id: str
    vote_type: str = "upvote"


# F-Idea1-2 (P2 / W14 BE-8.1): operator answer to outstanding clarification
# questions. Appends a timestamped line to ``clarification_notes`` and
# records an idea_lifecycle_log row so the audit chain captures the
# response.
class ClarificationResponseRequest(BaseModel):
    response: str = ""
    responder: str = "operator"
    # Frontend used these names during FE-1. Keep them as first-class inputs
    # so old browser sessions still persist real audit events instead of 422.
    answer: str = ""
    author: str = ""


# F-032: idea -> project promotion (generic). Reuses the project_mode store
# so the resulting project gets a full default plan (questions, council
# plan, worker plan, audit plan, masterplan, canon snapshot).
class PromoteIdeaRequest(BaseModel):
    project_name: str = ""
    constraints: str = ""
    preferred_stack: list[str] = []
    attachments: list[dict] = []
    auto_execute: bool = False
    owner_id: str = "workspace-default"
    team_id: str = ""


# F-032: kick off a small council/chat dyskusja against the idea BEFORE
# the user commits to promotion. Stores the thread in chat_engine so it
# is discoverable under /api/v1/workspace/sessions like any other chat.
class IdeaDiscussRequest(BaseModel):
    prompt: str = ""
    model_ids: list[str] = []
    rounds: int = 1


def _normalise_discussion_models(model_ids: list[str] | None, *, limit: int = 4) -> list[str]:
    """Resolve dashboard mini-council members without falling back to demo text."""
    resolved: list[str] = []
    for item in model_ids or []:
        model_id = str(item or "").strip()
        if model_id and model_id not in resolved:
            resolved.append(model_id)
        if len(resolved) >= limit:
            return resolved
    if resolved:
        return resolved
    from sylion.api.ai_workspace_routes import _default_discussion_model_ids

    for item in _default_discussion_model_ids(limit=limit):
        model_id = str(item or "").strip()
        if model_id and model_id not in resolved:
            resolved.append(model_id)
        if len(resolved) >= limit:
            break
    return resolved


def _send_chat_message(chat: Any, *, session_id: str, role: str, content: str,
                       model_id: str = "", metadata: dict | None = None) -> dict | None:
    """Call ChatEngine defensively across older signatures used in forks."""
    try:
        return chat.send_message(
            session_id=session_id,
            role=role,
            content=content,
            model_id=model_id,
            metadata=metadata,
        )
    except TypeError:
        try:
            return chat.send_message(session_id, role, content, model_id, metadata)
        except TypeError:
            try:
                return chat.send_message(session_id, content)
            except Exception:
                return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_idea(body: CreateIdeaRequest):
    """Create a new idea."""
    vault = _get_idea_vault()
    try:
        result = vault.create_idea(
            title=body.title,
            description=body.description,
            author=body.author,
            tags=body.tags,
        )
        attachments = []
        attachment_analysis = []
        attachment_ids = [
            str(item.get("attachment_id") or "").strip()
            for item in (body.attachments or [])
            if isinstance(item, dict) and str(item.get("attachment_id") or "").strip()
        ]
        if attachment_ids and result.get("idea_id"):
            from sylion.api.ai_workspace_routes import _get_idea_attachments

            attachment_store = _get_idea_attachments()
            attachments = attachment_store.reassign_attachments(
                attachment_ids,
                str(result["idea_id"]),
            )
            attachment_analysis = attachment_store.list_attachment_analysis(str(result["idea_id"]))
            result["attachments"] = attachments
            result["attachment_analysis"] = attachment_analysis
        initial_classification = _highest_attachment_decision_class(attachment_analysis)
        attachment_human_gate_required = _attachment_requires_human_gate(attachment_analysis)
        if attachment_human_gate_required and result.get("idea_id"):
            gated = vault.request_approval(
                str(result["idea_id"]),
                requested_by=body.author or "workspace-default",
                priority=f"attachment_{initial_classification.lower()}",
                decision_class=initial_classification,
            )
            if gated:
                result = gated
            result["attachments"] = attachments
            result["attachment_analysis"] = attachment_analysis
        publish_lifecycle_event(
            "aeis.idea.intake.completed",
            {
                "idea_id": result.get("idea_id", ""),
                "operator_id": body.author or "workspace-default",
                "domain": "application",
                "type": "research",
                "title": body.title,
                "description": body.description,
                "initial_classification": initial_classification,
                "attachment_human_gate_required": attachment_human_gate_required,
                "attachment_count": len(attachments),
                "attachment_analysis_count": len(attachment_analysis),
                "attachment_decision_classes": [
                    str(item.get("decision_class", ""))
                    for item in attachment_analysis
                    if isinstance(item, dict)
                ],
            },
            source_module="sylion.api.idea_routes",
            primary_key=result.get("idea_id", body.title),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{idea_id}")
def update_idea(idea_id: str, body: UpdateIdeaRequest):
    """Update fields on an existing idea."""
    vault = _get_idea_vault()
    try:
        if body.status in {"council_review", "awaiting_approval"}:
            if body.title is not None or body.description is not None or body.author is not None:
                updated_fields = vault.update_idea(
                    idea_id=idea_id,
                    title=body.title,
                    description=body.description,
                    author=body.author,
                )
                if not updated_fields:
                    result = None
                else:
                    result = (
                        vault.request_approval(
                            idea_id,
                            requested_by=body.author or "workspace-default",
                            priority="manual_transition",
                        )
                        if body.status == "awaiting_approval"
                        else vault.submit_for_council(
                            idea_id,
                            actor=body.author or "workspace-default",
                        )
                    )
            else:
                result = (
                    vault.request_approval(
                        idea_id,
                        requested_by=body.author or "workspace-default",
                        priority="manual_transition",
                    )
                    if body.status == "awaiting_approval"
                    else vault.submit_for_council(
                        idea_id,
                        actor=body.author or "workspace-default",
                    )
                )
        else:
            result = vault.update_idea(
                idea_id=idea_id,
                title=body.title,
                description=body.description,
                author=body.author,
                status=body.status,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return result


@router.delete("/{idea_id}")
def delete_idea(idea_id: str):
    """Delete an idea and its tags/votes."""
    vault = _get_idea_vault()
    deleted = vault.delete_idea(idea_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Retrieval -- static paths before dynamic /{idea_id} paths
# ---------------------------------------------------------------------------

@router.get("")
def list_ideas(
    status: str | None = None,
    tag: str | None = None,
    author: str | None = None,
    limit: int = 100,
):
    """List ideas with optional filters."""
    vault = _get_idea_vault()
    try:
        return vault.list_ideas(status=status, tag=tag, author=author, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search")
def search_ideas(query: str):
    """Search ideas by title or description."""
    vault = _get_idea_vault()
    return vault.search_ideas(query)


@router.get("/stats")
def get_idea_stats():
    """Aggregate idea statistics."""
    vault = _get_idea_vault()
    return vault.get_idea_stats()


@router.get("/{idea_id}")
def get_idea(idea_id: str):
    """Retrieve a single idea by ID."""
    vault = _get_idea_vault()
    result = vault.get_idea(idea_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return result


@router.get("/{idea_id}/history")
def get_idea_history(idea_id: str):
    """Return append-only lifecycle history for one idea."""
    vault = _get_idea_vault()
    if not vault.get_idea(idea_id):
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return {"idea_id": idea_id, "history": vault.get_lifecycle_history(idea_id)}


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------

@router.post("/{idea_id}/votes", status_code=201)
def vote_idea(idea_id: str, body: VoteIdeaRequest):
    """Cast or update a vote on an idea."""
    vault = _get_idea_vault()
    try:
        result = vault.vote_idea(
            idea_id=idea_id,
            user_id=body.user_id,
            vote_type=body.vote_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return result


@router.get("/{idea_id}/votes")
def get_votes(idea_id: str):
    """Get all votes for an idea."""
    vault = _get_idea_vault()
    return {"votes": vault.get_votes(idea_id)}


# ---------------------------------------------------------------------------
# F-032: discussion + promotion to project
# ---------------------------------------------------------------------------

@router.post("/{idea_id}/promote-to-project")
def promote_idea_to_project(idea_id: str, body: PromoteIdeaRequest):
    """Convert an idea into a fully-defaulted project record.

    Unlike funding's convert-to-project this is a *generic* path that
    works for any idea regardless of grant context. The user lands on
    the new project with default questions, council, worker plan and
    audit plan ready to be customised.
    """
    vault = _get_idea_vault()
    idea = vault.get_idea(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    if bool(idea.get("human_gate_required")) and str(idea.get("human_gate_decision") or "").lower() != "approved":
        raise HTTPException(
            status_code=409,
            detail=(
                "Idea requires approved HumanGate before promotion to project. "
                f"request_id={idea.get('human_gate_request_id') or ''}"
            ),
        )

    idea_text = (
        idea.get("description")
        or idea.get("content")
        or idea.get("idea")
        or ""
    ).strip()
    idea_title = (idea.get("title") or "").strip()
    project_name = (body.project_name or idea_title or idea_text[:72] or "Projekt z pomyslu").strip()

    # Late import to avoid a circular dependency between idea_routes and
    # projects_routes during module collection.
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
    project = {
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

    # Mark the idea as promoted so it doesn't keep showing in the active
    # backlog. Failure here must not roll back the project we already
    # created — a stuck status is recoverable, a phantom project is not.
    try:
        vault.update_idea(idea_id=idea_id, status="implemented")
    except Exception:
        pass

    publish_lifecycle_event(
        "aeis.idea.promoted_to_project",
        {
            "idea_id": idea_id,
            "project_id": project["project_id"],
            "operator_id": body.owner_id or "workspace-default",
        },
        source_module="sylion.api.idea_routes",
        primary_key=project["project_id"],
    )

    return {"idea_id": idea_id, "project": project}


@router.post("/{idea_id}/discuss")
def discuss_idea(idea_id: str, body: IdeaDiscussRequest):
    """Spin up a chat session against this idea so the user can argue
    it out with one or more models BEFORE deciding to promote.
    """
    vault = _get_idea_vault()
    idea = vault.get_idea(idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")

    title = (idea.get("title") or "Pomysl").strip()[:60]
    idea_text = (idea.get("description") or idea.get("content") or "").strip()
    user_prompt = (body.prompt or "").strip() or (
        "Przedyskutujmy ten pomysl: ryzyka, brakujace elementy, sugerowany "
        "stack, decyzja czy nadaje sie na projekt."
    )

    model_ids = _normalise_discussion_models(body.model_ids, limit=4)
    if not model_ids:
        raise HTTPException(
            status_code=409,
            detail="No discussion models configured. Add at least one API provider or Ollama model.",
        )
    rounds = max(1, min(int(body.rounds or 1), 3))

    # Late import to avoid pulling chat_engine at module load.
    from sylion.cognitive.chat_engine import get_chat_engine
    from sylion.core.event_bus import get_event_bus
    chat = get_chat_engine(event_bus=get_event_bus())

    # ChatEngine.create_session accepts a single model_id; we pass the
    # primary one here and let the per-message API choose later models.
    primary_model_id = model_ids[0] if model_ids else ""
    session = chat.create_session(
        title=f"Dyskusja: {title}",
        model_id=primary_model_id,
        system_prompt=(
            "Jestes czlonkiem rady doradczej rozwazajacej swiezy pomysl projektu. "
            "Bedz konkretny, wskaz: (1) silne strony, (2) ryzyka, (3) braki w "
            "opisie ktore trzeba uzupelnic, (4) sugerowany stack/podejscie, "
            "(5) czy warto promowac do pelnego projektu (TAK/NIE + uzasadnienie)."
        ),
    )
    session_id = session.get("session_id") if isinstance(session, dict) else None

    if not session_id:
        raise HTTPException(status_code=500, detail="Chat session was not created")

    _send_chat_message(
        chat,
        session_id=session_id,
        role="user",
        content=(
            f"Pomysl: {title}\n\nOpis:\n{idea_text}\n\n"
            f"Pytanie/aspekt do dyskusji: {user_prompt}"
        ),
        metadata={"source": "idea_discussion", "idea_id": idea_id, "round": 0},
    )

    from sylion.api.ai_workspace_routes import _run_idea_model_discussion

    responses: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    prior_round: list[str] = []

    for round_no in range(1, rounds + 1):
        round_results: list[dict[str, Any]] = []
        workers = min(len(model_ids), 4)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _run_idea_model_discussion,
                    title=title,
                    idea_text=idea_text,
                    user_prompt=user_prompt,
                    model_id=model_id,
                    round_no=round_no,
                    prior_round=prior_round,
                ): model_id
                for model_id in model_ids
            }
            for future in as_completed(futures):
                model_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = {
                        "ok": False,
                        "model_id": model_id,
                        "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                        "content": (
                            f"REAL_LLM_CALL_ERROR model={model_id}. "
                            f"Blad realnego wywolania: {type(exc).__name__}: {str(exc)[:500]}"
                        ),
                    }
                round_results.append(result)

        round_results.sort(key=lambda item: str(item.get("model_id") or ""))
        for result in round_results:
            model_id = str(result.get("model_id") or "")
            content = str(result.get("content") or "").strip()
            ok = bool(result.get("ok"))
            if not ok:
                errors.append({
                    "model_id": model_id,
                    "round": round_no,
                    "error": result.get("error") or content,
                })
            if not content:
                content = f"REAL_LLM_EMPTY_RESPONSE model={model_id}. Model returned no content."
                ok = False
                errors.append({"model_id": model_id, "round": round_no, "error": content})
            _send_chat_message(
                chat,
                session_id=session_id,
                role="assistant",
                content=content,
                model_id=model_id,
                metadata={
                    "source": "idea_discussion",
                    "idea_id": idea_id,
                    "round": round_no,
                    "model_id": model_id,
                    "ok": ok,
                    "provider": result.get("provider"),
                    "latency_ms": result.get("latency_ms"),
                    "prompt_tokens": result.get("prompt_tokens"),
                    "completion_tokens": result.get("completion_tokens"),
                    "estimated_cost_usd": result.get("estimated_cost_usd"),
                    "fallback_used": result.get("fallback_used"),
                    "error": result.get("error"),
                },
            )
            response_row = {
                key: result.get(key)
                for key in (
                    "ok", "model_id", "provider", "model", "latency_ms",
                    "prompt_tokens", "completion_tokens", "estimated_cost_usd",
                    "fallback_used", "error",
                )
            }
            response_row["round"] = round_no
            response_row["content_preview"] = content[:500]
            responses.append(response_row)
            prior_round.append(f"{model_id}: {content[:900]}")

    ok_count = len([item for item in responses if item.get("ok")])
    if ok_count == 0:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "No real model responded to idea discussion.",
                "session_id": session_id,
                "errors": errors,
            },
        )

    return {
        "idea_id": idea_id,
        "session_id": session_id,
        "model_ids": model_ids,
        "rounds": rounds,
        "responses": responses,
        "errors": errors,
        "status": "completed_with_errors" if errors else "completed",
    }


@router.post("/{idea_id}/clarification-response")
def add_clarification_response(idea_id: str, body: ClarificationResponseRequest):
    """W14 BE-8.1 — operator response to clarification questions.

    Appends ``[<iso-ts>] <responder>: <response>`` to
    ``idea.clarification_notes`` (preserving existing content), bumps
    ``last_activity_at`` and writes an ``idea_lifecycle_log`` audit row.

    F-Idea1-2 (P2): closes the gap between the FE clarification banner
    (which used to read-only display backend questions) and the audit
    chain. 404 if the idea is missing; 400 on empty response.
    """
    vault = _get_idea_vault()
    response = (body.response or body.answer or "").strip()
    responder = (body.responder or body.author or "operator").strip() or "operator"
    try:
        result = vault.add_clarification_response(
            idea_id=idea_id,
            response=response,
            responder=responder,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return result


@router.get("/{idea_id}/discussion")
def get_idea_discussion(idea_id: str):
    """List discussion sessions previously created for this idea (best-effort)."""
    from sylion.cognitive.chat_engine import get_chat_engine
    from sylion.core.event_bus import get_event_bus
    chat = get_chat_engine(event_bus=get_event_bus())

    sessions: list[dict] = []
    try:
        all_sessions = chat.list_sessions() if hasattr(chat, "list_sessions") else []
    except Exception:
        all_sessions = []
    for s in all_sessions or []:
        if not isinstance(s, dict):
            continue
        title = s.get("title") or ""
        session_id = str(s.get("session_id") or "")
        if not title.startswith("Dyskusja:") or not session_id:
            continue
        try:
            messages = chat.list_messages(session_id, limit=100)
        except Exception:
            messages = []
        linked_to_idea = False
        for message in messages or []:
            if not isinstance(message, dict):
                continue
            metadata = message.get("metadata") or {}
            if isinstance(metadata, dict) and metadata.get("idea_id") == idea_id:
                linked_to_idea = True
                break
        if linked_to_idea:
            sessions.append(s)
    return {"idea_id": idea_id, "sessions": sessions}
