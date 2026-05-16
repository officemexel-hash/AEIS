"""Provider Catalog control plane for Phase 2 onboarding.

This route composes the existing KeyVault, model registry, provider probes and
budget store into one operator-facing snapshot. It is intentionally computed
from current runtime truth instead of introducing a second provider database.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/provider-catalog", tags=["Provider Catalog"])

LOCAL_PROVIDERS = {"ollama", "lmstudio", "llamacpp", "vllm", "localai"}
LOCAL_PROBE_TIMEOUT_S = float(os.environ.get("SYLION_PROVIDER_CATALOG_LOCAL_TIMEOUT_S", "0.35"))

CAPABILITY_DEFINITIONS: list[dict[str, Any]] = [
    {"id": "text_generation", "label": "Text generation", "required": True},
    {"id": "code_generation", "label": "Code generation", "required": False},
    {"id": "polish_text", "label": "Polish text", "required": False},
    {"id": "long_context", "label": "Long context", "required": False},
    {"id": "vision_image_input", "label": "Vision / image input", "required": False},
    {"id": "function_calling", "label": "Function calling", "required": False},
    {"id": "embeddings", "label": "Embeddings", "required": False},
    {"id": "reasoning_deep", "label": "Reasoning deep", "required": False},
    {"id": "image_generation", "label": "Image generation", "required": False},
    {"id": "audio_tts", "label": "Audio TTS", "required": False},
    {"id": "audio_transcription", "label": "Audio transcription", "required": False},
    {"id": "video_analysis", "label": "Video analysis", "required": False},
]

PROVIDER_TEMPLATES: list[dict[str, Any]] = [
    {
        "provider": "anthropic",
        "display_name": "Anthropic",
        "kind": "api",
        "env_var": "ANTHROPIC_API_KEY",
        "default_endpoint": "https://api.anthropic.com",
        "default_models": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "long_context", "vision_image_input", "function_calling", "reasoning_deep"],
        "quality_tier": "premium",
        "cost_input_per_1m": 3.0,
        "cost_output_per_1m": 15.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "openai",
        "display_name": "OpenAI",
        "kind": "api",
        "env_var": "OPENAI_API_KEY",
        "default_endpoint": "https://api.openai.com",
        "default_models": ["gpt-5", "gpt-5-mini", "gpt-4o-mini", "text-embedding-3-small", "whisper-1"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "long_context", "vision_image_input", "function_calling", "embeddings", "reasoning_deep", "audio_tts", "audio_transcription"],
        "quality_tier": "premium",
        "cost_input_per_1m": 1.5,
        "cost_output_per_1m": 6.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "google",
        "display_name": "Google Gemini",
        "kind": "api",
        "env_var": "GOOGLE_API_KEY",
        "default_endpoint": "https://generativelanguage.googleapis.com",
        "default_models": ["gemini-2.5-pro", "gemini-2.5-flash"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "long_context", "vision_image_input", "function_calling", "video_analysis"],
        "quality_tier": "standard",
        "cost_input_per_1m": 1.25,
        "cost_output_per_1m": 5.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "openrouter",
        "display_name": "OpenRouter",
        "kind": "api",
        "env_var": "OPENROUTER_API_KEY",
        "default_endpoint": "https://openrouter.ai/api/v1",
        "default_models": ["openrouter/auto", "anthropic/claude-sonnet-4.5", "google/gemini-2.5-pro", "black-forest-labs/flux-schnell"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "long_context", "vision_image_input", "function_calling", "reasoning_deep", "image_generation"],
        "quality_tier": "broker",
        "cost_input_per_1m": 1.0,
        "cost_output_per_1m": 4.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "perplexity",
        "display_name": "Perplexity",
        "kind": "api",
        "env_var": "PERPLEXITY_API_KEY",
        "default_endpoint": "https://api.perplexity.ai",
        "default_models": ["sonar", "sonar-pro"],
        "capabilities": ["text_generation", "long_context"],
        "quality_tier": "research",
        "cost_input_per_1m": 1.0,
        "cost_output_per_1m": 1.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "mistral",
        "display_name": "Mistral",
        "kind": "api",
        "env_var": "MISTRAL_API_KEY",
        "default_endpoint": "https://api.mistral.ai",
        "default_models": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "function_calling", "embeddings"],
        "quality_tier": "eu_sovereign",
        "cost_input_per_1m": 2.0,
        "cost_output_per_1m": 6.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "groq",
        "display_name": "Groq",
        "kind": "api",
        "env_var": "GROQ_API_KEY",
        "default_endpoint": "https://api.groq.com/openai/v1",
        "default_models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "capabilities": ["text_generation", "code_generation", "long_context"],
        "quality_tier": "fast",
        "cost_input_per_1m": 0.6,
        "cost_output_per_1m": 0.8,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "deepseek",
        "display_name": "DeepSeek",
        "kind": "api",
        "env_var": "DEEPSEEK_API_KEY",
        "default_endpoint": "https://api.deepseek.com",
        "default_models": ["deepseek-chat", "deepseek-reasoner"],
        "capabilities": ["text_generation", "code_generation", "reasoning_deep", "function_calling"],
        "quality_tier": "code_reasoning",
        "cost_input_per_1m": 0.3,
        "cost_output_per_1m": 1.2,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "xai",
        "display_name": "xAI",
        "kind": "api",
        "env_var": "XAI_API_KEY",
        "default_endpoint": "https://api.x.ai/v1",
        "default_models": ["grok-2-1212", "grok-vision-beta"],
        "capabilities": ["text_generation", "code_generation", "vision_image_input", "function_calling"],
        "quality_tier": "standard",
        "cost_input_per_1m": 2.0,
        "cost_output_per_1m": 10.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "zai",
        "display_name": "Z.AI GLM",
        "kind": "api",
        "env_var": "ZAI_API_KEY",
        "default_endpoint": "https://api.z.ai/api/paas/v4",
        "default_models": ["glm-4-plus", "glm-4-air"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "function_calling"],
        "quality_tier": "standard",
        "cost_input_per_1m": 0.5,
        "cost_output_per_1m": 0.5,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "moonshot",
        "display_name": "Moonshot Kimi",
        "kind": "api",
        "env_var": "MOONSHOT_API_KEY",
        "default_endpoint": "https://api.moonshot.ai/v1",
        "default_models": ["kimi-k2.6", "moonshot-v1-128k"],
        "capabilities": ["text_generation", "code_generation", "long_context"],
        "quality_tier": "long_context",
        "cost_input_per_1m": 1.0,
        "cost_output_per_1m": 3.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "cohere",
        "display_name": "Cohere",
        "kind": "api",
        "env_var": "COHERE_API_KEY",
        "default_endpoint": "https://api.cohere.com",
        "default_models": ["command-r-plus", "embed-v4.0"],
        "capabilities": ["text_generation", "function_calling", "embeddings", "long_context"],
        "quality_tier": "rag",
        "cost_input_per_1m": 2.5,
        "cost_output_per_1m": 10.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "fireworks",
        "display_name": "Fireworks",
        "kind": "api",
        "env_var": "FIREWORKS_API_KEY",
        "default_endpoint": "https://api.fireworks.ai/inference/v1",
        "default_models": ["accounts/fireworks/models/llama-v3p3-70b-instruct"],
        "capabilities": ["text_generation", "code_generation", "function_calling"],
        "quality_tier": "open_models",
        "cost_input_per_1m": 0.9,
        "cost_output_per_1m": 0.9,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "together",
        "display_name": "Together AI",
        "kind": "api",
        "env_var": "TOGETHER_API_KEY",
        "default_endpoint": "https://api.together.xyz/v1",
        "default_models": ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"],
        "capabilities": ["text_generation", "code_generation", "function_calling"],
        "quality_tier": "open_models",
        "cost_input_per_1m": 0.9,
        "cost_output_per_1m": 0.9,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "replicate",
        "display_name": "Replicate",
        "kind": "api",
        "env_var": "REPLICATE_API_TOKEN",
        "default_endpoint": "https://api.replicate.com",
        "default_models": ["black-forest-labs/flux-schnell", "stability-ai/sdxl"],
        "capabilities": ["image_generation", "video_analysis", "audio_transcription"],
        "quality_tier": "media",
        "cost_input_per_1m": 0.0,
        "cost_output_per_1m": 0.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "elevenlabs",
        "display_name": "ElevenLabs",
        "kind": "api",
        "env_var": "ELEVENLABS_API_KEY",
        "default_endpoint": "https://api.elevenlabs.io",
        "default_models": ["eleven_multilingual_v2", "eleven_turbo_v2_5"],
        "capabilities": ["audio_tts"],
        "quality_tier": "audio",
        "cost_input_per_1m": 0.0,
        "cost_output_per_1m": 0.0,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "azure-openai",
        "display_name": "Azure OpenAI",
        "kind": "api",
        "env_var": "AZURE_OPENAI_API_KEY",
        "default_endpoint": "https://{resource}.openai.azure.com",
        "default_models": ["gpt-4o", "gpt-4o-mini", "text-embedding-3-large"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "vision_image_input", "function_calling", "embeddings"],
        "quality_tier": "enterprise",
        "cost_input_per_1m": 2.5,
        "cost_output_per_1m": 10.0,
        "quota_source": "azure_portal",
        "setup_fields": ["endpoint", "api_key", "deployment_name"],
    },
    {
        "provider": "aws-bedrock",
        "display_name": "AWS Bedrock",
        "kind": "api",
        "env_var": "AWS_PROFILE",
        "default_endpoint": "bedrock-runtime",
        "default_models": ["anthropic.claude-3-5-sonnet", "amazon.titan-embed-text-v2"],
        "capabilities": ["text_generation", "code_generation", "long_context", "embeddings"],
        "quality_tier": "enterprise",
        "cost_input_per_1m": 3.0,
        "cost_output_per_1m": 15.0,
        "quota_source": "aws_console",
        "setup_fields": ["aws_profile", "region"],
    },
    {
        "provider": "vertex-ai",
        "display_name": "Vertex AI",
        "kind": "api",
        "env_var": "GOOGLE_APPLICATION_CREDENTIALS",
        "default_endpoint": "https://{region}-aiplatform.googleapis.com",
        "default_models": ["gemini-2.5-pro", "textembedding-gecko"],
        "capabilities": ["text_generation", "code_generation", "vision_image_input", "embeddings", "video_analysis"],
        "quality_tier": "enterprise",
        "cost_input_per_1m": 1.25,
        "cost_output_per_1m": 5.0,
        "quota_source": "gcp_console",
        "setup_fields": ["service_account", "project_id", "region"],
    },
    {
        "provider": "huggingface",
        "display_name": "Hugging Face Inference",
        "kind": "api",
        "env_var": "HUGGINGFACE_API_TOKEN",
        "default_endpoint": "https://api-inference.huggingface.co",
        "default_models": ["meta-llama/Llama-3.1-70B-Instruct", "BAAI/bge-m3"],
        "capabilities": ["text_generation", "code_generation", "embeddings", "audio_transcription"],
        "quality_tier": "open_models",
        "cost_input_per_1m": 0.8,
        "cost_output_per_1m": 0.8,
        "quota_source": "provider_console",
        "setup_fields": ["api_key"],
    },
    {
        "provider": "ollama",
        "display_name": "Ollama",
        "kind": "local",
        "env_var": "OLLAMA_BASE_URL",
        "default_endpoint": "http://127.0.0.1:11434",
        "default_models": ["qwen2.5:7b-instruct", "bielik-11b-v2.3-instruct", "nomic-embed-text"],
        "capabilities": ["text_generation", "code_generation", "polish_text", "embeddings", "reasoning_deep"],
        "quality_tier": "local",
        "cost_input_per_1m": 0.0,
        "cost_output_per_1m": 0.0,
        "quota_source": "machine_capacity",
        "setup_fields": ["base_url"],
    },
    {
        "provider": "lmstudio",
        "display_name": "LM Studio",
        "kind": "local",
        "env_var": "LMSTUDIO_BASE_URL",
        "default_endpoint": "http://localhost:1234",
        "default_models": ["local-model"],
        "capabilities": ["text_generation", "code_generation", "polish_text"],
        "quality_tier": "local",
        "cost_input_per_1m": 0.0,
        "cost_output_per_1m": 0.0,
        "quota_source": "machine_capacity",
        "setup_fields": ["base_url"],
    },
    {
        "provider": "llamacpp",
        "display_name": "llama.cpp server",
        "kind": "local",
        "env_var": "LLAMACPP_BASE_URL",
        "default_endpoint": "http://localhost:8080",
        "default_models": ["gguf-loaded-model"],
        "capabilities": ["text_generation", "code_generation", "polish_text"],
        "quality_tier": "local",
        "cost_input_per_1m": 0.0,
        "cost_output_per_1m": 0.0,
        "quota_source": "machine_capacity",
        "setup_fields": ["base_url"],
    },
    {
        "provider": "vllm",
        "display_name": "vLLM",
        "kind": "local",
        "env_var": "VLLM_BASE_URL",
        "default_endpoint": "http://localhost:8001",
        "default_models": ["Qwen/Qwen2.5-72B-Instruct"],
        "capabilities": ["text_generation", "code_generation", "long_context", "function_calling"],
        "quality_tier": "local_server",
        "cost_input_per_1m": 0.0,
        "cost_output_per_1m": 0.0,
        "quota_source": "machine_capacity",
        "setup_fields": ["base_url"],
    },
]

CUSTOM_PROVIDER_TEMPLATE = {
    "provider": "custom-openai-compatible",
    "display_name": "Custom OpenAI-compatible",
    "kind": "custom",
    "env_var": "",
    "default_endpoint": "",
    "default_models": [],
    "capabilities": ["text_generation", "code_generation", "function_calling"],
    "quality_tier": "operator_defined",
    "cost_input_per_1m": 0.0,
    "cost_output_per_1m": 0.0,
    "quota_source": "operator_defined",
    "setup_fields": ["provider_id", "base_url", "api_key", "model_id"],
}

LOCAL_INSTALL_SUGGESTIONS = [
    {
        "capability": "image_generation",
        "title": "Local Stable Diffusion / ComfyUI",
        "provider": "local",
        "recommended_when": "Need private image generation and GPU with 8GB+ VRAM",
        "models": ["FLUX.1 schnell", "SDXL Turbo", "Stable Diffusion 3.5 Medium"],
        "install_hint": "Install ComfyUI or AUTOMATIC1111, then expose an HTTP workflow endpoint.",
    },
    {
        "capability": "audio_tts",
        "title": "Piper / Coqui / XTTS",
        "provider": "local",
        "recommended_when": "Need multilingual TTS without sending text to a vendor",
        "models": ["piper-pl_PL", "XTTS-v2", "Kokoro TTS"],
        "install_hint": "Run local TTS server and register it as a custom provider endpoint.",
    },
    {
        "capability": "embeddings",
        "title": "nomic-embed-text via Ollama",
        "provider": "ollama",
        "recommended_when": "Need local RAG/search memory",
        "models": ["nomic-embed-text", "bge-m3"],
        "install_hint": "ollama pull nomic-embed-text",
    },
]


class BenchmarkRequest(BaseModel):
    provider: str
    model: str = ""
    prompt: str = "Say OK"
    max_tokens: int = 32


class AutoArrangeCouncilRequest(BaseModel):
    force: bool = False
    max_members: int = 7


class CustomProviderRequest(BaseModel):
    provider_id: str
    display_name: str = ""
    base_url: str
    model_id: str
    api_key: str | None = None
    capabilities: list[str] = []


COUNCIL_ROLE_BLUEPRINTS: list[dict[str, Any]] = [
    {"member_id": "auto-architect", "role": "architect", "rank": "primary", "voting_weight": 1.4, "priority": 10, "specialization": "architecture, decomposition, high_risk_design", "max_tokens": 4096},
    {"member_id": "auto-planner", "role": "planner", "rank": "primary", "voting_weight": 1.2, "priority": 20, "specialization": "planning, sequencing, project_scope", "max_tokens": 4096},
    {"member_id": "auto-executor", "role": "executor", "rank": "support", "voting_weight": 1.0, "priority": 30, "specialization": "implementation, coding, iteration", "max_tokens": 4096},
    {"member_id": "auto-critic", "role": "critic", "rank": "senior_specialist", "voting_weight": 1.3, "priority": 40, "specialization": "risk, alternatives, failure_modes", "max_tokens": 3072},
    {"member_id": "auto-verifier", "role": "verifier", "rank": "validation_only", "voting_weight": 0.8, "priority": 50, "specialization": "offline_verification, tests, evidence", "max_tokens": 2048},
    {"member_id": "auto-security-sentinel", "role": "security_sentinel", "rank": "review_only", "voting_weight": 0.8, "priority": 60, "specialization": "security, secrets, privacy, human_gate", "max_tokens": 2048},
    {"member_id": "auto-cost-sentinel", "role": "cost_sentinel", "rank": "review_only", "voting_weight": 0.6, "priority": 70, "specialization": "cost, budget, local_first", "max_tokens": 1536},
]

RANK_LEVEL = {
    "primary": 1,
    "senior_specialist": 2,
    "support": 3,
    "review_only": 4,
    "validation_only": 5,
}


def _template_by_provider() -> dict[str, dict[str, Any]]:
    return {item["provider"]: item for item in PROVIDER_TEMPLATES}


def _safe_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


_registry = None
def _get_registry():
    global _registry
    if _registry is not None:
        return _registry
    from sylion.cognitive.model_registry import get_model_registry

    _registry = get_model_registry()
    return _registry


_vault = None
def _get_vault():
    global _vault
    if _vault is not None:
        return _vault
    from sylion.security.key_vault import get_key_vault

    _vault = get_key_vault()
    return _vault


def _active_key_providers() -> set[str]:
    providers: set[str] = set()
    try:
        for key in _get_vault().list_keys():
            if key.get("is_active"):
                providers.add(str(key.get("provider") or "").lower())
    except Exception:
        pass
    for template in PROVIDER_TEMPLATES:
        env_var = template.get("env_var") or ""
        if env_var and os.environ.get(env_var):
            providers.add(str(template["provider"]).lower())
    return providers


def _local_base_url(provider: str, template: dict[str, Any]) -> str:
    env_var = str(template.get("env_var") or "")
    return os.environ.get(env_var) or str(template.get("default_endpoint") or "")


def _local_probe_base_url(base_url: str) -> str:
    if base_url.startswith("http://localhost"):
        return base_url.replace("http://localhost", "http://127.0.0.1", 1)
    if base_url.startswith("https://localhost"):
        return base_url.replace("https://localhost", "https://127.0.0.1", 1)
    return base_url


def _local_probe_timeout():
    import httpx

    connect_timeout = min(0.2, LOCAL_PROBE_TIMEOUT_S)
    return httpx.Timeout(LOCAL_PROBE_TIMEOUT_S, connect=connect_timeout)


def _probe_ollama(base_url: str) -> dict[str, Any]:
    import httpx

    if not base_url:
        return {"status": "not_configured", "models": [], "raw_models": [], "latency_ms": 0, "error": "missing base_url"}
    probe_url = _local_probe_base_url(base_url).rstrip("/")
    start = time.time()
    try:
        with httpx.Client(timeout=_local_probe_timeout()) as client:
            response = client.get(f"{probe_url}/api/tags")
        latency_ms = int((time.time() - start) * 1000)
        if response.status_code >= 400:
            return {"status": "unavailable", "models": [], "raw_models": [], "latency_ms": latency_ms, "error": response.text[:160]}
        payload = response.json() or {}
        raw_models = [item for item in payload.get("models", []) if isinstance(item, dict)]
        models = [str(item.get("name") or "") for item in raw_models if item.get("name")]
        return {"status": "healthy" if models else "degraded", "models": models, "raw_models": raw_models, "latency_ms": latency_ms, "error": ""}
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "models": [], "raw_models": [], "latency_ms": int((time.time() - start) * 1000), "error": str(exc)[:160]}


def _probe_openai_compatible(base_url: str) -> dict[str, Any]:
    import httpx

    if not base_url:
        return {"status": "not_configured", "models": [], "latency_ms": 0, "error": "missing base_url"}
    probe_url = _local_probe_base_url(base_url).rstrip("/")
    start = time.time()
    try:
        with httpx.Client(timeout=_local_probe_timeout()) as client:
            response = client.get(f"{probe_url}/v1/models")
        latency_ms = int((time.time() - start) * 1000)
        if response.status_code >= 400:
            return {"status": "unavailable", "models": [], "latency_ms": latency_ms, "error": response.text[:160]}
        payload = response.json() or {}
        models = [
            str(item.get("id") or item.get("name") or "")
            for item in payload.get("data", [])
            if item.get("id") or item.get("name")
        ]
        return {"status": "healthy" if models else "degraded", "models": models, "latency_ms": latency_ms, "error": ""}
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "models": [], "latency_ms": int((time.time() - start) * 1000), "error": str(exc)[:160]}


def _probe_local_endpoints() -> dict[str, dict[str, Any]]:
    detected: dict[str, dict[str, Any]] = {}
    templates = _template_by_provider()

    ollama_template = templates["ollama"]
    ollama_base_url = _local_base_url("ollama", ollama_template)
    ollama_probe = _probe_ollama(ollama_base_url)
    detected["ollama"] = {
        "provider": "ollama",
        "endpoint": ollama_base_url,
        "status": ollama_probe["status"],
        "latency_ms": ollama_probe["latency_ms"],
        "models": ollama_probe["models"],
        "raw_models": ollama_probe["raw_models"],
        "trigger": "ollama_tags",
        "error": ollama_probe["error"],
    }

    for provider in ("lmstudio", "llamacpp", "vllm"):
        template = templates[provider]
        base_url = _local_base_url(provider, template)
        probe = _probe_openai_compatible(base_url)
        detected[provider] = {
            "provider": provider,
            "endpoint": base_url,
            "status": probe["status"],
            "latency_ms": probe["latency_ms"],
            "models": probe["models"],
            "raw_models": [{"name": item} for item in probe["models"]],
            "trigger": "openai_compatible_models",
            "error": probe["error"],
        }
    return detected


def _model_capabilities(model_id: str, provider: str, template_caps: list[str]) -> dict[str, int]:
    text = f"{provider} {model_id}".lower()
    caps: dict[str, int] = {cap: 70 for cap in template_caps}

    if any(needle in text for needle in ("llama", "qwen", "mistral", "gemma", "phi", "bielik", "pllum", "gpt", "claude", "gemini", "glm", "deepseek", "kimi")):
        caps.setdefault("text_generation", 75)
    if any(needle in text for needle in ("coder", "code", "qwen", "deepseek", "gpt", "claude", "mistral", "codestral")):
        caps["code_generation"] = max(caps.get("code_generation", 0), 78)
    if any(needle in text for needle in ("bielik", "pllum", "polish", "gpt", "claude", "gemini", "mistral", "qwen", "glm")):
        caps["polish_text"] = max(caps.get("polish_text", 0), 72)
    if any(needle in text for needle in ("128k", "200k", "1m", "long", "gemini", "claude", "kimi", "72b")):
        caps["long_context"] = max(caps.get("long_context", 0), 72)
    if any(needle in text for needle in ("vision", "gpt-4o", "gemini", "claude", "grok")):
        caps["vision_image_input"] = max(caps.get("vision_image_input", 0), 75)
    if any(needle in text for needle in ("embed", "embedding", "nomic", "bge")):
        caps["embeddings"] = max(caps.get("embeddings", 0), 85)
    if any(needle in text for needle in ("reason", "r1", "o1", "o3", "opus", "deepseek-reasoner")):
        caps["reasoning_deep"] = max(caps.get("reasoning_deep", 0), 82)
    if any(needle in text for needle in ("flux", "sdxl", "stable-diffusion", "dall-e", "image")):
        caps["image_generation"] = max(caps.get("image_generation", 0), 85)
    if any(needle in text for needle in ("tts", "eleven", "piper", "xtts", "kokoro")):
        caps["audio_tts"] = max(caps.get("audio_tts", 0), 85)
    if any(needle in text for needle in ("whisper", "transcrib", "stt")):
        caps["audio_transcription"] = max(caps.get("audio_transcription", 0), 85)
    return caps


def _status_level(*, configured: bool, local_status: str = "", has_models: bool = True) -> str:
    if not configured:
        return "not_configured"
    if local_status in {"unavailable", "offline"}:
        return "unavailable"
    if not has_models:
        return "degraded"
    return "healthy"


def _provider_snapshot() -> dict[str, Any]:
    templates = _template_by_provider()
    active_key_providers = _active_key_providers()
    local = _probe_local_endpoints()
    registered = []
    try:
        registered = _get_registry().list_models()
    except Exception:
        registered = []

    models_by_provider: dict[str, list[dict[str, Any]]] = {p: [] for p in templates}
    model_index: dict[str, dict[str, Any]] = {}

    def add_model(
        *,
        provider: str,
        model_id: str,
        display_name: str = "",
        endpoint: str = "",
        source: str,
        configured: bool,
        status: str,
        config: dict[str, Any] | None = None,
    ) -> None:
        if not model_id:
            return
        template = templates.get(provider, CUSTOM_PROVIDER_TEMPLATE)
        caps = _model_capabilities(model_id, provider, list(template.get("capabilities") or []))
        key = f"{provider}:{endpoint}:{model_id}"
        if key in model_index:
            return
        item = {
            "provider": provider,
            "model_id": model_id,
            "display_name": display_name or model_id,
            "endpoint": endpoint or template.get("default_endpoint", ""),
            "kind": "local" if provider in LOCAL_PROVIDERS else "api",
            "configured": configured,
            "status": status,
            "source": source,
            "capabilities": caps,
            "cost_input_per_1m": float(template.get("cost_input_per_1m") or 0.0),
            "cost_output_per_1m": float(template.get("cost_output_per_1m") or 0.0),
            "quality_tier": template.get("quality_tier", "standard"),
            "config": config or {},
        }
        model_index[key] = item
        models_by_provider.setdefault(provider, []).append(item)

    for model in registered:
        provider = str(model.get("provider") or "unknown").lower()
        template = templates.get(provider, CUSTOM_PROVIDER_TEMPLATE)
        config = _safe_json_object(model.get("config_json"))
        endpoint = str(config.get("base_url") or template.get("default_endpoint") or "")
        local_status = local.get(provider, {}).get("status", "")
        configured = True
        status = _status_level(
            configured=configured,
            local_status=local_status if provider in LOCAL_PROVIDERS else "",
            has_models=True,
        )
        add_model(
            provider=provider,
            model_id=str(model.get("model_id") or ""),
            display_name=str(model.get("display_name") or ""),
            endpoint=endpoint,
            source="registry",
            configured=configured,
            status=status,
            config=config,
        )

    for provider, detection in local.items():
        for model_id in detection.get("models") or []:
            add_model(
                provider=provider,
                model_id=str(model_id),
                endpoint=str(detection.get("endpoint") or templates[provider]["default_endpoint"]),
                source=detection.get("trigger") or "local_detection",
                configured=detection.get("status") == "healthy",
                status=str(detection.get("status") or "unavailable"),
            )

    for provider in active_key_providers:
        template = templates.get(provider)
        if not template:
            continue
        for model_id in template.get("default_models") or []:
            add_model(
                provider=provider,
                model_id=str(model_id),
                endpoint=str(template.get("default_endpoint") or ""),
                source="active_key",
                configured=True,
                status="healthy",
            )

    for provider, template in templates.items():
        configured = provider in active_key_providers or (provider in local and local[provider].get("status") == "healthy")
        provider_models = models_by_provider.get(provider, [])
        if not provider_models:
            for model_id in template.get("default_models") or []:
                add_model(
                    provider=provider,
                    model_id=str(model_id),
                    endpoint=str(template.get("default_endpoint") or ""),
                    source="template",
                    configured=False,
                    status="not_configured",
                )
        elif configured:
            for item in provider_models:
                item["configured"] = True
                if item["status"] == "not_configured":
                    item["status"] = "healthy"

    providers = []
    for provider, template in templates.items():
        provider_models = models_by_provider.get(provider, [])
        local_info = local.get(provider)
        configured = any(model.get("configured") for model in provider_models) or provider in active_key_providers
        status = _status_level(
            configured=configured,
            local_status=str(local_info.get("status") if local_info else ""),
            has_models=bool(provider_models),
        )
        providers.append({
            "provider": provider,
            "display_name": template["display_name"],
            "kind": template["kind"],
            "endpoint_count": 1 if template.get("default_endpoint") else 0,
            "model_count": len([m for m in provider_models if m.get("configured")]),
            "catalog_model_count": len(provider_models),
            "configured": configured,
            "status": status,
            "health_level": status,
            "latency_ms": int(local_info.get("latency_ms") or 0) if local_info else 0,
            "quota_status": "machine_capacity" if provider in LOCAL_PROVIDERS else ("unknown" if configured else "not_configured"),
            "default_endpoint": _local_base_url(provider, template) if provider in LOCAL_PROVIDERS else template.get("default_endpoint", ""),
            "env_var": template.get("env_var", ""),
            "models": provider_models,
            "template": template,
            "local_detection": local_info,
        })

    all_models = list(model_index.values())
    configured_models = [model for model in all_models if model.get("configured")]
    return {
        "providers": providers,
        "models": all_models,
        "configured_models": configured_models,
        "local_detection": local,
        "active_key_providers": sorted(active_key_providers),
    }


def _capability_matrix(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configured = [model for model in models if model.get("configured")]
    matrix = []
    for definition in CAPABILITY_DEFINITIONS:
        capability_id = definition["id"]
        available_models = [
            {
                "provider": model["provider"],
                "model_id": model["model_id"],
                "score": int(model.get("capabilities", {}).get(capability_id) or 0),
                "kind": model["kind"],
                "cost_input_per_1m": model["cost_input_per_1m"],
            }
            for model in configured
            if int(model.get("capabilities", {}).get(capability_id) or 0) > 0
        ]
        available_models.sort(key=lambda item: (-item["score"], item["cost_input_per_1m"], item["model_id"]))
        matrix.append({
            **definition,
            "available": bool(available_models),
            "model_count": len(available_models),
            "models": available_models,
            "gap": len(available_models) == 0,
            "single_point_of_failure": len(available_models) == 1,
        })
    return matrix


def _gap_recommendations(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations = {
        "image_generation": ["openrouter", "replicate", "local-stable-diffusion"],
        "audio_tts": ["elevenlabs", "openai", "local-tts"],
        "audio_transcription": ["openai", "huggingface", "local-whisper"],
        "video_analysis": ["google", "vertex-ai", "replicate"],
        "reasoning_deep": ["anthropic", "openai", "deepseek"],
        "long_context": ["anthropic", "google", "moonshot"],
        "embeddings": ["openai", "cohere", "ollama:nomic-embed-text"],
    }
    out = []
    for row in matrix:
        if row["gap"]:
            out.append({
                "capability": row["id"],
                "severity": "hard" if row.get("required") else "soft",
                "reason": "No configured model provides this capability.",
                "recommended_providers": recommendations.get(row["id"], ["openrouter", "custom-openai-compatible"]),
            })
        elif row["single_point_of_failure"]:
            out.append({
                "capability": row["id"],
                "severity": "soft",
                "reason": "Only one configured model covers this capability.",
                "recommended_providers": recommendations.get(row["id"], ["openrouter"]),
            })
    return out


def _priority_chains(matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chains = []
    for row in matrix:
        models = row.get("models") or []
        ordered = sorted(
            models,
            key=lambda item: (
                item.get("cost_input_per_1m", 0.0) > 0.0,
                item.get("cost_input_per_1m", 0.0),
                -int(item.get("score") or 0),
            ),
        )
        chains.append({
            "capability": row["id"],
            "chain": ordered[:5],
            "exhaustion_behavior": "fallback_then_human_gate" if ordered else "block_and_recommend_acquisition",
            "min_entries_recommended": 2 if row["id"] in {"text_generation", "code_generation", "polish_text"} else 1,
        })
    return chains


def _acquisition_advisor(gaps: list[dict[str, Any]], matrix: list[dict[str, Any]]) -> list[dict[str, Any]]:
    template_map = _template_by_provider()
    needed_caps = {item["capability"] for item in gaps if item["severity"] in {"hard", "soft"}}
    if not needed_caps:
        needed_caps = {
            row["id"]
            for row in matrix
            if row["model_count"] < (2 if row["id"] in {"text_generation", "code_generation", "polish_text"} else 1)
        }
    suggestions: list[dict[str, Any]] = []
    for template in PROVIDER_TEMPLATES:
        covered = sorted(set(template.get("capabilities") or []) & needed_caps)
        if not covered:
            continue
        quality_weight = {
            "premium": 5,
            "enterprise": 4,
            "eu_sovereign": 4,
            "media": 4,
            "audio": 4,
            "broker": 4,
            "local": 3,
            "local_server": 3,
        }.get(str(template.get("quality_tier")), 2)
        suggestions.append({
            "provider": template["provider"],
            "display_name": template["display_name"],
            "covers": covered,
            "quality_first_score": quality_weight * 10 + len(covered),
            "cost_input_per_1m": template.get("cost_input_per_1m", 0.0),
            "action": "add_api_key" if template["kind"] == "api" else "configure_local_endpoint",
            "template": template_map[template["provider"]],
        })
    suggestions.sort(key=lambda item: (-item["quality_first_score"], item["cost_input_per_1m"]))
    return suggestions[:8]


def _acceptance(snapshot: dict[str, Any], goal: str = "mixed") -> dict[str, Any]:
    matrix = snapshot["capability_matrix"]
    providers = snapshot["providers"]
    active_api = [p for p in providers if p["configured"] and p["kind"] == "api"]
    local_models = [m for m in snapshot["models"] if m.get("configured") and m.get("kind") == "local"]
    text_row = next(row for row in matrix if row["id"] == "text_generation")
    matrix_populated = any(row["model_count"] > 0 for row in matrix)
    api_key_count = 0
    try:
        api_key_count = len(_get_vault().list_keys())
    except Exception:
        pass
    default_secret = not bool(os.environ.get("SYLION_VAULT_SECRET"))
    fernet_available = False
    try:
        from sylion.security import key_vault as key_vault_module

        fernet_available = bool(getattr(key_vault_module, "_FERNET_AVAILABLE", False))
    except Exception:
        fernet_available = False

    if api_key_count == 0:
        secret_status = "pass"
        secret_evidence = "no API keys stored"
        secret_hard_block = False
    elif fernet_available and not default_secret:
        secret_status = "pass"
        secret_evidence = "Fernet encryption with custom vault secret"
        secret_hard_block = False
    elif fernet_available:
        secret_status = "warn"
        secret_evidence = "Fernet encryption active; default dev vault secret should be rotated before production"
        secret_hard_block = False
    else:
        secret_status = "fail"
        secret_evidence = "cryptography unavailable; vault fell back to base64 obfuscation"
        secret_hard_block = True

    checks = [
        {
            "id": "text_generation_provider",
            "label": "At least 1 provider with text_generation",
            "status": "pass" if text_row["model_count"] > 0 else "fail",
            "evidence": f"{text_row['model_count']} configured models",
            "hard_block": True,
        },
        {
            "id": "local_detection",
            "label": "Local model detection completed",
            "status": "pass" if snapshot["local_detection"] else "fail",
            "evidence": f"{len(snapshot['local_detection'])} local runtimes checked",
            "hard_block": False,
        },
        {
            "id": "capability_matrix",
            "label": "Capability matrix populated",
            "status": "pass" if matrix_populated else "fail",
            "evidence": f"{sum(1 for row in matrix if row['model_count'] > 0)}/{len(matrix)} capabilities",
            "hard_block": True,
        },
        {
            "id": "secret_encryption",
            "label": "Secret storage encryption acceptable",
            "status": secret_status,
            "evidence": secret_evidence,
            "hard_block": secret_hard_block,
        },
        {
            "id": "workspace_state_saved",
            "label": "Workspace provider catalog snapshot available",
            "status": "pass",
            "evidence": "provider_catalog_snapshot",
            "hard_block": False,
        },
    ]

    goal_key = str(goal or "mixed").lower()
    if goal_key == "public_products":
        checks.extend([
            {
                "id": "api_provider",
                "label": "At least 1 API provider",
                "status": "pass" if active_api else "warn",
                "evidence": f"{len(active_api)} configured API providers",
                "hard_block": False,
            },
            {
                "id": "fallback_chains",
                "label": "Fallback chains configured",
                "status": "pass" if any(len(c["chain"]) >= 2 for c in snapshot["priority_chains"]) else "warn",
                "evidence": "chains generated from configured models",
                "hard_block": False,
            },
        ])
    elif goal_key == "cybersecurity":
        sovereign = bool(local_models) or any(p["provider"] == "mistral" and p["configured"] for p in providers)
        checks.append({
            "id": "sovereign_provider",
            "label": "Sovereign/local provider available",
            "status": "pass" if sovereign else "warn",
            "evidence": f"{len(local_models)} local models",
            "hard_block": False,
        })
    elif goal_key == "research":
        for cap in ("reasoning_deep", "long_context"):
            row = next(item for item in matrix if item["id"] == cap)
            checks.append({
                "id": cap,
                "label": f"{cap} available",
                "status": "pass" if row["model_count"] else "warn",
                "evidence": f"{row['model_count']} models",
                "hard_block": False,
            })
    else:
        covered = sum(1 for row in matrix if row["model_count"] > 0)
        checks.append({
            "id": "diverse_capabilities",
            "label": "Diverse capabilities",
            "status": "pass" if covered >= 6 else "warn",
            "evidence": f"{covered}/{len(matrix)} capabilities",
            "hard_block": False,
        })

    hard_blocks = [check for check in checks if check["status"] == "fail" and check.get("hard_block")]
    soft_warnings = [check for check in checks if check["status"] in {"warn", "fail"} and not check.get("hard_block")]
    return {
        "goal": goal_key,
        "checks": checks,
        "hard_blocks": hard_blocks,
        "soft_warnings": soft_warnings,
        "accepted": not hard_blocks,
        "score": {
            "passed": sum(1 for check in checks if check["status"] == "pass"),
            "total": len(checks),
        },
    }


def _build_snapshot(goal: str = "mixed") -> dict[str, Any]:
    provider_data = _provider_snapshot()
    matrix = _capability_matrix(provider_data["models"])
    gaps = _gap_recommendations(matrix)
    chains = _priority_chains(matrix)
    snapshot = {
        **provider_data,
        "capability_definitions": CAPABILITY_DEFINITIONS,
        "capability_matrix": matrix,
        "gaps": gaps,
        "priority_chains": chains,
        "local_install_suggestions": LOCAL_INSTALL_SUGGESTIONS,
        "acquisition_advisor": _acquisition_advisor(gaps, matrix),
        "health_levels": ["healthy", "degraded", "quota_risk", "unavailable", "not_configured"],
        "quota_thresholds": {"warn_pct": 75, "soft_limit_pct": 90, "hard_limit_pct": 100},
        "generated_at": time.time(),
    }
    snapshot["acceptance"] = _acceptance(snapshot, goal=goal)
    return snapshot


def _council_candidate_score(model: dict[str, Any], role: str) -> float:
    text = f"{model.get('provider')} {model.get('model_id')}".lower()
    score = float(max((model.get("capabilities") or {}).values(), default=0)) / 10.0
    if model.get("kind") == "local":
        score += 0.8
    if role in {"architect", "planner"} and any(needle in text for needle in ("72b", "70b", "30b", "20b", "opus", "sonnet", "gpt-5", "qwen")):
        score += 2.0
    if role == "executor" and any(needle in text for needle in ("coder", "code", "qwen", "deepseek", "gpt-oss", "llama")):
        score += 2.0
    if role in {"critic", "security_sentinel"} and any(needle in text for needle in ("claude", "sonnet", "mistral", "qwen", "deepseek", "gpt")):
        score += 1.6
    if role == "verifier" and any(needle in text for needle in ("bielik", "pllum", "phi", "gemma", "mistral")):
        score += 1.8
    if role == "cost_sentinel" and model.get("kind") == "local":
        score += 2.4
    return score


def _ensure_registry_model(model: dict[str, Any]) -> None:
    model_id = str(model.get("model_id") or "")
    provider = str(model.get("provider") or "")
    if not model_id or not provider:
        return
    try:
        if _get_registry().get_model(model_id):
            return
        _get_registry().register_model(
            model_id=model_id,
            provider=provider,
            display_name=str(model.get("display_name") or model_id),
            config_json=json.dumps({
                "runtime_type": "local" if model.get("kind") == "local" else "external",
                "base_url": model.get("endpoint") or "",
                "source": "provider_catalog_council_auto_arrange",
            }, sort_keys=True),
        )
    except Exception:
        return


def _hierarchy_from_members(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        members,
        key=lambda item: (
            RANK_LEVEL.get(str(item.get("rank") or "primary"), 9),
            int(item.get("priority") or 0),
            -float(item.get("voting_weight") or 1.0),
            str(item.get("member_id") or ""),
        ),
    )
    total_weight = sum(max(0.0, float(item.get("voting_weight") or 0.0)) for item in ordered) or 1.0
    return [
        {
            "level": index,
            "label": f"R{index}",
            "member_id": item.get("member_id"),
            "model_id": item.get("model_id"),
            "role": item.get("role"),
            "rank": item.get("rank") or "primary",
            "priority": int(item.get("priority") or 0),
            "voting_weight": float(item.get("voting_weight") or 1.0),
            "influence_percent": round((float(item.get("voting_weight") or 1.0) / total_weight) * 100, 1),
            "task_types": [
                part.strip()
                for part in str(item.get("specialization") or item.get("role") or "").split(",")
                if part.strip()
            ],
        }
        for index, item in enumerate(ordered, start=1)
    ]


def _auto_arrange_council(force: bool = False, max_members: int = 7) -> dict[str, Any]:
    snapshot = _build_snapshot()
    candidates = [model for model in snapshot["models"] if model.get("configured")]
    if not candidates:
        raise ValueError("no configured local/API models available")

    vault = _get_vault()
    existing = vault.list_council_members()
    existing_ids = {str(item.get("member_id") or "") for item in existing}
    used_models = {str(item.get("model_id") or "") for item in existing if item.get("model_id")}
    configured: list[dict[str, Any]] = []

    for blueprint in COUNCIL_ROLE_BLUEPRINTS[: max(1, min(int(max_members or 7), len(COUNCIL_ROLE_BLUEPRINTS)))]:
        member_id = str(blueprint["member_id"])
        if member_id in existing_ids and not force:
            continue
        role = str(blueprint["role"])
        ranked = sorted(candidates, key=lambda item: _council_candidate_score(item, role), reverse=True)
        selected = next((item for item in ranked if str(item.get("model_id") or "") not in used_models), ranked[0])
        _ensure_registry_model(selected)
        used_models.add(str(selected.get("model_id") or ""))
        configured.append(
            vault.configure_council_member(
                member_id,
                str(selected["model_id"]),
                role,
                int(blueprint["priority"]),
                None,
                rank=str(blueprint["rank"]),
                voting_weight=float(blueprint["voting_weight"]),
                specialization=str(blueprint["specialization"]),
                max_tokens=int(blueprint["max_tokens"]),
            )
        )

    members = vault.list_council_members()
    hierarchy = vault.upsert_hierarchy(
        "AEIS default model council",
        _hierarchy_from_members(members),
        is_active=True,
    )
    return {
        "configured": configured,
        "members": members,
        "hierarchy": hierarchy,
        "summary": {
            "configured_count": len(configured),
            "member_count": len(members),
            "candidate_count": len(candidates),
            "force": force,
        },
    }


@router.get("")
def get_provider_catalog(goal: str = "mixed") -> dict[str, Any]:
    return _build_snapshot(goal=goal)


@router.get("/templates")
def list_provider_templates() -> dict[str, Any]:
    return {
        "templates": PROVIDER_TEMPLATES,
        "custom_template": CUSTOM_PROVIDER_TEMPLATE,
        "count": len(PROVIDER_TEMPLATES),
    }


@router.get("/capabilities")
def list_capabilities() -> dict[str, Any]:
    return {"capabilities": CAPABILITY_DEFINITIONS}


@router.post("/refresh-local")
def refresh_local_detection() -> dict[str, Any]:
    local = _probe_local_endpoints()
    return {
        "local_detection": local,
        "detected_model_count": sum(len(item.get("models") or []) for item in local.values()),
        "checked_at": time.time(),
    }


@router.post("/benchmark")
def benchmark_provider_model(body: BenchmarkRequest) -> dict[str, Any]:
    try:
        from sylion.api.ai_providers_routes import ProviderTestRequest, test_provider

        return test_provider(
            body.provider,
            ProviderTestRequest(
                prompt=body.prompt,
                model=body.model or None,
                max_tokens=max(1, min(int(body.max_tokens or 32), 512)),
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)[:300])


@router.post("/council/auto-arrange")
def auto_arrange_council(body: AutoArrangeCouncilRequest | None = None) -> dict[str, Any]:
    request = body or AutoArrangeCouncilRequest()
    try:
        return _auto_arrange_council(force=request.force, max_members=request.max_members)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/council/rebuild-hierarchy")
def rebuild_council_hierarchy() -> dict[str, Any]:
    members = _get_vault().list_council_members()
    hierarchy = _get_vault().upsert_hierarchy(
        "AEIS default model council",
        _hierarchy_from_members(members),
        is_active=True,
    )
    return {"members": members, "hierarchy": hierarchy}


@router.post("/custom-provider")
def create_custom_provider(body: CustomProviderRequest) -> dict[str, Any]:
    provider_id = body.provider_id.strip().lower()
    model_id = body.model_id.strip()
    base_url = body.base_url.strip()
    if not provider_id or not model_id or not base_url:
        raise HTTPException(status_code=422, detail="provider_id, model_id and base_url are required")

    key_id = ""
    if body.api_key and body.api_key.strip():
        stored = _get_vault().store_key(
            provider_id,
            body.api_key.strip(),
            display_name=body.display_name or f"{provider_id} key",
            metadata={"source": "provider_catalog_custom_provider", "base_url": base_url},
        )
        key_id = stored.get("key_id", "")
        _get_vault().activate_key(key_id)

    capabilities = body.capabilities or ["text_generation"]
    config = {
        "runtime_type": "external",
        "base_url": base_url,
        "provider_kind": "custom",
        "capabilities": capabilities,
        "source": "provider_catalog_custom_provider",
    }
    model = _get_registry().register_model(
        model_id=model_id,
        provider=provider_id,
        display_name=body.display_name or model_id,
        config_json=json.dumps(config, sort_keys=True),
    )
    for capability in capabilities:
        try:
            _get_registry().add_capability(
                model_id,
                capability,
                json.dumps({"source": "provider_catalog_custom_provider"}),
            )
        except Exception:
            pass
    return {
        "provider_id": provider_id,
        "model": model,
        "key_id": key_id,
        "status": "configured",
    }


@router.get("/acceptance")
def get_phase2_acceptance(goal: str = "mixed") -> dict[str, Any]:
    snapshot = _build_snapshot(goal=goal)
    return snapshot["acceptance"]
