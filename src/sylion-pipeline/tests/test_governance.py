"""Tests for SYLION AEIS governance modules."""
import pytest


def test_decision_ladder_propose(bus, spine):
    from sylion.core.decision_gate_engine import DecisionGateEngine
    from sylion.governance.decision_ladder import DecisionLadder, DecisionProposal
    dge = DecisionGateEngine(event_bus=bus)
    ladder = DecisionLadder(gate_engine=dge, evidence_spine=spine, event_bus=bus)
    result = ladder.propose(DecisionProposal(
        title="Test", description="test", source_plan="P01",
        change_type="config", blast_radius="low", proposed_by="agent_1"
    ))
    assert "proposal_id" in result
    assert result["decision_class"] in ("D0", "D1")


def test_decision_ladder_approve_execute(bus, spine):
    from sylion.core.decision_gate_engine import DecisionGateEngine
    from sylion.governance.decision_ladder import DecisionLadder, DecisionProposal
    dge = DecisionGateEngine(event_bus=bus)
    ladder = DecisionLadder(gate_engine=dge, evidence_spine=spine, event_bus=bus)
    result = ladder.propose(DecisionProposal(
        title="T", description="t", source_plan="P01",
        change_type="module", blast_radius="medium", proposed_by="a1"
    ))
    pid = result["proposal_id"]
    ladder.approve(pid, approved_by="board")
    ladder.execute(pid)


def test_council_workflow(bus, spine):
    from sylion.governance.council_workflow import CouncilWorkflow, CouncilSession, Vote, VoteValue
    from sylion.core.decision_gate_engine import DecisionClass
    cw = CouncilWorkflow(evidence_spine=spine, event_bus=bus)
    session = cw.open_session(CouncilSession(proposal_id="p1", decision_class=DecisionClass.D3, title="Test"))
    sid = session["session_id"]
    for i in range(4):
        r = cw.cast_vote(Vote(session_id=sid, member_id=f"m{i}", value=VoteValue.APPROVE, rationale="ok"))
        assert r["cast"]
    tally = cw.tally(sid)
    assert tally["resolved"]
    assert tally["outcome"] == "approved"


def test_roles(bus):
    from sylion.governance.roles import RolesManager
    roles = RolesManager(event_bus=bus)
    role = roles.create_role("Architect", permissions_list=["approve", "read", "write"])
    user_id = "user_001"
    roles.assign_role(role["role_id"], user_id, assigned_by="admin")
    assert roles.check_permission(user_id, "approve")


def test_gates_registry(bus):
    from sylion.governance.gates_registry import GatesRegistry, GateEvaluation
    gates = GatesRegistry(event_bus=bus)
    # Create gates to populate the registry (no longer pre-seeded)
    for i in range(12):
        gates.create_gate(f"gate-{i:02d}", gate_type="quality", scope="global")
    standard = gates.list_gates()
    assert len(standard) >= 10
    gate_id = standard[0]["gate_id"]
    gates.evaluate(GateEvaluation(gate_id=gate_id, module_id="test.mod", result="pass"))
    blocked = gates.check_blocking("test.mod")
    assert not blocked["blocked"]


def test_evidence_workflow(bus, spine):
    from sylion.governance.evidence_workflow import EvidenceWorkflow, EvidenceArtefact
    ewf = EvidenceWorkflow(evidence_spine=spine, event_bus=bus)
    pack = ewf.create_pack("prop1", "D2", created_by="test")
    art = EvidenceArtefact(name="unit_tests", artefact_type="test_result")
    art.compute_hash("all tests passed")
    ewf.add_artefact(pack["pack_id"], art)
    v = ewf.validate_pack(pack["pack_id"])
    assert v["valid"]


def test_policy_registry(bus):
    from sylion.governance.policy_registry import PolicyRegistry
    pr = PolicyRegistry(event_bus=bus)
    pr.register("POL-01", "Test policy", category="test", enforcement="advisory")
    p = pr.get("POL-01")
    assert p is not None
    assert p["name"] == "Test policy"


def test_self_explanation_validator(bus):
    from sylion.governance.self_explanation_validator import SelfExplanationValidator
    sev = SelfExplanationValidator(event_bus=bus)
    tmpl = sev.create_template(
        "reasoning", "decision",
        required_fields_json=[{"name": "explanation_text"}],
        quality_criteria_json=[{"field": "explanation_text", "min_length": 10}],
    )
    result = sev.validate_explanation(
        tmpl["template_id"],
        {"explanation_text": "Because X implies Y, we should Z"},
    )
    assert result["passed"]
