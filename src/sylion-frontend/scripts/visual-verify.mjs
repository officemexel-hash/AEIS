import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const OUT = path.resolve(process.cwd(), 'scripts/visual-verify-output');
fs.mkdirSync(OUT, { recursive: true });

const BASE = 'http://localhost:3001';

async function screenshot(page, name) {
  const p = path.join(OUT, name);
  await page.screenshot({ path: p, fullPage: false });
  console.log('screenshot:', p);
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

// --- Operator mode (default) ---
const opPage = await context.newPage();
await opPage.goto(`${BASE}/overview`, { waitUntil: 'networkidle' });
await opPage.waitForTimeout(1500);
await screenshot(opPage, '01-operator-overview.png');

// --- Switch to technical mode ---
const techPage = await context.newPage();
await techPage.goto(`${BASE}/overview`, { waitUntil: 'networkidle' });
await techPage.evaluate(() => {
  window.localStorage.setItem('sylion.advisor.mode', 'technical');
  window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'technical' }));
});
await techPage.reload({ waitUntil: 'networkidle' });
await techPage.waitForTimeout(1500);
await screenshot(techPage, '02-technical-overview.png');

// --- Orchestration pages (operator mode) ---
const orchRoutes = [
  '/orchestration/llm-routing',
  '/orchestration/council-rules',
  '/orchestration/auditor',
  '/orchestration/fixer',
  '/orchestration/dispatch',
  '/orchestration/tests',
  '/orchestration/teams',
  '/orchestration/event-map',
  '/orchestration/conversations',
];

for (const route of orchRoutes) {
  const p = await context.newPage();
  await p.goto(`${BASE}${route}`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(800);
  const name = route.replace(/\//g, '_').replace(/^_|_$/g, '') + '.png';
  await screenshot(p, `orch-${name}`);
  await p.close();
}

await browser.close();
console.log('All screenshots saved to', OUT);
