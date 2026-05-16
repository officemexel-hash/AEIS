"""
SYLION API -- Execution routes.

Endpoints for: tool_runner, workflow_engine, job_runner, retry_orchestrator.
"""

from fastapi import APIRouter, HTTPException

from sylion.execution.tool_runner import get_tool_runner
from sylion.execution.workflow_engine import get_workflow_engine
from sylion.execution.job_runner import get_job_runner
from sylion.execution.retry_orchestrator import get_retry_orchestrator

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


# ---------------------------------------------------------------------------
# Tool Runner
# ---------------------------------------------------------------------------

@router.post("/tools", status_code=201)
def register_tool(tool_id: str, name: str, description: str = "",
                  tool_type: str = "python"):
    """Register a new tool."""
    runner = get_tool_runner()
    return runner.register_tool(tool_id, name, description=description,
                                tool_type=tool_type)


@router.get("/tools")
def list_tools(active_only: bool = True):
    """List all registered tools."""
    runner = get_tool_runner()
    return {"tools": runner.list_tools(active_only=active_only)}


@router.get("/tools/{tool_id}")
def get_tool(tool_id: str):
    """Get a tool by ID."""
    runner = get_tool_runner()
    tool = runner.get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
    return tool


@router.post("/tools/{tool_id}/execute", status_code=201)
def execute_tool(tool_id: str):
    """Execute a registered tool through ToolRunner."""
    runner = get_tool_runner()
    result = runner.execute(tool_id)
    if "error" in result and result.get("result") == "error":
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/tools/executions")
def list_tool_executions(tool_id: str | None = None, limit: int = 100):
    """List tool execution records."""
    runner = get_tool_runner()
    return {"executions": runner.list_executions(tool_id=tool_id, limit=limit)}


@router.get("/tools/executions/{exec_id}")
def get_tool_execution(exec_id: str):
    """Get a single tool execution by ID."""
    runner = get_tool_runner()
    execution = runner.get_execution(exec_id)
    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution {exec_id} not found")
    return execution


# ---------------------------------------------------------------------------
# Workflow Engine
# ---------------------------------------------------------------------------

@router.post("/workflows", status_code=201)
def create_workflow(name: str, description: str = "",
                    steps: str = "[]"):
    """Create a new workflow definition."""
    import json
    engine = get_workflow_engine()
    step_list = json.loads(steps) if isinstance(steps, str) else []
    return engine.create_workflow(name, description=description, steps=step_list)


@router.get("/workflows")
def list_workflows(status: str | None = None):
    """List workflows."""
    engine = get_workflow_engine()
    return {"workflows": engine.list_workflows(status=status)}


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    """Get a workflow by ID."""
    engine = get_workflow_engine()
    wf = engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return wf


