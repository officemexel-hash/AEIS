"""W13 hybrid task-role matcher tests (ADR-001 Decision #5).

Two-stage matching covered:

1. Tag-overlap Jaccard primitives (``tag_overlap_score``).
2. Cosine similarity primitives (``cosine_similarity``).
3. Lazy ollama wrapper (``get_embedding_or_none``) — the FileNotFoundError
   path is the most important since ollama is rarely installed on CI.
4. ``hybrid_match`` — fallback path (no ollama) and skill-level filter.
5. ``POST /api/v1/role-catalog/hybrid-match`` endpoint via FastAPI.

Embeddings are stubbed via monkeypatch — never call out to a real ollama
binary in these tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from sylion.aeis_v2.role_match import hybrid as hybrid_mod
from sylion.aeis_v2.role_match import (
    HybridMatch,
    cosine_similarity,
    get_embedding_or_none,
    hybrid_match,
    jaccard_set_similarity,
    tag_overlap_score,
)
from sylion.api import role_catalog_routes
from sylion.api.role_catalog_routes import router as role_catalog_router


# --------------------------------------------------------------------------
# Test fixtures — synthetic roles so we don't depend on the YAML registry.
# --------------------------------------------------------------------------


@dataclass
class _FakeRole:
    """Minimal stand-in for ``sylion.skills.roles.Role`` (only what the
    matcher reads): id/name_pl/description_pl/capabilities/skill_level."""

    id: str
    name_pl: str
    description_pl: str
    capabilities: tuple[str, ...]
    skill_level: str = "any"


_FAKE_ROLES = [
    _FakeRole(
        id="data_engineer",
        name_pl="Inzynier danych",
        description_pl="Projektowanie pipeline'ow ETL i hurtowni danych.",
        capabilities=("sql", "python", "airflow", "etl"),
        skill_level="senior",
    ),
    _FakeRole(
        id="frontend_specialist",
        name_pl="Specjalista frontend",
        description_pl="React, TypeScript, Next.js — interfejsy uzytkownika.",
        capabilities=("typescript", "react", "nextjs"),
        skill_level="mid",
    ),
    _FakeRole(
        id="ai_orchestrator",
        name_pl="AI Orchestrator",
        description_pl="Routowanie zadan przez wiele modeli LLM.",
        capabilities=("llm_routing", "prompt_engineering"),
        skill_level="principal",
    ),
    _FakeRole(
        id="legacy_no_caps",
        name_pl="Legacy",
        description_pl="Stara rola bez tagow.",
        capabilities=(),
        skill_level="any",
    ),
]


def _client() -> TestClient:
    """Mount the W7 router on a bare FastAPI app (no lifespan, no DB)."""
    api = FastAPI()
    api.include_router(role_catalog_router)
    return TestClient(api)


# --------------------------------------------------------------------------
# tag_overlap_score (Jaccard primitives).
# --------------------------------------------------------------------------


def test_tag_overlap_score_jaccard() -> None:
    """Jaccard = |A n B| / |A u B| — verify on a hand-checked example."""
    task = {"sql", "python", "airflow"}
    role = {"sql", "python", "etl"}
    # intersection: {sql, python} = 2; union: {sql, python, airflow, etl} = 4.
    assert tag_overlap_score(task, role) == pytest.approx(2 / 4)


def test_tag_overlap_score_empty_union_returns_zero() -> None:
    """No tags on either side -> score must be 0.0 (never NaN/ZeroDivision)."""
    assert tag_overlap_score(set(), set()) == 0.0
    # Empty role set with a non-empty task set: |inter|=0, |union|>0 -> 0.0.
    assert tag_overlap_score({"sql"}, set()) == 0.0
    # Identical sets -> 1.0 (sanity check around the edge).
    assert tag_overlap_score({"sql"}, {"sql"}) == 1.0


def test_jaccard_set_similarity_identical() -> None:
    assert jaccard_set_similarity({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_set_similarity_empty_both() -> None:
    assert jaccard_set_similarity(set(), set()) == 1.0


def test_jaccard_set_similarity_one_empty() -> None:
    assert jaccard_set_similarity({"a"}, set()) == 0.0


def test_jaccard_set_similarity_partial_overlap() -> None:
    assert jaccard_set_similarity({"a", "b", "c"}, {"b", "c", "d"}) == pytest.approx(0.5)


def test_jaccard_set_similarity_no_overlap() -> None:
    assert jaccard_set_similarity({"a"}, {"b"}) == 0.0


# --------------------------------------------------------------------------
# cosine_similarity (numeric primitives).
# --------------------------------------------------------------------------


def test_cosine_similarity_orthogonal_zero() -> None:
    """Two orthogonal vectors must yield cosine == 0.0."""
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    # And explicitly when one side is the zero vector.
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    # Length mismatch -> 0.0 (defensive).
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_cosine_similarity_identical_one() -> None:
    """Two identical vectors must yield cosine == 1.0 (within float epsilon)."""
    v = [0.5, 0.25, 0.75, 1.0]
    assert math.isclose(cosine_similarity(v, v), 1.0, abs_tol=1e-9)
    # Scaled version still cos == 1.0 (cosine is scale-invariant).
    assert math.isclose(
        cosine_similarity(v, [x * 3.0 for x in v]), 1.0, abs_tol=1e-9
    )


# --------------------------------------------------------------------------
# get_embedding_or_none — ollama fallback path.
# --------------------------------------------------------------------------


def test_get_embedding_returns_none_when_ollama_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``ollama`` binary is missing, subprocess.run raises
    FileNotFoundError; the helper must swallow it and return ``None``."""

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("ollama: command not found")

    monkeypatch.setattr(hybrid_mod.subprocess, "run", _raise)
    assert get_embedding_or_none("anything") is None
    # Empty input also returns None without ever calling subprocess.
    assert get_embedding_or_none("") is None


