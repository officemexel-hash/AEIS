"""
SYLION Cognitive -- LLM Adapter Real Provider Tests

Tests for LLMAdapter with real provider support (anthropic/openai/ollama)
selected via SYLION_LLM_PROVIDER env var, with fallback to stub mode.

Covers:
  - Stub provider (default mode)
  - call_messages() API
  - Provider fallback with invalid credentials
  - Provider env var routing
  - SQLite call recording
  - get_call / list_calls
  - get_usage_stats
  - Singleton accessor
  - Token estimation
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.llm_adapter import (
    LLMAdapter,
    LLMCall,
    get_llm_adapter,
    _adapter as _grab_module_adapter,
)


# =====================================================================
# Helpers
# =====================================================================

# Env keys we touch -- used for cleanup
_ENV_KEYS = [
    "SYLION_LLM_PROVIDER",
    "SYLION_LLM_API_KEY",
    "SYLION_LLM_MODEL",
    "SYLION_LLM_BASE_URL",
    "SYLION_LLM_MAX_TOKENS",
    "SYLION_LLM_COST_PER_1K",
]


@pytest.fixture(autouse=True)
def _clean_env():
    """Remove all SYLION_LLM_* env vars before and after each test."""
    saved = {}
    for k in _ENV_KEYS:
        if k in os.environ:
            saved[k] = os.environ.pop(k)
    yield
    for k in _ENV_KEYS:
        if k in os.environ:
            del os.environ[k]
    os.environ.update(saved)


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


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the global singleton between tests so get_llm_adapter is fresh."""
    import sylion.cognitive.llm_adapter as _mod
    old = getattr(_mod, "_adapter", None)
    _mod._adapter = None
    yield
    _mod._adapter = old


# =====================================================================
# 1. TestStubProvider
# =====================================================================

class TestStubProvider:
    """Default mode (no SYLION_LLM_PROVIDER env var)."""

    def test_call_returns_stub_text(self, adapter):
        result = adapter.call("stub-model", "hello")
        assert result["text"] == "stub"

    def test_call_returns_call_id(self, adapter):
        result = adapter.call("stub-model", "hello")
        assert isinstance(result["call_id"], str)
        assert len(result["call_id"]) > 0

    def test_call_returns_zero_tokens_in_stub(self, adapter):
        result = adapter.call("stub-model", "hello")
        assert result["tokens"] == 0

    def test_call_returns_zero_cost_in_stub(self, adapter):
        result = adapter.call("stub-model", "hello")
        assert result["cost"] == 0.0

    def test_call_latency_is_positive_int(self, adapter):
        result = adapter.call("stub-model", "hello")
        assert isinstance(result["latency_ms"], int)
        assert result["latency_ms"] >= 0

    def test_call_records_to_db(self, adapter):
        result = adapter.call("db-model", "record me")
        row = adapter.get_call(result["call_id"])
        assert row is not None
        assert row["model_id"] == "db-model"
        assert row["status"] == "stub"

    def test_call_emits_event(self, adapter, captured_events):
        adapter.call("evt-model", "trigger event")
        assert len(captured_events) == 1
        evt = captured_events[0]
        assert evt.topic == "llm.call_completed"
        assert evt.payload["model_id"] == "evt-model"
        assert evt.source_module == "cognitive.llm_adapter"

    def test_call_emits_event_with_call_id(self, adapter, captured_events):
        result = adapter.call("evt-model", "trigger")
        evt = captured_events[0]
        assert evt.payload["call_id"] == result["call_id"]

    def test_no_crash_without_event_bus(self):
        adapter = LLMAdapter(event_bus=None)
        result = adapter.call("m", "p")
        assert result["call_id"] != ""
        assert result["text"] == "stub"


# =====================================================================
# 2. TestCallMessages
# =====================================================================

class TestCallMessages:
    """Test call_messages() with multi-turn message lists."""

    def test_call_messages_returns_same_format(self, adapter):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "What is 2+2?"},
        ]
        result = adapter.call_messages("chat-model", messages)
        assert "call_id" in result
        assert "text" in result
        assert "tokens" in result
        assert "cost" in result
        assert "latency_ms" in result

    def test_call_messages_stub_text(self, adapter):
        messages = [{"role": "user", "content": "hi"}]
        result = adapter.call_messages("m", messages)
        assert result["text"] == "stub"

    def test_call_messages_hashes_full_messages(self, adapter):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
        ]
        result = adapter.call_messages("m", messages)
        expected = hashlib.sha256(
            json.dumps(messages, default=str).encode("utf-8")
        ).hexdigest()
        row = adapter.get_call(result["call_id"])
        assert row["prompt_hash"] == expected

    def test_call_messages_records_model_id(self, adapter):
        messages = [{"role": "user", "content": "hello"}]
        adapter.call_messages("my-chat-model", messages)
        calls = adapter.list_calls(model_id="my-chat-model")
        assert len(calls) == 1
        assert calls[0]["model_id"] == "my-chat-model"

    def test_call_messages_with_max_tokens(self, adapter):
        messages = [{"role": "user", "content": "hi"}]
        result = adapter.call_messages("m", messages, max_tokens=200)
        assert result["call_id"] != ""


