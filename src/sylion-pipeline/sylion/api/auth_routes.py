"""
SYLION API -- Authentication routes.

Endpoints for the AuthProvider module:
  register_provider, update_provider, deregister_provider, list_providers,
  authenticate, validate_token, revoke_token, refresh_token,
  get_session, list_sessions, get_auth_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_auth_provider = None


def _get_auth_provider():
    global _auth_provider
    if _auth_provider is not None:
        return _auth_provider
    from sylion.security.auth_provider import get_auth_provider
    _auth_provider = get_auth_provider()
    return _auth_provider


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RegisterProviderRequest(BaseModel):
    name: str
    provider_type: str = "local"
    config_json: Any = None


class UpdateProviderRequest(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    config_json: Any = None
    is_active: int | None = None


class AuthenticateRequest(BaseModel):
    provider_id: str
    credentials_json: Any = None


# ---------------------------------------------------------------------------
# Provider management -- static paths before dynamic /{provider_id} paths
# ---------------------------------------------------------------------------

@router.post("/providers", status_code=201)
def register_provider(body: RegisterProviderRequest):
    """Register a new authentication provider."""
    ap = _get_auth_provider()
    try:
        return ap.register_provider(
            name=body.name,
            provider_type=body.provider_type,
            config_json=body.config_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/providers/list")
def list_providers(provider_type: str | None = None):
    """List authentication providers, optionally filtered by type."""
    ap = _get_auth_provider()
    return {"providers": ap.list_providers(provider_type=provider_type)}


# ---------------------------------------------------------------------------
# Provider dynamic paths
# ---------------------------------------------------------------------------

@router.get("/providers/{provider_id}")
def get_provider(provider_id: str):
    """Retrieve an authentication provider by ID."""
    ap = _get_auth_provider()
    result = ap._get_provider_raw(provider_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Provider {provider_id} not found")
    return result


@router.patch("/providers/{provider_id}")
def update_provider(provider_id: str, body: UpdateProviderRequest):
    """Update an authentication provider."""
    ap = _get_auth_provider()
    try:
        result = ap.update_provider(
            provider_id=provider_id,
            name=body.name,
            provider_type=body.provider_type,
            config_json=body.config_json,
            is_active=body.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Provider {provider_id} not found")
    return result


@router.delete("/providers/{provider_id}")
def deregister_provider(provider_id: str):
    """Deregister (soft-delete) an authentication provider."""
    ap = _get_auth_provider()
    deleted = ap.deregister_provider(provider_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Provider {provider_id} not found or already deregistered")
    return {"deregistered": True, "provider_id": provider_id}


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@router.post("/authenticate")
def authenticate(body: AuthenticateRequest):
    """Authenticate against a provider. Returns session + token."""
    ap = _get_auth_provider()
    try:
        provider = ap._get_provider_raw(body.provider_id)
        if not provider:
            raise ValueError(f"Provider '{body.provider_id}' does not exist")
        credentials = body.credentials_json or {}
        if (
            provider.get("provider_type") == "local"
            and isinstance(credentials, dict)
            and credentials.get("password") is not None
        ):
            username = (
                credentials.get("username")
                or credentials.get("user_id")
                or "admin"
            )
            user = ap.authenticate(str(username), str(credentials.get("password") or ""))
            if not user:
                raise HTTPException(status_code=401, detail="Invalid local credentials")
            credentials = {
                **credentials,
                "user_id": user["user_id"],
                "username": user["username"],
                "verified_local_credentials": True,
            }
        return ap.authenticate(body.provider_id, credentials)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tokens/{token_id}/validate")
def validate_token(token_id: str):
    """Validate a token. Returns token + session info if valid."""
    ap = _get_auth_provider()
    result = ap.validate_token(token_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail="Token not found, revoked, or expired")
    return result


@router.post("/tokens/{token_id}/revoke")
def revoke_token(token_id: str):
    """Revoke a token."""
    ap = _get_auth_provider()
    revoked = ap.revoke_token(token_id)
    if not revoked:
        raise HTTPException(status_code=404,
                            detail=f"Token {token_id} not found or already revoked")
    return {"revoked": True, "token_id": token_id}


@router.post("/tokens/{token_id}/refresh")
def refresh_token(token_id: str):
    """Refresh a token (extend expiry)."""
    ap = _get_auth_provider()
    try:
        result = ap.refresh_token(token_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Token {token_id} not found")
    return result


# ---------------------------------------------------------------------------
# Sessions -- static paths before dynamic /{session_id} paths
# ---------------------------------------------------------------------------

@router.get("/sessions/list")
def list_sessions(user_id: str | None = None):
    """List active sessions, optionally filtered by user."""
    ap = _get_auth_provider()
    return {"sessions": ap.list_sessions(user_id=user_id)}


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    """Retrieve a session by ID."""
    ap = _get_auth_provider()
    result = ap.get_session(session_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Session {session_id} not found")
    return result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_auth_stats():
    """Get aggregate authentication statistics."""
    ap = _get_auth_provider()
    return ap.get_auth_stats()
