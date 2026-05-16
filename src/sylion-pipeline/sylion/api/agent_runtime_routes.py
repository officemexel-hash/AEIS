"""
SYLION API -- Agent Runtime routes.

Endpoints for agent registration, execution, monitoring, and lifecycle management.
"""

from fastapi import APIRouter, Depends, HTTPException

from sylion.cognitive.agent_runtime import get_agent_runtime
from sylion.core.event_bus import SylionEvent, get_event_bus
from sylion.security.rbac import requires_role

router = APIRouter(prefix="/api/v1/agents", tags=["Agent Runtime"])


def _emit_agent_event(topic: str, payload: dict) -> None:
    safe_payload = {
        key: value
        for key, value in payload.items()
        if value is not None and not str(key).lower().endswith(("_key", "_secret", "_token", "password"))
    }
    try:
        get_event_bus().publish(
            SylionEvent(
                event_id="",
                topic=topic,
                payload={
                    "message": safe_payload.get("message") or topic,
                    "severity": safe_payload.get("severity", "info"),
                    "host": "local",
                    **safe_payload,
                },
                source_module="agent_runtime",
            )
        )
    except Exception:
        # Agent operations must not fail only because event telemetry is down.
        pass


# ---------------------------------------------------------------------------
# Registration & Lifecycle
# ---------------------------------------------------------------------------

