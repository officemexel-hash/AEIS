import { test, expect } from "@playwright/test";
const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

const pages = [
  "/overview",
  "/idea-vault",
  "/gates",
  "/settings",
  "/golden-tests",
  "/autonomy",
  "/rebuild",
  "/workers",
  "/build-state",
  "/skills",
  "/observability",
  "/devices",
  "/deploy",
  "/budget",
  "/costs",
  "/workspace",
];

for (const route of pages) {
  test(`Screenshot: ${route}`, async ({ page }) => {
    await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 15000 });
    await page.waitForTimeout(1500);
    const name = route.replace(/\//g, "_") || "root";
    await page.screenshot({ path: `test-results/audit-${name}.png`, fullPage: true });
  });
}
