from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from sylion.api.app import app
from sylion.efficiency.circuit_breaker import get_circuit_breaker
from sylion.efficiency.config_drift import get_config_drift_detector
from sylion.integration.orchestrator import IntegrationOrchestrator
from sylion.security.key_vault import reset_key_vault

client = TestClient(app)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def test_efficiency_drift_route_returns_live_state():
    detector = get_config_drift_detector()
    module_id = _uid("drift")
    detector.set_baseline(module_id, "replicas", 2)
    detector.check_drift(module_id, {"replicas": 3})

    response = client.get("/api/v1/efficiency/drift")
    assert response.status_code == 200

    payload = response.json()
    assert payload["available"] is True
    assert payload["drift_detected"] is True
    assert "message" not in payload
    assert any(drift["module_id"] == module_id for drift in payload["drifts"])


def test_efficiency_circuits_route_returns_live_state():
    breaker = get_circuit_breaker()
    circuit_id = _uid("circuit")
    breaker.register_circuit(circuit_id, failure_threshold=2, recovery_timeout=1.0)
    breaker.record_failure(circuit_id)

    response = client.get("/api/v1/efficiency/circuits")
    assert response.status_code == 200

    payload = response.json()
    assert payload["available"] is True
    assert "message" not in payload
    assert any(circuit["circuit_id"] == circuit_id for circuit in payload["circuits"])


def test_worker_heartbeat_returns_updated_worker_payload():
    register = client.post(
        "/api/v1/workers",
        json={"name": "Regression Worker", "host": "localhost", "capacity": 1},
    )
    assert register.status_code == 201
    worker_id = register.json()["worker_id"]

    response = client.post(
        f"/api/v1/workers/{worker_id}/heartbeat",
        json={"load": {"cpu": 0.42, "jobs": 1}},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["heartbeat_recorded"] is True
    assert payload["worker"]["worker_id"] == worker_id
    assert payload["worker"]["last_heartbeat"] is not None
    assert payload["load"] == {"cpu": 0.42, "jobs": 1}


def test_pipeline_submit_rejects_stub_runtime(monkeypatch):
    monkeypatch.setenv("SYLION_LLM_PROVIDER", "stub")
    monkeypatch.delenv("SYLION_LLM_MODEL", raising=False)
    reset_key_vault(db_path=":memory:")

    response = client.post(
        "/api/v1/pipeline/ideas",
        json={"idea": "Build a production workflow", "context": {}},
    )

    assert response.status_code == 409, response.text
    payload = response.json()
    assert payload["detail"]["runtime"]["ready"] is False
    assert any("Stub provider is not allowed" in reason for reason in payload["detail"]["runtime"]["reasons"])


def test_contract_stage_fails_when_no_targets_exist(tmp_path: Path):
    orchestrator = IntegrationOrchestrator(db_path=":memory:")

    result = orchestrator._run_stage("bld_missing_contracts", "contract_tests", cwd=str(tmp_path))

    assert result["success"] is False
    assert "No contract_tests targets discovered" in result["stderr"]


def test_contract_stage_uses_real_pytest_targets(tmp_path: Path, monkeypatch):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    contract_test = tests_dir / "test_contract_sample.py"
    contract_test.write_text("def test_contract_sample():\n    assert True\n", encoding="utf-8")

    recorded: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs):
        recorded["cmd"] = cmd
        recorded["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(cmd, 0, stdout="1 passed\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    orchestrator = IntegrationOrchestrator(db_path=":memory:")
    result = orchestrator._run_stage("bld_contract_targets", "contract_tests", cwd=str(tmp_path))

    assert result["success"] is True
    assert recorded["cmd"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(contract_test.resolve()),
    ]
    assert recorded["cwd"] == str(tmp_path.resolve())
