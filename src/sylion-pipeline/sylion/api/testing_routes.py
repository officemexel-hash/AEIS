"""SYLION API — W14 Testing Ontology routes.

REST endpoints for the 25 ontology objects exposed via OntologyStore.
Generic CRUD per object kind plus a few custom transitions (charter
approve, finding waive). E2 (CommandBus actions) will layer policy on
top of these routes; for E1 we expose a thin RBAC-checked surface.

Endpoint layout (registration order matters for FastAPI matching, so
specific routes are declared BEFORE generic ``/{kind}`` patterns)::

    GET    /api/v1/testing/health
    GET    /api/v1/testing/objects
    POST   /api/v1/testing/relations               -> link
    GET    /api/v1/testing/relations/{src_id}      -> get_related
    POST   /api/v1/testing/charters/{id}/approve   -> charter approve
    POST   /api/v1/testing/findings/{id}/waive     -> finding waive

    POST   /api/v1/testing/{kind}                  -> create
    GET    /api/v1/testing/{kind}                  -> list
    GET    /api/v1/testing/{kind}/{obj_id}         -> get
    PUT    /api/v1/testing/{kind}/{obj_id}         -> update
    DELETE /api/v1/testing/{kind}/{obj_id}         -> soft delete
    GET    /api/v1/testing/{kind}/{obj_id}/history -> audit log
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, fields, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from sylion.aeis.testing.ontology.enums import RStatus
from sylion.aeis.testing.ontology.objects import (
    CHARTER_TRANSITIONS,
    OBJECT_TABLE_MAP,
    PRIMARY_KEY_MAP,
)
from sylion.aeis.testing.ontology.store import (
    OntologyStore,
    get_ontology_store,
)
from sylion.security.rbac import requires_role

log = logging.getLogger("sylion.api.testing_routes")

router = APIRouter(prefix="/api/v1/testing", tags=["w14-testing"])


# Resource-name <-> dataclass mapping for the URL path parameter.
KIND_BY_PATH: dict[str, type] = {
    cls.__name__.lower(): cls for cls in OBJECT_TABLE_MAP
}

# Reserved path segments must not collapse into the generic /{kind} catch-all.
# Adding a new dedicated handler? Append the leading segment here too.
RESERVED_PATH_SEGMENTS: frozenset[str] = frozenset({
    "health", "objects", "relations", "charters", "findings",
    "release-gate", "truth-alignment", "simulation",
})


def _resolve_kind(kind: str) -> type:
    if kind.lower() in RESERVED_PATH_SEGMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"'{kind}' is a reserved path segment, not an ontology kind",
        )
    cls = KIND_BY_PATH.get(kind.lower())
    if not cls:
        valid = sorted(KIND_BY_PATH.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown ontology kind '{kind}'. Valid: {valid[:8]}...",
        )
    return cls


def _serialize(obj: Any) -> dict[str, Any]:
    if not is_dataclass(obj):
        raise TypeError("expected dataclass instance")
    return asdict(obj)


def _store() -> OntologyStore:
    """Dependency wrapper. Tests can override via FastAPI dependency_overrides."""
    return get_ontology_store()


# ---------------------------------------------------------------------------
# Health & catalog
# ---------------------------------------------------------------------------


@router.get("/health")
def health(store: OntologyStore = Depends(_store)) -> dict[str, Any]:
    """Lightweight ping used by smoke tests."""
    return store.health()


@router.get("/objects")
def list_objects() -> dict[str, list[dict[str, str]]]:
    """Return the 25 ontology kinds and their primary-key field names."""
    return {
        "kinds": [
            {
                "name": cls.__name__,
                "path": cls.__name__.lower(),
                "primary_key": PRIMARY_KEY_MAP[cls],
                "table": OBJECT_TABLE_MAP[cls],
            }
            for cls in OBJECT_TABLE_MAP
        ],
    }


@router.get("/release-gate/{project_id}")
def release_gate_compat(
    project_id: str,
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    """Compatibility surface for frontend testing hooks.

    The canonical dashboard endpoint is ``/api/v1/test-center/release-gate``.
    This route keeps the older ``/api/v1/testing/*`` client contract live while
    delegating to the same ReleaseRail evaluator.
    """
    from sylion.aeis.testing.release_rail import ReleaseRail

    return ReleaseRail(store).evaluate_for_project(project_id)


@router.get("/truth-alignment")
def truth_alignment_compat(
    feature_id: str | None = Query(default=None),
) -> dict[str, list[dict[str, Any]]]:
    """Compatibility surface returning row-shaped truth-alignment data."""
    from sylion.api.test_center_routes import _get_or_init_matrix

    matrix = _get_or_init_matrix()
    if feature_id:
        feature_ids = [feature_id]
    else:
        feature_ids = list(getattr(matrix, "_snapshots", {}).keys())
    return {"rows": [matrix.build_for_feature(fid) for fid in feature_ids]}


@router.get("/simulation/contracts")
def simulation_contracts_compat(
    project_id: str | None = Query(default=None),
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    """Compatibility list for W14 simulation contracts.

    Without this explicit route, ``/testing/simulation/contracts`` fell into
    the generic ``/{kind}/{obj_id}`` handler and failed because ``simulation``
    is not itself an ontology object kind.
    """
    from sylion.aeis.testing.ontology.objects import SimulationContract

    contracts = store.list(SimulationContract, limit=500)
    if project_id:
        contracts = [
            contract for contract in contracts
            if getattr(contract, "source_project_id", "") == project_id
        ]
    return {
        "contracts": [_serialize(contract) for contract in contracts],
        "count": len(contracts),
        "project_id": project_id,
    }


# ---------------------------------------------------------------------------
# Relations (declared BEFORE generic /{kind} so /relations/* never collapses)
# ---------------------------------------------------------------------------


class LinkPayload(BaseModel):
    src_id: str
    dst_id: str
    relation: str
    actor: str = ""


@router.post("/relations", status_code=201)
def link(
    payload: LinkPayload,
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    try:
        store.link(payload.src_id, payload.dst_id, payload.relation, actor=payload.actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "src_id": payload.src_id,
        "dst_id": payload.dst_id,
        "relation": payload.relation,
        "linked": True,
    }


@router.get("/relations/{src_id}")
def get_related(
    src_id: str,
    relation: str = Query(...),
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    return {
        "src_id": src_id,
        "relation": relation,
        "dst_ids": store.get_related(src_id, relation),
    }


# ---------------------------------------------------------------------------
# Custom transitions (E1 surface — full lifecycle wiring lands in E7)
# ---------------------------------------------------------------------------


class ApproveCharterPayload(BaseModel):
    actor: str
    hg_ticket_id: str | None = None
    council_session_id: str | None = None


@router.post("/charters/{charter_id}/approve")
def approve_charter(
    charter_id: str,
    payload: ApproveCharterPayload,
    store: OntologyStore = Depends(_store),
    _user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    from sylion.aeis.testing.ontology.objects import TestCharter

    charter = store.get(TestCharter, charter_id)
    if not charter:
        raise HTTPException(status_code=404, detail=f"Charter {charter_id} not found")
    allowed = CHARTER_TRANSITIONS.get(charter.status, set())
    if "approved" not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(f"Charter status '{charter.status}' cannot transition to "
                    f"'approved'. Allowed next: {sorted(allowed)}"),
        )
    charter.status = "approved"
    charter.approved_at = time.time()
    if payload.hg_ticket_id:
        charter.hg_ticket_id = payload.hg_ticket_id
    if payload.council_session_id:
        charter.council_session_id = payload.council_session_id
    return _serialize(store.update(charter, actor=payload.actor))


class WaiveFindingPayload(BaseModel):
    actor: str
    rationale: str


@router.post("/findings/{finding_id}/waive")
def waive_finding(
    finding_id: str,
    payload: WaiveFindingPayload,
    store: OntologyStore = Depends(_store),
    _user: str = Depends(requires_role("admin")),
) -> dict[str, Any]:
    from sylion.aeis.testing.ontology.objects import Finding

    finding = store.get(Finding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail=f"Finding {finding_id} not found")
    if not payload.rationale.strip():
        raise HTTPException(status_code=400, detail="rationale must not be empty")
    finding.r_status = RStatus.WAIVED_BY_HUMAN.value
    finding.closed_at = time.time()
    return _serialize(store.update(finding, actor=payload.actor))


# ---------------------------------------------------------------------------
# Generic CRUD per kind (declared AFTER all reserved-path handlers above)
# ---------------------------------------------------------------------------


class CreatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    fields_: dict[str, Any] = Field(default_factory=dict, alias="fields")
    actor: str = ""


class UpdatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    fields_: dict[str, Any] = Field(default_factory=dict, alias="fields")
    actor: str = ""


@router.post("/{kind}", status_code=201)
def create_object(
    kind: str,
    payload: CreatePayload,
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    cls = _resolve_kind(kind)
    valid_field_names = {f.name for f in fields(cls)}
    extra = set(payload.fields_) - valid_field_names
    if extra:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown fields for {cls.__name__}: {sorted(extra)}",
        )
    try:
        obj = cls(**payload.fields_)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        stored = store.create(obj, actor=payload.actor)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize(stored)


@router.get("/{kind}")
def list_objects_of_kind(
    kind: str,
    limit: int = Query(default=100, gt=0, le=10000),
    offset: int = Query(default=0, ge=0),
    include_deleted: bool = Query(default=False),
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    cls = _resolve_kind(kind)
    items = store.list(
        cls,
        filters=None,
        limit=limit,
        offset=offset,
        include_deleted=include_deleted,
    )
    return {"kind": cls.__name__, "items": [_serialize(o) for o in items]}


@router.get("/{kind}/{obj_id}")
def get_object(
    kind: str,
    obj_id: str,
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    cls = _resolve_kind(kind)
    obj = store.get(cls, obj_id)
    if not obj:
        raise HTTPException(status_code=404, detail=f"{cls.__name__} {obj_id} not found")
    return _serialize(obj)


@router.put("/{kind}/{obj_id}")
def update_object(
    kind: str,
    obj_id: str,
    payload: UpdatePayload,
    store: OntologyStore = Depends(_store),
    _user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    cls = _resolve_kind(kind)
    existing = store.get(cls, obj_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"{cls.__name__} {obj_id} not found")
    pk_field = PRIMARY_KEY_MAP[cls]
    valid_field_names = {f.name for f in fields(cls)}
    merged = asdict(existing)
    extra = set(payload.fields_) - valid_field_names
    if extra:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown fields for {cls.__name__}: {sorted(extra)}",
        )
    if pk_field in payload.fields_ and payload.fields_[pk_field] != obj_id:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mutate primary key '{pk_field}' via update",
        )
    merged.update(payload.fields_)
    try:
        new_obj = cls(**merged)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return _serialize(store.update(new_obj, actor=payload.actor))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{kind}/{obj_id}", status_code=204)
def delete_object(
    kind: str,
    obj_id: str,
    actor: str = Query(default=""),
    store: OntologyStore = Depends(_store),
    _user: str = Depends(requires_role("operator")),
) -> None:
    cls = _resolve_kind(kind)
    if not store.soft_delete(cls, obj_id, actor=actor):
        raise HTTPException(
            status_code=404,
            detail=f"{cls.__name__} {obj_id} not found or already deleted",
        )


@router.get("/{kind}/{obj_id}/history")
def object_history(
    kind: str,
    obj_id: str,
    store: OntologyStore = Depends(_store),
) -> dict[str, Any]:
    _resolve_kind(kind)  # validate kind name
    return {"obj_id": obj_id, "history": store.history(obj_id)}
