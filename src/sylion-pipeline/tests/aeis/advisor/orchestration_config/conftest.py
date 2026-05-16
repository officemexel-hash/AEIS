"""Orchestration config test conftest — clears PG tables for isolation."""
from __future__ import annotations

import pytest


_ORCHESTRATION_TABLES = [
    "advisor_orchestration.inter_model_conversations",
    "advisor_orchestration.llm_judge_routing",
    "advisor_orchestration.council_rules",
    "advisor_orchestration.auditor_cadence",
    "advisor_orchestration.fixer_protocol",
    "advisor_orchestration.dispatch_config",
    "advisor_orchestration.test_catalog",
    "advisor_orchestration.test_catalog_runs",
    "advisor_orchestration.team_formation_rules",
    "advisor_orchestration.active_teams",
    "advisor_orchestration.event_map_cache",
    "advisor_orchestration.config_kv",
]


@pytest.fixture(autouse=True)
def _clean_orchestration_tables():
    from sylion.aeis.advisor._db import get_pool
    from sylion.aeis.advisor.orchestration_config.service import _STORE

    # Clear in-memory store
    _STORE.clear()

    # Clear PG tables if available
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            for table in _ORCHESTRATION_TABLES:
                cur.execute(f"DELETE FROM {table}")
    except Exception:
        pass

    yield

    _STORE.clear()
    try:
        with get_pool().connection() as conn, conn.cursor() as cur:
            for table in _ORCHESTRATION_TABLES:
                cur.execute(f"DELETE FROM {table}")
    except Exception:
        pass
