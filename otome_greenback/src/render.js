// usage:
//   node render.js preview <outdir>          … 各素材の代表フレームをPNGで書き出し
//   node render.js video <outdir> [name ...] … 1920x1080 30fps のグリーンバックMP4を書き出し
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const { spawn } = require('child_process');
const fs = require('fs'), path = require('path');
const FPS = 30;

(async () => {
  const [mode, outdir, ...only] = process.argv.slice(2);
  fs.mkdirSync(outdir, { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('file://' + path.join(__dirname, 'index.html'));
  const mats = (await p.evaluate(() => window.materials)).filter(([n]) => !only.length || only.includes(n));
  const png = u => Buffer.from(u.split(',')[1], 'base64');

  for (const [i, [name, dur]] of mats.entries()) {
    const idx = String(Object.keys(mats).length && i + 1).padStart(2, '0');
    await p.evaluate(n => window.setMaterial(n), name);
    if (mode === 'preview') {
      for (const t of [0.3, dur * 0.25, dur * 0.6]) {
        fs.writeFileSync(path.join(outdir, `${name}_${t.toFixed(2)}.png`), png(await p.evaluate(t => window.render(t), t)));
      }
      continue;
    }
    const out = path.join(outdir, `${name}_greenback.mp4`);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const n = Math.round(dur * FPS);
    for (let f = 0; f < n; f++) {
      const buf = png(await p.evaluate(t => window.render(t), f / FPS));
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('done', out);
  }
  await b.close();
})();
