"""Tamper-evident audit chain implementation."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

#: 16 hex chars (8 bytes) — collision probability is ~ 2^-32 across the
#: rows in a single chain, well below tampering-detection requirements.
HASH_LEN: int = 16

#: First-row predecessor hash. Documented in __init__.py.
GENESIS_HASH: str = "0" * HASH_LEN

#: Process-wide write lock. Multiple paths share the lock — append rate
#: is bounded by audit emission frequency (≤ 100/s typical) so a single
#: lock keeps the implementation simple without blocking real workloads.
_APPEND_LOCK = threading.RLock()

#: Per-path last-content-hash cache. Sprint 2 day 7 perf fix per Kimi
#: review k1_audit_chain_perf_review (round 50:30) — eliminates the
#: O(n) tail-file-read on every append. After warm-up the cache is hit
#: on every append; the disk file is read at most once per process per
#: path. Cache is keyed by absolute path string so symlinks pointing to
#: the same file get the same entry.
_LAST_HASH_CACHE: dict[str, str] = {}


def _cache_key(path: Path) -> str:
    """Stable cache key for a path — absolute resolved string."""
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def reset_last_hash_cache() -> None:
    """Drop every cached last-hash entry. Tests and rotator helpers."""
    with _APPEND_LOCK:
        _LAST_HASH_CACHE.clear()


def invalidate_last_hash_cache(path: Path | str) -> None:
    """Invalidate a single path's cache entry — useful after rotation."""
    with _APPEND_LOCK:
        _LAST_HASH_CACHE.pop(_cache_key(Path(path)), None)


