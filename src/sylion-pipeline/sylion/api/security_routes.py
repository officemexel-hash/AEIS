"""
SYLION API -- Security routes.

Endpoints for: auth_provider, session_broker, audit_sink, execution_guard,
profile_manager.
"""

from fastapi import APIRouter, HTTPException

from sylion.security.auth_provider import get_auth_provider
from sylion.security.session_broker import get_session_broker
from sylion.security.audit_sink import get_audit_sink
from sylion.security.execution_guard import get_execution_guard

try:
    from sylion.security.profile_manager import get_security_profile_manager
    _HAS_PROFILE_MANAGER = True
except ImportError:
    _HAS_PROFILE_MANAGER = False

try:
    from sylion.security.security_profiles import (
        get_security_profile_manager as get_hardened_profile_manager,
    )
    _HAS_HARDENED_PROFILES = True
except ImportError:
    _HAS_HARDENED_PROFILES = False

router = APIRouter(prefix="/api/v1/security", tags=["security"])


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "security",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Auth Provider
# ---------------------------------------------------------------------------

@router.post("/users", status_code=201)
def create_user(user_id: str, username: str, password_hash: str,
                role: str = "viewer"):
    """Create a new user."""
    auth = get_auth_provider()
    try:
        return auth.create_user(user_id, username, password_hash, role=role)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/users")
def list_users(active_only: bool = True):
    """List users."""
    auth = get_auth_provider()
    return {"users": auth.list_users(active_only=active_only)}


@router.get("/auth/users")
def list_auth_users(active_only: bool = True):
    """Compatibility alias used by auth-provider dashboard panels."""
    return list_users(active_only=active_only)


@router.get("/users/{user_id}")
def get_user(user_id: str):
    """Get a user by ID."""
    auth = get_auth_provider()
    user = auth.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


@router.post("/auth/login")
def authenticate(username: str, password_hash: str):
    """Authenticate a user by credentials."""
    auth = get_auth_provider()
    user = auth.authenticate(username, password_hash)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"authenticated": True, "user_id": user["user_id"], "role": user["role"]}


@router.post("/auth/sessions", status_code=201)
def create_auth_session(user_id: str, token: str, expires_at: float):
    """Create a new auth session."""
    auth = get_auth_provider()
    return auth.create_session(user_id, token, expires_at)


@router.post("/auth/validate-token")
def validate_token(token: str):
    """Validate a session token."""
    auth = get_auth_provider()
    session = auth.validate_token(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"valid": True, "session_id": session["session_id"]}


@router.delete("/auth/sessions/{session_id}")
def revoke_auth_session(session_id: str):
    """Revoke an auth session."""
    auth = get_auth_provider()
    ok = auth.revoke_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"revoked": session_id}


# ---------------------------------------------------------------------------
# Session Broker
# ---------------------------------------------------------------------------

@router.post("/sessions", status_code=201)
def create_session(user_id: str, token: str,
                   timeout: int = 3600, ip_address: str = ""):
    """Create a managed session."""
    broker = get_session_broker()
    return broker.create("", user_id=user_id, token=token,
                         timeout=timeout, ip_address=ip_address)


@router.get("/sessions")
def list_sessions(user_id: str | None = None):
    """List managed sessions."""
    broker = get_session_broker()
    return {"sessions": broker.list_sessions(user_id=user_id)}


