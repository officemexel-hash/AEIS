import { test, expect } from "@playwright/test";
const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

test("CORS check: fetch /health from browser", async ({ page }) => {
  const result = await page.evaluate(async () => {
    try {
      const res = await fetch("http://localhost:8000/health", { signal: AbortSignal.timeout(5000) });
      return { ok: res.ok, status: res.status, headers: Object.fromEntries(res.headers) };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  console.log("CORS_RESULT:", JSON.stringify(result));
});

test("API check: fetch /api/v1/ideas from browser", async ({ page }) => {
  const result = await page.evaluate(async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/ideas", { signal: AbortSignal.timeout(5000) });
      const text = await res.text();
      return { ok: res.ok, status: res.status, preview: text.slice(0, 100) };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  console.log("API_RESULT:", JSON.stringify(result));
});
