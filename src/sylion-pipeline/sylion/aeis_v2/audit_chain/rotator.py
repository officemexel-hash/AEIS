"""Audit JSONL rotator — sprint 3 D-rotator deliverable.

Closes the chained-JSONL companion to ``sylion.aeis_v2.audit_chain.chain``:
without rotation a long-running pod accumulates ever-growing ``logs/v2/*.jsonl``
files until disk pressure breaks the audit emission pipeline.

The rotator answers two operational questions:

1. **When to rotate** — at midnight (UTC), or eagerly when a chain
   exceeds ``size_mb_threshold`` (default 100 MB). Both gates are
   independent: a small chain still rotates at midnight; a busy chain
   rotates the moment it crosses the size threshold.

2. **What to keep** — the rotator can prune rotated files older than
   ``retain_days`` (default 90 days, matching the 90-day retention in
   the W17 evidence-spine charter §4).

Rotation produces a sibling file named ``<original_stem>.<YYYY-MM-DD>.<seq>.jsonl``
in the same directory. Sequence numbers re-base at 1 each calendar day
to keep the filenames human-friendly. After rotation the rotator
invalidates the per-path :data:`_LAST_HASH_CACHE` so the next
``append_to_chain`` rebuilds against the empty (genesis) tail.

Audit emission for the rotator itself goes through ``append_to_chain``
to ``logs/v2/audit_rotation.jsonl``, so the DPO can see *who rotated
what when* in the same chained-JSONL format used by every other v2
module.
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from sylion.aeis_v2.audit_chain.chain import (
    append_to_chain,
    invalidate_last_hash_cache,
)

log = logging.getLogger(__name__)

#: Default rotation size threshold (megabytes).
DEFAULT_SIZE_MB_THRESHOLD: int = 100

#: Default retain window (days). Matches W17 evidence-spine §4 retention.
DEFAULT_RETAIN_DAYS: int = 90

#: Filename pattern for a rotated chain. e.g. ``gdpr_dsr.2026-04-28.1.jsonl``.
_ROTATED_NAME_RE = re.compile(
    r"^(?P<stem>.+)\.(?P<date>\d{4}-\d{2}-\d{2})\.(?P<seq>\d+)\.jsonl$"
)

#: Audit JSONL for the rotator's own actions. Resolved lazily so tests can
#: redirect via constructor arg.
DEFAULT_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "audit_rotation.jsonl"
)


def _today_iso(now: _dt.datetime | None = None) -> str:
    """Today's calendar date in UTC, ISO format ``YYYY-MM-DD``."""
    n = now or _dt.datetime.now(_dt.timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=_dt.timezone.utc)
    return n.strftime("%Y-%m-%d")


def _next_seq_for_date(directory: Path, stem: str, date_iso: str) -> int:
    """Find the next ``seq`` number for ``<stem>.<date>.<N>.jsonl`` in dir."""
    if not directory.exists():
        return 1
    seen: list[int] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        m = _ROTATED_NAME_RE.match(entry.name)
        if not m:
            continue
        if m.group("stem") != stem or m.group("date") != date_iso:
            continue
        try:
            seen.append(int(m.group("seq")))
        except ValueError:
            continue
    return max(seen) + 1 if seen else 1


def _file_size_mb(path: Path) -> float:
    """File size in megabytes; 0 for missing/unreadable files."""
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


@dataclass(frozen=True, slots=True)
class RotationDecision:
    """The rotator's reasoning about a single chain path."""

    path: Path
    rotated: bool
    reason: str
    rotated_to: Path | None = None
    size_mb: float = 0.0
    forced_by_size: bool = False
    forced_by_midnight: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "rotated": self.rotated,
            "reason": self.reason,
            "rotated_to": str(self.rotated_to) if self.rotated_to else None,
            "size_mb": round(self.size_mb, 4),
            "forced_by_size": self.forced_by_size,
            "forced_by_midnight": self.forced_by_midnight,
        }


@dataclass(frozen=True, slots=True)
class EvictionReport:
    """Summary of one ``evict_old`` invocation."""

    deleted: list[Path] = field(default_factory=list)
    kept: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "deleted": [str(p) for p in self.deleted],
            "kept": [str(p) for p in self.kept],
            "errors": list(self.errors),
        }


