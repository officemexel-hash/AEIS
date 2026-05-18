"""W14 BE-8 backend extensions — coverage matrix.

Bundles 9+ tests for the BE-8.{1,2,3,4,5} round-meta backend gaps:

* BE-8.1 — POST /api/v1/ideas/{id}/clarification-response (F-Idea1-2 P2).
* BE-8.2 — VALID_ORIGINS now allows ``round_meta`` (F-Idea1-3).
* BE-8.3 — round_meta_hooks promote project.phase post-approve (F-Idea6-2).
* BE-8.4 — POST/GET/DELETE/test on /api/v1/cloud-connectors (F-Hetzner-1 /
  F-Connectors-1).
* BE-8.5 — POST /api/v1/secrets/create with masking (F-A3-1 P1).

Each test is hermetic: in-memory SQLite stores + a fresh FastAPI app
mounted with only the router under test, so failures cannot bleed
between cases or pollute the operator data plane.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.api.cloud_connectors_routes as cloud_connectors_routes
import sylion.api.idea_routes as idea_routes
import sylion.api.secret_routes as secret_routes
import sylion.project_mode.round_meta_hooks as rm_hooks
from sylion.aeis_v2 import audit_profile as audit_profile_mod
from sylion.cognitive.idea_vault import IdeaVault
from sylion.governance import tickets as tickets_mod
from sylion.governance.ticket import (
    GovernanceTicket,
    VALID_ORIGINS,
    reset_ticket_store,
)
from sylion.project_mode import store as store_mod
from sylion.project_mode.store import ProjectModeStore
from sylion.security.cloud_connectors import (
    ALLOWED_PROVIDERS,
    CloudConnectorStore,
    reset_cloud_connector_store,
)
from sylion.security.secret_provider import reset_secret_provider


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_idea_vault(monkeypatch: pytest.MonkeyPatch) -> IdeaVault:
    """Mount a fresh in-memory IdeaVault behind the route's lazy accessor."""
    vault = IdeaVault(db_path=":memory:")
    monkeypatch.setattr(idea_routes, "_idea_vault", vault)
    # Silence the lifecycle event emitter so the in-memory test does not
    # need a configured event router.
    monkeypatch.setattr(
        idea_routes,
        "publish_lifecycle_event",
        lambda *_args, **_kwargs: "evt-test",
    )
    return vault


@pytest.fixture
def idea_client(isolated_idea_vault: IdeaVault) -> TestClient:
    api = FastAPI()
    api.include_router(idea_routes.router)
    return TestClient(api)


@pytest.fixture
def cloud_connector_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    store = CloudConnectorStore(db_path=":memory:")
    reset_cloud_connector_store()
    monkeypatch.setattr(cloud_connectors_routes, "_store", store)
    api = FastAPI()
    api.include_router(cloud_connectors_routes.router)
    return TestClient(api)


@pytest.fixture
def secret_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    reset_secret_provider()
    # The route's lazy cache must be cleared so each test gets a fresh
    # provider instance bound to the reset singleton.
    monkeypatch.setattr(secret_routes, "_provider", None)
    api = FastAPI()
    api.include_router(secret_routes.router)
    return TestClient(api)


@pytest.fixture
def isolated_store(monkeypatch: pytest.MonkeyPatch) -> ProjectModeStore:
    fresh = ProjectModeStore(db_path=":memory:")
    fresh._get_conn()
    monkeypatch.setattr(store_mod, "_store", fresh)
    monkeypatch.setattr(store_mod, "get_project_mode_store", lambda: fresh)
    return fresh


@pytest.fixture
def chain_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    target = tmp_path / "chains"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        audit_profile_mod, "resolve_audit_chain_dir", lambda *a, **kw: target,
    )
    return target


@pytest.fixture
def round_meta_env(
    isolated_store: ProjectModeStore, chain_dir: Path,
):
    reset_ticket_store(":memory:")
    tickets_mod.clear_post_resolve_hooks()
    rm_hooks._REGISTERED = False
    rm_hooks.register_round_meta_hook()
    yield isolated_store
    tickets_mod.clear_post_resolve_hooks()
    rm_hooks._REGISTERED = False
    reset_ticket_store(":memory:")


