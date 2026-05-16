"""Skills Marketplace — D5 supply-chain hardening tests."""
from __future__ import annotations

import pytest

from sylion.demo.skills_marketplace import (
    MarketplaceService, MarketplaceStore, Skill, SkillDependency,
)
from sylion.demo.skills_marketplace.models import MAX_SKILL_BUDGET_USD


@pytest.fixture
def store():
    return MarketplaceStore()


@pytest.fixture
def svc(store):
    return MarketplaceService(store=store)


def _upload(svc, name="my-skill", version="1.0.0",
             author="op_1", budget=10.0):
    return svc.upload_skill(
        name=name, version=version, author_id=author,
        sha256="a"*64, signature_pubkey="x"*64,
        description="demo", cost_budget_usd=budget,
    )


# -------- Models --------

def test_skill_name_alphanumeric():
    with pytest.raises(ValueError, match="name"):
        Skill(name="bad name!", author_id="op",
              sha256="a"*64, signature_pubkey="x"*64)


def test_skill_signature_pubkey_required():
    with pytest.raises(ValueError, match="signature_pubkey"):
        Skill(name="x", author_id="op", sha256="a"*64,
              signature_pubkey="")


def test_skill_budget_capped():
    with pytest.raises(ValueError, match="exceeds hard cap"):
        Skill(name="x", author_id="op", sha256="a"*64,
              signature_pubkey="x"*64,
              cost_budget_usd=MAX_SKILL_BUDGET_USD + 1)


def test_dependency_version_pin_must_be_exact():
    """Anti-typosquat / version range attack."""
    with pytest.raises(ValueError, match="EXACT"):
        SkillDependency(
            skill_id="s", dep_name="dep", dep_version_pin=">=1.0",
            dep_sha256="a"*64,
        )


def test_dependency_requires_sha256():
    with pytest.raises(ValueError, match="dep_sha256"):
        SkillDependency(
            skill_id="s", dep_name="d", dep_version_pin="1.0.0",
            dep_sha256="too_short",
        )


# -------- Upload + duplicate guard --------

def test_upload_skill_succeeds(svc):
    s = _upload(svc)
    assert s.status == "uploaded"


def test_adv_duplicate_name_version_blocked(svc):
    _upload(svc, name="popular-skill", version="1.0.0")
    with pytest.raises(ValueError, match="already published"):
        _upload(svc, name="popular-skill", version="1.0.0",
                 author="op_attacker")


def test_upload_same_name_different_version_allowed(svc):
    _upload(svc, name="versioned", version="1.0.0")
    s2 = _upload(svc, name="versioned", version="1.1.0")
    assert s2.skill_id


# -------- Static scan (D5 mandatory) --------

def test_clean_scan_marks_ready_for_review(svc):
    s = _upload(svc)
    scan = svc.run_static_scan(s.skill_id, findings=[])
    assert scan.severity_max == "none"
    fetched = svc._store.get_skill(s.skill_id)
    assert fetched.status == "ready_for_review"


def test_adv_high_severity_finding_blocks_skill(svc):
    s = _upload(svc, name="malicious-skill")
    scan = svc.run_static_scan(s.skill_id, findings=[
        {"severity": "high", "rule": "shell_injection",
         "file": "exec.py", "line": 42},
    ])
    assert scan.severity_max == "high"
    fetched = svc._store.get_skill(s.skill_id)
    assert fetched.status == "scan_failed"


def test_adv_critical_severity_finding_blocks_skill(svc):
    s = _upload(svc, name="evil")
    svc.run_static_scan(s.skill_id, findings=[
        {"severity": "critical", "rule": "eval_user_input"},
    ])
    assert svc._store.get_skill(s.skill_id).status == "scan_failed"


def test_low_severity_findings_allow_review(svc):
    s = _upload(svc)
    svc.run_static_scan(s.skill_id, findings=[
        {"severity": "low", "rule": "missing_docstring"},
    ])
    assert svc._store.get_skill(s.skill_id).status == "ready_for_review"


# -------- Approve (D5: Council required) --------

def test_adv_approve_without_council_blocked(svc):
    s = _upload(svc)
    svc.run_static_scan(s.skill_id, findings=[])
    with pytest.raises(PermissionError, match="council_session_id"):
        svc.approve_skill(s.skill_id, council_session_id="")


def test_approve_with_council_succeeds(svc):
    s = _upload(svc)
    svc.run_static_scan(s.skill_id, findings=[])
    approved = svc.approve_skill(
        s.skill_id, council_session_id="cs_d5_marketplace_001",
    )
    assert approved.status == "approved"
    assert approved.council_session_id == "cs_d5_marketplace_001"
    assert approved.approved_at is not None


def test_adv_approve_skill_without_scan_blocked(svc):
    s = _upload(svc)
    # Move to ready_for_review by raw status update (skipping scan)
    svc._store.update_skill_status(s.skill_id, "ready_for_review")
    with pytest.raises(ValueError, match="scan missing or has blocking"):
        svc.approve_skill(s.skill_id, council_session_id="cs_x")


def test_adv_approve_skill_with_failed_scan_blocked(svc):
    s = _upload(svc)
    svc.run_static_scan(s.skill_id, findings=[
        {"severity": "high", "rule": "x"},
    ])
    with pytest.raises(ValueError, match="cannot approve"):
        svc.approve_skill(s.skill_id, council_session_id="cs_x")


# -------- Cost guard (runaway cost protection) --------

def test_can_execute_within_budget(svc):
    s = _upload(svc, budget=5.0)
    svc.run_static_scan(s.skill_id, findings=[])
    svc.approve_skill(s.skill_id, council_session_id="cs_1")
    result = svc.can_execute(s.skill_id, projected_cost_usd=2.5)
    assert result["allowed"] is True


def test_adv_can_execute_blocks_runaway_cost(svc):
    s = _upload(svc, budget=5.0)
    svc.run_static_scan(s.skill_id, findings=[])
    svc.approve_skill(s.skill_id, council_session_id="cs_1")
    result = svc.can_execute(s.skill_id, projected_cost_usd=50.0)
    assert result["allowed"] is False
    assert "RUNAWAY COST" in result["reason"]


def test_can_execute_blocks_unapproved_skill(svc):
    s = _upload(svc)  # not approved
    result = svc.can_execute(s.skill_id, projected_cost_usd=1.0)
    assert result["allowed"] is False
    assert "not approved" in result["reason"]


# -------- Reviews --------

def test_review_decision_validated():
    from sylion.demo.skills_marketplace import SkillReview
    with pytest.raises(ValueError, match="decision"):
        SkillReview(skill_id="s", reviewer_id="r", decision="maybe")


def test_review_persisted(svc):
    s = _upload(svc)
    svc.run_static_scan(s.skill_id, findings=[])
    rv = svc.submit_review(s.skill_id, reviewer_id="rev_1",
                            decision="approve", rationale="LGTM")
    assert rv.review_id.startswith("rev_")


def test_store_health(store):
    h = store.health()
    assert h["ok"] is True
