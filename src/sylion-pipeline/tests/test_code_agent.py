"""
SYLION Cognitive -- Code Agent Tests

Comprehensive tests for CodeAgent: generate, review, analyze, fix,
list_operations, event emission, and error handling.
"""

from __future__ import annotations

import hashlib
import json
import threading

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.code_agent import CodeAgent, CodeOperation


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    """Fresh in-memory EventBus per test."""
    return EventBus()


@pytest.fixture
def agent(bus):
    """Fresh in-memory CodeAgent with EventBus attached."""
    return CodeAgent(event_bus=bus)


@pytest.fixture
def captured_events(bus):
    """Subscribe to all events and collect them in a list."""
    events: list[SylionEvent] = []
    bus.subscribe("*", events.append)
    return events


@pytest.fixture
def fake_llm():
    """A minimal fake LLM adapter that returns deterministic responses."""
    class FakeLLM:
        _default_model = "test-model-v1"

        def call(self, model_id: str, prompt: str) -> dict:
            return {"text": f"LLM_RESPONSE[{prompt[:20]}]"}

    return FakeLLM()


@pytest.fixture
def agent_with_llm(fake_llm, bus):
    """CodeAgent wired to the fake LLM adapter."""
    return CodeAgent(llm_adapter=fake_llm, event_bus=bus)


# =====================================================================
# Test CodeOperation dataclass
# =====================================================================

class TestCodeOperation:

    def test_auto_fields(self):
        op = CodeOperation()
        assert op.op_id != ""
        assert op.timestamp > 0.0

    def test_custom_fields(self):
        op = CodeOperation(op_id="custom1", operation="generate", timestamp=1.0)
        assert op.op_id == "custom1"
        assert op.operation == "generate"
        assert op.timestamp == 1.0


# =====================================================================
# Test generate
# =====================================================================

