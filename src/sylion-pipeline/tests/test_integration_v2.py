"""
SYLION AEIS Integration Test v2 — Cross-module flows through new infrastructure.

Covers:
  Flow 1: Full Module Lifecycle with Gates
  Flow 2: Contract Registry + Decision Boundaries
  Flow 3: Evidence Pack → Decision Flow
  Flow 4: Security Profile Swap
  Flow 5: Autonomy Controller (Self-Limitation)
  Flow 6: Rollback Contract (Decision Ladder rollback)

All tests use :memory: SQLite via conftest.py fixtures.
"""
import time

import pytest

# ---------------------------------------------------------------------------
# Core imports (used across multiple flows)
# ---------------------------------------------------------------------------
from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine, EvidenceEntry
from sylion.core.module_registry import (
    ModuleRegistry, ModuleManifest, ModuleKind, ModuleLifecycleStage,
)
from sylion.core.decision_gate_engine import DecisionGateEngine, DecisionClass
from sylion.core.contract_registry import ContractRegistry, Contract, ContractType

from sylion.governance.decision_ladder import DecisionLadder, DecisionProposal
from sylion.governance.decision_boundaries import DecisionBoundaryMap
from sylion.governance.evidence_workflow import EvidenceWorkflow, EvidenceArtefact
from sylion.governance.council_workflow import (
    CouncilWorkflow, CouncilSession, Vote, VoteValue, SessionStatus,
)
from sylion.governance.gates_registry import GatesRegistry, GateEvaluation, GateSeverity
from sylion.governance.policy_registry import PolicyRegistry

from sylion.security.profile_swap import ProfileSwapManager, SwapDirection
from sylion.aeis.self_limitation import SelfLimitationEngine


# ===========================================================================
# Flow 1: Full Module Lifecycle with Gates
# ===========================================================================

