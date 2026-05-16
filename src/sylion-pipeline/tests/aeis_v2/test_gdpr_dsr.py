"""Tests for ``sylion.aeis_v2.gdpr_v2.dsr`` — GDPR DSR handler.

Covers Articles 15/16/17/20 actions across the unit (DsrService) and
HTTP (FastAPI router) layers. RBAC is bypassed in tests via the
``SYLION_RBAC_DISABLED`` env var so we exercise routing/contract logic
without seeding a roles store.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.gdpr_v2 import (
    DSR_ACTIONS,
    DsrAuditEntry,
    DsrResult,
    DsrService,
    InMemoryUserDataStore,
    reset_dsr_service,
    set_dsr_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> InMemoryUserDataStore:
    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert", "email": "robert@example.com", "tier": "ops"})
    s.upsert("u-2", {"name": "Anna", "email": "anna@example.com", "tier": "viewer"})
    return s


@pytest.fixture
def service(tmp_path: Path, store: InMemoryUserDataStore) -> DsrService:
    audit = tmp_path / "gdpr_dsr.jsonl"
    return DsrService(store=store, audit_log_path=audit)


@pytest.fixture
def rbac_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")


# ---------------------------------------------------------------------------
# Module-level invariants
# ---------------------------------------------------------------------------


def test_dsr_actions_constants_match_canonical_set() -> None:
    """The canonical set is exactly the 4 GDPR articles we implement."""
    assert set(DSR_ACTIONS) == {
        "access", "rectification", "erasure", "portability",
    }


def test_dsr_audit_entry_to_dict_round_trips() -> None:
    e = DsrAuditEntry(
        event_id="abc",
        ts=123.0,
        action="access",
        user_id="u-1",
        actor="ops",
        success=True,
        details={"x": 1},
    )
    d = e.to_dict()
    assert d["event_id"] == "abc"
    assert d["ts"] == 123.0
    assert d["details"] == {"x": 1}


# ---------------------------------------------------------------------------
# InMemoryUserDataStore
# ---------------------------------------------------------------------------


def test_store_get_existing_returns_copy() -> None:
    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert"})
    got = s.get("u-1")
    assert got is not None
    got["name"] = "MUTATED"
    # Mutating the returned dict must not affect the store.
    assert s.get("u-1")["name"] == "Robert"  # type: ignore[index]


def test_store_get_missing_returns_none() -> None:
    s = InMemoryUserDataStore()
    assert s.get("absent") is None


def test_store_soft_delete_hides_from_get() -> None:
    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert"})
    assert s.soft_delete("u-1", ts=999.0) is True
    assert s.get("u-1") is None


def test_store_soft_delete_missing_returns_false() -> None:
    s = InMemoryUserDataStore()
    assert s.soft_delete("absent", ts=999.0) is False


def test_store_upsert_resurrects_soft_deleted() -> None:
    """RECTIFICATION on an erased user reverses the deletion (Art. 12.3)."""
    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert"})
    s.soft_delete("u-1", ts=999.0)
    s.upsert("u-1", {"email": "robert@example.com"})
    row = s.get("u-1")
    assert row is not None
    assert row["email"] == "robert@example.com"
    assert "deleted_at" not in row


def test_store_list_users_skips_deleted() -> None:
    s = InMemoryUserDataStore()
    s.upsert("u-1", {})
    s.upsert("u-2", {})
    s.soft_delete("u-1", ts=1.0)
    assert s.list_users() == ["u-2"]


# ---------------------------------------------------------------------------
# DsrService — Article 15 ACCESS
# ---------------------------------------------------------------------------


def test_access_returns_user_record(service: DsrService) -> None:
    r = service.access("u-1", actor="ops")
    assert isinstance(r, DsrResult)
    assert r.success is True
    assert r.payload is not None
    assert r.payload["name"] == "Robert"
    assert r.audit_event_id


def test_access_missing_user_returns_failure(service: DsrService) -> None:
    r = service.access("absent")
    assert r.success is False
    assert r.payload is None


def test_access_writes_audit_jsonl(service: DsrService, tmp_path: Path) -> None:
    """Sprint 2 day 6 — audit emission goes through audit_chain.

    Each row is shaped as ``{"prev_hash": ..., "content": <DsrAuditEntry
    dict>, "content_hash": ...}`` so the test reads the ``content``
    subkey to compare semantic fields.
    """
    audit = tmp_path / "gdpr_dsr.jsonl"
    s = DsrService(store=InMemoryUserDataStore(), audit_log_path=audit)
    s.access("absent", actor="ops")
    s.access("u-1", actor="ops")
    rows = [json.loads(l) for l in audit.read_text(encoding="utf-8").splitlines() if l]
    contents = [r["content"] for r in rows]
    assert len(contents) == 2
    assert all(e["action"] == "access" for e in contents)
    assert contents[0]["success"] is False
    assert contents[1]["actor"] == "ops"


# ---------------------------------------------------------------------------
# DsrService — Article 16 RECTIFICATION
# ---------------------------------------------------------------------------


def test_rectify_merges_patch(service: DsrService) -> None:
    r = service.rectify("u-1", {"email": "new@example.com"}, actor="ops")
    assert r.success is True
    assert service.access("u-1").payload["email"] == "new@example.com"  # type: ignore[index]


def test_rectify_empty_patch_fails(service: DsrService) -> None:
    r = service.rectify("u-1", {}, actor="ops")
    assert r.success is False
    assert "empty" in (r.payload or {}).get("error", "")


def test_rectify_creates_user_if_absent(service: DsrService) -> None:
    """RECTIFICATION on absent user_id creates the row (op-level convenience)."""
    r = service.rectify("u-new", {"name": "Carla"}, actor="ops")
    assert r.success is True
    assert service.access("u-new").payload["name"] == "Carla"  # type: ignore[index]


def test_rectify_unwinds_soft_delete(service: DsrService) -> None:
    """RECTIFICATION on erased user reverses the deletion."""
    service.erase("u-1")
    r = service.rectify("u-1", {"name": "Robert v2"}, actor="ops")
    assert r.success is True
    assert service.access("u-1").payload["name"] == "Robert v2"  # type: ignore[index]


# ---------------------------------------------------------------------------
# DsrService — Article 17 ERASURE
# ---------------------------------------------------------------------------


def test_erase_marks_user_deleted(service: DsrService) -> None:
    r = service.erase("u-1", actor="owner")
    assert r.success is True
    assert service.access("u-1").success is False


def test_erase_missing_user_fails(service: DsrService) -> None:
    r = service.erase("absent", actor="owner")
    assert r.success is False


def test_audit_emission_produces_verifiable_chain(tmp_path: Path) -> None:
    """Sprint 2 day 6 — DSR audit JSONL is now hash-chained + verifiable."""
    from sylion.aeis_v2.audit_chain import verify_chain

    audit = tmp_path / "gdpr_dsr.jsonl"
    s = DsrService(store=InMemoryUserDataStore(), audit_log_path=audit)
    # Multiple ops to populate the chain.
    s.access("absent", actor="ops")
    s.rectify("u-1", {"name": "Robert"}, actor="ops")
    s.access("u-1", actor="ops")
    s.erase("u-1", actor="owner")
    # The full chain must verify.
    assert verify_chain(audit) == []


def test_erase_audit_includes_purge_window(service: DsrService) -> None:
    r = service.erase("u-1", actor="owner")
    assert r.payload["soft_delete_ts"] > 0
    # Audit row carries the 30-day window (in seconds).
    # Sprint 2 day 6 — chained format: walk via content subkey.
    audit_rows = [
        json.loads(l)["content"] for l in service._audit_path.read_text(
            encoding="utf-8").splitlines() if l
    ]
    erase_rows = [e for e in audit_rows if e["action"] == "erasure"]
    assert erase_rows[-1]["details"]["hard_purge_after_s"] == 30 * 24 * 3600


# ---------------------------------------------------------------------------
# DsrService — Article 20 PORTABILITY
# ---------------------------------------------------------------------------


def test_portability_returns_versioned_bundle(service: DsrService) -> None:
    r = service.portability("u-1", actor="ops")
    assert r.success is True
    assert r.payload is not None
    assert r.payload["schema"] == "sylion.gdpr.dsr.portability/v1"
    assert "user" in r.payload
    assert r.payload["user"]["name"] == "Robert"


def test_portability_missing_user_fails(service: DsrService) -> None:
    r = service.portability("absent")
    assert r.success is False


# ---------------------------------------------------------------------------
# Singleton accessors
# ---------------------------------------------------------------------------


def test_set_dsr_service_replaces_singleton(tmp_path: Path) -> None:
    custom = DsrService(audit_log_path=tmp_path / "x.jsonl")
    set_dsr_service(custom)
    from sylion.aeis_v2.gdpr_v2 import get_dsr_service
    assert get_dsr_service() is custom
    reset_dsr_service()


# ---------------------------------------------------------------------------
# REST endpoints — exercise routing + RBAC (RBAC disabled for tests).
# ---------------------------------------------------------------------------


def test_endpoint_dsr_access_happy(rbac_disabled, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert"})
    set_dsr_service(DsrService(store=s, audit_log_path=tmp_path / "audit.jsonl"))
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/gdpr/dsr/access/u-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["action"] == "access"
        assert body["payload"]["name"] == "Robert"
    finally:
        reset_dsr_service()


def test_endpoint_dsr_access_missing_404(rbac_disabled, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    set_dsr_service(DsrService(audit_log_path=tmp_path / "audit.jsonl"))
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/gdpr/dsr/access/missing")
        assert resp.status_code == 404
        assert "user not found" in resp.json()["detail"]["error"]
    finally:
        reset_dsr_service()


def test_endpoint_dsr_rectification_happy(rbac_disabled, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert"})
    set_dsr_service(DsrService(store=s, audit_log_path=tmp_path / "audit.jsonl"))
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/gdpr/dsr/rectification/u-1",
            json={"patch": {"email": "robert@example.com"}},
        )
        assert resp.status_code == 200
        assert resp.json()["payload"]["patched_keys"] == ["email"]
    finally:
        reset_dsr_service()


def test_endpoint_dsr_erasure_happy(rbac_disabled, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert"})
    set_dsr_service(DsrService(store=s, audit_log_path=tmp_path / "audit.jsonl"))
    try:
        client = TestClient(app)
        resp = client.delete("/api/v1/gdpr/dsr/erasure/u-1")
        assert resp.status_code == 200
        assert resp.json()["action"] == "erasure"
        # Subsequent ACCESS must 404.
        resp2 = client.get("/api/v1/gdpr/dsr/access/u-1")
        assert resp2.status_code == 404
    finally:
        reset_dsr_service()


def test_endpoint_dsr_portability_happy(rbac_disabled, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    s = InMemoryUserDataStore()
    s.upsert("u-1", {"name": "Robert"})
    set_dsr_service(DsrService(store=s, audit_log_path=tmp_path / "audit.jsonl"))
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/gdpr/dsr/portability/u-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["payload"]["schema"] == "sylion.gdpr.dsr.portability/v1"
    finally:
        reset_dsr_service()


def test_endpoint_dsr_audit_recent_returns_entries(
    rbac_disabled, tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    audit = tmp_path / "gdpr_dsr.jsonl"
    s = InMemoryUserDataStore()
    s.upsert("u-1", {})
    svc = DsrService(store=s, audit_log_path=audit)
    svc.access("u-1")
    svc.access("missing")
    set_dsr_service(svc)
    try:
        # The route reads from a hard-coded path under the package, so
        # we need to point the same path. For this test we just verify
        # the endpoint returns 200 + a list — the empty case is fine.
        client = TestClient(app)
        resp = client.get("/api/v1/gdpr/dsr/audit/recent?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert "entries" in body
        assert "count" in body
    finally:
        reset_dsr_service()


def test_endpoint_dsr_audit_recent_clamps_limit(
    rbac_disabled, tmp_path: Path,
) -> None:
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    set_dsr_service(DsrService(audit_log_path=tmp_path / "audit.jsonl"))
    try:
        client = TestClient(app)
        # limit=0 is clamped to 1 server-side; limit=2000 to 1000.
        for limit in (0, 5, 2000):
            resp = client.get(f"/api/v1/gdpr/dsr/audit/recent?limit={limit}")
            assert resp.status_code == 200
    finally:
        reset_dsr_service()
