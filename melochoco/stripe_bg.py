"""柄の帯 + レースの縁取りが縦に並ぶ、9:16 の動く背景 (チョコ・バレンタイン・フリル・リボン).

  pip install numpy pillow
  python3 stripe_bg.py --out stripe_bg.mp4                  # 1080x1920 / 30fps / 10秒ループ
  python3 stripe_bg.py --out stripe_bg.mp4 --preview 2.5    # 指定秒の静止画だけ

帯 (上から): チョコがとろ〜り垂れるピンク / 赤のギンガムチェック / リボン柄 / 板チョコ / ハート柄 / 水玉.
帯の間は白いレース (スカラップ + ステッチ). 帯ごとに左右交互にゆっくり流れ、
リボン・ハートのチャーム・ハートのチョコがゆらゆら、ハートとキラキラがふわふわ上っていく.
動きは全部 10 秒周期にそろえてあるので、最後と最初がつながる (ループ素材).
"""
import argparse
import math
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS, D = 1080, 1920, 30, 10
SS = 3   # スプライトと柄のスーパーサンプリング倍率
TAU = 2 * math.pi

PINK_L = (252, 214, 226)
PINK = (246, 168, 194)
PINK_M = (240, 128, 166)
HOT = (232, 80, 126)
RED = (214, 38, 64)
RED_D = (170, 26, 50)
CHOCO = (110, 60, 46)
CHOCO_D = (72, 38, 30)
CHOCO_L = (156, 92, 70)
CREAM = (255, 248, 244)


# ---- 形 ----------------------------------------------------------------------------
def heart_pts(cx, cy, s, n=60, rot=0.0):
    pts = []
    ca, sa = math.cos(rot), math.sin(rot)
    for i in range(n):
        t = TAU * i / n
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        x, y = x / 32 * s, (y + 2) / 32 * s
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


def sprite(w, h, draw_fn):
    """SS 倍で描いて縮小した RGBA スプライト."""
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), SS)
    return im.resize((w, h), Image.LANCZOS)


def heart_sprite(s, fill, line=None, shine=True):
    def f(d, k):
        c = s * k / 2 + 3 * k
        if line:
            d.polygon(heart_pts(c, c, s * k * 1.0 + 5 * k), fill=line)
        d.polygon(heart_pts(c, c, s * k), fill=fill)
        if shine:
            d.ellipse((c - s * k * 0.3, c - s * k * 0.28, c - s * k * 0.12, c - s * k * 0.16),
                      fill=(255, 255, 255, 190))
    return sprite(s + 6, s + 6, f)


def bez(p0, p1, p2, p3, n=24):
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
            for t in [i / n for i in range(n + 1)]]


def path(start, *curves):
    """3次ベジェをつないだ閉じた形 (curves は (c1, c2, end) の並び)."""
    pts, p = [], start
    for c1, c2, e in curves:
        pts += bez(p, c1, c2, e)
        p = e
    return pts


# 🎀 の形 (横幅 1, 結び目が原点, 右半分. 左は左右反転)
BOW_LOOP = path((0.05, -0.06), ((0.17, -0.31), (0.45, -0.37), (0.48, -0.13)),
                ((0.51, 0.06), (0.37, 0.16), (0.22, 0.11)), ((0.14, 0.08), (0.08, 0.06), (0.05, 0.05)))
BOW_FOLD = path((0.07, -0.03), ((0.14, -0.11), (0.25, -0.1), (0.27, -0.01)),
                ((0.21, 0.04), (0.13, 0.04), (0.07, 0.03)))
BOW_SHINE = path((0.12, -0.17), ((0.2, -0.27), (0.35, -0.3), (0.42, -0.22)),
                 ((0.34, -0.25), (0.22, -0.23), (0.14, -0.14)))