@router.post("/register", status_code=201)
def register_agent(
    name: str,
    agent_type: str = "custom",
    provider: str = "openai",
    model_id: str = "",
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    tools: str = "",
    capabilities: str = "",
):
    """Register a new agent in the runtime."""
    rt = get_agent_runtime()
    tool_list = [t.strip() for t in tools.split(",") if t.strip()]
    cap_list = [c.strip() for c in capabilities.split(",") if c.strip()]
    try:
        result = rt.register_agent(
            name=name,
            agent_type=agent_type,
            provider=provider,
            model_id=model_id,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tool_list,
            capabilities=cap_list,
        )
        _emit_agent_event(
            "agent.registered",
            {
                "message": f"Agent registered: {name}",
                "agent_id": result.get("agent_id"),
                "agent_type": result.get("agent_type") or agent_type,
                "provider": result.get("provider") or provider,
                "model": result.get("model_id") or model_id,
                "role": result.get("agent_type") or agent_type,
                "status": result.get("status"),
            },
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{agent_id}")
def update_agent(
    agent_id: str,
    name: str | None = None,
    agent_type: str | None = None,
    provider: str | None = None,
    model_id: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    tools: str | None = None,
    capabilities: str | None = None,
    status: str | None = None,
):
    """Update an existing agent's configuration."""
    rt = get_agent_runtime()
    updates: dict = {}
    if name is not None:
        updates["name"] = name
    if agent_type is not None:
        updates["agent_type"] = agent_type
    if provider is not None:
        updates["provider"] = provider
    if model_id is not None:
        updates["model_id"] = model_id
    if system_prompt is not None:
        updates["system_prompt"] = system_prompt
    if max_tokens is not None:
        updates["max_tokens"] = max_tokens
    if temperature is not None:
        updates["temperature"] = temperature
    if tools is not None:
        updates["tools"] = [t.strip() for t in tools.split(",") if t.strip()]
    if capabilities is not None:
        updates["capabilities"] = [c.strip() for c in capabilities.split(",") if c.strip()]
    if status is not None:
        updates["status"] = status
    result = rt.update_agent(agent_id, **updates)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    _emit_agent_event(
        "agent.updated",
        {
            "message": f"Agent updated: {result.get('name', agent_id)}",
            "agent_id": agent_id,
            "agent_type": result.get("agent_type"),
            "provider": result.get("provider"),
            "model": result.get("model_id"),
            "role": result.get("agent_type"),
            "status": result.get("status"),
            "changed_fields": ",".join(sorted(updates.keys())),
        },
    )
    return result


@router.delete("/{agent_id}")
def deregister_agent(agent_id: str):
    """Remove an agent from the runtime."""
    rt = get_agent_runtime()
    result = rt.deregister_agent(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    _emit_agent_event("agent.deleted", {"message": f"Agent deleted: {agent_id}", "agent_id": agent_id})
    return result


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

@router.get("/list")
def list_agents(status: str | None = None, agent_type: str | None = None):
    """List registered agents, optionally filtered by status and type."""
    rt = get_agent_runtime()
    return {"agents": rt.list_agents(status=status, agent_type=agent_type)}


@router.get("")
@router.get("/")
def list_agents_root(status: str | None = None, agent_type: str | None = None):
    """Root alias for operator/API clients that probe ``/api/v1/agents``."""
    return list_agents(status=status, agent_type=agent_type)


@router.get("/stats")
def get_runtime_stats():
    """Get aggregate runtime statistics."""
    rt = get_agent_runtime()
    return rt.get_runtime_stats()


@router.get("/executions")
def list_executions(
    agent_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
):
    """List recent task executions."""
    rt = get_agent_runtime()
    return {"executions": rt.list_executions(agent_id=agent_id, status=status, limit=limit)}


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str):
    """Get details of a specific execution."""
    rt = get_agent_runtime()
    result = rt.get_execution(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found")
    return result


@router.post("/executions/{execution_id}/cancel")
def cancel_execution(execution_id: str,
                     _user: str = Depends(requires_role("operator"))):
    """Cancel a running execution. Operator-gated."""
    rt = get_agent_runtime()
    result = rt.cancel_execution(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Execution {execution_id} not found or not cancellable")
    _emit_agent_event(
        "agent.execution_cancelled",
        {
            "message": f"Agent execution cancelled: {execution_id}",
            "execution_id": execution_id,
            "agent_id": result.get("agent_id") if isinstance(result, dict) else None,
            "status": result.get("status") if isinstance(result, dict) else "cancelled",
            "severity": "warn",
        },
    )
    return result


# ---------------------------------------------------------------------------
# Per-agent operations (parameterized routes after static routes)
# ---------------------------------------------------------------------------

@router.get("/{agent_id}")
def get_agent(agent_id: str):
    """Get a single agent by ID."""
    rt = get_agent_runtime()
    result = rt.get_agent(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return result


@router.post("/{agent_id}/execute", status_code=201)
def execute_task(agent_id: str, task: str, context: str = ""):
    """Execute a task on the specified agent."""
    rt = get_agent_runtime()
    try:
        _emit_agent_event(
            "agent.execution_started",
            {
                "message": f"Agent execution started: {agent_id}",
                "agent_id": agent_id,
                "task_id": task[:80],
                "status": "started",
            },
        )
        result = rt.execute_task(agent_id, task, context=context or None)
        _emit_agent_event(
            "agent.execution_completed",
            {
                "message": f"Agent execution completed: {agent_id}",
                "agent_id": agent_id,
                "execution_id": result.get("execution_id") if isinstance(result, dict) else None,
                "status": result.get("status") if isinstance(result, dict) else "completed",
            },
        )
        return result
    except ValueError as e:
        _emit_agent_event(
            "agent.execution_failed",
            {"message": f"Agent execution failed: {agent_id}", "agent_id": agent_id, "severity": "error", "status": "failed"},
        )
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        _emit_agent_event(
            "agent.execution_failed",
            {"message": f"Agent execution failed: {agent_id}", "agent_id": agent_id, "severity": "error", "status": "missing_agent"},
        )
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{agent_id}/logs")
def get_logs(agent_id: str, execution_id: str | None = None):
    """Get logs for an agent, optionally filtered by execution."""
    rt = get_agent_runtime()
    if execution_id:
        return {"logs": rt.get_logs(execution_id)}
    # Return logs for all executions of this agent
    executions = rt.list_executions(agent_id=agent_id, limit=50)
    all_logs = []
    for ex in executions:
        all_logs.extend(rt.get_logs(ex["execution_id"]))
    return {"logs": all_logs}


@router.get("/{agent_id}/stats")
def get_agent_stats(agent_id: str):
    """Get statistics for a specific agent."""
    rt = get_agent_runtime()
    result = rt.get_agent_stats(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return result
