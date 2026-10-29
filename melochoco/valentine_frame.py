"""バレンタイン×チョコの正方形フレーム (中央が大きく透過で抜けている PNG).

  pip install numpy pillow
  python3 valentine_frame.py --out frame_out            # 2048x2048
  python3 valentine_frame.py --out frame_out --size 1080

- frame_square.png : 角丸の四角の窓 (窓は全体の約 76%)
- frame_heart.png  : 大きいハートの窓
- *_preview.png    : 窓に市松模様を敷いた確認用
上辺はチョコがとろ〜り、窓のふちは白いレースのフリル、四隅に🎀リボン・ハートのチョコ・ハートとキラキラ.
リボンやハートは stripe_bg.py の部品を使う.
"""
import argparse
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import stripe_bg as P

S = 2048          # 設計サイズ (ここで描いてから --size に縮小)
PINK_BG = (246, 170, 196)
PINK_DOT = (252, 210, 224)
CREAM = (255, 248, 244)
STITCH = (232, 96, 138)
RED = P.RED
CHOCO = np.array(P.CHOCO, np.float32) / 255


def rrect_path(x0, y0, x1, y1, r, step):
    """角丸四角形のふちを step 間隔でなぞった点."""
    segs = []
    w, h = x1 - x0 - 2 * r, y1 - y0 - 2 * r
    per = 2 * (w + h) + 2 * math.pi * r
    n = int(per / step)
    pts = []
    for i in range(n):
        s = per * i / n
        for (L, f) in ((w, lambda u: (x0 + r + u, y0)), (math.pi * r / 2, lambda u: (x1 - r + r * math.sin(u / r), y0 + r - r * math.cos(u / r))),
                       (h, lambda u: (x1, y0 + r + u)), (math.pi * r / 2, lambda u: (x1 - r + r * math.cos(u / r), y1 - r + r * math.sin(u / r))),
                       (w, lambda u: (x1 - r - u, y1)), (math.pi * r / 2, lambda u: (x0 + r - r * math.sin(u / r), y1 - r + r * math.cos(u / r))),
                       (h, lambda u: (x0, y1 - r - u)), (math.pi * r / 2, lambda u: (x0 + r - r * math.cos(u / r), y0 + r - r * math.sin(u / r)))):
            if s <= L:
                pts.append(f(s))
                break
            s -= L
    return pts


def heart_path(cx, cy, size, step):
    """大きいハートのふち (size は横幅)."""
    raw = P.heart_pts(cx, cy, size, n=2000)
    out, acc = [raw[0]], 0.0
    for a, b in zip(raw, raw[1:] + raw[:1]):
        acc += math.dist(a, b)
        if acc >= step:
            out.append(b)
            acc = 0.0
    return out


def scallop_mask(pts, base_poly_fn, r):
    """base_poly_fn で塗った形 + ふちに沿った円 (スカラップ)."""
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    base_poly_fn(d)
    for x, y in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return m


def offset_pts(pts, center, k):
    cx, cy = center
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts]


