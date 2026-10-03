"""「メロディックチョコレート」の動く文字 (フェルト文字 × 五線譜のリボン × チョコ × レース) をグリーンバックで書き出す.

  python3 melodic_choco_logo.py --font HachiMaruPop.ttf --fat 7 --out clips/text/melodic_choco_logo [--cache cache3d]

uketore_logo.py と同じ手書きの丸文字 + フェルトのステッチで、音楽モチーフを足した派手め版.
  0.0-0.6  後ろの大きいレースのドイリーがくるっと開き、五線譜のリボンが左から描かれる
  0.4-1.4  「メロディック」がリズムに合わせて1文字ずつ五線譜の上へぽんっ (着地ごとに音符が飛ぶ)
  1.3-2.3  「チョコレート」が落ちてきてむにっ → 下からチョコがとろっと垂れる
  2.3-5.4  全体がビートで脈打ち、文字は波のように順に跳ねる。音符・3Dのチョコ・ハートの紙吹雪が舞う
  5.4-6.0  文字が音符のように上へ飛んで、ぽんっと消える
クロマキー用に、緑系の色と半透明のぼかしは使わない。
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import os
import random
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import render3d as R
from zettai_reido_logo import (CHOCO_D, PINK, PINK_D, PINK_L, WHITE, clamp01, ease_out, ease_out_back, heart_poly,
                               heart_sticker, put, sparkle, spring)

W, H, FPS, DUR = 1920, 1080, 30, 6.0
EXIT_T = 5.4
BEAT = 60 / 128  # ビートの間隔 (128BPM)
SATIN, SATIN_D, SATIN_L = (236, 76, 138), (186, 38, 98), (255, 160, 198)
LAV = ((222, 196, 255), (176, 140, 238))
PINKS = ((255, 178, 212), (246, 120, 172))
CREAM = ((255, 250, 244), (255, 214, 230))
BERRY = ((246, 84, 132), (204, 34, 84))
CHOCO = ((208, 144, 104), (140, 80, 50))

# 上の段 (文字, 中心, 大きさ, 傾き, 色, ステッチ色)
TOP = [("メ", (395, 345), 1.0, -11, PINKS, WHITE), ("ロ", (595, 305), 0.92, 8, CREAM, PINK),
       ("デ", (800, 350), 1.06, -6, BERRY, WHITE), ("ィ", (960, 405), 0.62, 12, LAV, WHITE),
       ("ッ", (1080, 395), 0.62, -10, PINKS, WHITE), ("ク", (1245, 330), 1.0, 9, CREAM, PINK)]
# 下の段 (チョコ色)
BOTTOM = [("チ", (440, 690), 1.08, -8), ("ョ", (630, 750), 0.66, 12), ("コ", (815, 668), 1.06, 5),
          ("レ", (1030, 705), 0.98, -10), ("ー", (1225, 712), 0.9, 4), ("ト", (1430, 680), 1.08, 9)]
TOP_T0, BOTTOM_T0 = 0.42, 1.32
STAFF = [(-40, 470), (300, 420), (650, 500), (1000, 420), (1350, 500), (1700, 420), (1980, 470)]


def hump(u):
    return math.sin(math.pi * clamp01(u))


def ease_in(x):
    return clamp01(x) ** 2


def catmull(pts, n=600):
    P = np.array(pts, float)
    P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]])
    out, seg = [], len(P) - 3
    for i in range(seg):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for u in np.linspace(0, 1, n // seg, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    out.append(P[-2])
    return np.array(out)


# ---------------------------------------------------------------- フェルト文字 (チョコの垂れ付き)
class Felt:
    """手書き丸文字を太らせたフェルト風の1文字. 外側と中身を分けて持ち、間にチョコの垂れを挟める."""

    def __init__(self, ch, font, size, cols, stitch, fat, drips=False):
        f = ImageFont.truetype(font, size)
        S = self.S = int(size * 1.8)

        def mask(st):
            m = Image.new("L", (S, S), 0)
            ImageDraw.Draw(m).text((S / 2, S / 2), ch, font=f, anchor="mm", fill=255, stroke_width=st + fat,
                                   stroke_fill=255)
            return m
        m0, m1, m2 = mask(0), mask(9), mask(26)
        outer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        for k in range(12, 0, -1):
            outer.paste(CHOCO_D + (255,), (round(5 * k / 12), round(13 * k / 12)), m2)
        outer.paste(WHITE + (255,), (0, 0), m2)
        outer.paste(CHOCO_D + (255,), (0, 0), m1)
        self.outer = outer
        a = np.array(m0)
        bb = m0.getbbox()
        top, bot = cols
        self.bot = bot
        g = np.zeros((S, S, 4), np.uint8)
        yy = np.clip((np.arange(S) - bb[1]) / (bb[3] - bb[1]), 0, 1)[:, None]
        for c in range(3):
            g[..., c] = (top[c] * (1 - yy) + bot[c] * yy).astype(np.uint8)
        g[..., 3] = a
        fill = Image.fromarray(g, "RGBA")
        e1 = np.array(m0.filter(ImageFilter.MinFilter(13))) > 128
        e2 = np.array(m0.filter(ImageFilter.MinFilter(19))) > 128
        Y, X = np.mgrid[0:S, 0:S]
        st = ((e1 & ~e2) & (((X + Y) // 9) % 2 == 0)).astype(np.uint8) * 255
        fill.paste(stitch + (255,), (0, 0), Image.fromarray(st))
        inner = np.array(m0.filter(ImageFilter.MinFilter(11))).astype(np.float32) / 255
        inner = np.roll(inner, 5, 0)
        fade = np.clip((0.45 - yy) / 0.3, 0, 1)
        hl = Image.fromarray(np.minimum((inner * fade * 0.5 * 255).astype(np.uint8), a)).filter(ImageFilter.GaussianBlur(1.5))
        fill.paste(WHITE + (255,), (0, 0), hl)
        self.fill = fill
        self.drips = []
        if drips:  # いちばん下の画の、幅のある所に1本
            low = np.where(a > 128, np.arange(S)[:, None], -1).max(0)
            lim = low.max() - 18
            xs = np.nonzero(low >= lim)[0]
            if len(xs):
                segs = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
                sg = max(segs, key=len)
                if len(sg) >= 18:
                    cx = float(sg.mean())
                    self.drips.append((cx, int(low[int(cx)]) - 12, min(26, len(sg) * 0.55), 22 + size * 0.03))

    def draw(self, drip_k):
        im = self.outer.copy()
        if drip_k > 0.01 and self.drips:
            d = ImageDraw.Draw(im)
            for cx, y0, w, L in self.drips:
                ln = L * drip_k
                for pad, col in ((26, WHITE), (9, CHOCO_D), (0, self.bot)):
                    r = w * 0.9 + pad
                    d.rounded_rectangle((cx - w / 2 - pad, y0 - pad, cx + w / 2 + pad, y0 + ln + pad), radius=w / 2 + pad,
                                        fill=col)
                    d.ellipse((cx - r, y0 + ln - r, cx + r, y0 + ln + r), fill=col)
                d.ellipse((cx - w * 0.4, y0 + ln - w * 0.35, cx - w * 0.1, y0 + ln), fill=(214, 150, 120))
        im.alpha_composite(self.fill)
        return im


# ---------------------------------------------------------------- 飾り
def note_sticker(kind, fill, size=1.0):
    """♪ (kind=1) / ♫ (kind=2) を図形で描いたステッカー."""
    S = int(200 * size)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = size

    def shape(pad, col):
        heads = [(70 * k, 150 * k)] if kind == 1 else [(55 * k, 155 * k), (140 * k, 135 * k)]
        for hx, hy in heads:
            d.ellipse((hx - 30 * k - pad, hy - 22 * k - pad, hx + 30 * k + pad, hy + 22 * k + pad), fill=col)
            d.rectangle((hx + 18 * k - pad, hy - 110 * k - pad, hx + 30 * k + pad, hy), fill=col)
        if kind == 1:
            hx, hy = heads[0]
            d.polygon([(hx + 18 * k - pad, hy - 112 * k - pad), (hx + 75 * k + pad, hy - 70 * k),
                       (hx + 62 * k + pad, hy - 50 * k + pad), (hx + 30 * k, hy - 72 * k)], fill=col)
        else:
            (x1, y1), (x2, y2) = heads
            d.polygon([(x1 + 18 * k - pad, y1 - 112 * k - pad), (x2 + 30 * k + pad, y2 - 112 * k - pad),
                       (x2 + 30 * k + pad, y2 - 82 * k + pad), (x1 + 18 * k - pad, y1 - 82 * k + pad)], fill=col)
    shape(12, WHITE)
    shape(5, CHOCO_D)
    shape(0, fill)
    d.ellipse((S * 0.24, S * 0.68, S * 0.34, S * 0.74), fill=WHITE)
    return im


def doily(R=470, n=40):
    """後ろで回る大きいレースのドイリー (外は波、中は放射の模様と穴)."""
    S = R * 2 + 80
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    for pad, col in ((10, PINK_L), (4, WHITE)):
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = c + R * math.cos(a), c + R * math.sin(a)
            d.ellipse((x - 40 - pad, y - 40 - pad, x + 40 + pad, y + 40 + pad), fill=col)
        d.ellipse((c - R - pad, c - R - pad, c + R + pad, c + R + pad), fill=col)
    d.ellipse((c - R, c - R, c + R, c + R), fill=(255, 238, 245))
    for i in range(n):  # 縁の穴
        a = 2 * math.pi * (i + 0.5) / n
        x, y = c + (R + 12) * math.cos(a), c + (R + 12) * math.sin(a)
        d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=PINK_L)
    for i in range(24):  # 放射の帯
        a0, a1 = 2 * math.pi * i / 24, 2 * math.pi * (i + 0.5) / 24
        d.polygon([(c, c), (c + (R - 40) * math.cos(a0), c + (R - 40) * math.sin(a0)),
                   (c + (R - 40) * math.cos(a1), c + (R - 40) * math.sin(a1))], fill=(255, 222, 236))
    for rr in (R - 40, R * 0.62):  # 点線の輪
        for i in range(int(rr / 7)):
            a = 2 * math.pi * i / int(rr / 7)
            x, y = c + rr * math.cos(a), c + rr * math.sin(a)
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=PINK)
    for i in range(12):  # 内側のハートの輪
        a = 2 * math.pi * i / 12
        x, y = c + R * 0.78 * math.cos(a), c + R * 0.78 * math.sin(a)
        d.polygon(heart_poly(x, y, 16), fill=WHITE)
        d.polygon(heart_poly(x, y, 11), fill=PINK)
    return im


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, cache, fat):
        self.top = [Felt(ch, font, round(210 * sc), cols, st, fat) for ch, _, sc, _, cols, st in TOP]
        self.bottom = [Felt(ch, font, round(220 * sc), CHOCO, PINK, fat, drips=ch in "チコト")  # 垂れは3文字だけ
                       for ch, _, sc, _ in BOTTOM]
        self.doily = doily()
        self.staff = catmull(STAFF)
        self.notes = [note_sticker(1, PINK), note_sticker(2, (255, 214, 120)), note_sticker(1, (196, 168, 255)),
                      note_sticker(2, PINK_L), note_sticker(1, (246, 84, 132))]
        self.hearts = {r: heart_sticker(r) for r in (16, 22, 30)}
        self.sp_w, self.sp_p = sparkle(26), sparkle(32, PINK, WHITE)
        self.spr = {}
        for name, (size, n) in {"choco_heart": (520, 60), "bar": (300, 48), "truffle": (300, 48),
                                "macaron": (480, 60)}.items():
            self.spr[name] = [Image.open(os.path.join(cache, f"{name}_{size}_{i:02d}.png")).convert("RGBA")
                              for i in range(n)]
        rnd = random.Random(21)
        # 漂う音符と3Dのお菓子 (画面の外側寄り)
        spots = [(110, 210), (1810, 200), (130, 900), (1790, 900), (1640, 560), (260, 560), (960, 110), (960, 975),
                 (1500, 950), (420, 960)]
        kinds = ["note0", "bar", "note1", "truffle", "choco_heart", "note2", "note3", "macaron", "note4", "truffle"]
        self.floaters = [dict(x=x, y=y, k=k, ph=rnd.random(), s=rnd.uniform(0.85, 1.1)) for (x, y), k in zip(spots, kinds)]
        cols = [PINK, WHITE, (255, 214, 120), (246, 84, 132), PINK_L, (196, 168, 255)]
        self.confetti = []
        for i in range(60):
            c = Image.new("RGBA", (44, 44), (0, 0, 0, 0))
            dc = ImageDraw.Draw(c)
            if i % 3 == 0:
                dc.polygon(heart_poly(22, 22, 14), fill=cols[i % 6])
            elif i % 3 == 1:
                dc.ellipse((12, 12, 32, 32), fill=cols[i % 6])
            else:
                dc.rectangle((6, 15, 38, 29), fill=cols[i % 6])
            self.confetti.append(dict(im=c, x=rnd.uniform(0, W), y0=rnd.uniform(-1100, 0), v=rnd.uniform(160, 260),
                                      ph=rnd.random() * 6, r=rnd.uniform(0, 360), sw=rnd.uniform(20, 60)))
        self.twinkles = [(560, 170, "w", 0.0), (1380, 190, "p", 0.4), (1560, 760, "w", 0.7), (300, 800, "p", 0.2),
                         (1100, 560, "w", 0.85), (700, 540, "p", 0.55), (1730, 360, "w", 0.3), (190, 380, "p", 0.65)]

    def sprite(self, name, rev):
        seq = self.spr[name]
        return seq[int(math.floor(rev * len(seq))) % len(seq)]

    def draw_staff(self, im, reveal, t, idle):
        n = len(self.staff)
        k = max(2, int(n * reveal))
        q = self.staff[:k].copy()
        s = np.arange(k) / n
        q[:, 1] += idle * 16 * np.sin(2 * math.pi * t / 1.8 - s * 9)
        d = ImageDraw.Draw(im)
        nrm = np.gradient(q, axis=0)
        nrm = np.stack([-nrm[:, 1], nrm[:, 0]], 1)
        nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-6
        for r, col in ((70, WHITE), (62, CHOCO_D), (56, SATIN)):
            for x, y in q:
                d.ellipse((x - r, y - r, x + r, y + r), fill=col)
        for j in range(5):  # 五線
            off = (j - 2) * 20
            for (x, y), (nx, ny) in zip(q, nrm):
                d.ellipse((x + nx * off - 3, y + ny * off - 3, x + nx * off + 3, y + ny * off + 3), fill=WHITE)
        for i in range(0, len(q), 120):  # 小節線
            x, y = q[i]
            nx, ny = nrm[i]
            d.line([(x - nx * 40, y - ny * 40), (x + nx * 40, y + ny * 40)], fill=WHITE, width=6)
        return q

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idle = clamp01((t - 2.3) / 0.4)
        ex = clamp01((t - EXIT_T) / (DUR - EXIT_T))
        b = (t % BEAT) / BEAT
        pulse = idle * math.exp(-b * 6) * (1 - ex)  # ビートごとのドンッ
        P = 2 * math.pi * t / (BEAT * 4)

        # 後ろのドイリー
        k = ease_out_back(t / 0.6, 1.6) * (1 - ease_in((ex - 0.4) / 0.6))
        if k > 0:
            put(im, self.doily, 935, 520, k * (1 + 0.035 * pulse), t * 10 + 120 * (1 - ease_out(t / 0.6)))
        # 紙吹雪 (奥)
        if t > 2.0:
            for c in self.confetti[::2]:
                self._confetti(im, c, t)
        # 漂う音符・3Dのお菓子
        for j, f in enumerate(self.floaters):
            kk = ease_out_back((t - 1.9 - j * 0.07) / 0.35, 2.4) * (1 - ease_in(ex / 0.5))
            if kk <= 0:
                continue
            y = f["y"] + 18 * math.sin(2 * math.pi * (t / 2.4 + f["ph"]))
            rot = 12 * math.sin(2 * math.pi * (t / 1.9 + f["ph"]))
            s = kk * f["s"] * (1 + 0.08 * pulse)
            if f["k"].startswith("note"):
                put(im, self.notes[int(f["k"][4])], f["x"], y, s * 0.8, rot)
            elif f["k"] == "choco_heart":
                put(im, self.sprite("choco_heart", 0.2 * t + f["ph"]), f["x"], y, s * 0.42, rot)
            elif f["k"] == "macaron":
                put(im, self.sprite("macaron", 0.15 * t + f["ph"]), f["x"], y, s * 0.42, rot)
            else:
                put(im, self.sprite(f["k"], 0.25 * t + f["ph"]), f["x"], y, s * 0.62, rot)

        # 五線譜のリボン
        reveal = ease_out(t / 0.75) * (1 - ease_in((ex - 0.2) / 0.6))
        if reveal > 0.002:
            q = self.draw_staff(im, reveal, t, idle)
            if t < 0.8:
                put(im, self.sp_w, q[-1][0], q[-1][1], 1.4, t * 400)

        # 下の段: チョコレート (落ちてきてむにっ → 垂れる)
        for i, ((ch, (x, y), sc, rot), L) in enumerate(zip(BOTTOM, self.bottom)):
            t0 = BOTTOM_T0 + i * 0.13
            u = (t - t0) / 0.3
            if u < 0:
                continue
            uu = clamp01(u)
            land = t - t0 - 0.3
            yy = y - 620 * (1 - uu * uu)
            sq = spring(land, 0.22, 22, 8)
            r = rot + (1 - uu) * (25 if i % 2 else -25)
            wave = idle * 26 * hump(((t / (BEAT * 4)) - i * 0.08) % 1 / 0.22)  # 波のように順に跳ねる
            r += idle * 3 * math.sin(P + i)
            fly = ease_in(clamp01((ex - 0.25 - i * 0.05) / 0.5))
            yy -= wave + 900 * fly
            s = (1 + 0.05 * pulse) * (1 - fly * 0.4)
            g = L.draw(ease_out_back((t - t0 - 0.35) / 0.9, 1.3))
            put(im, g, x, yy, s, r, 1 + sq, 1 - sq)

        # 上の段: メロディック (リズムに合わせて五線譜の上へぽんっ)
        for i, ((ch, (x, y), sc, rot, _, _), L) in enumerate(zip(TOP, self.top)):
            t0 = TOP_T0 + i * BEAT / 3
            u = (t - t0) / 0.32
            if u < 0:
                continue
            land = t - t0 - 0.32
            k = ease_out_back(u, 2.8)
            jump = 120 * hump(u)
            sq = spring(land, 0.2, 24, 9)
            r = rot + (1 - ease_out(u)) * (-40 if i % 2 else 40)
            wave = idle * 24 * hump(((t / (BEAT * 4)) - 0.5 - i * 0.08) % 1 / 0.22)
            r += idle * 4 * math.sin(P * 1.5 + i * 1.3)
            fly = ease_in(clamp01((ex - i * 0.05) / 0.5))
            yy = y - jump - wave - 900 * fly
            s = k * (1 + 0.05 * pulse) * (1 - fly * 0.4)
            put(im, L.draw(0), x, yy, s, r, 1 + sq, 1 - sq)
            if 0 < land < 0.6:  # 着地で音符がぴょんっ
                q = land / 0.6
                put(im, self.notes[i % 5], x + 120 + 60 * q, y - 120 - 140 * ease_out(q), 0.6 * (1 - q ** 2),
                    20 - 30 * q)

        # 3Dのチョコハート (右上で大きく)
        kk = ease_out_back((t - 2.05) / 0.45, 2.6) * (1 - ease_in(ex / 0.5))
        if kk > 0:
            put(im, self.sprite("choco_heart", 0.18 * t), 1580, 300 + 12 * math.sin(P), 0.62 * kk * (1 + 0.1 * pulse),
                -14 + 6 * math.sin(P * 0.5))

        # 紙吹雪 (手前) とキラキラ
        if t > 2.0:
            for c in self.confetti[1::2]:
                self._confetti(im, c, t)
            for x, y, kind, ph in self.twinkles:
                q = ((t - 2.0) / 1.0 + ph) % 1
                put(im, self.sp_w if kind == "w" else self.sp_p, x, y, hump(q / 0.45) ** 2 * 1.3 * (1 - ex), 45 * q)
        return im

    @staticmethod
    def _confetti(im, c, t):
        y = c["y0"] + c["v"] * (t - 2.0)
        if y < -40 or y > H + 40:
            return
        x = c["x"] + c["sw"] * math.sin(t * 2.2 + c["ph"])
        put(im, c["im"], x, y, 1, c["r"] + 160 * t, 1, max(0.15, abs(math.cos(t * 5 + c["ph"]))))


SCENE = None


def _init(font, cache, fat):
    global SCENE
    SCENE = Scene(font, cache, fat)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Hachi Maru Pop など手書きの丸文字")
    ap.add_argument("--fat", type=int, default=7, help="細いフォントを太らせる量 (px)")
    ap.add_argument("--out", default="melodic_choco_logo")
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    with Pool(a.jobs) as pool:
        R.build_sprites(pool, a.cache, {"choco_heart": (520, 60), "bar": (300, 48), "truffle": (300, 48),
                                        "macaron": (480, 60)})
    if a.preview is not None:
        _init(a.font, a.cache, a.fat)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = round(DUR * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.cache, a.fat)) as pool:
        frames = pool.map(_frame, range(n), chunksize=4)
    Image.frombytes("RGBA", (W, H), frames[int(n * 0.6)]).save(a.out + ".png")
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
