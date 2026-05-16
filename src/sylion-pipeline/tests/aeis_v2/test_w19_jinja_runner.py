"""Tests for ``sylion.aeis_v2.policy_v2.jinja_runner`` — W19 G2 SKELETON.

Covers ADR-003 PROPOSED Option B foundation: feature flag default-disabled,
SandboxedEnvironment escape blocking (__class__, __mro__, __subclasses__),
syntax error handling, audit JSONL emission and best-effort error recovery.

The runner is NOT wired into routing/apply yet — these tests exercise the
helper directly so the path is green when ADR-003 lands at ACCEPTED.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.aeis_v2.policy_v2 import jinja_runner
from sylion.aeis_v2.policy_v2.jinja_runner import (
    JinjaContextSafelist,
    JinjaRenderResult,
    W19_EVALUATOR_ENABLED_ENV,
    emit_audit,
    is_evaluator_enabled,
    render_template,
)


# ---------------------------------------------------------------------------
# Feature flag default-disabled — ADR-003 PROPOSED guardrail.
# ---------------------------------------------------------------------------


def test_evaluator_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-003 still PROPOSED — flag defaults DISABLED."""
    monkeypatch.delenv(W19_EVALUATOR_ENABLED_ENV, raising=False)
    assert is_evaluator_enabled() is False


def test_evaluator_disabled_when_env_set_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator did not opt in — disabled stays disabled."""
    monkeypatch.setenv(W19_EVALUATOR_ENABLED_ENV, "1")
    assert is_evaluator_enabled() is False


def test_evaluator_enabled_when_env_set_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator flipped flag (post Council Hybrid sign-off) — enabled."""
    monkeypatch.setenv(W19_EVALUATOR_ENABLED_ENV, "0")
    assert is_evaluator_enabled() is True


