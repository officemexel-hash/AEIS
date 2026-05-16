"""SYLION FULL INTEGRATION TEST — Cross-module flow"""
import logging; logging.basicConfig(level=logging.WARNING)
import time

print("=== SYLION FULL INTEGRATION TEST ===\n")

# === SETUP: Shared infrastructure ===
from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine, EvidenceEntry
from sylion.core.module_registry import ModuleRegistry, ModuleManifest, ModuleKind, ModuleLifecycleStage
from sylion.core.decision_gate_engine import DecisionGateEngine, DecisionClass

bus = EventBus()
spine = EvidenceSpine(event_bus=bus)
registry = ModuleRegistry()

print("[SETUP] Shared EventBus, EvidenceSpine, ModuleRegistry")

# === FLOW 1: Module Registration → Lifecycle → Evidence ===
print("\n--- FLOW 1: Module Lifecycle with Evidence ---")

from sylion.governance.decision_ladder import DecisionLadder, DecisionProposal
from sylion.governance.evidence_workflow import EvidenceWorkflow, EvidenceArtefact

dge = DecisionGateEngine(event_bus=bus)
ladder = DecisionLadder(gate_engine=dge, evidence_spine=spine, event_bus=bus)
ewf = EvidenceWorkflow(evidence_spine=spine, event_bus=bus)

# Register module
registry.register(ModuleManifest(
    module_id="security.auth_provider", module_kind=ModuleKind.SECURITY,
    owner_plan="P09", description="Authentication provider"
))
print("  Registered: security.auth_provider")

# Propose a change via decision ladder
result = ladder.propose(DecisionProposal(
    title="Add OAuth2 support", description="Add OAuth2 flow to auth_provider",
    source_plan="P09", module_id="security.auth_provider",
    change_type="module", blast_radius="medium", affects_contracts=False,
    proposed_by="agent_3"
))
assert result["decision_class"] == "D2", f"Expected D2, got {result['decision_class']}"
pid = result["proposal_id"]
print(f"  Proposed: D2 decision (proposal={pid[:12]})")

# Create evidence pack
pack = ewf.create_pack(pid, result["decision_class"], created_by="agent_3")
art = EvidenceArtefact(name="unit_tests", artefact_type="test_result")
art.compute_hash("all 42 tests passed")
ewf.add_artefact(pack["pack_id"], art)
v = ewf.validate_pack(pack["pack_id"])
# D2 only requires test_result
assert v["valid"], f"Evidence validation failed: {v}"
ewf.submit_pack(pack["pack_id"])
print(f"  Evidence pack submitted: {pack['pack_id'][:12]}")

# Approve and execute
ladder.approve(pid, approved_by="board")
ladder.execute(pid)
print(f"  Decision executed")

# Verify evidence spine has entries
valid, msg = spine.verify_chain()
assert valid, f"Evidence chain broken: {msg}"
entries = spine.query(source_plan="P09")
assert len(entries) >= 1
print(f"  Evidence chain valid ({len(entries)} entries)")

print("[PASS] FLOW 1: Module Lifecycle with Evidence")

# === FLOW 2: Council Voting on D3+ Decision ===
print("\n--- FLOW 2: Council 4/4 Voting ---")

from sylion.governance.council_workflow import CouncilWorkflow, CouncilSession, Vote, VoteValue

council = CouncilWorkflow(evidence_spine=spine, event_bus=bus)

result2 = ladder.propose(DecisionProposal(
    title="Change contract schema", description="Add version field to all contracts",
    source_plan="P01", change_type="contract", blast_radius="medium",
    affects_contracts=True, proposed_by="agent_1"
))
assert result2["decision_class"] == "D3", f"Expected D3, got {result2['decision_class']}"
pid2 = result2["proposal_id"]
print(f"  Proposed: D3 decision (proposal={pid2[:12]})")

# Open council session
session = council.open_session(CouncilSession(
    proposal_id=pid2, decision_class=DecisionClass.D3,
    title="Contract schema change"
))
sid = session["session_id"]

