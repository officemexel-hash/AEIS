"""Capability tagging vocabulary for SYLION providers/models (PDF §8.1.8).

Used by:
  - W7 Role Catalog (matches role to model based on tags)
  - W13 Task-to-Role Suggester (picks model that has required tags)
  - W11 Provider routing (filter providers by required capability)

The vocabulary is split into four orthogonal axes:

  1. Modality   — what kinds of input/output the model handles
                  (text, code, vision, image-gen, audio-gen, video-gen,
                   embeddings, audio-transcribe).
  2. Capability — what advanced features it supports
                  (function-calling, long-context, reasoning, json-mode,
                   streaming).
  3. Tier/speed — cost & latency profile
                  (cheap, balanced, premium, fast, slow, precise).
  4. Locality   — where it runs and what hardware it needs
                  (local, cloud, gpu, cpu, quantized).

All known canonical tags are exposed as ``Final[str]`` constants and
collected into :data:`ALL_TAGS`. Models are tagged in :data:`MODEL_TAGS`;
the helpers :func:`tags_for` and :func:`models_with_tags` give callers a
small typed surface so we never sprinkle string-literal tag tests across
the codebase.
"""

from __future__ import annotations

from typing import Final


# ---------------------------------------------------------------------------
# Modality tags
# ---------------------------------------------------------------------------

MODALITY_TEXT: Final = "text"
MODALITY_CODE: Final = "code"
MODALITY_VISION: Final = "vision"
MODALITY_IMAGE_GEN: Final = "image-gen"
MODALITY_AUDIO_GEN: Final = "audio-gen"
MODALITY_AUDIO_TRANSCRIBE: Final = "audio-transcribe"
MODALITY_VIDEO_GEN: Final = "video-gen"
MODALITY_EMBEDDINGS: Final = "embeddings"


# ---------------------------------------------------------------------------
# Capability tags
# ---------------------------------------------------------------------------

CAP_FUNCTION_CALLING: Final = "function-calling"
CAP_LONG_CONTEXT: Final = "long-context"  # >100k tokens
CAP_REASONING: Final = "reasoning"
CAP_JSON_MODE: Final = "json-mode"
CAP_STREAMING: Final = "streaming"


# ---------------------------------------------------------------------------
# Cost/speed tier tags
# ---------------------------------------------------------------------------

TIER_CHEAP: Final = "cheap"          # < $1 / 1M tokens
TIER_BALANCED: Final = "balanced"    # $1 – $10 / 1M tokens
TIER_PREMIUM: Final = "premium"      # > $10 / 1M tokens
SPEED_FAST: Final = "fast"           # > 100 tok/s
SPEED_SLOW: Final = "slow"           # < 30 tok/s
PRECISE: Final = "precise"           # high accuracy on benchmarks


# ---------------------------------------------------------------------------
# Locality / hardware tags
# ---------------------------------------------------------------------------

LOCALITY_LOCAL: Final = "local"      # runs on operator's host
LOCALITY_CLOUD: Final = "cloud"      # remote API
LOCALITY_GPU: Final = "gpu"
LOCALITY_CPU: Final = "cpu"
LOCALITY_QUANTIZED: Final = "quantized"
LOCALITY_CONCURRENT: Final = "concurrent"  # high-throughput batched serving


ALL_TAGS: Final[frozenset[str]] = frozenset({
    # modality
    MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION, MODALITY_IMAGE_GEN,
    MODALITY_AUDIO_GEN, MODALITY_AUDIO_TRANSCRIBE, MODALITY_VIDEO_GEN,
    MODALITY_EMBEDDINGS,
    # capability
    CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_REASONING, CAP_JSON_MODE,
    CAP_STREAMING,
    # tier / speed
    TIER_CHEAP, TIER_BALANCED, TIER_PREMIUM, SPEED_FAST, SPEED_SLOW, PRECISE,
    # locality / hardware
    LOCALITY_LOCAL, LOCALITY_CLOUD, LOCALITY_GPU, LOCALITY_CPU,
    LOCALITY_QUANTIZED, LOCALITY_CONCURRENT,
})


# ---------------------------------------------------------------------------
# Model tag registry
# ---------------------------------------------------------------------------
# Per-model tag sets. Keep this in sync with provider DEFAULT_MODELS in
# sylion.api.ai_providers_routes plus local-provider supported_models.
# Targeted coverage: 30+ models spanning every provider so W7/W13 can
# match roles to models without provider-specific knowledge.

