// 月夜のゆめかわチェキ（横長・顔アップ）
// usage: node make_cheki_v2.js  → cheki3_*.png
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs'), path = require('path');
const here = __dirname;
const durl = f => 'data:image/png;base64,' + fs.readFileSync(f).toString('base64');

const html = `<!doctype html><script>
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
function starPath(g, x, y, r, rot = 0, k = 0.45) { g.beginPath(); for (let i = 0; i < 10; i++) { const a = i / 10 * TAU - Math.PI / 2 + rot, rr = i % 2 ? r * k : r; g.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } g.closePath(); }
function sparkle(g, x, y, r, col) { g.fillStyle = col; g.beginPath(); g.moveTo(x, y - r); g.quadraticCurveTo(x + r * .1, y - r * .1, x + r, y); g.quadraticCurveTo(x + r * .1, y + r * .1, x, y + r); g.quadraticCurveTo(x - r * .1, y + r * .1, x - r, y); g.quadraticCurveTo(x - r * .1, y - r * .1, x, y - r); g.fill(); }
function crescent(g, x, y, r, rot, fill, line) {
  const R = Math.ceil(r * 1.3), k = mk(R * 2, R * 2), m = k.getContext('2d');
  const shape = col => { const c = mk(R * 2, R * 2), q = c.getContext('2d');
    q.translate(R, R); q.rotate(rot); q.fillStyle = col; q.beginPath(); q.arc(0, 0, r, 0, TAU); q.fill();
    q.globalCompositeOperation = 'destination-out'; q.beginPath(); q.arc(r * 0.45, -r * 0.25, r * 0.8, 0, TAU); q.fill(); return c; };
  if (line) { const lc = shape(line), w = Math.max(2, r * 0.06);
    for (let i = 0; i < 16; i++) { const a = i / 16 * TAU; m.drawImage(lc, Math.cos(a) * w, Math.sin(a) * w); } }
  m.drawImage(shape(fill), 0, 0);
  g.drawImage(k, x - R, y - R);
}
// つやつやのラインストーン風ハートシール
function gemHeart(g, x, y, s, rot, c1, c2) {
  g.save(); g.translate(x, y); g.rotate(rot);
  heartPath(g, 0, 0, s); g.lineJoin = 'round'; g.strokeStyle = '#fff'; g.lineWidth = s * 0.14; g.stroke();
  const gr = g.createLinearGradient(-s / 2, -s / 2, s / 2, s / 2); gr.addColorStop(0, c1); gr.addColorStop(1, c2);
  g.fillStyle = gr; g.fill();
  g.fillStyle = 'rgba(255,255,255,0.85)'; g.beginPath(); g.ellipse(-s * 0.22, -s * 0.16, s * 0.12, s * 0.06, -0.7, 0, TAU); g.fill();
  g.beginPath(); g.arc(-s * 0.06, -s * 0.24, s * 0.03, 0, TAU); g.fill();
  g.restore();
}
// サテンの大きいリボン
function satinBow(g, x, y, s) {
  g.save(); g.translate(x, y);
  const grad = (x0, y0, x1, y1) => { const gr = g.createLinearGradient(x0, y0, x1, y1);
    gr.addColorStop(0, '#fbd3ec'); gr.addColorStop(0.45, '#e7b6f2'); gr.addColorStop(1, '#c8a2f0'); return gr; };
  const tail = d => { g.beginPath(); g.moveTo(d * s * 0.05, s * 0.05);
    g.bezierCurveTo(d * s * 0.2, s * 0.3, d * s * 0.12, s * 0.6, d * s * 0.32, s * 0.95);
    g.lineTo(d * s * 0.2, s * 0.86); g.lineTo(d * s * 0.12, s * 1.0);
    g.bezierCurveTo(d * s * -0.02, s * 0.6, d * s * 0.04, s * 0.3, d * s * -0.06, s * 0.08); g.closePath(); };
  const loop = d => { g.beginPath(); g.moveTo(0, 0);
    g.bezierCurveTo(d * s * 0.25, -s * 0.5, d * s * 0.78, -s * 0.42, d * s * 0.7, 0);
    g.bezierCurveTo(d * s * 0.66, s * 0.36, d * s * 0.25, s * 0.3, 0, 0); g.closePath(); };
  g.lineJoin = 'round';
  for (const d of [-1, 1]) { tail(d); g.strokeStyle = '#fff'; g.lineWidth = s * 0.05; g.stroke(); g.fillStyle = grad(0, 0, d * s * 0.3, s); g.fill(); g.strokeStyle = '#b48ae6'; g.lineWidth = s * 0.012; g.stroke(); }
  for (const d of [-1, 1]) { loop(d); g.strokeStyle = '#fff'; g.lineWidth = s * 0.05; g.stroke(); g.fillStyle = grad(0, -s * 0.4, d * s * 0.7, s * 0.3); g.fill(); g.strokeStyle = '#b48ae6'; g.lineWidth = s * 0.012; g.stroke();
    // 光沢
    g.strokeStyle = 'rgba(255,255,255,0.8)'; g.lineWidth = s * 0.03; g.lineCap = 'round';
    g.beginPath(); g.moveTo(d * s * 0.2, -s * 0.22); g.quadraticCurveTo(d * s * 0.45, -s * 0.32, d * s * 0.6, -s * 0.15); g.stroke();
    // ひだ
    g.strokeStyle = 'rgba(170,120,220,0.55)'; g.lineWidth = s * 0.015;
    g.beginPath(); g.moveTo(d * s * 0.08, -s * 0.03); g.quadraticCurveTo(d * s * 0.3, -s * 0.08, d * s * 0.42, s * 0.08); g.stroke(); }
  g.beginPath(); g.roundRect(-s * 0.1, -s * 0.12, s * 0.2, s * 0.24, s * 0.07);
  g.strokeStyle = '#fff'; g.lineWidth = s * 0.04; g.stroke(); g.fillStyle = grad(-s * 0.1, -s * 0.1, s * 0.1, s * 0.1); g.fill();
  g.strokeStyle = '#b48ae6'; g.lineWidth = s * 0.012; g.stroke();
  // 真ん中のパール
  const pg = g.createRadialGradient(-s * 0.02, -s * 0.03, 1, 0, 0, s * 0.06); pg.addColorStop(0, '#fff'); pg.addColorStop(1, '#f1dcef');
  g.fillStyle = pg; g.beginPath(); g.arc(0, 0, s * 0.055, 0, TAU); g.fill();
  g.restore();
}

function card(img) {
  const PW = 1250, PH = 1000, M = 80, BOT = 270, CW = PW + M * 2, CH = PH + M + BOT;
  const k = mk(CW, CH), g = k.getContext('2d');
  const cardP = new Path2D(); cardP.roundRect(0, 0, CW, CH, 28);
  g.save(); g.clip(cardP);
  const cg = g.createLinearGradient(0, 0, 0, CH); cg.addColorStop(0, '#efe5ff'); cg.addColorStop(1, '#ffe4f0');
  g.fillStyle = cg; g.fillRect(0, 0, CW, CH);
  // 金の小さな星と月の総柄
  seed = 21;
  for (let y = 30, r = 0; y < CH; y += 70, r++) for (let x = (r % 2) * 45 + 20; x < CW; x += 90) {
    const jx = x + (rnd() - .5) * 16, jy = y + (rnd() - .5) * 16;
    if ((r + Math.round(x / 90)) % 4 === 0) crescent(g, jx, jy, 9, -0.5, 'rgba(232,190,95,0.55)');
    else { starPath(g, jx, jy, 6 + rnd() * 3, rnd()); g.fillStyle = (r % 2 ? 'rgba(232,190,95,0.5)' : 'rgba(255,255,255,0.9)'); g.fill(); }
  }
  g.fillStyle = 'rgba(130,90,140,0.03)'; for (let i = 0; i < 12000; i++) g.fillRect(rnd() * CW, rnd() * CH, 1.5, 1.5);
  // 写真のまわりのレース（スカラップ＋パール）
  const lace = (x0, y0, x1, y1) => { const L = Math.hypot(x1 - x0, y1 - y0), n = Math.round(L / 34), dx = (x1 - x0) / n, dy = (y1 - y0) / n;
    for (let i = 0; i <= n; i++) { g.fillStyle = '#fff'; g.beginPath(); g.arc(x0 + dx * i, y0 + dy * i, 19, 0, TAU); g.fill(); } };
  const ox = M, oy = M;
  lace(ox, oy, ox + PW, oy); lace(ox + PW, oy, ox + PW, oy + PH); lace(ox + PW, oy + PH, ox, oy + PH); lace(ox, oy + PH, ox, oy);
  g.fillStyle = '#f6cde2';
  const pearls = (x0, y0, x1, y1) => { const L = Math.hypot(x1 - x0, y1 - y0), n = Math.round(L / 34), dx = (x1 - x0) / n, dy = (y1 - y0) / n, nx = -(y1 - y0) / L, ny = (x1 - x0) / L;
    for (let i = 0; i <= n; i++) { g.beginPath(); g.arc(x0 + dx * i - nx * 9, y0 + dy * i - ny * 9, 3.6, 0, TAU); g.fill(); } };
  pearls(ox, oy, ox + PW, oy); pearls(ox + PW, oy, ox + PW, oy + PH); pearls(ox + PW, oy + PH, ox, oy + PH); pearls(ox, oy + PH, ox, oy);
  // ===== 写真 =====
  g.save(); g.beginPath(); g.rect(ox, oy, PW, PH); g.clip(); g.translate(ox, oy);
  const sky = g.createLinearGradient(0, 0, 0, PH); sky.addColorStop(0, '#c9b5f4'); sky.addColorStop(0.55, '#f3c6e4'); sky.addColorStop(1, '#ffe5d8');
  g.fillStyle = sky; g.fillRect(0, 0, PW, PH);
  seed = 5;
  for (let i = 0; i < 26; i++) { const x = rnd() * PW, y = rnd() * PH, r = 20 + rnd() * 70; const bg = g.createRadialGradient(x, y, 0, x, y, r);
    bg.addColorStop(0, 'rgba(255,255,255,0.35)'); bg.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = bg; g.fillRect(x - r, y - r, r * 2, r * 2); }
  // 月（ふんわり光る）
  const mg = g.createRadialGradient(440, 150, 40, 440, 150, 210); mg.addColorStop(0, 'rgba(255,248,214,0.8)'); mg.addColorStop(1, 'rgba(255,248,214,0)');
  g.fillStyle = mg; g.fillRect(200, 0, 480, 380);
  crescent(g, 440, 150, 82, -0.45, '#fff4c4');
  for (let i = 0; i < 40; i++) { const x = rnd() * PW, y = rnd() * PH * 0.6; sparkle(g, x, y, 3 + rnd() * 9, rnd() < .3 ? '#fff6c8' : '#ffffff'); }
  const sc = PW / img.width; g.drawImage(img, 0, PH - img.height * sc, PW, img.height * sc);
  // ツヤ
  const gl = g.createLinearGradient(0, 0, PW, PH); gl.addColorStop(0, 'rgba(255,255,255,0.13)'); gl.addColorStop(0.28, 'rgba(255,255,255,0)'); gl.addColorStop(0.66, 'rgba(255,255,255,0)'); gl.addColorStop(0.72, 'rgba(255,255,255,0.08)'); gl.addColorStop(0.8, 'rgba(255,255,255,0)');
  g.fillStyle = gl; g.fillRect(0, 0, PW, PH);
  g.restore();
  g.strokeStyle = '#fff'; g.lineWidth = 6; g.strokeRect(ox, oy, PW, PH);
  // ===== 下の余白（真ん中はメッセージ用に空けてある） =====
  const by = oy + PH + BOT / 2 + 5;
  gemHeart(g, 150, by + 8, 92, -0.22, '#ffb3d1', '#f06d9f');
  gemHeart(g, 255, by - 30, 66, 0.12, '#e3cdfb', '#b48ae6');
  gemHeart(g, 345, by + 26, 54, -0.05, '#cfe8ff', '#8fc3f2');
  sparkle(g, 300, by - 92, 16, '#f2c95e'); sparkle(g, 75, by - 70, 12, '#c9a6f2'); sparkle(g, 420, by - 40, 10, '#ffb3d1');
  // 右：三日月と星のチャーム
  g.strokeStyle = '#e2b85b'; g.lineWidth = 3; g.setLineDash([2, 6]); g.lineCap = 'round';
  g.beginPath(); g.moveTo(CW - 330, by - 110); g.quadraticCurveTo(CW - 260, by - 40, CW - 180, by - 105); g.stroke(); g.setLineDash([]);
  crescent(g, CW - 165, by + 10, 78, -0.4, '#f8d77e', '#d9a640');
  starPath(g, CW - 290, by + 18, 30, 0.15); g.fillStyle = '#fff2a8'; g.fill(); g.strokeStyle = '#e2b85b'; g.lineWidth = 4; g.stroke();
  starPath(g, CW - 345, by - 55, 17, -0.2); g.fillStyle = '#e3cdfb'; g.fill(); g.strokeStyle = '#b48ae6'; g.lineWidth = 3; g.stroke();
  sparkle(g, CW - 80, by - 85, 18, '#ffffff'); sparkle(g, CW - 230, by + 95, 12, '#f2c95e');
  g.restore();
  // 写真の角のキラキラ星シール
  g.save(); g.translate(ox + PW - 20, oy + 24); g.rotate(0.25);
  starPath(g, 0, 0, 62, 0, 0.5); g.lineJoin = 'round'; g.strokeStyle = '#fff'; g.lineWidth = 14; g.stroke();
  const sg = g.createLinearGradient(-50, -50, 50, 50); sg.addColorStop(0, '#fff6c2'); sg.addColorStop(1, '#f2c95e'); g.fillStyle = sg; g.fill();
  g.fillStyle = 'rgba(255,255,255,0.9)'; g.beginPath(); g.ellipse(-14, -18, 10, 5, -0.6, 0, TAU); g.fill();
  g.restore();
  return k;
}

window.make = async (srcURL, bg) => {
  const img = await load(srcURL);
  const OW = 1800, OH = 1720, k = mk(OW, OH), g = k.getContext('2d');
  if (bg) {
    const bgg = g.createLinearGradient(0, 0, 0, OH); bgg.addColorStop(0, '#d9c8fa'); bgg.addColorStop(1, '#ffd9ea');
    g.fillStyle = bgg; g.fillRect(0, 0, OW, OH); seed = 77;
    for (let i = 0; i < 14; i++) { const x = rnd() * OW, y = rnd() * OH, r = 80 + rnd() * 160, cg = g.createRadialGradient(x, y, 0, x, y, r);
      cg.addColorStop(0, 'rgba(255,255,255,0.45)'); cg.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = cg; g.fillRect(x - r, y - r, r * 2, r * 2); }
    for (let i = 0; i < 70; i++) sparkle(g, rnd() * OW, rnd() * OH, 4 + rnd() * 12, rnd() < .3 ? '#fff3b8' : '#ffffff');
  }
  const c = card(img);
  g.save(); g.translate(OW / 2, OH / 2 + 40); g.rotate(0.03);
  g.shadowColor = 'rgba(130,80,150,0.3)'; g.shadowBlur = 45; g.shadowOffsetY = 16;
  g.drawImage(c, -c.width / 2, -c.height / 2); g.shadowColor = 'transparent';
  g.save(); g.translate(-c.width / 2 + 95, -c.height / 2 + 70); g.rotate(-0.42); satinBow(g, 0, 0, 280); g.restore();
  g.restore();
  return k.toDataURL('image/png');
};
</script>`;

(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.setContent(html);
  const src = durl(path.join(here, 'source2_cut.png'));
  for (const [name, bg] of [['cheki3_moon_dreamy', true], ['cheki3_moon_transparent', false]]) {
    const u = await p.evaluate(([s, bg]) => window.make(s, bg), [src, bg]);
    fs.writeFileSync(path.join(here, name + '.png'), Buffer.from(u.split(',')[1], 'base64'));
    console.log(name);
  }
  await b.close();
})();
