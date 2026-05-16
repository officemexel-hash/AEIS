from __future__ import annotations

from threading import Thread

from sylion.aeis_v2.replay_v2.replay_storage_lru import ReplayStorageLRU


def test_store_and_get_round_trip() -> None:
    s = ReplayStorageLRU()
    s.store("a", {"v": 1})
    assert s.get("a") == {"v": 1}


def test_get_missing_returns_none() -> None:
    assert ReplayStorageLRU().get("missing") is None


def test_get_refreshes_lru_order() -> None:
    s = ReplayStorageLRU()
    for k in ("a", "b", "c"):
        s.store(k, {"k": k})
    s.get("a")
    s.evict_old(2)
    assert s.get("a") == {"k": "a"}
    assert s.get("c") == {"k": "c"}
    assert s.get("b") is None


def test_evict_old_keeps_most_recent_items() -> None:
    s = ReplayStorageLRU()
    for k in ("a", "b", "c"):
        s.store(k, {"k": k})
    s.evict_old(2)
    assert list(s._data) == ["b", "c"]


def test_thread_safe_under_parallel_store_and_get() -> None:
    s = ReplayStorageLRU()

    def worker(i: int) -> None:
        key = f"s{i}"
        s.store(key, {"i": i})
        assert s.get(key) == {"i": i}

    threads = [Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    s.evict_old(5)
    assert len(s._data) == 5
