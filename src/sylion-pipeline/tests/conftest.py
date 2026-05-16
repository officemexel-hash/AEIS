"""Shared pytest configuration for the unified AEIS runtime tests."""

from __future__ import annotations

import os

# Default tests to RBAC-disabled so existing anonymous-client suites continue
# to pass. Tests that exercise RBAC enforcement opt in via monkeypatch.
os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")


def pytest_runtest_setup(item):
    """Reset per-test in-memory limiters used by the unified runtime tests."""
    try:
        from rate_limit_middleware import reset_rate_limit_store

        reset_rate_limit_store()
    except Exception:
        pass

    try:
        from sylion.infra.cache import reset_cache

        reset_cache()
    except Exception:
        pass


import socket as _f011_socket  # noqa: E402

_F011_PG_REACHABLE: bool | None = None


def _f011_postgres_reachable() -> bool:
    global _F011_PG_REACHABLE
    if _F011_PG_REACHABLE is not None:
        return _F011_PG_REACHABLE
    host = os.environ.get("PGHOST", "127.0.0.1")
    port = int(os.environ.get("PGPORT", "5432"))
    try:
        with _f011_socket.create_connection((host, port), timeout=0.5):
            _F011_PG_REACHABLE = True
    except Exception:
        _F011_PG_REACHABLE = False
    return _F011_PG_REACHABLE


def pytest_collection_modifyitems(config, items):
    import pytest as _pt

    if _f011_postgres_reachable():
        return
    skip_pg = _pt.mark.skip(
        reason="F-011: requires_postgres but PG not reachable; SQLite-only env"
    )
    for item in items:
        if "requires_postgres" in item.keywords:
            item.add_marker(skip_pg)
