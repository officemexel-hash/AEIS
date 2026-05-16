"""W16 Apps Builder — idea→app studio per ADR-001 #2 cascade.

Module realizes the 3-stage cascade pipeline:

1. **Phase 0**: Template matching via Jaccard tag-overlap
   (:func:`match_idea_to_templates`).
2. **G1 (this commit)**: Tag-overlap + embeddings cosine refinement via
   :mod:`sylion.aeis_v2.embeddings` provider abstraction
   (:func:`match_idea_to_templates_g1`). Falls back to step 1 when the
   provider returns ``None`` (Ollama unreachable).
3. **G2**: LLM generation as fallback when no template matches.

Per operator decision (ADR-001 #2), every generated app manifest must pass
through Council Hybrid (W3) before becoming production. Phase 0 is read-only
template browsing; idea→manifest generation lands in G2.

Multi-backend dispatch demo — this module's building blocks were assembled from:

- ``AppTemplate``, ``MatchResult``, ``score_tag_overlap``, ``rank_templates``
  — Codex CLI (``codex exec``)
- ``DEMO_TEMPLATES`` Polish content — Ollama gpt-oss:20b
- Module integration + tests + REST routes — Claude bg agent
- G1 cascade step 2 (embeddings refinement, cached) — Claude cron agent
- Adversarial review — Kimi (next round)

PDF reference: §3.3 \"Apps Builder — kompozytor aplikacji z palety widgetów
+ ontologii W15\".
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Literal
import unicodedata


@dataclass(frozen=True, slots=True)
class AppTemplate:
    """Szablon aplikacji z metadanymi, powiazaniami i tagami."""

    id: str
    name_pl: str
    description_pl: str
    object_type_ids: list[str]
    widget_ids: list[str]
    tags: list[str]

    def to_dict(self) -> dict[str, object]:
        """Zwraca reprezentacje slownikowa szablonu aplikacji."""
        return {
            "id": self.id,
            "name_pl": self.name_pl,
            "description_pl": self.description_pl,
            "object_type_ids": list(self.object_type_ids),
            "widget_ids": list(self.widget_ids),
            "tags": list(self.tags),
        }

    def matches_tags(self, query_tags: set[str]) -> float:
        """Zwraca wynik Jaccarda dla tagow szablonu i zapytania."""
        return score_tag_overlap(query_tags, set(self.tags))


def validate_app_template_dict(d: dict) -> tuple[bool, list[str]]:
    """Checks required AppTemplate payload shape."""
    errors: list[str] = []
    for key in ("id", "name_pl", "description_pl"):
        if not isinstance(d.get(key), str):
            errors.append(f"{key} must be str")
    for key, lo, hi in (("object_type_ids", 3, 5), ("widget_ids", 3, 5), ("tags", 5, 8)):
        value = d.get(key)
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            errors.append(f"{key} must be list[str]")
        elif not lo <= len(value) <= hi:
            errors.append(f"{key} len must be {lo}-{hi}")
    return (not errors, errors)


def score_tag_overlap(query_tags: set[str], template_tags: set[str]) -> float:
    """Oblicza podobienstwo Jaccarda dla dwoch zbiorow tagow."""
    union = query_tags | template_tags
    if not union:
        return 0.0
    intersection = query_tags & template_tags
    return len(intersection) / len(union)


def rank_templates(
    query_tags: set[str],
    templates: list[AppTemplate],
    top_n: int = 5,
) -> list[tuple[AppTemplate, float]]:
    """Zwraca liste najlepiej dopasowanych szablonow posortowana malejaco po wyniku."""
    ranked: list[tuple[AppTemplate, float]] = []
    for template in templates:
        score = score_tag_overlap(query_tags, set(template.tags))
        if score >= 0.05:
            ranked.append((template, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:top_n]


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Wynik dopasowania szablonu aplikacji."""

    template: AppTemplate
    score: float
    method: Literal["tag_overlap", "embedding", "llm_generated"]
    reason_pl: str

    def to_dict(self) -> dict[str, object]:
        """Zwraca reprezentacje slownikowa wyniku dopasowania."""
        return {
            "template": self.template.to_dict(),
            "score": self.score,
            "method": self.method,
            "reason_pl": self.reason_pl,
        }


# --------------------------------------------------------------------------
# Demo template library — 5 templates from ollama gpt-oss:20b dispatch (PoC)
# --------------------------------------------------------------------------

