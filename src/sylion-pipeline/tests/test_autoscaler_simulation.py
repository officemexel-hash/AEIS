from __future__ import annotations

from fastapi.testclient import TestClient

import sylion.api.autoscaler_routes as autoscaler_routes
from sylion.api.app import app
from sylion.core.evidence_spine import EvidenceSpine
from sylion.worker.autoscaler import (
    AutoscalerSignal,
    AutoscalerSimulationProfile,
    AutoscalerSimulationRunner,
    reset_autoscaler_simulation_runner,
)
from sylion.worker.registry import reset_worker_registry


def test_autoscaler_simulation_exercises_scale_up_down_and_cooldown():
    runner = AutoscalerSimulationRunner(evidence_spine=EvidenceSpine(":memory:"))

    result = runner.run()

    assert result["status"] == "pass"
    assert result["checks"]["scale_up_seen"] is True
    assert result["checks"]["scale_down_seen"] is True
    assert result["checks"]["cooldown_block_seen"] is True
    assert result["checks"]["no_flapping"] is True
    assert result["evidence_id"]


def test_autoscaler_simulation_cooldown_prevents_flapping():
    runner = AutoscalerSimulationRunner(evidence_spine=EvidenceSpine(":memory:"))
    profile = AutoscalerSimulationProfile(
        initial_workers=3,
        min_workers=2,
        max_workers=5,
        cooldown_sec=60,
        signals=[
            AutoscalerSignal(at_sec=0, queue_depth=20, cpu_pct=90, error_rate=0.0),
            AutoscalerSignal(at_sec=10, queue_depth=0, cpu_pct=5, error_rate=0.0),
            AutoscalerSignal(at_sec=20, queue_depth=20, cpu_pct=90, error_rate=0.0),
            AutoscalerSignal(at_sec=80, queue_depth=0, cpu_pct=5, error_rate=0.0),
        ],
    )

    result = runner.run(profile)

    assert result["checks"]["no_flapping"] is True
    assert result["decisions"][1]["action"] == "maintain"
    assert result["decisions"][1]["reason"] == "cooldown_active"


def test_autoscaler_simulation_route_runs_default_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("SYLION_WORKER_DB_PATH", str(tmp_path / "workers.sqlite"))
    reset_worker_registry()
    reset_autoscaler_simulation_runner()
    autoscaler_routes._autoscaler = None
    client = TestClient(app)

    response = client.post("/api/v1/workers/autoscaler/simulate", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pass"
    assert body["checks"]["scale_up_seen"] is True
    assert body["checks"]["scale_down_seen"] is True


def test_autoscaler_simulation_route_rejects_invalid_bounds():
    client = TestClient(app)

    response = client.post(
        "/api/v1/workers/autoscaler/simulate",
        json={"initial_workers": 1, "min_workers": 2, "max_workers": 6},
    )

    assert response.status_code == 400
    assert "initial_workers must be within min/max bounds" in response.json()["detail"]
