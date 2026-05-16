"""Tests for ``sylion.aeis_v2.apps_v2.g2_generation`` — W16 G2 LLM generator.

Sprint 3 deliverable. Verifies the ``LlmTemplateGenerator`` flow end-to-end
*without* shelling out to a real Ollama process — every test stubs the
subprocess via monkeypatch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.apps_v2 import (
    DEMO_TEMPLATES,
    AppTemplate,
    MatchResult,
)
from sylion.aeis_v2.apps_v2.g2_generation import (
    DEFAULT_MODEL,
    DEFAULT_NO_MATCH_THRESHOLD,
    GenerationOutcome,
    LlmTemplateGenerator,
    _extract_json,
    _validate_template_dict,
    should_invoke_g2,
)


# ---------------------------------------------------------------------------
# Module-level invariants
# ---------------------------------------------------------------------------


def test_default_model_documented() -> None:
    """ADR-002 multi-model routing matrix: gpt-oss:20b is the v2 default."""
    assert DEFAULT_MODEL == "gpt-oss:20b"


def test_default_no_match_threshold_matches_g1_floor() -> None:
    """0.4 is the W16 G1 step 3 ``conditional`` floor (sprint 2 day 4)."""
    assert DEFAULT_NO_MATCH_THRESHOLD == 0.4


def test_constructor_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError):
        LlmTemplateGenerator(timeout_s=0)


# ---------------------------------------------------------------------------
# should_invoke_g2 — gating helper
# ---------------------------------------------------------------------------


def _match(score: float) -> MatchResult:
    return MatchResult(
        template=DEMO_TEMPLATES[0], score=score,
        method="tag_overlap", reason_pl="t",
    )


def test_should_invoke_g2_no_matches_returns_true() -> None:
    """Empty match list → G2 must run (nothing to compare)."""
    assert should_invoke_g2([]) is True


def test_should_invoke_g2_high_score_skips() -> None:
    assert should_invoke_g2([_match(0.85)]) is False


def test_should_invoke_g2_below_threshold_runs() -> None:
    assert should_invoke_g2([_match(0.3)]) is True


def test_should_invoke_g2_threshold_boundary() -> None:
    """Exact threshold value does NOT trigger G2 (strict less-than)."""
    assert should_invoke_g2([_match(0.4)], threshold=0.4) is False


# ---------------------------------------------------------------------------
# _extract_json — Ollama stdout parser
# ---------------------------------------------------------------------------


def test_extract_json_pure_json() -> None:
    out = '{"id": "x", "name_pl": "y"}'
    assert _extract_json(out) == {"id": "x", "name_pl": "y"}


def test_extract_json_with_chatter_prefix() -> None:
    out = 'Sure, here is the JSON:\n{"id": "x"}\nDone.'
    assert _extract_json(out) == {"id": "x"}


def test_extract_json_returns_none_on_garbage() -> None:
    assert _extract_json("nothing here") is None


def test_extract_json_returns_none_on_empty() -> None:
    assert _extract_json("") is None


def test_extract_json_rejects_top_level_array() -> None:
    """Top-level JSON arrays don't match — we only accept dicts."""
    assert _extract_json("[1, 2, 3]") is None


# ---------------------------------------------------------------------------
# _validate_template_dict — bounds + required keys
# ---------------------------------------------------------------------------


def _good_dict() -> dict[str, Any]:
    return {
        "id": "test_app",
        "name_pl": "Test aplikacja",
        "description_pl": (
            "Opis aplikacji testowej z okolo stoma znakami "
            "by zmiescic sie w widelkach 50-200."
        ),
        "object_type_ids": ["customer", "project", "task"],
        "widget_ids": ["ObjectListView", "ChartWidget", "KpiCard"],
        "tags": ["a", "b", "c", "d", "e"],
    }


def test_validate_happy_path() -> None:
    ok, errors = _validate_template_dict(_good_dict())
    assert ok is True
    assert errors == []


def test_validate_rejects_missing_id() -> None:
    d = _good_dict()
    del d["id"]
    ok, errors = _validate_template_dict(d)
    assert ok is False
    assert any("id" in e for e in errors)


def test_validate_rejects_short_description() -> None:
    d = _good_dict()
    d["description_pl"] = "krotko"
    ok, errors = _validate_template_dict(d)
    assert ok is False
    assert any("description_pl" in e for e in errors)


def test_validate_rejects_too_few_object_types() -> None:
    d = _good_dict()
    d["object_type_ids"] = ["only_one"]
    ok, errors = _validate_template_dict(d)
    assert ok is False
    assert any("object_type_ids" in e for e in errors)


def test_validate_rejects_too_many_tags() -> None:
    d = _good_dict()
    d["tags"] = list("abcdefghi")  # 9 tags > max 8
    ok, errors = _validate_template_dict(d)
    assert ok is False
    assert any("tags" in e for e in errors)


# ---------------------------------------------------------------------------
# LlmTemplateGenerator — subprocess stubbed
# ---------------------------------------------------------------------------


def _stub_subprocess_run(stdout: str, returncode: int = 0):
    """Build a monkeypatch replacement for subprocess.run."""

    class _Result:
        def __init__(self) -> None:
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def _fake(*_args: Any, **_kwargs: Any) -> _Result:
        return _Result()

    return _fake


