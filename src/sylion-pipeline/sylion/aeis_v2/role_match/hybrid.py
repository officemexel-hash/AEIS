"""W13 hybrid task-role matcher per ADR-001 Decision #5.

Two-stage matching:

1. Tag overlap (Jaccard) -> narrow to top-10 (deterministic, zero-cost).
2. Embeddings cosine    -> rank top-3 from those (fuzzy refinement).

Embeddings are sourced through the unified
:mod:`sylion.aeis_v2.embeddings` provider abstraction (W13/W16 G1).
The default backend is ``OllamaEmbeddingProvider`` (``nomic-embed-text``),
but tests and alternative deployments can swap it via
:func:`set_default_provider`. The whole module degrades gracefully to
tag-overlap-only when the provider returns ``None``.

Result is :class:`HybridMatch` — AdvisorCard-shaped: the operator gets a
ranked list with a ``reason_pl`` for each, picks one (or auto = top-1).
"""
from __future__ import annotations

# ``subprocess`` is intentionally kept imported at module scope as a
# back-compat anchor: existing tests monkeypatch ``hybrid_mod.subprocess.run``
# to simulate ollama-missing failure modes. The actual subprocess call now
# lives inside :class:`OllamaEmbeddingProvider`, but since ``subprocess`` is
# a singleton module the monkeypatch still propagates to the provider.
import subprocess  # noqa: F401 — see docstring above.
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from sylion.skills.roles import (
    DEFAULT_SKILL_LEVEL,
    VALID_SKILL_LEVELS,
)

# Reuse the skill-level rank ordering from the role catalog (single source of
# truth) — but keep an explicit local copy so tests don't hit private symbols.
_SKILL_LEVEL_RANK: dict[str, int] = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "principal": 4,
    "any": 0,
}


@dataclass
class HybridMatch:
    """Explainable AdvisorCard-shaped match result.

    ``score`` is the combined ranking score in ``[0, 1]``:

    - When embeddings ran : ``0.6 * tag_overlap + 0.4 * embedding_sim``.
    - When embeddings did not run (ollama unreachable): ``score == tag_overlap``
      and ``embedding_sim == 0.0``.
    """

    role_id: str
    role_name: str
    score: float
    tag_overlap: float
    embedding_sim: float
    reason_pl: str
    skill_level: str
    capabilities: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (REST-friendly)."""
        return {
            "role_id": self.role_id,
            "role_name": self.role_name,
            "score": round(self.score, 4),
            "tag_overlap": round(self.tag_overlap, 4),
            "embedding_sim": round(self.embedding_sim, 4),
            "reason_pl": self.reason_pl,
            "skill_level": self.skill_level,
            "capabilities": list(self.capabilities),
        }


# ---------------------------------------------------------------------------
# Stage 1 — Jaccard tag overlap.
# ---------------------------------------------------------------------------


def tag_overlap_score(task_tags: set[str], role_tags: set[str]) -> float:
    """Jaccard similarity. Returns 0.0 when union is empty."""
    if not task_tags and not role_tags:
        return 0.0
    union = task_tags | role_tags
    if not union:
        return 0.0
    inter = task_tags & role_tags
    return len(inter) / len(union)


def jaccard_set_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity with explicit empty-set semantics."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Stage 2 — Ollama embeddings (lazy, optional).
# ---------------------------------------------------------------------------


def get_embedding_or_none(text: str) -> list[float] | None:
    """Lazy fetch embedding via the configured provider.

    Phase 0: ollama ``nomic-embed-text`` via :class:`OllamaEmbeddingProvider`
    singleton (the lazy default in :mod:`sylion.aeis_v2.embeddings`).
    G1: switchable to other providers via :func:`set_default_provider`.

    Returns ``None`` when:

    - the input text is empty/whitespace,
    - the active provider is unavailable (binary missing, timeout, etc.),
    - the embedding call fails for any other reason.

    Callers are expected to fall back to tag-overlap-only ranking.
    """
    from sylion.aeis_v2.embeddings import get_default_provider

    return get_default_provider().embed_one(text)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compatibility shim — delegates to :func:`embeddings.cosine_similarity`.

    Kept as a re-export so existing call sites and tests that import from
    :mod:`sylion.aeis_v2.role_match` keep working unchanged.
    """
    from sylion.aeis_v2.embeddings import cosine_similarity as _cosine

    return _cosine(a, b)


# ---------------------------------------------------------------------------
# Helpers (private).
# ---------------------------------------------------------------------------


