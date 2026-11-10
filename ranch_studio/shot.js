// usage: node shot.js <out.png> "<query+hash>" [t]
//   例: node shot.js out.png "#view=wire" 2
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..');
const srv = http.createServer((q, s) => {
  const f = path.join(ROOT, decodeURIComponent(q.url.split('?')[0]));
  fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); return s.end(); }
    s.writeHead(200, { 'Content-Type': f.endsWith('.js') ? 'text/javascript' : f.endsWith('.html') ? 'text/html' : 'image/png' }); s.end(d); });
}).listen(0);
(async () => {
  const [out, qs = '', t = '2'] = process.argv.slice(2);
  const port = srv.address().port;
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  p.on('console', m => console.log('[page]', m.text())); p.on('pageerror', e => console.log('[err]', e.message));
  const [qp, hp] = qs.split('#');
  await p.goto(`http://localhost:${port}/ranch_studio/index.html${qp || ''}#still&${hp || ''}`, { timeout: 300000 });
  await p.waitForFunction(() => window.ready, null, { timeout: 300000 });
  if (process.env.STATS) console.log(JSON.stringify(await p.evaluate(() => window.stats()), null, 1));
  const url = await p.evaluate(t => window.render(t), +t);
  fs.writeFileSync(out, Buffer.from(url.split(',')[1], 'base64'));
  await b.close(); srv.close();
})();
