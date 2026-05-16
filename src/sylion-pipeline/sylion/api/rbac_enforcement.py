"""Phase 3 W2.4 (scope-fill) — global RBAC enforcement middleware.

The Phase 3 master plan calls for ``>=80%`` of mutations (POST/PUT/PATCH/
DELETE) to be RBAC-protected. Decorating 633 routes one by one with
``Depends(requires_role(...))`` would spread policy across dozens of files
and almost guarantee drift; instead we enforce a *baseline* policy at the
middleware layer.

Design contract
---------------

* Reads ``request.state.user`` (already populated by :class:`AuthMiddleware`).
* Only fires for HTTP methods in ``{POST, PUT, PATCH, DELETE}``.
* Looks up the *longest matching* path prefix in :data:`POLICY` to find
  the required role(s).
* On miss, falls back to :data:`DEFAULT_ROLES` for ``/api/v1/*`` paths;
  paths outside ``/api/v1`` are passed through unchecked (legacy/internal).
* Honours ``SYLION_RBAC_DISABLED=1`` env bypass — same flag the per-route
  decorator already supports.
* Per-route ``Depends(requires_role(...))`` declarations remain
  authoritative: the middleware sets a *baseline*, the route can demand
  more (the dependency runs after the middleware).

Why a middleware and not auto-decorating routes?

1. One file owns the policy → trivial to audit.
2. New routes inherit protection by default; they are protected even
   before anyone remembers to add a decorator.
3. The coverage-test (:mod:`tests.security.test_rbac_coverage`) can read
   the policy table directly and assert ``mutation_coverage >= 0.80``.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("sylion.api.rbac_enforcement")


MUTATION_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})


# ---------------------------------------------------------------------------
# Path-prefix → required roles
# ---------------------------------------------------------------------------
# Order matters only for documentation — lookup uses *longest match wins*.
# Every mutation under /api/v1/<prefix> must be reachable by at least one
# of the listed roles. ``owner`` is implicitly accepted everywhere by
# :func:`requires_role` (superuser semantics) so we don't repeat it here.
#
# Roles legend (see CANONICAL_ROLES in sylion/security/rbac.py):
#   operator    = day-to-day mutations (deployments, projects, executions)
#   security    = vault, secrets, RBAC mgmt, security profiles, phantom
#   auditor     = audit-trail, evidence-timeline, decision-snapshots write
#                 (audit modules only allow auditors to *record* events)
#
# This table backs the ``mutation_coverage`` figure reported in
# tests/security/test_rbac_coverage.py.
POLICY: dict[str, tuple[str, ...]] = {
    # --- security-tier prefixes -------------------------------------------
    "/api/v1/security":            ("security",),
    "/api/v1/security-profiles":   ("security",),
    "/api/v1/security-audit":      ("security",),
    "/api/v1/security-ext":        ("security",),
    "/api/v1/secrets":             ("security",),
    "/api/v1/vault":               ("security",),
    "/api/v1/roles":               ("security",),
    "/api/v1/phantom":             ("security",),
    "/api/v1/execution-guard":     ("security",),
    "/api/v1/bootstrap":           ("security",),
    "/api/v1/profile-swaps":       ("security",),

    # --- auditor-tier prefixes --------------------------------------------
    "/api/v1/audit":               ("auditor",),
    "/api/v1/audit-sink":          ("auditor",),
    "/api/v1/audit-query":         ("auditor",),
    "/api/v1/hardened-audit":      ("auditor",),
    "/api/v1/evidence-timeline":   ("auditor",),
    "/api/v1/decision-snapshots":  ("auditor",),

    # --- operator-tier prefixes (default for /api/v1) ---------------------
    "/api/v1/aeis":                ("operator",),
    "/api/v1/agents":              ("operator",),
    "/api/v1/adapters":            ("operator",),
    "/api/v1/ai-providers":        ("operator",),
    "/api/v1/autonomy":            ("operator",),
    "/api/v1/brain":               ("operator",),
    "/api/v1/bundles":             ("operator",),
    "/api/v1/capacity":            ("operator",),
    "/api/v1/cellular":            ("operator",),
    "/api/v1/circuit-breakers":    ("operator",),
    "/api/v1/cognitive":           ("operator",),
    "/api/v1/connectors":          ("operator",),
    "/api/v1/container":           ("operator",),
    "/api/v1/contracts":           ("operator",),
    "/api/v1/core":                ("operator",),
    "/api/v1/council":             ("operator",),
    "/api/v1/decision-boundaries": ("operator",),
    "/api/v1/deploy":              ("operator",),
    "/api/v1/deployments":         ("operator",),
    "/api/v1/devices":             ("operator",),
    "/api/v1/efficiency":          ("operator",),
    "/api/v1/evaluator":           ("operator",),
    "/api/v1/execution":           ("operator",),
    "/api/v1/feedback":            ("operator",),
    "/api/v1/funding":             ("operator",),
    "/api/v1/gates":               ("operator",),
    "/api/v1/golden-sets":         ("operator",),
    "/api/v1/governance":          ("operator",),
    "/api/v1/healing-engine":      ("operator",),
    "/api/v1/ideas":               ("operator",),
    "/api/v1/integration":         ("operator",),
    "/api/v1/integrations":        ("operator",),
    "/api/v1/knowledge":           ("operator",),
    "/api/v1/lifecycle":           ("operator",),
    "/api/v1/memory":              ("operator",),
    "/api/v1/mobile":              ("operator",),
    "/api/v1/model-budget":        ("operator",),
    "/api/v1/model-registry":      ("operator",),
    "/api/v1/monitoring":          ("operator",),
    "/api/v1/notifications":       ("operator",),
    "/api/v1/observability":       ("operator",),
    "/api/v1/pipeline":            ("operator",),
    "/api/v1/projects":            ("operator",),
    "/api/v1/quality":             ("operator",),
    "/api/v1/rebuild":             ("operator",),
    "/api/v1/registry":            ("operator",),
    "/api/v1/regression":          ("operator",),
    "/api/v1/rollback":            ("operator",),
    "/api/v1/sdr":                 ("operator",),
    "/api/v1/self-explanation":    ("operator",),
    "/api/v1/self-healing":        ("operator",),
    "/api/v1/skills":              ("operator",),
    "/api/v1/snapshots":           ("operator",),
    "/api/v1/surface":             ("operator",),
    "/api/v1/versions":            ("operator",),
    "/api/v1/vps":                 ("operator",),
    "/api/v1/workers":             ("operator",),
    "/api/v1/workspace":           ("operator",),
}


# Default required roles for any /api/v1/* mutation that doesn't match a
# longer prefix in POLICY. Keeps newly-added routers protected by default.
DEFAULT_ROLES: tuple[str, ...] = ("operator",)


# Paths exempted from RBAC enforcement. Auth flows must remain reachable
# without a token (otherwise no-one can ever log in); /health is public.
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/",        # login / token mgmt — pre-auth
    "/api/v1/health",       # liveness probe
    "/health",              # legacy liveness
    "/docs",
    "/openapi.json",
    "/redoc",
)


def _disabled() -> bool:
    return os.environ.get("SYLION_RBAC_DISABLED", "0").strip() == "1"


def _required_roles_for(path: str) -> tuple[str, ...] | None:
    """Return the required role tuple for ``path``, or ``None`` if exempt.

    Resolution order:
      1. If the path matches an EXEMPT_PREFIXES entry → ``None``.
      2. If a POLICY prefix matches → its role tuple (longest match wins).
      3. If the path starts with ``/api/v1/`` → DEFAULT_ROLES.
      4. Otherwise → ``None`` (non-API surfaces like /metrics or /health).
    """
    for ex in EXEMPT_PREFIXES:
        if path == ex.rstrip("/") or path.startswith(ex):
            return None

    best: tuple[str, ...] | None = None
    best_len = -1
    for prefix, roles in POLICY.items():
        if path == prefix or path.startswith(prefix + "/"):
            if len(prefix) > best_len:
                best, best_len = roles, len(prefix)
    if best is not None:
        return best

    if path.startswith("/api/v1/"):
        return DEFAULT_ROLES

    return None


def _user_has_required_role(user_id: str, required: Iterable[str]) -> bool:
    """Look up assigned roles for ``user_id`` and check membership.

    Treats ``owner`` as superuser (matches :func:`requires_role`).
    """
    from sylion.governance.roles import get_roles_manager

    try:
        assigned = get_roles_manager().get_user_roles(user_id)
    except Exception:
        log.exception("rbac middleware: roles lookup failed for user=%s", user_id)
        return False

    names = {r["name"] for r in assigned}
    if "owner" in names:
        return True
    return bool(names & set(required))


class RBACEnforcementMiddleware(BaseHTTPMiddleware):
    """Apply :data:`POLICY` to every mutation request.

    Order of operations (must run *after* :class:`AuthMiddleware`):

    * non-mutation methods → pass through.
    * exempt paths → pass through.
    * ``SYLION_RBAC_DISABLED=1`` → pass through.
    * no user on request.state → ``401``.
    * user lacks required role → ``403``.
    * otherwise → pass through (per-route Depends still runs).
    """

    async def dispatch(self, request: Request, call_next):
        method = request.method
        if method not in MUTATION_METHODS:
            return await call_next(request)

        if _disabled():
            return await call_next(request)

        path = request.url.path
        required = _required_roles_for(path)
        if required is None:
            # exempt path or non-/api/v1 surface
            return await call_next(request)

        user_id = getattr(request.state, "user", None)
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "authentication required"},
            )

        if not _user_has_required_role(user_id, required):
            log.info(
                "rbac-mw 403 user=%s required=%s path=%s method=%s",
                user_id, sorted(required), path, method,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": {
                        "error": "forbidden",
                        "required_one_of": sorted(required),
                        "path": path,
                        "method": method,
                    }
                },
            )

        return await call_next(request)


__all__ = [
    "POLICY",
    "DEFAULT_ROLES",
    "EXEMPT_PREFIXES",
    "MUTATION_METHODS",
    "RBACEnforcementMiddleware",
]
