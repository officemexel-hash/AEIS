"""W18 Terminal — session model.

PDF §7.2: "Session Threading — każde 'co robisz' to session z
id/title/tasks/progress, wiele równolegle."

Każda sesja terminala to logiczna jednostka pracy operatora. W jednej
sesji może być wiele kroków/tasków, sesje mogą być prowadzone równolegle,
zachowywane (replay) i porównywane (`/diff`).

Phase 0: in-memory store. Phase G2 dodaje persystencję przez W15 OSDK.

KIMI W18 sessions review — memory hygiene
-----------------------------------------

Mirrors the dead-subscriber reaper that landed for ``stream.py`` (commit
``1f740888``) and applies the same lifecycle hygiene to the session
store. Three classes of leak that Phase 0 had to close before G2:

1. **Unbounded session count** — operator (or buggy frontend) could
   create unlimited sessions, RAM growing without ceiling. We cap the
   number of *active* sessions at ``MAX_ACTIVE_SESSIONS``; when a new
   session would push us past the cap we auto-archive the oldest active
   one (by ``created_at``) before creating the new entry.
2. **No idle timeout** — abandoned sessions stayed ``status="active"``
   forever. ``SessionStore.reap_idle()`` archives any active session
   whose ``updated_at`` is older than ``SESSION_IDLE_TIMEOUT_S``.
   Fired opportunistically inside :meth:`SessionStore.create`, throttled
   to once per ``SESSION_REAP_INTERVAL_S`` so the create hot-path stays
   cheap.
3. **No archive prune** — closed/archived sessions accumulated. The same
   ``reap_idle()`` pass also hard-deletes anything in
   ``status="archived"`` whose ``updated_at`` is older than
   ``SESSION_HARD_DELETE_AFTER_ARCHIVE_S``. That bounds total store
   size: at steady state the store holds at most
   ``MAX_ACTIVE_SESSIONS`` active rows plus 24 hours of archived rows.

Phase 0 caps are conservative because the store is in-memory and bounded
by single-process RAM. G2 with PG persistence will lift
``MAX_ACTIVE_SESSIONS`` to ~10k and move the reaper to a scheduled job;
the cap exists today purely to protect against operator-side bugs that
would otherwise leak sessions into RAM until OOM.
"""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Memory hygiene knobs (KIMI W18 sessions review)
# --------------------------------------------------------------------------
#
# Phase 0 in-memory store. G2 with PG persistence will lift the cap to
# ~10k. The cap protects against operator-side bugs creating unbounded
# sessions — without it a buggy frontend looping ``POST /sessions`` would
# OOM the backend in seconds.
def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("sessions: invalid %s=%r, falling back to %d", name, raw, default)
        return default


MAX_ACTIVE_SESSIONS: int = _env_int("SYLION_MAX_ACTIVE_SESSIONS", 100)
# Active session whose ``updated_at`` is older than this (seconds) is
# auto-archived by ``reap_idle``. 1 hour matches the SSE TTL ratio
# (sessions live longer than transient SSE subs).
SESSION_IDLE_TIMEOUT_S: float = 3600.0
# Throttle for opportunistic reap_idle invocations. Mirrors stream.py
# `_REAP_INTERVAL_S=30.0` shape but is wider (60s) because session
# lifecycle is slower than SSE event flow.
SESSION_REAP_INTERVAL_S: float = 60.0
# Hard-delete cutoff for archived sessions. After 24h in archive, a
# session is removed from the store entirely — caps the steady-state
# store size to ``MAX_ACTIVE_SESSIONS`` + 24h of archived rows.
SESSION_HARD_DELETE_AFTER_ARCHIVE_S: float = 86400.0


