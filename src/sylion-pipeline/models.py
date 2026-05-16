#!/usr/bin/env python3
"""
SYLION Model Registry — Multi-Model AI Management

Central registry for all AI models used in the pipeline.
Supports per-agent model assignment, multi-model verification,
model switching at runtime, and capability-based routing.

Models supported:
  - Claude (Anthropic): Sonnet, Opus, Haiku
  - GPT (OpenAI): GPT-5, GPT-5.4, GPT-5.4 Mini, o3
  - Gemini (Google): Pro, Flash, Ultra
  - Grok (xAI): Grok-3, Grok-3-mini
  - DeepSeek: V3, R1
  - Perplexity: Sonar Pro, Sonar (online search)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

log = logging.getLogger("models")


# ---------------------------------------------------------------------------
# Model Capabilities
# ---------------------------------------------------------------------------

class Capability(str, Enum):
    """What a model can do."""
    CODE_AUDIT      = "code_audit"       # Deep code analysis
    CODE_GENERATION = "code_generation"  # Write/patch code
    REASONING       = "reasoning"        # Complex multi-step logic
    SECURITY        = "security"         # Security-specific knowledge
    WEB_SEARCH      = "web_search"       # Real-time internet search
    LONG_CONTEXT    = "long_context"     # 100k+ token context
    FAST            = "fast"             # Low latency responses
    CHEAP           = "cheap"            # Low cost per token
    MULTILINGUAL    = "multilingual"     # Strong non-English support
    TOOL_USE        = "tool_use"         # Function calling / tool use
    VISION          = "vision"           # Image understanding
    STRUCTURED      = "structured"       # JSON / structured output


class Provider(str, Enum):
    """Model provider."""
    ANTHROPIC   = "anthropic"
    OPENAI      = "openai"
    GOOGLE      = "google"
    XAI         = "xai"
    DEEPSEEK    = "deepseek"
    PERPLEXITY  = "perplexity"
    OLLAMA      = "ollama"


# ---------------------------------------------------------------------------
# Model Definition
# ---------------------------------------------------------------------------

@dataclass
class ModelDef:
    """Full definition of an AI model."""
    id: str                              # Unique identifier (e.g. "claude-sonnet")
    provider: Provider
    model_id: str                        # API model name (e.g. "claude-sonnet-4-20250514")
    display_name: str                    # Human-readable name
    capabilities: list[Capability]
    api_key_env: str                     # Environment variable for API key
    base_url: str | None = None          # Custom API endpoint
    max_tokens: int = 8192              # Default max output tokens
    context_window: int = 200000        # Context window size
    cost_per_1m_input: float = 0.0      # Cost per 1M input tokens (USD)
    cost_per_1m_output: float = 0.0     # Cost per 1M output tokens (USD)
    rate_limit_rpm: int = 60            # Requests per minute
    supports_streaming: bool = True
    supports_tools: bool = True
    notes: str = ""                      # Special notes / caveats

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def has_capability(self, cap: Capability) -> bool:
        return cap in self.capabilities


# ---------------------------------------------------------------------------
# Model Registry — all supported models
# ---------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, ModelDef] = {}


def _register(m: ModelDef):
    MODEL_REGISTRY[m.id] = m
    return m


# ═══════════════════════════════════════════
# ANTHROPIC (Claude)
# ═══════════════════════════════════════════

_register(ModelDef(
    id="claude-sonnet",
    provider=Provider.ANTHROPIC,
    model_id="claude-sonnet-4-20250514",
    display_name="Claude Sonnet 4",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.SECURITY, Capability.LONG_CONTEXT, Capability.TOOL_USE,
        Capability.STRUCTURED, Capability.MULTILINGUAL, Capability.VISION,
    ],
    api_key_env="ANTHROPIC_API_KEY",
    context_window=200000,
    cost_per_1m_input=3.0,
    cost_per_1m_output=15.0,
    notes="Primary model — best for code audit and security analysis",
))

_register(ModelDef(
    id="claude-opus",
    provider=Provider.ANTHROPIC,
    model_id="claude-opus-4-20250514",
    display_name="Claude Opus 4",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.SECURITY, Capability.LONG_CONTEXT, Capability.TOOL_USE,
        Capability.STRUCTURED, Capability.MULTILINGUAL, Capability.VISION,
    ],
    api_key_env="ANTHROPIC_API_KEY",
    context_window=200000,
    cost_per_1m_input=15.0,
    cost_per_1m_output=75.0,
    notes="Most capable — use for critical decisions and complex reasoning",
))

_register(ModelDef(
    id="claude-haiku",
    provider=Provider.ANTHROPIC,
    model_id="claude-haiku-3-5-20250120",
    display_name="Claude Haiku 3.5",
    capabilities=[
        Capability.CODE_GENERATION, Capability.FAST, Capability.CHEAP,
        Capability.TOOL_USE, Capability.STRUCTURED,
    ],
    api_key_env="ANTHROPIC_API_KEY",
    context_window=200000,
    cost_per_1m_input=0.80,
    cost_per_1m_output=4.0,
    notes="Fast & cheap — good for quick verification and simple tasks",
))

# ═══════════════════════════════════════════
# OPENAI (GPT)
# ═══════════════════════════════════════════

_register(ModelDef(
    id="gpt-5",
    provider=Provider.OPENAI,
    model_id="gpt-5",
    display_name="GPT-5",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.SECURITY, Capability.LONG_CONTEXT, Capability.TOOL_USE,
        Capability.STRUCTURED, Capability.MULTILINGUAL, Capability.VISION,
    ],
    api_key_env="OPENAI_API_KEY",
    context_window=256000,
    cost_per_1m_input=2.0,
    cost_per_1m_output=8.0,
    notes="Strong at API security, input validation, injection patterns",
))

_register(ModelDef(
    id="gpt-5.4",
    provider=Provider.OPENAI,
    model_id="gpt-5.4",
    display_name="GPT-5.4",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.SECURITY, Capability.LONG_CONTEXT, Capability.TOOL_USE,
        Capability.STRUCTURED, Capability.MULTILINGUAL, Capability.VISION,
    ],
    api_key_env="OPENAI_API_KEY",
    context_window=1000000,
    cost_per_1m_input=2.0,
    cost_per_1m_output=8.0,
    notes="Latest GPT — 1M context, strong at code audit and security analysis",
))

_register(ModelDef(
    id="o3",
    provider=Provider.OPENAI,
    model_id="o3",
    display_name="o3 (reasoning)",
    capabilities=[
        Capability.REASONING, Capability.CODE_AUDIT, Capability.SECURITY,
        Capability.TOOL_USE, Capability.STRUCTURED,
    ],
    api_key_env="OPENAI_API_KEY",
    context_window=200000,
    cost_per_1m_input=2.0,
    cost_per_1m_output=8.0,
    notes="Deep reasoning model — use for complex security analysis",
))

_register(ModelDef(
    id="gpt-5.4-mini",
    provider=Provider.OPENAI,
    model_id="gpt-5.4-mini",
    display_name="GPT-5.4 Mini",
    capabilities=[
        Capability.CODE_GENERATION, Capability.FAST, Capability.CHEAP,
        Capability.TOOL_USE, Capability.STRUCTURED, Capability.LONG_CONTEXT,
    ],
    api_key_env="OPENAI_API_KEY",
    context_window=1000000,
    cost_per_1m_input=0.40,
    cost_per_1m_output=1.60,
    notes="Fast & cheap GPT-5.4 — 1M context, verification and bulk tasks",
))

# ═══════════════════════════════════════════
# GOOGLE (Gemini)
# ═══════════════════════════════════════════

_register(ModelDef(
    id="gemini-pro",
    provider=Provider.GOOGLE,
    model_id="gemini-2.5-pro-preview-06-05",
    display_name="Gemini 2.5 Pro",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.SECURITY, Capability.LONG_CONTEXT, Capability.TOOL_USE,
        Capability.STRUCTURED, Capability.MULTILINGUAL, Capability.VISION,
    ],
    api_key_env="GOOGLE_API_KEY",
    context_window=1000000,
    cost_per_1m_input=1.25,
    cost_per_1m_output=10.0,
    notes="1M context, strong at concurrency and race conditions",
))

_register(ModelDef(
    id="gemini-flash",
    provider=Provider.GOOGLE,
    model_id="gemini-2.5-flash-preview-05-20",
    display_name="Gemini 2.5 Flash",
    capabilities=[
        Capability.CODE_GENERATION, Capability.FAST, Capability.CHEAP,
        Capability.TOOL_USE, Capability.STRUCTURED, Capability.LONG_CONTEXT,
    ],
    api_key_env="GOOGLE_API_KEY",
    context_window=1000000,
    cost_per_1m_input=0.15,
    cost_per_1m_output=0.60,
    notes="Cheapest option with 1M context — bulk verification",
))

# ═══════════════════════════════════════════
# xAI (Grok)
# ═══════════════════════════════════════════

_register(ModelDef(
    id="grok-3",
    provider=Provider.XAI,
    model_id="grok-3",
    display_name="Grok 3",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.WEB_SEARCH, Capability.TOOL_USE, Capability.STRUCTURED,
    ],
    api_key_env="XAI_API_KEY",
    base_url="https://api.x.ai/v1",
    context_window=131072,
    cost_per_1m_input=3.0,
    cost_per_1m_output=15.0,
    notes="Has built-in web search via X/Twitter — good for CVE lookups",
))

_register(ModelDef(
    id="grok-3-mini",
    provider=Provider.XAI,
    model_id="grok-3-mini",
    display_name="Grok 3 Mini",
    capabilities=[
        Capability.CODE_GENERATION, Capability.FAST, Capability.CHEAP,
        Capability.REASONING, Capability.WEB_SEARCH,
    ],
    api_key_env="XAI_API_KEY",
    base_url="https://api.x.ai/v1",
    context_window=131072,
    cost_per_1m_input=0.30,
    cost_per_1m_output=0.50,
    notes="Fast Grok with web search — verification & CVE checks",
))

# ═══════════════════════════════════════════
# DEEPSEEK
# ═══════════════════════════════════════════

_register(ModelDef(
    id="deepseek-v3",
    provider=Provider.DEEPSEEK,
    model_id="deepseek-chat",
    display_name="DeepSeek V3",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.CHEAP, Capability.TOOL_USE, Capability.STRUCTURED,
    ],
    api_key_env="DEEPSEEK_API_KEY",
    base_url="https://api.deepseek.com/v1",
    context_window=128000,
    cost_per_1m_input=0.27,
    cost_per_1m_output=1.10,
    notes="Very cheap — good for bulk verification passes",
))

_register(ModelDef(
    id="deepseek-r1",
    provider=Provider.DEEPSEEK,
    model_id="deepseek-reasoner",
    display_name="DeepSeek R1 (reasoning)",
    capabilities=[
        Capability.REASONING, Capability.CODE_AUDIT, Capability.SECURITY,
    ],
    api_key_env="DEEPSEEK_API_KEY",
    base_url="https://api.deepseek.com/v1",
    context_window=128000,
    cost_per_1m_input=0.55,
    cost_per_1m_output=2.19,
    notes="Reasoning model — deep analysis, slower but thorough",
))

# ═══════════════════════════════════════════
# OLLAMA (Local Models)
# ═══════════════════════════════════════════

_register(ModelDef(
    id="ollama-llama3",
    provider=Provider.OLLAMA,
    model_id="ollama_chat/llama3",
    display_name="Llama 3 (Ollama, local)",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.STRUCTURED, Capability.MULTILINGUAL,
    ],
    api_key_env="OLLAMA_API_KEY",
    base_url=os.environ.get("OLLAMA_API_BASE", "http://localhost:11434"),
    context_window=131072,
    cost_per_1m_input=0.0,
    cost_per_1m_output=0.0,
    rate_limit_rpm=999,
    supports_streaming=True,
    supports_tools=False,  # ollama_chat supports tools, but litellm integration is flaky
    notes="Local model — zero API cost, full data privacy. Requires Ollama running locally.",
))

_register(ModelDef(
    id="ollama-llama3-70b",
    provider=Provider.OLLAMA,
    model_id="ollama_chat/llama3:70b",
    display_name="Llama 3 70B (Ollama, local)",
    capabilities=[
        Capability.CODE_AUDIT, Capability.CODE_GENERATION, Capability.REASONING,
        Capability.SECURITY, Capability.STRUCTURED, Capability.MULTILINGUAL,
    ],
    api_key_env="OLLAMA_API_KEY",
    base_url=os.environ.get("OLLAMA_API_BASE", "http://localhost:11434"),
    context_window=131072,
    cost_per_1m_input=0.0,
    cost_per_1m_output=0.0,
    rate_limit_rpm=999,
    supports_streaming=True,
    supports_tools=False,
    notes="Large local model — stronger reasoning, requires ~40GB VRAM. Zero API cost.",
))

# ═══════════════════════════════════════════
# PERPLEXITY (Online Search)
# ═══════════════════════════════════════════

_register(ModelDef(
    id="perplexity-sonar-pro",
    provider=Provider.PERPLEXITY,
    model_id="sonar-pro",
    display_name="Perplexity Sonar Pro",
    capabilities=[
        Capability.WEB_SEARCH, Capability.REASONING, Capability.STRUCTURED,
    ],
    api_key_env="PERPLEXITY_API_KEY",
    base_url="https://api.perplexity.ai",
    context_window=200000,
    cost_per_1m_input=3.0,
    cost_per_1m_output=15.0,
    notes="Online search — CVE databases, security advisories, latest vulns",
))

_register(ModelDef(
    id="perplexity-sonar",
    provider=Provider.PERPLEXITY,
    model_id="sonar",
    display_name="Perplexity Sonar",
    capabilities=[
        Capability.WEB_SEARCH, Capability.FAST, Capability.CHEAP,
    ],
    api_key_env="PERPLEXITY_API_KEY",
    base_url="https://api.perplexity.ai",
    context_window=128000,
    cost_per_1m_input=1.0,
    cost_per_1m_output=1.0,
    notes="Fast online search — quick CVE lookups, advisory checks",
))


# ---------------------------------------------------------------------------
# Model Router — intelligent model selection
# ---------------------------------------------------------------------------

class ModelRouter:
    """Routes tasks to the best model based on capabilities and availability."""

    def __init__(self):
        self.registry = MODEL_REGISTRY
        self._usage: dict[str, dict] = {}  # Track usage per model

    def get_available_models(self) -> list[ModelDef]:
        """Get all models with valid API keys."""
        return [m for m in self.registry.values() if m.is_available]

    def get_model(self, model_id: str) -> ModelDef | None:
        """Get a specific model by ID."""
        return self.registry.get(model_id)

    def get_by_provider(self, provider: Provider) -> list[ModelDef]:
        """Get all models from a provider."""
        return [m for m in self.registry.values()
                if m.provider == provider and m.is_available]

    def get_by_capability(self, cap: Capability) -> list[ModelDef]:
        """Get all available models with a specific capability."""
        return [m for m in self.get_available_models() if m.has_capability(cap)]

    def get_search_models(self) -> list[ModelDef]:
        """Get models capable of web search."""
        return self.get_by_capability(Capability.WEB_SEARCH)

    def get_cheap_models(self) -> list[ModelDef]:
        """Get cheap models for bulk verification."""
        return self.get_by_capability(Capability.CHEAP)

    def best_for_task(self, required: list[Capability],
                      preferred: list[Capability] | None = None,
                      exclude: list[str] | None = None,
                      max_cost_per_1m: float | None = None) -> ModelDef | None:
        """Select the best model for a task based on capabilities."""
        candidates = self.get_available_models()

        # Filter by exclusions
        if exclude:
            candidates = [m for m in candidates if m.id not in exclude]

        # Filter by required capabilities
        candidates = [m for m in candidates
                      if all(m.has_capability(r) for r in required)]

        # Filter by cost
        if max_cost_per_1m is not None:
            candidates = [m for m in candidates
                          if m.cost_per_1m_output <= max_cost_per_1m]

        if not candidates:
            return None

        # Score by preferred capabilities
        if preferred:
            def score(m: ModelDef) -> int:
                return sum(1 for p in preferred if m.has_capability(p))
            candidates.sort(key=score, reverse=True)

        return candidates[0]

    def get_verification_models(self, primary_model: str,
                                count: int = 3) -> list[ModelDef]:
        """Get models for cross-verification (different from primary).
        
        Strategy: pick from different providers for maximum diversity.
        """
        primary = self.get_model(primary_model)
        if not primary:
            return self.get_available_models()[:count]

        candidates = [m for m in self.get_available_models()
                      if m.id != primary_model
                      and m.has_capability(Capability.CODE_AUDIT)]

        # Prefer different providers
        seen_providers = {primary.provider}
        result = []
        for m in candidates:
            if m.provider not in seen_providers:
                result.append(m)
                seen_providers.add(m.provider)
            if len(result) >= count:
                break

        # Fill remaining from any provider
        if len(result) < count:
            remaining = [m for m in candidates if m not in result]
            result.extend(remaining[:count - len(result)])

        return result[:count]

    def track_usage(self, model_id: str, input_tokens: int,
                    output_tokens: int, elapsed_ms: int):
        """Track model usage for cost and performance analysis."""
        model = self.get_model(model_id)
        if not model:
            return
        if model_id not in self._usage:
            self._usage[model_id] = {
                "calls": 0, "input_tokens": 0, "output_tokens": 0,
                "total_cost": 0.0, "total_ms": 0,
            }
        u = self._usage[model_id]
        u["calls"] += 1
        u["input_tokens"] += input_tokens
        u["output_tokens"] += output_tokens
        u["total_ms"] += elapsed_ms
        u["total_cost"] += (
            (input_tokens / 1_000_000) * model.cost_per_1m_input +
            (output_tokens / 1_000_000) * model.cost_per_1m_output
        )

    def get_usage_report(self) -> dict:
        """Get usage report for all models."""
        return {mid: {**u, "model": self.registry[mid].display_name}
                for mid, u in self._usage.items()}


# ---------------------------------------------------------------------------
# Multi-Model Verifier
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Result of multi-model verification."""
    task_hash: str
    primary_model: str
    primary_response: str
    verifications: list[dict] = field(default_factory=list)
    consensus: bool = False
    confidence: float = 0.0
    discrepancies: list[str] = field(default_factory=list)

    @property
    def agreement_ratio(self) -> float:
        if not self.verifications:
            return 0.0
        agrees = sum(1 for v in self.verifications if v.get("agrees", False))
        return agrees / len(self.verifications)


