"""Synchronous facade for advisor preferences."""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sylion.aeis.advisor.preferences import _db, audit, catalog, learning, resolver
from sylion.aeis.advisor.preferences._models import CatalogEntry, PreferenceRow, ResolutionLevel
from sylion.core.event_backbone import get_event_backbone
from sylion.core.event_bus import SylionEvent


class PreferencesService:
    """High-level synchronous API for advisor preferences."""

    def __init__(self, event_bus: Any | None = None) -> None:
        self._event_bus = event_bus or get_event_backbone()
        self._lock = threading.Lock()

    def get_effective(
        self,
        *,
        user_id: str,
        project_type: str | None,
        project_domain: str | None,
        preference_key: str,
    ):
        return resolver.resolve_effective(
            user_id=user_id,
            project_type=project_type,
            project_domain=project_domain,
            preference_key=preference_key,
        )

    def get_explicit(
        self,
        *,
        user_id: str,
        project_type: str | None,
        project_domain: str | None,
        preference_key: str,
    ) -> PreferenceRow | None:
        return resolver.get_explicit(
            user_id=user_id,
            project_type=project_type,
            project_domain=project_domain,
            preference_key=preference_key,
        )

    def set_preference(
        self,
        *,
        user_id: str,
        project_type: str | None,
        project_domain: str | None,
        preference_key: str,
        value: Any,
        set_by: str = "user",
        reason: str | None = None,
        bypass_hard_check: bool = False,
    ) -> dict[str, Any]:
        """Persist one preference or create a hard-change request."""
        meta = catalog.get_preference_key_metadata(preference_key)
        if meta is not None and meta.is_hard_change and not bypass_hard_check:
            request = learning.request_hard_change(
                user_id=user_id,
                project_type=project_type,
                project_domain=project_domain,
                preference_key=preference_key,
                proposed_value=value,
                source_card_id=None,
                rationale=reason,
            )
            self._emit(
                "aeis.advisor.preferences.hard_change_requested",
                {
                    "request_id": request.request_id,
                    "user_id": user_id,
                    "preference_key": preference_key,
                },
            )
            return {
                "success": True,
                "requires_hard_confirmation": True,
                "hard_change_request_id": request.request_id,
                "error_message": "",
            }

        with self._lock:
            previous = _db.get_preference_row(user_id, project_type, project_domain, preference_key)
            was_new, old_value = _db.upsert_preference(
                user_id,
                project_type,
                project_domain,
                preference_key,
                value,
                set_by,
            )
            audit.log_change(
                user_id=user_id,
                project_type=project_type,
                project_domain=project_domain,
                preference_key=preference_key,
                old_value=None if was_new else old_value,
                new_value=value,
                change_type="INSERT" if was_new else "UPDATE",
                changed_by=set_by,
                reason=reason,
            )
            self._emit(
                "aeis.advisor.preferences.created" if previous is None
                else "aeis.advisor.preferences.updated",
                {
                    "user_id": user_id,
                    "project_type": project_type or "",
                    "project_domain": project_domain or "",
                    "preference_key": preference_key,
                },
            )
        return {
            "success": True,
            "requires_hard_confirmation": False,
            "hard_change_request_id": "",
            "error_message": "",
        }

    def reset_preference(
        self,
        *,
        user_id: str,
        project_type: str | None,
        project_domain: str | None,
        preference_key: str,
        reason: str | None = None,
    ) -> bool:
        """Delete one explicit level and let cascade fallback apply."""
        with self._lock:
            deleted = _db.delete_preference(user_id, project_type, project_domain, preference_key)
            if deleted is None:
                return False
            audit.log_change(
                user_id=user_id,
                project_type=project_type,
                project_domain=project_domain,
                preference_key=preference_key,
                old_value=deleted.get("preference_value"),
                new_value=None,
                change_type="RESET",
                changed_by="user",
                reason=reason,
            )
        self._emit(
            "aeis.advisor.preferences.reset",
            {
                "user_id": user_id,
                "project_type": project_type or "",
                "project_domain": project_domain or "",
                "preference_key": preference_key,
            },
        )
        return True

    def disable_preference(self, *, user_id: str, preference_key: str, reason: str | None = None) -> int:
        """Delete all explicit rows for one key."""
        with self._lock:
            deleted_rows = _db.clear_preference_key_for_user(user_id, preference_key)
            for row in deleted_rows:
                audit.log_change(
                    user_id=user_id,
                    project_type=row.get("project_type"),  # type: ignore[arg-type]
                    project_domain=row.get("project_domain"),  # type: ignore[arg-type]
                    preference_key=preference_key,
                    old_value=row.get("preference_value"),
                    new_value=None,
                    change_type="DELETE",
                    changed_by="user",
                    reason=reason,
                )
        self._emit(
            "aeis.advisor.preferences.disabled",
            {
                "user_id": user_id,
                "preference_key": preference_key,
                "levels_cleared": len(deleted_rows),
            },
        )
        return len(deleted_rows)

    def list_preferences(
        self,
        *,
        user_id: str,
        project_type: str | None = None,
        project_domain: str | None = None,
        preference_key: str | None = None,
    ) -> list[PreferenceRow]:
        """Return all explicit rows matching the filters.

        F-018b: when the advisor PG pool is offline (SQLite-only deploy),
        return an empty result instead of raising — this keeps the dashboard
        connection-monitor green and prevents the 30 s flicker observed when
        ``PoolTimeout`` propagated up through ``GET /api/v1/advisor/preferences``.
        """
        try:
            rows = _db.list_preferences(
                user_id,
                project_type=project_type,
                project_domain=project_domain,
                preference_key=preference_key,
            )
        except Exception as exc:  # noqa: BLE001 - any DB error -> graceful empty
            # Cache PG-unreachable so subsequent polls don't pay 2s timeout each.
            try:
                from sylion.aeis.advisor._db import mark_pg_unreachable
                mark_pg_unreachable()
            except Exception:
                pass
            import logging
            logging.getLogger("sylion.aeis.advisor.preferences").info(
                "list_preferences degraded to empty (PG unreachable?): %s",
                type(exc).__name__,
            )
            return []
        return [
            PreferenceRow(
                user_id=str(row["user_id"]),
                project_type=row.get("project_type"),  # type: ignore[arg-type]
                project_domain=row.get("project_domain"),  # type: ignore[arg-type]
                preference_key=str(row["preference_key"]),
                preference_value=row.get("preference_value"),
                set_by=str(row["set_by"]),
                created_at=row["created_at"],  # type: ignore[arg-type]
                updated_at=row["updated_at"],  # type: ignore[arg-type]
            )
            for row in rows
        ]

    def get_audit(
        self,
        *,
        user_id: str,
        since: datetime | None = None,
        limit: int = 100,
        preference_key: str | None = None,
    ):
        return audit.get_history(
            user_id,
            since=since,
            limit=limit,
            filter_preference_key=preference_key,
        )

    def soft_learning_tick(self, *, user_id: str) -> dict[str, Any]:
        """Apply eligible soft learning based on current history signals."""
        applied_keys: list[str] = []
        try:
            from sylion.aeis.advisor.history.service import get_history_service

            history = get_history_service()
            signals = history.list_learning_signals(user_id, only_unapplied=True)
        except Exception:
            signals = []
        for signal in signals:
            if getattr(signal, "hard_change_status", "") == "pending":
                continue
            key = getattr(signal, "preference_key", "") or ""
            if not key:
                continue
            learning.apply_soft_learning(
                user_id=user_id,
                preference_key=key,
                value=_signal_value(signal),
                project_type=getattr(signal, "context_project_type", None),
                project_domain=getattr(signal, "context_project_domain", None),
            )
            applied_keys.append(key)
        return {
            "applied_count": len(applied_keys),
            "pending_hard_confirmations": learning.count_pending_for_user(user_id),
            "applied_preference_keys": applied_keys,
        }

    def request_hard_change(
        self,
        *,
        user_id: str,
        project_type: str | None,
        project_domain: str | None,
        preference_key: str,
        proposed_value: Any,
        source_card_id: str | None,
        rationale: str | None,
    ):
        request = learning.request_hard_change(
            user_id=user_id,
            project_type=project_type,
            project_domain=project_domain,
            preference_key=preference_key,
            proposed_value=proposed_value,
            source_card_id=source_card_id,
            rationale=rationale,
        )
        self._emit(
            "aeis.advisor.preferences.hard_change_requested",
            {
                "request_id": request.request_id,
                "user_id": user_id,
                "preference_key": preference_key,
                "source_card_id": source_card_id or "",
            },
        )
        return request

    def confirm_hard_change(
        self,
        *,
        request_id: str,
        operator_signature: str,
        confirmed: bool,
    ) -> tuple[bool, Any, str | None]:
        ok, request, error = learning.confirm_hard_change(
            request_id=request_id,
            operator_signature=operator_signature,
            confirmed=confirmed,
        )
        if not ok or request is None:
            return False, None, error
        if confirmed:
            self.set_preference(
                user_id=request.user_id,
                project_type=request.project_type,
                project_domain=request.project_domain,
                preference_key=request.preference_key,
                value=request.proposed_value,
                set_by="user",
                reason=f"hard_change_confirmed:{request.request_id}",
                bypass_hard_check=True,
            )
            self._emit(
                "aeis.advisor.preferences.hard_change_confirmed",
                {
                    "request_id": request.request_id,
                    "user_id": request.user_id,
                    "preference_key": request.preference_key,
                },
            )
        return True, request, None

    def get_catalog(self, catalog_type: str, include_custom: bool = True) -> list[CatalogEntry]:
        """Return one catalog."""
        return catalog.list_catalog(catalog_type, include_custom=include_custom)

    def add_custom_catalog_entry(
        self,
        *,
        catalog_type: str,
        entry_id: str,
        display_name: str,
        description: str,
        created_by: str,
    ) -> CatalogEntry | None:
        entry = catalog.add_custom_entry(
            catalog_type=catalog_type,
            entry_id=entry_id,
            display_name=display_name,
            description=description,
            created_by=created_by,
        )
        if entry is not None:
            self._emit(
                "aeis.advisor.preferences.catalog_extended",
                {
                    "catalog_type": catalog_type,
                    "entry_id": entry_id,
                    "created_by": created_by,
                },
            )
        return entry

    def get_blocked_providers(
        self,
        *,
        user_id: str = "00000000-0000-0000-0000-000000000000",
        project_type: str | None = None,
        project_domain: str | None = None,
    ) -> list[str]:
        """Convenience helper used by pricing."""
        resolved = self.get_effective(
            user_id=user_id,
            project_type=project_type,
            project_domain=project_domain,
            preference_key="blocked_providers",
        )
        value = resolved.value
        return [str(item) for item in value] if isinstance(value, list) else []

    def _emit(self, topic: str, payload: dict[str, Any]) -> None:
        try:
            self._event_bus.publish(
                SylionEvent(
                    event_id=str(uuid.uuid4()),
                    topic=topic,
                    payload=payload,
                    source_module="sylion.aeis.advisor.preferences",
                    timestamp=time.time(),
                    idempotency_key=f"{topic}:{payload.get('user_id', '')}:{payload.get('preference_key', '')}",
                )
            )
        except Exception:
            pass


def _signal_value(signal: Any) -> Any:
    value = getattr(signal, "proposed_value", None)
    if value is not None:
        return value
    signal_type = getattr(signal, "signal_type", "")
    if signal_type == "card_rejection":
        return "high"
    if signal_type == "card_acceptance":
        return "low"
    return getattr(signal, "signal_strength", None)


_service: PreferencesService | None = None
_lock = threading.Lock()


def get_preferences_service() -> PreferencesService:
    """Return the singleton preferences service."""
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                _service = PreferencesService()
    return _service


def get_preferences() -> PreferencesService:
    """Compatibility alias used by other advisor modules."""
    return get_preferences_service()


def reset_preferences_service() -> None:
    """Reset singleton state for tests."""
    global _service
    with _lock:
        _service = None
    learning.reset_pending_requests()
