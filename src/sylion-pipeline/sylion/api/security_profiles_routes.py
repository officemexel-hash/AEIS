"""
SYLION API -- Security Profiles routes.

Endpoints for the SecurityProfilesManager module:
  create_profile, update_profile, delete_profile, get_profile,
  list_profiles, add_rule, remove_rule, get_rules,
  evaluate_profile, get_profile_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/v1/security-profiles", tags=["Security Profiles"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_security_profiles = None


def _get_security_profiles():
    global _security_profiles
    if _security_profiles is not None:
        return _security_profiles
    from sylion.security.security_profiles import get_security_profiles
    _security_profiles = get_security_profiles()
    return _security_profiles


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateProfileRequest(BaseModel):
    name: str
    level: str = "medium"
    description: str = ""
    rules_json: Any = None


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    level: str | None = None
    description: str | None = None
    rules_json: Any = None


class AddRuleRequest(BaseModel):
    rule_name: str
    rule_type: str = "allow"
    config_json: Any = None


class EvaluateProfileRequest(BaseModel):
    context_json: Any = None


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def create_profile(body: CreateProfileRequest):
    """Create a new security profile."""
    mgr = _get_security_profiles()
    try:
        return mgr.create_profile(
            name=body.name,
            level=body.level,
            description=body.description,
            rules_json=body.rules_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Static paths before dynamic /{profile_id} paths
# ---------------------------------------------------------------------------

@router.get("/list")
def list_profiles(level: str | None = None):
    """List security profiles, optionally filtered by level."""
    mgr = _get_security_profiles()
    return {"profiles": mgr.list_profiles(level=level)}


@router.get("/stats")
def get_profile_stats():
    """Get aggregate statistics about security profiles and rules."""
    mgr = _get_security_profiles()
    return mgr.get_profile_stats()


# ---------------------------------------------------------------------------
# Dynamic paths
# ---------------------------------------------------------------------------

@router.get("/{profile_id}")
def get_profile(profile_id: str):
    """Retrieve a security profile by ID."""
    mgr = _get_security_profiles()
    result = mgr.get_profile(profile_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Profile {profile_id} not found")
    return result


@router.patch("/{profile_id}")
def update_profile(profile_id: str, body: UpdateProfileRequest):
    """Update a security profile."""
    mgr = _get_security_profiles()
    try:
        result = mgr.update_profile(
            profile_id=profile_id,
            name=body.name,
            level=body.level,
            description=body.description,
            rules_json=body.rules_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Profile {profile_id} not found")
    return result


@router.delete("/{profile_id}")
def delete_profile(profile_id: str):
    """Soft-delete a security profile."""
    mgr = _get_security_profiles()
    deleted = mgr.delete_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Profile {profile_id} not found or already deleted")
    return {"deleted": True, "profile_id": profile_id}


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

@router.post("/{profile_id}/rules", status_code=201)
def add_rule(profile_id: str, body: AddRuleRequest):
    """Add a rule to a security profile."""
    mgr = _get_security_profiles()
    try:
        return mgr.add_rule(
            profile_id=profile_id,
            rule_name=body.rule_name,
            rule_type=body.rule_type,
            config_json=body.config_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{profile_id}/rules")
def get_rules(profile_id: str):
    """List all rules for a security profile."""
    mgr = _get_security_profiles()
    return {"rules": mgr.get_rules(profile_id)}


@router.delete("/rules/{rule_id}")
def remove_rule(rule_id: str):
    """Remove a rule from a security profile."""
    mgr = _get_security_profiles()
    removed = mgr.remove_rule(rule_id)
    if not removed:
        raise HTTPException(status_code=404,
                            detail=f"Rule {rule_id} not found")
    return {"removed": True, "rule_id": rule_id}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@router.post("/{profile_id}/evaluate")
def evaluate_profile(profile_id: str, body: EvaluateProfileRequest):
    """Evaluate a security profile against a context."""
    mgr = _get_security_profiles()
    try:
        return mgr.evaluate_profile(
            profile_id=profile_id,
            context_json=body.context_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
