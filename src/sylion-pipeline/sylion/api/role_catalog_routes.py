"""SYLION API — W7 Role Catalog routes.

Surfaces the role catalog from ``sylion.skills.roles`` as REST endpoints so
the operator dashboard can browse roles and match tasks to candidate roles.

The matcher endpoint is a heuristic placeholder — the full Task-to-Role
Suggester will live in W13.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.aeis_v2.role_match import hybrid_match
from sylion.skills.roles import (
    DEFAULT_SKILL_LEVEL,
    ROLE_REGISTRY,
    VALID_CATEGORIES,
    VALID_SKILL_LEVELS,
    get_role,
    list_capabilities,
    list_categories,
    list_roles,
    list_roles_by_capability,
    match_role_to_task,
    match_role_to_task_v2,
)

log = logging.getLogger(__name__)

# Phase 0: prefix /api/v1/role-catalog (avoid conflict with existing RBAC
# /api/v1/roles). PDF §8.2: W7 Role Catalog is semantically separate from
# governance roles — copywriter/illustrator etc, not security-tier RBAC roles.
router = APIRouter(prefix="/api/v1/role-catalog", tags=["role_catalog_v2"])


class RoleMatchRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Free-form task description")
    available_models: list[str] = Field(
        default_factory=list,
        description="Optional list of model ids that the system can currently serve",
    )
    top_n: int = Field(default=5, ge=1, le=20)


class RoleMatchTaskRequest(BaseModel):
    """Capability-overlap matcher request (W7 Phase-0 ext.)."""

    task_description: str = Field(
        default="",
        description="Optional free-form task text; capability keywords boost score.",
    )
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="Capability ids the candidate role must provide.",
    )
    skill_level: str = Field(
        default=DEFAULT_SKILL_LEVEL,
        description=f"Minimum skill level — one of {VALID_SKILL_LEVELS}.",
    )
    top_n: int = Field(default=5, ge=1, le=20)


class HybridMatchRequest(BaseModel):
    """W13 hybrid task-role matcher request (ADR-001 #5)."""

    task_description: str = Field(
        ...,
        min_length=1,
        description="Free-form task text used both for keyword overlap and embedding.",
    )
    task_tags: list[str] = Field(
        default_factory=list,
        description="Capability tags pulled from the task brief; matched via Jaccard.",
    )
    skill_level: Optional[str] = Field(
        default=None,
        description=(
            "Optional minimum skill level filter — one of "
            f"{VALID_SKILL_LEVELS}. ``null`` keeps every level."
        ),
    )
    top_overlap: int = Field(default=10, ge=1, le=50)
    top_final: int = Field(default=3, ge=1, le=20)


class RoleSelectionRequest(BaseModel):
    role_id: str = Field(..., min_length=1, max_length=160)
    task_description: str = Field(default="", max_length=4000)
    required_capabilities: list[str] = Field(default_factory=list)
    skill_level: str = Field(default=DEFAULT_SKILL_LEVEL, max_length=40)
    selected_by: str = Field(default="operator-main", max_length=120)
    source: str = Field(default="role_catalog_dashboard", max_length=120)


def _db_path() -> str:
    from sylion.aeis_v2.audit_profile import resolve_db_path

    return str(resolve_db_path("role_catalog.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS role_catalog_selections (
            selection_id TEXT PRIMARY KEY,
            role_id TEXT NOT NULL,
            role_name TEXT NOT NULL,
            task_description TEXT NOT NULL,
            required_capabilities_json TEXT NOT NULL,
            skill_level TEXT NOT NULL,
            selected_by TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _append_audit(kind: str, payload: dict[str, Any]) -> None:
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_path
        from sylion.core.audit_jsonl_writer import AuditJsonlWriter

        AuditJsonlWriter(resolve_audit_chain_path("role_catalog.jsonl")).append({
            "ts": time.time(),
            "kind": kind,
            "payload": payload,
        })
    except Exception:
        log.exception("role_catalog audit append failed")


def _selection_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "selection_id": row["selection_id"],
        "role_id": row["role_id"],
        "role_name": row["role_name"],
        "task_description": row["task_description"],
        "required_capabilities": json.loads(row["required_capabilities_json"]),
        "skill_level": row["skill_level"],
        "selected_by": row["selected_by"],
        "source": row["source"],
        "created_at": float(row["created_at"]),
    }


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "module": "role_catalog",
        "version": "v2.0.0",
        "total_roles": len(ROLE_REGISTRY),
        "timestamp": time.time(),
    }


@router.get("")
def list_all_roles(category: Optional[str] = None) -> dict[str, object]:
    """List roles (summary form). Optional ``?category=text`` filter."""
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown category {category!r} — allowed: {VALID_CATEGORIES}",
        )
    roles = list_roles(category=category)
    return {
        "total": len(roles),
        "category": category,
        "roles": [r.to_summary() for r in roles],
    }


