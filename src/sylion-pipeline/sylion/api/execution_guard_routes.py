"""
SYLION API -- Execution Guard routes.

Endpoints for the ExecutionGuard module:
  create_policy, update_policy, delete_policy, list_policies,
  request_approval, approve_request, deny_request,
  check_execution, get_execution_log.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/execution-guard", tags=["Execution Guard"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_execution_guard = None


def _get_execution_guard():
    global _execution_guard
    if _execution_guard is not None:
        return _execution_guard
    from sylion.security.execution_guard import get_execution_guard
    _execution_guard = get_execution_guard()
    return _execution_guard


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreatePolicyRequest(BaseModel):
    name: str
    scope: str = "global"
    rules_json: dict | str | None = None


class UpdatePolicyRequest(BaseModel):
    name: str | None = None
    scope: str | None = None
    rules_json: dict | str | None = None
    is_active: int | None = None


class RequestApprovalRequest(BaseModel):
    policy_id: str
    execution_context: dict | str


class ResolveApprovalRequest(BaseModel):
    request_id: str
    approver: str
    reason: str = ""


class CheckExecutionRequest(BaseModel):
    context: dict | str


# ---------------------------------------------------------------------------
# Policy CRUD
# ---------------------------------------------------------------------------

@router.post("/policies", status_code=201)
def create_policy(body: CreatePolicyRequest):
    """Create a new execution policy."""
    guard = _get_execution_guard()
    try:
        return guard.create_policy(
            name=body.name,
            scope=body.scope,
            rules_json=body.rules_json,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/policies/{policy_id}")
def update_policy(policy_id: str, body: UpdatePolicyRequest):
    """Update fields of an existing execution policy."""
    guard = _get_execution_guard()
    try:
        result = guard.update_policy(
            policy_id=policy_id,
            name=body.name,
            scope=body.scope,
            rules_json=body.rules_json,
            is_active=body.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Policy {policy_id} not found")
    return result


@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: str):
    """Delete an execution policy by ID."""
    guard = _get_execution_guard()
    deleted = guard.delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Policy {policy_id} not found")
    return {"deleted": True, "policy_id": policy_id}


# ---------------------------------------------------------------------------
# Policy listing -- static paths before dynamic /{...} paths
# ---------------------------------------------------------------------------

@router.get("/policies")
def list_policies(scope: str | None = None):
    """List execution policies, optionally filtered by scope."""
    guard = _get_execution_guard()
    results = guard.list_policies(scope=scope)
    return {"policies": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------

@router.post("/approvals/request", status_code=201)
def request_approval(body: RequestApprovalRequest):
    """Request execution approval against a policy."""
    guard = _get_execution_guard()
    return guard.request_approval(
        policy_id=body.policy_id,
        execution_context=body.execution_context,
    )


@router.post("/approvals/approve")
def approve_request(body: ResolveApprovalRequest):
    """Approve a pending approval request."""
    guard = _get_execution_guard()
    result = guard.approve_request(
        request_id=body.request_id,
        approver=body.approver,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Pending request {body.request_id} not found")
    return result


@router.post("/approvals/deny")
def deny_request(body: ResolveApprovalRequest):
    """Deny a pending approval request."""
    guard = _get_execution_guard()
    result = guard.deny_request(
        request_id=body.request_id,
        approver=body.approver,
        reason=body.reason,
    )
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Pending request {body.request_id} not found")
    return result


# ---------------------------------------------------------------------------
# Execution checking
# ---------------------------------------------------------------------------

@router.post("/check")
def check_execution(body: CheckExecutionRequest):
    """Evaluate execution context against active policies."""
    guard = _get_execution_guard()
    return guard.check_execution(context=body.context)


# ---------------------------------------------------------------------------
# Execution log -- static paths
# ---------------------------------------------------------------------------

@router.get("/log")
def get_execution_log(limit: int = 100):
    """Get recent execution log entries."""
    guard = _get_execution_guard()
    results = guard.get_execution_log(limit=limit)
    return {"entries": results, "count": len(results)}