@router.post("/sessions/{session_id}/validate")
def validate_session(session_id: str):
    """Validate a managed session (checks timeout)."""
    broker = get_session_broker()
    session = broker.validate(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session invalid or expired")
    return session


@router.post("/sessions/{session_id}/refresh")
def refresh_session(session_id: str):
    """Refresh a session's activity timestamp."""
    broker = get_session_broker()
    ok = broker.refresh(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"refreshed": session_id}


@router.delete("/sessions/{session_id}")
def destroy_session(session_id: str):
    """Destroy a managed session."""
    broker = get_session_broker()
    ok = broker.destroy(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"destroyed": session_id}


@router.post("/sessions/cleanup")
def cleanup_expired_sessions():
    """Remove all expired sessions."""
    broker = get_session_broker()
    removed = broker.cleanup_expired()
    return {"removed": removed}


@router.get("/sessions/stats")
def session_stats():
    """Get session statistics."""
    broker = get_session_broker()
    return broker.get_stats()


# ---------------------------------------------------------------------------
# Audit Sink
# ---------------------------------------------------------------------------

@router.post("/audit", status_code=201)
def log_audit(event_type: str, actor: str = "",
              resource: str = "", action: str = "",
              result: str = "", ip: str = ""):
    """Record an audit log entry."""
    sink = get_audit_sink()
    entry = sink.log(
        event_type,
        actor=actor,
        resource=resource,
        action=action,
        result=result,
        details={"ip": ip} if ip else None,
    )
    return {"audit_id": entry["entry_id"], "entry": entry}


@router.get("/audit")
def query_audit(event_type: str | None = None,
                actor: str | None = None,
                since: float | None = None,
                limit: int = 100):
    """Query the audit log."""
    sink = get_audit_sink()
    return {"entries": sink.query(event_type=event_type, actor=actor,
                                  since=since, limit=limit)}


@router.get("/audit/stats")
def audit_stats():
    """Get audit statistics."""
    sink = get_audit_sink()
    return sink.get_stats()


@router.get("/audit/export")
def export_audit(since: float | None = None, limit: int = 10000):
    """Export audit entries."""
    sink = get_audit_sink()
    return {"entries": sink.export(since=since, limit=limit)}


# ---------------------------------------------------------------------------
# Execution Guard
# ---------------------------------------------------------------------------

@router.post("/guard/rules", status_code=201)
def add_guard_rule(name: str, action: str = "allow",
                   resource_pattern: str = "*", priority: int = 0,
                   rule_id: str = ""):
    """Add a guard rule."""
    guard = get_execution_guard()
    return guard.add_rule(rule_id, name, action=action,
                          resource_pattern=resource_pattern,
                          priority=priority)


@router.get("/guard/rules")
def list_guard_rules(enabled_only: bool = True):
    """List guard rules."""
    guard = get_execution_guard()
    return {"rules": guard.list_rules(enabled_only=enabled_only)}


@router.get("/guard/rules/{rule_id}")
def get_guard_rule(rule_id: str):
    """Get a guard rule by ID."""
    guard = get_execution_guard()
    rule = guard.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")
    return rule


@router.post("/guard/check")
def guard_check(resource: str, action: str):
    """Check if a resource+action is allowed."""
    guard = get_execution_guard()
    result = guard.check(resource, action)
    return {"resource": resource, "action": action, "result": result}


@router.get("/guard/checks")
def list_guard_checks(resource: str | None = None, limit: int = 50):
    """List guard check history."""
    guard = get_execution_guard()
    return {"checks": guard.get_checks(resource=resource, limit=limit)}


# ---------------------------------------------------------------------------
# Security Profile Manager (Phase 4)
# ---------------------------------------------------------------------------

@router.post("/profiles", status_code=201)
def define_security_profile(name: str, level: str,
                            rules: str = "{}"):
    """Define a new security profile."""
    if not _HAS_PROFILE_MANAGER:
        raise HTTPException(status_code=501,
                            detail="profile_manager module not available")
    import json
    mgr = get_security_profile_manager()
    parsed = json.loads(rules) if isinstance(rules, str) else None
    return mgr.define_profile(name, level, rules=parsed)


@router.get("/profiles")
def list_security_profiles(level: str | None = None):
    """List security profiles."""
    if not _HAS_PROFILE_MANAGER:
        raise HTTPException(status_code=501,
                            detail="profile_manager module not available")
    mgr = get_security_profile_manager()
    return {"profiles": mgr.list_profiles(level=level)}


@router.get("/profiles/{profile_name_or_id}")
def get_security_profile(profile_name_or_id: str):
    """Get a security profile by name or ID."""
    if not _HAS_PROFILE_MANAGER:
        raise HTTPException(status_code=501,
                            detail="profile_manager module not available")
    mgr = get_security_profile_manager()
    result = mgr.get_profile(profile_name_or_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Profile {profile_name_or_id} not found")
    return result


@router.post("/profiles/assign")
def assign_security_profile(module_id: str, profile: str):
    """Assign a security profile to a module."""
    if not _HAS_PROFILE_MANAGER:
        raise HTTPException(status_code=501,
                            detail="profile_manager module not available")
    mgr = get_security_profile_manager()
    return mgr.assign_profile(module_id, profile)


@router.post("/profiles/hot-swap")
def hot_swap_security_profile(module_id: str, new_profile: str):
    """Hot-swap a module's security profile."""
    if not _HAS_PROFILE_MANAGER:
        raise HTTPException(status_code=501,
                            detail="profile_manager module not available")
    mgr = get_security_profile_manager()
    return mgr.hot_swap_profile(module_id, new_profile)


@router.get("/profiles/audit")
def get_profile_audit_trail(module_id: str | None = None,
                            limit: int = 100):
    """Get the security profile audit trail."""
    if not _HAS_PROFILE_MANAGER:
        raise HTTPException(status_code=501,
                            detail="profile_manager module not available")
    mgr = get_security_profile_manager()
    return {"audit_trail": mgr.get_audit_trail(module_id=module_id,
                                               limit=limit)}


@router.get("/profiles/stats")
def profile_manager_stats():
    """Get security profile manager statistics."""
    if not _HAS_PROFILE_MANAGER:
        raise HTTPException(status_code=501,
                            detail="profile_manager module not available")
    mgr = get_security_profile_manager()
    return mgr.get_stats()


# ---------------------------------------------------------------------------
# Hardened Security Profiles (Phase 5)
# Action validation, active profile management, prod-strict hardening.
# ---------------------------------------------------------------------------

@router.get("/hardened-profiles")
def list_hardened_profiles():
    """List all hardened security profiles (dev-light, standard, prod-strict)."""
    if not _HAS_HARDENED_PROFILES:
        raise HTTPException(status_code=501,
                            detail="security_profiles module not available")
    mgr = get_hardened_profile_manager()
    return {"profiles": mgr.list_profiles()}


@router.get("/hardened-profiles/active")
def get_active_hardened_profile():
    """Get the currently active hardened security profile."""
    if not _HAS_HARDENED_PROFILES:
        raise HTTPException(status_code=501,
                            detail="security_profiles module not available")
    mgr = get_hardened_profile_manager()
    profile = mgr.get_active_profile()
    return {"name": profile.name, "level": profile.level, "rules": profile.rules}


@router.get("/hardened-profiles/{name}")
def get_hardened_profile(name: str):
    """Get a specific hardened security profile by name."""
    if not _HAS_HARDENED_PROFILES:
        raise HTTPException(status_code=501,
                            detail="security_profiles module not available")
    mgr = get_hardened_profile_manager()
    profile = mgr.get_profile(name)
    if profile is None:
        raise HTTPException(status_code=404,
                            detail=f"Profile '{name}' not found")
    return {"name": profile.name, "level": profile.level, "rules": profile.rules}


@router.post("/hardened-profiles/active")
def set_active_hardened_profile(body: dict):
    """Set the active hardened security profile.

    Body: {"name": "dev-light" | "standard" | "prod-strict"}
    """
    if not _HAS_HARDENED_PROFILES:
        raise HTTPException(status_code=501,
                            detail="security_profiles module not available")
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400,
                            detail="Request body must include 'name'")
    mgr = get_hardened_profile_manager()
    result = mgr.set_active_profile(name)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/hardened-profiles/validate")
def validate_hardened_action(body: dict):
    """Validate an action against a hardened security profile.

    Body: {"profile_name": "...", "action_type": "...", "resource": "..."}
    """
    if not _HAS_HARDENED_PROFILES:
        raise HTTPException(status_code=501,
                            detail="security_profiles module not available")
    profile_name = body.get("profile_name", "")
    action_type = body.get("action_type", "")
    resource = body.get("resource", "")
    if not profile_name or not action_type or not resource:
        raise HTTPException(
            status_code=400,
            detail="Body must include profile_name, action_type, and resource",
        )
    mgr = get_hardened_profile_manager()
    return mgr.validate_action(profile_name, action_type, resource)


# ---------------------------------------------------------------------------
# Security Audit
# ---------------------------------------------------------------------------

from sylion.security.security_audit import get_security_auditor as _get_audit


@router.post("/audit/events")
def log_security_event(event_type: str, severity: str, source: str,
                       description: str = "", metadata: str = ""):
    import json as _json
    md = _json.loads(metadata) if metadata else None
    return _get_audit().log_event(event_type, severity, source, description or None, metadata=md)


@router.get("/audit/events")
def list_security_events(event_type: str = None, severity: str = None,
                         source: str = None, limit: int = 100):
    return {"events": _get_audit().get_events(event_type=event_type, severity=severity,
                                               source=source, limit=limit)}


@router.get("/audit/events/{event_id}")
def get_security_event(event_id: str):
    result = _get_audit().get_event(event_id)
    if not result:
        raise HTTPException(404, "Event not found")
    return result


@router.post("/audit/alerts")
def create_security_alert(title: str, description: str, severity: str,
                          source: str = ""):
    return _get_audit().create_alert(title, description, severity, source or None)


@router.get("/audit/alerts")
def list_security_alerts(severity: str = None, acknowledged: bool = None):
    return {"alerts": _get_audit().get_alerts(severity=severity, acknowledged=acknowledged)}


@router.post("/audit/alerts/{alert_id}/acknowledge")
def acknowledge_security_alert(alert_id: str, acknowledged_by: str = "system"):
    result = _get_audit().acknowledge_alert(alert_id, acknowledged_by)
    if not result:
        raise HTTPException(404, "Alert not found")
    return result


@router.post("/audit/access")
def log_access(user_id: str, resource: str, action: str,
              allowed: bool = True, ip_address: str = ""):
    return _get_audit().log_access(user_id, resource, action, allowed, ip_address or None)


@router.get("/audit/access")
def list_access_log(user_id: str = None, resource: str = None, limit: int = 100):
    return {"entries": _get_audit().get_access_log(user_id=user_id, resource=resource, limit=limit)}


@router.get("/audit/stats")
def get_security_audit_aggregator_stats():
    return _get_audit().get_security_stats()


@router.get("/audit/timeline")
def get_security_timeline(limit: int = 50):
    return {"timeline": _get_audit().get_timeline(limit=limit)}


# ---------------------------------------------------------------------------
# Session Manager -- lazy accessor
# ---------------------------------------------------------------------------

_session_mgr = None


def _get_session_mgr():
    global _session_mgr
    if _session_mgr is not None:
        return _session_mgr
    from sylion.security.session_manager import get_session_manager
    _session_mgr = get_session_manager()
    return _session_mgr


# ---------------------------------------------------------------------------
# Session Manager -- endpoints
# (static routes before parameterized /{user_id} /{session_id} routes)
# ---------------------------------------------------------------------------

@router.post("/session-manager/users", status_code=201)
def create_session_manager_user(username: str, email: str,
                                role: str = "viewer",
                                password_hash: str = ""):
    """Create a new user via the session manager."""
    mgr = _get_session_mgr()
    try:
        return mgr.create_user(username, email, role=role,
                               password_hash=password_hash)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session-manager/users")
def list_session_manager_users(role: str | None = None,
                               is_active: int | None = None):
    """List users via the session manager."""
    return {"users": _get_session_mgr().list_users(role=role,
                                                    is_active=is_active)}


@router.put("/session-manager/users/{user_id}")
def update_session_manager_user(user_id: str, email: str | None = None,
                                role: str | None = None,
                                is_active: int | None = None):
    """Update a user via the session manager."""
    mgr = _get_session_mgr()
    try:
        result = mgr.update_user(user_id, email=email, role=role,
                                 is_active=is_active)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"User {user_id} not found")
    return result


