"""
SYLION Funding Autopilot — Browser Automation (K1.2)

Automates form filling, draft saving, and final submission on external
funding portals (Horizon Europe, NCBR, FENG, generic).

Architecture
------------
  PortalDriver (abstract)  — portal-specific selectors & login flows
  PlaywrightBrowser        — browser lifecycle (launch / context / page)
  FundingFormFiller        — high-level orchestrator (fill → save → submit)

Graceful degradation
--------------------
If Playwright is not installed, the module remains importable and all
real-browser methods raise ``BrowserAutomationError("Playwright not installed")``.
Tests should use ``MockPortalDriver`` to validate orchestration logic.

Hook v1.0 (2026-04-24)
Changes: initial
Owner: K-SURF
TODO for D:
  - Install playwright + pytest-playwright in venv
  - Fill in real CSS selectors for each portal driver
  - Add CAPTCHA-solving or human-in-the-loop fallback
"""

from __future__ import annotations

import abc
import logging
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Protocol

from .governance_bridge import check_approved, submit_submission_ticket

log = logging.getLogger("sylion.funding_autopilot.browser_automation")

# ---------------------------------------------------------------------------
# Playwright availability
# ---------------------------------------------------------------------------

try:
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover
    _PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None  # type: ignore[misc,assignment]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class BrowserAutomationError(Exception):
    """Base exception for browser automation failures."""


class PortalLoginError(BrowserAutomationError):
    """Raised when portal login fails."""


class FieldMappingError(BrowserAutomationError):
    """Raised when a prepared field cannot be mapped to a DOM element."""


class SubmissionError(BrowserAutomationError):
    """Raised when final portal submission fails."""


# ---------------------------------------------------------------------------
# PortalDriver — abstract base
# ---------------------------------------------------------------------------

class PortalDriver(abc.ABC):
    """Portal-specific automation logic.

    Subclasses must implement selectors and login flows for each portal.
    """

    name: str = ""

    @abc.abstractmethod
    def login(self, page: Any, credentials: dict[str, str]) -> None:
        """Log in to the portal. Raises PortalLoginError on failure."""

    @abc.abstractmethod
    def navigate_to_form(self, page: Any, portal_url: str) -> None:
        """Navigate from landing page to the submission form."""

    @abc.abstractmethod
    def field_selector(self, field_name: str) -> str | None:
        """Return a CSS selector for *field_name*, or None if unsupported."""

    @abc.abstractmethod
    def click_save_draft(self, page: Any) -> str:
        """Click the Save-Draft button and return the portal draft reference."""

    @abc.abstractmethod
    def click_submit(self, page: Any) -> str:
        """Click the final Submit button and return the confirmation reference."""

    @abc.abstractmethod
    def handle_post_submit_modal(self, page: Any) -> dict[str, Any]:
        """Capture any post-submit modal / confirmation data."""


# ---------------------------------------------------------------------------
# Concrete portal drivers
# ---------------------------------------------------------------------------

