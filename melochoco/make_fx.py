"""3Dのお菓子・チョコの動画に重ねて使う、汎用エフェクト素材 (背景透過 / グリーンバック) を書き出す.

  pip install numpy pillow
  python3 make_fx.py --out fx_out            # 全部
  python3 make_fx.py --out fx_out sparkle    # 名前を指定して一部だけ
  python3 make_fx.py --out fx_out --sheet    # 確認用のコンタクトシートだけ

1エフェクトにつき次の3つを出力する (1920x1080 / 30fps)
- <name>.mov            ProRes 4444 (アルファ付き)。編集ソフト向け
- <name>.webm           VP9 (アルファ付き)。軽い透過版
- <name>_greenback.mp4  H.264 のグリーンバック (#00FF00)
"loop" と書いたものは最後と最初がつながるので、繰り返し並べて長くできる.
全部 numpy の SDF (距離関数) で描いているので、乱数の seed を変えれば別パターンも作れる.
"""
import argparse
import math
import os
import subprocess
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw

W, H, FPS = 1920, 1080, 30
TAU = 2 * math.pi
GREEN = np.array([0.0, 1.0, 0.0], np.float32)


def clip01(u):
    return np.clip(u, 0.0, 1.0)


def ease_out(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def ease_out_back(u, s=1.7):
    u = min(max(u, 0.0), 1.0)
    return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2


def rgb(c):
    return np.array(c, np.float32) / 255.0


class Frame:
    """乗算済みアルファの float キャンバス. over() で小さな矩形ごとに重ねていく."""

    def __init__(self):
        self.px = np.zeros((H, W, 4), np.float32)

    def grid(self, cx, cy, rad):
        """(cx, cy) 中心・半径 rad の範囲の画素座標. 画面外なら None."""
        x0, x1 = max(int(cx - rad), 0), min(int(cx + rad) + 2, W)
        y0, y1 = max(int(cy - rad), 0), min(int(cy + rad) + 2, H)
        if x0 >= x1 or y0 >= y1:
            return None
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        return x0, y0, xs + 0.5 - cx, ys + 0.5 - cy

    def over(self, x0, y0, color, alpha):
        h, w = alpha.shape
        dst = self.px[y0:y0 + h, x0:x0 + w]
        a = alpha[..., None]
        col = color if np.ndim(color) == 3 else np.broadcast_to(color, (h, w, 3))
        dst[..., :3] = col * a + dst[..., :3] * (1 - a)
        dst[..., 3:] = a + dst[..., 3:] * (1 - a)

    def straight_rgba(self):
        a = self.px[..., 3:]
        c = np.where(a > 1e-4, self.px[..., :3] / np.maximum(a, 1e-4), 0)
        out = np.concatenate([c, a], -1)
        return (clip01(out) * 255 + 0.5).astype(np.uint8)

    def on(self, bg):
        """背景 (H, W, 3) float に合成した RGB uint8."""
        out = self.px[..., :3] + bg * (1 - self.px[..., 3:])
        return (clip01(out) * 255 + 0.5).astype(np.uint8)


# ---------------------------------------------------------------- 形 (SDF)

def sd_segment(x, y, ax, ay, bx, by):
    pax, pay, bax, bay = x - ax, y - ay, bx - ax, by - ay
    h = clip01((pax * bax + pay * bay) / max(bax * bax + bay * bay, 1e-6))
    return np.hypot(pax - bax * h, pay - bay * h)


def sd_heart(x, y):
    """Inigo Quilez のハートの距離関数. y 上向き, 先端が (0,0), 高さ約 1.1."""
    x = np.abs(x)
    upper = np.hypot(x - 0.25, y - 0.75) - math.sqrt(2) / 4
    m = 0.5 * np.maximum(x + y, 0)
    lower = np.sqrt(np.minimum(x * x + (y - 1) ** 2, (x - m) ** 2 + (y - m) ** 2)) * np.sign(x - y)
    return np.where(x + y > 1, upper, lower)


def smin(a, b, k):
    h = clip01(0.5 + 0.5 * (b - a) / k)
    return b + (a - b) * h - k * h * (1 - h)


def rot(X, Y, ang):
    c, s = math.cos(ang), math.sin(ang)
    return X * c + Y * s, -X * s + Y * c


# ---------------------------------------------------------------- パーツ

WHITE = rgb((255, 255, 255))


def draw_sparkle(F, cx, cy, size, ang, tint, alpha=1.0):
    """4本の光条 + 斜めの短い光条 + 芯とハロー のキラッ."""
    if size < 1 or alpha <= 0:
        return
    g = F.grid(cx, cy, size)
    if g is None:
        return
    x0, y0, X, Y = g
    u, v = rot(X / size, Y / size, ang)

    def rays(p, q, w):
        t = clip01(1 - np.abs(p))
        return np.exp(-(q / (w * t ** 1.5 + 1e-4)) ** 2) * t

    d1, d2 = (u + v) * 1.414, (u - v) * 1.414   # 斜めは長さ半分
    ray = np.maximum.reduce([rays(u, v, 0.075), rays(v, u, 0.075),
                             0.7 * rays(d1, d2, 0.09), 0.7 * rays(d2, d1, 0.09)])
    r = np.hypot(u, v)
    core = np.exp(-(r / 0.11) ** 2)
    halo = 0.35 * np.exp(-(r / 0.33) ** 2)
    a = clip01(ray + core + halo) * alpha
    wt = clip01(ray * 0.9 + core)[..., None]
    F.over(x0, y0, tint * (1 - wt) + WHITE * wt, a)


def draw_heart(F, cx, cy, size, ang, color, alpha=1.0):
    """ぷっくりした立体風ハート. size は横幅の目安 (px)."""
    s = size / 1.2
    g = F.grid(cx, cy, s * 0.75)
    if g is None:
        return
    x0, y0, X, Y = g
    u, v = rot(X, Y, ang)
    hx, hy = u / s, -v / s + 0.55
    d = sd_heart(hx, hy) * s
    a = clip01(0.5 - d) * alpha
    depth = clip01(-d / (s * 0.22))
    shade = (0.68 + 0.32 * np.sqrt(depth)) * (1 + 0.15 * (hy - 0.55))
    hl = 0.9 * np.exp(-(((hx + 0.24) / 0.1) ** 2 + ((hy - 0.8) / 0.065) ** 2))
    hl += 0.35 * np.exp(-(((hx - 0.3) / 0.05) ** 2 + ((hy - 0.86) / 0.04) ** 2))
    col = color * shade[..., None]
    col = col * (1 - hl[..., None]) + hl[..., None]
    F.over(x0, y0, col, a)


def draw_capsule(F, cx, cy, length, rad, ang, color, alpha=1.0):
    """カラースプレー (丸い棒). 断面方向に陰影とツヤ."""
    g = F.grid(cx, cy, length / 2 + rad + 1)
    if g is None:
        return
    x0, y0, X, Y = g
    u, v = rot(X, Y, ang)
    hl = length / 2
    d = np.hypot(u - np.clip(u, -hl, hl), v) - rad
    a = clip01(0.5 - d) * alpha
    n = np.clip(v / rad, -1, 1)
    shade = 0.78 - 0.25 * n
    gloss = 0.7 * np.exp(-((n + 0.45) / 0.2) ** 2)
    col = color * shade[..., None]
    col = col * (1 - gloss[..., None]) + gloss[..., None]
    F.over(x0, y0, col, a)


def draw_paper(F, cx, cy, w, h, ang, flip, color, round_=False, alpha=1.0):
    """紙吹雪. flip は紙の裏返り (cos で縦幅がつぶれて暗くなる)."""
    k = math.cos(flip)
    hh = max(abs(k) * h / 2, 0.6)
    g = F.grid(cx, cy, max(w, h) / 2 + 2)
    if g is None:
        return
    x0, y0, X, Y = g
    u, v = rot(X, Y, ang)
    if round_:
        d = (np.hypot(u / (w / 2), v / hh) - 1) * min(w / 2, hh)
    else:
        qx, qy = np.abs(u) - w / 2, np.abs(v) - hh
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)
    a = clip01(0.5 - d) * alpha
    shade = 0.6 + 0.4 * abs(k) + (0.15 if k < 0 else 0)
    F.over(x0, y0, np.clip(color * shade, 0, 1), a)


