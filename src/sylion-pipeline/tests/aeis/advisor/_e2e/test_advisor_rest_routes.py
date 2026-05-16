"""Smoke test: advisor REST routes are mounted and respond with 2xx.

This is the contract test the operator wanted: "verify endpoints exist and
return JSON, not 404". Runs against an isolated FastAPI TestClient so it does
not interfere with the dev server.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.api.advisor_routes as advisor_routes
from sylion.api.advisor_routes import router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_advisor_health(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["module"] == "sylion.aeis.advisor"


def test_list_cards_returns_envelope(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/cards")
    assert r.status_code == 200
    data = r.json()
    assert "cards" in data
    assert isinstance(data["cards"], list)


def test_get_card_404_for_unknown(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/cards/does-not-exist")
    assert r.status_code in (404, 500)


def test_handle_card_action_validates_input(client: TestClient) -> None:
    r = client.post("/api/v1/advisor/cards/x/actions", json={})
    assert r.status_code in (400, 422, 500)


def test_preferences_listing_empty_user(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/preferences", params={"user_id": "test-user"})
    assert r.status_code == 200
    data = r.json()
    assert "preferences" in data


def test_onboarding_state_default(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/onboarding/state", params={"user_id": "test-user"})
    assert r.status_code == 200
    data = r.json()
    assert data["step"] >= 1
    assert isinstance(data["values"], dict)


def test_onboarding_step_save_and_complete(client: TestClient) -> None:
    user = "test-onboarding-user"

    r = client.put(
        "/api/v1/advisor/onboarding/step/2",
        params={"user_id": user},
        json={"values": {"operator_name": "Tester"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["step"] == 2
    assert data["values"]["operator_name"] == "Tester"
    assert 2 in data["completed_steps"]

    # Save another step and ensure values accumulate
    r = client.put(
        "/api/v1/advisor/onboarding/step/3",
        params={"user_id": user},
        json={"values": {"default_project_domain": "research"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["values"]["operator_name"] == "Tester"
    assert data["values"]["default_project_domain"] == "research"

    # Complete the wizard
    r = client.post(
        "/api/v1/advisor/onboarding/complete",
        params={"user_id": user},
        json={"values": {}},
    )
    assert r.status_code == 200
    assert r.json().get("completed_at")

    # Has completed flag
    r = client.get("/api/v1/advisor/onboarding/has_completed", params={"user_id": user})
    assert r.status_code == 200
    assert r.json()["completed"] is True


def test_phase1_onboarding_complete_acceptance_and_reset(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = "test-phase1-user"
    workspace = tmp_path / "phase1-workspace"
    chain_dir = tmp_path / "chains"
    chain_dir.mkdir()
    monkeypatch.setattr(advisor_routes, "resolve_audit_chain_dir", lambda default=None: chain_dir)
    monkeypatch.setattr(
        advisor_routes,
        "resolve_audit_chain_path",
        lambda filename, default_dir=None: chain_dir / filename,
    )

    r = client.delete("/api/v1/advisor/onboarding/state", params={"user_id": user})
    assert r.status_code == 200
    assert r.json()["step"] == 1

    values = {
        "language": "pl",
        "operator_name": "Tester",
        "display_name": "Tester",
        "system_name": "tester",
        "email_skipped": True,
        "operator_role": "solo",
        "timezone": "Europe/Warsaw",
        "timezone_confirmed": True,
        "workspace_path": str(workspace),
        "backup_frequency": "daily",
        "backup_retention_days": 30,
        "security_mode": "low_security",
        "low_security_confirm": "ROZUMIEM",
        "goals": ["internal_apps"],
        "initial_autonomy_preset": "balanced",
        "notification_channel": "in_app",
        "telemetry_consent": False,
        "tutorial_mode": "skip",
        "tutorial_project": "",
        "demo_mode_accepted": True,
    }
    r = client.post(
        "/api/v1/advisor/onboarding/phase1/complete",
        params={"user_id": user},
        json={"values": values},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["phase1_completed_at"]
    assert body["values"]["workspace_path"] == str(workspace)
    assert body["phase1_acceptance"]["accepted"] is True
    assert body["phase1_acceptance"]["passed"] == body["phase1_acceptance"]["total"]
    assert len(body["workspace_bootstrap"]["folders"]) == 15
    for folder in body["workspace_bootstrap"]["folders"]:
        assert Path(folder).exists()

    r = client.get("/api/v1/advisor/onboarding/phase1/acceptance-test", params={"user_id": user})
    assert r.status_code == 200
    assert r.json()["accepted"] is True

    r = client.get("/api/v1/advisor/onboarding/has_completed", params={"user_id": user})
    assert r.status_code == 200
    assert r.json()["completed"] is True

    r = client.delete("/api/v1/advisor/onboarding/state", params={"user_id": user})
    assert r.status_code == 200
    assert r.json() == {"step": 1, "completed_steps": [], "values": {}}

    r = client.get("/api/v1/advisor/onboarding/has_completed", params={"user_id": user})
    assert r.status_code == 200
    assert r.json()["completed"] is False


def test_phase1_storage_validation_accepts_missing_workspace_parent(
    client: TestClient,
    tmp_path,
) -> None:
    workspace = tmp_path / "missing-parent" / "operator"
    r = client.post(
        "/api/v1/advisor/onboarding/phase1/storage/validate",
        params={"user_id": "test-phase1-storage-user"},
        json={"path": str(workspace)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["would_create"] is True
    assert body["probe_path"] == str(tmp_path)
    assert "workspace_parent_will_be_created" in body["warnings"]
    assert "parent_missing" not in body["errors"]
    assert not workspace.exists()


def test_onboarding_responses_redact_credentials(client: TestClient) -> None:
    user = "test-onboarding-secrets"
    raw_key = "sk-test-abcdefghijklmnopqrstuvwxyz"
    raw_token = "hcloud-token-abcdefghijklmnopqrstuvwxyz"

    r = client.put(
        "/api/v1/advisor/onboarding/step/2",
        params={"user_id": user},
        json={
            "values": {
                "api_keys": [{"id": "k1", "provider": "openai", "key": raw_key}],
                "hosting_providers": [
                    {"id": "h1", "provider": "hetzner", "fields": {"token": raw_token, "project": "audit"}}
                ],
            }
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["values"]["api_keys"][0]["key"] != raw_key
    assert body["values"]["api_keys"][0]["key_masked"] is True
    assert body["values"]["hosting_providers"][0]["fields"]["token"] != raw_token
    assert body["values"]["hosting_providers"][0]["fields"]["project"] == "audit"

    r = client.get("/api/v1/advisor/onboarding/state", params={"user_id": user})
    assert r.status_code == 200
    body = r.json()
    assert body["values"]["api_keys"][0]["key"] != raw_key
    assert body["values"]["hosting_providers"][0]["fields"]["token"] != raw_token


def test_onboarding_complete_persists_runtime_keys_and_connectors(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sylion.security.cloud_connectors import reset_cloud_connector_store
    from sylion.security.key_vault import reset_key_vault
    from sylion.cognitive.model_registry import reset_model_registry
    from sylion.monitoring.model_budget import reset_model_budget

    monkeypatch.setattr(advisor_routes, "resolve_audit_chain_dir", lambda default=None: tmp_path)
    monkeypatch.setattr(
        advisor_routes,
        "resolve_audit_chain_path",
        lambda filename, default_dir=None: tmp_path / filename,
    )
    vault = reset_key_vault(db_path=tmp_path / "vault.db")
    connectors = reset_cloud_connector_store(db_path=tmp_path / "connectors.db")
    registry = reset_model_registry(db_path=tmp_path / "models.db")
    budgets = reset_model_budget(db_path=str(tmp_path / "budgets.db"))

    raw_key = "sk-test-valid-runtime-key-1234567890"
    bad_key = "AIza-invalid-google-key"
    hetzner_token = "hcloud-runtime-test-token-1234567890"

    r = client.post(
        "/api/v1/advisor/onboarding/complete",
        params={"user_id": "runtime-persist-user"},
        json={
            "values": {
                "api_keys": [
                    {
                        "id": "openai-key",
                        "provider": "openai",
                        "key": raw_key,
                        "validation_status": "ok",
                    },
                    {
                        "id": "google-key",
                        "provider": "google",
                        "key": bad_key,
                        "validation_status": "error",
                    },
                ],
                "blocked_providers": ["google"],
                "council_size": 3,
                "cost_ceilings": {"low": 0.05, "medium": 0.25, "high": 1.25, "critical": 4.0},
                "hosting_providers": [
                    {
                        "id": "hetzner-1",
                        "provider": "hetzner",
                        "fields": {"token": hetzner_token, "project": "audit"},
                    }
                ],
            }
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["values"]["api_keys"][0]["key"] != raw_key
    assert body["runtime_setup"]["api_keys"]["attempted"] == 1
    assert body["runtime_setup"]["connectors"]["attempted"] == 1
    assert len(body["runtime_setup"]["model_plane"]["models_registered"]) >= 1
    assert len(body["runtime_setup"]["model_plane"]["council_members"]) >= 1

    keys = vault.list_keys()
    assert len(keys) == 1
    assert keys[0]["provider"] == "openai"
    assert keys[0]["is_active"] == 1
    assert vault.get_decrypted_key(keys[0]["key_id"]) == raw_key

    registered = connectors.list(provider="hetzner")
    assert len(registered) == 1
    assert registered[0]["scope"] == "audit"
    assert registered[0]["credentials_masked"]["token"].endswith("7890")
    assert connectors.get_decrypted_credentials(registered[0]["connector_id"])["token"] == hetzner_token
    assert len(registry.list_models(provider="openai")) == 1
    assert len(budgets.list_budgets()) >= 1
    assert len(vault.list_council_members()) >= 1

    r = client.post(
        "/api/v1/advisor/onboarding/complete",
        params={"user_id": "runtime-persist-user"},
        json={
            "values": {
                "api_keys": [
                    {
                        "id": "openai-key",
                        "provider": "openai",
                        "key": raw_key,
                        "validation_status": "ok",
                    }
                ],
                "hosting_providers": [
                    {
                        "id": "hetzner-1",
                        "provider": "hetzner",
                        "fields": {"token": hetzner_token, "project": "audit"},
                    }
                ],
            }
        },
    )
    assert r.status_code == 200
    assert len(vault.list_keys(provider="openai")) == 1
    assert len(connectors.list(provider="hetzner")) == 1


def test_recent_audit_reads_real_hash_chains(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(advisor_routes, "resolve_audit_chain_dir", lambda default=None: tmp_path)
    monkeypatch.setattr(
        advisor_routes,
        "resolve_audit_chain_path",
        lambda filename, default_dir=None: tmp_path / filename,
    )

    r = client.put(
        "/api/v1/advisor/onboarding/step/2",
        params={"user_id": "audit-user"},
        json={"values": {"default_project_domain": "software"}},
    )
    assert r.status_code == 200

    r = client.get("/api/v1/advisor/audit/recent", params={"limit": 10})
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert entries
    assert entries[0]["action"] == "advisor.onboarding.step_saved"
    assert entries[0]["module"] == "advisor.onboarding"
    assert entries[0]["actor"] == "operator"
    assert entries[0]["chain_file"] == "advisor_audit.jsonl"


def test_monitoring_snapshot_shape(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/monitoring/snapshot")
    assert r.status_code == 200
    data = r.json()
    for key in ("projects", "throughput", "cost_vs_budget", "alerts", "subscription_recommendations"):
        assert key in data
    assert isinstance(data["projects"], list)


def test_subscriptions_routes_exist(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription._db.list_active_subscriptions",
        lambda operator_id: [],
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription._db.create_subscription",
        lambda **kwargs: {"subscription_id": "sub-test"},
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.subscription._db.deactivate_subscription",
        lambda sub_id: True,
    )

    r = client.get("/api/v1/advisor/subscriptions")
    assert r.status_code == 200
    assert "subscriptions" in r.json()

    r = client.post(
        "/api/v1/advisor/subscriptions",
        json={
            "provider_id": "anthropic",
            "plan_id": "claude-pro",
            "models_covered": ["claude-sonnet-4-6"],
        },
    )
    assert r.status_code == 200
    assert r.json()["subscription_id"] == "sub-test"

    r = client.delete("/api/v1/advisor/subscriptions/sub-test")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_funding_grants_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/funding/grants")
    assert r.status_code == 200
    data = r.json()
    assert "grants" in data
    assert isinstance(data["grants"], list)


def test_funding_deadlines_returns_list(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/funding/deadlines")
    assert r.status_code == 200
    assert "deadlines" in r.json()


def test_project_lifecycle_returns_16_phases(client: TestClient) -> None:
    r = client.get("/api/v1/advisor/projects/proj-1/lifecycle")
    assert r.status_code == 200
    data = r.json()
    assert data["project_id"] == "proj-1"
    assert len(data["phases"]) == 16
    for phase in data["phases"]:
        assert phase["hook_id"].startswith("H")
        assert "hook_event_type" in phase
