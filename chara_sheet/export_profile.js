// プロフィールフレームを書き出す: node export_profile.js
//  out/profile_frame.png（文章入り）/ out/profile_frame_blank.png（空）… 背景透過・2倍
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  fs.mkdirSync(path.join(__dirname, 'out'), { recursive: true });
  const browser = await chromium.launch();
  for (const [hash, name] of [['', 'profile_frame'], ['#blank', 'profile_frame_blank']]) {
    const page = await browser.newPage({ viewport: { width: 1300, height: 960 }, deviceScaleFactor: 2 });
    await page.goto('file://' + path.join(__dirname, 'profile_frame.html') + hash);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(__dirname, 'out', name + '.png'), omitBackground: true,
      clip: { x: 0, y: 0, width: 1300, height: 960 } });
    await page.close();
  }
  await browser.close();
})();