BOW_TAIL = path((0.02, 0.02), ((0.1, 0.15), (0.2, 0.28), (0.32, 0.42)), ((0.28, 0.42), (0.24, 0.41), (0.21, 0.39)),
                ((0.19, 0.42), (0.16, 0.45), (0.13, 0.49)), ((0.08, 0.34), (0.03, 0.2), (-0.04, 0.07)))


def bow_sprite(s, fill, dark, knot=None):
    """🎀 みたいなリボン (ふっくらした2つの輪 + 結び目 + V字に切ったしっぽ). s は横幅."""
    knot = knot or fill
    h = int(s * 0.9)
    oy = 0.37   # 結び目の高さ (上端からの割合 × 横幅)

    def f(d, k):
        S_, cx, cy = s * k, s * k / 2, oy * s * k
        sh = 0.018 * S_

        def P(pts, side=1, dx=0.0, dy=0.0):
            return [(cx + side * x * S_ + dx, cy + y * S_ + dy) for x, y in pts]
        for side in (-1, 1):                       # しっぽ (影 → 本体)
            d.polygon(P(BOW_TAIL, side, 0, sh), fill=dark)
            d.polygon(P(BOW_TAIL, side), fill=fill)
            d.line(P([(0.05, 0.1), (0.2, 0.37)], side), fill=dark, width=max(1, int(0.012 * S_)))
        for side in (-1, 1):                       # 輪
            d.polygon(P(BOW_LOOP, side, 0, sh), fill=dark)
            d.polygon(P(BOW_LOOP, side), fill=fill)
            d.polygon(P(BOW_FOLD, side), fill=dark)
            d.polygon(P(BOW_SHINE, side), fill=(255, 255, 255, 120))
        kw, kh = 0.075 * S_, 0.09 * S_             # 結び目
        d.rounded_rectangle((cx - kw, cy - kh + sh, cx + kw, cy + kh + sh), radius=kw * 0.7, fill=dark)
        d.rounded_rectangle((cx - kw, cy - kh, cx + kw, cy + kh), radius=kw * 0.7, fill=knot)
        d.line([(cx - kw * 0.45, cy - kh * 0.55), (cx - kw * 0.45, cy + kh * 0.5)], fill=dark,
               width=max(1, int(0.01 * S_)))
        d.ellipse((cx - kw * 0.55, cy - kh * 0.7, cx - kw * 0.05, cy - kh * 0.3), fill=(255, 255, 255, 140))
    return sprite(s, h, f)


def sparkle_sprite(s, col=(255, 255, 255)):
    def f(d, k):
        c = s * k / 2
        r = c * 0.95
        pts = []
        for i in range(16):
            a = TAU * i / 16
            rr = r if i % 4 == 0 else r * (0.18 if i % 2 else 0.3)
            pts.append((c + rr * math.cos(a), c + rr * math.sin(a)))
        d.polygon(pts, fill=col + (255,))
    im = sprite(s, s, f)
    glow = im.filter(ImageFilter.GaussianBlur(s / 6))
    return Image.alpha_composite(glow, im)


def choco_heart_sprite(s):
    def f(d, k):
        c = s * k / 2 + 3 * k
        d.polygon(heart_pts(c, c + 3 * k, s * k), fill=CHOCO_D)
        d.polygon(heart_pts(c, c, s * k), fill=CHOCO)
        d.polygon(heart_pts(c - s * k * 0.04, c - s * k * 0.05, s * k * 0.72), fill=CHOCO_L)
        d.polygon(heart_pts(c, c, s * k * 0.66), fill=CHOCO)
        # ピンクのチョコペン
        pts = [(c - s * k * 0.3 + s * k * 0.6 * i / 20, c + s * k * 0.05 * math.sin(i * 1.3) - s * k * 0.02)
               for i in range(21)]
        d.line(pts, fill=(255, 170, 200), width=int(s * k * 0.06), joint="curve")
        d.ellipse((c - s * k * 0.3, c - s * k * 0.3, c - s * k * 0.16, c - s * k * 0.2), fill=(255, 255, 255, 150))
    return sprite(s + 6, s + 6, f)