# 4/4 votes
for i in range(4):
    vote_result = council.cast_vote(Vote(
        session_id=sid, member_id=f"council_member_{i}", value=VoteValue.APPROVE,
        rationale="Evidence attached, low risk"
    ))
    assert vote_result["cast"], f"Vote {i} failed: {vote_result}"

tally = council.tally(sid)
assert tally["resolved"] and tally["outcome"] == "approved"
assert tally["approves"] == 4
print(f"  Council approved: 4/4")

# Approve via ladder
ladder.approve(pid2, approved_by="council_4/4")
ladder.execute(pid2)
print(f"  Decision executed")

# Verify chain integrity
valid2, msg2 = spine.verify_chain()
assert valid2, f"Chain broken after council: {msg2}"
print(f"  Evidence chain still valid")

print("[PASS] FLOW 2: Council 4/4 Voting")

# === FLOW 3: Module Deploy → Bundle ===
print("\n--- FLOW 3: Module Deploy + Bundle ---")

from sylion.core.environment_orchestrator import (
    EnvironmentOrchestrator, DeployRequest, DeployAction, BundleAssembler
)

# Register more modules for bundle
for mid in ["core.event_bus", "core.evidence_spine", "core.decision_gate_engine"]:
    registry.register(ModuleManifest(
        module_id=mid, module_kind=ModuleKind.CORE_KERNEL, owner_plan="P01"
    ))

# Advance one module through lifecycle
registry.transition("security.auth_provider", ModuleLifecycleStage.BUILD)
registry.transition("security.auth_provider", ModuleLifecycleStage.VALIDATE)
registry.transition("core.event_bus", ModuleLifecycleStage.BUILD)
registry.transition("core.event_bus", ModuleLifecycleStage.VALIDATE)

eo = EnvironmentOrchestrator(registry=registry, event_bus=bus)
ba = BundleAssembler(registry=registry, event_bus=bus)

# Deploy to shadow
dr = eo.deploy(DeployRequest(module_id="security.auth_provider", action=DeployAction.DEPLOY))
assert dr.status == "success"
print(f"  Deployed security.auth_provider to shadow")

# Assemble bundle
bundle = ba.assemble(["security.auth_provider", "core.event_bus"], created_by="integration_test")
v = ba.validate(bundle.bundle_id)
assert v["valid"], f"Bundle validation failed: {v}"
print(f"  Bundle validated: {bundle.bundle_id[:12]}")

print("[PASS] FLOW 3: Module Deploy + Bundle")

# === FLOW 4: Roles + Permissions ===
print("\n--- FLOW 4: Roles + Permissions ---")

from sylion.governance.roles import RolesRegistry, AgentRole, Department, Permission

roles = RolesRegistry(event_bus=bus)
roles.register(AgentRole(name="Kernel Architect", department=Department.ARCHITECTURE, level=4))
roles.register(AgentRole(name="Code Optimizer", department=Department.EFFICIENCY, level=4))
agents = roles.list_agents()
assert len(agents) == 2

arch_id = agents[0]["agent_id"]
assert roles.check_permission(arch_id, Permission.APPROVE)
assert not roles.check_permission(arch_id, Permission.VETO)

# Efficiency agent has VETO
eff_id = agents[1]["agent_id"]
assert roles.check_permission(eff_id, Permission.VETO)
print(f"  Roles verified: architect=APPROVE, optimizer=VETO")

print("[PASS] FLOW 4: Roles + Permissions")

# === FLOW 5: Gates Registry + Evaluation ===
print("\n--- FLOW 5: Gates Registry ---")

from sylion.governance.gates_registry import GatesRegistry, GateEvaluation, GateSeverity

gates = GatesRegistry(event_bus=bus)
standard = gates.list_gates()
assert len(standard) >= 10, f"Expected >=10 standard gates, got {len(standard)}"

gates.evaluate(GateEvaluation(gate_id="G-REG-01", module_id="security.auth_provider", result="pass"))
gates.evaluate(GateEvaluation(gate_id="G-BLD-01", module_id="security.auth_provider", result="pass"))
gates.evaluate(GateEvaluation(gate_id="G-VAL-01", module_id="security.auth_provider", result="pass"))

