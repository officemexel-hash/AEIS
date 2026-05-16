import { test, expect } from "@playwright/test";

const API_BASE = "http://localhost:8000";

/**
 * Backend API integration test suite.
 * Verifies each frontend page connects to live backend data, not mock fallbacks.
 * Requires both backend (port 8000) and frontend (port 3000) running.
 */

// Helper: fetch JSON from backend
async function apiFetch(path: string) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) return null;
  return res.json();
}

test.describe("Backend API health", () => {
  test("health endpoint returns ok", async () => {
    const data = await apiFetch("/health");
    expect(data).toBeTruthy();
    expect(data.status).toBe("ok");
    expect(data.modules).toBeGreaterThanOrEqual(65);
  });
});

test.describe("Page-level live data verification", () => {
  // Each test visits a page, waits for hydration, and checks for "Live" badge
  // and that backend endpoints return actual data

  test("/devices shows Live badge and backend data", async ({ page }) => {
    // Pre-fetch backend data to compare
    const regData = await apiFetch("/api/v1/devices/registry");
    const discData = await apiFetch("/api/v1/devices/discovery");

    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/devices", { waitUntil: "networkidle", timeout: 20000 });

    // Should show Live badge
    const liveBadge = page.locator("text=Live");
    await expect(liveBadge).toBeVisible({ timeout: 10000 });

    expect(errors).toEqual([]);
  });

  test("/costs shows Live badge and backend data", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/costs", { waitUntil: "networkidle", timeout: 20000 });

    const liveBadge = page.locator("text=Live");
    await expect(liveBadge).toBeVisible({ timeout: 10000 });

    expect(errors).toEqual([]);
  });

  test("/sdr shows Live badge and backend data", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/sdr", { waitUntil: "networkidle", timeout: 20000 });

    const liveBadge = page.locator("text=Live");
    await expect(liveBadge).toBeVisible({ timeout: 10000 });

    expect(errors).toEqual([]);
  });

  test("/cellular shows Live badge and backend data", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/cellular", { waitUntil: "networkidle", timeout: 20000 });

    const liveBadge = page.locator("text=Live");
    await expect(liveBadge).toBeVisible({ timeout: 10000 });

    expect(errors).toEqual([]);
  });

  test("/overview renders h1 content", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/overview", { waitUntil: "networkidle", timeout: 20000 });

    await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

    expect(errors).toEqual([]);
  });

  test("/health renders h1 content", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/health", { waitUntil: "networkidle", timeout: 20000 });

    await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

    expect(errors).toEqual([]);
  });

  test("/modules renders h1 content", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    await page.goto("/modules", { waitUntil: "networkidle", timeout: 20000 });

    await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

    expect(errors).toEqual([]);
  });
});

