import { test, expect } from "@playwright/test";

test("Trace all network requests to backend", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", r => {
    if (r.url().includes(":800")) requests.push(r.url());
  });
  page.on("requestfailed", r => {
    if (r.url().includes(":800")) requests.push("FAILED:" + r.url() + "|" + (r.failure()?.errorText || ""));
  });
  await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(3000);
  console.log("REQUESTS:", JSON.stringify(requests));
});

test("Trace idea-vault network", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", r => {
    if (r.url().includes(":800")) requests.push(r.url());
  });
  page.on("requestfailed", r => {
    if (r.url().includes(":800")) requests.push("FAILED:" + r.url() + "|" + (r.failure()?.errorText || ""));
  });
  await page.goto("http://localhost:3000/idea-vault", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(3000);
  console.log("IDEA_REQUESTS:", JSON.stringify(requests));
});
