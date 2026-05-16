"""Tests for ``sylion.aeis_v2.replay_v2`` — replay-as-fork PoC.

Covers SessionSnapshot capture, ReplayFork orchestration, divergence
score primitives and the composite ``compute_divergence_score``.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Sequence

import pytest

from sylion.aeis_v2.replay_v2 import (
    ReplayFork,
    ReplayResult,
    SessionSnapshot,
    compute_divergence_score,
    cosine_similarity_floats,
    jaccard_set_similarity,
    levenshtein_distance,
)


# ---------------------------------------------------------------------------
# levenshtein_distance
# ---------------------------------------------------------------------------


def test_levenshtein_identical_returns_zero() -> None:
    assert levenshtein_distance(["a", "b", "c"], ["a", "b", "c"]) == 0


def test_levenshtein_empty_either_side() -> None:
    assert levenshtein_distance([], []) == 0
    assert levenshtein_distance([], ["a"]) == 1
    assert levenshtein_distance(["a", "b"], []) == 2


def test_levenshtein_single_substitution() -> None:
    assert levenshtein_distance(["a", "b", "c"], ["a", "X", "c"]) == 1


def test_levenshtein_insertion_then_deletion() -> None:
    assert levenshtein_distance(["a", "b", "c"], ["a", "b", "c", "d"]) == 1
    assert levenshtein_distance(["a", "b", "c", "d"], ["a", "b", "c"]) == 1


def test_levenshtein_completely_different() -> None:
    assert levenshtein_distance(["a", "b"], ["x", "y"]) == 2


# ---------------------------------------------------------------------------
# jaccard_set_similarity
# ---------------------------------------------------------------------------


def test_jaccard_identical_sets_one() -> None:
    assert jaccard_set_similarity(["a", "b"], ["a", "b"]) == 1.0


def test_jaccard_both_empty_one() -> None:
    assert jaccard_set_similarity([], []) == 1.0


def test_jaccard_disjoint_zero() -> None:
    assert jaccard_set_similarity(["a", "b"], ["c", "d"]) == 0.0


def test_jaccard_partial_overlap() -> None:
    s = jaccard_set_similarity(["a", "b", "c"], ["b", "c", "d"])
    assert math.isclose(s, 2 / 4)


# ---------------------------------------------------------------------------
# cosine_similarity_floats
# ---------------------------------------------------------------------------


def test_cosine_identical_vectors_one() -> None:
    assert math.isclose(cosine_similarity_floats([1.0, 0.0], [1.0, 0.0]), 1.0)


def test_cosine_orthogonal_zero() -> None:
    assert math.isclose(cosine_similarity_floats([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_cosine_empty_returns_zero() -> None:
    assert cosine_similarity_floats([], []) == 0.0


def test_cosine_zero_norm_returns_zero() -> None:
    assert cosine_similarity_floats([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_length_mismatch_returns_zero() -> None:
    """Linter-rewritten contract: length mismatch is silent (returns 0.0)."""
    assert cosine_similarity_floats([1.0], [1.0, 1.0]) == 0.0


# ---------------------------------------------------------------------------
# compute_divergence_score
# ---------------------------------------------------------------------------


def test_compute_divergence_score_identical_zero() -> None:
    score = compute_divergence_score(
        ["a", "b", "c"], ["a", "b", "c"],
        [1.0, 0.0], [1.0, 0.0],
    )
    assert math.isclose(score, 0.0, abs_tol=1e-9)


def test_compute_divergence_score_completely_different_high() -> None:
    score = compute_divergence_score(
        ["a", "b"], ["x", "y"],
        [1.0, 0.0], [0.0, 1.0],
    )
    # 0.4*1.0 (full edit) + 0.6*1.0 (1-cos=1) = 1.0
    assert math.isclose(score, 1.0, abs_tol=1e-6)


def test_compute_divergence_score_within_unit_interval() -> None:
    score = compute_divergence_score(
        ["a", "b"], ["a", "X"],
        [1.0, 0.5], [0.5, 1.0],
    )
    assert 0.0 <= score <= 1.0


def test_compute_divergence_score_empty_decisions_no_crash() -> None:
    # max_len=0 → seq term is 0.0 by spec
    score = compute_divergence_score([], [], [1.0], [1.0])
    assert math.isclose(score, 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# SessionSnapshot.capture
# ---------------------------------------------------------------------------


def test_snapshot_capture_basic() -> None:
    s = SessionSnapshot.capture(
        {"foo": "bar", "session_id": "sess-1"}, decision_point=3,
    )
    assert s.snapshot_id
    assert s.original_session_id == "sess-1"
    assert s.decision_point == 3
    assert s.captured_at > 0
    assert s.state == {"foo": "bar", "session_id": "sess-1"}
    assert len(s.state_hash) == 16


def test_snapshot_capture_uses_provided_session_id_override() -> None:
    s = SessionSnapshot.capture(
        {"foo": "bar"}, decision_point=0, original_session_id="forced",
    )
    assert s.original_session_id == "forced"


def test_snapshot_capture_generates_uuid_when_no_session_id() -> None:
    s = SessionSnapshot.capture({"foo": "bar"}, decision_point=0)
    # UUID4 length is 36 chars with hyphens.
    assert len(s.original_session_id) == 36


def test_snapshot_state_is_deep_copied() -> None:
    """Mutations to the source dict must not bleed into the snapshot."""
    src = {"items": [1, 2, 3]}
    s = SessionSnapshot.capture(src, decision_point=0)
    src["items"].append(4)
    assert s.state["items"] == [1, 2, 3]


def test_snapshot_negative_decision_point_raises() -> None:
    with pytest.raises(ValueError):
        SessionSnapshot.capture({"foo": "bar"}, decision_point=-1)


def test_snapshot_to_dict_round_trip() -> None:
    s = SessionSnapshot.capture({"x": 1}, decision_point=0)
    d = s.to_dict()
    assert d["snapshot_id"] == s.snapshot_id
    assert d["state"] == {"x": 1}
    assert d["state_hash"] == s.state_hash


def test_snapshot_state_hash_stable_across_captures() -> None:
    s1 = SessionSnapshot.capture({"a": 1, "b": 2}, decision_point=0)
    s2 = SessionSnapshot.capture({"b": 2, "a": 1}, decision_point=0)
    # Sorted keys → same hash regardless of dict insertion order.
    assert s1.state_hash == s2.state_hash


# ---------------------------------------------------------------------------
# ReplayFork orchestrator
# ---------------------------------------------------------------------------


def _identity_replay(state, *, model_override=None, context_override=None):
    """Replay callable that returns 'identical to original' outcomes."""
    return (["a", "b", "c"], [1.0, 0.0, 0.0])


def _diverging_replay(state, *, model_override=None, context_override=None):
    """Replay callable that produces different decisions + final vector."""
    return (["x", "y", "z"], [0.0, 1.0, 0.0])


def test_replay_fork_identical_callable_zero_divergence(tmp_path: Path) -> None:
    snap = SessionSnapshot.capture({"x": 1}, decision_point=0)
    fork = ReplayFork(
        snap,
        original_decisions=["a", "b", "c"],
        original_final=[1.0, 0.0, 0.0],
        audit_log_path=tmp_path / "replay_fork.jsonl",
    )
    result = fork.run(_identity_replay)
    assert isinstance(result, ReplayResult)
    assert math.isclose(result.divergence_score, 0.0, abs_tol=1e-9)


def test_replay_fork_different_callable_nonzero_divergence(tmp_path: Path) -> None:
    snap = SessionSnapshot.capture({"x": 1}, decision_point=0)
    fork = ReplayFork(
        snap,
        original_decisions=["a", "b", "c"],
        original_final=[1.0, 0.0, 0.0],
        audit_log_path=tmp_path / "replay_fork.jsonl",
    )
    result = fork.run(_diverging_replay, model_override="gpt-oss-2")
    # Full edit distance + orthogonal cosine → score == 1.0
    assert math.isclose(result.divergence_score, 1.0, abs_tol=1e-6)
    assert result.model_override == "gpt-oss-2"


def test_replay_fork_emits_audit_jsonl(tmp_path: Path) -> None:
    audit = tmp_path / "replay_fork.jsonl"
    snap = SessionSnapshot.capture({"x": 1}, decision_point=0)
    fork = ReplayFork(
        snap,
        original_decisions=["a"],
        original_final=[1.0],
        audit_log_path=audit,
    )
    fork.run(_identity_replay)
    assert audit.exists()
    # Sprint 2 day 6 — chained format: walk via content subkey.
    rows = [
        json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()
        if line
    ]
    contents = [r["content"] for r in rows]
    assert len(contents) == 1
    assert contents[0]["kind"] == "replay_fork.run"
    assert contents[0]["snapshot_id"] == snap.snapshot_id
    assert "divergence_score" in contents[0]


def test_replay_fork_records_context_override(tmp_path: Path) -> None:
    snap = SessionSnapshot.capture({"x": 1}, decision_point=0)
    fork = ReplayFork(
        snap,
        original_decisions=["a"],
        original_final=[1.0],
        audit_log_path=tmp_path / "x.jsonl",
    )
    ctx = {"feature_flag": "new_router"}
    result = fork.run(_identity_replay, context_override=ctx)
    assert result.context_override == ctx


def test_replay_fork_to_dict_serialisable(tmp_path: Path) -> None:
    snap = SessionSnapshot.capture({"x": 1}, decision_point=0)
    fork = ReplayFork(
        snap,
        original_decisions=["a"],
        original_final=[1.0],
        audit_log_path=tmp_path / "x.jsonl",
    )
    result = fork.run(_identity_replay)
    d = result.to_dict()
    # JSON round-trip — proves all values are JSON-serialisable.
    json.dumps(d)
    assert d["replay_id"] == result.replay_id
    assert d["divergence_score"] == result.divergence_score


def test_replay_fork_audit_chain_verifies(tmp_path: Path) -> None:
    """Sprint 2 day 6 — replay_fork audit JSONL is hash-chained + verifiable."""
    from sylion.aeis_v2.audit_chain import verify_chain

    audit = tmp_path / "replay_fork.jsonl"
    snap = SessionSnapshot.capture({"x": 1}, decision_point=0)
    fork = ReplayFork(
        snap,
        original_decisions=["a", "b"],
        original_final=[1.0, 0.0],
        audit_log_path=audit,
    )
    # Run a few replays so the chain has multiple links.
    fork.run(_identity_replay)
    fork.run(_diverging_replay, model_override="alt-model")
    fork.run(_identity_replay, context_override={"flag": True})
    assert verify_chain(audit) == []


def test_replay_fork_audit_emit_failure_does_not_raise(tmp_path: Path) -> None:
    """A bad audit path must NOT break the replay run."""
    bad_path = tmp_path / "doesnotexist" / "x" / "y" / "z" / "audit.jsonl"
    # Make a path with a file in the way of a directory.
    blocker = tmp_path / "doesnotexist"
    blocker.write_text("not a dir")  # so .mkdir(parents=True) fails

    snap = SessionSnapshot.capture({"x": 1}, decision_point=0)
    fork = ReplayFork(
        snap,
        original_decisions=["a"],
        original_final=[1.0],
        audit_log_path=bad_path,
    )
    # Best-effort emit — must not raise.
    result = fork.run(_identity_replay)
    assert result.divergence_score >= 0.0
