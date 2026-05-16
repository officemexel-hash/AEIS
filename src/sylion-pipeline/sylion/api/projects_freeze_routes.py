"""SYLION AEIS v2 - Round Meta-Orchestration freeze endpoints (W14).

Implements the BE-1 / BE-2 / BE-3 endpoints from
``docs/w14_workplan/round_meta_orchestration/W14_PROMPT_CODEX_RM_BACKEND.md``:

* ``POST /api/v1/projects/{project_id}/canon/freeze``      (BE-1)
* ``POST /api/v1/projects/{project_id}/masterplan/freeze`` (BE-2)
* ``POST /api/v1/projects/{project_id}/build/authorize``   (BE-3)

Each endpoint creates a Human Gate ticket via the unified
``governance.tickets`` plane, enforces the round dependency chain
(canon -> masterplan -> build) and appends a hash-chained entry to
``logs/v2/<round>.jsonl`` for tamper-evident audit. All three are
idempotent: a second POST while a ticket is still pending returns the
existing ticket id instead of creating a duplicate.

The actual project-state mutation (``canon_frozen_at``, ``canon_hash``,
``build_authorized_at`` etc.) happens in the post-approval listener
``_complete_<round>_after_approval`` which is called when the Human
Gate ticket transitions to ``approved``. Routes themselves only return
``{ticket_id, status}`` immediately so the operator UI does not block
on async approvals.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sylion.aeis_v2.audit_chain import append_to_chain
from sylion.aeis_v2.audit_profile import resolve_audit_chain_dir
from sylion.governance.tickets import (
    GovernanceTicket,
    fetch_pending,
    submit,
)
from sylion.project_mode import get_project_mode_store

log = logging.getLogger(__name__)

router = APIRouter(tags=["round_meta"])

#: Locks per project_id used to serialise freeze requests so the
#: idempotency guard cannot race with itself when concurrent POSTs
#: hit the same endpoint.
_PROJECT_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.RLock()


def _project_lock(project_id: str) -> threading.RLock:
    with _LOCKS_GUARD:
        lk = _PROJECT_LOCKS.get(project_id)
        if lk is None:
            lk = threading.RLock()
            _PROJECT_LOCKS[project_id] = lk
        return lk


def _store():
    return get_project_mode_store()


def _audit_path(filename: str) -> Path:
    """Return the hash-chained JSONL path under the active audit profile."""
    return resolve_audit_chain_dir() / filename


def _load_project_or_404(project_id: str) -> dict[str, Any]:
    project = _store().get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _existing_pending_ticket(
    project_id: str, action: str, target: str,
) -> str | None:
    """Return the pending ticket_id for (action,target) on this project, or None."""
    try:
        pending = fetch_pending(origin="workspace", project_id=project_id)
    except Exception:  # noqa: BLE001 - defensive: ticket store outage
        log.warning(
            "round_meta: fetch_pending failed for project=%s action=%s",
            project_id, action, exc_info=True,
        )
        return None
    for ticket in pending:
        payload = ticket.payload or {}
        if payload.get("action") == action and payload.get("target") == target:
            return ticket.ticket_id
    return None


def _project_decision_class(project: dict[str, Any]) -> str:
    """Use the project's real risk class for round-meta HumanGate tickets."""
    governance = dict(project.get("governance_policy") or {})
    candidate = str(
        governance.get("decision_class")
        or governance.get("risk_class")
        or (project.get("canon_snapshot") or {}).get("decision_class")
        or "D3"
    ).upper()
    return candidate if candidate in {"D0", "D1", "D2", "D3", "D4", "D5"} else "D3"


def _at_least_decision_class(decision_class: str, minimum: str) -> str:
    """Escalate a decision class to the required minimum risk class."""
    order = ["D0", "D1", "D2", "D3", "D4", "D5"]
    current = decision_class if decision_class in order else "D3"
    required = minimum if minimum in order else "D3"
    return current if order.index(current) >= order.index(required) else required


def _priority_for_decision_class(decision_class: str) -> str:
    if decision_class == "D5":
        return "P0"
    if decision_class in {"D4", "D3"}:
        return "P1"
    return "P2"


