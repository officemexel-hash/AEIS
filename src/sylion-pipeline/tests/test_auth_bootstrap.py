from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from sylion.api import app as app_module
from sylion.security.auth_provider import get_auth_provider, reset_auth_provider


def _auth_probe_app() -> FastAPI:
    probe = FastAPI()
    probe.add_middleware(app_module.AuthMiddleware)

    @probe.post("/api/v1/workspace/probe")
    async def workspace_probe(request: Request):
        return {
            "user": getattr(request.state, "user", None),
            "token": getattr(request.state, "token", None),
        }

    return probe


def test_seed_auth_data_uses_sylion_admin_password_alias(tmp_path, monkeypatch):
    monkeypatch.delenv("SYLION_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("SYLION_ADMIN_PASSWORD", "AliasPass!1")
    reset_auth_provider(tmp_path / "auth.db")

    app_module._seed_auth_data()

    ap = get_auth_provider()
    assert ap.authenticate("admin", "AliasPass!1")
    assert ap.authenticate("admin", "admin") is None


def test_seed_auth_data_reconciles_legacy_default_admin_password(tmp_path, monkeypatch):
    monkeypatch.delenv("SYLION_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("SYLION_ADMIN_PASSWORD", "AliasPass!2")
    ap = reset_auth_provider(tmp_path / "auth.db")
    provider = ap.register_provider("local", provider_type="local", config_json={})
    ap.create_user("admin", "admin", "admin", role="owner", metadata={"source": "legacy-test"})
    ap.authenticate(provider["provider_id"], {"user_id": "admin", "password": "admin"})

    app_module._seed_auth_data()

    assert ap.authenticate("admin", "AliasPass!2")
    assert ap.authenticate("admin", "admin") is None


def test_dev_auth_falls_back_when_browser_sends_stale_bearer(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_AUTH_MODE", "dev")
    reset_auth_provider(tmp_path / "auth.db")
    client = TestClient(_auth_probe_app())

    response = client.post(
        "/api/v1/workspace/probe",
        headers={"Authorization": "Bearer stale-token-after-restart"},
    )

    assert response.status_code == 200
    assert response.json()["user"] == app_module._DEV_OPERATOR_ID
    assert response.json()["token"] == "dev-bypass"


def test_strict_auth_does_not_fall_back_for_stale_bearer(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_AUTH_MODE", "strict")
    reset_auth_provider(tmp_path / "auth.db")
    client = TestClient(_auth_probe_app())

    response = client.post(
        "/api/v1/workspace/probe",
        headers={"Authorization": "Bearer stale-token-after-restart"},
    )

    assert response.status_code == 200
    assert response.json()["user"] is None
    assert response.json()["token"] is None
