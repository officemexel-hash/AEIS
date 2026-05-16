import { defineConfig } from "@playwright/test";

/**
 * Lightweight Playwright config for aeis_simulation_4_products.spec.ts —
 * skips globalSetup/globalTeardown, runs tests in order so cross-test
 * globals (__BASELINE, __CREATED_IDEAS) work.
 */
export default defineConfig({
  testDir: "./",
  testMatch: /aeis_simulation_4_products\.spec\.ts/,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || "http://127.0.0.1:3002",
    trace: "off",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 10_000,
  },
});