@router.post("/session-manager/sessions", status_code=201)
def create_session_manager_session(user_id: str, ip_address: str = "",
                                   user_agent: str = ""):
    """Create a new session via the session manager."""
    mgr = _get_session_mgr()
    try:
        return mgr.create_session(user_id, ip_address=ip_address,
                                  user_agent=user_agent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/session-manager/sessions/validate")
def validate_session_manager_session(token: str):
    """Validate a session token via the session manager."""
    result = _get_session_mgr().validate_session(token)
    if not result:
        raise HTTPException(status_code=401,
                            detail="Invalid or expired session token")
    return result


@router.post("/session-manager/sessions/{session_id}/revoke")
def revoke_session_manager_session(session_id: str):
    """Revoke a session via the session manager."""
    revoked = _get_session_mgr().revoke_session(session_id)
    if not revoked:
        raise HTTPException(status_code=404,
                            detail=f"Session {session_id} not found")
    return {"revoked": session_id}


@router.get("/session-manager/sessions")
def list_session_manager_sessions(user_id: str | None = None,
                                  is_active: int | None = None):
    """List sessions via the session manager."""
    return {"sessions": _get_session_mgr().list_sessions(
        user_id=user_id, is_active=is_active,
    )}


@router.post("/session-manager/audit", status_code=201)
def create_session_manager_audit(session_id: str, action: str,
                                 resource: str = "",
                                 ip_address: str = "",
                                 metadata: str = ""):
    """Record an audit event via the session manager."""
    import json as _json
    mgr = _get_session_mgr()
    md = _json.loads(metadata) if metadata else None
    try:
        return mgr.audit_event(session_id, action, resource=resource,
                               ip_address=ip_address, metadata=md)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/session-manager/audit")
def list_session_manager_audit(user_id: str | None = None,
                               action: str | None = None,
                               limit: int = 100):
    """List audit events via the session manager."""
    return {"events": _get_session_mgr().list_audit_events(
        user_id=user_id, action=action, limit=limit,
    )}


@router.post("/session-manager/cleanup")
def cleanup_session_manager_expired():
    """Deactivate expired sessions via the session manager."""
    count = _get_session_mgr().cleanup_expired()
    return {"cleaned_up": count}