class MultiModelVerifier:
    """Verifies agent outputs across multiple AI models.
    
    Workflow:
    1. Agent produces output with primary model
    2. Verifier sends output to N other models asking "is this correct?"
    3. Collects votes, discrepancies, and confidence scores
    4. Returns consensus result
    """

    def __init__(self, router: ModelRouter, min_agreement: float = 0.66):
        self.router = router
        self.min_agreement = min_agreement
        self.results_cache: dict[str, VerificationResult] = {}

    def _task_hash(self, task: str, response: str) -> str:
        """Hash task+response for caching."""
        content = f"{task}|||{response}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def verify(self, task: str, primary_response: str,
                     primary_model: str,
                     verify_models: list[str] | None = None,
                     verify_count: int = 3,
                     context: str = "") -> VerificationResult:
        """Verify a response across multiple models.
        
        Args:
            task: Original task description
            primary_response: Response to verify
            primary_model: Model that generated the response
            verify_models: Specific models to use (or auto-select)
            verify_count: Number of verification models
            context: Additional context for verifiers
        """
        task_hash = self._task_hash(task, primary_response)

        # Check cache
        if task_hash in self.results_cache:
            return self.results_cache[task_hash]

        # Select verification models
        if verify_models:
            models = [self.router.get_model(m) for m in verify_models]
            models = [m for m in models if m is not None and m.is_available]
        else:
            models = self.router.get_verification_models(
                primary_model, count=verify_count
            )

        if not models:
            log.warning("No verification models available — skipping verification")
            return VerificationResult(
                task_hash=task_hash,
                primary_model=primary_model,
                primary_response=primary_response,
                consensus=True,
                confidence=0.5,
            )

        # Build verification prompt
        verify_prompt = f"""You are a verification agent. Another AI model has analyzed a task 
and produced a response. Your job is to independently verify the correctness.

## Original Task
{task}

{f'## Additional Context{chr(10)}{context}' if context else ''}

## Response to Verify (from {primary_model})
{primary_response}

## Your Verification
Analyze the response and provide:
1. "agrees": true/false — do you agree with the main conclusions?
2. "confidence": 0.0-1.0 — how confident are you?
3. "issues": [] — list any errors, omissions, or disagreements
4. "additions": [] — anything the original response missed
5. "reasoning": brief explanation of your assessment

Respond in JSON format only."""

        # Run verifications in parallel
        async def verify_single(model: ModelDef) -> dict:
            """Single model verification (placeholder for actual API call)."""
            # In production, this calls the actual LLM API
            # Here we return the structure for the orchestrator to fill
            return {
                "model": model.id,
                "model_name": model.display_name,
                "provider": model.provider.value,
                "prompt": verify_prompt,
                "status": "pending",
                "agrees": None,
                "confidence": 0.0,
                "issues": [],
                "additions": [],
                "reasoning": "",
            }

        verifications = await asyncio.gather(
            *[verify_single(m) for m in models],
            return_exceptions=True,
        )

        # Filter out exceptions
        valid = [v for v in verifications if isinstance(v, dict)]

        result = VerificationResult(
            task_hash=task_hash,
            primary_model=primary_model,
            primary_response=primary_response,
            verifications=valid,
        )

        self.results_cache[task_hash] = result
        return result


