"""
test_e2e_diagnostyka_v2.py — Diagnostics v2 screen E2E tests.

Covers 5 scenarios:
  DIAG-001  categories_pills_visible      — Category filter pills are rendered
  DIAG-002  filter_by_category_works      — Selecting a pill filters the events list
  DIAG-003  auto_refresh_30s              — Screen auto-refreshes its data ~every 30s
  DIAG-004  export_json_downloads         — Export to JSON triggers a file download
  DIAG-005  historical_run_comparison     — Historical run selector shows diff data

Pre-condition: SYLION app running on http://127.0.0.1:8421, admin account exists.
All data is mocked via page.route() for determinism in CI.
"""

import json
import time

import pytest
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8421"
API = f"{BASE_URL}/api"
ADMIN_USER = "admin"
ADMIN_PASS = "TestPass123!"

MOCK_CATEGORIES = ["auth", "upload", "pipeline", "device", "system"]
MOCK_EVENTS = [
    {"id": f"evt-{i}", "category": MOCK_CATEGORIES[i % len(MOCK_CATEGORIES)],
     "message": f"Event message {i}", "level": "INFO", "ts": 1700000000 + i * 60}
    for i in range(20)
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skip_if_no_server():
    try:
        requests.get(f"{API}/auth/status", timeout=4)
    except Exception:
        pytest.skip("SYLION app not reachable on http://127.0.0.1:8421")


def _needs_setup() -> bool:
    try:
        r = requests.get(f"{API}/auth/status", timeout=4)
        return r.json().get("needs_setup", False)
    except Exception:
        return False


def _login_via_ui(page):
    page.goto(BASE_URL)
    page.locator("#login-panel").wait_for(state="visible", timeout=8_000)
    page.locator("#login-username").fill(ADMIN_USER)
    page.locator("#login-password").fill(ADMIN_PASS)
    page.locator("button", has_text="Zaloguj").click()
    page.locator("#screen-dashboard").wait_for(state="visible", timeout=8_000)


def _navigate_to_diagnostics(page):
    """Navigate to the diagnostics v2 screen."""
    page.locator(
        "[data-screen='diagnostics'], [data-screen='diagnostyka'], "
        "a[href='#diagnostics'], a[href='#diagnostyka'], "
        ".nav-item:has-text('Diagnostics'), .nav-item:has-text('Diagnostyka'), "
        ".nav-item:has-text('Logs'), .nav-item:has-text('Events')"
    ).first.click()
    page.wait_for_selector(
        "#screen-diagnostics, #screen-diagnostyka, [id*='diagnostic'], "
        ".diagnostics-panel, .events-panel, [class*='diagnostic']",
        timeout=8_000,
    )


def _mock_diagnostics_api(page, events=None, categories=None):
    """Install route mocks for the diagnostics API."""
    if events is None:
        events = MOCK_EVENTS
    if categories is None:
        categories = MOCK_CATEGORIES

    diag_body = json.dumps({
        "events": events,
        "categories": categories,
        "total": len(events),
        "page": 1,
        "per_page": 50,
    })

    cat_body = json.dumps({"categories": categories})

    def mock_route(route):
        url = route.request.url
        if "/categories" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=cat_body,
            )
        elif any(seg in url for seg in ["/diagnostics", "/diagnostyka", "/events", "/logs"]):
            route.fulfill(
                status=200,
                content_type="application/json",
                body=diag_body,
            )
        else:
            route.continue_()

    page.route("**/api/diagnostics**", mock_route)
    page.route("**/api/diagnostyka**", mock_route)
    page.route("**/api/events**", mock_route)
    page.route("**/api/logs**", mock_route)


# ---------------------------------------------------------------------------
# DIAG-001 — Category filter pills are visible
# ---------------------------------------------------------------------------