@dataclass
class TerminalTask:
    """Pojedyncze zadanie wewnątrz sesji.

    Mapuje 1:1 na step W6 Execution Pipeline gdy sesja prowadzi pipeline,
    ale może też istnieć standalone (free-form todo).

    G2 step 1 — operator intervention surface
    -----------------------------------------
    Status enum extended to include ``paused``: an operator-issued pause
    flips ``running -> paused``; resume flips ``paused -> running``. The
    ``inputs`` dict carries operator-editable parameters that can be
    mutated mid-flight (only while ``paused`` or ``pending``).
    ``intervention_log`` is the per-task audit trail; every pause/resume/
    patch/skip writes one entry there in addition to the global JSONL log
    in ``logs/v2/intervention_audit.jsonl``.
    """

    task_id: str
    title: str
    # pending / running / paused / done / failed / skipped
    status: str = "pending"
    progress: float = 0.0             # 0..1
    started_at: float | None = None
    finished_at: float | None = None
    notes: str = ""
    pipeline_step_id: str | None = None    # bind to W6 if applicable

    # ------------------------------------------------------------------
    # G2 step 1 — intervention API fields
    # ------------------------------------------------------------------
    # Operator-editable parameters. PATCH /tasks/{id} can mutate this
    # while task is paused/pending. G2 step 2 will plumb edits to the
    # running agent through the W11 adapter bus.
    inputs: dict[str, Any] = field(default_factory=dict)
    # Wall-clock timestamp of the most recent pause. Reset to None on
    # resume so a paused-then-resumed-then-paused task only carries the
    # current pause's timestamp.
    paused_at: float | None = None
    # Operator-supplied reason string for the most recent pause.
    pause_reason: str = ""
    # Per-task audit trail. Each entry is a dict with keys:
    # {ts, action, actor, reason, before_state, after_state}.
    # Append-only; the API never reads back from here for control flow,
    # so corruption here cannot break pause/resume semantics.
    intervention_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TerminalSession:
    """Single threaded view of operator activity.

    PDF §7.2 wzorzec dump:

        14:32:01  W15·OntologyMigrator  qwen2.5:72b@laptop      Reading manifest customer.yaml ✓

    Każda taka linia może (ale nie musi) należeć do session — sesje są
    grupą logiczną, nie filtrem broadcastu.
    """

    session_id: str
    title: str
    created_at: float
    updated_at: float
    status: str = "active"            # active / paused / closed / archived
    operator_id: str = "operator"
    tasks: list[TerminalTask] = field(default_factory=list)
    # Wskaźnik aktualnie wykonywanego taska. Niezdefiniowany gdy lista pusta.
    current_task_idx: int | None = None
    # Wolne tagi do filtrowania w `/focus`.
    tags: list[str] = field(default_factory=list)
    # Snapshot ostatnich N event linii dla quick replay.
    last_events: list[dict[str, Any]] = field(default_factory=list)
    # Hash ostatniej linii dla replay-as-film integrity check (G2).
    last_hash: str = ""

    def progress_pct(self) -> int:
        """Średni progress wszystkich tasków, 0-100."""
        if not self.tasks:
            return 0
        total = sum(t.progress for t in self.tasks)
        return int(round((total / len(self.tasks)) * 100))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "operator_id": self.operator_id,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "status": t.status,
                    "progress": t.progress,
                    "started_at": t.started_at,
                    "finished_at": t.finished_at,
                    "notes": t.notes,
                    "pipeline_step_id": t.pipeline_step_id,
                    # G2 step 1 — intervention API fields. Always present
                    # in the wire shape so the frontend can render the
                    # pause/resume controls without an undefined check.
                    "inputs": dict(t.inputs),
                    "paused_at": t.paused_at,
                    "pause_reason": t.pause_reason,
                    "intervention_log": list(t.intervention_log),
                }
                for t in self.tasks
            ],
            "current_task_idx": self.current_task_idx,
            "progress_pct": self.progress_pct(),
            "tags": list(self.tags),
        }


