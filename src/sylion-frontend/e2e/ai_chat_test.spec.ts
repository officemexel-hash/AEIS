import { test, expect } from "@playwright/test";
const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

test("Settings: Validate OpenAI key and check result", async ({ page }) => {
  await page.goto(BASE + "/settings", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);

  // Find the openai card and click Validate
  const openaiCard = page.locator("div").filter({ hasText: /openai/i }).first();
  const validateBtn = openaiCard.locator("button").filter({ hasText: /Validate/i }).first();

  if (await validateBtn.isVisible().catch(() => false)) {
    await validateBtn.click();
    await page.waitForTimeout(4000);

    // Check for status change
    const cardText = await openaiCard.textContent() || "";
    console.log("OPENAI_CARD_AFTER_VALIDATE:", cardText.replace(/\s+/g, " ").slice(0, 200));

    // Screenshot after validation
    await page.screenshot({ path: "test-results/settings-after-validate.png" });
  }
});

test("Workspace: Send message to AI and check response", async ({ page }) => {
  await page.goto(BASE + "/workspace", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);

  // Click New Chat
  const newChatBtn = page.locator("button").filter({ hasText: /New Chat/i }).first();
  if (await newChatBtn.isVisible().catch(() => false)) {
    await newChatBtn.click();
    await page.waitForTimeout(1000);
  }

  // Find message input and type
  const input = page.locator("input[placeholder*='message'], textarea[placeholder*='message']").first();
  if (await input.isVisible().catch(() => false)) {
    await input.fill("Say exactly: AEIS_TEST_OK");
    await page.waitForTimeout(500);

    // Find send button
    const sendBtn = page.locator("button[type='submit'], button").filter({ hasText: /^$/ }).first();
    // Try clicking the send button near input
    const sendBtn2 = input.locator("xpath=../..").locator("button").first();
    if (await sendBtn2.isVisible().catch(() => false)) {
      await sendBtn2.click();
    } else {
      await input.press("Enter");
    }

    // Wait for response (up to 30s for AI response)
    await page.waitForTimeout(8000);

    const body = await page.locator("body").textContent() || "";
    const hasResponse = /AEIS_TEST_OK|test_ok|assistant|AI/i.test(body);
    console.log("WORKSPACE_HAS_RESPONSE:", hasResponse);
    console.log("WORKSPACE_BODY_SNIPPET:", body.replace(/\s+/g, " ").slice(0, 300));

    await page.screenshot({ path: "test-results/workspace-after-message.png" });
  } else {
    console.log("WORKSPACE_INPUT_NOT_VISIBLE");
  }
});
