"""TestingMemoryStore + W14SelfAudit smoke tests."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.memory import TestingMemoryStore
from sylion.aeis.testing.self_audit import W14SelfAudit


@pytest.fixture
def mem():
    return TestingMemoryStore()


# -------- Memory store --------

def test_record_and_list_lesson(mem):
    lid = mem.record_lesson(
        project_id="proj_x", release_id="rel_1",
        pattern_type="missing_backup_gate",
        context={"project_type": "device-action"},
        detection={"found_by": "L4"},
        resolution={"repair": "added gate"},
    )
    assert lid.startswith("lesson_")
    lessons = mem.list_lessons("proj_x")
    assert len(lessons) == 1
    assert lessons[0]["pattern_type"] == "missing_backup_gate"


def test_lessons_filtered_by_project(mem):
    mem.record_lesson("proj_a", "r1", "pa", {}, {}, {})
    mem.record_lesson("proj_b", "r2", "pb", {}, {}, {})
    a = mem.list_lessons("proj_a")
    b = mem.list_lessons("proj_b")
    assert len(a) == 1
    assert len(b) == 1


def test_lessons_similar_to(mem):
    mem.record_lesson("proj_a", "r1", "device-action_backup_missing", {}, {}, {})
    mem.record_lesson("proj_b", "r2", "ui_only_drift", {}, {}, {})
    similar = mem.list_lessons_similar_to("device-action")
    assert len(similar) == 1


def test_record_root_cause(mem):
    cid = mem.record_root_cause(
        finding_id="find_x", cause_class="contract_mismatch",
        description="API spec drift", confidence=0.85,
    )
    assert cid.startswith("rc_")
    causes = mem.list_root_causes("find_x")
    assert len(causes) == 1
    assert causes[0]["cause_class"] == "contract_mismatch"


def test_record_flaky(mem):
    pid = mem.record_flaky(
        test_id="test_concurrent_x",
        fail_modes=["race_condition", "timeout"],
        runs_total=100, runs_failed=8,
    )
    assert pid.startswith("flaky_")
    flaky = mem.list_flaky(min_fail_rate=0.05)
    assert len(flaky) == 1
    assert flaky[0]["fail_rate"] == pytest.approx(0.08)


def test_flaky_filtered_by_threshold(mem):
    mem.record_flaky("t1", [], 100, 1)   # 1% — below default 5%
    mem.record_flaky("t2", [], 100, 10)  # 10% — above
    flaky = mem.list_flaky(min_fail_rate=0.05)
    assert len(flaky) == 1


def test_anti_pattern_add_and_increment(mem):
    apid = mem.add_anti_pattern(
        "mock_oznaczony_jako_live", severity="D5",
        detection_rule="UI shows mock without badge",
        prevention="Mock Guardian + UI badge",
    )
    assert apid.startswith("ap_")
    aps = mem.list_anti_patterns()
    assert len(aps) == 1
    assert aps[0]["detected_in_count"] == 1

    # Increment when seen again
    success = mem.increment_anti_pattern("mock_oznaczony_jako_live")
    assert success
    aps = mem.list_anti_patterns()
    assert aps[0]["detected_in_count"] == 2


def test_anti_pattern_increment_unknown_returns_false(mem):
    assert mem.increment_anti_pattern("not_recorded") is False


def test_health_returns_counts(mem):
    mem.record_lesson("p", "r", "pt", {}, {}, {})
    mem.add_anti_pattern("ap1")
    h = mem.health()
    assert h["ok"] is True
    assert h["counts"]["w14_lessons"] == 1
    assert h["counts"]["w14_anti_patterns"] == 1


# -------- Self Audit --------

def test_self_audit_runs_all_pillars():
    audit = W14SelfAudit()
    result = audit.run_full_cycle()
    assert result["total_pillars"] == 10
    assert "status" in result
    assert "duration_s" in result
    assert isinstance(result["results"], list)


def test_self_audit_all_pillars_pass():
    audit = W14SelfAudit()
    result = audit.run_full_cycle()
    failed = [r for r in result["results"] if r["status"] == "fail"]
    assert not failed, f"failed pillars: {[r['pillar'] for r in failed]}"
    assert result["status"] == "pass"
    assert result["passed"] == result["total_pillars"]


def test_self_audit_each_pillar_has_duration():
    audit = W14SelfAudit()
    result = audit.run_full_cycle()
    for r in result["results"]:
        assert r["duration_s"] >= 0
        assert r["pillar"] != ""
