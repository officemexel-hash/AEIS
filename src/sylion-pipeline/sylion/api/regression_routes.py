"""
SYLION API -- Regression Detector routes.

Endpoints for RegressionDetector:
  create_baseline, update_baseline, get_baseline, list_baselines,
  run_regression_test, get_test_results, compare_metrics, get_regression_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/regression", tags=["Regression Detection"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_detector = None


def _get_detector():
    global _detector
    if _detector is not None:
        return _detector
    from sylion.quality.regression_detector import get_regression_detector
    _detector = get_regression_detector()
    return _detector


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateBaselineRequest(BaseModel):
    name: str
    version: str
    metrics_json: str = "{}"


class UpdateBaselineRequest(BaseModel):
    name: str | None = None
    version: str | None = None
    metrics_json: str | None = None
    status: str | None = None


class RunRegressionTestRequest(BaseModel):
    baseline_id: str
    test_name: str
    current_metrics_json: str = "{}"


class CompareMetricsRequest(BaseModel):
    baseline_id: str
    current_metrics_json: str = "{}"


# ---------------------------------------------------------------------------
# Baselines -- CRUD
# ---------------------------------------------------------------------------

@router.post("/baselines", status_code=201)
def create_baseline(body: CreateBaselineRequest):
    """Create a new regression baseline."""
    try:
        return _get_detector().create_baseline(
            name=body.name,
            version=body.version,
            metrics_json=body.metrics_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/baselines/{baseline_id}")
def update_baseline(baseline_id: str, body: UpdateBaselineRequest):
    """Update mutable fields on a baseline."""
    fields = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.version is not None:
        fields["version"] = body.version
    if body.metrics_json is not None:
        fields["metrics_json"] = body.metrics_json
    if body.status is not None:
        fields["status"] = body.status
    try:
        result = _get_detector().update_baseline(baseline_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail=f"Baseline {baseline_id} not found")
    return result


# ---------------------------------------------------------------------------
# Baselines -- Listing -- static paths before dynamic /{baseline_id}
# ---------------------------------------------------------------------------

@router.get("/baselines")
def list_baselines(status: str | None = None):
    """List baselines with optional status filter."""
    try:
        baselines = _get_detector().list_baselines(status=status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"baselines": baselines}


@router.get("/baselines/{baseline_id}")
def get_baseline(baseline_id: str):
    """Retrieve a single baseline by ID."""
    result = _get_detector().get_baseline(baseline_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Baseline {baseline_id} not found")
    return result


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

@router.get("/tests")
def list_regression_tests():
    """List regression tests."""
    return {"tests": _get_detector().get_test_results()}


@router.post("/tests/run", status_code=201)
def run_regression_test(body: RunRegressionTestRequest):
    """Run a regression test against a baseline."""
    try:
        return _get_detector().run_regression_test(
            baseline_id=body.baseline_id,
            test_name=body.test_name,
            current_metrics_json=body.current_metrics_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Results -- static paths
# ---------------------------------------------------------------------------

@router.get("/results")
def get_test_results(baseline_id: str | None = None, status: str | None = None):
    """Get test results with optional filters."""
    try:
        results = _get_detector().get_test_results(
            baseline_id=baseline_id, status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"results": results}


@router.get("/stats")
def get_regression_stats():
    """Aggregate regression detector statistics."""
    return _get_detector().get_regression_stats()


# ---------------------------------------------------------------------------
# Compare metrics (no storage)
# ---------------------------------------------------------------------------

@router.post("/compare")
def compare_metrics(body: CompareMetricsRequest):
    """Compare given metrics against a baseline without storing a result."""
    try:
        return _get_detector().compare_metrics(
            baseline_id=body.baseline_id,
            current_metrics_json=body.current_metrics_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