class TestFlow1ModuleLifecycleWithGates:
    """Register module → transition through all lifecycle stages → verify gate enforcement."""

    def test_full_lifecycle_with_gate_enforcement(self, bus, registry, spine):
        # -- Setup --
        dge = DecisionGateEngine(event_bus=bus)
        council = CouncilWorkflow(evidence_spine=spine, event_bus=bus)
        gates = GatesRegistry(event_bus=bus)
        enforcer = __import__(
            "sylion.core.lifecycle_gates", fromlist=["LifecycleGateEnforcer"]
        ).LifecycleGateEnforcer(council=council, spine=spine)

        # The registry uses on_event callbacks, not EventBus.publish.
        # Bridge them by registering a callback that publishes to the bus.
        emitted = []
        registry.on_event(lambda etype, payload: emitted.append({"type": etype, "payload": payload}))

        # Register module in DRAFT
        registry.register(ModuleManifest(
            module_id="lifecycle.test_mod",
            module_kind=ModuleKind.CORE_KERNEL,
            owner_plan="P01",
            description="Lifecycle test module",
        ))
        mod = registry.get("lifecycle.test_mod")
        assert mod is not None
        assert mod["lifecycle"] == "draft"
        enforcer.record_stage_entry("lifecycle.test_mod", "draft")

        # draft → build (no gate rule → always allowed)
        result = enforcer.check_gate("lifecycle.test_mod", "build", registry)
        assert result["allowed"], f"Gate to build blocked: {result['reasons']}"
        registry.transition("lifecycle.test_mod", ModuleLifecycleStage.BUILD)
        enforcer.record_stage_entry("lifecycle.test_mod", "build")
        assert registry.get("lifecycle.test_mod")["lifecycle"] == "build"

        # build → validate (gate: heartbeat within 1h — module just touched, should pass)
        # Force a fresh heartbeat
        registry.heartbeat("lifecycle.test_mod")
        result = enforcer.check_gate("lifecycle.test_mod", "validate", registry)
        assert result["allowed"], f"Gate to validate blocked: {result['reasons']}"
        registry.transition("lifecycle.test_mod", ModuleLifecycleStage.VALIDATE)
        enforcer.record_stage_entry("lifecycle.test_mod", "validate")
        assert registry.get("lifecycle.test_mod")["lifecycle"] == "validate"

        # Evaluate gates for the module
        gates.evaluate(GateEvaluation(gate_id="G-REG-01", module_id="lifecycle.test_mod", result="pass"))
        gates.evaluate(GateEvaluation(gate_id="G-BLD-01", module_id="lifecycle.test_mod", result="pass"))
        gates.evaluate(GateEvaluation(gate_id="G-VAL-01", module_id="lifecycle.test_mod", result="pass"))

        blocked = gates.check_blocking("lifecycle.test_mod")
        assert not blocked["blocked"], f"Module blocked by gates: {blocked['blocked_by']}"

        # validate → shadow (gate: requires evidence in spine)
        # Add evidence to satisfy the gate
        spine.append(EvidenceEntry(
            source_plan="lifecycle.test_mod",
            event_type="validation_report",
            payload={"status": "passed", "tests": 42},
        ))
        result = enforcer.check_gate("lifecycle.test_mod", "shadow", registry)
        assert result["allowed"], f"Gate to shadow blocked: {result['reasons']}"
        registry.transition("lifecycle.test_mod", ModuleLifecycleStage.SHADOW)
        enforcer.record_stage_entry("lifecycle.test_mod", "shadow")

        # shadow → dual (gate: 72h in shadow — bypass with backdated timestamp)
        past = time.time() - (73 * 3600)
        enforcer.record_stage_entry("lifecycle.test_mod", "shadow", entered_at=past)
        result = enforcer.check_gate("lifecycle.test_mod", "dual", registry)
        assert result["allowed"], f"Gate to dual blocked: {result['reasons']}"
        registry.transition("lifecycle.test_mod", ModuleLifecycleStage.DUAL)
        enforcer.record_stage_entry("lifecycle.test_mod", "dual")

        # dual → cutover (gate: 48h in dual + Council D3 approval)
        past_dual = time.time() - (49 * 3600)
        enforcer.record_stage_entry("lifecycle.test_mod", "dual", entered_at=past_dual)

        # Without council approval → blocked
        result = enforcer.check_gate("lifecycle.test_mod", "cutover", registry)
        assert not result["allowed"], "Expected cutover to be blocked without council"
        assert any("Council" in r for r in result["reasons"])

        # Create a council session and approve for this module
        session = council.open_session(CouncilSession(
            proposal_id="prop-lifecycle-cutover",
            decision_class=DecisionClass.D3,
            title="Cutover for lifecycle.test_mod",
        ))
        sid = session["session_id"]
        for i in range(4):
            council.cast_vote(Vote(
                session_id=sid, member_id=f"cm_{i}",
                value=VoteValue.APPROVE, rationale="Ready for cutover",
            ))
        tally = council.tally(sid)
        assert tally["resolved"] and tally["outcome"] == "approved"

        # Now cutover gate should pass
        result = enforcer.check_gate("lifecycle.test_mod", "cutover", registry)
        assert result["allowed"], f"Gate to cutover still blocked: {result['reasons']}"
        registry.transition("lifecycle.test_mod", ModuleLifecycleStage.CUTOVER)
        enforcer.record_stage_entry("lifecycle.test_mod", "cutover")

        # cutover → stable (gate: 24h in cutover + evidence)
        past_cutover = time.time() - (25 * 3600)
        enforcer.record_stage_entry("lifecycle.test_mod", "cutover", entered_at=past_cutover)
        spine.append(EvidenceEntry(
            source_plan="lifecycle.test_mod",
            event_type="cutover_report",
            payload={"status": "stable"},
        ))
        result = enforcer.check_gate("lifecycle.test_mod", "stable", registry)
        assert result["allowed"], f"Gate to stable blocked: {result['reasons']}"
        registry.transition("lifecycle.test_mod", ModuleLifecycleStage.STABLE)
        assert registry.get("lifecycle.test_mod")["lifecycle"] == "stable"

        # Verify events were emitted at transitions
        transition_events = [e for e in emitted if e["type"] == "module.lifecycle.transition"]
        assert len(transition_events) >= 6, (
            f"Expected >=6 transition events, got {len(transition_events)}"
        )


# ===========================================================================
# Flow 2: Contract Registry + Decision Boundaries
# ===========================================================================

