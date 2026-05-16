import { expect, test, type APIRequestContext } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

async function resetWorkers(request: APIRequestContext) {
  const response = await request.get(`${API_BASE_URL}/api/v1/workers`);
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  for (const worker of payload.workers ?? []) {
    const deleteResponse = await request.delete(
      `${API_BASE_URL}/api/v1/workers/${encodeURIComponent(worker.worker_id)}`,
    );
    expect([204, 404]).toContain(deleteResponse.status());
  }
}

test.describe("workers live flow", () => {
  test.beforeEach(async ({ request }) => {
    await resetWorkers(request);
  });

  test.afterEach(async ({ request }) => {
    await resetWorkers(request);
  });

  test("registers, heartbeats and deletes a worker without console or network errors", async ({ page, request }) => {
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

    await page.goto(`${BASE_URL}/workers`, { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Worker Fleet" })).toBeVisible();
    await expect(page.getByText("No workers registered")).toBeVisible();

    await page.getByRole("button", { name: "Register first worker" }).click();
    await page.getByRole("textbox", { name: "Worker name" }).fill("QA Worker Alpha");
    await page.getByRole("textbox", { name: "Tags (comma sep)" }).fill("qa,local");
    await page.getByRole("button", { name: "Register", exact: true }).click();

    await expect(page.getByText("QA Worker Alpha")).toBeVisible();
    await expect(page.getByText(/20\d{2}-\d{2}-\d{2} \d{2}:\d{2}/).first()).toBeVisible();
    await expect(page.getByText("1970")).toHaveCount(0);

    const beforeHeartbeat = await request.get(`${API_BASE_URL}/api/v1/workers`);
    const beforePayload = await beforeHeartbeat.json();
    expect(beforePayload.workers).toHaveLength(1);
    const workerId = beforePayload.workers[0].worker_id as string;
    const previousHeartbeat = Number(beforePayload.workers[0].last_heartbeat ?? 0);

    await page.getByText("QA Worker Alpha").first().click();
    await page.getByRole("button", { name: "Heartbeat" }).click();

    await expect
      .poll(async () => {
        const response = await request.get(`${API_BASE_URL}/api/v1/workers`);
        const payload = await response.json();
        return Number(payload.workers[0]?.last_heartbeat ?? 0);
      })
      .toBeGreaterThan(previousHeartbeat);

    await expect(page.getByText("1970")).toHaveCount(0);

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Delete" }).click();

    await expect(page.getByText("No workers registered")).toBeVisible();
    const finalWorkers = await request.get(`${API_BASE_URL}/api/v1/workers`);
    const finalPayload = await finalWorkers.json();
    expect(finalPayload.workers).toEqual([]);
    expect(networkErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
