"""
SYLION API -- Evaluator routes.

Endpoints for the Evaluator module:
  create_criteria, update_criteria, delete_criteria, list_criteria,
  create_evaluation, score_criterion, complete_evaluation,
  get_evaluation, list_evaluations, get_evaluation_summary.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/evaluator", tags=["Evaluator"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_evaluator = None


def _get_evaluator():
    global _evaluator
    if _evaluator is not None:
        return _evaluator
    from sylion.cognitive.evaluator import get_evaluator
    _evaluator = get_evaluator()
    return _evaluator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateCriteriaRequest(BaseModel):
    name: str
    description: str = ""
    weight: float = 1.0
    rubric: dict | None = None


class UpdateCriteriaRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    weight: float | None = None
    rubric: dict | None = None


class CreateEvaluationRequest(BaseModel):
    target_id: str
    target_type: str
    criteria_ids: list[str] | None = None


class ScoreCriterionRequest(BaseModel):
    score: float
    notes: str = ""


# ---------------------------------------------------------------------------
# Criteria CRUD
# ---------------------------------------------------------------------------

@router.post("/criteria", status_code=201)
def create_criteria(body: CreateCriteriaRequest):
    """Create a new evaluation criterion."""
    ev = _get_evaluator()
    try:
        return ev.create_criteria(
            name=body.name,
            description=body.description,
            weight=body.weight,
            rubric=body.rubric,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/criteria/{criteria_id}")
def update_criteria(criteria_id: str, body: UpdateCriteriaRequest):
    """Update an existing criterion."""
    ev = _get_evaluator()
    try:
        result = ev.update_criteria(
            criteria_id=criteria_id,
            name=body.name,
            description=body.description,
            weight=body.weight,
            rubric=body.rubric,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Criteria {criteria_id} not found")
    return result


@router.delete("/criteria/{criteria_id}")
def delete_criteria(criteria_id: str):
    """Delete a criterion."""
    ev = _get_evaluator()
    deleted = ev.delete_criteria(criteria_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Criteria {criteria_id} not found")
    return {"deleted": True}


@router.get("/criteria")
def list_criteria():
    """List all criteria."""
    ev = _get_evaluator()
    return ev.list_criteria()


# ---------------------------------------------------------------------------
# Evaluations -- static paths before dynamic /{evaluation_id} paths
# ---------------------------------------------------------------------------

@router.post("/evaluations", status_code=201)
def create_evaluation(body: CreateEvaluationRequest):
    """Create a new evaluation for a target."""
    ev = _get_evaluator()
    return ev.create_evaluation(
        target_id=body.target_id,
        target_type=body.target_type,
        criteria_ids=body.criteria_ids,
    )


@router.get("/evaluations")
def list_evaluations(
    target_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
):
    """List evaluations with optional filters."""
    ev = _get_evaluator()
    try:
        return ev.list_evaluations(
            target_id=target_id,
            status=status,
            limit=limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evaluations/{evaluation_id}/summary")
def get_evaluation_summary(evaluation_id: str):
    """Get a summary with per-criterion breakdown."""
    ev = _get_evaluator()
    result = ev.get_evaluation_summary(evaluation_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Evaluation {evaluation_id} not found")
    return result


@router.post("/evaluations/{evaluation_id}/score")
def score_criterion(evaluation_id: str, criteria_id: str, body: ScoreCriterionRequest):
    """Score a single criterion within an evaluation."""
    ev = _get_evaluator()
    try:
        result = ev.score_criterion(
            evaluation_id=evaluation_id,
            criteria_id=criteria_id,
            score=body.score,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Evaluation {evaluation_id} not found")
    return result


@router.post("/evaluations/{evaluation_id}/complete")
def complete_evaluation(evaluation_id: str):
    """Complete an evaluation and compute weighted score."""
    ev = _get_evaluator()
    result = ev.complete_evaluation(evaluation_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Evaluation {evaluation_id} not found")
    return result


@router.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str):
    """Retrieve an evaluation with its results."""
    ev = _get_evaluator()
    result = ev.get_evaluation(evaluation_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Evaluation {evaluation_id} not found")
    return result
