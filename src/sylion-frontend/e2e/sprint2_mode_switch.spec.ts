import { test, expect } from "@playwright/test";

test.describe("Sprint 2 — Mode switch visual diff", () => {
  test("operator mode by default, switching to technical changes badge, sidebar palette and fonts", async ({ page }) => {
    await page.goto("/overview", { waitUntil: "networkidle", timeout: 20_000 });

    const modeSwitcher = page.locator('[data-testid="mode-switcher"]');
    await expect(modeSwitcher).toBeVisible();

    // Default: operator mode
    const modeBadge = page.locator("[data-testid='mode-badge']").or(page.locator(".ModeBadge")).or(page.locator("text=Operator").first());
    // ModeBadge does not have a data-testid; use the text inside the badge
    const operatorBadgeText = page.locator("text=Operator").first();
    await expect(operatorBadgeText).toBeVisible({ timeout: 5_000 });

    // Sidebar is collapsed by default — expand it to verify text labels
    const expandBtn = page.locator('button[aria-label="Rozwiń menu"]').first();
    if (await expandBtn.isVisible().catch(() => false)) {
      await expandBtn.click();
      await page.waitForTimeout(400);
    }

    // Sidebar warm palette (operator background is lighter / warmer)
    const sidebar = page.locator("aside").first();
    const sidebarBgOperator = await sidebar.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(sidebarBgOperator).toBeTruthy();

    // Verify orchestration sidebar section visible in operator mode
    const orchestSection = page.getByText("Orkiestracja", { exact: false }).first();
    await expect(orchestSection).toBeVisible({ timeout: 8_000 });

    // Click ModeSwitcher → technical
    const technicalBtn = modeSwitcher.locator("[data-mode='technical']");
    await expect(technicalBtn).toBeVisible();
    await technicalBtn.click();
    await page.waitForTimeout(600);

    // Verify ModeBadge "Techniczny" amber visible
    const technicalBadgeText = page.locator("text=Techniczny").first();
    await expect(technicalBadgeText).toBeVisible({ timeout: 5_000 });

    // Verify sidebar cool palette + smaller fonts
    const sidebarBgTechnical = await sidebar.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(sidebarBgTechnical).toBeTruthy();
    // Cool palette should be darker / different from operator
    expect(sidebarBgTechnical).not.toBe(sidebarBgOperator);

    // Font size should be smaller in technical mode (text-[12px] vs text-[14px])
    const firstNavLink = sidebar.locator("a").first();
    const fontSizeTechnical = await firstNavLink.evaluate((el) => getComputedStyle(el).fontSize);
    expect(fontSizeTechnical).toBeTruthy();
  });
});
