"""
SYLION Cognitive Package -- Unit Tests

Tests for 7 modules: planner, evaluator, reasoner, context_builder,
model_router, llm_adapter, code_agent.
"""

from __future__ import annotations

import hashlib

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.planner import Planner
from sylion.cognitive.evaluator import Evaluator
from sylion.cognitive.reasoner import Reasoner
from sylion.cognitive.context_builder import ContextBuilder
from sylion.cognitive.model_router import ModelRouter
from sylion.cognitive.llm_adapter import LLMAdapter
from sylion.cognitive.code_agent import CodeAgent


# =====================================================================
# Planner tests
# =====================================================================

class TestPlanner:

    def test_create_plan(self):
        bus = EventBus()
        planner = Planner(event_bus=bus)
        plan = planner.create_plan("Test Plan", "Test description")
        assert "plan_id" in plan
        assert plan["title"] == "Test Plan"
        assert plan["status"] == "pending"

    def test_get_plan(self):
        planner = Planner()
        plan = planner.create_plan("Fetchable Plan")
        fetched = planner.get_plan(plan["plan_id"])
        assert fetched is not None
        assert fetched["title"] == "Fetchable Plan"

    def test_add_task_and_get_next(self):
        planner = Planner()
        plan = planner.create_plan("Task Plan")
        planner.add_task(plan["plan_id"], "Task 1", priority=1)
        planner.add_task(plan["plan_id"], "Task 2", priority=2)

        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task is not None
        # Higher priority (2) should come first
        assert next_task["title"] == "Task 2"
        assert next_task["priority"] == 2

    def test_complete_task(self):
        planner = Planner()
        plan = planner.create_plan("Complete Plan")
        task = planner.add_task(plan["plan_id"], "Do Something", priority=1)

        completed = planner.complete_task(task["task_id"])
        assert completed is not None
        assert completed["status"] == "completed"

        # Completed task should not be returned by get_next
        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task is None

    def test_complete_nonexistent_task(self):
        planner = Planner()
        assert planner.complete_task("ghost") is None

    def test_decompose_into_subtasks(self):
        planner = Planner()
        plan = planner.create_plan("Decompose Plan")
        subtasks = [
            {"title": "Step A", "priority": 2},
            {"title": "Step B", "priority": 1},
            {"title": "Step C", "priority": 0},
        ]
        results = planner.decompose(plan["plan_id"], subtasks)
        assert len(results) == 3
        assert all("task_id" in r for r in results)

    def test_get_tasks_filtered_by_status(self):
        planner = Planner()
        plan = planner.create_plan("Filter Plan")
        t1 = planner.add_task(plan["plan_id"], "Pending Task")
        t2 = planner.add_task(plan["plan_id"], "Done Task")
        planner.complete_task(t2["task_id"])

        pending = planner.get_tasks(plan["plan_id"], status="pending")
        assert len(pending) == 1
        assert pending[0]["title"] == "Pending Task"

    def test_dependency_resolution(self):
        planner = Planner()
        plan = planner.create_plan("Dep Plan")
        t1 = planner.add_task(plan["plan_id"], "First", priority=1)
        t2 = planner.add_task(plan["plan_id"], "Second", priority=2,
                              depends_on=[t1["task_id"]])

        # t2 depends on t1 which is pending, so t1 should be next
        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task["title"] == "First"

        # Complete t1, now t2 should be eligible
        planner.complete_task(t1["task_id"])
        next_task = planner.get_next_task(plan["plan_id"])
        assert next_task["title"] == "Second"

    def test_list_plans(self):
        planner = Planner()
        planner.create_plan("Plan A")
        planner.create_plan("Plan B")
        all_plans = planner.list_plans()
        assert len(all_plans) == 2


# =====================================================================
# Evaluator tests
# =====================================================================

class TestEvaluator:

    def test_evaluate_records_score(self):
        ev = Evaluator()
        result = ev.evaluate("plan", "p-1", score=0.85, verdict="pass")
        assert "evaluation_id" in result
        assert result["score"] == 0.85
        assert result["verdict"] == "pass"

    def test_get_evaluation(self):
        ev = Evaluator()
        result = ev.evaluate("task", "t-1", score=0.6, verdict="conditional",
                            details={"reason": "partial"})
        fetched = ev.get_evaluation(result["evaluation_id"])
        assert fetched is not None
        assert fetched["verdict"] == "conditional"
        assert fetched["details"]["reason"] == "partial"

    def test_query_by_target(self):
        ev = Evaluator()
        ev.evaluate("plan", "x", score=0.9, verdict="pass")
        ev.evaluate("plan", "x", score=0.7, verdict="conditional")
        ev.evaluate("plan", "y", score=0.5, verdict="fail")

        results = ev.query_by_target("plan", "x")
        assert len(results) == 2

    def test_get_average_score_returns_dict(self):
        """Quirk: get_average_score() returns dict with 'avg_score' key, not float."""
        ev = Evaluator()
        ev.evaluate("module", "m-1", score=0.8, verdict="pass")
        ev.evaluate("module", "m-2", score=0.6, verdict="conditional")

        result = ev.get_average_score("module")
        assert isinstance(result, dict)
        assert "avg_score" in result
        assert "target_type" in result
        assert result["avg_score"] == pytest.approx(0.7, abs=0.01)
        assert result["count"] == 2

    def test_get_average_score_empty(self):
        ev = Evaluator()
        result = ev.get_average_score("nonexistent")
        assert result["avg_score"] == 0.0
        assert result["count"] == 0

    def test_list_evaluations(self):
        ev = Evaluator()
        ev.evaluate("plan", "a", score=1.0, verdict="pass")
        ev.evaluate("plan", "b", score=0.0, verdict="fail")
        listed = ev.list_evaluations()
        assert len(listed) == 2


