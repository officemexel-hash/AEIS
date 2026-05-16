from __future__ import annotations


def test_app_mounts_advisor_and_orchestration_routers() -> None:
    from sylion.api.app import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/advisor/health" in paths
    assert "/api/v1/orchestration/health" in paths