def draw_blob(F, cx, cy, sigma, color, alpha):
    g = F.grid(cx, cy, sigma * 3)
    if g is None:
        return
    x0, y0, X, Y = g
    F.over(x0, y0, color, np.exp(-(X * X + Y * Y) / (2 * sigma * sigma)) * alpha)


def away_from_center(rng, n, keep=0.2, rx=0.27, ry=0.33, margin=40):
    """画面中央 (主役のお菓子が来る所) を避けがちに散らばる座標."""
    pts = []
    while len(pts) < n:
        x, y = rng.uniform(margin, W - margin), rng.uniform(margin, H - margin)
        inside = ((x - W / 2) / (W * rx)) ** 2 + ((y - H / 2) / (H * ry)) ** 2 < 1
        if not inside or rng.random() < keep:
            pts.append((x, y))
    return pts


PASTEL = [rgb(c) for c in [(255, 170, 200), (255, 105, 160), (255, 255, 255), (255, 214, 120),
                           (160, 230, 205), (200, 175, 245), (130, 200, 245), (120, 70, 45)]]


# ---------------------------------------------------------------- 1. キラキラ (loop)

def setup_sparkle(rng, D):
    pts = away_from_center(rng, 56)
    tints = [rgb((255, 225, 150)), rgb((255, 190, 220)), rgb((255, 250, 235)), rgb((200, 225, 255))]
    ps = []
    for i, (x, y) in enumerate(pts):
        k = int(rng.choice([2, 3, 4]))
        alts = [(x, y)] + [(x + rng.normal(0, 80), y + rng.normal(0, 60)) for _ in range(k - 1)]
        ps.append(dict(k=k, ph=rng.random(), pos=alts, size=rng.uniform(55, 150) * (0.6 if i % 3 else 1),
                       tint=tints[i % 4], ang=rng.uniform(-0.3, 0.3)))
    return ps


