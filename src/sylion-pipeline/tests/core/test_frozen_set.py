from sylion.core import FrozenSet


def test_contains_returns_true_only_for_present_items():
    values = FrozenSet({"alpha", "beta"})

    assert "alpha" in values
    assert "gamma" not in values


def test_iter_and_len_expose_wrapped_frozenset_contents():
    values = FrozenSet({1, 2, 3})

    assert len(values) == 3
    assert set(values) == {1, 2, 3}


def test_ratio_of_returns_overlap_relative_to_other_set_size():
    left = FrozenSet({1, 2, 3})
    right = FrozenSet({2, 3, 4, 5})

    assert left.ratio_of(right) == 0.5


def test_ratio_of_returns_zero_when_other_set_is_empty():
    values = FrozenSet({1, 2, 3})
    empty = FrozenSet(set())

    assert values.ratio_of(empty) == 0.0
