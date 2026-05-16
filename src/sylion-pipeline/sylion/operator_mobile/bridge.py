"""
SYLION Operator Mobile -- governance bridge.

Hook v1.0 (2026-04-25).
Changes: initial OperatorMobileBridge implementation for device bindings,
signed push envelopes, and governance queue proxy support.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import threading
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .secrets import sign_payload
from .store import (
    OperatorMobileStore,
    get_operator_mobile_store,
)


@dataclass
class MobilePushPayload:
    ticket_id: str
    title: str
    summary: str
    deeplink: str
    priority: str
    expires_at: datetime
    operator_id: str = ""
    project_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MobileBridge(Protocol):
    def notify_pending_ticket(self, payload: MobilePushPayload) -> None: ...

    def revoke_notification(self, ticket_id: str) -> None: ...

    def list_devices(self, operator_id: str) -> list[dict]: ...

    def bind_device(self, operator_id: str, device_token: str, platform: str) -> None: ...


class StubPushProvider:
    """In-process provider stub used until a real push backend lands."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.revoked: list[dict[str, Any]] = []

    def send(self, envelope: dict[str, Any], devices: list[dict[str, Any]]) -> None:
        self.sent.append({"envelope": envelope, "devices": devices})

    def revoke(self, ticket_id: str, devices: list[dict[str, Any]]) -> None:
        self.revoked.append({"ticket_id": ticket_id, "devices": devices})


class OperatorMobileBridge:
    """Bridge from unified governance tickets into mobile device notifications."""

    def __init__(
        self,
        store: OperatorMobileStore | None = None,
        signing_secret: str = "operator-mobile-dev-secret",
        push_provider: StubPushProvider | None = None,
        deeplink_base: str = "/operator-mobile/queue",
    ) -> None:
        self._store = store or get_operator_mobile_store()
        self._signing_secret = signing_secret
        self._push_provider = push_provider or StubPushProvider()
        self._deeplink_base = deeplink_base.rstrip("/")
        self._lock = threading.RLock()
        self._notifications: dict[str, dict[str, Any]] = {}

    @property
    def push_provider(self) -> StubPushProvider:
        return self._push_provider

    def bind_device(
        self,
        operator_id: str,
        device_token: str,
        platform: str,
        device_label: str = "",
    ) -> None:
        self._store.bind_device(
            operator_id=operator_id,
            device_token=device_token,
            platform=platform,
            device_label=device_label,
        )

    def list_devices(self, operator_id: str) -> list[dict]:
        return self._store.list_devices(operator_id)

    def unbind_device(self, device_id: str, operator_id: str | None = None) -> bool:
        return self._store.unbind_device(device_id, operator_id=operator_id)

    def notify_pending_ticket(self, payload: MobilePushPayload) -> None:
        devices = self.list_devices(payload.operator_id) if payload.operator_id else []
        payload_dict = self._payload_dict(payload)
        signature = sign_payload(self._signing_secret, payload_dict)
        envelope = {
            "payload": payload_dict,
            "signature": signature,
        }
        self._push_provider.send(envelope, devices)
        with self._lock:
            self._notifications[payload.ticket_id] = {
                "ticket_id": payload.ticket_id,
                "operator_id": payload.operator_id,
                "devices": [device.get("device_token", "") for device in devices],
                "signature": signature,
                "payload": payload_dict,
                "revoked": False,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }

    def revoke_notification(self, ticket_id: str) -> None:
        with self._lock:
            state = self._notifications.get(ticket_id)
            device_tokens = state.get("devices", []) if state else []
            devices = [{"device_token": token} for token in device_tokens]
            if state is not None:
                state["revoked"] = True
        self._push_provider.revoke(ticket_id, devices)

    def get_notification_state(self, ticket_id: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._notifications.get(ticket_id)
            return dict(state) if state else None

    def build_payload_from_ticket(
        self,
        ticket: Any,
        operator_id: str,
    ) -> MobilePushPayload:
        summary = str(getattr(ticket, "summary", "") or getattr(ticket, "title", ""))[:200]
        priority = str(getattr(ticket, "priority", "P2") or "P2")
        ticket_id = str(getattr(ticket, "ticket_id", ""))
        project_id = getattr(ticket, "project_id", None)
        created = float(getattr(ticket, "created_at", 0.0) or 0.0)
        expires = getattr(ticket, "sla_deadline", 0.0) or created + 3600
        metadata = getattr(ticket, "payload", {}) or {}
        return MobilePushPayload(
            ticket_id=ticket_id,
            title=str(getattr(ticket, "title", "") or ticket_id),
            summary=summary,
            deeplink=f"{self._deeplink_base}/{ticket_id}",
            priority=priority,
            expires_at=datetime.fromtimestamp(float(expires), tz=timezone.utc),
            operator_id=operator_id,
            project_id=project_id,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    @staticmethod
    def _payload_dict(payload: MobilePushPayload) -> dict[str, Any]:
        out = asdict(payload)
        out["expires_at"] = payload.expires_at.astimezone(timezone.utc).isoformat()
        return out


_bridge: OperatorMobileBridge | None = None
_bridge_lock = threading.Lock()


def get_operator_mobile_bridge(
    db_path: str | Path | None = None,
    signing_secret: str = "operator-mobile-dev-secret",
) -> OperatorMobileBridge:
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            store = get_operator_mobile_store(db_path=db_path)
            _bridge = OperatorMobileBridge(
                store=store,
                signing_secret=signing_secret,
            )
        return _bridge


def reset_operator_mobile_bridge(
    db_path: str | Path | None = None,
    signing_secret: str = "operator-mobile-dev-secret",
) -> OperatorMobileBridge:
    global _bridge
    with _bridge_lock:
        store = get_operator_mobile_store(db_path=db_path)
        _bridge = OperatorMobileBridge(
            store=store,
            signing_secret=signing_secret,
        )
        return _bridge
