import { defineConfig } from "@playwright/test";

/**
 * Lightweight Playwright config for human_4_products.spec.ts —
 * skips globalSetup/globalTeardown which depend on seed funding data.
 */
export default defineConfig({
  testDir: "./",
  testMatch: /human_4_products\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000",
    trace: "off",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 10_000,
  },
});
