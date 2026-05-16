"""GDPR Article 17 — hard purge cron.

Companion to ``aeis_v2/gdpr_v2/dsr.py`` (commit bc68430f). The DSR
service soft-deletes a user (``deleted_at = now()``) so the operator
can reverse an erasure within the GDPR Article 12.3 controller-response
window (one calendar month). After the window elapses the data must be
physically destroyed — that physical destruction is the job of this
module.

The cron runner is deliberately separate from DsrService so the daily
purge job can run in a different process / pod / container without
pulling FastAPI in. It accepts a :class:`PurgeableStore` interface
that the production PgUserDataStore will satisfy; the dev/test path
reuses :class:`InMemoryUserDataStore` extended with a ``hard_purge``
method.

Audit emission goes through :func:`append_to_chain` (commit ac97e957)
so the purge ledger is tamper-evident — the DPO can verify that no
purge entries were dropped or back-dated.
"""
from __future__ import annotations

import logging
import time
from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from sylion.aeis_v2.audit_chain import append_to_chain
from sylion.aeis_v2.gdpr_v2.dsr import InMemoryUserDataStore, UserDataStore

log = logging.getLogger(__name__)


def _default_audit_path() -> Path:
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_path

        return resolve_audit_chain_path(
            "gdpr_hard_purge.jsonl",
            Path(__file__).resolve().parents[3] / "logs" / "v2",
        )
    except Exception:  # noqa: BLE001
        return (
            Path(__file__).resolve().parents[3]
            / "logs" / "v2" / "gdpr_hard_purge.jsonl"
        )

#: Default GDPR Article 12.3 grace period — one calendar month. Operator
#: can override via the ``grace_period_s`` argument, but anything shorter
#: than 24 hours emits a warning so accidental misconfiguration is loud.
DEFAULT_GRACE_PERIOD_S: int = 30 * 24 * 3600


@dataclass(frozen=True, slots=True)
class PurgeReport:
    """Outcome of one purge_expired run."""

    started_at: float
    finished_at: float
    candidates: int
    purged: list[str]
    skipped: list[str]
    errors: list[str]

    @property
    def duration_s(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "candidates": self.candidates,
            "purged": list(self.purged),
            "skipped": list(self.skipped),
            "errors": list(self.errors),
        }


class PurgeableStore(Protocol):
    """Subset of UserDataStore that the cron needs."""

    def list_with_deleted_at(self) -> Iterable[tuple[str, float]]:
        """Yield ``(user_id, deleted_at_ts)`` for soft-deleted rows."""

    def hard_purge(self, user_id: str) -> bool:
        """Physically remove the row. Returns True on success."""


# ---------------------------------------------------------------------------
# Test/dev wrapper that adapts InMemoryUserDataStore to PurgeableStore.
# Production swaps in PgUserDataStore (cf2 design) which implements both
# UserDataStore + PurgeableStore directly.
# ---------------------------------------------------------------------------


class PurgeableInMemoryStore(InMemoryUserDataStore):
    """``InMemoryUserDataStore`` + the two purge primitives."""

    def list_with_deleted_at(self) -> Iterable[tuple[str, float]]:
        with self._lock:
            return [
                (uid, float(row["deleted_at"]))
                for uid, row in self._rows.items()
                if row.get("deleted_at") is not None
            ]

    def hard_purge(self, user_id: str) -> bool:
        with self._lock:
            row = self._rows.get(user_id)
            if row is None or row.get("deleted_at") is None:
                return False
            del self._rows[user_id]
            return True


# ---------------------------------------------------------------------------
# HardPurgeCron — orchestrator.
# ---------------------------------------------------------------------------


class HardPurgeCron:
    """Iterate soft-deleted users and physically purge those past the window.

    Audit log (chained, tamper-evident):

        kind="gdpr.hard_purge.run"   started_at, finished_at, candidates,
                                     purged_count, skipped_count
        kind="gdpr.hard_purge.row"   user_id, deleted_at, purged|skipped|error
    """

    def __init__(
        self,
        store: PurgeableStore,
        *,
        audit_log_path: Path | str | None = None,
        grace_period_s: int = DEFAULT_GRACE_PERIOD_S,
    ) -> None:
        self._store = store
        self._audit_path = (
            Path(audit_log_path) if audit_log_path is not None
            else _default_audit_path()
        )
        if grace_period_s < 24 * 3600:
            log.warning(
                "gdpr_hard_purge: grace_period_s=%d is shorter than 24h — "
                "GDPR Article 12.3 typically requires one calendar month",
                grace_period_s,
            )
        self._grace_period_s = grace_period_s

    @property
    def grace_period_s(self) -> int:
        return self._grace_period_s

    def _emit(self, payload: dict[str, Any]) -> None:
        try:
            append_to_chain(self._audit_path, payload)
        except OSError as exc:
            log.warning("gdpr_hard_purge: audit emit failed (%s)", exc)

    def purge_expired(self, now: float | None = None) -> PurgeReport:
        """Walk soft-deleted rows; purge those past the grace window.

        Args:
            now: override "current time" for deterministic tests. Defaults
                to ``time.time()``.

        Returns:
            :class:`PurgeReport` with candidates seen + per-user outcomes.
        """
        started_at = now if now is not None else time.time()
        rows = list(self._store.list_with_deleted_at())
        purged: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []

        for user_id, deleted_at in rows:
            age_s = started_at - deleted_at
            if age_s < self._grace_period_s:
                skipped.append(user_id)
                self._emit({
                    "kind": "gdpr.hard_purge.row",
                    "user_id": user_id,
                    "deleted_at": deleted_at,
                    "outcome": "skipped",
                    "age_s": age_s,
                })
                continue
            try:
                ok = self._store.hard_purge(user_id)
            except Exception as exc:  # noqa: BLE001
                errors.append(user_id)
                self._emit({
                    "kind": "gdpr.hard_purge.row",
                    "user_id": user_id,
                    "deleted_at": deleted_at,
                    "outcome": "error",
                    "error": str(exc),
                })
                continue
            if ok:
                purged.append(user_id)
                self._emit({
                    "kind": "gdpr.hard_purge.row",
                    "user_id": user_id,
                    "deleted_at": deleted_at,
                    "outcome": "purged",
                    "age_s": age_s,
                })
            else:
                # Already gone (race) — record but don't error.
                skipped.append(user_id)
                self._emit({
                    "kind": "gdpr.hard_purge.row",
                    "user_id": user_id,
                    "deleted_at": deleted_at,
                    "outcome": "already_gone",
                })

        finished_at = time.time()
        report = PurgeReport(
            started_at=started_at,
            finished_at=finished_at,
            candidates=len(rows),
            purged=purged,
            skipped=skipped,
            errors=errors,
        )
        self._emit({
            "kind": "gdpr.hard_purge.run",
            **report.to_dict(),
        })
        log.info(
            "gdpr_hard_purge: candidates=%d purged=%d skipped=%d errors=%d",
            len(rows), len(purged), len(skipped), len(errors),
        )
        return report
