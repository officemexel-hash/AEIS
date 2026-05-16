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

// Helper to ensure sidebar expanded
async function ensureExpanded(page) {
  const sidebarWidth = await page.evaluate(() => {
    const aside = document.querySelector('aside');
    return aside ? aside.getBoundingClientRect().width : 0;
  });
  if (sidebarWidth < 100) {
    // Click the toggle button at bottom of sidebar to expand
    await page.click('aside button[aria-label="Rozwiń menu"]');
    await page.waitForTimeout(500);
  }
}

// --- Operator mode (default) ---
const opPage = await context.newPage();
await opPage.goto(`${BASE}/overview`, { waitUntil: 'networkidle' });
await ensureExpanded(opPage);
await opPage.waitForTimeout(1500);
await screenshot(opPage, '03-operator-expanded.png');

// --- Switch to technical mode ---
const techPage = await context.newPage();
await techPage.goto(`${BASE}/overview`, { waitUntil: 'networkidle' });
await techPage.evaluate(() => {
  window.localStorage.setItem('sylion.advisor.mode', 'technical');
  window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'technical' }));
});
await techPage.reload({ waitUntil: 'networkidle' });
await ensureExpanded(techPage);
await techPage.waitForTimeout(1500);
await screenshot(techPage, '04-technical-expanded.png');

await browser.close();
console.log('Expanded screenshots saved to', OUT);