class HorizonEuropeDriver(PortalDriver):
    """Horizon Europe Funding & Tenders Portal (EC)."""

    name = "horizon_europe"

    def login(self, page: Any, credentials: dict[str, str]) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        # TODO: implement real ECAS login flow
        raise BrowserAutomationError("Horizon Europe login not yet implemented")

    def navigate_to_form(self, page: Any, portal_url: str) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        page.goto(portal_url)
        # TODO: wait for form frame, handle SPA navigation

    def field_selector(self, field_name: str) -> str | None:
        mapping = {
            "company_name": "input[name='coordinatorOrganizationName']",
            "project_title": "input[name='projectTitle']",
            "project_summary": "textarea[name='abstract']",
            "budget_total": "input[name='totalBudget']",
            "grant_requested": "input[name='requestedGrant']",
        }
        return mapping.get(field_name)

    def click_save_draft(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        # TODO: real selector + reference capture
        raise BrowserAutomationError("Horizon Europe save draft not yet implemented")

    def click_submit(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        raise BrowserAutomationError("Horizon Europe submit not yet implemented")

    def handle_post_submit_modal(self, page: Any) -> dict[str, Any]:
        return {}


class NCBRDriver(PortalDriver):
    """NCBR (Narodowe Centrum Badań i Rozwoju) — Polish funding portal."""

    name = "ncbr"

    def login(self, page: Any, credentials: dict[str, str]) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        raise BrowserAutomationError("NCBR login not yet implemented")

    def navigate_to_form(self, page: Any, portal_url: str) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        page.goto(portal_url)

    def field_selector(self, field_name: str) -> str | None:
        mapping = {
            "company_name": "input[id='wnioskodawcaNazwa']",
            "project_title": "input[id='tytulProjektu']",
            "project_summary": "textarea[id='streszczenie']",
            "budget_total": "input[id='budzetCalkowity']",
            "grant_requested": "input[id='dofinansowanie']",
        }
        return mapping.get(field_name)

    def click_save_draft(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        raise BrowserAutomationError("NCBR save draft not yet implemented")

    def click_submit(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        raise BrowserAutomationError("NCBR submit not yet implemented")

    def handle_post_submit_modal(self, page: Any) -> dict[str, Any]:
        return {}


class FENGDriver(PortalDriver):
    """Forschungsnetzwerk Energie / German energy research portal."""

    name = "feng"

    def login(self, page: Any, credentials: dict[str, str]) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        raise BrowserAutomationError("FENG login not yet implemented")

    def navigate_to_form(self, page: Any, portal_url: str) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        page.goto(portal_url)

    def field_selector(self, field_name: str) -> str | None:
        mapping = {
            "company_name": "input[name='organisation_name']",
            "project_title": "input[name='project_titel']",
            "project_summary": "textarea[name='zusammenfassung']",
            "budget_total": "input[name='gesamtbudget']",
            "grant_requested": "input[name='beantragte_foerderung']",
        }
        return mapping.get(field_name)

    def click_save_draft(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        raise BrowserAutomationError("FENG save draft not yet implemented")

    def click_submit(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        raise BrowserAutomationError("FENG submit not yet implemented")

    def handle_post_submit_modal(self, page: Any) -> dict[str, Any]:
        return {}


class GenericPortalDriver(PortalDriver):
    """Fallback driver using heuristics (data-testid, label text, placeholder)."""

    name = "generic"

    def login(self, page: Any, credentials: dict[str, str]) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        # Generic portals may not require login or use basic auth
        username = credentials.get("username")
        password = credentials.get("password")
        if username and password and page:
            # Attempt basic heuristic login
            user_sel = "input[type='text'], input[name='username'], input[name='email'], input[id='username']"
            pass_sel = "input[type='password'], input[name='password'], input[id='password']"
            try:
                page.fill(user_sel, username)
                page.fill(pass_sel, password)
                page.click("button[type='submit'], input[type='submit']")
                page.wait_for_load_state("networkidle")
            except Exception as exc:
                raise PortalLoginError(f"Generic login failed: {exc}") from exc

    def navigate_to_form(self, page: Any, portal_url: str) -> None:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        page.goto(portal_url)
        page.wait_for_load_state("networkidle")

    def field_selector(self, field_name: str) -> str | None:
        # Heuristic selectors — try multiple strategies
        heuristics: dict[str, list[str]] = {
            "company_name": [
                "input[data-testid='company-name']",
                "input[placeholder*='company' i]",
                "input[placeholder*='firm' i]",
                "input[name*='company' i]",
                "input[name*='organisation' i]",
                "input[id*='company' i]",
            ],
            "project_title": [
                "input[data-testid='project-title']",
                "input[placeholder*='title' i]",
                "input[name*='title' i]",
                "input[id*='title' i]",
            ],
            "project_summary": [
                "textarea[data-testid='summary']",
                "textarea[placeholder*='summary' i]",
                "textarea[placeholder*='abstract' i]",
                "textarea[name*='summary' i]",
                "textarea[name*='abstract' i]",
            ],
            "budget_total": [
                "input[data-testid='budget-total']",
                "input[placeholder*='total budget' i]",
                "input[name*='totalBudget' i]",
                "input[name*='budget_total' i]",
            ],
            "grant_requested": [
                "input[data-testid='grant-requested']",
                "input[placeholder*='grant' i]",
                "input[placeholder*='requested' i]",
                "input[name*='grant' i]",
                "input[name*='requested' i]",
            ],
        }
        # Return first strategy as a comma-joined fallback list
        selectors = heuristics.get(field_name)
        return ", ".join(selectors) if selectors else None

    def click_save_draft(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        # Try common draft-save selectors
        selectors = [
            "button:has-text('Save draft')",
            "button:has-text('Zapisz wersję roboczą')",
            "button:has-text('Entwurf speichern')",
            "input[value*='Save draft' i]",
        ]
        for sel in selectors:
            try:
                page.click(sel)
                page.wait_for_timeout(500)
                return f"draft-{uuid.uuid4().hex[:8]}"
            except Exception:
                continue
        raise SubmissionError("Could not find Save draft button")

    def click_submit(self, page: Any) -> str:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        selectors = [
            "button:has-text('Submit')",
            "button:has-text('Złóż wniosek')",
            "button:has-text('Einreichen')",
            "input[value*='Submit' i]",
        ]
        for sel in selectors:
            try:
                page.click(sel)
                page.wait_for_timeout(500)
                return f"ref-{uuid.uuid4().hex[:8]}"
            except Exception:
                continue
        raise SubmissionError("Could not find Submit button")

    def handle_post_submit_modal(self, page: Any) -> dict[str, Any]:
        return {}


# ---------------------------------------------------------------------------
# Driver registry
# ---------------------------------------------------------------------------

_PORTAL_DRIVERS: dict[str, type[PortalDriver]] = {
    "horizon_europe": HorizonEuropeDriver,
    "ncbr": NCBRDriver,
    "feng": FENGDriver,
    "generic": GenericPortalDriver,
}


def get_portal_driver(portal_name: str) -> PortalDriver:
    """Return an instantiated driver for *portal_name*.

    Falls back to ``GenericPortalDriver`` if name is unknown.
    """
    driver_cls = _PORTAL_DRIVERS.get(portal_name, GenericPortalDriver)
    return driver_cls()


def list_portal_drivers() -> list[str]:
    """Return list of registered portal driver names."""
    return list(_PORTAL_DRIVERS.keys())


# ---------------------------------------------------------------------------
# PlaywrightBrowser — low-level browser wrapper
# ---------------------------------------------------------------------------

class PlaywrightBrowser:
    """Context-manager wrapper around a Playwright browser instance.

    If Playwright is unavailable, ``__enter__`` raises ``BrowserAutomationError``.
    """

    def __init__(
        self,
        headless: bool = True,
        screenshot_dir: str | Path | None = None,
        timeout_ms: int = 30_000,
    ):
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.screenshot_dir = Path(screenshot_dir) if screenshot_dir else Path(tempfile.gettempdir()) / "sylion_browser"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._pw = None
        self._browser: Any = None
        self._context: Any = None
        self.page: Any = None

    # -- context manager --

    def __enter__(self) -> PlaywrightBrowser:
        if not _PLAYWRIGHT_AVAILABLE:
            raise BrowserAutomationError("Playwright not installed")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            accept_downloads=True,
        )
        self.page = self._context.new_page()
        self.page.set_default_timeout(self.timeout_ms)
        log.info("Browser launched (headless=%s)", self.headless)
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> None:
        if exc_type is not None:
            self._capture_failure_screenshot()
        self._close_all()

    # -- public --

    def screenshot(self, name: str | None = None) -> Path:
        """Capture a screenshot and return its path."""
        if self.page is None:
            raise BrowserAutomationError("Browser not started")
        filename = f"{name or 'screenshot'}_{uuid.uuid4().hex[:8]}.png"
        path = self.screenshot_dir / filename
        self.page.screenshot(path=str(path), full_page=True)
        log.info("Screenshot saved: %s", path)
        return path

    def pdf(self, name: str | None = None) -> Path:
        """Export current page as PDF and return its path."""
        if self.page is None:
            raise BrowserAutomationError("Browser not started")
        filename = f"{name or 'page'}_{uuid.uuid4().hex[:8]}.pdf"
        path = self.screenshot_dir / filename
        self.page.pdf(path=str(path))
        log.info("PDF saved: %s", path)
        return path

    # -- internals --

    def _capture_failure_screenshot(self) -> None:
        try:
            if self.page:
                self.screenshot(name="failure")
        except Exception as exc:
            log.warning("Failed to capture failure screenshot: %s", exc)

    def _close_all(self) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception as exc:
            log.warning("Context close error: %s", exc)
        try:
            if self._browser:
                self._browser.close()
        except Exception as exc:
            log.warning("Browser close error: %s", exc)
        try:
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            log.warning("Playwright stop error: %s", exc)
        log.info("Browser shut down")


# ---------------------------------------------------------------------------
# FundingFormFiller — high-level orchestrator
# ---------------------------------------------------------------------------

class FundingFormFiller:
    """Orchestrate filling a funding portal form from ``prepared_fields``.

    Usage (real browser):
        filler = FundingFormFiller(portal_name="ncbr")
        with filler.start_browser() as browser:
            result = filler.run(
                portal_url="https://...",
                credentials={"username": "...", "password": "..."},
                prepared_fields={...},
                action="save_draft",   # or "submit"
            )

    Usage (mock / test):
        filler = FundingFormFiller(driver=MockPortalDriver())
        result = filler.run(...)
    """

    def __init__(
        self,
        portal_name: str = "generic",
        driver: PortalDriver | None = None,
        headless: bool = True,
        screenshot_dir: str | Path | None = None,
    ):
        self.driver = driver or get_portal_driver(portal_name)
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self._browser: PlaywrightBrowser | None = None

    def start_browser(self) -> PlaywrightBrowser:
        """Return a PlaywrightBrowser context manager.

        Raises BrowserAutomationError if Playwright is missing.
        """
        self._browser = PlaywrightBrowser(
            headless=self.headless,
            screenshot_dir=self.screenshot_dir,
        )
        return self._browser

    def _final_submit_gate(
        self,
        portal_url: str,
        approval_ticket_id: str = "",
        application_id: str = "",
        session_id: str = "",
        amount: float = 0.0,
    ) -> dict[str, Any]:
        """Return final-submit gate state and create a ticket when needed."""
        if approval_ticket_id:
            return {
                "allowed": check_approved(approval_ticket_id),
                "governance_ticket_id": approval_ticket_id,
                "created": False,
            }

        ticket_id = submit_submission_ticket(
            application_id=application_id or "browser_submission",
            session_id=session_id or f"browser_{uuid.uuid4().hex[:12]}",
            portal=self.driver.name or portal_url,
            amount=amount,
        )
        return {
            "allowed": False,
            "governance_ticket_id": ticket_id,
            "created": True,
        }

    def run(
        self,
        portal_url: str,
        credentials: dict[str, str],
        prepared_fields: dict[str, Any],
        action: str = "save_draft",
        approval_ticket_id: str = "",
        application_id: str = "",
        session_id: str = "",
        amount: float = 0.0,
    ) -> dict[str, Any]:
        """Execute the full form-filling workflow.

        Args:
            portal_url: target portal URL.
            credentials: dict with at least ``username`` and ``password``.
            prepared_fields: mapping from field name to value.
            action: ``save_draft`` or ``submit``.
            approval_ticket_id: approved governance ticket required for submit.
            application_id: grant application id used when creating a gate.
            session_id: funding submission session id used when creating a gate.
            amount: requested grant amount used for gate priority.

        Returns:
            dict with ``success``, ``reference``, ``screenshots``, ``error``.
        """
        if action == "submit":
            gate = self._final_submit_gate(
                portal_url,
                approval_ticket_id=approval_ticket_id,
                application_id=application_id,
                session_id=session_id,
                amount=amount,
            )
            if not gate["allowed"]:
                return {
                    "success": False,
                    "reference": "",
                    "screenshots": [],
                    "error": "Final funding submit requires approved Human Gate ticket.",
                    "blocked": True,
                    "requires_human_gate": True,
                    "governance_ticket_id": gate["governance_ticket_id"],
                    "approval_ticket_id": gate["governance_ticket_id"],
                    "gate_created": gate["created"],
                }

        if not _PLAYWRIGHT_AVAILABLE:
            return {
                "success": False,
                "reference": "",
                "screenshots": [],
                "error": "Playwright not installed — cannot drive real browser",
            }

        if self._browser is None or self._browser.page is None:
            raise BrowserAutomationError("Browser not started. Use ``with filler.start_browser():``")

        page = self._browser.page
        screenshots: list[Path] = []

        try:
            # 1. Login
            self.driver.login(page, credentials)
            screenshots.append(self._browser.screenshot("after_login"))

            # 2. Navigate
            self.driver.navigate_to_form(page, portal_url)
            screenshots.append(self._browser.screenshot("after_navigate"))

            # 3. Fill fields
            for field_name, value in prepared_fields.items():
                selector = self.driver.field_selector(field_name)
                if selector is None:
                    log.warning("No selector for field '%s' on portal '%s'", field_name, self.driver.name)
                    continue
                try:
                    # Generic driver may return comma-joined fallback list
                    page.fill(selector, str(value))
                    log.debug("Filled '%s' with '%s...'", field_name, str(value)[:40])
                except Exception as exc:
                    log.warning("Failed to fill '%s': %s", field_name, exc)
                    raise FieldMappingError(f"Cannot fill field '{field_name}': {exc}") from exc

            screenshots.append(self._browser.screenshot("after_fill"))

            # 4. Action
            if action == "save_draft":
                reference = self.driver.click_save_draft(page)
            elif action == "submit":
                reference = self.driver.click_submit(page)
                modal_data = self.driver.handle_post_submit_modal(page)
            else:
                raise BrowserAutomationError(f"Unknown action: {action}")

            screenshots.append(self._browser.screenshot(f"after_{action}"))

            return {
                "success": True,
                "reference": reference,
                "screenshots": [str(p) for p in screenshots],
                "error": "",
                **({"modal_data": modal_data} if action == "submit" else {}),
            }

        except Exception as exc:
            log.exception("Browser automation failed")
            return {
                "success": False,
                "reference": "",
                "screenshots": [str(p) for p in screenshots],
                "error": f"{type(exc).__name__}: {exc}",
            }


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------

_filler: FundingFormFiller | None = None
_lock = threading.Lock()


def get_browser_automation(portal_name: str = "generic") -> FundingFormFiller:
    """Get or create the global FundingFormFiller singleton."""
    global _filler
    if _filler is None:
        with _lock:
            if _filler is None:
                _filler = FundingFormFiller(portal_name=portal_name)
    return _filler


def reset_browser_automation(portal_name: str = "generic") -> FundingFormFiller:
    """Reset the global singleton (for testing)."""
    global _filler
    with _lock:
        _filler = FundingFormFiller(portal_name=portal_name)
    return _filler
