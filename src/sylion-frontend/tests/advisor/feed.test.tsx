import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3000";

async function blockBackend(page: import("@playwright/test").Page) {
  await page.route(/\/health(\?.*)?$/, async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
  });
  await page.route(/\/api\/v1\/advisor\/.*/, async (route) => {
    await route.abort("failed");
  });
}

test.describe("advisor live feed (Phase B.1)", () => {
  test("feed_renders_demo_cards_when_backend_unreachable", async ({ page }) => {
    await blockBackend(page);
    await page.goto(`${BASE_URL}/advisor`, { waitUntil: "domcontentloaded" });

    const list = page.getByTestId("feed-list");
    await expect(list).toBeVisible();
    await expect(page.getByTestId("feed-card")).toHaveCount(2);
    await expect(
      page.locator('[data-testid="feed-card"]', { hasText: "Council size larger than your default" }),
    ).toHaveCount(1);
    await expect(
      page.locator('[data-testid="feed-card"]', { hasText: "BLOCK production deploy" }),
    ).toHaveCount(1);
  });

  test("mock_banner_visible_when_backend_unreachable", async ({ page }) => {
    await blockBackend(page);
    await page.goto(`${BASE_URL}/advisor`, { waitUntil: "domcontentloaded" });

    await expect(page.getByText("Backend unreachable")).toBeVisible();
    await expect(page.getByTestId("feed-source-indicator")).toContainText("MOCK");
  });

  test("risk_filter_filters_cards", async ({ page }) => {
    await blockBackend(page);
    await page.goto(`${BASE_URL}/advisor`, { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("feed-card")).toHaveCount(2);

    await page.getByTestId("filter-risk-low").click();
    await expect(page.getByTestId("feed-card")).toHaveCount(1);
    await expect(page.locator('[data-testid="feed-card"][data-risk="low"]')).toHaveCount(1);

    await page.getByTestId("filter-risk-critical").click();
    await expect(page.getByTestId("feed-card")).toHaveCount(1);
    await expect(page.locator('[data-testid="feed-card"][data-risk="critical"]')).toHaveCount(1);

    await page.getByTestId("filter-risk-all").click();
    await expect(page.getByTestId("feed-card")).toHaveCount(2);
  });

  test("critical_card_renders_in_modal", async ({ page }) => {
    await blockBackend(page);
    await page.goto(`${BASE_URL}/advisor`, { waitUntil: "domcontentloaded" });

    const modal = page.getByTestId("advisor-modal");
    await expect(modal).toBeVisible();
    await expect(modal).toHaveAttribute("data-card-id", "demo-card-critical");
    await expect(modal).toContainText("BLOCK production deploy");

    // Backdrop click must NOT dismiss critical/high modal
    await page.mouse.click(5, 5);
    await expect(modal).toBeVisible();
    // Escape key also blocked
    await page.keyboard.press("Escape");
    await expect(modal).toBeVisible();
  });

  test("low_risk_card_renders_in_toast", async ({ page }) => {
    await blockBackend(page);
    await page.goto(`${BASE_URL}/advisor`, { waitUntil: "domcontentloaded" });

    const toastQueue = page.getByTestId("advisor-toast-queue");
    await expect(toastQueue).toBeVisible();
    await expect(page.locator('[data-testid="advisor-toast"][data-risk="low"]')).toHaveCount(1);
    await expect(page.locator('[data-testid="advisor-toast"][data-risk="critical"]')).toHaveCount(0);
  });

  test("evidence_pack_viewer_appears_when_card_has_evidence_pack_id", async ({ page }) => {
    await blockBackend(page);
    await page.goto(`${BASE_URL}/advisor/demo-card-critical`, { waitUntil: "domcontentloaded" });

    await expect(page.getByTestId("advisor-detail-page")).toBeVisible();
    await expect(page.getByTestId("advisor-detail-evidence-toggle")).toBeVisible();

    await page.getByTestId("advisor-detail-evidence-toggle").click();
    await expect(page.getByTestId("advisor-detail-evidence")).toBeVisible();
    await expect(page.getByText("Evidence Pack")).toBeVisible();
    await expect(page.getByText("Rationale")).toBeVisible();
    await expect(page.getByText("Rollback")).toBeVisible();
  });
});
