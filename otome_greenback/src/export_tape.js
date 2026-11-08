// usage: node export_tape.js <outdir>
// <outdir>/transparent/*.png（背景透過） と <outdir>/greenback/*.png（グリーンバック）を書き出す
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const out = process.argv[2];
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + path.join(__dirname, 'tape.html'));
  for (const [dir, green] of [['transparent', false], ['greenback', true]]) {
    fs.mkdirSync(path.join(out, dir), { recursive: true });
    const res = await p.evaluate(g => window.exportAll(g), green);
    for (const { name, url } of res) fs.writeFileSync(path.join(out, dir, `${name}.png`), Buffer.from(url.split(',')[1], 'base64'));
    console.log(dir, res.length);
  }
  await b.close();
})();
