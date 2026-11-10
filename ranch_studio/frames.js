// 連番PNGの書き出し
// usage: node frames.js <outdir> <fps> <秒数> [worker番号] [worker数] ["?クエリ#ハッシュ"]
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const srv = http.createServer((q, s) => {
  const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
  fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); return s.end(); }
    s.writeHead(200, { 'Content-Type': f.endsWith('.js') ? 'text/javascript' : f.endsWith('.html') ? 'text/html' : 'image/png' }); s.end(d); });
}).listen(0);
(async () => {
  const [outdir, fps, dur, wi = '0', wn = '1', qs = ''] = process.argv.slice(2);
  fs.mkdirSync(outdir, { recursive: true });
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  p.on('pageerror', e => console.log('[err]', e.message));
  const [qp, hp] = qs.split('#');
  await p.goto(`http://localhost:${srv.address().port}/ranch_studio/index.html${qp || ''}#still&${hp || ''}`, { timeout: 300000 });
  await p.waitForFunction(() => window.ready, null, { timeout: 300000 });
  const N = Math.round(+fps * +dur);
  for (let i = +wi; i < N; i += +wn) {
    const f = path.join(outdir, `f${String(i).padStart(4, '0')}.png`);
    if (fs.existsSync(f)) continue;
    const url = await p.evaluate(t => window.render(t), i / +fps);
    fs.writeFileSync(f, Buffer.from(url.split(',')[1], 'base64'));
  }
  await b.close(); srv.close();
})();
