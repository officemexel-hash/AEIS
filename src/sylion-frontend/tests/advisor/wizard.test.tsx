import { test, expect, type Page } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_TEST_BASE_URL?.trim() || "http://127.0.0.1:3000";
const ONBOARDING_URL = `${BASE_URL}/onboarding`;
const LS_KEY = "sylion.advisor.onboarding";

async function blockBackend(page: Page) {
  await page.route(/\/health(\?.*)?$/, async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
  });
  await page.route(/\/api\/v1\/advisor\/.*/, async (route) => {
    await route.abort("failed");
  });
}

async function clearOnboarding(page: Page) {
  await page.addInitScript((k) => {
    try {
      window.localStorage.removeItem(k as string);
    } catch {
      // ignore
    }
  }, LS_KEY);
}

async function seedOnboarding(page: Page, payload: Record<string, unknown>) {
  await page.addInitScript(
    ({ k, v }) => {
      try {
        window.localStorage.setItem(k as string, JSON.stringify(v));
      } catch {
        // ignore
      }
    },
    { k: LS_KEY, v: payload },
  );
}

async function readOnboarding(page: Page): Promise<Record<string, unknown> | null> {
  return await page.evaluate((k) => {
    const raw = window.localStorage.getItem(k as string);
    return raw ? JSON.parse(raw) : null;
  }, LS_KEY);
}

