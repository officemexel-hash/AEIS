"""REST routes for Public Project Showcase demo (W14 E11)."""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("sylion.api.demo_portal")
router = APIRouter(prefix="/api/v1/reference/portal", tags=["reference:portal"])

_svc: Any = None


def _service():
    global _svc
    if _svc is None:
        from sylion.demo.public_project_showcase import PortalService, PortalStore
        db_path = os.environ.get("SYLION_DEMO_PORTAL_DB", "sylion_aeis.db")
        _svc = PortalService(store=PortalStore(db_path=db_path))
    return _svc


class CreateProjectIn(BaseModel):
    owner_id: str
    slug: str
    title: str
    description: str = ""
    visibility: str = "public"


class EditProjectIn(BaseModel):
    editor_id: str
    editor_role: str = "owner"
    title: str | None = None
    description: str | None = None
    visibility: str | None = None


class CommentIn(BaseModel):
    author_id: str
    author_role: str = "authenticated"
    body: str


class ContactIn(BaseModel):
    project_id: str | None = None
    submitter_email: str
    body: str
    submitter_ip: str


@router.get("/health")
def health() -> dict:
    try:
        return {"ok": True, **_service()._store.health()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/projects", status_code=201)
def create_project(body: CreateProjectIn) -> dict:
    try:
        p = _service().create_project(
            body.owner_id, body.slug, body.title,
            body.description, body.visibility,
        )
        return {"project_id": p.project_id, "slug": p.slug,
                "visibility": p.visibility}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects")
def list_projects(limit: int = 100) -> dict:
    items = _service()._store.list_public(limit=limit)
    return {
        "items": [
            {"project_id": p.project_id, "slug": p.slug,
             "title": p.title, "view_count": p.view_count,
             "owner_id": p.owner_id} for p in items
        ],
        "total": len(items),
    }


@router.get("/projects/{project_id}")
def get_project(project_id: str, viewer_role: str = "public") -> dict:
    try:
        p = _service().view_project(project_id, viewer_role=viewer_role)
        if p is None:
            raise HTTPException(status_code=404, detail="not found")
        return {
            "project_id": p.project_id, "slug": p.slug,
            "title": p.title, "description": p.description,
            "visibility": p.visibility, "view_count": p.view_count,
            "owner_id": p.owner_id,
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/projects/{project_id}")
def edit_project(project_id: str, body: EditProjectIn) -> dict:
    fields = {}
    if body.title is not None:
        fields["title"] = body.title
    if body.description is not None:
        fields["description"] = body.description
    if body.visibility is not None:
        fields["visibility"] = body.visibility
    try:
        p = _service().edit_project(
            project_id, body.editor_id,
            editor_role=body.editor_role, **fields,
        )
        return {"project_id": p.project_id, "title": p.title}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/comments", status_code=201)
def add_comment(project_id: str, body: CommentIn) -> dict:
    try:
        c = _service().add_comment(
            project_id, body.author_id, body.body,
            author_role=body.author_role,
        )
        return {"comment_id": c.comment_id}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/comments")
def list_comments(project_id: str) -> dict:
    items = _service()._store.list_comments(project_id)
    return {
        "items": [
            {"comment_id": c.comment_id, "author_id": c.author_id,
             "body": c.body, "created_at": c.created_at}
            for c in items
        ],
        "total": len(items),
    }


@router.post("/contact", status_code=201)
def submit_contact(body: ContactIn) -> dict:
    try:
        s = _service().submit_contact_form(
            body.project_id, body.submitter_email, body.body,
            body.submitter_ip,
        )
        return {"submission_id": s.submission_id, "status": s.status}
    except PermissionError as e:
        raise HTTPException(status_code=429, detail=str(e))  # rate-limited
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


__all__ = ["router"]

