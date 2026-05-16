import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const OUT = path.resolve(process.cwd(), 'scripts/visual-verify-output');
const BASE = 'http://localhost:3001';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

const techPage = await context.newPage();
await techPage.goto(`${BASE}/overview`, { waitUntil: 'networkidle' });
await techPage.evaluate(() => {
  window.localStorage.setItem('sylion.advisor.mode', 'technical');
  window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'technical' }));
});
await techPage.reload({ waitUntil: 'networkidle' });

// Close any modal/dialog by pressing Escape
await techPage.keyboard.press('Escape');
await techPage.waitForTimeout(300);

// Ensure sidebar expanded via localStorage + reload
await techPage.evaluate(() => {
  window.localStorage.setItem('sylion.sidebar.collapsed', 'false');
});
await techPage.reload({ waitUntil: 'networkidle' });
await techPage.keyboard.press('Escape');
await techPage.waitForTimeout(800);

await techPage.screenshot({ path: path.join(OUT, '04-technical-expanded.png'), fullPage: false });
console.log('saved technical expanded');

await browser.close();
