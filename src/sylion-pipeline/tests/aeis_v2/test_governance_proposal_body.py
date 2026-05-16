"""Regression test for POST /api/v1/governance/proposals body shape.

Bug fixed 2026-04-28: the route signature used bare query parameters
(``title: str, description: str, source_plan: str``) which FastAPI
interprets as ``Query()``. The frontend ``api.createProposal()`` sends
``{title, description, scope}`` as a JSON body, so every wizard at
/governance got a 422 ("Field required: query.title").

Fix accepts BOTH a JSON body (preferred — body wins if both present) and
the legacy query-param style (preserved for tests/test_api_integration.py).
"""
from __future__ import annotations

import pytest


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    from fastapi.testclient import TestClient
    from sylion.api.app import app

    return TestClient(app)


def test_proposal_via_json_body_201(client) -> None:
    """Frontend-style JSON body must succeed."""
    resp = client.post(
        "/api/v1/governance/proposals",
        json={
            "title": "Body-mode proposal",
            "description": "Submitted as JSON body, the way the wizard does it.",
            "scope": "pipeline",
        },
    )
    assert resp.status_code == 201, resp.text
    out = resp.json()
    assert "proposal_id" in out
    assert out.get("decision_class") in {"D0", "D1", "D2", "D3", "D4", "D5"}


def test_proposal_via_query_params_still_works(client) -> None:
    """Legacy query-param style preserved for existing integration tests."""
    resp = client.post(
        "/api/v1/governance/proposals",
        params={
            "title": "Query-mode proposal",
            "description": "Backwards-compat path for tests/test_api_integration.py.",
            "source_plan": "M1",
        },
    )
    assert resp.status_code == 201, resp.text
    assert "proposal_id" in resp.json()


def test_proposal_rejects_missing_title(client) -> None:
    """Body without title → 422 with structured error."""
    resp = client.post(
        "/api/v1/governance/proposals",
        json={"description": "no title"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail.get("error") == "missing_required_fields"
    assert detail.get("got_title") is False
    assert detail.get("got_description") is True


def test_proposal_rejects_missing_description(client) -> None:
    """Body without description → 422."""
    resp = client.post(
        "/api/v1/governance/proposals",
        json={"title": "no desc"},
    )
    assert resp.status_code == 422


def test_proposal_body_wins_over_query(client) -> None:
    """If both body and query params are present, body takes precedence."""
    resp = client.post(
        "/api/v1/governance/proposals?title=from-query&description=from-query",
        json={"title": "from-body", "description": "from-body-desc"},
    )
    assert resp.status_code == 201
    pid = resp.json()["proposal_id"]
    # Read it back and confirm body wins.
    detail = client.get(f"/api/v1/governance/proposals/{pid}")
    assert detail.status_code == 200
    assert detail.json().get("title") == "from-body"


def test_proposal_scope_field_accepted(client) -> None:
    """Frontend's ``scope`` field is accepted (it's part of the body model
    even though the underlying DecisionProposal doesn't store it as a
    distinct column — it's preserved in the body for forward compatibility)."""
    resp = client.post(
        "/api/v1/governance/proposals",
        json={
            "title": "scope test",
            "description": "ensure scope=council doesn't 422",
            "scope": "council",
        },
    )
    assert resp.status_code == 201
