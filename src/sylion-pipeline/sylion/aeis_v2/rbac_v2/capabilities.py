"""Capability registry for RBAC v2."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sylion.aeis_v2.audit_chain import append_to_chain

log = logging.getLogger(__name__)

#: New roles introduced in sprint 3. Names are deliberately lowercase
#: snake_case to match the canonical RBAC tier convention.
NEW_V2_ROLES: tuple[str, ...] = (
    "replay_operator",
    "lifecycle_manager",
    "metrics_viewer",
)

#: Canonical capability → who-grants-it default mapping. Operators can
#: extend this matrix at runtime via :func:`register_role_capabilities`
#: without touching this module. ``owner`` always has every capability
#: (superuser semantics, mirrors :mod:`sylion.security.rbac`).
DEFAULT_ROLE_CAPABILITIES: dict[str, frozenset[str]] = {
    # Canonical tier — capability mirrors what the existing endpoints
    # already enforce. Documenting it here keeps the surface explicit.
    "owner": frozenset({
        "*",  # superuser sentinel — has_capability returns True for any.
    }),
    "operator": frozenset({
        "gdpr.dsr.access",
        "gdpr.dsr.rectification",
        "gdpr.dsr.portability",
        "match_idea.read",
        "match_idea.run_council",
        "replay.run",
        "lifecycle.read",
    }),
    "auditor": frozenset({
        "gdpr.dsr.audit_recent",
        "audit_chain.verify",
        "metrics.read",
        "lifecycle.read",
    }),
    "security": frozenset({
        "audit_chain.verify",
        "vault.manage",
        "rbac.grant",
    }),
    "viewer": frozenset({
        "match_idea.read",
        "lifecycle.read",
    }),
    # New v2 roles — sprint 3 extension.
    "replay_operator": frozenset({
        "replay.run",
        "replay.list",
        "replay.snapshot",
    }),
    "lifecycle_manager": frozenset({
        "lifecycle.transition",
        "lifecycle.read",
        "lifecycle.history",
    }),
    "metrics_viewer": frozenset({
        "metrics.read",
        "health.read",
    }),
}


#: Audit JSONL — every grant emits a row so the auditor sees who gained
#: which capability when (per Kimi k2 backward-compat tracker).
RBAC_V2_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "rbac_v2.jsonl"
)


@dataclass(frozen=True, slots=True)
class RoleCapabilities:
    """Snapshot of a role's capabilities at a moment in time."""

    role: str
    capabilities: frozenset[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "capabilities": sorted(self.capabilities),
        }


# ---------------------------------------------------------------------------
# Process-wide mutable registry — start with DEFAULT_ROLE_CAPABILITIES.
# Operators extend at runtime; reset_capability_registry() restores defaults.
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, frozenset[str]] = dict(DEFAULT_ROLE_CAPABILITIES)
_LOCK = threading.RLock()


def _emit_audit(payload: dict[str, Any]) -> None:
    try:
        append_to_chain(RBAC_V2_AUDIT_LOG_PATH, payload)
    except Exception as exc:  # noqa: BLE001
        log.warning("rbac_v2: audit emit failed (%s)", exc)


def reset_capability_registry() -> None:
    """Restore DEFAULT_ROLE_CAPABILITIES. Test + operator helper."""
    global _REGISTRY
    with _LOCK:
        _REGISTRY = dict(DEFAULT_ROLE_CAPABILITIES)


def register_role_capabilities(
    role: str, capabilities: set[str] | frozenset[str],
    *, actor: str = "anonymous", merge: bool = True,
) -> RoleCapabilities:
    """Add or replace capabilities for ``role``.

    Args:
        role: name (any string — does not need to be canonical).
        capabilities: caps to register.
        actor: audit-trail attribution.
        merge: when True (default), unions with existing caps; when
            False, replaces wholesale.
    """
    if not role or not isinstance(role, str):
        raise ValueError("role must be a non-empty string")
    new_caps = frozenset(capabilities)
    with _LOCK:
        if merge and role in _REGISTRY:
            new_caps = _REGISTRY[role] | new_caps
        _REGISTRY[role] = new_caps
        snap = RoleCapabilities(role=role, capabilities=new_caps)
    _emit_audit({
        "kind": "rbac_v2.register",
        "actor": actor,
        "merge": merge,
        **snap.to_dict(),
    })
    return snap


def grant_role_capabilities(
    role: str, capabilities: set[str] | frozenset[str],
    *, actor: str = "anonymous",
) -> RoleCapabilities:
    """Convenience: ``register_role_capabilities(merge=True)``."""
    return register_role_capabilities(
        role, capabilities, actor=actor, merge=True,
    )


def list_capabilities_for_role(role: str) -> frozenset[str]:
    """Read-only snapshot of a role's caps. Empty for unknown roles."""
    with _LOCK:
        return _REGISTRY.get(role, frozenset())


def list_roles_with_capability(capability: str) -> list[str]:
    """All roles that grant ``capability`` (sorted, deterministic)."""
    if not capability:
        return []
    with _LOCK:
        return sorted(
            role for role, caps in _REGISTRY.items()
            if capability in caps or "*" in caps
        )


def has_capability(
    user_roles: set[str] | frozenset[str], capability: str,
) -> bool:
    """Returns True if any user_role grants ``capability``.

    Owner role has the ``*`` superuser sentinel — every capability check
    against an owner returns True.
    """
    if not capability:
        return False
    if not user_roles:
        return False
    with _LOCK:
        for r in user_roles:
            caps = _REGISTRY.get(r)
            if caps is None:
                continue
            if "*" in caps or capability in caps:
                return True
    return False


def audit_capability_check(
    user_id: str, user_roles: set[str], capability: str,
    *, granted: bool, actor: str = "system",
) -> None:
    """Best-effort emit a chained capability-check row for audit purposes.

    Production endpoints can call this after every authz decision so
    the DPO has a visibility surface for who-tried-what-when.
    """
    _emit_audit({
        "kind": "rbac_v2.check",
        "user_id": user_id,
        "user_roles": sorted(user_roles),
        "capability": capability,
        "granted": granted,
        "actor": actor,
    })


__all__ = [
    "DEFAULT_ROLE_CAPABILITIES",
    "NEW_V2_ROLES",
    "RBAC_V2_AUDIT_LOG_PATH",
    "RoleCapabilities",
    "audit_capability_check",
    "grant_role_capabilities",
    "has_capability",
    "list_capabilities_for_role",
    "list_roles_with_capability",
    "register_role_capabilities",
    "reset_capability_registry",
]
