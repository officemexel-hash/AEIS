"""Tests for ``sylion.aeis_v2.policy_v2.staged_rollout`` — sprint 4 prep."""
from __future__ import annotations

import pytest

from sylion.aeis_v2.policy_v2.staged_rollout import (
    DEFAULT_ROLLOUT_PERCENT,
    ROLLOUT_PERCENT_ENV,
    StagedRolloutGate,
    compute_rollout_bucket,
    is_in_rollout_bucket,
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ROLLOUT_PERCENT_ENV, raising=False)
    yield
    monkeypatch.delenv(ROLLOUT_PERCENT_ENV, raising=False)


# ---------------------------------------------------------------------------
# Module invariants
# ---------------------------------------------------------------------------


def test_default_rollout_percent_is_zero() -> None:
    """ADR-003 still PROPOSED → safe default off."""
    assert DEFAULT_ROLLOUT_PERCENT == 0


def test_rollout_env_var_name() -> None:
    assert ROLLOUT_PERCENT_ENV == "SYLION_W19_STAGED_ROLLOUT_PERCENT"


# ---------------------------------------------------------------------------
# compute_rollout_bucket
# ---------------------------------------------------------------------------


def test_bucket_deterministic() -> None:
    """Same id → same bucket on repeated calls."""
    a = compute_rollout_bucket("decision-abc")
    b = compute_rollout_bucket("decision-abc")
    assert a == b


def test_bucket_in_range() -> None:
    """Default modulo=100 → bucket in [0, 99]."""
    for i in range(50):
        b = compute_rollout_bucket(f"decision-{i}")
        assert 0 <= b < 100


def test_bucket_distinct_inputs_diverge() -> None:
    """Different ids should map to different buckets in expectation."""
    seen: set[int] = set()
    for i in range(100):
        seen.add(compute_rollout_bucket(f"d-{i}"))
    # 100 distinct decision ids should hit at least 30 distinct buckets
    # (sha256 distribution).
    assert len(seen) >= 30


def test_bucket_empty_id_returns_zero() -> None:
    assert compute_rollout_bucket("") == 0


def test_bucket_clamps_modulo() -> None:
    """modulo < 1 clamps to 1; > 100000 clamps."""
    assert compute_rollout_bucket("x", modulo=0) == 0
    assert compute_rollout_bucket("x", modulo=-5) == 0
    # Huge modulo OK (clamp keeps us inside [1, 100000]).
    b = compute_rollout_bucket("x", modulo=1_000_000)
    assert 0 <= b < 100_000


# ---------------------------------------------------------------------------
# is_in_rollout_bucket
# ---------------------------------------------------------------------------


def test_zero_percent_never_in_bucket() -> None:
    for i in range(20):
        assert is_in_rollout_bucket(f"d-{i}", 0) is False


def test_hundred_percent_always_in_bucket() -> None:
    for i in range(20):
        assert is_in_rollout_bucket(f"d-{i}", 100) is True


def test_negative_percent_clamps_to_zero() -> None:
    assert is_in_rollout_bucket("any", -10) is False


def test_above_100_percent_clamps_to_hundred() -> None:
    assert is_in_rollout_bucket("any", 1000) is True


def test_one_percent_includes_only_low_buckets() -> None:
    """At 1% only bucket 0 matches → roughly 1% of decisions."""
    matched = [
        is_in_rollout_bucket(f"d-{i}", 1) for i in range(1000)
    ]
    # Expected: ~10 matches (1% of 1000), with reasonable variance.
    n = sum(matched)
    assert 0 <= n <= 50


def test_fifty_percent_roughly_half() -> None:
    matched = sum(
        is_in_rollout_bucket(f"d-{i}", 50) for i in range(1000)
    )
    # 50% of 1000 should be 500 ± 80 (3-sigma binomial).
    assert 420 <= matched <= 580


# ---------------------------------------------------------------------------
# StagedRolloutGate — env-driven
# ---------------------------------------------------------------------------


def test_gate_default_zero_when_env_unset(clean_env) -> None:
    gate = StagedRolloutGate()
    assert gate.percent == 0
    assert gate.should_run("decision-x") is False


def test_gate_reads_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ROLLOUT_PERCENT_ENV, "100")
    gate = StagedRolloutGate()
    assert gate.percent == 100
    assert gate.should_run("any") is True


def test_gate_clamps_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ROLLOUT_PERCENT_ENV, "999")
    assert StagedRolloutGate().percent == 100
    monkeypatch.setenv(ROLLOUT_PERCENT_ENV, "-50")
    assert StagedRolloutGate().percent == 0


def test_gate_unparseable_env_falls_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ROLLOUT_PERCENT_ENV, "not-a-number")
    assert StagedRolloutGate().percent == DEFAULT_ROLLOUT_PERCENT


# ---------------------------------------------------------------------------
# StagedRolloutGate — fixed_percent override (test path)
# ---------------------------------------------------------------------------


def test_gate_fixed_percent_overrides_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ROLLOUT_PERCENT_ENV, "100")
    gate = StagedRolloutGate(fixed_percent=0)
    assert gate.percent == 0
    assert gate.should_run("any") is False


def test_gate_fixed_percent_clamps() -> None:
    assert StagedRolloutGate(fixed_percent=999).percent == 100
    assert StagedRolloutGate(fixed_percent=-1).percent == 0


def test_gate_to_dict_serialisable() -> None:
    import json

    g = StagedRolloutGate(fixed_percent=25)
    d = g.to_dict()
    json.dumps(d)
    assert d["fixed_percent"] == 25


# ---------------------------------------------------------------------------
# Determinism — flap protection
# ---------------------------------------------------------------------------


def test_same_decision_id_same_outcome_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate must NOT flap for the same decision_id at fixed percent."""
    monkeypatch.setenv(ROLLOUT_PERCENT_ENV, "20")
    gate = StagedRolloutGate()
    decision = "decision-flap-test"
    a = gate.should_run(decision)
    for _ in range(50):
        assert gate.should_run(decision) == a