def fx_sparkle(F, t, P, D):
    for p in P:
        c = t / D * p["k"] + p["ph"]
        idx, u = int(c) % p["k"], c % 1
        if u > 0.7:
            continue
        e = math.sin(math.pi * u / 0.7) ** 2
        x, y = p["pos"][idx]
        draw_sparkle(F, x, y, p["size"] * e, p["ang"] + 0.5 * u, p["tint"], min(1, e * 1.4))


# ---------------------------------------------------------------- 2. カラースプレーが降る (loop)

def setup_sprinkles(rng, D):
    cols = [rgb(c) for c in [(255, 140, 180), (255, 255, 255), (255, 220, 110), (150, 225, 200),
                             (180, 160, 240), (110, 190, 245), (110, 60, 40), (255, 95, 120)]]
    ps = []
    for i in range(110):
        z = rng.random()
        ps.append(dict(x=rng.uniform(0, W), k=1 + (z > 0.45), ph=rng.random(), z=z,
                       len=12 + 22 * z, rad=3 + 3.2 * z, a0=rng.uniform(0, TAU),
                       spin=int(rng.choice([-2, -1, 1, 2])), sway=rng.uniform(5, 25),
                       col=cols[i % len(cols)]))
    ps.sort(key=lambda p: p["z"])
    return ps


def fx_sprinkles(F, t, P, D):
    for p in P:
        f = (t / D * p["k"] + p["ph"]) % 1
        y = -50 + (H + 100) * f
        x = p["x"] + p["sway"] * math.sin(TAU * (f * 2 + p["ph"]))
        ang = p["a0"] + TAU * p["spin"] * t / D
        draw_capsule(F, x, y, p["len"], p["rad"], ang, p["col"])


# ---------------------------------------------------------------- 3. ハートがふわふわ上る (loop)

def setup_hearts(rng, D):
    cols = [rgb(c) for c in [(255, 120, 170), (255, 70, 120), (255, 175, 205), (235, 40, 80), (255, 215, 230)]]
    ps = []
    for i in range(30):
        z = rng.random()
        ps.append(dict(x=rng.uniform(60, W - 60), k=1 + (z > 0.5), ph=rng.random(), z=z,
                       size=24 + 70 * z ** 1.3, sway=rng.uniform(20, 70), j=int(rng.choice([1, 2])),
                       ph2=rng.random(), col=cols[i % len(cols)]))
    ps.sort(key=lambda p: p["z"])
    return ps


def fx_hearts(F, t, P, D):
    for p in P:
        f = (t / D * p["k"] + p["ph"]) % 1
        y = H + 80 - (H + 160) * f
        w = TAU * (p["j"] * t / D * p["k"] + p["ph2"])
        x = p["x"] + p["sway"] * math.sin(w)
        a = min(1, (1 - f) / 0.15)
        draw_heart(F, x, y, p["size"], 0.25 * math.cos(w), p["col"], a)


# ---------------------------------------------------------------- 4. 紙吹雪 (クラッカー)

def setup_confetti(rng, D):
    ps = []
    for side in (-1, 1):
        for i in range(140):
            ang = math.radians(rng.uniform(8, 42))    # 垂直からの傾き (画面の内側へ)
            sp = rng.uniform(1300, 2700)
            ps.append(dict(x0=W / 2 + side * (W / 2 + 10), y0=H + 20, vx=-side * math.sin(ang) * sp,
                           vy=-math.cos(ang) * sp, t0=0.15 + rng.uniform(0, 0.12),
                           tau=rng.uniform(0.45, 0.65), vt=rng.uniform(230, 420),
                           w=rng.uniform(14, 28), h=rng.uniform(8, 15), round_=rng.random() < 0.25,
                           spin=rng.uniform(-6, 6), flip=rng.uniform(5, 14), ph=rng.uniform(0, TAU),
                           flut=rng.uniform(15, 45), fw=rng.uniform(2.5, 5), col=PASTEL[int(rng.integers(len(PASTEL)))]))
    return ps


def fx_confetti(F, t, P, D):
    for p in P:
        s = t - p["t0"]
        if s < 0:
            continue
        e = 1 - math.exp(-s / p["tau"])
        x = p["x0"] + p["vx"] * p["tau"] * e + p["flut"] * math.sin(p["fw"] * s + p["ph"]) * e
        y = p["y0"] + p["vt"] * s + (p["vy"] - p["vt"]) * p["tau"] * e
        if y > H + 40 and s > 1:
            continue
        draw_paper(F, x, y, p["w"], p["h"], p["ph"] + p["spin"] * s, p["ph"] + p["flip"] * s,
                   p["col"], p["round_"])


