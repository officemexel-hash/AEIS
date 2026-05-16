"""Validation helpers for operator-selected role resolver models."""

from __future__ import annotations

import os
import subprocess

ENV_KEY_BY_PROVIDER: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "zai": "ZAI_API_KEY",
    "xai": "XAI_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
}

PROVIDER_OF_MODEL: dict[str, str] = {
    "claude-haiku-4-5": "anthropic",
    "claude-sonnet-4-6": "anthropic",
    "claude-opus-4-7": "anthropic",
    "gpt-5": "openai",
    "gpt-4.1-mini": "openai",
    "gemini-2.5-flash": "google",
    "gemini-2.5-pro": "google",
}

LOCAL_MODEL_PREFIXES: set[str] = {
    "qwen2.5",
    "qwen3",
    "qwen3.5",
    "llama3",
    "llama3.1",
    "llama3.2",
    "llama3.3",
    "mistral",
    "gemma2",
    "phi3",
    "codellama",
    "deepseek-coder",
}


class ModelNotAvailableError(Exception):
    """Raised when an operator-selected model is not actually available."""

    def __init__(self, model_id: str, reason: str):
        self.model_id = model_id
        self.reason = reason
        super().__init__(f"{model_id}: {reason}")


def check_model_available(operator_id: str, model_id: str) -> tuple[bool, str | None]:
    """Return ``(is_available, reason_in_polish)`` for one model id."""
    normalized = str(model_id or "").strip()
    if not normalized:
        return False, "Brak wybranego modelu"

    if _is_local_ollama_model(normalized):
        if _local_model_installed(normalized):
            return True, None
        return (
            False,
            f"Model lokalny '{normalized}' nie jest zainstalowany "
            f"(uruchom: ollama pull {normalized})",
        )

    provider = _provider_of_model(normalized)
    if not provider:
        return False, f"Nieznany model '{normalized}' - brak w katalogu"

    if _subscription_covers_model(operator_id, normalized, provider):
        return True, None

    if _resolve_provider_key(provider):
        return True, None

    provider_label = provider.capitalize()
    return (
        False,
        f"Brak dostepu do modelu '{normalized}' - wymagany aktywny klucz API "
        f"lub subskrypcja provider'a {provider_label}",
    )


def validate_judge_models(
    operator_id: str,
    judge_models: dict[str, str],
) -> dict[str, str | None]:
    """Validate per-risk judge assignments."""
    errors: dict[str, str | None] = {}
    for risk, model_expr in judge_models.items():
        normalized = str(model_expr or "").strip()
        if not normalized:
            errors[risk] = f"Brak wybranego modelu dla poziomu ryzyka '{risk}'"
            continue

        for single_model in _split_model_expr(normalized):
            ok, reason = check_model_available(operator_id, single_model)
            if not ok:
                errors[risk] = reason
                break
        else:
            errors[risk] = None
    return errors


def ensure_model_available(operator_id: str, model_id: str) -> None:
    """Raise ``ModelNotAvailableError`` when the selected model is unavailable."""
    ok, reason = check_model_available(operator_id, model_id)
    if not ok and reason:
        raise ModelNotAvailableError(model_id=str(model_id or "").strip(), reason=reason)


def _split_model_expr(model_expr: str) -> list[str]:
    return [part.strip() for part in str(model_expr).split("+") if part.strip()]


def _provider_of_model(model_id: str) -> str | None:
    provider = PROVIDER_OF_MODEL.get(model_id)
    if provider:
        return provider

    if model_id.startswith("claude"):
        return "anthropic"
    if model_id.startswith("gpt"):
        return "openai"
    if model_id.startswith("gemini"):
        return "google"
    return _provider_from_catalog(model_id)


def _provider_from_catalog(model_id: str) -> str | None:
    try:
        from sylion.aeis.advisor.pricing import catalog

        model = catalog.get_model(model_id)
    except Exception:
        return None
    if model is None or getattr(model, "is_local", False):
        return None
    return str(getattr(model, "provider_id", "") or "") or None


def _subscription_covers_model(operator_id: str, model_id: str, provider: str) -> bool:
    """Best-effort subscription hook.

    The current codebase does not expose a stable quota API for advisor
    subscriptions, so this checks an optional tracker when present and otherwise
    returns ``False`` without hitting heavier storage paths.
    """
    try:
        from sylion.aeis.advisor import subscription as subscription_module

        tracker = getattr(subscription_module, "quota_tracker", None)
        if tracker is None:
            return False
        get_quota_status = getattr(tracker, "get_quota_status", None)
        if get_quota_status is None:
            return False
        quota = get_quota_status(operator_id, model_id)
        if quota is None:
            return False
        return bool(getattr(quota, "has_quota", False))
    except Exception:
        return False


def _is_local_ollama_model(model_id: str) -> bool:
    if ":" not in model_id:
        return False
    prefix = model_id.split(":", 1)[0].strip().lower()
    return prefix in LOCAL_MODEL_PREFIXES


def _local_model_installed(model_id: str) -> bool:
    """Check whether ``ollama list`` contains the requested model."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    return model_id in (result.stdout or "")


def _resolve_provider_key(provider: str) -> str:
    try:
        from sylion.security.key_vault import get_key_vault

        vault = get_key_vault()
        active = [item for item in vault.list_keys(provider=provider) if item.get("is_active")]
        if active:
            value = vault.get_decrypted_key(active[0]["key_id"]) or ""
            if value:
                return value
    except Exception:
        pass

    env_key = ENV_KEY_BY_PROVIDER.get(provider, "")
    return os.environ.get(env_key, "") or ""
