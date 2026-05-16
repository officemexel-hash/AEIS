import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";
const ALT_API_BASE_URL = API_BASE_URL.includes("127.0.0.1")
  ? API_BASE_URL.replace("127.0.0.1", "localhost")
  : API_BASE_URL.replace("localhost", "127.0.0.1");

test.describe("environments live flow", () => {
  test("loads deployments and workers from the backend API base without false live state", async ({ page, request }) => {
    const consoleErrors: string[] = [];
    const networkErrors: string[] = [];
    const requestUrls: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    page.on("request", (req) => {
      requestUrls.push(req.url());
    });

    page.on("response", (response) => {
      if (response.status() >= 400) {
        const url = response.url();
        if (url.startsWith(BASE_URL) || url.startsWith(API_BASE_URL) || url.startsWith(ALT_API_BASE_URL)) {
          networkErrors.push(`${response.request().method()} ${response.status()} ${url}`);
        }
      }
    });

    const deploymentsResponse = await request.get(`${API_BASE_URL}/api/v1/deployments`);
    const workersResponse = await request.get(`${API_BASE_URL}/api/v1/workers`);
    expect(deploymentsResponse.ok()).toBeTruthy();
    expect(workersResponse.ok()).toBeTruthy();
    const deploymentsPayload = await deploymentsResponse.json();
    const workersPayload = await workersResponse.json();

    await page.goto(`${BASE_URL}/environments`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Environments" })).toBeVisible();
    await expect(page.getByText("LIVE", { exact: true })).toBeVisible();
    await expect(page.getByText("DEGRADED", { exact: true })).toHaveCount(0);

    expect(
      requestUrls.some(
        (url) =>
          url.startsWith(`${API_BASE_URL}/api/v1/deployments`) ||
          url.startsWith(`${ALT_API_BASE_URL}/api/v1/deployments`),
      ),
    ).toBeTruthy();
    expect(
      requestUrls.some(
        (url) =>
          url.startsWith(`${API_BASE_URL}/api/v1/workers`) ||
          url.startsWith(`${ALT_API_BASE_URL}/api/v1/workers`),
      ),
    ).toBeTruthy();
    expect(requestUrls.some((url) => url.startsWith(`${BASE_URL}/api/v1/deployments`))).toBeFalsy();
    expect(requestUrls.some((url) => url.startsWith(`${BASE_URL}/api/v1/workers`))).toBeFalsy();

    if ((deploymentsPayload.deployments ?? []).length === 0) {
      await expect(page.getByText("No deployments registered.")).toBeVisible();
    }

    if ((workersPayload.workers ?? []).length > 0) {
      const firstWorker = workersPayload.workers[0] as Record<string, unknown>;
      await expect(page.getByText(String(firstWorker.host ?? "--"))).toBeVisible();
    } else {
      await expect(page.getByText("No workers registered.")).toBeVisible();
    }

    expect(networkErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
