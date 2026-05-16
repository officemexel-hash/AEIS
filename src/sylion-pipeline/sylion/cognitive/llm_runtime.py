"""Runtime LLM dispatch for AEIS control-plane decisions.

This module is deliberately separate from dashboard routes: Council, idea
discussion, workers and tests can call the same real provider path instead of
manufacturing "demo" analyses. If no configured model can be reached, callers
get an explicit exception and must block/escalate.
"""

from __future__ import annotations

import json
import os
import re
import hashlib
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any


class LLMRuntimeError(RuntimeError):
    """Base exception for runtime LLM dispatch failures."""


class LLMUnavailable(LLMRuntimeError):
    """Raised when no configured provider can satisfy a request."""


@dataclass
class LLMCallResult:
    ok: bool
    text: str
    provider: str
    model: str
    provider_requested: str = ""
    model_requested: str = ""
    fallback_used: bool = False
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DIRECT_PROVIDERS: tuple[str, ...] = (
    "openai",
    "anthropic",
    "perplexity",
    "zai",
    "google",
    "moonshot",
    "deepseek",
    "mistral",
    "groq",
    "cohere",
    "fireworks",
    "together",
    "xai",
)

ROLE_FALLBACKS: dict[str, tuple[str, ...]] = {
    "planner": ("openai", "anthropic", "zai", "ollama", "perplexity"),
    "architect": ("anthropic", "openai", "zai", "ollama", "perplexity"),
    "critic": ("anthropic", "openai", "zai", "ollama", "perplexity"),
    "verifier": ("zai", "openai", "anthropic", "ollama", "perplexity"),
    "governance": ("anthropic", "openai", "perplexity", "zai", "ollama"),
    "security_sentinel": ("anthropic", "openai", "zai", "ollama"),
    "cost_sentinel": ("openai", "zai", "ollama", "perplexity"),
    "funding_specialist": ("perplexity", "anthropic", "openai", "zai", "ollama"),
    "domain_specialist": ("anthropic", "zai", "openai", "ollama", "perplexity"),
}

DEFAULT_PROVIDER_ORDER: tuple[str, ...] = (
    "openai",
    "anthropic",
    "zai",
    "perplexity",
    "ollama",
)

MODEL_ALIAS_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5",
    "perplexity": "sonar",
    "zai": "glm-4-plus",
    "moonshot": "moonshot-v1-8k",
}

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def infer_provider_for_model(model_id: str, installed_ollama: set[str] | None = None) -> str:
    """Infer provider from a model id without using OpenRouter aliases."""
    raw = str(model_id or "").strip()
    lowered = raw.lower()
    installed = installed_ollama or set()
    if not raw:
        return ""
    if raw in installed:
        return "ollama"
    if ":" in raw:
        return "ollama"
    if lowered.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    if lowered.startswith("claude"):
        return "anthropic"
    if lowered.startswith("sonar"):
        return "perplexity"
    if lowered.startswith("glm") or "z.ai" in lowered or lowered.startswith("zai"):
        return "zai"
    if lowered.startswith("gemini"):
        return "google"
    if lowered.startswith("kimi") or lowered.startswith("moonshot"):
        return "moonshot"
    if lowered.startswith("deepseek"):
        return "deepseek"
    if lowered.startswith("mistral"):
        return "mistral"
    if lowered.startswith("grok"):
        return "xai"
    if lowered.startswith("openrouter") or lowered.startswith(("anthropic/", "openai/", "google/", "meta-")):
        return "openrouter"
    return ""


def installed_ollama_models() -> list[str]:
    import httpx

    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code >= 400:
                return []
            data = response.json() or {}
    except Exception:
        return []
    return [
        str(item.get("name") or item.get("model") or "").strip()
        for item in data.get("models", []) or []
        if item.get("name") or item.get("model")
    ]


def ollama_reachable() -> bool:
    return bool(installed_ollama_models())


def preferred_ollama_model(requested: str = "") -> str:
    installed = installed_ollama_models()
    if requested and requested in installed:
        return requested
    env_default = os.environ.get("AEIS_OLLAMA_DEFAULT_MODEL", "").strip()
    if env_default and env_default in installed:
        return env_default
    for candidate in (
        "SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M",
        "PRIHLOP/PLLuM:12B-chat-Q8_0",
        "qwen2.5:7b-instruct",
        "qwen2.5:72b-instruct",
        "qwen3.5:latest",
        "gpt-oss:20b",
        "gemma2:9b",
        "mistral:7b",
        "llama3.2:3b",
        "phi3:mini",
    ):
        if candidate in installed:
            return candidate
    return installed[0] if installed else ""


def _routes():
    from sylion.api import ai_providers_routes

    return ai_providers_routes


