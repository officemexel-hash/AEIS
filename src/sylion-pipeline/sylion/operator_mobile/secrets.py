"""
SYLION Operator Mobile -- payload signing helpers.

Hook v1.0 (2026-04-25).
Changes: initial HMAC-SHA256 signing for mobile push envelopes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def canonical_payload(payload: dict[str, Any]) -> str:
    """Serialize payload into a stable JSON string for signatures."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sign_payload(secret: str, payload: dict[str, Any]) -> str:
    raw = canonical_payload(payload)
    return hmac.new(
        secret.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_payload(secret: str, payload: dict[str, Any], signature: str) -> bool:
    expected = sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature)
