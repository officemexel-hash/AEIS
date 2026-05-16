"""Shared PostgreSQL connection pool for advisor modules.

F-018b stability fix (2026-04-26):
- Previously: eager pool with min_size=1 + open=True + 30s default timeout.
  When PG was offline every advisor request hung 30s, dashboard flickered.
- Now: lazy pool with min_size=0, connect_timeout=2, pool timeout=2.
- Plus: cache "PG unreachable" status for ~60s so we don't pay 2s per call
  when SQLite-only deployment polls preferences every few seconds.

If a real PG deployment becomes reachable later the cache expires and the
next call re-probes — no restart required.
"""
from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None
_unreachable_until: float = 0.0  # epoch when cached unreachable state expires
_UNREACHABLE_TTL_S = 60.0  # how long to remember "PG offline" between probes


class PGUnreachable(RuntimeError):
    """Raised by ``get_pool`` when PG was probed as offline within TTL."""


class PgAdvisoryLock:
    def __init__(self, conn, lock_id: int, timeout_s: float | None = None, sleep_s: float = 0.05):
        self.conn, self.lock_id = conn, lock_id
        self.timeout_s, self.sleep_s = timeout_s, sleep_s

    def __enter__(self):
        with self.conn.cursor() as cur:
            if self.timeout_s is None:
                cur.execute("SELECT pg_advisory_lock(%s)", (self.lock_id,))
                return self
            deadline = time.time() + self.timeout_s
            while time.time() < deadline:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (self.lock_id,))
                row = cur.fetchone()
                if row and row[0]:
                    return self
                time.sleep(self.sleep_s)
        raise TimeoutError(f"timed out acquiring advisory lock {self.lock_id}")

    def __exit__(self, exc_type, exc, tb) -> None:
        with self.conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (self.lock_id,))


def _build_dsn() -> str:
    dsn = os.environ.get(
        "SYLION_PG_DSN",
        os.environ.get("SYLION_DB_URL", "postgresql://localhost/sylion"),
    )
    if "connect_timeout=" not in dsn:
        sep = "?" if "?" not in dsn else "&"
        dsn = f"{dsn}{sep}connect_timeout=2"
    return dsn


def get_pool() -> ConnectionPool:
    """Return the singleton advisor connection pool.

    Raises ``PGUnreachable`` if a recent probe found PG offline (cached for
    ``_UNREACHABLE_TTL_S`` seconds). In audit profile mode PG is disabled
    outright; modules must use an audit-local store or surface a real error.
    """
    global _pool, _unreachable_until
    if str(os.environ.get("SYLION_ADVISOR_FORCE_PG", "")).lower() not in {"1", "true", "yes"}:
        db_mode = str(os.environ.get("SYLION_DB_MODE", "sqlite")).strip().lower()
        has_pg_dsn = bool(os.environ.get("SYLION_DB_URL") or os.environ.get("SYLION_PG_DSN"))
        if db_mode != "postgres" or not has_pg_dsn:
            raise PGUnreachable(
                "Advisor PostgreSQL pool is disabled in local SQLite mode; "
                "module must use an audit-local store"
            )
        try:
            from sylion.aeis_v2.audit_profile import is_audit_mode

            if is_audit_mode():
                raise PGUnreachable(
                    "Advisor PostgreSQL pool is disabled in audit profile mode; "
                    "module must use an audit-local store"
                )
        except PGUnreachable:
            raise
        except Exception:
            pass
    now = time.time()
    if now < _unreachable_until:
        raise PGUnreachable(
            f"PG marked unreachable until {_unreachable_until - now:.1f}s from now"
        )
    if _pool is None:
        try:
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise RuntimeError(
                "Advisor PG support requires psycopg[pool]. Install the 'advisor' extra."
            ) from exc
        _pool = ConnectionPool(
            conninfo=_build_dsn(),
            min_size=0,
            max_size=10,
            open=True,
            timeout=2.0,
        )
    return _pool


def mark_pg_unreachable() -> None:
    """Mark PG as unreachable so subsequent get_pool() calls fail-fast."""
    global _unreachable_until
    _unreachable_until = time.time() + _UNREACHABLE_TTL_S


def reset_pg_reachability() -> None:
    """Clear the cached unreachable state (e.g. after PG admin restart)."""
    global _unreachable_until
    _unreachable_until = 0.0


def is_pg_reachable() -> bool:
    """Cheap probe used by service-layer code to skip PG calls when offline.

    Caches the negative result so repeated calls don't each pay the 2s timeout.
    """
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except PGUnreachable:
        return False
    except Exception:
        mark_pg_unreachable()
        return False


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    """Execute a statement without returning rows."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
    """Fetch a single row."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    """Fetch all rows for a query."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()
