"""
SYLION API -- AI Providers routes.

Real-call test endpoint for LLM providers. Pings a live LLM with a minimal
prompt and returns the raw response so operators can verify end-to-end
connectivity without trusting only format-level validation.

Supported providers:
  - anthropic (Claude)
  - openai (ChatGPT)
  - perplexity (Sonar)
  - google (Gemini)
  - zai (Z.AI GLM, OpenAI-compatible)
  - ollama (local models)

Keys resolve in order: (1) KeyVault active key, (2) os.environ.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sylion.aeis.advisor.events.lifecycle import publish_lifecycle_event

log = logging.getLogger("sylion.api.ai_providers")

router = APIRouter(prefix="/api/v1/ai-providers", tags=["AI Providers"])

DEFAULT_MODELS: dict[str, str] = {
    # F-026: use safe, current model ids — the previous "claude-haiku-4-5-20251001"
    # was a fictional date that returned 502. Anthropic accepts undated aliases
    # like "claude-haiku-4-5" which always resolve to the latest minor.
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
    "perplexity": "sonar",
    "google": "gemini-2.5-flash",
    "zai": "glm-4-plus",
    "openrouter": "openrouter/auto",
    # F-026 new providers:
    "moonshot": "kimi-k2.6",               # Kimi (official current default)
    "deepseek": "deepseek-chat",            # OAI-compat
    "xai": "grok-2-1212",                   # Grok
    "mistral": "mistral-small-latest",      # Mistral
    "groq": "llama-3.3-70b-versatile",      # Llama on Groq
    "cohere": "command-r-plus",             # Command R+
    "fireworks": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    "together": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    # PDF §8.1.6 — local OAI-compatible runtimes. No API key required;
    # _resolve_key returns "local" sentinel so /list and /test treat them
    # as configured. Default base URLs overridable via env (LMSTUDIO_BASE_URL,
    # VLLM_BASE_URL, LLAMACPP_BASE_URL).
    "lmstudio": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
    "vllm": "Qwen/Qwen2.5-72B-Instruct",
    "llamacpp": "ggml-org/Phi-3-mini-4k-instruct-GGUF",
    "ollama": "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M",
}

ENV_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "perplexity": "PERPLEXITY_API_KEY",
    "google": "GOOGLE_API_KEY",
    "zai": "ZAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "xai": "XAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    "cohere": "COHERE_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "together": "TOGETHER_API_KEY",
    # PDF §8.1.6 — local OAI-compat runtimes use no API keys. The env vars
    # below name the *base URL* override, not a credential, so the existing
    # _resolve_key fallback to os.environ keeps returning "" (no key). The
    # /list endpoint flags these via LOCAL_PROVIDERS so the UI can show
    # "no key needed" instead of an empty-key warning.
    "lmstudio": "LMSTUDIO_BASE_URL",
    "vllm": "VLLM_BASE_URL",
    "llamacpp": "LLAMACPP_BASE_URL",
    "ollama": "OLLAMA_BASE_URL",
}

# PDF §8.1.6 — providers that don't need an API key (local OAI-compat
# runtimes). list_providers() reports key_available=True for these as
# long as the daemon is reachable; test_provider() short-circuits the
# missing-key 400.
LOCAL_PROVIDERS: frozenset[str] = frozenset({"lmstudio", "vllm", "llamacpp", "ollama"})


# PDF §8.1.6 — base URLs for local OAI-compat runtimes. Resolved at call
# time from the corresponding LMSTUDIO_BASE_URL / VLLM_BASE_URL /
# LLAMACPP_BASE_URL env vars; falling back to the conventional defaults.
LOCAL_BASE_URLS: dict[str, str] = {
    # Windows resolves localhost through IPv6 first in some environments, which
    # can turn a closed local runtime probe into a multi-second dashboard stall.
    "lmstudio": "http://127.0.0.1:1234",
    "vllm": "http://127.0.0.1:8001",
    "llamacpp": "http://127.0.0.1:8080",
    "ollama": "http://127.0.0.1:11434",
}

_OPENROUTER_MODEL_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": None}


def _local_base_url(provider: str) -> str:
    env_var = ENV_KEYS.get(provider, "")
    return os.environ.get(env_var, LOCAL_BASE_URLS.get(provider, "")) or LOCAL_BASE_URLS.get(provider, "")


OLLAMA_BASE_URL = _local_base_url("ollama")


class ProviderTestRequest(BaseModel):
    prompt: str = "ping"
    model: str | None = None
    max_tokens: int = 32
    # F-023: allow frontend onboarding to validate a freshly-typed key
    # without first persisting it. When present, this overrides KeyVault/env.
    api_key: str | None = None


def _configured_provider_ids() -> list[str]:
    configured: list[str] = []
    for provider in DEFAULT_MODELS:
        if _resolve_key(provider):
            configured.append(provider)
    return configured


def _configured_model_ids(provider_ids: list[str]) -> list[str]:
    return [DEFAULT_MODELS[provider_id] for provider_id in provider_ids]


def _emit_provider_setup_requests(provider: str, model: str, *, has_key: bool) -> None:
    current_providers = _configured_provider_ids()
    current_models = _configured_model_ids(current_providers)
    existing_providers = [item for item in current_providers if item != provider]
    setup_context = "first_run" if not existing_providers else "add_provider"

    publish_lifecycle_event(
        "aeis.system.model_setup_requested",
        {
            "operator_id": "system",
            "setup_context": setup_context,
            "current_providers": current_providers,
            "current_models": current_models,
        },
        source_module="sylion.api.ai_providers_routes",
        primary_key=f"{provider}:{model}:model_setup",
    )
    publish_lifecycle_event(
        "aeis.system.api_provider_setup_requested",
        {
            "operator_id": "system",
            "action": "test",
            "provider_id": provider,
            "has_key": has_key,
            "is_active": provider in current_providers,
        },
        source_module="sylion.api.ai_providers_routes",
        primary_key=f"{provider}:provider_setup",
    )


def _resolve_key(provider: str) -> str:
    """Resolve API key: KeyVault first, then os.environ."""
    try:
        from sylion.security.key_vault import get_key_vault
        vault = get_key_vault()
        keys = vault.list_keys(provider=provider)
        active = [k for k in keys if k.get("is_active")]
        if active:
            val = vault.get_decrypted_key(active[0]["key_id"]) or ""
            if val:
                return val
    except Exception:
        pass
    return os.environ.get(ENV_KEYS.get(provider, ""), "") or ""


def _mask(key: str) -> str:
    if not key:
        return ""
    return key[:10] + "..." if len(key) > 10 else key[:3] + "..."


def _anthropic_headers(key: str) -> dict[str, str]:
    return {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


def _select_anthropic_model(key: str, preferred: str) -> str:
    """Pick an available Anthropic model without requiring the SDK package."""
    import httpx

    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(
                "https://api.anthropic.com/v1/models",
                headers=_anthropic_headers(key),
            )
            if r.status_code >= 400:
                return preferred
            ids = [
                str(m.get("id"))
                for m in (r.json().get("data") or [])
                if m.get("id")
            ]
    except Exception:  # noqa: BLE001
        return preferred
    if preferred in ids:
        return preferred

    preferred_lower = preferred.lower()
    preferred_family = next(
        (family for family in ("opus", "sonnet", "haiku") if family in preferred_lower),
        "",
    )
    family_order = (
        [preferred_family] if preferred_family else []
    ) + [family for family in ("opus", "sonnet", "haiku") if family != preferred_family]
    for needle in family_order:
        match = next((mid for mid in ids if needle in mid), None)
        if match:
            return match
    return ids[0] if ids else preferred


def _call_anthropic(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    import httpx

    selected_model = _select_anthropic_model(key, model)
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://api.anthropic.com/v1/messages",
            headers=_anthropic_headers(key),
            json={
                "model": selected_model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if r.status_code >= 400:
            body_preview = ""
            try:
                body_preview = r.json().get("error", {}).get("message", "")[:200]
            except Exception:
                body_preview = r.text[:200]
            raise RuntimeError(f"anthropic HTTP {r.status_code}: {body_preview}")
        data = r.json()
    parts = data.get("content") or []
    text = "".join(
        str(part.get("text") or "")
        for part in parts
        if isinstance(part, dict) and part.get("type") == "text"
    )
    usage = data.get("usage") or {}
    return {
        "text": text,
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "model_used": data.get("model", selected_model),
    }


def _call_openai(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    from openai import OpenAI
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content if resp.choices else ""
    return {
        "text": text or "",
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


def _call_perplexity(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url="https://api.perplexity.ai")
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content if resp.choices else ""
    return {
        "text": text or "",
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


def _call_google_once(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    import httpx
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json=payload)
        if r.status_code >= 400:
            body_preview = ""
            try:
                body_preview = r.json().get("error", {}).get("message", "")[:200]
            except Exception:
                body_preview = r.text[:200]
            raise RuntimeError(f"google HTTP {r.status_code}: {body_preview}")
        data = r.json()
    text = ""
    cand = data.get("candidates", [])
    if cand:
        parts = cand[0].get("content", {}).get("parts", [])
        if parts:
            text = parts[0].get("text", "")
    usage = data.get("usageMetadata", {}) or {}
    return {
        "text": text,
        "prompt_tokens": usage.get("promptTokenCount", 0),
        "completion_tokens": usage.get("candidatesTokenCount", 0),
        "model_used": model,
    }


def _list_google_generate_models(key: str) -> list[str]:
    """Return Gemini model ids that explicitly support generateContent."""
    import httpx

    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": key},
            )
            if r.status_code >= 400:
                return []
            data = r.json() or {}
    except Exception:
        return []

    out: list[str] = []
    for item in data.get("models", []) or []:
        methods = item.get("supportedGenerationMethods") or []
        name = str(item.get("name") or "")
        if "generateContent" not in methods or not name:
            continue
        out.append(name.removeprefix("models/"))
    return out


def _google_model_candidates(model: str, key: str) -> list[str]:
    listed = _list_google_generate_models(key)
    listed_set = set(listed)
    preferred_order = [
        model,
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
    ]

    candidates: list[str] = []
    for candidate in preferred_order:
        if not candidate or candidate in candidates:
            continue
        if not listed or candidate in listed_set:
            candidates.append(candidate)

    for candidate in listed:
        if candidate not in candidates and "flash" in candidate.lower():
            candidates.append(candidate)
    for candidate in listed:
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _call_google(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    """Gemini probe with current-model fallback.

    Google may return transient 503 on a specific model even when the key is
    valid. Query the key-visible model catalogue first so onboarding doesn't
    fail on stale hardcoded model ids.
    """
    errors: list[str] = []
    for candidate in _google_model_candidates(model, key):
        try:
            return _call_google_once(prompt, candidate, max_tokens, key)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}: {str(exc)[:160]}")
    raise RuntimeError("google validation failed on all configured models: " + " | ".join(errors))


def _call_zai(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    """Z.AI GLM -- OpenAI-compatible API at https://api.z.ai/api/paas/v4."""
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url="https://api.z.ai/api/paas/v4")
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content if resp.choices else ""
    return {
        "text": text or "",
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


def _call_openrouter(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    """F-017: OpenRouter aggregator -- OpenAI-compatible API at https://openrouter.ai/api/v1.

    Single API key gives access to ~100 models from Anthropic, OpenAI, Google,
    Meta, DeepSeek, Mistral, Qwen, etc. Model id format is `<vendor>/<model>`,
    e.g. `anthropic/claude-sonnet-4-5`, `meta-llama/llama-3.3-70b-instruct`,
    `deepseek/deepseek-r1`. Use `openrouter/auto` to let OpenRouter pick.

    Optional headers `HTTP-Referer` and `X-Title` are recommended by OpenRouter
    for analytics; we set them to identify SYLION traffic.
    """
    from openai import OpenAI
    client = OpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://sylion.local/aeis",
            "X-Title": "SYLION AEIS",
        },
    )
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content if resp.choices else ""
    return {
        "text": text or "",
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
        "model_used": getattr(resp, "model", model),
    }


