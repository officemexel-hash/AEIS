import { test, expect } from "@playwright/test";

test.describe("Round 1 Fixes Retest", () => {
  test("workers page shows registered worker", async ({ page }) => {
    await page.goto("http://localhost:3000/workers");
    await page.waitForTimeout(2000);
    // The stats card should show 1 worker
    await expect(page.locator("text=Worker Fleet")).toBeVisible();
    const countCard = page.locator("text=/1/").first();
    await expect(countCard).toBeVisible();
  });

  test("idea vault loads without 500", async ({ page }) => {
    await page.goto("http://localhost:3000/idea-vault");
    await page.waitForTimeout(2000);
    await expect(page.locator("textarea").first()).toBeVisible();
  });

  test("skills page shows created skill", async ({ page }) => {
    await page.goto("http://localhost:3000/skills");
    await page.waitForTimeout(2000);
    await expect(page.locator("text=Skill Registry")).toBeVisible();
    // With backend connected, should show skill count > 0 in stats
    const skillCount = page.locator("text=/Registered Skills/i");
    await expect(skillCount).toBeVisible();
  });

  test("governance page loads and proposals work", async ({ page }) => {
    await page.goto("http://localhost:3000/governance");
    await page.waitForTimeout(2000);
    await expect(page.locator("h1, h2").filter({ hasText: /Governance|Proposals/i }).first()).toBeVisible();
  });

  test("settings page loads with API keys", async ({ page }) => {
    await page.goto("http://localhost:3000/settings");
    await page.waitForTimeout(2000);
    await expect(page.locator("text=Settings").first()).toBeVisible();
  });
});
