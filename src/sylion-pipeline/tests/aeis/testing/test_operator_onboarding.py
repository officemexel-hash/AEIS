from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.aeis.testing.operator_onboarding import (
    OperatorOnboardingRunner,
    assess_duration,
)
from sylion.core.evidence_spine import EvidenceSpine


def advisor_only_app() -> FastAPI:
    from sylion.api.advisor_routes import router

    app = FastAPI()
    app.include_router(router)
    return app


def test_operator_onboarding_runner_completes_phase1():
    report = OperatorOnboardingRunner(
        app=advisor_only_app(),
        evidence_spine=EvidenceSpine(),
    ).run(record_evidence=True)

    assert report.status == "PASS"
    assert report.evidence_id.startswith("ev_")
    assert report.checked_steps == 15
    assert report.failed_steps == 0
    assert report.elapsed_minutes < 15
    assert report.acceptance_status == "PASS"
    assert report.has_completed is True
    assert report.workspace_folder_count == 15
    assert report.secrets_redacted is True


def test_operator_onboarding_endpoint_returns_pass():
    from sylion.api.app import app

    response = TestClient(app).get("/api/v1/test-center/operator-onboarding")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PASS"
    assert body["failed_steps"] == 0
    assert body["has_completed"] is True
    assert body["workspace_folder_count"] == 15
    assert body["frontend_contract_status"] == "PASS"


def test_operator_onboarding_frontend_contract_fails_closed(tmp_path: Path):
    (tmp_path / "src/sylion-frontend/src/app/(app)/onboarding").mkdir(parents=True)
    (tmp_path / "src/sylion-frontend/src/app/(app)/onboarding/page.tsx").write_text(
        'data-testid="onboarding-wizard"',
        encoding="utf-8",
    )

    runner = OperatorOnboardingRunner(
        root=tmp_path,
        app=advisor_only_app(),
        evidence_spine=EvidenceSpine(),
    )

    errors = runner.check_frontend_contract()

    assert errors
    assert any("missing marker" in error or "missing frontend onboarding file" in error for error in errors)


def test_operator_onboarding_duration_budget():
    assert assess_duration(14 * 60 + 59) is True
    assert assess_duration(15 * 60 + 1) is False
