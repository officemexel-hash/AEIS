from __future__ import annotations

from collections import defaultdict, deque


class RateLimitTracker:
    def __init__(self) -> None:
        self._calls_by_node: dict[str, deque[float]] = defaultdict(deque)

    def record_call(self, node_id: str, ts: float) -> None:
        self._calls_by_node[node_id].append(ts)

    def is_over_limit(
        self,
        node_id: str,
        window_seconds: float,
        max_count: int,
    ) -> bool:
        if window_seconds < 0:
            raise ValueError("window_seconds must be greater than or equal to 0")
        if max_count < 0:
            raise ValueError("max_count must be greater than or equal to 0")

        calls = self._calls_by_node[node_id]
        if not calls:
            return False

        latest_ts = calls[-1]
        cutoff_ts = latest_ts - window_seconds
        while calls and calls[0] < cutoff_ts:
            calls.popleft()

        return len(calls) > max_count
