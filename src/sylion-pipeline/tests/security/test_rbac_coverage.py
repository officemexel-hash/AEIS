"""Phase 3 W2.4 (scope-fill) — RBAC coverage acceptance test.

The master plan calls for RBAC enforcement on at least 80% of the API's
mutating routes. We compute coverage by introspecting the real FastAPI
app and asking the policy table in
:mod:`sylion.api.rbac_enforcement` what role (if any) each mutation
endpoint demands.

The test is intentionally cheap and self-contained: no HTTP calls, no
DB. It guards three properties:

  1. The global middleware is wired into ``sylion.api.app.app`` (drift
     guard for accidental removal).
  2. Mutation coverage stays ``>=80%`` — fails loudly if a refactor
     adds a new top-level prefix without updating ``POLICY``.
  3. The exemptions list contains only auth flows, health, and docs —
     nothing else may bypass enforcement.

The test also integrates with the global ``SYLION_RBAC_DISABLED=1``
default in ``tests/conftest.py``: even with that flag set, the
*coverage* (a static-analysis property) is correct because the
middleware bypass only affects request-time behaviour.
"""
from __future__ import annotations

import pytest

from sylion.api.rbac_enforcement import (
    EXEMPT_PREFIXES,
    MUTATION_METHODS,
    RBACEnforcementMiddleware,
    _required_roles_for,
)


REQUIRED_COVERAGE = 0.80


@pytest.fixture(scope="module")
def app():
    from sylion.api.app import app as fastapi_app
    return fastapi_app


def _iter_mutations(app):
    for route in app.routes:
        methods = getattr(route, "methods", None)
        if not methods:
            continue
        for m in methods - {"HEAD", "OPTIONS"}:
            if m in MUTATION_METHODS:
                yield m, route.path


# ---------------------------------------------------------------------------
# 1. middleware is wired
# ---------------------------------------------------------------------------


def test_rbac_enforcement_middleware_is_installed(app):
    middleware_classes = [m.cls for m in app.user_middleware]
    assert RBACEnforcementMiddleware in middleware_classes, (
        "RBACEnforcementMiddleware was removed from sylion.api.app — "
        "every mutation would now bypass policy"
    )


# ---------------------------------------------------------------------------
# 2. coverage threshold
# ---------------------------------------------------------------------------


def test_mutation_coverage_at_least_80_percent(app):
    total = 0
    protected = 0
    exempt = 0
    unmatched: list[tuple[str, str]] = []
    for method, path in _iter_mutations(app):
        total += 1
        required = _required_roles_for(path)
        if required is None:
            exempt += 1
        else:
            protected += 1
            if not required:
                unmatched.append((method, path))

    assert total > 0, "no mutation routes discovered — app may have failed to load"
    coverage = protected / total
    assert coverage >= REQUIRED_COVERAGE, (
        f"mutation RBAC coverage {coverage:.1%} below "
        f"required {REQUIRED_COVERAGE:.0%} "
        f"(protected={protected}, exempt={exempt}, total={total})"
    )
    assert not unmatched, (
        f"policy entries with empty role tuple: {unmatched[:5]}"
    )


# ---------------------------------------------------------------------------
# 3. exempt list contains only auth/health/docs
# ---------------------------------------------------------------------------


def test_exempt_prefixes_are_minimal():
    """Exempt list must remain narrow. Anything beyond auth flows, health
    and docs is a regression — every other surface should require a role.
    """
    allowed_buckets = (
        "/api/v1/auth",
        "/api/v1/health",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    )
    for ex in EXEMPT_PREFIXES:
        assert any(ex.startswith(b) or ex == b for b in allowed_buckets), (
            f"unexpected exempt prefix: {ex!r}"
        )


# ---------------------------------------------------------------------------
# 4. fan-out by tier (informational — also asserts no zero-tier surface)
# ---------------------------------------------------------------------------


def test_protected_tiers_distribution(app):
    """At least one mutation must exist in every canonical tier; if a
    refactor wipes out e.g. all auditor mutations we want to know."""
    by_tier: dict[str, int] = {"operator": 0, "security": 0, "auditor": 0}
    for _, path in _iter_mutations(app):
        roles = _required_roles_for(path)
        if not roles:
            continue
        for r in roles:
            if r in by_tier:
                by_tier[r] += 1

    for tier, count in by_tier.items():
        assert count > 0, f"no mutations protected at tier={tier} — policy regression"
