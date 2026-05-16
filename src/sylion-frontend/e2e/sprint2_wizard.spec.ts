import { test, expect } from "@playwright/test";

test.describe("Sprint 2 — Onboarding wizard", () => {
  test("Step 2 adds API key row, persists data, Cloudflare hosting fields appear; Step 10 skip completes wizard", async ({ page }) => {
    await page.goto("/onboarding", { waitUntil: "networkidle", timeout: 20_000 });

    // Wait for wizard to mount
    const wizard = page.locator('[data-testid="onboarding-wizard"]');
    await expect(wizard).toBeVisible({ timeout: 8_000 });

    // Jump to step 2 via nav
    const step2Nav = page.locator("nav button").filter({ hasText: /2\. Klucze API i hosting/i }).first();
    await step2Nav.click();
    await page.waitForTimeout(300);
    await expect(wizard).toHaveAttribute("data-step", "2");

    // Step 2: Click "+ Dodaj kolejny klucz API" → new row appears
    const addKeyBtn = page.locator('[data-testid="step2-add-key"]');
    await expect(addKeyBtn).toBeVisible();
    await addKeyBtn.click();
    await page.waitForTimeout(300);

    const providerSelects = page.locator('select[data-testid^="step2-provider-"]');
    const keyInputs = page.locator('input[data-testid^="step2-key-"]');
    expect(await providerSelects.count()).toBeGreaterThanOrEqual(1);
    expect(await keyInputs.count()).toBeGreaterThanOrEqual(1);

    // Fill provider + key → row data persists
    const firstProvider = providerSelects.first();
    const firstKey = keyInputs.first();
    await firstProvider.selectOption("openai");
    await firstKey.fill("sk-test-openai-key-123");

    // Navigate away and back to step 2 to verify persistence
    const step3Nav = page.locator("nav button").filter({ hasText: /3\. Limity budżetu/i }).first();
    await step3Nav.click();
    await page.waitForTimeout(300);
    await step2Nav.click();
    await page.waitForTimeout(300);

    const persistedProvider = page.locator('select[data-testid^="step2-provider-"]').first();
    const persistedKey = page.locator('input[data-testid^="step2-key-"]').first();
    await expect(persistedProvider).toHaveValue("openai");
    await expect(persistedKey).toHaveValue("sk-test-openai-key-123");

    // Add hosting provider Cloudflare → fields appear
    const addHostingBtn = page.locator('[data-testid="step2-add-hosting"]');
    await addHostingBtn.click();
    await page.waitForTimeout(300);

    const hostingProviderSelect = page.locator('select[data-testid^="step2-hosting-provider-"]').first();
    await hostingProviderSelect.selectOption("cloudflare");
    await page.waitForTimeout(300);

    const cloudflareToken = page.locator('input[data-testid^="step2-hosting-"][data-testid$="-token"]').first();
    const cloudflareAccount = page.locator('input[data-testid^="step2-hosting-"][data-testid$="-account_id"]').first();
    await expect(cloudflareToken).toBeVisible();
    await expect(cloudflareAccount).toBeVisible();

    // Jump to step 10
    const step10Nav = page.locator("nav button").filter({ hasText: /10\. Pierwszy pomysł/i }).first();
    await step10Nav.click();
    await page.waitForTimeout(300);
    await expect(wizard).toHaveAttribute("data-step", "10");

    // Step 10 "First idea" — click "Pominę na razie" → completes wizard
    const skipBtn = page.locator("button").filter({ hasText: /Pominę na razie/i }).first();
    await expect(skipBtn).toBeVisible();

    // Capture current URL before skip
    await skipBtn.click();

    // Wait for redirect to /advisor/cockpit (NOT /dashboard/operator-monitor)
    await page.waitForURL("**/advisor/cockpit", { timeout: 15_000 });
    expect(page.url()).toContain("/advisor/cockpit");
    expect(page.url()).not.toContain("/dashboard/operator-monitor");
  });
});
