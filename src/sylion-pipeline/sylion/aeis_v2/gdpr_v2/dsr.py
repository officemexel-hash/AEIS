"""GDPR DSR service implementation.

The :class:`DsrService` is the single entry point for all 4 GDPR actions.
It composes a :class:`UserDataStore` (pluggable — see
:class:`InMemoryUserDataStore` for the dev/test default) with audit JSONL
emission to ``logs/v2/gdpr_dsr.jsonl``.

Soft-delete contract (ERASURE):
    1. ``erase(user_id)`` flips ``deleted_at = now()`` on the row.
    2. The user disappears from ACCESS/PORTABILITY responses.
    3. A daily cron (TODO ``hard_purge.py``) physically removes rows
       where ``deleted_at`` is older than 30 days.
    4. Operators can ``rectify`` a soft-deleted user within the window
       to undo the ERASURE — the audit chain records both events so the
       DPO can verify the reversal trail.

Audit emission is best-effort: a failure to write the JSONL row is
logged but does NOT block the DSR action. Production deployments should
also tail the JSONL into a tamper-evident sink (e.g. S3 with object
lock) — this is documented in the W17 evidence-spine charter.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

log = logging.getLogger(__name__)


def _default_audit_path() -> Path:
    try:
        from sylion.aeis_v2.audit_profile import resolve_audit_chain_path

        return resolve_audit_chain_path(
            "gdpr_dsr.jsonl",
            Path(__file__).resolve().parents[3] / "logs" / "v2",
        )
    except Exception:  # noqa: BLE001
        return Path(__file__).resolve().parents[3] / "logs" / "v2" / "gdpr_dsr.jsonl"

#: All canonical DSR action names. Extend ONLY after a DPO impact assessment.
DSR_ACTIONS: tuple[str, ...] = (
    "access",
    "rectification",
    "erasure",
    "portability",
)
DsrAction = Literal["access", "rectification", "erasure", "portability"]


@dataclass(frozen=True, slots=True)
class DsrAuditEntry:
    """One row in the DSR audit JSONL.

    Field order is stable so downstream consumers (DPO export, SOX audit
    aggregator) can rely on the schema without a registry lookup.
    """

    event_id: str
    ts: float
    action: str
    user_id: str
    actor: str
    success: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "action": self.action,
            "user_id": self.user_id,
            "actor": self.actor,
            "success": self.success,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class DsrResult:
    """Outcome of a DSR action."""

    action: str
    user_id: str
    success: bool
    payload: dict[str, Any] | None
    audit_event_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "user_id": self.user_id,
            "success": self.success,
            "payload": self.payload,
            "audit_event_id": self.audit_event_id,
        }


class UserDataStore(ABC):
    """Abstract per-user data backend."""

    @abstractmethod
    def get(self, user_id: str) -> dict[str, Any] | None:
        """Return the full record or None if user does not exist or is erased."""

    @abstractmethod
    def upsert(self, user_id: str, data: dict[str, Any]) -> None:
        """Create or merge user data (used by RECTIFICATION)."""

    @abstractmethod
    def soft_delete(self, user_id: str, ts: float) -> bool:
        """Mark user as deleted_at=ts. Returns True if row existed and was flipped."""

    @abstractmethod
    def export_portable(self, user_id: str) -> dict[str, Any] | None:
        """Return GDPR Article 20 portable representation (JSON-serialisable)."""

    @abstractmethod
    def list_users(self) -> list[str]:
        """Return all user_ids known to the store (excluding hard-purged)."""


class InMemoryUserDataStore(UserDataStore):
    """Reference store for dev/test. NOT thread-safe across processes."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def get(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._rows.get(user_id)
            if row is None:
                return None
            if row.get("deleted_at") is not None:
                return None
            # Return a deep copy so callers can't mutate the store accidentally.
            return json.loads(json.dumps(row))

    def upsert(self, user_id: str, data: dict[str, Any]) -> None:
        with self._lock:
            existing = self._rows.get(user_id, {})
            merged = {**existing, **data}
            # RECTIFICATION on a soft-deleted user wipes the deletion flag —
            # this is the GDPR Article 12.3 reversal path.
            merged.pop("deleted_at", None)
            merged["user_id"] = user_id
            merged["updated_at"] = time.time()
            self._rows[user_id] = merged

    def soft_delete(self, user_id: str, ts: float) -> bool:
        with self._lock:
            row = self._rows.get(user_id)
            if row is None:
                return False
            row["deleted_at"] = ts
            return True

    def export_portable(self, user_id: str) -> dict[str, Any] | None:
        row = self.get(user_id)
        if row is None:
            return None
        # Article 20: machine-readable, structured. JSON satisfies that.
        return {
            "schema": "sylion.gdpr.dsr.portability/v1",
            "exported_at": time.time(),
            "user": row,
        }

    def list_users(self) -> list[str]:
        with self._lock:
            return sorted(uid for uid, row in self._rows.items()
                          if row.get("deleted_at") is None)


