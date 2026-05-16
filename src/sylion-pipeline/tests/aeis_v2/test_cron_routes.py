"""Cron-mode metrics — Phase 0 route tests.

Covers the read-only widget endpoint exposed under ``/api/v1/cron``:

- ``GET /api/v1/cron/status`` — total commits + recent + drafts size.

The endpoint shells out to ``git log`` and walks ``docs/v2/_drafts``;
both are wrapped defensively so the route returns sane defaults when
git is unavailable (CI containers, frozen runners) or the drafts tree
was pruned. The tests therefore only assert *shape* — no concrete
counts, since they vary per checkout.

Each test mounts only the cron router on a fresh ``FastAPI()`` instance
to skip the full lifespan (PG pools, demo seeders).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.api.cron_routes import router as cron_router


def _client() -> TestClient:
    """Return a TestClient with only the cron router mounted (no lifespan)."""
    api = FastAPI()
    api.include_router(cron_router)
    return TestClient(api)


# --------------------------------------------------------------------------
# GET /api/v1/cron/status — shape-only checks
# --------------------------------------------------------------------------


def test_get_cron_status_returns_total_commits():
    """Endpoint returns a dict with ``total_commits`` as a non-negative int.

    Subprocess can fail in CI (no git on PATH) — defensive wrapper must
    coerce that into a clean ``0`` rather than raising.
    """
    client = _client()
    r = client.get("/api/v1/cron/status")
    assert r.status_code == 200
    body = r.json()
    assert "total_commits" in body
    assert isinstance(body["total_commits"], int)
    assert body["total_commits"] >= 0


def test_get_cron_status_recent_commits_max_5():
    """``recent_commits`` is a list of <= 5 entries, each with hash+subject."""
    client = _client()
    r = client.get("/api/v1/cron/status")
    assert r.status_code == 200
    body = r.json()
    assert "recent_commits" in body
    assert isinstance(body["recent_commits"], list)
    assert len(body["recent_commits"]) <= 5
    for entry in body["recent_commits"]:
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"hash", "subject"}
        assert isinstance(entry["hash"], str)
        assert isinstance(entry["subject"], str)


def test_get_cron_status_drafts_size_kb_is_int():
    """``drafts_size_kb`` is a non-negative int (KB)."""
    client = _client()
    r = client.get("/api/v1/cron/status")
    assert r.status_code == 200
    body = r.json()
    assert "drafts_size_kb" in body
    assert isinstance(body["drafts_size_kb"], int)
    assert body["drafts_size_kb"] >= 0
