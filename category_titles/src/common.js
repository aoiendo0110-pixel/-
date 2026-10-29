// shared pieces for the Valentine title series (same motifs/colours as 各一(Tap♥))
const TAU = Math.PI * 2;
let MINI;
function buildMini() {
  MINI = {
    hp: heartSprite(46, paints.pinkDots, P.pinkDeep, { outline: 9, depth: 5 }),
    hr: heartSprite(40, paints.heartRed, P.redD, { outline: 9, depth: 5 }),
    hc: heartSprite(52, paints.chocBar, P.chocD, { outline: 9, depth: 5 }),
  };
}

// floating decorations: [type, x, y, scale, delay, phaseOffset]
function drawDeco(t, ph, list) {
  list.forEach(([ty, x, y, sc, d, po]) => {
    const s = pop(t, d, 0.5) * sc;
    if (s <= 0) return;
    const by = Math.sin(ph + po) * 8;
    const rot = Math.sin(ph + po * 1.3) * 0.18;
    if (ty === 'star') {
      const tw = 0.75 + 0.25 * Math.abs(Math.sin(ph * 2 + po));
      ctx.save(); ctx.translate(x, y + by); ctx.rotate(rot); ctx.scale(s * tw, s * tw);
      drawSparkle(ctx, 22, '#ffe28a'); ctx.restore();
    } else if (ty === 'bon') {
      ctx.save(); ctx.translate(x, y + by); ctx.rotate(rot); ctx.scale(s, s);
      drawBonbon(ctx, 24); ctx.restore();
    } else blit(MINI[ty], x, y + by, s, rot);
  });
}

// letters: [sprite, x, y, baseRot, delay, bobAmp] — pop + squash like 各一
function drawLetters(t, ph, letters, opt = {}) {
  letters.forEach(([sp, x, y, r, d, amp], i) => {
    let s = pop(t, d), dx = 0;
    if (opt.slide) { // slide in from a side instead of popping
      const k = clamp((t - d) / 0.6);
      if (t < d) return;
      s = 1; dx = (1 - ease.outBack(k, 1.8)) * opt.slide[i];
    }
    const bob = Math.sin(ph - i * 0.75) * amp;
    const wob = Math.sin(ph - i * 0.75 + 1.2) * 0.035;
    const k = clamp((t - d) / 0.35);
    const sq = 1 + Math.sin(k * Math.PI) * 0.08 * (1 - k);
    blit(sp, x + dx, y + bob, s, r + wob, 1 / sq, sq);
  });
}

// bow with flutter
function bowAt(t, ph, x, y, d, sc, rot, mirror = 1) {
  const s = pop(t, d, 0.6);
  if (s <= 0) return;
  ctx.save();
  ctx.translate(x, y + Math.sin(ph) * 9); ctx.rotate(rot + Math.sin(ph * 2) * 0.05); ctx.scale(s * sc * mirror, s * sc);
  drawBow(ctx, 1, Math.sin(ph * 2));
  ctx.restore();
}

// beat timing shared by "tap" hearts: returns {press, beat, bt}
function beatAt(t, start = 1.0) {
  const bt = ((t - start) % 1 + 1) % 1;
  let beat = 1, press = 1;
  if (t > start) {
    press = bt < 0.08 ? 1 - bt / 0.08 * 0.16 : 0.84 + 0.16 * ease.outElastic(clamp((bt - 0.08) / 0.5));
    beat = 1 + Math.max(0, Math.sin(clamp((bt - 0.08) / 0.25) * Math.PI)) * 0.12;
  }
  return { press, beat, bt };
}
function heartRipple(t, x, y, base = 60, start = 1.0) {
  if (t <= start) return;
  const { bt } = beatAt(t, start);
  for (let k = 0; k < 2; k++) {
    const rt = clamp((bt - 0.06 - k * 0.12) / 0.55);
    if (rt <= 0 || rt >= 1) continue;
    const R = base + rt * base, lw = 9 * (1 - rt);
    ctx.save(); ctx.translate(x, y + 6);
    heartPath(ctx, 0, 0, R * 2); ctx.lineJoin = 'round';
    ctx.strokeStyle = P.white; ctx.lineWidth = lw + 4; ctx.stroke();
    ctx.strokeStyle = k ? P.pink : P.red; ctx.lineWidth = lw; ctx.stroke();
    ctx.restore();
  }
}