# ---------------------------------------------------------------- 5. 湯気 (loop)

SC = 4  # 湯気は 1/4 解像度で計算して拡大


def setup_steam(rng, D):
    return [dict(ph=rng.random(), x=rng.normal(0, 80), drift=rng.uniform(-90, 90),
                 sw=rng.uniform(20, 60), ph2=rng.uniform(0, TAU), r=rng.uniform(0.8, 1.2))
            for _ in range(60)]


def fx_steam(F, t, P, D):
    h, w = H // SC, W // SC
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) * SC
    w1, w2 = TAU * 2 * t / D, TAU * 3 * t / D
    xs = xs + (40 * np.sin(ys / 75 + w1) + 16 * np.sin(ys / 29 - w2)) * (1.2 - ys / H)
    dens = np.zeros((h, w), np.float32)
    for p in P:
        life = (t / D * 2 + p["ph"]) % 1
        cy = H * 0.95 - life * H * 0.62
        cx = W / 2 + p["x"] + p["drift"] * life + p["sw"] * math.sin(TAU * life * 1.3 + p["ph2"]) * life
        r = (18 + 85 * life) * p["r"]
        env = math.sin(math.pi * life) ** 1.6
        dens += env * np.exp(-((xs - cx) ** 2 + ((ys - cy) * 0.75) ** 2) / (2 * r * r))
    a = (1 - np.exp(-dens * 0.35)) * 0.5
    big = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
    F.over(0, 0, rgb((255, 252, 248)), big)


# ---------------------------------------------------------------- 6. 粉砂糖 (loop)

def setup_sugar(rng, D):
    ps = []
    for _ in range(300):
        z = rng.random() ** 1.5
        ps.append(dict(x=rng.uniform(0, W), ph=rng.random(), z=z, k=1 + (z > 0.55),
                       sig=0.9 + 6 * z ** 2, a=0.95 - 0.55 * z, sw=rng.uniform(10, 50),
                       j=int(rng.choice([1, 2])), ph2=rng.random()))
    return ps


def fx_sugar(F, t, P, D):
    col = rgb((255, 252, 246))
    for p in P:
        f = (t / D * p["k"] + p["ph"]) % 1
        y = -30 + (H + 60) * f
        x = p["x"] + p["sw"] * math.sin(TAU * (p["j"] * t / D + p["ph2"]))
        draw_blob(F, x, y, p["sig"], col, p["a"])


# ---------------------------------------------------------------- 7. 光のスイープ (ツヤ出し)

def fx_shine(F, t, P, D):
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    th = math.radians(22)
    s = xs * math.cos(th) + ys * math.sin(th)
    span = W * math.cos(th) + H * math.sin(th)
    a = np.zeros((H, W), np.float32)
    for t0, dur, wid, amp in [(0.6, 1.3, 120, 0.55), (3.0, 0.9, 50, 0.4)]:
        u = (t - t0) / dur
        if not 0 <= u <= 1:
            continue
        c = -300 + (span + 600) * (u * u * (3 - 2 * u))
        a += amp * np.exp(-((s - c) / wid) ** 2) + amp * 0.8 * np.exp(-((s - c - wid * 0.9) / (wid * 0.18)) ** 2)
    if a.max() > 0:
        F.over(0, 0, WHITE, clip01(a))


# ---------------------------------------------------------------- 8. 登場ポン!

def setup_pop(rng, D):
    parts = []
    for i in range(34):
        ang = TAU * i / 34 + rng.uniform(-0.1, 0.1)
        parts.append(dict(ang=ang, sp=rng.uniform(900, 1800), kind=i % 3, size=rng.uniform(22, 46),
                          col=[rgb((255, 120, 170)), rgb((255, 215, 120)), rgb((255, 190, 215))][i % 3],
                          spin=rng.uniform(-5, 5)))
    twk = [dict(ang=rng.uniform(0, TAU), r=rng.uniform(250, 430), t0=0.6 + 0.22 * i,
                size=rng.uniform(45, 85)) for i in range(9)]
    return dict(parts=parts, twk=twk)


