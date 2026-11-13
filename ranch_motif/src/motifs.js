// 牧場・クローバー・お花・フリル・ハート・レース 共通パーツ (Canvas 2D)
// 各素材の HTML から <script src="motifs.js"> で読み込む。グローバル M に入る。
(function () {
  const TAU = Math.PI * 2;
  const C = {
    pink: '#ff8fba', pinkL: '#ffd3e3', pinkLL: '#ffe9f1', pinkD: '#f0679c', pinkDD: '#d94f86',
    yel: '#ffe169', yelL: '#fff4b8', yelD: '#f5c63c',
    grn: '#b5e26a', grnL: '#e0f5a8', grnD: '#86c443', grnDD: '#5fa33a',
    white: '#fffdf8', cream: '#fff8ec',
  };

  // 0..1 の周期関数たち (ループ用)
  const wave = (t, phase = 0) => Math.sin(TAU * t + phase);
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const ease = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
  const easeOutBack = (x) => { x = clamp(x); const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
  const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);

  // 決まった乱数 (毎回同じ配置になるように)
  function rng(seed) {
    let s = seed >>> 0 || 1;
    return () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
  }

  function tf(ctx, x, y, rot, sx, sy, fn) {
    ctx.save(); ctx.translate(x, y); if (rot) ctx.rotate(rot); if (sx !== 1 || sy !== 1) ctx.scale(sx, sy); fn(); ctx.restore();
  }

  // --- ハート -----------------------------------------------------------
  // 幅 1 (中心原点、上向き) のハートパス
  function heartPath(ctx, s) {
    ctx.beginPath();
    const n = 64;
    for (let i = 0; i <= n; i++) {
      const t = (i / n) * TAU;
      const x = 16 * Math.pow(Math.sin(t), 3);
      const y = -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t));
      const px = (x / 34) * s, py = ((y + 1.5) / 34) * s;
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
  }
  function heart(ctx, x, y, size, rot = 0, col = C.pink, opt = {}) {
    tf(ctx, x, y, rot, opt.sx ?? 1, 1, () => {
      heartPath(ctx, size);
      if (opt.outline !== false) { ctx.lineWidth = size * 0.07; ctx.strokeStyle = opt.stroke || C.white; ctx.lineJoin = 'round'; ctx.stroke(); }
      const g = ctx.createRadialGradient(-size * 0.15, -size * 0.2, size * 0.05, 0, 0, size * 0.7);
      g.addColorStop(0, opt.light || lighten(col, 0.35)); g.addColorStop(1, col);
      ctx.fillStyle = g; ctx.fill();
      if (opt.shine !== false) {
        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        ctx.beginPath(); ctx.ellipse(-size * 0.22, -size * 0.18, size * 0.09, size * 0.05, -0.7, 0, TAU); ctx.fill();
        ctx.beginPath(); ctx.arc(-size * 0.1, -size * 0.27, size * 0.025, 0, TAU); ctx.fill();
      }
    });
  }

  // --- クローバー -------------------------------------------------------
  function leafPath(ctx, s) { // 先端が原点、丸い側が -y 方向のハート形の葉
    ctx.beginPath();
    const n = 48;
    for (let i = 0; i <= n; i++) {
      const t = (i / n) * TAU;
      const x = 16 * Math.pow(Math.sin(t), 3);
      const y = -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t));
      const px = (x / 32) * s, py = ((y - 17) / 32) * s * 0.95;
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath();
  }
  function clover(ctx, x, y, size, rot = 0, opt = {}) {
    const leaves = opt.leaves ?? 4;
    const col = opt.col || C.grn, dark = opt.dark || C.grnD;
    tf(ctx, x, y, rot, opt.sx ?? 1, 1, () => {
      if (opt.stem !== false) {
        ctx.strokeStyle = dark; ctx.lineWidth = size * 0.07; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.quadraticCurveTo(size * 0.12, size * 0.4, size * 0.05, size * 0.75); ctx.stroke();
      }
      const ls = size * 0.52;
      for (let i = 0; i < leaves; i++) {
        tf(ctx, 0, 0, (i / leaves) * TAU + (leaves === 4 ? Math.PI / 4 : 0), 1, 1, () => {
          leafPath(ctx, ls);
          ctx.lineWidth = size * 0.05; ctx.strokeStyle = opt.stroke || C.white; ctx.stroke();
          const g = ctx.createLinearGradient(0, 0, 0, -ls);
          g.addColorStop(0, dark); g.addColorStop(1, col);
          ctx.fillStyle = g; ctx.fill();
          // 葉脈と白い模様
          ctx.strokeStyle = 'rgba(255,255,255,0.55)'; ctx.lineWidth = size * 0.022;
          ctx.beginPath(); ctx.moveTo(0, -ls * 0.08); ctx.lineTo(0, -ls * 0.62); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(-ls * 0.25, -ls * 0.42); ctx.quadraticCurveTo(0, -ls * 0.3, ls * 0.25, -ls * 0.42); ctx.stroke();
        });
      }
      ctx.fillStyle = opt.center || C.grnL; ctx.beginPath(); ctx.arc(0, 0, size * 0.06, 0, TAU); ctx.fill();
    });
  }

  // --- お花 -------------------------------------------------------------
  function daisy(ctx, x, y, size, rot = 0, opt = {}) {
    const n = opt.petals ?? 12;
    const pc = opt.petal || C.white, cc = opt.center || C.yel;
    const open = opt.open ?? 1;
    tf(ctx, x, y, rot, opt.sx ?? 1, 1, () => {
      for (let i = 0; i < n; i++) {
        tf(ctx, 0, 0, (i / n) * TAU, 1, 1, () => {
          ctx.beginPath(); ctx.ellipse(0, -size * 0.3 * open, size * 0.1, size * 0.24 * open, 0, 0, TAU);
          ctx.fillStyle = pc; ctx.fill();
          ctx.lineWidth = size * 0.018; ctx.strokeStyle = opt.petalLine || 'rgba(240,120,170,0.35)'; ctx.stroke();
        });
      }
      const g = ctx.createRadialGradient(-size * 0.04, -size * 0.04, 0, 0, 0, size * 0.17);
      g.addColorStop(0, C.yelL); g.addColorStop(1, cc);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, size * 0.16, 0, TAU); ctx.fill();
      ctx.fillStyle = 'rgba(230,160,40,0.55)';
      for (let i = 0; i < 7; i++) { const a = i * 2.4; const r = size * 0.09 * Math.sqrt(i / 7); ctx.beginPath(); ctx.arc(Math.cos(a) * r, Math.sin(a) * r, size * 0.018, 0, TAU); ctx.fill(); }
    });
  }
  // まるい花びら5枚の小花
  function blossom(ctx, x, y, size, rot = 0, opt = {}) {
    const n = opt.petals ?? 5, pc = opt.petal || C.pink, open = opt.open ?? 1;
    tf(ctx, x, y, rot, 1, 1, () => {
      for (let i = 0; i < n; i++) {
        tf(ctx, 0, 0, (i / n) * TAU, 1, 1, () => {
          ctx.beginPath(); ctx.arc(0, -size * 0.26 * open, size * 0.22 * (0.5 + 0.5 * open), 0, TAU);
          const g = ctx.createRadialGradient(0, -size * 0.1, 0, 0, -size * 0.26, size * 0.26);
          g.addColorStop(0, opt.inner || C.white); g.addColorStop(1, pc);
          ctx.fillStyle = g; ctx.fill();
          ctx.lineWidth = size * 0.03; ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.stroke();
        });
      }
      ctx.fillStyle = opt.center || C.yel; ctx.beginPath(); ctx.arc(0, 0, size * 0.11, 0, TAU); ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.arc(-size * 0.03, -size * 0.03, size * 0.035, 0, TAU); ctx.fill();
    });
  }
  function tulip(ctx, x, y, size, rot = 0, opt = {}) {
    const col = opt.col || C.pink, dark = opt.dark || C.pinkD, open = opt.open ?? 1;
    tf(ctx, x, y, rot, 1, 1, () => {
      if (opt.stem !== false) {
        ctx.strokeStyle = C.grnD; ctx.lineWidth = size * 0.08; ctx.lineCap = 'round';
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, size * 1.1); ctx.stroke();
        ctx.fillStyle = C.grn;
        ctx.beginPath(); ctx.moveTo(0, size * 1.05); ctx.quadraticCurveTo(size * 0.5, size * 0.75, size * 0.42, size * 0.35); ctx.quadraticCurveTo(size * 0.12, size * 0.7, 0, size * 1.05); ctx.fill();
      }
      const w = size * 0.42 * (0.7 + 0.3 * open), h = size * 0.62;
      const g = ctx.createLinearGradient(0, -h, 0, h * 0.2);
      g.addColorStop(0, lighten(col, 0.3)); g.addColorStop(1, dark);
      // 後ろの花びら
      ctx.fillStyle = dark;
      ctx.beginPath(); ctx.moveTo(-w, -h * 0.75); ctx.quadraticCurveTo(-w * 1.1, h * 0.15, 0, h * 0.18); ctx.quadraticCurveTo(w * 1.1, h * 0.15, w, -h * 0.75); ctx.lineTo(w * 0.45, -h * 0.4); ctx.lineTo(0, -h * 0.95); ctx.lineTo(-w * 0.45, -h * 0.4); ctx.closePath(); ctx.fill();
      // 前の花びら
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.moveTo(-w * 0.95, -h * 0.55); ctx.quadraticCurveTo(-w * 1.05, h * 0.18, 0, h * 0.2); ctx.quadraticCurveTo(w * 1.05, h * 0.18, w * 0.95, -h * 0.55); ctx.quadraticCurveTo(w * 0.4, -h * 0.1, 0, -h * 0.7); ctx.quadraticCurveTo(-w * 0.4, -h * 0.1, -w * 0.95, -h * 0.55); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.8)'; ctx.lineWidth = size * 0.035; ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.beginPath(); ctx.ellipse(-w * 0.45, -h * 0.15, w * 0.1, h * 0.2, 0.2, 0, TAU); ctx.fill();
    });
  }
  function leaf(ctx, x, y, size, rot = 0, opt = {}) {
    tf(ctx, x, y, rot, opt.sx ?? 1, 1, () => {
      ctx.beginPath(); ctx.moveTo(0, 0);
      ctx.bezierCurveTo(size * 0.45, -size * 0.2, size * 0.4, -size * 0.8, 0, -size);
      ctx.bezierCurveTo(-size * 0.4, -size * 0.8, -size * 0.45, -size * 0.2, 0, 0);
      const g = ctx.createLinearGradient(0, 0, 0, -size); g.addColorStop(0, opt.dark || C.grnD); g.addColorStop(1, opt.col || C.grn);
      ctx.fillStyle = g; ctx.fill();
      ctx.lineWidth = size * 0.05; ctx.strokeStyle = 'rgba(255,255,255,0.85)'; ctx.stroke();
      ctx.strokeStyle = 'rgba(255,255,255,0.55)'; ctx.lineWidth = size * 0.04;
      ctx.beginPath(); ctx.moveTo(0, -size * 0.1); ctx.lineTo(0, -size * 0.8); ctx.stroke();
    });
  }
  function petal(ctx, x, y, size, rot, col, sx = 1) {
    tf(ctx, x, y, rot, sx, 1, () => {
      ctx.beginPath(); ctx.moveTo(0, size * 0.5);
      ctx.bezierCurveTo(size * 0.6, size * 0.1, size * 0.45, -size * 0.5, size * 0.08, -size * 0.45);
      ctx.lineTo(0, -size * 0.32); ctx.lineTo(-size * 0.08, -size * 0.45);
      ctx.bezierCurveTo(-size * 0.45, -size * 0.5, -size * 0.6, size * 0.1, 0, size * 0.5);
      const g = ctx.createLinearGradient(0, size * 0.5, 0, -size * 0.5); g.addColorStop(0, C.white); g.addColorStop(1, col);
      ctx.fillStyle = g; ctx.fill();
    });
  }
  function sparkle(ctx, x, y, size, col = C.white, rot = 0) {
    tf(ctx, x, y, rot, 1, 1, () => {
      ctx.beginPath();
      for (let i = 0; i < 4; i++) {
        const a = (i / 4) * TAU;
        ctx.quadraticCurveTo(0, 0, Math.cos(a) * size, Math.sin(a) * size);
        ctx.quadraticCurveTo(0, 0, Math.cos(a + TAU / 8) * size * 0.18, Math.sin(a + TAU / 8) * size * 0.18);
      }
      ctx.closePath(); ctx.fillStyle = col; ctx.fill();
    });
  }
  // リボン (蝶結び)
  function bow(ctx, x, y, size, rot = 0, col = C.pink, dark = C.pinkD) {
    tf(ctx, x, y, rot, 1, 1, () => {
      ctx.lineJoin = 'round';
      for (const s of [-1, 1]) {
        // たれ
        ctx.fillStyle = dark;
        ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(s * size * 0.22, size * 0.62); ctx.lineTo(s * size * 0.32, size * 0.5); ctx.lineTo(s * size * 0.42, size * 0.66); ctx.lineTo(s * size * 0.3, 0); ctx.closePath(); ctx.fill();
        // 輪
        ctx.beginPath(); ctx.moveTo(0, 0);
        ctx.bezierCurveTo(s * size * 0.25, -size * 0.45, s * size * 0.7, -size * 0.35, s * size * 0.62, 0);
        ctx.bezierCurveTo(s * size * 0.68, size * 0.32, s * size * 0.25, size * 0.25, 0, 0);
        const g = ctx.createLinearGradient(0, -size * 0.4, 0, size * 0.3); g.addColorStop(0, lighten(col, 0.3)); g.addColorStop(1, col);
        ctx.fillStyle = g; ctx.fill(); ctx.lineWidth = size * 0.04; ctx.strokeStyle = C.white; ctx.stroke();
        ctx.strokeStyle = dark; ctx.lineWidth = size * 0.03;
        ctx.beginPath(); ctx.moveTo(s * size * 0.12, -size * 0.04); ctx.quadraticCurveTo(s * size * 0.3, -size * 0.18, s * size * 0.45, -size * 0.12); ctx.stroke();
      }
      ctx.fillStyle = dark; ctx.beginPath(); ctx.ellipse(0, 0, size * 0.12, size * 0.14, 0, 0, TAU); ctx.fill();
      ctx.lineWidth = size * 0.035; ctx.strokeStyle = C.white; ctx.stroke();
    });
  }
  function pearl(ctx, x, y, r) {
    const g = ctx.createRadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r);
    g.addColorStop(0, '#ffffff'); g.addColorStop(0.7, '#fff3f6'); g.addColorStop(1, '#f2c9d8');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
  }

  // --- フリル (帯) --------------------------------------------------------
  // 原点から +x 方向へ長さ len、+y 方向へ depth 垂れるフリル。phase で揺れる
  function frill(ctx, len, depth, opt = {}) {
    const pleat = opt.pleat ?? 46, col = opt.col || C.pink, dark = opt.dark || C.pinkD, light = opt.light || C.pinkLL;
    const n = Math.ceil(len / pleat), ph = opt.phase ?? 0, amp = opt.amp ?? 0.12;
    const bottom = (i) => depth * (1 + amp * Math.sin(ph + i * 0.9));
    ctx.save();
    ctx.beginPath(); ctx.moveTo(-2, 0);
    for (let i = 0; i < n; i++) {
      const x0 = i * pleat, x1 = x0 + pleat, b = bottom(i);
      ctx.lineTo(x0, b * 0.86);
      ctx.bezierCurveTo(x0 + pleat * 0.1, b * 1.08, x1 - pleat * 0.1, b * 1.08, x1, b * 0.86);
    }
    ctx.lineTo(n * pleat + 2, 0); ctx.closePath();
    ctx.fillStyle = col; ctx.fill();
    ctx.clip();
    // ひだの陰影
    for (let i = 0; i < n; i++) {
      const x0 = i * pleat;
      const g = ctx.createLinearGradient(x0, 0, x0 + pleat, 0);
      g.addColorStop(0, hexA(dark, 0.55)); g.addColorStop(0.35, hexA(light, 0.0)); g.addColorStop(0.5, hexA(light, 0.85)); g.addColorStop(0.68, hexA(light, 0.0)); g.addColorStop(1, hexA(dark, 0.55));
      ctx.fillStyle = g; ctx.fillRect(x0, 0, pleat, depth * 1.3);
    }
    // 上側のギャザーの影
    const g2 = ctx.createLinearGradient(0, 0, 0, depth * 0.35);
    g2.addColorStop(0, hexA(dark, 0.45)); g2.addColorStop(1, hexA(dark, 0));
    ctx.fillStyle = g2; ctx.fillRect(0, 0, len + pleat, depth * 0.35);
    ctx.restore();
    // すそのライン
    if (opt.hem !== false) {
      ctx.strokeStyle = opt.hem || C.white; ctx.lineWidth = Math.max(2, depth * 0.06);
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x0 = i * pleat, x1 = x0 + pleat, b = bottom(i) - depth * 0.08;
        ctx.moveTo(x0, b * 0.86); ctx.bezierCurveTo(x0 + pleat * 0.1, b * 1.08, x1 - pleat * 0.1, b * 1.08, x1, b * 0.86);
      }
      ctx.stroke();
    }
  }

  // --- レース (帯) --------------------------------------------------------
  // 透かし穴を開けたレースを別キャンバスに作って返す (上辺が原点、下へ垂れる)
  function makeLace(len, h, opt = {}) {
    const cv = document.createElement('canvas');
    const sc = opt.scallop ?? h * 0.9;
    const n = Math.ceil(len / sc) + 1;
    cv.width = Math.ceil(n * sc); cv.height = Math.ceil(h * 1.15);
    const c = cv.getContext('2d');
    const band = h * 0.32, col = opt.col || '#ffffff';
    c.fillStyle = col;
    c.fillRect(0, 0, cv.width, band);
    for (let i = 0; i < n; i++) {
      const cx = i * sc + sc / 2;
      c.beginPath(); c.arc(cx, band, sc / 2, 0, Math.PI); c.fill();
      // ピコット (縁の小さい玉)
      for (let k = 1; k < 8; k++) {
        const a = (k / 8) * Math.PI;
        c.beginPath(); c.arc(cx + Math.cos(a) * sc * 0.52, band + Math.sin(a) * sc * 0.52, sc * 0.055, 0, TAU); c.fill();
      }
    }
    c.globalCompositeOperation = 'destination-out';
    // 帯の穴 (小さい丸の列)
    for (let x = sc * 0.25; x < cv.width; x += sc * 0.5) { c.beginPath(); c.arc(x, band * 0.42, band * 0.14, 0, TAU); c.fill(); }
    for (let i = 0; i < n; i++) {
      const cx = i * sc + sc / 2, cy = band + sc * 0.17;
      c.beginPath(); c.arc(cx, cy, sc * 0.075, 0, TAU); c.fill(); // 花の芯
      for (let k = 0; k < 6; k++) { // 花びらの穴
        const a = (k / 6) * Math.PI - Math.PI * 0.0;
        if (Math.sin(a) < -0.1) continue;
        c.beginPath(); c.ellipse(cx + Math.cos(a) * sc * 0.2, cy + Math.sin(a) * sc * 0.2, sc * 0.07, sc * 0.04, a, 0, TAU); c.fill();
      }
      c.beginPath(); c.arc(i * sc, band + sc * 0.02, sc * 0.05, 0, TAU); c.fill(); // スカラップの間
    }
    c.globalCompositeOperation = 'source-over';
    // ふち取りの淡い影
    if (opt.shade !== false) {
      c.globalCompositeOperation = 'source-atop';
      const g = c.createLinearGradient(0, 0, 0, cv.height);
      g.addColorStop(0, 'rgba(255,190,215,0.0)'); g.addColorStop(1, 'rgba(255,170,205,0.35)');
      c.fillStyle = g; c.fillRect(0, 0, cv.width, cv.height);
      c.globalCompositeOperation = 'source-over';
    }
    return cv;
  }

  // ギンガムチェック
  function gingham(ctx, x, y, w, h, cell, base, line, offx = 0, offy = 0) {
    ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
    ctx.fillStyle = base; ctx.fillRect(x, y, w, h);
    ctx.fillStyle = line;
    const sx = x - (((offx % (cell * 2)) + cell * 2) % (cell * 2)) - cell * 2;
    const sy = y - (((offy % (cell * 2)) + cell * 2) % (cell * 2)) - cell * 2;
    for (let xx = sx; xx < x + w + cell * 2; xx += cell * 2) ctx.fillRect(xx, y, cell, h);
    for (let yy = sy; yy < y + h + cell * 2; yy += cell * 2) ctx.fillRect(x, yy, w, cell);
    ctx.restore();
  }

  function lighten(hex, k) {
    const [r, g, b] = hexRGB(hex);
    return `rgb(${Math.round(r + (255 - r) * k)},${Math.round(g + (255 - g) * k)},${Math.round(b + (255 - b) * k)})`;
  }
  function hexRGB(hex) {
    if (hex.startsWith('rgb')) return hex.match(/\d+/g).slice(0, 3).map(Number);
    const h = hex.replace('#', '');
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  function hexA(hex, a) { const [r, g, b] = hexRGB(hex); return `rgba(${r},${g},${b},${a})`; }

  // ===== ゆめかわ・ロリータ・乙女パーツ =====
  C.lav = '#e9dcff'; C.mint = '#cdf6e6'; C.peach = '#ffe0cc'; C.gold = '#ffd36b'; C.goldD = '#e9a93a';
  // パステルのオーロラ (ホロ) グラデ
  function holo(ctx, x0, y0, x1, y1, shift = 0) {
    const g = ctx.createLinearGradient(x0, y0, x1, y1);
    const cols = ['#ffd0e6', '#fff1b8', '#d9f7c6', '#ecdfff', '#ffd0e6'];
    for (let i = 0; i < 5; i++) g.addColorStop(((i / 4 + shift) % 1 + 1) % 1, cols[i]);
    // addColorStop は順番がずれても大丈夫なように 0 と 1 も入れる
    g.addColorStop(0, cols[0]); g.addColorStop(1, cols[0]);
    return g;
  }
  // バラ (上から見た形)
  function rose(ctx, x, y, size, rot = 0, opt = {}) {
    const col = opt.col || C.pink, dark = opt.dark || C.pinkD, light = opt.light || C.pinkLL;
    tf(ctx, x, y, rot, 1, 1, () => {
      // 外の花びら
      for (let i = 0; i < 6; i++) {
        tf(ctx, 0, 0, (i / 6) * TAU, 1, 1, () => {
          ctx.beginPath(); ctx.ellipse(0, -size * 0.3, size * 0.26, size * 0.22, 0, 0, TAU);
          const g = ctx.createRadialGradient(0, -size * 0.1, 0, 0, -size * 0.3, size * 0.3);
          g.addColorStop(0, dark); g.addColorStop(1, light);
          ctx.fillStyle = g; ctx.fill();
          ctx.lineWidth = size * 0.025; ctx.strokeStyle = '#fff'; ctx.stroke();
        });
      }
      ctx.beginPath(); ctx.arc(0, 0, size * 0.3, 0, TAU); ctx.fillStyle = col; ctx.fill();
      // うずまき
      ctx.lineCap = 'round';
      for (let k = 0; k < 3; k++) {
        ctx.beginPath();
        for (let a = 0; a < TAU * 1.6; a += 0.15) {
          const r = size * (0.04 + a * 0.03) + k * 0;
          const px = Math.cos(a + k * 2.1) * r, py = Math.sin(a + k * 2.1) * r;
          a ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
        }
        ctx.strokeStyle = k === 0 ? dark : 'rgba(255,255,255,0.75)'; ctx.lineWidth = size * (k === 0 ? 0.05 : 0.025); ctx.stroke();
      }
      ctx.fillStyle = 'rgba(255,255,255,0.8)'; ctx.beginPath(); ctx.ellipse(-size * 0.2, -size * 0.36, size * 0.07, size * 0.035, -0.6, 0, TAU); ctx.fill();
    });
  }
  // 宝石ハート (カット面とキラッ)
  function jewelHeart(ctx, x, y, size, rot = 0, col = C.pink, opt = {}) {
    tf(ctx, x, y, rot, opt.sx ?? 1, 1, () => {
      heartPath(ctx, size);
      ctx.lineWidth = size * 0.1; ctx.strokeStyle = opt.rim || C.gold; ctx.lineJoin = 'round'; ctx.stroke();
      ctx.lineWidth = size * 0.035; ctx.strokeStyle = '#fff'; ctx.stroke();
      const g = ctx.createLinearGradient(-size * 0.5, -size * 0.5, size * 0.5, size * 0.5);
      g.addColorStop(0, lighten(col, 0.6)); g.addColorStop(0.45, col); g.addColorStop(1, lighten(col, 0.25));
      ctx.fillStyle = g; ctx.fill();
      ctx.save(); heartPath(ctx, size); ctx.clip();
      ctx.strokeStyle = 'rgba(255,255,255,0.55)'; ctx.lineWidth = size * 0.02;
      ctx.beginPath(); ctx.moveTo(0, -size * 0.12); ctx.lineTo(-size * 0.3, -size * 0.38); ctx.moveTo(0, -size * 0.12); ctx.lineTo(size * 0.3, -size * 0.38);
      ctx.moveTo(0, -size * 0.12); ctx.lineTo(0, size * 0.48); ctx.moveTo(-size * 0.45, -size * 0.05); ctx.lineTo(0, -size * 0.12); ctx.lineTo(size * 0.45, -size * 0.05); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.3)'; ctx.beginPath(); ctx.moveTo(0, -size * 0.12); ctx.lineTo(-size * 0.3, -size * 0.38); ctx.lineTo(-size * 0.48, -size * 0.1); ctx.closePath(); ctx.fill();
      ctx.restore();
      sparkle(ctx, -size * 0.2, -size * 0.2, size * 0.16, '#fff');
    });
  }
  // ティアラ
  function crown(ctx, x, y, size, rot = 0) {
    tf(ctx, x, y, rot, 1, 1, () => {
      const w = size, h = size * 0.62;
      ctx.beginPath(); ctx.moveTo(-w / 2, h * 0.3);
      ctx.lineTo(-w / 2, -h * 0.15); ctx.lineTo(-w * 0.3, h * 0.05); ctx.lineTo(-w * 0.15, -h * 0.45); ctx.lineTo(0, -h * 0.05);
      ctx.lineTo(w * 0.15, -h * 0.45); ctx.lineTo(w * 0.3, h * 0.05); ctx.lineTo(w / 2, -h * 0.15); ctx.lineTo(w / 2, h * 0.3);
      ctx.quadraticCurveTo(0, h * 0.15, -w / 2, h * 0.3); ctx.closePath();
      const g = ctx.createLinearGradient(0, -h * 0.5, 0, h * 0.3); g.addColorStop(0, '#fff6c8'); g.addColorStop(1, C.gold);
      ctx.fillStyle = g; ctx.fill(); ctx.lineJoin = 'round'; ctx.lineWidth = size * 0.04; ctx.strokeStyle = '#fff'; ctx.stroke();
      for (const [px, py, r] of [[-w / 2, -h * 0.2, 0.06], [-w * 0.15, -h * 0.5, 0.07], [w * 0.15, -h * 0.5, 0.07], [w / 2, -h * 0.2, 0.06]]) pearl(ctx, px, py, size * r);
      jewelHeart(ctx, 0, h * 0.0, size * 0.32, 0, C.pink, { rim: '#fff' });
      for (const px of [-w * 0.32, w * 0.32]) { ctx.fillStyle = '#c9f07e'; ctx.beginPath(); ctx.arc(px, h * 0.16, size * 0.045, 0, TAU); ctx.fill(); }
    });
  }
  // 星 (まるい5つ星)
  function star(ctx, x, y, r, col = C.yel, rot = 0) {
    tf(ctx, x, y, rot, 1, 1, () => {
      ctx.beginPath();
      for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i / 10) * TAU, rr = i % 2 ? r * 0.48 : r; ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr); }
      ctx.closePath(); ctx.lineJoin = 'round'; ctx.lineWidth = r * 0.22; ctx.strokeStyle = '#fff'; ctx.stroke();
      ctx.fillStyle = col; ctx.fill();
      ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.beginPath(); ctx.arc(-r * 0.2, -r * 0.2, r * 0.13, 0, TAU); ctx.fill();
    });
  }
  // シャボン玉
  function bubble(ctx, x, y, r, shift = 0) {
    const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
    g.addColorStop(0, 'rgba(255,255,255,0.15)'); g.addColorStop(0.75, 'rgba(255,230,245,0.25)'); g.addColorStop(1, 'rgba(255,255,255,0.75)');
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
    ctx.lineWidth = Math.max(2, r * 0.07); ctx.strokeStyle = holo(ctx, x - r, y - r, x + r, y + r, shift); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.9)'; ctx.beginPath(); ctx.ellipse(x - r * 0.4, y - r * 0.4, r * 0.18, r * 0.09, -0.8, 0, TAU); ctx.fill();
    ctx.beginPath(); ctx.arc(x + r * 0.45, y + r * 0.35, r * 0.06, 0, TAU); ctx.fill();
  }
  // パールの飾り鎖 (2点のあいだを垂れ下がる)
  function pearlSwag(ctx, x0, y0, x1, y1, sag, r) {
    const L = Math.hypot(x1 - x0, y1 - y0), n = Math.max(3, Math.floor(L / (r * 2.3)));
    for (let i = 0; i <= n; i++) {
      const u = i / n, x = x0 + (x1 - x0) * u, y = y0 + (y1 - y0) * u + sag * 4 * u * (1 - u);
      pearl(ctx, x, y, r * (i % 4 === 2 ? 1.35 : 1));
    }
  }
  // レースのドイリー (丸い透かしレース) - キャッシュ
  const doilyCache = {};
  function doily(ctx, x, y, r, rot = 0, col = '#ffffff') {
    const key = Math.round(r) + col;
    if (!doilyCache[key]) {
      const cv = document.createElement('canvas'), R = Math.ceil(r * 1.2); cv.width = cv.height = R * 2;
      const c = cv.getContext('2d'); c.translate(R, R); c.fillStyle = col;
      const n = 18;
      c.beginPath(); c.arc(0, 0, r * 0.86, 0, TAU); c.fill();
      for (let i = 0; i < n; i++) { const a = (i / n) * TAU; c.beginPath(); c.arc(Math.cos(a) * r * 0.88, Math.sin(a) * r * 0.88, r * 0.17, 0, TAU); c.fill();
        c.beginPath(); c.arc(Math.cos(a) * r * 1.06, Math.sin(a) * r * 1.06, r * 0.04, 0, TAU); c.fill(); }
      c.globalCompositeOperation = 'destination-out';
      for (let i = 0; i < n; i++) { const a = (i / n) * TAU; c.beginPath(); c.arc(Math.cos(a) * r * 0.88, Math.sin(a) * r * 0.88, r * 0.07, 0, TAU); c.fill();
        const b = a + TAU / n / 2; c.beginPath(); c.ellipse(Math.cos(b) * r * 0.66, Math.sin(b) * r * 0.66, r * 0.09, r * 0.04, b, 0, TAU); c.fill(); }
      for (let i = 0; i < 12; i++) { const a = (i / 12) * TAU; c.beginPath(); c.arc(Math.cos(a) * r * 0.5, Math.sin(a) * r * 0.5, r * 0.045, 0, TAU); c.fill(); }
      c.globalCompositeOperation = 'source-over';
      doilyCache[key] = cv;
    }
    const cv = doilyCache[key];
    tf(ctx, x, y, rot, 1, 1, () => ctx.drawImage(cv, -cv.width / 2, -cv.height / 2));
  }
  // チュール (透けるフリル + ドット)
  function tulle(ctx, len, depth, opt = {}) {
    ctx.save(); ctx.globalAlpha *= opt.alpha ?? 0.6;
    frill(ctx, len, depth, { col: '#ffffff', dark: opt.dark || '#ffc6dc', light: '#ffffff', pleat: opt.pleat ?? 30, phase: opt.phase ?? 0, amp: 0.1, hem: false });
    ctx.restore();
    ctx.save(); ctx.fillStyle = 'rgba(255,255,255,0.85)';
    for (let x = 12; x < len; x += 26) for (let y = 12; y < depth * 0.8; y += 22) { ctx.beginPath(); ctx.arc(x + ((y / 22) % 2 ? 13 : 0), y, 2.4, 0, TAU); ctx.fill(); }
    ctx.restore();
  }
  // キルティング (ひし形のステッチ + 交点にパール)
  function quilt(ctx, x, y, w, h, cell, base, shade, offx = 0, offy = 0, pearls = true) {
    ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
    ctx.fillStyle = base; ctx.fillRect(x, y, w, h);
    const ox = ((offx % cell) + cell) % cell, oy = ((offy % cell) + cell) % cell;
    // ふっくら陰影
    for (let gy = -1; gy < h / cell * 2 + 2; gy++) for (let gx = -1; gx < w / cell + 2; gx++) {
      const cx = x + gx * cell + (gy % 2 ? cell / 2 : 0) + ox - cell, cy = y + gy * cell / 2 + oy - cell;
      const g = ctx.createRadialGradient(cx - cell * 0.1, cy - cell * 0.12, 0, cx, cy, cell * 0.55);
      g.addColorStop(0, 'rgba(255,255,255,0.55)'); g.addColorStop(1, shade);
      ctx.fillStyle = g; ctx.beginPath(); ctx.moveTo(cx, cy - cell / 2); ctx.lineTo(cx + cell / 2, cy); ctx.lineTo(cx, cy + cell / 2); ctx.lineTo(cx - cell / 2, cy); ctx.closePath(); ctx.fill();
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.95)'; ctx.lineWidth = 2.5; ctx.setLineDash([8, 6]);
    for (let k = -h - cell * 2; k < w + h + cell * 2; k += cell) {
      ctx.beginPath(); ctx.moveTo(x + k + ox, y + oy - cell); ctx.lineTo(x + k + ox + h + cell * 2, y + oy + h + cell); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(x + k + ox, y + oy - cell); ctx.lineTo(x + k + ox - h - cell * 2, y + oy + h + cell); ctx.stroke();
    }
    ctx.setLineDash([]);
    if (pearls) for (let gy = -1; gy < h / cell * 2 + 2; gy++) for (let gx = -1; gx < w / cell + 2; gx++) {
      const px = x + gx * cell + (gy % 2 ? 0 : cell / 2) + ox - cell, py = y + gy * cell / 2 + oy - cell;
      pearl(ctx, px, py, cell * 0.07);
    }
    ctx.restore();
  }
  // 細かいラメ
  function glitter(ctx, t, n, x, y, w, h, seed = 1, size = 10) {
    const r = rng(seed);
    for (let i = 0; i < n; i++) {
      const px = x + r() * w, py = y + r() * h, ph = r() * TAU, sp = 1 + Math.floor(r() * 3), s = size * (0.5 + r());
      const a = Math.pow(Math.max(0, Math.sin(TAU * t * sp + ph)), 3);
      if (a < 0.02) continue;
      sparkle(ctx, px, py, s * a, r() < 0.7 ? '#ffffff' : ['#fff3a8', '#ffd0e6', '#d9f7c6'][i % 3]);
    }
  }

  window.M = { holo, rose, jewelHeart, crown, star, bubble, pearlSwag, doily, tulle, quilt, glitter, TAU, C, wave, clamp, ease, easeOut, easeOutBack, rng, tf, heartPath, heart, leafPath, clover, daisy, blossom, tulip, leaf, petal, sparkle, bow, pearl, frill, makeLace, gingham, lighten, hexA };
})();