// pink-coated chocolate stick (used as the "/")
function chocStick(g, len, w) {
  g.save(); g.lineCap = 'round';
  const seg = (x0, x1, lw, col) => { g.beginPath(); g.moveTo(x0, 0); g.lineTo(x1, 0); g.strokeStyle = col; g.lineWidth = lw; g.stroke(); };
  seg(-len / 2, len / 2, w + 16, P.pinkDeep);
  seg(-len / 2, len / 2, w + 10, P.white);
  seg(-len / 2, -len / 2 + len * 0.28, w * 0.75, '#c98a55'); // biscuit handle
  seg(-len / 2 + len * 0.25, len / 2, w, '#ff8fbf');          // strawberry coating
  // chocolate drizzle stripes over the coating
  g.strokeStyle = P.choc; g.lineWidth = 5;
  for (let x = -len / 2 + len * 0.3; x < len / 2 - 6; x += 16) {
    g.beginPath(); g.moveTo(x, -w / 2 + 2); g.lineTo(x + 10, w / 2 - 2); g.stroke();
  }
  g.fillStyle = 'rgba(255,255,255,0.75)'; g.fillRect(-len / 2 + len * 0.3, -w / 2 + 3, len * 0.6, 4);
  g.restore();
}

// rounded name plate with scalloped lace edge all around
function lacePlate(g, x, y, w, h, t) {
  const r = h / 2, sc = 34;
  const outline = (ex) => { g.beginPath(); g.roundRect(x - ex, y - ex, w + ex * 2, h + ex * 2, r + ex); };
  // scallops along the perimeter of a slightly bigger rounded rect
  const per = [];
  const R = r + 16;
  const cx0 = x + r, cx1 = x + w - r, cy = y + r;
  const straight = cx1 - cx0;
  const total = straight * 2 + TAU * R;
  const n = Math.round(total / sc);
  for (let i = 0; i < n; i++) {
    let d = i / n * total, px, py;
    if (d < straight) { px = cx0 + d; py = cy - R; }
    else if ((d -= straight) < Math.PI * R) { const a = -Math.PI / 2 + d / R; px = cx1 + Math.cos(a) * R; py = cy + Math.sin(a) * R; }
    else if ((d -= Math.PI * R) < straight) { px = cx1 - d; py = cy + R; }
    else { d -= straight; const a = Math.PI / 2 + d / R; px = cx0 + Math.cos(a) * R; py = cy + Math.sin(a) * R; }
    per.push([px, py]);
  }
  const wav = Math.sin(t * Math.PI) * 0;
  g.fillStyle = P.pinkDeep; per.forEach(([px, py]) => { g.beginPath(); g.arc(px, py, sc / 2 + 6, 0, TAU); g.fill(); });
  g.fillStyle = P.white; per.forEach(([px, py]) => { g.beginPath(); g.arc(px, py, sc / 2 + 2, 0, TAU); g.fill(); });
  outline(6); g.fillStyle = P.pinkDeep; g.fill();
  outline(0);
  const gr = g.createLinearGradient(0, y, 0, y + h); gr.addColorStop(0, '#ffe3ef'); gr.addColorStop(1, '#ffc2dc');
  g.fillStyle = gr; g.fill();
  // eyelets in the lace
  g.save(); g.globalCompositeOperation = 'destination-out';
  per.forEach(([px, py]) => {
    const vx = px - (x + w / 2), vy = py - cy, l = Math.hypot(vx, vy * (w / h));
    g.beginPath(); g.arc(px + vx / l * 8, py + vy * (w / h) / l * 8, 4.5, 0, TAU); g.fill();
  });
  g.restore();
  // inner stitch + polka dots
  g.save(); outline(0); g.clip();
  g.fillStyle = 'rgba(255,255,255,0.8)';
  for (let yy = y + 14; yy < y + h; yy += 30) for (let xx = x + 14 + ((yy - y) / 30 % 2) * 15; xx < x + w; xx += 30) { g.beginPath(); g.arc(xx, yy, 4.5, 0, TAU); g.fill(); }
  g.restore();
  g.setLineDash([9, 7]); g.strokeStyle = P.pinkD; g.lineWidth = 3; outline(-12); g.stroke(); g.setLineDash([]);
}

const SCENES = {};
window.ready = (async () => {
  const name = new URLSearchParams(location.search).get('scene');
  await new Promise((res, rej) => { const s = document.createElement('script'); s.src = `scene_${name}.js`; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
  await document.fonts.load('900 100px MPR', '一次創作二次元アニメゲーム三/');
  buildMini();
  const sc = SCENES[name];
  sc.build();
  window.render = t => { ctx.clearRect(0, 0, W, H); sc.frame(t, t / 2 * TAU); return cv.toDataURL('image/png'); };
  return true;
})();