# ---------------------------------------------------------------------------
# Online Search Agent — Perplexity + Grok parallel search
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """Result from online search."""
    query: str
    model: str
    results: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    summary: str = ""
    raw_response: str = ""


class OnlineSearchAgent:
    """Parallel web search using Perplexity and Grok.
    
    Use cases in SYLION pipeline:
    - CVE lookup for discovered vulnerabilities
    - Latest security advisories for dependencies
    - Best practices validation
    - Compliance requirement verification
    - srsRAN / SDR documentation lookup
    """

    def __init__(self, router: ModelRouter):
        self.router = router
        self.cache: dict[str, list[SearchResult]] = {}

    def get_search_models(self) -> list[ModelDef]:
        """Get available search-capable models."""
        return self.router.get_search_models()

    async def search(self, query: str,
                     context: str = "",
                     models: list[str] | None = None) -> list[SearchResult]:
        """Search the web using multiple models in parallel.
        
        Returns results from each model for comparison.
        """
        if query in self.cache:
            return self.cache[query]

        if models:
            search_models = [self.router.get_model(m) for m in models]
            search_models = [m for m in search_models
                            if m is not None and m.is_available]
        else:
            search_models = self.get_search_models()

        if not search_models:
            log.warning("No search models available")
            return []

        search_prompt = f"""Search the web for the latest information about:

{query}

{f'Context: {context}' if context else ''}

Provide:
1. Direct answer with specific details
2. Sources (URLs) for each claim
3. Date of information (when was this published/updated)
4. Relevance to security auditing

Format as JSON with fields: summary, findings[], sources[]"""

        async def search_single(model: ModelDef) -> SearchResult:
            """Search with a single model."""
            return SearchResult(
                query=query,
                model=model.id,
                summary=f"[Pending search via {model.display_name}]",
                raw_response=search_prompt,
            )

        results = await asyncio.gather(
            *[search_single(m) for m in search_models],
            return_exceptions=True,
        )

        valid = [r for r in results if isinstance(r, SearchResult)]
        self.cache[query] = valid
        return valid

    async def search_cve(self, cve_id: str) -> list[SearchResult]:
        """Search for a specific CVE."""
        return await self.search(
            f"CVE {cve_id} vulnerability details affected versions patch",
            context="Security audit — need severity, affected software, and patches",
        )

    async def search_dependency(self, dep: str, version: str) -> list[SearchResult]:
        """Search for known vulnerabilities in a dependency."""
        return await self.search(
            f"{dep} {version} security vulnerabilities known issues",
            context="Dependency audit — checking for known security issues",
        )

    async def search_best_practice(self, topic: str) -> list[SearchResult]:
        """Search for current security best practices."""
        return await self.search(
            f"{topic} security best practices 2025 2026 recommendations",
            context="Validating implementation against current best practices",
        )


