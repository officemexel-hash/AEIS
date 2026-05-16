import { test, expect, Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

/**
 * HUMAN TESTER scenarios — behave like a real user.
 * Captures console errors, network failures, and UX issues.
 * Screenshots on failure; results aggregated into docs/production/HUMAN_TEST_REPORT.md.
 */

const ARTIFACTS_DIR = path.resolve(__dirname, "../../../docs/production/human-test-artifacts");
fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });

type Finding = {
  scenario: string;
  route?: string;
  consoleErrors: string[];
  pageErrors: string[];
  networkFailures: string[];
  uxIssues: string[];
  screenshot?: string;
  status: "PASS" | "FAIL";
  durationMs: number;
};

const FINDINGS: Finding[] = [];

function recordFinding(f: Finding) {
  FINDINGS.push(f);
  const line = `${f.status} ${f.scenario}${f.route ? " " + f.route : ""} (${f.durationMs}ms)`;
   
  console.log("[HUMAN-TEST]", line);
}

async function attachListeners(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const networkFailures: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const t = msg.text();
      if (t.includes("Hydration") || t.includes("favicon")) return;
      consoleErrors.push(t.slice(0, 500));
    }
  });
  page.on("pageerror", (err) => {
    if (err.message.includes("Hydration failed")) return;
    pageErrors.push(err.message.slice(0, 500));
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (url.includes("favicon") || url.startsWith("data:")) return;
    const err = req.failure()?.errorText ?? "failed";
    if (err.includes("ERR_ABORTED")) return;
    networkFailures.push(`${req.method()} ${url} — ${err}`);
  });
  page.on("response", (res) => {
    const s = res.status();
    if (s >= 500) networkFailures.push(`HTTP ${s} ${res.url()}`);
  });

  return { consoleErrors, pageErrors, networkFailures };
}

async function runScenario(
  page: Page,
  name: string,
  route: string,
  fn?: (page: Page) => Promise<string[]>,
) {
  const start = Date.now();
  const { consoleErrors, pageErrors, networkFailures } = await attachListeners(page);
  let uxIssues: string[] = [];
  let screenshot: string | undefined;
  let status: "PASS" | "FAIL" = "PASS";

  try {
    await page.goto(route, { waitUntil: "domcontentloaded", timeout: 20_000 });
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
    const body = page.locator("body");
    await expect(body).toBeVisible();

    const errText = await page.locator("text=/Application error|Internal Server Error|TypeError/i").count();
    if (errText > 0) uxIssues.push("Error banner visible on page");

    const h1 = await page.locator("h1").count();
    if (h1 === 0) uxIssues.push("No <h1> on page");

    if (fn) {
      const custom = await fn(page);
      uxIssues = uxIssues.concat(custom);
    }
  } catch (e: any) {
    status = "FAIL";
    uxIssues.push(`Exception: ${e?.message?.slice(0, 300) ?? String(e)}`);
  }

  if (consoleErrors.length || pageErrors.length || networkFailures.length || uxIssues.length) {
    status = "FAIL";
    const safe = name.replace(/[^a-z0-9_-]/gi, "_");
    const file = path.join(ARTIFACTS_DIR, `${safe}.png`);
    try {
      await page.screenshot({ path: file, fullPage: true });
      screenshot = path.relative(path.resolve(__dirname, "../../.."), file).replace(/\\/g, "/");
    } catch { /* ignore */ }
  }

  recordFinding({
    scenario: name,
    route,
    consoleErrors,
    pageErrors,
    networkFailures,
    uxIssues,
    screenshot,
    status,
    durationMs: Date.now() - start,
  });
}

test.describe.configure({ mode: "serial" });

test.describe("HUMAN TESTER — wejście do systemu", () => {
  test("landing /", async ({ page }) => {
    await runScenario(page, "landing_root", "/", async (p) => {
      const issues: string[] = [];
      const heading = p.locator("h1, h2").first();
      if (!(await heading.isVisible({ timeout: 4_000 }).catch(() => false))) {
        issues.push("No visible heading on landing");
      }
      return issues;
    });
  });

  test("overview loads", async ({ page }) => {
    await runScenario(page, "overview_dashboard", "/overview", async (p) => {
      const issues: string[] = [];
      const navCount = await p.locator("nav a, aside a").count();
      if (navCount < 5) issues.push(`Sidebar has only ${navCount} links (expected >=5)`);
      return issues;
    });
  });
});

test.describe("HUMAN TESTER — moduły AEIS", () => {
  const AEIS_ROUTES = [
    "/agents", "/modules", "/governance", "/evidence", "/evidence-spine",
    "/decisions", "/health", "/contracts", "/performance", "/devices",
    "/costs", "/sdr", "/cellular", "/rebuild", "/autonomy", "/lifecycle",
    "/skills", "/book", "/projects", "/idea-vault",
    "/anomalies", "/audit", "/budget", "/bundles", "/capacity",
    "/circuits", "/connectors", "/drift", "/evaluator", "/gates",
    "/golden-tests", "/healing", "/integrations", "/notifications",
    "/pipeline", "/risk", "/roles", "/secrets", "/security-scan",
    "/sla", "/workspace",
  ];

  for (const route of AEIS_ROUTES) {
    test(`module ${route}`, async ({ page }) => {
      await runScenario(page, `module_${route.replace(/\//g, "_")}`, route);
    });
  }
});

