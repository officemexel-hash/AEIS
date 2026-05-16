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
    yield
    reset_ticket_store()
    reset_operator_mobile_store()
    reset_operator_mobile_bridge()
    reset_operator_mobile_dispatcher()


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
        json={"decision": "approved", "reviewer": "operator-1", "reason": "approved from mobile"},
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["state"] == "approved"


def test_unbind_route_returns_404_for_missing_device(client):
    response = client.delete(
        "/api/v1/mobile/devices/missing-device",
        params={"operator_id": "operator-1"},
    )
    assert response.status_code == 404
