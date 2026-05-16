"""
SYLION API -- Self-Explanation Validator routes.

Endpoints for template CRUD, explanation validation, and validation statistics.
"""

from __future__ import annotations

import json as _json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/v1/self-explanation",
    tags=["Self-Explanation Validator"],
)


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_validator = None


def _get_validator():
    global _validator
    if _validator is not None:
        return _validator
    from sylion.governance.self_explanation_validator import (
        get_self_explanation_validator,
    )
    _validator = get_self_explanation_validator()
    return _validator


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateTemplateRequest(BaseModel):
    name: str
    scope: str
    required_fields: Optional[list[dict] | str] = None
    quality_criteria: Optional[list[dict] | str] = None


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    scope: Optional[str] = None
    required_fields: Optional[list[dict] | str] = None
    quality_criteria: Optional[list[dict] | str] = None
    is_active: Optional[bool] = None


class ValidateExplanationRequest(BaseModel):
    explanation_data: dict[str, Any]


# ---------------------------------------------------------------------------
# Template CRUD -- static paths BEFORE dynamic /{template_id} paths
# ---------------------------------------------------------------------------

@router.post("/templates", status_code=201)
def create_template(body: CreateTemplateRequest):
    """Create a new explanation template."""
    v = _get_validator()
    try:
        return v.create_template(
            name=body.name,
            scope=body.scope,
            required_fields_json=body.required_fields,
            quality_criteria_json=body.quality_criteria,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates")
def list_templates(scope: Optional[str] = None,
                   active_only: bool = False):
    """List templates, optionally filtered by scope and active status."""
    v = _get_validator()
    return {"templates": v.list_templates(scope=scope, active_only=active_only)}


@router.get("/templates/{template_id}")
def get_template_by_list(template_id: str):
    """Get a single template by ID (convenience lookup from list)."""
    v = _get_validator()
    templates = v.list_templates()
    for t in templates:
        if t["template_id"] == template_id:
            return t
    raise HTTPException(status_code=404,
                        detail=f"Template {template_id} not found")


@router.put("/templates/{template_id}")
def update_template(template_id: str, body: UpdateTemplateRequest):
    """Update an existing explanation template."""
    v = _get_validator()
    try:
        result = v.update_template(
            template_id,
            name=body.name,
            scope=body.scope,
            required_fields_json=body.required_fields,
            quality_criteria_json=body.quality_criteria,
            is_active=body.is_active,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"Template {template_id} not found")
    return result


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    """Delete a template and its associated validations."""
    v = _get_validator()
    deleted = v.delete_template(template_id)
    if not deleted:
        raise HTTPException(status_code=404,
                            detail=f"Template {template_id} not found")
    return {"deleted": template_id}


# ---------------------------------------------------------------------------
# Validation -- static paths BEFORE dynamic /{validation_id} paths
# ---------------------------------------------------------------------------

@router.post("/validate/{template_id}", status_code=201)
def validate_explanation(template_id: str, body: ValidateExplanationRequest):
    """Validate explanation data against a template."""
    v = _get_validator()
    try:
        return v.validate_explanation(template_id, body.explanation_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/validations")
def list_validations(template_id: Optional[str] = None,
                     limit: int = 100):
    """List validations, optionally filtered by template."""
    v = _get_validator()
    return {"validations": v.list_validations(template_id=template_id,
                                               limit=limit)}


@router.get("/validations/stats")
def validation_stats():
    """Get aggregate validation statistics."""
    v = _get_validator()
    return v.get_validation_stats()