DEMO_TEMPLATES: tuple[AppTemplate, ...] = (
    AppTemplate(
        id="inspection_field",
        name_pl="Inspekcje terenowe",
        description_pl=(
            "Aplikacja umozliwiajaca rejestracje i monitorowanie inspekcji "
            "terenowych w czasie rzeczywistym, wraz z mozliwoscia dodawania "
            "zdjec i raportow."
        ),
        object_type_ids=["customer", "project", "task"],
        widget_ids=[
            "ObjectListView", "ObjectFormEditor", "ChartWidget",
            "AlertBanner", "DateRangePicker",
        ],
        tags=["inspekcja", "terenowa", "raport", "monitorowanie", "audyt"],
    ),
    AppTemplate(
        id="approval_workflow",
        name_pl="Proces zatwierdzania",
        description_pl=(
            "Zautomatyzowany workflow pozwalajacy na zglaszanie, "
            "przegladanie i zatwierdzanie dokumentow oraz dzialan "
            "wewnatrz organizacji."
        ),
        object_type_ids=["idea", "task", "project"],
        widget_ids=[
            "ObjectListView", "KpiCard", "AlertBanner",
            "CommandButton", "TabsWidget",
        ],
        tags=["zatwierdzanie", "workflow", "dokumenty", "autoryzacja", "decyzje"],
    ),
    AppTemplate(
        id="inventory_lite",
        name_pl="Zarzadzanie magazynem (Lite)",
        description_pl=(
            "Lekka aplikacja do monitorowania stanow magazynowych, "
            "przyjmowania i wydawania towarow, z prostym interfejsem "
            "i raportami."
        ),
        object_type_ids=["vehicle", "task"],
        widget_ids=[
            "ObjectListView", "KpiCard", "ChartWidget",
            "ObjectFormEditor", "JsonViewer",
        ],
        tags=["magazyn", "stany", "inwentaryzacja", "raporty", "logistyka"],
    ),
    AppTemplate(
        id="timesheet_tracker",
        name_pl="Rejestr czasu pracy",
        description_pl=(
            "Aplikacja do ewidencji godzin pracy zespolu z agregacja "
            "tygodniowa/miesieczna i eksportem do raportow placowych."
        ),
        object_type_ids=["project", "task"],
        widget_ids=[
            "ObjectListView", "ObjectFormEditor", "DateRangePicker",
            "ChartWidget", "KpiCard",
        ],
        tags=["czas-pracy", "ewidencja", "rozliczenia", "raporty", "zespoly"],
    ),
    AppTemplate(
        id="maintenance_log",
        name_pl="Rejestr serwisow",
        description_pl=(
            "Dziennik napraw i przegladow technicznych z alertami "
            "o terminowych serwisach i historia zdarzen per zasob."
        ),
        object_type_ids=["vehicle", "task"],
        widget_ids=[
            "ObjectListView", "AlertBanner", "TabsWidget",
            "ObjectFormEditor", "DateRangePicker",
        ],
        tags=["serwis", "konserwacja", "alerty", "historia", "zasoby"],
    ),
)


def list_templates() -> list[dict[str, Any]]:
    """Return all demo templates as JSON-friendly dicts."""
    return [tpl.to_dict() for tpl in DEMO_TEMPLATES]


_TAG_ALIASES: dict[str, set[str]] = {
    "inspekcji": {"inspekcja"},
    "inspekcje": {"inspekcja"},
    "terenowych": {"terenowa"},
    "terenowe": {"terenowa"},
    "raportami": {"raport", "raporty"},
    "raportow": {"raport", "raporty"},
    "audytu": {"audyt"},
    "audytow": {"audyt"},
    "monitorowaniem": {"monitorowanie"},
    "monitoringu": {"monitorowanie"},
    "zasobow": {"zasoby"},
    "dokumentow": {"dokumenty"},
    "dokumentami": {"dokumenty"},
    "zatwierdzania": {"zatwierdzanie"},
    "magazynowe": {"magazyn"},
    "magazynowych": {"magazyn"},
    "stanow": {"stany"},
    "serwisow": {"serwis"},
    "przegladow": {"serwis", "konserwacja"},
    "napraw": {"serwis"},
    "godzin": {"czas-pracy", "ewidencja"},
    "pracy": {"czas-pracy"},
}

_PHRASE_ALIASES: tuple[tuple[str, str], ...] = (
    ("czas pracy", "czas-pracy"),
    ("ewidencja godzin", "ewidencja"),
    ("proces zatwierdzania", "zatwierdzanie"),
    ("inspekcje terenowe", "inspekcja"),
    ("inspekcji terenowych", "inspekcja"),
)


def _ascii_fold(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )


def extract_query_tags(idea_text: str) -> set[str]:
    """Extract local tags from natural Polish operator text."""
    import re

    normalized_text = _ascii_fold(idea_text.lower())
    words = re.findall(r"\w+", normalized_text)
    tags: set[str] = set()
    for word in words:
        if len(word) <= 2:
            continue
        tags.add(word)
        tags.update(_TAG_ALIASES.get(word, set()))

    for phrase, tag in _PHRASE_ALIASES:
        if phrase in normalized_text:
            tags.add(tag)

    return tags


