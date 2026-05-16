"""W13/W16 G1 — unified embeddings provider abstraction.

Re-exports the public API from :mod:`sylion.aeis_v2.embeddings.provider`.

Per ADR-001 #2 (idea->app cascade) and ADR-001 #5 (hybrid task-role
matcher), embeddings come from ``nomic-embed-text`` via Ollama by default.
This package exposes a swappable provider so downstream G2/G3 modules can
plug in alternative backends (OpenAI, Cohere, local sentence-transformers)
without touching consumers.

Public API:

- :class:`EmbeddingProvider` — abstract base.
- :class:`OllamaEmbeddingProvider` — default Ollama subprocess backend.
- :class:`StubEmbeddingProvider` — deterministic hash-based test provider.
- :func:`get_default_provider` / :func:`set_default_provider` /
  :func:`reset_default_provider` — thread-safe singleton accessor.
- :func:`cosine_similarity` — defensive cosine over equal-length vectors.

This module does NOT migrate any existing consumer (notably
:mod:`sylion.aeis_v2.role_match.hybrid`). Consumer migration is tracked
as a separate cron task for surgical safety.
"""
from __future__ import annotations

from sylion.aeis_v2.embeddings.provider import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    StubEmbeddingProvider,
    cosine_similarity,
    get_default_provider,
    reset_default_provider,
    set_default_provider,
)

__all__ = [
    "EmbeddingProvider",
    "OllamaEmbeddingProvider",
    "StubEmbeddingProvider",
    "cosine_similarity",
    "get_default_provider",
    "reset_default_provider",
    "set_default_provider",
]
