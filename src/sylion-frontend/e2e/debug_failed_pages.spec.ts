import { test, expect } from "@playwright/test";
const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

const pages = [
  { route: "/idea-vault", name: "idea-vault" },
  { route: "/gates", name: "gates" },
  { route: "/settings", name: "settings" },
  { route: "/golden-tests", name: "golden-tests" },
  { route: "/autonomy", name: "autonomy" },
  { route: "/rebuild", name: "rebuild" },
];

for (const p of pages) {
  test(`Debug: ${p.name}`, async ({ page }) => {
    await page.goto(BASE + p.route, { waitUntil: "networkidle", timeout: 15000 });
    await page.waitForTimeout(1500);
    const h1 = await page.locator("h1").first().textContent().catch(() => "NO_H1");
    const title = await page.title().catch(() => "NO_TITLE");
    const body = await page.locator("body").textContent() || "";
    const hasError = /error|failed|exception|something went wrong/i.test(body);
    const hasForm = await page.locator("input, textarea, select").count() > 0;
    const hasButton = await page.locator("button").count() > 0;
    const buttons = await page.locator("button").allTextContents();
    console.log(`PAGE:${p.route}|h1:${(h1 ?? "").trim()}|title:${title}|error:${hasError}|inputs:${hasForm}|buttons:${hasButton}|buttonTexts:${buttons.slice(0,8).join(",")}`);
    await page.screenshot({ path: `test-results/debug-${p.name}.png`, fullPage: true });
  });
}