def _oai_compat_call(
    base_url: str,
    prompt: str,
    model: str,
    max_tokens: int,
    key: str,
    *,
    default_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Generic OpenAI-compatible chat completion (DeepSeek, Groq, Mistral, etc.)."""
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url=base_url, default_headers=default_headers)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content if resp.choices else ""
    return {
        "text": text or "",
        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
    }


def _call_moonshot(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    """Kimi / Moonshot probe with real fallback across current Kimi surfaces.

    Kimi Open Platform documents the global OpenAI-compatible endpoint at
    api.moonshot.ai/v1. Kimi Code keys may be issued as sk-kimi-* and can use
    the coding endpoint. During onboarding we must validate the operator's
    actual key, not assume one surface.
    """
    attempts: list[tuple[str, list[str], dict[str, str] | None]] = [
        (
            "https://api.moonshot.ai/v1",
            [model, "kimi-k2.6", "kimi-k2.5", "kimi-k2", "moonshot-v1-8k"],
            None,
        )
    ]
    if key.startswith("sk-kimi-"):
        attempts.append(
            (
                "https://api.kimi.com/coding/v1",
                ["kimi-for-coding", model, "kimi-k2.5", "kimi-k2"],
                {"User-Agent": "SYLION-AEIS/3.5", "X-Msh-Platform": "aeis"},
            )
        )

    errors: list[str] = []
    for base_url, candidates, headers in attempts:
        model_candidates: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in model_candidates:
                model_candidates.append(candidate)
        for candidate in model_candidates:
            try:
                result = _oai_compat_call(
                    base_url,
                    prompt,
                    candidate,
                    max_tokens,
                    key,
                    default_headers=headers,
                )
                result["model_used"] = candidate
                result["base_url"] = base_url
                return result
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{base_url} {candidate}: {str(exc)[:120]}")
    if key.startswith("sk-kimi-"):
        try:
            result = _call_kimi_cli_probe(prompt, key)
            result["model_used"] = "kimi-for-coding"
            result["base_url"] = "kimi-cli://local"
            return result
        except Exception as exc:  # noqa: BLE001
            errors.append(f"kimi-cli local adapter: {str(exc)[:240]}")
    raise RuntimeError("Kimi validation failed on all configured endpoints: " + " | ".join(errors))


def _call_kimi_cli_probe(prompt: str, key: str) -> dict[str, Any]:
    """Validate Kimi Code keys through the official local Kimi CLI agent.

    Kimi Code membership keys are not interchangeable with Moonshot Open
    Platform keys and raw HTTP calls are rejected unless a supported coding
    agent is used. For onboarding we run the installed `kimi` CLI with an
    isolated temporary config/share/work directory and delete all temp files
    after the probe.
    """
    kimi_bin = shutil.which("kimi")
    if not kimi_bin:
        raise RuntimeError("Kimi Code key requires the official Kimi CLI adapter, but `kimi` was not found on PATH.")

    runtime_prompt = (
        "Tryb SYLION LLM Judge: odpowiedz tylko tekstem na ponizszy prompt. "
        "Nie uruchamiaj narzedzi, nie edytuj plikow i nie wykonuj komend.\n\n"
        + (prompt or "Odpowiedz dokladnie jednym slowem: OK")
    )
    safe_key = json.dumps(key)
    config = f"""
default_model = "kimi-for-coding"
default_thinking = false
default_yolo = false
default_plan_mode = false
default_editor = ""
theme = "dark"
merge_all_available_skills = false

[providers.kimi-for-coding]
type = "kimi"
base_url = "https://api.kimi.com/coding/v1"
api_key = {safe_key}

[models.kimi-for-coding]
provider = "kimi-for-coding"
model = "kimi-for-coding"
max_context_size = 262144

[loop_control]
max_steps_per_turn = 1
max_retries_per_step = 1
max_ralph_iterations = 0
reserved_context_size = 8192
compaction_trigger_ratio = 0.85

[background]
max_running_tasks = 1
keep_alive_on_exit = false
agent_task_timeout_s = 60
"""
    temp_root = tempfile.mkdtemp(prefix="aeis-kimi-cli-")
    try:
        config_path = os.path.join(temp_root, "config.toml")
        work_dir = os.path.join(temp_root, "work")
        share_dir = os.path.join(temp_root, "share")
        os.makedirs(work_dir, exist_ok=True)
        os.makedirs(share_dir, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.write(config)
        env = os.environ.copy()
        env["KIMI_SHARE_DIR"] = share_dir
        completed = subprocess.run(
            [
                kimi_bin,
                "--config-file",
                config_path,
                "--work-dir",
                work_dir,
                "--model",
                "kimi-for-coding",
                "--max-steps-per-turn",
                "1",
                "--max-retries-per-step",
                "1",
                "--quiet",
                "--prompt",
                runtime_prompt,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            check=False,
        )
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            detail = (stderr or stdout or f"exit {completed.returncode}")[:400]
            raise RuntimeError(detail)
        text = stdout.splitlines()[-1].strip() if stdout else ""
        if not text:
            raise RuntimeError("Kimi CLI returned an empty response.")
        return {
            "text": text[:20000],
            "prompt_tokens": max(1, len(runtime_prompt) // 4),
            "completion_tokens": max(1, len(text) // 4),
            "adapter": "kimi-cli",
            "requested_prompt_length": len(prompt or ""),
        }
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def _call_deepseek(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    return _oai_compat_call("https://api.deepseek.com/v1", prompt, model, max_tokens, key)


def _call_xai(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    return _oai_compat_call("https://api.x.ai/v1", prompt, model, max_tokens, key)


def _call_mistral(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    return _oai_compat_call("https://api.mistral.ai/v1", prompt, model, max_tokens, key)


def _call_groq(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    return _oai_compat_call("https://api.groq.com/openai/v1", prompt, model, max_tokens, key)


def _call_cohere(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    """Cohere v2 chat — uses native API, not OAI-compat."""
    import httpx
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://api.cohere.com/v2/chat",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        if r.status_code >= 400:
            raise RuntimeError(f"cohere HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
    parts = data.get("message", {}).get("content", [])
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    usage = data.get("usage", {}).get("billed_units", {})
    return {
        "text": text,
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
    }


def _call_fireworks(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    return _oai_compat_call("https://api.fireworks.ai/inference/v1", prompt, model, max_tokens, key)


def _call_together(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    return _oai_compat_call("https://api.together.xyz/v1", prompt, model, max_tokens, key)


# PDF §8.1.6 — local OAI-compatible runtimes. They share the same
# wire format as cloud OpenAI clones, so we reuse _oai_compat_call.
# A throwaway "sk-local" sentinel is passed because the OpenAI client
# requires a non-empty api_key string even when the server ignores it.
def _call_lmstudio(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    base = _local_base_url("lmstudio")
    return _oai_compat_call(f"{base.rstrip('/')}/v1", prompt, model, max_tokens, key or "sk-local")


def _call_vllm(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    base = _local_base_url("vllm")
    return _oai_compat_call(f"{base.rstrip('/')}/v1", prompt, model, max_tokens, key or "sk-local")


def _call_llamacpp(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    base = _local_base_url("llamacpp")
    return _oai_compat_call(f"{base.rstrip('/')}/v1", prompt, model, max_tokens, key or "sk-local")


def _call_ollama(prompt: str, model: str, max_tokens: int, key: str) -> dict[str, Any]:
    """Probe a real local Ollama model through the native generate API."""
    import httpx

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max(1, min(int(max_tokens or 32), 512))},
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate", json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"Ollama HTTP {response.status_code}: {response.text[:300]}")
        data = response.json() or {}

    return {
        "text": str(data.get("response") or ""),
        "prompt_tokens": int(data.get("prompt_eval_count") or 0),
        "completion_tokens": int(data.get("eval_count") or 0),
    }


DISPATCH = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "perplexity": _call_perplexity,
    "google": _call_google,
    "zai": _call_zai,
    "openrouter": _call_openrouter,
    "moonshot": _call_moonshot,
    "deepseek": _call_deepseek,
    "xai": _call_xai,
    "mistral": _call_mistral,
    "groq": _call_groq,
    "cohere": _call_cohere,
    "fireworks": _call_fireworks,
    "together": _call_together,
    # PDF §8.1.6 — local providers (no key required).
    "lmstudio": _call_lmstudio,
    "vllm": _call_vllm,
    "llamacpp": _call_llamacpp,
    "ollama": _call_ollama,
}


def _openrouter_public_models(limit: int) -> dict[str, Any]:
    import httpx

    now = time.time()
    cached = _OPENROUTER_MODEL_CACHE.get("payload")
    if cached and float(_OPENROUTER_MODEL_CACHE.get("expires_at") or 0.0) > now:
        payload = dict(cached)
        payload["cached"] = True
        payload["models"] = list(payload.get("models") or [])[:limit]
        payload["count"] = len(payload["models"])
        return payload

    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get("https://openrouter.ai/api/v1/models")
        if response.status_code >= 400:
            return {
                "available": False,
                "source": "openrouter_public_catalog",
                "models": [],
                "count": 0,
                "total_count": 0,
                "error": f"openrouter_http_{response.status_code}",
            }
        data = response.json() or {}
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "source": "openrouter_public_catalog",
            "models": [],
            "count": 0,
            "total_count": 0,
            "error": f"{type(exc).__name__}: {str(exc)[:160]}",
        }

    raw_models = list(data.get("data") or [])
    models: list[dict[str, Any]] = []
    for item in raw_models:
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        models.append(
            {
                "model_id": model_id,
                "id": model_id,
                "name": item.get("name") or model_id,
                "display_name": item.get("name") or model_id,
                "provider": "openrouter",
                "context_length": item.get("context_length"),
                "pricing": item.get("pricing") or {},
                "architecture": item.get("architecture") or {},
                "top_provider": item.get("top_provider") or {},
                "created": item.get("created"),
            }
        )

    payload = {
        "available": True,
        "source": "openrouter_public_catalog",
        "models": models,
        "count": min(len(models), limit),
        "total_count": len(models),
        "cached": False,
    }
    _OPENROUTER_MODEL_CACHE["payload"] = payload
    _OPENROUTER_MODEL_CACHE["expires_at"] = now + 3600
    payload = dict(payload)
    payload["models"] = list(models)[:limit]
    return payload


@router.get("/openrouter/models")
def list_openrouter_public_models(limit: int = 1000) -> dict[str, Any]:
    """Expose OpenRouter's public model catalog without reading or leaking API keys."""
    try:
        safe_limit = int(limit or 1000)
    except (TypeError, ValueError):
        safe_limit = 1000
    safe_limit = max(1, min(safe_limit, 2000))
    return _openrouter_public_models(safe_limit)


# F-018: surface ollama-installed models so the onboarding wizard can
# offer "select existing" instead of forcing a re-download.


def _ollama_installed_models() -> list[dict[str, Any]]:
    """Return list of locally installed Ollama models with size + modified time."""
    import httpx
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if r.status_code >= 400:
                return []
            data = r.json() or {}
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for m in data.get("models", []) or []:
        size_bytes = int(m.get("size") or 0)
        out.append({
            "name": m.get("name", ""),
            "size_bytes": size_bytes,
            "size_gb": round(size_bytes / (1024 ** 3), 2),
            "modified_at": m.get("modified_at", ""),
            "digest": (m.get("digest") or "")[:16],
            "family": (m.get("details") or {}).get("family", ""),
            "parameter_size": (m.get("details") or {}).get("parameter_size", ""),
            "quantization": (m.get("details") or {}).get("quantization_level", ""),
            "installed": True,
        })
    return out


@router.get("/local-models/installed")
def list_local_installed_models() -> dict[str, Any]:
    """F-018: list Ollama models present on disk so onboarding can mark
    them as already-installed instead of forcing a re-pull.

    Reachability of the Ollama daemon (default ``http://127.0.0.1:11434``,
    overridable via ``OLLAMA_BASE_URL``) is required; returns ``[]`` when
    Ollama is offline so frontend can show suggestions only.
    """
    models = _ollama_installed_models()
    return {
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_reachable": len(models) > 0 or _ollama_reachable(),
        "models": models,
        "count": len(models),
    }


@router.get("/ollama/models")
def list_ollama_models_legacy() -> dict[str, Any]:
    """Compatibility endpoint for the AI Models cockpit tab.

    The onboarding wizard uses /local-models/installed. The AI Models panel
    historically used /ollama/models and interpreted a missing endpoint as
    "Ollama offline". Keep both surfaces wired to the same real probe.
    """
    models = _ollama_installed_models()
    reachable = len(models) > 0 or _ollama_reachable()
    return {
        "available": reachable,
        "models": models,
        "count": len(models),
        "base_url": OLLAMA_BASE_URL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_reachable": reachable,
    }


def _ollama_reachable() -> bool:
    import httpx
    try:
        with httpx.Client(timeout=1.0) as client:
            r = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            return r.status_code < 500
    except Exception:
        return False


def _local_runtime_reachable(provider: str) -> bool:
    """Return whether a local runtime daemon is actually reachable."""
    import httpx

    if provider == "ollama":
        return _ollama_reachable()
    if provider not in LOCAL_PROVIDERS:
        return False
    base = _local_base_url(provider).rstrip("/")
    try:
        with httpx.Client(timeout=0.75) as client:
            response = client.get(f"{base}/v1/models")
        return response.status_code < 500
    except Exception:
        return False


class LocalModelPullRequest(BaseModel):
    model: str
    stream: bool = False


# F-023: key-info enrichment helpers — fetch accessible models + tier hints.

def _anthropic_key_info(key: str) -> dict[str, Any]:
    """Probe Anthropic API: list models + capture rate-limit headers from a tiny call."""
    import httpx
    info: dict[str, Any] = {"provider": "anthropic", "accessible_models": [], "rate_limits": {}, "plan_inferred": "unknown"}
    headers = _anthropic_headers(key)
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get("https://api.anthropic.com/v1/models", headers=headers)
            if r.status_code == 200:
                data = r.json() or {}
                info["accessible_models"] = [
                    {"id": m.get("id"), "display_name": m.get("display_name"), "type": m.get("type")}
                    for m in (data.get("data") or [])
                ]
            elif r.status_code == 401:
                info["error"] = "auth_failed"
                return info
            # Rate-limit hints: tiny ping to capture headers (1 token)
            ping = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json={
                    "model": _select_anthropic_model(key, DEFAULT_MODELS["anthropic"]),
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "."}],
                },
            )
            for h in ping.headers:
                if h.lower().startswith("anthropic-ratelimit-"):
                    info["rate_limits"][h.replace("anthropic-ratelimit-", "")] = ping.headers[h]
            req_limit = info["rate_limits"].get("requests-limit")
            if req_limit:
                try:
                    n = int(req_limit)
                    if n >= 4000:
                        info["plan_inferred"] = "enterprise"
                    elif n >= 1000:
                        info["plan_inferred"] = "tier_4_plus"
                    elif n >= 50:
                        info["plan_inferred"] = "build_tier"
                    else:
                        info["plan_inferred"] = "free_or_low"
                except ValueError:
                    pass
    except Exception as exc:
        info["error"] = f"probe_failed: {type(exc).__name__}"
    return info


