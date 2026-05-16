from __future__ import annotations

import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.api import security_ext_routes
from sylion.security.evidence_signer import EvidenceSigner


@pytest.fixture(autouse=True)
def _reset_route_signer():
    security_ext_routes._evidence_signer = EvidenceSigner(db_path=":memory:")
    yield
    security_ext_routes._evidence_signer = None


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(security_ext_routes.router)
    return TestClient(app, raise_server_exceptions=False)


def test_list_keys_returns_real_signer_state_without_exposing_key_material(client: TestClient):
    first = client.post(
        "/api/v1/security/evidence/keys/generate",
        json={"alias": "primary"},
    )
    second = client.post(
        "/api/v1/security/evidence/keys/generate",
        json={"alias": "backup", "key_type": "rsa"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    revoke = client.post(
        "/api/v1/security/evidence/keys/revoke",
        json={"key_id": second.json()["key_id"]},
    )
    assert revoke.status_code == 200

    response = client.get("/api/v1/security/evidence/keys")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["keys"]) == 2
    assert [item["alias"] for item in payload["keys"]] == ["primary", "backup"]
    assert payload["keys"][0]["is_revoked"] == 0
    assert payload["keys"][1]["is_revoked"] == 1
    assert all("public_key" not in item for item in payload["keys"])
    assert all("key_secret" not in item for item in payload["keys"])


def test_list_keys_returns_503_when_signer_bootstrap_fails(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    security_ext_routes._evidence_signer = None

    def _boom():
        raise RuntimeError("signer init failed")

    monkeypatch.setattr(security_ext_routes, "_get_evidence_signer", _boom)

    response = client.get("/api/v1/security/evidence/keys")

    assert response.status_code == 503
    assert response.json()["detail"] == "evidence signer unavailable"


def test_list_keys_returns_503_when_storage_read_fails(client: TestClient):
    class BrokenSigner:
        def list_keys(self):
            raise sqlite3.OperationalError("database is locked")

    security_ext_routes._evidence_signer = BrokenSigner()

    response = client.get("/api/v1/security/evidence/keys")

    assert response.status_code == 503
    assert response.json()["detail"] == "evidence signer storage unavailable during list_keys"


def test_sign_verify_and_stats_still_work_with_real_signer_backend(client: TestClient):
    generated = client.post(
        "/api/v1/security/evidence/keys/generate",
        json={"alias": "flow-key"},
    )
    key_id = generated.json()["key_id"]

    signed = client.post(
        "/api/v1/security/evidence/sign",
        json={
            "key_id": key_id,
            "evidence_id": "evidence-001",
            "data_json": '{"ok": true}',
        },
    )

    assert signed.status_code == 201

    verify = client.post(
        "/api/v1/security/evidence/verify",
        json={"signed_id": signed.json()["signed_id"]},
    )
    stats = client.get("/api/v1/security/evidence/stats")

    assert verify.status_code == 200
    assert verify.json()["valid"] is True
    assert stats.status_code == 200
    assert stats.json()["total_keys"] == 1
    assert stats.json()["total_signed"] == 1
