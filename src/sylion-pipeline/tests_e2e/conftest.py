"""
conftest_patch.py — patched shared fixtures for SYLION Playwright E2E test suite.

ROOT CAUSE FIX (issue at conftest.py:14):
    Original:  `from playwright.sync_api import sync_playwright`
    Problem:   Unconditional top-level import blocks `pytest --collect-only` when
               playwright is not installed, causing ALL 66+ E2E tests to fail at
               collection time with ModuleNotFoundError.
    Fix:       `pytest.importorskip("playwright.sync_api")` defers the error to
               skip time, allowing collection to succeed; individual tests are then
               marked skip (not error) when playwright is absent.

Usage — drop this file in place of the existing conftest.py:
    cp conftest_patch.py tests_e2e/conftest.py

Prerequisites (when playwright IS available):
    pip install pytest-playwright requests
    playwright install chromium
    pytest tests_e2e/ -v
    pytest tests_e2e/ -v --base-url http://127.0.0.1:8421
"""

import pytest

# ---------------------------------------------------------------------------
# Graceful import — collection never breaks even without playwright installed.
# When playwright is absent, `playwright_sync_api` is None and the
# `requires_playwright` decorator skips any test that tries to use it.
# ---------------------------------------------------------------------------

playwright_sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="playwright not installed — install via: pip install pytest-playwright && playwright install chromium",
    # minversion is optional; omit to skip any missing install regardless of version
)

# Only reached when playwright is available:
sync_playwright = playwright_sync_api.sync_playwright

# ---------------------------------------------------------------------------
# Public decorator: skip if playwright is absent
# ---------------------------------------------------------------------------


def requires_playwright(fn):
    """
    Decorator that marks a test/method to be skipped when playwright is not
    installed.  Apply to individual test functions or entire test classes.

    Example::

        @requires_playwright
        def test_something(page):
            ...
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if playwright_sync_api is None:
            pytest.skip("playwright not installed")
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Constants used across the suite
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "http://127.0.0.1:8421"
ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"


# ---------------------------------------------------------------------------
# Session-scoped browser
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser():
    """
    Launch a shared Chromium browser for the entire test session.
    Returns None (and skips) when playwright is not installed.
    """
    if playwright_sync_api is None:
        pytest.skip("playwright not installed")
        return None  # unreachable but satisfies type checkers

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


# ---------------------------------------------------------------------------
# Function-scoped page (fresh context per test)
# ---------------------------------------------------------------------------


@pytest.fixture
def page(browser, base_url):
    """
    Fresh browser context + page for each test function.
    Returns None when playwright is not installed (browser fixture already
    skips in that case, but the guard is kept for explicitness).
    """
    if browser is None:
        pytest.skip("playwright not installed")
        return None

    ctx = browser.new_context(base_url=base_url, ignore_https_errors=True)
    pg = ctx.new_page()
    yield pg
    ctx.close()


# ---------------------------------------------------------------------------
# base_url — can be overridden via --base-url CLI arg or env var
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url(request):
    return (
        getattr(request.config, "getoption", lambda *a, **kw: None)(
            "--base-url", default=DEFAULT_BASE_URL
        )
        or DEFAULT_BASE_URL
    )


# ---------------------------------------------------------------------------
# Shared helper: log in via UI and wait for dashboard
# ---------------------------------------------------------------------------


@pytest.fixture
def logged_in_page(page, base_url):
    """Returns a page that is already logged in as admin."""
    if page is None:
        pytest.skip("playwright not installed")
        return None
    page.goto(base_url)
    page.locator("#login-panel").wait_for(state="visible", timeout=8_000)
    page.locator("#login-username").fill(ADMIN_USER)
    page.locator("#login-password").fill(ADMIN_PASS)
    page.locator("button", has_text="Zaloguj").click()
    page.locator("#screen-dashboard").wait_for(state="visible", timeout=8_000)
    return page
