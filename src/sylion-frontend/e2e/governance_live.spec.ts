import { expect, test } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3001";
const API_BASE_URL = process.env.PLAYWRIGHT_TEST_API_BASE_URL?.trim() || "http://127.0.0.1:8000";

test.describe("governance live flow", () => {
  test("creates a proposal and records a real vote without fake timeline data", async ({ page, request }) => {
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

    const title = `Governance smoke ${Date.now()}`;

    await page.goto(`${BASE_URL}/governance`, { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Governance" })).toBeVisible();

    await page.getByRole("button", { name: "Create Proposal" }).click();
    await page.getByPlaceholder("Proposal title...").fill(title);
    await page.getByPlaceholder("Describe the proposal...").fill("Validate live proposal voting flow.");
    await page.getByRole("button", { name: "Submit" }).click();

    await expect(page.getByText(title)).toBeVisible();

    const proposalCard = page.locator('[data-slot="card"]').filter({ hasText: title }).first();
    await proposalCard.getByRole("button", { name: "For" }).click();

    await expect
      .poll(async () => {
        const response = await request.get(`${API_BASE_URL}/api/v1/governance/proposals`);
        const payload = await response.json();
        const proposal = (payload.proposals ?? []).find((item: Record<string, unknown>) => item.title === title);
        return proposal?.votes_for ?? 0;
      })
      .toBe(1);

    await page.getByRole("tab", { name: "Voting Activity" }).click();
    await expect(page.getByText("operator").first()).toBeVisible();
    await expect(page.locator('[data-slot="card"]').filter({ hasText: title }).first()).toBeVisible();
    await expect(page.getByText("agent_a1")).toHaveCount(0);
    await expect(page.getByText("board")).toHaveCount(0);

    expect(networkErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
