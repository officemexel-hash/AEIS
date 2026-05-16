import { chromium } from 'playwright';
import { mkdir } from 'fs/promises';

async function takeScreenshots() {
  await mkdir('screenshots', { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Operator mode — /projects (no modal)
  await page.goto('http://localhost:3001/projects');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => {
    localStorage.setItem('sylion.advisor.mode', 'operator');
    window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'operator' }));
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'screenshots/v2-operator-projects.png', fullPage: false });
  console.log('Saved v2-operator-projects.png');

  // Technical mode — /overview (no modal)
  await page.goto('http://localhost:3001/overview');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => {
    localStorage.setItem('sylion.advisor.mode', 'technical');
    window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'technical' }));
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'screenshots/v2-technical-overview.png', fullPage: false });
  console.log('Saved v2-technical-overview.png');

  // Operator mode with orchestration expanded
  await page.goto('http://localhost:3001/projects');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => {
    localStorage.setItem('sylion.advisor.mode', 'operator');
    window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'operator' }));
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  const orchBtn = await page.locator('button:has-text("Orkiestracja")');
  if (await orchBtn.count() > 0) {
    await orchBtn.click();
    await page.waitForTimeout(300);
  }
  // Also expand Config to show density
  const configBtn = await page.locator('button:has-text("Konfiguracja")');
  if (await configBtn.count() > 0) {
    await configBtn.click();
    await page.waitForTimeout(300);
  }
  await page.screenshot({ path: 'screenshots/v2-operator-expanded.png', fullPage: false });
  console.log('Saved v2-operator-expanded.png');

  await browser.close();
}

takeScreenshots().catch((err) => {
  console.error(err);
  process.exit(1);
});