test.describe("HUMAN TESTER — błędy i edge cases", () => {
  test("404 nieistniejąca strona", async ({ page }) => {
    // The response status for a 404 route is 404 by design — that's normal and logs a
    // "Failed to load resource" in the browser. We only check that the custom 404 UI renders.
    const start = Date.now();
    const pageErrors: string[] = [];
    const uxIssues: string[] = [];
    page.on("pageerror", (err) => {
      if (err.message.includes("Hydration failed")) return;
      pageErrors.push(err.message.slice(0, 500));
    });
    let status: "PASS" | "FAIL" = "PASS";
    let screenshot: string | undefined;
    try {
      await page.goto("/this-page-does-not-exist-xyz", { waitUntil: "domcontentloaded", timeout: 20_000 });
      await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
      const hasNotFound = await page.locator("text=/404|not found|nie znalez/i").count();
      if (hasNotFound === 0) uxIssues.push("No 404 message shown for missing route");
    } catch (e: any) {
      status = "FAIL";
      uxIssues.push(`Exception: ${e?.message?.slice(0, 300) ?? String(e)}`);
    }
    if (pageErrors.length || uxIssues.length) {
      status = "FAIL";
      const file = path.join(ARTIFACTS_DIR, "not_found_page.png");
      try {
        await page.screenshot({ path: file, fullPage: true });
        screenshot = path.relative(path.resolve(__dirname, "../../.."), file).replace(/\\/g, "/");
      } catch { /* ignore */ }
    }
    recordFinding({
      scenario: "not_found_page",
      route: "/this-page-does-not-exist-xyz",
      consoleErrors: [],
      pageErrors,
      networkFailures: [],
      uxIssues,
      screenshot,
      status,
      durationMs: Date.now() - start,
    });
  });

  test("odświeżenie strony głębokiej", async ({ page }) => {
    const start = Date.now();
    const pageErrors: string[] = [];
    const uxIssues: string[] = [];
    page.on("pageerror", (err) => {
      if (err.message.includes("Hydration failed")) return;
      pageErrors.push(err.message.slice(0, 500));
    });
    let status: "PASS" | "FAIL" = "PASS";
    let screenshot: string | undefined;
    try {
      await page.goto("/governance", { waitUntil: "domcontentloaded", timeout: 20_000 });
      await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
      await page.reload({ waitUntil: "domcontentloaded", timeout: 20_000 });
      await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
      const h1 = await page.locator("h1").count();
      if (h1 === 0) uxIssues.push("No <h1> after deep page reload");
    } catch (e: any) {
      status = "FAIL";
      uxIssues.push(`Exception: ${e?.message?.slice(0, 300) ?? String(e)}`);
    }
    if (pageErrors.length || uxIssues.length) {
      status = "FAIL";
      const file = path.join(ARTIFACTS_DIR, "deep_page_reload.png");
      try {
        await page.screenshot({ path: file, fullPage: true });
        screenshot = path.relative(path.resolve(__dirname, "../../.."), file).replace(/\\/g, "/");
      } catch { /* ignore */ }
    }
    recordFinding({
      scenario: "deep_page_reload",
      route: "/governance",
      consoleErrors: [],
      pageErrors,
      networkFailures: [],
      uxIssues,
      screenshot,
      status,
      durationMs: Date.now() - start,
    });
  });
});

test.describe("HUMAN TESTER — brak backendu (symulacja)", () => {
  test("strona pokazuje banner offline przy zablokowanym API", async ({ page, context }) => {
    // Block all backend calls (API + /health) to simulate full outage.
    await context.route(/localhost:8000/, (r) => r.abort());

    const start = Date.now();
    const pageErrors: string[] = [];
    const uxIssues: string[] = [];
    page.on("pageerror", (err) => {
      if (err.message.includes("Hydration failed")) return;
      pageErrors.push(err.message.slice(0, 500));
    });

    let status: "PASS" | "FAIL" = "PASS";
    let screenshot: string | undefined;
    try {
      await page.goto("/overview", { waitUntil: "domcontentloaded", timeout: 20_000 });
      await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

      const body = await page.locator("body").isVisible();
      if (!body) uxIssues.push("Body hidden when API blocked");
      const text = await page.textContent("body");
      if (!text || text.trim().length < 20) uxIssues.push("Page appears blank when API blocked");

      const banner = page.locator("text=/Backend offline|API niedostępne|offline/i");
      const bannerVisible = await banner.first().isVisible({ timeout: 5_000 }).catch(() => false);
      if (!bannerVisible) uxIssues.push("No offline banner shown when API blocked");
    } catch (e: any) {
      status = "FAIL";
      uxIssues.push(`Exception: ${e?.message?.slice(0, 300) ?? String(e)}`);
    }

    if (pageErrors.length || uxIssues.length) {
      status = "FAIL";
      const file = path.join(ARTIFACTS_DIR, "api_blocked_overview.png");
      try {
        await page.screenshot({ path: file, fullPage: true });
        screenshot = path.relative(path.resolve(__dirname, "../../.."), file).replace(/\\/g, "/");
      } catch { /* ignore */ }
    }

    recordFinding({
      scenario: "api_blocked_overview",
      route: "/overview",
      consoleErrors: [],
      pageErrors,
      networkFailures: [],
      uxIssues,
      screenshot,
      status,
      durationMs: Date.now() - start,
    });

    await context.unroute(/localhost:8000/);
  });
});

