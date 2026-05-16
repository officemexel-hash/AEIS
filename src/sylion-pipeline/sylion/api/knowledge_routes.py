"""
SYLION API -- Knowledge Distiller routes.

Endpoints for KnowledgeDistiller:
  create_entry, update_entry, delete_entry, get_entry, list_entries,
  search_entries, add_source, link_entries, get_linked, get_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/knowledge", tags=["Knowledge"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_distiller = None


def _get_distiller():
    global _distiller
    if _distiller is not None:
        return _distiller
    from sylion.cognitive.knowledge_distiller import get_knowledge_distiller
    _distiller = get_knowledge_distiller()
    return _distiller


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateEntryRequest(BaseModel):
    title: str
    content: str
    category: str = "fact"
    tags_json: str = "[]"


class UpdateEntryRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags_json: str | None = None


class AddSourceRequest(BaseModel):
    entry_id: str
    source_type: str
    source_ref: str
    relevance_score: float = 1.0


class LinkEntriesRequest(BaseModel):
    from_id: str
    to_id: str
    link_type: str = "related"


# ---------------------------------------------------------------------------
# Entry CRUD
# ---------------------------------------------------------------------------

@router.post("/entries", status_code=201)
def create_entry(body: CreateEntryRequest):
    """Create a new knowledge entry."""
    try:
        return _get_distiller().create_entry(
            title=body.title,
            content=body.content,
            category=body.category,
            tags_json=body.tags_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/entries/{entry_id}")
def update_entry(entry_id: str, body: UpdateEntryRequest):
    """Update mutable fields on a knowledge entry."""
    fields = {}
    if body.title is not None:
        fields["title"] = body.title
    if body.content is not None:
        fields["content"] = body.content
    if body.category is not None:
        fields["category"] = body.category
    if body.tags_json is not None:
        fields["tags_json"] = body.tags_json
    try:
        result = _get_distiller().update_entry(entry_id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
    return result


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: str):
    """Delete a knowledge entry and its associated sources/links."""
    ok = _get_distiller().delete_entry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
    return {"entry_id": entry_id, "removed": True}


# ---------------------------------------------------------------------------
# Listing & search -- static paths before dynamic /{entry_id}
# ---------------------------------------------------------------------------

@router.get("/entries")
def list_entries(category: str | None = None, tags: str | None = None,
                 limit: int = 100):
    """List knowledge entries with optional filters."""
    try:
        tag_list = tags.split(",") if tags else None
        entries = _get_distiller().list_entries(
            category=category, tags=tag_list, limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"entries": entries}


@router.get("/entries/search")
def search_entries(query: str, limit: int = 50):
    """Full-text search on title and content."""
    return {"entries": _get_distiller().search_entries(query=query, limit=limit)}


@router.get("/entries/{entry_id}")
def get_entry(entry_id: str):
    """Retrieve a single knowledge entry by ID."""
    result = _get_distiller().get_entry(entry_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")
    return result


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

@router.post("/sources", status_code=201)
def add_source(body: AddSourceRequest):
    """Add a source reference to a knowledge entry."""
    try:
        result = _get_distiller().add_source(
            entry_id=body.entry_id,
            source_type=body.source_type,
            source_ref=body.source_ref,
            relevance_score=body.relevance_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail=f"Entry {body.entry_id} not found")
    return result


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

@router.post("/links", status_code=201)
def link_entries(body: LinkEntriesRequest):
    """Create a link between two knowledge entries."""
    try:
        result = _get_distiller().link_entries(
            from_id=body.from_id,
            to_id=body.to_id,
            link_type=body.link_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="One or both entries not found")
    return result


@router.get("/entries/{entry_id}/linked")
def get_linked(entry_id: str):
    """Get all entries linked to the given entry."""
    return {"links": _get_distiller().get_linked(entry_id)}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats():
    """Aggregate knowledge distiller statistics."""
    return _get_distiller().get_stats()
