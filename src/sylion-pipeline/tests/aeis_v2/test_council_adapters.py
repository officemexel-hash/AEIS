"""Tests for ``sylion.aeis_v2.council_v2.adapters``.

Subprocess to ``ollama run`` is stubbed via monkeypatch — no live
Ollama required. The tests verify:

* render_role_prompt picks the right template per canonical role.
* parse_role_verdict_response handles canonical + degenerate stdout.
* OllamaRoleAdapter falls back to simulate_role_verdict on timeout /
  missing binary / non-zero returncode / unknown error.
* ScriptedRoleAdapter returns canned verdicts.
* make_ollama_evaluator caches per-role instances.
* Integration: evaluate_match_with_council accepts the adapter-derived
  evaluator without changes.
"""
from __future__ import annotations

import subprocess
from typing import Any

import pytest

from sylion.aeis_v2.council_v2 import (
    DEFAULT_MODEL,
    DEFAULT_ROLE_TIMEOUT_S,
    OllamaRoleAdapter,
    ScriptedRoleAdapter,
    evaluate_match_with_council,
    make_ollama_evaluator,
    parse_role_verdict_response,
    render_role_prompt,
)
from sylion.governance.council_hybrid import VALID_ROLES


# ---------------------------------------------------------------------------
# Module-level invariants
# ---------------------------------------------------------------------------


def test_default_model_is_ollama_gpt_oss() -> None:
    """ADR-002 routing matrix: gpt-oss:20b is the local default."""
    assert DEFAULT_MODEL == "gpt-oss:20b"


def test_default_role_timeout_is_8s() -> None:
    """8s × 9 roles = 72s worst-case Council decision."""
    assert DEFAULT_ROLE_TIMEOUT_S == 8.0


# ---------------------------------------------------------------------------
# render_role_prompt — per-role templating.
# ---------------------------------------------------------------------------


def test_render_prompt_known_role() -> None:
    out = render_role_prompt("planner", 0.85, ["a", "b"], "test idea")
    assert "Planner" in out
    assert "0.85" in out
    assert "test idea" in out


def test_render_prompt_unknown_role_uses_fallback() -> None:
    out = render_role_prompt("alien_role", 0.5, ["x"], "i")
    assert "alien_role" in out
    # Generic shape fallback must still mention canonical verdicts.
    assert "approve" in out.lower()


def test_render_prompt_truncates_long_idea() -> None:
    long_idea = "x" * 1000
    out = render_role_prompt("critic", 0.5, [], long_idea)
    # Idea truncated to 200 chars.
    assert "x" * 201 not in out


def test_render_prompt_handles_empty_tags() -> None:
    out = render_role_prompt("planner", 0.5, [], "i")
    # Renders without crashing; no traceback string in output.
    assert "Planner" in out


def test_render_prompt_includes_role_specific_bias() -> None:
    """Each role's prompt encodes its own bias keyword."""
    bias_keywords = {
        "planner": "feasibility",
        "architect": "spojnosc",
        "critic": "Sceptyk",
        "verifier": "testowalnosc",
        "governance": "dokumentacji",
        "cost_sentinel": "koszt",
        "security_sentinel": "bezpieczenstwa",
        "domain_specialist": "domeny",
        "funding_specialist": "budzet",
    }
    for role, kw in bias_keywords.items():
        prompt = render_role_prompt(role, 0.5, [], "")
        assert kw.lower() in prompt.lower(), (
            f"role {role}: missing bias keyword {kw!r}"
        )


# ---------------------------------------------------------------------------
# parse_role_verdict_response
# ---------------------------------------------------------------------------


def test_parse_extracts_canonical_verdict() -> None:
    verdict, _, _ = parse_role_verdict_response("approve\n0.9\nlooks good")
    assert verdict == "approve"


def test_parse_case_insensitive() -> None:
    verdict, _, _ = parse_role_verdict_response("APPROVE\n0.9")
    assert verdict == "approve"


def test_parse_extracts_confidence() -> None:
    _, conf, _ = parse_role_verdict_response("approve\n0.85\nx")
    assert conf == pytest.approx(0.85)


def test_parse_clamps_invalid_confidence_to_default() -> None:
    """No numeric in stdout → confidence defaults to 0.5."""
    _, conf, _ = parse_role_verdict_response("approve\nlooks fine")
    assert conf == 0.5


def test_parse_extracts_rationale() -> None:
    _, _, rationale = parse_role_verdict_response(
        "approve\n0.9\nthis is the rationale",
    )
    assert "rationale" in rationale.lower()


def test_parse_garbage_falls_back_to_conditional() -> None:
    verdict, conf, rationale = parse_role_verdict_response("blah blah blah")
    assert verdict == "conditional"
    assert conf == 0.5


def test_parse_empty_returns_conditional() -> None:
    verdict, conf, rationale = parse_role_verdict_response("")
    assert verdict == "conditional"
    assert conf == 0.5
    assert rationale == ""


def test_parse_rejects_non_canonical_word() -> None:
    """Hallucinated 'maybe'/'unsure' → conditional fallback."""
    verdict, _, _ = parse_role_verdict_response("maybe\n0.5\nmm")
    assert verdict == "conditional"


# ---------------------------------------------------------------------------
# OllamaRoleAdapter — subprocess stubbed
# ---------------------------------------------------------------------------


def _stub_ollama(stdout: str, returncode: int = 0):
    class _Result:
        def __init__(self) -> None:
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    def _fake(*_a: Any, **_kw: Any) -> _Result:
        return _Result()

    return _fake


