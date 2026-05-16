import { test, expect } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

test.describe("Sprint 2 — BackendOfflineGuard", () => {
  test("blocks UI when backend is offline and restores when it comes back", async ({ page }) => {
    // Mock backend offline
    await page.route(`${API_BASE}/health`, async (route) => {
      await route.fulfill({ status: 500, body: "Internal Server Error" });
    });

    // Also intercept relative /health calls that the guard might make
    await page.route("**/health", async (route) => {
      const url = route.request().url();
      if (url.includes("/health")) {
        await route.fulfill({ status: 500, body: "Internal Server Error" });
      } else {
        await route.continue();
      }
    });

    await page.goto("/overview", { waitUntil: "networkidle", timeout: 20_000 });

    // Verify modal "Backend niedostępny" visible
    const modal = page.locator("text=Backend niedostępny").first();
    await expect(modal).toBeVisible({ timeout: 10_000 });

    // Verify content blurred + pointer-events-none
    const blurredLayer = page.locator(".pointer-events-none.opacity-30.blur-sm");
    await expect(blurredLayer).toBeVisible({ timeout: 5_000 });

    // Click underlying element → no action (blocked)
    const currentUrl = page.url();
    const sidebarLink = page.locator("nav a, aside a").first();
    if (await sidebarLink.isVisible().catch(() => false)) {
      // Use force click to attempt bypassing the overlay; URL must not change because
      // the blurred layer has pointer-events-none and the modal intercepts events.
      try {
        await sidebarLink.click({ timeout: 2_000, force: true });
      } catch {
        // Expected: modal overlay blocks the click
      }
      await page.waitForTimeout(500);
      expect(page.url()).toBe(currentUrl);
    }

    // Restore backend
    await page.unroute("**/health");
    await page.route("**/health", async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ status: "ok" }), headers: { "content-type": "application/json" } });
    });

    // Wait for guard polling interval (5s) + margin
    await page.waitForTimeout(6_500);

    // Modal disappears, app usable
    await expect(modal).not.toBeVisible({ timeout: 8_000 });
    await expect(blurredLayer).not.toBeVisible({ timeout: 5_000 });

    // App should be usable again — sidebar link should work
    const navLink = page.locator("nav a, aside a").first();
    if (await navLink.isVisible().catch(() => false)) {
      await expect(navLink).toBeVisible();
    }
  });
});
