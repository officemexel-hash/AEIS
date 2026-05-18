"""
SYLION API -- Quality routes.

Endpoints for: golden_set_registry, regression_detector, test_runner.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from sylion.quality.golden_set_registry import get_golden_set_registry
from sylion.quality.regression_detector import get_regression_detector
from sylion.quality.test_runner import get_test_runner
from sylion.security.rbac import requires_role

router = APIRouter(prefix="/api/v1/quality", tags=["quality"])


class LoadTestProfileRequest(BaseModel):
    name: str = "aeis_10x_peak"
    expected_peak_operations: int = Field(default=25, ge=1, le=500)
    peak_multiplier: int = Field(default=10, ge=10, le=100)
    target_p99_ms: float = Field(default=500.0, gt=0)
    max_db_connections: int = Field(default=5, ge=1, le=100)
    max_memory_growth_bytes: int = Field(default=8 * 1024 * 1024, ge=1)
    worker_count: int = Field(default=4, ge=1, le=100)
    dispatch_target_p99_ms: float = Field(default=500.0, gt=0)
    metadata: dict[str, object] = Field(default_factory=dict)


def _model_dump(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _load_test_runner():
    from sylion.quality.load_test import get_load_test_runner

    db_path = os.environ.get("SYLION_LOAD_TEST_DB_PATH") or os.environ.get("SYLION_DB_PATH")
    return get_load_test_runner(db_path=db_path)


# ---------------------------------------------------------------------------
# Golden Set Registry
# ---------------------------------------------------------------------------

@router.post("/golden-sets", status_code=201)
def register_golden_set(set_id: str, name: str, description: str = "",
                        module_id: str = "", test_type: str = "contract",
                        input: str = "", expected_output: str = ""):
    """Register a new golden test set."""
    reg = get_golden_set_registry()
    return reg.register(set_id, name, description=description,
                        module_id=module_id, input=input,
                        expected_output=expected_output,
                        metadata={"test_type": test_type})


@router.get("/golden-sets")
def list_golden_sets(module_id: str | None = None, active_only: bool = True):
    """List golden test sets."""
    reg = get_golden_set_registry()
    return {"sets": reg.list_sets(module_id=module_id, active_only=active_only)}


@router.get("/golden-sets/{set_id}")
def get_golden_set(set_id: str):
    """Get a golden test set by ID."""
    reg = get_golden_set_registry()
    result = reg.get_set(set_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Golden set {set_id} not found")
    return result


@router.post("/golden-sets/{set_id}/run")
def run_golden_test(set_id: str, actual_output: str = ""):
    """Run a golden test and compare outputs."""
    reg = get_golden_set_registry()
    try:
        return reg.run_test(set_id, actual_output=actual_output)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/golden-sets/{set_id}/results")
def get_golden_results(set_id: str, limit: int = 50):
    """Get test results for a golden set."""
    reg = get_golden_set_registry()
    return {"results": reg.get_results(set_id, limit=limit)}


@router.get("/golden-sets/pass-rate")
def golden_pass_rate(module_id: str | None = None):
    """Get pass rate across golden sets."""
    reg = get_golden_set_registry()
    return reg.get_pass_rate(module_id=module_id)


@router.post("/golden-sets/{set_id}/deactivate")
def deactivate_golden_set(set_id: str):
    """Deactivate a golden test set."""
    reg = get_golden_set_registry()
    ok = reg.deactivate(set_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Golden set {set_id} not found")
    return {"deactivated": set_id}


# ---------------------------------------------------------------------------
# Regression Detector
# ---------------------------------------------------------------------------

@router.post("/regression/baselines", status_code=201)
def set_regression_baseline(module_id: str, suite_id: str, run_id: str,
                            pass_rate: float = 1.0, avg_duration: int = 0):
    """Set a regression baseline for a module."""
    det = get_regression_detector()
    return det.set_baseline(module_id, suite_id, run_id,
                            pass_rate=pass_rate, avg_duration=avg_duration)


@router.get("/regression/baselines/{module_id}")
def get_regression_baseline(module_id: str):
    """Get the regression baseline for a module."""
    det = get_regression_detector()
    result = det.get_baseline(module_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No baseline for module {module_id}")
    return result


@router.post("/regression/check")
def check_regression(module_id: str, suite_id: str, current_pass_rate: float):
    """Check for regression against baseline."""
    det = get_regression_detector()
    return det.check_regression(module_id, suite_id, current_pass_rate)


@router.get("/regression/alerts")
def list_regression_alerts(module_id: str | None = None,
                           severity: str | None = None,
                           limit: int = 100):
    """List regression alerts."""
    det = get_regression_detector()
    return {"alerts": det.list_alerts(module_id=module_id,
                                      severity=severity, limit=limit)}


@router.post("/regression/alerts/{alert_id}/acknowledge")
def acknowledge_regression_alert(alert_id: str):
    """Acknowledge a regression alert."""
    det = get_regression_detector()
    ok = det.acknowledge_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"acknowledged": alert_id}


@router.get("/regression/stats")
def regression_stats():
    """Get regression detector statistics."""
    det = get_regression_detector()
    return det.get_stats()


# ---------------------------------------------------------------------------
# Production Load Test
# ---------------------------------------------------------------------------

@router.post("/load-tests/10x", status_code=201)
def run_load_test_10x(
    body: LoadTestProfileRequest,
    _user: str = Depends(requires_role("operator")),
):
    """Run the production-readiness 10x peak load test."""
    from sylion.quality.load_test import LoadTestProfile

    try:
        return _load_test_runner().run_10x(LoadTestProfile(**_model_dump(body)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/load-tests")
def list_load_tests(
    limit: int = Query(default=100, ge=1, le=500),
    _user: str = Depends(requires_role("operator")),
):
    return {"runs": _load_test_runner().list_runs(limit=limit)}


@router.get("/load-tests/{run_id}")
def get_load_test(
    run_id: str,
    _user: str = Depends(requires_role("operator")),
):
    run = _load_test_runner().get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Load test run {run_id} not found")
    return run


# ---------------------------------------------------------------------------
# Test Runner
# ---------------------------------------------------------------------------

@router.post("/test-suites", status_code=201)
def create_test_suite(suite_id: str, name: str, description: str = "",
                      test_type: str = "unit", module_id: str = "",
                      test_count: int = 0):
    """Create a new test suite."""
    runner = get_test_runner()
    return runner.create_suite(suite_id, name, description=description,
                               test_type=test_type, module_id=module_id,
                               test_count=test_count)


@router.get("/test-suites")
def list_test_suites(module_id: str | None = None, active_only: bool = True):
    """List test suites."""
    runner = get_test_runner()
    return {"suites": runner.list_suites(module_id=module_id,
                                         active_only=active_only)}


@router.post("/test-suites/{suite_id}/run", status_code=201)
def run_test_suite(suite_id: str):
    """Run a test suite."""
    runner = get_test_runner()
    return runner.run_suite(suite_id)


@router.get("/test-runs")
def list_test_runs(suite_id: str | None = None, limit: int = 100):
    """List test runs."""
    runner = get_test_runner()
    return {"runs": runner.list_runs(suite_id=suite_id, limit=limit)}


@router.get("/test-runs/{run_id}")
def get_test_run(run_id: str):
    """Get a test run by ID."""
    runner = get_test_runner()
    result = runner.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.get("/test-suites/{suite_id}/latest-run")
def get_latest_test_run(suite_id: str):
    """Get the latest run for a test suite."""
    runner = get_test_runner()
    result = runner.get_latest_run(suite_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No runs for suite {suite_id}")
    return result


@router.get("/test-stats")
def test_stats():
    """Get test runner statistics."""
    runner = get_test_runner()
    return runner.get_stats()
