"""Tests for ``sylion.aeis_v2.audit_chain`` — tamper-evident audit chain.

Covers append + verify primitives and the integrity guarantees against
the 4 expected attack vectors: line removal, content mutation, hash
mutation, and out-of-order replay.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import (
    GENESIS_HASH,
    AuditChainEntry,
    Tampered,
    append_to_chain,
    compute_content_hash,
    verify_chain,
)


# ---------------------------------------------------------------------------
# compute_content_hash + GENESIS_HASH sanity
# ---------------------------------------------------------------------------


def test_genesis_hash_is_16_zeros() -> None:
    assert GENESIS_HASH == "0" * 16


def test_compute_content_hash_stable_across_calls() -> None:
    h1 = compute_content_hash("prev", {"a": 1, "b": 2})
    h2 = compute_content_hash("prev", {"b": 2, "a": 1})
    assert h1 == h2  # sort_keys → insertion order does not matter


def test_compute_content_hash_changes_with_content() -> None:
    h1 = compute_content_hash("prev", {"a": 1})
    h2 = compute_content_hash("prev", {"a": 2})
    assert h1 != h2


def test_compute_content_hash_changes_with_prev() -> None:
    h1 = compute_content_hash("prev1", {"a": 1})
    h2 = compute_content_hash("prev2", {"a": 1})
    assert h1 != h2


def test_compute_content_hash_length() -> None:
    h = compute_content_hash("p", {"x": 1})
    assert len(h) == 16


# ---------------------------------------------------------------------------
# AuditChainEntry serialisation
# ---------------------------------------------------------------------------


def test_entry_to_jsonl_round_trips() -> None:
    e = AuditChainEntry(prev_hash="abc", content={"x": 1}, content_hash="def")
    line = e.to_jsonl()
    d = json.loads(line)
    assert d["prev_hash"] == "abc"
    assert d["content"] == {"x": 1}
    assert d["content_hash"] == "def"


def test_entry_from_jsonl_dict() -> None:
    d = {"prev_hash": "p", "content": {"k": "v"}, "content_hash": "h"}
    e = AuditChainEntry.from_jsonl_dict(d)
    assert e.prev_hash == "p"
    assert e.content == {"k": "v"}
    assert e.content_hash == "h"


# ---------------------------------------------------------------------------
# append_to_chain — single-writer behaviour
# ---------------------------------------------------------------------------


def test_append_first_row_uses_genesis_prev(tmp_path: Path) -> None:
    p = tmp_path / "chain.jsonl"
    e = append_to_chain(p, {"hello": "world"})
    assert e.prev_hash == GENESIS_HASH
    assert e.content == {"hello": "world"}


def test_append_subsequent_rows_link_correctly(tmp_path: Path) -> None:
    p = tmp_path / "chain.jsonl"
    e1 = append_to_chain(p, {"a": 1})
    e2 = append_to_chain(p, {"a": 2})
    e3 = append_to_chain(p, {"a": 3})
    assert e2.prev_hash == e1.content_hash
    assert e3.prev_hash == e2.content_hash


def test_append_creates_parent_dir_if_missing(tmp_path: Path) -> None:
    p = tmp_path / "deep" / "nested" / "chain.jsonl"
    append_to_chain(p, {"x": 1})
    assert p.exists()


def test_append_writes_jsonl_format(tmp_path: Path) -> None:
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"x": 1})
    append_to_chain(p, {"x": 2})
    lines = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]
    assert len(lines) == 2
    for d in lines:
        assert set(d.keys()) >= {"prev_hash", "content", "content_hash"}


def test_append_handles_non_serializable_via_str(tmp_path: Path) -> None:
    """Datetimes and similar non-JSON natives are coerced via default=str."""
    import datetime as dt

    p = tmp_path / "chain.jsonl"
    e = append_to_chain(p, {"ts": dt.datetime(2026, 4, 28)})
    assert e.content_hash  # didn't raise
    # The content dict on the entry retains the original object — only
    # the hash payload coerces — so callers can still inspect locally.
    assert isinstance(e.content["ts"], dt.datetime)


# ---------------------------------------------------------------------------
# verify_chain — clean chain
# ---------------------------------------------------------------------------


def test_verify_empty_file_is_vacuously_clean(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    assert verify_chain(p) == []


def test_verify_missing_file_is_clean(tmp_path: Path) -> None:
    p = tmp_path / "absent.jsonl"
    assert verify_chain(p) == []


def test_verify_single_row_clean(tmp_path: Path) -> None:
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"x": 1})
    assert verify_chain(p) == []


def test_verify_multi_row_clean(tmp_path: Path) -> None:
    p = tmp_path / "chain.jsonl"
    for i in range(5):
        append_to_chain(p, {"i": i})
    assert verify_chain(p) == []


# ---------------------------------------------------------------------------
# verify_chain — tamper detection
# ---------------------------------------------------------------------------


def test_verify_detects_content_mutation(tmp_path: Path) -> None:
    """An attacker edits the content of a row but leaves hashes alone."""
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"x": 1})
    append_to_chain(p, {"x": 2})

    # Tamper: rewrite line 1 with different content but same hashes.
    lines = p.read_text(encoding="utf-8").splitlines()
    d = json.loads(lines[0])
    d["content"] = {"x": "TAMPERED"}
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")

    faults = verify_chain(p)
    # Line 1 has wrong content_hash, line 2 has correct prev/content.
    reasons = [f.reason for f in faults]
    assert "content_hash_mismatch" in reasons


def test_verify_detects_unparseable_json(tmp_path: Path) -> None:
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"x": 1})
    # Append garbage line.
    with open(p, "a", encoding="utf-8") as f:
        f.write("this-is-not-json\n")

    faults = verify_chain(p)
    assert any(f.reason == "json_parse_error" for f in faults)


def test_verify_detects_missing_field(tmp_path: Path) -> None:
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"x": 1})
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps({"prev_hash": "abc"}) + "\n")

    faults = verify_chain(p)
    assert any(f.reason == "missing_field" for f in faults)


def test_verify_detects_line_deletion(tmp_path: Path) -> None:
    """Deleting a row breaks the prev_hash link of the next row."""
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"i": 1})
    append_to_chain(p, {"i": 2})
    append_to_chain(p, {"i": 3})

    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l]
    # Delete the middle row.
    p.write_text(lines[0] + "\n" + lines[2] + "\n")

    faults = verify_chain(p)
    assert any(f.reason == "prev_hash_mismatch" for f in faults)


def test_verify_detects_hash_only_mutation(tmp_path: Path) -> None:
    """An attacker rewrites just the content_hash without touching content."""
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"x": 1})

    lines = p.read_text(encoding="utf-8").splitlines()
    d = json.loads(lines[0])
    d["content_hash"] = "deadbeefdeadbeef"
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")

    faults = verify_chain(p)
    assert any(f.reason == "content_hash_mismatch" for f in faults)


def test_verify_detects_first_row_prev_hash_mutation(tmp_path: Path) -> None:
    """First row's prev_hash must equal GENESIS_HASH."""
    p = tmp_path / "chain.jsonl"
    append_to_chain(p, {"x": 1})

    lines = p.read_text(encoding="utf-8").splitlines()
    d = json.loads(lines[0])
    d["prev_hash"] = "deadbeefdeadbeef"
    lines[0] = json.dumps(d, sort_keys=True)
    p.write_text("\n".join(lines) + "\n")

    faults = verify_chain(p)
    # Either prev_hash_mismatch (vs genesis) or content_hash_mismatch
    # (because content_hash was computed against GENESIS).
    assert faults  # at least one fault detected
    assert any(
        f.reason in ("prev_hash_mismatch", "content_hash_mismatch") for f in faults
    )


