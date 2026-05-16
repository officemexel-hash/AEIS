"""Tests for ``sylion.api.replay_routes`` — sprint 3 B-replay endpoints."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


def test_default_audit_path_matches_producer_root() -> None:
    """REGRESSION (2026-04-28 runtime): _DEFAULT_AUDIT_PATH must point at
    the same dir replay_v2.fork.AUDIT_LOG_PATH writes to.

    Same path-equivalence bug as metrics_v2 / health_v2 — both routes were
    using parents[1] (sylion/logs/v2) but producers write to parents[2]
    (logs/v2). Pin the equivalence to fail-fast on future drift.
    """
    from sylion.api.replay_routes import _DEFAULT_AUDIT_PATH
    import sylion.aeis_v2.replay_v2.fork as fork_mod

    expected_root = Path(fork_mod.__file__).resolve().parents[3] / "logs" / "v2"
    assert _DEFAULT_AUDIT_PATH.parent.resolve() == expected_root.resolve(), (
        f"replay_routes _DEFAULT_AUDIT_PATH={_DEFAULT_AUDIT_PATH} "
        f"does not match producer root={expected_root}"
    )


@pytest.fixture
def rbac_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")


@pytest.fixture
def fresh_storage(monkeypatch: pytest.MonkeyPatch):
    """Replace the module-level LRU with a fresh one per test."""
    from sylion.aeis_v2.replay_v2 import ReplayStorageLRU
    import sylion.api.replay_routes as mod

    new_store = ReplayStorageLRU()
    monkeypatch.setattr(mod, "_storage", new_store)
    monkeypatch.setattr(mod, "_storage_get", lambda: new_store)
    return new_store


def _client(rbac_disabled, fresh_storage):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sylion.api.replay_routes import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /terminal/sessions/{sid}/snapshot
# ---------------------------------------------------------------------------


def test_snapshot_endpoint_returns_snapshot_dict(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    body = {"decision_point": 3, "state": {"foo": "bar"}}
    resp = client.post("/api/v1/terminal/sessions/sess-1/snapshot", json=body)
    assert resp.status_code == 200
    out = resp.json()
    assert out["original_session_id"] == "sess-1"
    assert out["decision_point"] == 3
    assert out["state"] == {"foo": "bar"}
    assert out["snapshot_id"]
    assert out["state_hash"]


def test_snapshot_endpoint_negative_decision_point_422(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    body = {"decision_point": -1, "state": {}}
    resp = client.post("/api/v1/terminal/sessions/sess-x/snapshot", json=body)
    assert resp.status_code == 422


def test_snapshot_endpoint_persists_to_storage(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    body = {"decision_point": 0, "state": {"a": 1}}
    resp = client.post("/api/v1/terminal/sessions/s/snapshot", json=body)
    snapshot_id = resp.json()["snapshot_id"]
    # The fixture-backed LRU now contains the snapshot.
    assert fresh_storage.get(snapshot_id) is not None


# ---------------------------------------------------------------------------
# POST /replay/run
# ---------------------------------------------------------------------------


def test_replay_run_unknown_snapshot_404(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    body = {
        "snapshot_id": "deadbeefdeadbeef",
        "replay_decisions": ["a"],
        "replay_final": [1.0],
    }
    resp = client.post("/api/v1/replay/run", json=body)
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "snapshot_not_found"


def test_replay_run_disallowed_model_422(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    snap = client.post(
        "/api/v1/terminal/sessions/s/snapshot",
        json={"decision_point": 0, "state": {}},
    ).json()
    body = {
        "snapshot_id": snap["snapshot_id"],
        "model_override": "/etc/passwd",  # not in whitelist
        "replay_decisions": ["a"],
        "replay_final": [1.0],
    }
    resp = client.post("/api/v1/replay/run", json=body)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "model_override_not_allowed"
    assert "/etc/passwd" in detail["got"]


def test_replay_run_identical_outcomes_zero_divergence(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    snap = client.post(
        "/api/v1/terminal/sessions/s/snapshot",
        json={"decision_point": 0, "state": {"x": 1}},
    ).json()
    body = {
        "snapshot_id": snap["snapshot_id"],
        "original_decisions": ["a", "b", "c"],
        "original_final": [1.0, 0.0, 0.0],
        "replay_decisions": ["a", "b", "c"],
        "replay_final": [1.0, 0.0, 0.0],
    }
    resp = client.post("/api/v1/replay/run", json=body)
    assert resp.status_code == 200
    out = resp.json()
    # Identical → divergence 0.
    assert out["divergence_score"] == pytest.approx(0.0, abs=1e-9)


def test_replay_run_diverging_outcomes_high_divergence(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    snap = client.post(
        "/api/v1/terminal/sessions/s/snapshot",
        json={"decision_point": 0, "state": {}},
    ).json()
    body = {
        "snapshot_id": snap["snapshot_id"],
        "original_decisions": ["a", "b"],
        "original_final": [1.0, 0.0],
        "replay_decisions": ["x", "y"],
        "replay_final": [0.0, 1.0],
        "model_override": "claude-opus-4.7",
    }
    resp = client.post("/api/v1/replay/run", json=body)
    assert resp.status_code == 200
    assert resp.json()["divergence_score"] == pytest.approx(1.0, abs=1e-6)


def test_replay_run_strips_dunder_context_keys(
    rbac_disabled, fresh_storage,
) -> None:
    """Per Kimi k3 finding — dunder keys filtered before forwarding."""
    client = _client(rbac_disabled, fresh_storage)
    snap = client.post(
        "/api/v1/terminal/sessions/s/snapshot",
        json={"decision_point": 0, "state": {}},
    ).json()
    body = {
        "snapshot_id": snap["snapshot_id"],
        "original_decisions": ["a"],
        "original_final": [1.0],
        "replay_decisions": ["a"],
        "replay_final": [1.0],
        "context_override": {
            "feature_flag": "x",
            "__class__": "evil",
            "__init__": "evil",
        },
    }
    resp = client.post("/api/v1/replay/run", json=body)
    assert resp.status_code == 200
    out = resp.json()
    # The audit row should NOT carry __class__ in context_override.
    ctx = out.get("context_override") or {}
    assert "__class__" not in ctx
    assert "__init__" not in ctx
    assert ctx.get("feature_flag") == "x"


def test_replay_run_short_snapshot_id_422(
    rbac_disabled, fresh_storage,
) -> None:
    client = _client(rbac_disabled, fresh_storage)
    body = {
        "snapshot_id": "abc",  # too short, Pydantic min_length=8
        "replay_decisions": ["a"],
        "replay_final": [1.0],
    }
    resp = client.post("/api/v1/replay/run", json=body)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /replay/list
# ---------------------------------------------------------------------------


def test_list_replays_missing_audit_returns_empty(
    rbac_disabled, fresh_storage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import sylion.api.replay_routes as mod

    monkeypatch.setattr(mod, "_audit_path", lambda: tmp_path / "absent.jsonl")
    client = _client(rbac_disabled, fresh_storage)
    resp = client.get("/api/v1/replay/list?limit=10")
    assert resp.status_code == 200
    assert resp.json() == {"entries": [], "count": 0}


def test_list_replays_returns_chained_content(
    rbac_disabled, fresh_storage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Populate a chained audit JSONL then read via the endpoint."""
    from sylion.aeis_v2.audit_chain import append_to_chain

    audit = tmp_path / "replay_fork.jsonl"
    append_to_chain(audit, {"kind": "replay_fork.run", "snapshot_id": "s1"})
    append_to_chain(audit, {"kind": "replay_fork.run", "snapshot_id": "s2"})

    import sylion.api.replay_routes as mod

    monkeypatch.setattr(mod, "_audit_path", lambda: audit)

    client = _client(rbac_disabled, fresh_storage)
    resp = client.get("/api/v1/replay/list?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    ids = [e["snapshot_id"] for e in body["entries"]]
    assert ids == ["s1", "s2"]


def test_list_replays_clamps_limit(
    rbac_disabled, fresh_storage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import sylion.api.replay_routes as mod

    audit = tmp_path / "rf.jsonl"
    monkeypatch.setattr(mod, "_audit_path", lambda: audit)
    client = _client(rbac_disabled, fresh_storage)

    # Limit clamps at both ends without raising.
    for limit in (-1, 0, 5, 999_999):
        resp = client.get(f"/api/v1/replay/list?limit={limit}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Round-trip integration — snapshot → run → list
# ---------------------------------------------------------------------------


def test_snapshot_then_run_then_list_chain_intact(
    rbac_disabled, fresh_storage, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """End-to-end: snapshot, run replay, then read the audit list."""
    from sylion.aeis_v2.audit_chain import verify_chain

    audit = tmp_path / "replay_fork.jsonl"
    # Override BOTH the route's audit path AND the ReplayFork's audit path.
    import sylion.api.replay_routes as mod
    import sylion.aeis_v2.replay_v2.fork as fork_mod

    monkeypatch.setattr(mod, "_audit_path", lambda: audit)
    monkeypatch.setattr(fork_mod, "AUDIT_LOG_PATH", audit)

    client = _client(rbac_disabled, fresh_storage)
    snap = client.post(
        "/api/v1/terminal/sessions/sess-A/snapshot",
        json={"decision_point": 5, "state": {"phase": "compile"}},
    ).json()

    resp = client.post(
        "/api/v1/replay/run",
        json={
            "snapshot_id": snap["snapshot_id"],
            "original_decisions": ["a"],
            "original_final": [1.0],
            "replay_decisions": ["a"],
            "replay_final": [1.0],
        },
    )
    assert resp.status_code == 200

    list_resp = client.get("/api/v1/replay/list?limit=10")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] >= 1
    assert verify_chain(audit) == []
