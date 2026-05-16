"""
SYLION API -- Cognitive routes.

Endpoints for: planner, model_router, llm_adapter, evaluator.
"""

from fastapi import APIRouter, HTTPException

from sylion.cognitive.planner import get_planner
from sylion.cognitive.model_router import get_model_router
from sylion.cognitive.llm_adapter import get_llm_adapter
from sylion.cognitive.evaluator import get_evaluator

router = APIRouter(prefix="/api/v1/cognitive", tags=["cognitive"])


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "cognitive",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

@router.post("/plans", status_code=201)
def create_plan(title: str, description: str = "",
                parent_plan: str = ""):
    """Create a new plan."""
    planner = get_planner()
    return planner.create_plan(title, description=description,
                               parent_plan=parent_plan)


@router.get("/plans")
def list_plans(status: str | None = None):
    """List plans, optionally filtered by status."""
    planner = get_planner()
    return {"plans": planner.list_plans(status=status)}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str):
    """Get a plan by ID."""
    planner = get_planner()
    plan = planner.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
    return plan


@router.post("/plans/{plan_id}/tasks", status_code=201)
def add_task(plan_id: str, title: str, description: str = "",
             priority: int = 0, depends_on: str = ""):
    """Add a task to a plan."""
    planner = get_planner()
    deps = [d.strip() for d in depends_on.split(",") if d.strip()]
    return planner.add_task(plan_id, title, description=description,
                            priority=priority, depends_on=deps)


@router.post("/plans/{plan_id}/decompose", status_code=201)
def decompose_plan(plan_id: str, subtasks: list[dict]):
    """Decompose a plan into multiple tasks at once."""
    planner = get_planner()
    return {"tasks": planner.decompose(plan_id, subtasks)}


@router.get("/plans/{plan_id}/tasks")
def get_plan_tasks(plan_id: str, status: str | None = None):
    """Get tasks for a plan."""
    planner = get_planner()
    return {"tasks": planner.get_tasks(plan_id, status=status)}


@router.get("/plans/{plan_id}/next-task")
def get_next_task(plan_id: str):
    """Get the next eligible task for a plan."""
    planner = get_planner()
    task = planner.get_next_task(plan_id)
    if not task:
        return {"task": None, "message": "No eligible task found"}
    return task


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str):
    """Mark a task as completed."""
    planner = get_planner()
    result = planner.complete_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return result


# ---------------------------------------------------------------------------
# Model Router
# ---------------------------------------------------------------------------

@router.post("/models", status_code=201)
def register_model(model_id: str, provider: str, name: str,
                   cost_per_1k_tokens: float = 0.0,
                   capabilities: str = ""):
    """Register or update an LLM model."""
    router_ = get_model_router()
    caps = [c.strip() for c in capabilities.split(",") if c.strip()]
    return router_.register_model(
        model_id, provider, name,
        cost_per_1k_tokens=cost_per_1k_tokens,
        capabilities=caps,
    )


@router.get("/models")
def list_models(provider: str | None = None, capability: str | None = None):
    """List registered models."""
    router_ = get_model_router()
    return {"models": router_.list_models(provider=provider, capability=capability)}


@router.get("/models/{model_id}")
def get_model(model_id: str):
    """Get a model by ID."""
    router_ = get_model_router()
    model = router_.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return model


@router.post("/models/route")
def route_task(task_type: str, complexity: str = "medium",
               budget: float | None = None):
    """Route a task to the best matching model."""
    router_ = get_model_router()
    model = router_.route_request(task_type, complexity=complexity, budget=budget)
    if not model:
        raise HTTPException(status_code=404, detail="No suitable model found")
    return model


@router.get("/models/routing/stats")
def routing_stats():
    """Get routing statistics."""
    router_ = get_model_router()
    return router_.get_usage_stats()


# ---------------------------------------------------------------------------
# LLM Adapter
# ---------------------------------------------------------------------------

@router.post("/llm/call", status_code=201)
def llm_call(model_id: str, prompt: str, max_tokens: int = 1000):
    """Execute an LLM call through the configured adapter."""
    adapter = get_llm_adapter()
    return adapter.call(model_id, prompt, max_tokens=max_tokens)


@router.get("/llm/calls")
def list_llm_calls(model_id: str | None = None, limit: int = 100):
    """List LLM call records."""
    adapter = get_llm_adapter()
    return {"calls": adapter.list_calls(model_id=model_id, limit=limit)}


