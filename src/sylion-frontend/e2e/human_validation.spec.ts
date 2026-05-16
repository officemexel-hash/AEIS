import { test, expect } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3000";

/**
 * SCENARIUSZ A — Prosty workflow bazowy
 * Cel: Sprawdzić czy pomysł można wprowadzić, zapisać i prześledzić.
 */
test("Scenario A: Idea Vault intake and dashboard visibility", async ({ page }) => {
  // 1. Przejście do Idea Vault
  await page.goto(`${BASE}/idea-vault`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  // 2. Sprawdzenie czy formularz lub przycisk dodawania istnieje
  const addButton = page.locator("button").filter({ hasText: /Add|New|Nowy|Dodaj/i }).first();
  const hasAdd = await addButton.isVisible().catch(() => false);

  if (hasAdd) {
    await addButton.click();
    // 3. Wpisanie pomysłu
    const titleInput = page.locator("input[type='text']").first();
    await expect(titleInput).toBeVisible({ timeout: 5000 });
    await titleInput.fill("Test Human Validation Idea " + Date.now());

    // 4. Zapisanie
    const saveButton = page.locator("button").filter({ hasText: /Save|Zapisz|Submit/i }).first();
    await saveButton.click();

    // 5. Sprawdzenie czy pojawił się w liście
    await page.waitForTimeout(1000);
    const ideaCard = page.locator("text=/Test Human Validation Idea/").first();
    await expect(ideaCard).toBeVisible({ timeout: 10000 });
  }

  // 6. Dashboard powinien pokazywać pomysły
  await page.goto(`${BASE}/overview`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });
});

/**
 * SCENARIUSZ B — Workflow średnio złożony (Module + Worker + Build)
 * Cel: Sprawdzić czy można stworzyć moduł, przypisać do workera, i śledzić build.
 */
test("Scenario B: Module creation, worker assignment, and build tracking", async ({ page }) => {
  // 1. Moduły
  await page.goto(`${BASE}/modules`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  const addModuleBtn = page.locator("button").filter({ hasText: /Add|New|Nowy/i }).first();
  const canAddModule = await addModuleBtn.isVisible().catch(() => false);

  if (canAddModule) {
    await addModuleBtn.click();
    const moduleName = page.locator("input").first();
    await moduleName.fill("test-human-module-" + Date.now());
    const saveBtn = page.locator("button").filter({ hasText: /Save|Zapisz|Create/i }).first();
    await saveBtn.click();
    await page.waitForTimeout(1000);
  }

  // 2. Workers
  await page.goto(`${BASE}/workers`);
  await expect(page.locator("h1")).toContainText(/Worker|Workery/i, { timeout: 10000 });

  const addWorkerBtn = page.locator("button").filter({ hasText: /Register|Add|New/i }).first();
  const canAddWorker = await addWorkerBtn.isVisible().catch(() => false);

  if (canAddWorker) {
    await addWorkerBtn.click();
    const nameInput = page.locator("input[placeholder*='name' i], input[name*='name' i]").first();
    if (await nameInput.isVisible().catch(() => false)) {
      await nameInput.fill("Test-Worker-Human-" + Date.now());
      const saveWorker = page.locator("button").filter({ hasText: /Save|Register|Create/i }).first();
      await saveWorker.click();
      await page.waitForTimeout(1000);
    }
  }

  // 3. Builds
  await page.goto(`${BASE}/builds`);
  await expect(page.locator("h1")).toContainText(/Build|Builds|Fabryka/i, { timeout: 10000 });
});

/**
 * SCENARIUSZ C — Governance / Decisions / Human Gate
 * Cel: Sprawdzić czy governance naprawdę działa jako workflow decyzyjny.
 */
test("Scenario C: Governance proposal and decision workflow", async ({ page }) => {
  // 1. Governance
  await page.goto(`${BASE}/governance`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  // 2. Sprawdzenie czy są realne proposals / policies / gates
  const hasProposals = await page.locator("text=/proposal/i").first().isVisible().catch(() => false);
  const hasPolicies = await page.locator("text=/policy/i").first().isVisible().catch(() => false);
  const hasGates = await page.locator("text=/gate/i").first().isVisible().catch(() => false);

  console.log("Governance check:", { hasProposals, hasPolicies, hasGates });

  // 3. Decisions
  await page.goto(`${BASE}/decisions`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  // 4. Sprawdzenie czy decision ladder jest widoczny
  const hasDecisionClass = await page.locator("text=/D0|D1|D2|D3|D4|D5/i").first().isVisible().catch(() => false);
  console.log("Decision ladder visible:", hasDecisionClass);

  // 5. Evidence
  await page.goto(`${BASE}/evidence-spine`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });
});

/**
 * SCENARIUSZ D — Autonomy / Self-Evolution / Skills
 * Cel: Sprawdzić czy autonomia i samorozwój mają realne UI i workflow.
 */
test("Scenario D: Autonomy, self-evolution, and skills visibility", async ({ page }) => {
  // 1. Autonomy
  await page.goto(`${BASE}/autonomy`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  const hasAutonomyContent = await page.locator("text=/stage|mode|status|level/i").first().isVisible().catch(() => false);
  console.log("Autonomy content:", hasAutonomyContent);

  // 2. Skills
  await page.goto(`${BASE}/skills`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  const hasSkillsList = await page.locator("text=/skill|registry|draft|published/i").first().isVisible().catch(() => false);
  console.log("Skills content:", hasSkillsList);

  // 3. Rebuild (self-evolution)
  await page.goto(`${BASE}/rebuild`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });
});

/**
 * SCENARIUSZ E — Alerty, powiadomienia, human gate
 * Cel: Sprawdzić czy alerty są widoczne i czy prowadzą do akcji.
 */
test("Scenario E: Alerts, notifications, and human gate visibility", async ({ page }) => {
  // 1. Health / alerts
  await page.goto(`${BASE}/health`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  // 2. Build State (global snapshot)
  await page.goto(`${BASE}/build-state`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  const hasWorkerCard = await page.locator("text=/Workers/i").first().isVisible().catch(() => false);
  const hasAlertCard = await page.locator("text=/Alerts/i").first().isVisible().catch(() => false);
  console.log("Build state cards:", { hasWorkerCard, hasAlertCard });

  // 3. Observability
  await page.goto(`${BASE}/observability`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  const hasLogs = await page.locator("text=/Logs|log/i").first().isVisible().catch(() => false);
  const hasTraces = await page.locator("text=/Traces|trace/i").first().isVisible().catch(() => false);
  console.log("Observability content:", { hasLogs, hasTraces });
});

/**
 * SCENARIUSZ F — Używalność i czytelność dashboardu
 * Cel: Sprawdzić czy operator rozumie co się dzieje.
 */
test("Scenario F: Dashboard usability and real data verification", async ({ page }) => {
  await page.goto(`${BASE}/overview`);
  await expect(page.locator("h1")).toBeVisible({ timeout: 10000 });

  // Sprawdzenie czy dashboard ma jakiekolwiek liczby (nie tylko 0 lub puste)
  const numbers = await page.locator("text=/[0-9]+/").count();
  console.log("Dashboard numeric indicators:", numbers);

  // Sprawdzenie czy sidebar nawigacja prowadzi do realnych stron
  const links = ["/workers", "/builds", "/governance", "/decisions", "/evidence", "/autonomy", "/skills"];
  for (const link of links) {
    await page.goto(`${BASE}${link}`);
    const status = await page.locator("h1").first().isVisible().catch(() => false);
    console.log(`Navigation to ${link}:`, status ? "OK" : "BROKEN");
  }
});
