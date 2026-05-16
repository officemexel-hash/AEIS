"""
SYLION API -- Self-Healing Orchestrator routes.

Endpoints for: rule CRUD, event processing, session management, statistics.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/self-healing", tags=["Self-Healing"])

# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_self_healing = None


def _get_self_healing():
    global _self_healing
    if _self_healing is not None:
        return _self_healing
    from sylion.aeis.self_healing_orchestrator import get_self_healing_orchestrator
    _self_healing = get_self_healing_orchestrator()
    return _self_healing


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateRuleRequest(BaseModel):
    name: str
    trigger_type: str
    trigger_pattern: str
    action_type: str
    action_params: Optional[str] = None
    priority: int = 0


class UpdateRuleRequest(BaseModel):
    enabled: Optional[bool] = None


class ProcessEventRequest(BaseModel):
    trigger_type: str
    event_data: dict | str


class CompleteSessionRequest(BaseModel):
    result: str = "success"


# ---------------------------------------------------------------------------
# Rule CRUD -- static routes before dynamic /{rule_id} routes
# ---------------------------------------------------------------------------

@router.post("/rules", status_code=201)
def create_rule(body: CreateRuleRequest):
    """Create a new healing rule."""
    orch = _get_self_healing()
    try:
        return orch.create_rule(
            name=body.name,
            trigger_type=body.trigger_type,
            trigger_pattern=body.trigger_pattern,
            action_type=body.action_type,
            action_params=body.action_params,
            priority=body.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rules")
def list_rules(trigger_type: Optional[str] = None,
               enabled: Optional[bool] = None):
    """List healing rules, optionally filtered by trigger_type and/or enabled."""
    orch = _get_self_healing()
    return {"rules": orch.list_rules(trigger_type=trigger_type, enabled=enabled)}


@router.get("/rules/stats")
def healing_stats():
    """Get aggregate self-healing orchestrator statistics."""
    orch = _get_self_healing()
    return orch.get_stats()


@router.get("/rules/{rule_id}")
def get_rule(rule_id: str):
    """Get a single healing rule by ID."""
    orch = _get_self_healing()
    result = orch.get_rule(rule_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return result


@router.get("/rules/{rule_id}/status")
def get_rule_status(rule_id: str):
    """Compatibility endpoint for status-only dashboard cards."""
    orch = _get_self_healing()
    result = orch.get_rule(rule_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return {
        "rule_id": rule_id,
        "enabled": result.get("enabled", False),
        "status": "enabled" if result.get("enabled", False) else "disabled",
        "rule": result,
    }


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: UpdateRuleRequest):
    """Update a healing rule (toggle enabled/disabled)."""
    orch = _get_self_healing()
    result = orch.update_rule(rule_id, enabled=body.enabled)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return result


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    """Delete a healing rule by ID."""
    orch = _get_self_healing()
    deleted = orch.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return {"deleted": rule_id}


# ---------------------------------------------------------------------------
# Event processing
# ---------------------------------------------------------------------------

@router.post("/events/process", status_code=201)
def process_event(body: ProcessEventRequest):
    """Match an incoming event against healing rules and create sessions."""
    orch = _get_self_healing()
    try:
        sessions = orch.process_event(
            trigger_type=body.trigger_type,
            event_data=body.event_data,
        )
        return {"sessions": sessions}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/rules/{rule_id}/trigger", status_code=201)
def trigger_rule(rule_id: str):
    """Compatibility endpoint for manually triggering a healing rule."""
    orch = _get_self_healing()
    rule = orch.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    sessions = orch.process_event(
        trigger_type=rule.get("trigger_type", "manual"),
        event_data={"manual": True, "rule_id": rule_id},
    )
    return {"rule_id": rule_id, "sessions": sessions, "count": len(sessions)}


# ---------------------------------------------------------------------------
# Session management -- static routes before dynamic /{session_id} routes
# ---------------------------------------------------------------------------

@router.get("/sessions")
def list_sessions(rule_id: Optional[str] = None,
                  status: Optional[str] = None,
                  limit: int = 100):
    """List healing sessions, optionally filtered by rule_id and/or status."""
    orch = _get_self_healing()
    try:
        return {"sessions": orch.list_sessions(
            rule_id=rule_id, status=status, limit=limit,
        )}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Get a single healing session by ID."""
    orch = _get_self_healing()
    result = orch.get_session(session_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Session {session_id} not found")
    return result


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: str, body: CompleteSessionRequest):
    """Mark a healing session as completed or failed."""
    orch = _get_self_healing()
    result = orch.complete_session(session_id, result=body.result)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Session {session_id} not found")
    return result
