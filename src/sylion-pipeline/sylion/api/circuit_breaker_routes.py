"""
SYLION API -- Circuit Breaker routes.

Endpoints for the CircuitBreakerManager module:
  create_breaker, get_breaker, list_breakers,
  record_success, record_failure,
  get_state, force_open, force_close,
  get_events, get_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/circuit-breakers", tags=["Circuit Breakers"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_circuit_breaker = None


def _get_circuit_breaker():
    global _circuit_breaker
    if _circuit_breaker is not None:
        return _circuit_breaker
    from sylion.monitoring.circuit_breaker import get_circuit_breaker
    _circuit_breaker = get_circuit_breaker()
    return _circuit_breaker


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateBreakerRequest(BaseModel):
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max: int = 3


# ---------------------------------------------------------------------------
# Create / List
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_breaker(body: CreateBreakerRequest):
    """Create a new circuit breaker."""
    cb = _get_circuit_breaker()
    return cb.create_breaker(
        name=body.name,
        failure_threshold=body.failure_threshold,
        recovery_timeout=body.recovery_timeout,
        half_open_max=body.half_open_max,
    )


@router.get("/list")
def list_breakers(status: str | None = None):
    """List breakers, optionally filtered by effective state."""
    cb = _get_circuit_breaker()
    return {"breakers": cb.list_breakers(status=status)}


@router.get("/stats")
def get_stats():
    """Aggregate statistics across all breakers."""
    cb = _get_circuit_breaker()
    return cb.get_stats()


# ---------------------------------------------------------------------------
# Single breaker -- static paths before dynamic /{breaker_id} paths
# ---------------------------------------------------------------------------

@router.get("/{breaker_id}")
def get_breaker(breaker_id: str):
    """Get a single breaker with full state info."""
    cb = _get_circuit_breaker()
    result = cb.get_breaker(breaker_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Breaker {breaker_id} not found")
    return result


@router.get("/{breaker_id}/state")
def get_state(breaker_id: str):
    """Get the effective state of a breaker."""
    cb = _get_circuit_breaker()
    state = cb.get_state(breaker_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Breaker {breaker_id} not found")
    return {"breaker_id": breaker_id, "state": state}


@router.get("/{breaker_id}/events")
def get_events(breaker_id: str, limit: int = 100):
    """Get event history for a breaker."""
    cb = _get_circuit_breaker()
    return {"events": cb.get_events(breaker_id, limit=limit)}


# ---------------------------------------------------------------------------
# Record success / failure
# ---------------------------------------------------------------------------

@router.post("/{breaker_id}/success")
def record_success(breaker_id: str):
    """Record a successful call against a breaker."""
    cb = _get_circuit_breaker()
    try:
        return cb.record_success(breaker_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{breaker_id}/failure")
def record_failure(breaker_id: str):
    """Record a failed call against a breaker."""
    cb = _get_circuit_breaker()
    try:
        return cb.record_failure(breaker_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Force state transitions
# ---------------------------------------------------------------------------

@router.post("/{breaker_id}/force-open")
def force_open(breaker_id: str):
    """Manually force a breaker to OPEN state."""
    cb = _get_circuit_breaker()
    ok = cb.force_open(breaker_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Breaker {breaker_id} not found")
    return {"breaker_id": breaker_id, "state": "open"}


@router.post("/{breaker_id}/force-close")
def force_close(breaker_id: str):
    """Manually force a breaker to CLOSED state."""
    cb = _get_circuit_breaker()
    ok = cb.force_close(breaker_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Breaker {breaker_id} not found")
    return {"breaker_id": breaker_id, "state": "closed"}