def background():
    """フレーム部分の柄: ピンクに水玉と小さいハート."""
    im = Image.new("RGBA", (S, S), PINK_BG + (255,))
    d = ImageDraw.Draw(im)
    p = 92
    for j, y in enumerate(range(-p, S + p, p // 2)):
        for x in range(-p, S + p, p):
            cx = x + (p // 2 if j % 2 else 0)
            if (j + x // p) % 3 == 0:
                d.polygon(P.heart_pts(cx, y, 34), fill=(250, 196, 214, 255))
            else:
                d.ellipse((cx - 13, y - 13, cx + 13, y + 13), fill=PINK_DOT + (255,))
    return im


def choco_top(h=330, seed=3):
    """上辺のチョコの垂れ (SDF + ツヤの陰影)."""
    rng = random.Random(seed)
    ys, xs = np.mgrid[0:h, 0:S].astype(np.float32)
    d = ys - (120 + 14 * np.sin(xs / 120) + 8 * np.sin(xs / 47 + 1))
    for x in np.linspace(90, S - 90, 13) + np.array([rng.uniform(-45, 45) for _ in range(13)]):
        r, L = rng.uniform(20, 32), rng.uniform(40, 170)
        m = np.abs(xs - x) < r * 3
        X, Y = xs[m], ys[m]
        tip = 110 + L
        neck = np.where(Y < tip, np.abs(X - x) - r * 0.8, np.hypot(X - x, Y - tip) - r * 0.8)
        bulb = np.hypot(X - x, Y - tip) - r * 1.18
        dd = np.minimum(neck, bulb)
        hh = np.clip(0.5 + 0.5 * (d[m] - dd) / 34, 0, 1)
        d[m] = d[m] * (1 - hh) + dd * hh - 34 * hh * (1 - hh)
    a = np.clip(0.5 - d, 0, 1)
    q = np.clip(-d / 30, 0, 1)
    gy, gx = np.gradient(np.sqrt(1 - (1 - q) ** 2) * 30)
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-0.4, -0.6, 0.7])
    L /= np.linalg.norm(L)
    Hh = L + np.array([0, 0, 1.0])
    Hh /= np.linalg.norm(Hh)
    col = CHOCO * (0.5 + 0.6 * np.clip(n @ L, 0, 1))[..., None] + (np.clip(n @ Hh, 0, 1) ** 60)[..., None] * 0.9
    im = Image.fromarray((np.concatenate([np.clip(col, 0, 1), a[..., None]], -1) * 255).astype(np.uint8))
    out = Image.new("RGBA", (S, h + 14), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (110, 30, 50, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: v * 0.3).filter(ImageFilter.GaussianBlur(8)))
    out.alpha_composite(sh, (0, 10))
    out.alpha_composite(im, (0, 0))
    return out


def soft_shadow(mask, alpha=0.35, blur=10, dy=8):
    sh = Image.new("RGBA", (S, S), (130, 40, 70, 0))
    sh.putalpha(mask.point(lambda v: v * alpha).filter(ImageFilter.GaussianBlur(blur)))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, dy))
    return out


def build(window="square"):
    im = background()
    c = (S / 2, S / 2 + 20)
    if window == "square":
        x0, y0, x1, y1, r = 250, 270, S - 250, S - 230, 120
        edge = rrect_path(x0, y0, x1, y1, r, 52)
        poly = lambda d, k=1.0: d.rounded_rectangle(
            (c[0] - (c[0] - x0) * k, c[1] - (c[1] - y0) * k, c[0] + (x1 - c[0]) * k, c[1] + (y1 - c[1]) * k),
            radius=r * k, fill=255)
    else:
        size, cy = 1600, 900      # 上はチョコの下から、下の先端まで収まる大きさ
        edge = heart_path(S / 2, cy, size, 52)
        hp = P.heart_pts(S / 2, cy, size, n=400)
        poly = lambda d, k=1.0: d.polygon(offset_pts(hp, (S / 2, cy), k), fill=255)
        c = (S / 2, cy)
    # 赤い細いライン → 白いレース (外側スカラップ) → ステッチ → 窓 (内側スカラップ)
    outer = scallop_mask(offset_pts(edge, c, 1.075), lambda d: poly(d, 1.06), 30)
    red = scallop_mask(offset_pts(edge, c, 1.085), lambda d: poly(d, 1.07), 34)
    im.alpha_composite(soft_shadow(red))
    im.paste(Image.new("RGBA", (S, S), RED + (255,)), (0, 0), red)
    im.paste(Image.new("RGBA", (S, S), CREAM + (255,)), (0, 0), outer)
    d = ImageDraw.Draw(im)
    for (x, y) in offset_pts(edge, c, 1.075):           # レースの透かし穴
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=PINK_BG + (255,))
    st = offset_pts(edge, c, 1.03)
    for i in range(0, len(st) - 1, 2):                    # ステッチ
        d.line((st[i], st[i + 1]), fill=STITCH + (255,), width=7)
    # 窓を抜く (ふちは内側にもスカラップ) + 窓のふちに薄い影
    win = scallop_mask(offset_pts(edge, c, 0.995), lambda d2: poly(d2, 0.985), 20)
    win = win.filter(ImageFilter.GaussianBlur(0.8))
    inner_sh = Image.new("RGBA", (S, S), (120, 40, 60, 0))
    ring = Image.eval(win.filter(ImageFilter.GaussianBlur(10)), lambda v: 255 - v)
    inner_sh.putalpha(Image.composite(ring.point(lambda v: v * 0.35), Image.new("L", (S, S), 0), win))
    a = np.asarray(im.getchannel("A")).astype(np.float32) * (1 - np.asarray(win, np.float32) / 255)
    im.putalpha(Image.fromarray(a.astype(np.uint8)))
    im.alpha_composite(inner_sh)
    # 上辺のチョコ
    im.alpha_composite(choco_top(), (0, 0))
    deco(im, window)
    return im