def _audit_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect the module-level audit log to a tmp file."""
    import sylion.aeis_v2.apps_v2.g2_generation as mod

    audit = tmp_path / "g2.jsonl"
    monkeypatch.setattr(mod, "G2_AUDIT_LOG_PATH", audit)
    return audit


def test_generate_happy_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _audit_to_tmp(monkeypatch, tmp_path)
    valid_json = json.dumps(_good_dict())
    monkeypatch.setattr(
        "subprocess.run", _stub_subprocess_run(valid_json),
    )
    g = LlmTemplateGenerator()
    outcome = g.generate("audyt jakosci pomieszczen")
    assert isinstance(outcome, GenerationOutcome)
    assert outcome.succeeded is True
    assert outcome.fallback_used is False
    assert outcome.template is not None
    assert outcome.template.id == "test_app"


def test_generate_empty_idea_returns_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _audit_to_tmp(monkeypatch, tmp_path)
    g = LlmTemplateGenerator()
    outcome = g.generate("")
    assert outcome.succeeded is False
    assert outcome.fallback_used is False
    assert outcome.error == "empty_idea_text"


def test_generate_subprocess_timeout_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    import subprocess

    _audit_to_tmp(monkeypatch, tmp_path)

    def _raise_timeout(*_a: Any, **_kw: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="ollama", timeout=1)

    monkeypatch.setattr("subprocess.run", _raise_timeout)
    g = LlmTemplateGenerator()
    outcome = g.generate("test idea")
    assert outcome.succeeded is False
    assert outcome.fallback_used is True
    assert outcome.error == "subprocess_timeout"
    assert outcome.template is not None  # demo fallback


def test_generate_ollama_missing_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _audit_to_tmp(monkeypatch, tmp_path)

    def _missing(*_a: Any, **_kw: Any) -> Any:
        raise FileNotFoundError("ollama not on PATH")

    monkeypatch.setattr("subprocess.run", _missing)
    g = LlmTemplateGenerator()
    outcome = g.generate("test idea")
    assert outcome.error == "ollama_binary_not_found"
    assert outcome.fallback_used is True


def test_generate_garbage_stdout_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _audit_to_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "subprocess.run", _stub_subprocess_run("not json at all"),
    )
    g = LlmTemplateGenerator()
    outcome = g.generate("test idea")
    assert outcome.error == "json_parse_failed"
    assert outcome.fallback_used is True


def test_generate_invalid_template_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _audit_to_tmp(monkeypatch, tmp_path)
    bad = json.dumps({"id": "x"})  # missing required fields
    monkeypatch.setattr("subprocess.run", _stub_subprocess_run(bad))
    g = LlmTemplateGenerator()
    outcome = g.generate("test idea")
    assert outcome.error is not None
    assert outcome.error.startswith("validation_failed")
    assert outcome.fallback_used is True


def test_generate_returncode_nonzero_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _audit_to_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "subprocess.run", _stub_subprocess_run("oops", returncode=1),
    )
    g = LlmTemplateGenerator()
    outcome = g.generate("test idea")
    assert outcome.error == "ollama_returncode: 1"
    assert outcome.fallback_used is True


# ---------------------------------------------------------------------------
# Audit chain integration
# ---------------------------------------------------------------------------


def test_generate_emits_chained_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from sylion.aeis_v2.audit_chain import verify_chain

    audit = _audit_to_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "subprocess.run", _stub_subprocess_run(json.dumps(_good_dict())),
    )
    g = LlmTemplateGenerator()
    g.generate("test idea")
    g.generate("another idea")
    assert audit.exists()
    assert verify_chain(audit) == []
    contents = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    assert all(c.get("kind") == "g2_template_gen.attempt" for c in contents)


def test_generate_audit_does_not_leak_idea_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """idea_text is hashed (idea_hash), never echoed verbatim."""
    audit = _audit_to_tmp(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "subprocess.run", _stub_subprocess_run(json.dumps(_good_dict())),
    )
    g = LlmTemplateGenerator()
    secret_idea = "very-secret-business-plan-do-not-leak"
    g.generate(secret_idea)
    audit_blob = audit.read_text(encoding="utf-8")
    assert secret_idea not in audit_blob


# ---------------------------------------------------------------------------
# GenerationOutcome dataclass
# ---------------------------------------------------------------------------


def test_outcome_to_dict_serialisable() -> None:
    o = GenerationOutcome(
        succeeded=True, template=DEMO_TEMPLATES[0],
        error=None, elapsed_ms=12.345,
        model="gpt-oss:20b", fallback_used=False,
    )
    d = o.to_dict()
    json.dumps(d)
    assert d["succeeded"] is True
    assert d["template"]["id"] == DEMO_TEMPLATES[0].id
    assert d["elapsed_ms"] == 12.345


def test_outcome_to_dict_template_none() -> None:
    o = GenerationOutcome(
        succeeded=False, template=None, error="x",
        elapsed_ms=0.0, model="m", fallback_used=False,
    )
    d = o.to_dict()
    assert d["template"] is None