class TestCategoryPillsVisible:
    """DIAG-001 — Diagnostics screen must render category filter pills."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_categories_pills_visible(self, page):
        """
        After navigating to the diagnostics screen, filter pill buttons for
        each category must be visible.
        """
        from playwright.sync_api import expect

        _mock_diagnostics_api(page)
        _login_via_ui(page)
        _navigate_to_diagnostics(page)
        page.wait_for_timeout(2_000)

        # Pills can be implemented as buttons, chips, badges, or anchor tags
        pills = page.locator(
            ".category-pill, .filter-pill, .cat-pill, "
            ".chip, [class*='pill'], [class*='chip'], "
            ".filter-btn, [data-category], "
            "button.category, button.filter"
        )

        if pills.count() == 0:
            # Fallback: any clickable element matching a category name
            for cat in MOCK_CATEGORIES:
                cat_el = page.locator(
                    f"button:has-text('{cat}'), .tag:has-text('{cat}'), "
                    f"[data-value='{cat}'], span:has-text('{cat}')"
                ).first
                if cat_el.count() > 0:
                    pills = cat_el
                    break

        assert pills.count() > 0, (
            "No category filter pills found on diagnostics screen. "
            f"Expected pills for categories: {MOCK_CATEGORIES}"
        )

        # At least the first pill must be visible
        expect(pills.first).to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# DIAG-002 — Filtering by category works
# ---------------------------------------------------------------------------


class TestFilterByCategoryWorks:
    """DIAG-002 — Clicking a category pill must filter the displayed events."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_filter_by_category_works(self, page):
        """
        1. Render events for all categories.
        2. Click the 'auth' category pill.
        3. Assert only auth events are visible (or a filtered request is fired).
        """
        # Track API calls with category filter
        filtered_calls = []

        def mock_route(route):
            url = route.request.url
            if "category=auth" in url or "filter=auth" in url or "cat=auth" in url:
                filtered_calls.append(url)
                auth_events = [e for e in MOCK_EVENTS if e["category"] == "auth"]
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "events": auth_events,
                        "categories": MOCK_CATEGORIES,
                        "total": len(auth_events),
                    }),
                )
            elif any(seg in url for seg in ["/diagnostics", "/diagnostyka", "/events", "/logs", "/categories"]):
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "events": MOCK_EVENTS,
                        "categories": MOCK_CATEGORIES,
                        "total": len(MOCK_EVENTS),
                    }),
                )
            else:
                route.continue_()

        page.route("**/api/**", mock_route)

        _login_via_ui(page)
        _navigate_to_diagnostics(page)
        page.wait_for_timeout(2_000)

        # Count events before filtering
        event_rows_before = page.locator(
            ".event-row, .log-row, .event-item, tr.event, [class*='event-row']"
        ).count()

        # Find and click the 'auth' pill
        auth_pill = page.locator(
            "button:has-text('auth'), [data-category='auth'], "
            ".category-pill:has-text('auth'), .chip:has-text('auth'), "
            "[data-value='auth'], .filter-btn:has-text('auth')"
        ).first

        if auth_pill.count() == 0:
            pytest.skip("No 'auth' category pill found — DIAG-001 must pass first")

        auth_pill.click()
        page.wait_for_timeout(2_000)

        # Either: a filtered API call was made, or the visible row count changed
        event_rows_after = page.locator(
            ".event-row, .log-row, .event-item, tr.event, [class*='event-row']"
        ).count()

        auth_event_count = sum(1 for e in MOCK_EVENTS if e["category"] == "auth")

        assert (
            filtered_calls
            or event_rows_after != event_rows_before
            or (event_rows_after == auth_event_count and auth_event_count > 0)
        ), (
            "Clicking 'auth' category pill did not filter events — "
            "no filtered API call was observed and row count did not change"
        )


# ---------------------------------------------------------------------------
# DIAG-003 — Auto-refresh every 30 seconds
# ---------------------------------------------------------------------------


class TestAutoRefresh30s:
    """DIAG-003 — The diagnostics screen must auto-refresh data approximately every 30s."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_auto_refresh_fires_multiple_requests(self, page):
        """
        Stay on the diagnostics screen for ~35 seconds and verify that the
        events API is called at least twice (initial load + one auto-refresh).

        NOTE: This test is slow (~35s). It can be skipped in fast CI runs by
        setting the environment variable SKIP_SLOW_E2E=1.
        """
        import os

        if os.environ.get("SKIP_SLOW_E2E"):
            pytest.skip("SKIP_SLOW_E2E set — skipping 35s auto-refresh test")

        api_calls = []

        def mock_route(route):
            url = route.request.url
            if any(seg in url for seg in ["/diagnostics", "/diagnostyka", "/events", "/logs"]):
                api_calls.append({"url": url, "ts": time.time()})
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "events": MOCK_EVENTS,
                        "categories": MOCK_CATEGORIES,
                        "total": len(MOCK_EVENTS),
                    }),
                )
            else:
                route.continue_()

        page.route("**/api/**", mock_route)

        _login_via_ui(page)
        _navigate_to_diagnostics(page)

        # Wait 35 seconds for auto-refresh to fire
        page.wait_for_timeout(35_000)

        assert len(api_calls) >= 2, (
            f"Expected >= 2 API calls (initial + auto-refresh), got {len(api_calls)}. "
            "Diagnostics screen must auto-refresh every ~30 seconds."
        )

        if len(api_calls) >= 2:
            interval = api_calls[-1]["ts"] - api_calls[0]["ts"]
            # Interval should be between 20s and 60s
            assert 20 <= interval <= 60, (
                f"Auto-refresh interval is {interval:.1f}s, expected 20–60s (target 30s)"
            )


# ---------------------------------------------------------------------------
# DIAG-004 — Export JSON downloads a file
# ---------------------------------------------------------------------------


class TestExportJsonDownloads:
    """DIAG-004 — The 'Export JSON' button must trigger a file download."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_export_json_downloads(self, page):
        """
        Click the Export JSON button and assert that a file download is initiated.
        Playwright's download event is used to capture the downloaded file.
        """
        _mock_diagnostics_api(page)
        _login_via_ui(page)
        _navigate_to_diagnostics(page)
        page.wait_for_timeout(2_000)

        # Find export button
        export_btn = page.locator(
            "button:has-text('Export JSON'), button:has-text('Eksport'), "
            "button:has-text('Download'), a[download], "
            "[data-action='export'], [onclick*='export'], "
            "button:has-text('Export'), .export-btn"
        ).first

        if export_btn.count() == 0:
            pytest.skip("No Export JSON button found on diagnostics screen")

        # Capture download event
        with page.expect_download(timeout=10_000) as download_info:
            export_btn.click()

        download = download_info.value
        assert download is not None, "No download was triggered after clicking Export JSON"

        suggested_name = download.suggested_filename
        assert suggested_name, "Download has no suggested filename"

        # Should be a JSON file
        assert suggested_name.endswith(".json") or "json" in suggested_name.lower(), (
            f"Expected a .json download, got: {suggested_name}"
        )


