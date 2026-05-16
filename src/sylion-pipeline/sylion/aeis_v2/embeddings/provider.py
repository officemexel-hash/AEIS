"""W13/W16 G1: unified embeddings provider abstraction.

Per ADR-001 #5 (hybrid task-role matcher) and ADR-001 #2 (idea->app cascade),
embeddings come from ``nomic-embed-text`` via Ollama by default. This module
provides a swappable interface so G2/G3 can plug in OpenAI/Cohere/local
sentence-transformers without touching consumers.

Public API:

- :class:`EmbeddingProvider` — abstract base class. Returns L2-comparable
  vectors (callers use :func:`cosine_similarity` for normalization).
- :class:`OllamaEmbeddingProvider` — default backend, shells out to
  ``ollama embeddings -m <model> <text>``. Returns ``None`` on failure
  (binary missing, timeout, malformed payload, model not pulled).
- :class:`StubEmbeddingProvider` — deterministic hash-based vectors for
  tests / environments where ollama is unavailable.
- :func:`get_default_provider` / :func:`set_default_provider` /
  :func:`reset_default_provider` — singleton accessor with thread-safe
  swap (useful for tests and runtime backend switching).
- :func:`cosine_similarity` — standard cosine, defensive against zero
  vectors and length mismatches.

Notes
-----
This is a pure abstraction module — it does NOT migrate any existing
consumer (see :mod:`sylion.aeis_v2.role_match.hybrid`). Migration of
``hybrid.py`` to consume this provider is tracked as a separate cron task.
"""
from __future__ import annotations

import json
import logging
import math
import subprocess
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


class EmbeddingProvider(ABC):
    """Abstract embeddings backend.

    Implementations return numeric vectors comparable via cosine similarity.
    Vectors do NOT need to be pre-normalized — :func:`cosine_similarity`
    handles normalization. Returning ``None`` signals a transient failure
    and consumers must have a deterministic fallback path (per ADR-001 #5
    the matcher falls back to Jaccard tag overlap).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier (e.g. ``ollama:nomic-embed-text``)."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Expected vector dimensionality. Used for fast pre-validation."""

    @abstractmethod
    def embed_one(self, text: str) -> list[float] | None:
        """Embed a single text. Returns ``None`` on failure or empty input."""

    def embed_many(self, texts: list[str]) -> list[list[float] | None]:
        """Embed a batch. Default impl loops; subclasses can batch upstream."""
        return [self.embed_one(t) for t in texts]


@dataclass
class OllamaEmbeddingProvider(EmbeddingProvider):
    """Default backend: ``ollama embeddings -m <model> <text>`` via subprocess.

    Mirrors the lazy/forgiving semantics of
    :func:`sylion.aeis_v2.role_match.hybrid.get_embedding_or_none` — every
    failure mode (binary missing, timeout, non-zero exit, malformed JSON,
    non-numeric values) returns ``None`` so consumers can fall back.
    """

    model: str = "nomic-embed-text"
    timeout_s: float = 10.0
    _name_override: str = ""
    _dim: int = 768  # nomic-embed-text default

    @property
    def name(self) -> str:
        return self._name_override or f"ollama:{self.model}"

    @property
    def dim(self) -> int:
        return self._dim

    def embed_one(self, text: str) -> list[float] | None:
        if not text or not text.strip():
            return None
        try:
            result = subprocess.run(
                ["ollama", "embeddings", "-m", self.model, text],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except FileNotFoundError:
            # ollama binary not installed -> deterministic fallback.
            return None
        except subprocess.TimeoutExpired:
            return None
        except Exception as exc:  # pragma: no cover — defensive
            logging.getLogger(__name__).debug(
                "ollama embeddings failed: %s", exc
            )
            return None

        if result.returncode != 0:
            return None
        stdout = (result.stdout or "").strip()
        if not stdout:
            return None
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None

        embedding = payload.get("embedding")
        if embedding is None:
            # Newer ollama versions return ``embeddings: [[...]]`` instead.
            embeddings_list = payload.get("embeddings")
            if isinstance(embeddings_list, list) and embeddings_list:
                embedding = embeddings_list[0]

        if not isinstance(embedding, list) or not embedding:
            return None

        coerced: list[float] = []
        for value in embedding:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            coerced.append(float(value))
        return coerced or None


@dataclass
class StubEmbeddingProvider(EmbeddingProvider):
    """Test-only deterministic provider. Hash-based 64-d vectors in [-1, 1].

    Useful when ollama is unavailable (CI, offline dev) but consumers still
    want a non-None vector to exercise the embedding code path. Output is
    reproducible: same text always returns the same vector.
    """

    @property
    def name(self) -> str:
        return "stub:hash"

    @property
    def dim(self) -> int:
        return 64

    def embed_one(self, text: str) -> list[float] | None:
        if not text:
            return None
        import hashlib

        # SHA-512 produces 64 bytes — exactly the dim we expose.
        digest = hashlib.sha512(text.encode("utf-8")).digest()
        # Map each unsigned byte [0, 255] to [-1, 1) via (b - 128) / 128.
        return [(b - 128) / 128.0 for b in digest[:64]]


# ---------------------------------------------------------------------------
# Singleton accessor — thread-safe lazy default.
# ---------------------------------------------------------------------------


_default_provider: EmbeddingProvider | None = None
_lock = threading.Lock()


def get_default_provider() -> EmbeddingProvider:
    """Return the process-wide default provider.

    Lazy: the first call constructs an :class:`OllamaEmbeddingProvider`.
    Subsequent calls reuse it until :func:`set_default_provider` or
    :func:`reset_default_provider` is invoked.
    """
    global _default_provider
    with _lock:
        if _default_provider is None:
            _default_provider = OllamaEmbeddingProvider()
        return _default_provider


def set_default_provider(provider: EmbeddingProvider) -> None:
    """Replace the default — useful for tests or switching backends.

    The new provider is locked-in until reset. Tests must call
    :func:`reset_default_provider` in teardown to avoid leaking state.
    """
    global _default_provider
    with _lock:
        _default_provider = provider


def reset_default_provider() -> None:
    """Drop the cached default. Next :func:`get_default_provider` rebuilds."""
    global _default_provider
    with _lock:
        _default_provider = None


# ---------------------------------------------------------------------------
# Cosine similarity helper (kept here so consumers don't reach into
# role_match.hybrid for a primitive).
# ---------------------------------------------------------------------------


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Standard cosine similarity. Returns 0.0 on zero/length-mismatch."""
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


__all__ = [
    "EmbeddingProvider",
    "OllamaEmbeddingProvider",
    "StubEmbeddingProvider",
    "cosine_similarity",
    "get_default_provider",
    "reset_default_provider",
    "set_default_provider",
]
