"""Audit subscriber for aeis.advisor.* events."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

from sylion.aeis.advisor._db import get_pool
from sylion.aeis.advisor.events.proto_registry import ProtoRegistry
from sylion.core.event_backbone import EventBackbone, get_event_backbone
from sylion.core.event_bus import SylionEvent

log = logging.getLogger("sylion.aeis.advisor.events.audit_subscriber")


class AdvisorAuditSubscriber:
    """Persist aeis.advisor.* events into advisor_events audit tables."""

    def __init__(
        self,
        event_backbone: EventBackbone | None = None,
        proto_registry: ProtoRegistry | None = None,
    ) -> None:
        self._event_backbone = event_backbone or get_event_backbone()
        self._proto_registry = proto_registry or ProtoRegistry()
        self._started = False
        self.start()

    def start(self) -> None:
        """Subscribe once to the live event backbone."""
        if self._started:
            return
        self._event_backbone.subscribe("*", self._on_event)
        self._started = True

    def _on_event(self, event: SylionEvent) -> None:
        if not event.topic.startswith("aeis.advisor."):
            return

        is_valid, errors = self._proto_registry.validate(event.topic, event.payload)
        if not is_valid:
            self._record_validation_failure(event, errors)
            return

        self._persist_event(event)

    def _persist_event(self, event: SylionEvent) -> None:
        if _use_audit_chain_store():
            _append_advisor_event_chain(
                "advisor_event.persisted",
                {
                    "event_id": event.event_id,
                    "event_type": event.topic,
                    "payload": event.payload,
                    "producer_module": event.source_module or "unknown",
                    "timestamp": event.timestamp,
                },
            )
            return

        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO advisor_events.events (
                    event_id,
                    event_type,
                    payload_jsonb,
                    produced_at,
                    producer_module
                ) VALUES (%s, %s, %s, to_timestamp(%s), %s)
                ON CONFLICT (event_id) DO NOTHING
                """,
                (
                    event.event_id,
                    event.topic,
                    json.dumps(event.payload),
                    event.timestamp,
                    event.source_module or "unknown",
                ),
            )

    def _record_validation_failure(self, event: SylionEvent, errors: list[str]) -> None:
        log.warning("advisor event validation failed for %s: %s", event.topic, errors)
        if _use_audit_chain_store():
            _append_advisor_event_chain(
                "advisor_event.validation_failed",
                {
                    "event_id": event.event_id,
                    "event_type": event.topic,
                    "payload": event.payload,
                    "validation_errors": errors,
                    "producer_module": event.source_module or "unknown",
                    "timestamp": event.timestamp,
                },
            )
            return

        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO advisor_events.validation_failures (
                    attempted_event_type,
                    attempted_payload,
                    validation_errors,
                    producer_module
                ) VALUES (%s, %s, %s, %s)
                """,
                (
                    event.topic,
                    json.dumps(event.payload),
                    json.dumps({"errors": errors}),
                    event.source_module or "unknown",
                ),
            )


_subscriber: AdvisorAuditSubscriber | None = None
_subscriber_lock = threading.Lock()


def get_or_create_advisor_audit_subscriber(
    *,
    event_backbone: EventBackbone | None = None,
    proto_registry: ProtoRegistry | None = None,
) -> AdvisorAuditSubscriber:
    """Return the singleton audit subscriber."""
    global _subscriber
    if _subscriber is None:
        with _subscriber_lock:
            if _subscriber is None:
                _subscriber = AdvisorAuditSubscriber(
                    event_backbone=event_backbone,
                    proto_registry=proto_registry,
                )
    return _subscriber


def reset_advisor_audit_subscriber() -> None:
    """Reset singleton state for tests."""
    global _subscriber
    with _subscriber_lock:
        _subscriber = None


def _use_audit_chain_store() -> bool:
    if str(os.environ.get("SYLION_ADVISOR_FORCE_PG", "")).lower() in {"1", "true", "yes"}:
        return False
    try:
        from sylion.aeis_v2.audit_profile import is_audit_mode

        if is_audit_mode():
            return True
    except Exception:
        pass
    db_mode = str(os.environ.get("SYLION_DB_MODE", "sqlite")).strip().lower()
    has_pg_dsn = bool(os.environ.get("SYLION_DB_URL") or os.environ.get("SYLION_PG_DSN"))
    return db_mode != "postgres" or not has_pg_dsn


def _append_advisor_event_chain(action: str, payload: dict[str, Any]) -> None:
    from sylion.aeis_v2.audit_chain import append_to_chain
    from sylion.aeis_v2.audit_profile import resolve_audit_chain_path

    append_to_chain(
        resolve_audit_chain_path("advisor_events.jsonl"),
        {
            "action": action,
            "actor": "advisor.audit_subscriber",
            "module": "sylion.aeis.advisor.events",
            "timestamp": time.time(),
            **payload,
        },
    )