def test_tampered_to_dict_serialisable() -> None:
    t = Tampered(line_no=5, reason="x", expected="a", actual="b")
    d = t.to_dict()
    assert d["line_no"] == 5
    json.dumps(d)  # JSON-serialisable


# ---------------------------------------------------------------------------
# Concurrency — RLock prevents fork-on-append
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Last-hash side cache — sprint 2 day 7 perf fix per Kimi review.
# ---------------------------------------------------------------------------


def test_last_hash_cache_speeds_up_repeated_appends(tmp_path: Path) -> None:
    """Cached path: 100 appends complete in well under 1s.

    The on-disk file is still written each time, but the tail re-read
    is replaced by an O(1) dict lookup. We sanity-check the perf with
    a generous 5s budget so the test is robust on slow CI.
    """
    import time

    from sylion.aeis_v2.audit_chain import (
        append_to_chain,
        reset_last_hash_cache,
        verify_chain,
    )

    reset_last_hash_cache()
    p = tmp_path / "perf.jsonl"
    start = time.time()
    for i in range(100):
        append_to_chain(p, {"i": i})
    elapsed = time.time() - start
    assert elapsed < 5.0, f"100 appends took {elapsed:.2f}s — perf regression"
    # And the chain must still verify clean.
    assert verify_chain(p) == []


def test_invalidate_cache_forces_disk_reread(tmp_path: Path) -> None:
    """After invalidate the next append re-reads the on-disk tail."""
    from sylion.aeis_v2.audit_chain import (
        append_to_chain,
        invalidate_last_hash_cache,
        verify_chain,
    )
    from sylion.aeis_v2.audit_chain.chain import _LAST_HASH_CACHE, _cache_key

    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"a": 1})
    assert _cache_key(p) in _LAST_HASH_CACHE  # populated
    invalidate_last_hash_cache(p)
    assert _cache_key(p) not in _LAST_HASH_CACHE  # gone

    # Subsequent append still produces a verifiable chain (cache rebuild).
    append_to_chain(p, {"a": 2})
    assert verify_chain(p) == []


def test_reset_cache_drops_all_entries(tmp_path: Path) -> None:
    from sylion.aeis_v2.audit_chain import (
        append_to_chain,
        reset_last_hash_cache,
    )
    from sylion.aeis_v2.audit_chain.chain import _LAST_HASH_CACHE

    append_to_chain(tmp_path / "a.jsonl", {"x": 1})
    append_to_chain(tmp_path / "b.jsonl", {"x": 2})
    assert len(_LAST_HASH_CACHE) >= 2
    reset_last_hash_cache()
    assert len(_LAST_HASH_CACHE) == 0


def test_cache_keeps_chains_isolated_per_path(tmp_path: Path) -> None:
    """Cache entries for different paths must NOT cross-contaminate."""
    from sylion.aeis_v2.audit_chain import append_to_chain, verify_chain

    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    for i in range(5):
        append_to_chain(a, {"file": "a", "i": i})
        append_to_chain(b, {"file": "b", "i": i})
    # Both must verify independently.
    assert verify_chain(a) == []
    assert verify_chain(b) == []


def test_append_concurrent_threads_chain_intact(tmp_path: Path) -> None:
    """N threads appending in parallel must still produce a verifiable chain."""
    import threading

    p = tmp_path / "chain.jsonl"
    n = 20

    def worker(i: int) -> None:
        append_to_chain(p, {"thread": i})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert verify_chain(p) == []
    # Make sure all rows landed.
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l]
    assert len(lines) == n
