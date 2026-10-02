"""「絶対零度」のタイトルロゴ動画 (チョコ × リボン × フリル × ロリータ) をグリーンバックで書き出す.

  python3 zettai_reido_logo.py --font MochiyPopOne.ttf --out clips/text/zettai_reido_logo [--cache cache3d]

構成 (1920x1080, 6秒):
  0.0-1.6  登場: 大文字が時間差でドンッ → むにっ + 集中線とハート → チョコが垂れる → 飾りが順にぽんぽん
  1.6-5.3  待機: 文字が1つずつずれて揺れる / ふりがなタイルに波 / ツヤが横切る / キラキラ
  5.3-6.0  退場: 飾り → 文字の順にしゅっと消える
クロマキー用に、緑系の色と半透明のぼかしは使わない。3Dのリボンとチョコハートは render3d.py のスプライト。
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import os
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import render3d as R

W, H, FPS, DUR = 1920, 1080, 30, 6.0
OUT_T = 5.3  # 退場の開始

WHITE = (255, 255, 255)
CREAM = (255, 246, 236)
PINK = (255, 128, 182)
PINK_L = (255, 190, 215)
PINK_D = (226, 78, 140)
CHOCO_T, CHOCO_B = (168, 98, 64), (96, 48, 32)
CHOCO_D = (66, 33, 24)
ICE = (150, 205, 255)

SPRITES = {"bow_pink": (300, 48), "choco_heart": (520, 60), "heart": (160, 36)}


# ---------------------------------------------------------------- イージング
def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_out_back(x, s=2.0):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_in_back(x, s=1.8):
    x = clamp01(x)
    return (s + 1) * x ** 3 - s * x ** 2


def spring(u, amp=1.0, f=22, k=8):
    """着地後の減衰振動 (u: 着地からの秒)."""
    return 0.0 if u < 0 else amp * math.exp(-u * k) * math.cos(u * f)


def out_scale(t, order):
    """退場: order が小さいものから先に縮んで消える."""
    return 1 - ease_in_back((t - OUT_T - order * 0.035) / 0.28)


# ---------------------------------------------------------------- 描画の道具
def put(dst, im, cx, cy, s=1.0, rot=0.0, sx=1.0, sy=1.0):
    """im を中心 (cx, cy) に、倍率 s (sx, sy で縦横の潰れ)・回転 rot で重ねる."""
    w, h = round(im.width * s * sx), round(im.height * s * sy)
    if w < 2 or h < 2:
        return
    q = im.resize((w, h), Image.LANCZOS) if (w, h) != im.size else im
    if rot:
        q = q.rotate(rot, Image.BICUBIC, expand=True)
    x, y = round(cx - q.width / 2), round(cy - q.height / 2)
    l, t = max(0, -x), max(0, -y)
    r, b = min(q.width, dst.width - x), min(q.height, dst.height - y)
    if r > l and b > t:
        dst.alpha_composite(q.crop((l, t, r, b)), (x + l, y + t))


def heart_poly(cx, cy, r, n=48):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((cx + x * r / 16, cy - y * r / 16))
    return pts


def heart_sticker(r, fill=PINK, edge=WHITE, line=PINK_D):
    S = int(r * 2.6)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    d.polygon(heart_poly(c, c, r + 7), fill=line)
    d.polygon(heart_poly(c, c, r + 4), fill=edge)
    d.polygon(heart_poly(c, c, r), fill=fill)
    d.ellipse((c - r * 0.55, c - r * 0.6, c - r * 0.2, c - r * 0.3), fill=WHITE)
    return im


def sparkle(r, fill=WHITE, edge=PINK):
    S = int(r * 2 + 14)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    for pad, col in ((5, edge), (0, fill)):
        R, q = r + pad, r * 0.2 + pad * 0.6
        d.polygon([(c, c - R), (c + q, c - q), (c + R, c), (c + q, c + q), (c, c + R), (c - q, c + q),
                   (c - R, c), (c - q, c - q)], fill=col)
    return im


def snowflake(r):
    S = int(r * 2 + 16)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    for wd, col in ((max(5, r * 0.3), ICE), (max(2, r * 0.13), WHITE)):
        for k in range(6):
            a = math.pi / 3 * k
            d.line([(c, c), (c + r * math.cos(a), c + r * math.sin(a))], fill=col, width=round(wd))
            bx, by = c + r * 0.55 * math.cos(a), c + r * 0.55 * math.sin(a)
            for s in (-1, 1):
                b = a + s * 0.8
                d.line([(bx, by), (bx + r * 0.3 * math.cos(b), by + r * 0.3 * math.sin(b))], fill=col,
                       width=round(wd))
        d.ellipse((c - wd, c - wd, c + wd, c + wd), fill=col)
    return im


# ---------------------------------------------------------------- 大文字 (チョコの板)
FS = 250
ST_WHITE, ST_PINK, ST_DARK = 30, 20, 8  # フチの太さ (文字の輪郭からの距離)
EXTRUDE = (5, 13)  # 厚みの方向と量 (x, y)


STYLES = {
    # いちごチョコ: ピンクの中身に白い水玉、チョコ色のフチ
    "ichigo": dict(top=(255, 184, 214), bot=(242, 104, 160), mid=(140, 76, 50), dots=True, gloss=(255, 236, 244)),
    # ミルクチョコ: チョコの中身、ピンクのフチ
    "milk": dict(top=CHOCO_T, bot=CHOCO_B, mid=PINK, dots=False, gloss=(255, 214, 196)),
}


class Letter:
    """チョコ板の大文字. 外側 (厚み・白・色フチ・こげ茶フチ) と中身 (グラデ・ツヤ) を分けて持ち、
    間にチョコの垂れを挟んで、垂れが文字の中身とつながって見えるようにする."""

    def __init__(self, ch, font, style):
        st = self.st = STYLES[style]
        S = int(FS * 1.75)
        self.S = S

        def mask(stroke):
            m = Image.new("L", (S, S), 0)
            ImageDraw.Draw(m).text((S / 2, S / 2 - 20), ch, font=font, anchor="mm", fill=255,
                                   stroke_width=stroke, stroke_fill=255)
            return m
        m_fill, m_dark, m_pink, m_white = mask(0), mask(ST_DARK), mask(ST_PINK), mask(ST_WHITE)
        outer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        n = 14
        for k in range(n, 0, -1):  # 厚み
            outer.paste(CHOCO_D + (255,), (round(EXTRUDE[0] * k / n), round(EXTRUDE[1] * k / n)), m_white)
        outer.paste(WHITE + (255,), (0, 0), m_white)
        outer.paste(st["mid"] + (255,), (0, 0), m_pink)
        outer.paste(CHOCO_D + (255,), (0, 0), m_dark)
        self.outer = outer
        self.bb = bb = m_fill.getbbox()
        a = np.array(m_fill)
        g = np.zeros((S, S, 4), np.uint8)
        yy = np.clip((np.arange(S) - bb[1]) / (bb[3] - bb[1]), 0, 1)[:, None]
        for c in range(3):
            g[..., c] = (st["top"][c] * (1 - yy) + st["bot"][c] * yy).astype(np.uint8)
        g[..., 3] = a
        fill = Image.fromarray(g, "RGBA")
        if st["dots"]:  # 白い水玉 (互い違い)
            dm = Image.new("L", (S, S), 0)
            dd = ImageDraw.Draw(dm)
            for j, yy0 in enumerate(range(0, S, 46)):
                for xx0 in range(-46, S, 46):
                    x = xx0 + (23 if j % 2 else 0)
                    dd.ellipse((x - 8, yy0 - 8, x + 8, yy0 + 8), fill=255)
            dm = Image.fromarray(np.minimum(np.array(dm), a))
            fill.paste(WHITE + (255,), (0, 0), dm)
        # 上側のツヤ: 文字を少し細らせて下へずらした形の、上のほうだけをなめらかに明るく
        inner = np.array(m_fill.filter(ImageFilter.MinFilter(11))).astype(np.float32) / 255
        inner = np.roll(inner, 6, 0)
        fade = np.clip((0.55 - yy) / 0.35, 0, 1)
        hl = Image.fromarray((inner * fade * 0.5 * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
        hl = Image.fromarray(np.minimum(np.array(hl), a))
        fill.paste(st["gloss"] + (255,), (0, 0), hl)
        self.fill = fill
        self.m_fill = m_fill
        # チョコが垂れる場所: 文字のいちばん下の画の、幅がある所を最大2か所
        low = np.where(a > 128, np.arange(S)[:, None], -1).max(0)
        lim = low.max() - 22
        segs, x = [], 0
        while x < S:
            if low[x] >= lim:
                x0 = x
                while x < S and low[x] >= lim:
                    x += 1
                if x - x0 >= 26:
                    segs.append((x0, x))
            x += 1
        segs.sort(key=lambda s: -(s[1] - s[0]))
        self.drips = []
        for x0, x1 in segs[:1]:  # 垂れは1本だけ。短くぷっくり
            cx = (x0 + x1) / 2
            w = min(34, (x1 - x0) * 0.6)
            self.drips.append((cx, int(low[int(cx)]) - 14, w, 46))

    def draw(self, drip_k, shine=None):
        """drip_k: 垂れの伸び (0-1), shine: ツヤの帯の位置 (0-1) か None."""
        im = self.outer.copy()
        if drip_k > 0.01:
            d = ImageDraw.Draw(im)
            for cx, y0, w, L in self.drips:
                ln = L * drip_k
                for pad, col in ((ST_WHITE, WHITE), (ST_PINK, self.st["mid"]), (ST_DARK, CHOCO_D), (0, None)):
                    c = col or self.st["bot"]
                    r = w * 0.72 + pad
                    d.rounded_rectangle((cx - w / 2 - pad, y0 - pad, cx + w / 2 + pad, y0 + ln + pad),
                                        radius=w / 2 + pad, fill=c)
                    d.ellipse((cx - r, y0 + ln - r, cx + r, y0 + ln + r), fill=c)
                d.ellipse((cx - w * 0.42, y0 + ln - w * 0.4, cx - w * 0.12, y0 + ln - w * 0.05), fill=self.st["gloss"])
        im.alpha_composite(self.fill)
        if shine is not None:
            band = Image.new("L", im.size, 0)
            bx = -0.4 * self.S + 1.8 * self.S * shine
            ImageDraw.Draw(band).polygon([(bx, 0), (bx + 60, 0), (bx - 160, self.S), (bx - 220, self.S)], fill=255)
            band = Image.fromarray(np.minimum(np.array(band), np.array(self.m_fill)) // 10 * 7)
            im.paste((255, 236, 228, 255), (0, 0), band)
        return im


# ---------------------------------------------------------------- 飾り
def ruby_tile(ch, font, choco):
    r = 34
    S = r * 2 + 16
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    d.ellipse((c - r - 6, c - r - 3, c + r + 6, c + r + 9), fill=CHOCO_D)  # 下の厚み
    d.ellipse((c - r - 6, c - r - 6, c + r + 6, c + r + 6), fill=WHITE)
    d.ellipse((c - r, c - r, c + r, c + r), fill=CHOCO_B if choco else PINK)
    d.text((c, c + 1), ch, font=ImageFont.truetype(font, 40), anchor="mm", fill=WHITE)
    return im


def lace_tag(font):
    """スカラップのレース札 (ドイリー) に「−273.15 °C」."""
    R = 150
    S = R * 2 + 60
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    n = 24
    for pad, col in ((8, PINK_D), (4, WHITE)):  # 波の縁
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = c + R * math.cos(a), c + R * math.sin(a)
            d.ellipse((x - 20 - pad, y - 20 - pad, x + 20 + pad, y + 20 + pad), fill=col)
        d.ellipse((c - R - pad, c - R - pad, c + R + pad, c + R + pad), fill=col)
    d.ellipse((c - R - 6, c - R - 6, c + R + 6, c + R + 6), fill=CREAM)
    for i in range(n):  # レースの穴
        a = 2 * math.pi * (i + 0.5) / n
        x, y = c + (R + 4) * math.cos(a), c + (R + 4) * math.sin(a)
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=PINK_L)
    for i in range(48):  # 点線のステッチ
        a = 2 * math.pi * i / 48
        x, y = c + (R - 22) * math.cos(a), c + (R - 22) * math.sin(a)
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=PINK)
    r2 = R - 38
    d.ellipse((c - r2, c - r2, c + r2, c + r2), fill=PINK_L)
    f1, f2 = ImageFont.truetype(font, 54), ImageFont.truetype(font, 46)
    d.text((c, c - 22), "−273.15", font=f1, anchor="mm", fill=CHOCO_B, stroke_width=5, stroke_fill=WHITE)
    d.text((c, c + 40), "°C", font=f2, anchor="mm", fill=PINK_D, stroke_width=5, stroke_fill=WHITE)
    for s in (-1, 1):  # 小さいハート
        d.polygon(heart_poly(c + s * 78, c + 42, 13), fill=WHITE)
        d.polygon(heart_poly(c + s * 78, c + 42, 9), fill=PINK)
    return im


class Banner:
    """レースのフリル付きリボン帯「ABSOLUTE ZERO」. 中心から左右に開く."""

    def __init__(self, font):
        self.text = "ABSOLUTE ZERO"
        self.f = ImageFont.truetype(font, 50)
        self.w, self.h = 660, 96
        self.S = (self.w + 260, self.h + 90)

    def draw(self, open_k, text_k, wave=0.0):
        im = Image.new("RGBA", self.S, (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        cx, cy = self.S[0] / 2, self.S[1] / 2
        hw = self.w / 2 * ease_out(open_k)
        h = self.h
        if hw < 4:
            return im
        if open_k >= 0.85:  # 後ろの折り返し + 燕尾のしっぽ
            k = ease_out_back((open_k - 0.85) / 0.15)
            for s in (-1, 1):
                x0 = cx + s * (hw - 30)
                x1 = cx + s * (hw + 100 * k)
                y0 = cy - h / 2 + 22
                pts = [(x0, y0), (x1, y0), (x1 - s * 34 * k, cy + 11 + 18), (x1, y0 + h), (x0, y0 + h)]
                d.polygon([(x + s * 0, y) for x, y in pts], fill=WHITE)
                inner = [(x0, y0 + 6), (x1 - s * 7, y0 + 6), (x1 - s * 34 * k - s * 2, cy + 29),
                         (x1 - s * 7, y0 + h - 6), (x0, y0 + h - 6)]
                d.polygon(inner, fill=PINK_D)
                d.polygon([(cx + s * (hw - 30), y0 + h - 6), (cx + s * hw, cy + h / 2), (cx + s * hw, y0 + h - 6)],
                          fill=CHOCO_D)
        # フリル (上下のスカラップ)
        for yy in (cy - h / 2, cy + h / 2):
            n = int(hw * 2 / 26) + 1
            for i in range(n):
                x = cx - hw + 13 + i * 26
                d.ellipse((x - 16, yy - 16, x + 16, yy + 16), fill=PINK_D)
            for i in range(n):
                x = cx - hw + 13 + i * 26
                d.ellipse((x - 13, yy - 13, x + 13, yy + 13), fill=WHITE)
        d.rectangle((cx - hw, cy - h / 2, cx + hw, cy + h / 2), fill=PINK)
        d.rectangle((cx - hw, cy - h / 2 + 8, cx + hw, cy - h / 2 + 14), fill=PINK_L)
        for i in range(int(hw * 2 / 22)):  # ステッチ
            x = cx - hw + 12 + i * 22
            d.rectangle((x, cy + h / 2 - 16, x + 10, cy + h / 2 - 12), fill=WHITE)
        # 文字は1文字ずつぽん
        n = len(self.text)
        total = self.f.getlength(self.text) + 6 * (n - 1)
        x = cx - total / 2
        for i, ch in enumerate(self.text):
            cw = self.f.getlength(ch)
            k = ease_out_back((text_k * (n + 5) - i) / 5)
            if k > 0.02 and ch != " ":
                g = Image.new("RGBA", (90, 110), (0, 0, 0, 0))
                ImageDraw.Draw(g).text((45, 55), ch, font=self.f, anchor="mm", fill=WHITE, stroke_width=6,
                                       stroke_fill=CHOCO_D)
                put(im, g, x + cw / 2, cy + 3 - 5 * math.sin(wave - i * 0.6), k)
            x += cw + 6
        return im


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, cache):
        f = ImageFont.truetype(font, FS)
        # 大文字の配置: 「絶対」を左上・「零度」を右下に段違いで (中心, 傾き, 登場時刻)
        self.letters = []
        rows = [("絶対", (760, 375), -5.0, 0.0, "ichigo"), ("零度", (1200, 680), 3.5, 0.24, "milk")]
        for word, (x0, y0), ang, t0, style in rows:
            a = math.radians(ang)
            for j, ch in enumerate(word):
                dx = (j - 0.5) * 290
                self.letters.append(dict(L=Letter(ch, f, style), x=x0 + dx * math.cos(a), y=y0 - dx * math.sin(a),
                                         rot=ang, t0=t0 + j * 0.12))
        self.ruby = []
        for word, (x0, y0), ang, t0, choco in (("ぜったい", (800, 185), -5.0, 0.62, True),
                                                 ("れいど", (1390, 500), 3.5, 0.80, False)):
            a = math.radians(ang)
            for j, ch in enumerate(word):
                dx = (j - (len(word) - 1) / 2) * 84
                self.ruby.append(dict(im=ruby_tile(ch, font, (j % 2 == 0) == choco), x=x0 + dx * math.cos(a),
                                      y=y0 - dx * math.sin(a), rot=ang + (-6, 5, -3, 6)[j % 4], t0=t0 + j * 0.05,
                                      i=len(self.ruby)))
        self.tag = lace_tag(font)
        self.banner = Banner(font)
        self.hearts = {r: heart_sticker(r) for r in (18, 26, 34)}
        self.heart_w = heart_sticker(22, fill=WHITE, edge=PINK, line=PINK_D)
        self.sp_w, self.sp_p = sparkle(22), sparkle(28, PINK, WHITE)
        self.sp_s = sparkle(14)
        self.flake = snowflake(26)
        os.makedirs(cache, exist_ok=True)
        self.spr = {}
        for name, (size, n) in SPRITES.items():
            paths = [os.path.join(cache, f"{name}_{size}_{i:02d}.png") for i in range(n)]
            self.spr[name] = [Image.open(p).convert("RGBA") for p in paths]
        # 待機中のキラキラ・ハート (位置, 種類, 周期のずれ)
        self.twinkles = [(420, 400, "w", 0.0), (1100, 200, "p", 0.35), (1600, 620, "w", 0.6), (1010, 560, "s", 0.15),
                         (1620, 960, "p", 0.75), (780, 960, "s", 0.5), (1700, 420, "s", 0.9), (380, 640, "w", 0.25)]
        self.floaters = [(560, 0.0, 26), (1500, 0.4, 18), (900, 0.7, 34), (1700, 0.2, 26), (380, 0.55, 18)]
        self.flakes = [(1250, 300, 0.1), (390, 930, 0.6), (1700, 780, 0.35)]

    def sprite(self, name, rev):
        seq = self.spr[name]
        return seq[int(math.floor(rev * len(seq))) % len(seq)]

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idle = clamp01((t - 1.5) / 0.6)
        P = 2 * math.pi * t / 2.4  # 待機の揺れの位相

        # 浮かんで消えるハート (いちばん奥)
        if t > 1.4:
            for x, ph, r in self.floaters:
                q = ((t - 1.4) / 2.2 + ph) % 1
                s = out_scale(t, 0) * min(1, q * 6) * (1 - clamp01((q - 0.8) / 0.2))
                put(im, self.hearts[r], x + 20 * math.sin(q * 7), 1000 - 260 * q, s, 12 * math.sin(q * 9))

        # 3Dのチョコハート (右上)
        k = ease_out_back((t - 1.05) / 0.45, 2.4) * out_scale(t, 2)
        if k > 0:
            put(im, self.sprite("choco_heart", 0.22 * t), 1570, 300 + 10 * math.sin(P + 1) * idle, 0.5 * k,
                8 * math.sin(P * 0.5))
        # 雪の結晶 (絶対零度らしさを少しだけ)
        for x, y, ph in self.flakes:
            k = ease_out_back((t - 1.2 - ph * 0.4) / 0.4) * out_scale(t, 1)
            if k > 0:
                put(im, self.flake, x, y + 8 * math.sin(P + ph * 6), k, 50 * t + ph * 100)

        # レースの札 (左下). くるっと回って入る
        k = ease_out_back((t - 0.9) / 0.5, 2.2) * out_scale(t, 3)
        if k > 0:
            spin = -200 * (1 - ease_out((t - 0.9) / 0.5))
            put(im, self.tag, 590, 770 + 6 * math.sin(P + 2) * idle, k, -9 + spin + 3 * math.sin(P * 0.5) * idle)

        # 大文字 (着地の集中線とハートも)
        for i, d in enumerate(self.letters):
            u = (t - d["t0"]) / 0.3
            if u < 0:
                continue
            land = t - d["t0"] - 0.3
            fall = ease_out(u)
            s = 1 + 1.3 * (1 - fall) ** 2  # 大きいところから落ちてくる
            sq = spring(land, 0.16)
            rot = d["rot"] + (1 - fall) * (-22 if i % 2 else 18) + spring(land, 4, 16, 6)
            x, y = d["x"], d["y"] - 40 * (1 - fall)
            y += idle * 9 * math.sin(P - i * 0.8)
            rot += idle * 1.6 * math.sin(P - i * 0.8 + 1.1)
            drip = ease_out_back((t - d["t0"] - 0.35) / 0.9, 1.2)
            shine = None
            for st in (2.3, 4.3):
                sh = (t - st - i * 0.07) / 0.55
                if 0 < sh < 1:
                    shine = sh
            o = out_scale(t, 6 + (3 - i % 4) + i // 4)
            if land > 0 and land < 0.5:  # 集中線
                q = land / 0.5
                d2 = ImageDraw.Draw(im)
                for k2 in range(8):
                    a = 2 * math.pi * k2 / 8 + i
                    r0, r1 = 175 + 120 * ease_out(q), 175 + 120 * ease_out(q) + 70 * (1 - q)
                    d2.line([(x + r0 * math.cos(a), y + r0 * math.sin(a)), (x + r1 * math.cos(a), y + r1 * math.sin(a))],
                            fill=PINK if k2 % 2 else WHITE, width=max(2, round(12 * (1 - q))))
            g = d["L"].draw(drip, shine)  # クロマキーで汚れないよう半透明にはしない
            put(im, g, x, y, s * o, rot, 1 + sq, 1 - sq)
            if 0 < land < 0.7:  # はじけるミニハート
                q = land / 0.7
                for k2 in range(3):
                    a = -math.pi / 2 + (k2 - 1) * 0.9 + i
                    rr = 190 + 110 * ease_out(q)
                    put(im, self.hearts[18], x + rr * math.cos(a), y + rr * math.sin(a) - 30 * q,
                        (1 - q) * 1.2, 20 * (k2 - 1))

        # ふりがなタイル (待機中は波のようにぴょこぴょこ)
        for d in self.ruby:
            k = ease_out_back((t - d["t0"]) / 0.32, 2.6) * out_scale(t, 4 + d["i"] * 0.3)
            if k <= 0:
                continue
            wave = ((t - 1.8) / 2.4 - d["i"] * 0.05) % 1
            hop = -18 * math.sin(clamp01(wave / 0.12) * math.pi) * idle if t > 1.8 else 0
            put(im, d["im"], d["x"], d["y"] + hop - 30 * (1 - min(1, k)), k, d["rot"])

        # リボン帯 (下)
        ob = clamp01((t - 1.0) / 0.45)
        if ob > 0:
            b = self.banner.draw(ob, clamp01((t - 1.25) / 0.6), P * 1.5)
            put(im, b, 1210, 975 + 5 * math.sin(P + 0.5) * idle, out_scale(t, 5), -2 + 1.2 * math.sin(P * 0.5) * idle)

        # 3Dのリボン (「絶」の左上). ぽんっと出て、ゆらゆら
        k = ease_out_back((t - 0.75) / 0.4, 2.6) * out_scale(t, 3.5)
        if k > 0:
            wig = spring(t - 0.75 - 0.4, 14, 14, 4) + 5 * math.sin(P * 0.8) * idle
            put(im, self.sprite("bow_pink", 0), 500, 225, 0.9 * k, 22 + wig)

        # キラキラ (ぱちっと)
        if t > 1.3:
            for x, y, kind, ph in self.twinkles:
                q = ((t - 1.3) / 1.2 + ph) % 1
                s = math.sin(clamp01(q / 0.4) * math.pi) ** 2 * out_scale(t, 0)
                spr = {"w": self.sp_w, "p": self.sp_p, "s": self.sp_s}[kind]
                put(im, spr, x, y, s * 1.2, 45 * q)
        return im


SCENE = None


def _init(font, cache):
    global SCENE
    SCENE = Scene(font, cache)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Mochiy Pop One など丸い太字")
    ap.add_argument("--out", default="zettai_reido_logo")
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    with Pool(a.jobs) as pool:
        R.build_sprites(pool, a.cache, SPRITES)
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
    Image.frombytes("RGBA", (W, H), frames[int(n * 0.5)]).save(a.out + ".png")
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
