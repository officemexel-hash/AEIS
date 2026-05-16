"""SYLION AEIS v2 — replay-as-fork REST endpoints.

Sprint 3 B-replay deliverable. Wires the replay-as-fork primitives
(commit ``82b0af48``) and the LRU snapshot store (linter-merged
``ReplayStorageLRU``) into 3 REST endpoints:

    POST /api/v1/terminal/sessions/{session_id}/snapshot
        body  : {"decision_point": int, "state": dict | None}
        returns: SessionSnapshot dict — caller stores ``snapshot_id``

    POST /api/v1/replay/run
        body  : {"snapshot_id": str,
                 "model_override": str | None,
                 "context_override": dict | None,
                 "replay_decisions": list[str],   // simulated outcome
                 "replay_final":     list[float]}
        returns: ReplayResult dict — divergence_score etc.

    GET  /api/v1/replay/list?limit=N
        returns: last N rows from logs/v2/replay_fork.jsonl

The ``replay_decisions`` + ``replay_final`` fields on the run body let
the caller (operator console / e2e test) simulate the replay outcome
without rebuilding the entire upstream pipeline. A future commit will
swap this with a real replay-callable adapter that calls the actual
council wedge / federation router under override.

Per Kimi review k3_replay_endpoint_security (round 51:30):

* snapshot_id space is uuid4 — not enumerable in practice.
* model_override is constrained server-side to a known whitelist
  (same as ADR-002 routing matrix); anything else returns 422.
* context_override is filtered through ``JinjaContextSafelist`` to
  drop dunder keys before forwarding.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from sylion.aeis_v2.replay_v2 import (
    ReplayFork,
    ReplayStorageLRU,
    SessionSnapshot,
)
from sylion.security.rbac import requires_role

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["replay_v2"])

#: Process-wide LRU store for snapshots — capped to keep memory bounded.
_DEFAULT_LRU_CAP: int = 1000

#: Path to the replay-fork audit JSONL. Used by the list endpoint.
#: Path to replay-fork audit JSONL. Mirrors the producer-side path
#: (``aeis_v2/replay_v2/fork.py`` uses ``parents[3]/logs/v2``); from
#: ``api/replay_routes.py`` the equivalent is ``parents[2]`` (api/ and
#: aeis_v2/ share parent sylion/). Bug fixed at runtime check 2026-04-28
#: alongside metrics_v2 / health_v2 — same parents[1]→parents[2] drift.
_DEFAULT_AUDIT_PATH = (
    Path(__file__).resolve().parents[2]
    / "logs" / "v2" / "replay_fork.jsonl"
)

#: Allow-list of model overrides. Mirrors ADR-002 routing matrix —
#: anything else returns 422 (per Kimi k3 finding).
_ALLOWED_MODEL_OVERRIDES: frozenset[str] = frozenset({
    "gpt-oss:20b",        # Ollama default
    "claude-opus-4.7",
    "claude-sonnet-4.7",
    "kimi-k1",
    "codex-cli",
    "scripted",           # deterministic test harness
})


_storage = ReplayStorageLRU()


def _storage_get() -> ReplayStorageLRU:
    """Indirection so tests can monkeypatch the storage."""
    return _storage


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class _SnapshotBody(BaseModel):
    decision_point: int = Field(..., ge=0)
    state: dict[str, Any] = Field(default_factory=dict)


class _RunBody(BaseModel):
    snapshot_id: str = Field(..., min_length=8, max_length=64)
    model_override: str | None = Field(default=None, max_length=64)
    context_override: dict[str, Any] | None = None
    replay_decisions: list[str] = Field(default_factory=list)
    replay_final: list[float] = Field(default_factory=list)
    # The operator must ALSO submit the original outcomes so the server
    # can compute divergence without re-running upstream — keeps this
    # endpoint stateless and cheap.
    original_decisions: list[str] = Field(default_factory=list)
    original_final: list[float] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _filter_context_override(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """Drop any dunder keys (``__foo__``) — Kimi k3 finding."""
    if not ctx:
        return {}
    return {
        k: v for k, v in ctx.items()
        if not (k.startswith("__") and k.endswith("__"))
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/terminal/sessions/{session_id}/snapshot",
    dependencies=[Depends(requires_role("operator", "owner"))],
)
def snapshot_session(session_id: str, body: _SnapshotBody) -> dict[str, Any]:
    """Capture a snapshot of a session at ``decision_point``.

    The snapshot is stored in the process-wide LRU keyed by
    ``snapshot_id``; subsequent ``/replay/run`` calls reference that id.
    """
    snapshot = SessionSnapshot.capture(
        body.state,
        decision_point=body.decision_point,
        original_session_id=session_id,
    )
    payload = snapshot.to_dict()
    store = _storage_get()
    store.store(snapshot.snapshot_id, payload)
    store.evict_old(max=_DEFAULT_LRU_CAP)
    return payload


@router.post(
    "/replay/run",
    dependencies=[Depends(requires_role("operator", "owner"))],
)
def run_replay(body: _RunBody) -> dict[str, Any]:
    """Run a replay against an earlier snapshot + caller-supplied outcomes.

    Returns the full ReplayResult dict (incl. divergence_score). The
    audit JSONL is emitted by ``ReplayFork.run`` itself so the same
    chained log surfaces in ``GET /replay/list``.
    """
    if (
        body.model_override is not None
        and body.model_override not in _ALLOWED_MODEL_OVERRIDES
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "model_override_not_allowed",
                "allowed": sorted(_ALLOWED_MODEL_OVERRIDES),
                "got": body.model_override,
            },
        )

    store = _storage_get()
    snapshot_dict = store.get(body.snapshot_id)
    if snapshot_dict is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "snapshot_not_found",
                "snapshot_id": body.snapshot_id,
            },
        )

    # Reconstitute SessionSnapshot from stored dict.
    snapshot = SessionSnapshot(
        snapshot_id=snapshot_dict["snapshot_id"],
        original_session_id=snapshot_dict["original_session_id"],
        decision_point=snapshot_dict["decision_point"],
        captured_at=snapshot_dict["captured_at"],
        state=snapshot_dict["state"],
        state_hash=snapshot_dict["state_hash"],
    )

    fork = ReplayFork(
        snapshot,
        original_decisions=body.original_decisions,
        original_final=body.original_final,
    )

    # The caller pre-computed the replay outcomes; we wrap them in a
    # closure callable so ReplayFork.run signs the audit row + computes
    # divergence as if it had executed the replay itself.
    safe_ctx = _filter_context_override(body.context_override)

    def _replay_callable(_state, *, model_override=None, context_override=None):
        return (body.replay_decisions, body.replay_final)

    result = fork.run(
        _replay_callable,
        model_override=body.model_override,
        context_override=safe_ctx if safe_ctx else None,
    )
    return result.to_dict()


def _audit_path() -> Path:
    """Indirection so tests can monkeypatch the audit log path."""
    return _DEFAULT_AUDIT_PATH


@router.get(
    "/replay/list",
    dependencies=[Depends(requires_role("operator", "owner", "auditor"))],
)
def list_replays(limit: int = 50) -> dict[str, Any]:
    """Tail the replay_fork.jsonl chain. Capped at 1000 entries server-side."""
    import json

    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    path = _audit_path()
    if not path.exists():
        return {"entries": [], "count": 0}

    entries: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = row.get("content")
                if isinstance(content, dict):
                    entries.append(content)
    except OSError as exc:
        log.warning("replay_routes: list read failed (%s)", exc)
        return {"entries": [], "count": 0, "error": str(exc)}

    tail = entries[-limit:]
    return {"entries": tail, "count": len(tail)}
