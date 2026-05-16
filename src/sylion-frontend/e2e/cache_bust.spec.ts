import { test, expect } from "@playwright/test";

test("Hard reload and check API_BASE", async ({ page, context }) => {
  await context.clearCookies();
  await page.goto("http://localhost:3000/overview", { waitUntil: "networkidle", timeout: 15000 });
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  const requests: string[] = [];
  page.on("request", r => { if (r.url().includes(":800")) requests.push(r.url()); });

  // Trigger a data fetch by navigating
  await page.goto("http://localhost:3000/idea-vault", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(3000);

  const has8002 = requests.some(u => u.includes(":8002"));
  const has8000 = requests.some(u => u.includes(":8000"));
  console.log("HAS_8002:", has8002, "HAS_8000:", has8000, "REQUESTS:", requests);
});