# --------------------------------------------------------------------------
# hybrid_match — end-to-end on synthetic roles.
# --------------------------------------------------------------------------


def test_hybrid_match_falls_back_to_tag_overlap_when_embeddings_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``get_embedding_or_none`` returns ``None`` (ollama unreachable):

    - The matcher still ranks by Jaccard tag overlap.
    - ``embedding_sim`` is 0.0 on every result.
    - ``score`` equals ``tag_overlap`` exactly.
    """
    monkeypatch.setattr(hybrid_mod, "get_embedding_or_none", lambda _text: None)

    matches = hybrid_match(
        task_description="Build an ETL pipeline.",
        task_tags={"sql", "python", "airflow"},
        roles=_FAKE_ROLES,
        top_overlap=10,
        top_final=3,
    )

    assert matches, "expected at least one match in fallback mode"
    top = matches[0]
    assert top.role_id == "data_engineer"
    assert top.tag_overlap > 0.0
    assert top.embedding_sim == 0.0
    assert top.score == pytest.approx(top.tag_overlap)
    # Reason text must signal that embeddings were unavailable.
    assert "fallback" in top.reason_pl.lower() or "niedost" in top.reason_pl.lower()
    # to_dict serialises as a plain dict (REST-friendly).
    payload = top.to_dict()
    assert payload["role_id"] == "data_engineer"
    assert "score" in payload and "embedding_sim" in payload


def test_hybrid_match_filters_by_skill_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``skill_level='senior'`` filter must drop the ``mid`` role even
    when its tag overlap would otherwise be the highest."""
    monkeypatch.setattr(hybrid_mod, "get_embedding_or_none", lambda _text: None)

    matches = hybrid_match(
        task_description="Build a React + TypeScript dashboard.",
        task_tags={"react", "typescript"},
        roles=_FAKE_ROLES,
        skill_level="senior",
    )
    matched_ids = {m.role_id for m in matches}
    # frontend_specialist is mid-level — must be filtered out by senior+.
    assert "frontend_specialist" not in matched_ids


