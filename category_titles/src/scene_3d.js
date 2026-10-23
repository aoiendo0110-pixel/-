// 三次元 — each letter sits on its own chocolate heart that beats in turn, frill ribbon below
(() => {
  let G, PLATE;
  function chocHeart(g, w, h) {
    const gr = g.createRadialGradient(w * 0.35, h * 0.3, 8, w * 0.5, h * 0.5, w * 0.75);
    gr.addColorStop(0, '#b8774c'); gr.addColorStop(0.6, '#7a4027'); gr.addColorStop(1, '#4a2214');
    g.fillStyle = gr; g.fillRect(-50, -50, w + 100, h + 100);
    // pink drizzle zigzag
    g.strokeStyle = '#ffa6cb'; g.lineWidth = 7; g.lineCap = 'round'; g.lineJoin = 'round';
    for (const yy of [h * 0.78, h * 0.86]) {
      g.beginPath();
      for (let x = -10, k = 0; x <= w + 10; x += 22, k++) g.lineTo(x, yy + (k % 2 ? -10 : 10));
      g.stroke();
    }
    // sprinkles
    const cols = ['#ffffff', '#ff8fbf', '#e8344e'];
    for (let i = 0; i < 16; i++) {
      const x = (i * 71) % w, y = h * 0.08 + ((i * 37) % (h * 0.55));
      g.save(); g.translate(x, y); g.rotate(i); g.fillStyle = cols[i % 3]; g.fillRect(-6, -2, 12, 4); g.restore();
    }
    g.fillStyle = 'rgba(255,255,255,0.55)';
    g.beginPath(); g.ellipse(w * 0.28, h * 0.22, w * 0.1, h * 0.05, -0.6, 0, 7); g.fill();
  }
  SCENES['3d'] = {
    build() {
      const o = { outline: 18, depth: 10 };
      G = [glyph('三', 165, paints.pinkDots, P.pinkDeep, o), glyph('次', 165, paints.redStripe, P.redD, o), glyph('元', 165, paints.pinkHeart, P.pinkDeep, o)];
      PLATE = heartSprite(270, chocHeart, P.chocD, { outline: 16, depth: 10 });
    },
    frame(t, ph) {
      const fr = clamp((t - 0.6) / 0.6);
      if (fr > 0) drawFrill(ctx, t, 230, 230 + (1270 - 230) * (1 - Math.pow(1 - fr, 3)), 440);
      const X = [455, 750, 1045], Y = [250, 236, 250];
      X.forEach((x, i) => {
        // hearts drop in, then beat one after another
        const d = 0.05 + i * 0.15;
        if (t < d) return;
        const k = clamp((t - d) / 0.55);
        const drop = (1 - ease.outBack(k, 1.6)) * -420;
        const { press, beat } = beatAt(t + i * 0.33, 1.0 + i * 0.33);
        const bob = Math.sin(ph - i * 0.9) * 7;
        const rot = [-0.08, 0, 0.08][i] + Math.sin(ph - i * 0.9 + 1) * 0.03;
        blit(PLATE, x, Y[i] + drop + bob, beat, rot, 1 / press * 1.01, press);
        // letter rides on the heart
        const s = pop(t, 0.45 + i * 0.15);
        const sq = beat * (0.96 + 0.04 * press);
        blit(G[i], x + Math.sin(rot) * 20, Y[i] - 22 + drop + bob, s * sq, rot * 0.6);
      });
      bowAt(t, ph, 750, 70, 0.9, 0.68, 0);
      drawDeco(t, ph, [
        ['star', 240, 80, 1.0, 1.05, 1.2], ['hr', 600, 55, 0.9, 1.1, 2.1], ['hp', 905, 58, 0.9, 1.15, 0.6],
        ['bon', 1250, 80, 0.95, 1.2, 1.7], ['star', 1400, 210, 1.0, 1.25, 2.4], ['hc', 1330, 345, 1.0, 1.3, 0.3],
        ['hp', 150, 220, 1.0, 1.35, 1.0], ['bon', 190, 360, 0.9, 1.4, 4.1], ['star', 1450, 420, 0.75, 1.45, 2.8],
        ['hr', 70, 110, 0.8, 1.5, 3.3],
      ]);
    },
  };
})();
