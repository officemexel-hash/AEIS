"""W17 G2 step 3: cron worker that refreshes ``mv_cost_ledger``.

Phase 0 of step 3:

- In-process worker (``threading.Thread`` daemon) — not a real cron
  daemon yet. G3 replaces this with a proper systemd service / k8s
  CronJob calling ``POST /api/v1/federation/costs/refresh-mv``.
- Configurable interval (default 30s, env
  ``SYLION_COST_REFRESH_INTERVAL_S``).
- First refresh after the worker starts uses ``concurrently=False`` —
  ``REFRESH MATERIALIZED VIEW CONCURRENTLY`` requires the MV to already
  be populated AND have a unique index, which a fresh DDL apply cannot
  guarantee. Subsequent refreshes use ``concurrently=True`` so
  ``/costs/recent`` readers stay unblocked.
- Audit JSONL row per refresh under ``logs/v2/cost_ledger_refresh.jsonl``:
  ``{ts, duration_ms, success, error, concurrently}``. Mirrors the
  cost-ledger Phase 0 audit pattern (``cost_ledger.py``) so the operator
  console can render both feeds with the same parser.
- Graceful shutdown: ``stop_event`` triggers thread exit within at most
  one ``interval_s`` plus the in-flight refresh duration. We sleep on
  the event (``stop_event.wait(interval_s)``) so a stop request wakes
  the loop immediately rather than waiting out the full interval.

Why a thread (and not asyncio)?

The advisor uses sync FastAPI routes today; a daemon thread keeps the
worker self-contained without needing an event loop reference. When G3
swaps this for systemd/k8s the in-process loop goes away entirely, so
the threading scaffolding is intentionally lightweight.

Why a singleton?

Mirrors ``get_node_registry`` / ``get_federation_router`` so the REST
endpoints (``/costs/refresher/start|stop|stats``) always see the same
instance regardless of which uvicorn worker handled the request. A
``reset_refresher()`` test helper lets the suite spawn a fresh worker
with custom intervals per test.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# parents[3] resolves: cost_ledger_refresher.py -> deployment -> aeis_v2
# -> sylion -> sylion-pipeline/. Same convention as ``cost_ledger.py``
# so the operator console resolves both audit feeds via the same root.
REFRESH_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "cost_ledger_refresh.jsonl"
)


# Defaults are env-driven so operators can tune without redeploying;
# tests override via dataclass kwargs (interval_s=0.05) so suite runs
# in <1s. The float() cast tolerates "30", "30.0", "30s"-stripped, etc.
def _env_float(key: str, default: float) -> float:
    """Read an env var as float, falling back to ``default`` on parse error."""
    raw = os.environ.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        log.warning(
            "cost_ledger_refresher: env %s=%r is not a float, using default %r",
            key, raw, default,
        )
        return default


REFRESH_INTERVAL_S: float = _env_float("SYLION_COST_REFRESH_INTERVAL_S", 30.0)
REFRESH_INITIAL_DELAY_S: float = _env_float(
    "SYLION_COST_REFRESH_INITIAL_DELAY_S", 5.0,
)


@dataclass
class RefreshStats:
    """Aggregate stats over the lifetime of one ``CostLedgerRefresher``.

    Reset on ``CostLedgerRefresher.__init__`` (and therefore on
    ``reset_refresher()``). Fields:

    - ``total_refreshes``: every attempt, success or fail.
    - ``success_count`` / ``error_count``: split.
    - ``total_duration_ms``: sum of every attempt (incl. failures); used
      for ``avg_duration_ms``.
    - ``last_refresh_ts``: epoch seconds of the most recent attempt
      (success OR failure). 0.0 means "no refresh yet".
    - ``last_error``: most recent error string, or None on a clean run.
    - ``first_refresh_done``: True once the very first refresh attempt
      completed (success or failure). Drives the concurrently=False ->
      True transition.
    """

    total_refreshes: int = 0
    success_count: int = 0
    error_count: int = 0
    total_duration_ms: float = 0.0
    last_refresh_ts: float = 0.0
    last_error: str | None = None
    first_refresh_done: bool = False

    @property
    def avg_duration_ms(self) -> float:
        """Average duration in ms; 0.0 when no refreshes yet."""
        if self.total_refreshes <= 0:
            return 0.0
        return self.total_duration_ms / self.total_refreshes

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dump including the derived ``avg_duration_ms``.

        ``asdict`` only emits declared fields, so we splice in the
        property explicitly. Field order is stable so the operator UI
        can render predictable JSON.
        """
        out = asdict(self)
        out["avg_duration_ms"] = self.avg_duration_ms
        return out


