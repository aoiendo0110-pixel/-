// 二次元/アニメ — manga title card: navy outlines, screentone, lightning slash, impact burst, slam-in with shake
(() => {
  const C = {
    navy: '#25205e', cyan: '#5fd6ff', blue: '#3a76ff', blueL: '#c9f1ff',
    pink: '#ff7fcf', mag: '#ff3d8f', pinkL: '#ffe0f2', yel: '#ffe14d', yelD: '#ffb627', white: '#ffffff',
  };
  const rnd = n => { const x = Math.sin(n * 91.7 + 17.3) * 43758.5453; return x - Math.floor(x); };

  function tone(top, bot, dot) {
    return (g, w, h) => {
      g.fillStyle = grad(g, h, top, bot); g.fillRect(-60, -60, w + 120, h + 120);
      // halftone dots growing toward the bottom
      g.fillStyle = dot;
      for (let y = 0; y < h + 12; y += 11) for (let x = (y / 11 % 2) * 5.5; x < w + 12; x += 11) {
        const r = clamp((y / h - 0.35) * 1.6) * 3.6;
        if (r > 0.4) { g.beginPath(); g.arc(x, y, r, 0, TAU); g.fill(); }
      }
      // manga highlight slash
      g.fillStyle = 'rgba(255,255,255,0.9)';
      g.save(); g.rotate(-0.5);
      g.fillRect(-w, h * 0.22, w * 3, 5); g.fillRect(-w, h * 0.22 + 10, w * 3, 2.5);
      g.restore();
      shine(g, w, h, 0.9);
    };
  }

  function burstPath(g, rx, ry, seed, n = 30) {
    g.beginPath();
    for (let i = 0; i < n * 2; i++) {
      const a = i / (n * 2) * TAU;
      const k = i % 2 ? 0.87 : 1 + rnd(seed + i) * 0.08;
      const x = Math.cos(a) * rx * k, y = Math.sin(a) * ry * k;
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    }
    g.closePath();
  }
  function boltPath(g) {
    g.beginPath();
    g.moveTo(30, -95); g.lineTo(-28, 8); g.lineTo(6, 8); g.lineTo(-30, 95); g.lineTo(34, -18); g.lineTo(2, -18); g.lineTo(38, -95);
    g.closePath();
  }
  function filmStrip(g, n) {
    const fw = 46, w = fw * n, h = 52;
    rimFill(g, () => { g.beginPath(); g.roundRect(-w / 2, -h / 2, w, h, 6); }, [[C.navy, 12], [C.white, 6]], C.navy);
    for (let i = 0; i < n; i++) {
      const x = -w / 2 + i * fw;
      g.fillStyle = i % 2 ? C.pinkL : C.blueL; g.fillRect(x + 6, -h / 2 + 12, fw - 12, h - 24);
      g.fillStyle = C.white;
      for (let k = 0; k < 3; k++) { g.fillRect(x + 5 + k * 14, -h / 2 + 3, 7, 5); g.fillRect(x + 5 + k * 14, h / 2 - 8, 7, 5); }
    }
  }

  let G, BOLT;
  const chars = ['二', '次', '元', '/', 'ア', 'ニ', 'メ'];
  const X = [290, 458, 626, 750, 874, 1042, 1210];
  SCENES.anime = {
    fonts: [['160px Mochiy', '二次元アニメ']],
    build() {
      const F = '160px Mochiy';
      const blue = { shadow: C.navy, outer: C.navy, outline: 16, depth: 12, edge: 8, dir: [0.7, 1], paint: tone(C.cyan, C.blue, 'rgba(37,32,94,0.35)') };
      const pink = { ...blue, paint: tone(C.pink, C.mag, 'rgba(37,32,94,0.3)') };
      G = chars.map((ch, i) => ch === '/' ? null : glyph(ch, F, i < 3 ? blue : pink));
      BOLT = shapeSprite(76, 192, g => { g.save(); g.translate(38, 96); boltPath(g); g.restore(); },
        { shadow: C.navy, outer: C.navy, outline: 14, depth: 10, edge: 8, dir: [0.7, 1],
          paint: (g, w, h) => { g.fillStyle = grad(g, h, '#fff7b0', C.yel, C.yelD); g.fillRect(-50, -50, w + 100, h + 100); } });
    },
    frame(t) {
      const ph = t / 2 * TAU;
      const step12 = Math.floor(t * 12);
      // landing times for the slam-in
      const land = chars.map((_, i) => 0.35 + i * 0.12);
      // camera shake after each landing
      let shake = 0;
      land.forEach(l => { const d = t - l - 0.12; if (d > 0 && d < 0.25) shake = Math.max(shake, (1 - d / 0.25) * 9); });
      ctx.save();
      ctx.translate((rnd(step12 * 3.1) - 0.5) * shake * 2, (rnd(step12 * 7.7) - 0.5) * shake * 2);

      // impact burst behind everything (stepped jitter like an anime card)
      {
        const s = pop(t, 0.05, 0.4, 1.8);
        if (s > 0) {
          const seed = (Math.floor(t * 10) % 20) * 13;
          ctx.save(); ctx.translate(750, 252); ctx.scale(s, s);
          rimFill(ctx, () => burstPath(ctx, 610, 200, seed), [[C.navy, 16], [C.white, 8]], C.yel);
          // inner burst layer
          burstPath(ctx, 530, 165, seed + 5, 34); ctx.fillStyle = '#fff2a8'; ctx.fill();
          ctx.restore();
        }
      }

      // speed lines radiating outward from the burst (opaque wedges, flicker by step)
      if (t > 0.3) {
        ctx.save(); ctx.translate(750, 252);
        for (let i = 0; i < 26; i++) {
          if (rnd(i + (Math.floor(t * 12) % 24) * 31) < 0.45) continue;
          const a = i / 26 * TAU + rnd(i) * 0.1;
          const r0 = 1.0, r1 = 1.12 + rnd(i * 3) * 0.08;
          const ex = 640, ey = 222, wd = 0.012;
          ctx.beginPath();
          ctx.moveTo(Math.cos(a - wd) * ex * r0, Math.sin(a - wd) * ey * r0);
          ctx.lineTo(Math.cos(a) * ex * r1, Math.sin(a) * ey * r1);
          ctx.lineTo(Math.cos(a + wd) * ex * r0, Math.sin(a + wd) * ey * r0);
          ctx.closePath(); ctx.fillStyle = C.navy; ctx.fill();
        }
        ctx.restore();
      }

      // letters slam in from huge scale
      chars.forEach((ch, i) => {
        const t0 = land[i];
        if (t < t0) return;
        const k = clamp((t - t0) / 0.14);
        let sc = lerp(2.6, 1, ease.outCubic(k));
        let sx = 1, sy = 1;
        const after = t - t0 - 0.14;
        if (after > 0 && after < 0.3) { const q = Math.sin(after / 0.3 * Math.PI) * (1 - after / 0.3); sx = 1 + q * 0.18; sy = 1 - q * 0.18; }
        // idle: jumping wave
        const jump = Math.max(0, Math.sin(ph * 1 - i * 0.6)) * -16;
        const rot = Math.sin(ph - i * 0.6 + 1) * 0.05 + [-0.06, 0.04, -0.03, 0.12, -0.05, 0.03, 0.06][i];
        const y = 250 + jump + (i % 2 ? 6 : -4);
        if (ch === '/') {
          const flash = (t > 1.2 && ((t - 1.2) % 1) < 0.1) ? 1.18 : 1;
          blit(BOLT, X[i], y, sc * flash, rot, sx, sy);
        } else blit(G[i], X[i], y, sc, rot, sx, sy);
      });

      ctx.restore();

      // floating extras (outside the shake)
      const deco = [
        ['film', 130, 95, 3, 1.3, -0.3],
        ['film', 1395, 420, 3, 1.4, 0.25],
        ['spark', 1350, 75, 26, 1.35, 0],
        ['spark', 250, 445, 22, 1.45, 0],
        ['spark', 1450, 245, 18, 1.55, 0],
        ['star', 70, 270, 22, 1.5, 0],
        ['star', 960, 465, 20, 1.6, 0],
        ['star', 590, 40, 18, 1.65, 0],
        ['heart', 1185, 40, 34, 1.7, 0],
      ];
      deco.forEach(([ty, x, y, r, d, rot0], i) => {
        const s = pop(t, d, 0.45);
        if (s <= 0) return;
        const by = Math.sin(ph + i * 1.3) * 7;
        ctx.save(); ctx.translate(x, y + by); ctx.rotate(rot0 + Math.sin(ph + i) * 0.12); ctx.scale(s, s);
        if (ty === 'film') filmStrip(ctx, r);
        else if (ty === 'spark') {
          const tw = 0.7 + 0.3 * Math.abs(Math.sin(ph * 2 + i));
          ctx.scale(tw, tw); sparkle(ctx, r, i % 2 ? C.yel : C.white, C.white, C.navy);
        } else if (ty === 'star') rimFill(ctx, () => starPath(ctx, r, 5, 0.48), [[C.navy, 10], [C.white, 6]], i % 2 ? C.pink : C.cyan);
        else rimFill(ctx, () => heartPath(ctx, 0, 0, r), [[C.navy, 10], [C.white, 6]], C.mag);
        ctx.restore();
      });
    },
  };
})();
