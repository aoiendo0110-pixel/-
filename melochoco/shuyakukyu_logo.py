"""「主役級になる / 受け取れ♥」のタイトル動画 (フリルのカーテン舞台 × 王冠 × チョコのハート) をグリーンバックで書き出す.

  python3 shuyakukyu_logo.py --font MochiyPopOne.ttf --out clips/text/shuyakukyu_logo [--cache cache3d]

他のロゴ動画とは別の構成: 舞台の幕が開いて主役が登場する.
  0.0-1.0  閉じたフリルのカーテンが左右に開く (上には波打つ飾り幕)
  1.0-1.8  回るスターバーストの上に「主役級」が1文字ずつカードのようにくるっと裏返って登場 → 「級」に王冠が落ちる
  1.8-2.4  「になる」が右のカーテンの裏からぴょんぴょん跳ねてきて、それぞれの場所へ
  2.4-3.5  「受け取れ」のハートチョコが奥から手前へ投げつけられるように飛んでくる → 3Dのチョコハートがドキッ
  3.5-5.4  ハートがドキドキ脈打ち、紙吹雪が舞い、文字がそれぞれ揺れる
  5.4-6.0  カーテンが閉じて終わる
文字は1文字ずつ大きさ・角度・高さを変えて並べる。クロマキー用に緑系の色と半透明のぼかしは使わない。
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
from zettai_reido_logo import (CHOCO_D, CREAM, PINK, PINK_D, PINK_L, WHITE, clamp01, ease_out, ease_out_back,
                               heart_poly, heart_sticker, put, sparkle, spring)

W, H, FPS, DUR = 1920, 1080, 30, 6.0
CX = W / 2
OPEN_T, CLOSE_T = (0.25, 1.0), (5.35, 6.0)

GOLD, GOLD_D = (240, 192, 90), (176, 120, 40)
BERRY_T, BERRY_B, BERRY_D = (240, 54, 104), (176, 22, 66), (104, 8, 40)
CURTAIN = [(255, 168, 200), (246, 132, 176), (222, 96, 150)]  # 明・中・暗

# 文字の配置 (文字, 中心, 大きさ, 傾き, 登場時刻)
MAIN = [("主", (690, 385), 1.0, -9, 1.0), ("役", (935, 428), 0.82, 7, 1.14), ("級", (1185, 372), 1.06, -4, 1.28)]
NINARU = [("に", (1075, 610), 8, 1.85), ("な", (1190, 582), -11, 1.97), ("る", (1305, 620), 13, 2.09)]
UKETORE = [("受", (600, 800), -13, 2.45), ("け", (752, 842), 9, 2.58), ("取", (904, 796), -5, 2.71),
           ("れ", (1056, 846), 11, 2.84)]
HEART_POS, HEART_T = (1250, 812), 3.05


def ease_in_out(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def hump(u):
    return math.sin(math.pi * clamp01(u))


# ---------------------------------------------------------------- 文字
def sticker_text(ch, font, size, fill_t, fill_b, ring, line, extrude, outer=26, ring_w=17, line_w=7, gloss=0.4):
    """白フチ + 色フチ + 細フチ + 縦グラデ + ツヤ + 厚み の1文字."""
    f = ImageFont.truetype(font, size)
    S = int(size * 1.7)

    def mask(st):
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).text((S / 2, S / 2), ch, font=f, anchor="mm", fill=255, stroke_width=st, stroke_fill=255)
        return m
    m0, m1, m2, m3 = mask(0), mask(line_w), mask(ring_w), mask(outer)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    n = 12
    for k in range(n, 0, -1):
        im.paste(extrude + (255,), (round(extrude_dx * k / n), round(extrude_dy * k / n)), m3)
    im.paste(WHITE + (255,), (0, 0), m3)
    im.paste(ring + (255,), (0, 0), m2)
    im.paste(line + (255,), (0, 0), m1)
    bb = m0.getbbox()
    a = np.array(m0)
    g = np.zeros((S, S, 4), np.uint8)
    yy = np.clip((np.arange(S) - bb[1]) / (bb[3] - bb[1]), 0, 1)[:, None]
    for c in range(3):
        g[..., c] = (fill_t[c] * (1 - yy) + fill_b[c] * yy).astype(np.uint8)
    g[..., 3] = a
    im.alpha_composite(Image.fromarray(g, "RGBA"))
    if gloss:
        inner = np.array(m0.filter(ImageFilter.MinFilter(9))).astype(np.float32) / 255
        inner = np.roll(inner, 5, 0)
        fade = np.clip((0.5 - yy) / 0.3, 0, 1)
        hl = Image.fromarray(np.minimum((inner * fade * gloss * 255).astype(np.uint8), a))
        im.paste(WHITE + (255,), (0, 0), hl.filter(ImageFilter.GaussianBlur(1.5)))
    return im


extrude_dx, extrude_dy = 6, 14


def choco_heart_card(ch, font):
    """文字入りの2Dハートチョコ (ピンクのドリズル)."""
    r = 92
    S = int(r * 2.7)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    d.polygon(heart_poly(c + 5, c + 12, r + 12), fill=CHOCO_D)  # 厚み
    d.polygon(heart_poly(c, c, r + 12), fill=WHITE)
    d.polygon(heart_poly(c, c, r + 5), fill=PINK)
    d.polygon(heart_poly(c, c, r), fill=(112, 58, 38))
    # ドリズル (ハートの中だけ)
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon(heart_poly(c, c, r - 4), fill=255)
    dz = Image.new("L", (S, S), 0)
    dd = ImageDraw.Draw(dz)
    for k in range(5):
        y0 = c - r * 0.75 + k * r * 0.4
        pts = [(x, y0 + 0.45 * (x - c) + 10 * math.sin(x / 13 + k)) for x in range(0, S, 4)]
        dd.line(pts, fill=255, width=9)
    dz = Image.fromarray(np.minimum(np.array(dz), np.array(m)))
    im.paste((255, 170, 205, 255), (0, 0), dz)
    d.ellipse((c - r * 0.62, c - r * 0.58, c - r * 0.3, c - r * 0.3), fill=(176, 110, 82))
    f = ImageFont.truetype(font, 104)
    d.text((c + 3, c + 6), ch, font=f, anchor="mm", fill=CHOCO_D, stroke_width=9, stroke_fill=CHOCO_D)
    d.text((c, c), ch, font=f, anchor="mm", fill=WHITE, stroke_width=7, stroke_fill=PINK_D)
    return im


def crown():
    S = (300, 230)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = S[0] / 2

    def body(pad):
        return [(cx - 110 - pad, 175 + pad), (cx - 125 - pad, 60 - pad), (cx - 60, 120), (cx, 30 - pad * 1.4),
                (cx + 60, 120), (cx + 125 + pad, 60 - pad), (cx + 110 + pad, 175 + pad)]
    d.polygon(body(14), fill=WHITE)
    d.polygon(body(7), fill=GOLD_D)
    d.polygon(body(0), fill=GOLD)
    d.rounded_rectangle((cx - 118, 160, cx + 118, 200), 14, fill=WHITE)
    d.rounded_rectangle((cx - 112, 164, cx + 112, 196), 12, fill=GOLD_D)
    d.rounded_rectangle((cx - 108, 166, cx + 108, 190), 10, fill=GOLD)
    for x, y, r, col in ((cx - 125, 52, 16, PINK), (cx, 22, 20, BERRY_T), (cx + 125, 52, 16, PINK)):
        d.ellipse((x - r - 5, y - r - 5, x + r + 5, y + r + 5), fill=WHITE)
        d.ellipse((x - r, y - r, x + r, y + r), fill=col)
    d.polygon(heart_poly(cx, 135, 26), fill=WHITE)
    d.polygon(heart_poly(cx, 135, 20), fill=BERRY_T)
    for x in (cx - 70, cx + 70):
        d.ellipse((x - 9, 169, x + 9, 187), fill=PINK_L)
    d.line([(cx - 92, 72), (cx - 82, 145)], fill=(255, 236, 180), width=8)
    return im


def starburst(R=330, n=18):
    S = R * 2 + 20
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n
        r = R if i % 2 == 0 else R * 0.8
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=WHITE)
    pts2 = [(c + (x - c) * 0.96, c + (y - c) * 0.96) for x, y in pts]
    d.polygon(pts2, fill=(255, 214, 230))
    for i in range(n):  # 放射の帯
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 0.5) / n
        d.polygon([(c, c), (c + R * math.cos(a0), c + R * math.sin(a0)), (c + R * math.cos(a1), c + R * math.sin(a1))],
                  fill=(255, 236, 244))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).polygon(pts2, fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    d2 = ImageDraw.Draw(out)
    d2.polygon(pts, outline=WHITE, width=14)
    for i in range(n):  # 先っぽのドット
        a = 2 * math.pi * i / n
        x, y = c + R * 0.9 * math.cos(a), c + R * 0.9 * math.sin(a)
        d2.ellipse((x - 9, y - 9, x + 9, y + 9), fill=PINK)
    return out


# ---------------------------------------------------------------- 幕
def make_valance():
    """上の飾り幕: 波打つスワッグ + レース + リボン."""
    im = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 70), fill=CURTAIN[1])
    n = 5
    sw = W / n
    for i in range(n):
        x0, x1 = i * sw, (i + 1) * sw
        for pad, col in ((10, WHITE), (0, None)):
            pts = [(x0 - pad, 0)] + [(x0 + (x1 - x0) * u, 70 + 120 * math.sin(math.pi * u) + pad)
                                     for u in np.linspace(0, 1, 30)] + [(x1 + pad, 0)]
            d.polygon(pts, fill=col or CURTAIN[0])
        for k in (0.3, 0.55, 0.8):  # ひだ
            pts = [(x0 + (x1 - x0) * u, 60 + 120 * k * math.sin(math.pi * u)) for u in np.linspace(0.08, 0.92, 24)]
            d.line(pts, fill=CURTAIN[2], width=5)
        for u in np.linspace(0.03, 0.97, 16):  # レースのスカラップ
            x, y = x0 + (x1 - x0) * u, 70 + 120 * math.sin(math.pi * u)
            d.ellipse((x - 15, y - 4, x + 15, y + 22), fill=WHITE)
            d.ellipse((x - 4, y + 6, x + 4, y + 14), fill=PINK_L)
    for i in range(n + 1):  # 継ぎ目のリボン
        x = i * sw
        d.polygon([(x, 50), (x - 52, 18), (x - 58, 88)], fill=WHITE)
        d.polygon([(x, 50), (x + 52, 18), (x + 58, 88)], fill=WHITE)
        d.polygon([(x, 50), (x - 44, 26), (x - 48, 80)], fill=BERRY_T)
        d.polygon([(x, 50), (x + 44, 26), (x + 48, 80)], fill=BERRY_T)
        d.polygon([(x - 6, 50), (x - 30, 128), (x - 12, 120), (x - 2, 136), (x + 6, 52)], fill=BERRY_B)
        d.polygon([(x + 6, 50), (x + 30, 128), (x + 12, 120), (x + 2, 136), (x - 6, 52)], fill=BERRY_B)
        d.ellipse((x - 18, 32, x + 18, 68), fill=WHITE)
        d.ellipse((x - 12, 38, x + 12, 62), fill=BERRY_T)
    return im


def curtain_layer(o):
    """左右のカーテン. o=0 で閉じ (中央で合わさる), o=1 で開き (リボンで束ねた形)."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    y = yy[:, :1]
    # 開いたときの内側の縁: 上は広く、束ねた所 (y=640) で細く、下でまた少し広がる
    tie = 640
    e_open = np.where(y < tie, 430 - 170 * np.clip(y / tie, 0, 1) ** 1.6,
                      260 + 150 * np.clip((y - tie) / (H - tie), 0, 1) ** 0.8)
    e = CX - (CX - e_open) * o + 10 * np.sin(y / 38) * (0.4 + 0.6 * o) + 24 * (1 - o)  # 閉じたときは少し重ねる
    out = np.zeros((H, W, 4), np.uint8)
    for side in (0, 1):
        X = xx if side == 0 else W - 1 - xx
        inside = X < e
        u = X / np.maximum(e, 1)  # 0: 外側 → 1: 内側の縁
        sh = np.sin(u * math.pi * (9 + 5 * (1 - o)))  # ひだ
        col = np.where(sh[..., None] > 0.45, np.array(CURTAIN[0]),
                       np.where(sh[..., None] > -0.35, np.array(CURTAIN[1]), np.array(CURTAIN[2])))
        lace = (X >= e - 26) & (X < e)  # 縁のレース
        dots = lace & (((yy + (X - e) * 0) % 34) < 14) & (X > e - 18) & (X < e - 8)
        col = np.where(lace[..., None], np.array(WHITE), col)
        col = np.where(dots[..., None], np.array(PINK_L), col)
        edge = (X >= e - 34) & (X < e - 26)
        col = np.where(edge[..., None], np.array(CURTAIN[2]), col)
        m = inside
        out[m, :3] = col[m]
        out[m, 3] = 255
    im = Image.fromarray(out, "RGBA")
    if o > 0.6:  # 束ねるリボン
        k = ease_out_back((o - 0.6) / 0.4)
        d = ImageDraw.Draw(im)
        for side in (0, 1):
            ex = CX - (CX - 260) * o
            x = ex - 120 if side == 0 else W - ex + 120
            for pad, col in ((8, WHITE), (0, BERRY_T)):
                d.rounded_rectangle((x - 140 - pad, tie - 18 - pad, x + 140 + pad, tie + 18 + pad), 14, fill=col)
            r = 40 * k
            if r > 2:
                bx = x + (110 if side == 0 else -110)
                for pad, col in ((8, WHITE), (0, BERRY_T)):
                    d.polygon([(bx, tie), (bx - 2 * r - pad, tie - r - pad), (bx - 2 * r - pad, tie + r + pad)], fill=col)
                    d.polygon([(bx, tie), (bx + 2 * r + pad, tie - r - pad), (bx + 2 * r + pad, tie + r + pad)], fill=col)
                d.ellipse((bx - r * 0.5, tie - r * 0.5, bx + r * 0.5, tie + r * 0.5), fill=BERRY_B)
    return im


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, cache):
        self.main = [sticker_text(ch, font, round(210 * sc), BERRY_T, BERRY_B, GOLD, BERRY_D, BERRY_D)
                     for ch, _, sc, _, _ in MAIN]
        self.ninaru = [sticker_text(ch, font, 108, (255, 170, 206), (246, 112, 168), WHITE, CHOCO_D, PINK_D,
                                    outer=20, ring_w=14, line_w=7, gloss=0.35) for ch, *_ in NINARU]
        self.cards = [choco_heart_card(ch, font) for ch, *_ in UKETORE]
        self.crown = crown()
        self.burst = starburst()
        self.valance = make_valance()
        self.heart3d = Image.open(os.path.join(cache, "choco_heart_520_00.png")).convert("RGBA")
        self.hearts = {r: heart_sticker(r) for r in (16, 22, 30)}
        self.sp_w, self.sp_p = sparkle(24), sparkle(30, PINK, WHITE)
        rnd = random.Random(11)
        cols = [PINK, WHITE, GOLD, BERRY_T, PINK_L]
        self.confetti = []
        for i in range(46):
            c = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
            dc = ImageDraw.Draw(c)
            if i % 4 == 0:
                dc.polygon(heart_poly(20, 20, 13), fill=cols[i % 5])
            else:
                dc.rectangle((6, 13, 34, 27), fill=cols[i % 5])
            self.confetti.append(dict(im=c, x=rnd.uniform(380, W - 380), y0=rnd.uniform(-300, 500),
                                      v=rnd.uniform(120, 220), ph=rnd.random() * 6, r=rnd.uniform(0, 360),
                                      sw=rnd.uniform(20, 60)))
        self.twinkles = [(560, 250, "w", 0.0), (1380, 270, "p", 0.4), (470, 640, "p", 0.7), (1480, 560, "w", 0.2),
                         (820, 300, "w", 0.85), (1450, 900, "p", 0.55)]

    def curtain_open(self, t):
        if t >= CLOSE_T[0]:
            return 1 - ease_in_out((t - CLOSE_T[0]) / (CLOSE_T[1] - CLOSE_T[0]))
        return ease_in_out((t - OPEN_T[0]) / (OPEN_T[1] - OPEN_T[0]))

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idle = clamp01((t - 3.4) / 0.5)
        P = 2 * math.pi * t / 2.0
        beat = (hump((t % 1.0) / 0.12) * 0.09 + hump(((t % 1.0) - 0.18) / 0.12) * 0.06) * idle  # ドキドキ

        # スターバースト (ゆっくり回る)
        k = ease_out_back((t - 0.85) / 0.45, 1.8)
        if k > 0:
            put(im, self.burst, 945, 410, k * (1 + 0.02 * math.sin(P)), t * 12)
        # 紙吹雪 (奥のぶん)
        if t > 3.2:
            for j, c in enumerate(self.confetti[::2]):
                self._confetti(im, c, t, j)

        # 主役級: カードのようにくるっと裏返って登場
        for i, (ch, (x, y), sc, rot, t0) in enumerate(MAIN):
            u = (t - t0) / 0.42
            if u < 0:
                continue
            flip = math.cos(math.radians(180 * (1 - ease_out(u))))  # -1 → 1 (裏 → 表)
            sx = abs(flip) * (1 + spring(t - t0 - 0.42, 0.12, 20, 7))
            sy = 1 - spring(t - t0 - 0.42, 0.1, 20, 7)
            bob = idle * 10 * math.sin(P - i * 1.3)
            rr = rot + idle * 2.5 * math.sin(P * 0.7 + i * 2)
            s = 1 + 0.25 * hump(u * 0.6)
            put(im, self.main[i], x, y + bob - 40 * (1 - ease_out(u)), s, rr, max(0.02, sx), sy)
        # 王冠: 「級」に落ちてきて跳ねる
        if t > 1.62:
            u = clamp01((t - 1.62) / 0.3)
            _, (x, y), sc, rot, _ = MAIN[2]
            bob = idle * 10 * math.sin(P - 2 * 1.3)
            cy = y - 190 - 600 * (1 - u * u) - 40 * hump((t - 1.92) / 0.28) + bob
            cr = 14 + spring(t - 1.92, 12, 14, 5) + idle * 3 * math.sin(P * 0.7 + 4)
            put(im, self.crown, x + 30, cy, 0.95, cr)

        # になる: 右のカーテンの裏から、ぴょんぴょん跳ねて到着
        for i, (ch, (x, y), rot, t0) in enumerate(NINARU):
            u = (t - t0) / 0.45
            if u < 0:
                continue
            uu = clamp01(u)
            sx0 = x + 460
            px = sx0 + (x - sx0) * uu
            hop = 130 * abs(math.sin(uu * math.pi * 2)) * (1 - uu * 0.4)
            land = t - t0 - 0.45
            sq = spring(land, 0.18, 22, 8)
            r = rot + (1 - uu) * 40 + idle * 6 * math.sin(P * 1.2 + i * 1.7)
            idle_hop = idle * 14 * max(0, math.sin(P * 1.5 - i * 0.9)) ** 4
            put(im, self.ninaru[i], px, y - hop - idle_hop, 1, r, 1 + sq, 1 - sq)

        # 受け取れ: 奥 (画面中央) から手前へ投げつけられる
        for i, (ch, (x, y), rot, t0) in enumerate(UKETORE):
            u = (t - t0) / 0.32
            if u < 0:
                continue
            e = ease_out(u)
            px, py = 960 + (x - 960) * e, 520 + (y - 520) * e
            s = 0.12 + 0.88 * ease_out_back(u, 2.4)
            land = t - t0 - 0.32
            s *= 1 + spring(land, 0.1, 26, 9) + beat * 0.6
            r = rot + 360 * (1 - e) * (1 if i % 2 else -1) + idle * 5 * math.sin(P + i * 1.5)
            put(im, self.cards[i], px, py + idle * 6 * math.sin(P * 1.3 + i), s * 0.86, r)
            if 0 < land < 0.35:  # 当たった衝撃の線
                q = land / 0.35
                d = ImageDraw.Draw(im)
                for k2 in range(6):
                    a = 2 * math.pi * k2 / 6 + i
                    r0 = 125 + 70 * q
                    d.line([(x + r0 * math.cos(a), y + r0 * math.sin(a)),
                            (x + (r0 + 45 * (1 - q)) * math.cos(a), y + (r0 + 45 * (1 - q)) * math.sin(a))],
                           fill=WHITE if k2 % 2 else PINK, width=max(2, round(10 * (1 - q))))
        # 3Dのチョコハート (♥): ドキッと大きく出て、その後は脈打つ
        if t > HEART_T:
            u = (t - HEART_T) / 0.4
            s = 0.5 * (ease_out_back(u, 3.0) + spring(t - HEART_T - 0.4, 0.15, 18, 6)) * (1 + beat)
            x, y = HEART_POS
            put(im, self.heart3d, x, y, s, -12 + idle * 6 * math.sin(P))
            if 0 < t - HEART_T < 0.8:
                q = (t - HEART_T) / 0.8
                for k2 in range(8):
                    a = 2 * math.pi * k2 / 8
                    rr = 100 + 220 * ease_out(q)
                    put(im, self.hearts[(16, 22, 30)[k2 % 3]], x + rr * math.cos(a), y + rr * math.sin(a), 1 - q ** 2,
                        20 * k2)

        # 紙吹雪 (手前のぶん) とキラキラ
        if t > 3.2:
            for j, c in enumerate(self.confetti[1::2]):
                self._confetti(im, c, t, j + 100)
            for x, y, kind, ph in self.twinkles:
                q = ((t - 3.2) / 1.2 + ph) % 1
                s = hump(q / 0.45) ** 2
                put(im, self.sp_w if kind == "w" else self.sp_p, x, y, s * 1.2, 45 * q)

        # 幕 (いちばん手前)
        o = self.curtain_open(t)
        im.alpha_composite(curtain_layer(o))
        im.alpha_composite(self.valance)
        return im

    @staticmethod
    def _confetti(im, c, t, j):
        y = c["y0"] + c["v"] * (t - 3.2)
        if y > H + 40:
            return
        x = c["x"] + c["sw"] * math.sin(t * 2.2 + c["ph"])
        flip = abs(math.cos(t * 5 + c["ph"]))
        put(im, c["im"], x, y, 1, c["r"] + 140 * t, 1, max(0.15, flip))


SCENE = None


def _init(font, cache):
    global SCENE
    SCENE = Scene(font, cache)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Mochiy Pop One など丸い太字")
    ap.add_argument("--out", default="shuyakukyu_logo")
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    with Pool(a.jobs) as pool:
        R.build_sprites(pool, a.cache, {"choco_heart": (520, 60)})
    if a.preview is not None:
        _init(a.font, a.cache)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = round(DUR * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.cache)) as pool:
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
