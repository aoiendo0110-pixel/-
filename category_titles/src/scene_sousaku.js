// 一次創作 — atelier / sketchbook: marker font, crayon hatching, pencil-drawn underline, paint splats
(() => {
  const C = {
    ink: '#4b2f8f', lav: '#b892ff', lavL: '#e3d4ff', sky: '#7cc8ff', skyL: '#d6eeff',
    pink: '#ff8cc6', pinkL: '#ffd6ea', yel: '#ffd84d', yelL: '#fff3b8', white: '#ffffff',
  };
  const outBounce = x => {
    const n = 7.5625, d = 2.75;
    if (x < 1 / d) return n * x * x;
    if (x < 2 / d) return n * (x -= 1.5 / d) * x + 0.75;
    if (x < 2.5 / d) return n * (x -= 2.25 / d) * x + 0.9375;
    return n * (x -= 2.625 / d) * x + 0.984375;
  };
  // deterministic noise for the hand-drawn "boil"
  const rnd = n => { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

  function crayon(base, light) {
    return (g, w, h) => {
      g.fillStyle = grad(g, h, light, base, base); g.fillRect(-60, -60, w + 120, h + 120);
      // diagonal crayon hatching
      g.save(); g.rotate(-0.7);
      g.strokeStyle = 'rgba(255,255,255,0.45)'; g.lineWidth = 3; g.lineCap = 'round';
      for (let i = -h * 2; i < w * 2; i += 13) {
        g.beginPath(); g.moveTo(i, -h * 2); g.lineTo(i + 6 * Math.sin(i), h * 3); g.stroke();
      }
      g.restore();
      // speckles
      g.fillStyle = 'rgba(255,255,255,0.8)';
      for (let i = 0; i < 26; i++) { g.beginPath(); g.arc(rnd(i) * w, rnd(i + 50) * h, 1.6 + rnd(i + 9) * 2, 0, 7); g.fill(); }
      shine(g, w, h, 0.85);
    };
  }

  // paint splat: blob + droplets
  function splatPath(g, r, seed) {
    g.beginPath();
    const N = 14;
    for (let i = 0; i <= N; i++) {
      const a = i / N * TAU, rr = r * (0.78 + 0.32 * rnd(seed + i));
      const x = Math.cos(a) * rr, y = Math.sin(a) * rr;
      i ? g.quadraticCurveTo(Math.cos(a - TAU / N / 2) * r * 1.05, Math.sin(a - TAU / N / 2) * r * 1.05, x, y) : g.moveTo(x, y);
    }
    g.closePath();
    for (let k = 0; k < 3; k++) {
      const a = rnd(seed + 40 + k) * TAU, d = r * (1.35 + rnd(seed + 60 + k) * 0.35), rr = r * (0.14 + rnd(seed + 80 + k) * 0.12);
      g.moveTo(Math.cos(a) * d + rr, Math.sin(a) * d); g.arc(Math.cos(a) * d, Math.sin(a) * d, rr, 0, TAU);
    }
  }
  function drawSplat(g, r, seed, col, light) {
    rimFill(g, () => splatPath(g, r, seed), [[C.ink, 12], [C.white, 7]], col);
    g.fillStyle = light; g.beginPath(); g.ellipse(-r * 0.3, -r * 0.32, r * 0.22, r * 0.12, -0.6, 0, TAU); g.fill();
  }
  function star5(g, r, col) { rimFill(g, () => starPath(g, r, 5, 0.48), [[C.ink, 10], [C.white, 6]], col); }

  // pencil, tip at origin pointing down-left
  function drawPencil(g, s) {
    g.save(); g.scale(s, s);
    const body = () => { g.beginPath(); g.moveTo(0, 0); g.lineTo(22, -12); g.lineTo(150, -12); g.lineTo(150, 12); g.lineTo(22, 12); g.closePath(); };
    const all = () => { g.beginPath(); g.moveTo(0, 0); g.lineTo(22, -12); g.lineTo(178, -12); g.arcTo(186, -12, 186, 0, 8); g.arcTo(186, 12, 178, 12, 8); g.lineTo(22, 12); g.closePath(); };
    g.lineJoin = 'round';
    all(); g.strokeStyle = C.ink; g.lineWidth = 12; g.stroke();
    all(); g.strokeStyle = C.white; g.lineWidth = 6; g.stroke();
    // eraser + ferrule
    all(); g.fillStyle = C.pink; g.fill();
    g.fillStyle = '#c9b8e8'; g.fillRect(150, -12, 16, 24);
    g.fillStyle = C.white; g.fillRect(155, -12, 3, 24);
    // body stripes
    body(); g.fillStyle = C.yel; g.fill();
    g.fillStyle = '#ffbf3d'; g.fillRect(22, 4, 128, 8);
    g.fillStyle = C.yelL; g.fillRect(22, -8, 128, 5);
    // wood + lead
    g.beginPath(); g.moveTo(0, 0); g.lineTo(22, -12); g.lineTo(22, 12); g.closePath(); g.fillStyle = '#f6d3a8'; g.fill();
    g.beginPath(); g.moveTo(0, 0); g.lineTo(8, -4.4); g.lineTo(8, 4.4); g.closePath(); g.fillStyle = C.ink; g.fill();
    g.restore();
  }

  // underline path (wavy marker stroke)
  const UX0 = 290, UX1 = 1215, UY = 418;
  const uy = x => UY + Math.sin((x - UX0) / 62) * 9;

  let G;
  SCENES.sousaku = {
    fonts: [['220px Yusei', '一次創作']],
    build() {
      const F = '220px Yusei';
      const o = { shadow: C.ink, outline: 18, depth: 10, dir: [0, 1], outer: C.ink, edge: 6 };
      G = [
        glyph('一', F, { ...o, paint: crayon(C.lav, C.lavL) }),
        glyph('次', F, { ...o, paint: crayon(C.sky, C.skyL) }),
        glyph('創', F, { ...o, paint: crayon(C.pink, C.pinkL) }),
        glyph('作', F, { ...o, paint: crayon(C.yel, C.yelL) }),
      ];
    },
    frame(t) {
      const ph = t / 2 * TAU;
      const boil = Math.floor(t * 8) % 16; // stepped hand-drawn jitter

      // marker underline drawn by the pencil
      const dk = clamp((t - 0.15) / 1.3);
      const de = ease.outCubic(dk);
      const xEnd = lerp(UX0, UX1, de);
      if (dk > 0) {
        const line = (lw, col) => {
          ctx.beginPath();
          for (let x = UX0; x <= xEnd; x += 6) x === UX0 ? ctx.moveTo(x, uy(x)) : ctx.lineTo(x, uy(x));
          ctx.lineTo(xEnd, uy(xEnd));
          ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.stroke();
        };
        line(34, C.ink); line(26, C.white);
        const gr = ctx.createLinearGradient(UX0, 0, UX1, 0);
        gr.addColorStop(0, C.lav); gr.addColorStop(0.35, C.sky); gr.addColorStop(0.7, C.pink); gr.addColorStop(1, C.yel);
        line(16, gr);
      }

      // splats & stars behind letters
      const deco = [
        ['splat', 205, 205, 34, 3, C.pink, C.pinkL, 1.4],
        ['splat', 1305, 140, 30, 11, C.sky, C.skyL, 1.5],
        ['splat', 1440, 440, 22, 21, C.yel, C.yelL, 1.6],
        ['splat', 690, 70, 20, 31, C.lav, C.lavL, 1.55],
        ['star', 300, 75, 22, 0, C.yel, 0, 1.45],
        ['star', 1030, 60, 18, 0, C.pink, 0, 1.6],
        ['star', 150, 330, 16, 0, C.sky, 0, 1.7],
        ['star', 1450, 215, 16, 0, C.lav, 0, 1.75],
        ['dot', 480, 60, 9, 0, C.sky, 0, 1.5],
        ['dot', 860, 455, 10, 0, C.pink, 0, 1.65],
        ['dot', 1240, 470, 8, 0, C.lav, 0, 1.7],
      ];
      deco.forEach(([ty, x, y, r, seed, col, light, d], i) => {
        const s = pop(t, d, 0.45);
        if (s <= 0) return;
        const by = Math.sin(ph + i) * 6;
        const jr = (rnd(boil + i * 7) - 0.5) * 0.12;
        ctx.save(); ctx.translate(x, y + by); ctx.rotate(jr + Math.sin(ph + i * 2) * 0.15); ctx.scale(s, s);
        if (ty === 'splat') drawSplat(ctx, r, seed, col, light);
        else if (ty === 'star') star5(ctx, r, col);
        else rimFill(ctx, () => { ctx.beginPath(); ctx.arc(0, 0, r, 0, TAU); }, [[C.ink, 10], [C.white, 6]], col);
        ctx.restore();
      });

      // letters drop in and bounce, then wobble with a hand-drawn boil
      const pos = [[420, 238], [640, 232], [860, 236], [1085, 230]];
      G.forEach((sp, i) => {
        const d = 0.25 + i * 0.16;
        if (t < d) return;
        const k = clamp((t - d) / 0.7);
        const drop = (1 - outBounce(k)) * -420;
        const bob = Math.sin(ph - i * 0.9) * 8;
        const jx = (rnd(boil * 3 + i) - 0.5) * 3, jy = (rnd(boil * 5 + i) - 0.5) * 3;
        const jr = (rnd(boil * 7 + i) - 0.5) * 0.04;
        const tilt = [-0.07, 0.05, -0.04, 0.07][i];
        blit(sp, pos[i][0] + jx, pos[i][1] + drop + bob + jy, 1, tilt + jr + Math.sin(ph - i * 0.9 + 1) * 0.03);
      });

      // pencil: rides the underline, then hovers and doodles at the end
      {
        let px, py, rot;
        if (dk < 1) { px = xEnd; py = uy(xEnd); rot = -0.75; }
        else {
          const k = ease.outCubic(clamp((t - 1.45) / 0.5));
          px = lerp(UX1, 1290, k) + Math.cos(ph * 2) * 10;
          py = lerp(uy(UX1), 405, k) + Math.sin(ph * 2) * 12;
          rot = -0.75 + Math.sin(ph * 2) * 0.12;
        }
        const s = t < 0.15 ? pop(t, 0, 0.15) : 1;
        ctx.save(); ctx.translate(px, py); ctx.rotate(rot); ctx.scale(s, s);
        drawPencil(ctx, 0.95);
        ctx.restore();
      }
    },
  };
})();
