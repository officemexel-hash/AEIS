from __future__ import annotations

from pathlib import Path

from sylion.aeis_v2.audit_profile import resolve_db_path
from sylion.funding_autopilot.config import funding_db_path
from sylion.funding_autopilot.routes import reset_funding_route_service
from sylion.funding_autopilot.store import get_funding_store, reset_funding_store


def test_funding_db_path_follows_audit_profile(monkeypatch):
    monkeypatch.delenv("SYLION_DB_PATH", raising=False)
    monkeypatch.setenv("SYLION_AUDIT_PROFILE_ID", "r3_7_funding_truth_pytest")

    assert Path(funding_db_path()) == resolve_db_path("sylion_aeis.db")


def test_funding_route_service_uses_configured_shared_store(tmp_path, monkeypatch):
    db_path = tmp_path / "shared.sqlite"
    monkeypatch.setenv("SYLION_DB_PATH", str(db_path))

    service = reset_funding_route_service(str(db_path))
    assert Path(service.store.db_path) == db_path
    assert get_funding_store(str(db_path)) is service.store

    replacement_db_path = tmp_path / "replacement.sqlite"
    reset_funding_store(str(replacement_db_path))
    assert Path(get_funding_store(str(replacement_db_path)).db_path) == replacement_db_path
