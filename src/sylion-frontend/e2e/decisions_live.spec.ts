import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

test.describe("decisions live flow", () => {
  test("simulates and changes a decision using real backend state", async ({ page, request }) => {
    const consoleErrors: string[] = [];
    const networkErrors: string[] = [];
    const decisionId = `decision_${Date.now()}`;
    const initialChoice = `initial_choice_${Date.now()}`;
    const updatedChoice = `updated_choice_${Date.now()}`;

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

    const created = await request.post(`${API_BASE_URL}/api/v1/governance/decision-snapshots`, {
      data: {
        decision_id: decisionId,
        gate_id: "qa_decisions_live",
        choice_made: initialChoice,
      },
    });
    expect(created.ok()).toBeTruthy();
    const createdPayload = await created.json();
    const snapshotId = createdPayload.snapshot_id as string;

    await page.goto(`${BASE_URL}/decisions`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Decision Gates" })).toBeVisible();

    await page.getByRole("tab", { name: "Cascade Impact" }).click();
    const simulateCard = page.locator('[data-slot="card"]').filter({ hasText: "Simulate Change" }).first();
    await simulateCard.locator("select").selectOption(snapshotId);
    await simulateCard.getByPlaceholder("Enter new choice to simulate...").fill(updatedChoice);
    await simulateCard.getByRole("button", { name: /Simulate/i }).click();
    await expect(page.getByText("Simulation would show cascade preview here. Connect to backend for full simulation.")).toHaveCount(0);
    await expect(simulateCard.getByText("No downstream impact predicted from the current dependency graph.")).toBeVisible();

    await page.getByRole("tab", { name: "Timeline" }).click();
    const decisionEntry = page.getByText(initialChoice).last();
    await expect(decisionEntry).toBeVisible();
    await decisionEntry.click();
    await page.getByRole("button", { name: "Change Decision" }).click();
    await page.getByPlaceholder("Enter new choice...").fill(updatedChoice);
    await page.getByRole("button", { name: "Confirm Change" }).click();

    await expect
      .poll(async () => {
        const response = await request.get(`${API_BASE_URL}/api/v1/decision-snapshots`);
        const payload = await response.json();
        return (payload.snapshots ?? []).some(
          (snapshot: Record<string, unknown>) =>
            snapshot.decision_id === decisionId && snapshot.choice_made === updatedChoice,
        );
      })
      .toBe(true);

    await expect(page.getByText(updatedChoice).first()).toBeVisible();
    expect(networkErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
