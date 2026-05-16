import pytest

from sylion.core import RateLimitTracker


def test_is_over_limit_returns_false_when_node_has_no_calls():
    tracker = RateLimitTracker()

    assert not tracker.is_over_limit("node-a", window_seconds=60.0, max_count=1)


def test_is_over_limit_returns_false_at_exact_limit():
    tracker = RateLimitTracker()
    tracker.record_call("node-a", 10.0)
    tracker.record_call("node-a", 20.0)

    assert not tracker.is_over_limit("node-a", window_seconds=15.0, max_count=2)


def test_is_over_limit_returns_true_when_calls_exceed_limit_within_window():
    tracker = RateLimitTracker()
    tracker.record_call("node-a", 10.0)
    tracker.record_call("node-a", 15.0)
    tracker.record_call("node-a", 20.0)

    assert tracker.is_over_limit("node-a", window_seconds=10.0, max_count=2)


def test_is_over_limit_prunes_calls_older_than_window():
    tracker = RateLimitTracker()
    tracker.record_call("node-a", 5.0)
    tracker.record_call("node-a", 12.0)
    tracker.record_call("node-a", 18.0)

    assert not tracker.is_over_limit("node-a", window_seconds=10.0, max_count=2)
    assert not tracker.is_over_limit("node-a", window_seconds=5.0, max_count=2)


def test_is_over_limit_tracks_each_node_independently_and_validates_arguments():
    tracker = RateLimitTracker()
    tracker.record_call("node-a", 1.0)
    tracker.record_call("node-a", 2.0)
    tracker.record_call("node-b", 1.0)

    assert tracker.is_over_limit("node-a", window_seconds=5.0, max_count=1)
    assert not tracker.is_over_limit("node-b", window_seconds=5.0, max_count=1)

    with pytest.raises(ValueError):
        tracker.is_over_limit("node-a", window_seconds=-1.0, max_count=1)

    with pytest.raises(ValueError):
        tracker.is_over_limit("node-a", window_seconds=1.0, max_count=-1)