def test_evaluator_handles_whitespace_in_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trim whitespace before comparison — defensive."""
    monkeypatch.setenv(W19_EVALUATOR_ENABLED_ENV, "  0  ")
    assert is_evaluator_enabled() is True


# ---------------------------------------------------------------------------
# Happy path render.
# ---------------------------------------------------------------------------


def test_render_simple_template_succeeds() -> None:
    """`{{ x + 1 }}` with x=1 renders to "2"."""
    result = render_template("{{ x + 1 }}", {"x": 1})
    assert result.succeeded is True
    assert result.rendered == "2"
    assert result.error is None
    assert result.render_ms >= 0.0
    assert len(result.template_hash) == 16  # 16-char prefix of sha256


def test_render_template_hash_is_deterministic() -> None:
    """Identical templates produce identical hashes."""
    a = render_template("{{ x }}", {"x": "a"})
    b = render_template("{{ x }}", {"x": "b"})
    assert a.template_hash == b.template_hash
    c = render_template("{{ y }}", {"y": "a"})
    assert a.template_hash != c.template_hash


# ---------------------------------------------------------------------------
# Sandbox escape blocking — the security core of ADR-003 Option B.
# ---------------------------------------------------------------------------


def test_render_blocks_class_access() -> None:
    """`{{ ''.__class__ }}` MUST not return the actual class — SandboxedEnvironment
    coerces to Undefined which renders as empty string. Either way, the
    attacker cannot escape into the class hierarchy.
    """
    result = render_template("{{ ''.__class__ }}", {})
    # Either succeeds with empty/non-class output, or fails closed.
    if result.succeeded:
        assert result.rendered is not None
        # MUST NOT contain a class repr like "<class 'str'>".
        assert "<class" not in result.rendered
        assert "type" not in result.rendered.lower() or result.rendered == ""
    else:
        assert result.error is not None


def test_render_blocks_mro_iter() -> None:
    """Walking the MRO is a classic sandbox escape — MUST raise SecurityError."""
    result = render_template(
        "{% for c in ''.__class__.__mro__ %}{{ c }}{% endfor %}", {}
    )
    assert result.succeeded is False
    assert result.error is not None
    assert "sandbox" in result.error.lower() or "unsafe" in result.error.lower()


def test_render_blocks_subclasses() -> None:
    """`__subclasses__` traversal is the canonical RCE path — must be blocked."""
    result = render_template(
        "{{ ''.__class__.__mro__[1].__subclasses__() }}", {}
    )
    assert result.succeeded is False
    assert result.error is not None
    assert "sandbox" in result.error.lower() or "unsafe" in result.error.lower()


def test_render_blocks_dunder_globals() -> None:
    """Function `__globals__` access — sandbox coerces to Undefined or denies."""
    result = render_template("{{ x.__globals__ }}", {"x": lambda: None})
    # Either succeeds with empty Undefined render, or fails closed — but
    # MUST NOT expose the globals dict.
    if result.succeeded:
        assert result.rendered is not None
        assert "__builtins__" not in result.rendered
        assert "os" not in result.rendered or result.rendered == ""
    else:
        assert result.error is not None


def test_render_blocks_subclasses_call() -> None:
    """Calling __subclasses__ via dynamic-attribute lookup is also blocked."""
    result = render_template(
        "{{ ().__class__.__bases__[0].__subclasses__() }}", {}
    )
    assert result.succeeded is False
    assert result.error is not None


# ---------------------------------------------------------------------------
# Error path — syntax / runtime errors fail closed.
# ---------------------------------------------------------------------------


def test_render_syntax_error_returns_error() -> None:
    """Malformed template → fail-closed deny with `syntax:` prefix."""
    result = render_template("{{ unclosed", {})
    assert result.succeeded is False
    assert result.rendered is None
    assert result.error is not None
    assert "syntax" in result.error.lower()


def test_render_runtime_error_returns_error() -> None:
    """Division-by-zero at render time → fail-closed."""
    result = render_template("{{ 1 / 0 }}", {})
    assert result.succeeded is False
    assert result.error is not None


def test_render_with_huge_loop_completes_or_times_out() -> None:
    """Long loop should either finish under timeout or be flagged.

    jinja2 has no native timeout — the runner only post-checks elapsed
    time. This test verifies the result is well-formed in either case
    (succeeded with rendered string, OR failed with `timeout:` error).
    """
    result = render_template(
        "{% for i in range(100) %}{{ i }}{% endfor %}", {}
    )
    assert isinstance(result, JinjaRenderResult)
    if result.succeeded:
        assert result.rendered is not None
        # Sanity: rendered string contains some digits.
        assert "0" in result.rendered
    else:
        # Whatever failure mode triggered, error must be a non-empty string.
        assert result.error is not None and len(result.error) > 0


# ---------------------------------------------------------------------------
# Audit JSONL emit.
# ---------------------------------------------------------------------------


def test_emit_audit_writes_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """emit_audit appends a single chained JSONL row with required keys.

    Sprint 3: migrated to audit_chain (commit ac97e957) — content lives
    under a ``content`` subkey alongside ``prev_hash`` + ``content_hash``.
    """
    target = tmp_path / "w19_evaluator.jsonl"
    monkeypatch.setattr(jinja_runner, "W19_AUDIT_LOG_PATH", target)
    result = render_template("{{ a }}", {"a": "hello"})
    emit_audit("decision-abc", result, ["a"])
    assert target.exists()
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])["content"]
    for key in (
        "ts",
        "decision_id",
        "template_hash",
        "ctx_keys",
        "succeeded",
        "error",
        "render_ms",
    ):
        assert key in row
    assert row["decision_id"] == "decision-abc"
    assert row["ctx_keys"] == ["a"]
    assert row["succeeded"] is True
    assert row["error"] is None


def test_emit_audit_appends_multiple_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repeated calls append — they don't overwrite."""
    target = tmp_path / "w19_evaluator.jsonl"
    monkeypatch.setattr(jinja_runner, "W19_AUDIT_LOG_PATH", target)
    r1 = render_template("{{ a }}", {"a": "1"})
    r2 = render_template("{{ b }}", {"b": "2"})
    emit_audit("d1", r1, ["a"])
    emit_audit("d2", r2, ["b"])
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["content"]["decision_id"] == "d1"
    assert json.loads(lines[1])["content"]["decision_id"] == "d2"