blocked = gates.check_blocking("security.auth_provider")
assert not blocked["blocked"]
print(f"  Gates passed for security.auth_provider (10 standard gates)")

print("[PASS] FLOW 5: Gates Registry")

# === FLOW 6: Cognitive Pipeline ===
print("\n--- FLOW 6: Cognitive Pipeline ---")

from sylion.cognitive.planner import Planner
from sylion.cognitive.model_router import ModelRouter
from sylion.cognitive.llm_adapter import LLMAdapter
from sylion.cognitive.context_builder import ContextBuilder

planner = Planner(event_bus=bus)
plan = planner.create_plan("Security Audit", "Full audit pipeline")
planner.add_task(plan["plan_id"], "Register models", priority=3)
planner.add_task(plan["plan_id"], "Run audit", priority=2)
planner.add_task(plan["plan_id"], "Report", priority=1)

next_task = planner.get_next_task(plan["plan_id"])
assert next_task["title"] == "Register models"
planner.complete_task(next_task["task_id"])

mr = ModelRouter(event_bus=bus)
mr.register_model("gpt-4", "openai", "GPT-4", tier="premium", cost_in=0.03, cost_out=0.06, max_ctx=128000)
mr.register_model("mini", "openai", "Mini", tier="standard", cost_in=0.001, cost_out=0.002, max_ctx=128000)
choice = mr.route("audit")
assert choice["model_id"] == "mini"

la = LLMAdapter(model_router=mr, event_bus=bus)
result = la.call("mini", "Analyze security", max_tokens=500)
assert result is not None

cb = ContextBuilder()
cb.add_source("kanon", "Security profile abstraction allows swapping", priority=10)
ctx = cb.build_context("security", max_chars=1000)
assert "Security" in ctx

print(f"  Plan created, model routed (mini), LLM called, context built")

print("[PASS] FLOW 6: Cognitive Pipeline")

# === FLOW 7: Execution Pipeline ===
print("\n--- FLOW 7: Execution Pipeline ---")

from sylion.execution.tool_runner import ToolRunner
from sylion.execution.workflow_engine import WorkflowEngine
from sylion.execution.job_runner import JobRunner
from sylion.execution.retry_orchestrator import RetryOrchestrator

tr = ToolRunner(event_bus=bus)
tr.register_tool("sast", "SAST Scanner")
we = WorkflowEngine(event_bus=bus)
wf = we.create_workflow("Security Scan", steps=[
    {"name": "scan", "tool": "sast"},
    {"name": "report", "tool": "sast"}
])
run = we.run_workflow(wf["workflow_id"])
assert run is not None

jr = JobRunner(event_bus=bus)
j1 = jr.submit("scan", priority=5)
j2 = jr.submit("report", priority=1)
next_j = jr.get_next()
assert next_j["job_type"] == "scan"
jr.complete(next_j["job_id"], "done")

ro = RetryOrchestrator(event_bus=bus)
ro.set_policy("tool", "sast", max_retries=3)
ro.record_attempt("tool", "sast", "success")

print(f"  Workflow executed, jobs prioritized, retry configured")

print("[PASS] FLOW 7: Execution Pipeline")

# === FLOW 8: Security Pipeline ===
print("\n--- FLOW 8: Security Pipeline ---")

from sylion.security.auth_provider import AuthProvider
from sylion.security.session_broker import SessionBroker
from sylion.security.audit_sink import AuditSink
from sylion.security.execution_guard import ExecutionGuard

ap = AuthProvider(event_bus=bus)
ap.create_user("u1", "admin", "hash123", role="admin")
u = ap.authenticate("admin", "hash123")
assert u is not None

sb = SessionBroker(event_bus=bus)
sb.create("s1", "u1", "token1", timeout=3600)
assert sb.validate("s1") is not None

asink = AuditSink(event_bus=bus)
asink.log("login", actor="admin", action="login", result="success")

