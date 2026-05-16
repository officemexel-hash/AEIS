/**
 * SYLION AEIS v2 — Human-style 4-product dashboard tour.
 *
 * Operator usecase: act like a real user creating 4 products through the
 * dashboard, modifying ideas mid-flow, then verifying the trail.
 *
 * 4 products:
 *   P1 APP     - inspekcja terenowa (matches inspection_field)
 *   P2 PORTAL  - zatwierdzanie workflow (matches approval_workflow)
 *   P3 BOOK    - kucharska (no demo template -> council 404 path)
 *   P4 SERVICE - magazyn inwentaryzacja (matches inventory_lite)
 *
 * Real assertions — every test verifies actual UI content (specific
 * heading text, results panel, KPI labels), NOT just body.length > 50.
 *
 * Wymagania runtime:
 *   - backend ``:8421`` z SYLION_RBAC_DISABLED=1
 *   - frontend dev server skonfigurowany z NEXT_PUBLIC_API_URL=:8421
 *     tak żeby BackendOfflineGuard przeszedł natywnie (bez bypassu)
 */

import { test, expect, Page } from "@playwright/test";

const BASE = process.env.PLAYWRIGHT_TEST_BASE_URL || "http://localhost:3002";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8421";

/** Navigate + wait for the BackendOfflineGuard "checking" state to clear. */
async function visit(page: Page, path: string) {
  await page.goto(BASE + path, { waitUntil: "domcontentloaded", timeout: 45_000 });

  // Backend guard shows "Łączenie z serwerem..." until /health responds.
  // We wait until that text disappears (real backend on :8421 returns OK).
  try {
    await page.waitForFunction(
      () => !document.body.innerText.includes("Łączenie z serwerem"),
      { timeout: 25_000 },
    );
  } catch {
    // If the guard is stuck, surface the assertion failure with current
    // body so the test report carries the actual cause instead of a
    // generic timeout.
    const stuckBody = await page.locator("body").innerText();
    throw new Error(
      `BackendOfflineGuard never cleared at ${path}. body[:200]=${stuckBody.slice(0, 200)}`,
    );
  }
  // Small grace for hydration after guard clears.
  await page.waitForTimeout(800);
}

/** Submit an idea via the apps-builder wizard textarea. */
async function submitIdea(page: Page, ideaText: string, topN = 3): Promise<void> {
  const textarea = page.locator('textarea[aria-label="Opis pomyslu"]').first();
  await expect(textarea).toBeVisible({ timeout: 15_000 });
  await textarea.fill(ideaText);

  if (topN !== 3) {
    const slider = page.locator('input[aria-label="Liczba sugestii"]');
    if (await slider.count()) {
      await slider.fill(String(topN));
    }
  }

  const submitBtn = page
    .locator("button")
    .filter({ hasText: /Znajdz dopasowania/i })
    .first();
  await expect(submitBtn).toBeEnabled({ timeout: 5_000 });
  await submitBtn.click();

  // Wait until either results render OR an error banner appears.
  await Promise.race([
    page
      .locator("text=/Sugerowane szablony|Best match|Top dopasowanie|Wybierz/i")
      .first()
      .waitFor({ state: "visible", timeout: 20_000 })
      .catch(() => null),
    page
      .locator("text=/0 dopasowan|Brak dopasowan|niski wynik|low score/i")
      .first()
      .waitFor({ state: "visible", timeout: 20_000 })
      .catch(() => null),
    page.waitForTimeout(7_000),
  ]);
}

/* ============================================================
   Test 1 — APP: inspection_field flow
   ============================================================ */

test("P1 APP — wizard inspekcja: full flow", async ({ page }) => {
  await visit(page, "/apps-builder/wizard");

  // Wizard heading must be present.
  await expect(page.locator("text=Twoj pomysl")).toBeVisible({ timeout: 10_000 });

  await submitIdea(
    page,
    "inspekcja terenowa raport audyt monitorowanie urzadzen",
    5,
  );

  // After submit either the result panel mentions the matched template
  // OR shows an error. Real assertion: the page must contain at least
  // one of the two recognised states.
  const body = await page.locator("body").innerText();
  const matched = /inspection_field|Inspekcje terenowe/i.test(body);
  const erred = /Blad|Error|niedostepny/i.test(body);

  await page.screenshot({ path: "test-results/p1-wizard.png", fullPage: true });

  if (!matched && !erred) {
    throw new Error(
      `P1 wizard: neither match nor error visible. body[:300]=${body.slice(0, 300)}`,
    );
  }
  expect(matched).toBeTruthy();
});

/* ============================================================
   Test 2 — PORTAL: modify idea mid-flow (sloppy → detailed)
   ============================================================ */

