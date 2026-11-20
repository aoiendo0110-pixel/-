// パーツ素材を書き出す: node export_parts.js
//  parts/<名前>.png … 背景透過・3倍 ／ parts_catalog.png … 一覧
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const out = path.join(__dirname, 'parts');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const url = 'file://' + path.join(__dirname, 'parts.html');
  // 一覧
  let page = await browser.newPage({ viewport: { width: 1800, height: 1000 }, deviceScaleFactor: 1 });
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
  await page.screenshot({ path: path.join(__dirname, 'parts_catalog.png'), fullPage: true });
  await page.close();
  // 1個ずつ（背景透過）
  page = await browser.newPage({ viewport: { width: 1800, height: 1000 }, deviceScaleFactor: 3 });
  await page.goto(url + '#export');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
  const parts = await page.$$('.part');
  for (const el of parts) {
    const name = await el.getAttribute('data-name');
    await el.screenshot({ path: path.join(out, name + '.png'), omitBackground: true });
  }
  console.log(parts.length + ' parts');
  await browser.close();
})();
