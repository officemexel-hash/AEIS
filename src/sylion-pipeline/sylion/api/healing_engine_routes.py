"""
SYLION API -- Self-Healing Engine routes.

Endpoints for the SelfHealingEngine module:
  create_rule, update_rule, delete_rule, list_rules,
  report_incident, get_incident, list_incidents,
  resolve_incident, get_healing_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/healing-engine", tags=["Self-Healing Engine"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_self_healing_engine = None


def _get_self_healing_engine():
    global _self_healing_engine
    if _self_healing_engine is not None:
        return _self_healing_engine
    from sylion.monitoring.self_healing import get_self_healing
    _self_healing_engine = get_self_healing()
    return _self_healing_engine


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateRuleRequest(BaseModel):
    name: str
    condition_json: dict
    action_json: dict
    priority: int = 0


class UpdateRuleRequest(BaseModel):
    name: str | None = None
    condition_json: dict | None = None
    action_json: dict | None = None
    priority: int | None = None


class ReportIncidentRequest(BaseModel):
    source: str
    metric: str
    value: float
    severity: str = "medium"


class ResolveIncidentRequest(BaseModel):
    resolution: str


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------

@router.post("/rules", status_code=201)
def create_rule(body: CreateRuleRequest):
    """Create a new healing rule."""
    engine = _get_self_healing_engine()
    try:
        return engine.create_rule(
            name=body.name,
            condition_json=body.condition_json,
            action_json=body.action_json,
            priority=body.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: UpdateRuleRequest):
    """Update an existing rule."""
    engine = _get_self_healing_engine()
    result = engine.update_rule(
        rule_id=rule_id,
        name=body.name,
        condition_json=body.condition_json,
        action_json=body.action_json,
        priority=body.priority,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return result


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    """Delete a rule."""
    engine = _get_self_healing_engine()
    deleted = engine.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return {"deleted": True}


@router.get("/rules")
def list_rules(priority: int | None = None):
    """List rules, optionally filtered by priority."""
    engine = _get_self_healing_engine()
    return engine.list_rules(priority=priority)


# ---------------------------------------------------------------------------
# Incidents -- static paths before dynamic /{incident_id} paths
# ---------------------------------------------------------------------------

@router.post("/incidents", status_code=201)
def report_incident(body: ReportIncidentRequest):
    """Report a new incident."""
    engine = _get_self_healing_engine()
    try:
        return engine.report_incident(
            source=body.source,
            metric=body.metric,
            value=body.value,
            severity=body.severity,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/incidents")
def list_incidents(
    status: str | None = None,
    severity: str | None = None,
):
    """List incidents with optional status and severity filters."""
    engine = _get_self_healing_engine()
    return engine.list_incidents(status=status, severity=severity)


@router.get("/stats")
def get_healing_stats():
    """Aggregate healing statistics."""
    engine = _get_self_healing_engine()
    return engine.get_healing_stats()


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str, body: ResolveIncidentRequest):
    """Manually resolve an incident."""
    engine = _get_self_healing_engine()
    result = engine.resolve_incident(
        incident_id=incident_id,
        resolution=body.resolution,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Incident {incident_id} not found")
    return result


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Get a single incident by ID."""
    engine = _get_self_healing_engine()
    result = engine.get_incident(incident_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Incident {incident_id} not found")
    return result
