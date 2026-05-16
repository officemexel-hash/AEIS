import { test, expect } from "@playwright/test";

test("Direct browser visit to backend health", async ({ page }) => {
  await page.goto("http://127.0.0.1:8000/health", { timeout: 10000 });
  const body = await page.locator("body").textContent() || "";
  console.log("BODY:", body);
});

test("Network interception check", async ({ page }) => {
  let reqUrl = "";
  page.on("request", r => { if (r.url().includes(":8000")) reqUrl = r.url(); });
  page.on("requestfailed", r => { if (r.url().includes(":8000")) console.log("FAILED:", r.url(), r.failure()?.errorText); });
  await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(3000);
  console.log("REQ_URL:", reqUrl);
});