def test_emit_audit_records_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failed renders are logged with succeeded=False and error string."""
    target = tmp_path / "w19_evaluator.jsonl"
    monkeypatch.setattr(jinja_runner, "W19_AUDIT_LOG_PATH", target)
    # MRO iteration triggers a true SecurityError (not just Undefined).
    result = render_template(
        "{% for c in ''.__class__.__mro__ %}{{ c }}{% endfor %}", {}
    )
    emit_audit("decision-deny", result, [])
    row = json.loads(target.read_text(encoding="utf-8").splitlines()[0])["content"]
    assert row["succeeded"] is False
    assert row["error"] is not None


# ---------------------------------------------------------------------------
# Sprint 3 E1 — real timeout enforcement (Kimi k1 round 47:30).
# ---------------------------------------------------------------------------


def test_render_template_real_timeout_on_slow_template() -> None:
    """A template that loops 'forever' must trip the timeout cleanly.

    SandboxedEnvironment caps range() at MAX_RANGE=100000, so we use
    nested loops within that cap — 99999 × 99999 iterations is enough
    to vastly exceed any reasonable timeout budget.
    """
    slow = (
        "{% for i in range(99999) %}"
        "{% for j in range(99999) %}x{% endfor %}"
        "{% endfor %}"
    )
    result = render_template(slow, {}, timeout_s=0.1)
    assert result.succeeded is False
    assert result.error is not None
    assert "timeout" in result.error.lower()
    # Caller treats this as DENY (fail-closed).
    assert result.rendered is None


def test_render_template_sandbox_caps_huge_range() -> None:
    """Defense-in-depth: SandboxedEnvironment also caps range() at MAX_RANGE.

    This is independent of our timeout — even without a timeout the
    sandbox blocks a single range(10**7) call as fail-closed.
    """
    result = render_template("{% for i in range(10**7) %}x{% endfor %}", {})
    assert result.succeeded is False
    assert result.error is not None


def test_render_template_under_timeout_succeeds() -> None:
    """Quick template completes within the budget — no timeout."""
    result = render_template("{{ x }}", {"x": "ok"}, timeout_s=2.0)
    assert result.succeeded is True
    assert result.rendered == "ok"


def test_render_template_audit_chain_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprint 3 — emit_audit produces a verifiable chain."""
    from sylion.aeis_v2.audit_chain import verify_chain

    target = tmp_path / "w19_evaluator.jsonl"
    monkeypatch.setattr(jinja_runner, "W19_AUDIT_LOG_PATH", target)
    for i in range(3):
        r = render_template("{{ x }}", {"x": str(i)})
        emit_audit(f"d-{i}", r, ["x"])
    assert verify_chain(target) == []


def test_emit_audit_handles_path_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If filesystem fails, emit_audit must NOT raise — best-effort."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    # Patch builtins.open so the JSONL write fails inside emit_audit.
    monkeypatch.setattr("builtins.open", _boom)
    result = render_template("{{ x }}", {"x": "ok"})
    # MUST NOT raise:
    emit_audit("decision-x", result, ["x"])


def test_emit_audit_handles_mkdir_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If mkdir fails, emit_audit must NOT raise — best-effort."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr("pathlib.Path.mkdir", _boom)
    result = render_template("{{ x }}", {"x": "ok"})
    # MUST NOT raise:
    emit_audit("decision-y", result, ["x"])


# ---------------------------------------------------------------------------
# JinjaRenderResult dataclass invariants.
# ---------------------------------------------------------------------------


def test_render_result_is_frozen() -> None:
    """JinjaRenderResult is frozen — mutation raises."""
    result = render_template("{{ x }}", {"x": "y"})
    with pytest.raises((AttributeError, TypeError)):
        result.rendered = "tampered"  # type: ignore[misc]


def test_render_result_succeeded_property() -> None:
    """`.succeeded` reflects (error is None and rendered is not None)."""
    ok = render_template("{{ 1 }}", {})
    assert ok.succeeded is True
    bad = render_template("{{ unclosed", {})  # syntax error, fails closed
    assert bad.succeeded is False


def test_context_safelist_flat() -> None:
    s = JinjaContextSafelist({"r1": {"a"}})
    assert s.for_rule("r1", {"a": 1, "b": 2}) == {"a": 1}


def test_context_safelist_nested() -> None:
    ctx = {"a": {"ok": 1, "_hide": 2, "n": {"x": 3, "_y": 4}}, "b": 0}
    assert JinjaContextSafelist.filter_context(ctx, {"a"}) == {"a": {"ok": 1, "n": {"x": 3}}}


def test_context_safelist_dunder() -> None:
    ctx = {"a": {"__class__": "x", "safe": 1}, "__root__": 2}
    assert JinjaContextSafelist.filter_context(ctx, {"a", "__root__"}) == {"a": {"safe": 1}, "__root__": 2}


def test_context_safelist_empty() -> None:
    assert JinjaContextSafelist().for_rule("missing", {"a": 1}) == {}