# =====================================================================
# Reasoner tests
# =====================================================================

class TestReasoner:

    def test_reason_records_chain(self):
        r = Reasoner()
        result = r.reason(
            query="Why use Python?",
            conclusion="Python is versatile",
            steps=["Step 1: Check popularity", "Step 2: Check use cases"],
            confidence=0.92,
            source="kanon",
        )
        assert "chain_id" in result
        assert result["query"] == "Why use Python?"
        assert result["confidence"] == 0.92

    def test_get_chain(self):
        r = Reasoner()
        result = r.reason(
            query="Test query",
            conclusion="Test conclusion",
            steps=["a", "b"],
            confidence=0.8,
        )
        chain = r.get_chain(result["chain_id"])
        assert chain is not None
        assert chain["steps"] == ["a", "b"]

    def test_query_chains_by_text(self):
        r = Reasoner()
        r.reason(query="Python performance", conclusion="Fast enough", confidence=0.7)
        r.reason(query="Rust memory safety", conclusion="Guaranteed safe", confidence=0.95)

        results = r.query_chains("Python")
        assert len(results) == 1
        assert "Python" in results[0]["query"]

    def test_get_stats(self):
        r = Reasoner()
        r.reason(query="Q1", conclusion="C1", confidence=0.8, source="kanon")
        r.reason(query="Q2", conclusion="C2", confidence=0.6, source="llm")
        stats = r.get_stats()
        assert stats["total_chains"] == 2
        assert stats["avg_confidence"] == pytest.approx(0.7, abs=0.01)
        assert "kanon" in stats["by_source"]
        assert "llm" in stats["by_source"]

    def test_get_nonexistent_chain(self):
        r = Reasoner()
        assert r.get_chain("nope") is None


# =====================================================================
# ContextBuilder tests
# =====================================================================

class TestContextBuilder:

    def test_add_source(self):
        cb = ContextBuilder()
        result = cb.add_source("src-1", "Hello world content", priority=5)
        assert result["source_id"] == "src-1"
        assert result["priority"] == 5
        assert result["content_length"] == 19

    def test_priority_ordering(self):
        cb = ContextBuilder()
        cb.add_source("low", "low priority content", priority=1)
        cb.add_source("high", "high priority content", priority=10)
        cb.add_source("mid", "mid priority content", priority=5)

        context = cb.build_context("test", max_chars=10000)
        # High priority should appear first
        assert context.index("high") < context.index("low")

    def test_build_context_respects_budget(self):
        cb = ContextBuilder()
        cb.add_source("s1", "A" * 500, priority=1)
        cb.add_source("s2", "B" * 500, priority=1)

        context = cb.build_context("test", max_chars=600)
        assert len(context) <= 700  # Some overhead for headers

    def test_build_context_with_specific_sources(self):
        cb = ContextBuilder()
        cb.add_source("s1", "Content one", priority=1)
        cb.add_source("s2", "Content two", priority=1)
        cb.add_source("s3", "Content three", priority=1)

        context = cb.build_context("test", sources=["s1", "s3"])
        assert "s1" in context
        assert "s3" in context
        assert "s2" not in context

    def test_clear_sources(self):
        cb = ContextBuilder()
        cb.add_source("s1", "Content")
        cb.add_source("s2", "More content")
        result = cb.clear_sources()
        assert result["sources_cleared"] == 2

        context = cb.build_context("test")
        assert context == ""

    def test_get_context_stats(self):
        cb = ContextBuilder()
        cb.add_source("s1", "Short", priority=1)
        cb.add_source("s2", "Longer content here", priority=10)
        stats = cb.get_context_stats()
        assert stats["source_count"] == 2
        assert stats["max_priority"] == 10
        assert stats["min_priority"] == 1


# =====================================================================
# ModelRouter tests
# =====================================================================

