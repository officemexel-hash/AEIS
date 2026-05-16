"""Rule loader — pulls active rules from DB with simple in-process cache."""

from __future__ import annotations

import threading
import time

from sylion.aeis.advisor.engine._db import fetch_rules
from sylion.aeis.advisor.engine._models import Rule

_CACHE_TTL_S = 30.0
_lock = threading.Lock()
_cache: list[Rule] = []
_loaded_at: float = 0.0


def load_active_rules(force: bool = False) -> list[Rule]:
    global _cache, _loaded_at
    now = time.time()
    if force or not _cache or (now - _loaded_at) > _CACHE_TTL_S:
        with _lock:
            if force or not _cache or (now - _loaded_at) > _CACHE_TTL_S:
                _cache = fetch_rules(active_only=True)
                _loaded_at = now
    return list(_cache)


def invalidate_cache() -> None:
    global _cache, _loaded_at
    with _lock:
        _cache = []
        _loaded_at = 0.0
