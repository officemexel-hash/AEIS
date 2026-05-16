"""Regression test for CORS allow_origin_regex.

Fixed 2026-04-28: hardcoded ``allow_origins=[":3000", ":3001"]`` broke
when the Next.js dev server picked port 3002 (or higher) after a restart.
The browser blocked the response because no ``Access-Control-Allow-Origin``
header echoed the actual origin.

The fix: switch to ``allow_origin_regex`` matching any
``http://(localhost|127.0.0.1):<port>`` so dev iteration on changing
ports doesn't require backend restart.
"""
from __future__ import annotations

import re

import pytest


# ---------------------------------------------------------------------------
# Static regex shape — fail-fast when somebody narrows it back down.
# ---------------------------------------------------------------------------


def _read_cors_regex() -> str:
    """Pull the regex string out of ``app.py`` without importing the app
    (which spins up DB pools and FastAPI side-effects we don't need here).
    """
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "sylion" / "api" / "app.py"
    ).read_text(encoding="utf-8")
    m = re.search(r'allow_origin_regex=r"([^"]+)"', src)
    assert m, "allow_origin_regex literal not found in api/app.py"
    return m.group(1)


def test_cors_regex_accepts_localhost_3000() -> None:
    pattern = re.compile(_read_cors_regex())
    assert pattern.match("http://localhost:3000")


def test_cors_regex_accepts_127_3000() -> None:
    pattern = re.compile(_read_cors_regex())
    assert pattern.match("http://127.0.0.1:3000")


def test_cors_regex_accepts_localhost_3002_regression() -> None:
    """The exact case that broke 2026-04-28."""
    pattern = re.compile(_read_cors_regex())
    assert pattern.match("http://127.0.0.1:3002")
    assert pattern.match("http://localhost:3002")


def test_cors_regex_accepts_arbitrary_high_port() -> None:
    pattern = re.compile(_read_cors_regex())
    assert pattern.match("http://localhost:54321")


def test_cors_regex_rejects_https() -> None:
    """Production prod-https origins must NOT slip through the dev regex."""
    pattern = re.compile(_read_cors_regex())
    assert not pattern.match("https://localhost:3000")


def test_cors_regex_rejects_other_hosts() -> None:
    pattern = re.compile(_read_cors_regex())
    assert not pattern.match("http://example.com:3000")
    assert not pattern.match("http://10.0.0.5:3000")
    assert not pattern.match("http://malicious.localhost.evil:3000")


def test_cors_regex_rejects_no_port() -> None:
    pattern = re.compile(_read_cors_regex())
    assert not pattern.match("http://localhost")
    assert not pattern.match("http://127.0.0.1")


def test_cors_regex_rejects_path_suffix() -> None:
    """Origins MUST NOT carry a path; regex anchored prevents bypass."""
    pattern = re.compile(_read_cors_regex())
    assert not pattern.match("http://localhost:3000/evil")
    assert not pattern.match("http://localhost:3000?x=1")