class TestFlow2ContractRegistryDecisionBoundaries:
    """Publish contracts → check compatibility → register module with D3 boundary."""

    def test_contract_and_boundary_flow(self, bus, registry, spine):
        dge = DecisionGateEngine(event_bus=bus)
        ladder = DecisionLadder(gate_engine=dge, evidence_spine=spine, event_bus=bus)
        boundary = DecisionBoundaryMap()
        contract_reg = ContractRegistry(event_bus=bus)

        # -- Publish contracts --
        c1 = contract_reg.publish(Contract(
            name="auth.v1", contract_type=ContractType.GRPC_SERVICE,
            version="1.0.0", schema_def="message AuthRequest { string token; }",
            producer_module="security.auth_provider",
            consumer_modules=["core.event_bus"],
            description="Authentication contract",
        ))
        assert c1["version"] == "1.0.0"
        assert c1["breaking"] is False  # first publish, no previous version

        # Check compatibility for minor bump
        compat = contract_reg.check_compatibility("auth.v1", "1.1.0")
        assert compat["compatible"] is True
        assert compat["breaking"] is False

        # Check compatibility for major bump (breaking)
        compat_break = contract_reg.check_compatibility("auth.v1", "2.0.0")
        assert compat_break["breaking"] is True
        assert compat_break["compatible"] is False

        # -- Register module with D3 boundary --
        registry.register(ModuleManifest(
            module_id="contracts.mod_a",
            module_kind=ModuleKind.GOVERNANCE,
            owner_plan="P03",
            decision_class_entry="D3",
            description="Module at D3 boundary",
        ))

        # Get boundary
        bnd = boundary.get_boundary("contracts.mod_a", registry)
        assert bnd["allowed"] is True
        assert bnd["decision_class"] == "D3"
        assert bnd["requires_council"] is True

        # Attempt D3 decision without council → blocked
        v = boundary.validate_decision(
            "contracts.mod_a", "D3", registry,
            council_approved=False,
        )
        assert v["valid"] is False
        assert "council_approval" in v["missing_requirements"]

        # Attempt D3 decision with council approved → allowed
        v = boundary.validate_decision(
            "contracts.mod_a", "D3", registry,
            council_approved=True,
        )
        assert v["valid"] is True
        assert v["missing_requirements"] == []

        # Create Council session, vote 4/4 → D3 allowed
        council = CouncilWorkflow(evidence_spine=spine, event_bus=bus)
        session = council.open_session(CouncilSession(
            proposal_id="prop-contract-d3",
            decision_class=DecisionClass.D3,
            title="Contract schema change for mod_a",
        ))
        sid = session["session_id"]
        for i in range(4):
            r = council.cast_vote(Vote(
                session_id=sid, member_id=f"c_member_{i}",
                value=VoteValue.APPROVE,
                rationale="Contract change reviewed",
            ))
            assert r["cast"], f"Vote {i} failed: {r}"

        tally = council.tally(sid)
        assert tally["resolved"]
        assert tally["outcome"] == "approved"
        assert tally["approves"] == 4

        # Verify the session is now in closed_approved status
        sess = council.get_session(sid)
        assert sess["status"] == SessionStatus.CLOSED_APPROVED.value

        # Publish breaking contract version — verify event emitted
        contract_events = []
        bus.subscribe("contract.published", lambda e: contract_events.append(e))
        c2 = contract_reg.publish(Contract(
            name="auth.v1", contract_type=ContractType.GRPC_SERVICE,
            version="2.0.0", schema_def="message AuthRequest { string token; int expires; }",
            producer_module="security.auth_provider",
        ))
        assert c2["breaking"] is True


# ===========================================================================
# Flow 3: Evidence Pack → Decision Flow
# ===========================================================================

