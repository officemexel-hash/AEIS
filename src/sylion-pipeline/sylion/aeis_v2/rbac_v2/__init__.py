"""SYLION AEIS v2 — RBAC v2 capability extension (W7).

Sprint 3 deliverable. Sits alongside :mod:`sylion.security.rbac` (the
canonical 5-tier system: owner/operator/auditor/security/viewer) and
adds a **capability layer** so we can grant fine-grained permissions
without bloating the canonical tier set.

Three new roles ship today:

* ``replay_operator``   — can run replay-as-fork sessions
* ``lifecycle_manager`` — can drive idea-lifecycle transitions
* ``metrics_viewer``    — read-only access to /metrics/v2 + /health/v2

Each is mapped to a small set of capability strings; production
deployments can extend the matrix without touching this module by
calling :func:`register_role_capabilities`.

Per Kimi review k2 (round 54:30): the new roles are NOT added to
``CANONICAL_ROLES`` in ``sylion/security/rbac.py`` — that tuple is
deliberately frozen to avoid backward-compat risk. Instead we live
parallel to it; the existing ``requires_role(...)`` decorator still
accepts custom role names per its docstring, so the route layer can
say ``requires_role("replay_operator")`` and it works.
"""

from sylion.aeis_v2.rbac_v2.capabilities import (
    DEFAULT_ROLE_CAPABILITIES,
    NEW_V2_ROLES,
    RBAC_V2_AUDIT_LOG_PATH,
    RoleCapabilities,
    audit_capability_check,
    grant_role_capabilities,
    has_capability,
    list_capabilities_for_role,
    list_roles_with_capability,
    register_role_capabilities,
    reset_capability_registry,
)

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
