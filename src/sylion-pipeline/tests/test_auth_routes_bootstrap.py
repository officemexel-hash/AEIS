from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "auth-bootstrap.sqlite"

    monkeypatch.setenv("SYLION_DB_PATH", str(db_path))
    monkeypatch.setenv("SYLION_ENABLE_DEMO_DATA", "0")

    import sylion.security.auth_provider as auth_provider_module
    auth_provider_module.reset_auth_provider(db_path=str(db_path))

    import sylion.api.auth_routes as auth_routes_module
    auth_routes_module._auth_provider = None

    import sylion.api.app as app_module
    app_module = importlib.reload(app_module)

    with TestClient(app_module.app) as test_client:
        yield test_client


def test_auth_status_requires_explicit_setup(client: TestClient):
    response = client.get("/api/v1/auth/status")
    assert response.status_code == 200
    body = response.json()
    assert body["needs_setup"] is True
    assert body["setup_complete"] is False
    assert body["provider_count"] >= 1
    assert body["session_count"] == 0

    sessions = client.get("/api/v1/auth/sessions/list")
    assert sessions.status_code == 200
    assert sessions.json()["sessions"] == []


def test_setup_creates_first_admin_and_login_requires_real_password(client: TestClient):
    setup = client.post(
        "/api/v1/auth/setup",
        json={
            "username": "operator",
            "password": "OperatorPass!123",
            "display_name": "Operator",
        },
    )
    assert setup.status_code == 201, setup.text
    setup_body = setup.json()
    assert setup_body["user"]["username"] == "operator"
    assert setup_body["token"]

    status = client.get("/api/v1/auth/status")
    assert status.status_code == 200
    assert status.json()["setup_complete"] is True
    assert status.json()["needs_setup"] is False
    assert status.json()["session_count"] >= 1

    duplicate = client.post(
        "/api/v1/auth/setup",
        json={
            "username": "operator2",
            "password": "AnotherPass!123",
            "display_name": "Operator 2",
        },
    )
    assert duplicate.status_code == 409

    bad_login = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    good_login = client.post(
        "/api/v1/auth/login",
        json={"username": "operator", "password": "OperatorPass!123"},
    )
    assert good_login.status_code == 200, good_login.text
    good_body = good_login.json()
    assert good_body["user_id"] == "operator"
    assert good_body["token"]


def test_revoke_session_endpoint_invalidates_active_session(client: TestClient):
    setup = client.post(
        "/api/v1/auth/setup",
        json={
            "username": "operator",
            "password": "OperatorPass!123",
            "display_name": "Operator",
        },
    )
    assert setup.status_code == 201, setup.text
    payload = setup.json()

    revoke = client.post(f"/api/v1/auth/sessions/{payload['session_id']}/revoke")
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["revoked"] is True

    sessions = client.get("/api/v1/auth/sessions/list")
    assert sessions.status_code == 200
    assert sessions.json()["sessions"] == []

    validate = client.get(f"/api/v1/auth/tokens/{payload['token_id']}/validate")
    assert validate.status_code == 404
