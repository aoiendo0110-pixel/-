// フレームを書き出す: node export_frames.js song   （profile も可）
//  out/<name>_frame.png（文字入り）/ out/<name>_frame_blank.png（空）… 背景透過・2倍、余白は自動で切り詰め
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const name = process.argv[2] || 'song';
  fs.mkdirSync(path.join(__dirname, 'out'), { recursive: true });
  const browser = await chromium.launch();
  for (const [hash, suffix] of [['', ''], ['#blank', '_blank']]) {
    const page = await browser.newPage({ viewport: { width: 1300, height: 1400 }, deviceScaleFactor: 2 });
    await page.goto('file://' + path.join(__dirname, `${name}_frame.html`) + hash);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(600);
    // 描かれている範囲だけを切り出す
    const box = await page.evaluate(() => {
      let l = 1e9, t = 1e9, r = -1e9, b = -1e9;
      for (const el of document.querySelectorAll('.frame, .frame *')) {
        const q = el.getBoundingClientRect(); if (!q.width || !q.height) continue;
        l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom);
      }
      return { x: Math.max(0, l - 16), y: Math.max(0, t - 16), width: r - l + 32, height: b - t + 32 };
    });
    await page.screenshot({ path: path.join(__dirname, 'out', `${name}_frame${suffix}.png`), omitBackground: true, clip: box });
    await page.close();
  }
  await browser.close();
})();
