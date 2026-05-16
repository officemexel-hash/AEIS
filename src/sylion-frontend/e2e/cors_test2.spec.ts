import { test, expect } from "@playwright/test";

test("Fetch 127.0.0.1:8000", async ({ page }) => {
  const result = await page.evaluate(async () => {
    try {
      const res = await fetch("http://127.0.0.1:8000/health", { signal: AbortSignal.timeout(5000) });
      return { ok: res.ok, status: res.status };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  console.log("IP_RESULT:", JSON.stringify(result));
});

test("Fetch localhost:8000", async ({ page }) => {
  const result = await page.evaluate(async () => {
    try {
      const res = await fetch("http://localhost:8000/health", { signal: AbortSignal.timeout(5000) });
      return { ok: res.ok, status: res.status };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });
  console.log("LOCALHOST_RESULT:", JSON.stringify(result));
});
