"""
SYLION API -- Governance Gates routes.

Combined endpoints for GatesRegistry and HumanGate:
  Registry:   create_gate, update_gate, delete_gate, get_gate, list_gates,
              evaluate_gate, get_evaluations, get_gate_stats.
  HumanGate:  create_request, submit_review, get_request, list_requests,
              get_reviews, escalate_request, get_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/gates", tags=["Governance Gates"])


# ---------------------------------------------------------------------------
# Lazy accessors
# ---------------------------------------------------------------------------

_gates_registry = None
_human_gate = None


def _get_gates_registry():
    global _gates_registry
    if _gates_registry is not None:
        return _gates_registry
    from sylion.governance.gates_registry import get_gates_registry
    _gates_registry = get_gates_registry()
    return _gates_registry


def _get_human_gate():
    global _human_gate
    if _human_gate is not None:
        return _human_gate
    from sylion.governance.human_gate import get_human_gate
    _human_gate = get_human_gate()
    return _human_gate


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateGateRequest(BaseModel):
    name: str
    gate_type: str = "quality"
    criteria_json: dict | None = None
    scope: str = ""


class UpdateGateRequest(BaseModel):
    name: str | None = None
    gate_type: str | None = None
    criteria_json: dict | None = None
    scope: str | None = None
    enabled: bool | None = None


class EvaluateGateRequest(BaseModel):
    context_json: dict | None = None


class CreateReviewRequest(BaseModel):
    gate_id: str = ""
    title: str = ""
    description: str = ""
    context_json: dict | None = None
    requested_by: str = ""


class SubmitReviewRequest(BaseModel):
    request_id: str
    reviewer: str
    decision: str
    rationale: str = ""


class EscalateRequest(BaseModel):
    reason: str = ""


def _ticket_to_human_request(ticket) -> dict:
    """Expose canonical governance tickets through the legacy HumanGate panel."""
    payload = getattr(ticket, "payload", {}) or {}
    return {
        "request_id": ticket.ticket_id,
        "gate_id": f"governance:{ticket.origin}:{ticket.gate_type}",
        "title": ticket.title,
        "description": ticket.summary,
        "context_json": {
            "source": "governance_ticket",
            "ticket_id": ticket.ticket_id,
            "origin": ticket.origin,
            "project_id": ticket.project_id,
            "decision_class": ticket.decision_class,
            "gate_type": ticket.gate_type,
            "priority": ticket.priority,
            "payload": payload,
            "audit_chain_ref": ticket.audit_chain_ref,
        },
        "requested_by": ticket.requested_by,
        "status": ticket.state,
        "priority": ticket.priority,
        "escalated": ticket.state == "escalated",
        "escalation_reason": "",
        "created_at": ticket.created_at,
        "updated_at": ticket.resolved_at,
    }


def _governance_ticket_request(request_id: str) -> dict | None:
    from sylion.governance.tickets import fetch_by_id

    ticket = fetch_by_id(request_id)
    return _ticket_to_human_request(ticket) if ticket is not None else None


def _sync_idea_human_gate_review(request_record: dict | None, body: SubmitReviewRequest) -> None:
    """If a HumanGate request came from IdeaVault, mirror the decision there.

    F-V10-002 fix: previously the legacy ``governance.tickets`` store kept
    the ticket as ``pending`` after the operator clicked "Potrzebne info"
    (or any other decision) on the /gates page, because we only synced the
    decision into IdeaVault. The ``/gates`` UI ``Wszystkie`` tab and the
    ``/governance/tickets`` API therefore reported a stale state. Sync the
    canonical ticket store too so all surfaces converge.
    """
    if not request_record:
        return

    # Canonical ticket store mirror — runs for every HG request, regardless
    # of whether it originated from IdeaVault, so we never let governance
    # tickets drift behind gates/human/requests.
    try:
        from sylion.governance.ticket import get_ticket_store

        ticket_id = str(request_record.get("request_id") or "").strip()
        if ticket_id:
            store = get_ticket_store()
            decision_to_status = {
                "approved": "approved",
                "rejected": "rejected",
                "needs_info": "needs_info",
            }
            new_status = decision_to_status.get(body.decision)
            if new_status:
                try:
                    store.update_status(ticket_id, status=new_status,
                                        reviewer=body.reviewer,
                                        rationale=body.rationale)
                except (AttributeError, TypeError):
                    # Fallback for older TicketStore signatures
                    if hasattr(store, "resolve") and body.decision != "needs_info":
                        store.resolve(
                            ticket_id,
                            decision=body.decision,
                            reviewer=body.reviewer,
                            reason=body.rationale,
                        )
    except Exception:                                            # noqa: BLE001
        # Mirror is best-effort; a failure here must not break the
        # primary gates/human/requests review path.
        pass

    gate_id = str(request_record.get("gate_id") or "")
    if not gate_id.startswith("idea:"):
        return
    idea_id = gate_id.split(":", 1)[1].strip()
    if not idea_id:
        return
    from sylion.cognitive.idea_vault import get_idea_vault

    get_idea_vault().record_human_gate_decision(
        idea_id,
        body.decision,
        reviewer=body.reviewer,
        rationale=body.rationale,
    )


# ---------------------------------------------------------------------------
# Gate CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_gate(body: CreateGateRequest):
    """Create a new governance gate."""
    reg = _get_gates_registry()
    return reg.create_gate(
        name=body.name,
        gate_type=body.gate_type,
        criteria_json=body.criteria_json,
        scope=body.scope,
    )


@router.put("/{gate_id}")
def update_gate(gate_id: str, body: UpdateGateRequest):
    """Update mutable fields on a gate."""
    reg = _get_gates_registry()
    fields = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.gate_type is not None:
        fields["gate_type"] = body.gate_type
    if body.criteria_json is not None:
        fields["criteria_json"] = body.criteria_json
    if body.scope is not None:
        fields["scope"] = body.scope
    if body.enabled is not None:
        fields["enabled"] = body.enabled
    result = reg.update_gate(gate_id, **fields)
    if not result:
        raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
    return result


@router.delete("/{gate_id}")
def delete_gate(gate_id: str):
    """Delete a gate and its evaluations."""
    reg = _get_gates_registry()
    ok = reg.delete_gate(gate_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
    return {"gate_id": gate_id, "removed": True}


# ---------------------------------------------------------------------------
# Gate retrieval -- static paths before dynamic /{gate_id} paths
# ---------------------------------------------------------------------------

@router.get("/list")
def list_gates(gate_type: str | None = None, scope: str | None = None):
    """List gates, optionally filtered by type and scope."""
    reg = _get_gates_registry()
    return {"gates": reg.list_gates(gate_type=gate_type, scope=scope)}


@router.get("/stats")
def get_gate_stats():
    """Aggregate statistics across all gates and evaluations."""
    reg = _get_gates_registry()
    return reg.get_gate_stats()


@router.get("/{gate_id}")
def get_gate(gate_id: str):
    """Return a gate record by ID."""
    reg = _get_gates_registry()
    result = reg.get_gate(gate_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found")
    return result


# ---------------------------------------------------------------------------
# Gate evaluation
# ---------------------------------------------------------------------------

@router.post("/{gate_id}/evaluate")
def evaluate_gate(gate_id: str, body: EvaluateGateRequest):
    """Evaluate context against a gate's criteria."""
    reg = _get_gates_registry()
    result = reg.evaluate_gate(gate_id, context_json=body.context_json)
    if not result:
        raise HTTPException(status_code=404, detail=f"Gate {gate_id} not found or disabled")
    return result


