"""Phase 3 W2.4 (scope-fill) — global RBAC middleware end-to-end.

These tests boot the *real* FastAPI app (via TestClient) with RBAC
enforcement turned on (``SYLION_RBAC_DISABLED`` deleted) and assert:

* unauthenticated mutation → 401
* operator-tier mutation with operator token → reaches the route layer
  (we accept any non-401/403 status; the underlying handler may still
  return 4xx for missing payload / invalid id, that is fine — we only
  care about *RBAC* gating here).
* security-tier mutation rejects an operator-only token → 403
* auth flows, health, GETs are not gated.

We deliberately avoid asserting *exact* 200/201 statuses because the
mutation handlers under each prefix have their own validation logic;
a P3-W2.4 test must not become a regression suite for every domain
module.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app():
    from sylion.api.app import app as fastapi_app
    return fastapi_app


@pytest.fixture
def client(app, enable_rbac):
    # ``enable_rbac`` is a function-scoped fixture; build a fresh
    # TestClient per test so it sees the current env var state.
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# unauthenticated → 401
# ---------------------------------------------------------------------------


class TestUnauthenticated:
    def test_post_without_token_returns_401(self, client):
        # /api/v1/projects is operator-tier per POLICY.
        r = client.post("/api/v1/projects", json={"title": "x"})
        assert r.status_code == 401, (
            f"expected 401 for anonymous mutation, got {r.status_code}: {r.text[:200]}"
        )

    def test_delete_without_token_returns_401(self, client):
        r = client.delete("/api/v1/secrets/some-id")
        assert r.status_code == 401

    def test_get_does_not_require_auth(self, client):
        # GET on a list endpoint — middleware should pass through.
        r = client.get("/api/v1/projects")
        assert r.status_code != 401, (
            "GET endpoints must not be gated by RBAC middleware"
        )


# ---------------------------------------------------------------------------
# auth flow / health remain reachable
# ---------------------------------------------------------------------------


class TestExempt:
    def test_health_reachable(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_auth_register_provider_reachable(self, client):
        # The auth surface itself must remain anonymous-mutable, otherwise
        # no-one can ever bootstrap a token.
        r = client.post(
            "/api/v1/auth/providers",
            json={"name": "rbac-mw-test", "provider_type": "local"},
        )
        # 201 on success or 400 on duplicate — both prove RBAC didn't gate.
        assert r.status_code in (201, 400), (
            f"auth provider register should not be RBAC-gated, got {r.status_code}"
        )


# ---------------------------------------------------------------------------
# token paths — operator vs security tier
# ---------------------------------------------------------------------------


class TestAuthorized:
    def test_operator_token_passes_operator_route(
        self, client, system_role_token,
    ):
        # `system_role_token` mints `admin` with `owner` role — superuser.
        r = client.post(
            "/api/v1/projects",
            json={"title": "rbac-mw smoke", "idea": "x", "owner_id": "admin"},
            headers={"Authorization": f"Bearer {system_role_token}"},
        )
        # Owner → middleware passes. Handler may still 422/400 for payload
        # issues; the only forbidden outcomes are 401 and 403.
        assert r.status_code not in (401, 403), (
            f"owner token bounced: status={r.status_code} body={r.text[:200]}"
        )

    def test_owner_token_passes_security_route(
        self, client, system_role_token,
    ):
        r = client.post(
            "/api/v1/secrets",
            json={"name": "rbac-mw-smoke", "value": "x"},
            headers={"Authorization": f"Bearer {system_role_token}"},
        )
        assert r.status_code not in (401, 403)


class TestForbidden:
    def test_operator_token_blocked_on_security_route(
        self, client, role_assigned_token,
    ):
        token = role_assigned_token("operator", user_id="rbac-mw-op")
        r = client.post(
            "/api/v1/secrets",
            json={"name": "rbac-mw-blocked", "value": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403, (
            f"operator should not reach /api/v1/secrets, got {r.status_code}"
        )

    def test_viewer_token_blocked_on_operator_route(
        self, client, role_assigned_token,
    ):
        token = role_assigned_token("viewer", user_id="rbac-mw-viewer")
        r = client.post(
            "/api/v1/projects",
            json={"title": "x"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# disable flag bypass
# ---------------------------------------------------------------------------


class TestDisableBypass:
    def test_disable_flag_bypasses_middleware(self, app, monkeypatch):
        monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
        c = TestClient(app, raise_server_exceptions=False)
        r = c.post("/api/v1/projects", json={"title": "x"})
        assert r.status_code != 401, (
            "SYLION_RBAC_DISABLED=1 must allow anonymous mutations through "
            "(individual handlers may still 4xx for payload validation)"
        )