def match_idea_to_templates(
    idea_text: str,
    *,
    top_n: int = 3,
    min_score: float = 0.05,
) -> list[MatchResult]:
    """Phase 0 cascade: extract tags from text, rank templates by Jaccard.

    Phase 0 tag-extraction: split on whitespace + lowercase. G1 will replace
    with embeddings-based extraction.
    """
    query_tags = extract_query_tags(idea_text)

    scored = rank_templates(query_tags, list(DEMO_TEMPLATES), top_n=top_n * 3)
    results: list[MatchResult] = []
    for tpl, score in scored:
        if score < min_score:
            continue
        overlap = sorted(query_tags & set(tpl.tags))
        reason = (
            f"Pokrycie tagow Jaccard={score:.2f}; wspolne tagi: "
            f"{', '.join(overlap) if overlap else '(brak)'}"
        )
        results.append(MatchResult(
            template=tpl,
            score=score,
            method="tag_overlap",
            reason_pl=reason,
        ))
    return results[:top_n]


# --------------------------------------------------------------------------
# G1 cascade step 2 — embeddings refinement layer.
#
# After Phase 0 narrows DEMO_TEMPLATES by Jaccard overlap, G1 re-ranks the
# candidates by cosine similarity between the idea text and template text,
# using whichever ``EmbeddingProvider`` is the process default. Template
# embeddings are cached in-memory (per-id) so repeated idea queries pay the
# embedding cost only once per template.
#
# Fallback contract: if the provider's ``embed_one`` returns ``None`` for
# the idea text (e.g. ollama unreachable), G1 transparently degrades to the
# Phase 0 result and stamps ``method='tag_overlap'``. If a single template
# fails to embed but the idea succeeded, that template keeps its overlap
# score so ranking is never silently lost.
# --------------------------------------------------------------------------


_TEMPLATE_EMBEDDING_CACHE: dict[str, list[float]] = {}
_CACHE_LOCK = threading.Lock()

# --------------------------------------------------------------------------
# Idea-text caching layer (sprint 2 day 4 — wires CachingEmbeddingProvider
# into G1 cascade). Idea queries are unbounded (operator-typed text), so we
# benefit from a persistent SQLite cache keyed by (provider_name, sha256(idea)).
#
# Activated when ``SYLION_EMBEDDINGS_CACHE_PATH`` is set; otherwise we use an
# ephemeral in-memory ``:memory:`` cache so the wiring is exercised in tests
# but the production flow unchanged for unset deployments.
# --------------------------------------------------------------------------

_IDEA_PROVIDER_CACHE_LOCK = threading.Lock()
_IDEA_PROVIDER_CACHE: Any = None  # CachingEmbeddingProvider | None


def _get_cached_provider() -> Any:
    """Return a :class:`CachingEmbeddingProvider` wrapping the default.

    Lazy: first call constructs a SqliteEmbeddingCache rooted at
    ``$SYLION_EMBEDDINGS_CACHE_PATH`` (default ``:memory:``) and wraps the
    process-wide :func:`get_default_provider`. Subsequent calls reuse it.
    """
    import os

    from sylion.aeis_v2.embeddings import get_default_provider
    from sylion.aeis_v2.embeddings.cache import (
        CachingEmbeddingProvider,
        SqliteEmbeddingCache,
    )

    global _IDEA_PROVIDER_CACHE
    with _IDEA_PROVIDER_CACHE_LOCK:
        if _IDEA_PROVIDER_CACHE is None:
            db_path = os.environ.get("SYLION_EMBEDDINGS_CACHE_PATH", ":memory:")
            backend = SqliteEmbeddingCache(db_path=db_path)
            _IDEA_PROVIDER_CACHE = CachingEmbeddingProvider(
                underlying=get_default_provider(),
                backend=backend,
            )
        return _IDEA_PROVIDER_CACHE


def reset_idea_embedding_cache() -> None:
    """Drop the cached :class:`CachingEmbeddingProvider`. Test helper.

    Next call to :func:`_get_cached_provider` rebuilds against the current
    ``SYLION_EMBEDDINGS_CACHE_PATH`` env value and the current default
    embedding provider.
    """
    global _IDEA_PROVIDER_CACHE
    with _IDEA_PROVIDER_CACHE_LOCK:
        _IDEA_PROVIDER_CACHE = None


def idea_embedding_cache_stats() -> dict[str, float | int]:
    """Return cache stats for telemetry/widget consumption."""
    p = _get_cached_provider()
    return p.stats.to_dict()


