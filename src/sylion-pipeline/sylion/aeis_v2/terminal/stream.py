"""W18 Terminal — SSE event aggregator.

PDF §7.2 wzorzec:

    14:32:01  W15·OntologyMigrator  qwen2.5:72b@laptop      Reading manifest customer.yaml ✓

PDF §7.5 ryzyko: SSE scaling przy 20 hostów × 5 modeli × 10 actions/sec
= 1000 eventów/sec → mitigation: subscription model + filtrowanie na backend.

Phase 0 implementacja:

- ``TerminalEvent`` — kanoniczny shape eventu który backend wysyła do
  klienta SSE.
- ``EventSubscriber`` — kolejka per-klient z filtrowaniem.
- ``broadcaster`` — singleton: subscribuje sylion.core.event_bus
  wildcard, fan-outuje do każdego subscriber'a, drop-em-stale gdy
  klient nie nadąża.

Każdy klient SSE łączy się przez ``GET /api/v1/terminal/stream`` —
serwer zwraca strumień ``text/event-stream`` z każdym eventem jako
JSON. Klient (xterm.js + custom React) renderuje linie zgodnie z
formatem PDF §7.2.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, AsyncIterator

log = logging.getLogger(__name__)


# Maksymalna liczba eventów w buforze per klient zanim zaczynamy upuszczać
# najstarsze. PDF §7.5: filtrowanie na backend ogranicza obciążenie, ale
# slow client nie może zatrzymać całego dispatcha.
_QUEUE_MAX = 500


# KIMI W18 SSE review — finding #2 (memory leak / dead-subscriber accrual).
#
# If a client never reconnects (or `is_disconnected()` returns False
# pathologically), its EventSubscriber stays in TerminalBroadcaster._subs
# forever and every offer iterates over it. With 1000 events/sec and dead
# subs accumulating, CPU usage grows unbounded. The reaper below evicts
# any subscriber that has not been touched (yielded-to) for longer than
# STALE_SUBSCRIBER_TTL_S. We rate-limit the reaper to once per
# _REAP_INTERVAL_S so the offer hot-path stays O(n).
#
# A subscriber is considered dead if its ``last_seen_at`` is older than
# STALE_SUBSCRIBER_TTL_S. ``last_seen_at`` is bumped exclusively by the
# route handler via :meth:`EventSubscriber.touch` after each successful
# yield to the client (data line or heartbeat). Offer-side events bump
# ``last_event_at`` only — that timestamp tracks "the broadcaster tried
# to deliver" but does NOT prove the client received bytes. A heartbeat
# fires every 15s in the route, so a healthy subscriber will see at
# most ~15s of last_seen_at lag — well inside the 120s TTL.
STALE_SUBSCRIBER_TTL_S = 120.0
_REAP_INTERVAL_S = 30.0


# W18 G3 step 1 — replay-as-film recording flag.
#
# Every successful broadcast also appends the event to a daily JSONL log
# in ``logs/v2/terminal_replay/``. Production may flip this to False if
# the replay log volume is filling up faster than rotation can drain;
# the broadcast itself never depends on the recording side-effect.
BROADCAST_RECORDS_REPLAY: bool = True


@dataclass
class TerminalEvent:
    """Single line in the activity stream.

    Wszystkie pola opcjonalne poza ``ts``, ``layer``, ``message`` —
    pozwala adapterom emitować częściowe eventy gdy nie znają wszystkich
    pól (np. event ze starego v1 modułu).
    """

    ts: float                          # epoch seconds, server time
    layer: str                         # W7 / W11 / W15 / etc.
    message: str
    module: str = ""                   # canonical module path
    model: str = ""                    # if action involved a model
    host: str = "local"                # node identifier
    severity: str = "info"             # debug / info / warn / error / hg
    session_id: str = ""               # bind to TerminalSession if applicable
    cost_usd: float = 0.0              # incremental cost on this line
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    extra: dict[str, Any] = field(default_factory=dict)

    def to_sse_payload(self) -> str:
        """Render as SSE ``data: <json>`` payload (newline-terminated)."""
        return "data: " + json.dumps(asdict(self), ensure_ascii=False) + "\n\n"

    def matches_filter(self, f: "EventFilter") -> bool:
        if f.layers and self.layer not in f.layers:
            return False
        if f.hosts and self.host not in f.hosts:
            return False
        if f.models and self.model and self.model not in f.models:
            return False
        if f.severities and self.severity not in f.severities:
            return False
        if f.sessions and self.session_id not in f.sessions:
            return False
        return True


@dataclass
class EventFilter:
    """Server-side filter for SSE clients.

    PDF §7.2 "Filters & Focus" — operator może zawęzić do konkretnego
    layer'a / hosta / modelu / severity.
    """
    layers: set[str] = field(default_factory=set)
    hosts: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    severities: set[str] = field(default_factory=set)
    sessions: set[str] = field(default_factory=set)


class EventSubscriber:
    """Per-client subscription queue.

    Tracks two distinct liveness timestamps for the dead-subscriber reaper
    (KIMI review finding #2):

    - ``last_event_at`` — wall-clock time when an event was last offered
      to this subscriber (matched the filter). Bumped on both successful
      enqueue and overflow drop, because a drop still means "the client is
      alive but slow", not "the client is gone".
    - ``last_seen_at`` — wall-clock time when the route handler last
      successfully ``yield``-ed a payload (data or heartbeat) to the
      client. Bumped via :meth:`touch`. This is the authoritative
      liveness signal for the reaper. Initialized to creation time so
      a brand-new subscriber is never reaped before its first event.
    """

    def __init__(self, sub_id: str, filt: EventFilter | None = None):
        self.sub_id = sub_id
        self.filter = filt or EventFilter()
        self._queue: asyncio.Queue[TerminalEvent] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self.created_at = time.time()
        self.last_event_ts: float = 0.0
        self.last_event_at: float = self.created_at
        self.last_seen_at: float = self.created_at
        self.dropped: int = 0

    def touch(self) -> None:
        """Mark the subscriber as live.

        Called by the route handler after every successful yield (data
        line or heartbeat). This is the primary signal that prevents
        :meth:`TerminalBroadcaster.reap_stale` from evicting an active
        subscriber that just happens to be in a quiet stretch.
        """
        self.last_seen_at = time.time()

    def offer(self, event: TerminalEvent) -> None:
        """Try to enqueue an event. Drop on overflow with a counter bump.

        Updates ``last_event_at`` regardless of overflow status — a slow
        client that's dropping events is still alive enough that we
        shouldn't reap it from the offer side; only a fully-quiet
        subscriber should be considered dead.

        We deliberately do NOT bump ``last_seen_at`` here. Offer-time
        events don't prove the client received bytes — the queue could
        be filling up while the route handler is wedged. The
        authoritative liveness signal is :meth:`touch`, which the route
        handler calls after each successful ``yield``. If the route
        handler is dead, ``last_seen_at`` ages out and the reaper
        evicts this subscriber even though offers keep coming.
        """
        if not event.matches_filter(self.filter):
            return
        try:
            self._queue.put_nowait(event)
            self.last_event_ts = event.ts
        except asyncio.QueueFull:
            self.dropped += 1
        # Bump only last_event_at — see docstring above for why
        # last_seen_at is NOT updated here.
        self.last_event_at = time.time()

    async def stream(self) -> AsyncIterator[TerminalEvent]:
        """Async iterator that yields events as they arrive."""
        while True:
            evt = await self._queue.get()
            yield evt


class TerminalBroadcaster:
    """Singleton router subscribing to the event bus and fanning out to subs.

    Phase 0: simple list, every offer iterates all subscribers (O(n)).
    For >100 concurrent subscribers replace with topic-tree dispatch.
    """

    def __init__(self) -> None:
        self._subs: list[EventSubscriber] = []
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._wired_to_event_bus: bool = False
        # KIMI review #2 — rate-limit the reaper so the offer hot-path
        # remains O(n) instead of O(n²). Initialised to 0 so the first
        # offer in a fresh process triggers a reap (cheap with 0 subs).
        self._last_reap_at: float = 0.0

    async def add(self, sub: EventSubscriber) -> None:
        self._loop = asyncio.get_running_loop()
        async with self._lock:
            self._subs.append(sub)
        log.info("terminal: subscriber added id=%s subs_total=%d", sub.sub_id, len(self._subs))

    async def remove(self, sub: EventSubscriber) -> None:
        async with self._lock:
            try:
                self._subs.remove(sub)
            except ValueError:
                return
        log.info("terminal: subscriber removed id=%s subs_total=%d", sub.sub_id, len(self._subs))

    async def reap_stale(self) -> int:
        """Remove subscribers idle longer than ``STALE_SUBSCRIBER_TTL_S``.

        A subscriber is considered idle if its ``last_seen_at`` is more
        than ``STALE_SUBSCRIBER_TTL_S`` seconds in the past.
        ``last_seen_at`` is set exclusively by the route handler via
        :meth:`EventSubscriber.touch` after each successful yield, so a
        wedged route handler will let its subscription age out and be
        reaped here even while offers continue to fan out.

        Returns the number of subscribers reaped. Safe to call from the
        offer hot-path — the caller is expected to rate-limit invocations
        to roughly once per ``_REAP_INTERVAL_S`` to avoid an O(n²) cost.
        """
        async with self._lock:
            now = time.time()
            to_remove = [
                s for s in self._subs
                if (now - s.last_seen_at) > STALE_SUBSCRIBER_TTL_S
            ]
            for s in to_remove:
                try:
                    self._subs.remove(s)
                except ValueError:
                    pass
        if to_remove:
            log.info(
                "terminal: reaped %d stale subscribers (ttl=%.1fs); subs_total=%d",
                len(to_remove), STALE_SUBSCRIBER_TTL_S, len(self._subs),
            )
        return len(to_remove)

    async def offer(self, event: TerminalEvent) -> None:
        """Fan-out an event to every subscriber that matches its filter.

        After fan-out, opportunistically run :meth:`reap_stale` if the
        last reap was more than ``_REAP_INTERVAL_S`` seconds ago. This
        keeps the dispatcher cheap (one extra dict lookup + comparison
        per offer) while still bounding the dead-subscriber accumulation.

        W18 G3 step 1: best-effort record the event to the daily replay
        JSONL after fan-out. Recording failures are swallowed (logged at
        WARNING by ``replay.record_event``) so a broken disk never
        breaks the broadcast hot-path. Disabling globally is supported
        via ``BROADCAST_RECORDS_REPLAY = False``.
        """
        async with self._lock:
            subs = list(self._subs)
        for s in subs:
            s.offer(event)
        # W18 G3 step 1 — replay-as-film recording. Imported lazily so
        # tests can monkeypatch the replay module's REPLAY_LOG_DIR
        # without circular-import gymnastics, and so this code path
        # never runs during ``stream.py`` import time.
        if BROADCAST_RECORDS_REPLAY:
            try:
                from sylion.aeis_v2.terminal.replay import record_event
                record_event(event)
            except Exception as exc:  # noqa: BLE001
                log.warning("terminal: replay record failed (%s)", exc)
        # KIMI review #2 — rate-limited reap. We deliberately read/write
        # _last_reap_at without the lock: the worst case is two offers
        # racing and both triggering a reap, which is harmless (reap is
        # idempotent). The lock-free path keeps the hot path lock-light.
        now = time.time()
        if (now - self._last_reap_at) > _REAP_INTERVAL_S:
            self._last_reap_at = now
            await self.reap_stale()

    def _offer_without_loop(self, event: TerminalEvent) -> None:
        """Best-effort fan-out from threads that do not own an asyncio loop."""
        for s in list(self._subs):
            s.offer(event)
        if BROADCAST_RECORDS_REPLAY:
            try:
                from sylion.aeis_v2.terminal.replay import record_event

                record_event(event)
            except Exception as exc:  # noqa: BLE001
                log.warning("terminal: replay record failed (%s)", exc)

    def wire_to_event_bus(self) -> bool:
        """Idempotent: subscribe wildcard to ``sylion.core.event_bus``.

        Returns True on first successful wire-up. We do this lazily on
        first SSE connection — backend startup time isn't blocked if
        the event bus isn't ready yet.
        """
        if self._wired_to_event_bus:
            return True
        try:
            from sylion.core.event_bus import get_event_bus
            bus = get_event_bus()
        except Exception as exc:  # noqa: BLE001
            log.warning("terminal: event_bus unavailable (%s) — running without bus subscription", exc)
            return False

        def _adapter(evt: Any) -> None:
            """Convert SylionEvent → TerminalEvent and offer to broadcaster.

            ``SylionEvent`` shape (from sylion/core/event_bus.py):
              event_id, topic, payload, source_module, primary_key, ts.
            """
            try:
                topic = getattr(evt, "topic", "") or ""
                # Layer is the topic prefix up to first dot, e.g.
                # "aeis.advisor.card_created" -> "AEIS"
                # "w14.test.findings"          -> "W14"
                # "core.event_bus.bootstrap"   -> "CORE"
                #
                # Kimi review fix: previous if/else had identical bodies
                # (no-op check). Now we DO normalize the W## layer ids
                # specifically (W with digits canonicalised) and leave
                # everything else as the upper-cased prefix.
                layer = "?"
                if "." in topic:
                    head = topic.split(".", 1)[0].lower()
                    if head.startswith("w") and head[1:].isdigit():
                        # Canonical "W14" / "W15" / etc.
                        layer = "W" + head[1:]
                    else:
                        layer = head.upper()
                else:
                    # Topic without dots — best effort: capitalise.
                    layer = topic.upper() or "?"
                payload = getattr(evt, "payload", {}) or {}
                if not isinstance(payload, dict):
                    payload = {"raw": str(payload)}
                # We never want to leak secrets into the activity stream.
                # Extended denylist (Kimi review): include credentials,
                # auth, bearer, private_key as additional patterns.
                _SECRET_SUFFIXES = (
                    "_key", "_secret", "_token", "password",
                    "credentials", "auth", "bearer", "private",
                )
                payload = {k: v for k, v in payload.items()
                           if not any(k.lower().endswith(s) for s in _SECRET_SUFFIXES)}
                msg = payload.get("message") or payload.get("description") or topic
                safe_extra_keys = {
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
                    "path",
                    "method",
                }
                extra = {
                    key: str(payload.get(key))[:160]
                    for key in safe_extra_keys
                    if payload.get(key) not in (None, "")
                }
                extra.update({
                    "topic": topic,
                    "primary_key": getattr(evt, "primary_key", ""),
                })
                te = TerminalEvent(
                    ts=getattr(evt, "timestamp", None) or getattr(evt, "ts", time.time()) or time.time(),
                    layer=layer,
                    module=getattr(evt, "source_module", "") or "",
                    message=str(msg)[:500],
                    severity=str(payload.get("severity", "info")),
                    model=str(payload.get("model", "")),
                    host=str(payload.get("host", "local")),
                    session_id=str(payload.get("session_id", "")),
                    cost_usd=float(payload.get("cost_usd", 0.0) or 0.0),
                    extra=extra,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("terminal adapter failure: %s", exc)
                return
            # Schedule fan-out without blocking the bus dispatcher thread.
            try:
                loop = self._loop
                if loop is not None and loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.offer(te), loop)
                else:
                    # No running loop — synchronously enqueue (best-effort).
                    self._offer_without_loop(te)
            except Exception as exc:  # noqa: BLE001
                log.exception("terminal: fan-out scheduling failed (%s)", exc)

        try:
            # Wildcard-style subscription. event_bus.subscribe takes a
            # topic prefix — we use empty string for "everything" if the
            # implementation supports it. Otherwise we'd register many
            # topic-specific subscribers.
            bus.subscribe("*", _adapter)
            self._wired_to_event_bus = True
            log.info("terminal: subscribed to event_bus wildcard")
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("terminal: event_bus subscribe failed (%s) — bus shape may differ", exc)
            return False


_broadcaster: TerminalBroadcaster | None = None


def get_broadcaster() -> TerminalBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = TerminalBroadcaster()
    return _broadcaster