@router.get("/categories")
def list_role_categories() -> dict[str, object]:
    """Return category metadata + role_ids per category."""
    cats = list_categories()
    return {"categories": cats, "total": len(cats)}


@router.get("/category/{category}")
def list_roles_by_category(category: str) -> dict[str, object]:
    """List full role manifests for a single category."""
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"unknown category {category!r} — allowed: {VALID_CATEGORIES}",
        )
    roles = list_roles(category=category)
    return {
        "category": category,
        "total": len(roles),
        "roles": [r.to_dict() for r in roles],
    }


@router.post("/match")
def match_roles(body: RoleMatchRequest) -> dict[str, object]:
    """Return top-N roles for a free-form task using the local heuristic matcher.

    The real matcher with Task-to-Role pipelining lives in W13.
    """
    matches = match_role_to_task(
        body.task,
        available_models=set(body.available_models) if body.available_models else None,
        top_n=body.top_n,
    )
    return {
        "task": body.task,
        "available_models": body.available_models,
        "top_n": body.top_n,
        "matches": [m.to_summary() for m in matches],
        "engine": "heuristic-v0",
        "note": "Local heuristic matcher; W13 Task-to-Role Suggester provides the richer pipeline.",
    }


# ---------------------------------------------------------------------------
# W7 Phase-0 capability taxonomy endpoints (PDF §8.2 ext.).
# These are registered BEFORE the catch-all ``/{role_id}`` so the literal
# path segments (``capabilities``, ``by-capability``, ``match-task``) are
# never captured as a role id.
# ---------------------------------------------------------------------------


@router.get("/capabilities")
def list_role_capabilities() -> dict[str, object]:
    """Return deduplicated capability ids + count of roles per capability."""
    caps = list_capabilities()
    return {"count": len(caps), "capabilities": caps}


@router.get("/by-capability/{capability_id}")
def list_roles_with_capability(capability_id: str) -> dict[str, object]:
    """List roles that declare ``capability_id`` in their capabilities."""
    roles = list_roles_by_capability(capability_id)
    return {
        "capability": capability_id,
        "total": len(roles),
        "roles": [r.to_summary() for r in roles],
    }


@router.post("/match-task")
def match_task_to_roles(body: RoleMatchTaskRequest) -> dict[str, object]:
    """Capability-overlap matcher (W7 Phase-0; G2 will use embeddings).

    Scoring is intentionally simple — capability overlap (+5.0 each) plus a
    small boost (+1.0) per capability keyword that appears verbatim in the
    task description. Roles whose ``skill_level`` is below the requested
    minimum are filtered out.
    """
    skill_level = (body.skill_level or DEFAULT_SKILL_LEVEL).strip().lower()
    if skill_level not in VALID_SKILL_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"unknown skill_level {body.skill_level!r} — "
                f"allowed: {VALID_SKILL_LEVELS}"
            ),
        )
    matches = match_role_to_task_v2(
        body.task_description,
        required_capabilities=body.required_capabilities,
        skill_level=skill_level,
        top_n=body.top_n,
    )
    return {
        "task_description": body.task_description,
        "required_capabilities": list(body.required_capabilities),
        "skill_level": skill_level,
        "top_n": body.top_n,
        "matches": matches,
        "engine": "capability-overlap-v0",
        "note": (
            "Phase-0 matcher: simple capability overlap. "
            "G2 will replace this with embedding-based similarity."
        ),
    }


