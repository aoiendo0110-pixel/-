// 二次元/アニメ — two staggered tiers sliding in from each side, chocolate stick as the slash
(() => {
  let G, BIG;
  SCENES.anime = {
    build() {
      const o = { outline: 18, depth: 10 };
      G = [
        glyph('二', 190, paints.pinkDots, P.pinkDeep, o), glyph('次', 190, paints.chocSolid, P.chocD, o), glyph('元', 190, paints.pinkHeart, P.pinkDeep, o),
        glyph('ア', 190, paints.redStripe, P.redD, o), glyph('ニ', 190, paints.chocBar, P.chocD, o), glyph('メ', 190, paints.pinkDots, P.pinkDeep, o),
      ];
      BIG = heartSprite(92, paints.heartRed, P.redD, { outline: 13, depth: 7 });
    },
    frame(t, ph) {
      const f1 = clamp((t - 0.05) / 0.55), f2 = clamp((t - 0.3) / 0.55);
      if (f1 > 0) drawFrill(ctx, t, 170, 170 + (770 - 170) * (1 - Math.pow(1 - f1, 3)), 268);
      if (f2 > 0) { const e = 1 - Math.pow(1 - f2, 3); drawFrill(ctx, t + 0.5, 1370 - (1370 - 770) * e, 1370, 425); }
      // tap heart in the upper-right gap
      const { press, beat } = beatAt(t, 1.0);
      heartRipple(t, 1195, 128, 44, 1.0);
      blit(BIG, 1195, 128, pop(t, 0.9, 0.6) * beat, 0.12 + Math.sin(ph) * 0.05, 1 / press * 1.02, press);
      drawLetters(t, ph, [
        [G[0], 290, 158, -0.06, 0.1, 8], [G[1], 482, 150, 0.04, 0.18, 8], [G[2], 672, 160, -0.04, 0.26, 8],
        [G[3], 870, 322, 0.05, 0.42, 8], [G[4], 1065, 330, -0.04, 0.5, 8], [G[5], 1260, 320, 0.06, 0.58, 8],
      ], { slide: [-700, -700, -700, 700, 700, 700] });
      // chocolate stick slash
      {
        const s = pop(t, 0.36, 0.5);
        if (s > 0) {
          ctx.save(); ctx.translate(772, 242 + Math.sin(ph + 1) * 6); ctx.rotate(-1.05 + Math.sin(ph * 2) * 0.04); ctx.scale(s, s);
          chocStick(ctx, 240, 26); ctx.restore();
        }
      }
      bowAt(t, ph, 195, 66, 0.4, 0.8, -0.3);
      bowAt(t, ph + 1, 1352, 230, 0.75, 0.55, 0.3, -1);
      drawDeco(t, ph, [
        ['star', 900, 60, 1.0, 1.05, 1.2], ['hc', 1010, 150, 0.9, 1.1, 2.1], ['bon', 1420, 75, 0.95, 1.15, 0.6],
        ['star', 1455, 360, 0.8, 1.2, 1.7], ['hr', 1340, 40, 0.8, 1.25, 2.4], ['hp', 175, 395, 1.0, 1.3, 0.3],
        ['bon', 420, 440, 0.95, 1.35, 1.0], ['star', 620, 370, 0.9, 1.4, 4.1], ['hr', 80, 210, 0.85, 1.45, 2.8],
        ['star', 590, 470, 0.7, 1.5, 3.3],
      ]);
    },
  };
})();