class TestFlow3EvidencePackDecisionFlow:
    """Create EvidencePack → add artefacts → submit → validate → use for D3 decision."""

    def test_evidence_pack_to_decision(self, bus, registry, spine):
        dge = DecisionGateEngine(event_bus=bus)
        ladder = DecisionLadder(gate_engine=dge, evidence_spine=spine, event_bus=bus)
        ewf = EvidenceWorkflow(evidence_spine=spine, event_bus=bus)
        council = CouncilWorkflow(evidence_spine=spine, event_bus=bus)

        # Propose a D3 decision
        result = ladder.propose(DecisionProposal(
            title="Add rate limiter", description="Rate limiting for API",
            source_plan="P06", module_id="security.rate_limiter",
            change_type="contract", blast_radius="medium",
            affects_contracts=True, proposed_by="agent_2",
        ))
        assert result["decision_class"] == "D3"
        pid = result["proposal_id"]

        # Create evidence pack
        pack = ewf.create_pack(pid, "D3", created_by="agent_2")
        assert pack["status"] == "draft"
        pack_id = pack["pack_id"]

        # Add required artefacts for D3: test_result, benchmark, review
        art_test = EvidenceArtefact(name="unit_tests", artefact_type="test_result")
        art_test.compute_hash("all 50 tests passed")
        ewf.add_artefact(pack_id, art_test)

        art_bench = EvidenceArtefact(name="perf_benchmark", artefact_type="benchmark")
        art_bench.compute_hash("latency p99=12ms")
        ewf.add_artefact(pack_id, art_bench)

        art_review = EvidenceArtefact(name="code_review", artefact_type="review")
        art_review.compute_hash("LGTM by reviewer")
        ewf.add_artefact(pack_id, art_review)

        # Validate pack
        v = ewf.validate_pack(pack_id)
        assert v["valid"], f"Evidence pack validation failed: {v}"
        assert v["artefacts_count"] == 3
        assert v["missing_types"] == []

        # Submit pack — anchors to EvidenceSpine
        s = ewf.submit_pack(pack_id)
        assert s["submitted"]

        # Verify chain integrity
        valid, msg = spine.verify_chain()
        assert valid, f"Evidence chain broken: {msg}"

        # Verify the pack is now in submitted status
        fetched = ewf.get_pack(pack_id)
        assert fetched["status"] == "submitted"
        assert len(fetched["artefacts"]) == 3

        # Use the proposal for Council D3 approval
        session = council.open_session(CouncilSession(
            proposal_id=pid, decision_class=DecisionClass.D3,
            title="Rate limiter D3 approval",
            evidence_ref=pack_id,
        ))
        sid = session["session_id"]
        for i in range(4):
            council.cast_vote(Vote(
                session_id=sid, member_id=f"cm_{i}",
                value=VoteValue.APPROVE,
                rationale="Evidence pack submitted and validated",
            ))
        tally = council.tally(sid)
        assert tally["resolved"] and tally["outcome"] == "approved"

        # Approve and execute the decision via ladder
        ladder.approve(pid, approved_by="council_4/4")
        ladder.execute(pid)
        prop = ladder.get_proposal(pid)
        assert prop["status"] == "executed"

        # Verify evidence recorded in spine for the full flow
        entries = spine.query(event_type="decision.proposed")
        assert len(entries) >= 1
        entries_approved = spine.query(event_type="decision.approved")
        assert len(entries_approved) >= 1

        # Final chain integrity check
        valid2, msg2 = spine.verify_chain()
        assert valid2, f"Evidence chain broken after full flow: {msg2}"


# ===========================================================================
# Flow 4: Security Profile Swap
# ===========================================================================

class TestFlow4SecurityProfileSwap:
    """Start at dev-light → swap to staging-strict → verify D4 + Council + evidence."""

    def test_security_profile_swap_flow(self, bus, registry, spine):
        # Register a couple of modules with default dev-light profile
        registry.register(ModuleManifest(
            module_id="swap.mod_alpha",
            module_kind=ModuleKind.SECURITY,
            owner_plan="P09",
            description="Alpha module",
        ))
        registry.register(ModuleManifest(
            module_id="swap.mod_beta",
            module_kind=ModuleKind.CORE_KERNEL,
            owner_plan="P01",
            description="Beta module",
        ))

        swap_mgr = ProfileSwapManager(registry=registry, event_bus=bus, spine=spine)

        # Initial state: dev-light
        assert swap_mgr.get_current_profile() == "dev-light"

        # Validate swap from dev-light → staging-strict
        validation = swap_mgr.validate_swap("dev-light", "staging-strict")
        assert validation["valid"]
        assert validation["direction"] == "upgrade"
        assert validation["decision_class"] == "D4"

        # Verify D4 decision is required → validate via boundary map
        boundary = DecisionBoundaryMap()
        registry.register(ModuleManifest(
            module_id="swap.mod_gamma",
            module_kind=ModuleKind.GOVERNANCE,
            owner_plan="P09",
            decision_class_entry="D4",
            description="Module at D4 boundary",
        ))
        v = boundary.validate_decision(
            "swap.mod_gamma", "D4", registry,
            council_approved=False, human_approved=False,
        )
        assert v["valid"] is False
        assert "council_approval" in v["missing_requirements"]
        assert "human_approval" in v["missing_requirements"]

        # Create Council session, approve 4/4
        council = CouncilWorkflow(evidence_spine=spine, event_bus=bus)
        session = council.open_session(CouncilSession(
            proposal_id="prop-profile-swap",
            decision_class=DecisionClass.D4,
            title="Profile swap: dev-light → staging-strict",
        ))
        sid = session["session_id"]
        for i in range(4):
            council.cast_vote(Vote(
                session_id=sid, member_id=f"cm_{i}",
                value=VoteValue.APPROVE,
                rationale="Security hardening approved",
            ))
        tally = council.tally(sid)
        assert tally["resolved"] and tally["outcome"] == "approved"

        # Propose the swap
        proposal = swap_mgr.propose_swap(
            "staging-strict",
            "Hardening for staging environment",
            "security_engineer",
        )
        assert proposal["proposed"]
        assert proposal["direction"] == "upgrade"
        assert proposal["decision_class"] == "D4"
        proposal_id = proposal["proposal_id"]

        # Execute the swap with proper council approval
        exec_result = swap_mgr.execute_swap(proposal_id, council_approval={
            "votes": [
                {"member_id": f"cm_{i}", "value": "approve"}
                for i in range(4)
            ],
            "human_gate": "approved",
        })
        assert exec_result["executed"]
        assert exec_result["from"] == "dev-light"
        assert exec_result["to"] == "staging-strict"
        assert exec_result["modules_updated"] >= 2  # at least alpha and beta

        # Verify all modules updated
        for mid in ["swap.mod_alpha", "swap.mod_beta", "swap.mod_gamma"]:
            mod = registry.get(mid)
            assert mod["sec_profile"] == "staging-strict", f"{mid} not updated"

        # Verify swap manager state
        assert swap_mgr.get_current_profile() == "staging-strict"
        history = swap_mgr.get_swap_history()
        assert len(history) >= 1
        assert history[0]["to"] == "staging-strict"

        # Verify evidence recorded in spine (payload is stored as JSON string)
        import json as _json
        entries = spine.query(event_type="profile_swap.executed")
        assert len(entries) >= 1
        last_payload = entries[-1]["payload"]
        if isinstance(last_payload, str):
            last_payload = _json.loads(last_payload)
        assert last_payload["to"] == "staging-strict"

        # Chain integrity still valid
        valid, msg = spine.verify_chain()
        assert valid, f"Evidence chain broken after profile swap: {msg}"


