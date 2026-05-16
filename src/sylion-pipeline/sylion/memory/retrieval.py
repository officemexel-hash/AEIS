"""
SYLION Memory -- Retrieval

High-level retrieval over the Indexer. Provides a TF-based similarity fallback
and can build context windows within token budgets.

Phase 3 W1.3: hot reads (`retrieve`, `search_similar`) are cached under the
``memory.search`` namespace (TTL 15 min). The cache is invalidated by the
``Indexer.index_section`` and ``Indexer.remove_section`` write paths -- see
sylion/memory/indexer.py.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.infra.cache import default_ttl, get_cache, make_key
from sylion.memory.indexer import Indexer, get_indexer

log = logging.getLogger("sylion.memory.retrieval")

_CACHE_NAMESPACE = "memory.search"

CHARS_PER_TOKEN = 4


@dataclass
class RetrievalResult:
    """A single ranked retrieval result."""

    section_id: str = ""
    title: str = ""
    score: float = 0.0
    snippet: str = ""
    text: str = ""
    source: str = ""
    project_id: str = ""


@dataclass
class SimilarRun:
    """Shared-memory similarity hit returned by the public hook."""

    section_id: str = ""
    title: str = ""
    score: float = 0.0
    text: str = ""
    source: str = ""
    snippet: str = ""
    project_id: str = ""


class Retrieval:
    """High-level retrieval over the Indexer."""

    def __init__(self, indexer: Indexer | None = None, event_bus: EventBus | None = None):
        self._indexer = indexer
        self._event_bus = event_bus

    @property
    def indexer(self) -> Indexer:
        if self._indexer is None:
            self._indexer = get_indexer()
        return self._indexer

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.0,
        project_id: str | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve ranked results for a query.

        Phase 3 W1.3: result is cached under namespace ``memory.search`` keyed
        by ``(query, limit, min_score, project_id)``. Invalidated by indexer
        writes.
        """

        cache_key = make_key(_CACHE_NAMESPACE, "retrieve", query, limit,
                             min_score, project_id or "")
        cache = get_cache()
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return [RetrievalResult(**row) for row in cached_payload]

        raw_results = self.indexer.search(query, limit=limit,
                                          project_id=project_id)
        results: list[RetrievalResult] = []
        for row in raw_results:
            score = float(row.get("score", 0.0))
            if score < min_score:
                continue
            meta_row = self.indexer._conn.execute(
                "SELECT content_preview FROM index_metadata WHERE section_id = ?",
                (row.get("section_id", ""),),
            ).fetchone()
            preview = meta_row["content_preview"] if meta_row else ""
            results.append(
                RetrievalResult(
                    section_id=row.get("section_id", ""),
                    title=row.get("title", ""),
                    score=score,
                    snippet="",
                    text=preview,
                    source=f"index:{row.get('section_id', '')}",
                    project_id=row.get("project_id", "") or "",
                )
            )

        try:
            cache.set(
                cache_key,
                [asdict(r) for r in results],
                ttl=default_ttl(_CACHE_NAMESPACE),
            )
        except Exception:                         # noqa: BLE001
            log.warning("cache set failed for memory.search", exc_info=True)

        self._emit(
            "retrieval.retrieve",
            {
                "query": query,
                "project_id": project_id or "",
                "results_count": len(results),
            },
        )
        return results

    def search_similar(self, query: str, k: int = 3, project_id: str | None = None) -> list[SimilarRun]:
        """
        Hook v1.0 (2026-04-24)
        Changes: initial TF-based similarity fallback
        """

        retrieved = self.retrieve(query, limit=max(k, 1), min_score=0.0,
                                  project_id=project_id)
        if not retrieved:
            return []

        max_score = max(result.score for result in retrieved) or 1.0
        similar: list[SimilarRun] = []
        for result in retrieved[:k]:
            similar.append(
                SimilarRun(
                    section_id=result.section_id,
                    title=result.title,
                    score=round(result.score / max_score, 6),
                    text=result.text or result.title,
                    source=result.source or f"index:{result.section_id}",
                    snippet=result.snippet,
                    project_id=result.project_id,
                )
            )
        return similar

    def get_context(self, query: str, max_tokens: int = 4000,
                    project_id: str | None = None) -> str:
        """Assemble top search results into a context string within token budget."""

        results = self.retrieve(query, limit=50, min_score=0.0,
                                project_id=project_id)
        max_chars = max_tokens * CHARS_PER_TOKEN
        context_parts: list[str] = []
        used_chars = 0

        for result in results:
            header = f"## {result.title}" if result.title else f"## Section {result.section_id[:12]}"
            body = result.text or result.snippet
            snippet = f"{header} (score: {result.score})"
            if body:
                snippet = f"{snippet}\n{body}"

            entry_chars = len(snippet) + 2
            if used_chars + entry_chars > max_chars:
                break

            context_parts.append(snippet)
            used_chars += entry_chars

        context = "\n\n".join(context_parts)
        self._emit(
            "retrieval.get_context",
            {
                "query": query,
                "project_id": project_id or "",
                "max_tokens": max_tokens,
                "sections_used": len(context_parts),
                "approx_tokens": used_chars // CHARS_PER_TOKEN,
            },
        )
        return context

    def _emit(self, topic: str, payload: dict[str, Any]):
        if self._event_bus:
            self._event_bus.publish(
                SylionEvent(
                    event_id="",
                    topic=topic,
                    payload=payload,
                    source_module="memory.retrieval",
                )
            )


_retrieval: Retrieval | None = None


def get_retrieval(indexer: Indexer | None = None, event_bus: EventBus | None = None) -> Retrieval:
    global _retrieval
    if _retrieval is None:
        _retrieval = Retrieval(indexer, event_bus)
    return _retrieval


def reset_retrieval() -> None:
    global _retrieval
    _retrieval = None


def search_similar(query: str, k: int = 3, project_id: str | None = None) -> list[SimilarRun]:
    """Hook v1.0 (2026-04-24): shared similarity search."""

    return get_retrieval().search_similar(query, k=k, project_id=project_id)
