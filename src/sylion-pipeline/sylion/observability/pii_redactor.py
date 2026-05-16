"""
SYLION Observability -- PII redactor.

Scrubs personally identifiable information from structured log records before
they leave the process for an external backend (Loki, Elasticsearch).

Phase 3 W3.4: applied inside LogAggregator.log() so every emit path benefits
without per-callsite changes. The redactor is conservative -- it prefers
false positives (over-redaction) over leaks.

Coverage:
  - email addresses (RFC 5322 simplified)
  - phone numbers (E.164-ish + Polish 9-digit)
  - Polish PESEL (11 digits) and NIP (10 digits, with optional dashes)
  - credit card primary account numbers (13-19 digits, Luhn-validated to
    avoid scrubbing every long random string)
  - bearer tokens / API keys / Basic auth headers
  - IPv4 addresses (dotted-quad)
  - well-known sensitive field names: ``password``, ``passwd``, ``secret``,
    ``api_key``, ``apikey``, ``token``, ``authorization``, ``cookie``,
    ``session``, ``csrf``, ``otp``, ``mfa``, ``ssn``, ``credit_card``,
    ``card_number``, ``cvv``, ``cvc``, ``pin``

Usage::

    from sylion.observability.pii_redactor import redact_record
    safe = redact_record({"message": "user x@y.pl logged in", "extra": {...}})
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Field-name patterns scrubbed unconditionally regardless of value.
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset({
    "password", "passwd", "pwd",
    "secret", "secrets",
    "api_key", "apikey", "api-key",
    "token", "access_token", "refresh_token", "id_token",
    "authorization", "auth", "bearer",
    "cookie", "set-cookie",
    "session", "session_id", "sessionid",
    "csrf", "csrf_token", "xsrf_token",
    "otp", "mfa", "totp", "twofactor",
    "ssn",
    "credit_card", "card_number", "cardnumber", "pan",
    "cvv", "cvc", "cvn",
    "pin",
    "private_key", "privatekey",
    "client_secret", "client-secret",
})

# Anything containing one of these substrings is treated as sensitive.
SENSITIVE_FIELD_SUBSTRINGS: tuple[str, ...] = (
    "password", "secret", "token", "api_key", "apikey",
    "authorization", "private_key", "client_secret",
)

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
)

# E.164 (+CC + up to 14 digits) and Polish bare 9-digit format.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}(?!\d)",
)

_PESEL_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")
_NIP_RE = re.compile(r"(?<!\d)\d{3}-?\d{3}-?\d{2}-?\d{2}(?!\d)")
_IPV4_RE = re.compile(
    r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?!\d)",
)

# Bearer / Basic / generic Authorization headers embedded in messages.
_AUTH_HEADER_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*)(?:bearer|basic|token)\s+\S+",
)
_GENERIC_TOKEN_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|bearer)\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{16,}[\"']?",
)

# Credit card: 13-19 digit groups separated by spaces or dashes.
_CC_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _luhn_valid(number: str) -> bool:
    """Mod-10 check; reject patently random long digit strings."""
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _redact_credit_cards(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        candidate = match.group(0)
        return REDACTED if _luhn_valid(candidate) else candidate
    return _CC_RE.sub(_replace, text)


def redact_text(value: str) -> str:
    """Apply every regex pattern to a string. Order matters: header > token >
    email > cc > phone/ids/ip."""
    if not value:
        return value
    redacted = _AUTH_HEADER_RE.sub(r"\1" + REDACTED, value)
    redacted = _GENERIC_TOKEN_RE.sub(REDACTED, redacted)
    redacted = _EMAIL_RE.sub(REDACTED, redacted)
    redacted = _redact_credit_cards(redacted)
    redacted = _NIP_RE.sub(REDACTED, redacted)
    redacted = _PESEL_RE.sub(REDACTED, redacted)
    redacted = _IPV4_RE.sub(REDACTED, redacted)
    redacted = _PHONE_RE.sub(REDACTED, redacted)
    return redacted


def _is_sensitive_field(key: str) -> bool:
    lowered = key.lower().strip()
    if lowered in SENSITIVE_FIELD_NAMES:
        return True
    return any(token in lowered for token in SENSITIVE_FIELD_SUBSTRINGS)


def _redact_value(key: str, value: Any) -> Any:
    if _is_sensitive_field(key):
        if value is None or value == "":
            return value
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return redact_record(value)
    if isinstance(value, (list, tuple, set)):
        redacted_items = [_redact_value(key, item) for item in value]
        if isinstance(value, tuple):
            return tuple(redacted_items)
        if isinstance(value, set):
            return set(redacted_items)
        return redacted_items
    return value


def redact_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict with sensitive fields/values scrubbed.

    Does not mutate the input. Recursively descends into nested dicts and
    sequences. Non-string scalars (int/float/bool) pass through unchanged
    unless their key is sensitive.
    """
    if not isinstance(record, dict):
        return record
    redacted: dict[str, Any] = {}
    for key, value in record.items():
        redacted[key] = _redact_value(str(key), value)
    return redacted
