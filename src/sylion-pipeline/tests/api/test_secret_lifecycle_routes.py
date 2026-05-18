from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.api.secret_routes as secret_routes
from sylion.security.key_store_unified import reset_key_store_unified


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    reset_key_store_unified(db_path=":memory:", backend="memory")
    api = FastAPI()
    api.include_router(secret_routes.router)
    return TestClient(api)


def test_secret_lifecycle_dummy_flow_route_does_not_echo_values(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/v1/secrets/lifecycle/dummy-flow",
        json={
            "name": "AEIS_ROUTE_DUMMY_SECRET",
            "backend": "sops",
            "rotation_period_days": 90,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pass"
    assert body["final_version"] == 2
    assert "fixture-initial-value" not in response.text
    assert "fixture-rotated-value" not in response.text


def test_secret_lifecycle_add_validate_rotate_route(monkeypatch):
    client = _client(monkeypatch)

    add_response = client.post(
        "/api/v1/secrets/lifecycle/add",
        json={
            "name": "AEIS_ROUTE_SECRET",
            "value": "fixture-initial-value",
            "backend": "sops",
            "scope": "secrets",
            "rotation_period_days": 90,
        },
    )
    assert add_response.status_code == 201, add_response.text
    assert "fixture-initial-value" not in add_response.text

    validate_response = client.get(
        "/api/v1/secrets/lifecycle/AEIS_ROUTE_SECRET/validate"
    )
    assert validate_response.status_code == 200, validate_response.text
    assert validate_response.json()["valid"] is True

    rotate_response = client.post(
        "/api/v1/secrets/lifecycle/AEIS_ROUTE_SECRET/rotate",
        json={
            "new_value": "fixture-rotated-value",
            "backend": "sops",
            "rotation_period_days": 90,
        },
    )
    assert rotate_response.status_code == 200, rotate_response.text
    assert rotate_response.json()["version"] == 2
    assert "fixture-rotated-value" not in rotate_response.text

    validate_after = client.get(
        "/api/v1/secrets/lifecycle/AEIS_ROUTE_SECRET/validate"
    )
    assert validate_after.status_code == 200, validate_after.text
    assert validate_after.json()["version"] == 2


def test_secret_lifecycle_route_rejects_plaintext_backend(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/v1/secrets/lifecycle/add",
        json={
            "name": "AEIS_BAD_BACKEND",
            "value": "fixture-value",
            "backend": "plaintext",
            "rotation_period_days": 90,
        },
    )

    assert response.status_code == 400
    assert "production-safe" in response.text
