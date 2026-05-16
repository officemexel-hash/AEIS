import { test, expect, Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

/**
 * HUMAN FLOWS — interactive user journeys beyond "just open the page".
 * Sidebar clicks, keyboard, forms, refresh, cross-page nav.
 * Appends results into the shared HUMAN_TEST_REPORT.md.
 */

const ARTIFACTS_DIR = path.resolve(__dirname, "../../../docs/production/human-test-artifacts");
fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
const REPORT_PATH = path.resolve(__dirname, "../../../docs/production/HUMAN_TEST_REPORT.md");

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

async function track(page: Page, scenario: string, route: string, body: (p: Page) => Promise<string[]>) {
  const start = Date.now();
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const networkFailures: string[] = [];
  const uxIssues: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const t = msg.text();
    if (t.includes("Hydration") || t.includes("favicon")) return;
    consoleErrors.push(t.slice(0, 500));
  });
  page.on("pageerror", (err) => {
    if (err.message.includes("Hydration failed")) return;
    pageErrors.push(err.message.slice(0, 500));
  });
  page.on("requestfailed", (req) => {
    const url = req.url();
    if (url.includes("favicon") || url.startsWith("data:")) return;
    const err = req.failure()?.errorText ?? "failed";
    // ERR_ABORTED is normal when user navigates before resource finishes loading.
    if (err.includes("ERR_ABORTED")) return;
    networkFailures.push(`${req.method()} ${url} — ${err}`);
  });
  page.on("response", (res) => {
    if (res.status() >= 500) networkFailures.push(`HTTP ${res.status()} ${res.url()}`);
  });

  let status: "PASS" | "FAIL" = "PASS";
  try {
    const issues = await body(page);
    uxIssues.push(...issues);
  } catch (e: any) {
    status = "FAIL";
    uxIssues.push(`Exception: ${e?.message?.slice(0, 300) ?? String(e)}`);
  }

  let screenshot: string | undefined;
  if (consoleErrors.length || pageErrors.length || networkFailures.length || uxIssues.length) {
    status = "FAIL";
    const file = path.join(ARTIFACTS_DIR, `${scenario}.png`);
    try {
      await page.screenshot({ path: file, fullPage: true });
      screenshot = path.relative(path.resolve(__dirname, "../../.."), file).replace(/\\/g, "/");
    } catch { /* ignore */ }
  }

  FINDINGS.push({
    scenario, route, consoleErrors, pageErrors, networkFailures,
    uxIssues, screenshot, status, durationMs: Date.now() - start,
  });
   
  console.log("[HUMAN-FLOWS]", status, scenario);
}

test.describe.configure({ mode: "serial" });

test.describe("HUMAN FLOWS — nawigacja w sidebar", () => {
  test("klik w 5 linków sidebar prowadzi do właściwej strony", async ({ page }) => {
    await track(page, "sidebar_click_navigation", "/overview", async (p) => {
      const issues: string[] = [];
      await p.goto("/overview", { waitUntil: "domcontentloaded", timeout: 20_000 });
      await p.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

      const targets = ["/agents", "/governance", "/health", "/skills", "/modules"];
      for (const href of targets) {
        const link = p.locator(`nav a[href="${href}"], aside a[href="${href}"]`).first();
        const visible = await link.isVisible({ timeout: 2_000 }).catch(() => false);
        if (!visible) {
          issues.push(`Sidebar link ${href} not visible`);
          continue;
        }
        await link.click();
        await p.waitForURL(`**${href}`, { timeout: 10_000 }).catch(() => {
          issues.push(`Navigation to ${href} did not update URL`);
        });
        await p.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => {});
        // h1 may render after loading skeleton resolves — wait up to 5s.
        const gotH1 = await p.locator("h1").first().waitFor({ state: "visible", timeout: 5_000 }).then(() => true).catch(() => false);
        if (!gotH1) issues.push(`${href} has no <h1> after click-nav`);
      }
      return issues;
    });
  });

  test("sidebar collapse/expand zachowuje strukturę", async ({ page }) => {
    await track(page, "sidebar_toggle", "/overview", async (p) => {
      const issues: string[] = [];
      await p.goto("/overview", { waitUntil: "domcontentloaded" });
      await p.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => {});
      const beforeCount = await p.locator("nav a, aside a").count();

      const toggle = p.locator("button[aria-label*=sidebar i], button[aria-label*=collapse i], button[aria-label*=menu i]").first();
      const hasToggle = await toggle.isVisible({ timeout: 2_000 }).catch(() => false);
      if (!hasToggle) return issues; // no toggle button — skip silently

      await toggle.click();
      await p.waitForTimeout(400);
      const afterCount = await p.locator("nav a, aside a").count();
      if (afterCount < beforeCount / 2) issues.push(`Sidebar lost links after collapse: ${beforeCount} → ${afterCount}`);

      await toggle.click();
      await p.waitForTimeout(400);
      return issues;
    });
  });
});