class AuditRotator:
    """Rotate + evict chained audit JSONL files.

    Thread-safe via an :data:`RLock` so concurrent operator + cron
    invocations don't double-rotate the same file.
    """

    def __init__(
        self,
        *,
        size_mb_threshold: int = DEFAULT_SIZE_MB_THRESHOLD,
        retain_days: int = DEFAULT_RETAIN_DAYS,
        audit_log_path: Path | str | None = None,
    ) -> None:
        if size_mb_threshold <= 0:
            raise ValueError("size_mb_threshold must be positive")
        if retain_days <= 0:
            raise ValueError("retain_days must be positive")
        self._size_mb_threshold = size_mb_threshold
        self._retain_days = retain_days
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None
            else DEFAULT_AUDIT_LOG_PATH
        )
        self._lock = threading.RLock()

    @property
    def size_mb_threshold(self) -> int:
        return self._size_mb_threshold

    @property
    def retain_days(self) -> int:
        return self._retain_days

    def _emit(self, payload: dict[str, Any]) -> None:
        try:
            append_to_chain(self._audit_log_path, payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("audit_rotator: audit emit failed (%s)", exc)

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def rotate_if_needed(
        self,
        path: Path | str,
        *,
        now: _dt.datetime | None = None,
        force_midnight: bool = False,
    ) -> RotationDecision:
        """Rotate a chain if it crossed size or midnight boundary.

        Args:
            path: chain JSONL to inspect.
            now: override "current time" for tests. Defaults to UTC now.
            force_midnight: treat this call as a midnight rotation
                regardless of the actual time. Used by the cron runner.
        """
        p = Path(path)
        with self._lock:
            if not p.exists() or p.stat().st_size == 0:
                return RotationDecision(
                    path=p, rotated=False, reason="empty_or_missing",
                )

            size_mb = _file_size_mb(p)
            forced_by_size = size_mb >= self._size_mb_threshold

            if not (forced_by_size or force_midnight):
                return RotationDecision(
                    path=p, rotated=False, reason="under_threshold",
                    size_mb=size_mb,
                )

            date_iso = _today_iso(now)
            seq = _next_seq_for_date(p.parent, p.stem, date_iso)
            rotated_name = f"{p.stem}.{date_iso}.{seq}.jsonl"
            rotated_path = p.parent / rotated_name

            try:
                p.rename(rotated_path)
            except OSError as exc:
                log.warning("audit_rotator: rename failed (%s)", exc)
                return RotationDecision(
                    path=p, rotated=False, reason=f"rename_failed:{exc}",
                    size_mb=size_mb,
                )

            # Drop the cache entry — the next append on the original
            # path starts a fresh chain from genesis.
            invalidate_last_hash_cache(p)

            decision = RotationDecision(
                path=p,
                rotated=True,
                reason="rotated",
                rotated_to=rotated_path,
                size_mb=size_mb,
                forced_by_size=forced_by_size,
                forced_by_midnight=force_midnight,
            )
            self._emit({
                "kind": "audit_rotation.rotate",
                **decision.to_dict(),
            })
            log.info(
                "audit_rotator: rotated %s -> %s (size_mb=%.2f, "
                "forced_by_size=%s, forced_by_midnight=%s)",
                p, rotated_path, size_mb, forced_by_size, force_midnight,
            )
            return decision

    # ------------------------------------------------------------------
    # Eviction
    # ------------------------------------------------------------------

    def evict_old(
        self, directory: Path | str, *, now: _dt.datetime | None = None,
    ) -> EvictionReport:
        """Delete rotated files older than ``retain_days``.

        Only files matching the canonical rotated name pattern are
        considered — original chain files are never touched.
        """
        d = Path(directory)
        if not d.exists():
            return EvictionReport()

        n = now or _dt.datetime.now(_dt.timezone.utc)
        if n.tzinfo is None:
            n = n.replace(tzinfo=_dt.timezone.utc)
        cutoff = n - _dt.timedelta(days=self._retain_days)

        deleted: list[Path] = []
        kept: list[Path] = []
        errors: list[str] = []

        with self._lock:
            for entry in d.iterdir():
                if not entry.is_file():
                    continue
                m = _ROTATED_NAME_RE.match(entry.name)
                if not m:
                    continue
                date_str = m.group("date")
                try:
                    file_date = _dt.datetime.strptime(
                        date_str, "%Y-%m-%d",
                    ).replace(tzinfo=_dt.timezone.utc)
                except ValueError:
                    errors.append(f"unparseable_date:{entry.name}")
                    continue

                if file_date < cutoff:
                    try:
                        entry.unlink()
                        deleted.append(entry)
                    except OSError as exc:
                        errors.append(f"unlink_failed:{entry.name}:{exc}")
                else:
                    kept.append(entry)

        report = EvictionReport(deleted=deleted, kept=kept, errors=errors)
        self._emit({
            "kind": "audit_rotation.evict",
            "directory": str(d),
            "retain_days": self._retain_days,
            **report.to_dict(),
        })
        log.info(
            "audit_rotator: evict directory=%s deleted=%d kept=%d errors=%d",
            d, len(deleted), len(kept), len(errors),
        )
        return report

    # ------------------------------------------------------------------
    # Cron entrypoint
    # ------------------------------------------------------------------

    def run_daily(
        self,
        chain_paths: Iterable[Path | str],
        *,
        directory: Path | str,
        now: _dt.datetime | None = None,
    ) -> dict[str, Any]:
        """Run a midnight rotation across ``chain_paths`` + evict old.

        Used by the cron runner. Returns a summary suitable for the
        operator dashboard.
        """
        rotations: list[RotationDecision] = []
        for path in chain_paths:
            d = self.rotate_if_needed(path, now=now, force_midnight=True)
            rotations.append(d)
        eviction = self.evict_old(directory, now=now)

        summary = {
            "rotations": [r.to_dict() for r in rotations],
            "rotated_count": sum(1 for r in rotations if r.rotated),
            "eviction": eviction.to_dict(),
        }
        self._emit({"kind": "audit_rotation.run_daily", **summary})
        return summary


__all__ = [
    "AuditRotator",
    "DEFAULT_RETAIN_DAYS",
    "DEFAULT_SIZE_MB_THRESHOLD",
    "EvictionReport",
    "RotationDecision",
]