# ===========================================================================
# Flow 5: Autonomy Controller (Self-Limitation)
# ===========================================================================

class TestFlow5AutonomyController:
    """Self-Limitation Engine as autonomy controller: check stages, verify constraints."""

    def test_autonomy_stages_and_constraints(self, bus, spine):
        sle = SelfLimitationEngine(event_bus=bus)

        # -- Stage 1: observe (read-only constraints) --
        # Register an API rate limit policy: scope="api", max 10 calls per 3600s
        sle.register_policy("slp-api-rate", "api", max_calls=10, window_seconds=3600)

        # Check rate within limit — no actions recorded yet → allowed
        result = sle.check_rate("api", "client1")
        assert result["allowed"] is True
        assert result["remaining"] == 10

        # Record a few actions (below limit)
        for _ in range(5):
            sle.record_action("api", "client1", action="call", result="ok")

        # Verify no violations yet (only 5 of 10 calls used)
        violations = sle.get_violations(scope="api")
        assert len(violations) == 0

        # Record actions to exceed the limit (10 total)
        for _ in range(5):
            sle.record_action("api", "client1", action="call", result="ok")

        # 11th action should trigger a violation
        rec = sle.record_action("api", "client1", action="call", result="ok")
        assert rec["is_violation"] is True

        # Verify violation was recorded
        violations = sle.get_violations(scope="api")
        assert len(violations) >= 1

        # -- Advance to propose stage: can propose new policies --
        sle.register_policy("slp-memory", "memory", max_calls=4096, window_seconds=3600)

        result_mem = sle.check_rate("memory", "host1")
        assert result_mem["allowed"] is True

        # Check stats
        stats = sle.get_stats()
        assert stats["total_policies"] == 2
        assert stats["violation_count"] >= 1

        # Verify events emitted (action_violation fires when record_action exceeds limit)
        events = bus.query(topic="aeis.self_limitation.action_violation")
        assert len(events) >= 1


# ===========================================================================
# Flow 6: Rollback Contract (Decision Ladder rollback)
# ===========================================================================