test.describe("HUMAN FLOWS — interakcja ze stroną", () => {
  test("back/forward history działa", async ({ page }) => {
    await track(page, "browser_history_nav", "/overview", async (p) => {
      const issues: string[] = [];
      await p.goto("/overview", { waitUntil: "domcontentloaded" });
      await p.goto("/agents", { waitUntil: "domcontentloaded" });
      await p.goBack({ waitUntil: "domcontentloaded", timeout: 10_000 });
      if (!p.url().endsWith("/overview")) issues.push(`goBack landed on ${p.url()} not /overview`);
      await p.goForward({ waitUntil: "domcontentloaded", timeout: 10_000 });
      if (!p.url().endsWith("/agents")) issues.push(`goForward landed on ${p.url()} not /agents`);
      return issues;
    });
  });

  test("keyboard Tab przechodzi przez interaktywne elementy", async ({ page }) => {
    await track(page, "keyboard_tab_focus", "/overview", async (p) => {
      const issues: string[] = [];
      await p.goto("/overview", { waitUntil: "domcontentloaded" });
      await p.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => {});
      const focusables: string[] = [];
      for (let i = 0; i < 5; i++) {
        await p.keyboard.press("Tab");
        const tag = await p.evaluate(() => {
          const el = document.activeElement;
          return el ? `${el.tagName}${el.getAttribute("href") ? "[href]" : ""}` : "";
        });
        focusables.push(tag);
      }
      const uniq = new Set(focusables.filter(Boolean));
      if (uniq.size < 2) issues.push(`Tab focus trapped — only ${uniq.size} unique focusable elements in 5 presses`);
      return issues;
    });
  });

  test("nagłówki stron są unikalne", async ({ page }) => {
    await track(page, "unique_page_titles", "/", async (p) => {
      const issues: string[] = [];
      const seen = new Map<string, string[]>();
      for (const r of ["/overview", "/agents", "/governance", "/devices", "/sdr"]) {
        await p.goto(r, { waitUntil: "domcontentloaded" });
        await p.waitForLoadState("networkidle", { timeout: 6_000 }).catch(() => {});
        const title = (await p.title()).trim();
        const h1 = (await p.locator("h1").first().textContent().catch(() => "")) ?? "";
        const key = `${title} | ${h1.trim()}`;
        const arr = seen.get(key) ?? [];
        arr.push(r);
        seen.set(key, arr);
      }
      for (const [key, routes] of seen) {
        if (routes.length > 1) issues.push(`Identical title/h1 "${key}" for routes: ${routes.join(", ")}`);
      }
      return issues;
    });
  });
});

test.describe("HUMAN FLOWS — rozszerzone moduły", () => {
  const EXTRA_ROUTES = [
    "/anomalies", "/audit", "/budget", "/bundles", "/capacity",
    "/circuits", "/connectors", "/drift", "/evaluator", "/gates",
    "/golden-tests", "/healing", "/integrations", "/notifications",
    "/pipeline", "/risk", "/roles", "/secrets", "/security-scan",
    "/sla", "/workspace", "/settings",
  ];

  for (const route of EXTRA_ROUTES) {
    test(`reload działa na ${route}`, async ({ page }) => {
      await track(page, `reload_${route.replace(/\//g, "_")}`, route, async (p) => {
        const issues: string[] = [];
        await p.goto(route, { waitUntil: "domcontentloaded", timeout: 20_000 });
        await p.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => {});
        const h1Before = await p.locator("h1").count();
        await p.reload({ waitUntil: "domcontentloaded", timeout: 20_000 });
        await p.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => {});
        const h1After = await p.locator("h1").count();
        if (h1Before > 0 && h1After === 0) issues.push(`<h1> disappeared after reload on ${route}`);
        return issues;
      });
    });
  }
});

test.afterAll(async () => {
  if (!FINDINGS.length) return;
  let md = fs.existsSync(REPORT_PATH) ? fs.readFileSync(REPORT_PATH, "utf8") : "# HUMAN TEST REPORT — SYLION AEIS\n\n";
  // Strip any prior FLOWS section so re-runs replace instead of appending.
  const marker = "\n---\n\n# HUMAN FLOWS — interactive journeys";
  const idx = md.indexOf(marker);
  if (idx !== -1) md = md.slice(0, idx);

  const total = FINDINGS.length;
  const passed = FINDINGS.filter((f) => f.status === "PASS").length;
  const failed = total - passed;

  const lines: string[] = [];
  lines.push("\n---\n");
  lines.push("# HUMAN FLOWS — interactive journeys");
  lines.push("");
  lines.push(`- **Generated:** ${new Date().toISOString()}`);
  lines.push("");
  lines.push("## Summary");
  lines.push("");
  lines.push(`| Scenarios | Passed | Failed |`);
  lines.push(`|-----------|-------:|-------:|`);
  lines.push(`| ${total} | ${passed} | ${failed} |`);
  lines.push("");

  const failures = FINDINGS.filter((f) => f.status === "FAIL");
  if (failures.length) {
    lines.push("## ❌ Failures");
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

  lines.push("## Wszystkie scenariusze (flows)");
  lines.push("");
  lines.push("| Status | Scenario | Route | Time |");
  lines.push("|--------|----------|-------|-----:|");
  for (const f of FINDINGS) {
    const badge = f.status === "PASS" ? "✅ PASS" : "❌ FAIL";
    lines.push(`| ${badge} | ${f.scenario} | \`${f.route ?? ""}\` | ${f.durationMs}ms |`);
  }

  md += lines.join("\n");
  fs.writeFileSync(REPORT_PATH, md, "utf8");
   
  console.log(`[HUMAN-FLOWS] Report appended: ${REPORT_PATH}`);
});
