from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.quality.load_test import reset_load_test_runner


@pytest.fixture(autouse=True)
def _reset_load_test_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_LOAD_TEST_DB_PATH", str(tmp_path / "load_tests.sqlite"))
    reset_load_test_runner()
    yield
    reset_load_test_runner()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_quality_load_test_route_runs_10x_and_persists_result(client):
    response = client.post(
        "/api/v1/quality/load-tests/10x",
        json={
            "name": "pytest_10x",
            "expected_peak_operations": 5,
            "peak_multiplier": 10,
            "target_p99_ms": 500,
            "worker_count": 2,
        },
    )

    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "pass"
    assert run["target_operations"] == 50
    assert run["payload"]["checks"]["db_connections_within_limit"] is True

    listed = client.get("/api/v1/quality/load-tests")
    assert listed.status_code == 200
    assert listed.json()["runs"][0]["run_id"] == run["run_id"]

    fetched = client.get(f"/api/v1/quality/load-tests/{run['run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run["run_id"]


def test_quality_load_test_route_rejects_below_10x_multiplier(client):
    response = client.post(
        "/api/v1/quality/load-tests/10x",
        json={
            "expected_peak_operations": 5,
            "peak_multiplier": 9,
        },
    )

    assert response.status_code == 422
