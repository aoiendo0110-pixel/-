// 外見の特徴ステッカーを書き出す: node export_stickers.js
//  out/look_frame.png … 組んだかたまり ／ out/look_stickers/<名前>.png … 1枚ずつ（背景透過・3倍）
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const out = path.join(__dirname, 'out', 'look_stickers');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch();
  const url = 'file://' + path.join(__dirname, 'look_frame.html');
  // かたまり
  let page = await browser.newPage({ viewport: { width: 1400, height: 1200 }, deviceScaleFactor: 2 });
  await page.goto(url); await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(600);
  const box = await page.evaluate(() => {
    let l = 1e9, t = 1e9, r = -1e9, b = -1e9;
    for (const el of document.querySelectorAll('.frame > *')) {
      const q = el.getBoundingClientRect(); if (!q.width || !q.height) continue;
      l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom);
    }
    return { x: Math.max(0, l - 20), y: Math.max(0, t - 20), width: r - l + 40, height: b - t + 40 };
  });
  await page.screenshot({ path: path.join(__dirname, 'out', 'look_frame.png'), omitBackground: true, clip: box });
  await page.close();
  // 1枚ずつ
  page = await browser.newPage({ viewport: { width: 1600, height: 1200 }, deviceScaleFactor: 3 });
  await page.goto(url + '#parts'); await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(600);
  for (const el of await page.$$('.stk')) {
    const name = await el.getAttribute('data-name');
    const q = await el.boundingBox();
    await page.screenshot({ path: path.join(out, name + '.png'), omitBackground: true,
      clip: { x: q.x - 16, y: q.y - 16, width: q.width + 32, height: q.height + 32 } });
  }
  await browser.close();
})();
