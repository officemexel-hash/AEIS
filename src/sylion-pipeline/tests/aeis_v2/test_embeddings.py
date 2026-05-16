"""W13/W16 G1 unified embeddings provider tests.

Covers the abstraction at :mod:`sylion.aeis_v2.embeddings.provider`:

- :class:`OllamaEmbeddingProvider` — error paths (binary missing, timeout,
  bad JSON, non-zero return code) and the happy path with a stubbed
  subprocess.
- :class:`StubEmbeddingProvider` — determinism + dimensionality.
- :func:`cosine_similarity` — orthogonal/identical/zero/length-mismatch.
- Default-provider singleton lifecycle.

All ollama subprocess calls are stubbed via monkeypatch; the test never
shells out to a real ``ollama`` binary.
"""
from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from typing import Any

import pytest

from sylion.aeis_v2.embeddings import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    StubEmbeddingProvider,
    cosine_similarity,
    get_default_provider,
    reset_default_provider,
    set_default_provider,
)
from sylion.aeis_v2.embeddings import provider as provider_mod


# --------------------------------------------------------------------------
# Helpers: stub ``subprocess.CompletedProcess`` for ollama calls.
# --------------------------------------------------------------------------


@dataclass
class _FakeCompleted:
    """Minimal stand-in for :class:`subprocess.CompletedProcess`."""

    returncode: int
    stdout: str
    stderr: str = ""


@pytest.fixture(autouse=True)
def _reset_default_singleton() -> Any:
    """Ensure each test starts with a fresh default provider state."""
    reset_default_provider()
    yield
    reset_default_provider()


# --------------------------------------------------------------------------
# OllamaEmbeddingProvider — failure paths.
# --------------------------------------------------------------------------


def test_ollama_provider_returns_none_when_ollama_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``ollama`` binary is missing, ``subprocess.run`` raises
    FileNotFoundError; provider must swallow it and return ``None``."""

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("ollama: command not found")

    monkeypatch.setattr(provider_mod.subprocess, "run", _raise)

    p = OllamaEmbeddingProvider()
    assert p.embed_one("anything") is None
    # Empty input takes the early-return branch (subprocess never called).
    assert p.embed_one("") is None
    assert p.embed_one("   ") is None


def test_ollama_provider_returns_none_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Long-running ollama invocations time out — must surface as ``None``."""

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd="ollama", timeout=10)

    monkeypatch.setattr(provider_mod.subprocess, "run", _raise)

    p = OllamaEmbeddingProvider(timeout_s=0.01)
    assert p.embed_one("hello") is None


def test_ollama_provider_returns_none_on_nonzero_returncode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero exit code (e.g. model not pulled) -> ``None``."""

    def _fake_run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(returncode=1, stdout="", stderr="model not found")

    monkeypatch.setattr(provider_mod.subprocess, "run", _fake_run)

    assert OllamaEmbeddingProvider().embed_one("hello") is None


def test_ollama_provider_parses_json_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: ``{"embedding": [...]}`` parses into a list[float]."""
    expected = [0.1, 0.2, 0.3, -0.4]

    def _fake_run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(
            returncode=0, stdout=json.dumps({"embedding": expected})
        )

    monkeypatch.setattr(provider_mod.subprocess, "run", _fake_run)

    out = OllamaEmbeddingProvider().embed_one("hello")
    assert out is not None
    assert out == pytest.approx(expected)
    # Type must be list[float] — even if input had ints, we coerce.
    assert all(isinstance(x, float) for x in out)


def test_ollama_provider_parses_embeddings_array_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newer ollama returns ``{"embeddings": [[...]]}`` — must also parse."""
    expected = [0.5, 0.6, 0.7]

    def _fake_run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(
            returncode=0, stdout=json.dumps({"embeddings": [expected]})
        )

    monkeypatch.setattr(provider_mod.subprocess, "run", _fake_run)

    out = OllamaEmbeddingProvider().embed_one("hello")
    assert out is not None
    assert out == pytest.approx(expected)


def test_ollama_provider_returns_none_on_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-JSON stdout (e.g. ollama wrote a help banner) -> ``None``."""

    def _fake_run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(returncode=0, stdout="not-json {{{")

    monkeypatch.setattr(provider_mod.subprocess, "run", _fake_run)

    assert OllamaEmbeddingProvider().embed_one("hello") is None