# ---------------------------------------------------------------------------
# Agent Memory / Learning System
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """A single memory entry for agent learning."""
    id: str
    agent_name: str
    category: str                        # "finding", "false_positive", "pattern", "preference"
    content: str
    confidence: float = 1.0
    created_at: str = ""
    used_count: int = 0
    last_used: str = ""
    source_models: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentMemory:
    """Persistent memory system for agent learning.
    
    Agents remember:
    - Patterns that led to true positive findings
    - False positives to avoid in future runs
    - Preferred code patterns in the SYLION codebase
    - Model-specific strengths (which model finds what)
    - Successful patches and their patterns
    - Search results worth caching
    """

    MEMORY_DIR = Path(__file__).parent / "memory"

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.entries: dict[str, MemoryEntry] = {}
        self.memory_file = self.MEMORY_DIR / f"{agent_name}.json"
        self.load()

    def load(self):
        """Load memory from disk."""
        if not self.memory_file.exists():
            return
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for entry_data in raw.get("entries", []):
                entry = MemoryEntry(**entry_data)
                self.entries[entry.id] = entry
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            log.warning(f"Failed to load memory for {self.agent_name}: {e}")

    def save(self):
        """Save memory to disk."""
        self.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "agent_name": self.agent_name,
            "entry_count": len(self.entries),
            "entries": [
                {
                    "id": e.id, "agent_name": e.agent_name,
                    "category": e.category, "content": e.content,
                    "confidence": e.confidence, "created_at": e.created_at,
                    "used_count": e.used_count, "last_used": e.last_used,
                    "source_models": e.source_models, "tags": e.tags,
                    "metadata": e.metadata,
                }
                for e in self.entries.values()
            ],
        }
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def remember(self, category: str, content: str,
                 confidence: float = 1.0,
                 source_models: list[str] | None = None,
                 tags: list[str] | None = None,
                 metadata: dict | None = None) -> str:
        """Store a new memory entry."""
        from datetime import datetime, timezone
        entry_id = hashlib.sha256(
            f"{self.agent_name}:{category}:{content}".encode()
        ).hexdigest()[:12]

        if entry_id in self.entries:
            # Update existing
            self.entries[entry_id].used_count += 1
            self.entries[entry_id].confidence = max(
                self.entries[entry_id].confidence, confidence
            )
            if source_models:
                existing = set(self.entries[entry_id].source_models)
                existing.update(source_models)
                self.entries[entry_id].source_models = list(existing)
        else:
            self.entries[entry_id] = MemoryEntry(
                id=entry_id,
                agent_name=self.agent_name,
                category=category,
                content=content,
                confidence=confidence,
                created_at=datetime.now(timezone.utc).isoformat(),
                source_models=source_models or [],
                tags=tags or [],
                metadata=metadata or {},
            )

        self.save()
        return entry_id

    def recall(self, category: str | None = None,
               tags: list[str] | None = None,
               min_confidence: float = 0.5,
               limit: int = 50) -> list[MemoryEntry]:
        """Recall memories matching criteria."""
        from datetime import datetime, timezone
        results = list(self.entries.values())

        if category:
            results = [e for e in results if e.category == category]
        if tags:
            tag_set = set(tags)
            results = [e for e in results if tag_set & set(e.tags)]

        results = [e for e in results if e.confidence >= min_confidence]
        results.sort(key=lambda e: (e.confidence, e.used_count), reverse=True)

        # Update last_used
        now = datetime.now(timezone.utc).isoformat()
        for e in results[:limit]:
            e.last_used = now
            e.used_count += 1

        self.save()
        return results[:limit]

    def forget(self, entry_id: str) -> bool:
        """Remove a memory entry (e.g., outdated false positive)."""
        if entry_id in self.entries:
            del self.entries[entry_id]
            self.save()
            return True
        return False

    def remember_false_positive(self, file: str, line: int,
                                 finding_type: str, reason: str,
                                 models: list[str]):
        """Remember a false positive to avoid in future runs."""
        self.remember(
            category="false_positive",
            content=f"{file}:{line} — {finding_type}: {reason}",
            confidence=1.0,
            source_models=models,
            tags=["false_positive", finding_type],
            metadata={"file": file, "line": line, "type": finding_type},
        )

    def remember_true_positive(self, file: str, line: int,
                                finding_type: str, severity: str,
                                models: list[str]):
        """Remember a confirmed finding pattern."""
        self.remember(
            category="finding",
            content=f"{file}:{line} — {finding_type} [{severity}]",
            confidence=1.0,
            source_models=models,
            tags=["true_positive", finding_type, severity],
            metadata={"file": file, "line": line, "type": finding_type,
                      "severity": severity},
        )

    def remember_pattern(self, pattern: str, description: str,
                          models: list[str]):
        """Remember a code pattern (good or bad)."""
        self.remember(
            category="pattern",
            content=f"{pattern}: {description}",
            source_models=models,
            tags=["pattern"],
        )

    def get_false_positives(self, file: str | None = None) -> list[MemoryEntry]:
        """Get known false positives, optionally filtered by file."""
        fps = self.recall(category="false_positive")
        if file:
            fps = [e for e in fps if e.metadata.get("file") == file]
        return fps

    def get_known_patterns(self) -> list[MemoryEntry]:
        """Get all known code patterns."""
        return self.recall(category="pattern")

    def export_context(self, max_entries: int = 20) -> str:
        """Export memory as context string for agent prompts."""
        lines = [f"## Agent Memory — {self.agent_name}",
                 f"Entries: {len(self.entries)}\n"]

        # False positives
        fps = self.recall(category="false_positive", limit=max_entries // 3)
        if fps:
            lines.append("### Known False Positives (skip these)")
            for e in fps:
                lines.append(f"- {e.content}")
            lines.append("")

        # Patterns
        patterns = self.recall(category="pattern", limit=max_entries // 3)
        if patterns:
            lines.append("### Known Patterns")
            for e in patterns:
                lines.append(f"- {e.content}")
            lines.append("")

        # Previous findings
        findings = self.recall(category="finding", limit=max_entries // 3)
        if findings:
            lines.append("### Previous Findings (confirmed)")
            for e in findings:
                lines.append(f"- {e.content} (by: {', '.join(e.source_models)})")

        return "\n".join(lines)

    @property
    def stats(self) -> dict:
        """Get memory statistics."""
        categories = {}
        for e in self.entries.values():
            categories[e.category] = categories.get(e.category, 0) + 1
        return {
            "total": len(self.entries),
            "categories": categories,
            "avg_confidence": (sum(e.confidence for e in self.entries.values())
                               / max(len(self.entries), 1)),
        }


# ---------------------------------------------------------------------------
# Convenience: Global instances
# ---------------------------------------------------------------------------

# Global router instance
router = ModelRouter()

# Create search agent
search_agent = OnlineSearchAgent(router)

# Create verifier
verifier = MultiModelVerifier(router)