test.describe("HUMAN TESTER — mobile viewport", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("mobile overview", async ({ page }) => {
    await runScenario(page, "mobile_overview", "/overview", async (p) => {
      const issues: string[] = [];
      // Check for horizontal overflow
      const overflow = await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4);
      if (overflow) issues.push("Horizontal scroll / layout overflow on mobile");
      return issues;
    });
  });
  test("mobile modules", async ({ page }) => {
    await runScenario(page, "mobile_modules", "/modules");
  });
});

test.describe("HUMAN TESTER — role / sekcje", () => {
  const ROLE_ROUTES = [
    { name: "operator", route: "/overview" },
    { name: "auditor", route: "/audit" },
    { name: "governance", route: "/governance" },
    { name: "security", route: "/security-scan" },
  ];
  for (const r of ROLE_ROUTES) {
    test(`role ${r.name}`, async ({ page }) => {
      await runScenario(page, `role_${r.name}`, r.route);
    });
  }
});

test.afterAll(async () => {
  const reportPath = path.resolve(__dirname, "../../../docs/production/HUMAN_TEST_REPORT.md");
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });

  const total = FINDINGS.length;
  const passed = FINDINGS.filter((f) => f.status === "PASS").length;
  const failed = total - passed;
  const now = new Date().toISOString();

  const lines: string[] = [];
  lines.push("# HUMAN TEST REPORT — SYLION AEIS");
  lines.push("");
  lines.push(`- **Generated:** ${now}`);
  lines.push(`- **Tester:** QA + HUMAN TESTER (Playwright)`);
  lines.push(`- **Frontend:** http://localhost:3000`);
  lines.push(`- **Backend:** http://localhost:8000`);
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`| Scenarios | Passed | Failed |`);
  lines.push(`|-----------|-------:|-------:|`);
  lines.push(`| ${total} | ${passed} | ${failed} |`);
  lines.push("");

  const failures = FINDINGS.filter((f) => f.status === "FAIL");
  if (failures.length) {
    lines.push("## ❌ Failures — wymaga działania BACKEND/FRONTEND");
    lines.push("");
    for (const f of failures) {
      lines.push(`### ${f.scenario} — \`${f.route ?? ""}\``);
      if (f.consoleErrors.length) {
        lines.push(`**Console errors (${f.consoleErrors.length}):**`);
        for (const e of f.consoleErrors.slice(0, 5)) lines.push(`- \`${e}\``);
      }
      if (f.pageErrors.length) {
        lines.push(`**Page errors (${f.pageErrors.length}):**`);
        for (const e of f.pageErrors.slice(0, 5)) lines.push(`- \`${e}\``);
      }
      if (f.networkFailures.length) {
        lines.push(`**Network failures (${f.networkFailures.length}):**`);
        for (const e of f.networkFailures.slice(0, 8)) lines.push(`- \`${e}\``);
      }
      if (f.uxIssues.length) {
        lines.push(`**UX issues:**`);
        for (const e of f.uxIssues) lines.push(`- ${e}`);
      }
      if (f.screenshot) lines.push(`**Screenshot:** \`${f.screenshot}\``);
      lines.push("");
    }
  } else {
    lines.push("## ✅ Wszystkie scenariusze PASS");
    lines.push("");
  }

  lines.push("## Wszystkie scenariusze");
  lines.push("");
  lines.push("| Status | Scenario | Route | Time |");
  lines.push("|--------|----------|-------|-----:|");
  for (const f of FINDINGS) {
    const badge = f.status === "PASS" ? "✅ PASS" : "❌ FAIL";
    lines.push(`| ${badge} | ${f.scenario} | \`${f.route ?? ""}\` | ${f.durationMs}ms |`);
  }
  lines.push("");

  // Preserve any existing HUMAN FLOWS section so parallel/sequential runs don't clobber it.
  let preservedFlows = "";
  if (fs.existsSync(reportPath)) {
    const prior = fs.readFileSync(reportPath, "utf8");
    const marker = "\n---\n\n# HUMAN FLOWS — interactive journeys";
    const idx = prior.indexOf(marker);
    if (idx !== -1) preservedFlows = prior.slice(idx);
  }

  fs.writeFileSync(reportPath, lines.join("\n") + preservedFlows, "utf8");
   
  console.log(`[HUMAN-TEST] Report written: ${reportPath}`);
});