def fx_pop(F, t, P, D):
    cx, cy, T0 = W / 2, H / 2, 0.25
    s = t - T0
    if s < 0:
        return
    # 白い閃光
    u = s / 0.35
    if u < 1:
        draw_blob(F, cx, cy, 80 + 160 * ease_out(u), rgb((255, 245, 250)), 0.9 * (1 - u) ** 2)
    # 広がるリング (ピンク → 金)
    for dt, col, wd in [(0, rgb((255, 140, 185)), 26), (0.1, rgb((255, 215, 120)), 12)]:
        u = (s - dt) / 0.6
        if 0 <= u < 1:
            r = 90 + 520 * ease_out(u)
            g = F.grid(cx, cy, r + wd)
            x0, y0, X, Y = g
            d = np.abs(np.hypot(X, Y) - r) - (wd * (1 - u) + 2) / 2
            F.over(x0, y0, col, clip01(0.5 - d) * (1 - u ** 2))
    # 集中線
    for i in range(14):
        ang = TAU * i / 14 + 0.11
        ro = 170 + 470 * ease_out(s / 0.45)
        ri = 170 + 470 * ease_out((s - 0.1) / 0.45)
        if ro - ri < 1:
            continue
        col = [rgb((255, 120, 170)), rgb((255, 215, 120)), WHITE][i % 3]
        ax, ay = cx + math.cos(ang) * ri, cy + math.sin(ang) * ri
        bx, by = cx + math.cos(ang) * ro, cy + math.sin(ang) * ro
        mx, my = (ax + bx) / 2, (ay + by) / 2
        g = F.grid(mx, my, (ro - ri) / 2 + 10)
        if g is None:
            continue
        x0, y0, X, Y = g
        d = sd_segment(X + mx, Y + my, ax, ay, bx, by) - 6
        F.over(x0, y0, col, clip01(0.5 - d))
    # 飛び散るハート・星・粒
    for p in P["parts"]:
        u = s / 1.4
        if u >= 1:
            continue
        e = 1 - math.exp(-s / 0.3)
        dist = 120 + p["sp"] * 0.3 * e
        x = cx + math.cos(p["ang"]) * dist
        y = cy + math.sin(p["ang"]) * dist + 160 * s * s
        k = (1 - u) ** 0.6 * ease_out_back(s / 0.15)
        if p["kind"] == 0:
            draw_heart(F, x, y, p["size"] * k, p["spin"] * s * 0.3, p["col"])
        elif p["kind"] == 1:
            draw_sparkle(F, x, y, p["size"] * 1.4 * k, p["spin"] * s, p["col"])
        else:
            draw_blob(F, x, y, p["size"] * 0.22 * k, p["col"], 1.0)
    # 余韻のキラキラ
    for q in P["twk"]:
        for rep in range(2):
            u = (s - q["t0"] - rep * 1.6) / 0.9
            if 0 <= u < 1:
                e = math.sin(math.pi * u) ** 2
                draw_sparkle(F, cx + math.cos(q["ang"]) * q["r"], cy + math.sin(q["ang"]) * q["r"] * 0.8,
                             q["size"] * e, u * 0.6, rgb((255, 225, 160)), e)


# ---------------------------------------------------------------- 9/10. チョコが垂れてくる

def setup_drip(rng, D):
    xs = np.linspace(40, W - 40, 15) + rng.uniform(-40, 40, 15)
    return [dict(x=float(x), r=rng.uniform(13, 26), L=rng.uniform(40, 380), t0=rng.uniform(0.35, 1.6),
                 dur=rng.uniform(1.6, 3.2)) for x in xs]


def drip_frame(F, t, P, base):
    h0 = 95
    shift = -(h0 + 60) * (1 - ease_out(t / 0.7))
    ymax = int(min(H, h0 + 30 + max(p["L"] for p in P) * 1.15 + 60))
    ys, xs = np.mgrid[0:ymax, 0:W].astype(np.float32)
    ys = ys - shift
    edge = h0 + 10 * np.sin(xs / 90 + 1) + 6 * np.sin(xs / 37 + 2)
    d = ys - edge
    for p in P:
        u = (t - p["t0"]) / p["dur"]
        if u <= 0:
            continue
        L = p["L"] * ease_out(u) + 10 * max(0.0, t - p["t0"] - p["dur"])
        r = p["r"]
        x0, x1 = int(p["x"] - r * 3), int(p["x"] + r * 3)
        sl = (slice(None), slice(max(x0, 0), min(x1, W)))
        X, Y = xs[sl], ys[sl]
        tip = h0 + L
        neck = sd_segment(X, Y, p["x"], 0, p["x"], tip) - r * (0.85 + 0.08 * math.sin(t * 3 + p["x"]))
        bulb = np.hypot(X - p["x"], Y - tip) - r * 1.2 * min(1, u * 3)
        dd = smin(neck, bulb, 10)
        d[sl] = smin(d[sl], dd, 26)
    a = clip01(0.5 - d)
    # 断面が丸い盛り上がりとみなして法線を作り、ツヤを出す
    R = 34.0
    q = clip01(-d / R)
    hgt = np.sqrt(1 - (1 - q) ** 2) * R
    gy, gx = np.gradient(hgt)
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    L_ = np.array([-0.45, -0.65, 0.62], np.float32)
    L_ /= np.linalg.norm(L_)
    Hv = L_ + np.array([0, 0, 1], np.float32)
    Hv /= np.linalg.norm(Hv)
    diff = clip01(n @ L_)
    nh = clip01(n @ Hv)
    spec = nh ** 70 * 0.95 + nh ** 10 * 0.12
    col = base * (0.42 + 0.7 * diff)[..., None] + spec[..., None]
    F.over(0, 0, np.clip(col, 0, 1), a)


