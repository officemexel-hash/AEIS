import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: require.resolve("./e2e/global-setup"),
  // F-013 follow-up (Kimi review): teardown ensures seed records do not
  // accumulate across CI runs. Deletes records tagged with current
  // ``seed_run_id`` from globalSetup.
  globalTeardown: require.resolve("./e2e/global-teardown"),
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    actionTimeout: 8_000,
  },
  webServer: {
    command: "npm run dev",
    port: 3000,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
