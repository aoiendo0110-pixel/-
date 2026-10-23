// 三次元 — deep extruded letters whose depth swings like a turning camera, plus rotating 3D primitives
(() => {
  const C = { navy: '#241a4a', white: '#ffffff' };
  const LETTERS = [
    { ch: '三', x: 455, y: 238, face: ['#ffffff', '#ffe0ee', '#ffb3d1', '#ff8fbd'], near: [255, 122, 170], far: [122, 31, 79] },
    { ch: '次', x: 750, y: 238, face: ['#ffffff', '#e2f2ff', '#a8d6ff', '#7ab8ff'], near: [96, 150, 255], far: [40, 40, 130] },
    { ch: '元', x: 1045, y: 238, face: ['#ffffff', '#fff3cc', '#ffd873', '#ffb84d'], near: [255, 150, 70], far: [140, 60, 30] },
  ];
  const FONT = '230px Dela';
  const mixc = (a, b, k) => `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], k))).join(',')})`;

  // ---------- tiny 3D mesh renderer (orthographic) ----------
  const CUBE = {
    v: [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]],
    f: [[0, 1, 2, 3], [5, 4, 7, 6], [4, 0, 3, 7], [1, 5, 6, 2], [4, 5, 1, 0], [3, 2, 6, 7]],
  };
  const OCTA = {
    v: [[0, -1.3, 0], [1, 0, 0], [0, 0, 1], [-1, 0, 0], [0, 0, -1], [0, 1.3, 0]],
    f: [[0, 2, 1], [0, 3, 2], [0, 4, 3], [0, 1, 4], [5, 1, 2], [5, 2, 3], [5, 3, 4], [5, 4, 1]],
  };
  const LIGHT = (() => { const l = [-0.45, -0.65, 0.62]; const n = Math.hypot(...l); return l.map(v => v / n); })();
  function rot([x, y, z], ax, ay) {
    let c = Math.cos(ax), s = Math.sin(ax);
    [y, z] = [y * c - z * s, y * s + z * c];
    c = Math.cos(ay); s = Math.sin(ay);
    [x, z] = [x * c + z * s, -x * s + z * c];
    return [x, y, z];
  }
  function mesh(g, M, r, ax, ay, base) {
    const P = M.v.map(p => rot(p, ax, ay));
    const faces = M.f.map(f => {
      const [a, b, c] = f.map(i => P[i]);
      const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], w = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      let n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
      const nl = Math.hypot(...n); n = n.map(v => v / nl);
      return { f, n, z: f.reduce((s, i) => s + P[i][2], 0) / f.length };
    }).filter(F => F.n[2] < 0); // facing the viewer (z toward -)
    const path = F => { g.beginPath(); F.f.forEach((i, k) => k ? g.lineTo(P[i][0] * r, P[i][1] * r) : g.moveTo(P[i][0] * r, P[i][1] * r)); g.closePath(); };
    g.lineJoin = 'round';
    faces.forEach(F => { path(F); g.strokeStyle = C.navy; g.lineWidth = 20; g.stroke(); });
    faces.forEach(F => { path(F); g.strokeStyle = C.white; g.lineWidth = 12; g.stroke(); });
    faces.forEach(F => {
      const d = clamp(-(F.n[0] * LIGHT[0] + F.n[1] * LIGHT[1] - F.n[2] * LIGHT[2]) * 0.5 + 0.5);
      path(F); g.fillStyle = mixc(base[0], base[1], 1 - d); g.fill();
    });
    faces.forEach(F => { path(F); g.strokeStyle = C.navy; g.lineWidth = 3; g.stroke(); });
  }
  function sphere(g, r, base) {
    rimFill(g, () => { g.beginPath(); g.arc(0, 0, r, 0, TAU); }, [[C.navy, 20], [C.white, 12]], C.white);
    const gr = g.createRadialGradient(-r * 0.35, -r * 0.4, r * 0.05, 0, 0, r);
    gr.addColorStop(0, '#ffffff'); gr.addColorStop(0.25, mixc(base[0], [255, 255, 255], 0.3)); gr.addColorStop(1, mixc(base[1], base[1], 0));
    g.beginPath(); g.arc(0, 0, r, 0, TAU); g.fillStyle = gr; g.fill();
    g.strokeStyle = C.navy; g.lineWidth = 3; g.stroke();
  }
  function planet(g, r, base, ringCol, tilt) {
    const ring = (a0, a1) => { g.beginPath(); g.ellipse(0, 0, r * 1.75, r * 0.5, tilt, a0, a1); };
    const strokeRing = (a0, a1) => {
      g.lineCap = 'round';
      ring(a0, a1); g.strokeStyle = C.navy; g.lineWidth = 20; g.stroke();
      ring(a0, a1); g.strokeStyle = C.white; g.lineWidth = 14; g.stroke();
      ring(a0, a1); g.strokeStyle = ringCol; g.lineWidth = 7; g.stroke();
    };
    strokeRing(Math.PI, TAU);
    sphere(g, r, base);
    strokeRing(0, Math.PI);
  }

  SCENES['3d'] = {
    fonts: [[FONT, '三次元']],
    build() {
      LETTERS.forEach(L => { L.m = measure(L.ch, FONT); });
    },
    frame(t) {
      const ph = t / 2 * TAU;

      // background primitives
      const shapes = [
        ['cube', 175, 120, 44, 1.2, [255, 170, 205], [190, 60, 120]],
        ['sphere', 95, 290, 34, 1.3, [200, 170, 255], [110, 70, 200]],
        ['octa', 1310, 105, 44, 1.35, [255, 230, 140], [220, 120, 40]],
        ['planet', 1365, 330, 36, 1.45, [140, 200, 255], [50, 90, 200]],
        ['cube', 615, 452, 20, 1.55, [140, 200, 255], [50, 80, 190]],
        ['sphere', 885, 48, 18, 1.6, [255, 170, 205], [190, 60, 120]],
        ['octa', 1180, 455, 22, 1.65, [200, 170, 255], [110, 70, 200]],
        ['sphere', 330, 450, 15, 1.7, [255, 230, 140], [220, 120, 40]],
      ];
      shapes.forEach(([ty, x, y, r, d, c1, c2], i) => {
        const s = pop(t, d, 0.5);
        if (s <= 0) return;
        const by = Math.sin(ph + i * 1.1) * 9;
        ctx.save(); ctx.translate(x, y + by); ctx.scale(s, s);
        const a = ph + i;
        if (ty === 'cube') mesh(ctx, CUBE, r * 0.62, a * 0.5 + 0.6, a + 0.5, [c1, c2]);
        else if (ty === 'octa') mesh(ctx, OCTA, r * 0.8, 0.35, a, [c1, c2]);
        else if (ty === 'sphere') sphere(ctx, r, [c1, c2]);
        else planet(ctx, r, [c1, c2], '#ffd873', -0.3 + Math.sin(ph) * 0.12);
        ctx.restore();
      });

      // extruded letters
      LETTERS.forEach((L, i) => {
        const t0 = 0.15 + i * 0.18;
        if (t < t0) return;
        const k = clamp((t - t0) / 0.9);
        const s = ease.outBack(clamp((t - t0) / 0.5), 2.2);
        const grow = ease.outCubic(k);
        // camera-like swing: extrusion direction slides left/right
        const yaw = Math.sin(ph - i * 0.45) * 0.75 + (1 - grow) * 1.6;
        const D = 42 * grow;
        const vx = -Math.sin(yaw) * D, vy = D * 0.6;
        const bob = Math.sin(ph - i * 0.8) * 8;
        const { m } = L;
        const x0 = -m.w / 2 + m.l, y0 = -m.h / 2 + m.a;
        ctx.save();
        ctx.translate(L.x, L.y + bob - vy * 0.4);
        ctx.scale(s * (0.94 + 0.06 * Math.cos(yaw)), s);
        ctx.font = FONT; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
        const N = Math.max(1, Math.ceil(D / 1.4));
        const layer = (j, fn) => { const q = j / N; fn(x0 + vx * q, y0 + vy * q, q); };
        for (let j = N; j >= 0; j--) layer(j, (x, y) => { ctx.strokeStyle = C.navy; ctx.lineWidth = 30; ctx.strokeText(L.ch, x, y); });
        for (let j = N; j >= 0; j--) layer(j, (x, y) => { ctx.strokeStyle = C.white; ctx.lineWidth = 20; ctx.strokeText(L.ch, x, y); });
        for (let j = N; j >= 1; j--) layer(j, (x, y, q) => {
          const col = mixc(L.near, L.far, q);
          ctx.fillStyle = col; ctx.fillText(L.ch, x, y);
          ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.strokeText(L.ch, x, y);
        });
        // front face edge + glossy face
        ctx.strokeStyle = mixc(L.far, L.far, 0); ctx.lineWidth = 6; ctx.strokeText(L.ch, x0, y0);
        const gr = ctx.createLinearGradient(0, -m.h / 2, 0, m.h / 2);
        gr.addColorStop(0, L.face[0]); gr.addColorStop(0.42, L.face[1]); gr.addColorStop(0.43, L.face[2]); gr.addColorStop(1, L.face[3]);
        ctx.fillStyle = gr; ctx.fillText(L.ch, x0, y0);
        ctx.restore();
      });

      // sparkles
      [[300, 60, 20, 1.5], [1460, 200, 16, 1.6], [1210, 40, 15, 1.7], [60, 420, 15, 1.75], [1450, 470, 14, 1.8]].forEach(([x, y, r, d], i) => {
        const s = pop(t, d, 0.4);
        if (s <= 0) return;
        const tw = 0.7 + 0.3 * Math.abs(Math.sin(ph * 2 + i * 1.7));
        ctx.save(); ctx.translate(x, y); ctx.rotate(Math.sin(ph + i) * 0.3); ctx.scale(s * tw, s * tw);
        sparkle(ctx, r, i % 2 ? '#ffd873' : '#ffb3d1', C.white, C.navy);
        ctx.restore();
      });
    },
  };
})();