class DsrService:
    """Orchestrator for all 4 DSR actions + audit JSONL emission."""

    def __init__(
        self,
        store: UserDataStore | None = None,
        audit_log_path: Path | str | None = None,
    ) -> None:
        self._store = store or InMemoryUserDataStore()
        self._audit_path = (
            Path(audit_log_path) if audit_log_path is not None
            else _default_audit_path()
        )
        self._lock = threading.RLock()

    @property
    def store(self) -> UserDataStore:
        return self._store

    def _emit_audit(self, entry: DsrAuditEntry) -> None:
        # Sprint 2 day 6 — migrated to tamper-evident chain (commit ac97e957).
        # Best-effort emit: a chain failure does NOT block the DSR action.
        try:
            from sylion.aeis_v2.audit_chain import append_to_chain

            append_to_chain(self._audit_path, entry.to_dict())
        except Exception as exc:  # noqa: BLE001
            log.warning("gdpr_dsr: audit emit failed (%s)", exc)

    # ------------------------------------------------------------------
    # GDPR Article 15 — ACCESS
    # ------------------------------------------------------------------

    def access(self, user_id: str, *, actor: str = "anonymous") -> DsrResult:
        record = self._store.get(user_id)
        success = record is not None
        entry = DsrAuditEntry(
            event_id=str(uuid.uuid4()),
            ts=time.time(),
            action="access",
            user_id=user_id,
            actor=actor,
            success=success,
            details={"found": success},
        )
        self._emit_audit(entry)
        return DsrResult(
            action="access",
            user_id=user_id,
            success=success,
            payload=record,
            audit_event_id=entry.event_id,
        )

    # ------------------------------------------------------------------
    # GDPR Article 16 — RECTIFICATION
    # ------------------------------------------------------------------

    def rectify(
        self,
        user_id: str,
        patch: dict[str, Any],
        *,
        actor: str = "anonymous",
    ) -> DsrResult:
        if not patch:
            entry = DsrAuditEntry(
                event_id=str(uuid.uuid4()),
                ts=time.time(),
                action="rectification",
                user_id=user_id,
                actor=actor,
                success=False,
                details={"reason": "empty patch"},
            )
            self._emit_audit(entry)
            return DsrResult(
                action="rectification",
                user_id=user_id,
                success=False,
                payload={"error": "empty patch"},
                audit_event_id=entry.event_id,
            )

        with self._lock:
            self._store.upsert(user_id, patch)

        entry = DsrAuditEntry(
            event_id=str(uuid.uuid4()),
            ts=time.time(),
            action="rectification",
            user_id=user_id,
            actor=actor,
            success=True,
            details={"patched_keys": sorted(patch.keys())},
        )
        self._emit_audit(entry)
        return DsrResult(
            action="rectification",
            user_id=user_id,
            success=True,
            payload={"patched_keys": sorted(patch.keys())},
            audit_event_id=entry.event_id,
        )

    # ------------------------------------------------------------------
    # GDPR Article 17 — ERASURE (soft-delete + 30d hard purge by cron)
    # ------------------------------------------------------------------

    def erase(self, user_id: str, *, actor: str = "anonymous") -> DsrResult:
        ts = time.time()
        with self._lock:
            ok = self._store.soft_delete(user_id, ts)
        entry = DsrAuditEntry(
            event_id=str(uuid.uuid4()),
            ts=ts,
            action="erasure",
            user_id=user_id,
            actor=actor,
            success=ok,
            details={"soft_delete_ts": ts, "hard_purge_after_s": 30 * 24 * 3600},
        )
        self._emit_audit(entry)
        return DsrResult(
            action="erasure",
            user_id=user_id,
            success=ok,
            payload={"soft_delete_ts": ts} if ok else {"error": "user not found"},
            audit_event_id=entry.event_id,
        )

    # ------------------------------------------------------------------
    # GDPR Article 20 — PORTABILITY
    # ------------------------------------------------------------------

    def portability(self, user_id: str, *, actor: str = "anonymous") -> DsrResult:
        bundle = self._store.export_portable(user_id)
        success = bundle is not None
        entry = DsrAuditEntry(
            event_id=str(uuid.uuid4()),
            ts=time.time(),
            action="portability",
            user_id=user_id,
            actor=actor,
            success=success,
            details={"schema": bundle["schema"] if bundle else None},
        )
        self._emit_audit(entry)
        return DsrResult(
            action="portability",
            user_id=user_id,
            success=success,
            payload=bundle,
            audit_event_id=entry.event_id,
        )


# ---------------------------------------------------------------------------
# Singleton accessor — thread-safe lazy default for the REST router.
# ---------------------------------------------------------------------------

_default_service: DsrService | None = None
_lock = threading.Lock()


def get_dsr_service() -> DsrService:
    """Return the process-wide DsrService singleton."""
    global _default_service
    with _lock:
        if _default_service is None:
            _default_service = DsrService()
        return _default_service


def set_dsr_service(service: DsrService) -> None:
    """Replace the default — useful for tests / wiring a real PG store."""
    global _default_service
    with _lock:
        _default_service = service


def reset_dsr_service() -> None:
    """Drop the cached default. Next :func:`get_dsr_service` rebuilds."""
    global _default_service
    with _lock:
        _default_service = None
