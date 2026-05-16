from sylion.governance.levenshtein import levenshtein_distance


def test_identical():
    assert levenshtein_distance(["a", "b"], ["a", "b"]) == 0


def test_empty():
    assert levenshtein_distance([], []) == 0


def test_prefix_only_diff():
    assert levenshtein_distance(["x", "a", "b"], ["a", "b"]) == 1


def test_full_diff():
    assert levenshtein_distance(["a", "b"], ["x", "y"]) == 2


def test_asymmetric_lengths():
    assert levenshtein_distance(["a", "b", "c", "d"], ["a"]) == 3
