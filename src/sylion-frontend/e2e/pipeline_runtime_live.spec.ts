import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

test.describe("pipeline runtime live flow", () => {
  test("uses persisted backend runtime config and blocks stub-only UI", async ({ page, request }) => {
    const consoleErrors: string[] = [];
    const networkErrors: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    page.on("response", (response) => {
      if (response.status() >= 400) {
        const url = response.url();
        if (url.startsWith(BASE_URL) || url.startsWith(API_BASE_URL)) {
          networkErrors.push(`${response.request().method()} ${response.status()} ${url}`);
        }
      }
    });

    const runtimeResponse = await request.get(`${API_BASE_URL}/api/v1/workspace/settings/runtime/llm`);
    expect(runtimeResponse.ok()).toBeTruthy();
    const runtimePayload = (await runtimeResponse.json()) as {
      ollama_models?: string[];
    };
    const ollamaModels = runtimePayload.ollama_models ?? [];
    test.skip(ollamaModels.length === 0, "Local Ollama runtime is not available on this host.");

    const selectedModel = ollamaModels.includes("qwen3.5:latest") ? "qwen3.5:latest" : ollamaModels[0];
    const saveResponse = await request.put(`${API_BASE_URL}/api/v1/workspace/settings/runtime/llm`, {
      data: {
        provider: "ollama",
        model: selectedModel,
        base_url: "http://localhost:11434",
      },
    });
    expect(saveResponse.ok()).toBeTruthy();
    const savedPayload = (await saveResponse.json()) as {
      ready: boolean;
      provider: string;
      model: string;
    };
    expect(savedPayload.ready).toBeTruthy();
    expect(savedPayload.provider).toBe("ollama");
    expect(savedPayload.model).toBe(selectedModel);

    const suffix = Date.now().toString().slice(-6);
    const idea = `Pipeline runtime smoke ${suffix}`;

    await page.goto(`${BASE_URL}/pipeline`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Pipeline", exact: true })).toBeVisible();
    await expect(page.getByText("Execution Runtime")).toBeVisible();
    await expect(page.locator("option[value='stub']")).toHaveCount(0);
    await expect(page.getByText("READY", { exact: true })).toBeVisible();
    await expect(page.getByText("Runtime ready for live execution")).toBeVisible();

    await page.locator("textarea").first().fill(idea);
    await page.getByRole("button", { name: "Submit to Pipeline" }).click();

    await expect
      .poll(async () => {
        const response = await request.get(`${API_BASE_URL}/api/v1/pipeline/runs`);
        const payload = await response.json();
        return payload.runs.some((run: Record<string, unknown>) => String(run.idea ?? "") === idea);
      })
      .toBeTruthy();

    await expect(networkErrors).toEqual([]);
    await expect(consoleErrors).toEqual([]);
  });
});