class TestFlow6RollbackContract:
    """Create rollback plan → execute decision → detect failure → rollback → verify evidence."""

    def test_rollback_decision_flow(self, bus, registry, spine):
        dge = DecisionGateEngine(event_bus=bus)
        ladder = DecisionLadder(gate_engine=dge, evidence_spine=spine, event_bus=bus)
        council = CouncilWorkflow(evidence_spine=spine, event_bus=bus)
        policy_reg = PolicyRegistry(event_bus=bus)

        # Register a governance policy for the module
        policy_reg.register(
            "pol-deploy", "Deploy Policy",
            category="governance",
            description="Controls deployment approvals",
            rules=[{"rule": "require_rollback_plan", "enforcement": "strict"}],
            enforcement="mandatory",
        )

        # Register module
        registry.register(ModuleManifest(
            module_id="rollback.target_mod",
            module_kind=ModuleKind.EXECUTION,
            owner_plan="P05",
            description="Module targeted for rollback test",
        ))

        # Propose a change WITH a rollback plan
        result = ladder.propose(DecisionProposal(
            title="Deploy v2.0 of target_mod",
            description="Major version upgrade with rollback plan",
            source_plan="P05",
            module_id="rollback.target_mod",
            change_type="module",
            blast_radius="medium",
            reversible=True,
            rollback_plan="Revert to v1.0 and restore previous config",
            proposed_by="agent_5",
        ))
        pid = result["proposal_id"]
        assert result["decision_class"] == "D2"

        # Verify proposal stored correctly
        prop = ladder.get_proposal(pid)
        assert prop["rollback_plan"] == "Revert to v1.0 and restore previous config"
        assert prop["reversible"] == 1

        # Approve and execute
        ladder.approve(pid, approved_by="board")
        ladder.execute(pid)
        prop = ladder.get_proposal(pid)
        assert prop["status"] == "executed"

        # -- Simulate failure detected → create a new proposal for rollback --
        rollback_result = ladder.propose(DecisionProposal(
            title="ROLLBACK: Revert target_mod to v1.0",
            description="Rolling back due to production failure detected",
            source_plan="P05",
            module_id="rollback.target_mod",
            change_type="module",
            blast_radius="medium",
            reversible=True,
            rollback_plan="Restore v1.0 baseline",
            proposed_by="agent_5",
        ))
        rb_pid = rollback_result["proposal_id"]
        assert rollback_result["decision_class"] in ("D1", "D2")

        # Execute rollback
        ladder.approve(rb_pid, approved_by="emergency_board")
        ladder.execute(rb_pid)
        rb_prop = ladder.get_proposal(rb_pid)
        assert rb_prop["status"] == "executed"

        # Verify evidence recorded in spine for both original and rollback
        entries = spine.query(event_type="decision.proposed")
        assert len(entries) >= 2  # original + rollback

        entries_approved = spine.query(event_type="decision.approved")
        assert len(entries_approved) >= 2  # original + rollback

        # Verify the policy was applied
        policy_reg.apply("pol-deploy", "module", "rollback.target_mod",
                         result="rolled_back", applied_by="agent_5")
        apps = policy_reg.get_applications("pol-deploy")
        assert len(apps) >= 1
        assert apps[0]["result"] == "rolled_back"

        # Verify decision records in DGE
        decisions = dge.get_decisions(source_plan="P05")
        assert len(decisions) >= 2

        # Final chain integrity
        valid, msg = spine.verify_chain()
        assert valid, f"Evidence chain broken after rollback flow: {msg}"


# ===========================================================================
# Cross-cutting: Event Bus catalog verification
# ===========================================================================

class TestCrossCuttingEventCatalog:
    """Verify that all flows leave proper event traces."""

    def test_event_bus_catalog_after_all_flows(self, bus, registry, spine):
        # Run a minimal flow that touches multiple subsystems
        dge = DecisionGateEngine(event_bus=bus)
        ladder = DecisionLadder(gate_engine=dge, evidence_spine=spine, event_bus=bus)
        ewf = EvidenceWorkflow(evidence_spine=spine, event_bus=bus)

        registry.register(ModuleManifest(
            module_id="catalog.test_mod",
            module_kind=ModuleKind.COGNITIVE,
            owner_plan="P02",
        ))

        result = ladder.propose(DecisionProposal(
            title="Catalog test", description="Event catalog verification",
            source_plan="P02", module_id="catalog.test_mod",
            change_type="module", proposed_by="agent_test",
        ))
        pid = result["proposal_id"]

        pack = ewf.create_pack(pid, result["decision_class"], created_by="agent_test")
        art = EvidenceArtefact(name="test", artefact_type="test_result")
        art.compute_hash("pass")
        ewf.add_artefact(pack["pack_id"], art)

        # Verify event catalog has entries from multiple domains
        catalog = bus.get_catalog()
        assert "decision.proposed" in catalog or "decision.classified" in catalog
        assert "evidence.appended" in catalog or "evidence.pack_created" in catalog

        # Replay should work without errors
        count = bus.replay()
        assert count >= 1