def _resolve_key(provider: str) -> str:
    try:
        return _routes()._resolve_key(provider)  # type: ignore[attr-defined]
    except Exception:
        return ""


def configured_providers() -> list[str]:
    providers: list[str] = []
    for provider in DIRECT_PROVIDERS:
        if _resolve_key(provider):
            providers.append(provider)
    if ollama_reachable():
        providers.append("ollama")
    # OpenRouter is intentionally excluded from generic fallback when direct
    # provider keys exist. It is used only when explicitly requested or when no
    # direct provider can run.
    if not providers and _resolve_key("openrouter"):
        providers.append("openrouter")
    return providers


def provider_available(provider: str) -> bool:
    provider = str(provider or "").lower()
    if provider == "ollama":
        return ollama_reachable()
    if provider == "openrouter":
        direct_available = any(_resolve_key(item) for item in DIRECT_PROVIDERS)
        return bool(_resolve_key("openrouter")) and not direct_available
    return bool(_resolve_key(provider))


def _registered_models_by_provider(provider: str) -> set[str]:
    try:
        from sylion.cognitive.model_registry import get_model_registry

        return {
            str(item.get("model_id") or "")
            for item in get_model_registry().list_models(provider=provider)
            if item.get("model_id")
        }
    except Exception:
        return set()


def resolve_model(provider: str, requested_model: str = "") -> str:
    provider = str(provider or "").lower()
    requested = str(requested_model or "").strip()
    if provider == "ollama":
        model = preferred_ollama_model(requested)
        if not model:
            raise LLMUnavailable("Ollama is reachable=false or has no installed models")
        return model
    registered = _registered_models_by_provider(provider)
    if requested and requested in registered:
        return requested
    if requested and infer_provider_for_model(requested) == provider and not registered:
        # No registry entry exists in small tests; use the requested model only
        # when the provider is explicitly inferred and no better truth exists.
        return requested
    try:
        default = _routes().DEFAULT_MODELS.get(provider)  # type: ignore[attr-defined]
    except Exception:
        default = ""
    return default or MODEL_ALIAS_DEFAULTS.get(provider, requested)


def provider_candidates(
    *,
    provider: str = "",
    model: str = "",
    role: str = "",
) -> list[str]:
    requested_provider = str(provider or "").strip().lower() or infer_provider_for_model(model)
    role_key = str(role or "").strip().lower()
    ordered: list[str] = []
    if requested_provider:
        ordered.append(requested_provider)
    ordered.extend(ROLE_FALLBACKS.get(role_key, DEFAULT_PROVIDER_ORDER))
    ordered.extend(DEFAULT_PROVIDER_ORDER)
    direct_available = any(_resolve_key(item) for item in DIRECT_PROVIDERS)
    if requested_provider == "openrouter" or not direct_available:
        ordered.append("openrouter")

    seen: set[str] = set()
    out: list[str] = []
    for item in ordered:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _call_ollama(prompt: str, model: str, max_tokens: int) -> dict[str, Any]:
    import httpx

    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max(1, int(max_tokens or 256)),
                    "temperature": 0.1,
                },
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"ollama HTTP {response.status_code}: {response.text[:240]}")
        data = response.json() or {}
    return {
        "text": str(data.get("response") or ""),
        "prompt_tokens": int(data.get("prompt_eval_count") or 0),
        "completion_tokens": int(data.get("eval_count") or 0),
        "model_used": model,
    }


