from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start_ts: float
    end_ts: float

    def __post_init__(self) -> None:
        if self.end_ts < self.start_ts:
            raise ValueError("end_ts must be greater than or equal to start_ts")

    def contains(self, ts: float) -> bool:
        return self.start_ts <= ts <= self.end_ts

    def overlaps_with(self, other: "TimeWindow") -> bool:
        return self.start_ts <= other.end_ts and other.start_ts <= self.end_ts

    @property
    def duration_seconds(self) -> float:
        return self.end_ts - self.start_ts


def is_within_window(iso_ts: str, window_seconds: int, now: float | None = None) -> bool:
    parsed = datetime.fromisoformat(iso_ts).timestamp()
    current = datetime.now().timestamp() if now is None else now
    return (current - parsed) <= window_seconds
