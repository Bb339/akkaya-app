const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    timeout: 8000,
  });
  const page = await browser.newPage({ viewport: { width: 1300, height: 850 }, deviceScaleFactor: 1 });
  const errors = [];
  const dialogs = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', async d => {
    dialogs.push(d.message());
    await d.dismiss().catch(() => {});
  });
  await page.goto('http://127.0.0.1:5000/?v=132', { waitUntil: 'domcontentloaded', timeout: 12000 });
  await page.waitForTimeout(700);
  await page.evaluate(() => {
    document.querySelector('[data-demo-user="betul.demir"]')?.click();
    document.querySelector('.auth-submit')?.click();
  });
  await page.waitForTimeout(5000);
  const result = await page.evaluate(() => ({
    patch: window.__sazlicaPatchVersion,
    optionCount: document.querySelectorAll('#parcelSelect option').length,
    options: [...document.querySelectorAll('#parcelSelect option')].slice(0, 4).map(o => o.textContent),
    bell: document.getElementById('notificationBellBtn')?.innerText || '',
    controls: [...document.querySelectorAll('#farmerDecisionCard select,#farmerDecisionCard button')]
      .map(el => ({ id: el.id, visible: !!el.offsetParent, text: el.textContent.trim().slice(0, 80) })),
    messages: (document.getElementById('farmerUserRequestThreadV100')?.innerText ||
      document.getElementById('userRequestThread')?.innerText || '').slice(0, 220),
    tiles: document.querySelectorAll('#map img.leaflet-tile').length,
    completeTiles: [...document.querySelectorAll('#map img.leaflet-tile')]
      .filter(img => img.complete && img.naturalWidth > 0).length,
    bodyStart: document.body.innerText.slice(0, 500),
  }));
  console.log(JSON.stringify({ errors, dialogs, result }, null, 2));
  await browser.close();
})();