class TestGenerate:

    def test_generate_returns_operation_dict(self, agent):
        result = agent.generate("write a fibonacci function")
        assert result["op_id"]
        assert result["operation"] == "generate"
        assert result["input_hash"] != ""
        assert result["output_hash"] != ""
        assert result["result"] == "stub"  # no LLM adapter
        assert result["timestamp"] > 0

    def test_generate_with_language(self, agent):
        result = agent.generate("hello world", language="rust")
        assert result["operation"] == "generate"
        # metadata stored in DB should contain language
        ops = agent.list_operations("generate")
        assert len(ops) == 1
        meta = ops[0]["metadata"]
        assert meta["language"] == "rust"

    def test_generate_input_hash_matches_sha256(self, agent):
        prompt = "test prompt"
        result = agent.generate(prompt)
        expected = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        assert result["input_hash"] == expected

    def test_generate_with_llm_adapter(self, agent_with_llm):
        result = agent_with_llm.generate("sort an array")
        assert "LLM_RESPONSE[" in result["result"]
        assert result["result"] != "stub"

    def test_quality_report_is_not_evaluated_as_artifact_contract(self, agent):
        prompt = (
            "Oceń gotowość produktu, wskaż braki, ryzyka, decyzje Human Gate, "
            "wynik guardów i czy produkt może zostać uznany za zaliczony."
        )
        report = (
            "## Ocena gotowości produktu\n"
            "Artefakt zawiera lokalny CRM z listą klientów, statusami leadów, filtrem i eksportem CSV.\n"
            "Braki: dokumentacja użytkownika wymaga doprecyzowania, a testy wydajnościowe są poza zakresem MVP.\n"
            "Ryzyka: błędne dane wejściowe i niepełny eksport CSV.\n"
            "Human Gate: operator zatwierdza zakres przed wdrożeniem.\n"
            "Guard: walidacja danych oraz test akceptacyjny dodawania, filtrowania i eksportu.\n"
            "Produkt może zostać uznany za zaliczony po potwierdzeniu testów i zapisaniu raportu."
        )
        assert agent._quality_findings(prompt, report) == []

    def test_quality_report_still_rejects_generic_text(self, agent):
        prompt = "Oceń gotowość produktu i wynik guardów."
        report = "Produkt wygląda dobrze. Brak szczegółów."
        assert "artifact_contract_too_thin" in agent._quality_findings(prompt, report)

    def test_localhost_runtime_url_is_allowed(self, agent):
        prompt = "Wytworz artefakt implementacyjny dla lokalnego CRM z klientami, leadami i eksportem CSV."
        base = (
            "Artefakt implementacyjny produktu CRM. Model danych: klient, lead, status oraz eksport CSV. "
            "API: GET /api/customers, POST /api/customers, PUT /api/customers/{id} i endpoint eksportu. "
            "Kod: schema Customer, class CustomerService, walidacja email, statusu i pustych pol. "
            "Testy akceptacyjne: test dodawania klienta, test zmiany statusu, test filtrowania i test eksportu CSV. "
            "Dane wejsciowe, oczekiwany wynik, kryterium zaliczenia, ryzyka, Human Gate i Guard sa opisane. "
        )
        text = (base * 8) + "Uruchom lokalnie: http://localhost:3000."
        assert "irrelevant_external_url" not in agent._quality_findings(prompt, text)

    def test_example_com_email_fixture_is_allowed(self, agent):
        prompt = "Napisz testy akceptacyjne produktu CRM dla klientow, statusow leadow, filtrow i eksportu CSV."
        base = (
            "Testy akceptacyjne CRM. Dane wejsciowe: Jan Kowalski, jan.kowalski@example.com, status Nowy. "
            "Model danych: klient, lead, status, filtr, eksport CSV. API: POST /api/customers oraz GET /api/customers/export. "
            "Test dodawania klienta ma oczekiwany wynik: rekord pojawia sie na liscie. "
            "Test statusu ma kryterium zaliczenia: status zmienia sie na Wygrany. "
            "Guard waliduje email, puste pola, unikalnosc i eksport bez danych prywatnych. "
        )
        text = base * 8
        findings = agent._quality_findings(prompt, text)
        assert "bad_marker:example.com" not in findings
        assert "irrelevant_external_url" not in findings

    def test_example_com_endpoint_is_blocked(self, agent):
        prompt = "Wytworz artefakt implementacyjny dla lokalnego CRM z klientami, leadami i eksportem CSV."
        base = (
            "Artefakt implementacyjny produktu CRM. Model danych: klient, lead, status oraz eksport CSV. "
            "API: GET /api/customers, POST /api/customers, PUT /api/customers/{id} i endpoint eksportu. "
            "Kod: schema Customer, class CustomerService, walidacja email, statusu i pustych pol. "
            "Testy akceptacyjne: test dodawania klienta, test zmiany statusu, test filtrowania i test eksportu CSV. "
            "Dane wejsciowe, oczekiwany wynik, kryterium zaliczenia, ryzyka, Human Gate i Guard sa opisane. "
        )
        text = (base * 8) + "Dokumentacja demo: https://example.com/crm."
        assert "bad_marker:example.com" in agent._quality_findings(prompt, text)


# =====================================================================
# Test review
# =====================================================================

class TestReview:

    def test_review_returns_operation_dict(self, agent):
        result = agent.review("def foo(): pass")
        assert result["op_id"]
        assert result["operation"] == "review"
        assert result["result"] == "stub"

    def test_review_with_criteria(self, agent):
        result = agent.review("x = 1", criteria=["security", "style"])
        ops = agent.list_operations("review")
        assert len(ops) == 1
        meta = ops[0]["metadata"]
        assert "security" in meta["criteria"]
        assert "style" in meta["criteria"]

    def test_review_empty_criteria_defaults(self, agent):
        result = agent.review("pass", criteria=None)
        assert result["operation"] == "review"
        ops = agent.list_operations("review")
        assert ops[0]["metadata"]["criteria"] == []


# =====================================================================
# Test analyze
# =====================================================================

