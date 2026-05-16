"""SYLION AEIS v2 — REST routes for the W15 Ontology Runtime Plane.

Phase 0 endpoints (read-only introspection of the registry):

    GET  /api/v1/ontology/types
        List all loaded object types with summary metadata.

    GET  /api/v1/ontology/types/{type_id}
        Full manifest of a single type (raw pydantic dump).

    GET  /api/v1/ontology/types/{type_id}/ddl
        Render the auto-generated DDL for a type. Pure preview — does
        NOT execute against the database. Use this in code-review of a
        new manifest before applying.

    GET  /api/v1/ontology/types/{type_id}/actions
        Preview of action endpoints that would be exposed for this type.

    POST /api/v1/ontology/reload
        Re-walk every registered manifest directory and refresh the
        in-process registry. Useful during development after editing a
        YAML file.

CRUD endpoints for instance-level operations (create/read/update/delete
+ action invocation) land in G2 of the W15 charter — they require the
PostgreSQL backing store and OSDK runtime.

PDF §3.2 alignment:
- "Object Type Registry — manifesty YAML, schema versioning" → GET types
- "Object Query API — REST + gRPC + OSDK Python auto-generated" →
  Phase 0 just exposes the type metadata; full query API in G2.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from sylion.aeis_v2.ontology import (
    ManifestValidationError,
    compile_to_ddl,
    get_registry,
)
from sylion.aeis_v2.ontology.compiler import explain_actions

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ontology", tags=["ontology_v2"])


@router.get("/types")
def list_object_types() -> dict[str, Any]:
    """List every object type currently loaded in the registry.

    Returns ``{count, types: [{id, name_pl, name_en, version, d_level,
    tags, actions, dedicated_columns, relations, audit_enabled,
    search_enabled, source}, ...]}``.
    """
    reg = get_registry()
    rows = reg.list_summaries()
    return {"count": len(rows), "types": rows}


@router.get("/types/{type_id}")
def get_object_type(type_id: str) -> dict[str, Any]:
    """Full manifest dump for a single type."""
    reg = get_registry()
    manifest = reg.get(type_id)
    if not manifest:
        raise HTTPException(404, f"object type '{type_id}' not found")
    return manifest.model_dump(mode="json")


@router.get("/types/{type_id}/ddl")
def render_object_type_ddl(type_id: str) -> dict[str, Any]:
    """Compile the type to PostgreSQL DDL — preview only, no execution.

    The DDL is what *would* be applied if this manifest were promoted
    via the (future) DDL applier. Useful for code review of a new
    object type before it touches the database.
    """
    reg = get_registry()
    manifest = reg.get(type_id)
    if not manifest:
        raise HTTPException(404, f"object type '{type_id}' not found")
    artifacts = compile_to_ddl(manifest)
    return {
        "type_id": type_id,
        "version": manifest.metadata.version,
        "ddl": artifacts.render_sql(),
        "notes": artifacts.notes,
        "rollback": artifacts.rollback,
    }


@router.get("/types/{type_id}/actions")
def list_object_type_actions(type_id: str) -> dict[str, Any]:
    """Preview every action endpoint that would exist for this type."""
    reg = get_registry()
    manifest = reg.get(type_id)
    if not manifest:
        raise HTTPException(404, f"object type '{type_id}' not found")
    return {
        "type_id": type_id,
        "actions": explain_actions(manifest),
    }


@router.post("/types/{type_id}/apply")
def apply_object_type(type_id: str, dry_run: bool = False) -> dict[str, Any]:
    """Apply a single manifest's DDL to PostgreSQL.

    Idempotent (CREATE TABLE IF NOT EXISTS, etc.). Returns ``preview_only=True``
    when PG unreachable. Operator can pass ``?dry_run=true`` to skip PG entirely.
    """
    from sylion.aeis_v2.ontology.applier import apply_manifest
    reg = get_registry()
    manifest = reg.get(type_id)
    if not manifest:
        raise HTTPException(404, f"object type '{type_id}' not found")
    result = apply_manifest(manifest, dry_run=dry_run)
    return result.to_dict()


@router.post("/apply-all")
def apply_all_object_types(
    dry_run: bool = False,
    atomic: bool = False,
) -> dict[str, Any]:
    """Apply DDL for every loaded manifest. Returns per-type ApplyResult list.

    Query params:
        dry_run: when ``true``, skips PG entirely; per-manifest preview rows.
        atomic: when ``true`` (P0-2 fix), wraps the entire batch in ONE
            outer transaction. Any mid-batch failure rolls back EVERY
            manifest (no Frankenstein half-applied state). Default
            ``false`` keeps the legacy per-manifest transaction behavior
            so existing callers are not silently broken.
    """
    from sylion.aeis_v2.ontology.applier import apply_all
    reg = get_registry()
    manifests = [reg.get(tid) for tid in reg.list_ids()]
    manifests = [m for m in manifests if m is not None]
    results = apply_all(manifests, dry_run=dry_run, atomic_batch=atomic)
    return {
        "count": len(results),
        "applied": sum(1 for r in results if r.applied),
        "preview_only": sum(1 for r in results if r.preview_only),
        "errors": sum(1 for r in results if r.error),
        "atomic": atomic,
        "results": [r.to_dict() for r in results],
    }


@router.post("/reload")
def reload_registry() -> dict[str, Any]:
    """Re-walk every registered directory and refresh the in-process registry.

    Errors in individual files surface as HTTP 400 with the offending
    path so the operator can fix the YAML and try again.
    """
    reg = get_registry()
    try:
        new_count = reg.reload()
    except ManifestValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "manifest validation failed",
                "path": str(exc.path) if exc.path else None,
                "message": str(exc),
            },
        ) from exc
    return {
        "ok": True,
        "manifest_count": new_count,
        "type_ids": reg.list_ids(),
    }


@router.get("/health")
def ontology_health() -> dict[str, Any]:
    """Smoke endpoint — confirms the W15 plane is wired up."""
    reg = get_registry()
    return {
        "status": "ok",
        "phase": "0",
        "registry_size": len(reg),
        "type_ids": reg.list_ids(),
    }


@router.post("/regenerate-osdk")
def regenerate_osdk_endpoint() -> dict[str, Any]:
    """Regenerate OSDK Python client modules for every loaded manifest.

    Writes to `sylion/aeis_v2/ontology/_osdk/<type_id>.py`. Idempotent.
    """
    from sylion.aeis_v2.ontology.osdk_gen import regenerate_all
    paths = regenerate_all()
    return {"count": len(paths), "paths": paths}


@router.get("/types/{type_id}/osdk")
def preview_osdk(type_id: str) -> dict[str, Any]:
    """Preview the OSDK module that WOULD be generated for this type."""
    from sylion.aeis_v2.ontology.osdk_gen import generate_module
    reg = get_registry()
    manifest = reg.get(type_id)
    if not manifest:
        raise HTTPException(404, f"object type '{type_id}' not found")
    mod = generate_module(manifest)
    return {
        "type_id": mod.type_id,
        "module_name": mod.module_name,
        "line_count": mod.line_count,
        "code": mod.code,
    }


@router.post("/regenerate-osdk-ts")
def regenerate_osdk_ts_endpoint() -> dict[str, Any]:
    """Regenerate OSDK-TS frontend client modules for every loaded manifest.

    Mirrors :func:`regenerate_osdk_endpoint` but emits TypeScript files
    into ``src/sylion-frontend/src/lib/osdk-ts/<type_id>.ts``. Also
    refreshes the barrel ``index.ts`` so new types are automatically
    re-exported from the package root.
    """
    from sylion.aeis_v2.ontology.osdk_ts_gen import regenerate_ts_all
    paths = regenerate_ts_all()
    return {"count": len(paths), "paths": [str(p) for p in paths]}


@router.get("/types/{type_id}/osdk-ts")
def preview_osdk_ts(type_id: str) -> dict[str, Any]:
    """Preview the TypeScript OSDK module that WOULD be generated for this type.

    Mirrors :func:`preview_osdk` so frontend devs and code reviewers can
    inspect generated TS without writing to disk first.
    """
    from sylion.aeis_v2.ontology.osdk_ts_gen import generate_ts_module
    reg = get_registry()
    manifest = reg.get(type_id)
    if not manifest:
        raise HTTPException(404, f"object type '{type_id}' not found")
    mod = generate_ts_module(manifest)
    return {
        "type_id": mod.type_id,
        "module_name": mod.module_name,
        "line_count": mod.line_count,
        "code": mod.code,
    }


@router.post("/migration/w14/preview")
def preview_w14_migration(
    sqlite_path: str = "src/sylion-pipeline/sylion_aeis.db",
) -> dict[str, Any]:
    """Dry-run preview of W14 -> v2 migration.

    Reads sample (10%) from SQLite, transforms to W15 shape, reports per
    type. Phase 0 - does NOT touch PG.
    """
    from pathlib import Path

    from sylion.aeis_v2.ontology.migration import preview_all_w14

    reg = get_registry()
    manifests = [reg.get(tid) for tid in reg.list_ids() if tid.startswith("w14_")]
    manifests = [m for m in manifests if m is not None]
    p = Path(sqlite_path)
    if not p.exists():
        raise HTTPException(404, f"sqlite db not found: {sqlite_path}")
    previews = preview_all_w14(p, manifests)
    return {
        "count": len(previews),
        "with_data": sum(1 for pv in previews if pv.source_row_count > 0),
        "errors": sum(1 for pv in previews if pv.errors),
        "previews": [pv.to_dict() for pv in previews],
    }


@router.post("/migration/w14/apply")
def apply_w14_migration(payload: dict[str, Any]) -> dict[str, Any]:
    """W15 G3 full runner: real bulk import from SQLite to PG.

    Body
    ----
    ``{"sqlite_path": "...", "dry_run": true|false}``

    Behavior
    --------
    - For every loaded manifest with id ``w14_*``, opens the SQLite
      source, streams every row, transforms via ``transform_w14_row``,
      INSERTs into ``sylion_v2.<table>`` with per-row error tolerance,
      commits per batch (or rolls back on dry-run).
    - Idempotency: if the target PG table already has rows, that type
      is skipped with ``applied=False, rationale="Zaaplikowane
      wczesniej, pomijam"``. G2 will replace this with diff-and-merge.
    - PG unreachable -> per-type result has
      ``applied=False, rationale="PG niedostepny..."`` and the audit
      JSONL still gets a row for forensics.
    """
    from pathlib import Path

    from sylion.aeis_v2.ontology.migration import run_all_w14_migrations

    sqlite_path = payload.get("sqlite_path") or "src/sylion-pipeline/sylion_aeis.db"
    dry_run_raw = payload.get("dry_run", True)
    dry_run = bool(dry_run_raw)

    p = Path(sqlite_path)
    if not p.exists():
        raise HTTPException(404, f"sqlite db not found: {sqlite_path}")

    reg = get_registry()
    manifests = [reg.get(tid) for tid in reg.list_ids() if tid.startswith("w14_")]
    manifests = [m for m in manifests if m is not None]

    results = run_all_w14_migrations(manifests, p, dry_run=dry_run)
    return {
        "count": len(results),
        "dry_run": dry_run,
        "applied": sum(1 for r in results if r.applied),
        "skipped": sum(
            1 for r in results
            if not r.applied and "Zaaplikowane wczesniej" in r.rationale
        ),
        "errors": sum(1 for r in results if r.failed_rows > 0),
        "results": [r.to_dict() for r in results],
    }