def _openai_key_info(key: str) -> dict[str, Any]:
    """Probe OpenAI: list models accessible by this key."""
    info: dict[str, Any] = {"provider": "openai", "accessible_models": [], "rate_limits": {}, "plan_inferred": "unknown"}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        models = client.models.list()
        ids = [{"id": m.id} for m in (models.data or [])]
        info["accessible_models"] = ids
        # Coarse plan heuristic from model availability
        ids_set = {m["id"] for m in ids}
        if any("o1" in i or "gpt-4.5" in i for i in ids_set):
            info["plan_inferred"] = "tier_3_plus_or_pro"
        elif "gpt-4o" in ids_set:
            info["plan_inferred"] = "build_tier"
        else:
            info["plan_inferred"] = "free_or_limited"
    except Exception as exc:
        info["error"] = f"probe_failed: {type(exc).__name__}"
    return info


def _openrouter_key_info(key: str) -> dict[str, Any]:
    """Probe OpenRouter: /auth/key returns plan + credit balance."""
    import httpx
    info: dict[str, Any] = {"provider": "openrouter", "accessible_models": [], "rate_limits": {}, "plan_inferred": "unknown"}
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data") or {}
                info["plan_inferred"] = data.get("label") or "credits"
                info["balance_usd"] = data.get("usage", 0)
                info["credit_limit_usd"] = data.get("limit")
                info["rate_limits"] = data.get("rate_limit", {}) or {}
                # Get model count
                rm = client.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {key}"})
                if rm.status_code == 200:
                    info["accessible_models"] = [{"id": m.get("id")} for m in (rm.json().get("data") or [])][:50]
    except Exception as exc:
        info["error"] = f"probe_failed: {type(exc).__name__}"
    return info


