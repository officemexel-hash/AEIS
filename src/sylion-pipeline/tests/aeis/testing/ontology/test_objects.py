"""Unit tests for the 25 W14 ontology dataclasses."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.ontology.enums import (
    ALL_ENUMS,
    BranchState,
    BranchType,
    DLevel,
    EvidenceTier,
    GuardianClass,
    HumanErrorClass,
    PersonaCapability,
    ReleaseStatus,
    RStatus,
    Severity,
    TestClass,
)
from sylion.aeis.testing.ontology.objects import (
    OBJECT_TABLE_MAP,
    PRIMARY_KEY_MAP,
    Requirement,
    TestCharter,
)
from tests.aeis.testing.ontology.fixtures import (
    ALL_FACTORIES,
    make_alert,
    make_attempt,
    make_branch,
    make_case,
    make_charter,
    make_decision_trace,
    make_error_injection,
    make_eval_suite,
    make_finding,
    make_loop_report,
    make_near_miss,
    make_patch,
    make_persona,
    make_plan,
    make_readiness_report,
    make_regression,
    make_release_candidate,
    make_release_decision,
    make_requirement,
    make_run,
    make_scenario,
    make_simulation_branch,
    make_simulation_contract,
    make_simulation_evidence,
    make_suite,
)

# ---------------------------------------------------------------------------
# Enum sanity
# ---------------------------------------------------------------------------


def test_all_12_enums_registered() -> None:
    assert len(ALL_ENUMS) == 12
    names = {e.__name__ for e in ALL_ENUMS}
    assert names == {
        "DLevel", "RStatus", "TestClass", "ReleaseStatus",
        "Severity", "GateType", "HumanErrorClass", "EvidenceTier",
        "BranchType", "BranchState", "PersonaCapability", "GuardianClass",
    }


def test_dlevel_has_six_levels() -> None:
    assert DLevel.values() == ("D0", "D1", "D2", "D3", "D4", "D5")


def test_rstatus_lifecycle_complete() -> None:
    expected = {
        "OPEN", "TRIAGED", "REPRODUCED", "CLASSIFIED", "REPAIR_PROPOSED",
        "WAITING_FOR_HUMAN_GATE", "REPAIRING", "READY_FOR_RETEST",
        "REGRESSION_FAILED", "VERIFIED", "ESCALATED", "WAIVED_BY_HUMAN",
        "CLOSED",
    }
    assert set(RStatus.values()) == expected


def test_testclass_t0_through_t19() -> None:
    vals = TestClass.values()
    assert len(vals) == 20
    assert vals[0] == "T0"
    assert vals[-1] == "T19"


def test_severity_p0_to_p4() -> None:
    assert Severity.values() == ("P0", "P1", "P2", "P3", "P4")


def test_human_error_class_21_total() -> None:
    assert len(HumanErrorClass.values()) == 21


def test_guardian_class_13_total() -> None:
    assert len(GuardianClass.values()) == 13


def test_evidence_tier_h0_to_h4() -> None:
    assert EvidenceTier.values() == ("H0", "H1", "H2", "H3", "H4")


def test_release_status_10_values() -> None:
    assert len(ReleaseStatus.values()) == 10


def test_branch_type_four_kinds() -> None:
    assert BranchType.values() == ("simulation", "repair", "test", "release")


def test_branch_state_three_kinds() -> None:
    assert BranchState.values() == ("open", "merged", "discarded")


def test_persona_capability_three_kinds() -> None:
    assert PersonaCapability.values() == ("beginner", "intermediate", "expert")


def test_enum_has_value_helper() -> None:
    assert DLevel.has_value("D3")
    assert not DLevel.has_value("D9")


# ---------------------------------------------------------------------------
# Object registries
# ---------------------------------------------------------------------------


def test_object_table_map_has_25_entries() -> None:
    assert len(OBJECT_TABLE_MAP) == 25


def test_primary_key_map_matches_object_map() -> None:
    assert set(PRIMARY_KEY_MAP) == set(OBJECT_TABLE_MAP)


def test_table_names_unique() -> None:
    names = list(OBJECT_TABLE_MAP.values())
    assert len(set(names)) == len(names)


# ---------------------------------------------------------------------------
# Per-object construction (smoke + ID prefix + invariants)
# ---------------------------------------------------------------------------


def test_create_requirement_minimal() -> None:
    r = make_requirement()
    assert r.req_id.startswith("req_")
    assert r.source == "SoT"
    assert r.test_required is True


def test_create_charter_minimal() -> None:
    c = make_charter()
    assert c.charter_id.startswith("tc_")
    assert c.status == "draft"
    assert TestClass.UNIT.value in c.required_test_classes


def test_create_plan_minimal() -> None:
    p = make_plan()
    assert p.plan_id.startswith("tp_")
    assert p.charter_id.startswith("tc_")


def test_create_suite_minimal() -> None:
    s = make_suite()
    assert s.suite_id.startswith("ts_")
    assert s.test_class == TestClass.SECURITY.value
    assert s.enabled is True


def test_create_case_minimal() -> None:
    c = make_case()
    assert c.case_id.startswith("tc_")
    assert c.evaluator == "exact_match"


def test_create_eval_suite_minimal() -> None:
    es = make_eval_suite()
    assert es.suite_id.startswith("es_")


def test_create_run_minimal() -> None:
    r = make_run()
    assert r.run_id.startswith("tr_")
    assert r.status == "running"


def test_create_regression_minimal() -> None:
    rr = make_regression()
    assert rr.regression_id.startswith("rr_")
    assert rr.status == "pending"


def test_create_finding_minimal() -> None:
    f = make_finding()
    assert f.finding_id.startswith("find_")
    assert f.r_status == RStatus.OPEN.value


def test_create_patch_minimal() -> None:
    p = make_patch()
    assert p.proposal_id.startswith("patch_")
    assert p.branch_id != "main"
    assert p.diff_lines_added + p.diff_lines_removed > 0


def test_create_repair_attempt_minimal() -> None:
    a = make_attempt()
    assert a.attempt_id.startswith("ra_")
    assert a.n == 1


def test_create_loop_report_minimal() -> None:
    lr = make_loop_report()
    assert lr.report_id.startswith("lr_")
    assert lr.loop_type == "same_failure"


def test_create_alert_minimal() -> None:
    a = make_alert()
    assert a.alert_id.startswith("ga_")
    assert a.acknowledged is False


def test_create_simulation_contract_minimal() -> None:
    sc = make_simulation_contract()
    assert sc.contract_id.startswith("sc_")


def test_create_simulation_branch_minimal() -> None:
    sb = make_simulation_branch()
    assert sb.sim_branch_id.startswith("simb_")
    assert sb.state == BranchState.OPEN.value


def test_create_simulation_evidence_minimal() -> None:
    se = make_simulation_evidence()
    assert se.evidence_id.startswith("se_")
    assert len(se.branch_snapshot_hash) == 64


def test_create_persona_minimal() -> None:
    p = make_persona()
    assert p.persona_id.startswith("persona_")
    assert 0.0 <= p.error_proneness <= 1.0


def test_create_scenario_minimal() -> None:
    s = make_scenario()
    assert s.scenario_id.startswith("scn_")
    assert s.difficulty == "easy"


def test_create_error_injection_minimal() -> None:
    inj = make_error_injection()
    assert inj.injection_id.startswith("hei_")


def test_create_decision_trace_minimal() -> None:
    t = make_decision_trace()
    assert t.trace_id.startswith("hdt_")


def test_create_near_miss_minimal() -> None:
    nm = make_near_miss()
    assert nm.near_miss_id.startswith("nm_")
    assert nm.future_risk == "low"


def test_create_branch_minimal() -> None:
    b = make_branch()
    assert b.branch_id.startswith("br_")
    assert b.branch_type == BranchType.TEST.value


def test_create_release_candidate_minimal() -> None:
    rc = make_release_candidate()
    assert rc.rc_id.startswith("rc_")
    assert rc.gate_status == ReleaseStatus.RELEASE_CANDIDATE.value


def test_create_release_decision_minimal() -> None:
    rd = make_release_decision()
    assert rd.decision_id.startswith("rd_")
    assert rd.outcome in ("approved", "rejected", "deferred", "rollback")


def test_create_readiness_report_minimal() -> None:
    rrr = make_readiness_report()
    assert rrr.report_id.startswith("rrr_")
    assert 0.0 <= rrr.human_comprehension_score <= 1.0


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


def test_requirement_rejects_invalid_source() -> None:
    with pytest.raises(ValueError, match="source"):
        Requirement(source="random", source_ref="x", description="d")


def test_requirement_rejects_missing_description() -> None:
    with pytest.raises(ValueError, match="description"):
        Requirement(source="SoT", source_ref="x", description="")


def test_charter_rejects_empty_test_classes() -> None:
    with pytest.raises(ValueError, match="required_test_classes"):
        TestCharter(
            project_id="proj_abc123def456",
            source_of_truth_version="1",
            masterplan_version="1",
            scope={"a": 1},
            required_test_classes=[],
            required_personas=["operator_beginner"],
            required_evidence=["test_result"],
            release_blockers=["P0"],
            auto_repair_policy={},
            approval={"d_level": DLevel.D2.value},
        )


def test_charter_rejects_invalid_status() -> None:
    with pytest.raises(ValueError, match="status"):
        make_charter(status="leaked_state")


def test_charter_rejects_unknown_test_class() -> None:
    with pytest.raises(ValueError, match="required_test_classes"):
        make_charter(required_test_classes=["T99"])


def test_finding_rejects_invalid_severity() -> None:
    with pytest.raises(ValueError, match="severity"):
        make_finding(severity="P9")


def test_finding_rejects_invalid_r_status() -> None:
    with pytest.raises(ValueError, match="r_status"):
        make_finding(r_status="WAT")


def test_patch_proposal_rejects_main_branch() -> None:
    with pytest.raises(ValueError, match="main"):
        make_patch(branch_id="main")


def test_patch_proposal_rejects_zero_diff() -> None:
    with pytest.raises(ValueError, match="diff_lines"):
        make_patch(diff_lines_added=0, diff_lines_removed=0)


def test_repair_attempt_rejects_zero_n() -> None:
    with pytest.raises(ValueError, match="n"):
        make_attempt(n=0)


def test_persona_rejects_error_proneness_out_of_range() -> None:
    with pytest.raises(ValueError, match="error_proneness"):
        make_persona(error_proneness=1.5)


def test_persona_rejects_negative_attention() -> None:
    with pytest.raises(ValueError, match="attention_span_min"):
        make_persona(attention_span_min=0)


def test_loop_report_rejects_similarity_out_of_range() -> None:
    with pytest.raises(ValueError, match="similarity_score"):
        make_loop_report(similarity_score=1.5)


def test_simulation_contract_rejects_runtime_above_3600() -> None:
    with pytest.raises(ValueError, match="max_runtime_seconds"):
        make_simulation_contract(safety={"max_runtime_seconds": 7200, "max_cost_usd": 1.0})


def test_simulation_contract_rejects_cost_above_10() -> None:
    with pytest.raises(ValueError, match="max_cost_usd"):
        make_simulation_contract(safety={"max_runtime_seconds": 60, "max_cost_usd": 100.0})


def test_simulation_contract_rejects_main_mutation_without_d5() -> None:
    with pytest.raises(ValueError, match="main_mutation_allowed"):
        make_simulation_contract(
            isolation={"main_mutation_allowed": True, "external_network_allowed": False},
            safety={"max_runtime_seconds": 60, "max_cost_usd": 1.0},
        )


def test_simulation_contract_allows_main_mutation_with_d5_council() -> None:
    sc = make_simulation_contract(
        isolation={"main_mutation_allowed": True, "external_network_allowed": False},
        safety={
            "max_runtime_seconds": 60,
            "max_cost_usd": 1.0,
            "approved_d_level": DLevel.D5.value,
            "council_approved": True,
        },
    )
    assert sc.isolation["main_mutation_allowed"] is True


def test_simulation_evidence_rejects_short_hash() -> None:
    with pytest.raises(ValueError, match="branch_snapshot_hash"):
        make_simulation_evidence(branch_snapshot_hash="abc")


def test_simulation_evidence_rejects_invalid_layer() -> None:
    with pytest.raises(ValueError, match="layer_executed"):
        make_simulation_evidence(layer_executed=5)


def test_release_decision_rejects_empty_signatures() -> None:
    with pytest.raises(ValueError, match="signatures"):
        make_release_decision(signatures=[])


def test_release_candidate_rejects_invalid_gate_status() -> None:
    with pytest.raises(ValueError, match="gate_status"):
        make_release_candidate(gate_status="MAYBE")


def test_human_scenario_rejects_invalid_difficulty() -> None:
    with pytest.raises(ValueError, match="difficulty"):
        make_scenario(difficulty="impossible")


def test_human_near_miss_rejects_score_out_of_range() -> None:
    with pytest.raises(ValueError, match="operator_message_quality_score"):
        make_near_miss(operator_message_quality_score=1.5)


# ---------------------------------------------------------------------------
# Exhaustive: every factory must be import-clean & produce a valid object
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("factory", ALL_FACTORIES)
def test_each_factory_produces_valid_object(factory) -> None:
    obj = factory()
    assert obj is not None
    pk_field = PRIMARY_KEY_MAP[type(obj)]
    pk_value = getattr(obj, pk_field)
    assert isinstance(pk_value, str) and len(pk_value) > 4
