from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import sylion.api.integration_orchestrator_routes as routes


class FakeOrchestrator:
    def __init__(self):
        self._builds: dict[str, dict] = {
            "bld_seed_001": {
                "build_id": "bld_seed_001",
                "name": "Seed Build",
                "description": "Existing build",
                "status": "draft",
                "patch_ids": ["patch-1"],
                "module_ids": ["core.worker"],
                "validation_results": {},
                "evidence_pack": None,
                "error_log": None,
                "metadata": {},
                "created_at": 1.0,
                "updated_at": 1.0,
            }
        }
        self._results = {
            "bld_seed_001": [
                {
                    "result_id": "res_seed_001",
                    "build_id": "bld_seed_001",
                    "stage": "contract_tests",
                    "success": True,
                    "stdout": "ok",
                    "stderr": "",
                    "duration_ms": 12,
                    "created_at": 2.0,
                }
            ]
        }

    def create_candidate_build(self, name, description="", patch_ids=None, module_ids=None, metadata=None):
        build = {
            "build_id": "bld_new_001",
            "name": name,
            "description": description,
            "status": "draft",
            "patch_ids": patch_ids or [],
            "module_ids": module_ids or [],
            "validation_results": {},
            "evidence_pack": None,
            "error_log": None,
            "metadata": metadata or {},
            "created_at": 3.0,
            "updated_at": 3.0,
        }
        self._builds[build["build_id"]] = build
        self._results[build["build_id"]] = []
        return build

    def list_candidate_builds(self, status=None):
        builds = list(self._builds.values())
        if status:
            builds = [build for build in builds if build["status"] == status]
        return sorted(builds, key=lambda build: build["created_at"], reverse=True)

    def get_candidate_build(self, build_id):
        return self._builds.get(build_id)

    def update_build_status(self, build_id, status):
        build = self._builds.get(build_id)
        if build is None:
            return None
        build["status"] = status
        build["updated_at"] += 1
        return build

    def delete_candidate_build(self, build_id):
        removed = self._builds.pop(build_id, None)
        self._results.pop(build_id, None)
        return removed is not None

    def run_validation(self, build_id, sandbox_dir=None):
        build = self._builds.get(build_id)
        if build is None:
            raise ValueError("missing build")
        build["status"] = "ready"
        result = {
            "build_id": build_id,
            "stages": {
                "contract_tests": {
                    "success": True,
                    "stdout": f"validated in {sandbox_dir or 'default'}",
                    "stderr": "",
                    "duration_ms": 10,
                }
            },
        }
        self._results[build_id].append(
            {
                "result_id": f"res_{build_id}",
                "build_id": build_id,
                "stage": "contract_tests",
                "success": True,
                "stdout": "validated",
                "stderr": "",
                "duration_ms": 10,
                "created_at": 4.0,
            }
        )
        return result

    def promote(self, build_id):
        return self.update_build_status(build_id, "promoted")

    def reject(self, build_id, reason=""):
        build = self.update_build_status(build_id, "rejected")
        if build is not None:
            build["error_log"] = reason
        return build

    def get_results_for_build(self, build_id):
        return self._results.get(build_id, [])


class FakeDriftDetector:
    def __init__(self):
        self._drifts = [
            {
                "drift_id": "drift_001",
                "description": "Worker contract drift",
                "source_module": "core.worker",
                "target_module": "core.integration",
                "severity": "warning",
                "status": "open",
            }
        ]

    def detect_all(self):
        return list(self._drifts)

    def list_drifts(self, status=None, severity=None, source_module=None):
        drifts = list(self._drifts)
        if status:
            drifts = [drift for drift in drifts if drift["status"] == status]
        if severity:
            drifts = [drift for drift in drifts if drift["severity"] == severity]
        if source_module:
            drifts = [drift for drift in drifts if drift["source_module"] == source_module]
        return drifts

    def get_drift_summary(self):
        return {
            "total_open": len(self._drifts),
            "by_type": {"contract": len(self._drifts)},
            "by_severity": {"warning": len(self._drifts)},
        }


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)

    fake_orchestrator = FakeOrchestrator()
    fake_drift_detector = FakeDriftDetector()
    monkeypatch.setattr(routes, "_get_orchestrator", lambda: fake_orchestrator)
    monkeypatch.setattr(routes, "_get_drift_detector", lambda: fake_drift_detector)

    return TestClient(app)


def test_candidate_build_routes_use_singular_integration_prefix(client: TestClient):
    listing = client.get("/api/v1/integration/builds")
    assert listing.status_code == 200
    assert listing.json()["builds"][0]["build_id"] == "bld_seed_001"

    created = client.post(
        "/api/v1/integration/builds",
        json={
            "name": "Build Contract Test",
            "description": "Validates frontend contract",
            "patch_ids": ["patch-2"],
            "module_ids": ["core.integration"],
            "metadata": {"source": "test"},
        },
    )
    assert created.status_code == 201
    build = created.json()
    assert build["build_id"] == "bld_new_001"
    assert build["module_ids"] == ["core.integration"]

    validate = client.post(
        "/api/v1/integration/builds/bld_new_001/validate",
        json={"sandbox_dir": "sandbox/contracts"},
    )
    assert validate.status_code == 200
    assert validate.json()["results"]["stages"]["contract_tests"]["success"] is True

    promote = client.post("/api/v1/integration/builds/bld_new_001/promote")
    assert promote.status_code == 200
    assert promote.json()["status"] == "promoted"

    reject = client.post("/api/v1/integration/builds/bld_seed_001/reject", json={"reason": "manual review"})
    assert reject.status_code == 200
    assert reject.json()["error_log"] == "manual review"

    results = client.get("/api/v1/integration/builds/bld_new_001/results")
    assert results.status_code == 200
    assert results.json()["results"][0]["stage"] == "contract_tests"


def test_drift_routes_use_singular_integration_prefix(client: TestClient):
    detect = client.post("/api/v1/integration/drift/detect")
    assert detect.status_code == 200
    assert detect.json()["count"] == 1

    listing = client.get("/api/v1/integration/drift", params={"severity": "warning"})
    assert listing.status_code == 200
    assert listing.json()["drifts"][0]["drift_id"] == "drift_001"

    summary = client.get("/api/v1/integration/drift/summary")
    assert summary.status_code == 200
    assert summary.json()["total_open"] == 1
