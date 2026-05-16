from __future__ import annotations

from collections import OrderedDict
from threading import RLock


class ReplayStorageLRU:
    def __init__(self) -> None:
        self._lock = RLock()
        self._data: OrderedDict[str, dict] = OrderedDict()

    def store(self, snapshot_id: str, snapshot_dict: dict) -> None:
        with self._lock:
            self._data[snapshot_id] = snapshot_dict
            self._data.move_to_end(snapshot_id)

    def get(self, snapshot_id: str) -> dict | None:
        with self._lock:
            value = self._data.get(snapshot_id)
            if value is not None:
                self._data.move_to_end(snapshot_id)
            return value

    def evict_old(self, max: int = 100) -> None:
        with self._lock:
            max = max if max > 0 else 0
            while len(self._data) > max:
                self._data.popitem(last=False)
