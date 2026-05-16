"""LoopGovernor tests — hard limits enforcement."""
from __future__ import annotations

import time
import pytest

from sylion.aeis.testing.loop_governor import DEFAULT_LIMITS, LoopGovernor
from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import Finding, LoopReport, RepairAttempt


@pytest.fixture
def store():
    return OntologyStore()


@pytest.fixture
def gov(store):
    return LoopGovernor(ontology=store)


@pytest.fixture
def finding(store):
    f = Finding(severity="P1", d_level="D3", title="x",
                description="d", discovered_by="t")
    store.create(f)
    return f


def _attempt(store, finding_id, n, **kw):
    a = RepairAttempt(
        finding_id=finding_id, n=n,
        r_phase=kw.get("r_phase", "REPAIRING"),
        result=kw.get("result", "success"),
        files_touched_count=kw.get("files_touched_count", 1),
        diff_lines=kw.get("diff_lines", 10),
        time_in_phase_s=kw.get("time_in_phase_s", 5.0),
        completed_at=time.time(),
    )
    store.create(a)
    return a


# -------- Defaults --------

def test_defaults_match_canonical_spec():
    assert DEFAULT_LIMITS["max_auto_fix_attempts_per_finding"] == 2
    assert DEFAULT_LIMITS["max_total_no_go_iterations"] == 3
    assert DEFAULT_LIMITS["max_files_touched_no_hg"] == 5
    assert DEFAULT_LIMITS["max_diff_size_no_hg"] == 300
    assert DEFAULT_LIMITS["max_time_in_repair_loop_s"] == 1800
    assert DEFAULT_LIMITS["max_new_p0_p1_introduced"] == 0
    assert DEFAULT_LIMITS["max_parallel_repair_agents_per_finding"] == 1


# -------- check() --------

def test_check_allows_first_attempt(gov, finding):
    result = gov.check(finding.finding_id, {"files_touched_count": 1, "diff_lines": 10})
    assert result["allowed"] is True
    assert result["loop_report_id"] is None


def test_check_blocks_max_attempts_per_finding(gov, store, finding):
    _attempt(store, finding.finding_id, 1)
    _attempt(store, finding.finding_id, 2)
    result = gov.check(finding.finding_id, {})
    assert result["allowed"] is False
    assert result["reason"] == "max_auto_fix_attempts_per_finding"
    assert result["loop_report_id"]


def test_check_blocks_max_no_go_iterations(gov, store, finding):
    # 1 attempt (within limit), but each is failed -> NO-GO threshold
    _attempt(store, finding.finding_id, 1, result="failed_same")
    result = gov.check(finding.finding_id, {})
    # max_attempts=2 still not hit (only 1 done) but check NO-GO with future
    # Rather than relying on this, simulate 3 NO-GOs — but max_attempts=2 first
    # Easier: lower attempts limit
    g = LoopGovernor(store, limits={"max_auto_fix_attempts_per_finding": 99})
    _attempt(store, finding.finding_id, 2, result="regression_failed")
    _attempt(store, finding.finding_id, 3, result="failed_new")
    result = g.check(finding.finding_id, {})
    assert result["allowed"] is False
    assert result["reason"] == "max_total_no_go_iterations"


def test_check_blocks_max_files_touched_no_hg(gov, finding):
    result = gov.check(
        finding.finding_id,
        {"files_touched_count": 6, "diff_lines": 10, "has_hg_ticket": False},
    )
    assert result["allowed"] is False
    assert result["reason"] == "max_files_touched_no_hg"


def test_check_allows_files_touched_with_hg(gov, finding):
    result = gov.check(
        finding.finding_id,
        {"files_touched_count": 100, "diff_lines": 10, "has_hg_ticket": True},
    )
    assert result["allowed"] is True


def test_check_blocks_max_diff_size_no_hg(gov, finding):
    result = gov.check(
        finding.finding_id,
        {"files_touched_count": 1, "diff_lines": 500, "has_hg_ticket": False},
    )
    assert result["allowed"] is False
    assert result["reason"] == "max_diff_size_no_hg"


def test_check_blocks_new_p0_p1_introduced(gov, finding):
    result = gov.check(
        finding.finding_id,
        {"files_touched_count": 1, "diff_lines": 5, "new_p0_p1_introduced": 1},
    )
    assert result["allowed"] is False
    assert result["reason"] == "max_new_p0_p1_introduced"


def test_check_blocks_unknown_finding(gov):
    result = gov.check("find_doesnotexist", {})
    assert result["allowed"] is False
    assert result["reason"] == "finding_not_found"


def test_check_blocks_max_time_in_repair_loop(gov, store, finding):
    # Create attempt with started_at way in the past
    a = RepairAttempt(
        finding_id=finding.finding_id, n=1, r_phase="REPAIRING",
        result="success", files_touched_count=1, diff_lines=5,
        time_in_phase_s=0.1,
        started_at=time.time() - 3600,  # 1h ago, > 1800s default
        completed_at=time.time() - 3500,
    )
    store.create(a)
    result = gov.check(finding.finding_id, {})
    assert result["allowed"] is False
    assert result["reason"] == "max_time_in_repair_loop_s"


# -------- LoopReport --------

def test_generate_loop_report_creates_record(gov, store, finding):
    _attempt(store, finding.finding_id, 1, result="failed_same")
    _attempt(store, finding.finding_id, 2, result="failed_same")
    report = gov.generate_loop_report(
        finding.finding_id, loop_type="same_failure",
    )
    assert report.report_id.startswith("lr_")
    assert report.attempts_n == 2
    assert report.required_decision["type"] == "Human Gate"
    assert "further_auto_patch" in report.blocked_actions


def test_loop_report_persisted_to_store(gov, store, finding):
    _attempt(store, finding.finding_id, 1, result="failed_same")
    _attempt(store, finding.finding_id, 2, result="failed_same")
    report = gov.generate_loop_report(finding.finding_id)
    persisted = store.get(LoopReport, report.report_id)
    assert persisted is not None
    assert persisted.finding_id == finding.finding_id
