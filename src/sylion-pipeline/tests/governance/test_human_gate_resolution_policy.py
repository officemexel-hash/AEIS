from fastapi import FastAPI
from fastapi.testclient import TestClient

import sylion.api.gates_routes as gates_routes
from sylion.governance.human_gate import reset_human_gate
from sylion.governance.tickets import fetch_by_id, reset_ticket_store


def _client(monkeypatch):
    reset_ticket_store(":memory:")
    monkeypatch.setattr(gates_routes, "_human_gate", reset_human_gate(":memory:"))
    app = FastAPI()
    app.include_router(gates_routes.router)
    return TestClient(app)


def test_legacy_human_gate_d3_resolution_requires_rationale(monkeypatch):
    client = _client(monkeypatch)

    created = client.post(
        "/api/v1/gates/human/requests",
        json={
            "gate_id": "production:deploy",
            "title": "Approve production deploy",
            "context_json": {"decision_class": "D4"},
            "requested_by": "test",
        },
    )
    assert created.status_code == 201
    request_id = created.json()["request_id"]

    missing_reason = client.post(
        "/api/v1/gates/human/reviews",
        json={
            "request_id": request_id,
            "reviewer": "operator",
            "decision": "approved",
        },
    )
    assert missing_reason.status_code == 422
    assert "reason is required" in missing_reason.json()["detail"]
    assert fetch_by_id(request_id).state == "pending"

    with_reason = client.post(
        "/api/v1/gates/human/reviews",
        json={
            "request_id": request_id,
            "reviewer": "operator",
            "decision": "approved",
            "rationale": "operator verified rollback and blast radius",
        },
    )
    assert with_reason.status_code == 201
    assert fetch_by_id(request_id).state == "approved"