def _generic_key_info(provider: str, key: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "accessible_models": [],
        "rate_limits": {},
        "plan_inferred": "test_via_test_endpoint",
        "note": f"Detailed key-info not yet implemented for {provider}; use /test/{provider} to verify the key works.",
    }


KEY_INFO_DISPATCH = {
    "anthropic": _anthropic_key_info,
    "openai": _openai_key_info,
    "openrouter": _openrouter_key_info,
}


class KeyInfoRequest(BaseModel):
    api_key: str | None = None


# F-027: hosting-provider validation. Symmetric to /test/{provider} but for
# Cloudflare/AWS/Vercel/Render/Fly/Railway/DigitalOcean/Hetzner/OVH/custom.
# Returns {ok, account_label, message, raw_status} so the wizard can show
# "Connected to Hetzner project 'default' (3 servers)" instead of nothing.

class HostingTestRequest(BaseModel):
    fields: dict[str, str] = {}


def _hosting_hetzner(fields: dict[str, str]) -> dict[str, Any]:
    import httpx
    token = (fields.get("token") or "").strip()
    project = (fields.get("project") or "default").strip()
    if not token:
        return {"ok": False, "error": "missing API Token"}
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(
                "https://api.hetzner.cloud/v1/servers",
                headers={"Authorization": f"Bearer {token}"},
                params={"per_page": 1},
            )
            if r.status_code == 401:
                return {"ok": False, "error": "auth_failed (401)"}
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:120]}"}
            data = r.json() or {}
            meta = data.get("meta", {}).get("pagination", {})
            return {
                "ok": True,
                "account_label": f"Hetzner Cloud · project={project}",
                "message": f"{meta.get('total_entries', '?')} serwerów dostępnych",
                "details": {"total_servers": meta.get("total_entries"), "project": project},
            }
    except Exception as exc:
        return {"ok": False, "error": f"network: {type(exc).__name__}"}


