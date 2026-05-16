"""Phase 3 W2.4 — RBAC enforcement primitives.

Tiny dependency-injection helper layered on top of the existing
``governance.roles.RolesManager`` (Phase 2 K-territory, untouched by
Phase 3) and the Phase 2 ``AuthMiddleware`` that already sets
``request.state.user`` from the bearer token.

Use as a FastAPI dependency:

.. code-block:: python

    from fastapi import Depends
    from sylion.security.rbac import requires_role

    @router.post("/proposals/{proposal_id}/approve")
    def approve_proposal(
        proposal_id: str,
        _user: str = Depends(requires_role("owner", "operator")),
    ):
        ...

Behaviour:

* missing / invalid bearer token  -> ``HTTP 401``
* token valid but role mismatch   -> ``HTTP 403``
* SYLION_RBAC_DISABLED=1          -> bypass (dev / load tests)

Why a dependency, not a decorator? FastAPI rewrites the signature of
decorated handlers and the surrounding ``Request`` is not always in scope.
Dependencies hook into the same machinery FastAPI already uses for auth
patterns and they show up correctly in OpenAPI without monkey-patching.
"""
from __future__ import annotations

import logging
import os
from typing import Callable

from fastapi import HTTPException, Request

log = logging.getLogger("sylion.security.rbac")


# Canonical role tier names. Documented in ``docs/phase3/rbac_matrix.md``.
# These are the *names* expected to exist in the governance.roles store —
# the matrix doc lists the seeded permission set per name. The RolesManager
# itself does not constrain naming, so this list is advisory: if an
# operator creates a custom role the decorator still accepts it.
CANONICAL_ROLES: tuple[str, ...] = (
    "owner",        # full admin — superset of everything
    "operator",     # day-to-day deployments, projects, executions
    "auditor",      # audit-trail review (incl. integrity endpoint)
    "security",     # vault, secrets, RBAC management
    "viewer",       # read-only — does NOT pass any requires_role check
)


def _disabled() -> bool:
    return os.environ.get("SYLION_RBAC_DISABLED", "0").strip() == "1"


def requires_role(*role_names: str) -> Callable[[Request], str]:
    """Return a FastAPI dependency that asserts the caller has at least
    one of ``role_names``.

    The dependency yields the user_id on success — bind it to a parameter
    if you want to log who performed the action::

        def approve(_id: str,
                    user: str = Depends(requires_role("owner"))):
            audit("approved", actor=user)
    """
    if not role_names:
        raise ValueError("requires_role(): at least one role name required")
    required = frozenset(role_names)

    def _dep(request: Request) -> str:
        if _disabled():
            return getattr(request.state, "user", "rbac-disabled") or "anonymous"
        user_id = getattr(request.state, "user", None)
        if not user_id:
            # No bearer token (or invalid). 401 lets the client know to
            # re-authenticate; 403 would falsely imply they're known but
            # under-privileged.
            raise HTTPException(
                status_code=401,
                detail="authentication required",
            )

        # Lazy import: avoid pulling the governance store on cold start
        # for routes that don't need RBAC.
        from sylion.governance.roles import get_roles_manager

        try:
            assigned = get_roles_manager().get_user_roles(user_id)
        except Exception:
            log.exception("rbac: roles lookup failed for user=%s", user_id)
            raise HTTPException(status_code=500, detail="rbac lookup failed")

        # owner always passes regardless of required set — superuser semantics.
        # Mirrors dashboard/rbac.py:has_permission() behaviour for consistency.
        names = {r["name"] for r in assigned}
        if "owner" in names or names & required:
            return user_id

        log.info(
            "rbac 403 user=%s required=%s assigned=%s path=%s",
            user_id, sorted(required), sorted(names), request.url.path,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "required_one_of": sorted(required),
                "assigned": sorted(names),
            },
        )

    _dep.__name__ = f"requires_role_{'_'.join(sorted(required))}"
    return _dep


__all__ = ["CANONICAL_ROLES", "requires_role"]
