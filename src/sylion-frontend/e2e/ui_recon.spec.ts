import { test, expect } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

const routes = [
  "/overview",
  "/modules",
  "/workers",
  "/build-state",
  "/builds",
  "/governance",
  "/decisions",
  "/evidence",
  "/autonomy",
  "/skills",
  "/observability",
  "/autoscaler",
  "/health",
  "/idea-vault",
  "/pipeline",
  "/settings",
  "/budget",
  "/costs",
  "/devices",
  "/deploy",
  "/events",
  "/golden-tests",
  "/healing",
  "/integrations",
  "/lifecycle",
  "/performance",
  "/projects",
  "/quality",
  "/rebuild",
  "/risk",
  "/security-scan",
  "/sla",
  "/workspace",
];

for (const route of routes) {
  test(`UI recon: ${route}`, async ({ page }) => {
    await page.goto(`${BASE}${route}`, { waitUntil: "networkidle", timeout: 15000 });
    await page.waitForTimeout(1000);
    const title = await page.locator("h1").first().textContent().catch(() => "NO_H1");
    const hasError = await page.locator("text=404").first().isVisible().catch(() => false);
    const hasError2 = await page.locator("text=Error").first().isVisible().catch(() => false);
    console.log(`ROUTE: ${route} | h1: "${title?.trim()}" | 404: ${hasError} | Error: ${hasError2}`);
    await page.screenshot({ path: `test-results/ui-recon-${route.replace(/\//g, "_")}.png`, fullPage: true });
  });
}
