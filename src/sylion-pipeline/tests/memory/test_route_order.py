import importlib.util
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.memory.evidence_store import reset_evidence_store
from sylion.memory.indexer import reset_indexer
from sylion.memory.retrieval import reset_retrieval
from sylion.memory.self_model_store import reset_self_model_store


def _reset_all() -> None:
    reset_indexer()
    reset_evidence_store()
    reset_retrieval()
    reset_self_model_store()


def _load_router():
    routes_path = Path(__file__).resolve().parents[2] / "sylion" / "api" / "memory_routes.py"
    spec = importlib.util.spec_from_file_location("b3_memory_routes_test_module", routes_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.router


def test_evidence_stats_route_is_not_shadowed():
    _reset_all()

    app = FastAPI()
    app.include_router(_load_router())
    client = TestClient(app)

    response = client.get("/api/v1/memory/evidence/stats")

    assert response.status_code == 200
    assert "total_evidence" in response.json()

    _reset_all()