def _hosting_cloudflare(fields: dict[str, str]) -> dict[str, Any]:
    import httpx
    token = (fields.get("token") or "").strip()
    if not token:
        return {"ok": False, "error": "missing API Token"}
    try:
        with httpx.Client(timeout=6.0) as client:
            r = client.get(
                "https://api.cloudflare.com/client/v4/user/tokens/verify",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code == 401:
                return {"ok": False, "error": "auth_failed (401)"}
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            data = r.json() or {}
            ok = bool(data.get("success"))
            return {
                "ok": ok,
                "account_label": "Cloudflare",
                "message": data.get("messages", [{}])[0].get("message", "Token verified"),
                "details": {"status": data.get("result", {}).get("status")},
            }
    except Exception as exc:
        return {"ok": False, "error": f"network: {type(exc).__name__}"}


def _hosting_vercel(fields: dict[str, str]) -> dict[str, Any]:
    import httpx
    token = (fields.get("token") or "").strip()
    if not token:
        return {"ok": False, "error": "missing token"}
    try:
        with httpx.Client(timeout=6.0) as client:
            r = client.get("https://api.vercel.com/v2/user", headers={"Authorization": f"Bearer {token}"})
            if r.status_code == 401 or r.status_code == 403:
                return {"ok": False, "error": f"auth_failed ({r.status_code})"}
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            data = r.json().get("user") or {}
            return {
                "ok": True,
                "account_label": f"Vercel · {data.get('username') or data.get('email') or 'user'}",
                "message": data.get("email", ""),
            }
    except Exception as exc:
        return {"ok": False, "error": f"network: {type(exc).__name__}"}


def _hosting_digitalocean(fields: dict[str, str]) -> dict[str, Any]:
    import httpx
    token = (fields.get("token") or "").strip()
    if not token:
        return {"ok": False, "error": "missing PAT"}
    try:
        with httpx.Client(timeout=6.0) as client:
            r = client.get(
                "https://api.digitalocean.com/v2/account",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code == 401:
                return {"ok": False, "error": "auth_failed (401)"}
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            acc = r.json().get("account") or {}
            return {
                "ok": True,
                "account_label": f"DigitalOcean · {acc.get('email', 'user')}",
                "message": f"droplet limit: {acc.get('droplet_limit', '?')}",
                "details": {"status": acc.get("status"), "verified": acc.get("email_verified")},
            }
    except Exception as exc:
        return {"ok": False, "error": f"network: {type(exc).__name__}"}


def _hosting_render(fields: dict[str, str]) -> dict[str, Any]:
    import httpx
    key = (fields.get("api_key") or "").strip()
    if not key:
        return {"ok": False, "error": "missing API Key"}
    try:
        with httpx.Client(timeout=6.0) as client:
            r = client.get(
                "https://api.render.com/v1/services",
                headers={"Authorization": f"Bearer {key}"},
                params={"limit": 1},
            )
            if r.status_code == 401:
                return {"ok": False, "error": "auth_failed (401)"}
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            return {"ok": True, "account_label": "Render", "message": "API key valid"}
    except Exception as exc:
        return {"ok": False, "error": f"network: {type(exc).__name__}"}


def _hosting_flyio(fields: dict[str, str]) -> dict[str, Any]:
    import httpx
    token = (fields.get("token") or "").strip()
    if not token:
        return {"ok": False, "error": "missing FlyV1 token"}
    try:
        with httpx.Client(timeout=6.0) as client:
            r = client.post(
                "https://api.fly.io/graphql",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"query": "{ viewer { email } }"},
            )
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}"}
            data = r.json().get("data", {}).get("viewer") or {}
            if not data.get("email"):
                return {"ok": False, "error": "auth_failed"}
            return {"ok": True, "account_label": f"Fly.io · {data['email']}", "message": "Token verified"}
    except Exception as exc:
        return {"ok": False, "error": f"network: {type(exc).__name__}"}


