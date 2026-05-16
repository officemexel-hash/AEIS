"""
SYLION API -- Roles & Permissions routes.

Endpoints for: RolesManager (create_role, update_role, delete_role, get_role,
              list_roles, assign_role, revoke_assignment, get_user_roles,
              check_permission).
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from typing import Optional

from sylion.security.rbac import requires_role

router = APIRouter(prefix="/api/v1/roles", tags=["Roles & Permissions"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_roles = None


def _get_roles():
    global _roles
    if _roles is not None:
        return _roles
    from sylion.governance.roles import get_roles_manager
    _roles = get_roles_manager()
    return _roles


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateRoleRequest(BaseModel):
    name: str
    description: str = ""
    permissions_list: Optional[list[str]] = None


class UpdateRoleRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AssignRoleRequest(BaseModel):
    role_id: str
    user_id: str
    assigned_by: str = ""


class CheckPermissionRequest(BaseModel):
    user_id: str
    permission: str


# ---------------------------------------------------------------------------
# Role CRUD -- static routes before parameterized /{role_id} routes
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_role(body: CreateRoleRequest):
    """Create a new role with optional permissions."""
    roles = _get_roles()
    try:
        return roles.create_role(
            body.name,
            description=body.description,
            permissions_list=body.permissions_list,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_roles():
    """List all roles with their permissions."""
    roles = _get_roles()
    return {"roles": roles.list_roles()}


@router.get("/{role_id}")
def get_role(role_id: str):
    """Get a single role with its permissions."""
    roles = _get_roles()
    result = roles.get_role(role_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Role {role_id} not found")
    return result


@router.put("/{role_id}")
def update_role(role_id: str, body: UpdateRoleRequest):
    """Update role metadata (name, description)."""
    roles = _get_roles()
    try:
        result = roles.update_role(
            role_id,
            name=body.name,
            description=body.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Role {role_id} not found")
    return result


@router.delete("/{role_id}")
def delete_role(role_id: str):
    """Delete a role and all associated permissions/assignments."""
    roles = _get_roles()
    deleted = roles.delete_role(role_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Role {role_id} not found")
    return {"deleted": role_id}


# ---------------------------------------------------------------------------
# Assignment management
# ---------------------------------------------------------------------------

@router.post("/assignments", status_code=201)
def assign_role(body: AssignRoleRequest,
                _user: str = Depends(requires_role("owner"))):
    """Assign a role to a user. Owner-only — privilege escalation vector."""
    roles = _get_roles()
    try:
        return roles.assign_role(
            body.role_id,
            body.user_id,
            assigned_by=body.assigned_by,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/assignments/{assignment_id}")
def revoke_assignment(assignment_id: str):
    """Revoke a role assignment."""
    roles = _get_roles()
    revoked = roles.revoke_assignment(assignment_id)
    if not revoked:
        raise HTTPException(status_code=404,
                            detail=f"Assignment {assignment_id} not found")
    return {"revoked": assignment_id}


@router.get("/users/{user_id}/roles")
def get_user_roles(user_id: str):
    """Get all roles assigned to a user."""
    roles = _get_roles()
    return {"roles": roles.get_user_roles(user_id)}


# ---------------------------------------------------------------------------
# Permission checking
# ---------------------------------------------------------------------------

@router.post("/check-permission")
def check_permission(body: CheckPermissionRequest):
    """Check if a user has a specific permission through any role."""
    roles = _get_roles()
    granted = roles.check_permission(body.user_id, body.permission)
    return {
        "user_id": body.user_id,
        "permission": body.permission,
        "granted": granted,
    }
