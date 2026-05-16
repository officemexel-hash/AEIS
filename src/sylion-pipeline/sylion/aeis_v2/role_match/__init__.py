"""W13 hybrid task-role matcher per ADR-001 Decision #5.

Two-stage matching:
1. Tag overlap (Jaccard) -> narrow to top-10
2. Embeddings cosine    -> rank top-3

Embeddings via Ollama ``nomic-embed-text``. Lazy import; falls back to
tag-overlap-only when ollama unavailable.

Public API:

- :class:`HybridMatch` — explainable match result (AdvisorCard format).
- :func:`tag_overlap_score` — Jaccard similarity over capability tag sets.
- :func:`get_embedding_or_none` — lazy ollama embedder; ``None`` on failure.
- :func:`cosine_similarity` — standard cosine over equal-length vectors.
- :func:`hybrid_match` — two-stage matcher returning top-N HybridMatches.

REST entry point: ``POST /api/v1/role-catalog/hybrid-match`` in
``sylion/api/role_catalog_routes.py``.

Charter: ADR-001 #5 (operator decision 2026-04-27).
"""
from __future__ import annotations

from sylion.aeis_v2.role_match.hybrid import (
    HybridMatch,
    cosine_similarity,
    get_embedding_or_none,
    hybrid_match,
    jaccard_set_similarity,
    tag_overlap_score,
)

__all__ = [
    "HybridMatch",
    "cosine_similarity",
    "get_embedding_or_none",
    "hybrid_match",
    "jaccard_set_similarity",
    "tag_overlap_score",
]
