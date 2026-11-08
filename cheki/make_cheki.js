// usage: node make_cheki.js  → cheki_*.png を同じフォルダに書き出し
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs'), path = require('path');
const here = __dirname, tapeDir = path.join(here, '../otome_greenback/masking_tape/transparent');
const durl = (f, mime) => `data:${mime};base64,` + fs.readFileSync(f).toString('base64');

const html = `<!doctype html><canvas id=c></canvas><script>
const TAU = Math.PI * 2;
const load = u => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = u; });
const mk = (w, h) => { const k = document.createElement('canvas'); k.width = w; k.height = h; return k; };
let seed = 9; const rnd = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
function heartPath(g, x, y, s) {
  g.beginPath(); g.moveTo(x, y - 0.2 * s);
  g.bezierCurveTo(x - 0.1 * s, y - 0.47 * s, x - 0.52 * s, y - 0.47 * s, x - 0.52 * s, y - 0.12 * s);
  g.bezierCurveTo(x - 0.52 * s, y + 0.15 * s, x - 0.2 * s, y + 0.3 * s, x, y + 0.47 * s);
  g.bezierCurveTo(x + 0.2 * s, y + 0.3 * s, x + 0.52 * s, y + 0.15 * s, x + 0.52 * s, y - 0.12 * s);
  g.bezierCurveTo(x + 0.52 * s, y - 0.47 * s, x + 0.1 * s, y - 0.47 * s, x, y - 0.2 * s); g.closePath();
}
function star(g, x, y, r, rot = 0) { g.beginPath(); for (let i = 0; i < 10; i++) { const a = i / 10 * TAU - Math.PI / 2 + rot, rr = i % 2 ? r * 0.45 : r; g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } g.closePath(); }
function sparkle(g, x, y, r) { g.beginPath(); g.moveTo(x, y - r); g.quadraticCurveTo(x, y, x + r, y); g.quadraticCurveTo(x, y, x, y + r); g.quadraticCurveTo(x, y, x - r, y); g.quadraticCurveTo(x, y, x, y - r); g.closePath(); }
// 手描きペン風：少しガタつかせた線で縁取り
function pen(g, col, w) { g.strokeStyle = col; g.lineWidth = w; g.lineJoin = 'round'; g.lineCap = 'round'; }
function bowSticker(g, x, y, s, rot) {
  g.save(); g.translate(x, y); g.rotate(rot);
  const parts = d => { const p = new Path2D();
    p.moveTo(0, 0); p.bezierCurveTo(d * s * 0.2, -s * 0.45, d * s * 0.62, -s * 0.4, d * s * 0.56, 0); p.bezierCurveTo(d * s * 0.5, s * 0.36, d * s * 0.2, s * 0.3, 0, 0);
    p.moveTo(-d * s * 0.04, s * 0.04); p.lineTo(d * s * 0.32, s * 0.62); p.lineTo(d * s * 0.2, s * 0.52); p.lineTo(d * s * 0.12, s * 0.66); p.lineTo(d * s * 0.06, s * 0.06); return p; };
  const L = parts(-1), R = parts(1);
  g.lineJoin = 'round'; g.strokeStyle = '#fff'; g.lineWidth = s * 0.14; g.stroke(L); g.stroke(R);
  g.fillStyle = '#ff9cc2'; g.fill(L); g.fill(R);
  g.fillStyle = '#fff'; for (const p of [L, R]) { g.save(); g.clip(p); for (let yy = -s; yy < s; yy += s * 0.15) for (let xx = -s; xx < s; xx += s * 0.15) { g.beginPath(); g.arc(xx + ((yy / (s * 0.15)) % 2 ? s * 0.075 : 0), yy, s * 0.03, 0, TAU); g.fill(); } g.restore(); }
  g.fillStyle = '#f2689c'; g.beginPath(); g.ellipse(0, 0, s * 0.1, s * 0.12, 0, 0, TAU); g.fill();
  g.restore();
}

function card(img, variant, fit) {
  const CW = 1080, CH = 1720, k = mk(CW, CH), g = k.getContext('2d');
  const card = new Path2D(); card.roundRect(0, 0, CW, CH, 24);
  g.save(); g.clip(card);
  if (variant === 'pink') {
    g.fillStyle = '#ffd6e5'; g.fillRect(0, 0, CW, CH);
    g.fillStyle = 'rgba(255,255,255,0.75)';
    for (let y = 20, r = 0; y < CH; y += 44, r++) for (let x = (r % 2) * 22; x < CW + 22; x += 44) { g.beginPath(); g.arc(x, y, 5, 0, TAU); g.fill(); }
  } else { g.fillStyle = '#fffdfb'; g.fillRect(0, 0, CW, CH); }
  // 紙の質感
  seed = 3; g.fillStyle = 'rgba(150,110,120,0.035)'; for (let i = 0; i < 9000; i++) g.fillRect(rnd() * CW, rnd() * CH, 1.5, 1.5);
  // 写真（instax mini 比率 46:62）
  const px = 80, py = 96, pw = 920, ph = 1240;
  if (fit) { // 全身が入るように収める（元絵の白背景で余白を埋める）
    g.fillStyle = '#ffffff'; g.fillRect(px, py, pw, ph);
    const sc = Math.min(pw / img.width, (ph - 40) / img.height), dw = img.width * sc, dh = img.height * sc;
    g.drawImage(img, px + (pw - dw) / 2, py + (ph - dh) / 2, dw, dh);
  } else {
    const sa = pw / ph, sw = img.width, sh = sw / sa, sy = Math.min(img.height - sh, 10);
    g.drawImage(img, 0, sy, sw, sh, px, py, pw, ph);
  }
  // ほんのりツヤ
  const gl = g.createLinearGradient(px, py, px + pw, py + ph);
  gl.addColorStop(0, 'rgba(255,255,255,0.10)'); gl.addColorStop(0.3, 'rgba(255,255,255,0)'); gl.addColorStop(0.62, 'rgba(255,255,255,0)'); gl.addColorStop(0.7, 'rgba(255,255,255,0.08)'); gl.addColorStop(0.78, 'rgba(255,255,255,0)');
  g.fillStyle = gl; g.fillRect(px, py, pw, ph);
  g.strokeStyle = 'rgba(90,60,80,0.12)'; g.lineWidth = 3; g.strokeRect(px, py, pw, ph);
  // 下の余白のらくがき（真ん中はメッセージ用にあけておく）
  const by = 1530;
  g.save(); g.translate(205, by - 10); g.rotate(-0.18);
  heartPath(g, 0, 0, 120); g.fillStyle = '#ff8fb8'; g.fill(); pen(g, '#e2588f', 5); g.stroke(); g.restore();
  g.fillStyle = '#fff'; g.beginPath(); g.ellipse(180, by - 32, 13, 8, -0.8, 0, TAU); g.fill();
  g.save(); g.translate(322, by - 78); g.rotate(0.25); heartPath(g, 0, 0, 58); pen(g, '#ff8fb8', 6); g.stroke(); g.restore();
  g.save(); g.translate(300, by + 60); g.rotate(-0.1); heartPath(g, 0, 0, 40); g.fillStyle = '#c9a6f2'; g.fill(); g.restore();
  // 三日月（ブローチに合わせて）
  g.save(); g.translate(865, by - 4); g.rotate(-0.35);
  const m = new Path2D(); m.arc(0, 0, 78, 0, TAU); const cut = new Path2D(); cut.arc(34, -20, 66, 0, TAU);
  g.save(); g.beginPath(); g.rect(-200, -200, 400, 400); g.arc(34, -20, 66, 0, TAU, true); g.clip('evenodd');
  g.fillStyle = '#f6d27a'; g.fill(m); pen(g, '#d9a640', 5); g.stroke(m); g.restore();
  g.restore();
  star(g, 745, by - 70, 26, 0.2); g.fillStyle = '#fff0a6'; g.fill(); pen(g, '#e6b84a', 4); g.stroke();
  star(g, 960, by + 70, 18, -0.2); g.fillStyle = '#d9c2f7'; g.fill(); pen(g, '#a983e0', 3.5); g.stroke();
  sparkle(g, 960, by - 95, 22); g.fillStyle = '#c9a6f2'; g.fill();
  sparkle(g, 720, by + 70, 16); g.fillStyle = '#ffb3cd'; g.fill();
  sparkle(g, 420, by - 20, 14); g.fillStyle = '#ffd36e'; g.fill();
  // 点々のライン（手描き風）
  g.fillStyle = '#ffb3cd'; for (let x = 470; x <= 640; x += 22) { g.beginPath(); g.arc(x, by + 95 + Math.sin(x / 30) * 6, 4, 0, TAU); g.fill(); }
  g.restore();
  // 写真の角にリボンシール
  bowSticker(g, px + pw - 30, py + ph - 10, 150, 0.18);
  return k;
}

window.make = async (srcURL, tapeA, tapeB, variant, bg, fit) => {
  const [img, ta, tb] = await Promise.all([load(srcURL), load(tapeA), load(tapeB)]);
  const OW = 1500, OH = 2100, k = mk(OW, OH), g = k.getContext('2d');
  if (bg) { // ピンクギンガムの背景
    g.fillStyle = '#fff3f7'; g.fillRect(0, 0, OW, OH); g.fillStyle = 'rgba(255,170,200,0.35)';
    for (let x = 0; x < OW; x += 80) g.fillRect(x, 0, 40, OH); for (let y = 0; y < OH; y += 80) g.fillRect(0, y, OW, 40);
  }
  const c = card(img, variant, fit);
  g.save(); g.translate(OW / 2, OH / 2 + 10); g.rotate(-0.045);
  g.shadowColor = 'rgba(150,80,110,0.28)'; g.shadowBlur = 40; g.shadowOffsetY = 14;
  g.drawImage(c, -c.width / 2, -c.height / 2); g.shadowColor = 'transparent';
  const tape = (t, x, y, rot) => { g.save(); g.translate(x, y); g.rotate(rot); const s = 0.6; g.globalAlpha = 0.94; g.drawImage(t, -t.width * s / 2, -t.height * s / 2, t.width * s, t.height * s); g.restore(); };
  tape(ta, -c.width / 2 + 40, -c.height / 2 + 30, -0.72);
  tape(tb, c.width / 2 - 40, -c.height / 2 + 30, 0.7);
  g.restore();
  return k.toDataURL('image/png');
};
</script>`;

(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.setContent(html);
  const SRC = process.env.SRC || 'source.jpg', PRE = process.env.PRE || 'cheki', FIT = !!process.env.FIT;
  const src = durl(path.join(here, SRC), 'image/jpeg');
  const T = n => durl(path.join(tapeDir, n), 'image/png');
  const jobs = [
    [PRE + '_white_transparent', '07_lace_print_short.png', '01_pink_gingham_short.png', 'white', false],
    [PRE + '_white_gingham', '07_lace_print_short.png', '01_pink_gingham_short.png', 'white', true],
    [PRE + '_pink_transparent', '13_sky_heart_short.png', '08_lavender_star_short.png', 'pink', false],
    [PRE + '_pink_gingham', '13_sky_heart_short.png', '08_lavender_star_short.png', 'pink', true],
  ];
  for (const [name, a, bb, v, bg] of jobs) {
    const u = await p.evaluate(([s, x, y, v, bg, f]) => window.make(s, x, y, v, bg, f), [src, T(a), T(bb), v, bg, FIT]);
    fs.writeFileSync(path.join(here, name + '.png'), Buffer.from(u.split(',')[1], 'base64'));
    console.log(name);
  }
  await b.close();
})();
