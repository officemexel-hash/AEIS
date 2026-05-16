"""W16 G1 cascade step 2 — tests for embeddings-refined idea→template matching.

Covers :func:`sylion.aeis_v2.apps_v2.match_idea_to_templates_g1` and the
companion REST endpoint ``POST /api/v1/apps/match-idea-g1``:

- Fallback to Phase 0 when the provider returns ``None`` (Ollama
  unreachable or any other transient failure).
- Happy-path scoring with a deterministic stub provider (no real Ollama).
- Template embedding cache: second hit must NOT re-call ``embed_one``.
- ``top_n`` cap, empty/no-overlap input, cache reset helper.
- Full HTTP test against the W16 router.

Tests install :class:`StubEmbeddingProvider` (or smaller stubs) via
:func:`set_default_provider` so the suite never shells out to a real
``ollama`` binary. Each test resets the singleton AND the template
embedding cache to avoid cross-test bleed.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.aeis_v2.apps_v2 import (
    DEMO_TEMPLATES,
    MatchResult,
    idea_embedding_cache_stats,
    match_idea_to_templates_g1,
    reset_idea_embedding_cache,
    reset_template_embedding_cache,
)
from sylion.aeis_v2.embeddings import (
    EmbeddingProvider,
    StubEmbeddingProvider,
    reset_default_provider,
    set_default_provider,
)
from sylion.api.apps_routes import router as apps_router


# --------------------------------------------------------------------------
# Test scaffolding — counting stub providers and shared fixtures.
# --------------------------------------------------------------------------


class _NoneProvider(EmbeddingProvider):
    """Stub that always returns ``None`` (mimics ollama-missing)."""

    @property
    def name(self) -> str:
        return "stub:none"

    @property
    def dim(self) -> int:
        return 0

    def embed_one(self, text: str) -> list[float] | None:
        return None


class _CountingStub(EmbeddingProvider):
    """Wraps a base provider and tracks every ``embed_one`` invocation."""

    def __init__(self, base: EmbeddingProvider) -> None:
        self._base = base
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return f"counting:{self._base.name}"

    @property
    def dim(self) -> int:
        return self._base.dim

    def embed_one(self, text: str) -> list[float] | None:
        self.calls.append(text)
        return self._base.embed_one(text)


@pytest.fixture(autouse=True)
def _reset_state() -> Any:
    """Each test starts with a fresh provider singleton + empty caches.

    Sprint 2 day 4 wired CachingEmbeddingProvider into the G1 path; the
    cached wrapper is a separate singleton so we reset it too.
    """
    reset_default_provider()
    reset_template_embedding_cache()
    reset_idea_embedding_cache()
    yield
    reset_default_provider()
    reset_template_embedding_cache()
    reset_idea_embedding_cache()


def _client() -> TestClient:
    """Return a TestClient with only the W16 router mounted (no lifespan)."""
    api = FastAPI()
    api.include_router(apps_router)
    return TestClient(api)


# --------------------------------------------------------------------------
# 1. Fallback when embeddings unavailable.
# --------------------------------------------------------------------------


def test_g1_falls_back_when_embeddings_unavailable() -> None:
    """Provider returns ``None`` for the idea -> Phase 0 result, method=tag_overlap."""
    set_default_provider(_NoneProvider())

    results = match_idea_to_templates_g1(
        "inspekcja terenowa raport audyt monitorowanie",
        top_n=3,
    )

    assert len(results) >= 1
    # Inspection idea should still pick the inspection template (Phase 0 win).
    assert results[0].template.id == "inspection_field"
    # The cascade collapsed to Phase 0 — method must reflect that.
    assert all(r.method == "tag_overlap" for r in results)
    # And the reason text is the Phase 0 wording (no "cosine" / "->" arrow).
    assert "Pokrycie tagow" in results[0].reason_pl


# --------------------------------------------------------------------------
# 2. Happy path with deterministic stub provider.
# --------------------------------------------------------------------------


def test_g1_uses_embeddings_with_stub_provider() -> None:
    """StubEmbeddingProvider produces vectors -> method=='embedding' + score formula."""
    set_default_provider(StubEmbeddingProvider())

    results = match_idea_to_templates_g1(
        "inspekcja terenowa raport audyt monitorowanie",
        top_n=3,
        embedding_weight=0.4,
    )

    assert len(results) >= 1
    assert all(isinstance(r, MatchResult) for r in results)
    # At least the top result was scored by embeddings.
    assert results[0].method == "embedding"
    # The reason text follows the G1 template ("Tag-overlap X + cosine Y -> Z").
    assert "cosine" in results[0].reason_pl
    assert "->" in results[0].reason_pl
    # Combined score is in [0, 1] and respects the formula bounds.
    for r in results:
        assert 0.0 <= r.score <= 1.0
    # Sorted descending by combined score.
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------
# 3. Template embedding cache: second pass must reuse cached vectors.
# --------------------------------------------------------------------------


def test_g1_caches_template_embeddings() -> None:
    """Repeated G1 calls re-embed the idea but reuse cached template vectors."""
    counter = _CountingStub(StubEmbeddingProvider())
    set_default_provider(counter)

    # First query primes the cache.
    first = match_idea_to_templates_g1(
        "inspekcja terenowa raport audyt monitorowanie",
        top_n=3,
    )
    assert first  # sanity
    first_calls = list(counter.calls)
    # First call: 1 idea embedding + N template embeddings (N == candidates).
    assert any("inspekcja" in c for c in first_calls)
    template_calls_first = [
        c for c in first_calls if "inspekcja" not in c.split(":", 1)[0]
    ]
    assert len(template_calls_first) >= 1, (
        "first pass should embed at least one template"
    )

    # Second query — same idea text, same candidates. Sprint 2 day 4:
    # CachingEmbeddingProvider is now wired in front of the underlying
    # provider, so the idea text is cached too. Both caches (template
    # in-memory + idea SQLite) hit, so the provider sees ZERO calls.
    counter.calls.clear()
    second = match_idea_to_templates_g1(
        "inspekcja terenowa raport audyt monitorowanie",
        top_n=3,
    )
    assert second
    assert len(counter.calls) == 0, (
        f"expected idea + templates to be fully cached on second call, "
        f"got: {counter.calls!r}"
    )


# --------------------------------------------------------------------------
# 4. top_n is respected after re-ranking.
# --------------------------------------------------------------------------


def test_g1_top_n_respected() -> None:
    """``top_n=2`` returns at most 2 results even when many candidates score."""
    set_default_provider(StubEmbeddingProvider())

    # Wide query that overlaps tags across many templates.
    big_query = (
        "inspekcja zatwierdzanie magazyn czas-pracy serwis konserwacja "
        "raporty audyt workflow"
    )
    results = match_idea_to_templates_g1(big_query, top_n=2)
    assert len(results) <= 2
    # And top_n=1 returns exactly one match (or zero if no Phase 0 overlap).
    one = match_idea_to_templates_g1(big_query, top_n=1)
    assert len(one) <= 1


# --------------------------------------------------------------------------
# 5. Empty / no-overlap idea returns empty list.
# --------------------------------------------------------------------------


def test_g1_empty_idea_returns_empty() -> None:
    """No Phase 0 overlap -> G1 short-circuits to ``[]`` (no embedding call)."""
    counter = _CountingStub(StubEmbeddingProvider())
    set_default_provider(counter)

    results = match_idea_to_templates_g1(
        "xyzzy frobnicate quuxbar plugh",
        top_n=3,
    )
    assert results == []
    # Phase 0 returned [] -> we must NOT have called the embedding provider.
    assert counter.calls == []


# --------------------------------------------------------------------------
# 6. Cache reset clears cached state.
# --------------------------------------------------------------------------


def test_g1_reset_cache_clears_state() -> None:
    """``reset_template_embedding_cache`` forces re-computation on next query."""
    counter = _CountingStub(StubEmbeddingProvider())
    set_default_provider(counter)

    match_idea_to_templates_g1("inspekcja terenowa raport audyt", top_n=3)
    # Capture template-embedding call count from the first pass.
    first_template_calls = [
        c for c in counter.calls if not c.startswith("inspekcja terenowa")
    ]
    assert len(first_template_calls) >= 1

    # Wipe BOTH caches (template in-memory + idea SQLite) and re-run.
    # Templates AND idea must be re-embedded from scratch.
    reset_template_embedding_cache()
    reset_idea_embedding_cache()
    set_default_provider(counter)  # re-pin counter for the new cached wrapper
    counter.calls.clear()
    match_idea_to_templates_g1("inspekcja terenowa raport audyt", top_n=3)
    second_template_calls = [
        c for c in counter.calls if not c.startswith("inspekcja terenowa")
    ]
    assert len(second_template_calls) >= 1, (
        "cache reset must force the provider to re-embed templates"
    )


# --------------------------------------------------------------------------
# 6b. Sprint 2 day 4 — CachingEmbeddingProvider wired into G1 path.
# --------------------------------------------------------------------------


def test_g1_idea_text_cached_across_calls() -> None:
    """Sprint 2 day 4: second call with same idea text does not re-embed it."""
    counter = _CountingStub(StubEmbeddingProvider())
    set_default_provider(counter)

    idea = "inspekcja terenowa raport audyt"
    match_idea_to_templates_g1(idea, top_n=3)
    # Idea text is what the operator typed verbatim — equality match on the
    # call list distinguishes it from the template texts (which add the
    # name + description prefix).
    first_idea_calls = [c for c in counter.calls if c == idea]
    assert len(first_idea_calls) == 1, "first call must embed the idea once"

    counter.calls.clear()
    match_idea_to_templates_g1(idea, top_n=3)
    second_idea_calls = [c for c in counter.calls if c == idea]
    assert len(second_idea_calls) == 0, (
        "second identical call must hit the SQLite cache, not the provider"
    )


def test_g1_idea_cache_stats_track_hits_and_misses() -> None:
    """idea_embedding_cache_stats reflects hits / misses after G1 calls."""
    set_default_provider(StubEmbeddingProvider())

    # Cold start — first call is a miss.
    match_idea_to_templates_g1("audyt jakosci", top_n=3)
    s1 = idea_embedding_cache_stats()
    assert s1["misses"] >= 1
    assert s1["size"] >= 1

    # Repeat — must register at least one hit.
    match_idea_to_templates_g1("audyt jakosci", top_n=3)
    s2 = idea_embedding_cache_stats()
    assert s2["hits"] >= 1
    assert s2["hit_rate"] > 0


def test_g1_idea_cache_distinct_texts_distinct_rows() -> None:
    """Different idea texts produce distinct cache rows (no false hits)."""
    set_default_provider(StubEmbeddingProvider())

    match_idea_to_templates_g1("inspekcja terenowa raport", top_n=3)
    match_idea_to_templates_g1("zatwierdzanie dokumentow autoryzacja", top_n=3)
    s = idea_embedding_cache_stats()
    assert s["size"] >= 2


# --------------------------------------------------------------------------
# 7. POST /api/v1/apps/match-idea-g1 endpoint.
# --------------------------------------------------------------------------


def test_post_match_idea_g1_endpoint() -> None:
    """Full HTTP round-trip with a stub provider and a real fallback case."""
    set_default_provider(StubEmbeddingProvider())
    client = _client()

    r = client.post(
        "/api/v1/apps/match-idea-g1",
        json={
            "idea_text": "inspekcja terenowa raport audyt monitorowanie",
            "top_n": 3,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["phase"] == "G1"
    # With a working stub provider, embeddings should drive the result.
    assert body["method_used"] == "embedding"
    assert body["fallback_reason"] is None
    assert body["match_count"] == len(body["matches"])
    assert body["match_count"] >= 1
    first = body["matches"][0]
    assert first["method"] == "embedding"
    # The G1 reason is recognisable (carries the "->" arrow + cosine token).
    assert "cosine" in first["reason_pl"]

    # Now swap to a None provider — the endpoint must surface the fallback.
    reset_default_provider()
    reset_template_embedding_cache()
    reset_idea_embedding_cache()
    set_default_provider(_NoneProvider())
    r2 = client.post(
        "/api/v1/apps/match-idea-g1",
        json={
            "idea_text": "inspekcja terenowa raport audyt monitorowanie",
            "top_n": 3,
        },
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["phase"] == "G1"
    assert body2["method_used"] == "tag_overlap"
    assert body2["fallback_reason"] is not None
    assert "Ollama" in body2["fallback_reason"]
