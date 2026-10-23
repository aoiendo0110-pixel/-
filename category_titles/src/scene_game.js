// 二次元/ゲーム — whole title on a frilled lace name plate with a bow on top
(() => {
  let G, BIG;
  SCENES.game = {
    build() {
      const o = { outline: 16, depth: 9 };
      G = [
        glyph('二', 150, paints.pinkDots, P.pinkDeep, o), glyph('次', 150, paints.chocSolid, P.chocD, o),
        glyph('元', 150, paints.redStripe, P.redD, o), glyph('/', 150, paints.heartRed, P.redD, o),
        glyph('ゲ', 150, paints.pinkHeart, P.pinkDeep, o), glyph('ー', 150, paints.chocBar, P.chocD, o),
        glyph('ム', 150, paints.pinkDots, P.pinkDeep, o),
      ];
      BIG = heartSprite(80, paints.heartRed, P.redD, { outline: 12, depth: 7 });
    },
    frame(t, ph) {
      const ps = pop(t, 0.05, 0.6);
      if (ps > 0) {
        ctx.save(); ctx.translate(750, 258 + Math.sin(ph) * 4); ctx.scale(ps, ps); ctx.translate(-750, -258);
        lacePlate(ctx, 190, 150, 1120, 216, t);
        ctx.restore();
      }
      const X = [318, 470, 622, 742, 862, 1012, 1162];
      drawLetters(t, ph, X.map((x, i) => [G[i], x, 258 + (i % 2 ? 6 : -4), [-0.06, 0.05, -0.04, 0.1, -0.05, 0.03, 0.06][i], 0.35 + i * 0.09, 7]));
      bowAt(t, ph, 750, 128, 0.95, 0.85, 0);
      // tap heart pinned to the plate's lower-right corner
      const { press, beat } = beatAt(t, 1.2);
      heartRipple(t, 1310, 375, 38, 1.2);
      blit(BIG, 1310, 375, pop(t, 1.0, 0.6) * beat, 0.2 + Math.sin(ph) * 0.05, 1 / press * 1.02, press);
      drawDeco(t, ph, [
        ['star', 330, 70, 1.0, 1.05, 1.2], ['hp', 510, 85, 0.9, 1.1, 2.1], ['bon', 1005, 80, 0.9, 1.15, 0.6],
        ['hr', 1180, 70, 0.9, 1.2, 1.7], ['star', 1440, 170, 0.9, 1.25, 2.4], ['hc', 110, 150, 0.9, 1.3, 0.3],
        ['star', 75, 360, 0.8, 1.35, 1.0], ['hp', 470, 455, 0.85, 1.4, 4.1], ['bon', 860, 460, 0.85, 1.45, 2.8],
        ['hr', 1450, 450, 0.8, 1.5, 3.3],
      ]);
    },
  };
})();