MODEL_TAGS: Final[dict[str, frozenset[str]]] = {
    # ---------- Anthropic ------------------------------------------------
    "claude-haiku-4-5": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_JSON_MODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    "claude-sonnet-4-5": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_JSON_MODE, CAP_STREAMING,
        TIER_BALANCED, PRECISE, LOCALITY_CLOUD,
    }),
    "claude-opus-4-7": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_REASONING, CAP_JSON_MODE,
        CAP_STREAMING, TIER_PREMIUM, PRECISE, LOCALITY_CLOUD,
    }),
    # ---------- OpenAI ---------------------------------------------------
    "gpt-4o": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_JSON_MODE, CAP_STREAMING,
        TIER_BALANCED, PRECISE, LOCALITY_CLOUD,
    }),
    "gpt-4o-mini": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_JSON_MODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    "o1-mini": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_REASONING, CAP_LONG_CONTEXT,
        TIER_BALANCED, SPEED_SLOW, PRECISE, LOCALITY_CLOUD,
    }),
    "o1-preview": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_REASONING, CAP_LONG_CONTEXT,
        TIER_PREMIUM, SPEED_SLOW, PRECISE, LOCALITY_CLOUD,
    }),
    "text-embedding-3-large": frozenset({
        MODALITY_EMBEDDINGS, TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    # ---------- Perplexity ----------------------------------------------
    "sonar": frozenset({
        MODALITY_TEXT, CAP_STREAMING, TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    "sonar-pro": frozenset({
        MODALITY_TEXT, CAP_STREAMING, CAP_LONG_CONTEXT,
        TIER_BALANCED, PRECISE, LOCALITY_CLOUD,
    }),
    # ---------- Google Gemini -------------------------------------------
    "gemini-2.0-flash-lite": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_JSON_MODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    "gemini-2.0-flash": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_JSON_MODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    "gemini-1.5-pro": frozenset({
        MODALITY_TEXT, MODALITY_CODE, MODALITY_VISION,
        CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_JSON_MODE, CAP_STREAMING,
        TIER_BALANCED, PRECISE, LOCALITY_CLOUD,
    }),
    # ---------- Z.AI GLM ------------------------------------------------
    "glm-4-plus": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_FUNCTION_CALLING, CAP_JSON_MODE, CAP_STREAMING,
        TIER_BALANCED, LOCALITY_CLOUD,
    }),
    "glm-4v-plus": frozenset({
        MODALITY_TEXT, MODALITY_VISION, CAP_STREAMING,
        TIER_BALANCED, LOCALITY_CLOUD,
    }),
    # ---------- OpenRouter (aggregator/auto routes) ---------------------
    "openrouter/auto": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_BALANCED, LOCALITY_CLOUD,
    }),
    # ---------- Moonshot (Kimi) -----------------------------------------
    "moonshot-v1-8k": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_CLOUD,
    }),
    "moonshot-v1-128k": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_LONG_CONTEXT, CAP_STREAMING,
        TIER_BALANCED, LOCALITY_CLOUD,
    }),
    # ---------- DeepSeek -------------------------------------------------
    "deepseek-chat": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_FUNCTION_CALLING, CAP_JSON_MODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    "deepseek-reasoner": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_REASONING, CAP_LONG_CONTEXT, CAP_STREAMING,
        TIER_BALANCED, PRECISE, LOCALITY_CLOUD,
    }),
    # ---------- xAI (Grok) ----------------------------------------------
    "grok-2-1212": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_FUNCTION_CALLING, CAP_JSON_MODE, CAP_STREAMING,
        TIER_BALANCED, LOCALITY_CLOUD,
    }),
    "grok-2-vision-1212": frozenset({
        MODALITY_TEXT, MODALITY_VISION, CAP_STREAMING,
        TIER_BALANCED, LOCALITY_CLOUD,
    }),
    # ---------- Mistral --------------------------------------------------
    "mistral-small-latest": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_FUNCTION_CALLING, CAP_JSON_MODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    "mistral-large-latest": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_FUNCTION_CALLING, CAP_JSON_MODE, CAP_STREAMING,
        TIER_BALANCED, PRECISE, LOCALITY_CLOUD,
    }),
    # ---------- Groq -----------------------------------------------------
    "llama-3.3-70b-versatile": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    # ---------- Cohere ---------------------------------------------------
    "command-r-plus": frozenset({
        MODALITY_TEXT, MODALITY_CODE,
        CAP_FUNCTION_CALLING, CAP_LONG_CONTEXT, CAP_STREAMING,
        TIER_BALANCED, LOCALITY_CLOUD,
    }),
    # ---------- Fireworks ------------------------------------------------
    "accounts/fireworks/models/llama-v3p3-70b-instruct": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    # ---------- Together AI ----------------------------------------------
    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_CLOUD,
    }),
    # ---------- Local: Ollama -------------------------------------------
    "qwen2.5:7b-instruct": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_LOCAL, LOCALITY_GPU,
    }),
    "qwen2.5-coder:32b": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_LOCAL, LOCALITY_GPU, PRECISE,
    }),
    "llama3.2:3b": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST, LOCALITY_LOCAL, LOCALITY_CPU,
        LOCALITY_QUANTIZED,
    }),
    "llama3.1:70b": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_LONG_CONTEXT, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_LOCAL, LOCALITY_GPU, PRECISE,
    }),
    "nomic-embed-text": frozenset({
        MODALITY_EMBEDDINGS, TIER_CHEAP, SPEED_FAST,
        LOCALITY_LOCAL, LOCALITY_CPU,
    }),
    # ---------- Local: LM Studio (typical packs) -------------------------
    "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_LOCAL, LOCALITY_CPU, LOCALITY_QUANTIZED,
    }),
    # ---------- Local: vLLM (high-throughput) ----------------------------
    "Qwen/Qwen2.5-72B-Instruct": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_LONG_CONTEXT, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_LOCAL, LOCALITY_GPU, LOCALITY_CONCURRENT,
        SPEED_FAST, PRECISE,
    }),
    "mistralai/Mixtral-8x7B-Instruct-v0.1": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_LOCAL, LOCALITY_GPU, LOCALITY_CONCURRENT,
        SPEED_FAST,
    }),
    # ---------- Local: llama.cpp (quantized GGUF) ------------------------
    "TheBloke/Llama-2-7B-Chat-GGUF": frozenset({
        MODALITY_TEXT, CAP_STREAMING,
        TIER_CHEAP, LOCALITY_LOCAL, LOCALITY_CPU, LOCALITY_QUANTIZED,
    }),
    "ggml-org/Phi-3-mini-4k-instruct-GGUF": frozenset({
        MODALITY_TEXT, MODALITY_CODE, CAP_STREAMING,
        TIER_CHEAP, SPEED_FAST,
        LOCALITY_LOCAL, LOCALITY_CPU, LOCALITY_QUANTIZED,
    }),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tags_for(model_id: str) -> frozenset[str]:
    """Return the capability tags for ``model_id`` (empty set if unknown)."""
    return MODEL_TAGS.get(model_id, frozenset())


