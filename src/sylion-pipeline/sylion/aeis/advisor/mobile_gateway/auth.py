"""JWT decode stub + biometric step-up scaffold for the mobile gateway.

Etap 1 stub. The Etap 2 mobile app will issue device-bound JWTs via the
existing ``sylion.security.auth`` flow; until then this module performs a
non-verifying JWT decode (signature verification deferred). The biometric
step-up gate inspects the ``X-Biometric-Verified`` header and is enforced
for D3+ card actions in ``api.py``.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("sylion.aeis.advisor.mobile_gateway.auth")


# TODO(Etap 2): swap stub decode for sylion.security.auth signature verification.
class AuthError(Exception):
    """Raised when authentication fails — surfaced as HTTP 401."""


@dataclass(frozen=True)
class MobilePrincipal:
    """Authenticated principal extracted from a mobile request."""

    operator_id: str
    device_id: str
    biometric_verified: bool = False
    raw_token: str = ""


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_token_unverified(token: str) -> dict:
    """Decode a JWT payload without signature verification (Etap 1 stub)."""
    if not token:
        raise AuthError("missing bearer token")
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed token")
    try:
        body = _b64url_decode(parts[1])
        claims = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise AuthError(f"invalid token payload: {exc}") from exc
    if not isinstance(claims, dict):
        raise AuthError("token payload must be an object")
    return claims


def extract_bearer(authorization_header: Optional[str]) -> str:
    if not authorization_header:
        raise AuthError("missing Authorization header")
    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("expected 'Bearer <token>' Authorization header")
    return parts[1]


def authenticate(
    authorization_header: Optional[str],
    biometric_header: Optional[str] = None,
) -> MobilePrincipal:
    """Decode JWT, return MobilePrincipal. Raises AuthError on failure."""
    token = extract_bearer(authorization_header)
    claims = decode_token_unverified(token)
    operator_id = str(claims.get("sub") or claims.get("operator_id") or "").strip()
    if not operator_id:
        raise AuthError("token missing operator subject")
    device_id = str(claims.get("device_id") or claims.get("did") or "").strip()
    if not device_id:
        raise AuthError("token missing device_id")
    return MobilePrincipal(
        operator_id=operator_id,
        device_id=device_id,
        biometric_verified=_parse_truthy(biometric_header),
        raw_token=token,
    )


def biometric_required_for_d_level(d_level: str) -> bool:
    """Return True if the D-level demands a biometric step-up."""
    if not d_level:
        return False
    normalized = d_level.strip().upper()
    if not normalized.startswith("D"):
        return False
    try:
        ordinal = int(normalized[1:])
    except ValueError:
        return False
    return ordinal >= 3


def _parse_truthy(raw: Optional[str]) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}
