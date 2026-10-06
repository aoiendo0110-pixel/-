"""「閉じ込める」のタイトル動画 (チョコの箱 × リボン × レース × ハートの錠) をグリーンバックで書き出す.

  python3 tojikomeru_logo.py --font MochiyPopOne.ttf --font-sub HachiMaruPop.ttf --out clips/text/tojikomeru_logo

zettai_reido_logo.py とは別の構成: 言葉をチョコの箱に「閉じ込めて」鍵をかける.
  0.0-0.6  ギンガム敷きのチョコ箱が下からせり上がる
  0.6-1.7  文字が1つずつ放り込まれ、ひだの紙カップにぽすっと入る (回りながら / カップもむにっ)
  1.7-2.3  サテンのリボン帯が上から伸び、リボン結びがぽんっ。紙タグ「ないしょ♡」が揺れて出る
  2.3-3.1  ハートの錠が落ちてきてぶらん → 鍵がくるくる飛んできて差し込み、回して「カチッ♡」
  3.1-5.4  箱がぶるっ・ハートが弾ける → 文字が順にぴょこっ、錠がゆらゆら
  5.4-6.0  箱ごと傾いて下へ落ちて退場
クロマキー用に、緑系の色と半透明のぼかしは使わない。
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import os
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from zettai_reido_logo import (CHOCO_D, CREAM, PINK, PINK_D, PINK_L, WHITE, clamp01, ease_out, ease_out_back,
                               heart_poly, heart_sticker, put, sparkle, spring)

W, H, FPS, DUR = 1920, 1080, 30, 6.0
EXIT_T = 5.4

TEXT = "閉じ込める"
RUBY = {0: "と", 2: "こ"}
CUP_X0, CUP_DX, CUP_Y, CUP_R = 318, 258, 612, 118
BOX = (140, 400, 1790, 810)  # 箱の外形
RIB_X, RIB_W = 1625, 124  # 縦のリボン帯
LOCK_PIVOT = (RIB_X, 470)
GOLD, GOLD_D = (238, 190, 92), (168, 116, 40)
SATIN, SATIN_D, SATIN_L = (236, 76, 138), (186, 38, 98), (255, 150, 192)
CUPS = [((255, 176, 204), (226, 104, 154)), ((156, 92, 62), (100, 52, 34))]
TILTS = (-5, 4, -3, 5, -4)


def ease_in(x):
    return clamp01(x) ** 2


def hump(u):
    """0→1→0 の山 (u: 0-1)."""
    return math.sin(math.pi * clamp01(u))


# ---------------------------------------------------------------- 部品
def make_box():
    x0, y0, x1, y1 = BOX
    pad = 40
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # 下にのぞくレースのフリル (箱の後ろ)
    for x in range(x0 + 26, x1 - 10, 36):
        d.ellipse((x - 26, y1 - 16, x + 26, y1 + 36), fill=PINK_D)
    for x in range(x0 + 26, x1 - 10, 36):
        d.ellipse((x - 22, y1 - 16, x + 22, y1 + 31), fill=WHITE)
        d.ellipse((x - 5, y1 + 13, x + 5, y1 + 23), fill=PINK_L)
    d.rounded_rectangle((x0, y0 + 16, x1, y1 + 16), 44, fill=CHOCO_D)  # 厚み
    d.rounded_rectangle((x0 - 8, y0 - 8, x1 + 8, y1 + 8), 50, fill=WHITE)
    d.rounded_rectangle((x0, y0, x1, y1), 44, fill=(116, 60, 40))
    d.rounded_rectangle((x0 + 10, y0 + 8, x1 - 10, y0 + 22), 8, fill=(170, 104, 72))
    # 中敷き: ピンクのギンガム
    ix0, iy0, ix1, iy1 = x0 + 34, y0 + 34, x1 - 34, y1 - 34
    cell = 34
    g = np.zeros((iy1 - iy0, ix1 - ix0, 4), np.uint8)
    yy, xx = np.mgrid[0:iy1 - iy0, 0:ix1 - ix0]
    a, b = (yy // cell) % 2, (xx // cell) % 2
    cols = np.array([[255, 236, 243], [255, 212, 228], [255, 188, 212]], np.uint8)
    g[..., :3] = cols[a + b]
    g[..., 3] = 255
    tray = Image.fromarray(g, "RGBA")
    m = Image.new("L", tray.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tray.width - 1, tray.height - 1), 26, fill=255)
    im.paste(tray, (ix0, iy0), m)
    d.rounded_rectangle((ix0, iy0, ix1, iy1), 26, outline=WHITE, width=5)
    # 小さいハートのスタンプ (カップの間)
    for i in range(4):
        cx = CUP_X0 + CUP_DX * (i + 0.5)
        for cy in (iy0 + 30, iy1 - 30):
            d.polygon(heart_poly(cx, cy, 11), fill=WHITE)
            d.polygon(heart_poly(cx, cy, 7), fill=PINK)
    return im


def make_cup(fill, dark, r=CUP_R):
    S = int(r * 2 + 50)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    n = 22
    for pad, col in ((9, WHITE), (4, dark)):
        for i in range(n):
            a = 2 * math.pi * i / n
            d.ellipse((c + r * math.cos(a) - 16 - pad, c + r * math.sin(a) - 16 - pad,
                       c + r * math.cos(a) + 16 + pad, c + r * math.sin(a) + 16 + pad), fill=col)
        d.ellipse((c - r - pad, c - r - pad, c + r + pad, c + r + pad), fill=col)
    for i in range(n):
        a = 2 * math.pi * i / n
        d.ellipse((c + r * math.cos(a) - 16, c + r * math.sin(a) - 16, c + r * math.cos(a) + 16,
                   c + r * math.sin(a) + 16), fill=fill)
    d.ellipse((c - r, c - r, c + r, c + r), fill=fill)
    for i in range(n):  # ひだ
        a = 2 * math.pi * (i + 0.5) / n
        d.line([(c + r * 0.66 * math.cos(a), c + r * 0.66 * math.sin(a)),
                (c + (r + 10) * math.cos(a), c + (r + 10) * math.sin(a))], fill=dark, width=4)
    r2 = r * 0.66
    d.ellipse((c - r2, c - r2, c + r2, c + r2), fill=dark)
    d.ellipse((c - r2 + 6, c - r2 + 6, c + r2 - 6, c + r2 - 6), fill=fill)
    return im


def make_letter(ch, font):
    """クリームの文字 + チョコのフチ + 白フチ + ピンクの影."""
    f = ImageFont.truetype(font, 176)
    S = 340

    def mask(st):
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).text((S / 2, S / 2 - 6), ch, font=f, anchor="mm", fill=255, stroke_width=st,
                               stroke_fill=255)
        return m
    m0, m1, m2 = mask(0), mask(11), mask(20)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    im.paste(PINK_D + (255,), (5, 10), m2)
    im.paste(WHITE + (255,), (0, 0), m2)
    im.paste(CHOCO_D + (255,), (0, 0), m1)
    bb = m0.getbbox()
    g = np.zeros((S, S, 4), np.uint8)
    yy = np.clip((np.arange(S) - bb[1]) / (bb[3] - bb[1]), 0, 1)[:, None]
    for c, (a, b) in enumerate(zip(CREAM, (255, 214, 228))):
        g[..., c] = (a * (1 - yy) + b * yy).astype(np.uint8)
    g[..., 3] = 255
    im.paste(Image.fromarray(g, "RGBA"), (0, 0), m0)
    return im


def make_bow():
    """サテンのリボン結び (白フチ)."""
    S = (420, 300)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = S[0] / 2, 120

    def loop(s, pad, col):
        pts = []
        for i in range(40):
            a = 2 * math.pi * i / 40
            x = 0.5 + 0.5 * math.cos(a)
            y = math.sin(a) * (0.35 + 0.35 * x)
            pts.append((cx + s * (12 + 150 * x) + s * pad * math.cos(a) * 0.4, cy - 30 * x + 95 * y + pad * math.sin(a)))
        d.polygon(pts, fill=col)

    def tail(s, pad, col):
        d.polygon([(cx + s * 10 - s * pad, cy - pad), (cx + s * 40 + s * pad, cy - pad),
                   (cx + s * 120 + s * pad, cy + 165 + pad), (cx + s * 82, cy + 135), (cx + s * 50 - s * pad,
                                                                                     cy + 170 + pad)], fill=col)
    for pad, col in ((10, WHITE), (0, None)):
        for s in (-1, 1):
            tail(s, pad, col or SATIN_D)
        for s in (-1, 1):
            loop(s, pad, col or SATIN)
    for s in (-1, 1):  # 輪の内側の折り目
        d.polygon([(cx + s * 18, cy - 12), (cx + s * 92, cy - 28), (cx + s * 40, cy + 24)], fill=SATIN_D)
        d.line([(cx + s * 60, cy - 70), (cx + s * 140, cy - 54)], fill=SATIN_L, width=8)
    d.ellipse((cx - 44, cy - 42, cx + 44, cy + 42), fill=WHITE)
    d.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=SATIN)
    d.ellipse((cx - 18, cy - 22, cx + 2, cy - 6), fill=SATIN_L)
    return im


def make_lock(closed):
    """ハートの南京錠 (上の丸は吊るす輪). closed=False は掛け金が上がった状態."""
    S = (240, 330)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, hy = S[0] / 2, 200  # ハートの中心
    up = 0 if closed else 30
    for wd, col in ((34, WHITE), (26, GOLD_D), (16, GOLD)):  # 掛け金
        d.arc((cx - 50, hy - 140 - up, cx + 50, hy - 40 - up), 180, 360, fill=col, width=wd)
        for s in (-1, 1):
            d.line([(cx + s * 50 - s * wd / 2 + s * (wd / 2), hy - 90 - up), (cx + s * 50, hy - 40 - (up if s > 0 else 0))],
                   fill=col, width=wd)
    d.polygon(heart_poly(cx, hy, 98), fill=WHITE)
    d.polygon(heart_poly(cx, hy, 90), fill=PINK_D)
    d.polygon(heart_poly(cx, hy, 82), fill=PINK)
    d.ellipse((cx - 56, hy - 52, cx - 26, hy - 24), fill=WHITE)
    d.ellipse((cx - 16, hy - 20, cx + 16, hy + 12), fill=CHOCO_D)  # 鍵穴
    d.polygon([(cx - 9, hy), (cx + 9, hy), (cx + 14, hy + 40), (cx - 14, hy + 40)], fill=CHOCO_D)
    return im


def make_key():
    """金のハートの鍵. 先端が左 (x=0 側), ハートの持ち手が右."""
    S = (330, 150)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cy = 75
    for pad, col in ((8, WHITE), (4, GOLD_D), (0, GOLD)):
        d.rounded_rectangle((14 - pad, cy - 10 - pad, 220 + pad, cy + 10 + pad), 8, fill=col)
        for x in (24, 54):  # 歯
            d.rectangle((x - pad, cy + 4, x + 18 + pad, cy + 38 + pad), fill=col)
        d.polygon(heart_poly(265, cy + 4, 50 + pad), fill=col)
    d.polygon(heart_poly(265, cy + 4, 22), fill=WHITE)
    d.polygon(heart_poly(265, cy + 4, 16), fill=PINK)
    return im


def make_tag(font):
    S = (330, 170)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((30, 30, 318, 152), 26, fill=PINK_D)
    d.rounded_rectangle((36, 22, 312, 144), 24, fill=WHITE)
    d.rounded_rectangle((46, 32, 302, 134), 18, fill=CREAM)
    for x in range(60, 292, 18):
        d.rectangle((x, 122, x + 9, 126), fill=PINK_L)
    d.ellipse((58, 70, 78, 90), fill=WHITE, outline=PINK_D, width=4)  # 紐の穴
    d.text((192, 80), "ないしょ♡", font=ImageFont.truetype(font, 50), anchor="mm", fill=CHOCO_D)
    return im


def text_sticker(text, font, size, fill=PINK, line=CHOCO_D):
    f = ImageFont.truetype(font, size)
    bb = f.getbbox(text, stroke_width=14)
    im = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 30), (0, 0, 0, 0))
    o = (10 - bb[0], 10 - bb[1])
    d = ImageDraw.Draw(im)
    d.text((o[0] + 3, o[1] + 7), text, font=f, fill=PINK_D, stroke_width=14, stroke_fill=PINK_D)
    d.text(o, text, font=f, fill=WHITE, stroke_width=14, stroke_fill=WHITE)
    d.text(o, text, font=f, fill=fill, stroke_width=5, stroke_fill=line)
    return im


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, font_sub):
        self.box = make_box()
        self.cups = [make_cup(*CUPS[i % 2]) for i in range(len(TEXT))]
        self.letters = [make_letter(ch, font) for ch in TEXT]
        self.ruby = {i: text_sticker(ch, font_sub, 58) for i, ch in RUBY.items()}
        self.bow = make_bow()
        self.lock_open, self.lock_closed = make_lock(False), make_lock(True)
        self.key = make_key()
        self.tag = make_tag(font_sub)
        self.kachi = text_sticker("カチッ♡", font_sub, 70)
        self.hearts = {r: heart_sticker(r) for r in (16, 22, 30)}
        self.sp_w, self.sp_p, self.sp_s = sparkle(24), sparkle(30, PINK, WHITE), sparkle(15)
        self.twinkles = [(240, 300, "w", 0.0), (900, 330, "p", 0.4), (1300, 860, "s", 0.2), (1780, 300, "w", 0.65),
                         (120, 700, "s", 0.8), (1820, 860, "p", 0.3), (640, 880, "w", 0.55), (1150, 300, "s", 0.9)]

    def cup_x(self, i):
        return CUP_X0 + CUP_DX * i

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idle = clamp01((t - 3.2) / 0.4)
        P = 2 * math.pi * t / 1.8
        # 鍵がかかった瞬間に箱がぶるっ
        shake = spring(t - 3.05, 7, 40, 9) if t > 3.05 else 0

        # キラキラ (奥)
        if t > 3.1:
            for x, y, kind, ph in self.twinkles:
                q = ((t - 3.1) / 1.3 + ph) % 1
                s = hump(q / 0.45) ** 2
                put(im, {"w": self.sp_w, "p": self.sp_p, "s": self.sp_s}[kind], x, y, s * 1.2, 45 * q)

        im.alpha_composite(self.box)
        # 紙カップと文字
        for i, ch in enumerate(TEXT):
            x = self.cup_x(i)
            t0 = 0.62 + i * 0.21
            land = t - t0 - 0.36
            csq = spring(land, 0.1, 26, 10) if land > 0 else 0
            put(im, self.cups[i], x, CUP_Y, 1, 0, 1 + csq, 1 - csq)
            u = (t - t0) / 0.36
            if u < 0:
                continue
            u = clamp01(u)
            dir_ = -1 if i % 2 else 1
            lx = x + (1 - u) * 160 * dir_
            ly = CUP_Y - 8 - 760 * (1 - u * u)  # 加速しながら落ちる
            rot = TILTS[i] + (1 - u) * 300 * dir_ + spring(land, 10, 18, 7)
            sq = spring(land, 0.22, 24, 8)
            # 待機: 鍵の直後に順番にぴょこっ、その後はゆっくりした波
            hop = 30 * hump((t - 3.15 - i * 0.08) / 0.3)
            hop += idle * 12 * max(0, math.sin(P - i * 0.9)) ** 3
            rot += idle * 3 * math.sin(P * 0.5 - i * 1.1)
            put(im, self.letters[i], lx, ly - hop, 1, rot, 1 + sq, 1 - sq)
            if i in RUBY:
                k = ease_out_back((t - t0 - 0.3) / 0.3, 2.6)
                if k > 0:
                    put(im, self.ruby[i], x + 92, CUP_Y - 128 - hop, k, TILTS[i] + 12)
            if 0 < land < 0.45:  # 着地のミニハート
                q = land / 0.45
                for s in (-1, 1):
                    put(im, self.hearts[16], x + s * (80 + 70 * ease_out(q)), CUP_Y - 60 - 50 * q, 1 - q, s * 20)

        # 縦のリボン帯 (上から伸びる)
        rb = ease_out((t - 1.75) / 0.35)
        if rb > 0:
            d = ImageDraw.Draw(im)
            y0, y1 = BOX[1] - 14, BOX[1] - 14 + (BOX[3] - BOX[1] + 42) * rb
            x0, x1 = RIB_X - RIB_W / 2, RIB_X + RIB_W / 2
            d.rectangle((x0 - 7, y0, x1 + 7, y1), fill=WHITE)
            d.rectangle((x0, y0, x1, y1), fill=SATIN)
            d.rectangle((x0 + 14, y0, x0 + 30, y1), fill=SATIN_L)
            d.rectangle((x1 - 18, y0, x1 - 10, y1), fill=SATIN_D)
            for yy in np.arange(y0 + 10, y1 - 10, 22):  # ステッチ
                d.rectangle((x0 + 4, yy, x0 + 8, yy + 10), fill=WHITE)
                d.rectangle((x1 - 8, yy, x1 - 4, yy + 10), fill=WHITE)

        # 紙タグ (紐で箱の角に)
        k = ease_out_back((t - 2.0) / 0.4, 2.2)
        if k > 0:
            ang = -14 + spring(t - 2.0, 22, 9, 3.5) + idle * 4 * math.sin(P * 0.6)
            put(im, self.tag, 270, 360, k, ang)

        # ハートの錠: 落ちてきて、ぶらん
        if t > 2.25:
            u = clamp01((t - 2.25) / 0.3)
            drop = -560 * (1 - u * u)
            th = spring(t - 2.55, 20, 7, 2.6) + spring(t - 3.05, 8, 9, 3) + idle * 4 * math.sin(P * 0.7)
            a = math.radians(th)
            L = 120
            px, py = LOCK_PIVOT
            lx, ly = px + L * math.sin(a), py + drop + L * math.cos(a)
            d = ImageDraw.Draw(im)
            d.line([(px, py + drop), (lx - 40 * math.sin(a), ly - 40 * math.cos(a))], fill=WHITE, width=14)
            d.line([(px, py + drop), (lx - 40 * math.sin(a), ly - 40 * math.cos(a))], fill=GOLD_D, width=7)
            d.ellipse((px - 16, py + drop - 16, px + 16, py + drop + 16), fill=WHITE)
            d.ellipse((px - 10, py + drop - 10, px + 10, py + drop + 10), fill=GOLD)
            lock = self.lock_closed if t > 3.05 else self.lock_open
            # 錠の画像の中のハート中心 (200) が (lx, ly + 90) あたりに来るよう、画像中心を置く
            cxo, cyo = lx + 35 * math.sin(a), ly + 35 * math.cos(a)
            put(im, lock, cxo, cyo, 1.05, -th)
            self.keyhole = (cxo + 1.05 * 35 * math.sin(a), cyo + 1.05 * 35 * math.cos(a))
            # 鍵: くるくる飛んできて、差し込んで回す
            if 2.55 < t < 3.35:
                kx, ky = self.keyhole
                v = clamp01((t - 2.55) / 0.35)
                e = ease_out(v)
                sx, sy = 2050, 260
                bx = sx + (kx - sx) * e
                by = sy + (ky - sy) * e - 220 * hump(v)
                spin = 720 * (1 - e)
                turn = 90 * ease_out_back((t - 2.95) / 0.12, 1.5)
                ks = 1.0 * (1 - ease_out((t - 3.15) / 0.2))
                # 鍵の先 (画像の左端寄り) を鍵穴に合わせる
                ang = math.radians(spin + turn)
                off = 135
                put(im, self.key, bx + off * math.cos(ang), by - off * math.sin(ang), ks, spin + turn)
            # 「カチッ♡」とはじけるハート
            if t > 3.05:
                q = (t - 3.05) / 0.9
                if q < 1:
                    for j in range(8):
                        aa = 2 * math.pi * j / 8 + 0.4
                        rr = 60 + 190 * ease_out(q)
                        put(im, self.hearts[(16, 22, 30)[j % 3]], cxo + rr * math.cos(aa), cyo + rr * math.sin(aa) - 40 * q,
                            1.1 * (1 - q) ** 0.6 if q > 0.6 else 1.1, 25 * math.sin(j))
                k = ease_out_back((t - 3.05) / 0.3, 2.6)
                put(im, self.kachi, 1660, 935 + 6 * math.sin(P) * idle, k, -10 + 4 * math.sin(P * 0.8) * idle)

        # リボン結び (帯の上端)
        k = ease_out_back((t - 2.0) / 0.35, 2.8)
        if k > 0:
            wig = spring(t - 2.0, 18, 13, 4.5) + idle * 3 * math.sin(P * 0.6 + 1)
            put(im, self.bow, RIB_X, BOX[1] + 60, k * 0.95, wig)

        # 全体の動き: 登場 (下からせり上がる) / 鍵のぶるっ / 退場 (傾いて落ちる)
        dy, rot = 0.0, 0.0
        if t < 0.6:
            q = ease_out_back(t / 0.6, 1.6)
            dy, rot = 900 * (1 - q), 8 * (1 - q)
        if t > EXIT_T:
            q = (t - EXIT_T) / (DUR - EXIT_T)
            dy = -40 * hump(q / 0.3) + 1400 * ease_in(clamp01((q - 0.15) / 0.85))
            rot = -16 * ease_in(clamp01((q - 0.1) / 0.9))
        dx = shake
        if dy or rot or dx:
            im = im.rotate(rot, Image.BICUBIC, center=(W / 2, H / 2 + 100), translate=(dx, dy))
        return im


SCENE = None


def _init(font, font_sub):
    global SCENE
    SCENE = Scene(font, font_sub)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="文字用: Mochiy Pop One など丸い太字")
    ap.add_argument("--font-sub", required=True, help="小さい文字用: Hachi Maru Pop など手書き風")
    ap.add_argument("--out", default="tojikomeru_logo")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    if a.preview is not None:
        _init(a.font, a.font_sub)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = round(DUR * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.font_sub)) as pool:
        frames = pool.map(_frame, range(n), chunksize=4)
    Image.frombytes("RGBA", (W, H), frames[int(n * 0.7)]).save(a.out + ".png")
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    raw = ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    for args in ([*raw, "-f", "lavfi", "-i", f"color=0x00FF00:s={W}x{H}:r={FPS}",
                  "-filter_complex", "[1][0]overlay=shortest=1,format=yuv420p", "-c:v", "libx264", "-crf", "16",
                  "-movflags", "+faststart", a.out + "_greenback.mp4"],
                 [*raw, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24", "-row-mt", "1",
                  "-auto-alt-ref", "0", a.out + ".webm"]):
        p = subprocess.Popen([ff, "-y", "-v", "error", *args], stdin=subprocess.PIPE)
        for fb in frames:
            p.stdin.write(fb)
        p.stdin.close()
        p.wait()


if __name__ == "__main__":
    main()
