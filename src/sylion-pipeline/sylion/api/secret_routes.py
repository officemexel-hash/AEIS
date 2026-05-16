"""
SYLION API -- Secret Provider routes.

Endpoints for the SecretProvider module:
  store_secret, get_secret, rotate_secret, delete_secret,
  list_secrets, get_secret_history,
  get_access_log, get_secret_stats.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/secrets", tags=["Secrets"])

# F-V10-007 fix: when an operator stores a key under one of these canonical
# env-style names, also mirror it into the KeyVault under the matching
# provider id so /ai-providers/test/* and the model router pick it up
# without a second copy/paste step.
_CANONICAL_SECRET_TO_PROVIDER: dict[str, str] = {
    "OPENAI_API_KEY": "openai",
    "OPENAI": "openai",
    "CHATGPT": "openai",
    "CHAT_GPT": "openai",
    "ANTHROPIC_API_KEY": "anthropic",
    "ANTHROPIC": "anthropic",
    "CLAUDE": "anthropic",
    "CLOUDE": "anthropic",
    "PERPLEXITY_API_KEY": "perplexity",
    "PERPLEXITY": "perplexity",
    "GOOGLE_API_KEY": "google",
    "GEMINI_API_KEY": "google",
    "GOOGLE": "google",
    "GEMINI": "google",
    "ZAI_API_KEY": "zai",
    "ZAI": "zai",
    "Z_AI": "zai",
    "OPENROUTER_API_KEY": "openrouter",
    "OPENROUTER": "openrouter",
    "OPENROUTE": "openrouter",
    "MOONSHOT_API_KEY": "moonshot",
    "KIMI_API_KEY": "moonshot",
    "MOONSHOT": "moonshot",
    "KIMI": "moonshot",
    "MISTRAL_API_KEY": "mistral",
    "MISTRAL": "mistral",
    "DEEPSEEK_API_KEY": "deepseek",
    "DEEPSEEK": "deepseek",
    "GROQ_API_KEY": "groq",
    "GROQ": "groq",
    "TOGETHER_API_KEY": "together",
    "TOGETHER": "together",
    "XAI_API_KEY": "xai",
    "XAI": "xai",
    "GROK": "xai",
}


def _provider_for_secret_name(name: str) -> str | None:
    canonical = name.strip().upper()
    provider = _CANONICAL_SECRET_TO_PROVIDER.get(canonical)
    if provider:
        return provider
    simplified = "".join(ch for ch in canonical if ch.isalnum())
    aliases = {
        "CHATGPT": "openai",
        "OPENAI": "openai",
        "CLAUDE": "anthropic",
        "CLOUDE": "anthropic",
        "ANTHROPIC": "anthropic",
        "PERPLEXITY": "perplexity",
        "GOOGLE": "google",
        "GEMINI": "google",
        "ZAI": "zai",
        "ZAIAPIKEY": "zai",
        "OPENROUTER": "openrouter",
        "OPENROUTE": "openrouter",
        "KIMI": "moonshot",
        "MOONSHOT": "moonshot",
        "DEEPSEEK": "deepseek",
        "MISTRAL": "mistral",
        "GROQ": "groq",
        "TOGETHER": "together",
        "XAI": "xai",
        "GROK": "xai",
    }
    return aliases.get(simplified)


def _mirror_provider_secret_to_key_vault(
    name: str,
    value: str | None,
    *,
    replace_active: bool = False,
) -> dict | None:
    """Mirror canonical provider secrets into KeyVault for model runtime use."""
    if not value:
        return None
    canonical = name.strip().upper()
    provider_for_secret = _provider_for_secret_name(name)
    if not provider_for_secret:
        return None

    from sylion.security.key_vault import get_key_vault
    vault = get_key_vault()
    provider_keys = vault.list_keys(provider=provider_for_secret)
    active_keys = [k for k in provider_keys if k.get("is_active") in (1, True)]
    for key in active_keys:
        key_id = key.get("key_id")
        if key_id and vault.get_decrypted_key(key_id) == value:
            return {
                "provider": provider_for_secret,
                "mirrored": False,
                "reason": "active_key_up_to_date",
                "key_id": key_id,
            }
    if active_keys and not replace_active:
        return {
            "provider": provider_for_secret,
            "mirrored": False,
            "reason": "active_key_exists",
            "key_id": active_keys[0].get("key_id"),
        }
    for key in provider_keys:
        key_id = key.get("key_id")
        if key_id and vault.get_decrypted_key(key_id) == value:
            vault.activate_key(key_id)
            return {
                "provider": provider_for_secret,
                "mirrored": False,
                "reason": "existing_key_activated",
                "key_id": key_id,
            }
    record = vault.store_key(
        provider=provider_for_secret,
        encrypted_key=value,
        display_name=canonical,
        metadata={"source": "secrets_dashboard", "secret_name": canonical},
    )
    key_id = record.get("key_id")
    if key_id:
        vault.activate_key(key_id)
    return {
        "provider": provider_for_secret,
        "mirrored": True,
        "key_id": key_id,
    }


def _provider_limit_summary(provider: str, key_info: dict[str, Any]) -> dict[str, Any]:
    """Normalize provider introspection into operator-facing budget fields.

    Most subscription products (ChatGPT Plus/Pro, Claude web plans, Gemini web)
    do not expose 5-hour or weekly app quotas through API keys. When a provider
    exposes API credit or rate-limit headers, return them; otherwise mark the
    field explicitly as unavailable instead of guessing.
    """
    rate_limits = key_info.get("rate_limits") or {}
    summary: dict[str, Any] = {
        "subscription_5h": {"status": "not_exposed_by_provider_api"},
        "subscription_weekly": {"status": "not_exposed_by_provider_api"},
        "api_budget": {"status": "not_exposed_by_provider_api"},
        "rate_limits": rate_limits,
        "plan_inferred": key_info.get("plan_inferred") or "unknown",
    }
    if provider == "openrouter":
        summary["api_budget"] = {
            "status": "reported_by_provider",
            "usage_usd": key_info.get("balance_usd"),
            "credit_limit_usd": key_info.get("credit_limit_usd"),
        }
    elif rate_limits:
        summary["api_budget"] = {
            "status": "rate_limit_headers_only",
            "note": "Provider reports rate-limit windows, not account balance.",
        }
    return summary


def _validate_provider_secret(name: str, value: str | None) -> dict[str, Any] | None:
    provider = _provider_for_secret_name(name)
    if not provider or not value:
        return None

    validation: dict[str, Any] = {
        "provider": provider,
        "connection": {"ok": False, "status": "not_run"},
        "key_info": {"ok": False, "status": "not_run"},
        "limits": {},
        "notes": [
            "API keys usually do not expose ChatGPT/Claude/Gemini web subscription message quotas.",
            "AEIS records provider test result now and should track runtime spend internally during executions.",
        ],
    }
    try:
        from sylion.api.ai_providers_routes import (
            DEFAULT_MODELS,
            KeyInfoRequest,
            ProviderTestRequest,
            get_key_info,
            test_provider,
        )
        test_result = test_provider(
            provider,
            ProviderTestRequest(
                prompt="Odpowiedz dokladnie jednym slowem: OK",
                model=DEFAULT_MODELS.get(provider),
                max_tokens=8,
                api_key=value,
            ),
        )
        validation["connection"] = {
            "ok": True,
            "status": "connected",
            "model": test_result.get("model"),
            "latency_ms": test_result.get("latency_ms"),
        }
    except Exception as exc:  # noqa: BLE001
        detail = getattr(exc, "detail", None)
        validation["connection"] = {
            "ok": False,
            "status": "failed",
            "error": str(detail or exc)[:500],
        }

    try:
        from sylion.api.ai_providers_routes import KeyInfoRequest, get_key_info
        info = get_key_info(provider, KeyInfoRequest(api_key=value))
        validation["key_info"] = {
            "ok": True,
            "status": "introspected",
            "plan_inferred": info.get("plan_inferred"),
            "accessible_model_count": len(info.get("accessible_models") or []),
            "rate_limits": info.get("rate_limits") or {},
            "api_balance_usd": info.get("balance_usd"),
            "credit_limit_usd": info.get("credit_limit_usd"),
            "note": info.get("note"),
        }
        validation["limits"] = _provider_limit_summary(provider, info)
    except Exception as exc:  # noqa: BLE001
        detail = getattr(exc, "detail", None)
        validation["key_info"] = {
            "ok": False,
            "status": "failed",
            "error": str(detail or exc)[:500],
        }
        validation["limits"] = _provider_limit_summary(provider, {})

    return validation


def _backfill_provider_secrets_to_key_vault() -> list[dict]:
    """Backfill already-stored canonical secrets into KeyVault without exposing values."""
    sp = _get_provider()
    results: list[dict] = []
    for secret in sp.list_secrets():
        name = str(secret.get("name") or "")
        if not _provider_for_secret_name(name):
            continue
        record = sp.get_secret(name)
        results.append(_mirror_provider_secret_to_key_vault(name, record.get("value") if record else None) or {
            "secret": name,
            "mirrored": False,
            "reason": "not_provider_secret",
        })
    return results


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_provider = None


def _get_provider():
    global _provider
    if _provider is not None:
        return _provider
    from sylion.security.secret_provider import get_secret_provider
    _provider = get_secret_provider()
    return _provider


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class StoreSecretRequest(BaseModel):
    name: str
    value_encrypted: str
    scope: str = "default"
    metadata_json: dict | None = None


# W14 BE-8.5 (F-A3-1 P1): operator-friendly create-secret body so the
# /secrets dashboard does not have to pre-encrypt the value. Plaintext
# is encrypted at rest by the underlying provider.
class CreateSecretRequest(BaseModel):
    name: str
    value: str
    scope: str = "default"
    metadata: dict | None = None


class RotateSecretRequest(BaseModel):
    new_value: str


# ---------------------------------------------------------------------------
# Store / List
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def store_secret(body: StoreSecretRequest):
    """Store a new secret (or overwrite existing)."""
    sp = _get_provider()
    try:
        record = sp.store_secret(
            name=body.name,
            value_encrypted=body.value_encrypted,
            scope=body.scope,
            metadata_json=body.metadata_json,
        )
        mirror = _mirror_provider_secret_to_key_vault(body.name, body.value_encrypted, replace_active=True)
        if mirror:
            record["key_vault"] = mirror
            record["provider_validation"] = _validate_provider_secret(body.name, body.value_encrypted)
        return record
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create", status_code=201)
def create_secret(body: CreateSecretRequest):
    """W14 BE-8.5 (F-A3-1 P1) — operator-facing create-secret endpoint.

    Accepts a plaintext ``value`` (the provider encrypts at rest) and
    returns ``{secret_id, name, scope, version}`` *without* the value
    so the response is safe to render in the /secrets UI. This sits
    alongside the legacy ``POST /api/v1/secrets`` (which still uses
    the misleading ``value_encrypted`` field name) for backwards
    compatibility — old callers keep working unchanged.
    """
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="name must be non-empty")
    if not body.value:
        raise HTTPException(status_code=400, detail="value must be non-empty")
    sp = _get_provider()
    try:
        record = sp.store_secret(
            name=body.name.strip(),
            value_encrypted=body.value,
            scope=body.scope or "default",
            metadata_json=body.metadata,
        )
    except Exception as exc:                                    # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))

    # F-V10-007 fix: providers (`/api/v1/ai-providers/test/*`) read from
    # KeyVault, not from /secrets. When the operator stores a key under a
    # canonical provider env-name (e.g. ``OPENAI_API_KEY``), mirror it into
    # the KeyVault so the smoke test, model router, and Funding live
    # discovery can find it without a second copy/paste.
    mirror = _mirror_provider_secret_to_key_vault(body.name, body.value, replace_active=True)
    provider_validation = _validate_provider_secret(body.name, body.value) if mirror else None

    return {
        "secret_id": record.get("name"),
        "name": record.get("name"),
        "scope": record.get("scope"),
        "version": record.get("version"),
        "stored": True,
        "key_vault": mirror,
        "provider_validation": provider_validation,
    }


@router.get("/list")
def list_secrets(scope: str | None = None):
    """List secrets (without values), optionally filtered by scope."""
    sp = _get_provider()
    _backfill_provider_secrets_to_key_vault()
    return {"secrets": sp.list_secrets(scope=scope)}


@router.get("/stats")
def get_secret_stats():
    """Aggregate secret statistics."""
    sp = _get_provider()
    return sp.get_secret_stats()


# ---------------------------------------------------------------------------
# Single secret -- static paths before dynamic /{name} paths
# ---------------------------------------------------------------------------

@router.get("/{name}")
def get_secret(name: str, reveal: bool = False):
    """Retrieve a secret's metadata.

    By default the cleartext ``value`` and the (mis-named) ``value_encrypted``
    fields are stripped from the response so a casual GET cannot leak the key.
    Set ``?reveal=true`` to retrieve the raw value — that path should be used
    only by the secret-injection runtime and is audited at the provider layer.
    """
    sp = _get_provider()
    result = sp.get_secret(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    if not reveal and isinstance(result, dict):
        sanitized = dict(result)
        sanitized.pop("value", None)
        sanitized.pop("value_encrypted", None)
        return sanitized
    return result


@router.post("/{name}/rotate")
def rotate_secret(name: str, body: RotateSecretRequest):
    """Rotate a secret with a new value."""
    sp = _get_provider()
    try:
        result = sp.rotate_secret(name, new_value=body.new_value)
        if not result:
            raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}")
def delete_secret(name: str):
    """Delete a secret and its version history."""
    sp = _get_provider()
    ok = sp.delete_secret(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Secret '{name}' not found")
    return {"deleted": True, "name": name}


@router.get("/{name}/history")
def get_secret_history(name: str, limit: int = 20):
    """Return version history for a secret."""
    sp = _get_provider()
    return {"history": sp.get_secret_history(name, limit=limit)}


# ---------------------------------------------------------------------------
# Access logging
# ---------------------------------------------------------------------------

@router.get("/access/log")
def get_access_log(limit: int = 100):
    """Return recent access log entries."""
    sp = _get_provider()
    return {"logs": sp.get_access_log(limit=limit)}
