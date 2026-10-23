// usage: node render.js <scene> <outdir> <fps> <duration> [t1,t2,... for preview]
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [scene, outdir, fps, dur, list] = process.argv.slice(2);
  fs.mkdirSync(outdir, { recursive: true });
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const p = await b.newPage();
  p.on('pageerror', e => console.error('pageerror', e.message));
  await p.goto('file://' + path.join(__dirname, 'index.html') + '?scene=' + scene);
  await p.evaluate(() => window.ready);
  const times = list ? list.split(',').map(Number)
    : Array.from({ length: Math.round(+fps * +dur) }, (_, i) => i / +fps);
  for (let i = 0; i < times.length; i++) {
    const url = await p.evaluate(t => window.render(t), times[i]);
    fs.writeFileSync(path.join(outdir, `f${String(i).padStart(4, '0')}.png`), Buffer.from(url.split(',')[1], 'base64'));
  }
  await b.close();
})();
