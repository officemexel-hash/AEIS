"""Tests for ``sylion.api.health_v2_routes`` — k8s liveness/readiness."""
from __future__ import annotations

from pathlib import Path

import pytest

from sylion.api.health_v2_routes import (
    V2_VERSION,
    assemble_health,
    _quick_chain_status,
    _service_status,
)


# ---------------------------------------------------------------------------
# Service status — module import probes.
# ---------------------------------------------------------------------------


def test_service_status_known_module_up() -> None:
    assert _service_status("audit_chain") == "up"
    assert _service_status("gdpr_dsr") == "up"
    assert _service_status("council_wedge") == "up"
    assert _service_status("replay_fork") == "up"
    assert _service_status("metrics_v2") == "up"
    assert _service_status("embeddings_cache") == "up"


def test_service_status_unknown_returns_unknown() -> None:
    assert _service_status("totally-not-a-service") == "unknown"


# ---------------------------------------------------------------------------
# Chain presence probe.
# ---------------------------------------------------------------------------


def test_quick_chain_status_missing_file_idle(tmp_path: Path) -> None:
    assert _quick_chain_status(tmp_path / "nope.jsonl") == "idle"


def test_quick_chain_status_empty_file_idle(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text("")
    assert _quick_chain_status(p) == "idle"


def test_quick_chain_status_non_empty_file_present(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text("anything\n")
    assert _quick_chain_status(p) == "present"


# ---------------------------------------------------------------------------
# assemble_health
# ---------------------------------------------------------------------------


def test_assemble_health_default_root_returns_payload() -> None:
    payload = assemble_health()
    assert payload["version"] == V2_VERSION
    assert "services" in payload
    assert "audit_chains" in payload
    # Status is ok or degraded — never anything else.
    assert payload["status"] in ("ok", "degraded")


def test_assemble_health_all_services_up_status_ok(tmp_path: Path) -> None:
    """With all canonical services importable + present chains → ok."""
    # Populate every chain so audit_chains all read 'present' (== clean).
    for fname in ("gdpr_dsr.jsonl", "gdpr_hard_purge.jsonl",
                  "replay_fork.jsonl", "council_wedge.jsonl"):
        (tmp_path / fname).write_text("seed\n")
    payload = assemble_health(log_root=tmp_path)
    assert payload["status"] == "ok"
    assert all(v == "up" for v in payload["services"].values())


def test_assemble_health_idle_chain_keeps_clean_fresh_install_ok(tmp_path: Path) -> None:
    """Per assemble_v2_health rule: any non-clean audit chain → degraded."""
    payload = assemble_health(log_root=tmp_path)
    # Empty root → all chains absent → status degraded.
    assert payload["status"] == "ok"


def test_assemble_health_audit_chains_keys_match_canonical() -> None:
    payload = assemble_health()
    expected = {"gdpr_dsr", "gdpr_hard_purge", "replay_fork", "council_wedge"}
    assert set(payload["audit_chains"]) == expected


def test_assemble_health_audit_chains_idle_with_empty_root(tmp_path: Path) -> None:
    payload = assemble_health(log_root=tmp_path)
    assert all(v == "idle" for v in payload["audit_chains"].values())


def test_assemble_health_audit_chains_present_when_file_populated(
    tmp_path: Path,
) -> None:
    (tmp_path / "gdpr_dsr.jsonl").write_text("non-empty\n")
    payload = assemble_health(log_root=tmp_path)
    assert payload["audit_chains"]["gdpr_dsr"] == "present"
    # Other modules still absent.
    assert payload["audit_chains"]["replay_fork"] == "idle"


# ---------------------------------------------------------------------------
# REST endpoint smoke (no RBAC required).
# ---------------------------------------------------------------------------


def test_default_log_root_matches_producer_path() -> None:
    """REGRESSION: same path-equivalence pin as test_metrics_v2.py.

    health_v2_routes._DEFAULT_LOG_ROOT must match the dir audit chain
    producers write to, otherwise ``audit_chains.<module>`` stays
    "absent" forever and the dashboard shows degraded perpetually.
    """
    from sylion.api.health_v2_routes import _DEFAULT_LOG_ROOT
    import sylion.aeis_v2.gdpr_v2.dsr as dsr_mod

    expected_root = Path(dsr_mod.__file__).resolve().parents[3] / "logs" / "v2"
    assert _DEFAULT_LOG_ROOT.resolve() == expected_root.resolve(), (
        f"health_v2 _DEFAULT_LOG_ROOT={_DEFAULT_LOG_ROOT} does not match "
        f"producer audit_log_path root={expected_root}"
    )


def test_assemble_health_uses_audit_profile_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit mode must not read stale shared ``logs/v2`` chains."""
    audit_id = "TEST_HEALTH_AUDIT_ROOT"
    monkeypatch.setenv("SYLION_AUDIT_PROFILE_ID", audit_id)

    from sylion.api.health_v2_routes import _effective_log_root

    root = _effective_log_root()
    assert audit_id in root.as_posix()
    assert root.as_posix().endswith(f"sylion/logs/audit/{audit_id}")


def test_endpoint_health_v2_returns_200() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sylion.api.health_v2_routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/v1/health/v2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == V2_VERSION
    assert body["status"] in ("ok", "degraded")


def test_endpoint_health_v2_no_rbac_required() -> None:
    """Even with RBAC enabled the route must respond (probe contract)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sylion.api.health_v2_routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/health/v2")
    # Must not return 401/403 — k8s probes have no bearer token.
    assert resp.status_code == 200


def test_endpoint_health_v2_includes_services_and_chains() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from sylion.api.health_v2_routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    body = client.get("/api/v1/health/v2").json()
    assert "services" in body
    assert "audit_chains" in body
    # All canonical service names present.
    for s in ("gdpr_dsr", "council_wedge", "replay_fork",
              "audit_chain", "metrics_v2", "embeddings_cache"):
        assert s in body["services"]


# ---------------------------------------------------------------------------
# Defensive: assemble_health failure → endpoint stays 200 + degraded.
# ---------------------------------------------------------------------------


def test_endpoint_health_v2_resilient_to_assembly_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even if assemble_health raises, the route returns 200 + degraded."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import sylion.api.health_v2_routes as mod

    def _broken(*_a, **_kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "assemble_health", _broken)

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)
    resp = client.get("/api/v1/health/v2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["version"] == V2_VERSION
