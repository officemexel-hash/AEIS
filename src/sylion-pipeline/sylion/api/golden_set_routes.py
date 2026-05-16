"""
SYLION API -- Golden Set routes.

Combined endpoints for GoldenSetRegistry and GoldenSetRunner:
  Registry:  create_set, update_set, delete_set, get_set, list_sets,
             add_case, remove_case, get_cases, import_cases.
  Runner:    start_run, get_run, list_runs, get_results,
             get_run_summary, compare_runs, get_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/golden-sets", tags=["Golden Sets"])


# ---------------------------------------------------------------------------
# Lazy accessors
# ---------------------------------------------------------------------------

_golden_set_registry = None
_golden_set_runner = None


def _get_registry():
    global _golden_set_registry
    if _golden_set_registry is not None:
        return _golden_set_registry
    from sylion.quality.golden_set_registry import get_golden_set_registry
    _golden_set_registry = get_golden_set_registry()
    return _golden_set_registry


def _get_runner():
    global _golden_set_runner
    if _golden_set_runner is not None:
        return _golden_set_runner
    from sylion.quality.golden_set_runner import get_golden_set_runner
    _golden_set_runner = get_golden_set_runner()
    return _golden_set_runner


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateSetRequest(BaseModel):
    name: str
    description: str = ""
    category: str = ""


class UpdateSetRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None


class AddCaseRequest(BaseModel):
    set_id: str
    input_json: dict | None = None
    expected_output_json: dict | None = None
    metadata_json: dict | None = None


class ImportCasesRequest(BaseModel):
    set_id: str
    cases: list[dict]


class StartRunRequest(BaseModel):
    set_id: str
    runner_config_json: dict | None = None


class CompareRunsRequest(BaseModel):
    run_id_1: str
    run_id_2: str


# ---------------------------------------------------------------------------
# Set CRUD
# ---------------------------------------------------------------------------

@router.post("/sets", status_code=201)
def create_set(body: CreateSetRequest):
    """Create a new golden set."""
    reg = _get_registry()
    return reg.create_set(
        name=body.name,
        description=body.description,
        category=body.category,
    )


@router.put("/sets/{set_id}")
def update_set(set_id: str, body: UpdateSetRequest):
    """Update mutable fields on a golden set."""
    reg = _get_registry()
    fields = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.description is not None:
        fields["description"] = body.description
    if body.category is not None:
        fields["category"] = body.category
    result = reg.update_set(set_id, **fields)
    if not result:
        raise HTTPException(status_code=404, detail=f"Golden set {set_id} not found")
    return result


@router.delete("/sets/{set_id}")
def delete_set(set_id: str):
    """Delete a golden set and all its cases."""
    reg = _get_registry()
    ok = reg.delete_set(set_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Golden set {set_id} not found")
    return {"set_id": set_id, "removed": True}


@router.get("/sets")
def list_sets(category: str | None = None):
    """List golden sets, optionally filtered by category."""
    reg = _get_registry()
    return {"sets": reg.list_sets(category=category)}


@router.get("/sets/{set_id}")
def get_set(set_id: str):
    """Return a golden set record by ID."""
    reg = _get_registry()
    result = reg.get_set(set_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Golden set {set_id} not found")
    return result


# ---------------------------------------------------------------------------
# Case management
# ---------------------------------------------------------------------------

@router.post("/cases", status_code=201)
def add_case(body: AddCaseRequest):
    """Add a single test case to a golden set."""
    reg = _get_registry()
    result = reg.add_case(
        set_id=body.set_id,
        input_json=body.input_json,
        expected_output_json=body.expected_output_json,
        metadata_json=body.metadata_json,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Golden set {body.set_id} not found")
    return result


@router.delete("/cases/{case_id}")
def remove_case(case_id: str):
    """Remove a single test case by case_id."""
    reg = _get_registry()
    ok = reg.remove_case(case_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return {"case_id": case_id, "removed": True}


@router.get("/sets/{set_id}/cases")
def get_cases(set_id: str):
    """Return all test cases for a golden set."""
    reg = _get_registry()
    return {"cases": reg.get_cases(set_id)}


@router.post("/cases/import")
def import_cases(body: ImportCasesRequest):
    """Bulk-import test cases into a golden set."""
    reg = _get_registry()
    created = reg.import_cases(body.set_id, body.cases)
    if not created:
        result = reg.get_set(body.set_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Golden set {body.set_id} not found")
    return {"imported": len(created), "cases": created}


# ---------------------------------------------------------------------------
# Runner -- Run execution
# ---------------------------------------------------------------------------

@router.post("/runs", status_code=201)
def start_run(body: StartRunRequest):
    """Execute all cases in a golden set and record results."""
    runner = _get_runner()
    return runner.start_run(
        set_id=body.set_id,
        runner_config_json=body.runner_config_json,
    )


# ---------------------------------------------------------------------------
# Runner -- Retrieval -- static paths before dynamic /{run_id} paths
# ---------------------------------------------------------------------------

@router.get("/runs/list")
def list_runs(set_id: str | None = None, status: str | None = None):
    """List runs with optional filters."""
    runner = _get_runner()
    return {"runs": runner.list_runs(set_id=set_id, status=status)}


@router.get("/runs/stats")
def get_runner_stats():
    """Aggregate statistics across all runs."""
    runner = _get_runner()
    return runner.get_stats()


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    """Return a single run record."""
    runner = _get_runner()
    result = runner.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.get("/runs/{run_id}/results")
def get_results(run_id: str):
    """Return all case results for a run."""
    runner = _get_runner()
    return {"results": runner.get_results(run_id)}


@router.get("/runs/{run_id}/summary")
def get_run_summary(run_id: str):
    """Return a run summary with pass rate."""
    runner = _get_runner()
    result = runner.get_run_summary(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.post("/runs/compare")
def compare_runs(body: CompareRunsRequest):
    """Compare two runs, showing per-case diffs."""
    runner = _get_runner()
    result = runner.compare_runs(body.run_id_1, body.run_id_2)
    if not result:
        raise HTTPException(status_code=404, detail="One or both runs not found")
    return result
