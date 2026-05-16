import { test, expect } from "@playwright/test";

test("Check API_BASE in browser", async ({ page }) => {
  await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle", timeout: 15000 });
  const env = await page.evaluate(() => {
    return {
      nextPublicApiUrl: (window as any).__NEXT_PUBLIC_API_URL || "not_set",
      apiBaseFromScript: (window as any).API_BASE || "not_set",
    };
  });
  console.log("ENV_CHECK:", JSON.stringify(env));

  // Try to find API_BASE in page source
  const html = await page.content();
  const match = html.match(/localhost:\d+/g);
  console.log("PORTS_IN_HTML:", match ? [...new Set(match)] : []);
});
