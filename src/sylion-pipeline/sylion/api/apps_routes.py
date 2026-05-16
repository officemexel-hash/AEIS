"""REST routes for the W16 Apps Builder plane.

The dashboard surface is intentionally live: it exposes canonical app
templates, persists operator selections as draft manifests, and returns
per-app details from storage. It must not simulate a successful selection
only in the browser.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/apps", tags=["apps_v2"])


class MatchIdeaRequest(BaseModel):
    """Operator-typed idea description for the idea-to-template cascade."""

    idea_text: str = Field(min_length=3, max_length=2000)
    top_n: int | None = Field(default=3, ge=1, le=10)


class CreateAppFromTemplateRequest(BaseModel):
    """Create a persisted draft app manifest from a selected template."""

    template_id: str = Field(min_length=1, max_length=120)
    idea_text: str | None = Field(default=None, max_length=2000)
    operator_id: str = Field(default="operator-main", min_length=1, max_length=120)


def _db_path() -> str:
    from sylion.aeis_v2.audit_profile import resolve_db_path

    return str(resolve_db_path("apps_builder.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS apps_builder_apps (
            app_id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            object_types_json TEXT NOT NULL,
            widgets_json TEXT NOT NULL,
            version TEXT NOT NULL,
            status TEXT NOT NULL,
            idea_text TEXT,
            manifest_json TEXT NOT NULL,
            operator_id TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def _append_audit(kind: str, payload: dict[str, Any]) -> None:
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_path
        from sylion.core.audit_jsonl_writer import AuditJsonlWriter

        AuditJsonlWriter(resolve_audit_chain_path("apps_builder.jsonl")).append({
            "ts": time.time(),
            "kind": kind,
            "payload": payload,
        })
    except Exception:
        log.exception("apps_builder audit append failed")


def _templates() -> list[dict[str, Any]]:
    from sylion.aeis_v2.apps_v2 import list_templates

    return list_templates()


def _template_entry(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(template["id"]),
        "name": str(template["name_pl"]),
        "description": str(template["description_pl"]),
        "object_types": list(template.get("object_type_ids") or []),
        "widgets": list(template.get("widget_ids") or []),
        "version": "1.0.0",
        "source": "canonical_template",
        "status": "available",
        "template_id": str(template["id"]),
    }


def _row_entry(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["app_id"],
        "name": row["name"],
        "description": row["description"],
        "object_types": json.loads(row["object_types_json"]),
        "widgets": json.loads(row["widgets_json"]),
        "version": row["version"],
        "source": "operator_registry",
        "status": row["status"],
        "template_id": row["template_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _find_template(template_id: str) -> dict[str, Any] | None:
    for template in _templates():
        if str(template.get("id")) == template_id:
            return template
    return None


def _list_persisted_apps() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM apps_builder_apps ORDER BY created_at DESC"
        ).fetchall()
    return [_row_entry(row) for row in rows]


def _build_manifest(
    *,
    app_id: str,
    template: dict[str, Any],
    idea_text: str | None,
    operator_id: str,
    created_at: float,
) -> dict[str, Any]:
    return {
        "schema_version": "w16.app_manifest.v1",
        "app_id": app_id,
        "template_id": str(template["id"]),
        "name": str(template["name_pl"]),
        "description": str(template["description_pl"]),
        "source": "dashboard_template_selection",
        "operator_id": operator_id,
        "idea_text": idea_text or "",
        "object_types": list(template.get("object_type_ids") or []),
        "widgets": list(template.get("widget_ids") or []),
        "routing": {
            "decision_class": "D2",
            "requires_council": False,
            "requires_human_gate": False,
        },
        "audit": {
            "created_at": created_at,
            "chain": "apps_builder.jsonl",
        },
    }


@router.get("")
def list_apps() -> dict[str, Any]:
    """List persisted app drafts plus canonical templates."""
    templates = [_template_entry(template) for template in _templates()]
    created = _list_persisted_apps()
    apps = created + templates
    return {
        "count": len(apps),
        "created_count": len(created),
        "template_count": len(templates),
        "apps": apps,
    }


@router.get("/health")
def apps_health() -> dict[str, Any]:
    """Confirm the W16 plane is wired to real storage."""
    created = _list_persisted_apps()
    templates = _templates()
    return {
        "status": "ok",
        "storage": "sqlite",
        "db_path": _db_path(),
        "created_count": len(created),
        "template_count": len(templates),
        "app_ids": [entry["id"] for entry in created],
        "template_ids": [str(entry["id"]) for entry in templates],
    }


@router.post("/from-template", status_code=201)
def create_app_from_template(req: CreateAppFromTemplateRequest) -> dict[str, Any]:
    """Persist a draft app manifest after an operator picks a template."""
    template = _find_template(req.template_id)
    if template is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "template not found", "template_id": req.template_id},
        )

    created_at = time.time()
    app_id = f"app_{req.template_id}_{uuid.uuid4().hex[:8]}"
    manifest = _build_manifest(
        app_id=app_id,
        template=template,
        idea_text=req.idea_text,
        operator_id=req.operator_id,
        created_at=created_at,
    )
    object_types = list(template.get("object_type_ids") or [])
    widgets = list(template.get("widget_ids") or [])
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO apps_builder_apps (
                app_id, template_id, name, description, object_types_json,
                widgets_json, version, status, idea_text, manifest_json,
                operator_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                app_id,
                req.template_id,
                str(template["name_pl"]),
                str(template["description_pl"]),
                json.dumps(object_types, ensure_ascii=False),
                json.dumps(widgets, ensure_ascii=False),
                "0.1.0",
                "draft_manifest",
                req.idea_text or "",
                json.dumps(manifest, ensure_ascii=False),
                req.operator_id,
                created_at,
                created_at,
            ),
        )
        conn.commit()

    app = {
        "id": app_id,
        "name": str(template["name_pl"]),
        "description": str(template["description_pl"]),
        "object_types": object_types,
        "widgets": widgets,
        "version": "0.1.0",
        "source": "operator_registry",
        "status": "draft_manifest",
        "template_id": req.template_id,
        "created_at": created_at,
        "updated_at": created_at,
    }
    _append_audit("apps_builder.app_created_from_template", {
        "app_id": app_id,
        "template_id": req.template_id,
        "operator_id": req.operator_id,
        "status": "draft_manifest",
    })
    return {"app": app, "manifest": manifest}


@router.post("/match-idea")
def match_idea(req: MatchIdeaRequest) -> dict[str, Any]:
    """Rank canonical templates for the operator's idea."""
    from sylion.aeis_v2.apps_v2 import match_idea_to_templates

    top_n = req.top_n or 3
    matches = match_idea_to_templates(req.idea_text, top_n=top_n)
    return {
        "idea_text": req.idea_text,
        "match_count": len(matches),
        "matches": [m.to_dict() for m in matches],
        "phase": "template_matching",
        "method_used": "tag_overlap",
    }


