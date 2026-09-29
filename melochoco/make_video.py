"""バレンタイン×ロリータ風 歌詞動画ジェネレーター.

使い方:
  python3 make_video.py --image illust.png --audio source.mov \
      --font-pop Dela.ttf --font-cute Hachi.ttf --out out.mp4
"""
import argparse
import math
import random
import subprocess
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30

# ---- パレット -------------------------------------------------------------
PINK = (255, 150, 195)
HOTPINK = (255, 92, 160)
BERRY = (196, 28, 92)
CHOCO = (74, 36, 24)
DARKCHOCO = (46, 22, 16)
CREAM = (255, 244, 226)
WHITE = (255, 255, 255)
GOLD = (236, 196, 120)

# ---- 歌詞タイムライン --------------------------------------------------------
# (開始, テキスト) の行をグループ単位で表示。グループ終了時に退場。
GROUPS = [
    dict(start=0.0, end=2.2, style="pop", rows=[(0.05, "める散らかして")]),
    dict(start=2.2, end=4.1, style="ribbon", rows=[(2.25, "吐き気催すまで")]),
    dict(start=4.1, end=7.25, style="pop",
         rows=[(4.1, "受け取れ"), (4.7, "メロディック"), (5.4, "チョコレート"), (6.2, "メンタル")]),
    dict(start=7.3, end=9.8, style="vert", rows=[(7.4, "お好み通り")]),
    dict(start=9.9, end=11.1, style="plate", rows=[(9.95, "型に流して")]),
    dict(start=11.1, end=12.0, style="plate", rows=[(11.15, "冷やして")]),
    dict(start=12.0, end=13.3, style="plate", rows=[(12.05, "できあがり")]),
    dict(start=13.6, end=16.65, style="pop",
         rows=[(13.7, "ハートに"), (14.6, "割れ目"), (15.15, "できませんように")]),
    dict(start=16.7, end=21.2, style="pop", icy=True,
         rows=[(16.7, "絶対零度で"), (17.85, "固めて"), (19.45, "とじこめる")]),
    dict(start=21.4, end=22.6, style="ribbon", rows=[(21.45, "しろくろリボン")]),
    dict(start=22.6, end=25.0, style="ribbon", rows=[(22.65, "強く結んだなら")]),
    dict(start=25.1, end=26.5, style="ribbon", rows=[(25.15, "できあがりよ")]),
    dict(start=26.5, end=28.4, style="ribbon", rows=[(26.55, "欲しいならあげる")]),
    dict(start=28.6, end=99, style="final", rows=[(28.6, "君を"), (29.3, "めろつかせちゃうぞ")]),
]

# 背景パターンの切り替え (開始秒, パターン名)
BG_SCHEDULE = [(0, "dots"), (4.1, "stripes"), (7.25, "hearts"), (9.85, "gingham"),
               (13.3, "dots"), (16.65, "hearts"), (21.2, "stripes"), (25.05, "gingham"),
               (28.5, "final")]
DRIP_WIPES = [13.3, 21.2, 28.5]  # チョコが垂れて画面を覆う転換


# ---- 汎用ヘルパー -----------------------------------------------------------
def heart_pts(cx, cy, s, n=80):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * s / 16, cy - y * s / 16))
    return pts


def ease_out_back(x):
    x = min(max(x, 0), 1)
    c1, c3 = 1.9, 2.9
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def supersample(w, h, draw_fn, k=2):
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), k)
    return im.resize((w, h), Image.LANCZOS)


def paste(dst, src, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if scale != 1.0:
        src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.BILINEAR)
    if rot:
        src = src.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1.0:
        a = src.getchannel("A").point(lambda v: int(v * alpha))
        src = src.copy()
        src.putalpha(a)
    _paste_clip(dst, src, int(cx - src.width / 2), int(cy - src.height / 2))


def _paste_clip(dst, src, x, y):
    l, t = max(0, -x), max(0, -y)
    r, b = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if r <= l or b <= t:
        return
    dst.alpha_composite(src.crop((l, t, r, b)), (x + l, y + t))


# ---- スプライト -------------------------------------------------------------
def make_heart(size, fill, edge=WHITE):
    def d(dr, k):
        s = size * k
        dr.polygon(heart_pts(s / 2, s / 2 + s * 0.04, s * 0.48), fill=edge)
        dr.polygon(heart_pts(s / 2, s / 2 + s * 0.04, s * 0.40), fill=fill)
        dr.ellipse([s * 0.28, s * 0.26, s * 0.38, s * 0.36], fill=(255, 255, 255, 170))
    return supersample(size, size, d, 3)


