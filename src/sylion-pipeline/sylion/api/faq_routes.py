"""FAQ API routes for server-side search and editable FAQ entries."""
from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/faq", tags=["faq"])


@router.get("/search")
def search_faq(
    q: str = Query(..., min_length=2, description="Search query"),
    category: str | None = Query(None, description="Filter by category"),
):
    """Server-side FAQ search placeholder.

    Currently search is done client-side via string matching in faq-entries.ts.
    This endpoint is reserved for future RAG over module docs (Phase 2).
    """
    return {
        "results": [],
        "note": "Search is done client-side. Server-side RAG reserved for future phase.",
        "q": q,
        "category": category,
    }


@router.get("/entries")
def list_entries():
    """Return FAQ entries.

    Currently entries live in the static TypeScript file faq-entries.ts.
    This endpoint is reserved for future migration to PG table advisor.faq_entries,
    which will allow editing FAQ content without frontend redeploy.
    """
    return {
        "entries": [],
        "source": "static",
        "note": "Entries are currently static (faq-entries.ts). PG-backed version planned.",
    }


@router.get("/contextual/{context_key}")
def contextual_hints(context_key: str):
    """Return FAQ entries relevant to a given UI context key.

    The operator dashboard can call this to show relevant FAQ entries
    next to cards, decisions, or alerts. Currently returns empty list
    (contextual matching is done client-side via contextHints in faq-entries.ts).
    """
    return {
        "context_key": context_key,
        "entries": [],
        "note": "Contextual matching is done client-side via HelpHint component.",
    }