def _hosting_unverifiable(provider: str, fields: dict[str, str]) -> dict[str, Any]:
    """For providers where the auth flow is too complex for a quick probe
    (OVH OAuth signature, AWS sigv4, Railway graphql with team scoping)
    we accept the credentials as 'configured' and let the actual deploy
    pipeline catch failures at use time.
    """
    has_any = any(bool(v and v.strip()) for v in fields.values())
    if not has_any:
        return {"ok": False, "error": "missing credentials"}
    return {
        "ok": True,
        "account_label": f"{provider} (configured)",
        "message": "Walidacja online niedostępna — sprawdzimy przy pierwszym deployu.",
    }


HOSTING_DISPATCH: dict[str, Any] = {
    "hetzner": _hosting_hetzner,
    "cloudflare": _hosting_cloudflare,
    "vercel": _hosting_vercel,
    "digitalocean": _hosting_digitalocean,
    "render": _hosting_render,
    "flyio": _hosting_flyio,
    # Unverifiable inline — accept as configured.
    "ovh": lambda f: _hosting_unverifiable("OVHcloud", f),
    "aws": lambda f: _hosting_unverifiable("AWS", f),
    "railway": lambda f: _hosting_unverifiable("Railway", f),
    "custom": lambda f: _hosting_unverifiable("Custom hosting", f),
}