def _submit_freeze_ticket(
    project_id: str,
    *,
    action: str,
    target: str,
    title: str,
    summary: str,
    decision_class: str,
    gate_type: str,
    priority: str | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> str:
    """Submit a single-gate Human Gate freeze ticket. Returns ticket_id."""
    payload: dict[str, Any] = {
        "action": action,
        "target": target,
        "requires_human_gate": True,
    }
    if extra_payload:
        payload.update(extra_payload)
    return submit(GovernanceTicket(
        origin="workspace",
        project_id=project_id,
        decision_class=decision_class,
        gate_type=gate_type,
        priority=priority or _priority_for_decision_class(decision_class),
        title=title,
        summary=summary,
        payload=payload,
        requested_by="round_meta",
    ))


# ---------------------------------------------------------------------------
# BE-1 -- canon freeze
# ---------------------------------------------------------------------------


class CanonFreezeBody(BaseModel):
    reason: str = Field(default="", max_length=2000)
    evidence_pack_id: str = Field(default="", max_length=128)


@router.post("/api/v1/projects/{project_id}/canon/freeze")
def freeze_canon(project_id: str, body: CanonFreezeBody | None = None) -> dict[str, Any]:
    """Round 1 freeze: marks canon (Source of Truth) as locked pending HG.

    Returns 404 if project missing, 409 if canon empty, 400 if already frozen.
    """
    explicit_body = body is not None
    body = body or CanonFreezeBody()
    project = _load_project_or_404(project_id)
    canon_text = str(project.get("canonical_book") or "").strip()
    if not canon_text:
        raise HTTPException(
            status_code=409,
            detail="Project canon is empty - draft canonical_book first",
        )
    approvals = dict(project.get("approvals") or {})
    if approvals.get("book") is True or project.get("canon_frozen_at"):
        if not explicit_body:
            return {
                **project,
                "status": project.get("status", "definition_in_progress"),
                "freeze_status": "already_frozen",
            }
        raise HTTPException(
            status_code=400,
            detail="Project canon already frozen",
        )

    with _project_lock(project_id):
        decision_class = _project_decision_class(project)
        existing = _existing_pending_ticket(
            project_id, action="project_freeze", target="canon",
        )
        if existing:
            return {
                "ticket_id": existing,
                "pending_governance_ticket_id": existing,
                "status": "pending_human_gate",
            }

        ticket_id = _submit_freeze_ticket(
            project_id,
            action="project_freeze",
            target="canon",
            title="Approve project canon freeze (Round 1)",
            summary=(
                "Round 1: lock the Source of Truth before Round 2 "
                "(masterplan) can begin."
            ),
            decision_class=decision_class,
            gate_type="source_of_truth_gate",
            extra_payload={
                "reason": body.reason,
                "evidence_pack_id": body.evidence_pack_id,
                "decision_class": decision_class,
                "semantic_gate_type": "source_of_truth_gate",
                "canon_hash_preview": hashlib.sha256(
                    canon_text.encode("utf-8"),
                ).hexdigest()[:16],
            },
        )

        append_to_chain(
            _audit_path("canon_freeze.jsonl"),
            {
                "kind": "round_meta.canon.freeze.requested",
                "project_id": project_id,
                "ticket_id": ticket_id,
                "ts": time.time(),
                "reason": body.reason,
                "evidence_pack_id": body.evidence_pack_id,
            },
        )

        approvals["book_pending_ticket_id"] = ticket_id
        project["approvals"] = approvals
        project["updated_at"] = time.time()
        _store().upsert_project(project)
        _store().add_event(
            project_id, "project.canon.freeze.requested",
            {"ticket_id": ticket_id},
        )

    return {
        "ticket_id": ticket_id,
        "pending_governance_ticket_id": ticket_id,
        "status": "pending_human_gate",
    }


# ---------------------------------------------------------------------------
# BE-2 -- masterplan freeze
# ---------------------------------------------------------------------------


class MasterplanFreezeBody(BaseModel):
    reason: str = Field(default="", max_length=2000)
    evidence_pack_id: str = Field(default="", max_length=128)


@router.post("/api/v1/projects/{project_id}/masterplan/freeze")
def freeze_masterplan(
    project_id: str, body: MasterplanFreezeBody | None = None,
) -> dict[str, Any]:
    """Round 2 freeze: requires Round 1 approved (canon frozen)."""
    explicit_body = body is not None
    body = body or MasterplanFreezeBody()
    project = _load_project_or_404(project_id)
    approvals = dict(project.get("approvals") or {})
    if not (approvals.get("book") is True or project.get("canon_frozen_at")):
        raise HTTPException(
            status_code=409,
            detail="Round 1 (canon) musi byc ukonczona pierwsza",
        )
    masterplan_text = str(project.get("masterplan") or "").strip()
    if not masterplan_text:
        raise HTTPException(
            status_code=409,
            detail="Project masterplan is empty - draft it before freeze",
        )
    if approvals.get("operating_model") is True or project.get("masterplan_frozen_at"):
        if not explicit_body:
            return {
                **project,
                "status": project.get("status", "definition_in_progress"),
                "freeze_status": "already_frozen",
            }
        raise HTTPException(
            status_code=400,
            detail="Project masterplan already frozen",
        )

    with _project_lock(project_id):
        decision_class = _at_least_decision_class(
            _project_decision_class(project),
            "D4",
        )
        existing = _existing_pending_ticket(
            project_id, action="project_freeze", target="masterplan",
        )
        if existing:
            return {
                "ticket_id": existing,
                "pending_governance_ticket_id": existing,
                "status": "pending_human_gate",
            }

        ticket_id = _submit_freeze_ticket(
            project_id,
            action="project_freeze",
            target="masterplan",
            title="Approve project masterplan freeze (Round 2)",
            summary=(
                "Round 2: lock the operating masterplan before Round 3 "
                "(build authorize) can run."
            ),
            decision_class=decision_class,
            gate_type="masterplan_gate",
            extra_payload={
                "reason": body.reason,
                "evidence_pack_id": body.evidence_pack_id,
                "decision_class": decision_class,
                "semantic_gate_type": "masterplan_gate",
                "masterplan_hash_preview": hashlib.sha256(
                    masterplan_text.encode("utf-8"),
                ).hexdigest()[:16],
            },
        )

        append_to_chain(
            _audit_path("masterplan_freeze.jsonl"),
            {
                "kind": "round_meta.masterplan.freeze.requested",
                "project_id": project_id,
                "ticket_id": ticket_id,
                "ts": time.time(),
                "reason": body.reason,
                "evidence_pack_id": body.evidence_pack_id,
            },
        )

        approvals["operating_model_pending_ticket_id"] = ticket_id
        project["approvals"] = approvals
        project["updated_at"] = time.time()
        _store().upsert_project(project)
        _store().add_event(
            project_id, "project.masterplan.freeze.requested",
            {"ticket_id": ticket_id},
        )

    return {
        "ticket_id": ticket_id,
        "pending_governance_ticket_id": ticket_id,
        "status": "pending_human_gate",
    }


# ---------------------------------------------------------------------------
# BE-3 -- build authorize (financial + production + external_action)
# ---------------------------------------------------------------------------


class BuildAuthorizeBody(BaseModel):
    cost_cap_usd: float = Field(..., ge=0.0)
    autonomy_level: Literal["L0", "L1", "L2", "L3", "L4"]
    external_actions_policy: dict[str, Any] = Field(default_factory=dict)


@router.post("/api/v1/projects/{project_id}/build/authorize")
def authorize_build(
    project_id: str, body: BuildAuthorizeBody,
) -> dict[str, Any]:
    """Round 3: financial + production + external_action multi-gate HG.

    The unified ticket plane records ``gate_type=financial`` (highest
    severity slot), with ``payload.gate_types`` listing the full multi-
    gate set ``[financial, production, external_action]``. This matches
    the operator console expectation that one ticket-row covers the
    Round 3 review even though three gates must each approve before the
    HG transition fires.
    """
    project = _load_project_or_404(project_id)
    approvals = dict(project.get("approvals") or {})
    if not (approvals.get("operating_model") is True or project.get("masterplan_frozen_at")):
        raise HTTPException(
            status_code=409,
            detail="Round 2 (masterplan) musi byc ukonczona pierwsza",
        )
    if project.get("build_authorized_at"):
        raise HTTPException(
            status_code=400,
            detail="Project build already authorized",
        )

    with _project_lock(project_id):
        decision_class = _at_least_decision_class(
            _project_decision_class(project),
            "D4",
        )
        existing = _existing_pending_ticket(
            project_id, action="project_build_authorize", target="build",
        )
        if existing:
            approvals["build_pending_ticket_id"] = existing
            project["approvals"] = approvals
            project["updated_at"] = time.time()
            _store().upsert_project(project)
            return {
                "ticket_id": existing,
                "pending_governance_ticket_id": existing,
                "status": "pending_human_gate",
            }

        ticket_id = _submit_freeze_ticket(
            project_id,
            action="project_build_authorize",
            target="build",
            title="Authorize project build (Round 3)",
            summary=(
                "Round 3: financial + production + external_action gate "
                "before any cost can be spent or external action taken."
            ),
            decision_class=decision_class,
            gate_type="financial",
            extra_payload={
                "cost_cap_usd": float(body.cost_cap_usd),
                "autonomy_level": body.autonomy_level,
                "decision_class": decision_class,
                "external_actions_policy": body.external_actions_policy,
                "gate_types": ["financial", "production", "external_action"],
            },
        )

        append_to_chain(
            _audit_path("build_authorize.jsonl"),
            {
                "kind": "round_meta.build.authorize.requested",
                "project_id": project_id,
                "ticket_id": ticket_id,
                "ts": time.time(),
                "cost_cap_usd": float(body.cost_cap_usd),
                "autonomy_level": body.autonomy_level,
                "external_actions_policy": body.external_actions_policy,
            },
        )

        _store().add_event(
            project_id, "project.build.authorize.requested",
            {"ticket_id": ticket_id, "autonomy_level": body.autonomy_level},
        )

        approvals["build_pending_ticket_id"] = ticket_id
        project["approvals"] = approvals
        project["updated_at"] = time.time()
        _store().upsert_project(project)

    return {
        "ticket_id": ticket_id,
        "pending_governance_ticket_id": ticket_id,
        "status": "pending_human_gate",
    }


__all__ = [
    "BuildAuthorizeBody",
    "CanonFreezeBody",
    "MasterplanFreezeBody",
    "router",
]