class SessionStore:
    """Thread-safe in-process store for active sessions.

    Phase 0: dict in memory. Phase G2: persist via W15 OSDK on a
    `terminal_session` ontology type so sessions survive restarts and
    replay log can be hash-chained.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, TerminalSession] = {}
        # KIMI W18 sessions review — rate-limit reap_idle so the create
        # hot-path stays O(1) amortised. Initialised to 0.0 so the first
        # create() in a fresh process triggers a reap (cheap with empty
        # store).
        self._last_reap_at: float = 0.0

    def create(self, title: str, operator_id: str = "operator", tags: list[str] | None = None) -> TerminalSession:
        # Run hygiene before creation: archive idle, hard-delete old
        # archived. Throttled so a tight burst of creates does not pay
        # the O(n) scan on every call.
        self._maybe_reap()
        # Enforce the active-session cap. If we are already at the cap
        # with no idle entries, archive the oldest active session by
        # ``created_at`` — a deterministic eviction policy that is easy
        # for an operator to reason about.
        with self._lock:
            active = [s for s in self._sessions.values() if s.status == "active"]
            if len(active) >= MAX_ACTIVE_SESSIONS:
                oldest = min(active, key=lambda s: s.created_at)
                oldest.status = "archived"
                oldest.updated_at = time.time()
                log.warning(
                    "sessions: active cap reached (%d) — auto-archived oldest session_id=%s title=%r",
                    MAX_ACTIVE_SESSIONS, oldest.session_id, oldest.title,
                )

        sess = TerminalSession(
            session_id=uuid.uuid4().hex[:12],
            title=title,
            created_at=time.time(),
            updated_at=time.time(),
            operator_id=operator_id,
            tags=list(tags or []),
        )
        with self._lock:
            self._sessions[sess.session_id] = sess
        return sess

    def get(self, session_id: str) -> TerminalSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_active(self) -> list[TerminalSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.status == "active"]

    def list_all(self) -> list[TerminalSession]:
        with self._lock:
            return sorted(
                self._sessions.values(),
                key=lambda s: s.updated_at,
                reverse=True,
            )

    def add_task(
        self,
        session_id: str,
        title: str,
        pipeline_step_id: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> TerminalTask | None:
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return None
            task = TerminalTask(
                task_id=uuid.uuid4().hex[:8],
                title=title,
                pipeline_step_id=pipeline_step_id,
                inputs=dict(inputs or {}),
            )
            sess.tasks.append(task)
            if sess.current_task_idx is None:
                sess.current_task_idx = 0
            sess.updated_at = time.time()
            return task

    def update_task(self, session_id: str, task_id: str,
                    status: str | None = None,
                    progress: float | None = None,
                    notes: str | None = None) -> bool:
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return False
            for t in sess.tasks:
                if t.task_id == task_id:
                    if status is not None:
                        t.status = status
                        if status == "running" and t.started_at is None:
                            t.started_at = time.time()
                        if status in {"done", "failed", "skipped"} and t.finished_at is None:
                            t.finished_at = time.time()
                    if progress is not None:
                        t.progress = max(0.0, min(1.0, progress))
                    if notes is not None:
                        t.notes = notes
                    sess.updated_at = time.time()
                    return True
            return False

    def find_task(
        self, session_id: str, task_id: str,
    ) -> tuple[TerminalSession, TerminalTask] | None:
        """Locate a (session, task) pair under the store lock.

        Returns ``None`` if either the session or the task is missing.
        Used by the W18 G2 intervention routes that need transactional
        access to both the session (to bump ``updated_at``) and the task
        (to mutate state + append an intervention_log entry).
        """
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return None
            for t in sess.tasks:
                if t.task_id == task_id:
                    return sess, t
            return None

    def close(self, session_id: str, status: str = "closed") -> bool:
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return False
            sess.status = status
            sess.updated_at = time.time()
            return True

    def append_event(self, session_id: str, event: dict[str, Any], cap: int = 200) -> bool:
        """Append a streaming event to the session's recent buffer.

        ``cap`` keeps memory bounded. For full audit log + replay use
        the global ``replay.py`` (G2). Phase 0 just keeps last N for
        quick UI fetch.
        """
        with self._lock:
            sess = self._sessions.get(session_id)
            if not sess:
                return False
            sess.last_events.append(event)
            if len(sess.last_events) > cap:
                # Drop oldest 25% so we don't trim every append.
                drop = len(sess.last_events) - int(cap * 0.75)
                sess.last_events = sess.last_events[drop:]
            sess.updated_at = time.time()
            return True

    def reap_idle(self) -> tuple[int, int]:
        """Sweep idle/archived sessions; return ``(archived, deleted)``.

        Two passes under the same lock acquisition:

        1. **Auto-archive idle actives**: any session with
           ``status == "active"`` whose ``updated_at`` is older than
           ``SESSION_IDLE_TIMEOUT_S`` is flipped to ``status="archived"``.
           ``updated_at`` is bumped to ``now`` so the archived row gets
           the full ``SESSION_HARD_DELETE_AFTER_ARCHIVE_S`` grace before
           hard delete.
        2. **Hard-delete stale archives**: any session with
           ``status == "archived"`` whose ``updated_at`` is older than
           ``SESSION_HARD_DELETE_AFTER_ARCHIVE_S`` is dropped from
           ``self._sessions`` entirely.

        Returns the per-pass counts as ``(archived, deleted)``. Safe to
        call from the create() hot-path — :meth:`_maybe_reap` rate-limits
        invocations to roughly one per ``SESSION_REAP_INTERVAL_S`` so the
        scan cost stays bounded.
        """
        now = time.time()
        archived = 0
        deleted = 0
        with self._lock:
            # Pass 1: archive idle actives. Iterate over a snapshot of
            # values so we never mutate the dict mid-iteration.
            for s in list(self._sessions.values()):
                if (
                    s.status == "active"
                    and (now - s.updated_at) > SESSION_IDLE_TIMEOUT_S
                ):
                    s.status = "archived"
                    s.updated_at = now
                    archived += 1
            # Pass 2: hard-delete stale archives. We compute the stale
            # set against the (possibly updated) ``updated_at`` from
            # pass 1, but pass-1 just bumped them to ``now`` so they
            # cannot be picked up here in the same sweep — the bump is
            # intentional: a freshly-archived session gets a full TTL
            # before deletion.
            stale_ids = [
                sid for sid, s in self._sessions.items()
                if (
                    s.status == "archived"
                    and (now - s.updated_at) > SESSION_HARD_DELETE_AFTER_ARCHIVE_S
                )
            ]
            for sid in stale_ids:
                del self._sessions[sid]
                deleted += 1
        if archived:
            log.info("sessions: archived %d idle sessions", archived)
        if deleted:
            log.info("sessions: hard-deleted %d stale archived sessions", deleted)
        return archived, deleted

    def _maybe_reap(self) -> None:
        """Throttled wrapper around :meth:`reap_idle`.

        The create() hot-path calls this every time. To keep the scan
        amortised cheap we only actually run reap_idle when more than
        ``SESSION_REAP_INTERVAL_S`` seconds have elapsed since the last
        invocation. We deliberately read/write ``_last_reap_at`` without
        the lock — the worst case is two threads racing and both
        triggering a reap, which is harmless (reap is idempotent and the
        inner pass takes the lock anyway).
        """
        now = time.time()
        if (now - self._last_reap_at) > SESSION_REAP_INTERVAL_S:
            self._last_reap_at = now
            self.reap_idle()


# Process singleton.
_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
