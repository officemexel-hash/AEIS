"""
SYLION Cognitive -- Model Router Tests

Covers:
  - register_model (CRUD, upsert via INSERT OR REPLACE)
  - get_model / list_models (filters, ordering, capability search)
  - route_request (capability match, budget filter, complexity-based selection)
  - record_usage (usage tracking with tokens, latency, success)
  - get_usage_stats (aggregate stats, per-model and global)
  - get_cost_report (cost breakdown by model and provider)
  - event emission
  - thread safety
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.model_router import (
    ModelRouter,
    ModelInfo,
    UsageRecord,
    COMPLEXITY_ORDER,
    CAPABILITY_COMPLEXITY_MAP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def router(bus):
    """Fresh in-memory ModelRouter wired to a test EventBus."""
    return ModelRouter(event_bus=bus)


def _register_sample_models(router):
    """Register a set of sample models for routing tests."""
    router.register_model(
        "cheap-model", "provider-a", "Cheap Model",
        capabilities=["simple_chat", "translation"],
        cost_per_1k_tokens=0.01,
    )
    router.register_model(
        "mid-model", "provider-a", "Mid Model",
        capabilities=["summarization", "code_generation", "analysis"],
        cost_per_1k_tokens=0.05,
    )
    router.register_model(
        "premium-model", "provider-b", "Premium Model",
        capabilities=["reasoning", "vision", "multi_step", "code_generation"],
        cost_per_1k_tokens=0.15,
    )
    router.register_model(
        "flagship-model", "provider-b", "Flagship Model",
        capabilities=["planning", "autonomous", "reasoning", "vision"],
        cost_per_1k_tokens=0.50,
    )


# ===========================================================================
# 1. register_model
# ===========================================================================

class TestRegisterModel:

    def test_register_returns_dict(self, router):
        result = router.register_model("gpt-4o", "openai", "GPT-4o")
        assert result["model_id"] == "gpt-4o"
        assert result["provider"] == "openai"
        assert result["model_name"] == "GPT-4o"
        assert result["capabilities"] == []
        assert result["cost_per_1k_tokens"] == 0.0

    def test_register_with_capabilities(self, router):
        result = router.register_model(
            "claude-3", "anthropic", "Claude 3",
            capabilities=["vision", "reasoning"],
            cost_per_1k_tokens=0.03,
        )
        assert result["capabilities"] == ["vision", "reasoning"]
        assert result["cost_per_1k_tokens"] == 0.03

    def test_register_emits_event(self, router, bus):
        events = []
        bus.subscribe("model_router.model.registered", lambda e: events.append(e))
        router.register_model("ev-model", "ev-prov", "Event Model")
        assert len(events) == 1
        assert events[0].payload["model_id"] == "ev-model"

    def test_register_upsert_replaces(self, router):
        router.register_model("upsert-m", "prov-a", "V1", cost_per_1k_tokens=0.01)
        router.register_model("upsert-m", "prov-b", "V2", cost_per_1k_tokens=0.05)
        model = router.get_model("upsert-m")
        assert model["provider"] == "prov-b"
        assert model["model_name"] == "V2"
        assert model["cost_per_1k_tokens"] == 0.05

    def test_register_defaults_capabilities_empty(self, router):
        result = router.register_model("def-cap", "prov", "Model")
        assert result["capabilities"] == []


# ===========================================================================
# 2. get_model / list_models
# ===========================================================================

class TestGetModel:

    def test_get_model_returns_dict(self, router):
        router.register_model("get-1", "prov", "Model 1",
                              capabilities=["chat"], cost_per_1k_tokens=0.02)
        model = router.get_model("get-1")
        assert model is not None
        assert model["model_id"] == "get-1"
        assert model["capabilities"] == ["chat"]
        assert model["cost_per_1k_tokens"] == 0.02

    def test_get_model_not_found(self, router):
        assert router.get_model("ghost") is None

    def test_get_model_parses_capabilities_json(self, router):
        router.register_model("json-cap", "p", "M",
                              capabilities=["a", "b", "c"])
        model = router.get_model("json-cap")
        assert isinstance(model["capabilities"], list)
        assert len(model["capabilities"]) == 3


class TestListModels:

    def test_list_all_models(self, router):
        _register_sample_models(router)
        models = router.list_models()
        assert len(models) == 4

    def test_list_ordered_by_cost_ascending(self, router):
        _register_sample_models(router)
        models = router.list_models()
        for i in range(len(models) - 1):
            assert models[i]["cost_per_1k_tokens"] <= models[i + 1]["cost_per_1k_tokens"]

    def test_list_filter_by_provider(self, router):
        _register_sample_models(router)
        results = router.list_models(provider="provider-a")
        assert len(results) == 2
        assert all(m["provider"] == "provider-a" for m in results)

    def test_list_filter_by_capability(self, router):
        _register_sample_models(router)
        results = router.list_models(capability="reasoning")
        assert len(results) == 2
        for m in results:
            assert "reasoning" in m["capabilities"]

    def test_list_filter_by_provider_and_capability(self, router):
        _register_sample_models(router)
        results = router.list_models(provider="provider-b", capability="vision")
        assert len(results) == 2

    def test_list_empty_when_no_match(self, router):
        _register_sample_models(router)
        results = router.list_models(provider="nonexistent")
        assert results == []

    def test_list_empty_when_no_models(self, router):
        assert router.list_models() == []


# ===========================================================================
# 3. route_request
# ===========================================================================

class TestRouteRequest:

    def test_route_by_capability(self, router):
        _register_sample_models(router)
        result = router.route_request("translation", complexity="low")
        assert result is not None
        assert result["model_id"] == "cheap-model"

    def test_route_cheapest_for_low_complexity(self, router):
        _register_sample_models(router)
        result = router.route_request("simple_chat", complexity="low")
        assert result["cost_per_1k_tokens"] == 0.01

    def test_route_prefers_expensive_for_high_complexity(self, router):
        _register_sample_models(router)
        result = router.route_request("reasoning", complexity="high")
        assert result is not None
        # Among reasoning-capable models sorted descending by cost
        assert result["model_id"] in ("premium-model", "flagship-model")
        # Should pick most expensive reasoning model
        assert result["model_id"] == "flagship-model"

    def test_route_with_budget(self, router):
        _register_sample_models(router)
        result = router.route_request("code_generation", complexity="medium", budget=0.10)
        assert result is not None
        assert result["cost_per_1k_tokens"] <= 0.10

    def test_route_budget_too_low_returns_none(self, router):
        _register_sample_models(router)
        result = router.route_request("code_generation", complexity="medium", budget=0.001)
        assert result is None

    def test_route_no_models_returns_none(self, router):
        result = router.route_request("anything")
        assert result is None

    def test_route_no_capability_match_falls_back(self, router):
        _register_sample_models(router)
        # "planning" only matches flagship, but we ask for "nonexistent_task"
        # fallback picks cheapest overall
        result = router.route_request("nonexistent_task", complexity="low")
        assert result is not None
        assert result["model_id"] == "cheap-model"

    def test_route_emits_event(self, router, bus):
        _register_sample_models(router)
        events = []
        bus.subscribe("model_router.request.routed", lambda e: events.append(e))
        router.route_request("translation", complexity="low")
        assert len(events) == 1
        assert events[0].payload["task_type"] == "translation"
        assert events[0].payload["selected_model"] == "cheap-model"

    def test_route_critical_complexity(self, router):
        _register_sample_models(router)
        result = router.route_request("planning", complexity="critical")
        assert result is not None
        assert result["model_id"] == "flagship-model"


# ===========================================================================
# 4. record_usage
# ===========================================================================

class TestRecordUsage:

    def test_record_returns_dict(self, router):
        router.register_model("usage-m", "p", "M")
        result = router.record_usage("usage-m", 100, 50, 120.5, success=True)
        assert "usage_id" in result
        assert result["model_id"] == "usage-m"
        assert result["tokens_total"] == 150
        assert result["latency_ms"] == 120.5
        assert result["success"] is True

    def test_record_failure(self, router):
        router.register_model("fail-m", "p", "M")
        result = router.record_usage("fail-m", 50, 0, 3000.0, success=False)
        assert result["success"] is False

    def test_record_emits_event(self, router, bus):
        router.register_model("ev-u", "p", "M")
        events = []
        bus.subscribe("model_router.usage.recorded", lambda e: events.append(e))
        router.record_usage("ev-u", 100, 50, 200.0)
        assert len(events) == 1
        assert events[0].payload["tokens_in"] == 100
        assert events[0].payload["tokens_out"] == 50

    def test_multiple_usage_records(self, router):
        router.register_model("multi-u", "p", "M")
        for i in range(10):
            router.record_usage("multi-u", 100, 50, 100.0 + i)
        stats = router.get_usage_stats(model_id="multi-u")
        assert stats["total_requests"] == 10


# ===========================================================================
# 5. get_usage_stats
# ===========================================================================

class TestGetUsageStats:

    def _seed_usage(self, router):
        router.register_model("stat-a", "p-a", "Model A", cost_per_1k_tokens=0.02)
        router.register_model("stat-b", "p-b", "Model B", cost_per_1k_tokens=0.05)
        router.record_usage("stat-a", 1000, 500, 100.0)
        router.record_usage("stat-a", 2000, 1000, 150.0, success=False)
        router.record_usage("stat-b", 500, 200, 80.0)

    def test_stats_global(self, router):
        self._seed_usage(router)
        stats = router.get_usage_stats()
        assert stats["total_requests"] == 3
        assert stats["total_tokens_in"] == 3500
        assert stats["total_tokens_out"] == 1700
        assert stats["total_tokens"] == 5200

    def test_stats_by_model(self, router):
        self._seed_usage(router)
        stats = router.get_usage_stats(model_id="stat-a")
        assert stats["total_requests"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == pytest.approx(50.0, abs=0.1)

    def test_stats_cost_calculation(self, router):
        self._seed_usage(router)
        stats_a = router.get_usage_stats(model_id="stat-a")
        # stat-a: 1500 tokens total from first, 3000 from second = 4500
        expected_cost = (4500 / 1000.0) * 0.02
        assert stats_a["estimated_cost"] == pytest.approx(expected_cost, abs=0.001)

    def test_stats_avg_latency(self, router):
        self._seed_usage(router)
        stats = router.get_usage_stats(model_id="stat-a")
        assert stats["avg_latency_ms"] == pytest.approx(125.0, abs=0.1)

    def test_stats_empty(self, router):
        stats = router.get_usage_stats()
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0
        assert stats["avg_latency_ms"] == 0.0
        assert stats["estimated_cost"] == 0.0
        assert stats["success_rate"] == 0.0


# ===========================================================================
# 6. get_cost_report
# ===========================================================================

class TestGetCostReport:

    def test_cost_report_by_model(self, router):
        router.register_model("cr-a", "prov-x", "Model A", cost_per_1k_tokens=0.01)
        router.register_model("cr-b", "prov-y", "Model B", cost_per_1k_tokens=0.10)
        router.record_usage("cr-a", 10000, 5000, 100.0)
        router.record_usage("cr-b", 1000, 500, 200.0)

        report = router.get_cost_report()
        assert len(report["by_model"]) == 2
        assert report["total_requests"] == 2

        # Find each model in the report
        model_a = [m for m in report["by_model"] if m["model_id"] == "cr-a"][0]
        model_b = [m for m in report["by_model"] if m["model_id"] == "cr-b"][0]
        assert model_a["total_tokens"] == 15000
        assert model_b["total_tokens"] == 1500
        assert model_a["cost"] == pytest.approx(0.15, abs=0.001)
        assert model_b["cost"] == pytest.approx(0.15, abs=0.001)

    def test_cost_report_by_provider(self, router):
        router.register_model("cp-1", "shared-prov", "M1", cost_per_1k_tokens=0.01)
        router.register_model("cp-2", "shared-prov", "M2", cost_per_1k_tokens=0.02)
        router.record_usage("cp-1", 1000, 0, 50.0)
        router.record_usage("cp-2", 1000, 0, 60.0)

        report = router.get_cost_report()
        assert len(report["by_provider"]) == 1
        assert report["by_provider"][0]["provider"] == "shared-prov"
        assert report["by_provider"][0]["request_count"] == 2

    def test_cost_report_empty(self, router):
        report = router.get_cost_report()
        assert report["by_model"] == []
        assert report["by_provider"] == []
        assert report["total_cost"] == 0.0
        assert report["total_requests"] == 0

    def test_cost_report_total_cost(self, router):
        router.register_model("tc-1", "p", "M", cost_per_1k_tokens=0.05)
        router.record_usage("tc-1", 10000, 10000, 100.0)
        report = router.get_cost_report()
        # 20000 tokens / 1000 * 0.05 = 1.0
        assert report["total_cost"] == pytest.approx(1.0, abs=0.001)
        assert report["total_tokens"] == 20000


# ===========================================================================
# 7. Data classes
# ===========================================================================

class TestDataClasses:

    def test_model_info_auto_timestamp(self):
        info = ModelInfo(model_id="t", provider="p", model_name="m")
        assert info.registered_at > 0

    def test_usage_record_auto_fields(self):
        record = UsageRecord(model_id="t", tokens_in=10, tokens_out=5, latency_ms=100.0)
        assert len(record.usage_id) == 32  # uuid hex
        assert record.timestamp > 0

    def test_usage_record_explicit_fields(self):
        record = UsageRecord(
            usage_id="custom-id", model_id="t",
            tokens_in=10, tokens_out=5, latency_ms=100.0,
            timestamp=1234567890.0,
        )
        assert record.usage_id == "custom-id"
        assert record.timestamp == 1234567890.0


class TestConstants:

    def test_complexity_order_values(self):
        assert COMPLEXITY_ORDER["low"] < COMPLEXITY_ORDER["medium"]
        assert COMPLEXITY_ORDER["medium"] < COMPLEXITY_ORDER["high"]
        assert COMPLEXITY_ORDER["high"] < COMPLEXITY_ORDER["critical"]

    def test_capability_complexity_map_has_entries(self):
        assert len(CAPABILITY_COMPLEXITY_MAP) > 0
        assert CAPABILITY_COMPLEXITY_MAP["simple_chat"] == "low"
        assert CAPABILITY_COMPLEXITY_MAP["autonomous"] == "critical"


# ===========================================================================
# 8. Thread safety
# ===========================================================================

class TestThreadSafety:

    def test_concurrent_register_and_usage(self):
        router = ModelRouter()
        errors = []
        lock = threading.Lock()

        def worker(idx):
            try:
                mid = f"model-{idx % 5}"
                router.register_model(
                    mid, f"prov-{idx % 3}", f"Model {mid}",
                    capabilities=["chat"],
                    cost_per_1k_tokens=0.01 + idx * 0.001,
                )
                router.record_usage(mid, 100, 50, 100.0 + idx)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        models = router.list_models()
        assert len(models) == 5  # 5 unique model IDs
        stats = router.get_usage_stats()
        assert stats["total_requests"] == 30

    def test_concurrent_routing(self):
        router = ModelRouter()
        router.register_model("r-1", "p", "M1", capabilities=["chat"], cost_per_1k_tokens=0.01)
        router.register_model("r-2", "p", "M2", capabilities=["chat", "reasoning"], cost_per_1k_tokens=0.10)

        results = []
        errors = []
        lock = threading.Lock()

        def route_worker(_):
            try:
                r = router.route_request("chat", complexity="low")
                with lock:
                    results.append(r)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=route_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 20
        # All should route to cheapest for "chat" at low complexity
        for r in results:
            assert r is not None
            assert r["model_id"] == "r-1"
