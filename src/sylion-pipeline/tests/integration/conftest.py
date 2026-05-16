"""Phase 2 D-INTEGRATE integration tests — shared fixtures."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "integration.sqlite")


@pytest.fixture(autouse=True)
def reset_singletons(tmp_db_path: str):
    """Reset every governance/skills/memory/mobile singleton with a fresh tmp DB."""
    from sylion.governance.audit_chain import reset_audit_chain
    from sylion.governance.ticket import reset_ticket_store
    from sylion.memory import bootstrap as memory_bootstrap
    from sylion.skills.runtime import reset_skills_runtime
    from sylion.operator_mobile import (
        reset_operator_mobile_bridge,
        reset_operator_mobile_store,
    )

    reset_audit_chain(db_path=tmp_db_path)
    reset_ticket_store(db_path=tmp_db_path)
    memory_bootstrap({"db_path": tmp_db_path})
    reset_skills_runtime()
    reset_operator_mobile_store(db_path=tmp_db_path)
    reset_operator_mobile_bridge(db_path=tmp_db_path)
    yield