def fx_drip_choco(F, t, P, D):
    drip_frame(F, t, P, rgb((112, 62, 36)))


def fx_drip_berry(F, t, P, D):
    drip_frame(F, t, P, rgb((240, 128, 165)))


# ---------------------------------------------------------------- 11. 白いオーロラ (loop)

def setup_aurora(rng, D):
    return [dict(yb=yb, a1=rng.uniform(70, 120), l1=rng.uniform(280, 420), n1=int(rng.choice([1, -1])),
                 a2=rng.uniform(20, 40), l2=rng.uniform(110, 170), n2=int(rng.choice([2, -2])),
                 p=rng.uniform(0, TAU, 4), up=up, amp=amp)
            for yb, up, amp in [(0.3, 120, 0.8), (0.56, 95, 0.6), (0.8, 75, 0.45)]]


def fx_aurora(F, t, P, D):
    h, w = H // SC, W // SC
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) * SC
    w1 = TAU * t / D
    # ふわっとさせるためのゆらぎ
    xs = xs + 35 * np.sin(ys / 95 + 2 * w1) + 15 * np.sin(ys / 41 - 3 * w1)
    x1 = xs[0]
    inten = np.zeros((h, w), np.float32)
    for b in P:
        p = b["p"]
        yc = (b["yb"] * H + b["a1"] * np.sin(x1 / b["l1"] + b["n1"] * w1 + p[0])
              + b["a2"] * np.sin(x1 / b["l2"] + b["n2"] * w1 + p[1]))
        d = yc[None, :] - ys
        prof = np.where(d > 0, np.exp(-(np.maximum(d, 0) / b["up"]) ** 1.6), np.exp(-(d / 30) ** 2))
        rays = 0.85 + 0.15 * np.sin(xs / 55 + w1 + 2.5 * np.sin(xs / 160 - w1 + p[2]))
        along = 0.15 + 0.85 * (0.5 + 0.5 * np.sin(xs / W * math.pi * 2.2 - w1 + p[3])) ** 2
        inten += b["amp"] * prof * rays * along
    a = (1 - np.exp(-inten * 2.0)) * 0.9
    big = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255
    F.over(0, 0, rgb((255, 255, 255)), big)


# ---------------------------------------------------------------- 12〜14. ライトリーク・ボケ玉 (loop)
# 光は足し算で重ねて最後に 1-exp(-x) で丸め、アルファ = RGB の最大値にする.
# 黒背景版にスクリーン/加算合成すると、レンズに光が入ったような見え方になる.

def light_to_frame(F, L):
    light = 1 - np.exp(-L)
    F.px[..., :3] = light
    F.px[..., 3] = light.max(-1)


LEAK_COLS = [rgb(c) for c in [(255, 110, 25), (255, 60, 120), (255, 170, 40), (255, 80, 60), (240, 90, 200)]]


def setup_leak(rng, D):
    blobs = []
    for i in range(7):
        side = i % 2   # 左右の端から差し込む
        blobs.append(dict(x=(-0.05 + 0.18 * rng.random()) if side == 0 else (1.05 - 0.18 * rng.random()),
                          y=rng.uniform(0.0, 1.0), r=rng.uniform(0.15, 0.32), ax=rng.uniform(0.03, 0.1),
                          ay=rng.uniform(0.05, 0.15), n=int(rng.choice([1, -1])), ph=rng.uniform(0, TAU),
                          fl=int(rng.choice([1, 2, 3])), ph2=rng.uniform(0, TAU),
                          amp=rng.uniform(1.6, 3.0), col=LEAK_COLS[i % len(LEAK_COLS)]))
    return blobs


def leak_light(t, P, D):
    h, w = H // SC, W // SC
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    xs, ys = xs / w, ys / h * (H / W)
    L = np.zeros((h, w, 3), np.float32)
    w1 = TAU * t / D
    for b in P:
        cx = b["x"] + b["ax"] * math.cos(b["n"] * w1 + b["ph"])
        cy = (b["y"] + b["ay"] * math.sin(b["n"] * w1 + b["ph"])) * H / W
        k = b["amp"] * (0.5 + 0.5 * math.sin(b["fl"] * w1 + b["ph2"])) ** 1.5
        g = np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * (b["r"] * 0.5) ** 2))
        L += k * g[..., None] * b["col"]
    # 斜めに走る光の筋
    s = (xs * 0.94 + ys * 0.34)
    c = 0.5 + 0.35 * math.sin(w1)
    L += (0.9 * (0.5 + 0.5 * math.sin(2 * w1)) ** 2 * np.exp(-((s - c) / 0.05) ** 2))[..., None] * P[0].get("streak", rgb((255, 190, 130)))
    out = np.empty((H, W, 3), np.float32)
    for ch in range(3):
        im = Image.fromarray(L[..., ch].astype(np.float32))
        out[..., ch] = np.asarray(im.resize((W, H), Image.BICUBIC))
    return np.maximum(out, 0)


