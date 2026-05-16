"""Shared fixtures for security tests (Phase 3 W2.4 scope-fill).

* :fixture:`enable_rbac` — flips ``SYLION_RBAC_DISABLED`` off for the test
  function so the global middleware actually enforces. The top-level
  ``tests/conftest.py`` defaults to disabled.

* :fixture:`system_role_token` — mints a real bearer token bound to a
  ``admin`` user with the ``owner`` role assigned via
  :class:`AuthProvider` + :class:`RolesManager`. Use to drive S1-S8
  acceptance walks under enforcement so they mirror what the operator
  console does in production.

* :fixture:`role_assigned_token` — parametrised variant — assigns an
  arbitrary role and returns the token. Used by RBAC enforcement tests
  to assert per-role behaviour against the live middleware.

The fixtures are scoped to ``function`` because each test typically
uses a fresh sqlite-backed AuthProvider/RolesManager singleton.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def enable_rbac(monkeypatch):
    """Force RBAC enforcement on for this test only."""
    monkeypatch.delenv("SYLION_RBAC_DISABLED", raising=False)
    yield


@pytest.fixture
def system_role_token(monkeypatch):
    """Mint a bearer token for ``admin`` with the ``owner`` role.

    Returns the token string. Tests should pass it as
    ``Authorization: Bearer <token>``.

    Side-effect: the underlying :class:`AuthProvider` and
    :class:`RolesManager` singletons are populated. Tests that need a
    clean slate should reset them via the existing reset helpers in
    ``sylion.security.auth_provider`` / ``sylion.governance.roles``.
    """
    from sylion.security.auth_provider import get_auth_provider
    from sylion.governance.roles import get_roles_manager

    ap = get_auth_provider()
    providers = ap.list_providers(provider_type="local")
    if not providers:
        ap.register_provider("local", provider_type="local", config_json={})
        providers = ap.list_providers(provider_type="local")
    provider_id = providers[0]["provider_id"]

    auth = ap.authenticate(
        provider_id=provider_id,
        credentials_json={"user_id": "admin"},
    )
    token = auth["token_id"]

    rm = get_roles_manager()
    role_name = "owner"
    existing = [r for r in rm.list_roles() if r["name"] == role_name]
    if existing:
        role_id = existing[0]["role_id"]
    else:
        role_id = rm.create_role(role_name, description="superuser")["role_id"]
    rm.assign_role(role_id=role_id, user_id="admin", assigned_by="test-fixture")

    return token


@pytest.fixture
def role_assigned_token():
    """Factory: ``role_assigned_token(role_name, user_id="user-x")`` →
    bearer token for that user with that role assigned.

    Useful when an RBAC enforcement test needs to assert that a
    *specific* role tier (e.g. ``security`` or ``auditor``) hits or
    bounces under the global middleware.
    """
    minted: list[str] = []

    def _mint(role_name: str, user_id: str = "fixture-user") -> str:
        from sylion.security.auth_provider import get_auth_provider
        from sylion.governance.roles import get_roles_manager

        ap = get_auth_provider()
        providers = ap.list_providers(provider_type="local")
        if not providers:
            ap.register_provider("local", provider_type="local", config_json={})
            providers = ap.list_providers(provider_type="local")
        provider_id = providers[0]["provider_id"]

        auth = ap.authenticate(
            provider_id=provider_id,
            credentials_json={"user_id": user_id},
        )
        token = auth["token_id"]
        minted.append(token)

        rm = get_roles_manager()
        existing = [r for r in rm.list_roles() if r["name"] == role_name]
        if existing:
            role_id = existing[0]["role_id"]
        else:
            role_id = rm.create_role(role_name)["role_id"]
        rm.assign_role(role_id=role_id, user_id=user_id, assigned_by="test-fixture")
        return token

    return _mint