@router.get("/llm/calls/{call_id}")
def get_llm_call(call_id: str):
    """Get a single LLM call record."""
    adapter = get_llm_adapter()
    call = adapter.get_call(call_id)
    if not call:
        raise HTTPException(status_code=404, detail=f"LLM call {call_id} not found")
    return call


@router.get("/llm/usage")
def llm_usage_stats():
    """Get aggregate LLM usage statistics."""
    adapter = get_llm_adapter()
    return adapter.get_usage_stats()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

@router.post("/evaluations", status_code=201)
def create_evaluation(target_type: str, target_id: str,
                      score: float, verdict: str,
                      details: str = "{}"):
    """Record a new evaluation."""
    import json
    ev = get_evaluator()
    return ev.evaluate(
        target_type, target_id, score, verdict,
        details=json.loads(details) if isinstance(details, str) else {},
    )


@router.get("/evaluations")
def list_evaluations(limit: int = 100):
    """List recent evaluations."""
    ev = get_evaluator()
    return {"evaluations": ev.list_evaluations(limit=limit)}


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str):
    """Get a single evaluation by ID."""
    ev = get_evaluator()
    result = ev.get_evaluation(evaluation_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
    return result


@router.get("/evaluations/target/{target_type}/{target_id}")
def query_evaluations_by_target(target_type: str, target_id: str):
    """Query evaluations for a specific target."""
    ev = get_evaluator()
    return {"evaluations": ev.query_by_target(target_type, target_id)}


@router.get("/evaluations/average/{target_type}")
def average_score(target_type: str):
    """Get average score for a target type."""
    ev = get_evaluator()
    return ev.get_average_score(target_type)


# ---------------------------------------------------------------------------
# Feedback Collector
# ---------------------------------------------------------------------------

from sylion.cognitive.feedback_collector import get_feedback_collector as _get_fc


@router.post("/feedback", status_code=201)
def submit_feedback(user_id: str, rating: int, category: str = "general",
                    comment: str = "", session_id: str = "",
                    message_id: str = "", metadata: str = ""):
    """Submit user feedback."""
    import json as _json
    fc = _get_fc()
    md = _json.loads(metadata) if metadata else None
    return fc.submit_feedback(
        user_id, rating, category=category,
        comment=comment or None, session_id=session_id or None,
        message_id=message_id or None, metadata=md,
    )


@router.get("/feedback/stats")
def feedback_stats():
    """Get feedback statistics."""
    return _get_fc().get_feedback_stats()


@router.get("/feedback/average")
def feedback_average(user_id: str = None, category: str = None, since: float = None):
    """Get average rating."""
    return _get_fc().get_average_rating(
        user_id=user_id or None, category=category or None, since=since,
    )


@router.get("/feedback/summaries")
def feedback_summaries(category: str = None, limit: int = 30):
    """List feedback summaries."""
    return {"summaries": _get_fc().get_summaries(category=category, limit=limit)}


@router.post("/feedback/summaries/generate")
def generate_feedback_summary(period: str, category: str = "general"):
    """Generate a feedback summary for a period."""
    return _get_fc().generate_summary(period, category=category)


@router.get("/feedback/trend")
def feedback_trend(days: int = 7, category: str = None):
    """Get feedback trend."""
    return {"trend": _get_fc().get_trend(days=days, category=category)}


@router.get("/feedback")
def list_feedback(user_id: str = None, session_id: str = None,
                  category: str = None, min_rating: int = None,
                  max_rating: int = None, since: float = None, limit: int = 50):
    """List feedback entries."""
    return {"feedback": _get_fc().list_feedback(
        user_id=user_id or None, session_id=session_id or None,
        category=category or None, min_rating=min_rating,
        max_rating=max_rating, since=since, limit=limit,
    )}


@router.get("/feedback/{feedback_id}")
def get_feedback(feedback_id: str):
    """Get a feedback entry by ID."""
    result = _get_fc().get_feedback(feedback_id)
    if not result:
        raise HTTPException(404, "Feedback not found")
    return result


@router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: str):
    """Delete a feedback entry."""
    ok = _get_fc().delete_feedback(feedback_id)
    if not ok:
        raise HTTPException(404, "Feedback not found")
    return {"deleted": feedback_id}


# ---------------------------------------------------------------------------
# Hallucination Detector -- lazy accessor
# ---------------------------------------------------------------------------

_halluc = None


def _get_halluc():
    global _halluc
    if _halluc is not None:
        return _halluc
    from sylion.cognitive.hallucination_detector import get_hallucination_detector
    _halluc = get_hallucination_detector()
    return _halluc