# =====================================================================
# 3. TestProviderFallback
# =====================================================================

class TestProviderFallback:
    """Real provider env set but with invalid credentials -> graceful fallback."""

    def test_anthropic_invalid_key_falls_back(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "anthropic"
        os.environ["SYLION_LLM_API_KEY"] = "sk-invalid-key-00000000"
        result = adapter.call("fallback-test", "hello")
        assert result["text"] == "stub"
        assert result["call_id"] != ""

    def test_anthropic_invalid_key_records_fallback_status(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "anthropic"
        os.environ["SYLION_LLM_API_KEY"] = "sk-invalid-key-00000000"
        result = adapter.call("fallback-status", "hello")
        row = adapter.get_call(result["call_id"])
        assert row["status"] == "fallback"

    def test_openai_invalid_key_falls_back(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "openai"
        os.environ["SYLION_LLM_API_KEY"] = "sk-invalid-key-00000000"
        result = adapter.call("fallback-openai", "hello")
        assert result["text"] == "stub"

    def test_ollama_unreachable_falls_back(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "ollama"
        os.environ["SYLION_LLM_BASE_URL"] = "http://127.0.0.1:1"
        result = adapter.call("fallback-ollama", "hello")
        assert result["text"] == "stub"

    def test_fallback_still_records_to_db(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "openai"
        os.environ["SYLION_LLM_API_KEY"] = "bad-key"
        result = adapter.call("fb-db", "hello")
        row = adapter.get_call(result["call_id"])
        assert row is not None
        assert row["status"] == "fallback"
        assert row["model_id"] == "fb-db"

    def test_fallback_still_emits_event(self, adapter, captured_events):
        os.environ["SYLION_LLM_PROVIDER"] = "anthropic"
        os.environ["SYLION_LLM_API_KEY"] = "bad-key"
        adapter.call("fb-evt", "hello")
        assert len(captured_events) == 1
        assert captured_events[0].topic == "llm.call_completed"

    def test_unknown_provider_falls_back_to_stub(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "nonexistent_provider"
        result = adapter.call("unk-provider", "hello")
        assert result["text"] == "stub"
        row = adapter.get_call(result["call_id"])
        assert row["status"] == "stub"


# =====================================================================
# 4. TestProviderRouting
# =====================================================================

class TestProviderRouting:
    """Test _get_provider() reads env var correctly."""

    def test_default_is_stub(self, adapter):
        assert adapter._get_provider() == "stub"

    def test_anthropic_env(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "anthropic"
        assert adapter._get_provider() == "anthropic"

    def test_openai_env(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "openai"
        assert adapter._get_provider() == "openai"

    def test_ollama_env(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "ollama"
        assert adapter._get_provider() == "ollama"

    def test_case_insensitive(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "AnThRoPiC"
        assert adapter._get_provider() == "anthropic"

    def test_model_default_per_provider(self, adapter):
        os.environ["SYLION_LLM_PROVIDER"] = "anthropic"
        assert adapter._get_model("anthropic") == "claude-sonnet-4-20250514"
        os.environ["SYLION_LLM_PROVIDER"] = "openai"
        assert adapter._get_model("openai") == "gpt-4o"
        os.environ["SYLION_LLM_PROVIDER"] = "ollama"
        assert adapter._get_model("ollama") == "llama3"
        assert adapter._get_model("stub") == "stub"

    def test_model_override_via_env(self, adapter):
        os.environ["SYLION_LLM_MODEL"] = "my-custom-model"
        assert adapter._get_model("anthropic") == "my-custom-model"

    def test_unknown_provider_model_default(self, adapter):
        assert adapter._get_model("unknown") == "stub"

    def test_max_tokens_from_env(self, adapter):
        os.environ["SYLION_LLM_MAX_TOKENS"] = "8192"
        assert adapter._get_max_tokens() == 8192

    def test_max_tokens_invalid_fallback(self, adapter):
        os.environ["SYLION_LLM_MAX_TOKENS"] = "not-a-number"
        assert adapter._get_max_tokens() == 4096

    def test_cost_per_1k_from_env(self, adapter):
        os.environ["SYLION_LLM_COST_PER_1K"] = "0.03"
        assert adapter._get_cost_per_1k() == pytest.approx(0.03)

    def test_cost_per_1k_invalid_fallback(self, adapter):
        os.environ["SYLION_LLM_COST_PER_1K"] = "bad"
        assert adapter._get_cost_per_1k() == 0.0


# =====================================================================
# 5. TestCallRecording
# =====================================================================

class TestCallRecording:
    """Verify call records in SQLite have all required fields."""

    def test_record_has_call_id(self, adapter):
        result = adapter.call("rec-model", "prompt")
        row = adapter.get_call(result["call_id"])
        assert row["call_id"] == result["call_id"]
        assert len(row["call_id"]) == 32  # uuid hex

    def test_record_has_model_id(self, adapter):
        adapter.call("model-rec-123", "prompt")
        calls = adapter.list_calls()
        assert calls[0]["model_id"] == "model-rec-123"

    def test_record_has_prompt_hash(self, adapter):
        prompt = "hash this prompt"
        result = adapter.call("m", prompt)
        row = adapter.get_call(result["call_id"])
        assert len(row["prompt_hash"]) == 64  # sha256 hex

    def test_record_prompt_hash_matches_sha256(self, adapter):
        messages = [{"role": "user", "content": "check hash"}]
        result = adapter.call_messages("m", messages)
        expected = hashlib.sha256(
            json.dumps(messages, default=str).encode("utf-8")
        ).hexdigest()
        row = adapter.get_call(result["call_id"])
        assert row["prompt_hash"] == expected

    def test_record_has_tokens(self, adapter):
        result = adapter.call("m", "prompt")
        row = adapter.get_call(result["call_id"])
        assert isinstance(row["completion_tokens"], int)
        assert row["completion_tokens"] == 0  # stub mode

    def test_record_has_cost(self, adapter):
        result = adapter.call("m", "prompt")
        row = adapter.get_call(result["call_id"])
        assert isinstance(row["cost"], float)
        assert row["cost"] == 0.0  # stub mode

    def test_record_has_latency(self, adapter):
        result = adapter.call("m", "prompt")
        row = adapter.get_call(result["call_id"])
        assert isinstance(row["latency_ms"], int)
        assert row["latency_ms"] >= 0

    def test_record_has_status(self, adapter):
        result = adapter.call("m", "prompt")
        row = adapter.get_call(result["call_id"])
        assert row["status"] == "stub"

    def test_record_has_timestamp(self, adapter):
        before = time.time()
        result = adapter.call("m", "prompt")
        after = time.time()
        row = adapter.get_call(result["call_id"])
        assert before <= row["timestamp"] <= after


# =====================================================================
# 6. TestGetCall
# =====================================================================

class TestGetCall:
    """get_call: retrieve existing and nonexistent calls."""

    def test_get_existing_call(self, adapter):
        result = adapter.call("existing-model", "hi")
        fetched = adapter.get_call(result["call_id"])
        assert fetched is not None
        assert fetched["call_id"] == result["call_id"]
        assert fetched["model_id"] == "existing-model"

    def test_get_nonexistent_returns_none(self, adapter):
        assert adapter.get_call("nonexistent-id-12345") is None

    def test_get_returns_dict(self, adapter):
        result = adapter.call("m", "p")
        fetched = adapter.get_call(result["call_id"])
        assert isinstance(fetched, dict)


# =====================================================================
# 7. TestListCalls
# =====================================================================

class TestListCalls:
    """list_calls: list all and filter by model_id."""

    def test_list_empty(self, adapter):
        assert adapter.list_calls() == []

    def test_list_all(self, adapter):
        adapter.call("m1", "p1")
        adapter.call("m2", "p2")
        calls = adapter.list_calls()
        assert len(calls) == 2

    def test_list_filter_by_model(self, adapter):
        adapter.call("alpha", "p1")
        adapter.call("beta", "p2")
        adapter.call("alpha", "p3")
        calls = adapter.list_calls(model_id="alpha")
        assert len(calls) == 2
        assert all(c["model_id"] == "alpha" for c in calls)

    def test_list_filter_nonexistent_model(self, adapter):
        adapter.call("alpha", "p1")
        calls = adapter.list_calls(model_id="nonexistent")
        assert calls == []

    def test_list_respects_limit(self, adapter):
        for i in range(15):
            adapter.call("m", f"prompt-{i}")
        calls = adapter.list_calls(limit=5)
        assert len(calls) == 5

    def test_list_ordered_by_timestamp_desc(self, adapter):
        adapter.call("m", "first")
        adapter.call("m", "second")
        adapter.call("m", "third")
        calls = adapter.list_calls()
        assert calls[0]["timestamp"] >= calls[1]["timestamp"]
        assert calls[1]["timestamp"] >= calls[2]["timestamp"]

    def test_list_default_limit_100(self, adapter):
        for i in range(120):
            adapter.call("m", f"prompt-{i}")
        calls = adapter.list_calls()
        assert len(calls) == 100


# =====================================================================
# 8. TestGetUsageStats
# =====================================================================

class TestGetUsageStats:
    """get_usage_stats: empty, populated, by_model breakdown."""

    def test_empty_stats(self, adapter):
        stats = adapter.get_usage_stats()
        assert stats["total_calls"] == 0
        assert stats["total_prompt_tokens"] == 0
        assert stats["total_completion_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["by_model"] == {}

    def test_populated_stats(self, adapter):
        adapter.call("m1", "p1")
        adapter.call("m1", "p2")
        adapter.call("m2", "p3")
        stats = adapter.get_usage_stats()
        assert stats["total_calls"] == 3

    def test_by_model_breakdown(self, adapter):
        adapter.call("model-a", "p1")
        adapter.call("model-a", "p2")
        adapter.call("model-b", "p3")
        stats = adapter.get_usage_stats()
        assert stats["by_model"]["model-a"]["calls"] == 2
        assert stats["by_model"]["model-b"]["calls"] == 1

    def test_by_model_cost(self, adapter):
        adapter.call("m1", "p1")
        stats = adapter.get_usage_stats()
        assert "m1" in stats["by_model"]
        assert isinstance(stats["by_model"]["m1"]["cost"], float)

    def test_total_cost_rounded_to_six_decimals(self, adapter):
        adapter.call("m", "p")
        stats = adapter.get_usage_stats()
        # Verify it is a float and rounded
        cost_str = str(stats["total_cost"])
        if "." in cost_str:
            decimals = len(cost_str.split(".")[1])
            assert decimals <= 6


# =====================================================================
# 9. TestSingleton
# =====================================================================

class TestSingleton:
    """get_llm_adapter returns instance, idempotent."""

    def test_returns_llm_adapter_instance(self):
        adapter = get_llm_adapter()
        assert isinstance(adapter, LLMAdapter)

    def test_idempotent_returns_same_instance(self):
        a = get_llm_adapter()
        b = get_llm_adapter()
        assert a is b

    def test_singleton_ignores_args_on_second_call(self):
        bus1 = EventBus()
        a = get_llm_adapter(event_bus=bus1)
        bus2 = EventBus()
        b = get_llm_adapter(event_bus=bus2)
        assert a is b
        assert a._event_bus is bus1

    def test_singleton_can_make_calls(self):
        adapter = get_llm_adapter()
        result = adapter.call("singleton-test", "hello")
        assert result["text"] == "stub"


# =====================================================================
# 10. TestTokenEstimation
# =====================================================================

class TestTokenEstimation:
    """Verify _estimate_tokens() works (len(text) // 4)."""

    def test_empty_string_minimum_1(self, adapter):
        # len("") // 4 == 0, but max(1, 0) == 1
        assert adapter._estimate_tokens("") == 1

    def test_short_string(self, adapter):
        # len("ab") // 4 == 0 -> max(1, 0) == 1
        assert adapter._estimate_tokens("ab") == 1

    def test_four_chars(self, adapter):
        assert adapter._estimate_tokens("abcd") == 1

    def test_eight_chars(self, adapter):
        assert adapter._estimate_tokens("abcdefgh") == 2

    def test_longer_text(self, adapter):
        text = "a" * 100
        assert adapter._estimate_tokens(text) == 25

    def test_unicode_text(self, adapter):
        # unicode chars counted by len() in Python
        text = "hello world"
        assert adapter._estimate_tokens(text) == len(text) // 4

    def test_estimate_is_int(self, adapter):
        result = adapter._estimate_tokens("some text here")
        assert isinstance(result, int)
        assert result >= 1

    def test_cost_calculation(self, adapter):
        os.environ["SYLION_LLM_COST_PER_1K"] = "0.01"
        cost = adapter._calculate_cost(1000)
        assert cost == pytest.approx(0.01)

    def test_cost_calculation_zero_tokens(self, adapter):
        os.environ["SYLION_LLM_COST_PER_1K"] = "0.01"
        cost = adapter._calculate_cost(0)
        assert cost == 0.0