def _make_project(
    store: ProjectModeStore,
    *,
    canon_frozen: bool = False,
    masterplan_frozen: bool = False,
) -> dict[str, Any]:
    return store.upsert_project({
        "project_id": "proj_be8",
        "title": "BE-8",
        "idea": "demo",
        "constraints": "",
        "canonical_book": "Source of truth body.",
        "masterplan": "Masterplan body.",
        "approvals": {
            "book": canon_frozen,
            "operating_model": masterplan_frozen,
        },
        "canon_frozen_at": 1.0 if canon_frozen else None,
        "masterplan_frozen_at": 1.0 if masterplan_frozen else None,
    })


def _submit_freeze(action: str, target: str, **payload_extras: Any) -> str:
    payload: dict[str, Any] = {"action": action, "target": target}
    payload.update(payload_extras)
    return tickets_mod.submit(GovernanceTicket(
        origin="round_meta",
        project_id="proj_be8",
        decision_class="D3",
        gate_type="production",
        priority="P1",
        title=f"freeze {target}",
        summary=f"freeze {target} on proj_be8",
        payload=payload,
        requested_by="be8_test",
    ))


# ---------------------------------------------------------------------------
# BE-8.1 — clarification response
# ---------------------------------------------------------------------------


def test_clarification_response_appends_to_notes(
    idea_client: TestClient, isolated_idea_vault: IdeaVault,
) -> None:
    created = isolated_idea_vault.create_idea(
        title="needs clarity", description="x", author="op",
    )
    idea_id = created["idea_id"]
    isolated_idea_vault.submit_for_clarification(
        idea_id, notes="please answer Q1", actor="auditor",
    )

    r = idea_client.post(
        f"/api/v1/ideas/{idea_id}/clarification-response",
        json={"response": "answer to Q1", "responder": "alice"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    notes = str(body.get("clarification_notes") or "")
    assert "please answer Q1" in notes  # preserves prior content
    assert "alice: answer to Q1" in notes
    # Lifecycle log row written even though status did not change.
    history = isolated_idea_vault.get_lifecycle_history(idea_id)
    appended = [
        h for h in history
        if h.get("rationale") == "clarification response appended"
    ]
    assert len(appended) >= 1


def test_clarification_response_404(
    idea_client: TestClient,
) -> None:
    r = idea_client.post(
        "/api/v1/ideas/missing-id/clarification-response",
        json={"response": "anything"},
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# BE-8.2 — round_meta origin allowed
# ---------------------------------------------------------------------------


def test_round_meta_origin_allowed(round_meta_env) -> None:
    assert "round_meta" in VALID_ORIGINS
    _make_project(round_meta_env)
    ticket_id = _submit_freeze("project_freeze", "canon")
    ticket = tickets_mod.fetch_by_id(ticket_id)
    assert ticket is not None
    assert ticket.origin == "round_meta"


# ---------------------------------------------------------------------------
# BE-8.3 — phase auto-promote
# ---------------------------------------------------------------------------


def test_phase_auto_promote_after_canon_freeze_approve(
    round_meta_env,
) -> None:
    _make_project(round_meta_env)
    ticket_id = _submit_freeze("project_freeze", "canon")
    assert tickets_mod.resolve(
        ticket_id,
        "approved",
        reason="BE-8 canon freeze approved by operator",
        reviewer="op1",
    ) is True
    project = round_meta_env.get_project("proj_be8")
    assert project is not None
    assert project["phase"] == "masterplan_in_progress"
    assert project["canon_frozen_at"]


def test_phase_auto_promote_after_masterplan_freeze_approve(
    round_meta_env,
) -> None:
    _make_project(round_meta_env, canon_frozen=True)
    ticket_id = _submit_freeze("project_freeze", "masterplan")
    assert tickets_mod.resolve(
        ticket_id,
        "approved",
        reason="BE-8 masterplan freeze approved by operator",
        reviewer="op1",
    ) is True
    project = round_meta_env.get_project("proj_be8")
    assert project is not None
    assert project["phase"] == "build_authorization"
    assert project["masterplan_frozen_at"]


def test_phase_auto_promote_after_build_authorize_approve(
    round_meta_env,
) -> None:
    _make_project(round_meta_env, canon_frozen=True, masterplan_frozen=True)
    ticket_id = _submit_freeze(
        "project_build_authorize", "build",
        cost_cap_usd=25.0, autonomy_level="L1",
    )
    assert tickets_mod.resolve(
        ticket_id,
        "approved",
        reason="BE-8 build authorization approved by operator",
        reviewer="op1",
    ) is True
    project = round_meta_env.get_project("proj_be8")
    assert project is not None
    assert project["phase"] in {"execution", "broadcast", "governance"}
    assert project["status"] in {"building", "completed", "blocked_on_audit"}
    assert project["build_authorized_at"]


# ---------------------------------------------------------------------------
# BE-8.4 — cloud connectors
# ---------------------------------------------------------------------------


def test_connectors_register_and_list(
    cloud_connector_client: TestClient,
) -> None:
    connector_token = "mask-me-1234"
    # POST register
    r = cloud_connector_client.post(
        "/api/v1/cloud-connectors",
        json={
            "provider": "hetzner",
            "name": "prod-cluster",
            "credentials": {"token": connector_token, "project": "p1"},
            "scope": "prod",
        },
    )
    assert r.status_code == 201, r.text
    payload = r.json()
    connector_id = payload["connector_id"]
    masked = payload["credentials_masked"]
    # Token masked, project preserved.
    assert masked["token"].startswith("***") and masked["token"].endswith("1234")
    assert masked["project"] == "p1"

    # GET list
    r = cloud_connector_client.get("/api/v1/cloud-connectors")
    assert r.status_code == 200
    items = r.json()["connectors"]
    assert len(items) == 1
    assert items[0]["connector_id"] == connector_id
    # Plaintext credentials must not leak in list output.
    raw = r.text
    assert connector_token not in raw

    # DELETE
    r = cloud_connector_client.delete(
        f"/api/v1/cloud-connectors/{connector_id}",
    )
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    # 404 on subsequent get
    r = cloud_connector_client.get(
        f"/api/v1/cloud-connectors/{connector_id}",
    )
    assert r.status_code == 404


def test_connectors_register_rejects_unknown_provider(
    cloud_connector_client: TestClient,
) -> None:
    r = cloud_connector_client.post(
        "/api/v1/cloud-connectors",
        json={
            "provider": "no-such-provider",
            "name": "x",
            "credentials": {"token": "abc"},
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "unsupported provider" in detail
    # All 8 blessed providers must surface from the providers endpoint.
    r = cloud_connector_client.get("/api/v1/cloud-connectors/providers")
    assert r.status_code == 200
    providers = r.json()["providers"]
    assert set(providers) == ALLOWED_PROVIDERS


def test_connectors_test_endpoint(
    cloud_connector_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Register an AWS connector (unverifiable provider → no-op success).
    r = cloud_connector_client.post(
        "/api/v1/cloud-connectors",
        json={
            "provider": "aws",
            "name": "main",
            "credentials": {
                "access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            },
            "scope": "default",
        },
    )
    assert r.status_code == 201, r.text
    connector_id = r.json()["connector_id"]

    # POST /test should always return ok=True for the no-op providers.
    r = cloud_connector_client.post(
        f"/api/v1/cloud-connectors/{connector_id}/test",
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "ok"
    assert body["provider"] == "aws"

    # last_test_at / last_test_status updated on the record.
    r = cloud_connector_client.get(
        f"/api/v1/cloud-connectors/{connector_id}",
    )
    assert r.status_code == 200
    record = r.json()
    assert record["last_test_status"] == "ok"
    assert record["last_test_at"]


# ---------------------------------------------------------------------------
# BE-8.5 — secrets create
# ---------------------------------------------------------------------------


def test_secrets_post_creates_entry(secret_client: TestClient) -> None:
    r = secret_client.post(
        "/api/v1/secrets/create",
        json={
            "name": "anthropic_api_key",
            "value": "sk-ant-xxxx-yyyy-zzzz",
            "scope": "production",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "anthropic_api_key"
    assert body["scope"] == "production"
    assert body["secret_id"] == "anthropic_api_key"
    assert body["stored"] is True
    # Plaintext must not be echoed in the response.
    assert "sk-ant" not in r.text

    # Listing must show the new secret without value.
    r = secret_client.get("/api/v1/secrets/list?scope=production")
    assert r.status_code == 200
    secrets = r.json()["secrets"]
    assert any(s.get("name") == "anthropic_api_key" for s in secrets)


def test_secrets_create_rejects_empty(secret_client: TestClient) -> None:
    r = secret_client.post(
        "/api/v1/secrets/create",
        json={"name": "", "value": "x"},
    )
    assert r.status_code == 400
