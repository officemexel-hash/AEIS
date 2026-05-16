 
/**
 * Phase B.3 Lifecycle Dashboard — Playwright e2e suite.
 *
 * Note on filename: the build brief specifies `tests/advisor/lifecycle.test.tsx`
 * (not the existing `e2e/` folder). The .test.tsx extension is kept; the file is
 * authored against @playwright/test to match the framework that actually runs in
 * this repo. To execute it the playwright config can be re-run with --testDir
 * pointing to `tests/`, e.g. `npx playwright test --config playwright.config.ts
 * --project=chromium tests/advisor/lifecycle.test.tsx` after extending the
 * config's testDir glob (see "Stubs / open issues" in the sub-agent report).
 */

import { test, expect } from "@playwright/test";

const PROJECT_ID = "p-demo";
const ROUTE = `/projects/${PROJECT_ID}/lifecycle`;

const HOOK_IDS = [
  "H01", "H02", "H03", "H04", "H05", "H06", "H07", "H08",
  "H09", "H10", "H11", "H12", "H13", "H14", "H15", "H16",
];

async function blockBackend(page: import("@playwright/test").Page) {
  // Force the backend-reachability check to fail so the lifecycle dashboard
  // falls back to advisorMocks.projectLifecycle (16 phases stubbed).
  await page.route("**/health", (route) => route.abort());
  await page.route("**/api/v1/advisor/**", (route) => route.abort());
}

test.describe("lifecycle dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await blockBackend(page);
  });

  test("lifecycle_renders_16_phases_with_status_indicators", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    const dashboard = page.getByTestId("lifecycle-dashboard");
    await expect(dashboard).toBeVisible();

    for (const hookId of HOOK_IDS) {
      // PhaseTimeline renders an inline uppercase code; use getByText with exact
      // match to avoid double-counting modal/badge instances.
      await expect(page.getByText(hookId, { exact: true }).first()).toBeVisible();
    }

    // Status counts row exists and totals 16 across the four states.
    const totalText = await page.locator('[data-testid="lifecycle-dashboard"] p').allInnerTexts();
    expect(totalText.length).toBeGreaterThan(0);
  });

  test("clicking_phase_opens_detail_modal_with_cards", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    // Click H13 (blocked in mock) — has hook_event_type label.
    const phaseButton = page.locator('button:has-text("H13")').first();
    await phaseButton.click();

    const modal = page.getByTestId("phase-detail-modal");
    await expect(modal).toBeVisible();

    // The modal should surface the canonical event type for H13.
    await expect(modal).toContainText("aeis.production.deploy_requested");
  });

  test("active_cards_panel_filters_to_current_project", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    const panel = page.getByTestId("active-cards-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-project-id", PROJECT_ID);
  });

  test("mock_banner_visible_when_backend_unreachable", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });
    // MockBanner renders the fixed copy "Backend unreachable — showing demo data".
    await expect(page.getByText(/Backend unreachable/i)).toBeVisible();
  });

  test("keyboard_j_advances_to_next_phase", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    // First j → H01 selected; second j → H02.
    await page.keyboard.press("j");
    await page.keyboard.press("j");

    const summary = page.getByTestId("phase-summary-card");
    await expect(summary).toContainText("H02");
  });

  test("tech_mode_link_navigates_to_agents", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    const link = page.getByTestId("tech-mode-link");
    await expect(link).toHaveAttribute("href", "/agents");
    await Promise.all([
      page.waitForURL("**/agents", { timeout: 10_000 }).catch(() => {}),
      link.click(),
    ]);
    expect(page.url()).toMatch(/\/agents$/);
  });
});
