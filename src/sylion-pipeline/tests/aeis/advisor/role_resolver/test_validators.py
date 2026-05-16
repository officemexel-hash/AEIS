from __future__ import annotations

from sylion.aeis.advisor.role_resolver import _validators


def test_local_model_installed_returns_true(monkeypatch):
    monkeypatch.setattr(_validators, "_local_model_installed", lambda model_id: True)

    ok, reason = _validators.check_model_available("op-1", "qwen2.5:7b-instruct")

    assert ok is True
    assert reason is None


def test_local_model_not_installed_returns_polish_reason(monkeypatch):
    monkeypatch.setattr(_validators, "_local_model_installed", lambda model_id: False)

    ok, reason = _validators.check_model_available("op-1", "qwen2.5:7b-instruct")

    assert ok is False
    assert reason == (
        "Model lokalny 'qwen2.5:7b-instruct' nie jest zainstalowany "
        "(uruchom: ollama pull qwen2.5:7b-instruct)"
    )


def test_cloud_model_with_api_key_available(monkeypatch):
    monkeypatch.setattr(_validators, "_subscription_covers_model", lambda *args: False)
    monkeypatch.setattr(_validators, "_resolve_provider_key", lambda provider: "sk-test")

    ok, reason = _validators.check_model_available("op-1", "claude-opus-4-7")

    assert ok is True
    assert reason is None


def test_cloud_model_no_key_no_subscription_unavailable(monkeypatch):
    monkeypatch.setattr(_validators, "_subscription_covers_model", lambda *args: False)
    monkeypatch.setattr(_validators, "_resolve_provider_key", lambda provider: "")

    ok, reason = _validators.check_model_available("op-1", "claude-opus-4-7")

    assert ok is False
    assert reason == (
        "Brak dostepu do modelu 'claude-opus-4-7' - wymagany aktywny klucz API "
        "lub subskrypcja provider'a Anthropic"
    )


def test_subscription_covers_model_available(monkeypatch):
    monkeypatch.setattr(_validators, "_subscription_covers_model", lambda *args: True)
    monkeypatch.setattr(_validators, "_resolve_provider_key", lambda provider: "")

    ok, reason = _validators.check_model_available("op-1", "gpt-5")

    assert ok is True
    assert reason is None


def test_dual_judge_validates_both_sides(monkeypatch):
    seen: list[str] = []

    def _fake_check(operator_id: str, model_id: str):
        seen.append(model_id)
        if model_id == "gpt-5":
            return False, "Brak dostepu do modelu 'gpt-5'"
        return True, None

    monkeypatch.setattr(_validators, "check_model_available", _fake_check)

    errors = _validators.validate_judge_models(
        "op-1",
        {"critical": "claude-opus-4-7+gpt-5"},
    )

    assert seen == ["claude-opus-4-7", "gpt-5"]
    assert errors == {"critical": "Brak dostepu do modelu 'gpt-5'"}


def test_validate_judge_models_returns_error_per_risk(monkeypatch):
    def _fake_check(operator_id: str, model_id: str):
        return {
            "claude-opus-4-7": (False, "Brak dostepu do modelu 'claude-opus-4-7'"),
            "gpt-5": (True, None),
        }[model_id]

    monkeypatch.setattr(_validators, "check_model_available", _fake_check)

    errors = _validators.validate_judge_models(
        "op-1",
        {
            "low": "",
            "high": "gpt-5",
            "critical": "claude-opus-4-7",
        },
    )

    assert errors == {
        "low": "Brak wybranego modelu dla poziomu ryzyka 'low'",
        "high": None,
        "critical": "Brak dostepu do modelu 'claude-opus-4-7'",
    }
