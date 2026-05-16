from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.api.rebuild_routes as rebuild_routes
from sylion.rebuild.cft_runner import CFTRunner
from sylion.rebuild.cutover_controller import CutoverController
from sylion.rebuild.lpw_manager import LPWManager
from sylion.rebuild.orchestrator import RebuildOrchestrator


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(rebuild_routes.router)
    return TestClient(app)


def test_cft_route_missing_actual_hash_returns_422(monkeypatch):
    runner = CFTRunner(db_path=":memory:")
    suite = runner.create_suite("Route Suite", module_id="mod-1")
    monkeypatch.setattr(rebuild_routes, "get_cft_runner", lambda: runner)

    resp = _client().post(
        f"/api/v1/rebuild/cft/suites/{suite['suite_id']}/run",
        params={"golden_hash": "abc123"},
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["status"] == "failed_closed"
    assert detail["error_code"] == "actual_hash_required"


def test_lpw_restore_route_missing_snapshot_returns_409(monkeypatch):
    mgr = LPWManager(db_path=":memory:")
    mgr.record("mod-1", "1.0.0")
    monkeypatch.setattr(rebuild_routes, "get_lpw_manager", lambda: mgr)

    resp = _client().post("/api/v1/rebuild/lpw/mod-1/restore")

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["status"] == "failed_closed"
    assert detail["error_code"] == "snapshot_hash_missing"


def test_orchestrator_execute_route_without_executor_returns_409(monkeypatch):
    orch = RebuildOrchestrator(db_path=":memory:")
    plan = orch.create_plan("Route Plan")
    orch.add_step(plan["plan_id"], "mod-1")
    monkeypatch.setattr(rebuild_routes, "get_rebuild_orchestrator", lambda: orch)

    resp = _client().post(
        f"/api/v1/rebuild/orchestrator/plans/{plan['plan_id']}/execute"
    )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["status"] == "failed_closed"
    assert detail["error_code"] == "step_executor_missing"


def test_cutover_rollback_route_pending_plan_returns_409(monkeypatch):
    ctrl = CutoverController(db_path=":memory:")
    plan = ctrl.create_plan("mod-1")
    monkeypatch.setattr(rebuild_routes, "get_cutover_controller", lambda: ctrl)

    resp = _client().post(
        f"/api/v1/rebuild/cutover/plans/{plan['plan_id']}/rollback"
    )

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["status"] == "failed_closed"
    assert detail["error_code"] == "plan_not_executed"
