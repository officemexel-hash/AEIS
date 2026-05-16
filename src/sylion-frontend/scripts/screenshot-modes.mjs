import { chromium } from 'playwright';
import { mkdir } from 'fs/promises';

async function takeScreenshots() {
  await mkdir('screenshots', { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Screenshot 1: Operator mode
  await page.goto('http://localhost:3001/advisor');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => {
    localStorage.setItem('sylion.advisor.mode', 'operator');
    window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'operator' }));
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  await page.screenshot({ path: 'screenshots/mode-operator.png', fullPage: false });
  console.log('Saved screenshots/mode-operator.png');

  // Screenshot 2: Technical mode
  await page.evaluate(() => {
    localStorage.setItem('sylion.advisor.mode', 'technical');
    window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'technical' }));
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  await page.screenshot({ path: 'screenshots/mode-technical.png', fullPage: false });
  console.log('Saved screenshots/mode-technical.png');

  // Screenshot 3: Operator sidebar expanded with orchestration
  await page.evaluate(() => {
    localStorage.setItem('sylion.advisor.mode', 'operator');
    window.dispatchEvent(new CustomEvent('sylion:advisor-mode', { detail: 'operator' }));
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(800);
  // Expand orchestration section
  const orchBtn = await page.locator('button:has-text("Orkiestracja")');
  if (await orchBtn.count() > 0) {
    await orchBtn.click();
    await page.waitForTimeout(300);
  }
  await page.screenshot({ path: 'screenshots/mode-operator-orch.png', fullPage: false });
  console.log('Saved screenshots/mode-operator-orch.png');

  await browser.close();
}

takeScreenshots().catch((err) => {
  console.error(err);
  process.exit(1);
});