def setup_bokeh(rng, D):
    cols = [rgb(c) for c in [(255, 250, 240), (255, 200, 120), (255, 150, 190), (255, 185, 90), (220, 225, 255)]]
    ps = []
    for i in range(42):
        z = rng.random()
        ps.append(dict(x=rng.uniform(0, W), y=rng.uniform(0, H), r=18 + 110 * z ** 1.5, z=z,
                       k=int(rng.choice([1, 2])), ph=rng.random(), dx=rng.uniform(-60, 60),
                       dy=rng.uniform(-140, -40), amp=rng.uniform(0.6, 1.3) * (1.2 - 0.5 * z),
                       col=cols[i % len(cols)]))
    return ps


def bokeh_light(t, P, D, L):
    for p in P:
        f = (t / D * p["k"] + p["ph"]) % 1
        env = math.sin(math.pi * f) ** 2
        cx = p["x"] + p["dx"] * (f - 0.5) * 2
        cy = p["y"] + p["dy"] * (f - 0.5) * 2
        r = p["r"]
        x0, x1 = max(int(cx - r - 3), 0), min(int(cx + r + 4), W)
        y0, y1 = max(int(cy - r - 3), 0), min(int(cy + r + 4), H)
        if x0 >= x1 or y0 >= y1:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        d = np.hypot(xs + 0.5 - cx, ys + 0.5 - cy) / r
        soft = 0.04 + 0.12 * p["z"]    # 大きい玉ほどフチがぼける
        disc = clip01((1 - d) / soft)
        ring = np.exp(-((d - 0.93) / (0.06 + soft * 0.5)) ** 2) * 0.6
        v = (disc * (0.55 + 0.15 * d) + ring * disc.clip(0.3)) * p["amp"] * env
        L[y0:y1, x0:x1] += v[..., None] * p["col"]
    return L


def fx_lightleak(F, t, P, D):
    light_to_frame(F, leak_light(t, P, D))


def fx_bokeh(F, t, P, D):
    light_to_frame(F, bokeh_light(t, P, D, np.zeros((H, W, 3), np.float32)))


def fx_leak_bokeh(F, t, P, D):
    L = leak_light(t, P["leak"], D) * 0.8
    light_to_frame(F, bokeh_light(t, P["bokeh"], D, L))


def setup_leak_bokeh(rng, D):
    return dict(leak=setup_leak(rng, D), bokeh=setup_bokeh(rng, D)[:30])


def whiten(ps, rng):
    """色を白 (ほんのり暖色/寒色のゆらぎだけ) に置き換える."""
    whites = [rgb(c) for c in [(255, 255, 255), (255, 250, 242), (246, 250, 255)]]
    for i, p in enumerate(ps):
        p["col"] = whites[i % 3]
    return ps


def setup_leak_white(rng, D):
    ps = whiten(setup_leak(rng, D), rng)
    for p in ps:
        p["amp"] *= 0.55    # 白は色より明るく見えるので控えめに
    ps[0]["streak"] = WHITE
    return ps


def setup_bokeh_white(rng, D):
    return whiten(setup_bokeh(rng, D), rng)


def setup_leak_bokeh_white(rng, D):
    P = setup_leak_bokeh(rng, D)
    whiten(P["leak"], rng)
    for p in P["leak"]:
        p["amp"] *= 0.55
    P["leak"][0]["streak"] = WHITE
    whiten(P["bokeh"], rng)
    return P


# ---------------------------------------------------------------- 一覧

# name: (秒数, 描画関数, セットアップ関数, seed, loop か)
EFFECTS = {
    "sparkle":     (8, fx_sparkle, setup_sparkle, 1, True),
    "sprinkles":   (8, fx_sprinkles, setup_sprinkles, 2, True),
    "hearts":      (8, fx_hearts, setup_hearts, 3, True),
    "confetti":    (7, fx_confetti, setup_confetti, 4, False),
    "steam":       (8, fx_steam, setup_steam, 5, True),
    "sugar":       (10, fx_sugar, setup_sugar, 6, True),
    "shine":       (5, fx_shine, None, 0, False),
    "pop":         (5, fx_pop, setup_pop, 8, False),
    "drip_choco":  (6, fx_drip_choco, setup_drip, 9, False),
    "drip_berry":  (6, fx_drip_berry, setup_drip, 10, False),
    "aurora":      (10, fx_aurora, setup_aurora, 11, True),
    "lightleak":   (8, fx_lightleak, setup_leak, 12, True),
    "bokeh":       (8, fx_bokeh, setup_bokeh, 13, True),
    "leak_bokeh":  (8, fx_leak_bokeh, setup_leak_bokeh, 14, True),
    "lightleak_white":  (8, fx_lightleak, setup_leak_white, 12, True),
    "bokeh_white":      (8, fx_bokeh, setup_bokeh_white, 13, True),
    "leak_bokeh_white": (8, fx_leak_bokeh, setup_leak_bokeh_white, 14, True),
}

