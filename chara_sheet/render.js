// しょこら設定シートを PNG に書き出す:  node render.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  fs.mkdirSync(path.join(__dirname, 'out'), { recursive: true });
  const browser = await chromium.launch();
  const url = 'file://' + path.join(__dirname, 'shokora_sheet.html');
  for (const [name, w, hash] of [['3x4', 1500, ''], ['4x5', 1600, '#ig']]) {
    const page = await browser.newPage({ viewport: { width: w, height: 2000 }, deviceScaleFactor: 1 });
    await page.goto(url + hash);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(__dirname, 'out', `shokora_sheet_${name}.png`) });
    await page.close();
  }
  await browser.close();
})();
