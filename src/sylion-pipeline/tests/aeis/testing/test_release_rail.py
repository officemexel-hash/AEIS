"""ReleaseRail tests — 12+6 checklist."""
from __future__ import annotations

import time
import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import (
    Finding, ReleaseReadinessReport, TestCharter,
)
from sylion.aeis.testing.release_rail import (
    PROD_CHECKLIST, RC_CHECKLIST, EvaluationContext, ReleaseRail,
)


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def rail(store):
    return ReleaseRail(ontology=store)


def _approved_charter(store, project_id="proj_x") -> TestCharter:
    c = TestCharter(
        project_id=project_id,
        source_of_truth_version="v1", masterplan_version="v1",
        scope={}, required_test_classes=["T2"],
        required_personas=["operator_beginner"],
        required_evidence=[], release_blockers=[],
        auto_repair_policy={}, approval={"d_level": "D3"},
        status="approved", approved_at=time.time(),
    )
    store.create(c)
    return c


def _ctx_clean(charter_id=None) -> EvaluationContext:
    return EvaluationContext(
        project_id="proj_x",
        rc_id="rc_test_1",
        charter_id=charter_id,
        sot_approved=True, masterplan_approved=True,
        audit_chain_intact=True, artifact_hashes_present=True,
        human_like_passed=True, regression_passed=True,
        every_pass_has_evidence=True, no_mock_as_live=True,
        all_mandatory_tests_passed=True,  # E6 V2: now a canonical field
    )


# -------- Checklist constants --------

def test_rc_checklist_has_12_items():
    assert len(RC_CHECKLIST) == 12


def test_prod_checklist_has_6_items():
    assert len(PROD_CHECKLIST) == 6


def test_no_overlap_between_rc_and_prod():
    assert set(RC_CHECKLIST).isdisjoint(set(PROD_CHECKLIST))


# -------- evaluate() --------

def test_evaluate_clean_rc_pass(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    verdict = rail.evaluate(ctx)
    assert verdict["rc_pass"] is True
    assert verdict["status"] == "READY_FOR_RELEASE_CANDIDATE"
    # RC items all pass (no RC-specific blockers)
    rc_blockers = [b for b in verdict["blockers"] if b in RC_CHECKLIST]
    assert rc_blockers == []
    # PROD blockers may exist (6 items) until separately satisfied


def test_evaluate_blocks_no_sot_approval(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.sot_approved = False
    verdict = rail.evaluate(ctx)
    assert verdict["rc_pass"] is False
    assert "sot_approved" in verdict["blockers"]
    assert verdict["status"] == "BLOCKED_BY_GOVERNANCE"


def test_evaluate_blocks_no_masterplan(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.masterplan_approved = False
    verdict = rail.evaluate(ctx)
    assert "masterplan_approved" in verdict["blockers"]
    assert verdict["status"] == "BLOCKED_BY_GOVERNANCE"


def test_evaluate_blocks_unapproved_charter(rail, store):
    charter = TestCharter(
        project_id="proj_x", source_of_truth_version="v1",
        masterplan_version="v1", scope={}, required_test_classes=["T2"],
        required_personas=[], required_evidence=[], release_blockers=[],
        auto_repair_policy={}, approval={},
        status="proposed",  # NOT approved
    )
    store.create(charter)
    ctx = _ctx_clean(charter.charter_id)
    verdict = rail.evaluate(ctx)
    assert "test_charter_approved" in verdict["blockers"]


def test_evaluate_blocks_open_p1_finding(rail, store):
    charter = _approved_charter(store)
    f = Finding(severity="P1", d_level="D3", title="bug",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    ctx = _ctx_clean(charter.charter_id)
    verdict = rail.evaluate(ctx)
    assert "no_p0_p1_findings" in verdict["blockers"]


def test_evaluate_allows_resolved_p1_finding(rail, store):
    charter = _approved_charter(store)
    f = Finding(severity="P1", d_level="D3", title="fixed",
                description="d", discovered_by="t",
                r_status="VERIFIED")
    store.create(f)
    ctx = _ctx_clean(charter.charter_id)
    verdict = rail.evaluate(ctx)
    # If only finding-related, RC should pass
    assert verdict["checklist_results"]["no_p0_p1_findings"] is True


def test_evaluate_blocks_open_d4_finding(rail, store):
    charter = _approved_charter(store)
    f = Finding(severity="P3", d_level="D4", title="open d4",
                description="d", discovered_by="t", r_status="OPEN")
    store.create(f)
    ctx = _ctx_clean(charter.charter_id)
    verdict = rail.evaluate(ctx)
    assert "d3_findings_decided" in verdict["blockers"]


def test_evaluate_prod_requires_release_rehearsal(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    # RC clean but no PROD items
    verdict = rail.evaluate(ctx)
    assert verdict["rc_pass"] is True
    assert verdict["prod_pass"] is False
    assert "release_rehearsal_passed" in verdict["blockers"]


def test_evaluate_prod_pass_with_all_items(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.release_rehearsal_passed = True
    ctx.rollback_tested_within_7d = True
    ctx.final_approval_signed = True
    ctx.council_completed_d4_d5 = True
    ctx.sentinels_pass = True
    ctx.operator_signed_final_gate = True
    verdict = rail.evaluate(ctx)
    assert verdict["prod_pass"] is True
    assert verdict["status"] == "READY_FOR_PRODUCTION"


def test_evaluate_blocks_mock_as_live(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.no_mock_as_live = False
    verdict = rail.evaluate(ctx)
    assert "no_mock_as_live" in verdict["blockers"]


def test_evaluate_blocks_regression_failed(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.regression_passed = False
    verdict = rail.evaluate(ctx)
    assert "regression_passed" in verdict["blockers"]
    # not governance — findings/regression bucket
    assert verdict["status"] == "BLOCKED_BY_FINDINGS"


def test_evaluate_blocks_audit_chain_broken(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.audit_chain_intact = False
    verdict = rail.evaluate(ctx)
    assert "audit_chain_intact" in verdict["blockers"]
    assert verdict["status"] == "BLOCKED_BY_GOVERNANCE"


# -------- generate_report --------

def test_generate_report_persisted(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    report = rail.generate_report(ctx)
    assert report.report_id.startswith("rrr_")
    persisted = store.get(ReleaseReadinessReport, report.report_id)
    assert persisted is not None
    assert "sot_approved" in persisted.checklist_results


def test_report_recommendations_for_blocked(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.sot_approved = False
    report = rail.generate_report(ctx)
    assert any("resolve_sot_approved" in r for r in report.recommendations)


def test_report_high_comprehension_when_human_like_passed(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.human_like_passed = True
    report = rail.generate_report(ctx)
    assert report.human_comprehension_score >= 0.8


def test_report_low_comprehension_when_human_like_failed(rail, store):
    charter = _approved_charter(store)
    ctx = _ctx_clean(charter.charter_id)
    ctx.human_like_passed = False
    report = rail.generate_report(ctx)
    assert report.human_comprehension_score <= 0.5
