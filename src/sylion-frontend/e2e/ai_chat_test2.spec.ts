import { test, expect } from "@playwright/test";
const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

test("Workspace: Send message with correct send button", async ({ page }) => {
  await page.goto(BASE + "/workspace", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);

  // Click New Chat
  await page.locator("button").filter({ hasText: /New Chat/i }).first().click();
  await page.waitForTimeout(1000);

  // Find input and fill
  const input = page.locator("textarea").first();
  await input.fill("Say exactly: AEIS_TEST_OK");
  await page.waitForTimeout(500);

  // Send via Enter (ChatPanel handles Enter key)
  await input.press("Enter");

  // Wait longer for AI response
  await page.waitForTimeout(15000);

  // Check if message bubble appeared
  const bubbles = await page.locator("[class*='bubble'], [class*='message']").count();
  const body = await page.locator("body").textContent() || "";
  const hasTestOk = body.includes("AEIS_TEST_OK");
  console.log("BUBBLES:", bubbles, "HAS_TEST_OK:", hasTestOk);

  await page.screenshot({ path: "test-results/workspace-message-sent.png" });
});

test("Settings: Click each Validate and capture result", async ({ page }) => {
  await page.goto(BASE + "/settings", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);

  const providers = ["openai", "anthropic", "perplexity", "google"];
  for (const p of providers) {
    const card = page.locator("div").filter({ hasText: new RegExp(p, "i") }).first();
    const btn = card.locator("button").filter({ hasText: /Validate/i }).first();
    if (await btn.isVisible().catch(() => false)) {
      await btn.click();
      await page.waitForTimeout(3000);
      const text = await card.textContent() || "";
      const valid = /valid|success|green/i.test(text);
      const invalid = /invalid|error|fail|red/i.test(text);
      console.log(`VALIDATE_${p.toUpperCase()}: valid=${valid}, invalid=${invalid}`);
    }
  }

  await page.screenshot({ path: "test-results/settings-all-validated.png" });
});