def _skill_satisfies(role_level: str, requested: str | None) -> bool:
    """``True`` if ``role_level`` meets the ``requested`` minimum.

    Mirrors :func:`sylion.skills.roles._skill_level_satisfies` but is local
    to keep the matcher self-contained.
    """
    if requested in (None, "", "any"):
        return True
    role_norm = (role_level or DEFAULT_SKILL_LEVEL).strip().lower()
    req_norm = str(requested).strip().lower()
    if req_norm not in VALID_SKILL_LEVELS:
        return True  # unknown levels behave like 'any'
    if role_norm in ("", "any"):
        # Legacy YAMLs that haven't declared a level match any explicit request.
        return True
    return _SKILL_LEVEL_RANK.get(role_norm, 0) >= _SKILL_LEVEL_RANK.get(req_norm, 0)


def _build_reason(
    role: Any,
    overlap: float,
    emb_sim: float,
    used_embeddings: bool,
) -> str:
    """Polish-language explanation per AdvisorCard format."""
    overlap_pct = int(round(overlap * 100))
    if used_embeddings:
        emb_pct = int(round(emb_sim * 100))
        return (
            f"Pokrycie tagow {overlap_pct}% + podobienstwo opisu {emb_pct}% "
            f"(embeddings nomic-embed-text); skill_level={role.skill_level}."
        )
    return (
        f"Pokrycie tagow {overlap_pct}% (embeddings niedostepne, "
        f"fallback Jaccard); skill_level={role.skill_level}."
    )


# ---------------------------------------------------------------------------
# Public matcher.
# ---------------------------------------------------------------------------


def hybrid_match(
    task_description: str,
    task_tags: Iterable[str],
    roles: Iterable[Any],
    *,
    top_overlap: int = 10,
    top_final: int = 3,
    skill_level: str | None = None,
) -> list[HybridMatch]:
    """Two-stage hybrid matcher per ADR-001 #5.

    Stage 1 (always runs): rank roles by Jaccard overlap on capability tags
    and keep the top ``top_overlap`` candidates. Roles that don't satisfy
    ``skill_level`` (when given) are filtered before ranking.

    Stage 2 (lazy): embed the task description via ollama
    ``nomic-embed-text``, then embed each candidate's name+description+caps
    string and compute cosine similarity. If ollama is unreachable for the
    *task* embedding, stage 2 is skipped entirely and ``score == tag_overlap``
    for every candidate.

    Returns up to ``top_final`` :class:`HybridMatch` objects sorted by
    descending combined score.
    """
    tags = {str(t).strip().lower() for t in task_tags if str(t).strip()}

    # Stage 1: filter + rank by tag overlap.
    overlap_scored: list[tuple[Any, float]] = []
    for role in roles:
        if not _skill_satisfies(getattr(role, "skill_level", "any"), skill_level):
            continue
        role_caps = {
            str(c).strip().lower()
            for c in getattr(role, "capabilities", ())
            if str(c).strip()
        }
        overlap_scored.append((role, tag_overlap_score(tags, role_caps)))

    overlap_scored.sort(
        key=lambda pair: (-pair[1], getattr(pair[0], "id", "")),
    )
    candidates = overlap_scored[: max(0, top_overlap)]
    if not candidates:
        return []

    # Stage 2: embeddings refinement (lazy ollama).
    task_emb = get_embedding_or_none(task_description) if task_description else None
    use_embeddings = task_emb is not None

    results: list[HybridMatch] = []
    for role, overlap_s in candidates:
        emb_sim = 0.0
        if use_embeddings:
            role_text = (
                f"{getattr(role, 'name_pl', '')}: "
                f"{getattr(role, 'description_pl', '')} "
                f"{' '.join(getattr(role, 'capabilities', ()))}"
            ).strip()
            role_emb = get_embedding_or_none(role_text) if role_text else None
            if role_emb and task_emb:
                emb_sim = cosine_similarity(task_emb, role_emb)
                # Cosine on real embeddings can be negative; clamp to [0,1] so
                # the combined score stays in [0,1].
                if emb_sim < 0.0:
                    emb_sim = 0.0
                elif emb_sim > 1.0:
                    emb_sim = 1.0

        if use_embeddings:
            combined = 0.6 * overlap_s + 0.4 * emb_sim
        else:
            combined = overlap_s

        results.append(
            HybridMatch(
                role_id=getattr(role, "id", ""),
                role_name=getattr(role, "name_pl", ""),
                score=combined,
                tag_overlap=overlap_s,
                embedding_sim=emb_sim,
                reason_pl=_build_reason(role, overlap_s, emb_sim, use_embeddings),
                skill_level=getattr(role, "skill_level", DEFAULT_SKILL_LEVEL),
                capabilities=list(getattr(role, "capabilities", ())),
            )
        )

    results.sort(key=lambda m: (-m.score, m.role_id))
    return results[: max(0, top_final)]


__all__ = [
    "HybridMatch",
    "cosine_similarity",
    "get_embedding_or_none",
    "hybrid_match",
    "jaccard_set_similarity",
    "tag_overlap_score",
]