@dataclass(frozen=True, slots=True)
class AuditChainEntry:
    """One on-disk row in the chain."""

    prev_hash: str
    content: dict[str, Any]
    content_hash: str

    def to_jsonl(self) -> str:
        return json.dumps(
            {
                "prev_hash": self.prev_hash,
                "content": self.content,
                "content_hash": self.content_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    @classmethod
    def from_jsonl_dict(cls, d: dict[str, Any]) -> "AuditChainEntry":
        return cls(
            prev_hash=str(d.get("prev_hash", "")),
            content=dict(d.get("content") or {}),
            content_hash=str(d.get("content_hash", "")),
        )


@dataclass(frozen=True, slots=True)
class Tampered:
    """Verification fault — a row that fails the chain check."""

    line_no: int
    reason: str
    expected: str
    actual: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_no": self.line_no,
            "reason": self.reason,
            "expected": self.expected,
            "actual": self.actual,
        }


def compute_content_hash(prev_hash: str, content: dict[str, Any]) -> str:
    """Compute the next hash given the previous tail and new content.

    Stable: ``json.dumps`` with ``sort_keys=True`` ensures dict iteration
    order does not affect the hash.
    """
    payload = prev_hash + json.dumps(
        content, sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:HASH_LEN]


def _read_tail_hash(path: Path) -> str:
    """Return the ``content_hash`` of the last row, or GENESIS_HASH if empty."""
    if not path.exists():
        return GENESIS_HASH
    last_line: str | None = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
    except OSError as exc:
        log.warning("audit_chain: tail read failed (%s)", exc)
        return GENESIS_HASH
    if not last_line:
        return GENESIS_HASH
    try:
        d = json.loads(last_line)
    except json.JSONDecodeError:
        # Corrupt tail — fall back to genesis. The corruption itself
        # will be flagged by verify_chain on the next audit walk.
        return GENESIS_HASH
    return str(d.get("content_hash") or GENESIS_HASH)


def append_to_chain(
    path: Path | str, content: dict[str, Any],
) -> AuditChainEntry:
    """Atomically append a content dict as the next chain entry.

    The function reads the tail of the file under a process-wide RLock
    so concurrent appends from different threads cannot both base their
    hash on the same predecessor (which would fork the chain).

    Performance: a per-path ``_LAST_HASH_CACHE`` short-circuits the
    O(n) tail-file scan after the first append. The on-disk file is
    read exactly once per process per path; subsequent appends hit
    the cache in O(1). Cache invalidation happens automatically on
    every successful append, and explicitly via
    :func:`invalidate_last_hash_cache` after file rotation.

    Returns:
        :class:`AuditChainEntry` describing the freshly-written row.

    Raises:
        OSError: if the file cannot be opened for append. Callers that
            cannot afford to fail (e.g. GDPR audit emission) should
            wrap this in a ``try/except OSError`` to log + degrade.
    """
    p = Path(path)
    key = _cache_key(p)
    with _APPEND_LOCK:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Cache hit → O(1); cache miss → O(n) tail read once.
        prev = _LAST_HASH_CACHE.get(key)
        if prev is None:
            prev = _read_tail_hash(p)
        ch = compute_content_hash(prev, content)
        entry = AuditChainEntry(
            prev_hash=prev, content=dict(content), content_hash=ch,
        )
        with open(p, "a", encoding="utf-8") as f:
            f.write(entry.to_jsonl() + "\n")
        _LAST_HASH_CACHE[key] = ch
        return entry


def verify_chain(path: Path | str) -> list[Tampered]:
    """Walk a chain JSONL and report tampered rows.

    Empty / missing file → ``[]`` (vacuously valid).

    Detected faults:

    * unparseable JSON line
    * missing ``prev_hash`` / ``content`` / ``content_hash`` field
    * recomputed content_hash differs from the on-disk value
    * prev_hash does not equal the previous row's content_hash
      (or the genesis hash for the first row)
    """
    p = Path(path)
    faults: list[Tampered] = []
    if not p.exists():
        return faults

    expected_prev = GENESIS_HASH
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    d = json.loads(stripped)
                except json.JSONDecodeError:
                    faults.append(Tampered(
                        line_no=line_no,
                        reason="json_parse_error",
                        expected="<valid json object>",
                        actual=stripped[:64],
                    ))
                    # The chain breaks here — every subsequent row is
                    # untrustworthy. We keep walking so the operator
                    # sees the full damage.
                    expected_prev = ""
                    continue
                prev_hash = str(d.get("prev_hash") or "")
                content = d.get("content")
                content_hash = str(d.get("content_hash") or "")
                if not isinstance(content, dict) or not content_hash:
                    faults.append(Tampered(
                        line_no=line_no,
                        reason="missing_field",
                        expected="prev_hash+content+content_hash",
                        actual=stripped[:64],
                    ))
                    expected_prev = ""
                    continue
                # 1) prev_hash must match the running expected.
                if expected_prev and prev_hash != expected_prev:
                    faults.append(Tampered(
                        line_no=line_no,
                        reason="prev_hash_mismatch",
                        expected=expected_prev,
                        actual=prev_hash,
                    ))
                # 2) content_hash must match the recomputed value.
                recomputed = compute_content_hash(prev_hash, content)
                if recomputed != content_hash:
                    faults.append(Tampered(
                        line_no=line_no,
                        reason="content_hash_mismatch",
                        expected=recomputed,
                        actual=content_hash,
                    ))
                expected_prev = content_hash
    except OSError as exc:
        log.warning("audit_chain: verify read failed (%s)", exc)
    return faults


def check_chain_replay_consistency(chain_path_a: Path, chain_path_b: Path) -> bool:
    def _head_prev_and_count(path: Path) -> tuple[str | None, int]:
        head = None
        count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    stripped = raw.strip()
                    if not stripped:
                        continue
                    count += 1
                    if head is None:
                        try:
                            head = str(json.loads(stripped)["prev_hash"])
                        except (json.JSONDecodeError, KeyError, TypeError):
                            return None, count
        except OSError:
            return None, 0
        return head, count

    head_a, count_a = _head_prev_and_count(chain_path_a)
    head_b, count_b = _head_prev_and_count(chain_path_b)
    return bool(head_a) and head_a == head_b and count_a == count_b
