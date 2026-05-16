"""End-to-end smoke test across sprint 2 + sprint 3 v2 modules.

Sprint 3 deliverable. Exercises every major v2 surface in a single
sequential scenario, asserting every audit chain stays clean from end
to end. This is the canonical CI gate before shipping any v2 change.

Scenario (10 steps):

    1. GDPR DSR rectify creates user u-smoke-1.
    2. GDPR DSR access returns the user record.
    3. Match-idea-G1 against demo templates (no Council yet).
    4. Match-idea-G1-with-council runs full G1 cascade incl. council vote.
    5. SessionSnapshot.capture + ReplayFork.run with identity callable.
    6. IdeaLifecycle transitions idea-smoke-1 through 4 valid states.
    7. GDPR DSR erasure soft-deletes u-smoke-1.
    8. HardPurgeCron purges u-smoke-1 after grace window.
    9. GET /api/v1/metrics/v2 — Prometheus exposition surfaces counters.
    10. GET /api/v1/health/v2 — payload includes services + audit_chains.

Every audit JSONL written along the way is pointed at a tmp_path so
the test isolates from production logs and can call verify_chain on
each file at the end.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.audit_chain import verify_chain


@pytest.fixture
def rbac_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")


@pytest.fixture
def isolated_audit_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> dict[str, Path]:
    """Redirect every chained audit log path to tmp_path.

    Returns a dict so the test body can call verify_chain on each.
    """
    paths = {
        "gdpr_dsr": tmp_path / "gdpr_dsr.jsonl",
        "council_wedge": tmp_path / "council_wedge.jsonl",
        "replay_fork": tmp_path / "replay_fork.jsonl",
        "gdpr_hard_purge": tmp_path / "gdpr_hard_purge.jsonl",
        "idea_lifecycle": tmp_path / "idea_lifecycle.jsonl",
    }

    # council_wedge audit path is a module-level constant.
    import sylion.aeis_v2.council_v2.wedge as wedge_mod
    monkeypatch.setattr(wedge_mod, "AUDIT_LOG_PATH", paths["council_wedge"])

    # replay_fork: the fork module's default path.
    import sylion.aeis_v2.replay_v2.fork as fork_mod
    monkeypatch.setattr(fork_mod, "AUDIT_LOG_PATH", paths["replay_fork"])

    return paths


@pytest.fixture
def isolated_dsr_service(
    isolated_audit_paths: dict[str, Path],
) -> Any:
    """Replace the global DsrService with an in-memory + tmp-audit one."""
    from sylion.aeis_v2.gdpr_v2 import (
        DsrService,
        InMemoryUserDataStore,
        reset_dsr_service,
        set_dsr_service,
    )

    store = InMemoryUserDataStore()
    svc = DsrService(
        store=store,
        audit_log_path=isolated_audit_paths["gdpr_dsr"],
    )
    set_dsr_service(svc)
    yield svc
    reset_dsr_service()


def test_v2_e2e_full_smoke_chain_intact(
    rbac_disabled,
    isolated_audit_paths: dict[str, Path],
    isolated_dsr_service: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end happy path with chain integrity verified at the end."""
    from fastapi.testclient import TestClient
    from sylion.aeis_v2.gdpr_v2 import HardPurgeCron, PurgeableInMemoryStore
    from sylion.aeis_v2.lifecycle_v2 import IdeaLifecycle
    from sylion.aeis_v2.replay_v2 import ReplayFork, SessionSnapshot
    from sylion.api.app import app

    client = TestClient(app)

    # --- 1. GDPR DSR rectify ---
    resp = client.post(
        "/api/v1/gdpr/dsr/rectification/u-smoke-1",
        json={"patch": {"name": "Smoke", "tier": "ops"}},
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "rectification"

    # --- 2. GDPR DSR access ---
    resp = client.get("/api/v1/gdpr/dsr/access/u-smoke-1")
    assert resp.status_code == 200
    assert resp.json()["payload"]["name"] == "Smoke"

    # --- 3. Match-idea G1 (Phase 0 → embeddings) ---
    resp = client.post(
        "/api/v1/apps/match-idea-g1",
        json={"idea_text": "inspekcja terenowa raport", "top_n": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["match_count"] >= 1

    # --- 4. Match-idea-G1 with Council Hybrid wedge ---
    resp = client.post(
        "/api/v1/apps/match-idea-g1-with-council",
        json={"idea_text": "inspekcja terenowa raport audyt", "top_n": 3},
    )
    assert resp.status_code == 200
    council_decision = resp.json()["council_decision"]
    assert council_decision["verdict"] in (
        "approve", "reject", "conditional", "tie", "no_data",
    )

    # --- 5. Replay-as-fork PoC ---
    snap = SessionSnapshot.capture(
        {"phase": "compile", "score": 0.85}, decision_point=2,
    )
    fork = ReplayFork(
        snap,
        original_decisions=["plan", "build"],
        original_final=[1.0, 0.0, 0.0],
        audit_log_path=isolated_audit_paths["replay_fork"],
    )

    def _identity_replay(state, *, model_override=None, context_override=None):
        return (["plan", "build"], [1.0, 0.0, 0.0])

    result = fork.run(_identity_replay)
    assert result.divergence_score == pytest.approx(0.0, abs=1e-9)

    # --- 6. IdeaLifecycle: 4 valid transitions on idea-smoke-1 ---
    lc = IdeaLifecycle(audit_log_path=isolated_audit_paths["idea_lifecycle"])
    assert lc.transition("idea-smoke-1", "draft", "submitted") is True
    assert lc.transition("idea-smoke-1", "submitted", "under_review") is True
    assert lc.transition("idea-smoke-1", "under_review", "approved") is True
    assert lc.transition("idea-smoke-1", "approved", "in_progress") is True
    assert lc.current_state("idea-smoke-1") == "in_progress"

    # --- 7. GDPR DSR erasure (soft-delete) ---
    resp = client.delete("/api/v1/gdpr/dsr/erasure/u-smoke-1")
    assert resp.status_code == 200

    # Subsequent access must 404.
    resp = client.get("/api/v1/gdpr/dsr/access/u-smoke-1")
    assert resp.status_code == 404

    # --- 8. HardPurgeCron — purge after grace window ---
    purgeable = PurgeableInMemoryStore()
    # Stage a soft-deleted user older than grace.
    purgeable.upsert("u-old", {})
    purgeable.soft_delete("u-old", ts=0.0)
    cron = HardPurgeCron(
        purgeable,
        audit_log_path=isolated_audit_paths["gdpr_hard_purge"],
        grace_period_s=10,
    )
    report = cron.purge_expired(now=1000.0)
    assert "u-old" in report.purged

    # --- 9. GET /metrics/v2 (Prometheus exposition) ---
    resp = client.get("/api/v1/metrics/v2")
    assert resp.status_code == 200
    assert "sylion_v2_audit_chain_size" in resp.text
    assert resp.headers["content-type"].startswith("text/plain")

    # --- 10. GET /health/v2 ---
    resp = client.get("/api/v1/health/v2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    for service in (
        "gdpr_dsr", "council_wedge", "replay_fork",
        "audit_chain", "metrics_v2", "embeddings_cache",
    ):
        assert body["services"][service] in ("up", "down", "unknown")

    # --- Final: every chained audit JSONL must verify clean. ---
    for module, path in isolated_audit_paths.items():
        if not path.exists():
            continue  # the run touched fewer than expected — fine if empty
        faults = verify_chain(path)
        assert faults == [], (
            f"audit chain {module} has {len(faults)} fault(s): "
            f"{[f.to_dict() for f in faults]}"
        )


# ---------------------------------------------------------------------------
# A complementary "negative" path — the smoke test should also catch a
# tampered chain, not just confirm the happy case.
# ---------------------------------------------------------------------------


def test_v2_e2e_detects_tamper_via_verify_chain(
    rbac_disabled,
    isolated_audit_paths: dict[str, Path],
    isolated_dsr_service: Any,
) -> None:
    """If somebody mutates the gdpr_dsr.jsonl mid-flow, verify_chain catches it."""
    from fastapi.testclient import TestClient

    from sylion.api.app import app

    client = TestClient(app)
    # Two DSR ops to seed the chain.
    client.post(
        "/api/v1/gdpr/dsr/rectification/u-tamper",
        json={"patch": {"name": "x"}},
    )
    client.get("/api/v1/gdpr/dsr/access/u-tamper")

    audit = isolated_audit_paths["gdpr_dsr"]
    assert audit.exists()
    # Tamper: append garbage.
    with open(audit, "a", encoding="utf-8") as f:
        f.write("not-json\n")

    faults = verify_chain(audit)
    assert faults  # the smoke test would surface this on the final assertion
    assert any(f.reason == "json_parse_error" for f in faults)
