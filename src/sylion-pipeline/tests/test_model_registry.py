"""
Comprehensive tests for sylion.cognitive.model_registry -- ModelRegistry class.
Tests: registration, capabilities, health tracking, stats, comparison, search,
events, thread safety, edge cases.
"""
from __future__ import annotations

import json
import threading
import time

import pytest

from sylion.cognitive.model_registry import (
    ModelRegistry,
    PROFICIENCY_ORDER,
    VALID_PROFICIENCIES,
    get_model_registry,
    reset_model_registry,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_event_payload(events: list[dict], index: int = 0) -> dict:
    """Extract and deserialize payload from an EventBus query result."""
    raw = events[index]["payload"]
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _registry(bus: EventBus | None = None) -> ModelRegistry:
    """Create a fresh in-memory ModelRegistry."""
    return ModelRegistry(event_bus=bus)


def _register_sample(reg: ModelRegistry, model_id: str = "gpt-4o",
                     provider: str = "openai",
                     display_name: str = "GPT-4o") -> dict:
    """Register a sample model and return the result."""
    return reg.register_model(
        model_id=model_id,
        provider=provider,
        display_name=display_name,
        model_family="gpt",
        context_window=128000,
        cost_per_1k_in=0.005,
        cost_per_1k_out=0.015,
    )


# ---------------------------------------------------------------------------
# Model Registration
# ---------------------------------------------------------------------------

class TestRegisterModel:

    def test_register_returns_model_dict(self):
        reg = _registry()
        result = _register_sample(reg)
        assert result["model_id"] == "gpt-4o"
        assert result["provider"] == "openai"
        assert result["display_name"] == "GPT-4o"

    def test_register_stores_all_fields(self):
        reg = _registry()
        result = _register_sample(reg)
        assert result["model_family"] == "gpt"
        assert result["context_window"] == 128000
        assert result["cost_per_1k_in"] == 0.005
        assert result["cost_per_1k_out"] == 0.015

    def test_register_sets_is_active(self):
        reg = _registry()
        result = _register_sample(reg)
        assert result["is_active"] == 1

    def test_register_sets_registered_at(self):
        reg = _registry()
        result = _register_sample(reg)
        assert result["registered_at"] > 0

    def test_register_minimal_fields(self):
        reg = _registry()
        result = reg.register_model("m1", "provider-a", "Model One")
        assert result["model_id"] == "m1"
        assert result["cost_per_1k_in"] == 0.0
        assert result["cost_per_1k_out"] == 0.0

    def test_register_defaults_none_fields(self):
        reg = _registry()
        result = reg.register_model("m1", "p", "M")
        assert result["model_family"] is None
        assert result["context_window"] is None

    def test_register_emits_event(self):
        bus = EventBus()
        reg = _registry(bus=bus)
        _register_sample(reg)
        events = bus.query(topic="model.registered")
        assert len(events) == 1
        payload = _get_event_payload(events)
        assert payload["model_id"] == "gpt-4o"
        assert events[0]["source_module"] == "cognitive.model_registry"

    def test_register_without_event_bus(self):
        reg = _registry(bus=None)
        result = _register_sample(reg)
        assert result["model_id"] == "gpt-4o"

    def test_register_duplicate_updates_existing(self):
        reg = _registry()
        _register_sample(reg, "m1", "p1", "First")
        result = _register_sample(reg, "m1", "p2", "Updated")
        assert result["provider"] == "p2"
        assert result["display_name"] == "Updated"
        assert result["updated_at"] is not None

    def test_register_multiple_models(self):
        reg = _registry()
        reg.register_model("m1", "p1", "M1")
        reg.register_model("m2", "p2", "M2")
        reg.register_model("m3", "p3", "M3")
        models = reg.list_models()
        assert len(models) == 3


# ---------------------------------------------------------------------------
# Get Model
# ---------------------------------------------------------------------------

class TestGetModel:

    def test_get_existing_model(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.get_model("gpt-4o")
        assert result is not None
        assert result["model_id"] == "gpt-4o"

    def test_get_nonexistent_model(self):
        reg = _registry()
        result = reg.get_model("nonexistent")
        assert result is None

    def test_get_includes_capabilities(self):
        reg = _registry()
        _register_sample(reg)
        reg.add_capability("gpt-4o", "code_generation", "high")
        result = reg.get_model("gpt-4o")
        assert len(result["capabilities"]) == 1
        assert result["capabilities"][0]["task_type"] == "code_generation"

    def test_get_includes_latest_health(self):
        reg = _registry()
        _register_sample(reg)
        reg.record_health("gpt-4o", 150.0, True, 500)
        result = reg.get_model("gpt-4o")
        assert result["latest_health"] is not None
        assert result["latest_health"]["latency_ms"] == 150.0

    def test_get_without_health_records(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.get_model("gpt-4o")
        assert result["latest_health"] is None

    def test_get_deregistered_model_returns_none(self):
        reg = _registry()
        _register_sample(reg)
        reg.deregister_model("gpt-4o")
        result = reg.get_model("gpt-4o")
        assert result is None


# ---------------------------------------------------------------------------
# List Models
# ---------------------------------------------------------------------------

class TestListModels:

    def _setup_models(self, reg: ModelRegistry):
        reg.register_model("gpt-4o", "openai", "GPT-4o", model_family="gpt")
        reg.register_model("gpt-3.5", "openai", "GPT-3.5", model_family="gpt")
        reg.register_model("claude-3", "anthropic", "Claude 3", model_family="claude")
        reg.register_model("gemini-pro", "google", "Gemini Pro", model_family="gemini")

    def test_list_all(self):
        reg = _registry()
        self._setup_models(reg)
        models = reg.list_models()
        assert len(models) == 4

    def test_list_filter_by_provider(self):
        reg = _registry()
        self._setup_models(reg)
        models = reg.list_models(provider="openai")
        assert len(models) == 2
        assert all(m["provider"] == "openai" for m in models)

    def test_list_filter_by_family(self):
        reg = _registry()
        self._setup_models(reg)
        models = reg.list_models(family="gpt")
        assert len(models) == 2
        assert all(m["model_family"] == "gpt" for m in models)

    def test_list_filter_active_only(self):
        reg = _registry()
        self._setup_models(reg)
        reg.deregister_model("gpt-3.5")
        models = reg.list_models(is_active=True)
        assert len(models) == 3

    def test_list_filter_inactive_only(self):
        reg = _registry()
        self._setup_models(reg)
        reg.deregister_model("gpt-3.5")
        models = reg.list_models(is_active=False)
        assert len(models) == 1
        assert models[0]["model_id"] == "gpt-3.5"

    def test_list_ordered_by_display_name(self):
        reg = _registry()
        self._setup_models(reg)
        models = reg.list_models()
        names = [m["display_name"] for m in models]
        assert names == sorted(names)

    def test_list_empty_registry(self):
        reg = _registry()
        models = reg.list_models()
        assert models == []

    def test_list_combined_filters(self):
        reg = _registry()
        self._setup_models(reg)
        models = reg.list_models(provider="openai", family="gpt")
        assert len(models) == 2


# ---------------------------------------------------------------------------
# Update Model
# ---------------------------------------------------------------------------

class TestUpdateModel:

    def test_update_single_field(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.update_model("gpt-4o", display_name="GPT-4o Turbo")
        assert result["display_name"] == "GPT-4o Turbo"

    def test_update_multiple_fields(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.update_model(
            "gpt-4o",
            context_window=200000,
            cost_per_1k_in=0.01,
            cost_per_1k_out=0.03,
        )
        assert result["context_window"] == 200000
        assert result["cost_per_1k_in"] == 0.01
        assert result["cost_per_1k_out"] == 0.03

    def test_update_sets_updated_at(self):
        reg = _registry()
        _register_sample(reg)
        before = reg.get_model("gpt-4o")
        time.sleep(0.01)
        result = reg.update_model("gpt-4o", display_name="New")
        assert result["updated_at"] is not None

    def test_update_nonexistent_returns_none(self):
        reg = _registry()
        result = reg.update_model("nope", display_name="X")
        assert result is None

    def test_update_deregistered_returns_none(self):
        reg = _registry()
        _register_sample(reg)
        reg.deregister_model("gpt-4o")
        result = reg.update_model("gpt-4o", display_name="X")
        assert result is None

    def test_update_no_kwargs_returns_model(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.update_model("gpt-4o")
        assert result is not None
        assert result["model_id"] == "gpt-4o"

    def test_update_ignores_disallowed_kwargs(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.update_model("gpt-4o", bogus_field="nope")
        assert result is not None


# ---------------------------------------------------------------------------
# Deregister Model
# ---------------------------------------------------------------------------

class TestDeregisterModel:

    def test_deregister_active_model(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.deregister_model("gpt-4o")
        assert result is True

    def test_deregister_makes_get_return_none(self):
        reg = _registry()
        _register_sample(reg)
        reg.deregister_model("gpt-4o")
        assert reg.get_model("gpt-4o") is None

    def test_deregister_nonexistent_returns_false(self):
        reg = _registry()
        result = reg.deregister_model("nonexistent")
        assert result is False

    def test_deregister_already_deregistered_returns_false(self):
        reg = _registry()
        _register_sample(reg)
        reg.deregister_model("gpt-4o")
        result = reg.deregister_model("gpt-4o")
        assert result is False

    def test_deregister_emits_event(self):
        bus = EventBus()
        reg = _registry(bus=bus)
        _register_sample(reg)
        reg.deregister_model("gpt-4o")
        events = bus.query(topic="model.deregistered")
        assert len(events) == 1
        payload = _get_event_payload(events)
        assert payload["model_id"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

class TestCapabilities:

    def test_add_capability(self):
        reg = _registry()
        _register_sample(reg)
        cap = reg.add_capability("gpt-4o", "code_generation", "high")
        assert cap["task_type"] == "code_generation"
        assert cap["proficiency"] == "high"
        assert cap["model_id"] == "gpt-4o"
        assert cap["capability_id"] != ""

    def test_add_capability_with_max_tokens(self):
        reg = _registry()
        _register_sample(reg)
        cap = reg.add_capability("gpt-4o", "summarization", "medium", max_tokens=4096)
        assert cap["max_tokens"] == 4096

    def test_add_capability_default_proficiency(self):
        reg = _registry()
        _register_sample(reg)
        cap = reg.add_capability("gpt-4o", "translation")
        assert cap["proficiency"] == "medium"

    def test_add_capability_invalid_proficiency(self):
        reg = _registry()
        _register_sample(reg)
        with pytest.raises(ValueError, match="Invalid proficiency"):
            reg.add_capability("gpt-4o", "task", "godlike")

    def test_add_capability_inactive_model_raises(self):
        reg = _registry()
        _register_sample(reg)
        reg.deregister_model("gpt-4o")
        with pytest.raises(ValueError, match="not found or inactive"):
            reg.add_capability("gpt-4o", "task")

    def test_add_capability_nonexistent_model_raises(self):
        reg = _registry()
        with pytest.raises(ValueError, match="not found or inactive"):
            reg.add_capability("ghost", "task")

    def test_add_capability_emits_event(self):
        bus = EventBus()
        reg = _registry(bus=bus)
        _register_sample(reg)
        reg.add_capability("gpt-4o", "code_generation", "high")
        events = bus.query(topic="model.capability.added")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["task_type"] == "code_generation"

    def test_remove_capability(self):
        reg = _registry()
        _register_sample(reg)
        cap = reg.add_capability("gpt-4o", "vision")
        result = reg.remove_capability(cap["capability_id"])
        assert result is True
        model = reg.get_model("gpt-4o")
        assert len(model["capabilities"]) == 0

    def test_remove_nonexistent_capability(self):
        reg = _registry()
        result = reg.remove_capability("nonexistent")
        assert result is False

    def test_multiple_capabilities(self):
        reg = _registry()
        _register_sample(reg)
        reg.add_capability("gpt-4o", "code_generation", "high")
        reg.add_capability("gpt-4o", "vision", "medium")
        reg.add_capability("gpt-4o", "translation", "low")
        model = reg.get_model("gpt-4o")
        assert len(model["capabilities"]) == 3


# ---------------------------------------------------------------------------
# Get Model For Task
# ---------------------------------------------------------------------------

class TestGetModelForTask:

    def _setup(self, reg: ModelRegistry):
        reg.register_model("gpt-4o", "openai", "GPT-4o")
        reg.register_model("claude-3", "anthropic", "Claude 3")
        reg.register_model("gemini", "google", "Gemini")
        reg.add_capability("gpt-4o", "code_generation", "expert")
        reg.add_capability("claude-3", "code_generation", "high")
        reg.add_capability("gemini", "code_generation", "medium")

    def test_find_models_for_task(self):
        reg = _registry()
        self._setup(reg)
        results = reg.get_model_for_task("code_generation")
        assert len(results) == 3

    def test_filter_by_min_proficiency(self):
        reg = _registry()
        self._setup(reg)
        results = reg.get_model_for_task("code_generation", min_proficiency="high")
        # expert and high should match
        assert len(results) == 2

    def test_filter_by_expert_only(self):
        reg = _registry()
        self._setup(reg)
        results = reg.get_model_for_task("code_generation", min_proficiency="expert")
        assert len(results) == 1
        assert results[0]["model_id"] == "gpt-4o"

    def test_no_models_for_unknown_task(self):
        reg = _registry()
        self._setup(reg)
        results = reg.get_model_for_task("nonexistent_task")
        assert results == []

    def test_excludes_inactive_models(self):
        reg = _registry()
        self._setup(reg)
        reg.deregister_model("gemini")
        results = reg.get_model_for_task("code_generation")
        assert len(results) == 2
        assert all(r["is_active"] == 1 for r in results)

    def test_result_includes_matching_capability(self):
        reg = _registry()
        self._setup(reg)
        results = reg.get_model_for_task("code_generation")
        for r in results:
            assert "matching_capability" in r
            assert r["matching_capability"]["task_type"] == "code_generation"


# ---------------------------------------------------------------------------
# Health Tracking
# ---------------------------------------------------------------------------

class TestHealthTracking:

    def test_record_health_success(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.record_health("gpt-4o", 150.0, True, 500)
        assert result["latency_ms"] == 150.0
        assert result["success"] is True
        assert result["tokens_used"] == 500
        assert result["health_id"] != ""

    def test_record_health_failure(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.record_health("gpt-4o", 0.0, False, 0, error="timeout")
        assert result["success"] is False
        assert result["error"] == "timeout"

    def test_record_health_defaults(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.record_health("gpt-4o", 100.0, True)
        assert result["tokens_used"] == 0
        assert result["error"] is None

    def test_record_health_emits_event(self):
        bus = EventBus()
        reg = _registry(bus=bus)
        _register_sample(reg)
        reg.record_health("gpt-4o", 200.0, True)
        events = bus.query(topic="model.health.recorded")
        assert len(events) == 1
        payload = json.loads(events[0]["payload"])
        assert payload["latency_ms"] == 200.0

    def test_get_model_health(self):
        reg = _registry()
        _register_sample(reg)
        for i in range(5):
            reg.record_health("gpt-4o", float(i * 100), True, i * 100)
        health = reg.get_model_health("gpt-4o")
        assert len(health) == 5

    def test_get_model_health_limit(self):
        reg = _registry()
        _register_sample(reg)
        for i in range(20):
            reg.record_health("gpt-4o", float(i), True)
        health = reg.get_model_health("gpt-4o", limit=5)
        assert len(health) == 5

    def test_get_model_health_ordered_desc(self):
        reg = _registry()
        _register_sample(reg)
        reg.record_health("gpt-4o", 100.0, True)
        time.sleep(0.01)
        reg.record_health("gpt-4o", 200.0, True)
        health = reg.get_model_health("gpt-4o")
        assert health[0]["latency_ms"] == 200.0  # most recent first

    def test_get_model_health_empty(self):
        reg = _registry()
        _register_sample(reg)
        health = reg.get_model_health("gpt-4o")
        assert health == []

    def test_record_health_for_unknown_model(self):
        """Health records can be created even for unregistered models
        (no FK enforcement in SQLite by default)."""
        reg = _registry()
        result = reg.record_health("phantom", 100.0, True)
        assert result["model_id"] == "phantom"


# ---------------------------------------------------------------------------
# Model Stats
# ---------------------------------------------------------------------------

class TestModelStats:

    def test_stats_empty(self):
        reg = _registry()
        _register_sample(reg)
        stats = reg.get_model_stats("gpt-4o")
        assert stats["total_calls"] == 0
        assert stats["avg_latency_ms"] == 0.0
        assert stats["success_rate"] == 0.0

    def test_stats_with_data(self):
        reg = _registry()
        _register_sample(reg)
        reg.record_health("gpt-4o", 100.0, True, 500)
        reg.record_health("gpt-4o", 200.0, True, 300)
        reg.record_health("gpt-4o", 300.0, False, 0)
        stats = reg.get_model_stats("gpt-4o")
        assert stats["total_calls"] == 3
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == pytest.approx(66.67, rel=0.01)
        assert stats["avg_latency_ms"] == pytest.approx(200.0, rel=0.01)

    def test_stats_total_tokens(self):
        reg = _registry()
        _register_sample(reg)
        reg.record_health("gpt-4o", 100.0, True, 500)
        reg.record_health("gpt-4o", 200.0, True, 300)
        stats = reg.get_model_stats("gpt-4o")
        assert stats["total_tokens_used"] == 800

    def test_stats_estimated_cost(self):
        reg = _registry()
        reg.register_model("m1", "p", "M",
                           cost_per_1k_in=0.01, cost_per_1k_out=0.03)
        reg.record_health("m1", 100.0, True, 1000)
        stats = reg.get_model_stats("m1")
        # avg cost = (0.01 + 0.03) / 2 = 0.02 per 1k
        # 1000 tokens * 0.02 / 1000 = 0.02
        assert stats["estimated_cost"] == pytest.approx(0.02, rel=0.01)

    def test_stats_model_id_in_result(self):
        reg = _registry()
        _register_sample(reg)
        stats = reg.get_model_stats("gpt-4o")
        assert stats["model_id"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Registry Stats
# ---------------------------------------------------------------------------

class TestRegistryStats:

    def _setup(self, reg: ModelRegistry):
        reg.register_model("gpt-4o", "openai", "GPT-4o", model_family="gpt")
        reg.register_model("gpt-3.5", "openai", "GPT-3.5", model_family="gpt")
        reg.register_model("claude-3", "anthropic", "Claude 3", model_family="claude")

    def test_registry_stats_counts(self):
        reg = _registry()
        self._setup(reg)
        stats = reg.get_registry_stats()
        assert stats["total_models"] == 3
        assert stats["active_models"] == 3
        assert stats["inactive_models"] == 0

    def test_registry_stats_by_provider(self):
        reg = _registry()
        self._setup(reg)
        stats = reg.get_registry_stats()
        assert stats["by_provider"]["openai"] == 2
        assert stats["by_provider"]["anthropic"] == 1

    def test_registry_stats_by_family(self):
        reg = _registry()
        self._setup(reg)
        stats = reg.get_registry_stats()
        assert stats["by_family"]["gpt"] == 2
        assert stats["by_family"]["claude"] == 1

    def test_registry_stats_after_deregister(self):
        reg = _registry()
        self._setup(reg)
        reg.deregister_model("gpt-3.5")
        stats = reg.get_registry_stats()
        assert stats["active_models"] == 2
        assert stats["inactive_models"] == 1

    def test_registry_stats_overall_health(self):
        reg = _registry()
        self._setup(reg)
        reg.record_health("gpt-4o", 100.0, True)
        reg.record_health("gpt-4o", 200.0, False)
        stats = reg.get_registry_stats()
        h = stats["overall_health"]
        assert h["total_calls"] == 2
        assert h["success_rate"] == 50.0
        assert h["avg_latency_ms"] == pytest.approx(150.0, rel=0.01)

    def test_registry_stats_empty(self):
        reg = _registry()
        stats = reg.get_registry_stats()
        assert stats["total_models"] == 0
        assert stats["by_provider"] == {}
        assert stats["overall_health"]["total_calls"] == 0


# ---------------------------------------------------------------------------
# Compare Models
# ---------------------------------------------------------------------------

class TestCompareModels:

    def _setup(self, reg: ModelRegistry):
        reg.register_model("gpt-4o", "openai", "GPT-4o",
                           model_family="gpt", context_window=128000,
                           cost_per_1k_in=0.005, cost_per_1k_out=0.015)
        reg.register_model("claude-3", "anthropic", "Claude 3",
                           model_family="claude", context_window=200000,
                           cost_per_1k_in=0.003, cost_per_1k_out=0.015)
        reg.register_model("gemini", "google", "Gemini",
                           model_family="gemini", context_window=32000,
                           cost_per_1k_in=0.001, cost_per_1k_out=0.002)
        reg.add_capability("gpt-4o", "code_generation", "expert")
        reg.add_capability("gpt-4o", "vision", "high")
        reg.add_capability("claude-3", "code_generation", "high")
        reg.add_capability("gemini", "translation", "low")
        # Health records
        reg.record_health("gpt-4o", 200.0, True, 1000)
        reg.record_health("claude-3", 150.0, True, 800)
        reg.record_health("claude-3", 300.0, False, 0)
        reg.record_health("gemini", 50.0, True, 200)

    def test_compare_returns_all_models(self):
        reg = _registry()
        self._setup(reg)
        result = reg.compare_models(["gpt-4o", "claude-3", "gemini"])
        assert len(result["models"]) == 3

    def test_compare_fastest(self):
        reg = _registry()
        self._setup(reg)
        result = reg.compare_models(["gpt-4o", "claude-3", "gemini"])
        assert result["comparison"]["fastest"] == "gemini"

    def test_compare_most_reliable(self):
        reg = _registry()
        self._setup(reg)
        result = reg.compare_models(["gpt-4o", "claude-3", "gemini"])
        # gemini and gpt-4o both have 100% success, gpt-4o and gemini are both reliable
        assert result["comparison"]["most_reliable"] in ("gpt-4o", "gemini")

    def test_compare_cheapest_input(self):
        reg = _registry()
        self._setup(reg)
        result = reg.compare_models(["gpt-4o", "claude-3", "gemini"])
        assert result["comparison"]["cheapest_input"] == "gemini"

    def test_compare_largest_context(self):
        reg = _registry()
        self._setup(reg)
        result = reg.compare_models(["gpt-4o", "claude-3", "gemini"])
        assert result["comparison"]["largest_context"] == "claude-3"

    def test_compare_most_capabilities(self):
        reg = _registry()
        self._setup(reg)
        result = reg.compare_models(["gpt-4o", "claude-3", "gemini"])
        assert result["comparison"]["most_capabilities"] == "gpt-4o"

    def test_compare_empty_list(self):
        reg = _registry()
        result = reg.compare_models([])
        assert result["models"] == []
        assert result["comparison"] == {}

    def test_compare_with_unknown_model(self):
        reg = _registry()
        self._setup(reg)
        result = reg.compare_models(["gpt-4o", "nonexistent"])
        assert len(result["models"]) == 1

    def test_compare_no_health_data(self):
        reg = _registry()
        reg.register_model("m1", "p1", "M1", context_window=8000, cost_per_1k_in=0.01)
        reg.register_model("m2", "p2", "M2", context_window=16000, cost_per_1k_in=0.02)
        result = reg.compare_models(["m1", "m2"])
        assert "comparison" in result
        assert result["comparison"]["cheapest_input"] == "m1"


# ---------------------------------------------------------------------------
# Search Models
# ---------------------------------------------------------------------------

class TestSearchModels:

    def _setup(self, reg: ModelRegistry):
        reg.register_model("gpt-4o", "openai", "GPT-4o", model_family="gpt")
        reg.register_model("gpt-3.5-turbo", "openai", "GPT-3.5 Turbo", model_family="gpt")
        reg.register_model("claude-3-opus", "anthropic", "Claude 3 Opus", model_family="claude")
        reg.register_model("gemini-pro", "google", "Gemini Pro", model_family="gemini")

    def test_search_by_model_id(self):
        reg = _registry()
        self._setup(reg)
        results = reg.search_models("gpt")
        assert len(results) == 2

    def test_search_by_display_name(self):
        reg = _registry()
        self._setup(reg)
        results = reg.search_models("Claude")
        assert len(results) == 1
        assert results[0]["model_id"] == "claude-3-opus"

    def test_search_by_provider(self):
        reg = _registry()
        self._setup(reg)
        results = reg.search_models("anthropic")
        assert len(results) == 1

    def test_search_by_family(self):
        reg = _registry()
        self._setup(reg)
        results = reg.search_models("gemini")
        assert len(results) == 1

    def test_search_no_results(self):
        reg = _registry()
        self._setup(reg)
        results = reg.search_models("nonexistent")
        assert results == []

    def test_search_excludes_inactive(self):
        reg = _registry()
        self._setup(reg)
        reg.deregister_model("gpt-3.5-turbo")
        results = reg.search_models("gpt")
        assert len(results) == 1
        assert results[0]["model_id"] == "gpt-4o"

    def test_search_case_insensitive_partial(self):
        reg = _registry()
        self._setup(reg)
        results = reg.search_models("OPUS")
        assert len(results) == 1

    def test_search_empty_query(self):
        reg = _registry()
        self._setup(reg)
        results = reg.search_models("")
        assert len(results) == 4  # LIKE '%%' matches everything


# ---------------------------------------------------------------------------
# Proficiency Helpers
# ---------------------------------------------------------------------------

class TestProficiency:

    def test_valid_proficiencies(self):
        assert "low" in VALID_PROFICIENCIES
        assert "medium" in VALID_PROFICIENCIES
        assert "high" in VALID_PROFICIENCIES
        assert "expert" in VALID_PROFICIENCIES

    def test_proficiency_ordering(self):
        assert PROFICIENCY_ORDER["low"] < PROFICIENCY_ORDER["medium"]
        assert PROFICIENCY_ORDER["medium"] < PROFICIENCY_ORDER["high"]
        assert PROFICIENCY_ORDER["high"] < PROFICIENCY_ORDER["expert"]

    def test_add_all_proficiencies(self):
        reg = _registry()
        _register_sample(reg)
        for prof in ["low", "medium", "high", "expert"]:
            cap = reg.add_capability("gpt-4o", f"task_{prof}", prof)
            assert cap["proficiency"] == prof


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:

    def test_all_event_topics(self):
        bus = EventBus()
        reg = _registry(bus=bus)
        _register_sample(reg)
        reg.add_capability("gpt-4o", "code", "high")
        reg.record_health("gpt-4o", 100.0, True)
        reg.deregister_model("gpt-4o")

        assert len(bus.query(topic="model.registered")) == 1
        assert len(bus.query(topic="model.capability.added")) == 1
        assert len(bus.query(topic="model.health.recorded")) == 1
        assert len(bus.query(topic="model.deregistered")) == 1

    def test_event_payloads_have_model_id(self):
        bus = EventBus()
        reg = _registry(bus=bus)
        _register_sample(reg)
        reg.add_capability("gpt-4o", "code", "high")
        reg.record_health("gpt-4o", 100.0, True)
        reg.deregister_model("gpt-4o")

        for topic in ["model.registered", "model.capability.added",
                       "model.health.recorded", "model.deregistered"]:
            events = bus.query(topic=topic)
            payload = json.loads(events[0]["payload"])
            assert payload["model_id"] == "gpt-4o"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_model_registry_returns_instance(self):
        import sylion.cognitive.model_registry as mod
        mod._registry = None
        instance = get_model_registry()
        assert isinstance(instance, ModelRegistry)
        mod._registry = None

    def test_reset_model_registry_returns_new_instance(self):
        import sylion.cognitive.model_registry as mod
        mod._registry = None
        a = get_model_registry()
        b = reset_model_registry()
        assert a is not b
        mod._registry = None


# ---------------------------------------------------------------------------
# Thread Safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_register_no_crash(self):
        reg = _registry()
        errors = []

        def register_n(n):
            try:
                for i in range(10):
                    reg.register_model(
                        f"model-{n}-{i}",
                        f"provider-{n}",
                        f"Model {n}-{i}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_n, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        models = reg.list_models()
        assert len(models) == 50

    def test_concurrent_health_recording(self):
        reg = _registry()
        _register_sample(reg)
        errors = []

        def record_n():
            try:
                for i in range(20):
                    reg.record_health("gpt-4o", float(i * 10), True, i * 100)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_n) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        health = reg.get_model_health("gpt-4o", limit=1000)
        assert len(health) == 100

    def test_concurrent_register_and_query(self):
        reg = _registry()
        errors = []

        def writer():
            try:
                for i in range(10):
                    reg.register_model(f"m{i}", "p", f"Model {i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(10):
                    reg.list_models()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_register_model_with_special_characters(self):
        reg = _registry()
        result = reg.register_model("my-model_v2.0", "provider-a", "My Model v2.0")
        assert result["model_id"] == "my-model_v2.0"

    def test_zero_cost_model(self):
        reg = _registry()
        result = reg.register_model("free", "local", "Free Model",
                                    cost_per_1k_in=0.0, cost_per_1k_out=0.0)
        assert result["cost_per_1k_in"] == 0.0
        assert result["cost_per_1k_out"] == 0.0

    def test_large_context_window(self):
        reg = _registry()
        result = reg.register_model("big", "p", "Big",
                                    context_window=2000000)
        assert result["context_window"] == 2000000

    def test_health_with_zero_latency(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.record_health("gpt-4o", 0.0, True)
        assert result["latency_ms"] == 0.0

    def test_health_with_large_token_count(self):
        reg = _registry()
        _register_sample(reg)
        result = reg.record_health("gpt-4o", 100.0, True, tokens_used=1000000)
        assert result["tokens_used"] == 1000000

    def test_capability_same_task_different_model(self):
        reg = _registry()
        reg.register_model("m1", "p1", "M1")
        reg.register_model("m2", "p2", "M2")
        cap1 = reg.add_capability("m1", "code_generation", "high")
        cap2 = reg.add_capability("m2", "code_generation", "expert")
        assert cap1["capability_id"] != cap2["capability_id"]

        results = reg.get_model_for_task("code_generation")
        assert len(results) == 2

    def test_list_models_no_filters_returns_all(self):
        reg = _registry()
        reg.register_model("m1", "p1", "M1")
        reg.register_model("m2", "p2", "M2")
        models = reg.list_models()
        assert len(models) == 2

    def test_search_with_special_characters(self):
        reg = _registry()
        reg.register_model("v2.0-model", "p", "V2.0 Model")
        results = reg.search_models("v2.0")
        assert len(results) == 1

    def test_model_without_family_search(self):
        reg = _registry()
        reg.register_model("m1", "openai", "Test")
        results = reg.search_models("openai")
        assert len(results) == 1
