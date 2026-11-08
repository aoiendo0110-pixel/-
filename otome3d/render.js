// usage: node render.js <obj> <outdir> <fps> <dur> [t1,t2..] [w] [h]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [obj, outdir, fps, dur, list, w='1920', h='1080'] = process.argv.slice(2);
  fs.mkdirSync(outdir, { recursive: true });
  const b = await chromium.launch({ args: ['--allow-file-access-from-files','--use-gl=angle','--use-angle=swiftshader','--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: +w, height: +h } });
  p.on('console', m => console.log('[page]', m.text()));
  p.on('pageerror', e => console.log('[err]', e.message));
  await p.goto(`file://${path.join(__dirname, 'index.html')}?obj=${obj}&export&w=${w}&h=${h}`);
  await p.waitForFunction(() => window.ready, null, { timeout: 120000 });
  const times = list && list !== '-' ? list.split(',').map(Number)
    : Array.from({ length: Math.round(+fps * +dur) }, (_, i) => i / +fps);
  for (let i = 0; i < times.length; i++) {
    const url = await p.evaluate(t => window.render(t), times[i]);
    fs.writeFileSync(path.join(outdir, `f${String(i).padStart(4, '0')}.png`), Buffer.from(url.split(',')[1], 'base64'));
  }
  await b.close();
})();
