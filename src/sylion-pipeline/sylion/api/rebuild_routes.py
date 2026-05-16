"""
SYLION API -- Rebuild routes.

Endpoints for: cft_runner, cutover_controller, lpw_manager, orchestrator,
golden_set_manager.
"""

from fastapi import APIRouter, HTTPException

from sylion.rebuild.cft_runner import get_cft_runner
from sylion.rebuild.cutover_controller import get_cutover_controller
from sylion.rebuild.lpw_manager import get_lpw_manager
from sylion.rebuild.orchestrator import get_rebuild_orchestrator

try:
    from sylion.rebuild.golden_set_manager import get_golden_set_manager
    _HAS_GOLDEN_SET = True
except ImportError:
    _HAS_GOLDEN_SET = False

router = APIRouter(prefix="/api/v1/rebuild", tags=["rebuild"])


# ---------------------------------------------------------------------------
# CFT Runner (Canonical Format Tests)
# ---------------------------------------------------------------------------

@router.post("/cft/suites", status_code=201)
def create_cft_suite(name: str, description: str = "", module_id: str = ""):
    """Create a new CFT test suite."""
    runner = get_cft_runner()
    return runner.create_suite(name, description=description,
                               module_id=module_id)


@router.get("/cft/suites")
def list_cft_suites(module_id: str | None = None, active_only: bool = True,
                    limit: int = 100):
    """List CFT test suites."""
    runner = get_cft_runner()
    return {"suites": runner.list_suites(module_id=module_id,
                                         active_only=active_only,
                                         limit=limit)}


@router.post("/cft/suites/{suite_id}/run", status_code=201)
def run_cft_test(suite_id: str, golden_hash: str, actual_hash: str = "",
                 duration_ms: int = 0):
    """Run a CFT test for a suite."""
    runner = get_cft_runner()
    return runner.run_test(suite_id, golden_hash, actual_hash=actual_hash,
                           duration_ms=duration_ms)


@router.get("/cft/suites/{suite_id}/results")
def get_cft_results(suite_id: str, limit: int = 100):
    """Get CFT test results for a suite."""
    runner = get_cft_runner()
    return {"results": runner.get_results(suite_id, limit=limit)}


@router.get("/cft/suites/{suite_id}/pass-rate")
def get_cft_pass_rate(suite_id: str):
    """Get pass rate for a CFT suite."""
    runner = get_cft_runner()
    return runner.get_pass_rate(suite_id)


# ---------------------------------------------------------------------------
# Cutover Controller
# ---------------------------------------------------------------------------

@router.post("/cutover/plans", status_code=201)
def create_cutover_plan(module_id: str, current_state: str = "shadow",
                        target_state: str = "cutover",
                        auto_rollback: bool = False):
    """Create a new cutover plan."""
    ctrl = get_cutover_controller()
    return ctrl.create_plan(module_id, current_state=current_state,
                            target_state=target_state,
                            auto_rollback=auto_rollback)


@router.get("/cutover/plans")
def list_cutover_plans(status: str | None = None,
                       module_id: str | None = None,
                       limit: int = 100):
    """List cutover plans."""
    ctrl = get_cutover_controller()
    return {"plans": ctrl.list_plans(status=status, module_id=module_id,
                                     limit=limit)}