def test_ollama_adapter_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "subprocess.run",
        _stub_ollama("approve\n0.9\nlooks great"),
    )
    a = OllamaRoleAdapter(role="planner")
    verdict, conf, rationale = a.evaluate(0.85, ["good"], idea_text="x")
    assert verdict == "approve"
    assert conf == pytest.approx(0.9)
    assert "[planner/ollama]" in rationale


def test_ollama_adapter_timeout_falls_back_to_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_timeout(*_a: Any, **_kw: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="ollama", timeout=1)

    monkeypatch.setattr("subprocess.run", _raise_timeout)
    a = OllamaRoleAdapter(role="planner")
    verdict, _, _ = a.evaluate(0.85, ["good"])
    # simulate_role_verdict says: top_score >= 0.7 → approve.
    assert verdict == "approve"


def test_ollama_adapter_missing_binary_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing(*_a: Any, **_kw: Any) -> Any:
        raise FileNotFoundError("ollama not on PATH")

    monkeypatch.setattr("subprocess.run", _missing)
    a = OllamaRoleAdapter(role="planner")
    verdict, _, _ = a.evaluate(0.2, ["good"])
    # simulate: low score → reject
    assert verdict == "reject"


def test_ollama_adapter_returncode_nonzero_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("subprocess.run", _stub_ollama("oops", returncode=1))
    a = OllamaRoleAdapter(role="planner")
    verdict, _, _ = a.evaluate(0.85, ["good"])
    # Simulator-derived approval (top_score 0.85 ≥ 0.7).
    assert verdict == "approve"


def test_ollama_adapter_unknown_exception_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_unknown(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("disk full")

    monkeypatch.setattr("subprocess.run", _raise_unknown)
    a = OllamaRoleAdapter(role="security_sentinel")
    # Tags include 'unsafe' — simulator will reject regardless of score.
    verdict, _, _ = a.evaluate(0.9, ["public", "unsafe"])
    assert verdict == "reject"


def test_ollama_adapter_stamps_role_in_rationale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "subprocess.run", _stub_ollama("approve\n0.9\nbecause yes"),
    )
    a = OllamaRoleAdapter(role="critic")
    _, _, rationale = a.evaluate(0.85, [])
    assert rationale.startswith("[critic/ollama]")


# ---------------------------------------------------------------------------
# ScriptedRoleAdapter — deterministic test harness
# ---------------------------------------------------------------------------


def test_scripted_adapter_returns_canned_verdict() -> None:
    a = ScriptedRoleAdapter(role="planner", canned_verdict="reject")
    v, c, r = a.evaluate(0.85, ["good"])
    assert v == "reject"
    assert c == pytest.approx(0.85)


def test_scripted_adapter_clamps_non_canonical_to_conditional() -> None:
    a = ScriptedRoleAdapter(role="x", canned_verdict="banana")
    v, _, _ = a.evaluate(0.0, [])
    assert v == "conditional"


# ---------------------------------------------------------------------------
# make_ollama_evaluator — caching dispatcher
# ---------------------------------------------------------------------------


def test_make_evaluator_caches_role_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First call constructs an adapter; second call reuses it."""
    monkeypatch.setattr("subprocess.run", _stub_ollama("approve\n0.9"))
    eval_fn = make_ollama_evaluator()
    eval_fn("planner", 0.85, ["good"])
    eval_fn("planner", 0.85, ["good"])
    # Implementation detail check: the cache dict is bound to the closure.
    cache = eval_fn.__closure__[0].cell_contents  # type: ignore[index]
    assert "planner" in cache
    assert isinstance(cache["planner"], OllamaRoleAdapter)


# ---------------------------------------------------------------------------
# Integration with evaluate_match_with_council
# ---------------------------------------------------------------------------


def test_council_wedge_accepts_scripted_adapter() -> None:
    """The wedge's role_evaluator hook accepts the new adapter contract."""
    from sylion.governance.council_hybrid import CouncilHybrid

    council = CouncilHybrid(db_path=":memory:")
    matches = [{
        "template": {
            "id": "t",
            "name_pl": "T", "description_pl": "D",
            "object_type_ids": [], "widget_ids": [],
            "tags": ["x"],
        },
        "score": 0.85,
        "method": "embedding",
        "reason_pl": "t",
    }]

    # Build a per-role dispatch using ScriptedRoleAdapter.
    adapters = {
        role: ScriptedRoleAdapter(role=role, canned_verdict="approve")
        for role in VALID_ROLES
    }

    def _evaluator(role: str, top_score: float, tags: list[str]):
        return adapters[role].evaluate(top_score, tags)

    decision = evaluate_match_with_council(
        matches, idea_text="ok", council=council,
        role_evaluator=_evaluator,
    )
    assert decision.verdict == "approve"
    assert decision.dissents == []


def test_council_wedge_with_ollama_adapter_falls_back_when_subprocess_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Realistic prod scenario: ollama unreachable → wedge still produces."""
    from sylion.governance.council_hybrid import CouncilHybrid

    def _missing(*_a: Any, **_kw: Any) -> Any:
        raise FileNotFoundError("ollama not on PATH")

    monkeypatch.setattr("subprocess.run", _missing)

    council = CouncilHybrid(db_path=":memory:")
    matches = [{
        "template": {
            "id": "t",
            "name_pl": "T", "description_pl": "D",
            "object_type_ids": [], "widget_ids": [],
            "tags": ["x"],
        },
        "score": 0.85,
        "method": "embedding",
        "reason_pl": "t",
    }]

    decision = evaluate_match_with_council(
        matches, idea_text="ok", council=council,
        role_evaluator=make_ollama_evaluator(),
    )
    # All 9 roles fall back to simulate_role_verdict; high score → approve.
    assert decision.verdict == "approve"