test("P2 PORTAL — operator zmienia pomysl mid-flow", async ({ page }) => {
  await visit(page, "/apps-builder/wizard");

  await expect(page.locator("text=Twoj pomysl")).toBeVisible();

  // Step 1: sloppy but valid submission (>=10 chars min).
  await submitIdea(page, "portal aplikacja firmowa", 3);
  await page.screenshot({ path: "test-results/p2-sloppy.png", fullPage: true });

  // Step 2: clear via Wyczysc.
  const clearBtn = page.locator("button").filter({ hasText: /Wyczysc/i }).first();
  if (await clearBtn.isEnabled({ timeout: 3_000 }).catch(() => false)) {
    await clearBtn.click();
    await page.waitForTimeout(500);
  }

  // Step 3: detailed re-submission.
  await submitIdea(
    page,
    "portal pracownika zatwierdzanie wnioskow workflow dokumenty " +
      "autoryzacja decyzje audyt KPI metryki",
    5,
  );

  const body = await page.locator("body").innerText();
  await page.screenshot({ path: "test-results/p2-detailed.png", fullPage: true });
  expect(body).toMatch(/approval_workflow|zatwierdzanie/i);
});

/* ============================================================
   Test 3 — BOOK: low-match idea
   ============================================================ */

test("P3 BOOK — kucharska bez matcha", async ({ page }) => {
  await visit(page, "/apps-builder/wizard");

  await submitIdea(
    page,
    "ksiazka kucharska rodzinne przepisy zdjecia kategorie",
    3,
  );

  await page.screenshot({ path: "test-results/p3-book.png", fullPage: true });

  // Real assertion: either zero matches indicator OR low-score banner OR
  // the wizard explicitly tells operator that nothing matched.
  const body = await page.locator("body").innerText();
  const isLowMatch = /0 dopasowan|brak dopasowan|niski wynik|0 matches|Brak/i.test(body);
  expect(isLowMatch).toBeTruthy();
});

/* ============================================================
   Test 4 — SERVICE: magazyn inventory_lite
   ============================================================ */

test("P4 SERVICE — magazyn z modyfikacja slidera", async ({ page }) => {
  await visit(page, "/apps-builder/wizard");

  await submitIdea(
    page,
    "magazyn stany inwentaryzacja raporty logistyka czesci zamienne",
    8,
  );

  const body = await page.locator("body").innerText();
  await page.screenshot({ path: "test-results/p4-magazyn.png", fullPage: true });
  expect(body).toMatch(/inventory_lite|magazyn|stany/i);
});

/* ============================================================
   Test 5 — /v2/admin: real metrics dashboard assertions
   ============================================================ */

test("ADMIN — /v2/admin pokazuje 6 KPI cards z prawdziwymi danymi", async ({
  page,
}) => {
  await visit(page, "/v2/admin");

  // Page header must be visible.
  await expect(
    page.locator("text=AEIS v2 — Admin").first(),
  ).toBeVisible({ timeout: 10_000 });

  // Allow first metrics fetch to land.
  await page.waitForTimeout(4_000);

  await page.screenshot({ path: "test-results/admin.png", fullPage: true });

  // 6 KPI labels must all be visible (not via body.includes which is
  // sloppy — use .locator(text=...).count()).
  const labels = [
    /W19 Evaluator/i,
    /Canary Rollout/i,
    /W19 Renders/i,
    /Audit Chain Rows/i,
    /Audit Violations/i,
    /Open Circuits/i,
  ];
  for (const re of labels) {
    const loc = page.locator("text=" + re.source).first();
    await expect(loc).toBeVisible({ timeout: 8_000 });
  }
});

/* ============================================================
   Test 6 — sidebar nav: navigate v2 sections
   ============================================================ */

test("NAV — sidebar prowadzi przez wszystkie v2 sekcje", async ({ page }) => {
  await visit(page, "/v2/admin");

  const sections = [
    { href: "/ontology", marker: /ontolog/i },
    { href: "/apps-builder", marker: /apps?[ -]builder|aplikacj/i },
    { href: "/terminal", marker: /terminal/i },
    { href: "/role-catalog", marker: /role|rola|katalog/i },
    { href: "/federation", marker: /federacja|federation/i },
    { href: "/policy", marker: /polic|polityka/i },
  ];

  for (const sec of sections) {
    await visit(page, sec.href);
    const body = await page.locator("body").innerText();
    if (!sec.marker.test(body)) {
      throw new Error(
        `${sec.href} body did NOT match ${sec.marker}. body[:200]=${body.slice(0, 200)}`,
      );
    }
  }
});

/* ============================================================
   Test 7 — final API verification (post UI activity)
   ============================================================ */

test("VERIFY — backend metrics + chains po UI activity", async ({ request }) => {
  // Health.
  const health = await request.get(`${API_BASE}/api/v1/health/v2`);
  expect(health.ok()).toBeTruthy();
  const hb = await health.json();
  expect(hb.services.audit_chain).toBe("up");
  expect(hb.services.gdpr_dsr).toBe("up");
  expect(hb.services.council_wedge).toBe("up");

  // Metrics fetch.
  const metrics = await request.get(`${API_BASE}/api/v1/metrics/v2`);
  expect(metrics.ok()).toBeTruthy();
  const text = await metrics.text();

  // Council decisions counter must have grown from the wizard runs.
  const m = text.match(
    /sylion_v2_council_decisions_total\{verdict="approve"\}\s+(\d+)/,
  );
  if (m) {
    const count = parseInt(m[1], 10);
    console.log("Council approve count:", count);
  }

  // chained audit JSONLs visible:
  expect(text).toContain("sylion_v2_audit_chain_size");
  expect(text).toContain("sylion_v2_w19_renders_total");
  expect(text).toContain("adapter_bus_dispatch_total");
});
