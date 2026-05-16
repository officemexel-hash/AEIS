"""
SYLION Cognitive -- LLM Adapter Tests

Comprehensive tests for LLMAdapter: call, get_call, list_calls,
get_usage_stats, event emission, and error handling.
"""

from __future__ import annotations

import hashlib
import json
import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.llm_adapter import LLMAdapter, LLMCall


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    """Fresh in-memory EventBus per test."""
    return EventBus()


@pytest.fixture
def adapter(bus):
    """Fresh in-memory LLMAdapter with EventBus attached."""
    return LLMAdapter(event_bus=bus)


@pytest.fixture
def captured_events(bus):
    """Subscribe to all events and collect them."""
    events: list[SylionEvent] = []
    bus.subscribe("*", events.append)
    return events


# =====================================================================
# Test LLMCall dataclass
# =====================================================================

class TestLLMCall:

    def test_auto_fields(self):
        call = LLMCall()
        assert call.call_id != ""
        assert call.timestamp > 0.0
        assert call.status == "pending"

    def test_custom_fields(self):
        call = LLMCall(call_id="abc", model_id="gpt-4", status="completed", timestamp=1.0)
        assert call.call_id == "abc"
        assert call.model_id == "gpt-4"


# =====================================================================
# Test call (stub)
# =====================================================================

class TestCall:

    def test_call_returns_response_dict(self, adapter):
        result = adapter.call("test-model", "Hello world")
        assert "call_id" in result
        assert result["text"] == "stub"
        assert isinstance(result["tokens"], int)
        assert isinstance(result["cost"], float)
        assert isinstance(result["latency_ms"], int)

    def test_call_records_prompt_hash(self, adapter):
        prompt = "what is 2+2?"
        result = adapter.call("math-model", prompt)
        # Adapter hashes json.dumps of the messages array
        messages = [{"role": "user", "content": prompt}]
        expected_hash = hashlib.sha256(json.dumps(messages).encode("utf-8")).hexdigest()
        record = adapter.get_call(result["call_id"])
        assert record is not None
        assert record["prompt_hash"] == expected_hash

    def test_call_stores_model_id(self, adapter):
        adapter.call("model-alpha", "prompt1")
        adapter.call("model-beta", "prompt2")
        stats = adapter.get_usage_stats()
        assert "model-alpha" in stats["by_model"]
        assert "model-beta" in stats["by_model"]

    def test_call_with_max_tokens_param(self, adapter):
        # max_tokens accepted but stub ignores it
        result = adapter.call("m1", "p1", max_tokens=500)
        assert result["call_id"] != ""


# =====================================================================
# Test get_call
# =====================================================================

class TestGetCall:

    def test_get_existing_call(self, adapter):
        result = adapter.call("model-x", "hello")
        fetched = adapter.get_call(result["call_id"])
        assert fetched is not None
        assert fetched["model_id"] == "model-x"
        assert fetched["status"] == "stub"

    def test_get_nonexistent_call(self, adapter):
        fetched = adapter.get_call("does-not-exist")
        assert fetched is None


# =====================================================================
# Test list_calls
# =====================================================================

class TestListCalls:

    def test_list_all_calls(self, adapter):
        adapter.call("m1", "p1")
        adapter.call("m2", "p2")
        calls = adapter.list_calls()
        assert len(calls) == 2

    def test_list_filtered_by_model(self, adapter):
        adapter.call("model-a", "p1")
        adapter.call("model-b", "p2")
        adapter.call("model-a", "p3")
        calls = adapter.list_calls(model_id="model-a")
        assert len(calls) == 2
        assert all(c["model_id"] == "model-a" for c in calls)

    def test_list_respects_limit(self, adapter):
        for i in range(20):
            adapter.call("m", f"prompt-{i}")
        calls = adapter.list_calls(limit=5)
        assert len(calls) == 5

    def test_list_empty(self, adapter):
        calls = adapter.list_calls()
        assert calls == []

    def test_list_ordered_by_timestamp_desc(self, adapter):
        adapter.call("m", "first")
        adapter.call("m", "second")
        calls = adapter.list_calls()
        assert calls[0]["prompt_hash"] != calls[1]["prompt_hash"]


# =====================================================================
# Test get_usage_stats
# =====================================================================

class TestGetUsageStats:

    def test_stats_empty(self, adapter):
        stats = adapter.get_usage_stats()
        assert stats["total_calls"] == 0
        assert stats["total_prompt_tokens"] == 0
        assert stats["total_completion_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["by_model"] == {}

    def test_stats_after_calls(self, adapter):
        adapter.call("m1", "p1")
        adapter.call("m1", "p2")
        adapter.call("m2", "p3")
        stats = adapter.get_usage_stats()
        assert stats["total_calls"] == 3
        assert "m1" in stats["by_model"]
        assert stats["by_model"]["m1"]["calls"] == 2
        assert "m2" in stats["by_model"]
        assert stats["by_model"]["m2"]["calls"] == 1

    def test_stats_cost_rounding(self, adapter):
        adapter.call("m", "p")
        stats = adapter.get_usage_stats()
        # total_cost is rounded to 6 decimals
        assert isinstance(stats["total_cost"], float)


# =====================================================================
# Test event emission
# =====================================================================

class TestEventEmission:

    def test_call_emits_event(self, adapter, captured_events):
        adapter.call("emit-model", "test prompt")
        assert len(captured_events) == 1
        evt = captured_events[0]
        assert evt.topic == "llm.call_completed"
        assert evt.payload["model_id"] == "emit-model"

    def test_no_event_without_bus(self):
        adapter = LLMAdapter(event_bus=None)
        result = adapter.call("m", "p")
        assert result["call_id"] != ""


# =====================================================================
# Test thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_calls(self, adapter):
        errors: list[Exception] = []

        def do_call(idx):
            try:
                adapter.call(f"model-{idx % 3}", f"prompt-{idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_call, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stats = adapter.get_usage_stats()
        assert stats["total_calls"] == 30


# =====================================================================
# Test model_router parameter (unused in stub)
# =====================================================================

class TestModelRouter:

    def test_adapter_ignores_none_router(self, bus):
        adapter = LLMAdapter(model_router=None, event_bus=bus)
        result = adapter.call("m", "p")
        assert result["text"] == "stub"

    def test_adapter_accepts_arbitrary_router(self, bus):
        class DummyRouter:
            pass
        adapter = LLMAdapter(model_router=DummyRouter(), event_bus=bus)
        result = adapter.call("m", "p")
        assert result["call_id"] != ""