def test_hybrid_match_uses_embeddings_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When stubbed embeddings are returned, ``embedding_sim`` must surface
    on results and the combined score becomes ``0.6*overlap + 0.4*emb``."""

    def _fake_embed(text: str) -> list[float] | None:
        # Different texts -> different embeddings; pick a tiny hand-tuned
        # space so the data_engineer description is closest to the task.
        if not text:
            return None
        if "ETL" in text or "etl" in text:
            return [1.0, 0.0]
        if "data_engineer" in text or "Inzynier danych" in text:
            return [0.9, 0.4358898943540674]  # cos ~= 0.9
        return [0.0, 1.0]

    monkeypatch.setattr(hybrid_mod, "get_embedding_or_none", _fake_embed)

    matches = hybrid_match(
        task_description="Build an ETL pipeline for analytics.",
        task_tags={"sql", "python"},
        roles=_FAKE_ROLES,
    )
    assert matches
    top = matches[0]
    assert top.role_id == "data_engineer"
    assert top.embedding_sim > 0.0
    # Combined score formula: 0.6 * overlap + 0.4 * emb.
    expected = 0.6 * top.tag_overlap + 0.4 * top.embedding_sim
    assert top.score == pytest.approx(expected)
    # Reason text should mention embeddings / nomic.
    assert "embeddings" in top.reason_pl.lower() or "nomic" in top.reason_pl.lower()


# --------------------------------------------------------------------------
# REST: POST /api/v1/role-catalog/hybrid-match
# --------------------------------------------------------------------------


def test_post_hybrid_match_returns_top_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through FastAPI. With embeddings stubbed to ``None`` the
    response shape stays stable and ``used_embeddings`` is False."""
    # Force ollama-unavailable path so the test is hermetic.
    monkeypatch.setattr(
        "sylion.aeis_v2.role_match.hybrid.get_embedding_or_none",
        lambda _text: None,
    )

    client = _client()
    r = client.post(
        "/api/v1/role-catalog/hybrid-match",
        json={
            "task_description": "Build an ETL pipeline for daily analytics.",
            "task_tags": ["sql", "python"],
            "skill_level": None,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "hybrid-jaccard+nomic-embed-text"
    assert body["used_embeddings"] is False
    assert body["task_tags"] == ["sql", "python"]
    assert isinstance(body["matches"], list)
    assert 0 < len(body["matches"]) <= 3
    top = body["matches"][0]
    # Real registry has data_engineer carrying sql+python -> must rank #1.
    assert top["role_id"] == "data_engineer"
    assert top["tag_overlap"] > 0.0
    assert top["embedding_sim"] == 0.0
    assert "reason_pl" in top
    assert "skill_level" in top
    assert "capabilities" in top


def test_post_hybrid_match_rejects_invalid_skill_level() -> None:
    """Invalid skill_level -> 400 (mirrors /match-task contract)."""
    client = _client()
    r = client.post(
        "/api/v1/role-catalog/hybrid-match",
        json={
            "task_description": "Anything.",
            "task_tags": ["sql"],
            "skill_level": "wizard",
        },
    )
    assert r.status_code == 400


# --------------------------------------------------------------------------
# Light sanity check on the public surface (regression guard).
# --------------------------------------------------------------------------


def test_hybrid_match_dataclass_to_dict_round_trip() -> None:
    """``HybridMatch.to_dict`` is the wire format — keys must stay stable."""
    m = HybridMatch(
        role_id="data_engineer",
        role_name="Inzynier danych",
        score=0.75,
        tag_overlap=0.5,
        embedding_sim=0.875,
        reason_pl="test reason",
        skill_level="senior",
        capabilities=["sql", "python"],
    )
    d = m.to_dict()
    assert d == {
        "role_id": "data_engineer",
        "role_name": "Inzynier danych",
        "score": 0.75,
        "tag_overlap": 0.5,
        "embedding_sim": 0.875,
        "reason_pl": "test reason",
        "skill_level": "senior",
        "capabilities": ["sql", "python"],
    }


# --------------------------------------------------------------------------
# W13/W16 G1 — provider pluggability via embeddings.set_default_provider.
# --------------------------------------------------------------------------


def test_hybrid_match_uses_stub_provider_when_set() -> None:
    """When the default provider is swapped to ``StubEmbeddingProvider`` the
    matcher MUST exercise the embeddings code path:

    - ``used_embeddings`` is true (reason text mentions ``nomic``/``embeddings``,
      NOT the fallback wording).
    - The combined score is computed via ``0.6*overlap + 0.4*embedding_sim``
      (i.e. the embeddings branch ran) — verified by reproducing the formula.
    - At least one candidate gets a non-zero ``embedding_sim`` (Stub vectors
      are deterministic but not orthogonal-on-average — over the real role
      catalog at least one cosine clears the zero-clamp, proving the Stub
      payload is consumed end-to-end).
    """
    from sylion.aeis_v2.embeddings import (
        StubEmbeddingProvider,
        reset_default_provider,
        set_default_provider,
    )

    set_default_provider(StubEmbeddingProvider())
    try:
        matches = hybrid_match(
            task_description="data engineering ETL pipeline analytics",
            task_tags={"sql", "python"},
            roles=_FAKE_ROLES,
        )
        assert matches, "expected at least one match with stub provider active"
        top = matches[0]

        # Reason text must signal the embeddings branch was active.
        reason_lower = top.reason_pl.lower()
        assert "embeddings" in reason_lower or "nomic" in reason_lower
        assert "fallback" not in reason_lower
        assert "niedost" not in reason_lower

        # Combined score must follow the embeddings formula (not pure overlap).
        expected = 0.6 * top.tag_overlap + 0.4 * top.embedding_sim
        assert top.score == pytest.approx(expected), (
            f"score={top.score} expected={expected} "
            f"(overlap={top.tag_overlap}, emb_sim={top.embedding_sim})"
        )

        # End-to-end Stub consumption: at least one candidate must report a
        # strictly positive embedding_sim (Stub vectors are reproducible but
        # not all orthogonal — at least one role text correlates positively
        # with the task text).
        assert any(m.embedding_sim > 0.0 for m in matches), (
            "expected at least one candidate with embedding_sim > 0 when Stub is active"
        )
    finally:
        reset_default_provider()


def test_hybrid_match_after_reset_provider_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Set Stub, then reset — the matcher must rebuild an Ollama default.
    Since ollama is not actually running in CI (subprocess.run is patched
    to raise FileNotFoundError), every embedding call returns ``None`` and
    the matcher falls back to tag-overlap-only ranking.
    """
    from sylion.aeis_v2.embeddings import (
        StubEmbeddingProvider,
        reset_default_provider,
        set_default_provider,
    )

    # Step 1: install Stub so we know the singleton is non-default.
    set_default_provider(StubEmbeddingProvider())
    # Step 2: reset — next get_default_provider() call will rebuild Ollama.
    reset_default_provider()
    # Step 3: simulate ollama-missing — patch subprocess.run on the provider
    # module (the actual call site after migration). Since ``subprocess`` is
    # a singleton module, patching it via ``hybrid_mod.subprocess`` also
    # affects the provider's import.
    def _raise(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("ollama: command not found")

    monkeypatch.setattr(hybrid_mod.subprocess, "run", _raise)

    try:
        matches = hybrid_match(
            task_description="Build an ETL pipeline.",
            task_tags={"sql", "python", "airflow"},
            roles=_FAKE_ROLES,
        )
        assert matches, "expected fallback ranking to still produce matches"
        top = matches[0]
        # Fallback path -> embedding_sim is exactly 0, score == tag_overlap.
        assert top.embedding_sim == 0.0
        assert top.score == pytest.approx(top.tag_overlap)
        reason_lower = top.reason_pl.lower()
        assert "fallback" in reason_lower or "niedost" in reason_lower
    finally:
        reset_default_provider()


# Reference the imported module to keep linters happy (it's used via
# monkeypatch.setattr above).
_ = role_catalog_routes
