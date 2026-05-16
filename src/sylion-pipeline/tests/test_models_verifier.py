from __future__ import annotations

import asyncio

from models import ModelRouter, MultiModelVerifier


def test_ollama_local_models_are_reported_available(monkeypatch):
    monkeypatch.setattr("models._list_ollama_models", lambda base_url: {"qwen3.5:latest", "gpt-oss:20b"})
    router = ModelRouter()

    available_ids = {model.id for model in router.get_available_models()}

    assert "ollama-qwen3.5" in available_ids
    assert "ollama-gpt-oss-20b" in available_ids


def test_multimodel_verifier_computes_consensus_from_real_responses(monkeypatch):
    router = ModelRouter()
    verifier = MultiModelVerifier(router=router, min_agreement=0.5)
    monkeypatch.setattr(
        router,
        "get_verification_models",
        lambda primary_model, count=3: [
            router.get_model("ollama-qwen3.5"),
            router.get_model("ollama-gpt-oss-20b"),
        ],
    )

    responses = iter(
        [
            {
                "text": '{"agrees": true, "confidence": 0.8, "issues": [], "additions": ["more tests"], "reasoning": "Looks sound."}',
                "prompt_tokens": 10,
                "completion_tokens": 15,
            },
            {
                "text": '{"agrees": false, "confidence": 0.6, "issues": ["missing validation"], "additions": [], "reasoning": "Input handling is incomplete."}',
                "prompt_tokens": 12,
                "completion_tokens": 18,
            },
        ]
    )
    monkeypatch.setattr(verifier, "_call_verification_model", lambda model, prompt: next(responses))

    result = asyncio.run(
        verifier.verify(
            task="Review this implementation",
            primary_response="The code is production-ready.",
            primary_model="gpt-5",
            verify_count=2,
        )
    )

    assert len(result.verifications) == 2
    assert result.consensus is True
    assert result.confidence == 0.7
    assert "missing validation" in result.discrepancies
