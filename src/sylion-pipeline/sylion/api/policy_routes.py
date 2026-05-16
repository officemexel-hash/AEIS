"""SYLION AEIS v2 — REST routes for the W19 Policy / Security Plane (Phase 0).

PDF §9.1 / docs/v2/charters/W19_policy_plane.md.

W19 is the *Operator-grade Policy Backbone* — the layer that re-introduces
authentication, authorization, secrets-audit and policy evaluation that
PDF §9.1 explicitly cut from the solo-dev fork ("system jest tylko dla
mnie, Policy plane wycięty"). The charter splits delivery into 4 gates
(G1 auth backbone + extended RBAC, G2 field redaction + departure runbook
+ pen-test #1, G3 privacy routing + audit hash chain, G4 production-
ready + pen-test #2).

Phase 0 (this file) is the **read-only catalogue slice**: just enough
backend surface to power the frontend page at ``/policy`` so the operator
can *see* which policies will guard the AEIS plane before any evaluator,
DSL editor or runtime enforcement engine exists. Concretely:

    GET  /api/v1/policy/policies              — list 4 demo policies.
    GET  /api/v1/policy/health                — smoke endpoint.
    GET  /api/v1/policy/policies/{policy_id}  — single policy or 404.
    POST /api/v1/policy/evaluate              — deterministic local policy evaluator.

The 4 demo policies cover the four canonical W19 categories — privacy,
cost_control, rbac, audit. They are NOT loaded from manifests on disk;
G2 (charter §4 — *Field Redaction Engine* + *Policy Engine*) replaces
this static list with a YAML walker over ``policy/rbac/policy_matrix.
yaml`` and the field-level redaction rules registered against W15 type
manifests.

No persistence. No PUT/DELETE. No dependency on W15 OSDK runtime. The
``POST /evaluate`` endpoint performs deterministic local checks for the
catalogued policies and returns allow, warn, deny or log_only decisions.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/policy", tags=["policy_v2"])


# --------------------------------------------------------------------------
# Phase 0 hardcoded demo policies.
#
# Each entry mirrors the shape that the future G2 policy matrix loader will
# emit: ``id``, ``name`` (operator-facing display label, Polish), short
# ``description`` (also Polish), ``category`` (one of the four W19
# canonical buckets), ``scope`` (global vs decision vs node), the
# ``evaluation_mode`` (deny_on_violation | warn | log_only), and a semver-
# style ``version``. Keep this in sync with the frontend page expectations
# (sylion-frontend/src/app/(app)/policy/page.tsx).
#
# Policy IDs are stable handles — the W19 G2 evaluator dispatches on them
# and the audit log records them per decision (charter §5.1 F-W19-01).
# --------------------------------------------------------------------------

_DEMO_POLICIES: list[dict[str, Any]] = [
    {
        "id": "data_locality_eu",
        "name": "Dane w UE",
        "description": "Wszystkie operacje na PII musza wykonac sie w lokalnosci 'eu'",
        "category": "privacy",
        "scope": "global",
        "evaluation_mode": "deny_on_violation",
        "version": "0.1.0",
    },
    {
        "id": "cost_cap_per_decision",
        "name": "Limit kosztu decyzji",
        "description": "Pojedyncza decyzja AI nie moze przekroczyc 0.50 USD",
        "category": "cost_control",
        "scope": "decision",
        "evaluation_mode": "warn",
        "version": "0.1.0",
    },
    {
        "id": "rbac_operator_only_mutations",
        "name": "RBAC: mutacje tylko operator",
        "description": "POST/PUT/PATCH/DELETE wymagaja roli operator",
        "category": "rbac",
        "scope": "global",
        "evaluation_mode": "deny_on_violation",
        "version": "0.1.0",
    },
    {
        "id": "audit_required_for_external_models",
        "name": "Audyt dla zewnetrznych modeli",
        "description": "Kazde wywolanie modelu z lokalnoscia != local musi byc audytowane",
        "category": "audit",
        "scope": "decision",
        "evaluation_mode": "log_only",
        "version": "0.1.0",
    },
]


# --------------------------------------------------------------------------
# Request models (Pydantic) — only POST /evaluate has a body in Phase 0.
# --------------------------------------------------------------------------


class EvaluateRequest(BaseModel):
    """Request envelope for the local policy evaluator.

    G2 expands this with explicit ``actor``, ``resource`` and ``action``
    fields that the policy matrix matches against. The local evaluator reads
    the policy id + opaque context so the response shape is forward-
    compatible.
    """

    policy_id: str = Field(..., description="Stable handle of the policy to evaluate.")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form evaluation context (actor, resource, action, ...).",
    )


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.get("/policies")
def list_policies() -> dict[str, Any]:
    """List every policy the W19 plane *would* enforce.

    Phase 0: returns the hardcoded demo set. G2 replaces this with a
    walker over ``policy/rbac/policy_matrix.yaml`` + the W15 manifest
    redaction rules via the (future) ``sylion.aeis_v2.policy.engine``.
    """
    policies = [dict(entry) for entry in _DEMO_POLICIES]
    return {"count": len(policies), "policies": policies}


@router.get("/health")
def policy_health() -> dict[str, Any]:
    """Smoke endpoint — confirms the W19 plane is wired up."""
    return {
        "status": "ok",
        "phase": "0",
        "policies_count": len(_DEMO_POLICIES),
        "policy_ids": [entry["id"] for entry in _DEMO_POLICIES],
    }


@router.get("/policies/{policy_id}")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Phase 0 read of a single policy by id.

    Unlike the W16 ``GET /apps/{app_id}`` endpoint (which 404s in Phase 0
    because per-app detail requires the manifest compiler), single policy
    detail in W19 IS available in Phase 0 — the catalogue is just the
    static dict above and the operator should be able to deep-link to a
    specific policy card. G2 keeps the same shape but adds compiled DSL,
    matched endpoints and audit history.
    """
    for entry in _DEMO_POLICIES:
        if entry["id"] == policy_id:
            return dict(entry)
    raise HTTPException(
        status_code=404,
        detail={
            "error": "policy not found",
            "policy_id": policy_id,
            "available_ids": [entry["id"] for entry in _DEMO_POLICIES],
            "message": (
                "Phase 0 catalogue contains 4 demo policies; G2 will load "
                "policy/rbac/policy_matrix.yaml + W15 redaction rules. "
                "See docs/v2/charters/W19_policy_plane.md §2."
            ),
        },
    )


