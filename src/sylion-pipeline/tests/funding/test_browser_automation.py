"""
Tests for sylion.funding_autopilot.browser_automation (K1.2).

These tests use ``MockPortalDriver`` to validate orchestration logic and
explicitly simulate Playwright absence for graceful-degradation checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sylion.funding_autopilot.browser_automation as browser_automation
from sylion.funding_autopilot.browser_automation import (
    BrowserAutomationError,
    FieldMappingError,
    FundingFormFiller,
    GenericPortalDriver,
    HorizonEuropeDriver,
    NCBRDriver,
    FENGDriver,
    PortalDriver,
    PlaywrightBrowser,
    _PLAYWRIGHT_AVAILABLE,
    get_browser_automation,
    get_portal_driver,
    list_portal_drivers,
    reset_browser_automation,
)
from sylion.funding_autopilot.governance_bridge import submit_submission_ticket
from sylion.governance.tickets import fetch_by_id, reset_ticket_store, resolve


@pytest.fixture(autouse=True)
def _fresh_governance_tickets():
    reset_ticket_store()
    yield


# ---------------------------------------------------------------------------
# Mock driver for testing orchestration without a real browser
# ---------------------------------------------------------------------------

class MockPortalDriver(PortalDriver):
    """In-memory mock that records all interactions."""

    name = "mock"

    def __init__(self):
        self.calls: list[dict] = []
        self._references = {"save_draft": "mock-draft-123", "submit": "mock-ref-456"}

    def _record(self, method: str, **kwargs):
        self.calls.append({"method": method, **kwargs})

    def login(self, page, credentials):
        self._record("login", credentials=credentials)
        if credentials.get("fail"):
            raise BrowserAutomationError("Mock login failure")

    def navigate_to_form(self, page, portal_url):
        self._record("navigate_to_form", portal_url=portal_url)

    def field_selector(self, field_name):
        self._record("field_selector", field_name=field_name)
        # Support all common fields for testing
        return f"#{field_name}"

    def click_save_draft(self, page):
        self._record("click_save_draft")
        return self._references["save_draft"]

    def click_submit(self, page):
        self._record("click_submit")
        return self._references["submit"]

    def handle_post_submit_modal(self, page):
        self._record("handle_post_submit_modal")
        return {"confirmation_code": "CONF-789"}


class FakePage:
    def __init__(self):
        self.fills: list[tuple[str, str]] = []

    def fill(self, selector: str, value: str):
        self.fills.append((selector, value))


class FakeBrowser:
    def __init__(self):
        self.page = FakePage()

    def screenshot(self, name: str):
        return Path(f"{name}.png")


# ---------------------------------------------------------------------------
# Portal driver registry tests
# ---------------------------------------------------------------------------

class TestPortalRegistry:
    def test_list_drivers(self):
        drivers = list_portal_drivers()
        assert "horizon_europe" in drivers
        assert "ncbr" in drivers
        assert "feng" in drivers
        assert "generic" in drivers

    def test_get_horizon_driver(self):
        d = get_portal_driver("horizon_europe")
        assert isinstance(d, HorizonEuropeDriver)

    def test_get_ncbr_driver(self):
        d = get_portal_driver("ncbr")
        assert isinstance(d, NCBRDriver)

    def test_get_feng_driver(self):
        d = get_portal_driver("feng")
        assert isinstance(d, FENGDriver)

    def test_get_unknown_falls_back_to_generic(self):
        d = get_portal_driver("unknown_portal_xyz")
        assert isinstance(d, GenericPortalDriver)


# ---------------------------------------------------------------------------
# Field selector tests
# ---------------------------------------------------------------------------

class TestFieldSelectors:
    def test_horizon_europe_selectors(self):
        d = HorizonEuropeDriver()
        assert d.field_selector("company_name") is not None
        assert d.field_selector("project_title") is not None
        assert d.field_selector("budget_total") is not None
        assert d.field_selector("nonexistent_field") is None

    def test_ncbr_selectors(self):
        d = NCBRDriver()
        assert d.field_selector("company_name") is not None
        assert d.field_selector("project_summary") is not None

    def test_generic_heuristic_selectors(self):
        d = GenericPortalDriver()
        sel = d.field_selector("company_name")
        assert sel is not None
        assert "data-testid" in sel or "placeholder" in sel


# ---------------------------------------------------------------------------
# Playwright availability & graceful degradation
# ---------------------------------------------------------------------------

class TestPlaywrightAvailability:
    @pytest.fixture(autouse=True)
    def _simulate_missing_playwright(self, monkeypatch):
        monkeypatch.setattr(browser_automation, "_PLAYWRIGHT_AVAILABLE", False)

    def test_playwright_not_installed(self):
        assert browser_automation._PLAYWRIGHT_AVAILABLE is False

    def test_playwright_browser_raises_on_enter(self):
        with pytest.raises(BrowserAutomationError, match="Playwright not installed"):
            with PlaywrightBrowser():
                pass  # pragma: no cover

    def test_real_drivers_raise_without_playwright(self):
        d = HorizonEuropeDriver()
        with pytest.raises(BrowserAutomationError, match="Playwright not installed"):
            d.login(page=None, credentials={})

    def test_funding_form_filler_run_returns_graceful_error(self):
        filler = FundingFormFiller(portal_name="generic")
        result = filler.run(
            portal_url="https://example.com",
            credentials={},
            prepared_fields={"company_name": "Acme"},
            action="save_draft",
        )
        assert result["success"] is False
        assert "Playwright not installed" in result["error"]


# ---------------------------------------------------------------------------
# FundingFormFiller with MockPortalDriver
# ---------------------------------------------------------------------------

class TestFundingFormFillerMock:
    @pytest.fixture
    def mock_driver(self):
        return MockPortalDriver()

    @pytest.fixture
    def filler(self, mock_driver):
        return FundingFormFiller(driver=mock_driver)

    def test_run_save_draft_without_browser(self, filler, mock_driver, monkeypatch):
        """When no browser is started and Playwright is missing, run() returns
        the graceful-degradation dict BEFORE touching the driver."""
        monkeypatch.setattr(browser_automation, "_PLAYWRIGHT_AVAILABLE", False)
        result = filler.run(
            portal_url="https://test.portal",
            credentials={"username": "u", "password": "p"},
            prepared_fields={"company_name": "Acme"},
            action="save_draft",
        )
        assert result["success"] is False
        assert "Playwright not installed" in result["error"]
        # Driver was never invoked because we bail early
        assert len(mock_driver.calls) == 0

    def test_submit_without_approval_creates_human_gate_and_blocks(self, filler, mock_driver):
        result = filler.run(
            portal_url="https://test.portal",
            credentials={"username": "u", "password": "p"},
            prepared_fields={"company_name": "Acme"},
            action="submit",
            application_id="app_browser_1",
            session_id="sess_browser_1",
            amount=250_000,
        )

        assert result["success"] is False
        assert result["blocked"] is True
        assert result["requires_human_gate"] is True
        assert result["gate_created"] is True
        assert len(mock_driver.calls) == 0

        ticket = fetch_by_id(result["governance_ticket_id"])
        assert ticket is not None
        assert ticket.origin == "funding"
        assert ticket.decision_class == "D4"
        assert ticket.state == "pending"

    def test_submit_with_pending_human_gate_blocks(self, filler, mock_driver):
        ticket_id = submit_submission_ticket(
            application_id="app_browser_2",
            session_id="sess_browser_2",
            portal="mock",
            amount=100_000,
        )

        result = filler.run(
            portal_url="https://test.portal",
            credentials={"username": "u", "password": "p"},
            prepared_fields={"company_name": "Acme"},
            action="submit",
            approval_ticket_id=ticket_id,
        )

        assert result["success"] is False
        assert result["blocked"] is True
        assert result["governance_ticket_id"] == ticket_id
        assert result["gate_created"] is False
        assert len(mock_driver.calls) == 0

    def test_submit_with_approved_human_gate_runs_driver(self, filler, mock_driver, monkeypatch):
        ticket_id = submit_submission_ticket(
            application_id="app_browser_3",
            session_id="sess_browser_3",
            portal="mock",
            amount=100_000,
        )
        assert resolve(
            ticket_id,
            "approved",
            reason="operator approved browser automation submit",
            reviewer="operator@example.com",
        ) is True
        monkeypatch.setattr(browser_automation, "_PLAYWRIGHT_AVAILABLE", True)
        filler._browser = FakeBrowser()

        result = filler.run(
            portal_url="https://test.portal",
            credentials={"username": "u", "password": "p"},
            prepared_fields={"company_name": "Acme"},
            action="submit",
            approval_ticket_id=ticket_id,
        )

        methods = [call["method"] for call in mock_driver.calls]
        assert result["success"] is True
        assert result["reference"] == "mock-ref-456"
        assert "click_submit" in methods
        assert "handle_post_submit_modal" in methods

    def test_singleton_get_and_reset(self):
        f1 = get_browser_automation("ncbr")
        f2 = get_browser_automation("ncbr")
        assert f1 is f2
        f3 = reset_browser_automation("feng")
        assert f3 is not f1
        assert f3.driver.name == "feng"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_custom_exceptions(self):
        exc = BrowserAutomationError("test")
        assert str(exc) == "test"
        assert isinstance(FieldMappingError("fm"), BrowserAutomationError)
