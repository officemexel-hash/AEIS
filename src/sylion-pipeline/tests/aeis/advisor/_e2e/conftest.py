"""E2E demo conftest — reuses the integration shim so the demo flow drives
real engine + history modules through their public service APIs.
"""

from __future__ import annotations

import os
import pytest

# F-011: requires PostgreSQL — auto-skipped by tests/conftest.py if PG not reachable.
pytestmark = pytest.mark.requires_postgres

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("OLLAMA_BASE_URL", "http://127.0.0.1:1")

from tests.aeis.advisor._integration.conftest import (  # noqa: F401 (re-export)
    _INTEGRATION_TEST_SCHEMA,
    _NAME_REWRITES,
)
from tests.aeis.advisor.engine._pg_test_pool import install_test_pool


@pytest.fixture(autouse=True)
def _e2e_pg_pool(monkeypatch):
    from sylion.aeis.advisor.engine.service import reset_engine_service
    from sylion.aeis.advisor.history.service import reset_history_service

    reset_engine_service()
    reset_history_service()

    pool = install_test_pool(monkeypatch)
    from tests.aeis.advisor.engine import _pg_test_pool as shim
    original = shim.translate_query

    def _translate(q: str) -> str:
        out = original(q)
        for fq, flat in _NAME_REWRITES.items():
            out = out.replace(fq, flat)
        return out

    monkeypatch.setattr(shim, "translate_query", _translate)
    pool.execute_script(_INTEGRATION_TEST_SCHEMA)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")

    yield pool

    pool.close()
    reset_engine_service()
    reset_history_service()
