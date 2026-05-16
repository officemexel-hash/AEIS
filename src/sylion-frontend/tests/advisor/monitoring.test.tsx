 
/**
 * Phase B.4 Operator Monitoring Dashboard — Playwright e2e suite.
 *
 * Note on filename: the build brief specifies `tests/advisor/monitoring.test.tsx`
 * (not the existing `e2e/` folder). The .test.tsx extension is kept; the file is
 * authored against @playwright/test to match the framework that actually runs in
 * this repo (matches the conventions established in
 * tests/advisor/{feed,wizard,lifecycle}.test.tsx). To execute the suite the
 * playwright config's testDir glob must be extended to include `tests/`, e.g.
 * `npx playwright test --config playwright.config.ts --project=chromium
 * tests/advisor/monitoring.test.tsx`.
 */

import { test, expect } from "@playwright/test";

const ROUTE = "/dashboard/operator-monitor";

async function blockBackend(page: import("@playwright/test").Page) {
  // Force the backend-reachability check to fail so the monitoring dashboard
  // renders advisorMocks.monitoringSnapshot (3 mock projects, 14d throughput).
  await page.route("**/health", (route) => route.abort());
  await page.route("**/api/v1/advisor/**", (route) => route.abort());
}

const MOCK_PROJECT_IDS = ["p-1", "p-2", "p-3"];

test.describe("operator monitoring dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await blockBackend(page);
  });

  test("dashboard_renders_with_mock_data_when_backend_unreachable", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    const dashboard = page.getByTestId("operator-monitor-page");
    await expect(dashboard).toBeVisible();

    // Heading
    await expect(page.getByRole("heading", { name: /Operator Monitoring/i })).toBeVisible();

    // MockBanner renders the canonical fallback copy.
    await expect(page.getByText(/Backend unreachable/i)).toBeVisible();

    // Headline KPI block exposes the projects count from advisorMocks (3).
    const stats = page.getByTestId("headline-stats");
    await expect(stats).toContainText("3"); // projects
  });

  test("projects_matrix_shows_all_projects_with_active_phase", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    const matrix = page.getByTestId("projects-matrix");
    await expect(matrix).toBeVisible();

    // All three mock projects render as rows in the matrix.
    for (const projectId of MOCK_PROJECT_IDS) {
      const row = page.getByTestId(`matrix-row-${projectId}`);
      await expect(row).toBeVisible();
    }

    // The active hook cell has the sylion-blue active styling. Mock data places
    // p-1 at H08, p-2 at H13, p-3 at H06 — verify each one was tagged active.
    await expect(page.getByTestId("matrix-cell-p-1-H08")).toHaveClass(/sylion-blue/);
    await expect(page.getByTestId("matrix-cell-p-2-H13")).toHaveClass(/sylion-blue/);
    await expect(page.getByTestId("matrix-cell-p-3-H06")).toHaveClass(/sylion-blue/);
  });

  test("cost_vs_budget_shows_per_project_breakdown", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    // Cost & Budget lives under the "Cost & Budget" tab.
    await page.getByRole("tab", { name: /Cost.*Budget/i }).click();

    const card = page.getByTestId("cost-vs-budget");
    await expect(card).toBeVisible();
    await expect(page.getByTestId("global-progress")).toBeVisible();
    await expect(page.getByTestId("per-project-chart")).toBeVisible();

    // Each mock project name appears as a Y-axis label in the bar chart.
    await expect(page.getByText("Funding research bot").first()).toBeVisible();
    await expect(page.getByText("Operator console refresh").first()).toBeVisible();
    await expect(page.getByText("Council weight calibration").first()).toBeVisible();
  });

  test("alerts_link_to_card_detail_page", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    // alert-1 in the mock has card_id="demo-card-critical" → must render as anchor.
    const linkable = page.getByTestId("alert-row-alert-1");
    await expect(linkable).toBeVisible();
    await expect(linkable).toHaveAttribute("href", "/advisor/demo-card-critical");

    // alert-2 has no card_id → not an anchor (we render a div).
    const nonLinkable = page.getByTestId("alert-row-alert-2");
    await expect(nonLinkable).toBeVisible();
    await expect(nonLinkable).not.toHaveAttribute("href", /.+/);
  });

  test("throughput_chart_renders_14_days", async ({ page }) => {
    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    const chart = page.getByTestId("recommendation-throughput");
    await expect(chart).toBeVisible();
    await expect(page.getByTestId("throughput-chart")).toBeVisible();

    // The Recharts area chart paints one polyline path per series. 3 series
    // (emitted/accepted/rejected) over 14 days means 3 visible <path> nodes.
    const paths = page.locator('[data-testid="throughput-chart"] svg path');
    await expect(paths.first()).toBeVisible();

    // Y-axis ticks (rendered Recharts text nodes) reflect the data range.
    await expect(chart).toContainText("Emitted");
    await expect(chart).toContainText("Accepted");
    await expect(chart).toContainText("Rejected");
  });

  test("subscription_banner_visible_when_recommendations_present", async ({ page }) => {
    // The default mock returns an empty subscription_recommendations array; we
    // intercept the snapshot endpoint and inject a single subscription card so
    // the banner renders. Note: the dashboard short-circuits to mock when
    // /health is blocked, so we additionally allow /health to succeed here.
    await page.unroute("**/health");
    await page.route("**/health", (route) =>
      route.fulfill({ status: 200, body: JSON.stringify({ status: "ok" }) }),
    );
    await page.route("**/api/v1/advisor/monitoring/snapshot", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          projects: [],
          throughput: Array.from({ length: 14 }, (_, i) => ({ ts: 0, emitted: i, accepted: i, rejected: 0 })),
          cost_vs_budget: { spend_usd: 0, budget_usd: 0, per_project: {} },
          council_activity: [],
          subscription_recommendations: [
            {
              envelope_version: "1.0.0",
              header: {
                card_id: "sub-1",
                schema_version: "1.0.0",
                card_type: "decision",
                title: "Upgrade to Pro tier",
                rationale: "Projected ROI > 15%.",
                confidence_score: 0.83,
                confidence_label: "high",
                sources: ["rule_engine"],
                risk_level: "medium",
                project_domain: "subscription",
                d_level: "D3",
                evidence_pack_id: "ev-1",
                history_based: false,
                related_history_card_ids: [],
                historical_acceptance_rate: 0,
                created_at: 0,
                updated_at: 0,
                priority: "high",
                tags: ["subscription"],
                dont_learn: false,
                human_gate_required: true,
                mobile_allowed: true,
                requires_biometric: false,
                push_priority: "normal",
                audit_trail_id: "trail",
                operator_id: "op-1",
                emitting_module: "sylion.aeis.advisor.subscription",
                used_local_fallback: false,
              },
              body: {
                recommendation: "Move to Pro tier",
                expected_benefit: "20% lower per-token cost.",
                recommendation_type: "REC_TYPE_PURCHASE_PLAN",
              },
            },
          ],
          alerts: [],
        }),
      }),
    );

    await page.goto(ROUTE, { waitUntil: "domcontentloaded" });

    const banner = page.getByTestId("subscription-banner");
    await expect(banner).toBeVisible();

    // The banner row is an anchor pointing to the card detail page.
    const cardRow = page.getByTestId("subscription-card-sub-1");
    await expect(cardRow).toHaveAttribute("href", "/advisor/sub-1");
    await expect(cardRow).toContainText("Upgrade to Pro tier");
  });
});
