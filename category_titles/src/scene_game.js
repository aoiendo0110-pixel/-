// 二次元/ゲーム — real pixel art: whole scene drawn on a 150x50 grid and scaled x10 with nearest-neighbour
(() => {
  const LW = 150, LH = 50, U = 10;
  const low = mk(LW, LH), g = low.getContext('2d');
  const C = {
    ink: '#1d1640', shade: '#0f0a26', white: '#ffffff',
    blue: ['#8ff3ff', '#4fd0ff', '#3f8cff', '#5b4bd8'],
    warm: ['#fff07a', '#ffc43d', '#ff8a3d', '#ff4f7b'],
    pink: '#ff6bd0', pinkL: '#ffc2ec', red: '#ff3d6b', yel: '#ffd23d', yelL: '#fff3a8', lav: '#b48cff',
  };
  const px = (x, y, col) => { g.fillStyle = col; g.fillRect(x, y, 1, 1); };
  const rect = (x, y, w, h, col) => { g.fillStyle = col; g.fillRect(x, y, w, h); };

  // binary glyph masks from DotGothic16 at its native 16px grid
  function maskOf(ch) {
    const c = mk(24, 24), cg = c.getContext('2d');
    cg.font = '16px Dot'; cg.textBaseline = 'top'; cg.fillStyle = '#000';
    cg.fillText(ch, 2, 2);
    const d = cg.getImageData(0, 0, 24, 24).data;
    const m = [];
    for (let y = 0; y < 24; y++) { m.push([]); for (let x = 0; x < 24; x++) m[y].push(d[(y * 24 + x) * 4 + 3] >= 110 ? 1 : 0); }
    return m;
  }
  function dilate(m) {
    return m.map((row, y) => row.map((v, x) => {
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if (m[y + dy] && m[y + dy][x + dx]) return 1;
      return 0;
    }));
  }
  function drawMask(m, ox, oy, colFn) {
    m.forEach((row, y) => row.forEach((v, x) => { if (v) px(ox + x - 2, oy + y - 2, colFn(x, y)); }));
  }

  // tiny 3x5 font for HUD text
  const FONT = {
    P: '111101111100100', R: '110101110101101', E: '111100110100111', S: '011100010001110',
    T: '111010010010010', A: '010101111101101', H: '101101111101101', ' ': '000000000000000',
  };
  function hud(str, x, y, col) {
    [...str].forEach((ch, i) => {
      const b = FONT[ch];
      for (let k = 0; k < 15; k++) if (b[k] === '1') {
        const xx = x + i * 4 + (k % 3), yy = y + Math.floor(k / 3);
        px(xx + 1, yy + 1, C.ink); // drop shadow
      }
      for (let k = 0; k < 15; k++) if (b[k] === '1') px(x + i * 4 + (k % 3), y + Math.floor(k / 3), col);
    });
  }
  const HEART = ['.##.##.', '#######', '#######', '.#####.', '..###..', '...#...'];
  function sprite(rows, x, y, col, outline = C.ink) {
    const hit = (r, c) => rows[r] && rows[r][c] === '#';
    for (let r = -1; r <= rows.length; r++) for (let c = -1; c <= rows[0].length; c++) {
      if (hit(r, c)) continue;
      let n = false;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if ((dx === 0 || dy === 0) && hit(r + dy, c + dx)) n = true;
      if (n) px(x + c, y + r, outline);
    }
    rows.forEach((row, r) => [...row].forEach((ch, c) => { if (ch === '#') px(x + c, y + r, col); }));
  }
  function heart(x, y, full) {
    sprite(HEART, x, y, full ? C.red : C.pinkL);
    if (full) { px(x + 1, y + 1, C.white); px(x + 2, y + 1, C.pinkL); }
  }
  function coin(x, y, f) {
    // 4-frame spin: widths 6,4,2,4
    const w = [6, 4, 2, 4][f], ox = x + (6 - w) / 2;
    rect(ox - 1, y, w + 2, 8, C.ink); rect(ox, y - 1, w, 10, C.ink);
    rect(ox, y, w, 8, C.yel);
    if (w > 2) { rect(ox + 1, y + 1, 1, 6, C.yelL); rect(ox + w - 1, y + 1, 1, 7, '#e89a1c'); }
  }
  function star(x, y, big, col) {
    if (big) { rect(x - 2, y, 5, 1, col); rect(x, y - 2, 1, 5, col); rect(x - 1, y - 1, 3, 3, col); px(x, y, C.white); }
    else { rect(x - 1, y, 3, 1, col); rect(x, y - 1, 1, 3, col); }
  }
  function pad(x, y) {
    // gamepad 15x8
    rect(x + 1, y, 13, 8, C.ink); rect(x, y + 1, 15, 6, C.ink); rect(x + 1, y + 7, 4, 2, C.ink); rect(x + 10, y + 7, 4, 2, C.ink);
    rect(x + 1, y + 1, 13, 6, C.lav); rect(x + 2, y + 7, 2, 1, C.lav); rect(x + 11, y + 7, 2, 1, C.lav);
    rect(x + 2, y + 1, 11, 1, '#d7c4ff');
    rect(x + 3, y + 3, 3, 1, C.ink); rect(x + 4, y + 2, 1, 3, C.ink); // d-pad
    px(x + 10, y + 4, C.red); px(x + 12, y + 3, C.yel); // buttons
  }

  const chars = ['二', '次', '元', '/', 'ゲ', 'ー', 'ム'];
  let M;
  SCENES.game = {
    fonts: [['16px Dot', '二次元/ゲーム']],
    build() {
      M = chars.map(ch => {
        const m0 = maskOf(ch);
        // pixel-bold: OR with copies shifted right and down
        const m = m0.map((row, y) => row.map((v, x) => v || row[x - 1] || (m0[y - 1] && (m0[y - 1][x] || m0[y - 1][x - 1])) ? 1 : 0));
        const d1 = dilate(m), d2 = dilate(d1);
        return { m, d1, d2 };
      });
    },
    frame(t) {
      g.clearRect(0, 0, LW, LH);
      const ph = t / 2 * TAU;
      const st = Math.floor(t * 12) / 12; // stepped retro timing
      const sph = st / 2 * TAU;

      // HUD: HP hearts top-left
      if (t > 0.1) {
        hud('HP', 5, 4, C.white);
        for (let i = 0; i < 3; i++) heart(15 + i * 9, 3, t > 1.4 + i * 0.12);
      }
      // coins top-right
      [[141, 3, 0], [76, 2, 2]].forEach(([x, y, o], i) => {
        if (t < 1.3 + i * 0.1) return;
        const hop = 0;
        coin(x, y + hop, (Math.floor(t * 8) + o) % 4);
      });

      // title letters: blip in one by one, then stepped wave hop
      const XS = [14, 32, 50, 67, 81, 99, 117], Y0 = 15;
      chars.forEach((ch, i) => {
        const t0 = 0.25 + i * 0.13;
        if (t < t0) return;
        const k = t - t0;
        let dy = k < 0.08 ? -4 : k < 0.16 ? -2 : 0;
        dy += Math.round(Math.max(0, Math.sin(sph - i * 0.7)) * -3);
        const ox = XS[i], oy = Y0 + dy;
        const { m, d1, d2 } = M[i];
        const pal = i < 3 ? C.blue : C.warm;
        // palette cycle on the right half for an arcade shimmer
        const cyc = i > 3 ? Math.floor(t * 6) % 4 : 0;
        drawMask(d2, ox + 1, oy + 1, () => C.shade);
        drawMask(d2, ox, oy, () => C.ink);
        drawMask(d1, ox, oy, () => C.white);
        drawMask(m, ox, oy, (x, y) => {
          if (ch === '/') return C.pink;
          const band = clamp(Math.floor((y - 2) / 4.5), 0, 3);
          return i > 3 && cyc ? pal[(band + cyc) % 4] : pal[band];
        });
        // gloss pixel
        for (let y = 0; y < 24; y++) { const x = m[y].indexOf(1); if (x >= 0) { px(ox + x - 2, oy + y - 2, C.white); break; } }
      });

      // stars twinkle
      [[8, 22, 0], [140, 22, 1], [62, 6, 2], [96, 8, 3], [112, 44, 4], [40, 44, 5], [146, 40, 6]].forEach(([x, y, o]) => {
        if (t < 1.2 + o * 0.06) return;
        const f = (Math.floor(t * 6) + o) % 4;
        if (f === 3) return;
        star(x, y, f === 1, o % 2 ? C.yelL : C.pinkL);
      });

      // gamepad bottom-right
      if (t > 1.5) pad(126, 37 + Math.round(Math.max(0, Math.sin(sph + 2)) * -2));

      // PRESS START blinking + cursor
      if (t > 1.6) {
        const on = Math.floor((t - 1.6) * 2) % 2 === 0;
        if (on) hud('PRESS START', 54, 41, C.yelL);
        const cx = 48 + (Math.floor(t * 4) % 2);
        rect(cx, 41, 1, 5, C.pink); rect(cx + 1, 42, 1, 3, C.pink); px(cx + 2, 43, C.pink);
      }

      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(low, 0, 0, LW * U, LH * U);
    },
  };
})();
