// 一次創作 — single row like 各一; bow on the last letter, beating tap-heart on the left
(() => {
  let G, BIG;
  SCENES.sousaku = {
    build() {
      G = [
        glyph('一', 230, paints.chocBar, P.chocD, { outline: 20, depth: 11 }),
        glyph('次', 230, paints.pinkDots, P.pinkDeep, { outline: 20, depth: 11 }),
        glyph('創', 230, paints.redStripe, P.redD, { outline: 20, depth: 11 }),
        glyph('作', 230, paints.pinkHeart, P.pinkDeep, { outline: 20, depth: 11 }),
      ];
      BIG = heartSprite(84, paints.heartRed, P.redD, { outline: 13, depth: 7 });
    },
    frame(t, ph) {
      const fr = clamp((t - 0.05) / 0.6);
      if (fr > 0) drawFrill(ctx, t, 300, 300 + (1250 - 300) * (1 - Math.pow(1 - fr, 3)), 400);
      // tap heart top-left
      const { press, beat } = beatAt(t, 1.0);
      heartRipple(t, 225, 150, 40, 1.0);
      blit(BIG, 225, 150, pop(t, 0.75, 0.6) * beat, -0.15 + Math.sin(ph) * 0.05, 1 / press * 1.02, press);
      drawLetters(t, ph, [
        [G[0], 420, 250, 0.05, 0.15, 9],
        [G[1], 650, 228, -0.06, 0.27, 9],
        [G[2], 885, 238, 0.05, 0.39, 9],
        [G[3], 1115, 226, -0.07, 0.51, 9],
      ]);
      bowAt(t, ph, 1215, 92, 0.65, 0.78, 0.3, -1);
      drawDeco(t, ph, [
        ['star', 330, 75, 1.0, 1.05, 1.2], ['bon', 560, 62, 0.9, 1.1, 2.1], ['hr', 770, 70, 1.0, 1.15, 0.6],
        ['hc', 1000, 72, 1.0, 1.2, 1.7], ['hp', 1395, 190, 1.0, 1.25, 2.4], ['star', 1440, 330, 0.9, 1.3, 0.3],
        ['bon', 1335, 440, 0.95, 1.35, 1.0], ['hr', 560, 465, 0.9, 1.4, 4.1], ['star', 870, 470, 0.8, 1.45, 2.8],
        ['hp', 165, 300, 0.9, 1.5, 3.3], ['star', 110, 80, 0.75, 1.55, 5.0],
      ]);
    },
  };
})();
