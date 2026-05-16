import math

from sylion.aeis_v2.replay_v2.divergence import compute_weighted_divergence


def test_weighted_divergence_zero_for_identical_inputs() -> None:
    assert compute_weighted_divergence(["a"], ["a"], [1.0, 0.0], [1.0, 0.0]) == 0.0


def test_weighted_divergence_combines_cosine_and_edit_distance() -> None:
    score = compute_weighted_divergence(["a", "b"], ["a", "c"], [1.0, 0.0], [0.0, 1.0])
    assert math.isclose(score, 0.8, abs_tol=1e-9)


def test_weighted_divergence_clamps_negative_cosine_case_to_one() -> None:
    score = compute_weighted_divergence(["a"], ["b"], [1.0, 0.0], [-1.0, 0.0])
    assert score == 1.0


def test_weighted_divergence_handles_empty_decisions() -> None:
    assert compute_weighted_divergence([], [], [0.0], [0.0]) == 0.6
