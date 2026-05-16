from __future__ import annotations

import json

import pytest

from sylion.cognitive.model_registry import get_model_registry, reset_model_registry
from sylion.cognitive.model_runtime_policy import (
    preflight_model_call,
    record_model_usage,
)
from sylion.governance.human_gate import reset_human_gate
from sylion.governance.ticket import reset_ticket_store
from sylion.monitoring.model_budget import get_model_budget, reset_model_budget


@pytest.fixture()
def policy_runtime(tmp_path):
    db_path = tmp_path / "model-runtime-policy.sqlite"
    reset_ticket_store(db_path=db_path)
    reset_human_gate(db_path=db_path)
    reset_model_registry(db_path=db_path)
    reset_model_budget()
    budget = get_model_budget(db_path=str(db_path))
    yield {
        "db_path": db_path,
        "budget": budget,
    }
    reset_model_budget()


def _register(model_id: str, provider: str, config: dict):
    registry = get_model_registry()
    return registry.register_model(
        model_id=model_id,
        provider=provider,
        display_name=model_id,
        config_json=json.dumps(config),
    )


def test_read_only_model_blocks_runtime_and_creates_human_gate(policy_runtime):
    _register(
        "readonly-model",
        "openai",
        {
            "access_level": "read_only",
            "approval_policy": "always_human_gate",
        },
    )

    result = preflight_model_call(
        "readonly-model",
        provider="openai",
        operation="llm_adapter.call",
        action_type="generation",
        risk_level="medium",
    )

    assert result["allowed"] is False
    assert result["requires_human_gate"] is True
    assert result["reason"] == "Model access_level=read_only does not permit runtime execution."
    assert result["human_gate_request"]["status"] == "pending"
    assert result["human_gate_request"]["gate_id"] == "ai_model_runtime_policy"


def test_budget_exceeded_blocks_before_provider_execution(policy_runtime):
    _register(
        "budgeted-model",
        "ollama",
        {
            "access_level": "full",
            "approval_policy": "ask_for_risky_changes",
            "cost_per_1k_tokens_usd": 1.0,
        },
    )
    budget = policy_runtime["budget"]
    budget.set_budget("budgeted-model", daily_limit=0.01, monthly_limit=1.0)
    budget.record_usage("budgeted-model", tokens=20, cost=0.02)

    result = preflight_model_call(
        "budgeted-model",
        provider="ollama",
        operation="ai_provider_connectivity_test",
        action_type="connectivity_test",
        risk_level="low",
    )

    assert result["allowed"] is False
    assert result["reason"] == "Model budget exceeded; execution requires operator approval."
    assert result["human_gate_request"]["gate_id"] == "ai_model_runtime_policy"


def test_record_model_usage_applies_operator_configured_cost(policy_runtime):
    _register(
        "priced-model",
        "ollama",
        {
            "access_level": "full",
            "approval_policy": "ask_for_risky_changes",
            "cost_per_1k_tokens_usd": 1.0,
        },
    )
    budget = policy_runtime["budget"]
    budget.set_budget("priced-model", daily_limit=10.0, monthly_limit=100.0)

    usage = record_model_usage(
        "priced-model",
        provider="ollama",
        prompt_tokens=10,
        completion_tokens=5,
    )

    assert usage is not None
    assert usage["tokens"] == 15
    assert usage["cost"] == pytest.approx(0.015)
    assert budget.get_budget("priced-model")["spent_today"] == pytest.approx(0.015)
