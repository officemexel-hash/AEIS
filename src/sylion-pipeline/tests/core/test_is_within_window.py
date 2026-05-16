from datetime import datetime

from sylion.core.time_window import is_within_window
import sylion.core.time_window as time_window


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls.fromisoformat("2026-04-28T12:00:00+00:00")


def test_returns_true_inside_window(monkeypatch):
    monkeypatch.setattr(time_window, "datetime", FrozenDateTime)
    assert is_within_window("2026-04-28T11:59:31+00:00", 30)


def test_returns_true_at_boundary(monkeypatch):
    monkeypatch.setattr(time_window, "datetime", FrozenDateTime)
    assert is_within_window("2026-04-28T11:59:30+00:00", 30)


def test_returns_false_outside_window(monkeypatch):
    monkeypatch.setattr(time_window, "datetime", FrozenDateTime)
    assert not is_within_window("2026-04-28T11:59:29+00:00", 30)


def test_returns_true_for_future_timestamp(monkeypatch):
    monkeypatch.setattr(time_window, "datetime", FrozenDateTime)
    assert is_within_window("2026-04-28T12:00:05+00:00", 30)
