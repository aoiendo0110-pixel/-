// shared drawing engine for the 1500x500 green-back typography scenes
const W = 1500, H = 500;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const SS = 2; // sprite supersampling
const TAU = Math.PI * 2;

const ease = {
  outBack: (x, s = 2.2) => 1 + (s + 1) * Math.pow(x - 1, 3) + s * Math.pow(x - 1, 2),
  outElastic: x => x <= 0 ? 0 : x >= 1 ? 1 : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * (TAU / 3)) + 1,
  outCubic: x => 1 - Math.pow(1 - x, 3),
};
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, k) => a + (b - a) * k;
function mk(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
const pop = (t, t0, d = 0.55, s = 2.6) => t < t0 ? 0 : ease.outBack(clamp((t - t0) / d), s);
function grad(g, h, ...stops) {
  const gr = g.createLinearGradient(0, 0, 0, h);
  stops.forEach((c, i) => gr.addColorStop(i / (stops.length - 1), c));
  return gr;
}

function heartPath(g, cx, cy, s) {
  const w = s / 2, h = s * 0.92;
  g.beginPath();
  g.moveTo(cx, cy + h * 0.5);
  g.bezierCurveTo(cx - w * 0.15, cy + h * 0.38, cx - w, cy + h * 0.05, cx - w, cy - h * 0.2);
  g.bezierCurveTo(cx - w, cy - h * 0.5, cx - w * 0.45, cy - h * 0.62, cx, cy - h * 0.28);
  g.bezierCurveTo(cx + w * 0.45, cy - h * 0.62, cx + w, cy - h * 0.5, cx + w, cy - h * 0.2);
  g.bezierCurveTo(cx + w, cy + h * 0.05, cx + w * 0.15, cy + h * 0.38, cx, cy + h * 0.5);
  g.closePath();
}
function starPath(g, r, n = 4, inner = 0.32) {
  g.beginPath();
  for (let i = 0; i < n * 2; i++) {
    const a = i * Math.PI / n - Math.PI / 2, rr = i % 2 ? r * inner : r;
    i ? g.lineTo(Math.cos(a) * rr, Math.sin(a) * rr) : g.moveTo(Math.cos(a) * rr, Math.sin(a) * rr);
  }
  g.closePath();
}
// outlined shape helper: rim colors from outside in, then fill
function rimFill(g, pathFn, rims, fill) {
  g.lineJoin = 'round'; g.lineCap = 'round';
  rims.forEach(([col, lw]) => { pathFn(); g.strokeStyle = col; g.lineWidth = lw; g.stroke(); });
  pathFn(); g.fillStyle = fill; g.fill();
}
function sparkle(g, r, col, rim = '#ffffff', edge = '#5b3a9e') {
  rimFill(g, () => starPath(g, r), [[edge, 9], [rim, 5]], col);
}

// Layered sticker sprite: extrusion shadow + outline + patterned fill
function sticker(size, shapeFn, opt) {
  const pad = 44 * SS;
  const cw = Math.ceil(size.w * SS + pad * 2), ch = Math.ceil(size.h * SS + pad * 2);
  const out = mk(cw, ch), g = out.getContext('2d');
  const outline = (opt.outline ?? 14) * SS, depth = (opt.depth ?? 8) * SS;
  const dir = opt.dir ?? [0.55, 1];
  const draw = (gg, dx, dy, mode, style, lw) => {
    gg.save(); gg.translate(pad + dx, pad + dy); gg.scale(SS, SS);
    gg.lineJoin = 'round'; gg.lineCap = 'round';
    shapeFn(gg, mode, style, lw / SS);
    gg.restore();
  };
  for (let i = depth; i >= 0; i -= 1) draw(g, i * dir[0], i * dir[1], 'stroke', opt.shadow, outline + (opt.edge ?? 5) * SS);
  if (opt.outer) draw(g, 0, 0, 'stroke', opt.outer, outline + (opt.edge ?? 5) * SS);
  draw(g, 0, 0, 'stroke', opt.rim ?? '#ffffff', outline);
  const f = mk(cw, ch), fg = f.getContext('2d');
  draw(fg, 0, 0, 'fill', '#000', 0);
  fg.globalCompositeOperation = 'source-atop';
  fg.save(); fg.translate(pad, pad); fg.scale(SS, SS);
  opt.paint(fg, size.w, size.h);
  fg.restore();
  if (opt.inner) draw(fg, 0, 0, 'stroke', opt.inner, (opt.innerW ?? 4) * SS);
  g.drawImage(f, 0, 0);
  return { c: out, ox: pad / SS, oy: pad / SS, w: size.w, h: size.h };
}

function measure(ch, font) {
  ctx.font = font;
  const m = ctx.measureText(ch);
  return {
    l: m.actualBoundingBoxLeft, a: m.actualBoundingBoxAscent,
    w: Math.ceil(m.actualBoundingBoxLeft + m.actualBoundingBoxRight),
    h: Math.ceil(m.actualBoundingBoxAscent + m.actualBoundingBoxDescent),
  };
}
function glyph(ch, font, opt) {
  const m = measure(ch, font);
  return sticker({ w: m.w, h: m.h }, (g, mode, style, lw) => {
    g.font = font; g.textBaseline = 'alphabetic';
    if (mode === 'stroke') { g.strokeStyle = style; g.lineWidth = lw; g.strokeText(ch, m.l, m.a); }
    else { g.fillStyle = style; g.fillText(ch, m.l, m.a); }
  }, opt);
}
function shapeSprite(w, h, pathFn, opt) {
  return sticker({ w, h }, (g, mode, style, lw) => {
    pathFn(g);
    if (mode === 'stroke') { g.strokeStyle = style; g.lineWidth = lw; g.stroke(); }
    else { g.fillStyle = style; g.fill(); }
  }, opt);
}

// draw sprite centred on its shape box
function blit(sp, cx, cy, sc = 1, rot = 0, sx = 1, sy = 1) {
  if (sc <= 0.001) return;
  ctx.save();
  ctx.translate(cx, cy); ctx.rotate(rot); ctx.scale(sc * sx, sc * sy);
  ctx.drawImage(sp.c, -(sp.ox + sp.w / 2), -(sp.oy + sp.h / 2), sp.c.width / SS, sp.c.height / SS);
  ctx.restore();
}
function shine(g, w, h, a = 0.8) {
  g.fillStyle = `rgba(255,255,255,${a})`;
  g.beginPath(); g.ellipse(w * 0.26, h * 0.16, Math.min(w * 0.14, 34), Math.min(h * 0.045, 9), -0.35, 0, 7); g.fill();
  g.beginPath(); g.arc(w * 0.44, h * 0.11, Math.min(w, h) * 0.03 + 2, 0, 7); g.fill();
}

// scenes register here: { fonts: [...], build(), frame(t) }
const SCENES = {};
window.ready = (async () => {
  const name = new URLSearchParams(location.search).get('scene');
  await new Promise((res, rej) => { const s = document.createElement('script'); s.src = `scene_${name}.js`; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
  const sc = SCENES[name];
  for (const f of sc.fonts) await document.fonts.load(f[0], f[1]);
  sc.build();
  window.render = t => { ctx.clearRect(0, 0, W, H); sc.frame(t); return cv.toDataURL('image/png'); };
  return true;
})();