@router.get("/cutover/plans/{plan_id}")
def get_cutover_plan(plan_id: str):
    """Get a cutover plan by ID."""
    ctrl = get_cutover_controller()
    result = ctrl.get_plan(plan_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Cutover plan {plan_id} not found")
    return result


@router.post("/cutover/plans/{plan_id}/execute")
def execute_cutover_plan(plan_id: str):
    """Execute a cutover plan."""
    ctrl = get_cutover_controller()
    return ctrl.execute(plan_id)


@router.post("/cutover/plans/{plan_id}/rollback")
def rollback_cutover_plan(plan_id: str):
    """Rollback a cutover plan."""
    ctrl = get_cutover_controller()
    return ctrl.rollback(plan_id)


@router.post("/cutover/plans/{plan_id}/events", status_code=201)
def record_cutover_event(plan_id: str, event_type: str,
                         details: str = "{}"):
    """Record an event during cutover."""
    import json
    ctrl = get_cutover_controller()
    return ctrl.record_event(
        plan_id, event_type,
        details=json.loads(details) if isinstance(details, str) else None,
    )


# ---------------------------------------------------------------------------
# LPW Manager (Last Known Working)
# ---------------------------------------------------------------------------

@router.post("/lpw/records", status_code=201)
def record_lpw(module_id: str, version: str, snapshot_hash: str = "",
               status: str = "stable"):
    """Record a Last-Persisted-Working state."""
    mgr = get_lpw_manager()
    return mgr.record(module_id, version, snapshot_hash=snapshot_hash,
                      status=status)


@router.post("/lpw/snapshots", status_code=201)
def snapshot_lpw(module_id: str, version: str, content_hash: str = "",
                 description: str = ""):
    """Create an LPW snapshot."""
    mgr = get_lpw_manager()
    return mgr.snapshot(module_id, version, content_hash=content_hash,
                        description=description)


@router.get("/lpw/{module_id}")
def get_lpw(module_id: str):
    """Get the LPW record for a module."""
    mgr = get_lpw_manager()
    result = mgr.get_lpw(module_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No LPW for module {module_id}")
    return result


@router.get("/lpw")
def list_lpw(status: str | None = None, limit: int = 100):
    """List LPW records."""
    mgr = get_lpw_manager()
    return {"records": mgr.list_lpw(status=status, limit=limit)}


@router.get("/lpw/{module_id}/history")
def lpw_history(module_id: str, limit: int = 50):
    """Get LPW history for a module."""
    mgr = get_lpw_manager()
    return {"history": mgr.get_history(module_id, limit=limit)}


@router.post("/lpw/{module_id}/restore")
def restore_lpw(module_id: str):
    """Restore a module to its LPW state."""
    mgr = get_lpw_manager()
    return mgr.restore(module_id)


# ---------------------------------------------------------------------------
# Rebuild Orchestrator
# ---------------------------------------------------------------------------

@router.post("/orchestrator/plans", status_code=201)
def create_rebuild_plan(name: str, description: str = "",
                        modules: str = "", strategy: str = "progressive"):
    """Create a new rebuild plan."""
    orch = get_rebuild_orchestrator()
    mod_list = [m.strip() for m in modules.split(",") if m.strip()]
    return orch.create_plan(name, description=description,
                            modules=mod_list if mod_list else None,
                            strategy=strategy)


@router.get("/orchestrator/plans")
def list_rebuild_plans(status: str | None = None, limit: int = 100):
    """List rebuild plans."""
    orch = get_rebuild_orchestrator()
    return {"plans": orch.list_plans(status=status, limit=limit)}


@router.get("/orchestrator/plans/{plan_id}")
def get_rebuild_plan(plan_id: str):
    """Get a rebuild plan by ID."""
    orch = get_rebuild_orchestrator()
    result = orch.get_plan(plan_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Rebuild plan {plan_id} not found")
    return result


@router.post("/orchestrator/plans/{plan_id}/steps", status_code=201)
def add_rebuild_step(plan_id: str, module_id: str, action: str = "rebuild",
                     order_num: int = 0):
    """Add a step to a rebuild plan."""
    orch = get_rebuild_orchestrator()
    return orch.add_step(plan_id, module_id, action=action,
                         order_num=order_num)


@router.get("/orchestrator/plans/{plan_id}/steps")
def get_rebuild_steps(plan_id: str):
    """Get steps for a rebuild plan."""
    orch = get_rebuild_orchestrator()
    return {"steps": orch.get_steps(plan_id)}


@router.post("/orchestrator/plans/{plan_id}/execute")
def execute_rebuild_plan(plan_id: str):
    """Execute a rebuild plan."""
    orch = get_rebuild_orchestrator()
    return orch.execute_plan(plan_id)


# ---------------------------------------------------------------------------
# Golden Set Manager (Phase 4)
# ---------------------------------------------------------------------------

@router.post("/golden-sets", status_code=201)
def create_golden_set(name: str, version: str = "1.0",
                      test_cases: str = "[]"):
    """Create a new golden set with optional test cases."""
    if not _HAS_GOLDEN_SET:
        raise HTTPException(status_code=501,
                            detail="golden_set_manager module not available")
    import json
    mgr = get_golden_set_manager()
    parsed = json.loads(test_cases) if isinstance(test_cases, str) else None
    return mgr.create_golden_set(name, version=version,
                                 test_cases=parsed)


@router.get("/golden-sets")
def list_golden_sets(status: str | None = None, limit: int = 100):
    """List golden sets."""
    if not _HAS_GOLDEN_SET:
        raise HTTPException(status_code=501,
                            detail="golden_set_manager module not available")
    mgr = get_golden_set_manager()
    return {"golden_sets": mgr.list_golden_sets(status=status, limit=limit)}


@router.get("/golden-sets/{set_id}")
def get_golden_set(set_id: str):
    """Get a golden set with all test cases."""
    if not _HAS_GOLDEN_SET:
        raise HTTPException(status_code=501,
                            detail="golden_set_manager module not available")
    mgr = get_golden_set_manager()
    result = mgr.get_golden_set(set_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Golden set {set_id} not found")
    return result


@router.post("/golden-sets/{set_id}/fidelity", status_code=201)
def run_golden_set_fidelity(set_id: str, module_id: str,
                            threshold: float = 0.90):
    """Run a fidelity test against a golden set for a module."""
    if not _HAS_GOLDEN_SET:
        raise HTTPException(status_code=501,
                            detail="golden_set_manager module not available")
    mgr = get_golden_set_manager()
    return mgr.run_fidelity_test(set_id, module_id, threshold=threshold)


@router.get("/golden-sets/{set_id}/validate")
def validate_golden_set(set_id: str):
    """Validate a golden set has sufficient test cases."""
    if not _HAS_GOLDEN_SET:
        raise HTTPException(status_code=501,
                            detail="golden_set_manager module not available")
    mgr = get_golden_set_manager()
    return mgr.validate_set(set_id)


@router.get("/golden-sets/stats")
def golden_set_stats():
    """Get golden set manager statistics."""
    if not _HAS_GOLDEN_SET:
        raise HTTPException(status_code=501,
                            detail="golden_set_manager module not available")
    mgr = get_golden_set_manager()
    return mgr.get_stats()
