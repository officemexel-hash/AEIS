from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sylion.api.app import app
import sylion.api.provider_catalog_routes as routes
from sylion.cognitive.model_registry import ModelRegistry
from sylion.security.key_vault import KeyVault


client = TestClient(app)
BASE = "/api/v1/provider-catalog"


@pytest.fixture(autouse=True)
def _isolated_catalog(monkeypatch):
    routes._registry = ModelRegistry()
    routes._vault = KeyVault()
    monkeypatch.setattr(
        routes,
        "_probe_local_endpoints",
        lambda: {
            "ollama": {
                "provider": "ollama",
                "endpoint": "http://127.0.0.1:11434",
                "status": "healthy",
                "latency_ms": 12,
                "models": ["qwen2.5:7b-instruct", "nomic-embed-text"],
                "raw_models": [{"name": "qwen2.5:7b-instruct"}, {"name": "nomic-embed-text"}],
                "trigger": "ollama_tags",
                "error": "",
            },
            "lmstudio": {
                "provider": "lmstudio",
                "endpoint": "http://localhost:1234",
                "status": "unavailable",
                "latency_ms": 1,
                "models": [],
                "raw_models": [],
                "trigger": "openai_compatible_models",
                "error": "offline",
            },
            "llamacpp": {
                "provider": "llamacpp",
                "endpoint": "http://localhost:8080",
                "status": "unavailable",
                "latency_ms": 1,
                "models": [],
                "raw_models": [],
                "trigger": "openai_compatible_models",
                "error": "offline",
            },
            "vllm": {
                "provider": "vllm",
                "endpoint": "http://localhost:8001",
                "status": "unavailable",
                "latency_ms": 1,
                "models": [],
                "raw_models": [],
                "trigger": "openai_compatible_models",
                "error": "offline",
            },
        },
    )
    yield
    routes._registry = None
    routes._vault = None


def test_templates_expose_phase2_catalog():
    response = client.get(f"{BASE}/templates")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 24
    providers = {item["provider"] for item in data["templates"]}
    assert {"anthropic", "openai", "ollama", "replicate", "elevenlabs"} <= providers
    assert data["custom_template"]["provider"] == "custom-openai-compatible"


def test_snapshot_builds_three_catalog_inputs_and_acceptance():
    response = client.get(BASE)
    assert response.status_code == 200
    data = response.json()

    assert data["providers"]
    assert data["models"]
    assert data["capability_matrix"]
    assert data["priority_chains"]
    assert data["acceptance"]["accepted"] is True

    text_row = next(row for row in data["capability_matrix"] if row["id"] == "text_generation")
    assert text_row["available"] is True
    assert any(model["provider"] == "ollama" for model in text_row["models"])


def test_default_vault_secret_is_warning_when_fernet_encryption_is_available(monkeypatch):
    monkeypatch.delenv("SYLION_VAULT_SECRET", raising=False)
    routes._vault.store_key("openai", "sk-test-provider-catalog", "Test key")

    response = client.get(f"{BASE}/acceptance")
    assert response.status_code == 200
    data = response.json()

    secret = next(check for check in data["checks"] if check["id"] == "secret_encryption")
    assert data["accepted"] is True
    assert secret["status"] in {"pass", "warn"}
    assert secret["hard_block"] is False
    assert not data["hard_blocks"]


def test_capability_gaps_drive_acquisition_advisor():
    response = client.get(BASE)
    assert response.status_code == 200
    data = response.json()

    gap_ids = {item["capability"] for item in data["gaps"]}
    assert "image_generation" in gap_ids
    suggestions = {item["provider"] for item in data["acquisition_advisor"]}
    assert suggestions & {"openrouter", "replicate"}


def test_custom_provider_registers_model_without_plaintext_key_response():
    response = client.post(
        f"{BASE}/custom-provider",
        json={
            "provider_id": "localai-private",
            "display_name": "LocalAI Private",
            "base_url": "http://localhost:8088/v1",
            "model_id": "private-model",
            "api_key": "sk-private-test",
            "capabilities": ["text_generation", "code_generation"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "configured"
    assert data["model"]["model_id"] == "private-model"
    assert "sk-private-test" not in str(data)


def test_auto_arrange_council_creates_members_and_active_hierarchy():
    response = client.post(f"{BASE}/council/auto-arrange", json={"force": False, "max_members": 4})
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["member_count"] >= 4
    assert data["hierarchy"]["is_active"] in {1, True}
    assert len(data["hierarchy"]["levels"]) >= 4
    assert all("influence_percent" in level for level in data["hierarchy"]["levels"])