def estimate_cost_usd(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if provider == "ollama":
        return 0.0
    # Conservative control-plane estimates. The precise billing remains in the
    # provider portal; AEIS uses this for budget guard visibility.
    rates = {
        "openai": (0.00015, 0.00060),
        "anthropic": (0.00080, 0.00400),
        "perplexity": (0.00100, 0.00100),
        "zai": (0.00050, 0.00050),
        "google": (0.00010, 0.00040),
        "moonshot": (0.00020, 0.00020),
        "openrouter": (0.00100, 0.00300),
    }
    in_rate, out_rate = rates.get(provider, (0.00050, 0.00150))
    return round((max(prompt_tokens, 0) / 1000.0) * in_rate + (max(completion_tokens, 0) / 1000.0) * out_rate, 6)


def _fallback_token_estimate(text: str) -> int:
    return max(1, len(str(text or "")) // 4)


def _record_llm_usage(result: LLMCallResult, prompt: str, role: str = "") -> None:
    """Best-effort durable usage ledger for real LLM calls.

    Provider APIs do not always return token counts. We still record a
    conservative token estimate so Council runtime activity is visible to W18
    and audit DB checks instead of silently looking like zero work.
    """
    now = time.time()
    model_key = f"{result.provider}:{result.model}"
    prompt_hash = hashlib.sha256(str(prompt or "").encode("utf-8", errors="replace")).hexdigest()
    call_id = f"llm_{uuid.uuid4().hex[:16]}"
    try:
        from sylion.aeis_v2.audit_profile import resolve_db_path

        conn = sqlite3.connect(resolve_db_path("sylion_aeis.db"))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS llm_calls (
                    call_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL DEFAULT '',
                    prompt_hash TEXT NOT NULL DEFAULT '',
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    cost REAL NOT NULL DEFAULT 0.0,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sylion_models (
                    model_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL DEFAULT '',
                    model_name TEXT NOT NULL DEFAULT '',
                    capabilities TEXT NOT NULL DEFAULT '[]',
                    cost_per_1k_tokens REAL NOT NULL DEFAULT 0.0,
                    registered_at REAL NOT NULL DEFAULT 0.0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sylion_model_usage (
                    usage_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL DEFAULT '',
                    tokens_in INTEGER NOT NULL DEFAULT 0,
                    tokens_out INTEGER NOT NULL DEFAULT 0,
                    latency_ms REAL NOT NULL DEFAULT 0.0,
                    success INTEGER NOT NULL DEFAULT 1,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO sylion_models "
                "(model_id, provider, model_name, capabilities, cost_per_1k_tokens, registered_at) "
                "VALUES (?, ?, ?, '[]', 0.0, ?)",
                (model_key, result.provider, result.model, now),
            )
            conn.execute(
                "INSERT INTO llm_calls "
                "(call_id, model_id, prompt_hash, prompt_tokens, completion_tokens, cost, latency_ms, status, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    call_id,
                    model_key,
                    prompt_hash,
                    int(result.prompt_tokens),
                    int(result.completion_tokens),
                    float(result.estimated_cost_usd),
                    int(result.latency_ms),
                    "ok" if result.ok else "error",
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO sylion_model_usage "
                "(usage_id, model_id, tokens_in, tokens_out, latency_ms, success, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"usage_{uuid.uuid4().hex[:16]}",
                    model_key,
                    int(result.prompt_tokens),
                    int(result.completion_tokens),
                    float(result.latency_ms),
                    1 if result.ok else 0,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    try:
        from sylion.aeis_v2.deployment.cost_ledger import CostRecord, emit_cost_record

        emit_cost_record(CostRecord(
            ts=now,
            session_id="",
            decision_id=call_id,
            host=result.provider,
            model=model_key,
            tokens_in=int(result.prompt_tokens),
            tokens_out=int(result.completion_tokens),
            cost_usd=float(result.estimated_cost_usd),
            metadata={
                "role": role,
                "provider_requested": result.provider_requested,
                "model_requested": result.model_requested,
                "fallback_used": result.fallback_used,
                "prompt_hash": prompt_hash,
            },
        ))
    except Exception:
        pass


def call_llm(
    prompt: str,
    *,
    provider: str = "",
    model: str = "",
    role: str = "",
    max_tokens: int = 512,
) -> LLMCallResult:
    """Call a real configured provider.

    Fallback is allowed only to other configured direct providers or to local
    Ollama. OpenRouter is not used when a dedicated provider key exists.
    """
    requested_provider = str(provider or "").strip().lower()
    requested_model = str(model or "").strip()
    errors: list[str] = []
    for candidate in provider_candidates(provider=requested_provider, model=requested_model, role=role):
        if not provider_available(candidate):
            errors.append(f"{candidate}:not_configured")
            continue
        try:
            resolved_model = resolve_model(candidate, requested_model)
            start = time.time()
            if candidate == "ollama":
                raw = _call_ollama(prompt, resolved_model, max_tokens)
            else:
                routes = _routes()
                key = _resolve_key(candidate)
                raw = routes.DISPATCH[candidate](prompt, resolved_model, max_tokens, key)  # type: ignore[attr-defined]
            latency_ms = int((time.time() - start) * 1000)
            prompt_tokens = int(raw.get("prompt_tokens") or 0)
            completion_tokens = int(raw.get("completion_tokens") or 0)
            model_used = str(raw.get("model_used") or resolved_model)
            if prompt_tokens <= 0:
                prompt_tokens = _fallback_token_estimate(prompt)
            response_text = str(raw.get("text") or "")
            if completion_tokens <= 0:
                completion_tokens = _fallback_token_estimate(response_text)
            result = LLMCallResult(
                ok=True,
                text=response_text,
                provider=candidate,
                model=model_used,
                provider_requested=requested_provider,
                model_requested=requested_model,
                fallback_used=bool(candidate != requested_provider or model_used != requested_model),
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=estimate_cost_usd(candidate, model_used, prompt_tokens, completion_tokens),
            )
            _record_llm_usage(result, prompt, role)
            return result
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}:{type(exc).__name__}:{str(exc)[:160]}")
            continue
    raise LLMUnavailable("; ".join(errors) or "no configured provider")


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse the first JSON object from model output."""
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}
