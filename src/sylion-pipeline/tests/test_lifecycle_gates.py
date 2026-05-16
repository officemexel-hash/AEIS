"""Tests for SYLION AEIS lifecycle gate enforcement."""
import time

import pytest

from sylion.core.evidence_spine import EvidenceEntry, EvidenceSpine
from sylion.core.lifecycle_gates import (
    GATE_RULES,
    GateRequirement,
    LifecycleGateEnforcer,
)
from sylion.core.module_registry import (
    ModuleKind,
    ModuleLifecycleStage,
    ModuleManifest,
    ModuleRegistry,
)
from sylion.core.decision_gate_engine import DecisionClass
from sylion.governance.council_workflow import (
    CouncilSession,
    CouncilWorkflow,
    SessionStatus,
    Vote,
    VoteValue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_registry_with_module(module_id: str = "test.mod",
                                lifecycle: str = "draft") -> ModuleRegistry:
    """Create a registry with a single module registered."""
    reg = ModuleRegistry()
    reg.register(ModuleManifest(
        module_id=module_id,
        module_kind=ModuleKind.CORE_KERNEL,
        owner_plan="P01",
        lifecycle_stage=ModuleLifecycleStage(lifecycle),
    ))
    return reg


def _advance_module(registry: ModuleRegistry, enforcer: LifecycleGateEnforcer,
                    module_id: str, stages: list[str]):
    """Transition a module through a sequence of stages, recording entry times."""
    for stage in stages:
        registry.transition(module_id, ModuleLifecycleStage(stage))
        enforcer.record_stage_entry(module_id, stage)


def _make_council_with_approval(module_id: str, decision_class: DecisionClass) -> CouncilWorkflow:
    """Create a council with an approved session for the given module."""
    cw = CouncilWorkflow()
    session = CouncilSession(
        proposal_id=module_id,
        decision_class=decision_class,
        title=f"Approve {module_id} lifecycle transition",
    )
    result = cw.open_session(session)
    sid = result["session_id"]

    for i in range(4):
        cw.cast_vote(Vote(
            session_id=sid,
            member_id=f"council_member_{i}",
            value=VoteValue.APPROVE,
            rationale="approved",
        ))
    return cw


# ---------------------------------------------------------------------------
# Tests: gate rules are defined correctly
# ---------------------------------------------------------------------------

class TestGateRules:
    def test_all_gated_stages_have_rules(self):
        gated = {"validate", "shadow", "dual", "cutover", "stable", "deprecated"}
        assert set(GATE_RULES.keys()) == gated

    def test_validate_requires_heartbeat(self):
        rule = GATE_RULES["validate"]
        assert rule.min_heartbeat_age_hours == 1

    def test_shadow_requires_evidence(self):
        rule = GATE_RULES["shadow"]
        assert rule.requires_evidence is True
        assert rule.evidence_type == "validation_report"

    def test_dual_requires_shadow_duration(self):
        rule = GATE_RULES["dual"]
        assert rule.min_duration_hours == 72
        assert rule.duration_from_stage == "shadow"

    def test_cutover_requires_dual_duration_and_council(self):
        rule = GATE_RULES["cutover"]
        assert rule.min_duration_hours == 48
        assert rule.duration_from_stage == "dual"
        assert rule.requires_council_approval is True
        assert rule.decision_class == "D3"

    def test_stable_requires_cutover_duration_and_evidence(self):
        rule = GATE_RULES["stable"]
        assert rule.min_duration_hours == 24
        assert rule.duration_from_stage == "cutover"
        assert rule.requires_evidence is True

    def test_deprecated_requires_council_d4(self):
        rule = GATE_RULES["deprecated"]
        assert rule.requires_council_approval is True
        assert rule.decision_class == "D4"


# ---------------------------------------------------------------------------
# Tests: validate gate (heartbeat check)
# ---------------------------------------------------------------------------

class TestValidateGate:
    def test_allows_when_heartbeat_fresh(self):
        reg = _make_registry_with_module("mod.val", "build")
        enforcer = LifecycleGateEnforcer()
        result = enforcer.check_gate("mod.val", "validate", reg)
        assert result["allowed"] is True
        assert result["reasons"] == []

    def test_blocks_when_heartbeat_stale(self):
        reg = _make_registry_with_module("mod.val", "build")
        # Manually make heartbeat stale
        reg._conn.execute(
            "UPDATE sylion_modules SET last_heartbeat = ? WHERE module_id = ?",
            (time.time() - 7200, "mod.val"),  # 2 hours ago
        )
        reg._conn.commit()

        enforcer = LifecycleGateEnforcer()
        result = enforcer.check_gate("mod.val", "validate", reg)
        assert result["allowed"] is False
        assert any("Heartbeat" in r for r in result["reasons"])

    def test_enforce_raises_on_stale_heartbeat(self):
        reg = _make_registry_with_module("mod.val2", "build")
        reg._conn.execute(
            "UPDATE sylion_modules SET last_heartbeat = ? WHERE module_id = ?",
            (time.time() - 7200, "mod.val2"),
        )
        reg._conn.commit()

        enforcer = LifecycleGateEnforcer()
        with pytest.raises(ValueError, match="Heartbeat"):
            enforcer.enforce("mod.val2", "validate", reg)

    def test_enforce_passes_on_fresh_heartbeat(self):
        reg = _make_registry_with_module("mod.val3", "build")
        enforcer = LifecycleGateEnforcer()
        enforcer.enforce("mod.val3", "validate", reg)  # should not raise


# ---------------------------------------------------------------------------
# Tests: shadow gate (evidence check)
# ---------------------------------------------------------------------------

class TestShadowGate:
    def test_blocks_when_no_evidence(self):
        reg = _make_registry_with_module("mod.shd", "validate")
        enforcer = LifecycleGateEnforcer()
        result = enforcer.check_gate("mod.shd", "shadow", reg)
        assert result["allowed"] is False
        assert any("evidence" in r.lower() for r in result["reasons"])

    def test_allows_when_evidence_present(self):
        spine = EvidenceSpine()
        spine.append(EvidenceEntry(
            source_plan="mod.shd2",
            event_type="validation_report",
            payload={"status": "pass"},
        ))

        reg = _make_registry_with_module("mod.shd2", "validate")
        enforcer = LifecycleGateEnforcer(spine=spine)
        result = enforcer.check_gate("mod.shd2", "shadow", reg)
        assert result["allowed"] is True

    def test_allows_with_any_evidence_matching_event_type(self):
        spine = EvidenceSpine()
        spine.append(EvidenceEntry(
            source_plan="some.other.plan",
            event_type="validation_report",
            payload={"ok": True},
        ))

        reg = _make_registry_with_module("mod.shd3", "validate")
        enforcer = LifecycleGateEnforcer(spine=spine)
        result = enforcer.check_gate("mod.shd3", "shadow", reg)
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# Tests: dual gate (72h shadow duration)
# ---------------------------------------------------------------------------

class TestDualGate:
    def test_blocks_when_shadow_too_short(self):
        reg = _make_registry_with_module("mod.dual", "shadow")
        enforcer = LifecycleGateEnforcer()
        # Record shadow entry just now (0 hours)
        enforcer.record_stage_entry("mod.dual", "shadow", time.time())

        result = enforcer.check_gate("mod.dual", "dual", reg)
        assert result["allowed"] is False
        assert any("shadow" in r.lower() and "72" in r for r in result["reasons"])

    def test_allows_when_shadow_long_enough(self):
        reg = _make_registry_with_module("mod.dual2", "shadow")
        enforcer = LifecycleGateEnforcer()
        # Record shadow entry 80 hours ago
        enforcer.record_stage_entry("mod.dual2", "shadow", time.time() - 80 * 3600)

        result = enforcer.check_gate("mod.dual2", "dual", reg)
        assert result["allowed"] is True

    def test_blocks_when_never_entered_shadow(self):
        reg = _make_registry_with_module("mod.dual3", "shadow")
        enforcer = LifecycleGateEnforcer()
        result = enforcer.check_gate("mod.dual3", "dual", reg)
        assert result["allowed"] is False
        assert any("No record" in r for r in result["reasons"])


# ---------------------------------------------------------------------------
# Tests: cutover gate (48h dual + Council D3)
# ---------------------------------------------------------------------------

class TestCutoverGate:
    def test_blocks_when_dual_too_short_and_no_council(self):
        reg = _make_registry_with_module("mod.cut", "dual")
        enforcer = LifecycleGateEnforcer()
        enforcer.record_stage_entry("mod.cut", "dual", time.time())

        result = enforcer.check_gate("mod.cut", "cutover", reg)
        assert result["allowed"] is False
        reasons_text = " ".join(result["reasons"])
        assert "dual" in reasons_text.lower()
        assert "Council" in reasons_text or "D3" in reasons_text

    def test_blocks_when_dual_long_enough_but_no_council(self):
        reg = _make_registry_with_module("mod.cut2", "dual")
        enforcer = LifecycleGateEnforcer()
        enforcer.record_stage_entry("mod.cut2", "dual", time.time() - 60 * 3600)

        result = enforcer.check_gate("mod.cut2", "cutover", reg)
        assert result["allowed"] is False
        assert any("Council" in r or "D3" in r for r in result["reasons"])

    def test_allows_when_dual_long_enough_and_council_approved(self):
        cw = _make_council_with_approval("mod.cut3", DecisionClass.D3)
        reg = _make_registry_with_module("mod.cut3", "dual")
        enforcer = LifecycleGateEnforcer(council=cw)
        enforcer.record_stage_entry("mod.cut3", "dual", time.time() - 50 * 3600)

        result = enforcer.check_gate("mod.cut3", "cutover", reg)
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# Tests: stable gate (24h cutover + evidence)
# ---------------------------------------------------------------------------

class TestStableGate:
    def test_blocks_when_cutover_too_short(self):
        reg = _make_registry_with_module("mod.stb", "cutover")
        enforcer = LifecycleGateEnforcer()
        enforcer.record_stage_entry("mod.stb", "cutover", time.time())

        result = enforcer.check_gate("mod.stb", "stable", reg)
        assert result["allowed"] is False

    def test_blocks_when_cutover_long_enough_but_no_evidence(self):
        reg = _make_registry_with_module("mod.stb2", "cutover")
        enforcer = LifecycleGateEnforcer()
        enforcer.record_stage_entry("mod.stb2", "cutover", time.time() - 30 * 3600)

        result = enforcer.check_gate("mod.stb2", "stable", reg)
        assert result["allowed"] is False
        assert any("evidence" in r.lower() for r in result["reasons"])

    def test_allows_when_cutover_long_enough_and_evidence_present(self):
        spine = EvidenceSpine()
        spine.append(EvidenceEntry(
            source_plan="mod.stb3",
            event_type="cutover_report",
            payload={"status": "healthy"},
        ))

        reg = _make_registry_with_module("mod.stb3", "cutover")
        enforcer = LifecycleGateEnforcer(spine=spine)
        enforcer.record_stage_entry("mod.stb3", "cutover", time.time() - 30 * 3600)

        result = enforcer.check_gate("mod.stb3", "stable", reg)
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# Tests: deprecated gate (Council D4)
# ---------------------------------------------------------------------------

class TestDeprecatedGate:
    def test_blocks_when_no_council_approval(self):
        reg = _make_registry_with_module("mod.dep", "stable")
        enforcer = LifecycleGateEnforcer()
        result = enforcer.check_gate("mod.dep", "deprecated", reg)
        assert result["allowed"] is False
        assert any("D4" in r for r in result["reasons"])

    def test_blocks_when_council_approved_but_wrong_class(self):
        cw = _make_council_with_approval("mod.dep2", DecisionClass.D3)
        reg = _make_registry_with_module("mod.dep2", "stable")
        enforcer = LifecycleGateEnforcer(council=cw)
        result = enforcer.check_gate("mod.dep2", "deprecated", reg)
        assert result["allowed"] is False

    def test_allows_when_council_d4_approved(self):
        cw = _make_council_with_approval("mod.dep3", DecisionClass.D4)
        reg = _make_registry_with_module("mod.dep3", "stable")
        enforcer = LifecycleGateEnforcer(council=cw)
        result = enforcer.check_gate("mod.dep3", "deprecated", reg)
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# Tests: ungated stages (draft, build)
# ---------------------------------------------------------------------------

class TestUngatedStages:
    def test_build_is_ungated(self):
        reg = _make_registry_with_module("mod.ung", "draft")
        enforcer = LifecycleGateEnforcer()
        result = enforcer.check_gate("mod.ung", "build", reg)
        assert result["allowed"] is True

    def test_draft_is_ungated(self):
        reg = _make_registry_with_module("mod.ung2", "draft")
        enforcer = LifecycleGateEnforcer()
        # draft has no incoming gate -- this just verifies no KeyError
        result = enforcer.check_gate("mod.ung2", "draft", reg)
        assert result["allowed"] is True


# ---------------------------------------------------------------------------
# Tests: stage entry tracking
# ---------------------------------------------------------------------------

class TestStageEntryTracking:
    def test_record_and_retrieve(self):
        enforcer = LifecycleGateEnforcer()
        ts = 1700000000.0
        enforcer.record_stage_entry("mod.track", "shadow", ts)
        assert enforcer.get_stage_entry_time("mod.track", "shadow") == ts

    def test_hours_in_stage(self):
        enforcer = LifecycleGateEnforcer()
        enforcer.record_stage_entry("mod.hours", "dual", time.time() - 5 * 3600)
        hours = enforcer.get_hours_in_stage("mod.hours", "dual")
        assert hours is not None
        assert 4.9 < hours < 5.1

    def test_unknown_stage_returns_none(self):
        enforcer = LifecycleGateEnforcer()
        assert enforcer.get_stage_entry_time("nonexistent", "shadow") is None
        assert enforcer.get_hours_in_stage("nonexistent", "shadow") is None


# ---------------------------------------------------------------------------
# Tests: unknown module
# ---------------------------------------------------------------------------

class TestUnknownModule:
    def test_check_gate_returns_not_found(self):
        reg = ModuleRegistry()  # empty
        enforcer = LifecycleGateEnforcer()
        result = enforcer.check_gate("no.such.module", "shadow", reg)
        assert result["allowed"] is False
        assert any("not found" in r for r in result["reasons"])


# ---------------------------------------------------------------------------
# Tests: enforce wrapper
# ---------------------------------------------------------------------------

class TestEnforceWrapper:
    def test_enforce_raises_value_error(self):
        reg = _make_registry_with_module("mod.enf", "validate")
        enforcer = LifecycleGateEnforcer()  # no spine -> no evidence
        with pytest.raises(ValueError, match="Lifecycle gate blocked"):
            enforcer.enforce("mod.enf", "shadow", reg)

    def test_enforce_succeeds_when_gate_passes(self):
        reg = _make_registry_with_module("mod.enf2", "build")
        enforcer = LifecycleGateEnforcer()
        # validate gate just checks heartbeat, which is fresh
        enforcer.enforce("mod.enf2", "validate", reg)  # no raise


# ---------------------------------------------------------------------------
# Tests: full lifecycle happy path
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    def test_happy_path_through_all_gates(self):
        """Exercise all gates in sequence with proper evidence and approvals."""
        module_id = "mod.happy"

        # Set up infrastructure
        spine = EvidenceSpine()
        cw = CouncilWorkflow()

        reg = ModuleRegistry()
        enforcer = LifecycleGateEnforcer(council=cw, spine=spine)

        # Register at draft
        reg.register(ModuleManifest(
            module_id=module_id,
            module_kind=ModuleKind.CORE_KERNEL,
            owner_plan="P01",
        ))

        # draft -> build (ungated)
        enforcer.enforce(module_id, "build", reg)
        reg.transition(module_id, ModuleLifecycleStage.BUILD)
        enforcer.record_stage_entry(module_id, "build")

        # build -> validate (heartbeat check -- fresh by default)
        enforcer.enforce(module_id, "validate", reg)
        reg.transition(module_id, ModuleLifecycleStage.VALIDATE)
        enforcer.record_stage_entry(module_id, "validate")

        # validate -> shadow (needs evidence)
        spine.append(EvidenceEntry(
            source_plan=module_id,
            event_type="validation_report",
            payload={"tests_passed": True},
        ))
        enforcer.enforce(module_id, "shadow", reg)
        reg.transition(module_id, ModuleLifecycleStage.SHADOW)
        enforcer.record_stage_entry(module_id, "shadow", time.time() - 80 * 3600)

        # shadow -> dual (needs 72h in shadow)
        enforcer.enforce(module_id, "dual", reg)
        reg.transition(module_id, ModuleLifecycleStage.DUAL)
        enforcer.record_stage_entry(module_id, "dual", time.time() - 55 * 3600)

        # dual -> cutover (needs 48h in dual + D3 council)
        session = CouncilSession(
            proposal_id=module_id,
            decision_class=DecisionClass.D3,
            title=f"Approve {module_id} cutover",
        )
        opened = cw.open_session(session)
        sid = opened["session_id"]
        for i in range(4):
            cw.cast_vote(Vote(session_id=sid, member_id=f"m{i}",
                              value=VoteValue.APPROVE, rationale="ok"))

        enforcer.enforce(module_id, "cutover", reg)
        reg.transition(module_id, ModuleLifecycleStage.CUTOVER)
        enforcer.record_stage_entry(module_id, "cutover", time.time() - 30 * 3600)

        # cutover -> stable (needs 24h + evidence)
        spine.append(EvidenceEntry(
            source_plan=module_id,
            event_type="cutover_complete",
            payload={"healthy": True},
        ))
        enforcer.enforce(module_id, "stable", reg)
        reg.transition(module_id, ModuleLifecycleStage.STABLE)
        enforcer.record_stage_entry(module_id, "stable")

        # stable -> deprecated (needs D4 council)
        dep_session = CouncilSession(
            proposal_id=module_id,
            decision_class=DecisionClass.D4,
            title=f"Deprecate {module_id}",
        )
        dep_opened = cw.open_session(dep_session)
        dep_sid = dep_opened["session_id"]
        for i in range(4):
            cw.cast_vote(Vote(session_id=dep_sid, member_id=f"m{i}",
                              value=VoteValue.APPROVE, rationale="ok"))
        # D4 requires human gate
        cw.human_gate_decide(dep_sid, "approved", by="admin")

        enforcer.enforce(module_id, "deprecated", reg)
        reg.transition(module_id, ModuleLifecycleStage.DEPRECATED)

        assert reg.get(module_id)["lifecycle"] == "deprecated"