@router.get("/{gate_id}/evaluations")
def get_evaluations(gate_id: str, limit: int = 50):
    """Return recent evaluations for a gate."""
    reg = _get_gates_registry()
    return {"evaluations": reg.get_evaluations(gate_id, limit=limit)}


# ---------------------------------------------------------------------------
# HumanGate -- Request management
# ---------------------------------------------------------------------------

@router.post("/human/requests", status_code=201)
def create_human_request(body: CreateReviewRequest):
    """Create a new human review request."""
    hg = _get_human_gate()
    return hg.create_request(
        gate_id=body.gate_id,
        title=body.title,
        description=body.description,
        context_json=body.context_json,
        requested_by=body.requested_by,
    )


@router.post("/human/reviews", status_code=201)
def submit_human_review(body: SubmitReviewRequest):
    """Submit a review for a human gate request."""
    hg = _get_human_gate()
    valid_decisions = {"approved", "rejected", "needs_info"}
    if body.decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision '{body.decision}'. Must be one of {valid_decisions}",
        )
    request_record = hg.get_request(body.request_id)
    try:
        result = hg.submit_review(
            request_id=body.request_id,
            reviewer=body.reviewer,
            decision=body.decision,
            rationale=body.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result is None:
        governance_request = _governance_ticket_request(body.request_id)
        if governance_request is not None:
            from sylion.governance.tickets import resolve

            if body.decision == "needs_info":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "needs_info_not_terminal_for_governance_ticket",
                        "message": "Canonical governance tickets stay pending until approved or rejected.",
                        "request": governance_request,
                    },
                )
            try:
                changed = resolve(
                    body.request_id,
                    body.decision,
                    reason=body.rationale,
                    reviewer=body.reviewer,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if not changed:
                raise HTTPException(status_code=409, detail="Governance ticket is not pending")
            return {
                "review_id": f"governance:{body.request_id}",
                "request_id": body.request_id,
                "reviewer": body.reviewer,
                "decision": body.decision,
                "rationale": body.rationale,
                "source": "governance_ticket",
            }
    if not result:
        raise HTTPException(status_code=404, detail=f"Request {body.request_id} not found")
    _sync_idea_human_gate_review(request_record, body)
    return result


@router.get("/human/requests")
def list_human_requests(status: str | None = None, reviewer: str | None = None):
    """List human gate requests, optionally filtered by status or reviewer."""
    hg = _get_human_gate()
    requests = hg.list_requests(status=status, reviewer=reviewer)
    if reviewer:
        return {"requests": requests}

    from sylion.governance.tickets import get_ticket_store

    states = [status] if status else None
    ticket_requests = [
        _ticket_to_human_request(ticket)
        for ticket in get_ticket_store().list(states=states, limit=500)
    ]
    seen = {str(item.get("request_id")) for item in requests}
    requests.extend(
        item for item in ticket_requests
        if str(item.get("request_id")) not in seen
    )
    requests.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
    return {"requests": requests}


@router.get("/human/stats")
def get_human_stats():
    """Aggregate statistics across all human gate requests."""
    hg = _get_human_gate()
    return hg.get_stats()


@router.get("/human/requests/{request_id}")
def get_human_request(request_id: str):
    """Return a human gate request record."""
    hg = _get_human_gate()
    result = hg.get_request(request_id)
    if not result:
        result = _governance_ticket_request(request_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    return result


@router.get("/human/requests/{request_id}/reviews")
def get_human_reviews(request_id: str):
    """Return all reviews for a human gate request."""
    hg = _get_human_gate()
    return {"reviews": hg.get_reviews(request_id)}


@router.post("/human/requests/{request_id}/escalate")
def escalate_human_request(request_id: str, body: EscalateRequest):
    """Escalate a pending request."""
    hg = _get_human_gate()
    result = hg.escalate_request(request_id, reason=body.reason)
    if not result:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    return result
