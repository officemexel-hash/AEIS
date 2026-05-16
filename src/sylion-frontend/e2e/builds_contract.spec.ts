import { expect, test, type Page, type Route } from "@playwright/test";

const apiHostPattern = /http:\/\/(localhost|127\.0\.0\.1):8000\/.*/;

type BuildPayload = {
  build_id: string;
  name: string;
  description: string;
  status: string;
  patch_ids: string[];
  module_ids: string[];
  created_at: number;
  updated_at: number;
  validation_results?: Record<string, unknown>;
  evidence_pack?: unknown;
  error_log?: string | null;
  metadata?: Record<string, unknown>;
};

async function fulfillJson(route: Route, status: number, payload: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

async function mockBuildsSurface(
  page: Page,
  options?: {
    builds?: BuildPayload[];
    buildsStatus?: number;
    drifts?: Record<string, unknown>[];
    driftSummary?: Record<string, unknown>;
  },
) {
  const requests: string[] = [];
  const builds = options?.builds ?? [];
  const drifts = options?.drifts ?? [];
  const driftSummary = options?.driftSummary ?? {
    total_open: drifts.length,
    by_type: {},
    by_severity: {},
  };

  await page.route(apiHostPattern, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    requests.push(`${request.method()} ${url.pathname}${url.search}`);

    if (url.pathname === "/health") {
      await fulfillJson(route, 200, { status: "ok", version: "test", modules: 1, endpoints: 1 });
      return;
    }

    if (url.pathname === "/api/v1/integration/builds" && request.method() === "GET") {
      await fulfillJson(route, options?.buildsStatus ?? 200, { builds });
      return;
    }

    if (url.pathname === "/api/v1/integration/drift" && request.method() === "GET") {
      await fulfillJson(route, 200, { drifts });
      return;
    }

    if (url.pathname === "/api/v1/integration/drift/summary" && request.method() === "GET") {
      await fulfillJson(route, 200, driftSummary);
      return;
    }

    if (url.pathname.startsWith("/api/v1/integrations/")) {
      await fulfillJson(route, 418, { detail: "wrong integration path" });
      return;
    }

    await fulfillJson(route, 404, { detail: `unmocked ${request.method()} ${url.pathname}` });
  });

  return requests;
}

test("builds page uses the singular integration endpoint and renders live data", async ({ page }) => {
  const requests = await mockBuildsSurface(page, {
    builds: [
      {
        build_id: "bld_live_001",
        name: "Live Build",
        description: "Candidate build",
        status: "ready",
        patch_ids: ["patch-1"],
        module_ids: ["core.worker", "core.integration"],
        created_at: 1_717_000_000,
        updated_at: 1_717_000_000,
        validation_results: {},
        evidence_pack: null,
        error_log: null,
        metadata: {},
      },
    ],
    drifts: [
      {
        drift_id: "drift_live_001",
        description: "Contract drift detected",
        source_module: "core.worker",
        target_module: "core.integration",
        severity: "warning",
        status: "open",
      },
    ],
  });
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/builds", { waitUntil: "networkidle", timeout: 20_000 });

  await expect(page.getByRole("heading", { name: "Build Factory" })).toBeVisible();
  await expect(page.getByText("Live Build")).toBeVisible();
  await expect(page.getByText("Contract drift detected")).toBeVisible();

  expect(requests.some((entry) => entry.includes("/api/v1/integration/builds?status="))).toBeTruthy();
  expect(requests.some((entry) => entry.includes("/api/v1/integrations/builds"))).toBeFalsy();
  expect(requests.some((entry) => entry.includes("/api/v1/integrations/drift"))).toBeFalsy();
  expect(pageErrors).toEqual([]);
});

test("builds page renders empty states when no build or drift data exists", async ({ page }) => {
  await mockBuildsSurface(page);

  await page.goto("/builds", { waitUntil: "networkidle", timeout: 20_000 });

  await expect(page.getByText("No candidate builds yet")).toBeVisible();
  await expect(page.getByText("No open drift detected.")).toBeVisible();
});

test("builds page renders a recoverable error state when the build list fails", async ({ page }) => {
  await mockBuildsSurface(page, { buildsStatus: 500 });

  await page.goto("/builds", { waitUntil: "networkidle", timeout: 20_000 });

  await expect(page.getByText("Build data unavailable")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry builds" })).toBeVisible();
});
