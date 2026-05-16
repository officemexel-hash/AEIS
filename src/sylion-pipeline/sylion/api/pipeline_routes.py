"""
SYLION API -- Pipeline routes.

Endpoints for: idea submission, run execution, status tracking,
step inspection, run cancellation via PipelineController,
and state machine operations (transition, pause, resume, cancel,
decision-change, history, active runs, stats).
"""

import logging
import threading

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])
log = logging.getLogger("sylion.api.pipeline_routes")

_active_execution_lock = threading.Lock()
_active_executions: set[str] = set()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class IdeaSubmit(BaseModel):
    idea: str
    context: dict = {}


class PipelineApproval(BaseModel):
    approved: bool
    reason: str = ""


class TransitionRequest(BaseModel):
    to_state: str
    trigger: str = "manual"
    snapshot_id: str = ""
    gate_id: str = ""
    decision_id: str = ""
    metadata: dict = {}


class CancelRunRequest(BaseModel):
    reason: str = ""


class DecisionChangeRequest(BaseModel):
    snapshot_id: str
    decision_id: str


# ---------------------------------------------------------------------------
# Lazy controller accessor
# ---------------------------------------------------------------------------

_controller = None


def _get_controller():
    """Lazily initialise PipelineController with subsystem singletons.

    Imports are deferred to avoid circular-import issues at module load time.
    """
    global _controller
    if _controller is not None:
        return _controller

    from sylion.cognitive.planner import get_planner
    from sylion.cognitive.code_agent import get_code_agent
    from sylion.cognitive.llm_adapter import get_llm_adapter
    from sylion.execution.workflow_engine import get_workflow_engine
    from sylion.core.decision_gate_engine import get_decision_engine
    from sylion.core.event_bus import get_event_bus
    from sylion.core.pipeline_controller import PipelineController
    from sylion.aeis_v2.audit_profile import resolve_db_path

    llm = get_llm_adapter()
    db_path = str(resolve_db_path("sylion_aeis.db"))

    _controller = PipelineController(
        planner=get_planner(llm_adapter=llm),
        code_agent=get_code_agent(llm_adapter=llm, db_path=db_path),
        workflow_engine=get_workflow_engine(),
        decision_gate=get_decision_engine(),
        event_bus=get_event_bus(),
        db_path=db_path,
    )
    return _controller


# ---------------------------------------------------------------------------
# Lazy state machine accessor
# ---------------------------------------------------------------------------

_sm = None


def _get_sm():
    """Lazily initialise PipelineStateMachine singleton."""
    global _sm
    if _sm is not None:
        return _sm
    from sylion.pipeline.state_machine import get_pipeline_state_machine
    _sm = get_pipeline_state_machine()
    return _sm


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# 1. POST /api/v1/pipeline/ideas -- submit a new idea
@router.post("/ideas")
async def submit_idea(body: IdeaSubmit):
    """Submit an idea to the pipeline."""
    ctrl = _get_controller()
    result = ctrl.submit_idea(body.idea, body.context)
    return {
        "run_id": result.get("run_id"),
        "status": "pending",
        "idea": body.idea,
    }


