import pytest

from sylion.core import TimeWindow


def test_contains_includes_start_middle_and_end():
    window = TimeWindow(10.0, 20.0)

    assert window.contains(10.0)
    assert window.contains(15.0)
    assert window.contains(20.0)


def test_contains_rejects_timestamps_outside_window():
    window = TimeWindow(10.0, 20.0)

    assert not window.contains(9.99)
    assert not window.contains(20.01)


def test_overlaps_with_returns_true_for_partial_overlap():
    left = TimeWindow(10.0, 20.0)
    right = TimeWindow(15.0, 25.0)

    assert left.overlaps_with(right)
    assert right.overlaps_with(left)


def test_overlaps_with_returns_false_for_disjoint_windows():
    left = TimeWindow(10.0, 20.0)
    right = TimeWindow(20.1, 30.0)

    assert not left.overlaps_with(right)
    assert not right.overlaps_with(left)


def test_duration_seconds_and_invalid_range():
    window = TimeWindow(3.5, 8.0)

    assert window.duration_seconds == pytest.approx(4.5)

    with pytest.raises(ValueError):
        TimeWindow(8.0, 3.5)
