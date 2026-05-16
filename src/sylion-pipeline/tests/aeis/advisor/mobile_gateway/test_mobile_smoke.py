"""Smoke tests for the AEIS advisor mobile gateway (Etap 1 stub).

Golden minimums per `aeis.advisor.mobile_gateway.json` manifest:
  - cards_endpoint_returns_paginated_list
  - card_detail_returns_envelope_when_card_exists
  - card_detail_returns_404_when_missing
  - card_action_accepts_when_low_risk
  - card_action_requires_biometric_when_d3_or_higher
  - auth_failure_returns_401
  - sync_snapshot_returns_expected_shape
  - unimplemented_endpoints_return_501
  - request_handled_event_emitted_after_successful_call
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SYLION_RBAC_DISABLED", "1")
os.environ.setdefault("SYLION_RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("GOOGLE_API_KEY", "")

from sylion.aeis.advisor.engine._db import (
    insert_recommendation,
    reset_engine_db,
)
from sylion.aeis.advisor.engine._models import (
    AdvisorCardEnvelope,
    AdvisorCardHeader,
    DecisionCard,
    confidence_label_for,
)
from sylion.aeis.advisor.engine.service import reset_engine_service
from sylion.aeis.advisor.mobile_gateway import (
    build_mobile_router,
    reset_mobile_router,
)


_OPERATOR_ID = "op-mobile-1"
_DEVICE_ID = "device-test-1"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("SYLION_ADVISOR_ENGINE_SQLITE", str(tmp_path / "engine.db"))
    reset_engine_db()
    reset_engine_service()
    reset_mobile_router()
    yield
    reset_engine_db()
    reset_engine_service()
    reset_mobile_router()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(build_mobile_router())
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _make_token(operator_id: str = _OPERATOR_ID, device_id: str = _DEVICE_ID) -> str:
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode("utf-8"))
    payload = _b64url(json.dumps({"sub": operator_id, "device_id": device_id}).encode("utf-8"))
    signature = _b64url(b"stub")
    return f"{header}.{payload}.{signature}"


def _auth_headers(biometric: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {_make_token()}"}
    if biometric:
        headers["X-Biometric-Verified"] = "true"
    return headers


def _seed_card(
    *,
    card_id: str,
    operator_id: str = _OPERATOR_ID,
    d_level: str = "D1",
    risk_level: str = "low",
) -> AdvisorCardEnvelope:
    header = AdvisorCardHeader(
        card_id=card_id,
        card_type="decision",
        title=f"card {card_id}",
        rationale="seeded for tests",
        confidence_score=0.7,
        confidence_label=confidence_label_for(0.7),
        risk_level=risk_level,
        project_domain="software",
        project_type="research",
        d_level=d_level,
        operator_id=operator_id,
        sources=["rule_engine"],
        llm_judge_audit_id="aud-1",
    )
    body = DecisionCard(
        recommendation="seed", recommendation_type="REC_TYPE_SAMPLE",
    )
    env = AdvisorCardEnvelope(header=header, decision=body)
    insert_recommendation(env)
    return env


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cards_endpoint_returns_paginated_list(client: TestClient):
    _seed_card(card_id="c-1")
    _seed_card(card_id="c-2")

    resp = client.get("/mobile/v1/cards", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert "cards" in body
    assert body["total"] == 2
    returned_ids = {c["header"]["card_id"] for c in body["cards"]}
    assert returned_ids == {"c-1", "c-2"}


def test_card_detail_returns_envelope_when_card_exists(client: TestClient):
    _seed_card(card_id="c-detail")
    resp = client.get("/mobile/v1/cards/c-detail", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["header"]["card_id"] == "c-detail"
    assert body["envelope_version"] == "1.0.0"


def test_card_detail_returns_404_when_missing(client: TestClient):
    resp = client.get("/mobile/v1/cards/nope", headers=_auth_headers())
    assert resp.status_code == 404


def test_card_action_accepts_when_low_risk(client: TestClient):
    _seed_card(card_id="c-low", d_level="D1")
    resp = client.post(
        "/mobile/v1/cards/c-low/actions",
        headers=_auth_headers(),
        json={"action": "accept", "operator_note": "ok"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["card_id"] == "c-low"
    assert body["biometric_required"] is False


def test_card_action_requires_biometric_when_d3_or_higher(client: TestClient):
    _seed_card(card_id="c-high", d_level="D3", risk_level="high")

    # Without biometric -> 401 + biometric_step_up event
    resp = client.post(
        "/mobile/v1/cards/c-high/actions",
        headers=_auth_headers(biometric=False),
        json={"action": "accept"},
    )
    assert resp.status_code == 401
    assert "biometric" in resp.json()["detail"].lower()

    # With biometric -> 200
    resp_ok = client.post(
        "/mobile/v1/cards/c-high/actions",
        headers=_auth_headers(biometric=True),
        json={"action": "accept"},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["biometric_required"] is True


def test_auth_failure_returns_401(client: TestClient):
    # No Authorization header
    resp = client.get("/mobile/v1/cards")
    assert resp.status_code == 401

    # Malformed bearer token
    resp = client.get("/mobile/v1/cards", headers={"Authorization": "Bearer not.a.jwt-payload"})
    assert resp.status_code == 401

    # Missing 'sub'/'operator_id' claim
    bad_payload = _b64url(json.dumps({"device_id": _DEVICE_ID}).encode("utf-8"))
    bad_token = f"{_b64url(b'{}')}.{bad_payload}.{_b64url(b'sig')}"
    resp = client.get("/mobile/v1/cards", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401


def test_sync_snapshot_returns_expected_shape(client: TestClient):
    _seed_card(card_id="c-sync-1")
    resp = client.get("/mobile/v1/sync/snapshot", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "operator_id",
        "cards",
        "projects",
        "human_gate_pending",
        "funding_deadlines",
        "settings",
        "snapshot_taken_at",
    ):
        assert key in body
    assert body["operator_id"] == _OPERATOR_ID
    assert any(card["header"]["card_id"] == "c-sync-1" for card in body["cards"])


def test_unimplemented_endpoints_return_501(client: TestClient):
    resp = client.put(
        "/mobile/v1/preferences/some-key",
        headers=_auth_headers(),
        json={"value": "x"},
    )
    assert resp.status_code == 501

    resp = client.post(
        "/mobile/v1/human_gate/ticket-1/decide",
        headers=_auth_headers(),
        json={"decision": "approve", "reviewer": "op"},
    )
    assert resp.status_code == 501


def test_request_handled_event_emitted_after_successful_call(client: TestClient):
    _seed_card(card_id="c-event")

    captured: list[Any] = []

    class _StubBackbone:
        def publish(self, event):
            captured.append(event)
            return event.event_id

    with mock.patch(
        "sylion.core.event_backbone.get_event_backbone",
        return_value=_StubBackbone(),
    ):
        resp = client.get("/mobile/v1/cards/c-event", headers=_auth_headers())

    assert resp.status_code == 200
    topics = [getattr(e, "topic", "") for e in captured]
    assert "aeis.advisor.mobile_gateway.request_handled" in topics
    handled = next(e for e in captured if e.topic == "aeis.advisor.mobile_gateway.request_handled")
    assert handled.payload["operator_id"] == _OPERATOR_ID
    assert handled.payload["status_code"] == 200
    assert handled.payload["path"].endswith("/mobile/v1/cards/c-event")