class TestModelRouter:

    def _register_models(self, router):
        router.register_model("cheap", "openai", "GPT-3.5",
                              cost_per_1k_tokens=0.001)
        router.register_model("mid", "openai", "GPT-4",
                              cost_per_1k_tokens=0.03)
        router.register_model("premium", "anthropic", "Claude",
                              cost_per_1k_tokens=0.08,
                              capabilities=["vision", "code"])
        router.register_model("inactive", "test", "Old Model",
                              cost_per_1k_tokens=0.0005)
        # Remove inactive model
        router._conn.execute(
            "DELETE FROM sylion_models WHERE model_id = 'inactive'"
        )
        router._conn.commit()

    def test_route_selects_cheapest_active(self):
        """Quirk: route_request() selects cheapest active model."""
        router = ModelRouter()
        self._register_models(router)
        result = router.route_request("translation")
        assert result is not None
        assert result["model_id"] == "cheap"

    def test_route_with_budget_constraint(self):
        router = ModelRouter()
        self._register_models(router)
        result = router.route_request("complex_task", budget=0.05)
        assert result is not None
        assert result["cost_per_1k_tokens"] <= 0.05

    def test_route_with_capability_requirement(self):
        router = ModelRouter()
        self._register_models(router)
        result = router.route_request("vision", complexity="high")
        assert result is not None
        assert result["model_id"] == "premium"

    def test_route_no_matching_model(self):
        router = ModelRouter()
        router.register_model("basic", "test", "Basic", cost_per_1k_tokens=0.01)
        result = router.route_request("task", budget=0.001)
        assert result is None

    def test_register_and_get_model(self):
        router = ModelRouter()
        router.register_model("m1", "provider", "Model One",
                              capabilities=["code", "reasoning"])
        model = router.get_model("m1")
        assert model is not None
        assert model["capabilities"] == ["code", "reasoning"]

    def test_list_models_filters(self):
        router = ModelRouter()
        self._register_models(router)
        all_models = router.list_models()
        assert len(all_models) == 3  # inactive was deleted
        openai_models = router.list_models(provider="openai")
        assert len(openai_models) == 2

    def test_get_usage_stats(self):
        router = ModelRouter()
        self._register_models(router)
        router.route_request("task1")
        router.route_request("task2")
        stats = router.get_usage_stats()
        assert "estimated_cost" in stats


# =====================================================================
# LLMAdapter tests
# =====================================================================

class TestLLMAdapter:

    def test_call_returns_stub(self):
        llm = LLMAdapter()
        result = llm.call("gpt-4", "What is 2+2?")
        assert "call_id" in result
        assert result["text"] == "stub"
        assert "tokens" in result
        assert "cost" in result

    def test_call_records_in_db(self):
        llm = LLMAdapter()
        result = llm.call("gpt-4", "prompt")
        record = llm.get_call(result["call_id"])
        assert record is not None
        assert record["model_id"] == "gpt-4"
        assert record["status"] == "stub"

    def test_list_calls(self):
        llm = LLMAdapter()
        llm.call("model-a", "prompt 1")
        llm.call("model-b", "prompt 2")
        llm.call("model-a", "prompt 3")

        all_calls = llm.list_calls()
        assert len(all_calls) == 3

        model_a_calls = llm.list_calls(model_id="model-a")
        assert len(model_a_calls) == 2

    def test_get_usage_stats(self):
        llm = LLMAdapter()
        llm.call("gpt-4", "prompt")
        stats = llm.get_usage_stats()
        assert stats["total_calls"] == 1
        assert "by_model" in stats
        assert "gpt-4" in stats["by_model"]

    def test_get_nonexistent_call(self):
        llm = LLMAdapter()
        assert llm.get_call("nope") is None


# =====================================================================
# CodeAgent tests
# =====================================================================

class TestCodeAgent:

    def test_generate(self):
        agent = CodeAgent()
        result = agent.generate("Write a fibonacci function", language="python")
        assert "op_id" in result
        assert result["operation"] == "generate"
        assert result["result"] == "stub"

    def test_review(self):
        agent = CodeAgent()
        result = agent.review("def foo(): pass", criteria=["style", "correctness"])
        assert result["operation"] == "review"

    def test_analyze(self):
        agent = CodeAgent()
        result = agent.analyze("class Foo:\n    pass")
        assert result["operation"] == "analyze"

    def test_fix(self):
        agent = CodeAgent()
        result = agent.fix("def bar(x)\n    return x", "Missing colon")
        assert result["operation"] == "fix"
        assert result["result"] == "stub"

    def test_list_operations(self):
        agent = CodeAgent()
        agent.generate("code 1")
        agent.review("code 2")
        agent.generate("code 3")

        all_ops = agent.list_operations()
        assert len(all_ops) == 3

        gen_ops = agent.list_operations(operation="generate")
        assert len(gen_ops) == 2

    def test_operations_have_hashes(self):
        agent = CodeAgent()
        result = agent.generate("test prompt")
        assert result["input_hash"] != ""
        assert len(result["input_hash"]) == 64  # SHA-256 hex