@router.post("/workflows/{workflow_id}/run", status_code=201)
def run_workflow(workflow_id: str):
    """Execute a workflow."""
    engine = get_workflow_engine()
    result = engine.run_workflow(workflow_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/workflows/runs")
def list_workflow_runs(workflow_id: str | None = None, limit: int = 100):
    """List workflow runs."""
    engine = get_workflow_engine()
    return {"runs": engine.list_runs(workflow_id=workflow_id, limit=limit)}


@router.get("/workflows/runs/{run_id}")
def get_workflow_run(run_id: str):
    """Get a workflow run by ID."""
    engine = get_workflow_engine()
    run = engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


# ---------------------------------------------------------------------------
# Job Runner
# ---------------------------------------------------------------------------

@router.post("/jobs", status_code=201)
def submit_job(job_type: str, priority: int = 0):
    """Submit a new job to the queue."""
    runner = get_job_runner()
    return runner.submit(job_type, priority=priority)


@router.get("/jobs")
def list_jobs(status: str | None = None, limit: int = 100):
    """List jobs with optional status filter."""
    runner = get_job_runner()
    return {"jobs": runner.list_jobs(status=status, limit=limit)}


@router.get("/jobs/next")
def get_next_job():
    """Get the next highest-priority queued job."""
    runner = get_job_runner()
    job = runner.get_next()
    if not job:
        return {"job": None, "message": "No queued jobs"}
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Get a job by ID."""
    runner = get_job_runner()
    job = runner.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/jobs/{job_id}/complete")
def complete_job(job_id: str, result: str = ""):
    """Mark a job as completed."""
    runner = get_job_runner()
    ok = runner.complete(job_id, result=result)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"completed": job_id}


@router.post("/jobs/{job_id}/fail")
def fail_job(job_id: str, error: str = ""):
    """Mark a job as failed."""
    runner = get_job_runner()
    ok = runner.fail(job_id, error=error)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"failed": job_id}


@router.get("/jobs/stats")
def job_stats():
    """Get job queue statistics."""
    runner = get_job_runner()
    return runner.get_stats()


# ---------------------------------------------------------------------------
# Retry Orchestrator
# ---------------------------------------------------------------------------

@router.post("/retry/policies", status_code=201)
def create_retry_policy(name: str, max_retries: int = 3,
                        base_delay_ms: int = 1000, max_delay_ms: int = 60000,
                        backoff_factor: float = 2.0, jitter: float = 0.1):
    """Create a retry policy."""
    orch = get_retry_orchestrator()
    return orch.create_policy(
        name, max_retries=max_retries,
        base_delay_ms=base_delay_ms, max_delay_ms=max_delay_ms,
        backoff_factor=backoff_factor, jitter=jitter,
    )


@router.get("/retry/policies")
def list_retry_policies():
    orch = get_retry_orchestrator()
    return {"policies": orch.list_policies()}


@router.post("/retry/attempts", status_code=201)
def record_retry_attempt(operation_type: str, operation_id: str,
                         error_type: str = "unknown",
                         error_message: str = ""):
    """Record a retry attempt."""
    orch = get_retry_orchestrator()
    return orch.register_attempt(operation_type, operation_id,
                                error_type=error_type,
                                error_message=error_message)


@router.get("/retry/attempts")
def get_retry_attempts(operation_type: str = "", limit: int = 20):
    """Get recent retry attempts."""
    orch = get_retry_orchestrator()
    kwargs = {"limit": limit}
    if operation_type:
        kwargs["operation_type"] = operation_type
    return {"attempts": orch.get_attempts(**kwargs)}


@router.get("/retry/dlq")
def get_dead_letter_queue():
    orch = get_retry_orchestrator()
    return {"entries": orch.get_dlq_entries()}


@router.get("/retry/stats")
def get_retry_stats():
    orch = get_retry_orchestrator()
    return orch.get_stats()


# ---------------------------------------------------------------------------
# Execution Planner
# ---------------------------------------------------------------------------

from sylion.execution.execution_planner import get_execution_planner as _get_planner


@router.post("/plans")
def create_plan(name: str, description: str = "", created_by: str = ""):
    return _get_planner().create_plan(name, description or None, created_by or None)


@router.get("/plans")
def list_plans(status: str = None, limit: int = 50, offset: int = 0):
    return {"plans": _get_planner().list_plans(status=status, limit=limit, offset=offset)}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str):
    result = _get_planner().get_plan(plan_id)
    if not result:
        raise HTTPException(404, "Plan not found")
    return result


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: str):
    return {"deleted": _get_planner().delete_plan(plan_id)}


@router.post("/plans/{plan_id}/steps")
def add_step(plan_id: str, name: str, step_type: str = "tool_call", config: str = "", order: int = None):
    import json as _json
    cfg = _json.loads(config) if config else None
    return _get_planner().add_step(plan_id, name, step_type, config=cfg, order=order)


@router.post("/plans/{plan_id}/start")
def start_plan(plan_id: str):
    return _get_planner().start_plan(plan_id)


@router.post("/plans/{plan_id}/cancel")
def cancel_plan(plan_id: str):
    return _get_planner().cancel_plan(plan_id)


@router.get("/plans/{plan_id}/progress")
def get_plan_progress(plan_id: str):
    try:
        return _get_planner().get_plan_progress(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/plans/{plan_id}/order")
def get_execution_order(plan_id: str):
    return {"steps": _get_planner().get_execution_order(plan_id)}


@router.post("/steps/{step_id}/complete")
def complete_step(step_id: str, result: str = ""):
    return _get_planner().complete_step(step_id, result=result or None)


@router.post("/steps/{step_id}/fail")
def fail_step(step_id: str, error: str = ""):
    return _get_planner().fail_step(step_id, error=error or None)
