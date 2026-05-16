"""Tests for sylion.security.rbac (Phase 3 W2.4).

We verify the FastAPI dependency directly:

* missing user state -> 401
* user with no matching role -> 403
* user with required role -> 200
* user with 'owner' superuser role -> 200 even when 'owner' not in required set
* SYLION_RBAC_DISABLED=1 short-circuits

We mount on a tiny Starlette/FastAPI app so the test exercises the dep
through the same dependency-injection machinery production routes use.
"""
from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from sylion.security.rbac import requires_role


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("SYLION_RBAC_DISABLED", raising=False)
    app = FastAPI()

    @app.middleware("http")
    async def _stub_auth(request: Request, call_next):
        request.state.user = request.headers.get("x-test-user") or None
        return await call_next(request)

    @app.post("/owner-only")
    def owner_only(_user: str = Depends(requires_role("owner"))):
        return {"user": _user}

    @app.post("/operator-or-owner")
    def operator_or_owner(_user: str = Depends(requires_role("operator", "owner"))):
        return {"user": _user}

    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Test stub for the governance roles store. We don't want to rely on the
# real RolesManager (which would touch SQLite); patch get_roles_manager.
# ---------------------------------------------------------------------------

class _StubRolesManager:
    def __init__(self, mapping: dict[str, list[str]]):
        # mapping: user_id -> list of role names
        self._mapping = mapping

    def get_user_roles(self, user_id: str) -> list[dict]:
        return [{"name": n} for n in self._mapping.get(user_id, [])]


@pytest.fixture
def roles(monkeypatch):
    """Override get_roles_manager to return our stub. Returns the stub
    so each test can mutate the user→roles mapping."""
    stub = _StubRolesManager({
        "alice": ["owner"],
        "bob": ["operator"],
        "carol": ["viewer"],
    })

    def _get():
        return stub

    monkeypatch.setattr(
        "sylion.governance.roles.get_roles_manager",
        _get,
    )
    return stub


# ---------------------------------------------------------------------------
# 401 — no user
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    def test_no_user_returns_401(self, client, roles):
        # No X-Test-User header -> request.state.user = None.
        r = client.post("/owner-only")
        assert r.status_code == 401
        assert "auth" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 403 — user with wrong role
# ---------------------------------------------------------------------------


class TestForbidden:
    def test_viewer_cannot_access_owner_only(self, client, roles):
        r = client.post("/owner-only", headers={"X-Test-User": "carol"})
        assert r.status_code == 403
        body = r.json()["detail"]
        assert body["error"] == "forbidden"
        assert "owner" in body["required_one_of"]
        assert "viewer" in body["assigned"]

    def test_unknown_user_403_not_500(self, client, roles):
        # User is authenticated (state.user set) but has zero roles assigned.
        r = client.post("/owner-only", headers={"X-Test-User": "ghost"})
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 200 — happy paths
# ---------------------------------------------------------------------------


class TestAuthorized:
    def test_owner_passes_owner_only(self, client, roles):
        r = client.post("/owner-only", headers={"X-Test-User": "alice"})
        assert r.status_code == 200
        assert r.json() == {"user": "alice"}

    def test_operator_passes_operator_route(self, client, roles):
        r = client.post(
            "/operator-or-owner",
            headers={"X-Test-User": "bob"},
        )
        assert r.status_code == 200

    def test_owner_is_superuser_for_any_required_role(self, client, roles):
        # 'owner' is not literally in the required set ("operator", "owner")
        # *yet*, but if someone changes the route to require only "operator"
        # the owner should still pass. Verify the superuser shortcut.
        @client.app.post("/security-only")
        def _(_user: str = Depends(requires_role("security"))):  # noqa: F841
            return {}

        r = client.post("/security-only", headers={"X-Test-User": "alice"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Disable flag
# ---------------------------------------------------------------------------


class TestDisableFlag:
    def test_disable_bypasses_check(self, monkeypatch, client, roles):
        monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
        # carol is viewer -> would normally 403 on /owner-only.
        r = client.post("/owner-only", headers={"X-Test-User": "carol"})
        assert r.status_code == 200

    def test_disable_with_no_user_returns_anonymous(
        self, monkeypatch, client, roles,
    ):
        monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
        r = client.post("/owner-only")
        assert r.status_code == 200
        assert r.json()["user"] in ("rbac-disabled", "anonymous")


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------


class TestApiSurface:
    def test_empty_role_list_raises(self):
        with pytest.raises(ValueError):
            requires_role()

    def test_canonical_roles_exposed(self):
        from sylion.security.rbac import CANONICAL_ROLES
        for r in ("owner", "operator", "auditor", "security", "viewer"):
            assert r in CANONICAL_ROLES
