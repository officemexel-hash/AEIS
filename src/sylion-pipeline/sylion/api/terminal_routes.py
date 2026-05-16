"""SYLION AEIS v2 — REST + SSE routes for W18 Operator Terminal.

Phase 0 endpoints:

    GET  /api/v1/terminal/health
        Smoke check.

    GET  /api/v1/terminal/commands
        Lista wszystkich slash-commands z statusem implementacji.

    POST /api/v1/terminal/exec
        Body: ``{"line": "/status", "ctx": {...}}``. Wykona komende i
        zwroci CommandResult.

    GET  /api/v1/terminal/sessions
        Lista wszystkich sesji (sortowane po updated_at desc).

    POST /api/v1/terminal/sessions
        Body: ``{"title": "...", "tags": [...]}``. Tworzy nową sesje.

    GET  /api/v1/terminal/sessions/{session_id}
        Szczegoly + last_events.

    POST /api/v1/terminal/sessions/{session_id}/tasks
        Body: ``{"title": "..."}``. Dodaje task.

    POST /api/v1/terminal/sessions/{session_id}/close
        Zamyka sesje.

    POST /api/v1/terminal/sessions/{id}/tasks/{tid}/pause     [G2 step 1]
    POST /api/v1/terminal/sessions/{id}/tasks/{tid}/resume    [G2 step 1]
    PATCH /api/v1/terminal/sessions/{id}/tasks/{tid}          [G2 step 1]
    POST /api/v1/terminal/sessions/{id}/tasks/{tid}/skip      [G2 step 1]
    POST /api/v1/terminal/sessions/{id}/cancel                [G2 step 1]
        Operator intervention surface. Pause/resume flip status between
        ``running`` and ``paused``; PATCH /tasks/{id} mutates
        ``title``/``inputs``/``notes`` and is state-machine-aware (only
        allowed while ``paused`` or ``pending``). Skip flips a task to
        ``skipped``. Cancel closes the session and skips every open task.
        All five emit a JSONL audit row to ``logs/v2/intervention_audit.jsonl``
        and a per-task entry to ``TerminalTask.intervention_log``.

    GET  /api/v1/terminal/stream
        text/event-stream — broadcast wszystkich eventów z event_bus
        z opcjonalnym filtrem przez query: ``?layers=W14,W15&hosts=local``.

PDF §7.4 stack: SSE + FastAPI + sylion.core.event_bus subscriber.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sylion.aeis_v2.terminal import (
    BUILTIN_COMMANDS,
    get_session_store,
    list_commands,
)
from sylion.aeis_v2.terminal.command_router import execute_terminal_intent
from sylion.aeis_v2.terminal.replay import (
    MAX_REPLAY_SLICE_SIZE,
    get_replay_slice,
    list_replay_days,
)
from sylion.aeis_v2.terminal.sessions import TerminalSession, TerminalTask
from sylion.aeis_v2.terminal.stream import (
    EventFilter,
    EventSubscriber,
    TerminalEvent,
    get_broadcaster,
)
from sylion.security.rbac import requires_role

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/terminal", tags=["terminal_v2"])

_TERMINAL_SECRET_RE = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://[^\s]+)"
    r"|(?:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    r"|(?:sk-[a-zA-Z0-9_-]+)"
    r"|(?:Bearer\s+[a-zA-Z0-9._-]+)"
    r"|(?:pplx-[a-zA-Z0-9_-]+)"
    r"|(?:sk-or-v1-[a-zA-Z0-9_-]+)",
    re.IGNORECASE,
)


def _redact_terminal_text(text: str) -> str:
    return _TERMINAL_SECRET_RE.sub("<redacted>", str(text or ""))[:500]


# --------------------------------------------------------------------------
# G2 step 1 — intervention audit JSONL
# --------------------------------------------------------------------------
#
# Mirrors the W17 federation routing audit (logs/v2/routing_audit.jsonl) and
# the W15 ontology applier audit (logs/v2/apply_audit.jsonl). One JSON
# object per line, append-only, best-effort write. Disk full / permission
# error logs at WARNING but does NOT block the API response — a paused
# task is more important than a missing audit row, and the per-task
# intervention_log on the TerminalTask itself is a second-line trail.
#
# G2 step 2 will mirror this row to the W11 adapter bus so the running
# agent receives the pause/resume signal in real time. G2 step 3 moves
# the JSONL into a PG audit table once persistence lands; the file
# remains as the DR fallback.
#
# parents[3] resolves: terminal_routes.py -> api -> sylion -> sylion-pipeline/
INTERVENTION_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "intervention_audit.jsonl"
)


def _emit_intervention_audit(
    *,
    session_id: str,
    task_id: str | None,
    action: str,
    actor: str,
    reason: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """Append one structured JSON line per operator intervention.

    Schema (one JSON object per line):
        {ts, session_id, task_id, action, actor, reason, before, after}

    ``task_id`` is ``None`` for session-level actions (e.g. ``cancel``)
    that do not target a single task.

    Failure to write is best-effort: WARNING-level log, no exception
    propagated. The W18 intervention API must complete even when the
    audit infra is down.
    """
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "task_id": task_id,
        "action": action,
        "actor": actor,
        "reason": reason,
        "before": before,
        "after": after,
    }
    try:
        INTERVENTION_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(INTERVENTION_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("intervention_audit: failed to write JSONL (%s)", exc)


def _task_state_snapshot(task: TerminalTask) -> dict[str, Any]:
    """Capture the operator-visible task state for audit before/after rows."""
    return {
        "status": task.status,
        "title": task.title,
        "progress": task.progress,
        "notes": task.notes,
        "inputs": dict(task.inputs),
        "paused_at": task.paused_at,
        "pause_reason": task.pause_reason,
    }


def _record_intervention(
    *,
    session: TerminalSession,
    task: TerminalTask | None,
    action: str,
    actor: str,
    reason: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    """Write intervention to per-task log + global JSONL.

    Belt-and-braces: per-task ``intervention_log`` always gets the entry
    (in-memory, cheap, never fails); JSONL is best-effort. Session-level
    interventions still get logged to the JSONL with ``task_id=None``.
    """
    entry = {
        "ts": time.time(),
        "action": action,
        "actor": actor,
        "reason": reason,
        "before_state": before,
        "after_state": after,
    }
    if task is not None:
        task.intervention_log.append(entry)
    _emit_intervention_audit(
        session_id=session.session_id,
        task_id=task.task_id if task is not None else None,
        action=action,
        actor=actor,
        reason=reason,
        before=before,
        after=after,
    )


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------


class ExecRequest(BaseModel):
    line: str
    ctx: dict[str, Any] | None = None


class CreateSessionRequest(BaseModel):
    title: str
    tags: list[str] | None = None
    operator_id: str = "operator"


class AddTaskRequest(BaseModel):
    title: str
    pipeline_step_id: str | None = None


# --------------------------------------------------------------------------
# G2 step 1 — intervention request models
# --------------------------------------------------------------------------


class PauseRequest(BaseModel):
    reason: str = ""


class ResumeRequest(BaseModel):
    reason: str = ""


class PatchTaskRequest(BaseModel):
    """PATCH /tasks/{id} — operator edit while paused/pending.

    Carries the operator-editable parameter dict ``inputs`` plus
    title/notes; status/progress are NOT operator-editable through this
    route — they flow through the pause/resume/skip state machine.
    """
    title: str | None = None
    inputs: dict[str, Any] | None = None
    notes: str | None = None


class SkipRequest(BaseModel):
    reason: str = ""


class CancelRequest(BaseModel):
    reason: str = ""


# --------------------------------------------------------------------------
# Health + diagnostics
# --------------------------------------------------------------------------


@router.get("/health")
def terminal_health() -> dict[str, Any]:
    """Smoke endpoint."""
    store = get_session_store()
    return {
        "status": "ok",
        "phase": "0",
        "active_sessions": len(store.list_active()),
        "total_sessions": len(store.list_all()),
        "commands_registered": len(BUILTIN_COMMANDS),
        "broadcaster_wired": get_broadcaster()._wired_to_event_bus,  # noqa: SLF001
    }


@router.get("/commands")
def get_commands() -> dict[str, Any]:
    """Lista wszystkich slash-commands."""
    cmds = list_commands()
    return {
        "count": len(cmds),
        "implemented": sum(1 for c in cmds if c["implemented"] == "yes"),
        "commands": cmds,
    }


# --------------------------------------------------------------------------
# Command execution
# --------------------------------------------------------------------------


@router.post("/exec")
def exec_command(req: ExecRequest) -> dict[str, Any]:
    """Wykonaj jedna komende."""
    ctx = req.ctx or {}
    execution = execute_terminal_intent(req.line, ctx)
    result = execution.result
    session_id = str(ctx.get("session_id") or "")
    broadcaster = get_broadcaster()
    line = _redact_terminal_text(req.line)
    result_text = _redact_terminal_text(result.text or f"[{result.kind}]")
    result_severity = "error" if result.kind == "error" else "warn" if result.kind == "not_implemented" else "info"
    safe_extra = {
        key: str(ctx.get(key))[:160]
        for key in (
            "project_id",
            "agent_id",
            "worker_id",
            "role",
            "environment_id",
            "council_session_id",
            "task_id",
            "phase",
            "action",
            "status",
        )
        if ctx.get(key) not in (None, "")
    }
    try:
        broadcaster._offer_without_loop(  # noqa: SLF001 - sync FastAPI route emits to W18 stream/replay.
            TerminalEvent(
                ts=time.time(),
                layer="W18",
                module="operator",
                host="local",
                message=f"$ {line}",
                severity="debug",
                session_id=session_id,
                extra=safe_extra,
            )
        )
        broadcaster._offer_without_loop(  # noqa: SLF001
            TerminalEvent(
                ts=time.time(),
                layer="W18",
                module="terminal",
                host="local",
                message=result_text,
                severity=result_severity,
                session_id=session_id,
                extra=safe_extra,
            )
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("terminal exec: failed to emit W18 event (%s)", exc)
    return execution.to_response()


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


@router.get("/sessions")
def list_sessions() -> dict[str, Any]:
    """Lista wszystkich sesji posortowana po updated_at desc."""
    store = get_session_store()
    return {
        "count": len(store.list_all()),
        "sessions": [s.to_dict() for s in store.list_all()],
    }


@router.post("/sessions")
def create_session(req: CreateSessionRequest) -> dict[str, Any]:
    store = get_session_store()
    sess = store.create(
        title=req.title,
        operator_id=req.operator_id,
        tags=req.tags or [],
    )
    return sess.to_dict()


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    store = get_session_store()
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, f"session '{session_id}' not found")
    out = sess.to_dict()
    out["last_events"] = sess.last_events[-50:]
    return out


@router.post("/sessions/{session_id}/tasks")
def add_task(session_id: str, req: AddTaskRequest) -> dict[str, Any]:
    store = get_session_store()
    if not store.get(session_id):
        raise HTTPException(404, f"session '{session_id}' not found")
    task = store.add_task(session_id, req.title, req.pipeline_step_id)
    if not task:
        raise HTTPException(500, "failed to add task")
    return {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status,
        "progress": task.progress,
        "pipeline_step_id": task.pipeline_step_id,
    }


@router.post("/sessions/{session_id}/close")
def close_session(session_id: str, status: str = "closed") -> dict[str, Any]:
    store = get_session_store()
    ok = store.close(session_id, status)
    if not ok:
        raise HTTPException(404, f"session '{session_id}' not found")
    return {"ok": True, "session_id": session_id, "status": status}


# --------------------------------------------------------------------------
# G2 step 1 — operator intervention API
# --------------------------------------------------------------------------
#
# State machine:
#
#     pending --(start)--> running --(pause)--> paused --(resume)--> running
#         |                  |        |                  |
#         |                  |        +--(patch ok)------+    (only paused/pending)
#         |                  |
#         +--(skip)----------+--(skip)---> skipped
#         |                  |
#         |                  +--(complete)--> done / failed
#
# The pause/resume routes are the operator's pin on a running task; the
# real-time wiring to the agent (i.e. "actually stop processing") lands
# in G2 step 2 via the W11 adapter bus. Step 1 here just moves the
# server-side state and writes the audit trail; the agent continues to
# emit progress via the existing event_bus path.
#
# Auth: every intervention is restricted to the ``operator`` role. The
# RBAC enforcement middleware also covers POST/PATCH globally; the
# Depends(...) here makes the requirement local + visible in OpenAPI.


def _intervention_actor(user_id: str | None) -> str:
    """Normalise the actor string for the audit row.

    ``requires_role`` returns the user_id; in dev mode (RBAC disabled)
    that may be ``"rbac-disabled"`` or ``"anonymous"``. Either way we
    record what we have — the audit row is a trail of *which user
    issued which intervention*, and "operator" or "rbac-disabled" still
    parses cleanly downstream.
    """
    return user_id or "anonymous"


@router.post("/sessions/{session_id}/tasks/{task_id}/pause")
def pause_task(
    session_id: str,
    task_id: str,
    req: PauseRequest,
    user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    """Pause a running task.

    Only ``running`` tasks can be paused. Any other state returns 409
    with a human-readable explanation. On success the task flips to
    ``paused``, ``paused_at`` is set, ``pause_reason`` is recorded, and
    one entry lands in both the per-task ``intervention_log`` and the
    global JSONL audit.
    """
    store = get_session_store()
    pair = store.find_task(session_id, task_id)
    if pair is None:
        raise HTTPException(404, f"task '{task_id}' in session '{session_id}' not found")
    sess, task = pair

    if task.status != "running":
        raise HTTPException(
            409,
            (
                f"cannot pause task in status '{task.status}' — "
                f"only 'running' tasks can be paused"
            ),
        )

    before = _task_state_snapshot(task)
    task.status = "paused"
    task.paused_at = time.time()
    task.pause_reason = req.reason or ""
    sess.updated_at = time.time()
    after = _task_state_snapshot(task)

    _record_intervention(
        session=sess, task=task,
        action="pause",
        actor=_intervention_actor(user),
        reason=req.reason or "",
        before=before, after=after,
    )

    return {
        "ok": True,
        "session_id": session_id,
        "task_id": task_id,
        "task": after,
    }


@router.post("/sessions/{session_id}/tasks/{task_id}/resume")
def resume_task(
    session_id: str,
    task_id: str,
    req: ResumeRequest,
    user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    """Resume a paused task.

    Only ``paused`` tasks can be resumed. Any other state returns 409.
    On success the task flips back to ``running``, ``paused_at`` is
    cleared, ``pause_reason`` is reset, and the intervention is logged.
    """
    store = get_session_store()
    pair = store.find_task(session_id, task_id)
    if pair is None:
        raise HTTPException(404, f"task '{task_id}' in session '{session_id}' not found")
    sess, task = pair

    if task.status != "paused":
        raise HTTPException(
            409,
            (
                f"cannot resume task in status '{task.status}' — "
                f"only 'paused' tasks can be resumed"
            ),
        )

    before = _task_state_snapshot(task)
    task.status = "running"
    task.paused_at = None
    task.pause_reason = ""
    if task.started_at is None:
        # Edge: a task that was added then directly paused before any
        # state machine drove it through ``running`` would have no
        # started_at. Set it now so progress reports have a baseline.
        task.started_at = time.time()
    sess.updated_at = time.time()
    after = _task_state_snapshot(task)

    _record_intervention(
        session=sess, task=task,
        action="resume",
        actor=_intervention_actor(user),
        reason=req.reason or "",
        before=before, after=after,
    )

    return {
        "ok": True,
        "session_id": session_id,
        "task_id": task_id,
        "task": after,
    }


@router.patch("/sessions/{session_id}/tasks/{task_id}")
def patch_task(
    session_id: str,
    task_id: str,
    req: PatchTaskRequest,
    user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    """Edit a task's prompt/inputs/notes/title while paused or pending.

    The operator's mid-flight edit hatch. Allowed only when the task
    has not yet started or has been explicitly paused — editing a live
    ``running`` task would race with the agent. ``done``/``failed``/
    ``skipped`` are terminal: edits there return 409.

    Partial updates: any subset of ``title``, ``inputs``, ``notes`` may
    be supplied; missing keys leave the existing value alone. ``inputs``
    REPLACES the whole dict (not a merge) so the operator can clear a
    bad parameter by omitting it.
    """
    store = get_session_store()
    pair = store.find_task(session_id, task_id)
    if pair is None:
        raise HTTPException(404, f"task '{task_id}' in session '{session_id}' not found")
    sess, task = pair

    if task.status not in {"paused", "pending"}:
        raise HTTPException(
            409,
            (
                f"cannot patch task in status '{task.status}' — "
                f"edits are only allowed in 'paused' or 'pending'"
            ),
        )

    before = _task_state_snapshot(task)
    diff: dict[str, Any] = {}
    if req.title is not None and req.title != task.title:
        diff["title"] = {"from": task.title, "to": req.title}
        task.title = req.title
    if req.inputs is not None and dict(req.inputs) != dict(task.inputs):
        diff["inputs"] = {"from": dict(task.inputs), "to": dict(req.inputs)}
        task.inputs = dict(req.inputs)
    if req.notes is not None and req.notes != task.notes:
        diff["notes"] = {"from": task.notes, "to": req.notes}
        task.notes = req.notes
    sess.updated_at = time.time()
    after = _task_state_snapshot(task)

    # The before snapshot in the audit row carries the diff explicitly
    # so an auditor reading a single row can answer "what changed" without
    # diffing two snapshots themselves.
    before_for_audit = dict(before)
    before_for_audit["_diff"] = diff

    _record_intervention(
        session=sess, task=task,
        action="patch",
        actor=_intervention_actor(user),
        reason="",
        before=before_for_audit, after=after,
    )

    return {
        "ok": True,
        "session_id": session_id,
        "task_id": task_id,
        "task": after,
        "diff": diff,
    }


@router.post("/sessions/{session_id}/tasks/{task_id}/skip")
def skip_task(
    session_id: str,
    task_id: str,
    req: SkipRequest,
    user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    """Skip a stuck or unwanted task.

    Skip is allowed from any non-terminal state. ``done`` returns 409 —
    skipping a completed task would be misleading in audit. ``skipped``
    and ``failed`` also return 409 (already terminal).
    """
    store = get_session_store()
    pair = store.find_task(session_id, task_id)
    if pair is None:
        raise HTTPException(404, f"task '{task_id}' in session '{session_id}' not found")
    sess, task = pair

    if task.status in {"done", "failed", "skipped"}:
        raise HTTPException(
            409,
            (
                f"cannot skip task in terminal status '{task.status}'"
            ),
        )

    before = _task_state_snapshot(task)
    task.status = "skipped"
    if task.finished_at is None:
        task.finished_at = time.time()
    # Preserve paused_at if the task was paused-then-skipped; the audit
    # row carries enough context that we don't need to scrub it.
    sess.updated_at = time.time()
    after = _task_state_snapshot(task)

    _record_intervention(
        session=sess, task=task,
        action="skip",
        actor=_intervention_actor(user),
        reason=req.reason or "",
        before=before, after=after,
    )

    return {
        "ok": True,
        "session_id": session_id,
        "task_id": task_id,
        "task": after,
    }


@router.post("/sessions/{session_id}/cancel")
def cancel_session(
    session_id: str,
    req: CancelRequest,
    user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    """Cancel an entire session.

    Closes the session (status -> ``closed``) and forces every still-open
    task (``pending`` / ``running`` / ``paused``) to ``skipped``. Emits
    one audit row per skipped task plus one session-level row recording
    the cancel itself. Idempotent in the trivial sense: cancelling an
    already-closed session is a no-op (returns 200 with skipped_count=0).
    """
    store = get_session_store()
    sess = store.get(session_id)
    if not sess:
        raise HTTPException(404, f"session '{session_id}' not found")

    actor = _intervention_actor(user)
    reason = req.reason or ""
    open_states = {"pending", "running", "paused"}

    skipped_task_ids: list[str] = []
    # Snapshot session state for audit. We capture status before we
    # mutate anything so the audit row reflects the operator's view.
    session_before = {
        "status": sess.status,
        "task_count": len(sess.tasks),
        "open_task_count": sum(1 for t in sess.tasks if t.status in open_states),
    }

    for task in list(sess.tasks):
        if task.status in open_states:
            t_before = _task_state_snapshot(task)
            task.status = "skipped"
            if task.finished_at is None:
                task.finished_at = time.time()
            t_after = _task_state_snapshot(task)
            _record_intervention(
                session=sess, task=task,
                action="skip",
                actor=actor,
                reason=f"session cancelled: {reason}".strip(": ").strip(),
                before=t_before, after=t_after,
            )
            skipped_task_ids.append(task.task_id)

    # Close the session itself.
    sess.status = "closed"
    sess.updated_at = time.time()
    session_after = {
        "status": sess.status,
        "task_count": len(sess.tasks),
        "open_task_count": 0,
    }

    _record_intervention(
        session=sess, task=None,
        action="cancel",
        actor=actor,
        reason=reason,
        before=session_before, after=session_after,
    )

    return {
        "ok": True,
        "session_id": session_id,
        "status": sess.status,
        "skipped_count": len(skipped_task_ids),
        "skipped_task_ids": skipped_task_ids,
    }


# --------------------------------------------------------------------------
# SSE stream
# --------------------------------------------------------------------------


@router.get("/stream")
async def stream_events(
    request: Request,
    layers: str = Query("", description="comma-separated layer prefixes"),
    hosts: str = Query("", description="comma-separated host names"),
    models: str = Query("", description="comma-separated model ids"),
    severities: str = Query("", description="comma-separated severities"),
    sessions: str = Query("", description="comma-separated session ids"),
) -> StreamingResponse:
    """SSE stream of terminal events.

    Klient (xterm.js + custom React) podlacza się przez `EventSource`.
    Backend lazy-podpina się do ``sylion.core.event_bus`` przy
    pierwszym kliencie. Heartbeat co 15s żeby proxie nie ubiły TCP.
    """
    broadcaster = get_broadcaster()
    broadcaster.wire_to_event_bus()

    def _csv_set(s: str) -> set[str]:
        return {x.strip() for x in s.split(",") if x.strip()}

    filt = EventFilter(
        layers=_csv_set(layers),
        hosts=_csv_set(hosts),
        models=_csv_set(models),
        severities=_csv_set(severities),
        sessions=_csv_set(sessions),
    )
    sub = EventSubscriber(sub_id=uuid.uuid4().hex[:8], filt=filt)
    await broadcaster.add(sub)

    # Powitalna linia: pomaga klientowi potwierdzić że rzeczywiście otrzymuje stream.
    welcome = TerminalEvent(
        ts=time.time(),
        layer="W18",
        module="terminal.stream",
        message=(
            f"Subscribed sub_id={sub.sub_id}. "
            f"Filters: layers={sorted(filt.layers) or 'all'}, "
            f"hosts={sorted(filt.hosts) or 'all'}, "
            f"models={sorted(filt.models) or 'all'}, "
            f"severities={sorted(filt.severities) or 'all'}, "
            f"sessions={sorted(filt.sessions) or 'all'}."
        ),
        severity="info",
    )
    sub.offer(welcome)

    async def gen():
        # Kimi review fix: use the asyncio loop's monotonic clock for
        # heartbeat scheduling. Previously we mixed time.time() (system
        # clock) with asyncio.wait_for (which uses loop.time() under
        # the hood). If the wall clock jumped backward (NTP step,
        # daylight savings on a poorly-configured host), the computed
        # `timeout = heartbeat_at - time.time()` could become hours
        # long — the SSE stream would hang and the operator would see
        # nothing. Monotonic time is immune to wall-clock jumps.
        #
        # KIMI review finding #2 (memory leak): every successful yield
        # below calls ``sub.touch()`` so TerminalBroadcaster.reap_stale
        # can reliably distinguish a live-but-quiet client from a dead
        # one. Without touch(), a long quiet stretch would let the
        # reaper evict an active operator.
        loop = asyncio.get_event_loop()
        try:
            heartbeat_at = loop.time() + 15.0
            while True:
                if await request.is_disconnected():
                    break
                # Wait for next event with timeout so we can still send heartbeats.
                try:
                    timeout = max(0.5, min(30.0, heartbeat_at - loop.time()))
                    evt = await asyncio.wait_for(sub._queue.get(), timeout=timeout)  # noqa: SLF001
                    yield evt.to_sse_payload()
                    sub.touch()
                except asyncio.TimeoutError:
                    pass
                # Heartbeat (SSE comment) — keeps proxies happy without polluting client.
                if loop.time() >= heartbeat_at:
                    yield ": heartbeat\n\n"
                    sub.touch()
                    heartbeat_at = loop.time() + 15.0
        finally:
            await broadcaster.remove(sub)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# --------------------------------------------------------------------------
# Test injection (Phase 0 dev convenience)
# --------------------------------------------------------------------------


class InjectEventRequest(BaseModel):
    layer: str = "W18"
    module: str = "terminal.test"
    message: str
    model: str = ""
    host: str = "local"
    severity: str = "info"
    session_id: str = ""
    extra: dict[str, Any] | None = None


@router.post("/_dev/inject_event")
async def inject_event(req: InjectEventRequest) -> dict[str, Any]:
    """Wstrzyknij syntetyczny event do broadcaster — uzywane przez QA i
    w trakcie developmentu. NIE jest exposed jako stable API; w prod
    wylaczone przez RBAC enforcement (POST blocked w SYLION_AUTH_MODE=strict).
    """
    evt = TerminalEvent(
        ts=time.time(),
        layer=req.layer,
        module=req.module,
        message=req.message,
        model=req.model,
        host=req.host,
        severity=req.severity,
        session_id=req.session_id,
        extra=req.extra or {},
    )
    await get_broadcaster().offer(evt)
    return {"ok": True, "event_id": evt.event_id, "ts": evt.ts}


# --------------------------------------------------------------------------
# G3 step 1 — replay-as-film backend
# --------------------------------------------------------------------------
#
# Phase 0 deliverable: server-side recording happens in
# ``TerminalBroadcaster.offer`` (best-effort append to a daily JSONL).
# These two endpoints expose the read side:
#
#   GET /replay/slice  — fetch ordered events in [start_ts, end_ts]
#                        with optional session_id / layer filters.
#   GET /replay/days   — enumerate which dates have replay logs at all.
#
# G3 step 2 will add a ``GET /replay/stream`` SSE endpoint that paces
# the slice at 1x/2x/4x/8x for the operator's "rewind to incident"
# experience. Keeping the slice query separate from the streaming side
# means the operator UI can pre-fetch a count + bounds before deciding
# whether to play it back.
#
# Auth: operator role only. Replay logs may carry session ids, model
# names, and message bodies that are sensitive enough to warrant the
# same gate as the live SSE stream.


@router.get("/replay/slice")
def replay_slice(
    start_ts: float = Query(..., description="UTC epoch start (inclusive)"),
    end_ts: float = Query(..., description="UTC epoch end (inclusive)"),
    session_id: str = Query("", description="optional session_id filter"),
    layer: str = Query("", description="optional layer filter (e.g. W15)"),
    max_events: int = Query(
        1000,
        ge=1,
        le=MAX_REPLAY_SLICE_SIZE,
        description=f"max rows returned, capped at {MAX_REPLAY_SLICE_SIZE}",
    ),
    user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    """Return a recorded slice of TerminalEvents.

    The returned dict matches ``ReplaySlice.to_dict()``: events list +
    bounds + truncation flag + applied filters. Empty session_id /
    layer query params are treated as "no filter" -- the route does the
    empty-string-to-None coercion so the URL stays clean (``?layer=``
    works just like omitting the param).

    The endpoint NEVER raises on a quiet window: a query for a range
    with no matching log files returns ``events=[]`` with
    ``truncated=False`` and ``total_count=0``.
    """
    if end_ts < start_ts:
        raise HTTPException(
            400, f"end_ts ({end_ts}) must be >= start_ts ({start_ts})",
        )
    sid = session_id or None
    lay = layer or None
    slice_ = get_replay_slice(
        start_ts=start_ts,
        end_ts=end_ts,
        session_id=sid,
        layer=lay,
        max_events=max_events,
    )
    return slice_.to_dict()


@router.get("/replay/days")
def replay_days(
    user: str = Depends(requires_role("operator")),
) -> dict[str, Any]:
    """Enumerate dates with at least one recorded event.

    Returns ``{"count": N, "days": ["YYYY-MM-DD", ...]}`` sorted
    descending so the most recent day is first -- matches the operator
    UI's date-picker convention (recent at top).
    """
    days = list_replay_days()
    return {"count": len(days), "days": days}
