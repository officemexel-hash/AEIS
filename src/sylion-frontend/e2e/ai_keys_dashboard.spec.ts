import { test, expect } from "@playwright/test";
const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

test("Settings: API keys visible and Validate buttons clickable", async ({ page }) => {
  await page.goto(BASE + "/settings", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);

  // Check for the 4 provider cards
  const providers = ["openai", "anthropic", "perplexity", "google"];
  for (const p of providers) {
    const card = page.locator("text=/" + p + "/i").first();
    const visible = await card.isVisible().catch(() => false);
    console.log(`PROVIDER_${p.toUpperCase()}: visible=${visible}`);
  }

  // Count Validate buttons
  const validateBtns = page.locator("button").filter({ hasText: /Validate/i });
  const count = await validateBtns.count();
  console.log(`VALIDATE_BUTTONS: ${count}`);

  // Click first validate button and wait for result
  if (count > 0) {
    await validateBtns.first().click();
    await page.waitForTimeout(3000);
    const body = await page.locator("body").textContent() || "";
    const hasSuccess = /valid|success|ok|green/i.test(body);
    const hasError = /invalid|error|fail|red/i.test(body);
    console.log(`VALIDATE_RESULT: success_indicator=${hasSuccess}, error_indicator=${hasError}`);
  }

  // Screenshot
  await page.screenshot({ path: "test-results/settings-keys-live.png" });
});

test("Workspace: Chat creation and model selection", async ({ page }) => {
  await page.goto(BASE + "/workspace", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);

  // Click New Chat
  const newChatBtn = page.locator("button").filter({ hasText: /New Chat/i }).first();
  if (await newChatBtn.isVisible().catch(() => false)) {
    await newChatBtn.click();
    await page.waitForTimeout(1000);
    console.log("NEW_CHAT_CLICKED: true");

    // Look for model selector
    const modelSelector = page.locator("button, [role='combobox'], select").filter({ hasText: /gpt|claude|sonar|gemini|model/i }).first();
    const hasSelector = await modelSelector.isVisible().catch(() => false);
    console.log(`MODEL_SELECTOR: ${hasSelector}`);
  } else {
    console.log("NEW_CHAT_CLICKED: false (button not visible)");
  }

  await page.screenshot({ path: "test-results/workspace-chat.png" });
});

test("Hetzner: Search for Hetzner UI", async ({ page }) => {
  // Check if Hetzner exists in settings, integrations, or deploy
  for (const route of ["/settings", "/integrations", "/deploy"]) {
    await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 15000 });
    await page.waitForTimeout(500);
    const body = await page.locator("body").textContent() || "";
    const hasHetzner = /hetzner|hcloud|server|vps/i.test(body);
    console.log(`HETZNER_SEARCH_${route}: ${hasHetzner}`);
  }
});