# 光りもの. スクリーン/加算合成用の黒背景版 (<name>_blackback.mp4) も書き出す
GLOW = {"sparkle", "steam", "shine", "aurora", "lightleak", "bokeh", "leak_bokeh",
        "lightleak_white", "bokeh_white", "leak_bokeh_white"}
BLACK = np.zeros(3, np.float32)

_cache = {}


def params(name):
    if name not in _cache:
        D, _, setup, seed, _ = EFFECTS[name]
        _cache[name] = setup(np.random.default_rng(seed), D) if setup else None
    return _cache[name]


def render(name, t):
    D, fn, _, _, _ = EFFECTS[name]
    F = Frame()
    fn(F, t, params(name), D)
    return F


def demo_bg(w=W, h=H):
    """プレビュー用の背景 (ピンクのグラデ + 中央に仮のお菓子の円)."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    top, bot = rgb((255, 228, 236)), rgb((246, 190, 210))
    bg = top + (bot - top) * (ys / h)[..., None]
    d = np.hypot(xs - w / 2, (ys - h / 2) * 1.15) - h * 0.2
    bg = np.where((d < 0)[..., None], rgb((95, 52, 32)) * (1 - 0.3 * ys[..., None] / h), bg)
    return bg.astype(np.float32)


def _job(arg):
    name, i = arg
    F = render(name, i / FPS)
    return (F.straight_rgba().tobytes(), F.on(GREEN).tobytes(), F.on(DEMO).tobytes(),
            F.on(BLACK).tobytes() if name in GLOW else None)


DEMO = demo_bg()


def ff(args, out):
    return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", *args, out], stdin=subprocess.PIPE)


def export(name, out, pool):
    D = EFFECTS[name][0]
    raw = ["-f", "rawvideo", "-s", f"{W}x{H}", "-r", str(FPS)]
    p_mov = ff([*raw, "-pix_fmt", "rgba", "-i", "-", "-c:v", "prores_ks", "-profile:v", "4444",
                "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", "-vendor", "apl0"], f"{out}/{name}.mov")
    p_webm = ff([*raw, "-pix_fmt", "rgba", "-i", "-", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                 "-b:v", "0", "-crf", "28", "-row-mt", "1", "-auto-alt-ref", "0"], f"{out}/{name}.webm")
    h264 = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-movflags", "+faststart"]
    p_gb = ff([*raw, "-pix_fmt", "rgb24", "-i", "-", *h264], f"{out}/{name}_greenback.mp4")
    p_dm = ff([*raw, "-pix_fmt", "rgb24", "-i", "-", "-vf", "scale=960:540", *h264],
              f"{out}/demo_{name}.mp4")
    procs = [p_mov, p_webm, p_gb, p_dm]
    if name in GLOW:
        procs.append(ff([*raw, "-pix_fmt", "rgb24", "-i", "-", *h264], f"{out}/{name}_blackback.mp4"))
    for frames in pool.imap(_job, [(name, i) for i in range(D * FPS)], chunksize=2):
        for p, buf in zip(procs, (frames[0], *frames)):
            p.stdin.write(buf)
    for p in procs:
        p.stdin.close()
        p.wait()


def contact_sheet(names, path):
    tw, th = 640, 360
    sheet = Image.new("RGB", (tw * 2, (th + 30) * ((len(names) + 1) // 2)), (40, 30, 35))
    dr = ImageDraw.Draw(sheet)
    for k, name in enumerate(names):
        D = EFFECTS[name][0]
        t = {"confetti": 1.2, "pop": 0.55, "shine": 1.2, "drip_choco": 4.0, "drip_berry": 4.0}.get(name, D * 0.37)
        im = Image.fromarray(render(name, t).on(DEMO)).resize((tw, th), Image.LANCZOS)
        x, y = (k % 2) * tw, (k // 2) * (th + 30)
        sheet.paste(im, (x, y + 30))
        dr.text((x + 10, y + 8), f"{name}  ({D}s, t={t:.2f})", fill=(255, 220, 235))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--out", default="fx_out")
    ap.add_argument("--sheet", action="store_true", help="コンタクトシートだけ作る")
    a = ap.parse_args()
    names = a.names or list(EFFECTS)
    os.makedirs(a.out, exist_ok=True)
    contact_sheet(names, f"{a.out}/contact_sheet.png")
    if a.sheet:
        return
    with Pool() as pool:
        for name in names:
            print("render", name, flush=True)
            export(name, a.out, pool)


if __name__ == "__main__":
    main()
