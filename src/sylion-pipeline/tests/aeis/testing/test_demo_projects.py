"""DemoProjectOrchestrator tests — 6 manifests must load + validate."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from sylion.aeis.testing.demo_projects import (
    DemoProjectManifest, DemoProjectOrchestrator,
)
from sylion.aeis.testing.demo_projects.orchestrator import EXPECTED_PROJECTS


@pytest.fixture(scope="module", autouse=True)
def isolated_demo_runtime(tmp_path_factory):
    root = tmp_path_factory.mktemp("demo_projects_runtime")
    db_path = root / "aeis_clean.db"
    old_db = os.environ.get("SYLION_DB_PATH")
    old_root = os.environ.get("SYLION_PROJECT_START_ROOT")
    os.environ["SYLION_DB_PATH"] = str(db_path)
    os.environ["SYLION_PROJECT_START_ROOT"] = str(root / "projects")

    from sylion.aeis.testing.ontology.store import reset_ontology_store
    from sylion.governance.ticket import reset_ticket_store

    reset_ontology_store()
    reset_ticket_store(db_path=db_path)
    yield
    reset_ontology_store()
    reset_ticket_store()
    if old_db is None:
        os.environ.pop("SYLION_DB_PATH", None)
    else:
        os.environ["SYLION_DB_PATH"] = old_db
    if old_root is None:
        os.environ.pop("SYLION_PROJECT_START_ROOT", None)
    else:
        os.environ["SYLION_PROJECT_START_ROOT"] = old_root


@pytest.fixture
def orch():
    return DemoProjectOrchestrator()


# -------- Loading --------

def test_loads_all_6_expected_manifests(orch):
    cov = orch.coverage()
    assert cov["expected"] == 6
    assert cov["present"] == 6
    assert cov["missing"] == []


def test_no_unexpected_manifests(orch):
    cov = orch.coverage()
    assert cov["unexpected"] == []


def test_each_manifest_has_required_fields(orch):
    for m in orch.list_manifests():
        assert m.project_id
        assert m.name
        assert m.type
        assert m.target_d_level
        assert m.required_personas
        assert m.required_test_classes
        assert m.release_blockers
        assert m.success_criteria


# -------- Validation --------

def test_all_manifests_validate_clean(orch):
    errors = orch.validate_all()
    assert errors == {}, f"validation errors: {errors}"


def test_each_manifest_has_min_3_errors_per_spec(orch):
    for m in orch.list_manifests():
        assert len(m.domain_specific_human_errors) >= 3, (
            f"{m.project_id} has only "
            f"{len(m.domain_specific_human_errors)} errors"
        )


def test_d5_projects_require_council_or_multisig_criteria(orch):
    for m in orch.list_manifests():
        if m.target_d_level == "D5":
            criteria_text = " ".join(m.success_criteria)
            assert ("Council session D5" in criteria_text
                    or "multi-sig" in criteria_text), (
                f"{m.project_id} (D5) missing strict criteria"
            )


# -------- D-level distribution --------

def test_two_d5_projects(orch):
    d5 = [m for m in orch.list_manifests() if m.target_d_level == "D5"]
    assert len(d5) == 2  # factory + marketplace


def test_three_d4_projects(orch):
    d4 = [m for m in orch.list_manifests() if m.target_d_level == "D4"]
    assert len(d4) == 3  # mobile + crm + funding


def test_one_d3_project(orch):
    d3 = [m for m in orch.list_manifests() if m.target_d_level == "D3"]
    assert len(d3) == 1  # public portal


# -------- Domain coverage --------

def test_covers_6_distinct_domains(orch):
    domains = {m.domain for m in orch.list_manifests()}
    assert len(domains) >= 5  # may overlap on supply_chain etc


def test_covers_6_distinct_types(orch):
    types = {m.type for m in orch.list_manifests()}
    assert types == {
        "mobile-app", "web-portal", "industrial-iot",
        "crm", "fintech-grants", "marketplace",
    }


# -------- Per-project specifics --------

def test_factory_uses_d5_industrial_safety(orch):
    m = orch.get_manifest("proj_demo_03_factory_automation_panel")
    assert m is not None
    assert m.target_d_level == "D5"
    assert m.domain == "industrial_safety"


def test_marketplace_includes_security_test_class(orch):
    m = orch.get_manifest("proj_demo_06_skills_marketplace")
    assert m is not None
    assert "T10" in m.required_test_classes  # security
    assert "T19" in m.required_test_classes  # llm behavioral


def test_crm_includes_governance_test(orch):
    m = orch.get_manifest("proj_demo_04_operator_crm")
    assert m is not None
    assert "T11" in m.required_test_classes  # governance
    assert "T10" in m.required_test_classes  # security (PII)


def test_mobile_includes_release_rehearsal(orch):
    m = orch.get_manifest("proj_demo_01_mobile_field_inspector")
    assert m is not None
    assert "T15" in m.required_test_classes  # release rehearsal


def test_funding_includes_chaos_test(orch):
    m = orch.get_manifest("proj_demo_05_funding_pipeline_tracker")
    assert m is not None
    assert "T13" in m.required_test_classes  # chaos/recovery


# -------- expected_count --------

def test_expected_count_is_6(orch):
    assert orch.expected_count() == 6
    assert len(EXPECTED_PROJECTS) == 6


# -------- execute_demo end-to-end lifecycle --------

def test_execute_demo_runs_all_steps_for_mobile():
    from sylion.aeis.testing.demo_projects import execute_demo
    from sylion.governance.tickets import fetch_by_id

    result = execute_demo("proj_demo_01_mobile_field_inspector")
    assert result["status"] == "READY_FOR_PRODUCTION"
    assert result["total_steps"] == 9
    step_names = [s["name"] for s in result["steps"]]
    assert step_names == [
        "project_lifecycle_completed", "charter_approved",
        "mandatory_tests_recorded", "findings_injected",
        "all_findings_verified_closed",
        "release_candidate_promoted", "production_governance_completed",
        "release_readiness_report", "memory_recorded",
    ]
    steps = {s["name"]: s for s in result["steps"]}
    lifecycle = steps["project_lifecycle_completed"]
    assert lifecycle["state"] == "CLOSED"
    assert lifecycle["audit_events"] >= 30
    assert Path(lifecycle["build_artifact"]["path"]).is_file()

    charter_ticket = steps["charter_approved"]["hg_ticket_id"]
    assert charter_ticket
    assert not charter_ticket.startswith("hg_")
    assert fetch_by_id(charter_ticket).state == "approved"

    decision = steps["production_governance_completed"]["decision"]
    assert decision["hg_ticket_id"]
    assert fetch_by_id(decision["hg_ticket_id"]).state == "approved"
    assert steps["release_readiness_report"]["blockers"] == []


def test_execute_demo_unknown_project_returns_error():
    from sylion.aeis.testing.demo_projects import execute_demo
    result = execute_demo("demo_does_not_exist")
    assert result["status"] == "error"
    assert "not found" in result["reason"]


def test_execute_demo_works_for_all_6_projects():
    """Proof of concept: every manifest can be driven through full lifecycle."""
    from sylion.aeis.testing.demo_projects import execute_demo
    project_ids = [p[0] for p in EXPECTED_PROJECTS]
    for pid in project_ids:
        result = execute_demo(pid)
        assert result["status"] == "READY_FOR_PRODUCTION", (
            f"{pid}: status={result.get('status')}"
        )


def test_execute_demo_d5_projects_pass_strict_checks():
    """D5 projects (factory + marketplace) require all 12+6 checklist items."""
    from sylion.aeis.testing.demo_projects import execute_demo
    for pid in ("proj_demo_03_factory_automation_panel",
                "proj_demo_06_skills_marketplace"):
        result = execute_demo(pid)
        assert result["status"] == "READY_FOR_PRODUCTION"
        rrr = next(s for s in result["steps"]
                   if s["name"] == "release_readiness_report")
        assert rrr["blockers"] == []
