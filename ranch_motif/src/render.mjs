// HTML 素材をコマ送りで PNG に書き出して ffmpeg で動画にする
//   (リポジトリ直下で)  python3 -m http.server 8765 &
//   node ranch_motif/src/render.mjs <name> [hash] [--still 秒]
// HTML 側は window.SPEC = {w,h,fps,dur,alpha} と window.renderFrame(秒) を用意する
import { createRequire } from 'module';
const { chromium } = createRequire(import.meta.url)('playwright');
import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

const args = process.argv.slice(2);
const name = args[0];
const hash = args[1] && !args[1].startsWith('--') ? args[1] : '';
const stillIdx = args.indexOf('--still');
const still = stillIdx >= 0 ? parseFloat(args[stillIdx + 1]) : null;
const tag = name + (hash ? '_' + hash : '');
const here = path.dirname(new URL(import.meta.url).pathname);
const outDir = path.resolve(here, '..', 'out');
const work = path.resolve(process.env.WORK || '/tmp', 'ranch_frames', tag);
const url = `http://localhost:8765/ranch_motif/src/${name}.html${hash ? '#' + hash : ''}`;
const PAGES = parseInt(process.env.PAGES || '3');

const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
async function openPage() {
  const page = await browser.newPage({ viewport: { width: 400, height: 300 } });
  page.on('console', (m) => { if (m.type() === 'error') console.error('[page]', m.text()); });
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto(url);
  await page.waitForFunction(() => window.SPEC && window.renderFrame && (window.READY === undefined || window.READY === true), null, { timeout: 60000 });
  return page;
}
async function grab(page, t) {
  await page.evaluate(async (t) => { await window.renderFrame(t); }, t);
  const data = await page.evaluate(() => document.getElementById('c').toDataURL('image/png'));
  return Buffer.from(data.split(',')[1], 'base64');
}

const first = await openPage();
const spec = await first.evaluate(() => window.SPEC);
fs.mkdirSync(outDir, { recursive: true });

if (still !== null) {
  fs.writeFileSync(path.join(outDir, `${tag}_still.png`), await grab(first, still));
  await browser.close();
  console.log('still ->', `${tag}_still.png`);
  process.exit(0);
}

fs.rmSync(work, { recursive: true, force: true });
fs.mkdirSync(work, { recursive: true });
const total = Math.round(spec.fps * spec.dur);
const pages = [first];
for (let i = 1; i < PAGES; i++) pages.push(await openPage());
let next = 0, done = 0;
const t0 = Date.now();
await Promise.all(pages.map(async (p) => {
  while (next < total) {
    const i = next++;
    fs.writeFileSync(path.join(work, `f${String(i).padStart(5, '0')}.png`), await grab(p, i / spec.fps));
    if (++done % 30 === 0) console.log(`${tag}: ${done}/${total} (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
}));
await browser.close();

const ff = (a) => execFileSync('ffmpeg', ['-y', '-v', 'error', ...a], { stdio: 'inherit' });
const inp = ['-framerate', String(spec.fps), '-i', path.join(work, 'f%05d.png')];
if (spec.alpha) {
  // 透過 WebM (VP9 alpha)
  ff([...inp, '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-b:v', '0', '-crf', '30', '-row-mt', '1', '-auto-alt-ref', '0', path.join(outDir, `${tag}_transparent.webm`)]);
  // パープルバック MP4 (クロマキー用。色は KEY=0xRRGGBB で変更可)
  const key = process.env.KEY || '0x8000ff';
  ff([...inp, '-filter_complex', `color=${key}:s=${spec.w}x${spec.h}:r=${spec.fps}[bg];[bg][0]overlay=shortest=1,format=yuv420p`,
    '-c:v', 'libx264', '-crf', '17', '-preset', 'slow', '-movflags', '+faststart', path.join(outDir, `${tag}_purpleback.mp4`)]);
  // 透過 MOV (ProRes 4444, 編集ソフト用)
  if (process.env.PRORES) ff([...inp, '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0', path.join(outDir, `${tag}_alpha.mov`)]);
} else {
  ff([...inp, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17', '-preset', 'slow', '-movflags', '+faststart', path.join(outDir, `${tag}.mp4`)]);
  ff([...inp, '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuv420p', '-b:v', '0', '-crf', '32', '-row-mt', '1', path.join(outDir, `${tag}.webm`)]);
}
// サムネ (中間のコマ)
fs.copyFileSync(path.join(work, `f${String(Math.floor(total / 2)).padStart(5, '0')}.png`), path.join(outDir, `${tag}_thumb.png`));
console.log(`done ${tag} in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
