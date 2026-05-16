"""Proto registry stub for advisor event validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegistryEntry:
    """Descriptor metadata for one event topic."""

    event_type: str
    proto_message_type: str
    proto_descriptor: bytes = b""
    proto_version: int = 1
    is_internal: bool = True
    is_active: bool = True


class ProtoRegistry:
    """In-memory validator registry until descriptors are fully populated."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}
        self._validators: dict[str, Any] = {}

    def register(
        self,
        *,
        event_type: str,
        proto_message_type: str,
        validator: Any | None = None,
        proto_descriptor: bytes = b"",
        proto_version: int = 1,
        is_internal: bool = True,
    ) -> None:
        """Register a descriptor stub and optional callable validator."""
        self._entries[event_type] = RegistryEntry(
            event_type=event_type,
            proto_message_type=proto_message_type,
            proto_descriptor=proto_descriptor,
            proto_version=proto_version,
            is_internal=is_internal,
        )
        if validator is not None:
            self._validators[event_type] = validator

    def list_entries(self) -> list[RegistryEntry]:
        """Return registered descriptors."""
        return list(self._entries.values())

    def validate(self, event_type: str, payload: dict[str, Any]) -> tuple[bool, list[str]]:
        validator = self._validators.get(event_type)
        if validator is None:
            validator = self._validators.get("*")
        if validator is None:
            if not isinstance(payload, dict):
                return False, ["payload_must_be_object"]
            return True, []
        result = validator(payload)
        if result is True or result is None:
            return True, []
        if result is False:
            return False, ["validator_rejected_payload"]
        if isinstance(result, str):
            return False, [result]
        if isinstance(result, list):
            return len(result) == 0, [str(item) for item in result]
        return True, []
