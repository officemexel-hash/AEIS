"""
SYLION API -- Memory routes.

Endpoints for: kanon_access, compact_layer, evidence_store,
indexer, kb_adapter, retrieval, self_model_store.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.memory.kanon_access import KanonSection, get_kanon_access
from sylion.memory.compact_layer import get_compact_layer
from sylion.memory.evidence_store import get_evidence_store
from sylion.memory.indexer import get_indexer
from sylion.memory.kb_adapter import get_kb_adapter
from sylion.memory.obsidian_sync import ObsidianMemorySync
from sylion.memory.plane import get_memory_plane
from sylion.memory.retrieval import get_retrieval
from sylion.memory.self_model_store import get_self_model_store

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


class ObsidianSyncRequest(BaseModel):
    project_id: str
    related_project_ids: list[str] = Field(default_factory=list)
    force: bool = False
    source: str = "manual_api"


class MemoryPlaneWriteRequest(BaseModel):
    content: str
    provenance: dict[str, Any]
    project_id: str = ""
    evidence_id: str = ""
    created_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    retention_policy: str = "memory-plane"


@router.get("/health")
def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "memory",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# Obsidian-backed long-horizon memory
# ---------------------------------------------------------------------------

def _obsidian_sync() -> ObsidianMemorySync:
    return ObsidianMemorySync()


def _project_for_obsidian(project_id: str) -> dict:
    try:
        from sylion.api.project_start_routes import _project

        return _project(project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found") from exc


@router.get("/obsidian/connector")
def obsidian_connector_status() -> dict:
    """Return the effective Obsidian local-vault connector settings."""
    return _obsidian_sync().connector_status()


@router.post("/obsidian/sync")
def sync_project_to_obsidian_memory(body: ObsidianSyncRequest) -> dict:
    """Sync a CLOSED project into the Obsidian-compatible long-horizon vault."""
    project = _project_for_obsidian(body.project_id)
    related: list[dict | str] = []
    for related_id in body.related_project_ids:
        try:
            related.append(_project_for_obsidian(related_id))
        except HTTPException:
            related.append(related_id)
    try:
        return _obsidian_sync().sync_project(
            project,
            related_projects=related,
            source=body.source or "manual_api",
            require_closed=not body.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/obsidian/status")
def get_obsidian_sync_status(project_id: str) -> dict:
    """Return sync status for one project without fabricating success."""
    return _obsidian_sync().status(project_id)


@router.get("/obsidian/graph")
def get_obsidian_memory_graph() -> dict:
    """Return the Obsidian backlink graph built from the durable sync index."""
    return _obsidian_sync().graph()


@router.get("/obsidian/notes/{project_id}")
def get_obsidian_project_note(project_id: str) -> dict:
    """Return one synced Markdown note for UI smoke and evidence checks."""
    try:
        return _obsidian_sync().read_note(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Obsidian note not found") from exc


# ---------------------------------------------------------------------------
# Kanon Access
# ---------------------------------------------------------------------------

@router.post("/kanon/load")
def load_kanon_text(raw_text: str):
    """Load raw text into the Kanon store."""
    ka = get_kanon_access()
    return ka.load_text(raw_text)


@router.get("/kanon/sections")
def list_kanon_sections(chapter: str | None = None):
    """List Kanon sections, optionally filtered by chapter."""
    ka = get_kanon_access()
    return {"sections": ka.list_sections(chapter=chapter)}


@router.get("/kanon/sections/{section_id}")
def get_kanon_section(section_id: str):
    """Get a single Kanon section by ID."""
    ka = get_kanon_access()
    result = ka.get_section(section_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Section {section_id} not found")
    return result


@router.post("/kanon/sections", status_code=201)
def store_kanon_section(section_id: str, title: str, content: str,
                        chapter: str = "", section_number: int = 0,
                        hash: str = ""):
    """Store a new Kanon section."""
    ka = get_kanon_access()
    section = KanonSection(
        section_id=section_id,
        title=title,
        content=content,
        chapter=chapter,
        section_number=section_number,
        hash=hash,
    )
    return ka.store_section(section)


@router.get("/kanon/search")
def search_kanon(query_text: str, limit: int = 10):
    """Search the Kanon by text query."""
    ka = get_kanon_access()
    return {"results": ka.search(query_text, limit=limit)}


@router.get("/kanon/full-text")
def get_kanon_full_text():
    """Get the full Kanon text."""
    ka = get_kanon_access()
    return {"text": ka.get_full_text()}


# ---------------------------------------------------------------------------
# Compact Layer
# ---------------------------------------------------------------------------

@router.post("/compact")
def compact_text(text: str):
    """Compact text using the compact layer."""
    cl = get_compact_layer()
    return cl.compact(text)


@router.post("/compact/record", status_code=201)
def record_compaction(original: str, compacted: str, fidelity: float = 0.0):
    """Record a compaction result."""
    cl = get_compact_layer()
    return cl.record_compaction(original, compacted, fidelity=fidelity)


@router.get("/compact/records")
def list_compact_records(limit: int = 50):
    """List compaction records."""
    cl = get_compact_layer()
    return {"records": cl.list_records(limit=limit)}


@router.post("/compact/fidelity")
def compute_fidelity(original: str, compacted: str):
    """Compute fidelity score between original and compacted text."""
    cl = get_compact_layer()
    score = cl.compute_fidelity(original, compacted)
    return {"fidelity": score}


@router.get("/compact/stats")
def compact_stats():
    """Get compact layer statistics."""
    cl = get_compact_layer()
    return cl.get_stats()


# ---------------------------------------------------------------------------
# Evidence Store
# ---------------------------------------------------------------------------

@router.post("/evidence", status_code=201)
def store_evidence(evidence_id: str = "", pack_id: str = "",
                   artefact_type: str = "", name: str = "",
                   content: str = "", metadata: str = "{}"):
    """Store a new evidence artefact."""
    import json
    es = get_evidence_store()
    return es.store(
        evidence_id=evidence_id,
        pack_id=pack_id,
        artefact_type=artefact_type,
        name=name,
        content=content,
        metadata=json.loads(metadata) if isinstance(metadata, str) else None,
    )


@router.get("/evidence/stats")
def evidence_store_stats():
    """Get evidence store statistics."""
    es = get_evidence_store()
    return es.get_stats()


@router.get("/evidence-store")
def list_evidence_store(pack_id: str | None = None, artefact_type: str | None = None, limit: int = 100):
    """Compatibility endpoint for dashboard evidence-store listings."""
    es = get_evidence_store()
    if pack_id:
        items = es.query_by_pack(pack_id, limit=limit)
    elif artefact_type:
        items = es.query_by_type(artefact_type, limit=limit)
    else:
        stats = es.get_stats()
        items = []
        if stats.get("total_evidence", 0) > 0:
            items = es.query_by_pack("", limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/evidence/{evidence_id}")
def retrieve_evidence(evidence_id: str):
    """Retrieve an evidence artefact by ID."""
    es = get_evidence_store()
    result = es.retrieve(evidence_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} not found")
    return result


@router.delete("/evidence/{evidence_id}")
def delete_evidence(evidence_id: str):
    """Delete an evidence artefact."""
    es = get_evidence_store()
    removed = es.delete(evidence_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} not found")
    return {"deleted": evidence_id}


@router.get("/evidence/by-pack/{pack_id}")
def query_evidence_by_pack(pack_id: str, limit: int = 100):
    """Query evidence by pack ID."""
    es = get_evidence_store()
    return {"evidence": es.query_by_pack(pack_id, limit=limit)}


@router.get("/evidence/by-type/{artefact_type}")
def query_evidence_by_type(artefact_type: str, limit: int = 100):
    """Query evidence by artefact type."""
    es = get_evidence_store()
    return {"evidence": es.query_by_type(artefact_type, limit=limit)}


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------

@router.post("/index/sections", status_code=201)
def index_section(section_id: str, title: str, content: str,
                  project_id: str = ""):
    """Index a section for search."""
    idx = get_indexer()
    return idx.index_section(section_id, title, content,
                             project_id=project_id)


@router.delete("/index/sections/{section_id}")
def remove_indexed_section(section_id: str):
    """Remove a section from the index."""
    idx = get_indexer()
    removed = idx.remove_section(section_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Section {section_id} not in index")
    return {"removed": section_id}


@router.get("/index/search")
def search_index(query: str, limit: int = 10,
                 project_id: str | None = None):
    """Search the index."""
    idx = get_indexer()
    return {"results": idx.search(query, limit=limit, project_id=project_id)}


@router.get("/index/stats")
def index_stats():
    """Get indexer statistics."""
    idx = get_indexer()
    return idx.get_stats()


# ---------------------------------------------------------------------------
# KB Adapter
# ---------------------------------------------------------------------------

@router.post("/kb/sources", status_code=201)
def register_kb_source(source_id: str, name: str, source_type: str = "file",
                       path: str = "", config: str = "{}"):
    """Register a knowledge base source."""
    import json
    kb = get_kb_adapter()
    return kb.register_source(
        source_id, name, source_type=source_type, path=path,
        config=json.loads(config) if isinstance(config, str) else None,
    )


@router.get("/kb/sources")
def list_kb_sources(active_only: bool = True):
    """List knowledge base sources."""
    kb = get_kb_adapter()
    return {"sources": kb.list_sources(active_only=active_only)}


@router.get("/kb/sources/{source_id}")
def get_kb_source(source_id: str):
    """Get a knowledge base source by ID."""
    kb = get_kb_adapter()
    result = kb.get_source(source_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    return result


@router.post("/kb/sources/{source_id}/index")
def index_kb_source(source_id: str):
    """Index a knowledge base source."""
    kb = get_kb_adapter()
    result = kb.index(source_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
    return result


@router.post("/kb/query")
def query_kb(source_id: str, query_text: str, limit: int = 10):
    """Query a knowledge base source."""
    kb = get_kb_adapter()
    return {"results": kb.query(source_id, query_text, limit=limit)}


@router.get("/kb/stats")
def kb_stats():
    """Get knowledge base adapter statistics."""
    kb = get_kb_adapter()
    return kb.get_stats()


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

@router.get("/retrieval")
def retrieve_memory(query: str, limit: int = 10, min_score: float = 0.0,
                    project_id: str | None = None):
    """Retrieve memory items by query."""
    ret = get_retrieval()
    results = ret.search_similar(query, k=limit, project_id=project_id)
    filtered = [result for result in results if result.score >= min_score]
    return {
        "results": [
            {
                "section_id": result.section_id,
                "title": result.title,
                "text": result.text,
                "score": result.score,
                "source": result.source,
                "project_id": result.project_id,
            }
            for result in filtered
        ]
    }


@router.get("/retrieval/context")
def get_context(query: str, max_tokens: int = 4000,
                project_id: str | None = None):
    """Get assembled context for a query."""
    ret = get_retrieval()
    context = ret.get_context(query, max_tokens=max_tokens,
                              project_id=project_id)
    return {"context": context}


# ---------------------------------------------------------------------------
# Self-Model Store
# ---------------------------------------------------------------------------

@router.post("/self-model/initialize", status_code=201)
def initialize_self_model(model_id: str, capabilities: str = "{}",
                          constraints: str = "{}"):
    """Initialize a new self-model."""
    import json
    sms = get_self_model_store()
    return sms.initialize(
        model_id,
        capabilities=json.loads(capabilities) if isinstance(capabilities, str) else None,
        constraints=json.loads(constraints) if isinstance(constraints, str) else None,
    )


@router.get("/self-model/{model_id}")
def get_self_model(model_id: str):
    """Get the current self-model."""
    sms = get_self_model_store()
    result = sms.get(model_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return result


@router.get("/self-model/{model_id}/latest")
def get_self_model_latest(model_id: str):
    """Get the latest self-model snapshot."""
    sms = get_self_model_store()
    result = sms.get_latest(model_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No snapshots for model {model_id}")
    return result


@router.post("/self-model/{model_id}/update")
def update_self_model(model_id: str, capabilities: str = "{}",
                      constraints: str = "{}", health: str = "healthy",
                      autonomy_level: int = 0):
    """Update a self-model."""
    import json
    sms = get_self_model_store()
    result = sms.update(
        model_id,
        capabilities=json.loads(capabilities) if isinstance(capabilities, str) else None,
        constraints=json.loads(constraints) if isinstance(constraints, str) else None,
        health=health,
        autonomy_level=autonomy_level,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return result


@router.post("/self-model/{model_id}/snapshot", status_code=201)
def snapshot_self_model(model_id: str, reason: str = ""):
    """Create a snapshot of the current self-model state."""
    sms = get_self_model_store()
    result = sms.snapshot(model_id, reason=reason)
    if not result:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return result


@router.get("/self-model/{model_id}/history")
def self_model_history(model_id: str, limit: int = 20):
    """Get self-model snapshot history."""
    sms = get_self_model_store()
    return {"history": sms.get_history(model_id, limit=limit)}


# ---------------------------------------------------------------------------
# Unified memory plane (CP6 unification 2026-04-25)
# Single truth-plane endpoints aggregating across kanon / evidence / index /
# kb / compact / self_model so callers no longer need to walk N stores.
# ---------------------------------------------------------------------------

def _safe_call(fn, default):
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc), "default": default}


@router.get("/stats")
def get_memory_stats():
    """Aggregate stats across the entire memory plane.

    One endpoint, all stores. Mirrors the unified-plane pattern used by
    governance/tickets/stats and skills/runtime/stats.
    """
    return {
        "kanon": _safe_call(lambda: {"sections": len(get_kanon_access().list_sections() or [])}, {}),
        "evidence": _safe_call(lambda: get_evidence_store().get_stats(), {}),
        "compact": _safe_call(lambda: get_compact_layer().get_stats(), {}),
        "indexer": _safe_call(lambda: get_indexer().get_stats(), {}),
        "kb": _safe_call(lambda: get_kb_adapter().get_stats(), {}),
        "plane": _safe_call(lambda: get_memory_plane().stats(), {}),
        "obsidian": _safe_call(lambda: _obsidian_sync().graph()["counts"], {}),
    }


@router.get("/recent")
def get_recent_memory(limit: int = 20):
    """Return most-recent memory artefacts across all stores.

    Combines kanon sections, evidence entries, and indexer entries into a
    single recency-ordered list — the unified retrieval entry point.
    """
    items: list[dict] = []
    try:
        sections = get_kanon_access().list_sections() or []
        for s in sections[-limit:]:
            items.append({
                "kind": "kanon_section",
                "id": s.get("section_id") if isinstance(s, dict) else getattr(s, "section_id", ""),
                "title": s.get("title") if isinstance(s, dict) else getattr(s, "title", ""),
                "timestamp": s.get("created_at", 0) if isinstance(s, dict) else getattr(s, "created_at", 0),
            })
    except Exception as exc:
        items.append({"kind": "kanon_section", "error": str(exc)})
    try:
        # evidence_store has no list-all method, but stats gives counts; we
        # pull the by_type list as a synthetic recent slice.
        ev_stats = get_evidence_store().get_stats() or {}
        for artefact_type, cnt in (ev_stats.get("by_type") or {}).items():
            items.append({
                "kind": "evidence_summary",
                "artefact_type": artefact_type,
                "count": cnt,
            })
    except Exception as exc:
        items.append({"kind": "evidence_summary", "error": str(exc)})
    try:
        graph = _obsidian_sync().graph()
        items.append({
            "kind": "obsidian_graph",
            "id": "long_horizon_memory",
            "title": "Obsidian long-horizon memory",
            "count": graph.get("counts", {}).get("nodes", 0),
            "timestamp": graph.get("updated_at", 0),
        })
    except Exception as exc:
        items.append({"kind": "obsidian_graph", "error": str(exc)})
    return {"items": items[:limit], "count": len(items)}


# ---------------------------------------------------------------------------
# Canonical MemoryPlane write/read API
# ---------------------------------------------------------------------------

@router.post("/plane/write", status_code=201)
def write_memory_plane_entry(body: MemoryPlaneWriteRequest) -> dict:
    """Write through the canonical memory plane with project scope and provenance."""
    try:
        return get_memory_plane().write(
            content=body.content,
            provenance=body.provenance,
            project_id=body.project_id,
            evidence_id=body.evidence_id,
            created_by=body.created_by,
            metadata=body.metadata,
            retention_policy=body.retention_policy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/plane/search")
def search_memory_plane(query: str, limit: int = 10, project_id: str | None = None) -> dict:
    """Search canonical memory entries, optionally scoped to one project."""
    return {"results": get_memory_plane().search(query, limit=limit, project_id=project_id)}


@router.get("/plane/projects/{project_id}")
def list_memory_plane_project(project_id: str, limit: int = 100) -> dict:
    """Return the materialized project view for canonical memory entries."""
    return {"entries": get_memory_plane().list_project(project_id, limit=limit)}


@router.get("/plane/entries/{entry_id}")
def get_memory_plane_entry(entry_id: str) -> dict:
    """Return one canonical memory entry."""
    entry = get_memory_plane().get(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Memory entry {entry_id} not found")
    return entry


@router.get("/plane/stats")
def get_memory_plane_stats() -> dict:
    """Return canonical MemoryPlane entry counts."""
    return get_memory_plane().stats()
