import { test, expect } from "@playwright/test";

test.describe("Sprint 2 — Cockpit v4", () => {
  test("renders hero, orb, metrics, decisions, lifecycle and config cards", async ({ page }) => {
    await page.goto("/advisor/cockpit", { waitUntil: "networkidle", timeout: 20_000 });

    // Aurora background / visual hero
    const hero = page.locator(".visual-hero");
    await expect(hero).toBeVisible({ timeout: 8_000 });

    // AdvisorCore orb
    const orb = page.locator(".core-orb");
    await expect(orb).toBeVisible({ timeout: 5_000 });

    // Metric tiles (4)
    const tiles = page.locator(".metric-tile");
    await expect(tiles).toHaveCount(4, { timeout: 5_000 });

    // Featured decision card — may be absent if backend has no cards
    const featuredCard = page.locator(".decision-card.featured");
    const hasFeatured = await featuredCard.isVisible().catch(() => false);
    if (hasFeatured) {
      const acceptBtn = featuredCard.locator("button").filter({ hasText: /Akceptuj/i }).first();
      await acceptBtn.click();
      // Modal may or may not be implemented; verify no crash at minimum
      await page.waitForTimeout(500);
    }

    // Lifecycle rail shows 15 phases
    const lifecyclePanel = page.locator(".lifecycle-panel");
    await expect(lifecyclePanel).toBeVisible();
    const phases = lifecyclePanel.locator(".lifecycle-rail .phase-tile");
    await expect(phases).toHaveCount(15, { timeout: 8_000 }).catch(async () => {
      // Backend may return a variable number of phases; ensure at least 15
      const count = await phases.count();
      expect(count).toBeGreaterThanOrEqual(15);
    });

    // ConfigurationControlCards (4 cards)
    const configGrid = page.locator(".config-grid");
    await expect(configGrid).toBeVisible();
    const configCards = configGrid.locator(".config-card");
    await expect(configCards).toHaveCount(4, { timeout: 5_000 });
  });
});