def test_ollama_provider_returns_none_on_empty_embedding_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``{"embedding": []}`` is treated as a failure, not a valid vector."""

    def _fake_run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(returncode=0, stdout=json.dumps({"embedding": []}))

    monkeypatch.setattr(provider_mod.subprocess, "run", _fake_run)

    assert OllamaEmbeddingProvider().embed_one("hello") is None


def test_ollama_provider_returns_none_on_non_numeric_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A string or bool inside the vector breaks the parser -> ``None``."""

    def _fake_run(*_args: object, **_kwargs: object) -> _FakeCompleted:
        return _FakeCompleted(
            returncode=0, stdout=json.dumps({"embedding": [0.1, "oops", 0.3]})
        )

    monkeypatch.setattr(provider_mod.subprocess, "run", _fake_run)

    assert OllamaEmbeddingProvider().embed_one("hello") is None


def test_ollama_provider_name_includes_model() -> None:
    """``name`` defaults to ``ollama:<model>``."""
    p = OllamaEmbeddingProvider(model="custom-model")
    assert p.name == "ollama:custom-model"
    assert p.dim == 768


def test_ollama_provider_embed_many_loops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default ``embed_many`` calls ``embed_one`` per text (order preserved)."""
    calls: list[str] = []

    def _fake_run(args: list[str], **_kwargs: object) -> _FakeCompleted:
        # Last positional arg is the text.
        calls.append(args[-1])
        return _FakeCompleted(
            returncode=0, stdout=json.dumps({"embedding": [float(len(args[-1]))]})
        )

    monkeypatch.setattr(provider_mod.subprocess, "run", _fake_run)

    out = OllamaEmbeddingProvider().embed_many(["a", "bb", "ccc"])
    assert calls == ["a", "bb", "ccc"]
    assert out == [[1.0], [2.0], [3.0]]


# --------------------------------------------------------------------------
# StubEmbeddingProvider.
# --------------------------------------------------------------------------


def test_stub_provider_returns_deterministic_vector() -> None:
    """Same input must produce byte-identical output across calls."""
    p = StubEmbeddingProvider()
    v1 = p.embed_one("ETL pipeline")
    v2 = p.embed_one("ETL pipeline")
    assert v1 is not None and v2 is not None
    assert v1 == v2
    # Different input -> different vector (collision is astronomically unlikely).
    v3 = p.embed_one("frontend dashboard")
    assert v3 != v1


def test_stub_provider_dim_is_64() -> None:
    """Stub vectors are exactly 64-d and live in [-1, 1)."""
    p = StubEmbeddingProvider()
    assert p.dim == 64
    assert p.name == "stub:hash"
    v = p.embed_one("hello")
    assert v is not None
    assert len(v) == 64
    assert all(-1.0 <= x < 1.0 for x in v)


def test_stub_provider_returns_none_on_empty_input() -> None:
    """Empty string still returns ``None`` (matches Ollama provider)."""
    assert StubEmbeddingProvider().embed_one("") is None


# --------------------------------------------------------------------------
# cosine_similarity helper.
# --------------------------------------------------------------------------


def test_cosine_similarity_orthogonal_zero() -> None:
    """Orthogonal vectors -> cos == 0.0."""
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    # Zero vector on either side -> 0.0 (no NaN).
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 1.0], [0.0, 0.0]) == 0.0
    # Length mismatch -> 0.0 (defensive).
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0
    # Empty vectors -> 0.0.
    assert cosine_similarity([], []) == 0.0


def test_cosine_similarity_identical_one() -> None:
    """Identical vectors -> cos == 1.0 within float epsilon (scale-invariant)."""
    v = [0.5, 0.25, 0.75, 1.0]
    assert math.isclose(cosine_similarity(v, v), 1.0, abs_tol=1e-9)
    # Cosine is scale-invariant: 3x the same vector still cos == 1.0.
    assert math.isclose(
        cosine_similarity(v, [x * 3.0 for x in v]), 1.0, abs_tol=1e-9
    )
    # Anti-parallel -> -1.0.
    assert math.isclose(
        cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0, abs_tol=1e-9
    )


# --------------------------------------------------------------------------
# Default-provider singleton lifecycle.
# --------------------------------------------------------------------------


def test_get_default_provider_is_singleton() -> None:
    """Two consecutive ``get_default_provider`` calls return the same object."""
    a = get_default_provider()
    b = get_default_provider()
    assert a is b
    # Default backend is Ollama.
    assert isinstance(a, OllamaEmbeddingProvider)


def test_set_default_provider_swaps_singleton() -> None:
    """``set_default_provider`` replaces the cached default for subsequent calls."""
    stub = StubEmbeddingProvider()
    set_default_provider(stub)
    assert get_default_provider() is stub
    # Reset path returns to the lazy Ollama default.
    reset_default_provider()
    fresh = get_default_provider()
    assert fresh is not stub
    assert isinstance(fresh, OllamaEmbeddingProvider)


def test_embedding_provider_is_abstract() -> None:
    """Direct instantiation of the ABC must fail (sanity guard)."""
    with pytest.raises(TypeError):
        EmbeddingProvider()  # type: ignore[abstract]
