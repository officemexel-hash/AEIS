"""ID-related validators."""
from __future__ import annotations

import re

_HEX_RE = re.compile(r"^[a-f0-9]+$")


def require_prefix(value: str, prefix: str, field_name: str) -> None:
    """Require that an ID starts with the canonical prefix."""
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ValueError(
            f"{field_name} must start with '{prefix}', got: {value!r}"
        )


def require_uuid_hex(value: str, field_name: str, min_len: int = 12) -> None:
    """Require that the ID's hex tail is a valid lowercase hex string."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string, got {type(value).__name__}")
    # ID may have prefix like "tc_<hex>" — strip up to the last underscore
    hex_part = value.rsplit("_", 1)[-1]
    if len(hex_part) < min_len:
        raise ValueError(
            f"{field_name} hex tail must be at least {min_len} chars, "
            f"got {len(hex_part)}"
        )
    if not _HEX_RE.match(hex_part):
        raise ValueError(
            f"{field_name} hex tail must be lowercase hex, got: {hex_part!r}"
        )