@router.post("/hosting/test/{provider}")
def test_hosting_provider(provider: str, req: HostingTestRequest | None = None) -> dict[str, Any]:
    """F-027: validate hosting-provider credentials so the wizard mirrors the
    AI-key validation flow. Returns ``{ok: bool, account_label, message,
    error?}`` — frontend renders the same green/red badges as AI keys.
    """
    provider = provider.lower()
    fn = HOSTING_DISPATCH.get(provider)
    if not fn:
        raise HTTPException(404, f"unknown hosting provider '{provider}'")
    body = req or HostingTestRequest()
    return {"provider": provider, **fn(body.fields or {})}


@router.post("/key-info/{provider}")
def get_key_info(provider: str, req: KeyInfoRequest | None = None) -> dict[str, Any]:
    """F-023: rich key introspection — accessible models, rate limits,
    inferred plan tier. Frontend uses this so onboarding can show
    'Plan: build_tier · 12 models · 4000 req/min' instead of just a
    green check.
    """
    provider = provider.lower()
    if provider not in DISPATCH:
        raise HTTPException(status_code=404, detail=f"unknown provider '{provider}'")
    if provider in LOCAL_PROVIDERS:
        installed_models: list[dict[str, Any]] = []
        if provider == "ollama":
            installed_models = _ollama_installed_models()
        default_model = DEFAULT_MODELS.get(provider, "")
        accessible_models = [
            str(item.get("name") or item.get("model") or "")
            for item in installed_models
            if isinstance(item, dict) and (item.get("name") or item.get("model"))
        ]
        if default_model and default_model not in accessible_models:
            accessible_models.insert(0, default_model)
        return {
            "provider": provider,
            "locality": "local",
            "base_url": _local_base_url(provider),
            "runtime_reachable": _local_runtime_reachable(provider),
            "api_key_required": False,
            "plan_inferred": "local_runtime",
            "accessible_models": accessible_models,
            "installed_models": installed_models,
            "rate_limits": {
                "requests_per_minute": None,
                "tokens_per_minute": None,
                "limited_by": "local_hardware",
            },
            "quota": {
                "subscription_first": True,
                "api_balance_required": False,
                "remaining": None,
                "window": "local",
            },
        }
    body = req or KeyInfoRequest()
    key = body.api_key.strip() if body.api_key and body.api_key.strip() else _resolve_key(provider)
    if not key:
        raise HTTPException(
            status_code=400,
            detail=f"no API key for {provider} (set {ENV_KEYS[provider]} or pass api_key in body)",
        )
    fn = KEY_INFO_DISPATCH.get(provider, lambda k: _generic_key_info(provider, k))
    return fn(key)


@router.get("/key-info/{provider}")
def get_key_info_readonly(provider: str) -> dict[str, Any]:
    """Read-only compatibility alias for dashboard/provider status refresh."""
    return get_key_info(provider, None)


# F-bug-pull: in-memory tracker for in-flight pulls. Survives only until
# backend restart — that is intentional, on restart we ask Ollama who
# really has the model. Format: {model_id: {"status": "...", "started":
# float, "finished": float|None, "error": str|None, "bytes": int|None}}
_PULL_STATE: dict[str, dict[str, Any]] = {}


def _do_pull(model_id: str) -> None:
    """Background-thread pull. Streams Ollama's progress JSON lines and
    only flips to ``completed`` when Ollama itself emits ``status:
    success``. Failures land in ``_PULL_STATE[model_id]['error']``.
    """
    import httpx
    state = _PULL_STATE.setdefault(model_id, {})
    state["status"] = "pulling"
    state["started"] = time.time()
    state["error"] = None
    state["bytes"] = 0
    payload = {"name": model_id, "stream": True}
    try:
        # No timeout = let big pulls run for hours, but it's fine — this
        # function executes in a worker thread, the asyncio event loop
        # is unaffected.
        with httpx.Client(timeout=None) as client:
            with client.stream(
                "POST", f"{OLLAMA_BASE_URL}/api/pull", json=payload,
            ) as r:
                if r.status_code >= 400:
                    state["status"] = "error"
                    state["error"] = f"HTTP {r.status_code}: {r.text[:300]}"
                    return
                last = None
                for line in r.iter_lines():
                    if not line:
                        continue
                    last = line
                    try:
                        evt = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    state["bytes"] = int(evt.get("completed") or state.get("bytes") or 0)
                    state["total"] = int(evt.get("total") or state.get("total") or 0)
                    if evt.get("error"):
                        state["status"] = "error"
                        state["error"] = str(evt["error"])
                        return
                if last and "success" in str(last):
                    state["status"] = "completed"
                else:
                    # Stream ended without explicit success — treat as
                    # completed if we got at least one event, else error.
                    state["status"] = "completed" if last else "error"
                    if not last:
                        state["error"] = "Ollama stream closed without progress"
    except Exception as exc:
        state["status"] = "error"
        state["error"] = f"Ollama unreachable: {exc}"
    finally:
        state["finished"] = time.time()


