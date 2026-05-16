import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.skills.registry as registry_mod
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
    yield
    registry_mod._registry = None
    reset_skills_runtime()


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
