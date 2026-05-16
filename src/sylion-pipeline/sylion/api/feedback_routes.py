"""
SYLION API -- Feedback Collector routes.

Endpoints for FeedbackCollector:
  create_category, list_categories, create_item, list_items,
  submit_response, get_responses, get_item_stats, get_category_stats,
  export_feedback.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/feedback", tags=["Feedback"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_collector = None


def _get_collector():
    global _collector
    if _collector is not None:
        return _collector
    from sylion.cognitive.feedback_collector import get_feedback_collector
    _collector = get_feedback_collector()
    return _collector


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateCategoryRequest(BaseModel):
    name: str
    description: str = ""


class CreateItemRequest(BaseModel):
    category_id: str
    question: str
    item_type: str = "text"
    options_json: str = "[]"


class SubmitResponseRequest(BaseModel):
    item_id: str
    user_id: str
    value: str
    metadata_json: str = "{}"


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.post("/categories", status_code=201)
def create_category(body: CreateCategoryRequest):
    """Create a new feedback category."""
    try:
        return _get_collector().create_category(
            name=body.name,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/categories")
def list_categories():
    """List all feedback categories."""
    return {"categories": _get_collector().list_categories()}


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

@router.post("/items", status_code=201)
def create_item(body: CreateItemRequest):
    """Create a new feedback item within a category."""
    try:
        return _get_collector().create_item(
            category_id=body.category_id,
            question=body.question,
            item_type=body.item_type,
            options_json=body.options_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/items")
def list_items(category_id: str | None = None):
    """List feedback items, optionally filtered by category."""
    return {"items": _get_collector().list_items(category_id=category_id)}


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

@router.post("/responses", status_code=201)
def submit_response(body: SubmitResponseRequest):
    """Submit a response to a feedback item."""
    try:
        return _get_collector().submit_response(
            item_id=body.item_id,
            user_id=body.user_id,
            value=body.value,
            metadata_json=body.metadata_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/responses")
def get_responses(item_id: str | None = None, user_id: str | None = None):
    """Get responses with optional filters."""
    return {"responses": _get_collector().get_responses(
        item_id=item_id, user_id=user_id,
    )}


# ---------------------------------------------------------------------------
# Stats -- static paths
# ---------------------------------------------------------------------------

@router.get("/stats/items/{item_id}")
def get_item_stats(item_id: str):
    """Get aggregate statistics for a specific item."""
    return _get_collector().get_item_stats(item_id)


@router.get("/stats/categories")
def get_category_stats():
    """Get aggregate statistics across all categories."""
    return _get_collector().get_category_stats()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@router.get("/export")
def export_feedback(category_id: str | None = None):
    """Export feedback responses, optionally filtered by category."""
    return {"feedback": _get_collector().export_feedback(category_id=category_id)}
