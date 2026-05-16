"""W15 G2: dedicated v2 PostgreSQL pool with stricter defaults.

Phase 0 of G2: provide the singleton + factory. Migration of every
consumer (applier, cost_ledger_pg, federation cost-ledger writes) lands
in subsequent cron rounds.

Differences from v1 advisor pool:
- max_size=20 (was 10) — supports concurrent applier + cost_ledger writes
- timeout=5.0 (was 2.0) — slightly more generous for DDL transactions
- statement_timeout='60000ms' default (matches APPLIER_STATEMENT_TIMEOUT_MS)
- search_path='sylion_v2, public' (DDL lands in v2 schema by default)
- isolation_level='REPEATABLE READ' on DDL connections (snapshot consistency)
- Reuses PGUnreachable typed exception from v1 _db
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

POOL_V2_MAX_SIZE = int(os.environ.get("SYLION_V2_POOL_MAX_SIZE", "20"))
POOL_V2_TIMEOUT_S = float(os.environ.get("SYLION_V2_POOL_TIMEOUT_S", "5.0"))
POOL_V2_STATEMENT_TIMEOUT_MS = int(
    os.environ.get("SYLION_V2_STATEMENT_TIMEOUT_MS", "60000")
)
POOL_V2_SCHEMA_PATH = os.environ.get("SYLION_V2_SCHEMA_PATH", "sylion_v2, public")
POOL_V2_ISOLATION = os.environ.get("SYLION_V2_ISOLATION", "REPEATABLE READ")

_pool: Any = None
_pool_lock = threading.Lock()


def get_v2_pool():
    """Lazy-init the v2 pool. Returns ``None`` when PG unreachable.

    Reuses ``PGUnreachable`` typed exception from v1 ``_db`` so callers
    can catch the same way (defensive — wrapping a different exc would
    break the existing migration audit code paths).

    Three branches mirror the applier's ``_get_pg_connection`` so the
    operator UI / log scraper sees the same severity gradients:

    - ``ImportError`` (advisor pool module missing): log.error, return
      None. This is a packaging defect — the v1 ``advisor`` extra was
      not installed alongside aeis_v2.
    - ``PGUnreachable`` (typed exception from v1 ``_db``): log.info,
      return None. Routine — PG offline, fall back to preview-only.
    - any other ``Exception``: log.error with ``exc_info=True``, return
      None. Unexpected — pool init blew up (likely a config bug).
    """
    global _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            from sylion.aeis.advisor._db import PGUnreachable, _build_dsn
        except ImportError as exc:
            logging.getLogger(__name__).error(
                "v2 pool: advisor _db missing (%s) — install the 'advisor' "
                "extra; v2 pool unavailable",
                exc,
            )
            return None
        try:
            import psycopg_pool

            db_url = _build_dsn()
            # Same kwargs as v1 but stricter (larger max_size, longer
            # timeout, statement_timeout pinned, schema + isolation set
            # via libpq ``options`` so every checked-out conn inherits
            # them without an explicit ``SET LOCAL`` round-trip).
            _pool = psycopg_pool.ConnectionPool(
                conninfo=db_url,
                min_size=1,
                max_size=POOL_V2_MAX_SIZE,
                timeout=POOL_V2_TIMEOUT_S,
                kwargs={
                    "options": (
                        f"-c search_path={POOL_V2_SCHEMA_PATH} "
                        f"-c default_transaction_isolation='{POOL_V2_ISOLATION}' "
                        f"-c statement_timeout={POOL_V2_STATEMENT_TIMEOUT_MS}"
                    ),
                },
                open=True,
            )
            return _pool
        except PGUnreachable as exc:
            logging.getLogger(__name__).info(
                "v2 pool: PG unreachable (%s) — preview-only mode", exc,
            )
            return None
        except Exception as exc:  # noqa: BLE001 — unexpected pool init failure
            logging.getLogger(__name__).error(
                "v2 pool: init failed unexpectedly (%s) — investigate "
                "config/env; preview-only mode for now",
                exc, exc_info=True,
            )
            return None


def reset_v2_pool() -> None:
    """Test helper — clear singleton.

    Closes the underlying psycopg pool best-effort if one was created.
    Safe to call when no pool was ever initialised (no-op).
    """
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.close()
            except Exception:  # noqa: BLE001 — best-effort close
                pass
        _pool = None