def models_with_tags(
    required: set[str] | frozenset[str],
    prefer: set[str] | frozenset[str] | None = None,
) -> list[str]:
    """Return models that have ALL ``required`` tags.

    When ``prefer`` is given the result is sorted by overlap with
    ``prefer`` (descending), so callers can express soft preferences
    like “local if available, else cloud”.
    """
    required_fs = frozenset(required)
    candidates = [
        model_id
        for model_id, tags in MODEL_TAGS.items()
        if required_fs.issubset(tags)
    ]
    if prefer:
        prefer_fs = frozenset(prefer)
        candidates.sort(
            key=lambda m: len(MODEL_TAGS[m] & prefer_fs),
            reverse=True,
        )
    else:
        candidates.sort()
    return candidates


def validate_registry() -> list[str]:
    """Return a list of unknown tags found in :data:`MODEL_TAGS`.

    Empty list ⇒ registry is clean. Used by tests to catch typos.
    """
    bad: list[str] = []
    for model_id, tags in MODEL_TAGS.items():
        for t in tags:
            if t not in ALL_TAGS:
                bad.append(f"{model_id}:{t}")
    return bad


__all__ = [
    # vocabulary
    "ALL_TAGS",
    "MODEL_TAGS",
    # modality
    "MODALITY_TEXT", "MODALITY_CODE", "MODALITY_VISION",
    "MODALITY_IMAGE_GEN", "MODALITY_AUDIO_GEN",
    "MODALITY_AUDIO_TRANSCRIBE", "MODALITY_VIDEO_GEN",
    "MODALITY_EMBEDDINGS",
    # capability
    "CAP_FUNCTION_CALLING", "CAP_LONG_CONTEXT", "CAP_REASONING",
    "CAP_JSON_MODE", "CAP_STREAMING",
    # tier / speed
    "TIER_CHEAP", "TIER_BALANCED", "TIER_PREMIUM",
    "SPEED_FAST", "SPEED_SLOW", "PRECISE",
    # locality
    "LOCALITY_LOCAL", "LOCALITY_CLOUD", "LOCALITY_GPU", "LOCALITY_CPU",
    "LOCALITY_QUANTIZED", "LOCALITY_CONCURRENT",
    # helpers
    "tags_for", "models_with_tags", "validate_registry",
]
