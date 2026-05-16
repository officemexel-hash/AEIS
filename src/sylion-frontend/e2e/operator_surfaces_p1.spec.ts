import { test, expect, type Page, type Route } from "@playwright/test";

type ApiOverride = (route: Route, url: URL) => Promise<void> | void;

const runtimeReadyPayload = {
  ready: true,
  provider: "openai",
  model: "gpt-4o",
  base_url: "",
  runtime_source: "settings",
  active_key_providers: ["openai"],
  active_key_count: 1,
  ollama_models: [],
  reasons: [],
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function fulfillText(route: Route, body: string, status = 500) {
  await route.fulfill({
    status,
    contentType: "text/plain",
    body,
  });
}

async function mockOperatorSurfaceApi(page: Page, overrides: Record<string, ApiOverride> = {}) {
  await page.route("**/health", async (route) => {
    const url = new URL(route.request().url());
    const key = `${route.request().method()} ${url.pathname}`;
    const override = overrides[key];
    if (override) {
      await override(route, url);
      return;
    }
    await fulfillJson(route, {
      status: "ok",
      version: "test",
      modules: 0,
      endpoints: 0,
      db_mode: "memory",
    });
  });

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const key = `${route.request().method()} ${url.pathname}`;
    const override = overrides[key];
    if (override) {
      await override(route, url);
      return;
    }

    if (route.request().method() === "GET" && url.pathname === "/api/v1/core/modules") {
      await fulfillJson(route, { modules: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/governance/gates") {
      await fulfillJson(route, { gates: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/governance/decision-snapshots/timeline") {
      await fulfillJson(route, { timeline: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/governance/compliance/global") {
      await fulfillJson(route, { compliance: { score: 100 } });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/pipeline/runs") {
      await fulfillJson(route, { runs: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/workspace/settings/runtime/llm") {
      await fulfillJson(route, runtimeReadyPayload);
      return;
    }
    if (route.request().method() === "PUT" && url.pathname === "/api/v1/workspace/settings/runtime/llm") {
      await fulfillJson(route, runtimeReadyPayload);
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/workspace/ideas") {
      await fulfillJson(route, { ideas: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/workspace/ideas/stats") {
      await fulfillJson(route, { total: 0, by_status: {}, by_category: {} });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/workspace/settings/keys") {
      await fulfillJson(route, { keys: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/workspace/settings/hierarchies") {
      await fulfillJson(route, { hierarchies: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/workspace/settings/council-members") {
      await fulfillJson(route, { members: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/workspace/sessions") {
      await fulfillJson(route, {
        sessions: [{ session_id: "session-1", title: "Live Session" }],
      });
      return;
    }
    if (
      route.request().method() === "GET" &&
      /^\/api\/v1\/workspace\/sessions\/[^/]+\/messages$/.test(url.pathname)
    ) {
      await fulfillJson(route, { messages: [] });
      return;
    }
    if (route.request().method() === "POST" && url.pathname === "/api/v1/workspace/sessions") {
      await fulfillJson(route, { session_id: "session-1", title: "New Chat" });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/devices/registry") {
      await fulfillJson(route, { devices: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/devices/discovery") {
      await fulfillJson(route, { devices: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/deployments") {
      await fulfillJson(route, { deployments: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/devices/tests") {
      await fulfillJson(route, { tests: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/rebuild/orchestrator/plans") {
      await fulfillJson(route, { plans: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/rebuild/lpw") {
      await fulfillJson(route, { entries: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/rebuild/cutover/plans") {
      await fulfillJson(route, { plans: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/aeis/explanations") {
      await fulfillJson(route, { explanations: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/aeis/improvements") {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/monitoring/preservation") {
      await fulfillJson(route, {
        mode: "active",
        status: "healthy",
        metrics: {
          cpu_usage: 21,
          memory_usage: 33,
          event_throughput: 120,
          error_rate: 1.2,
          active_modules: 4,
          healthy_modules: 4,
        },
      });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/aeis/autonomy/status") {
      await fulfillJson(route, {
        status: {
          current_stage: "SUPERVISED",
          pending_approvals: 1,
          available_actions: 2,
          escalation_count: 0,
        },
      });
      return;
    }
    if (route.request().method() === "GET" && url.pathname === "/api/v1/build-state") {
      await fulfillJson(route, {
        workers: {},
        assignments: {},
        alerts: {},
        drift: {},
        contracts: {},
      });
      return;
    }

    await fulfillJson(route, {});
  });
}

function surfaceAlert(page: Page, text: string) {
  return page.getByRole("alert").filter({ hasText: text }).first();
}

test("overview keeps quick-submit input and stays on page after submit failure", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "POST /api/v1/workspace/ideas": (route) => fulfillText(route, "quick submit failed"),
  });

  await page.goto("/overview", { waitUntil: "networkidle" });

  const input = page.getByPlaceholder("Describe your idea...");
  await input.fill("Operator draft from overview");
  await page.getByRole("button", { name: /^Submit$/ }).click();

  await expect(page).toHaveURL(/\/overview$/);
  await expect(input).toHaveValue("Operator draft from overview");
  await expect(surfaceAlert(page, "Submission failed.")).toContainText("Submission failed.");
});

test("pipeline preserves idea and context after submit failure", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "POST /api/v1/pipeline/ideas": (route) => fulfillText(route, "pipeline submit failed"),
  });

  await page.goto("/pipeline", { waitUntil: "networkidle" });

  const ideaInput = page.getByPlaceholder("Describe what you want the pipeline to build, analyze, or generate...");
  const contextInput = page.getByPlaceholder('{"module": "evidence", "priority": "high"}');

  await ideaInput.fill("Pipeline draft that must survive an error");
  await contextInput.fill('{"operator":"persist"}');
  await page.getByRole("button", { name: "Submit to Pipeline" }).click();

  await expect(ideaInput).toHaveValue("Pipeline draft that must survive an error");
  await expect(contextInput).toHaveValue('{"operator":"persist"}');
  await expect(surfaceAlert(page, "Submission failed.")).toContainText("Submission failed.");
});

test("idea vault keeps text and attachments when upload fails", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "POST /api/v1/workspace/ideas/upload": (route) => fulfillText(route, "upload failed"),
  });

  await page.goto("/idea-vault", { waitUntil: "networkidle" });

  const textarea = page.getByPlaceholder("Describe your idea. What should the AEIS pipeline build, analyze, or generate? Be specific about the goal, scope, and expected output...");
  await textarea.fill("Idea vault draft with attachment");
  await page.locator('input[type="file"]').setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("attachment-body"),
  });

  await expect(page.getByText("notes.txt")).toBeVisible();
  await page.getByRole("button", { name: "Submit & Execute" }).click();

  await expect(textarea).toHaveValue("Idea vault draft with attachment");
  await expect(page.getByText("notes.txt", { exact: true })).toBeVisible();
  await expect(surfaceAlert(page, "Attachment upload failed")).toContainText("Attachment upload failed");
});

test("chat keeps message draft on send failure and exposes attachment CTA as unavailable", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "POST /api/v1/workspace/sessions/session-1/messages": (route) => fulfillText(route, "chat send failed"),
  });

  await page.goto("/workspace", { waitUntil: "networkidle" });

  await page.getByRole("button", { name: "Live Session" }).click();
  const attachmentButton = page.getByRole("button", { name: "Attachments not available yet" });
  await expect(attachmentButton).toBeDisabled();

  const textarea = page.getByPlaceholder("Type a message...");
  await textarea.fill("Keep this chat draft");
  await textarea.press("Enter");

  await expect(textarea).toHaveValue("Keep this chat draft");
  await expect(surfaceAlert(page, "Message failed to send.")).toContainText("Message failed to send.");
  await expect(page.getByText("Attachments are not available on this chat surface yet.")).toBeVisible();
});

test("rebuild and devices surface disabled unavailable CTAs instead of dead clicks", async ({ page }) => {
  await mockOperatorSurfaceApi(page);

  await page.goto("/rebuild", { waitUntil: "networkidle" });
  await expect(page.getByRole("button", { name: "Run CFT unavailable" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "LPW checkpoint unavailable" })).toBeDisabled();
  await expect(page.getByText("CFT and LPW execution triggers are not available on this surface yet.")).toBeVisible();

  await page.goto("/devices", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Tests" }).click();
  await expect(page.getByRole("button", { name: "Run Contract Tests unavailable" })).toBeDisabled();
  await expect(page.getByText("Contract test execution is not available on this surface yet.")).toBeVisible();
});

test("settings waits for health before showing offline state", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "GET /health": async (route) => {
      await page.waitForTimeout(600);
      await fulfillJson(route, {
        status: "ok",
        version: "test",
        modules: 0,
        endpoints: 0,
        db_mode: "memory",
      });
    },
  });

  await page.goto("/settings");

  await expect(page.getByText("Loading settings surface...")).toBeVisible();
  await expect(page.getByText("Backend not reachable")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
});

test("settings shows actionable error when API keys fail to load", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "GET /api/v1/workspace/settings/keys": (route) => fulfillText(route, "settings keys failed"),
  });

  await page.goto("/settings", { waitUntil: "networkidle" });

  await expect(surfaceAlert(page, "API keys unavailable")).toContainText("settings keys failed");
  await expect(page.getByText("API keys could not be loaded.")).toBeVisible();
});

test("build state shows API failure instead of rendering zeroed fake stats", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "GET /api/v1/build-state": (route) => fulfillText(route, "build state failed"),
  });

  await page.goto("/build-state", { waitUntil: "networkidle" });

  await expect(surfaceAlert(page, "Build state unavailable")).toContainText("build state failed");
  await expect(page.getByText("No build-state records yet")).toHaveCount(0);
});

test("agents surface marks missing telemetry as unavailable instead of inventing live data", async ({ page }) => {
  await mockOperatorSurfaceApi(page, {
    "GET /api/v1/monitoring/preservation": (route) => fulfillText(route, "self observation failed"),
    "GET /api/v1/aeis/autonomy/status": (route) => fulfillText(route, "autonomy status failed"),
  });

  await page.goto("/agents", { waitUntil: "networkidle" });

  await expect(surfaceAlert(page, "Some agent telemetry is unavailable")).toContainText("self observation failed");
  await expect(page.getByText("No live autonomy snapshot from backend")).toBeVisible();
  await expect(page.getByText("Self-observation feed not reported by backend")).toBeVisible();
  await page.getByRole("tab", { name: /Self-Observation/i }).click();
  await expect(page.getByText("Self-observation data unavailable")).toBeVisible();
});