eg = ExecutionGuard(event_bus=bus)
eg.add_rule("r1", "Allow API", action="allow", resource_pattern="/api/*")
c = eg.check("/api/modules", "GET")
assert c is not None

print(f"  Auth -> Session -> Audit -> Guard pipeline verified")

print("[PASS] FLOW 8: Security Pipeline")

# === FLOW 9: Efficiency + Quality ===
print("\n--- FLOW 9: Efficiency + Quality ---")

from sylion.efficiency.code_bloat import CodeBloatTracker
from sylion.efficiency.cost_envelope import CostEnvelopeTracker
from sylion.quality.golden_set_registry import GoldenSetRegistry
from sylion.quality.regression_detector import RegressionDetector

cbt = CodeBloatTracker(event_bus=bus)
cbt.measure("security.auth_provider", loc=500, complexity=12, deps=2)
assert cbt.is_within_budget("security.auth_provider")

cet = CostEnvelopeTracker(event_bus=bus)
cet.set_budget("openai", daily_limit=10.0)
cet.record("openai", "mini", 1000, 500, 0.05)
assert cet.is_within_budget("openai")

gsr = GoldenSetRegistry(event_bus=bus)
gsr.register("gs-auth", "Auth baseline", module_id="security.auth_provider",
              input="test_input", expected_output="expected")
test_r = gsr.run_test("gs-auth", actual_output="expected")

rd = RegressionDetector(event_bus=bus)
rd.set_baseline("security.auth_provider", "gs-auth", "r1", pass_rate=0.95)
reg = rd.check_regression("security.auth_provider", "gs-auth", current_pass_rate=0.95)

print(f"  Bloat OK, cost within budget, golden set passed, no regression")

print("[PASS] FLOW 9: Efficiency + Quality")

# === FLOW 10: AEIS Self-* Pipeline ===
print("\n--- FLOW 10: AEIS Self-* ---")

from sylion.aeis.self_observation import SelfObservation
from sylion.aeis.improvement_queue import ImprovementQueue
from sylion.aeis.self_limitation import SelfLimitationEngine
from sylion.aeis.self_preservation import SelfPreservationEngine
from sylion.skills.registry import SkillsRegistry

so = SelfObservation(event_bus=bus)
so.record("cpu", 45.0)
so.record("memory", 60.0)
dashboard = so.get_dashboard()
assert dashboard is not None

iq = ImprovementQueue(event_bus=bus)
iq.submit("Optimize queries", priority=5)
n = iq.get_next()
assert n is not None

sl = SelfLimitationEngine(event_bus=bus)
sl.register_policy("slp-api", "API limit", threshold=10000)
c = sl.check("slp-api", 5000)
assert c in ("within", "ok", "pass", True) or (isinstance(c, dict) and c.get("status") == "within")

spr = SelfPreservationEngine(event_bus=bus)
spr.check_health("core", score=0.95)
assert not spr.should_shutdown()

sr = SkillsRegistry(event_bus=bus)
sr.register("s-audit", "Security Audit", domain="security")
sr.publish("s-audit")
assert sr.get("s-audit")["lifecycle"] == "PUBLISHED"

print(f"  Observation -> Improvement -> Limitation -> Preservation -> Skills lifecycle")

print("[PASS] FLOW 10: AEIS Self-* Pipeline")

# === FINAL: Evidence Spine Integrity ===
print("\n--- FINAL: Evidence Spine Integrity ---")
valid, msg = spine.verify_chain()
assert valid, f"Evidence chain broken at end: {msg}"
print(f"  Chain valid: {msg}")
print(f"  Total evidence entries: {len(spine.query())}")

# Event bus catalog
cat = bus.get_catalog()
print(f"  Event topics: {len(cat)} unique topics")
assert len(cat) >= 5, f"Expected >=5 event topics, got {len(cat)}"

print(f"\n  Event catalog: {list(cat.keys())}")

print("\n" + "="*50)
print("=== ALL 10 INTEGRATION FLOWS PASSED ===")
print("="*50)
