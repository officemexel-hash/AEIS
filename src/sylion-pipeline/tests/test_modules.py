"""Tests for SYLION AEIS memory, cognitive, and execution modules."""
import pytest


# --- Memory ---
def test_kanon_access(bus):
    from sylion.memory.kanon_access import KanonAccess
    ka = KanonAccess(event_bus=bus)
    ka.load_text("# Section 1\nContent here.\n\n# Section 2\nMore content.")
    sections = ka.list_sections()
    assert len(sections) >= 2


def test_compact_layer(bus):
    from sylion.memory.compact_layer import CompactLayer
    cl = CompactLayer(event_bus=bus)
    text = "Hello world.\n" * 10 + "Unique line here.\n"
    result = cl.compact(text)
    assert "compacted" in result
    assert result["ratio"] >= 1.0


def test_evidence_store(bus):
    from sylion.memory.evidence_store import EvidenceStore
    es = EvidenceStore(event_bus=bus)
    es.store(evidence_id="ev1", pack_id="p1", artefact_type="test", name="ev1", content="data")
    r = es.retrieve("ev1")
    assert r is not None


def test_self_model_store(bus):
    from sylion.memory.self_model_store import SelfModelStore
    sms = SelfModelStore(event_bus=bus)
    sms.initialize("model1", capabilities={"competence": 0.85})
    sms.snapshot("model1", reason="test")
    latest = sms.get_latest("model1")
    assert latest is not None


def test_indexer():
    from sylion.memory.indexer import Indexer
    idx = Indexer()
    idx.index_section("s1", "Python Testing", "Python testing module integration")
    results = idx.search("python testing")
    assert len(results) >= 1


def test_retrieval():
    from sylion.memory.retrieval import Retrieval
    ret = Retrieval()
    ret.indexer.index_section("d1", "Security Audit", "Security audit pipeline for autonomous systems")
    ctx = ret.get_context("security", max_tokens=500)
    assert "security" in ctx.lower() or "audit" in ctx.lower()


# --- Cognitive ---
def test_planner(bus):
    from sylion.cognitive.planner import Planner
    p = Planner(event_bus=bus)
    plan = p.create_plan("Test Plan", "Description")
    assert "plan_id" in plan
    t1 = p.add_task(plan["plan_id"], "Task 1", priority=2)
    t2 = p.add_task(plan["plan_id"], "Task 2", priority=1)
    nt = p.get_next_task(plan["plan_id"])
    assert nt is not None
    p.complete_task(nt["task_id"])


def test_model_router(bus):
    from sylion.cognitive.model_router import ModelRouter
    mr = ModelRouter(event_bus=bus)
    mr.register_model("gpt-4", "openai", "GPT-4", cost_per_1k_tokens=0.03)
    mr.register_model("mini", "openai", "Mini", cost_per_1k_tokens=0.001)
    choice = mr.route_request("simple task")
    assert choice["model_id"] == "mini"


def test_llm_adapter(bus):
    from sylion.cognitive.llm_adapter import LLMAdapter
    from sylion.cognitive.model_router import ModelRouter
    mr = ModelRouter(event_bus=bus)
    mr.register_model("test", "test", "Test", cost_per_1k_tokens=0.001)
    la = LLMAdapter(model_router=mr, event_bus=bus)
    result = la.call("test", "Hello", max_tokens=100)
    assert result is not None


def test_evaluator(bus):
    from sylion.cognitive.evaluator import Evaluator
    ev = Evaluator(event_bus=bus)
    crit = ev.create_criteria("quality", description="Overall quality", weight=1.0)
    criteria_id = crit["criteria_id"]
    evaluation = ev.create_evaluation("test_target", "test_type", criteria_ids=[criteria_id])
    evaluation_id = evaluation["evaluation_id"]
    ev.score_criterion(evaluation_id, criteria_id, score=0.9, notes="pass")
    ev.complete_evaluation(evaluation_id)
    summary = ev.get_evaluation_summary(evaluation_id)
    assert summary["weighted_score"] == 0.9


def test_context_builder():
    from sylion.cognitive.context_builder import ContextBuilder
    cb = ContextBuilder()
    cb.add_source("s1", "Important security context", priority=10)
    cb.add_source("s2", "Less relevant info", priority=1)
    ctx = cb.build_context("security", max_chars=500)
    assert "security" in ctx.lower()


# --- Execution ---
def test_tool_runner(bus):
    from sylion.execution.tool_runner import ToolRunner
    tr = ToolRunner(event_bus=bus)
    tr.register_tool("sast", "SAST Scanner")
    r = tr.execute("sast", {"target": "src/"})
    assert r is not None


def test_workflow_engine(bus):
    from sylion.execution.workflow_engine import WorkflowEngine
    we = WorkflowEngine(event_bus=bus)
    wf = we.create_workflow("Test WF", steps=[{"name": "step1", "tool": "test"}])
    assert "workflow_id" in wf
    run = we.run_workflow(wf["workflow_id"])
    assert run is not None


def test_job_runner(bus):
    from sylion.execution.job_runner import JobRunner
    jr = JobRunner(event_bus=bus)
    jr.submit("high_prio", priority=5)
    jr.submit("low_prio", priority=1)
    nt = jr.get_next()
    assert nt["job_type"] == "high_prio"
    jr.complete(nt["job_id"], "done")


def test_retry_orchestrator(bus):
    from sylion.execution.retry_orchestrator import RetryOrchestrator
    ro = RetryOrchestrator(event_bus=bus)
    ro.create_policy("tool-sast", max_retries=3)
    ro.register_attempt("tool", "sast", error_type="test_error", error_message="test")
    attempts = ro.get_attempts(operation_type="tool")
    assert len(attempts) >= 1