# ---------------------------------------------------------------------------
# W13 hybrid matcher (ADR-001 #5).
# Stage 1 — Jaccard tag overlap (top-10).
# Stage 2 — ollama nomic-embed-text cosine refinement (top-3).
# Module degrades to tag-overlap-only when ollama is unreachable.
# ---------------------------------------------------------------------------


@router.post("/hybrid-match")
def hybrid_match_task_to_roles(body: HybridMatchRequest) -> dict[str, object]:
    """W13 hybrid matcher per ADR-001 Decision #5.

    Two-stage matching:

    1. Jaccard tag overlap narrows to top-10 candidates (deterministic,
       zero-cost; matches ``task_tags`` against role ``capabilities``).
    2. Ollama ``nomic-embed-text`` cosine similarity ranks the top-3 from
       those (fuzzy refinement). When ollama is unreachable the module
       degrades gracefully to tag-overlap-only ranking.

    Each match carries a Polish-language ``reason_pl`` so the operator gets
    an explainable AdvisorCard list to pick from (or auto = top-1).
    """
    skill_level = body.skill_level
    if skill_level is not None:
        skill_norm = skill_level.strip().lower()
        if skill_norm and skill_norm not in VALID_SKILL_LEVELS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"unknown skill_level {body.skill_level!r} — "
                    f"allowed: {VALID_SKILL_LEVELS} or null."
                ),
            )
        skill_level = skill_norm or None

    matches = hybrid_match(
        body.task_description,
        set(body.task_tags),
        list(ROLE_REGISTRY.values()),
        top_overlap=body.top_overlap,
        top_final=body.top_final,
        skill_level=skill_level,
    )
    used_embeddings = any(m.embedding_sim > 0.0 for m in matches)
    return {
        "task_description": body.task_description,
        "task_tags": list(body.task_tags),
        "skill_level": skill_level,
        "top_overlap": body.top_overlap,
        "top_final": body.top_final,
        "matches": [m.to_dict() for m in matches],
        "used_embeddings": used_embeddings,
        "engine": "hybrid-jaccard+nomic-embed-text",
        "note": (
            "ADR-001 #5: stage1 Jaccard tag overlap (top-10) + "
            "stage2 ollama nomic-embed-text cosine (top-3). "
            "Falls back to tag-overlap-only when ollama unavailable."
        ),
    }


@router.post("/selections", status_code=201)
def select_role_for_pipeline(body: RoleSelectionRequest) -> dict[str, object]:
    """Persist the operator's role choice from the catalog surface."""
    role = get_role(body.role_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"role {body.role_id!r} not found")
    selection_id = f"role_sel_{uuid.uuid4().hex[:12]}"
    created_at = time.time()
    role_dict = role.to_dict()
    role_name = str(role_dict.get("name_pl") or role_dict.get("name") or body.role_id)
    record = {
        "selection_id": selection_id,
        "role_id": body.role_id,
        "role_name": role_name,
        "task_description": body.task_description,
        "required_capabilities": list(body.required_capabilities),
        "skill_level": body.skill_level,
        "selected_by": body.selected_by,
        "source": body.source,
        "created_at": created_at,
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO role_catalog_selections (
                selection_id, role_id, role_name, task_description,
                required_capabilities_json, skill_level, selected_by, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                selection_id,
                body.role_id,
                role_name,
                body.task_description,
                json.dumps(list(body.required_capabilities), ensure_ascii=True),
                body.skill_level,
                body.selected_by,
                body.source,
                created_at,
            ),
        )
        conn.commit()
    _append_audit("role_catalog.role_selected", record)
    return record


@router.get("/selections")
def list_role_selections(limit: int = 50) -> dict[str, object]:
    """Return persisted dashboard role selections, newest first."""
    safe_limit = max(1, min(int(limit or 50), 200))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM role_catalog_selections
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    selections = [_selection_from_row(row) for row in rows]
    return {"count": len(selections), "selections": selections}


@router.get("/{role_id}")
def get_role_manifest(role_id: str) -> dict[str, object]:
    """Return the full manifest for a single role."""
    role = get_role(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"role {role_id!r} not found")
    return role.to_dict()