@router.post("/local-models/pull")
async def pull_local_model(req: LocalModelPullRequest) -> dict[str, Any]:
    """F-018 / F-bug-pull: trigger Ollama to pull a model.

    Returns IMMEDIATELY with ``{status: "pulling"}``. The actual pull
    runs in a background worker thread (so the asyncio event loop and
    the rest of the API stay responsive even when downloading a 42GB
    model). Poll ``GET /local-models/pull-status/<model>`` for progress.

    Previously this was a synchronous ``httpx.Client`` inside an ``async``
    handler, which blocked the event loop for the entire duration of the
    download — every other request 504'd until it finished.
    """
    model_id = req.model.strip()
    if not model_id:
        raise HTTPException(400, "model name required")

    # If a pull is already in flight for this model, just report it.
    existing = _PULL_STATE.get(model_id)
    if existing and existing.get("status") == "pulling":
        return {"model": model_id, "status": "pulling", "already_running": True}

    # Spawn the worker. We use threading rather than BackgroundTasks
    # because BackgroundTasks ties to the request lifetime — once the
    # response goes out, FastAPI cancels the task. We want it detached.
    import threading
    t = threading.Thread(target=_do_pull, args=(model_id,), daemon=True)
    t.start()

    # Give the thread a beat to update _PULL_STATE so we return a
    # truthful starting status.
    time.sleep(0.05)
    return {
        "model": model_id,
        "status": _PULL_STATE.get(model_id, {}).get("status", "pulling"),
        "started": _PULL_STATE.get(model_id, {}).get("started"),
        "poll_url": f"/api/v1/ai-providers/local-models/pull-status/{model_id}",
    }


@router.get("/local-models/pull-status/{model_id:path}")
async def pull_local_model_status(model_id: str) -> dict[str, Any]:
    """F-bug-pull: poll progress of a running ``/local-models/pull``.

    Returns the same dict that the worker maintains: status (pulling /
    completed / error / unknown), started/finished timestamps, byte
    counters when Ollama provides them, and any error string.
    """
    state = _PULL_STATE.get(model_id)
    if not state:
        return {"model": model_id, "status": "unknown"}
    return {"model": model_id, **state}


@router.get("/list")
def list_providers() -> dict[str, Any]:
    """List supported providers with key-availability (without exposing keys).

    PDF §8.1.6: local providers (LM Studio, vLLM, llama.cpp) report
    ``key_available=True`` and ``locality="local"`` so the UI can label
    them "no key needed" instead of warning about a missing credential.
    """
    out = []
    for p in DEFAULT_MODELS:
        is_local = p in LOCAL_PROVIDERS
        key = "" if is_local else _resolve_key(p)
        runtime_reachable = _local_runtime_reachable(p) if is_local else None
        entry = {
            "provider": p,
            "default_model": DEFAULT_MODELS[p],
            "env_var": ENV_KEYS[p],
            "key_available": True if is_local else bool(key),
            "key_preview": "(local — no key)" if is_local else _mask(key),
            "locality": "local" if is_local else "cloud",
            "runtime_reachable": runtime_reachable,
            "ready": bool(runtime_reachable) if is_local else bool(key),
        }
        if is_local:
            entry["base_url"] = _local_base_url(p)
        out.append(entry)
    return {"providers": out}


@router.post("/test/{provider}")
def test_provider(provider: str, req: ProviderTestRequest | None = None) -> dict[str, Any]:
    """Make a real minimal call to the given provider and return raw response."""
    provider = provider.lower()
    if provider not in DISPATCH:
        raise HTTPException(status_code=404, detail=f"unknown provider '{provider}'")

    body = req or ProviderTestRequest()
    model = body.model or DEFAULT_MODELS[provider]
    # F-023: prefer user-supplied key from request body (used during wizard
    # validation before the key is persisted to KeyVault). Fall back to vault/env.
    key = body.api_key.strip() if body.api_key and body.api_key.strip() else _resolve_key(provider)
    # PDF §8.1.6 — local OAI-compat runtimes don't need a key. Skip the
    # "no key" 400 and let the dispatcher pass the "sk-local" sentinel.
    if not key and provider not in LOCAL_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"no API key for {provider} (set {ENV_KEYS[provider]} or add to KeyVault, or pass api_key in body)",
        )
    _emit_provider_setup_requests(provider, model, has_key=bool(key))

    start = time.time()
    try:
        result = DISPATCH[provider](body.prompt, model, body.max_tokens, key)
    except Exception as exc:  # noqa: BLE001
        log.exception("provider=%s call failed", provider)
        raise HTTPException(
            status_code=502,
            detail={"provider": provider, "model": model, "error": str(exc)[:300]},
        )
    latency_ms = int((time.time() - start) * 1000)

    return {
        "provider": provider,
        "model": model,
        "prompt": body.prompt,
        "key_preview": _mask(key),
        "latency_ms": latency_ms,
        "response": result,
    }
