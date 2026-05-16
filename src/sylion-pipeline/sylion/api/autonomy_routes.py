"""SYLION API -- Autonomy routes (Wave A5, RB-013).

Per-project autonomy loop attached to the governance spine. Backed by
`sylion.autonomy.stage_machine`. Every D2+ transition submits a
`GovernanceTicket` (origin='autonomy') and writes a project.autonomy_update
entry to the unified audit chain.

Endpoints:
  GET  /api/v1/autonomy/{project_id}/state    -- current phase + counters
  POST /api/v1/autonomy/{project_id}/advance  -- one transition step
  POST /api/v1/autonomy/{project_id}/steer    -- operator-driven jump
  POST /api/v1/autonomy/{project_id}/event    -- accumulate a tick
  GET  /api/v1/autonomy/{project_id}/transitions -- recent transitions
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.autonomy.stage_machine import (
    AutonomyPhase,
    AutonomyTransition,
    get_autonomy_machine,
)

log = logging.getLogger("sylion.api.autonomy_routes")

router = APIRouter(prefix="/api/v1/autonomy", tags=["autonomy"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AdvanceRequest(BaseModel):
    decision_class: str = Field("D0", description="D0..D5; D2+ submits a ticket")
    reason: str = ""
    actor: str = "autonomy"


class SteerRequest(BaseModel):
    target_phase: str = Field(..., description="phase name from PHASE_ORDER")
    actor: str = Field(..., description="operator id")
    reason: str = "operator_steer"


class TransitionResponse(BaseModel):
    transition_id: str
    project_id: str
    from_phase: str
    to_phase: str
    decision_class: str
    reason: str
    actor: str
    ticket_id: str | None
    audit_entry_id: str | None
    timestamp: float


class StateResponse(BaseModel):
    project_id: str
    phase: str
    event_count: int
    cycle_count: int
    last_transition_at: float
    ready_to_advance: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize(t: AutonomyTransition) -> dict[str, Any]:
    return {
        "transition_id": t.transition_id,
        "project_id": t.project_id,
        "from_phase": t.from_phase,
        "to_phase": t.to_phase,
        "decision_class": t.decision_class,
        "reason": t.reason,
        "actor": t.actor,
        "ticket_id": t.ticket_id,
        "audit_entry_id": t.audit_entry_id,
        "timestamp": t.timestamp,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{project_id}/state", response_model=StateResponse)
def get_state(project_id: str) -> StateResponse:
    machine = get_autonomy_machine()
    return StateResponse(**machine.get_state(project_id))


@router.post("/{project_id}/event")
def record_event(project_id: str) -> dict[str, Any]:
    machine = get_autonomy_machine()
    count = machine.record_event(project_id)
    return {"project_id": project_id, "event_count": count}


@router.post("/{project_id}/advance", response_model=TransitionResponse)
def advance(project_id: str, body: AdvanceRequest) -> TransitionResponse:
    machine = get_autonomy_machine()
    try:
        transition = machine.advance(
            project_id=project_id,
            decision_class=body.decision_class,
            reason=body.reason,
            actor=body.actor,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return TransitionResponse(**_serialize(transition))


@router.post("/{project_id}/steer", response_model=TransitionResponse)
def steer(project_id: str, body: SteerRequest) -> TransitionResponse:
    machine = get_autonomy_machine()
    try:
        target = AutonomyPhase(body.target_phase)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"unknown phase '{body.target_phase}'",
        )
    transition = machine.steer(
        project_id=project_id,
        target_phase=target,
        actor=body.actor,
        reason=body.reason,
    )
    return TransitionResponse(**_serialize(transition))


@router.get("/{project_id}/transitions", response_model=list[TransitionResponse])
def list_transitions(
    project_id: str, limit: int = 50,
) -> list[TransitionResponse]:
    machine = get_autonomy_machine()
    return [
        TransitionResponse(**_serialize(t))
        for t in machine.list_transitions(project_id, limit=limit)
    ]
