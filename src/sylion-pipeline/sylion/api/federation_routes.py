"""SYLION AEIS v2 — REST routes for W17 Compute Provider Federation.

PDF §8.4 — *"Hybrid Local + Central Deployment Architecture"*.

Phase 0 endpoints (prefix ``/api/v1/federation``):

    GET    /health                             — registry size + counters
    GET    /nodes                              — wszystkie zarejestrowane
    GET    /nodes/active                       — ONLINE + heartbeat <= 60s
    POST   /nodes                              — register Node
    POST   /nodes/{node_id}/heartbeat          — update heartbeat + models
    DELETE /nodes/{node_id}                    — unregister
    POST   /route                              — RoutingRequest → RoutingDecision

Wszystkie odpowiedzi są JSON-friendly (``Node.to_dict()`` /
``RoutingDecision.to_dict()``).

Persystencja: brak (Phase 0 in-memory). Po restarcie backendu registry
jest pusty — nodey muszą się zarejestrować ponownie. Phase G2 wpinamy
W15 OSDK i każdy heartbeat pójdzie do append-only event logu.

P1-6: per-node-id heartbeat token bucket (5 rps, 10 burst); per-IP
registration token bucket (0.5 rps, 3 burst). Bypass with
``SYLION_RATE_LIMIT_DISABLED=1``.
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from sylion.aeis_v2.deployment import (
    Node,
    NodeKind,
    NodeStatus,
    PrivacyLevel,
    RoutingRequest,
    get_federation_router,
    get_node_registry,
)
from sylion.aeis_v2.deployment.cost_ledger import (
    CostRecord,
    aggregate_cost_by,
    emit_cost_record,
    query_cost_jsonl,
)
from sylion.aeis_v2.deployment.cost_ledger_pg import (
    apply_cost_ledger_pg_ddl,
    refresh_mv_cost_ledger,
)
from sylion.aeis_v2.deployment.cost_ledger_refresher import (
    CostLedgerRefresher,
    get_refresher,
)
from sylion.aeis_v2.deployment.nodes import (
    MAX_AVAILABLE_MODELS,
    MAX_COST_PER_1K_TOKENS_USD,
)
from sylion.security.rbac import requires_role

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/federation", tags=["federation_v2"])


# --------------------------------------------------------------------------
# W17 P1-6: per-node-id heartbeat + per-IP registration rate limiters
# --------------------------------------------------------------------------
#
# Adversarial review (docs/v2/reviews/ADVERSARIAL_REVIEW_W17_federation.md
# P1-6) noted: a misbehaving (or hostile) node can post heartbeats at
# 1000 req/sec, and the registry semaphore + Python GIL would still let
# those eat all event-loop budget; legitimate nodes' heartbeats start
# timing out. The global ``RateLimitMiddleware`` (sylion/api/rate_limit.py)
# is keyed per-IP/per-user, not per-node-id, so a single IP hosting many
# nodes can still saturate the heartbeat path.
#
# Fix: a tiny in-process token bucket keyed on ``node_id`` for heartbeats
# (5 rps, burst 10 — generous; legit nodes heartbeat every 10-30s) and a
# stricter bucket keyed on source IP for registration (0.5 rps, burst 3).
# Honours the standard ``SYLION_RATE_LIMIT_DISABLED=1`` env-var bypass for
# dev/test/load-profiling, mirroring the ``SYLION_RBAC_DISABLED`` pattern.

HEARTBEAT_RATE_PER_SEC: float = 5.0
HEARTBEAT_BURST: float = 10.0
REGISTRATION_RATE_PER_SEC: float = 0.5
REGISTRATION_BURST: float = 3.0


def _rate_limit_disabled() -> bool:
    """Read env at call time so tests using ``monkeypatch.setenv`` work."""
    return os.environ.get("SYLION_RATE_LIMIT_DISABLED", "0").strip() == "1"


# Module-level token-bucket maps. ``threading.Lock`` guards every read /
# write so concurrent uvicorn workers can't race on bucket math. We hold
# the lock for the (read, refill, decide, write) tuple — the work inside
# is microseconds so contention is negligible compared to a real handler.
_HEARTBEAT_BUCKETS: dict[str, tuple[float, float]] = {}
_REGISTRATION_BUCKETS: dict[str, tuple[float, float]] = {}
_BUCKET_LOCK = threading.Lock()


def _check_token_bucket(
    buckets: dict[str, tuple[float, float]],
    key: str,
    rate_per_sec: float,
    burst: float,
) -> bool:
    """Generic token-bucket gate.

    Returns ``True`` if the request is allowed (bucket had >= 1 token,
    decremented by 1) or ``False`` if the caller should be 429-ed.

    Refills the bucket lazily: ``tokens = min(burst, tokens + dt * rate)``
    where ``dt`` is wall time since the last refill. Fresh keys start at
    full burst (so the first request never gets 429).
    """
    now = time.monotonic()
    with _BUCKET_LOCK:
        tokens, last_refill = buckets.get(key, (burst, now))
        elapsed = max(0.0, now - last_refill)
        tokens = min(burst, tokens + elapsed * rate_per_sec)
        if tokens >= 1.0:
            buckets[key] = (tokens - 1.0, now)
            return True
        # Don't update last_refill on rejection — preserves continuous
        # refill so a node spamming 100 req/s still earns 1 token every
        # 1/rate_per_sec seconds rather than starving forever.
        buckets[key] = (tokens, last_refill)
        return False


def _check_heartbeat_rate(node_id: str) -> bool:
    """Per-node-id heartbeat gate (5 rps, burst 10). Bypass via env."""
    if _rate_limit_disabled():
        return True
    return _check_token_bucket(
        _HEARTBEAT_BUCKETS, node_id,
        HEARTBEAT_RATE_PER_SEC, HEARTBEAT_BURST,
    )


def _check_registration_rate(client_ip: str | None) -> bool:
    """Per-IP registration gate (0.5 rps, burst 3). Bypass via env.

    ``client_ip=None`` (e.g. starlette TestClient with no client tuple)
    skips the check — there is no useful key to scope against, and the
    test surface should not be poisoned by an unkeyable bucket.
    """
    if _rate_limit_disabled():
        return True
    if client_ip is None:
        return True
    return _check_token_bucket(
        _REGISTRATION_BUCKETS, client_ip,
        REGISTRATION_RATE_PER_SEC, REGISTRATION_BURST,
    )


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------


def _validate_cost_dict(value: dict[str, float] | None) -> None:
    """W17 P1-2: shared NaN/inf/negative/over-max guard for cost dicts.

    Raises ``HTTPException(422)`` with a field-specific error message when
    any model's cost is non-numeric, NaN/inf, negative, or above
    ``MAX_COST_PER_1K_TOKENS_USD``. This mirrors ``Node.validate`` so the
    REST surface and the dataclass enforce the same invariant.

    Why a route-level helper rather than a Pydantic ``field_validator``?
    Pydantic stores the raw bad input in its ``ValidationError.errors()``
    payload, and FastAPI's default 422 handler tries to ``json.dumps`` that
    payload — which crashes on bare ``NaN``/``Infinity`` because stdlib
    ``json`` is RFC-compliant. Validating in the route lets us craft a
    JSON-safe error body that doesn't echo the poisoned float.
    """
    if not value:
        return
    for model_id, price in value.items():
        try:
            p = float(price)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"cost_per_1k_tokens_usd['{model_id}'] is not "
                    f"numeric"
                ),
            ) from exc
        if math.isnan(p) or math.isinf(p):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"cost_per_1k_tokens_usd['{model_id}'] must be "
                    f"finite (no NaN/inf)"
                ),
            )
        if p < 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"cost_per_1k_tokens_usd['{model_id}'] must be "
                    f">= 0, got {p}"
                ),
            )
        if p > MAX_COST_PER_1K_TOKENS_USD:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"cost_per_1k_tokens_usd['{model_id}'] exceeds "
                    f"max {MAX_COST_PER_1K_TOKENS_USD} USD/1k tokens, "
                    f"got {p}"
                ),
            )


class RegisterNodeRequest(BaseModel):
    """Body dla ``POST /nodes``.

    ``node_id`` jest opcjonalny — registry wygeneruje uuid jesli pusty
    lub None. Pozostale pola mapuja sie 1:1 na ``Node``.
    """

    node_id: str | None = None
    name: str
    kind: NodeKind
    status: NodeStatus = NodeStatus.UNKNOWN
    base_url: str = ""
    locality: str = "local"
    tags: list[str] = Field(default_factory=list)
    available_models: list[str] = Field(default_factory=list)
    cost_per_1k_tokens_usd: dict[str, float] = Field(default_factory=dict)
    capacity_score: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class HeartbeatRequest(BaseModel):
    """Body dla ``POST /nodes/{node_id}/heartbeat``.

    ``available_models`` jest opcjonalny — gdy podany, snapshot zastepuje
    cala liste; gdy ``None``, lista pozostaje bez zmian.

    ``cost_per_1k_tokens_usd`` jest opcjonalny — gdy podany, kazda wartosc
    przechodzi przez P1-2 guard (NaN/inf/negative/over-max rejection)
    zanim trafi do registry.
    """

    status: NodeStatus = NodeStatus.ONLINE
    available_models: list[str] | None = None
    cost_per_1k_tokens_usd: dict[str, float] | None = None


class RouteRequest(BaseModel):
    """Body dla ``POST /route`` — fields ``RoutingRequest``."""

    model_id: str
    privacy_level: PrivacyLevel = PrivacyLevel.ANY
    fallback_models: list[str] = Field(default_factory=list)
    max_cost_per_1k: float | None = None
    prefer_locality: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------


@router.get("/health", dependencies=[Depends(requires_role("operator"))])
def federation_health() -> dict[str, Any]:
    """Smoke endpoint — daje podglad stanu federacji w jednym wywolaniu.

    P0-6 hardening: requires `operator` role. The middleware
    ``RBACEnforcementMiddleware`` only fires on mutation methods
    (POST/PUT/PATCH/DELETE), so GET endpoints must declare the dependency
    explicitly. Honours ``SYLION_RBAC_DISABLED=1`` env bypass for dev/test.
    """
    reg = get_node_registry()
    rtr = get_federation_router()
    return {
        "status": "ok",
        "phase": "0",
        "total_nodes": reg.size(),
        "active_nodes": len(reg.list_active()),
        "routing_decisions_total": rtr.decisions_total,
    }


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------


@router.get("/nodes", dependencies=[Depends(requires_role("operator"))])
def list_nodes() -> dict[str, Any]:
    """Wszystkie zarejestrowane node-y, posortowane po nazwie.

    P0-6 hardening: requires `operator` role to prevent anonymous topology
    leak (base_url, available_models, cost_per_1k_tokens_usd, metadata).
    """
    reg = get_node_registry()
    nodes = reg.list_all()
    return {
        "count": len(nodes),
        "nodes": [n.to_dict() for n in nodes],
    }


@router.get("/nodes/active", dependencies=[Depends(requires_role("operator"))])
def list_active_nodes(stale_secs: int = 60) -> dict[str, Any]:
    """Tylko aktywne (ONLINE + heartbeat <= ``stale_secs`` sek temu).

    P0-6 hardening: requires `operator` role; same rationale as ``/nodes``.
    """
    reg = get_node_registry()
    nodes = reg.list_active(stale_secs=stale_secs)
    return {
        "count": len(nodes),
        "stale_secs": stale_secs,
        "nodes": [n.to_dict() for n in nodes],
    }


@router.post("/nodes")
def register_node(req: RegisterNodeRequest, request: Request) -> dict[str, Any]:
    """Zarejestruj lub zastap node-a w federacji.

    Jesli ``node_id`` w body jest podany i istnieje — node zostanie
    zastapiony (replace). Heartbeat ustawiany jest na ``now``.

    P0-1 hardening: ``Node.validate`` rejects unknown locality, unbounded
    capacity_score, missing cost for compute providers, and oversized
    available_models lists. Raises HTTP 400 on validation failure.

    P1-2 hardening: every ``cost_per_1k_tokens_usd`` entry is checked for
    NaN/inf/negative/over-max via ``_validate_cost_dict`` *before* it
    reaches ``Node.validate`` so the response is HTTP 422 with a field-
    specific message. ``Node.validate`` repeats the same check at the
    dataclass boundary as defense in depth.

    P1-6 hardening: per-source-IP token bucket (0.5 rps, burst 3) caps
    registration storms. Bypass with ``SYLION_RATE_LIMIT_DISABLED=1``.
    """
    client_ip = request.client.host if request.client else None
    if not _check_registration_rate(client_ip):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "registration rate limit exceeded",
                "client_ip": client_ip,
                "limit_per_sec": REGISTRATION_RATE_PER_SEC,
                "burst": REGISTRATION_BURST,
            },
        )
    _validate_cost_dict(req.cost_per_1k_tokens_usd)
    try:
        node = Node.validate(
            node_id=req.node_id or "",
            name=req.name,
            kind=req.kind,
            status=req.status,
            base_url=req.base_url,
            locality=req.locality,
            tags=list(req.tags),
            available_models=list(req.available_models),
            cost_per_1k_tokens_usd=dict(req.cost_per_1k_tokens_usd),
            capacity_score=float(req.capacity_score),
            metadata=dict(req.metadata),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    reg = get_node_registry()
    saved = reg.register(node)
    return saved.to_dict()


@router.post("/nodes/{node_id}/heartbeat")
def heartbeat(node_id: str, req: HeartbeatRequest) -> dict[str, Any]:
    """Odswiez heartbeat zarejestrowanego node-a.

    P0-1 hardening: cap available_models length on heartbeat (a hostile
    node could otherwise flood the registry by claiming thousands of models).

    P1-2 hardening: validate every ``cost_per_1k_tokens_usd`` value if a
    cost update was sent on this heartbeat (reject NaN/inf/negative/over-
    max). The federation router's sort math depends on these being finite
    and non-negative.

    P1-6 hardening: per-node-id token bucket (5 rps, burst 10) caps
    heartbeat storms. Bypass with ``SYLION_RATE_LIMIT_DISABLED=1``.
    """
    if not _check_heartbeat_rate(node_id):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "heartbeat rate limit exceeded",
                "node_id": node_id,
                "limit_per_sec": HEARTBEAT_RATE_PER_SEC,
                "burst": HEARTBEAT_BURST,
            },
        )
    if req.available_models is not None and len(req.available_models) > MAX_AVAILABLE_MODELS:
        raise HTTPException(
            400,
            f"available_models has {len(req.available_models)} entries; "
            f"max is {MAX_AVAILABLE_MODELS}",
        )
    _validate_cost_dict(req.cost_per_1k_tokens_usd)
    reg = get_node_registry()
    ok = reg.update_heartbeat(
        node_id=node_id,
        status=req.status,
        available_models=req.available_models,
    )
    if not ok:
        raise HTTPException(404, f"node '{node_id}' nie zarejestrowany w federacji")
    node = reg.get(node_id)
    return {"ok": True, "node": node.to_dict() if node else None}


@router.delete("/nodes/{node_id}")
def unregister_node(node_id: str) -> dict[str, Any]:
    """Usun node-a z federacji."""
    reg = get_node_registry()
    ok = reg.unregister(node_id)
    if not ok:
        raise HTTPException(404, f"node '{node_id}' nie zarejestrowany w federacji")
    return {"ok": True, "node_id": node_id}


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


@router.post("/route")
def route_request(req: RouteRequest) -> dict[str, Any]:
    """Zwroc decyzje routingu dla taska wymagajacego ``model_id``."""
    rtr = get_federation_router()
    decision = rtr.route(RoutingRequest(
        model_id=req.model_id,
        privacy_level=req.privacy_level,
        fallback_models=list(req.fallback_models),
        max_cost_per_1k=req.max_cost_per_1k,
        prefer_locality=list(req.prefer_locality),
    ))
    return decision.to_dict()


# --------------------------------------------------------------------------
# W17 cost-ledger (Phase 0) — read endpoints + DEV-only synthetic write.
# --------------------------------------------------------------------------
#
# Per ADR-001 Decision #3 the cost-ledger is event-sourced: every routing
# decision emits a ``cost.recorded`` event (see federation._record_decision_cost)
# that lands in ``logs/v2/cost_ledger.jsonl`` plus the in-process event_bus.
# These endpoints expose the JSONL aggregation for the operator UI; G2
# will swap the implementation to read the PG materialized view
# ``mv_cost_ledger`` while keeping the same response shape.


class RecordCostRequest(BaseModel):
    """DEV-MODE body for ``POST /costs/record``.

    ONLY accepted when ``SYLION_DEV_MODE=1`` — the production path is
    ``federation.route()`` automatically emitting a cost row. Operators
    use this synthetic endpoint to seed the ledger for UI smoke tests
    and load-profiling without spinning up a real LLM call.
    """

    session_id: str = ""
    decision_id: str = ""
    host: str = ""
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get(
    "/costs/recent",
    dependencies=[Depends(requires_role("operator"))],
)
def costs_recent(
    limit: int = 100,
    model: str | None = None,
    session_id: str | None = None,
    host: str | None = None,
) -> dict[str, Any]:
    """Return the most recent N cost records, newest last.

    Query params:
        limit: cap on returned rows (max 1000 to bound payload).
        model: exact model_id filter.
        session_id: exact session_id filter.
        host: exact node_id filter.

    P0-6 hardening: requires `operator` role; the cost ledger reveals
    routing topology (which nodes serve which models) so anonymous read
    is not allowed.
    """
    if limit < 0:
        raise HTTPException(400, "limit must be >= 0")
    if limit > 1000:
        limit = 1000
    rows = query_cost_jsonl(
        limit=limit,
        model=model,
        session_id=session_id,
        host=host,
    )
    return {
        "count": len(rows),
        "limit": limit,
        "records": [r.to_dict() for r in rows],
    }


@router.get(
    "/costs/aggregate",
    dependencies=[Depends(requires_role("operator"))],
)
def costs_aggregate(
    group_by: str = "model",
    since: float = 0.0,
    until: float | None = None,
) -> dict[str, Any]:
    """Aggregate cost by ``model`` / ``host`` / ``session_id`` over a window.

    Query params:
        group_by: one of ``model``, ``host``, ``session_id``.
        since: epoch seconds lower bound (inclusive). 0.0 = all-time.
        until: epoch seconds upper bound (inclusive). Omit for unbounded.

    Returns ``{group_by, since, until, buckets: {key: {totals}}}``.
    """
    try:
        agg = aggregate_cost_by(since_ts=since, until_ts=until, group_by=group_by)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "group_by": group_by,
        "since": since,
        "until": until,
        "buckets": agg,
    }


@router.post("/costs/record")
def costs_record(req: RecordCostRequest) -> dict[str, Any]:
    """DEV-MODE: emit a synthetic cost row into the ledger.

    Gated on ``SYLION_DEV_MODE=1`` — anything else returns 403. Used by
    operators and integration smoke tests to seed the JSONL without
    routing a real LLM call.

    Production cost emission goes through ``federation.route()`` →
    ``_record_decision_cost`` → ``emit_cost_record``; this endpoint
    exists only to short-circuit that pipeline for dev/test scenarios.
    """
    if os.environ.get("SYLION_DEV_MODE", "0").strip() != "1":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "costs/record is dev-only",
                "hint": "set SYLION_DEV_MODE=1 to enable",
            },
        )
    record = CostRecord(
        ts=time.time(),
        session_id=req.session_id,
        decision_id=req.decision_id,
        host=req.host,
        model=req.model,
        tokens_in=int(req.tokens_in),
        tokens_out=int(req.tokens_out),
        cost_usd=float(req.cost_usd),
        metadata=dict(req.metadata),
    )
    emit_cost_record(record)
    return {"ok": True, "record": record.to_dict()}


# --------------------------------------------------------------------------
# W17 G2 step 2 — PG cost-ledger DDL bootstrap + MV refresh
# --------------------------------------------------------------------------
#
# Per ADR-001 #3 the steady-state cost-ledger lives in PG; these endpoints
# let the operator (a) bootstrap the schema (``cost_event`` + ``mv_cost_ledger``)
# and (b) trigger an ad-hoc refresh of the MV when they want fresh
# numbers between the cron-scheduled refreshes (G2 step 3).
#
# Both endpoints are operator-role gated — DDL changes and MV refreshes
# are not anonymous-safe (DDL mutates schema; concurrent refreshes can
# stack up locks even with CONCURRENTLY).


class ApplyPgDdlRequest(BaseModel):
    """Body for ``POST /costs/apply-pg-ddl``.

    ``dry_run`` mirrors the W15 applier convention — when True, the
    response shows ``statements_total`` without touching PG so the
    operator can preview the impact in the UI before clicking Apply.
    """

    dry_run: bool = False


@router.post(
    "/costs/apply-pg-ddl",
    dependencies=[Depends(requires_role("operator"))],
)
def costs_apply_pg_ddl(req: ApplyPgDdlRequest) -> dict[str, Any]:
    """Apply ``sylion_v2.cost_event`` table + ``mv_cost_ledger`` MV DDL.

    Idempotent — uses CREATE ... IF NOT EXISTS everywhere. Operators run
    this once per deployment to bootstrap the schema; re-running on an
    already-applied schema is a no-op at the PG layer.

    Reuses the v1 advisor pool via ``_get_pg_connection`` (same path the
    W15 ontology applier uses). When PG is unreachable the response
    carries ``preview_only=True`` and ``applied=False`` — the operator
    UI surfaces a "PG offline — schema not applied" toast.
    """
    # Reuse the W15 applier's pool resolver — it already has fail-fast
    # PGUnreachable plumbing with a 60s negative-cache, so we don't pay
    # 2s per call when PG is offline.
    from sylion.aeis_v2.ontology.applier import _get_pg_connection
    pool = _get_pg_connection()
    return apply_cost_ledger_pg_ddl(pool, dry_run=req.dry_run)


class RefreshMvRequest(BaseModel):
    """Body for ``POST /costs/refresh-mv``.

    ``concurrently=True`` (default) keeps /costs/recent readers
    unblocked. Pass ``False`` ONLY for the very first refresh after a
    fresh ``apply-pg-ddl`` — see ``cost_ledger_pg.refresh_mv_cost_ledger``.
    """

    concurrently: bool = True


@router.post(
    "/costs/refresh-mv",
    dependencies=[Depends(requires_role("operator"))],
)
def costs_refresh_mv(req: RefreshMvRequest) -> dict[str, Any]:
    """Refresh ``sylion_v2.mv_cost_ledger`` (operator-triggered).

    Steady-state refreshes happen on a cron schedule (G2 step 3); this
    endpoint exists for the "I just changed cost_per_1k and want fresh
    numbers in the dashboard NOW" flow.

    Returns ``{ok: bool, concurrently: bool, error: str|None}``. ``ok=False``
    with ``error="pg_unreachable"`` when the pool is unavailable so the UI
    can branch on a stable error string.
    """
    from sylion.aeis_v2.ontology.applier import _get_pg_connection
    pool = _get_pg_connection()
    if pool is None:
        return {
            "ok": False,
            "concurrently": req.concurrently,
            "error": "pg_unreachable",
        }
    ok = refresh_mv_cost_ledger(pool, concurrently=req.concurrently)
    return {
        "ok": bool(ok),
        "concurrently": req.concurrently,
        "error": None if ok else "refresh_failed",
    }


# --------------------------------------------------------------------------
# W17 G2 step 3 — cron refresh worker control surface
# --------------------------------------------------------------------------
#
# These endpoints let the operator console start/stop the in-process
# daemon thread that periodically calls ``REFRESH MATERIALIZED VIEW
# CONCURRENTLY``. G3 replaces the daemon with a proper systemd service
# / k8s CronJob; the REST shape stays the same so the UI doesn't have
# to branch on the deployment topology.
#
# Operator-role only — start/stop affects the cost-ledger freshness
# guarantees that downstream dashboards rely on.


class RefresherStartRequest(BaseModel):
    """Body for ``POST /costs/refresher/start``.

    ``interval_s`` overrides ``SYLION_COST_REFRESH_INTERVAL_S`` for the
    lifetime of the new worker. Pass ``None`` to keep the env-driven
    default. ``initial_delay_s`` mirrors the env var of the same name.
    """

    interval_s: float | None = None
    initial_delay_s: float | None = None


@router.post(
    "/costs/refresher/start",
    dependencies=[Depends(requires_role("operator"))],
)
def costs_refresher_start(req: RefresherStartRequest) -> dict[str, Any]:
    """Start (or hot-reconfigure) the cost-ledger refresh daemon.

    Behaviour:

    - When the singleton refresher is NOT running with the requested
      schedule, we stop+drop+rebuild it so the new interval applies
      immediately. This is rare (the operator would only override
      defaults to chase a debugging incident), and rebuild is cheap
      (a Thread + Event).
    - When already running with the same schedule, ``start()`` is
      idempotent — we just return the current stats.
    - The new worker spawns a daemon thread that survives FastAPI
      reloads but dies with the process; long-running deployments
      that need durability across restarts should use the G3
      systemd/k8s replacement.
    """
    from sylion.aeis_v2.deployment import cost_ledger_refresher as _mod

    interval = req.interval_s if req.interval_s is not None else None
    delay = req.initial_delay_s if req.initial_delay_s is not None else None
    rebuild_needed = interval is not None or delay is not None

    if rebuild_needed:
        # Stop the existing singleton, replace with a custom-config one.
        existing = get_refresher()
        existing.stop(timeout_s=2.0)
        new_kwargs: dict[str, Any] = {}
        if interval is not None:
            if interval <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"interval_s must be > 0, got {interval}",
                )
            new_kwargs["interval_s"] = float(interval)
        if delay is not None:
            if delay < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"initial_delay_s must be >= 0, got {delay}",
                )
            new_kwargs["initial_delay_s"] = float(delay)
        try:
            new_refresher = CostLedgerRefresher(**new_kwargs)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        _mod._refresher_singleton = new_refresher
        new_refresher.start()
        ref = new_refresher
    else:
        ref = get_refresher()
        ref.start()

    return {
        "ok": True,
        "running": ref.is_running(),
        "interval_s": ref.interval_s,
        "initial_delay_s": ref.initial_delay_s,
        "stats": ref.stats.to_dict(),
    }


@router.post(
    "/costs/refresher/stop",
    dependencies=[Depends(requires_role("operator"))],
)
def costs_refresher_stop(timeout_s: float = 5.0) -> dict[str, Any]:
    """Stop the cost-ledger refresh daemon and report the final stats.

    ``timeout_s`` caps how long we wait for the loop to exit (default
    5s). On timeout the response carries ``ok=False`` and operators
    can investigate via logs; the daemon is still flagged for stop and
    will exit on its next loop iteration.
    """
    if timeout_s < 0:
        raise HTTPException(400, f"timeout_s must be >= 0, got {timeout_s}")
    ref = get_refresher()
    clean = ref.stop(timeout_s=float(timeout_s))
    return {
        "ok": bool(clean),
        "running": ref.is_running(),
        "stats": ref.stats.to_dict(),
    }


@router.get(
    "/costs/refresher/stats",
    dependencies=[Depends(requires_role("operator"))],
)
def costs_refresher_stats() -> dict[str, Any]:
    """Return live stats for the cost-ledger refresh daemon.

    Always returns 200 — even when the daemon has never been started
    (in which case ``running=False`` and stats are zeroed). The
    operator UI polls this endpoint to render the "last refresh N
    seconds ago" widget.
    """
    ref = get_refresher()
    return {
        "running": ref.is_running(),
        "interval_s": ref.interval_s,
        "initial_delay_s": ref.initial_delay_s,
        "stats": ref.stats.to_dict(),
    }


# ----------------------------------------------------------------------------
# W17 cost-cap REST runtime control (a7d2 W17 sprint 1 + my fixes)
# ----------------------------------------------------------------------------

from typing import Literal as _Literal  # noqa: E402

from sylion.aeis_v2.deployment import federation as _fed_mod  # noqa: E402
from sylion.aeis_v2.deployment.federation import (  # noqa: E402
    COST_CAP_PER_DECISION_USD,
    _evaluate_cost_cap,
    get_runtime_cost_cap_mode,
    set_runtime_cost_cap_mode,
)


class CostCapModeRequest(BaseModel):
    """Body for ``POST /cost-cap/mode``."""

    mode: _Literal["warn", "deny", "off"] | None = None


class CostCapSimulateRequest(BaseModel):
    """Body for ``POST /cost-cap/simulate`` — pure dry-run."""

    cost_per_1k_usd: float = Field(ge=0, le=1000)
    estimated_tokens: int | None = Field(default=None, ge=0, le=1_000_000)
    mode: _Literal["warn", "deny", "off"] = "warn"


@router.post(
    "/cost-cap/mode",
    dependencies=[Depends(requires_role("operator"))],
)
def cost_cap_mode_route(req: CostCapModeRequest) -> dict[str, Any]:
    """Set runtime cost-cap mode (in-memory). Pass ``mode=null`` to clear."""
    try:
        set_runtime_cost_cap_mode(req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, "mode": get_runtime_cost_cap_mode()}


@router.get(
    "/cost-cap/status",
    dependencies=[Depends(requires_role("operator"))],
)
def cost_cap_status_route() -> dict[str, Any]:
    """Diagnostic snapshot — runtime/env/effective + warnings counter."""
    return {
        "mode": get_runtime_cost_cap_mode(),
        "limit_usd": COST_CAP_PER_DECISION_USD,
        "estimated_tokens": _fed_mod.COST_CAP_ESTIMATED_TOKENS,
        "warnings_total": _fed_mod.cost_cap_warnings_total,
    }


@router.post(
    "/cost-cap/simulate",
    dependencies=[Depends(requires_role("operator"))],
)
def cost_cap_simulate_route(req: CostCapSimulateRequest) -> dict[str, Any]:
    """Simulate cost-cap evaluation without affecting state.

    Pure function — does NOT mutate the warn-counter. Lets the operator
    pre-validate a (cost_per_1k, tokens, mode) triple before flipping
    the runtime knob via /cost-cap/mode.
    """
    result = _evaluate_cost_cap(
        cost_per_1k_usd=req.cost_per_1k_usd,
        estimated_tokens=req.estimated_tokens,
        mode=req.mode,
    )
    return {
        "exceeded": result.exceeded,
        "estimated_usd": result.estimated_usd,
        "limit_usd": COST_CAP_PER_DECISION_USD,
        "decision": result.action,
        "mode": req.mode,
    }
