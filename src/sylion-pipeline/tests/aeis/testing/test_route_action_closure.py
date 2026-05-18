from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.aeis.testing.route_action_closure import (
    RouteActionClosureRunner,
    RouteActionSpec,
    classify_action_response,
)
from sylion.core.evidence_spine import EvidenceSpine


def test_route_action_closure_passes_against_fastapi_app():
    from sylion.api.app import app

    report = RouteActionClosureRunner(
        app=app,
        evidence_spine=EvidenceSpine(),
    ).run(record_evidence=True)

    assert report.status == "PASS"
    assert report.evidence_id.startswith("ev_")
    assert report.checked_actions >= 9
    assert report.failed_actions == 0
    assert all(result.backend_route_found for result in report.results)
    assert all(result.frontend_action_found for result in report.results)


def test_route_action_closure_endpoint_returns_pass():
    from sylion.api.app import app

    response = TestClient(app).get("/api/v1/test-center/route-action-closure")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PASS"
    assert body["failed_actions"] == 0
    assert body["evidence_id"].startswith("ev_")


def test_route_action_closure_fails_closed_when_backend_route_missing(tmp_path: Path):
    frontend = tmp_path / "src/sylion-frontend/src/lib/api/client.ts"
    frontend.parent.mkdir(parents=True)
    frontend.write_text(
        """
        export async function request<T>() {
          throw new Error("API 500");
        }
        if (!text.trim()) return undefined as T;
        const marker = "missing-route-marker";
        """,
        encoding="utf-8",
    )
    spec = RouteActionSpec(
        action_id="missing.backend",
        surface="/contracts",
        frontend_route="/contracts",
        method="POST",
        api_path="/api/v1/not-registered",
        surface_paths=("src/sylion-frontend/src/lib/api/client.ts",),
        action_paths=("src/sylion-frontend/src/lib/api/client.ts",),
        required_markers=("missing-route-marker",),
    )

    report = RouteActionClosureRunner(
        root=tmp_path,
        app=FastAPI(),
        specs=(spec,),
        evidence_spine=EvidenceSpine(),
    ).run(record_evidence=False)

    assert report.status == "FAIL"
    assert report.results[0].backend_route_found is False
    assert "missing backend route" in report.results[0].errors[0]


def test_route_action_closure_fails_closed_when_frontend_marker_missing():
    from sylion.api.app import app

    spec = RouteActionSpec(
        action_id="missing.marker",
        surface="/contracts",
        frontend_route="/contracts",
        method="GET",
        api_path="/api/v1/contracts",
        surface_paths=("src/sylion-frontend/src/app/(app)/contracts/page.tsx",),
        action_paths=("src/sylion-frontend/src/lib/api/client.ts",),
        required_markers=("__marker_that_must_not_exist__",),
    )

    report = RouteActionClosureRunner(
        app=app,
        specs=(spec,),
        evidence_spine=EvidenceSpine(),
    ).run(record_evidence=False)

    assert report.status == "FAIL"
    assert report.results[0].backend_route_found is True
    assert "__marker_that_must_not_exist__" in report.results[0].missing_markers


def test_action_response_contract_covers_204_and_error_states():
    assert classify_action_response(204, "").ok is True
    assert classify_action_response(204, "").category == "no_content_success"

    forbidden = classify_action_response(403, '{"detail":"forbidden"}')
    assert forbidden.ok is False
    assert forbidden.retryable is False
    assert forbidden.category == "authorization_error"

    server_error = classify_action_response(500, "boom")
    assert server_error.ok is False
    assert server_error.retryable is True
    assert server_error.category == "server_error"

    network = classify_action_response(0, "", network_error="ECONNRESET")
    assert network.ok is False
    assert network.retryable is True
    assert network.category == "transport_error"

    timeout = classify_action_response(0, "", timeout=True)
    assert timeout.ok is False
    assert timeout.retryable is True
    assert timeout.category == "timeout"
