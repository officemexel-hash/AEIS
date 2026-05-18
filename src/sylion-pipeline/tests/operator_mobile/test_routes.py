import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.governance.ticket import GovernanceTicket, reset_ticket_store
from sylion.governance.tickets import submit
from sylion.operator_mobile import (
    reset_operator_mobile_bridge,
    reset_operator_mobile_dispatcher,
    reset_operator_mobile_store,
)
from sylion.security.audit_trail_aggregator import (
    get_audit_trail_aggregator,
    reset_audit_trail_aggregator,
)


def _load_router():
    routes_path = Path(__file__).resolve().parents[2] / "sylion" / "api" / "operator_mobile_routes.py"
    spec = importlib.util.spec_from_file_location("b5_operator_mobile_routes_test_module", routes_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.router


@pytest.fixture(autouse=True)
def _reset_singletons():
    reset_ticket_store()
    reset_operator_mobile_store()
    reset_operator_mobile_bridge()
    reset_operator_mobile_dispatcher()
    reset_audit_trail_aggregator()
    yield
    reset_ticket_store()
    reset_operator_mobile_store()
    reset_operator_mobile_bridge()
    reset_operator_mobile_dispatcher()
    reset_audit_trail_aggregator()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(_load_router())
    return TestClient(app)


def test_bind_list_queue_and_decide_routes(client):
    bind_response = client.post(
        "/api/v1/mobile/devices/bind",
        json={
            "operator_id": "operator-1",
            "device_token": "token-1",
            "platform": "ios",
            "device_label": "iPhone",
        },
    )
    assert bind_response.status_code == 201
    assert bind_response.json()["device"]["device_token"] == "token-1"
    device_id = bind_response.json()["device"]["device_id"]

    ticket_id = submit(
        GovernanceTicket(
            origin="mobile",
            project_id="proj-1",
            decision_class="D3",
            gate_type="blocking",
            priority="P1",
            title="Approve deploy",
            summary="Review queued deployment",
            payload={"operator_id": "operator-1"},
            requested_by="mobile-routes-test",
        )
    )

    devices_response = client.get("/api/v1/mobile/devices", params={"operator_id": "operator-1"})
    assert devices_response.status_code == 200
    assert devices_response.json()["count"] == 1

    queue_response = client.get("/api/v1/mobile/queue", params={"operator_id": "operator-1"})
    assert queue_response.status_code == 200
    assert queue_response.json()["tickets"][0]["ticket_id"] == ticket_id

    detail_response = client.get(
        f"/api/v1/mobile/queue/{ticket_id}",
        params={"operator_id": "operator-1"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["ticket_id"] == ticket_id

    decision_response = client.post(
        f"/api/v1/mobile/queue/{ticket_id}/decision",
        json={
            "decision": "approved",
            "reviewer": "operator-1",
            "reason": "approved from mobile",
            "device_id": device_id,
            "auth_method": "pin",
        },
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["state"] == "approved"
    audit = get_audit_trail_aggregator().query(source="operator_mobile")
    assert audit[0]["metadata"]["ticket_id"] == ticket_id
    assert audit[0]["metadata"]["device_id"] == device_id


def test_mobile_d3_decision_requires_reason_and_bound_device(client):
    bind_response = client.post(
        "/api/v1/mobile/devices/bind",
        json={
            "operator_id": "operator-1",
            "device_token": "token-1",
            "platform": "ios",
        },
    )
    device_id = bind_response.json()["device"]["device_id"]
    ticket_id = submit(
        GovernanceTicket(
            origin="mobile",
            project_id="proj-1",
            decision_class="D4",
            gate_type="production",
            priority="P0",
            title="Approve production action",
            summary="D4 approval must carry rationale.",
            payload={"operator_id": "operator-1"},
            requested_by="mobile-routes-test",
        )
    )

    missing_reason = client.post(
        f"/api/v1/mobile/queue/{ticket_id}/decision",
        json={
            "decision": "approved",
            "reviewer": "operator-1",
            "device_id": device_id,
        },
    )
    assert missing_reason.status_code == 422
    assert "reason is required" in missing_reason.json()["detail"]

    missing_device = client.post(
        f"/api/v1/mobile/queue/{ticket_id}/decision",
        json={
            "decision": "approved",
            "reviewer": "operator-1",
            "reason": "operator confirmed legal and rollback checks",
        },
    )
    assert missing_device.status_code == 422
    assert "device_id is required" in missing_device.json()["detail"]

    wrong_device = client.post(
        f"/api/v1/mobile/queue/{ticket_id}/decision",
        json={
            "decision": "approved",
            "reviewer": "operator-1",
            "reason": "operator confirmed legal and rollback checks",
            "device_id": "other-device",
        },
    )
    assert wrong_device.status_code == 403

    with_reason = client.post(
        f"/api/v1/mobile/queue/{ticket_id}/decision",
        json={
            "decision": "approved",
            "reviewer": "operator-1",
            "reason": "operator confirmed legal and rollback checks",
            "device_id": device_id,
            "auth_method": "biometric",
        },
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["state"] == "approved"


def test_unbind_route_returns_404_for_missing_device(client):
    response = client.delete(
        "/api/v1/mobile/devices/missing-device",
        params={"operator_id": "operator-1"},
    )
    assert response.status_code == 404