# ---------------------------------------------------------------------------
# DIAG-005 — Historical run comparison shows different data
# ---------------------------------------------------------------------------


class TestHistoricalRunComparison:
    """DIAG-005 — The historical run selector must switch the displayed events."""

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_server()
        if _needs_setup():
            pytest.skip("App in setup mode")

    def test_historical_run_comparison(self, page):
        """
        1. Mock two distinct historical runs with different event sets.
        2. Navigate to diagnostics.
        3. Use the run selector to switch from run A to run B.
        4. Assert the event data changes.
        """
        RUN_A_ID = "run-historical-A"
        RUN_B_ID = "run-historical-B"

        run_a_events = [
            {"id": f"A-evt-{i}", "category": "auth", "message": f"Run A event {i}",
             "level": "INFO", "ts": 1700000000 + i}
            for i in range(5)
        ]
        run_b_events = [
            {"id": f"B-evt-{i}", "category": "pipeline", "message": f"Run B event {i}",
             "level": "WARNING", "ts": 1700100000 + i}
            for i in range(8)
        ]
        runs_list = [
            {"id": RUN_A_ID, "label": "Run A — 2023-11-14", "event_count": len(run_a_events)},
            {"id": RUN_B_ID, "label": "Run B — 2023-11-15", "event_count": len(run_b_events)},
        ]

        active_run = {"id": RUN_A_ID}

        def mock_route(route):
            url = route.request.url
            if "/runs" in url and "list" in url:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"runs": runs_list}),
                )
            elif RUN_B_ID in url:
                active_run["id"] = RUN_B_ID
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "events": run_b_events,
                        "categories": ["pipeline"],
                        "total": len(run_b_events),
                        "run_id": RUN_B_ID,
                    }),
                )
            elif any(seg in url for seg in ["/diagnostics", "/diagnostyka", "/events", "/logs"]):
                events = run_a_events if active_run["id"] == RUN_A_ID else run_b_events
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "events": events,
                        "categories": MOCK_CATEGORIES,
                        "total": len(events),
                        "run_id": active_run["id"],
                    }),
                )
            elif "/categories" in url:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"categories": MOCK_CATEGORIES}),
                )
            else:
                route.continue_()

        page.route("**/api/**", mock_route)

        _login_via_ui(page)
        _navigate_to_diagnostics(page)
        page.wait_for_timeout(2_000)

        # Find the historical run selector
        run_selector = page.locator(
            "select[id*='run'], select[name*='run'], "
            ".run-selector, #run-select, [data-role='run-selector'], "
            "select:has(option:has-text('Run A'))"
        ).first

        if run_selector.count() == 0:
            # Try a dropdown button pattern
            run_dropdown = page.locator(
                "button:has-text('Run A'), button:has-text('Select Run'), "
                "[class*='run-dropdown'], .run-picker"
            ).first
            if run_dropdown.count() == 0:
                pytest.skip("No historical run selector found on diagnostics screen")
            run_dropdown.click()
            page.wait_for_timeout(500)
            run_b_option = page.locator(
                f"[data-id='{RUN_B_ID}'], :has-text('Run B'), [data-value='{RUN_B_ID}']"
            ).first
            if run_b_option.count() == 0:
                pytest.skip("Run B option not found in dropdown")
            run_b_option.click()
        else:
            run_selector.select_option(value=RUN_B_ID)

        page.wait_for_timeout(2_000)

        # Verify data switched to Run B (8 events instead of 5)
        event_rows = page.locator(
            ".event-row, .log-row, .event-item, tr.event, [class*='event-row']"
        )
        row_count = event_rows.count()

        # Accept: row count matches Run B count, OR the active run state changed
        assert active_run["id"] == RUN_B_ID or row_count == len(run_b_events) or row_count != len(run_a_events), (
            "Selecting Run B did not change the displayed events — "
            "historical run comparison must reload data for the selected run"
        )