def _extract_tags(text: str) -> set[str]:
    """Naive whitespace+lowercase token extraction (matches Phase 0 logic)."""
    import re

    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 2}


def _get_cached_template_embedding(
    tpl_id: str,
    tpl_text: str,
    provider: Any,
) -> list[float] | None:
    """Look up (or compute and store) the embedding for a template.

    Thread-safe: cache reads/writes are guarded by ``_CACHE_LOCK``. The
    actual ``embed_one`` call happens *outside* the lock so concurrent
    queries against different templates don't serialise on the provider.
    """
    with _CACHE_LOCK:
        if tpl_id in _TEMPLATE_EMBEDDING_CACHE:
            return _TEMPLATE_EMBEDDING_CACHE[tpl_id]
    emb = provider.embed_one(tpl_text)
    if emb is not None:
        with _CACHE_LOCK:
            _TEMPLATE_EMBEDDING_CACHE[tpl_id] = emb
    return emb


def reset_template_embedding_cache() -> None:
    """Clear the template embedding cache. Test helper."""
    with _CACHE_LOCK:
        _TEMPLATE_EMBEDDING_CACHE.clear()


def match_idea_to_templates_g1(
    idea_text: str,
    *,
    top_n: int = 3,
    min_overlap: float = 0.05,
    embedding_weight: float = 0.4,
) -> list[MatchResult]:
    """G1 cascade step 2: tag-overlap + embedding refinement.

    1. Run Phase 0 tag-overlap with a wider net (``top_n*3``); if no
       Phase 0 match exists, return ``[]`` (the cascade will hand off
       to G2 LLM generation in a future commit).
    2. Embed the idea text via :func:`get_default_provider`.
    3. For each candidate, fetch (or compute & cache) the template
       embedding and compute cosine similarity.
    4. Combined score = ``(1 - w) * overlap + w * cosine``. Re-rank.
    5. ``method='embedding'`` when at least one candidate was scored
       with cosine; ``method='tag_overlap'`` when the provider returned
       ``None`` for the idea (e.g. Ollama unreachable).
    """
    from sylion.aeis_v2.embeddings import cosine_similarity

    # Stage 1 — Phase 0 with a wider net so embedding re-ranking has room.
    phase0 = match_idea_to_templates(
        idea_text, top_n=top_n * 3, min_score=min_overlap,
    )
    if not phase0:
        return []

    # Stage 2 — embeddings refinement (lazy provider with read-through cache).
    # Idea text queries pass through CachingEmbeddingProvider so repeated
    # operator queries hit the persistent SQLite store (sprint 2 day 4).
    provider = _get_cached_provider()
    idea_emb = provider.embed_one(idea_text)
    use_embeddings = idea_emb is not None

    if not use_embeddings:
        # Embeddings unavailable -> fallback to Phase 0 (already
        # carries method='tag_overlap').
        return phase0[:top_n]

    idea_tags = _extract_tags(idea_text)
    refined: list[MatchResult] = []
    for match in phase0:
        tpl = match.template
        tpl_text = (
            f"{tpl.name_pl}: {tpl.description_pl} "
            f"{' '.join(tpl.tags)}"
        )
        tpl_emb = _get_cached_template_embedding(tpl.id, tpl_text, provider)
        if tpl_emb is None:
            # Embedding failed for this template — keep the tag-overlap
            # score so the candidate is not silently dropped.
            refined.append(match)
            continue
        cos = cosine_similarity(idea_emb, tpl_emb)
        # Cosine on real embeddings can be negative; clamp to [0,1] so
        # combined stays in [0,1] (matches role_match.hybrid behaviour).
        if cos < 0.0:
            cos = 0.0
        elif cos > 1.0:
            cos = 1.0
        combined = (1.0 - embedding_weight) * match.score + embedding_weight * cos
        common_tags = sorted(set(tpl.tags) & idea_tags)
        refined.append(MatchResult(
            template=tpl,
            score=combined,
            method="embedding",
            reason_pl=(
                f"Tag-overlap {match.score:.2f} + cosine {cos:.2f} "
                f"-> {combined:.2f}; wspolne tagi: "
                f"{', '.join(common_tags) if common_tags else '(brak)'}"
            ),
        ))
    refined.sort(key=lambda m: m.score, reverse=True)
    return refined[:top_n]


__all__ = [
    "AppTemplate",
    "MatchResult",
    "DEMO_TEMPLATES",
    "validate_app_template_dict",
    "score_tag_overlap",
    "rank_templates",
    "list_templates",
    "match_idea_to_templates",
    "match_idea_to_templates_g1",
    "reset_template_embedding_cache",
    "reset_idea_embedding_cache",
    "idea_embedding_cache_stats",
]
