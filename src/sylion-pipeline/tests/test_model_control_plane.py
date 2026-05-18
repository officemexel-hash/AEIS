from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.api.model_control_plane_routes as routes
from sylion.api.model_control_plane_routes import router
from sylion.cognitive.model_control_plane import ModelControlPlane, reset_model_control_plane


def _plane(tmp_path) -> ModelControlPlane:
    reset_model_control_plane()
    return ModelControlPlane(db_path=tmp_path / "model-control-plane.sqlite")


def _register_two_models(plane: ModelControlPlane) -> None:
    plane.register_provider(
        "openai",
        display_name="OpenAI",
        keys_ref="vault://providers/openai",
        quotas={"requests_per_minute": 120},
        models=[
            {
                "model_id": "mcp-primary",
                "display_name": "MCP Primary",
                "capabilities": ["planning", "code_generation"],
                "model_family": "gpt",
                "context_window": 128000,
                "cost_profile": {
                    "cost_per_1k_in": 0.01,
                    "cost_per_1k_out": 0.03,
                    "cost_per_1k_tokens": 0.02,
                },
            },
            {
                "model_id": "mcp-fallback",
                "display_name": "MCP Fallback",
                "capabilities": ["planning", "code_generation"],
                "model_family": "gpt-mini",
                "context_window": 64000,
                "cost_profile": {
                    "cost_per_1k_in": 0.002,
                    "cost_per_1k_out": 0.006,
                    "cost_per_1k_tokens": 0.004,
                },
            },
        ],
    )


def test_provider_registration_writes_registry_router_and_provider_plane(tmp_path):
    plane = _plane(tmp_path)
    _register_two_models(plane)

    provider = plane.get_provider("openai")
    assert provider["keys_ref"] == "vault://providers/openai"
    assert len(provider["models"]) == 2

    registry_model = plane.model_registry.get_model("mcp-primary")
    assert registry_model["provider"] == "openai"
    assert registry_model["context_window"] == 128000
    assert {cap["task_type"] for cap in registry_model["capabilities"]} >= {"planning", "code_generation"}

    routed = plane.model_router.route_request("planning", complexity="high", budget=0.05)
    assert routed["model_id"] == "mcp-primary"


def test_routing_resolve_enforces_budget_before_model_selection(tmp_path):
    plane = _plane(tmp_path)
    _register_two_models(plane)
    plane.set_budget("mcp-primary", daily_limit=0.01, monthly_limit=0.10, provider="openai")
    plane.set_budget("mcp-fallback", daily_limit=10.0, monthly_limit=20.0, provider="openai")
    plane.set_routing("J1", "mcp-primary", fallback_chain=["mcp-fallback"])

    first = plane.resolve_route("J1", task_type="planning")
    assert first["selected_model_id"] == "mcp-primary"
    assert first["budget_enforced"] is True

    plane.record_usage("mcp-primary", tokens=1000, cost=0.02, task_type="planning")
    second = plane.resolve_route("J1", task_type="planning")
    assert second["selected_model_id"] == "mcp-fallback"
    assert second["fallback_used"] is True
    assert second["attempts"][0]["reason"] == "budget_blocked"


def test_route_and_council_config_reject_unknown_models(tmp_path):
    plane = _plane(tmp_path)
    _register_two_models(plane)

    with pytest.raises(ValueError, match="ModelRegistry"):
        plane.set_routing("J2", "missing-model")

    with pytest.raises(ValueError, match="ModelRegistry"):
        plane.configure_council(
            "project-x",
            quorum=2,
            roles=["architect", "critic"],
            model_assignments={"architect": "missing-model"},
        )


def test_council_config_assignments_reference_registry_models(tmp_path):
    plane = _plane(tmp_path)
    _register_two_models(plane)

    config = plane.configure_council(
        "project-x",
        quorum=2,
        roles=["architect", "critic"],
        weights={"architect": 0.7, "critic": 0.3},
        model_assignments={"architect": "mcp-primary", "critic": "mcp-fallback"},
    )

    assert config["quorum"] == 2
    assert config["model_assignments"]["architect"] == "mcp-primary"
    assert plane.snapshot()["control_checks"]["all_routes_reference_registered_models"] is True


def test_model_control_plane_routes_cover_provider_routing_council_and_snapshot(tmp_path):
    app = FastAPI()
    app.include_router(router)
    routes._control_plane = ModelControlPlane(db_path=tmp_path / "routes.sqlite")
    client = TestClient(app)

    provider = client.post(
        "/api/v1/model-control-plane/providers",
        json={
            "provider_id": "route-openai",
            "display_name": "Route OpenAI",
            "keys_ref": "vault://providers/route-openai",
            "models": [
                {
                    "model_id": "route-primary",
                    "display_name": "Route Primary",
                    "capabilities": ["planning"],
                    "cost_profile": {"cost_per_1k_tokens": 0.02},
                },
                {
                    "model_id": "route-fallback",
                    "display_name": "Route Fallback",
                    "capabilities": ["planning"],
                    "cost_profile": {"cost_per_1k_tokens": 0.01},
                },
            ],
        },
    )
    assert provider.status_code == 201

    budget = client.post(
        "/api/v1/model-control-plane/budgets",
        json={"model_id": "route-primary", "daily_limit": 1.0, "monthly_limit": 5.0},
    )
    assert budget.status_code == 201

    route = client.post(
        "/api/v1/model-control-plane/routing",
        json={"stage": "J2", "model_id": "route-primary", "fallback_chain": ["route-fallback"]},
    )
    assert route.status_code == 201

    resolved = client.post(
        "/api/v1/model-control-plane/routing/resolve",
        json={"stage": "J2", "task_type": "planning"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["selected_model_id"] == "route-primary"

    council = client.post(
        "/api/v1/model-control-plane/council-config",
        json={
            "project_id": "route-project",
            "quorum": 1,
            "roles": ["architect"],
            "model_assignments": {"architect": "route-primary"},
        },
    )
    assert council.status_code == 201

    snapshot = client.get("/api/v1/model-control-plane/snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["providers"][0]["provider_id"] == "route-openai"
    assert body["routes"][0]["stage"] == "J2"
    assert body["council_configs"][0]["project_id"] == "route-project"

    routes._control_plane = None
