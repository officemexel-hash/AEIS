"""Mobile gateway test conftest — installs SQLite-backed PG pool shim.

Per 08_audit_revisions.md Revision 2 tests use an in-memory SQLite-backed
shim of the shared PG pool.  Schema is recreated per-test for isolation.
"""
from __future__ import annotations

import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


# Reuse engine schema + rewrites — mobile_gateway exercises engine tables.
from tests.aeis.advisor.engine.conftest import _ENGINE_TEST_SCHEMA, _NAME_REWRITES


@pytest.fixture(autouse=True)
def _mobile_pg_pool(monkeypatch):
    from sylion.aeis.advisor.engine.service import reset_engine_service
    from sylion.aeis.advisor.mobile_gateway import reset_mobile_router

    reset_engine_service()
    reset_mobile_router()

    pool = install_test_pool(monkeypatch)

    # Patch the shim's query translator to rewrite schema-qualified names.
    from tests.aeis.advisor.engine import _pg_test_pool as shim
    original_translate = shim.translate_query

    def _translate_with_rewrites(query: str) -> str:
        out = original_translate(query)
        for fq, flat in _NAME_REWRITES.items():
            out = out.replace(fq, flat)
        return out

    monkeypatch.setattr(shim, "translate_query", _translate_with_rewrites)

    pool.execute_script(_ENGINE_TEST_SCHEMA)

    yield pool

    pool.close()
    reset_engine_service()
    reset_mobile_router()
