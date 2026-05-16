from sylion.core.score_labels import score_to_label


def test_score_below_low_is_low():
    assert score_to_label(0.2) == "low"


def test_score_at_low_is_medium():
    assert score_to_label(0.3) == "medium"


def test_score_between_thresholds_is_medium():
    assert score_to_label(0.5) == "medium"


def test_score_at_medium_is_high():
    assert score_to_label(0.7) == "high"


def test_custom_thresholds_are_used():
    thresholds = {"low": 0.4, "medium": 0.8}
    assert score_to_label(0.39, thresholds) == "low"
    assert score_to_label(0.4, thresholds) == "medium"
    assert score_to_label(0.8, thresholds) == "high"