@router.post("/match-idea-g1")
def match_idea_g1(req: MatchIdeaRequest) -> dict[str, Any]:
    """Rank templates with embedding refinement when available."""
    from sylion.aeis_v2.apps_v2 import match_idea_to_templates_g1

    top_n = req.top_n or 3
    matches = match_idea_to_templates_g1(req.idea_text, top_n=top_n)
    used_embeddings = bool(matches) and matches[0].method == "embedding"
    degraded_reason = None if used_embeddings else "embedding provider unavailable"
    return {
        "idea_text": req.idea_text,
        "match_count": len(matches),
        "matches": [m.to_dict() for m in matches],
        "phase": "embedding_refinement",
        "method_used": "embedding" if used_embeddings else "tag_overlap",
        "fallback_reason": degraded_reason,
        "degraded_reason": degraded_reason,
    }


@router.post("/match-idea-g1-with-council")
def match_idea_g1_with_council(req: MatchIdeaRequest) -> dict[str, Any]:
    """Rank templates and submit the top match to Council Hybrid."""
    from sylion.aeis_v2.apps_v2 import match_idea_to_templates_g1
    from sylion.aeis_v2.council_v2.wedge import evaluate_match_with_council

    top_n = req.top_n or 3
    matches = match_idea_to_templates_g1(req.idea_text, top_n=top_n)
    if not matches:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no matches found by G1 cascade",
                "idea_text": req.idea_text,
                "phase": "embedding_refinement",
            },
        )

    matches_dict = [m.to_dict() for m in matches]
    decision = evaluate_match_with_council(
        matches_dict,
        idea_text=req.idea_text,
    )
    return {
        "idea_text": req.idea_text,
        "match_count": len(matches),
        "matches": matches_dict,
        "phase": "embedding_refinement+council",
        "council_decision": decision.to_dict(),
    }


@router.get("/{app_id}")
def get_app(app_id: str) -> dict[str, Any]:
    """Return persisted app detail or canonical template detail."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM apps_builder_apps WHERE app_id = ?",
            (app_id,),
        ).fetchone()
    if row is not None:
        return {"app": _row_entry(row), "manifest": json.loads(row["manifest_json"])}

    template = _find_template(app_id)
    if template is not None:
        return {
            "app": _template_entry(template),
            "manifest": _build_manifest(
                app_id=str(template["id"]),
                template=template,
                idea_text=None,
                operator_id="system",
                created_at=0.0,
            ),
        }

    raise HTTPException(
        status_code=404,
        detail={"error": "app not found", "app_id": app_id},
    )
