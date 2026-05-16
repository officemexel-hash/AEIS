"""
SYLION Operator Mobile -- pending ticket dispatcher.

Hook v1.0 (2026-04-25).
Changes: initial poll loop that maps governance pending tickets to mobile pushes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from .bridge import OperatorMobileBridge, get_operator_mobile_bridge

log = logging.getLogger("sylion.operator_mobile.dispatcher")


def _default_fetch_pending(
    operator_id: str | None = None,
    project_id: str | None = None,
    priority: str | None = None,
) -> list[Any]:
    try:
        from sylion.governance.tickets import fetch_pending
    except ImportError:
        return []
    return fetch_pending(
        operator_id=operator_id,
        project_id=project_id,
        priority=priority,
    )


class OperatorMobileDispatcher:
    """Poll governance pending tickets and fan them out to mobile devices."""

    def __init__(
        self,
        bridge: OperatorMobileBridge | None = None,
        governance_fetch_pending: Callable[..., list[Any]] | None = None,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self._bridge = bridge or get_operator_mobile_bridge()
        self._governance_fetch_pending = governance_fetch_pending or _default_fetch_pending
        self._poll_interval_seconds = poll_interval_seconds

    def poll_once(
        self,
        operator_id: str | None = None,
        project_id: str | None = None,
        priority: str | None = None,
    ) -> dict[str, int]:
        tickets = self._governance_fetch_pending(
            operator_id=operator_id,
            project_id=project_id,
            priority=priority,
        )
        dispatched = 0
        skipped = 0

        for ticket in tickets:
            payload = getattr(ticket, "payload", {}) or {}
            operator_ids: list[str] = []
            if operator_id:
                operator_ids = [operator_id]
            elif isinstance(payload.get("operator_ids"), list):
                operator_ids = [
                    str(item).strip()
                    for item in payload["operator_ids"]
                    if str(item).strip()
                ]
            elif payload.get("operator_id"):
                operator_ids = [str(payload.get("operator_id")).strip()]

            if not operator_ids:
                skipped += 1
                continue

            for current_operator_id in operator_ids:
                mobile_payload = self._bridge.build_payload_from_ticket(
                    ticket,
                    current_operator_id,
                )
                self._bridge.notify_pending_ticket(mobile_payload)
                dispatched += 1

        return {
            "tickets": len(tickets),
            "dispatched": dispatched,
            "skipped": skipped,
        }

    def run_forever(
        self,
        stop_event: threading.Event | None = None,
        operator_id: str | None = None,
    ) -> None:
        stop_event = stop_event or threading.Event()
        while not stop_event.is_set():
            try:
                self.poll_once(operator_id=operator_id)
            except Exception:  # pragma: no cover - defensive loop guard
                log.exception("operator mobile dispatcher loop failed")
            stop_event.wait(self._poll_interval_seconds)


_dispatcher: OperatorMobileDispatcher | None = None
_dispatcher_lock = threading.Lock()


def get_operator_mobile_dispatcher() -> OperatorMobileDispatcher:
    global _dispatcher
    with _dispatcher_lock:
        if _dispatcher is None:
            _dispatcher = OperatorMobileDispatcher()
        return _dispatcher


def reset_operator_mobile_dispatcher() -> OperatorMobileDispatcher:
    global _dispatcher
    with _dispatcher_lock:
        _dispatcher = OperatorMobileDispatcher()
        return _dispatcher