# 2. POST /api/v1/pipeline/runs/{run_id}/execute -- start execution
@router.post("/runs/{run_id}/execute")
async def execute_run(run_id: str):
    """Start a pipeline run without blocking the ASGI event loop."""
    ctrl = _get_controller()
    current = ctrl.get_run(run_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if current.get("status") in {"planning", "generating", "running"}:
        return current

    with _active_execution_lock:
        if run_id in _active_executions:
            return current
        _active_executions.add(run_id)

    def _execute_in_background() -> None:
        try:
            ctrl.execute_run(run_id)
        except Exception:
            log.exception("background pipeline execution failed for run %s", run_id[:12])
        finally:
            with _active_execution_lock:
                _active_executions.discard(run_id)

    thread = threading.Thread(
        target=_execute_in_background,
        name=f"pipeline-run-{run_id[:12]}",
        daemon=True,
    )
    thread.start()

    return {
        **current,
        "status": "running",
        "execution": "background",
    }


# 3. GET /api/v1/pipeline/runs/{run_id} -- get status
@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get pipeline run status."""
    ctrl = _get_controller()
    result = ctrl.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


# 4. GET /api/v1/pipeline/runs -- list all runs
@router.get("/runs")
async def list_runs(status: str = None, limit: int = 50):
    """List pipeline runs."""
    ctrl = _get_controller()
    result = ctrl.list_runs(status=status, limit=limit)
    return {"runs": result}


# 5. POST /api/v1/pipeline/runs/{run_id}/cancel -- cancel
@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, body: CancelRunRequest = None):
    """Cancel a pipeline run (controller + state machine)."""
    ctrl = _get_controller()
    result = ctrl.cancel_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Also cancel in the state machine
    reason = body.reason if body else ""
    sm_result = {}
    try:
        sm = _get_sm()
        sm_result = sm.cancel(run_id, reason=reason)
    except ValueError:
        pass  # state machine may not track this run

    return {"cancelled": True, **result, "state_machine": sm_result}


# 6. GET /api/v1/pipeline/runs/{run_id}/steps -- get step details
@router.get("/runs/{run_id}/steps")
async def get_run_steps(run_id: str):
    """Get steps for a pipeline run."""
    ctrl = _get_controller()
    run = ctrl.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"steps": run.get("steps", [])}


# ---------------------------------------------------------------------------
# State Machine routes
# ---------------------------------------------------------------------------

# 7. POST /api/v1/pipeline/runs/{run_id}/state -- transition state
@router.post("/runs/{run_id}/state")
async def transition_state(run_id: str, body: TransitionRequest):
    """Transition a pipeline run to a new state."""
    sm = _get_sm()
    try:
        result = sm.transition(
            run_id,
            body.to_state,
            trigger=body.trigger,
            snapshot_id=body.snapshot_id or None,
            gate_id=body.gate_id or None,
            decision_id=body.decision_id or None,
            metadata=body.metadata or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# 8. GET /api/v1/pipeline/runs/{run_id}/state -- get current state
@router.get("/runs/{run_id}/state")
async def get_run_state(run_id: str):
    """Get the current state machine state for a pipeline run."""
    sm = _get_sm()
    result = sm.get_state(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found in state machine")
    return result


# 9. GET /api/v1/pipeline/runs/{run_id}/history -- state transition history
@router.get("/runs/{run_id}/history")
async def get_run_history(run_id: str):
    """Get the state transition history for a pipeline run."""
    sm = _get_sm()
    return {"history": sm.get_history(run_id)}


# 10. POST /api/v1/pipeline/runs/{run_id}/pause -- pause run
@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: str):
    """Pause a pipeline run."""
    sm = _get_sm()
    try:
        result = sm.pause(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# 11. POST /api/v1/pipeline/runs/{run_id}/resume -- resume paused run
@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str):
    """Resume a paused pipeline run."""
    sm = _get_sm()
    try:
        result = sm.resume(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# 12. POST /api/v1/pipeline/runs/{run_id}/decision-change -- handle decision change
@router.post("/runs/{run_id}/decision-change")
async def decision_change(run_id: str, body: DecisionChangeRequest):
    """Handle a decision change for a pipeline run (may roll back to planning)."""
    sm = _get_sm()
    try:
        result = sm.handle_decision_change(
            run_id,
            snapshot_id=body.snapshot_id,
            decision_id=body.decision_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# 13. GET /api/v1/pipeline/state-machine/active -- list active runs
@router.get("/state-machine/active")
async def list_active_runs():
    """List all active (non-terminal) pipeline runs."""
    sm = _get_sm()
    return {"runs": sm.list_active_runs()}


# 14. GET /api/v1/pipeline/state-machine/stats -- run statistics
@router.get("/state-machine/stats")
async def get_run_stats():
    """Get aggregate pipeline run statistics by state."""
    sm = _get_sm()
    return sm.get_run_stats()
