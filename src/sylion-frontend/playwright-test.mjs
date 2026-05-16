import { chromium } from "playwright";

const routes = [
  "/", "/overview", "/idea-vault", "/skills", "/book",
  "/projects", "/governance", "/agents", "/modules", "/evidence",
  "/contracts", "/lifecycle", "/decisions", "/autonomy", "/evidence-spine",
  "/health", "/rebuild", "/performance",
];

async function testDashboard() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  let totalPageErrors = 0;

  for (const route of routes) {
    const pageErrors = [];
    const errorResponses = [];

    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("response", (res) => {
      if (res.status() >= 400 && res.url().includes("localhost:3000")) {
        errorResponses.push({ url: res.url(), status: res.status() });
      }
    });

    try {
      const response = await page.goto(`http://localhost:3000${route}`, { waitUntil: "networkidle", timeout: 15000 });
      await page.waitForTimeout(3000);

      const status = response?.status() ?? 0;
      const hasIssues = pageErrors.length > 0 || errorResponses.length > 0;
      const icon = hasIssues ? "✗" : "✓";
      totalPageErrors += pageErrors.length;

      console.log(`${icon} ${route.padEnd(16)} HTTP ${status}  page_errors=${pageErrors.length}  frontend_404s=${errorResponses.length}`);

      for (const e of pageErrors) {
        console.log(`   PAGE ERROR: ${e.substring(0, 300)}`);
      }
      for (const r of errorResponses) {
        console.log(`   FRONTEND 404: ${r.status} ${r.url}`);
      }
    } catch (err) {
      console.log(`✗ ${route.padEnd(16)} FATAL: ${err.message.substring(0, 150)}`);
      totalPageErrors++;
    }

    page.removeAllListeners("pageerror");
    page.removeAllListeners("response");
  }

  await browser.close();

  console.log(`\n${"=".repeat(60)}`);
  if (totalPageErrors === 0) {
    console.log(`ALL ${routes.length} PAGES CLEAN — no hydration errors, no React errors`);
    console.log("(Backend 404s for missing endpoints are expected)");
  } else {
    console.log(`FOUND ${totalPageErrors} page errors — need fixing`);
    process.exit(1);
  }
}

testDashboard().catch((e) => { console.error(e); process.exit(1); });
