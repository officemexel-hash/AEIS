from __future__ import annotations

from pathlib import Path

from sylion.aeis.testing.production_readiness import (
    DEFAULT_REQUIREMENTS,
    ProductionReadinessRunner,
)


def _write_evidence(root: Path, requirement_ids: set[str]) -> None:
    for requirement in DEFAULT_REQUIREMENTS:
        if requirement.requirement_id not in requirement_ids:
            continue
        path = root / requirement.evidence_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# frozen\n\nPASS1/PASS2\n", encoding="utf-8")


def test_readiness_blocks_when_required_freeze_evidence_is_missing(tmp_path):
    present = {
        requirement.requirement_id
        for requirement in DEFAULT_REQUIREMENTS
        if requirement.requirement_id != "PROD-P0-007"
    }
    _write_evidence(tmp_path, present)
    runner = ProductionReadinessRunner(root=tmp_path, db_path=tmp_path / "readiness.sqlite")

    report = runner.evaluate(project_id="project_readiness")

    assert report.status == "BLOCKED"
    assert report.can_mark_production_ready is False
    assert "PROD-P0-007" in report.p0_blockers
    assert report.next_blocker["requirement_id"] == "PROD-P0-007"
    assert report.next_blocker["next_action"].startswith("Fix implementation")


def test_readiness_can_only_mark_ready_when_every_required_item_is_frozen(tmp_path):
    _write_evidence(tmp_path, {requirement.requirement_id for requirement in DEFAULT_REQUIREMENTS})
    runner = ProductionReadinessRunner(root=tmp_path, db_path=tmp_path / "readiness.sqlite")

    report = runner.evaluate(project_id="project_readiness")

    assert report.status == "PROD_READY"
    assert report.can_mark_production_ready is True
    assert report.p0_blockers == []
    assert report.p1_blockers == []
    assert report.warnings == []


def test_repair_command_records_protocol_and_blocks_continue_on_failures(tmp_path):
    _write_evidence(tmp_path, set())
    runner = ProductionReadinessRunner(root=tmp_path, db_path=tmp_path / "readiness.sqlite")

    command = runner.command(project_id="project_readiness", actor="pytest", action="start")

    assert command["repair_protocol"]["command"] == "AEIS_PRODUCTION_REPAIR_LOOP"
    assert command["allowed_to_continue"] is False
    assert command["next_blocker"]["priority"] == "P0"
    latest = runner.latest_report()
    assert latest["report_id"] == command["report_id"]