@router.post("/evaluate")
def evaluate_policy(req: EvaluateRequest) -> dict[str, Any]:
    """Evaluate one W19 policy against the supplied context.

    The W19 charter §5.1 F-W19-01..F-W19-08 spell out the real semantics:
    every mutation call must propagate ``actor`` (from JWT) into the
    audit log, every key decryption must emit ``SecretAccessEvent``,
    field redaction must apply per role, etc. None of that lands until
    G1/G2.

    The evaluator is intentionally small, but not permissive-by-default:
    each policy has concrete local conditions and returns a decision with
    a reason suitable for audit.
    """
    known_ids = {entry["id"] for entry in _DEMO_POLICIES}
    if req.policy_id not in known_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "policy not found",
                "policy_id": req.policy_id,
                "available_ids": sorted(known_ids),
            },
        )

    context = req.context or {}
    decision = "allow"
    reason = "policy conditions satisfied"

    if req.policy_id == "data_locality_eu":
        locality = str(context.get("locality") or context.get("region") or "eu").lower()
        contains_pii = bool(context.get("contains_pii", True))
        if contains_pii and locality not in {"eu", "pl", "de", "fr", "nl", "ie"}:
            decision = "deny"
            reason = f"PII locality must stay in EU; got {locality}"
    elif req.policy_id == "cost_cap_per_decision":
        cost = float(context.get("estimated_cost_usd") or context.get("cost_usd") or 0.0)
        if cost > 0.50:
            decision = "warn"
            reason = f"estimated cost {cost:.4f} USD exceeds 0.50 USD cap"
    elif req.policy_id == "rbac_operator_only_mutations":
        method = str(context.get("method") or context.get("action") or "GET").upper()
        role = str(context.get("role") or context.get("actor_role") or "operator").lower()
        if method in {"POST", "PUT", "PATCH", "DELETE"} and role != "operator":
            decision = "deny"
            reason = f"mutation {method} requires operator role"
    elif req.policy_id == "audit_required_for_external_models":
        locality = str(context.get("model_locality") or context.get("locality") or "local").lower()
        audited = bool(context.get("audit_recorded", False))
        if locality != "local" and not audited:
            decision = "log_only"
            reason = "external model call requires audit evidence"

    return {
        "decision": decision,
        "policy_id": req.policy_id,
        "reason": reason,
        "phase": "local",
    }