# ---------------------------------------------------------------------------
# Hallucination Detector -- endpoints
# (static routes before parameterized /{check_id} routes)
# ---------------------------------------------------------------------------

@router.get("/hallucinations/stats")
def hallucination_stats():
    """Get hallucination detector statistics."""
    return _get_halluc().get_stats()


@router.post("/hallucinations/detect-patterns")
def detect_hallucination_patterns():
    """Analyze checks for recurring hallucination patterns."""
    return {"patterns": _get_halluc().detect_patterns()}


@router.get("/hallucinations")
def list_hallucination_checks(status: str | None = None,
                              source_type: str | None = None,
                              limit: int = 100):
    """List hallucination checks with optional filters."""
    return {"checks": _get_halluc().list_checks(status=status,
                                                 source_type=source_type,
                                                 limit=limit)}


@router.post("/hallucinations", status_code=201)
def create_hallucination_check(source_type: str, source_id: str,
                               claim: str, expected_answer: str = ""):
    """Create a new hallucination check record."""
    try:
        return _get_halluc().check_claim(source_type, source_id, claim,
                                         expected_answer=expected_answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/hallucinations/{check_id}")
def get_hallucination_check(check_id: str):
    """Get a single hallucination check by ID."""
    result = _get_halluc().get_check(check_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Check {check_id} not found")
    return result


@router.post("/hallucinations/{check_id}/verify")
def verify_hallucination_check(check_id: str, is_hallucination: bool,
                               confidence: float, evidence: str = ""):
    """Update verification status of a hallucination check."""
    result = _get_halluc().verify_check(check_id, is_hallucination,
                                        confidence, evidence=evidence)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Check {check_id} not found")
    return result


@router.post("/hallucinations/{check_id}/resolve")
def resolve_hallucination_check(check_id: str):
    """Mark a hallucination check as resolved."""
    result = _get_halluc().resolve_check(check_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Check {check_id} not found")
    return result


# ---------------------------------------------------------------------------
# Model Performance Tracker -- lazy accessor
# ---------------------------------------------------------------------------

_mpt = None


def _get_mpt():
    global _mpt
    if _mpt is not None:
        return _mpt
    from sylion.cognitive.model_performance import get_model_performance_tracker
    _mpt = get_model_performance_tracker()
    return _mpt


# ---------------------------------------------------------------------------
# Model Performance Tracker -- endpoints
# (static routes before parameterized /{model_id} routes)
# ---------------------------------------------------------------------------

@router.post("/performance/metrics", status_code=201)
def record_performance_metric(model_id: str, metric_type: str,
                              metric_value: float, tokens_used: int = 0,
                              latency_ms: float = 0.0, metadata: str = ""):
    """Record a performance metric for a model."""
    import json as _json
    md = _json.loads(metadata) if metadata else None
    try:
        return _get_mpt().record_metric(
            model_id, metric_type, metric_value,
            tokens_used=tokens_used, latency_ms=latency_ms,
            metadata=md,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/performance/metrics")
def list_performance_metrics(model_id: str | None = None,
                             metric_type: str | None = None,
                             since: float | None = None,
                             limit: int = 100):
    """List performance metrics with optional filters."""
    return {"metrics": _get_mpt().get_metrics(
        model_id=model_id, metric_type=metric_type,
        since=since, limit=limit,
    )}


@router.get("/performance/summary/{model_id}")
def get_performance_summary(model_id: str, period: str = "daily"):
    """Get the latest performance summary for a model."""
    try:
        result = _get_mpt().get_summary(model_id, period=period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"No {period} summary for model {model_id}")
    return result


@router.get("/performance/summaries")
def list_performance_summaries(period: str | None = None, limit: int = 50):
    """List performance summaries."""
    return {"summaries": _get_mpt().list_summaries(period=period, limit=limit)}


@router.post("/performance/leaderboard/update")
def update_performance_leaderboard(metric_type: str = "overall"):
    """Recompute and store leaderboard rankings."""
    try:
        entries = _get_mpt().update_leaderboard(metric_type=metric_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"entries": entries}


@router.get("/performance/leaderboard")
def get_performance_leaderboard(metric_type: str = "overall"):
    """Get current leaderboard rankings."""
    try:
        return {"leaderboard": _get_mpt().get_leaderboard(metric_type=metric_type)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/performance/stats")
def performance_stats():
    """Get aggregate performance statistics."""
    return _get_mpt().get_stats()