def make_bow(size, col, dark, stripe=True):
    def d(dr, k):
        s = size * k
        c = (s / 2, s * 0.42)
        # しっぽ
        for sx in (-1, 1):
            dr.polygon([c, (c[0] + sx * s * 0.12, c[1]), (c[0] + sx * s * 0.30, s * 0.95),
                        (c[0] + sx * s * 0.20, s * 0.86), (c[0] + sx * s * 0.14, s * 0.97)], fill=dark)
        # ループ
        for sx in (-1, 1):
            pts = [c, (c[0] + sx * s * 0.47, c[1] - s * 0.30), (c[0] + sx * s * 0.50, c[1]),
                   (c[0] + sx * s * 0.45, c[1] + s * 0.26)]
            dr.polygon(pts, fill=col, outline=dark)
            dr.line([pts[0], pts[1], pts[2], pts[3], pts[0]], fill=dark, width=max(1, int(s * 0.03)))
            if stripe:
                for j in (0.3, 0.6):
                    dr.line([(c[0] + sx * s * 0.08, c[1] - s * 0.04 * (1 - j)),
                             (c[0] + sx * s * 0.47 * j + sx * s * 0.08, c[1] - s * 0.28 * j)],
                            fill=(255, 255, 255, 200), width=max(1, int(s * 0.025)))
        r = s * 0.09
        dr.ellipse([c[0] - r, c[1] - r * 1.2, c[0] + r, c[1] + r * 1.2], fill=col, outline=dark,
                   width=max(1, int(s * 0.03)))
    return supersample(size, size, d, 3)


def make_choco(size):
    def d(dr, k):
        s = size * k
        dr.rounded_rectangle([s * .05, s * .05, s * .95, s * .95], radius=s * .1, fill=CHOCO)
        for i in range(2):
            for j in range(2):
                x0, y0 = s * (.12 + .42 * i), s * (.12 + .42 * j)
                dr.rounded_rectangle([x0, y0, x0 + s * .34, y0 + s * .34], radius=s * .05,
                                     fill=(110, 58, 38), outline=DARKCHOCO, width=int(2 * k))
    return supersample(size, size, d, 3)


def make_sparkle(size, col=WHITE):
    def d(dr, k):
        s = size * k
        c = s / 2
        dr.polygon([(c, 0), (c + s * .1, c - s * .1), (s, c), (c + s * .1, c + s * .1), (c, s),
                    (c - s * .1, c + s * .1), (0, c), (c - s * .1, c - s * .1)], fill=col)
    return supersample(size, size, d, 3)


def make_doily(size):
    """回転させるレースのドイリー (キャラ背面)."""
    def d(dr, k):
        s = size * k
        c = s / 2
        R = s * 0.49
        n = 36
        for i in range(n):  # 外周スカラップ
            a = 2 * math.pi * i / n
            x, y = c + math.cos(a) * R * 0.93, c + math.sin(a) * R * 0.93
            rr = R * 0.085
            dr.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 255, 255, 235))
        dr.ellipse([c - R * .93, c - R * .93, c + R * .93, c + R * .93], fill=(255, 255, 255, 235))
        for i in range(n):  # 穴あきレース
            a = 2 * math.pi * (i + .5) / n
            for rf, hr in ((0.86, .028), (0.76, .02)):
                x, y = c + math.cos(a) * R * rf, c + math.sin(a) * R * rf
                dr.ellipse([x - R * hr, y - R * hr, x + R * hr, y + R * hr], fill=(0, 0, 0, 0))
        dr.ellipse([c - R * .7, c - R * .7, c + R * .7, c + R * .7], outline=(255, 170, 205, 255),
                   width=int(5 * k))
        for i in range(24):  # 花びら模様
            a = 2 * math.pi * i / 24
            x, y = c + math.cos(a) * R * .6, c + math.sin(a) * R * .6
            dr.ellipse([x - R * .07, y - R * .07, x + R * .07, y + R * .07], fill=(255, 205, 225, 255))
        dr.ellipse([c - R * .52, c - R * .52, c + R * .52, c + R * .52], fill=(255, 240, 246, 255))
        dr.polygon(heart_pts(c, c + R * .03, R * .42), fill=(255, 190, 215, 255))
    im = supersample(size, size, d, 2)
    return im


