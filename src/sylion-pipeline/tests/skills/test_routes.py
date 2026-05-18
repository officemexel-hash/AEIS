import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.skills.registry as registry_mod
from sylion.skills.demand_signal import reset_demand_signal_analyzer
from sylion.skills.executor import reset_skills_executor
from sylion.skills.integration import reset_skill_integration_layer
from sylion.skills.runtime import reset_skills_runtime


def _load_router():
    routes_path = Path(__file__).resolve().parents[2] / "sylion" / "api" / "skills_routes.py"
    spec = importlib.util.spec_from_file_location("b1_skills_routes_test_module", routes_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.router


@pytest.fixture(autouse=True)
def _reset_singletons():
    registry_mod._registry = None
    reset_skills_runtime()
    reset_skills_executor()
    reset_demand_signal_analyzer()
    reset_skill_integration_layer()
    yield
    registry_mod._registry = None
    reset_skills_runtime()
    reset_skills_executor()
    reset_demand_signal_analyzer()
    reset_skill_integration_layer()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(_load_router())
    return TestClient(app)


def test_register_list_state_and_execute_routes(client):
    register_response = client.post(
        "/api/v1/skills/register",
        json={
            "skill_id": "route.echo",
            "name": "route.echo",
            "entry_point": "sylion.skills.catalog:seed_echo_handler",
            "inputs": [{"name": "text", "type": "string", "required": True}],
            "outputs": [{"name": "output", "type": "string"}],
            "steps": [
                "Read the text payload.",
                "Return the same text.",
            ],
        },
    )
    assert register_response.status_code == 201

    list_response = client.get("/api/v1/skills")
    assert list_response.status_code == 200
    loaded_ids = {skill["skill_id"] for skill in list_response.json()["skills"]}
    assert "route.echo" in loaded_ids

    state_response = client.get("/api/v1/skills/route.echo/state")
    assert state_response.status_code == 200
    assert state_response.json()["loaded"] is True

    execute_response = client.post(
        "/api/v1/skills/route.echo/execute",
        json={"context": {"text": "hello"}},
    )
    assert execute_response.status_code == 201
    assert execute_response.json()["output"] == "hello"


def test_integration_routes_execute_pipeline_dispatch_and_demand(client):
    register_response = client.post(
        "/api/v1/skills/register",
        json={
            "skill_id": "route.pipeline",
            "name": "route.pipeline",
            "entry_point": "sylion.skills.catalog:seed_echo_handler",
            "inputs": [{"name": "text", "type": "string", "required": True}],
            "outputs": [{"name": "output", "type": "string"}],
        },
    )
    assert register_response.status_code == 201

    publish_response = client.post("/api/v1/skills/skills/route.pipeline/publish")
    assert publish_response.status_code == 200

    pipeline_response = client.post(
        "/api/v1/skills/integration/pipeline-step",
        json={
            "skill_id": "route.pipeline",
            "inputs": {"text": "pipeline-route"},
            "project_id": "project-route",
            "pipeline_id": "W10",
            "step_id": "step-1",
            "actor_id": "operator@example.com",
        },
    )
    assert pipeline_response.status_code == 201
    pipeline_json = pipeline_response.json()
    assert pipeline_json["ok"] is True
    assert pipeline_json["source"] == "skills.pipeline"
    assert pipeline_json["evidence_id"].startswith("ev_")

    dispatch_response = client.post(
        "/api/v1/skills/integration/dispatch",
        json={
            "skill_id": "route.pipeline",
            "inputs": {"text": "dispatch-route"},
            "project_id": "project-route",
            "dispatch_source": "J5",
        },
    )
    assert dispatch_response.status_code == 201
    assert dispatch_response.json()["source"] == "skills.dispatch"

    demand_response = client.post(
        "/api/v1/skills/integration/demand",
        json={
            "signal_type": "pipeline_needs_skill",
            "source": "W10",
            "skill_id": "route.pipeline",
            "confidence": 0.9,
            "details": {"pipeline_id": "W10"},
        },
    )
    assert demand_response.status_code == 201
    assert demand_response.json()["report"]["signal_count"] >= 1