class CostLedgerRefresher:
    """Daemon thread that periodically refreshes ``sylion_v2.mv_cost_ledger``.

    Lifecycle:

    1. ``__init__`` — captures interval + initial delay, builds a
       ``threading.Event`` for stop signalling. NO thread is spawned
       yet.
    2. ``start()`` — idempotent: spawns the daemon thread on first call;
       subsequent calls while the thread is alive are no-ops.
    3. Background loop:
       - Sleep ``initial_delay_s`` (or until stop signalled).
       - Loop while not stopped:
         - Resolve PG pool via ``_get_pg_connection`` (lazy import to
           avoid pulling psycopg at module import time).
         - Refresh: first attempt uses ``concurrently=False`` (the
           steady-state guard), every subsequent attempt uses
           ``concurrently=True``.
         - Record stats + emit one JSONL audit row.
         - Wait ``interval_s`` (or until stop signalled).
    4. ``stop(timeout_s)`` — signals the event, joins the thread.

    Thread safety:

    - ``_stats`` mutations are guarded by ``_lock`` so the public
      ``stats`` accessor never races with the loop body.
    - ``_thread`` reference is mutated only inside ``start()`` /
      ``stop()`` under ``_lock`` so concurrent start+stop calls don't
      tear the state machine.
    """

    def __init__(
        self,
        *,
        interval_s: float = REFRESH_INTERVAL_S,
        initial_delay_s: float = REFRESH_INITIAL_DELAY_S,
    ) -> None:
        if interval_s <= 0:
            raise ValueError(
                f"interval_s must be > 0, got {interval_s!r}",
            )
        if initial_delay_s < 0:
            raise ValueError(
                f"initial_delay_s must be >= 0, got {initial_delay_s!r}",
            )
        self._interval_s = float(interval_s)
        self._initial_delay_s = float(initial_delay_s)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._stats = RefreshStats()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def stats(self) -> RefreshStats:
        """Snapshot of stats. Read under lock for consistency."""
        with self._lock:
            # Return a shallow copy so callers can't mutate our state.
            return RefreshStats(
                total_refreshes=self._stats.total_refreshes,
                success_count=self._stats.success_count,
                error_count=self._stats.error_count,
                total_duration_ms=self._stats.total_duration_ms,
                last_refresh_ts=self._stats.last_refresh_ts,
                last_error=self._stats.last_error,
                first_refresh_done=self._stats.first_refresh_done,
            )

    @property
    def interval_s(self) -> float:
        """Configured refresh interval (seconds)."""
        return self._interval_s

    @property
    def initial_delay_s(self) -> float:
        """Configured initial delay before the first refresh (seconds)."""
        return self._initial_delay_s

    def is_running(self) -> bool:
        """True when the daemon thread is alive and the stop flag is unset."""
        with self._lock:
            t = self._thread
        return t is not None and t.is_alive() and not self._stop_event.is_set()

    def start(self) -> None:
        """Start the daemon thread. Idempotent.

        If the thread is already alive a second call is a no-op (logged
        at DEBUG). If a previous run stopped, a fresh thread is spawned
        and the stop event is cleared.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                log.debug(
                    "cost_ledger_refresher: start() called but thread "
                    "already running",
                )
                return
            # Clear any stale stop signal from a previous lifecycle.
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="cost-ledger-refresher",
                daemon=True,
            )
            self._thread.start()
        log.info(
            "cost_ledger_refresher: started "
            "(interval=%.3fs, initial_delay=%.3fs)",
            self._interval_s, self._initial_delay_s,
        )

    def stop(self, timeout_s: float = 5.0) -> bool:
        """Signal stop and wait for the thread to exit.

        Returns True when the thread exited within ``timeout_s``,
        False on timeout. The caller can decide whether to retry or
        accept the leak (in tests we always succeed because intervals
        are tiny; in prod the cron worker is the only long-lived
        consumer of the pool).
        """
        with self._lock:
            t = self._thread
        if t is None:
            return True
        self._stop_event.set()
        t.join(timeout=timeout_s)
        clean = not t.is_alive()
        if clean:
            log.info("cost_ledger_refresher: stopped cleanly")
            with self._lock:
                self._thread = None
        else:
            log.warning(
                "cost_ledger_refresher: stop timed out after %.1fs",
                timeout_s,
            )
        return clean

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_pool(self) -> Any:
        """Lazy-resolve the PG pool via the W15 applier helper.

        Imported at call time so module import does not pull psycopg
        when the worker is never started (e.g. a test suite that only
        imports the dataclass). Returns ``None`` when PG is unreachable
        — the loop body handles that as a refresh error and keeps
        looping.
        """
        try:
            from sylion.aeis_v2.ontology.applier import _get_pg_connection
            return _get_pg_connection()
        except Exception as exc:  # noqa: BLE001 — module-import or PG-init error
            log.warning(
                "cost_ledger_refresher: pool resolver failed (%s)", exc,
            )
            return None

    def _run(self) -> None:
        """Daemon-thread main loop.

        We sleep via ``stop_event.wait(seconds)`` so a stop request
        wakes us up immediately — ``time.sleep`` would force the
        operator to wait out a 30s tick before the worker exits.
        """
        # Initial delay — give the FastAPI app time to finish lifespan
        # init before we hammer the pool with the first REFRESH.
        if self._stop_event.wait(self._initial_delay_s):
            log.info(
                "cost_ledger_refresher: stop signalled during initial delay",
            )
            return

        while not self._stop_event.is_set():
            pool = self._resolve_pool()
            with self._lock:
                concurrently = self._stats.first_refresh_done
            success, duration_ms, error = self._refresh_once(
                pool, concurrently=concurrently,
            )
            self._record_attempt(success, duration_ms, error)
            self._emit_refresh_audit(
                success=success,
                duration_ms=duration_ms,
                error=error,
                concurrently=concurrently,
            )
            # Wait the interval (or until stop) before the next tick.
            if self._stop_event.wait(self._interval_s):
                break
        log.info("cost_ledger_refresher: loop exiting")

    def _refresh_once(
        self, pool: Any, *, concurrently: bool,
    ) -> tuple[bool, float, str | None]:
        """Single refresh attempt.

        Returns ``(success, duration_ms, error_or_None)``. Failures
        never raise — the caller (loop body) just records them and
        keeps looping. ``pool=None`` is reported as a soft error
        ("pg_unreachable") so operators see the cause in the audit.
        """
        t0 = time.monotonic()
        if pool is None:
            duration_ms = (time.monotonic() - t0) * 1000.0
            return False, duration_ms, "pg_unreachable"
        # Lazy import — keeps the deployment package import-time clean
        # of psycopg when the worker is never instantiated.
        try:
            from sylion.aeis_v2.deployment.cost_ledger_pg import (
                refresh_mv_cost_ledger,
            )
            ok = refresh_mv_cost_ledger(pool, concurrently=concurrently)
        except Exception as exc:  # noqa: BLE001 — defensive: worker must not crash
            duration_ms = (time.monotonic() - t0) * 1000.0
            return False, duration_ms, f"{type(exc).__name__}: {exc}"
        duration_ms = (time.monotonic() - t0) * 1000.0
        if not ok:
            return False, duration_ms, "refresh_failed"
        return True, duration_ms, None

    def _record_attempt(
        self, success: bool, duration_ms: float, error: str | None,
    ) -> None:
        """Update the in-memory stats under lock."""
        with self._lock:
            self._stats.total_refreshes += 1
            self._stats.total_duration_ms += duration_ms
            self._stats.last_refresh_ts = time.time()
            self._stats.first_refresh_done = True
            if success:
                self._stats.success_count += 1
                self._stats.last_error = None
            else:
                self._stats.error_count += 1
                self._stats.last_error = error

    def _emit_refresh_audit(
        self,
        *,
        success: bool,
        duration_ms: float,
        error: str | None,
        concurrently: bool,
    ) -> None:
        """Append one JSONL row to ``REFRESH_AUDIT_LOG_PATH``.

        Audit failures (disk full, permission denied) are logged at
        WARNING and swallowed — the cron worker must not die because
        the audit sink is degraded. Stats already captured the row
        in-memory so an operator can still inspect via the stats
        endpoint.

        We re-resolve the path on every call so a test that
        ``monkeypatch.setattr(module, "REFRESH_AUDIT_LOG_PATH", ...)``
        wins over a stale closure.
        """
        path = REFRESH_AUDIT_LOG_PATH
        # Tests may rebind the module-level constant; re-import to
        # pick that up even if a long-lived loop body cached the
        # original.
        try:
            import sylion.aeis_v2.deployment.cost_ledger_refresher as _mod
            path = _mod.REFRESH_AUDIT_LOG_PATH
        except Exception:  # noqa: BLE001 — fallback to the local symbol
            pass

        row = {
            "ts": time.time(),
            "duration_ms": float(duration_ms),
            "success": bool(success),
            "error": error,
            "concurrently": bool(concurrently),
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning(
                "cost_ledger_refresher: audit write failed (%s) — "
                "stats still captured the row",
                exc,
            )


# --------------------------------------------------------------------------
# Singleton accessor — mirrors get_node_registry / get_federation_router
# --------------------------------------------------------------------------
#
# The REST endpoints (``/costs/refresher/start|stop|stats``) all need
# the same instance regardless of uvicorn worker. Tests use
# ``reset_refresher()`` to drop the singleton between cases so a
# previous test's running thread can't leak into the next.

_refresher_singleton: CostLedgerRefresher | None = None
_singleton_lock = threading.Lock()


def get_refresher() -> CostLedgerRefresher:
    """Return the singleton ``CostLedgerRefresher``, lazy-init on first call.

    The singleton is constructed with the env-driven defaults
    (``REFRESH_INTERVAL_S`` / ``REFRESH_INITIAL_DELAY_S``). Operators
    who need a different schedule can call ``reset_refresher()`` and
    construct a fresh ``CostLedgerRefresher(interval_s=...)`` directly,
    or set the env vars before the first ``get_refresher()`` call.
    """
    global _refresher_singleton
    with _singleton_lock:
        if _refresher_singleton is None:
            _refresher_singleton = CostLedgerRefresher()
        return _refresher_singleton


def reset_refresher() -> None:
    """Drop the singleton (after stopping it cleanly).

    Test helper — never call from production code. Stops the existing
    thread first so a leaked daemon doesn't outlive the test.
    """
    global _refresher_singleton
    with _singleton_lock:
        old = _refresher_singleton
        _refresher_singleton = None
    if old is not None:
        try:
            old.stop(timeout_s=2.0)
        except Exception as exc:  # noqa: BLE001 — best effort
            log.warning(
                "cost_ledger_refresher: reset_refresher stop failed (%s)",
                exc,
            )


__all__ = [
    "REFRESH_AUDIT_LOG_PATH",
    "REFRESH_INTERVAL_S",
    "REFRESH_INITIAL_DELAY_S",
    "RefreshStats",
    "CostLedgerRefresher",
    "get_refresher",
    "reset_refresher",
]