class TestAnalyze:

    def test_analyze_returns_result(self, agent):
        result = agent.analyze("class Foo: pass")
        assert result["operation"] == "analyze"
        assert result["input_hash"] != ""
        assert result["result"] == "stub"

    def test_analyze_metadata_records_code_length(self, agent):
        code = "x = 1\ny = 2\n"
        agent.analyze(code)
        ops = agent.list_operations("analyze")
        assert ops[0]["metadata"]["code_length"] == len(code)


# =====================================================================
# Test fix
# =====================================================================

class TestFix:

    def test_fix_returns_result(self, agent):
        result = agent.fix("def foo()\n  pass", "missing colon")
        assert result["operation"] == "fix"
        assert result["result"] == "stub"

    def test_fix_metadata_records_issue(self, agent):
        agent.fix("broken code", "type error on line 5")
        ops = agent.list_operations("fix")
        meta = ops[0]["metadata"]
        assert meta["issue"] == "type error on line 5"
        assert meta["code_length"] == len("broken code")


# =====================================================================
# Test list_operations
# =====================================================================

class TestListOperations:

    def test_list_all_operations(self, agent):
        agent.generate("p1")
        agent.review("code")
        agent.analyze("code2")
        ops = agent.list_operations()
        assert len(ops) == 3

    def test_list_filtered_by_operation(self, agent):
        agent.generate("p1")
        agent.generate("p2")
        agent.review("c1")
        gen_ops = agent.list_operations("generate")
        assert len(gen_ops) == 2
        review_ops = agent.list_operations("review")
        assert len(review_ops) == 1

    def test_list_respects_limit(self, agent):
        for i in range(15):
            agent.generate(f"prompt-{i}")
        ops = agent.list_operations(limit=5)
        assert len(ops) == 5

    def test_list_returns_parsed_metadata(self, agent):
        agent.generate("hello")
        ops = agent.list_operations()
        assert isinstance(ops[0]["metadata"], dict)

    def test_list_empty(self, agent):
        ops = agent.list_operations()
        assert ops == []


# =====================================================================
# Test event emission
# =====================================================================

class TestEventEmission:

    def test_generate_emits_event(self, agent, captured_events):
        agent.generate("test prompt")
        assert len(captured_events) == 1
        evt = captured_events[0]
        assert evt.topic == "code.operation"
        assert evt.payload["operation"] == "generate"

    def test_no_event_without_bus(self):
        agent = CodeAgent(event_bus=None)
        # Should not raise
        result = agent.generate("quiet prompt")
        assert result["operation"] == "generate"


# =====================================================================
# Test thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_generates(self, agent):
        errors: list[Exception] = []

        def do_generate(idx):
            try:
                agent.generate(f"concurrent-{idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_generate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        ops = agent.list_operations()
        assert len(ops) == 20


# =====================================================================
# Test LLM adapter failure handling
# =====================================================================

class TestLLMAdapterFailure:

    def test_llm_exception_falls_back_to_stub(self, bus):
        class BrokenLLM:
            def call(self, model_id, prompt):
                raise RuntimeError("LLM unavailable")

        agent = CodeAgent(llm_adapter=BrokenLLM(), event_bus=bus)
        result = agent.generate("test")
        assert result["result"] == "stub"

    def test_llm_missing_text_key_falls_back(self, bus):
        class BadLLM:
            def call(self, model_id, prompt):
                return {"no_text_key": "oops"}

        agent = CodeAgent(llm_adapter=BadLLM(), event_bus=bus)
        result = agent.generate("test")
        assert result["result"] == ""  # .get("text", "") returns ""

    def test_policy_block_does_not_fall_back_to_stub(self, bus):
        class BlockingLLM:
            def call(self, model_id, prompt):
                return {
                    "status": "blocked",
                    "blocked": True,
                    "policy": {"reason": "code generation blocked"},
                }

        agent = CodeAgent(llm_adapter=BlockingLLM(), event_bus=bus)
        with pytest.raises(PermissionError, match="code generation blocked"):
            agent.generate("unsafe change")
        assert agent.list_operations() == []
