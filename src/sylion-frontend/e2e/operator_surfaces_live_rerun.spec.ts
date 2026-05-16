import { expect, test, type Page } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";
const ALT_API_BASE_URL = API_BASE_URL.includes("127.0.0.1")
  ? API_BASE_URL.replace("127.0.0.1", "localhost")
  : API_BASE_URL.replace("localhost", "127.0.0.1");

type SurfaceDefinition = {
  path: string;
  heading: string | RegExp;
  contentHint: string | RegExp;
  apiHints: string[];
  forbiddenTexts?: Array<string | RegExp>;
};

function attachRuntimeMonitors(page: Page) {
  const consoleErrors: string[] = [];
  const networkErrors: string[] = [];
  const requestUrls: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  page.on("request", (request) => {
    requestUrls.push(request.url());
  });

  page.on("response", (response) => {
    if (response.status() >= 400) {
      const url = response.url();
      if (url.startsWith(BASE_URL) || url.startsWith(API_BASE_URL)) {
        networkErrors.push(`${response.request().method()} ${response.status()} ${url}`);
      }
    }
  });

  return { consoleErrors, networkErrors, requestUrls };
}

async function expectHintVisible(page: Page, hint: string | RegExp) {
  if (typeof hint === "string") {
    await expect(page.getByText(hint, { exact: false }).first()).toBeVisible();
    return;
  }
  await expect(page.getByText(hint).first()).toBeVisible();
}

async function expectHeadingVisible(page: Page, heading: string | RegExp) {
  if (typeof heading === "string") {
    await expect(page.getByRole("heading", { name: heading, exact: false }).first()).toBeVisible();
    return;
  }
  await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
}

async function verifySurface(page: Page, surface: SurfaceDefinition) {
  const monitor = attachRuntimeMonitors(page);

  await page.goto(`${BASE_URL}${surface.path}`, { waitUntil: "networkidle" });
  await expectHeadingVisible(page, surface.heading);
  await expectHintVisible(page, surface.contentHint);

  for (const forbidden of surface.forbiddenTexts ?? []) {
    if (typeof forbidden === "string") {
      await expect(page.getByText(forbidden, { exact: false })).toHaveCount(0);
    } else {
      await expect(page.getByText(forbidden)).toHaveCount(0);
    }
  }

  const apiUrls = monitor.requestUrls.filter(
    (url) => url.startsWith(API_BASE_URL) || url.startsWith(ALT_API_BASE_URL),
  );
  expect(apiUrls.length).toBeGreaterThan(0);
  expect(
    surface.apiHints.some((apiHint) => apiUrls.some((url) => url.includes(apiHint))),
  ).toBeTruthy();

  expect(monitor.networkErrors).toEqual([]);
  expect(monitor.consoleErrors).toEqual([]);
}