def paste(im, sp, x, y, rot=0.0):
    if rot:
        sp = sp.rotate(rot, Image.BICUBIC, expand=True)
    im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))


def deco(im, window):
    redbow = P.bow_sprite(430, P.RED + (255,), P.RED_D + (255,))
    pinkbow = P.bow_sprite(330, (250, 110, 155, 255), (210, 70, 115, 255))
    ch_big, ch_mid, ch_s = P.choco_heart_sprite(230), P.choco_heart_sprite(170), P.choco_heart_sprite(120)
    hr = [P.heart_sprite(s, col + (255,), line=(255, 255, 255, 255))
          for s, col in ((110, P.RED), (80, (240, 128, 166)), (64, P.RED), (56, (255, 190, 210)))]
    sp = [P.sparkle_sprite(s) for s in (90, 70, 54)]
    if window == "square":
        paste(im, redbow, 300, 300, -14)
        paste(im, ch_big, S - 250, S - 260, 12)
        paste(im, ch_s, S - 420, S - 160, -18)
        paste(im, hr[0], S - 160, S - 430, 16)
        paste(im, pinkbow, 250, S - 250, 10)
        paste(im, hr[1], 430, S - 140, -12)
        paste(im, ch_mid, S - 260, 300, -10)
        paste(im, hr[2], S - 420, 190, 14)
        paste(im, hr[3], 150, 520, -8)
        paste(im, hr[2], S / 2, S - 120, 0)
        paste(im, P.heart_sprite(52, (255, 190, 210, 255), line=(255, 255, 255, 255)), S / 2 - 90, S - 110, -15)
        paste(im, P.heart_sprite(52, (240, 128, 166, 255), line=(255, 255, 255, 255)), S / 2 + 90, S - 110, 15)
        for (x, y, k) in ((520, 170, 0), (S - 150, 650, 1), (150, S - 560, 2), (S - 640, S - 110, 1), (S / 2 + 300, 160, 2)):
            paste(im, sp[k], x, y)
    else:
        paste(im, redbow, S / 2, 330, 0)
        paste(im, ch_big, 260, S - 300, -12)
        paste(im, ch_mid, S - 270, S - 300, 12)
        paste(im, pinkbow, 270, 520, -10)
        paste(im, hr[0], S - 250, 560, 14)
        paste(im, hr[1], S / 2 - 260, S - 120, -12)
        paste(im, hr[2], S / 2 + 260, S - 120, 12)
        paste(im, hr[2], 140, S - 640, -10)
        paste(im, hr[3], S - 140, S - 660, 10)
        for (x, y, k) in ((170, 300, 0), (S - 170, 300, 0), (S / 2 - 420, S - 160, 1), (S / 2 + 420, S - 160, 1),
                          (S - 120, 1000, 2), (120, 1000, 2)):
            paste(im, sp[k], x, y)


def checker(size, n=32):
    yy, xx = np.mgrid[0:size, 0:size]
    v = (((xx // n) + (yy // n)) % 2) * 30 + 210
    return Image.fromarray(np.stack([v, v, v, np.full_like(v, 255)], -1).astype(np.uint8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="frame_out")
    ap.add_argument("--size", type=int, default=2048)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for name in ("square", "heart"):
        im = build(name)
        if a.size != S:
            im = im.resize((a.size, a.size), Image.LANCZOS)
        im.save(os.path.join(a.out, f"frame_{name}.png"))
        pv = checker(im.width)
        pv.alpha_composite(im)
        pv.convert("RGB").resize((1024, 1024), Image.LANCZOS).save(os.path.join(a.out, f"frame_{name}_preview.png"))
        al = np.asarray(im.getchannel("A"))
        print(name, "透過の割合:", round(float((al < 8).mean()), 3))


if __name__ == "__main__":
    main()