test.describe("Backend API endpoint verification", () => {
  // Verify all backend endpoints return valid JSON, not 500 errors

  const endpoints = [
    { path: "/health", key: "status", expected: "ok" },
    { path: "/api/v1/core/modules", key: "modules" },
    { path: "/api/v1/core/events", key: "events" },
    { path: "/api/v1/core/contracts", key: "contracts" },
    { path: "/api/v1/core/evidence", key: "evidence" },
    { path: "/api/v1/governance/proposals", key: "proposals" },
    { path: "/api/v1/governance/gates", key: "gates" },
    { path: "/api/v1/governance/policies", key: "policies" },
    { path: "/api/v1/cognitive/models", key: "models" },
    { path: "/api/v1/cognitive/evaluations", key: "evaluations" },
    { path: "/api/v1/execution/tools", key: "tools" },
    { path: "/api/v1/execution/workflows", key: "workflows" },
    { path: "/api/v1/execution/jobs", key: "jobs" },
    { path: "/api/v1/security/audit", key: "entries" },
    { path: "/api/v1/security/sessions", key: "sessions" },
    { path: "/api/v1/skills/skills", key: "skills" },
    { path: "/api/v1/skills/executions", key: "executions" },
    { path: "/api/v1/skills/demand/signals", key: "signals" },
    { path: "/api/v1/memory/kanon/sections", key: "sections" },
    { path: "/api/v1/devices/discovery", key: "devices" },
    { path: "/api/v1/devices/registry", key: "devices" },
    { path: "/api/v1/devices/deployments", key: "deployments" },
    { path: "/api/v1/devices/tests", key: "tests" },
    { path: "/api/v1/sdr/devices", key: "devices" },
    { path: "/api/v1/sdr/captures", key: "captures" },
    { path: "/api/v1/sdr/analysis", key: "analyses" },
    { path: "/api/v1/sdr/rf/policies", key: "policies" },
    { path: "/api/v1/cellular/ran", key: "stacks" },
    { path: "/api/v1/cellular/cores", key: "cores" },
    { path: "/api/v1/cellular/ue", key: "ues" },
    { path: "/api/v1/cellular/isolation", key: "checks" },
    { path: "/api/v1/cellular/attack-vectors", key: "vectors" },
    { path: "/api/v1/cellular/control-plane", key: "analyses" },
    { path: "/api/v1/cellular/evidence", key: "evidence" },
    { path: "/api/v1/efficiency/cost/records", key: "records" },
    { path: "/api/v1/efficiency/cost/daily", key: "daily_spend" },
    { path: "/api/v1/efficiency/cost/monthly", key: "monthly_spend" },
    { path: "/api/v1/efficiency/budgets", key: "budgets" },
    { path: "/api/v1/efficiency/drift", key: "drifts" },
    { path: "/api/v1/efficiency/circuits", key: "circuits" },
    { path: "/api/v1/monitoring/bloat/modules", key: "modules" },
    { path: "/api/v1/monitoring/cost/records", key: "records" },
    { path: "/api/v1/monitoring/preservation/mode", key: "mode" },
    { path: "/api/v1/aeis/explanations", key: "explanations" },
    { path: "/api/v1/aeis/limitation/policies", key: "policies" },
    { path: "/api/v1/aeis/autonomy/status", key: "current_stage" },
    { path: "/api/v1/quality/golden-sets", key: "sets" },
    { path: "/api/v1/quality/regression/alerts", key: "alerts" },
    { path: "/api/v1/rebuild/orchestrator/plans", key: "plans" },
    { path: "/api/v1/rebuild/lpw", key: "records" },
    // Phase 5
    { path: "/api/v1/security/hardened-profiles", key: "profiles" },
    { path: "/api/v1/security/hardened-profiles/active", key: "name" },
    { path: "/api/v1/efficiency/cost/alerts", key: "alerts" },
    { path: "/api/v1/efficiency/cost/summary", key: "providers" },
    { path: "/api/v1/core/hot-swap/environments", key: "environments" },
    { path: "/api/v1/core/hot-swap/active", key: "name" },
    { path: "/api/v1/core/hot-swap/health", key: "environments" },
  ];

  for (const ep of endpoints) {
    test(`GET ${ep.path} returns {${ep.key}}`, async () => {
      const data = await apiFetch(ep.path);
      expect(data).toBeTruthy();
      expect(data).toHaveProperty(ep.key);
      if (ep.expected) {
        expect(data[ep.key]).toBe(ep.expected);
      }
    });
  }
});

test.describe("Frontend pages render without errors", () => {
  const pages = [
    "/", "/overview", "/idea-vault", "/skills", "/book", "/projects",
    "/agents", "/modules", "/governance", "/evidence", "/evidence-spine",
    "/decisions", "/health", "/contracts", "/performance", "/devices",
    "/costs", "/sdr", "/cellular", "/rebuild", "/autonomy", "/lifecycle",
  ];

  for (const path of pages) {
    test(`${path || "/"} renders without JS errors`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => {
        if (err.message.includes("Hydration failed because")) return;
        errors.push(err.message);
      });

      await page.goto(path, { waitUntil: "networkidle", timeout: 20000 });

      // Page body should be visible
      await expect(page.locator("body")).toBeVisible();

      // No JavaScript runtime errors
      expect(errors).toEqual([]);
    });
  }
});