def make_lace_strip(width, height, col=WHITE, holes=True):
    def d(dr, k):
        w, h = width * k, height * k
        n = int(width / 44)
        step = w / n
        dr.rectangle([0, 0, w, h * .45], fill=col)
        for i in range(n + 1):
            x = i * step
            dr.ellipse([x - step * .55, h * .1, x + step * .55, h * .95], fill=col)
            if holes:
                r = step * .12
                dr.ellipse([x - r, h * .5 - r, x + r, h * .5 + r], fill=(0, 0, 0, 0))
                dr.ellipse([x + step / 2 - r * .6, h * .25 - r * .6, x + step / 2 + r * .6, h * .25 + r * .6],
                           fill=(0, 0, 0, 0))
    return supersample(width, height, d, 2)


# ---- 背景パターン ------------------------------------------------------------
TILE = 120


def make_pattern(kind):
    pw, ph = W + TILE * 2, H + TILE * 2
    im = Image.new("RGB", (pw, ph))
    dr = ImageDraw.Draw(im)
    if kind == "dots":
        im.paste((255, 176, 208), (0, 0, pw, ph))
        for y in range(0, ph, TILE // 2):
            off = (y // (TILE // 2)) % 2 * TILE // 2
            for x in range(-TILE, pw, TILE):
                r = 15
                dr.ellipse([x + off - r, y - r, x + off + r, y + r], fill=(255, 128, 180))
    elif kind == "stripes":
        im.paste(BERRY, (0, 0, pw, ph))
        for x in range(-ph, pw, TILE // 2):
            dr.polygon([(x, 0), (x + 26, 0), (x + 26 + ph, ph), (x + ph, ph)], fill=(160, 16, 72))
            dr.line([(x + 40, 0), (x + 40 + ph, ph)], fill=(255, 150, 190), width=3)
    elif kind == "hearts":
        im.paste(DARKCHOCO, (0, 0, pw, ph))
        for y in range(0, ph, TILE // 2):
            off = (y // (TILE // 2)) % 2 * TILE // 2
            for x in range(-TILE, pw, TILE):
                dr.polygon(heart_pts(x + off, y, 16), fill=(98, 44, 40))
    elif kind == "gingham":
        im.paste((255, 236, 240), (0, 0, pw, ph))
        ov = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for x in range(0, pw, TILE // 2):
            od.rectangle([x, 0, x + TILE // 4, ph], fill=(255, 140, 185, 90))
        for y in range(0, ph, TILE // 2):
            od.rectangle([0, y, pw, y + TILE // 4], fill=(255, 140, 185, 90))
        im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    elif kind == "final":
        im.paste((40, 14, 24), (0, 0, pw, ph))
        cx, cy = pw / 2, ph / 2
        for i in range(24):  # 集中線
            a0 = 2 * math.pi * i / 24
            a1 = a0 + math.pi / 24
            R = 3000
            dr.polygon([(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R),
                        (cx + math.cos(a1) * R, cy + math.sin(a1) * R)], fill=(120, 20, 70))
    return im.convert("RGBA")


def make_glow_vignette():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    for i in range(40):  # 周辺減光
        a = int(4 + i * 2.2)
        dr.rectangle([i * 6, i * 6, W - i * 6, H - i * 6], outline=(40, 0, 20, max(0, 90 - a)), width=6)
    return im.filter(ImageFilter.GaussianBlur(20))


# ---- 固定フレーム装飾 (上部パール, 下部レース, 四隅リボン) ------------------
def make_frame_deco(bow_big):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 下部: ピンクのフリル + 白レース
    frill = make_lace_strip(W + 80, 110, (255, 120, 170, 255), holes=False)
    lace = make_lace_strip(W + 80, 80, (255, 255, 255, 255))
    im.alpha_composite(frill.transpose(Image.FLIP_TOP_BOTTOM), (-40, H - 110))
    im.alpha_composite(lace.transpose(Image.FLIP_TOP_BOTTOM), (-20, H - 72))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, H - 22, W, H], fill=CHOCO)
    for x in range(0, W, 28):  # ゴールドステッチ
        dr.line([(x, H - 12), (x + 14, H - 12)], fill=GOLD, width=3)
    # 上部: パールの連なり
    for i in range(0, W + 40, 34):
        y = 150 + 22 * math.sin(i / W * math.pi * 6)
        dr.ellipse([i - 11, y - 11, i + 11, y + 11], fill=(255, 250, 245), outline=(230, 190, 205), width=2)
    # 四隅のリボン
    for (x, y, rot) in ((120, 150, 18), (W - 120, 150, -18), (110, H - 150, -10), (W - 110, H - 150, 10)):
        paste(im, bow_big, x, y, 1.0, rot)
    return im


def draw_drips(t, base=70):
    """上から垂れるチョコ (ゆらゆら伸縮)."""
    k = 2
    h = 360
    im = Image.new("RGBA", (W * k, h * k), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, W * k, base * k], fill=CHOCO)
    rnd = random.Random(7)
    x = 0
    while x < W:
        w = rnd.uniform(40, 90)
        L = rnd.uniform(20, 130) * (0.8 + 0.25 * math.sin(t * rnd.uniform(0.8, 2.0) + rnd.random() * 6))
        cx = x + w / 2
        dr.rectangle([(cx - w * .3) * k, 0, (cx + w * .3) * k, (base + L) * k], fill=CHOCO)
        dr.ellipse([(cx - w * .3) * k, (base + L - w * .3) * k, (cx + w * .3) * k, (base + L + w * .3) * k],
                   fill=CHOCO)
        # くぼみ
        dr.ellipse([(x + w - w * .22) * k, (base - w * .2) * k, (x + w + w * .22) * k, (base + w * .2) * k],
                   fill=CHOCO)
        # ハイライト
        dr.line([((cx - w * .12) * k, (base + 6) * k), ((cx - w * .12) * k, (base + L - 6) * k)],
                fill=(140, 80, 60, 200), width=int(5 * k))
        x += w
    return im.resize((W, h), Image.BILINEAR)


def draw_drip_wipe(p):
    """p: 0..1 画面をチョコが上から覆い、下へ抜けていく."""
    if p <= 0 or p >= 1:
        return None
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rnd = random.Random(3)
    if p < 0.5:  # 覆う
        top, bot = -200, -200 + (H + 500) * ease_out(p * 2)
    else:  # 抜ける
        top, bot = (H + 300) * ((p - 0.5) * 2) ** 1.6 - 150, H + 400
    dr.rectangle([0, top, W, bot], fill=DARKCHOCO)
    x = 0
    while x < W:
        w = rnd.uniform(60, 140)
        L = rnd.uniform(40, 200)
        cx = x + w / 2
        dr.rectangle([cx - w * .35, bot - 5, cx + w * .35, bot + L], fill=DARKCHOCO)
        dr.ellipse([cx - w * .35, bot + L - w * .35, cx + w * .35, bot + L + w * .35], fill=DARKCHOCO)
        x += w * 0.8
    for i in range(10):  # ハート抜き
        hx, hy = rnd.uniform(100, W - 100), rnd.uniform(top + 100, min(bot, H) - 50) if bot - top > 200 else -999
        dr.polygon(heart_pts(hx, hy, rnd.uniform(20, 50)), fill=(120, 40, 60, 255))
    return im


# ---- 文字スプライト ---------------------------------------------------------
_cache = {}


def char_sprite(ch, font_path, size, fill, s1, s2, s3=None):
    key = (ch, font_path, size, fill, s1, s2, s3)
    if key in _cache:
        return _cache[key]
    f = ImageFont.truetype(font_path, size)
    pad = int(size * 0.45)
    dim = size + pad * 2
    im = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    c = (dim / 2, dim / 2)
    # 影
    sh = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((c[0] + size * .06, c[1] + size * .08), ch, font=f, anchor="mm",
                            fill=(60, 0, 30, 170), stroke_width=int(size * .2), stroke_fill=(60, 0, 30, 170))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(size * .04)))
    dr = ImageDraw.Draw(im)
    if s3:
        dr.text(c, ch, font=f, anchor="mm", fill=s3, stroke_width=int(size * .2), stroke_fill=s3)
    dr.text(c, ch, font=f, anchor="mm", fill=s2, stroke_width=int(size * .14), stroke_fill=s2)
    dr.text(c, ch, font=f, anchor="mm", fill=fill, stroke_width=int(size * .07), stroke_fill=s1)
    # 上半分に艶
    gl = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    ImageDraw.Draw(gl).text(c, ch, font=f, anchor="mm", fill=(255, 255, 255, 110))
    mask = Image.new("L", (dim, dim), 0)
    ImageDraw.Draw(mask).rectangle([0, 0, dim, c[1] - size * .05], fill=255)
    gl.putalpha(Image.fromarray(np.minimum(np.array(gl.getchannel("A")), np.array(mask))))
    im.alpha_composite(gl)
    _cache[key] = im
    return im


# ---- リボンバナー / ハートプレート -------------------------------------------
def make_ribbon_banner(width):
    h = 170
    total = width + 160

    def d(dr, k):
        W2, H2 = total * k, h * k
        y0, y1 = H2 * .22, H2 * .78
        # 端の二股しっぽ
        for sx, x in ((1, 0), (-1, W2)):
            dr.polygon([(x, y0 + 20 * k), (x + sx * 110 * k, y0 + 20 * k), (x + sx * 110 * k, y1 + 20 * k),
                        (x, y1 + 20 * k), (x + sx * 40 * k, (y0 + y1) / 2 + 20 * k)], fill=(28, 12, 10))
        dr.rectangle([70 * k, y0, W2 - 70 * k, y1], fill=(30, 14, 12))
        # フリル
        n = int(total / 26)
        for i in range(n + 1):
            x = 70 * k + (W2 - 140 * k) * i / n
            r = 16 * k
            dr.ellipse([x - r, y0 - r, x + r, y0 + r * .6], fill=(255, 140, 185))
            dr.ellipse([x - r, y1 - r * .6, x + r, y1 + r], fill=(255, 140, 185))
        dr.rectangle([70 * k, y0, W2 - 70 * k, y1], fill=(30, 14, 12))
        for x in range(int(80 * k), int(W2 - 80 * k), int(24 * k)):  # ステッチ
            dr.line([(x, y0 + 10 * k), (x + 12 * k, y0 + 10 * k)], fill=GOLD, width=int(3 * k))
            dr.line([(x, y1 - 10 * k), (x + 12 * k, y1 - 10 * k)], fill=GOLD, width=int(3 * k))
    return supersample(total, h, d, 2)


def make_plate(size):
    def d(dr, k):
        s = size * k
        c = s / 2
        for i in range(30):  # レース縁
            a = 2 * math.pi * i / 30
            x, y = c + math.cos(a) * s * .44, c + math.sin(a) * s * .44
            dr.ellipse([x - s * .05, y - s * .05, x + s * .05, y + s * .05], fill=(255, 255, 255))
        dr.ellipse([s * .06, s * .06, s * .94, s * .94], fill=(255, 255, 255), outline=(40, 20, 30),
                   width=int(6 * k))
        dr.ellipse([s * .14, s * .14, s * .86, s * .86], outline=(255, 150, 190), width=int(4 * k))
        dr.polygon(heart_pts(c, c + s * .03, s * .34), fill=(255, 225, 236))
        dr.polygon(heart_pts(c, c + s * .03, s * .30), fill=(92, 44, 32))
    return supersample(size, size, d, 2)


# ---- アセット構築 (fork 前にグローバルで作る) --------------------------------
A = {}


def build_assets(args):
    ch = Image.open(args.image).convert("RGBA")
    ch = ch.crop(ch.getbbox())
    sc = 1000 / ch.height
    A["char"] = ch.resize((int(ch.width * sc), int(ch.height * sc)), Image.LANCZOS)
    # キャラを背景から浮かせる影
    pad = 60
    shadow = Image.new("RGBA", (A["char"].width + pad * 2, A["char"].height + pad * 2), (0, 0, 0, 0))
    sil = Image.new("RGBA", A["char"].size, (90, 10, 50, 0))
    sil.putalpha(A["char"].getchannel("A").point(lambda v: min(255, v * 0.8)))
    shadow.alpha_composite(sil, (pad, pad))
    A["char_shadow"] = shadow.filter(ImageFilter.GaussianBlur(22))
    A["pat"] = {k: make_pattern(k) for k in ("dots", "stripes", "hearts", "gingham", "final")}
    A["vig"] = make_glow_vignette()
    A["doily"] = make_doily(1150)
    A["bow_big"] = make_bow(230, (210, 30, 90), (90, 10, 40))
    A["frame"] = make_frame_deco(A["bow_big"])
    A["hearts"] = [make_heart(s, c) for s, c in ((60, HOTPINK), (44, BERRY), (50, (255, 200, 220)),
                                                  (36, (230, 20, 80)), (70, (255, 120, 170)))]
    A["bows"] = [make_bow(80, (255, 120, 170), (160, 30, 80)), make_bow(70, (250, 250, 250), (60, 30, 30)),
                 make_bow(64, (40, 20, 20), (0, 0, 0), stripe=False)]
    A["choco"] = make_choco(56)
    A["spark"] = [make_sparkle(40), make_sparkle(28, (255, 230, 150))]
    A["plate"] = make_plate(820)
    A["fpop"], A["fcute"] = args.font_pop, args.font_cute
    # オーディオの音量エンベロープ → 拍ごとのパルス
    raw = subprocess.run([args.ffmpeg, "-v", "error", "-i", args.audio, "-vn", "-ac", "1", "-ar", "11025",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    spf = 11025 // FPS
    n = len(a) // spf
    rms = np.sqrt((a[: n * spf].reshape(n, spf) ** 2).mean(1))
    rms = rms / (np.percentile(rms, 95) + 1e-6)
    onset = np.maximum(0, np.diff(rms, prepend=rms[0]))
    onset = onset / (np.percentile(onset, 97) + 1e-6)
    pulse = np.zeros(n)
    for i in range(n):
        pulse[i] = max(min(onset[i], 1.5), pulse[i - 1] * 0.78 if i else 0)
    A["pulse"] = np.clip(pulse, 0, 1.5)
    A["nframes"] = n
    # パーティクル
    rnd = random.Random(42)
    parts = []
    for i in range(46):
        kind = rnd.choice(["heart"] * 5 + ["bow"] * 2 + ["choco"] * 2 + ["spark"] * 2)
        parts.append(dict(kind=kind, idx=rnd.randrange(8), x=rnd.uniform(0, W), y0=rnd.uniform(0, H),
                          vy=rnd.uniform(40, 130), sway=rnd.uniform(20, 60), fr=rnd.uniform(.5, 1.5),
                          rot=rnd.uniform(-30, 30), vr=rnd.uniform(-60, 60), sc=rnd.uniform(.6, 1.2)))
    A["parts"] = parts


# ---- 描画 -------------------------------------------------------------------
def bg_at(t):
    cur = BG_SCHEDULE[0]
    for s in BG_SCHEDULE:
        if t >= s[0]:
            cur = s
    return cur


def text_style(group):
    if group.get("icy"):
        return (WHITE, (40, 60, 120), (150, 220, 255), WHITE)
    if group["style"] == "final":
        return (CREAM, CHOCO, HOTPINK, WHITE)
    return (CREAM, CHOCO, HOTPINK, WHITE)


def layout_row(text, cx, cy, max_w, size_max):
    size = int(min(size_max, max_w / max(len(text), 1)))
    return size, [(cx + (i - (len(text) - 1) / 2) * size * 0.98, cy) for i in range(len(text))]


def draw_group(im, g, t, gi, pulse):
    if t < g["start"] - 0.05 or t > g["end"] + 0.25:
        return
    out = 0.0 if t <= g["end"] else (t - g["end"]) / 0.25  # 退場 0..1
    fill, s1, s2, s3 = text_style(g)
    style = g["style"]
    rnd = random.Random(gi * 101)
    LX = 600  # テキストエリア中心 x (右はキャラ)

    if style == "ribbon":
        text = g["rows"][0][1]
        size = int(min(96, 900 / len(text)))
        bw = int(len(text) * size * 1.02 + 60)
        key = ("banner", bw)
        if key not in _cache:
            _cache[key] = make_ribbon_banner(bw)
        ban = _cache[key]
        slide = ease_out((t - g["start"]) / 0.3)
        bx = -ban.width / 2 + (LX + ban.width / 2) * slide
        by = 790 + 6 * math.sin(t * 3)
        paste(im, ban, bx, by, 1.0, 2 * math.sin(t * 2 + gi), 1 - out)
        pos = [(bx + (i - (len(text) - 1) / 2) * size * 1.02, by) for i in range(len(text))]
        rows = [(g["rows"][0][0], text, size, pos, A["fcute"], (CREAM, (120, 20, 60), HOTPINK, None))]
    elif style == "plate":
        text = g["rows"][0][1]
        pin = ease_out_back((t - 9.85) / 0.35)
        paste(im, A["plate"], LX, 520, pin * (1 + 0.03 * pulse) * (1 - out * 0.2 if g["end"] >= 13 else 1),
              4 * math.sin(t * 1.5), 1 - (out if g["end"] >= 13 else 0))
        size, pos = layout_row(text, LX, 530, 470, 115)
        rows = [(g["rows"][0][0], text, size, pos, A["fcute"],
                 (CREAM, (70, 20, 30), (255, 110, 170), WHITE))]
    elif style == "vert":
        text = g["rows"][0][1]
        size = 150
        rows = [(g["rows"][0][0], text, size,
                 [(LX - 120 + (i % 2) * 40, 170 + i * size * 1.0) for i in range(len(text))], A["fpop"],
                 (fill, s1, s2, s3))]
        # 縦書きの横に小さいハート列
        for i in range(6):
            paste(im, A["hearts"][i % 5], LX + 170, 200 + i * 130 + 10 * math.sin(t * 4 + i), 1.0,
                  10 * math.sin(t * 3 + i), 1 - out)
    elif style == "final":
        rows = []
        sz = 280
        rows.append((g["rows"][0][0], "君を", sz, [(360, 360), (360 + sz, 360)], A["fpop"], (fill, s1, s2, s3)))
        text = g["rows"][1][1]
        size = 160
        pos = []
        for i in range(len(text)):
            if i < 5:
                pos.append((230 + i * 165, 640 + 30 * math.sin(i * 1.4)))
            else:
                pos.append((330 + (i - 5) * 165, 840 + 30 * math.sin(i * 1.4)))
        rows.append((g["rows"][1][0], text, size, pos, A["fpop"], (fill, s1, s2, s3)))
    else:  # pop
        n = len(g["rows"])
        rows = []
        gap = 190 if n <= 3 else 170
        top = 540 - gap * (n - 1) / 2
        for ri, (st, text) in enumerate(g["rows"]):
            max_size = 200 if n == 1 else 170
            size, pos = layout_row(text, LX + (ri % 2 * 2 - 1) * 30 * (n > 1), top + ri * gap, 1050, max_size)
            rows.append((st, text, size, pos, A["fpop"], (fill, s1, s2, s3)))

    # 各行の文字をポップ
    for ri, (st, text, size, pos, font, cols) in enumerate(rows):
        # その行の次の行開始まで (または終了) を歌唱区間とする
        nxt = rows[ri + 1][0] if ri + 1 < len(rows) else min(g["end"], st + 2.4)
        span = max(0.25, min(nxt - st, 2.0) * 0.75)
        if style == "final" and ri == 1:
            span = 1.3
        for i, ch in enumerate(text):
            if ch == " ":
                continue
            ti = st + span * i / max(len(text), 1)
            lt = t - ti
            if lt < 0:
                continue
            sc = ease_out_back(lt / 0.2) * (1 + 0.06 * pulse)
            rot = rnd.uniform(-9, 9) + 3 * math.sin(t * 2.4 + i * .7)
            x, y = pos[i]
            y += 8 * math.sin(t * 3 + i * .8)
            if style == "final":
                x += rnd.uniform(-1, 1) * 6 * pulse * math.sin(t * 40 + i)
                y += rnd.uniform(-1, 1) * 6 * pulse * math.cos(t * 37 + i)
            spr = char_sprite(ch, font, size, *cols)
            paste(im, spr, x, y - (1 - min(lt / 0.2, 1)) * 40, sc * (1 - out * .4), rot + out * 25, 1 - out)


def render(fi):
    t = fi / FPS
    pulse = float(A["pulse"][min(fi, len(A["pulse"]) - 1)])
    bt, bname = bg_at(t)
    pat = A["pat"][bname]
    off = int((t * 60) % TILE)
    im = pat.crop((off, off, off + W, off + H)).copy() if bname != "final" else \
        pat.rotate(t * 25, Image.BILINEAR, center=(W / 2 + TILE, H / 2 + TILE)).crop((TILE, TILE, TILE + W, TILE + H))

    # キャラ背面: ドイリー + 大ハート
    dcx, dcy = 1360, 560
    paste(im, A["doily"], dcx, dcy, 0.95 + 0.03 * pulse, t * 12)
    bh = make_heart_cached(560, (255, 90, 150))
    paste(im, bh, dcx, dcy + 10, 1 + 0.08 * pulse, 0, 0.9)

    # パーティクル (背面側 前半)
    draw_particles(im, t, 0, 23)

    # キャラ (ふわふわ)
    cy = 560 + 14 * math.sin(t * 1.6)
    paste(im, A["char_shadow"], 1360 + 18, cy + 26, 1.0, 2.0 * math.sin(t * 1.1), 0.8)
    paste(im, A["char"], 1360 + 6 * math.sin(t * 0.9), cy, 1.0 + 0.012 * pulse, 2.0 * math.sin(t * 1.1))

    # 歌詞
    for gi, g in enumerate(GROUPS):
        draw_group(im, g, t, gi, pulse)

    # パーティクル (前面)
    draw_particles(im, t, 23, 46)

    # フレーム装飾
    im.alpha_composite(draw_drips(t), (0, 0))
    im.alpha_composite(A["frame"])
    im.alpha_composite(A["vig"])
    draw_title(im)

    # 切替フラッシュ
    for s, _ in BG_SCHEDULE[1:]:
        if 0 <= t - s < 0.18:
            a = int(160 * (1 - (t - s) / 0.18))
            im.alpha_composite(Image.new("RGBA", (W, H), (255, 230, 240, a)))
    for s in DRIP_WIPES:
        wp = draw_drip_wipe((t - (s - 0.35)) / 0.7)
        if wp is not None:
            im.alpha_composite(wp)
    # 終わりのフェード
    end_t = A["nframes"] / FPS
    if t > end_t - 0.4:
        a = int(255 * min(1, (t - (end_t - 0.4)) / 0.4))
        im.alpha_composite(Image.new("RGBA", (W, H), (30, 10, 16, a)))
    return im.convert("RGB").tobytes()


def make_heart_cached(size, col):
    key = ("bigheart", size, col)
    if key not in _cache:
        _cache[key] = make_heart(size, col, (255, 255, 255))
    return _cache[key]


def draw_particles(im, t, a, b):
    for p in A["parts"][a:b]:
        y = (p["y0"] + p["vy"] * t) % (H + 160) - 80
        x = p["x"] + p["sway"] * math.sin(t * p["fr"] + p["y0"])
        rot = p["rot"] + p["vr"] * t
        if p["kind"] == "heart":
            spr = A["hearts"][p["idx"] % len(A["hearts"])]
        elif p["kind"] == "bow":
            spr = A["bows"][p["idx"] % len(A["bows"])]
        elif p["kind"] == "choco":
            spr = A["choco"]
        else:
            spr = A["spark"][p["idx"] % 2]
            p_sc = p["sc"] * (0.6 + 0.4 * abs(math.sin(t * 5 + p["x"])))
            paste(im, spr, x, y, p_sc, rot)
            continue
        paste(im, spr, x, y, p["sc"], rot)


def draw_title(im):
    key = "title"
    if key not in _cache:
        lab = Image.new("RGBA", (520, 90), (0, 0, 0, 0))
        dr = ImageDraw.Draw(lab)
        dr.rounded_rectangle([10, 10, 510, 80], radius=35, fill=(255, 255, 255, 230), outline=HOTPINK, width=5)
        f = ImageFont.truetype(A["fcute"], 36)
        dr.text((260, 46), "♡ めろチョコ ♡ 歌ってみた ♡", font=f, anchor="mm", fill=BERRY)
        _cache[key] = lab
    im.alpha_composite(_cache[key], (W - 560, 20))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--font-pop", required=True)
    ap.add_argument("--font-cute", required=True)
    ap.add_argument("--out", default="out.mp4")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--preview", type=float, nargs="*", help="指定秒のPNGだけ書き出す")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    build_assets(args)

    if args.preview:
        for s in args.preview:
            Image.frombytes("RGB", (W, H), render(int(s * FPS))).save(f"preview_{s:05.2f}.png")
        return

    enc = subprocess.Popen([args.ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", args.audio,
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                            "-movflags", "+faststart", args.out], stdin=subprocess.PIPE)
    with Pool(args.jobs) as pool:
        for i, fr in enumerate(pool.imap(render, range(A["nframes"]), chunksize=4)):
            enc.stdin.write(fr)
            if i % 60 == 0:
                print(f"frame {i}/{A['nframes']}", flush=True)
    enc.stdin.close()
    enc.wait()


if __name__ == "__main__":
    main()
