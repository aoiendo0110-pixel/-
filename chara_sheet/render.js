// しょこら設定シートを PNG に書き出す:  node render.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const SHEETS = [
  ['shokora_sheet.html', 'shokora_sheet'],
  ['shokora_sheet_gotegote.html', 'shokora_gotegote'],
];
(async () => {
  fs.mkdirSync(path.join(__dirname, 'out'), { recursive: true });
  const browser = await chromium.launch();
  for (const [file, prefix] of SHEETS) {
    const url = 'file://' + path.join(__dirname, file);
    for (const [name, w, hash] of [['3x4', 1500, ''], ['4x5', 1600, '#ig']]) {
      const page = await browser.newPage({ viewport: { width: w, height: 2000 }, deviceScaleFactor: 1 });
      await page.goto(url + hash);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(__dirname, 'out', `${prefix}_${name}.png`) });
      await page.close();
    }
  }
  // ショコラボックス版 (16:9, 2倍)
  {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
    await page.goto('file://' + path.join(__dirname, 'shokora_chocobox.html'));
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(__dirname, 'out', 'shokora_chocobox_16x9.png') });
    await page.close();
  }
  // 設定シート 16:9 (2倍)
  {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
    await page.goto('file://' + path.join(__dirname, 'shokora_sheet_16x9.html'));
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(900);
    await page.screenshot({ path: path.join(__dirname, 'out', 'shokora_sheet_16x9.png') });
    await page.close();
  }
  await browser.close();
})();
