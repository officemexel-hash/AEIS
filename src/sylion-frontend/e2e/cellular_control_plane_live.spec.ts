import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

test.describe("cellular control-plane live flow", () => {
  test("analyzes decoded trace text and shows real anomalies in the UI", async ({ page, request }) => {
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

    const suffix = Date.now().toString().slice(-6);
    const sourceLabel = `playwright-control-plane-${suffix}.txt`;
    const sourceText = [
      "DL NAS Identity Request",
      "DL NAS Attach Reject",
    ].join("\n");

    await page.goto(`${BASE_URL}/cellular`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Cellular Security Lab", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Control-plane", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Control-Plane Analysis", exact: true })).toBeVisible();

    await page.getByLabel("Source Label").fill(sourceLabel);
    await page.getByLabel("Decoded Trace").fill(sourceText);
    await page.getByRole("button", { name: "Analyze Trace", exact: true }).click();

    await expect
      .poll(async () => {
        const response = await request.get(`${API_BASE_URL}/api/v1/cellular/control-plane`);
        const payload = await response.json();
        return payload.analyses.find((analysis: Record<string, unknown>) => String(analysis.pcap_source ?? "") === sourceLabel) ?? null;
      })
      .not.toBeNull();

    await expect(page.getByText(sourceLabel, { exact: true })).toBeVisible();
    await expect(page.getByText("2 messages", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("2 anomalies", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("missing_security_mode", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("reject_detected", { exact: true }).first()).toBeVisible();

    await expect(networkErrors).toEqual([]);
    await expect(consoleErrors).toEqual([]);
  });
});
