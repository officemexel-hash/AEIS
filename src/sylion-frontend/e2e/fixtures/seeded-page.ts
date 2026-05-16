import { expect, test as base, type Page } from "@playwright/test";

type SeedState = {
  backendUrl?: string;
  seed_run_id?: string;
  seeded?: Array<{ kind?: string }>;
};

function readSeedState(): SeedState {
  const raw = process.env.PLAYWRIGHT_SEED_STATE;
  if (!raw) {
    return {};
  }

  try {
    return JSON.parse(raw) as SeedState;
  } catch {
    return {};
  }
}

async function waitForSeedReadiness(page: Page): Promise<void> {
  const state = readSeedState();
  const backendUrl = process.env.BACKEND_URL?.trim() || state.backendUrl || "http://127.0.0.1:8010";
  const usesDeploymentFallback = (state.seeded ?? []).some((entry) => entry.kind === "deployment");

  const [proposalsResponse, secondaryResponse] = await Promise.all([
    page.request.get(`${backendUrl}/api/v1/governance/proposals`),
    usesDeploymentFallback
      ? page.request.get(`${backendUrl}/api/v1/deployments`)
      : page.request.get(`${backendUrl}/api/v1/integration/builds`),
  ]);

  expect(proposalsResponse.ok()).toBeTruthy();
  expect(secondaryResponse.ok()).toBeTruthy();
}

export const test = base.extend<{ seededPage: Page }>({
  seededPage: async ({ page }, runFixture) => {
    await waitForSeedReadiness(page);
    await runFixture(page);
  },
});

export { expect } from "@playwright/test";