test.describe("Onboarding wizard (Phase B.2)", () => {
  test.beforeEach(async ({ page }) => {
    await blockBackend(page);
  });

  test("wizard_starts_at_step_1_with_no_local_state", async ({ page }) => {
    await clearOnboarding(page);
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    const wizard = page.getByTestId("onboarding-wizard");
    await expect(wizard).toBeVisible();
    await expect(wizard).toHaveAttribute("data-step", "1");
    await expect(page.getByTestId("step1-name")).toBeVisible();
  });

  test("step_can_be_skipped_when_optional", async ({ page }) => {
    await seedOnboarding(page, {
      step: 9,
      completed_steps: [1, 2, 3, 4, 5, 6, 7, 8],
      values: {
        operator_name: "Tester",
        goals: ["ship_software"],
        usage_cadence: "weekly",
        default_project_domain: "software",
        autonomy_level: "suggest",
        council_size: 5,
        quality_speed_cost: { quality: 0.4, speed: 0.3, cost: 0.3 },
      },
    });
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    const wizard = page.getByTestId("onboarding-wizard");
    await expect(wizard).toHaveAttribute("data-step", "9");
    const skipButton = page.getByRole("button", { name: /^skip$/i });
    await expect(skipButton).toBeVisible();
    await skipButton.click();
    await expect(wizard).toHaveAttribute("data-step", "10");
  });

  test("smart_default_apply_writes_correct_value", async ({ page }) => {
    await clearOnboarding(page);
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    // First SmartDefault on step 1: "Use Operator" — populates operator_name.
    const advisorButtons = page.getByRole("button", { name: /apply/i });
    await advisorButtons.first().click();
    await expect(page.getByTestId("step1-name")).toHaveValue("Operator");
    const data = await readOnboarding(page);
    expect((data?.values as { operator_name?: string })?.operator_name).toBe("Operator");
  });

  test("step_validation_blocks_next_when_required_field_missing", async ({ page }) => {
    await clearOnboarding(page);
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    const nextBtn = page.getByRole("button", { name: /^next$/i });
    await expect(nextBtn).toBeDisabled();
    await page.getByTestId("step1-name").fill("Ada");
    await expect(nextBtn).toBeDisabled();
    await page.getByTestId("step1-goal-ship_software").click();
    await expect(nextBtn).toBeDisabled();
    await page.getByTestId("step1-cadence-weekly").click();
    await expect(nextBtn).toBeEnabled();
  });

  test("quality_speed_cost_slider_sums_to_one", async ({ page }) => {
    await seedOnboarding(page, {
      step: 7,
      completed_steps: [1, 2, 3, 4, 5, 6],
      values: {
        operator_name: "Tester",
        goals: ["ship_software"],
        usage_cadence: "weekly",
        default_project_domain: "software",
        autonomy_level: "suggest",
        council_size: 5,
      },
    });
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    const slider = page.getByTestId("step7-quality");
    await slider.evaluate((el: HTMLInputElement) => {
      el.value = "0.7";
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await page.waitForTimeout(150);
    const data = await readOnboarding(page);
    const w = (data?.values as {
      quality_speed_cost?: { quality: number; speed: number; cost: number };
    })?.quality_speed_cost;
    expect(w).toBeTruthy();
    if (w) {
      const sum = w.quality + w.speed + w.cost;
      expect(Math.abs(sum - 1)).toBeLessThanOrEqual(0.005);
    }
    await expect(page.getByTestId("step7-sum")).toContainText(/balanced/);
  });

  test("funding_country_drilldown_shows_pl_voivodeships", async ({ page }) => {
    await seedOnboarding(page, {
      step: 9,
      completed_steps: [1, 2, 3, 4, 5, 6, 7, 8],
      values: {
        operator_name: "Tester",
        goals: ["ship_software"],
        usage_cadence: "weekly",
        default_project_domain: "software",
        autonomy_level: "suggest",
        council_size: 5,
        quality_speed_cost: { quality: 0.4, speed: 0.3, cost: 0.3 },
      },
    });
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    await page.getByTestId("step9-toggle").click();
    await expect(page.getByTestId("step9-countries")).toBeVisible();
    await expect(page.getByTestId("step9-pl-regions")).toHaveCount(0);
    await page.getByTestId("step9-country-PL").click();
    await expect(page.getByTestId("step9-pl-regions")).toBeVisible();
    await expect(page.getByTestId("step9-region-mazowieckie")).toBeVisible();
    await expect(page.getByTestId("step9-region-dolnoslaskie")).toBeVisible();
  });

  test("complete_redirects_to_lifecycle_or_dashboard_based_on_first_idea", async ({ page }) => {
    // 1) No first_idea_project_id => /dashboard/operator-monitor
    await seedOnboarding(page, {
      step: 10,
      completed_steps: [1, 2, 3, 4, 5, 6, 7, 8, 9],
      values: {
        operator_name: "Tester",
        goals: ["ship_software"],
        usage_cadence: "weekly",
        default_project_domain: "software",
        autonomy_level: "suggest",
        council_size: 5,
        quality_speed_cost: { quality: 0.4, speed: 0.3, cost: 0.3 },
      },
    });
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /complete setup/i }).click();
    await page
      .waitForURL((url) => url.pathname.startsWith("/dashboard/operator-monitor"), {
        timeout: 10_000,
      })
      .catch(() => {});
    expect(page.url()).toMatch(/\/dashboard\/operator-monitor/);

    // 2) With first_idea_project_id => /projects/<id>/lifecycle
    await seedOnboarding(page, {
      step: 10,
      completed_steps: [1, 2, 3, 4, 5, 6, 7, 8, 9],
      values: {
        operator_name: "Tester",
        goals: ["ship_software"],
        usage_cadence: "weekly",
        default_project_domain: "software",
        autonomy_level: "suggest",
        council_size: 5,
        quality_speed_cost: { quality: 0.4, speed: 0.3, cost: 0.3 },
        first_idea_project_id: "p-test-42",
      },
    });
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /complete setup/i }).click();
    await page
      .waitForURL((url) => url.pathname === "/projects/p-test-42/lifecycle", {
        timeout: 10_000,
      })
      .catch(() => {});
    expect(page.url()).toMatch(/\/projects\/p-test-42\/lifecycle/);
  });

  test("state_persists_across_remounts_via_localstorage", async ({ page }) => {
    await clearOnboarding(page);
    await page.goto(ONBOARDING_URL, { waitUntil: "domcontentloaded" });
    await page.getByTestId("step1-name").fill("Persistent Ada");
    await page.getByTestId("step1-goal-ship_software").click();
    await page.getByTestId("step1-cadence-weekly").click();
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("step1-name")).toHaveValue("Persistent Ada");
    await expect(page.getByTestId("step1-goal-ship_software")).toHaveAttribute(
      "data-active",
      "true",
    );
    await expect(page.getByTestId("step1-cadence-weekly")).toHaveAttribute(
      "data-active",
      "true",
    );
  });
});