const STATIC_SURFACES: SurfaceDefinition[] = [
  {
    path: "/auth",
    heading: "Authentication",
    contentHint: "Operator access, bootstrap and session state",
    apiHints: ["/health", "/api/v1/auth/status", "/api/v1/auth/providers", "/api/v1/auth/sessions"],
    forbiddenTexts: ["Backend not reachable"],
  },
  {
    path: "/settings",
    heading: "Settings",
    contentHint: "API keys, model hierarchy, council configuration",
    apiHints: ["/health", "/api/v1/workspace/settings/keys", "/api/v1/workspace/settings/hierarchies", "/api/v1/workspace/settings/council-members"],
    forbiddenTexts: ["Backend not reachable"],
  },
  {
    path: "/health",
    heading: "System Health",
    contentHint: "Live monitoring and diagnostics",
    apiHints: ["/health"],
  },
  {
    path: "/notifications",
    heading: "Notifications",
    contentHint: "Workspace notification feed with real unread and acknowledgment state",
    apiHints: ["/health", "/api/v1/notifications", "/api/v1/workspace/notifications/workspace-default/unread-count"],
    forbiddenTexts: ["Backend Not Reachable"],
  },
  {
    path: "/costs",
    heading: "Cost Dashboard",
    contentHint: "Budget monitoring and spending analytics",
    apiHints: ["/health", "/api/v1/monitoring/budget", "/api/v1/monitoring/budget/summary"],
    forbiddenTexts: ["Backend not reachable"],
  },
  {
    path: "/events",
    heading: "Event Backbone",
    contentHint: "Pub/sub health, catalog & event stream",
    apiHints: ["/health", "/api/v1/event-backbone/health", "/api/v1/event-backbone/catalog", "/api/v1/event-backbone/events"],
  },
  {
    path: "/skills",
    heading: "Skill Registry",
    contentHint: /Skill Registry|No skills registered yet\./,
    apiHints: ["/health", "/api/v1/skills/skills", "/api/v1/skills/executions"],
  },
  {
    path: "/workspace",
    heading: "AI Workspace",
    contentHint: /Thinking Layer \+ Working Layer|No pipeline runs yet\. Submit an idea above\./,
    apiHints: ["/health", "/api/v1/workspace/sessions", "/api/v1/workspace/settings/runtime/llm", "/api/v1/pipeline/runs"],
  },
  {
    path: "/builds",
    heading: "Build Factory",
    contentHint: /Candidate builds, validation & drift detection|No candidate builds yet/,
    apiHints: ["/health", "/api/v1/integration/builds", "/api/v1/integration/drift", "/api/v1/integration/drift/summary"],
  },
  {
    path: "/deploy",
    heading: "Deploy",
    contentHint: /Operator surface for real launched artifacts and deployment bundles|No deployable artifacts are ready yet\./,
    apiHints: ["/health", "/api/v1/deploy/summary", "/api/v1/deploy/topologies"],
  },
  {
    path: "/build-state",
    heading: /Build State|No build-state records yet|Build state unavailable/i,
    contentHint: /No build-state records yet|Recent Alerts|Build State/i,
    apiHints: ["/health", "/api/v1/build-state"],
    forbiddenTexts: ["Backend offline"],
  },
  {
    path: "/agents",
    heading: "AEIS Agents",
    contentHint: /Some agent telemetry is unavailable|Self-observation data unavailable|AEIS Agents/,
    apiHints: ["/health", "/api/v1/aeis/explanations", "/api/v1/aeis/improvements", "/api/v1/monitoring/preservation", "/api/v1/aeis/autonomy/status"],
  },
  {
    path: "/overview",
    heading: "SYLION AEIS",
    contentHint: /Idea Vault|Decision Gates|Module Categories|Governance/i,
    apiHints: ["/health", "/api/v1/core/modules", "/api/v1/governance/gates"],
    forbiddenTexts: ["Backend not reachable"],
  },
  {
    path: "/idea-vault",
    heading: "Idea Vault",
    contentHint: /Submit ideas, execute through the AEIS pipeline|Your Idea Vault is empty/i,
    apiHints: ["/health", "/api/v1/workspace/ideas", "/api/v1/pipeline/runs"],
    forbiddenTexts: ["Backend not reachable"],
  },
  {
    path: "/rebuild",
    heading: /Rebuild & Cutover/i,
    contentHint: /Rebuild|Cutover|Bundle|Shadow/i,
    apiHints: ["/health", "/api/v1/rebuild/orchestrator/plans", "/api/v1/rebuild/lpw", "/api/v1/rebuild/cutover/plans", "/api/v1/core/modules"],
  },
  {
    path: "/devices",
    heading: "Device Management",
    contentHint: /Device Registry|Device discovery, registry, artifact deployment, and on-device testing/i,
    apiHints: ["/health", "/api/v1/devices/discovery", "/api/v1/devices/registry", "/api/v1/deployments", "/api/v1/devices/tests"],
    forbiddenTexts: ["Backend not reachable"],
  },
  {
    path: "/contracts",
    heading: "Contract Registry",
    contentHint: /Compatibility|Producer|Contract/i,
    apiHints: ["/health", "/api/v1/core/contracts"],
  },
  {
    path: "/lifecycle",
    heading: "Module Lifecycle",
    contentHint: /Autonomy|Lifecycle Transition Gates|Draft|Cutover|Stable/i,
    apiHints: ["/health", "/api/v1/aeis/autonomy/status", "/api/v1/aeis/autonomy/stages", "/api/v1/governance/lifecycle/stages", "/api/v1/governance/lifecycle/entries", "/api/v1/governance/gates", "/api/v1/core/modules"],
  },
  {
    path: "/book",
    heading: "Quality & Knowledge",
    contentHint: /Golden sets, regressions, kanon, and self-model|Regression|Self-model|Kanon/i,
    apiHints: ["/health", "/api/v1/quality/golden-sets", "/api/v1/quality/regression/alerts", "/api/v1/memory/kanon/sections", "/api/v1/memory/self-model"],
    forbiddenTexts: ["Backend not reachable"],
  },
  {
    path: "/budget",
    heading: "Model Budget",
    contentHint: /Spending limits and cost tracking|Budget Alerts|Budget/i,
    apiHints: ["/health", "/api/v1/monitoring/budget", "/api/v1/monitoring/budget/summary", "/api/v1/efficiency/cost/alerts"],
    forbiddenTexts: ["Backend not reachable"],
  },
];

test.describe("operator surfaces live rerun", () => {
  for (const surface of STATIC_SURFACES) {
    test(`${surface.path} loads from live backend without false offline/demo state`, async ({ page }) => {
      await verifySurface(page, surface);
    });
  }

  test("/projects list and first detail page render against live backend data", async ({ page, request }) => {
    const listResponse = await request.get(`${API_BASE_URL}/api/v1/projects`);
    expect(listResponse.ok()).toBeTruthy();
    const payload = (await listResponse.json()) as { projects?: Array<Record<string, unknown>> };
    const projects = payload.projects ?? [];

    await verifySurface(page, {
      path: "/projects",
      heading: "Project Tracker",
      contentHint: "Milestones, dependencies, and execution phases",
      apiHints: ["/health", "/api/v1/projects"],
      forbiddenTexts: ["Backend not reachable"],
    });

    expect(projects.length, "No live projects are currently recorded in the backend.").toBeGreaterThan(0);
    const firstProjectId = String(projects[0]?.project_id ?? "");
    const firstTitle = String(projects[0]?.title ?? "");
    expect(firstProjectId).not.toBe("");

    const monitor = attachRuntimeMonitors(page);
    await page.goto(`${BASE_URL}/projects/${encodeURIComponent(firstProjectId)}`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: firstTitle || /.+/ }).first()).toBeVisible();
    await expect(
      page.getByText(/Timeline|Masterplan|Pending Questions|Cost Ledger/i).first(),
    ).toBeVisible();
    const apiUrls = monitor.requestUrls.filter(
      (url) => url.startsWith(API_BASE_URL) || url.startsWith(ALT_API_BASE_URL),
    );
    expect(apiUrls.length).toBeGreaterThan(0);
    expect(
      apiUrls.some((url) => url.includes(`/api/v1/projects/${firstProjectId}`)),
    ).toBeTruthy();
    expect(monitor.networkErrors).toEqual([]);
    expect(monitor.consoleErrors).toEqual([]);
  });
});
