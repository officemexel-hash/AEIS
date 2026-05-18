from __future__ import annotations

import pytest

from sylion.core.evidence_spine import EvidenceSpine
from sylion.ops.production_deploy_pipeline import (
    PIPELINE_STAGES,
    ProductionDeployPipeline,
    ProductionDeployRequest,
)


ARTIFACT_SHA = "a" * 64
PREVIOUS_SHA = "b" * 64


@pytest.fixture
def pipeline() -> ProductionDeployPipeline:
    return ProductionDeployPipeline(
        db_path=":memory:",
        evidence_spine=EvidenceSpine(db_path=":memory:"),
    )


def _request(**overrides) -> ProductionDeployRequest:
    data = {
        "project_id": "project_prod_pipeline_smoke",
        "artifact_sha256": ARTIFACT_SHA,
        "previous_artifact_sha256": PREVIOUS_SHA,
        "release_version": "2026.05.18.1",
        "target_environment": "production",
        "approval_ticket_id": "ticket-approved",
        "scan_report": {
            "scanner": "trivy",
            "critical": 0,
            "high": 0,
            "medium": 1,
            "low": 2,
        },
        "smoke_report": {
            "golden_tests_passed": True,
            "healthcheck_passed": True,
            "p99_ms": 180,
            "p99_target_ms": 500,
        },
        "operator_probe": {
            "healthcheck_passed": True,
            "operator_probe_passed": True,
            "error_rate": 0.0,
        },
    }
    data.update(overrides)
    return ProductionDeployRequest(**data)


def test_pipeline_completes_all_stages_and_records_rollback_drill(pipeline):
    run = pipeline.run(_request())

    assert run["status"] == "completed"
    assert run["artifact_sha256"] == ARTIFACT_SHA
    assert run["current_live_sha256"] == ARTIFACT_SHA
    assert [stage["stage_name"] for stage in run["stages"]] == list(PIPELINE_STAGES)
    assert all(stage["status"] == "completed" for stage in run["stages"])
    assert all(stage["evidence_id"] for stage in run["stages"])
    assert run["evidence_id"]

    assert len(run["rollbacks"]) == 1
    rollback = run["rollbacks"][0]
    assert rollback["status"] == "passed"
    assert rollback["restored_artifact_sha256"] == PREVIOUS_SHA
    assert rollback["details"]["drill"] is True
    assert rollback["evidence_id"]


def test_pipeline_blocks_production_target_without_approval(pipeline):
    with pytest.raises(ValueError, match="approval_ticket_id is required"):
        pipeline.run(_request(approval_ticket_id=""))


def test_pipeline_stops_before_production_when_canary_fails(pipeline):
    run = pipeline.run(_request(
        failure_injection_stage="canary",
        include_rollback_drill=False,
    ))

    assert run["status"] == "failed"
    assert [stage["stage_name"] for stage in run["stages"]] == [
        "build",
        "container_scan",
        "staging_deploy",
        "smoke_test",
        "canary",
    ]
    assert run["stages"][-1]["status"] == "failed"
    assert run["stages"][-1]["error"] == "failure_injection_triggered"
    assert run["current_live_sha256"] == PREVIOUS_SHA
    assert run["rollbacks"] == []


def test_pipeline_rolls_back_after_post_deploy_failure(pipeline):
    run = pipeline.run(_request(
        failure_injection_stage="post_deploy_verification",
        include_rollback_drill=False,
    ))

    assert run["status"] == "rolled_back"
    assert run["current_live_sha256"] == PREVIOUS_SHA
    assert run["rollbacks"][0]["restored_artifact_sha256"] == PREVIOUS_SHA
    assert run["rollbacks"][0]["details"]["reason"] == "failure_injection_triggered"


def test_container_scan_failure_blocks_later_stages(pipeline):
    run = pipeline.run(_request(
        scan_report={"scanner": "trivy", "critical": 1, "high": 0},
        include_rollback_drill=False,
    ))

    assert run["status"] == "failed"
    assert [stage["stage_name"] for stage in run["stages"]] == [
        "build",
        "container_scan",
    ]
    assert run["stages"][-1]["error"] == "critical_vulnerabilities_present"