# ---- 柄の帯 (横にタイル状につながる) ------------------------------------------------
def tile(period, height, draw_fn, bg):
    """横方向に周期 period でつながる帯を、W + period の幅で作る."""
    n = W // period + 2
    im = Image.new("RGBA", (n * period * SS, height * SS), bg + (255,))
    d = ImageDraw.Draw(im)
    for i in range(-1, n + 1):
        draw_fn(d, i * period * SS, SS)
    return im.resize((n * period, height), Image.LANCZOS)


def band_top(h):
    """ピンクのうっすらストライプ (チョコの垂れは別レイヤー)."""
    p = 60

    def f(d, x0, k):
        d.polygon([(x0, 0), (x0 + p * k * 0.5, 0), (x0 + p * k * 0.5 - h * k * 0.3, h * k), (x0 - h * k * 0.3, h * k)],
                  fill=(250, 196, 214, 255))
    return tile(p, h, f, PINK_L), p


def band_gingham(h):
    p = 64

    def f(d, x0, k):
        for yy in range(0, h * k, p * k):
            d.rectangle((x0, yy, x0 + p * k - 1, yy + p * k // 2 - 1), fill=(244, 150, 176, 255))
        d.rectangle((x0, 0, x0 + p * k // 2 - 1, h * k), fill=(240, 134, 164, 255))
        for yy in range(0, h * k, p * k):
            d.rectangle((x0, yy, x0 + p * k // 2 - 1, yy + p * k // 2 - 1), fill=(222, 64, 96, 255))
    return tile(p, h, f, (255, 226, 234)), p


def band_bows(h, bows):
    p = 150

    im = tile(p, h, lambda d, x0, k: None, PINK)
    for i in range(-1, im.width // p + 1):
        for row, (yy, off) in enumerate(((h * 0.28, 0), (h * 0.74, p / 2))):
            b = bows[(i + row) % 2]
            x = int(i * p + off + p / 2 - b.width / 2)
            if -b.width < x < im.width:
                im.alpha_composite(b, (max(x, 0), int(yy - b.height / 2)), (max(-x, 0), 0))
    return im, p


def band_chocobar(h):
    p = 120

    def f(d, x0, k):
        m = 10 * k
        for yy in (m, h * k / 2 + m / 2):
            x1, y1 = x0 + m, yy
            x2, y2 = x0 + p * k - m, yy + h * k / 2 - 1.5 * m
            d.rounded_rectangle((x1, y1, x2, y2), radius=12 * k, fill=CHOCO_D + (255,))
            d.rounded_rectangle((x1, y1, x2 - 5 * k, y2 - 5 * k), radius=12 * k, fill=CHOCO_L + (255,))
            d.rounded_rectangle((x1 + 5 * k, y1 + 5 * k, x2 - 5 * k, y2 - 5 * k), radius=10 * k, fill=CHOCO + (255,))
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            d.polygon(heart_pts(cx, cy, 34 * k), fill=CHOCO_D + (255,))
            d.polygon(heart_pts(cx - 1.5 * k, cy - 1.5 * k, 34 * k), fill=(128, 72, 56, 255))
    return tile(p, h, f, CHOCO_D), p


def band_hearts(h, hearts):
    p = 130
    im = tile(p, h, lambda d, x0, k: None, PINK_L)
    for i in range(-1, im.width // p + 1):
        for row, (yy, off) in enumerate(((h * 0.27, 0), (h * 0.73, p / 2))):
            hs = hearts[(i + row) % 2]
            x = int(i * p + off + p / 2 - hs.width / 2)
            if -hs.width < x < im.width:
                im.alpha_composite(hs, (max(x, 0), int(yy - hs.height / 2)), (max(-x, 0), 0))
    return im, p


def band_dots(h):
    p = 96

    def f(d, x0, k):
        r = 17 * k
        for yy in np.arange(p * k * 0.25, h * k + p * k, p * k * 0.5):
            row = int(round((yy - p * k * 0.25) / (p * k * 0.5)))
            off = p * k / 2 if row % 2 else 0
            cx = x0 + p * k / 2 + off
            d.ellipse((cx - r, yy - r, cx + r, yy + r), fill=(250, 150, 182, 255))
            d.ellipse((cx - r * 0.5, yy - r * 0.6, cx - r * 0.1, yy - r * 0.25), fill=(255, 205, 222, 255))
    return tile(p, h, f, HOT), p


def lace_tile():
    """白いレースの縁取り (上下スカラップ + 透かし穴 + ピンクのステッチ). 周期 60px."""
    p, h = 60, 84

    def f(d, x0, k):
        mid = h * k / 2
        d.rectangle((x0, mid - 20 * k, x0 + p * k, mid + 20 * k), fill=CREAM + (255,))
        for cx in (x0 + p * k / 4, x0 + p * k * 3 / 4):
            r = p * k / 4 + 2 * k
            d.ellipse((cx - r, mid - 20 * k - r * 0.9, cx + r, mid - 20 * k + r * 0.9), fill=CREAM + (255,))
            d.ellipse((cx - r, mid + 20 * k - r * 0.9, cx + r, mid + 20 * k + r * 0.9), fill=CREAM + (255,))
            hr = 4 * k   # 透かし穴
            d.ellipse((cx - hr, mid - 28 * k - hr, cx + hr, mid - 28 * k + hr), fill=(0, 0, 0, 0))
            d.ellipse((cx - hr, mid + 28 * k - hr, cx + hr, mid + 28 * k + hr), fill=(0, 0, 0, 0))
        # ステッチ
        d.line((x0 + 6 * k, mid, x0 + p * k / 2 - 6 * k, mid), fill=PINK_M + (255,), width=int(3.5 * k))
        d.line((x0 + p * k / 2 + 6 * k, mid, x0 + p * k - 6 * k, mid), fill=PINK_M + (255,), width=int(3.5 * k))
    im = tile(p, h, f, (0, 0, 0))
    a = np.asarray(im).copy()
    # 背景を透明に (tile は不透明背景で作るので、黒を抜く)
    black = (a[..., 0] < 8) & (a[..., 1] < 8) & (a[..., 2] < 8)
    a[black] = 0
    lace = Image.fromarray(a)
    sh = Image.new("RGBA", lace.size, (120, 40, 60, 0))
    sh.putalpha(lace.getchannel("A").point(lambda v: v * 0.35).filter(ImageFilter.GaussianBlur(4)))
    out = Image.new("RGBA", (lace.width, lace.height + 8), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 6))
    out.alpha_composite(lace, (0, 0))
    return out, p


# ---- チョコの垂れ (上端) -------------------------------------------------------------
def choco_drip(t, rng_drips, h=260):
    """上からとろ〜りと垂れるチョコ. 垂れはゆっくり伸び縮みする (10 秒周期)."""
    w1 = TAU * t / D
    ys, xs = np.mgrid[0:h, 0:W].astype(np.float32)
    base = 70 + 8 * np.sin(xs / 70 + w1) + 5 * np.sin(xs / 31 - 2 * w1)
    d = ys - base
    for (x, r, L, ph, k) in rng_drips:
        L2 = L * (0.8 + 0.2 * math.sin(k * w1 + ph))
        m = np.abs(xs - x) < r * 3
        X, Y = xs[m], ys[m]
        tip = 60 + L2
        seg = np.hypot(X - x, np.maximum(Y - tip, 0) * (Y > tip) + np.minimum(Y - 0, 0)) - r * 0.8
        neck = np.where(Y < tip, np.abs(X - x) - r * 0.8, np.hypot(X - x, Y - tip) - r * 0.8)
        bulb = np.hypot(X - x, Y - tip) - r * 1.15
        dd = np.minimum(neck, bulb)
        hh = np.clip(0.5 + 0.5 * (d[m] - dd) / 24, 0, 1)
        d[m] = d[m] * (1 - hh) + dd * hh - 24 * hh * (1 - hh)
    a = np.clip(0.5 - d, 0, 1)
    q = np.clip(-d / 22, 0, 1)
    hgt = np.sqrt(1 - (1 - q) ** 2)
    gy, gx = np.gradient(hgt * 22)
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L = np.array([-0.4, -0.6, 0.7])
    L /= np.linalg.norm(L)
    Hh = L + np.array([0, 0, 1.0])
    Hh /= np.linalg.norm(Hh)
    diff = np.clip(n @ L, 0, 1)
    spec = np.clip(n @ Hh, 0, 1) ** 60
    col = np.array(CHOCO, np.float32) / 255 * (0.5 + 0.6 * diff)[..., None] + spec[..., None] * 0.9
    rgba = np.concatenate([np.clip(col, 0, 1), a[..., None]], -1)
    im = Image.fromarray((rgba * 255).astype(np.uint8))
    sh = Image.new("RGBA", im.size, (90, 30, 40, 0))
    sh.putalpha(im.getchannel("A").point(lambda v: v * 0.3).filter(ImageFilter.GaussianBlur(6)))
    out = Image.new("RGBA", (W, h + 10), (0, 0, 0, 0))
    out.alpha_composite(sh, (0, 8))
    out.alpha_composite(im, (0, 0))
    return out


# ---- 組み立て ----------------------------------------------------------------------
class Scene:
    def __init__(self, seed=7):
        rng = random.Random(seed)
        self.rng = rng
        bows_small = [bow_sprite(84, RED + (255,), RED_D + (255,)), bow_sprite(84, (250, 120, 160, 255),
                                                                              (220, 80, 120, 255))]
        hearts_small = [heart_sprite(52, RED + (255,)), heart_sprite(52, PINK_M + (255,))]
        hts = [300, 290, 300, 270, 300, 460]
        makers = [lambda h: band_top(h), lambda h: band_gingham(h), lambda h: band_bows(h, bows_small),
                  lambda h: band_chocobar(h), lambda h: band_hearts(h, hearts_small), lambda h: band_dots(h)]
        self.bands, y = [], 0
        dirs = [1, -1, 1, -1, 1, -1]
        for h, mk, dr in zip(hts, makers, dirs):
            im, p = mk(h)
            # 10 秒で周期 p の整数倍だけ流れる (約 45px/秒) → つなぎ目なしでループ
            self.bands.append(dict(im=im, p=p, y=y, h=h, dir=dr, n=max(1, round(45 * D / p))))
            y += h
        self.lace, self.lace_p = lace_tile()
        self.seams = [sum(hts[:i + 1]) for i in range(5)]
        self.drips = [(x, rng.uniform(12, 20), rng.uniform(40, 150), rng.uniform(0, TAU), rng.choice([1, 2]))
                      for x in np.linspace(40, W - 40, 10) + np.array([rng.uniform(-30, 30) for _ in range(10)])]
        # 飾り
        self.big_bows = [(bow_sprite(230, RED + (255,), RED_D + (255,)), 820,
                          self.seams[1] + 4, 0.0),
                         (bow_sprite(190, (250, 110, 155, 255), (210, 70, 115, 255)), 210,
                          self.seams[3] + 4, 1.7),
                         (bow_sprite(200, RED + (255,), RED_D + (255,)), 640,
                          self.seams[4] + 4, 3.1)]
        self.charms = [(heart_sprite(46, RED + (255,), line=(255, 255, 255, 255)), x, self.seams[s], ph)
                       for x, s, ph in [(560, 0, 0.3), (180, 1, 1.2), (930, 2, 2.0), (400, 2, 2.6), (880, 3, 0.8),
                                        (120, 4, 1.9), (960, 4, 0.4)]]
        self.chocos = [(choco_heart_sprite(96), 300, self.seams[0] + 6, 0.5),
                       (choco_heart_sprite(84), 760, self.seams[2] + 4, 2.2)]
        cols = [(255, 255, 255, 230), (255, 214, 228, 230), (255, 160, 190, 230)]
        self.floaters = [dict(sp=heart_sprite(rng.randint(22, 50), cols[i % 3], shine=False), x=rng.uniform(40, W - 40),
                              ph=rng.random(), sw=rng.uniform(15, 40), k=rng.choice([1, 2])) for i in range(16)]
        self.sparks = [dict(sp=sparkle_sprite(rng.randint(26, 54)), x=rng.uniform(30, W - 30), y=rng.uniform(80, H - 80),
                            ph=rng.random(), k=rng.choice([2, 3])) for _ in range(22)]

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        u = t / D
        for b in self.bands:
            off = int(round(b["dir"] * b["n"] * b["p"] * u)) % b["p"]
            im.paste(b["im"].crop((off, 0, off + W, b["h"])), (0, b["y"]))
        for i, y in enumerate(self.seams):   # レースも帯の境目で左右交互に流れる
            p = self.lace_p
            off = int(round((1 if i % 2 else -1) * p * u * 6)) % p
            im.alpha_composite(self.lace.crop((off, 0, off + W, self.lace.height)), (0, y - 42))
        im.alpha_composite(choco_drip(t, self.drips), (0, 0))
        w1 = TAU * u
        for sp, x, y, ph in self.chocos:
            a = 8 * math.sin(w1 + ph)
            s = sp.rotate(a, Image.BICUBIC, expand=True)
            im.alpha_composite(s, (int(x - s.width / 2), int(y - s.height / 2 + 4 * math.sin(2 * w1 + ph))))
        for sp, x, y, ph in self.charms:
            a = 12 * math.sin(2 * w1 + ph)
            s = sp.rotate(a, Image.BICUBIC, expand=True)
            im.alpha_composite(s, (int(x - s.width / 2), int(y - s.height / 2 + 3 * math.sin(2 * w1 + ph))))
        for sp, x, y, ph in self.big_bows:
            a = 6 * math.sin(w1 + ph)
            sc = 1 + 0.04 * math.sin(2 * w1 + ph)
            s = sp.resize((int(sp.width * sc), int(sp.height * sc)), Image.BICUBIC).rotate(a, Image.BICUBIC, expand=True)
            im.alpha_composite(s, (int(x - s.width / 2), int(y - s.height * 0.42)))
        for f in self.floaters:
            v = (u * f["k"] + f["ph"]) % 1
            y = H + 60 - (H + 120) * v
            x = f["x"] + f["sw"] * math.sin(TAU * (v * 2 + f["ph"]))
            sp = f["sp"].copy()
            alpha = min(1, v / 0.1, (1 - v) / 0.15)
            sp.putalpha(sp.getchannel("A").point(lambda q: q * alpha * 0.85))
            im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))
        for s in self.sparks:
            v = (u * s["k"] + s["ph"]) % 1
            if v > 0.5:
                continue
            e = math.sin(math.pi * v / 0.5) ** 2
            size = max(2, int(s["sp"].width * e))
            sp = s["sp"].resize((size, size), Image.BICUBIC)
            im.alpha_composite(sp, (int(s["x"] - size / 2), int(s["y"] - size / 2)))
        return im.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="stripe_bg.mp4")
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    sc = Scene()
    if a.preview:
        for t in a.preview:
            sc.frame(t).save(a.out.rsplit(".", 1)[0] + f"_{t:.2f}.png")
        return
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                          "-crf", "17", "-preset", "slow", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    for i in range(D * FPS):
        p.stdin.write(sc.frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()


if __name__ == "__main__":
    main()
