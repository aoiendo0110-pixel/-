"""ロリータ×お菓子の装飾パーツ (フリル・レース・キルティング・チョコ垂れ・カード枠・可愛い文字)."""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from make_video import heart_pts, supersample

PINK = (255, 150, 195)
LPINK = (255, 214, 228)
HOTPINK = (255, 92, 160)
RED = (220, 28, 62)
DRED = (150, 12, 40)
BROWN = (96, 50, 32)
DBROWN = (58, 28, 18)
YELLOW = (255, 214, 90)
GOLD = (236, 186, 70)
WHITE = (255, 255, 255)
CREAM = (255, 247, 236)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def vgrad(w, h, top, bot):
    g = np.linspace(0, 1, h)[:, None, None]
    arr = np.array(top, np.float32) * (1 - g) + np.array(bot, np.float32) * g
    arr = np.repeat(arr, w, 1)
    if arr.shape[-1] == 3:
        arr = np.concatenate([arr, np.full((h, w, 1), 255)], -1)
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def pearl(r, col=(255, 248, 250)):
    def d(dr, k):
        R = r * k
        dr.ellipse([0, 0, 2 * R, 2 * R], fill=lerp(col, (220, 190, 205), 0.5))
        dr.ellipse([R * 0.12, R * 0.08, R * 1.84, R * 1.76], fill=col)
        dr.ellipse([R * 0.45, R * 0.35, R * 0.95, R * 0.8], fill=(255, 255, 255))
    return supersample(2 * r, 2 * r, d, 3)


def gem_heart(s, col=RED):
    def d(dr, k):
        S = s * k
        dr.polygon(heart_pts(S / 2, S / 2 + S * .04, S * .5), fill=GOLD)
        dr.polygon(heart_pts(S / 2, S / 2 + S * .04, S * .4), fill=col)
        dr.polygon(heart_pts(S / 2 - S * .05, S / 2 - S * .02, S * .22), fill=lerp(col, WHITE, .35))
        dr.ellipse([S * .3, S * .28, S * .42, S * .38], fill=WHITE)
    return supersample(s, s, d, 3)


# ---- フリル ----------------------------------------------------------------
def frill(width, height, col, trim=None, n=None, flip=False):
    """ひだ付きフリル. 上端が縫い付け側、下端が波打つ."""
    n = n or max(4, int(width / 70))

    def d(dr, k):
        w, h = width * k, height * k
        sw = w / n
        dark = lerp(col, (60, 0, 20), 0.28)
        light = lerp(col, WHITE, 0.35)
        dr.rectangle([0, 0, w, h * 0.35], fill=col)
        for i in range(n + 1):
            x = i * sw
            dr.ellipse([x - sw * 0.62, h * 0.05, x + sw * 0.62, h], fill=col)
        for i in range(n + 1):  # ひだの影
            x = i * sw
            for j, off in enumerate((-0.28, 0.0, 0.28)):
                xx = x + off * sw
                dr.line([(xx, h * 0.02), (xx + off * sw * 0.2, h * 0.9)], fill=dark if j != 1 else light,
                        width=max(1, int(sw * 0.07)))
        for i in range(n + 1):  # 裾の縁取り
            x = i * sw
            dr.arc([x - sw * 0.62, h * 0.05, x + sw * 0.62, h], 20, 160, fill=trim or light,
                   width=max(2, int(h * 0.07)))
    im = supersample(width, height, d, 2)
    return im.transpose(Image.FLIP_TOP_BOTTOM) if flip else im


def lace(width, height, col=WHITE):
    def d(dr, k):
        w, h = width * k, height * k
        n = max(4, int(width / 40))
        sw = w / n
        dr.rectangle([0, 0, w, h * 0.42], fill=col)
        for i in range(n + 1):
            x = i * sw
            dr.ellipse([x - sw * .55, h * .1, x + sw * .55, h * .95], fill=col)
            r = sw * .13
            dr.ellipse([x - r, h * .55 - r, x + r, h * .55 + r], fill=(0, 0, 0, 0))
            for a in range(6):  # 花の透かし
                ang = a * math.pi / 3
                cx, cy = x + sw / 2 + math.cos(ang) * sw * .14, h * .22 + math.sin(ang) * sw * .14
                rr = sw * .06
                dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(0, 0, 0, 0))
        for x in range(0, int(w), int(12 * k)):
            dr.ellipse([x, h * .02, x + 5 * k, h * .02 + 5 * k], fill=(0, 0, 0, 0))
    return supersample(width, height, d, 2)


def stitch_band(width, height, col, stitch=GOLD):
    im = Image.new("RGBA", (width, height), col + (255,))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, width, 4], fill=lerp(col, WHITE, .3))
    for x in range(0, width, 26):
        for y in (int(height * .25), int(height * .75)):
            dr.line([(x, y), (x + 13, y)], fill=stitch, width=3)
    for x in range(40, width, 160):
        paste_c(im, gem_heart(int(height * .8)), x, height / 2)
    return im


def paste_c(dst, src, cx, cy):
    dst.alpha_composite(src, (int(cx - src.width / 2), int(cy - src.height / 2))) if (
        cx - src.width / 2 >= 0 and cy - src.height / 2 >= 0 and cx + src.width / 2 <= dst.width
        and cy + src.height / 2 <= dst.height) else _clip(dst, src, int(cx - src.width / 2), int(cy - src.height / 2))


def _clip(dst, src, x, y):
    l, t = max(0, -x), max(0, -y)
    r, b = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if r > l and b > t:
        dst.alpha_composite(src.crop((l, t, r, b)), (x + l, y + t))


# ---- チョコ垂れ ------------------------------------------------------------
def choco_drips(width, height, seed=7, base=60, col=BROWN, t=0.0):
    k = 2
    im = Image.new("RGBA", (width * k, height * k), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rnd = random.Random(seed)
    hi = lerp(col, (255, 200, 170), 0.35)
    dr.rectangle([0, 0, width * k, base * k], fill=col)
    x = 0
    drips = []
    while x < width:
        w = rnd.uniform(40, 95)
        L = rnd.uniform(20, height - base - 30) * (0.85 + 0.15 * math.sin(t * rnd.uniform(1, 2) + rnd.random() * 6))
        cx = x + w / 2
        drips.append((cx, w, L))
        dr.rectangle([(cx - w * .28) * k, 0, (cx + w * .28) * k, (base + L) * k], fill=col)
        dr.ellipse([(cx - w * .28) * k, (base + L - w * .28) * k, (cx + w * .28) * k, (base + L + w * .28) * k],
                   fill=col)
        dr.ellipse([(x + w - w * .2) * k, (base - w * .18) * k, (x + w + w * .2) * k, (base + w * .18) * k], fill=col)
        x += w
    for cx, w, L in drips:  # ツヤ
        dr.line([((cx - w * .12) * k, (base * .5) * k), ((cx - w * .12) * k, (base + L - 4) * k)], fill=hi,
                width=int(6 * k))
        dr.ellipse([(cx - w * .16) * k, (base + L - 2) * k, (cx - w * .04) * k, (base + L + 10) * k], fill=WHITE)
    dr.line([(0, 14 * k), (width * k, 14 * k)], fill=hi, width=int(5 * k))
    return im.resize((width, height), Image.LANCZOS)


# ---- 背景パターン ------------------------------------------------------------
def quilt(pw, ph, base, stitch, stud=True, s=110):
    """キルティング柄 (ひし形がぷっくり + ステッチ + パール)."""
    im = Image.new("RGBA", (pw, ph), lerp(base, (0, 0, 0), .15) + (255,))
    dr = ImageDraw.Draw(im)
    for j in range(-1, ph // (s // 2) + 2):
        for i in range(-1, pw // s + 2):
            cx = i * s + (j % 2) * s / 2
            cy = j * s / 2
            for q in range(7):  # 中央ほど明るく
                f = 1 - q / 7
                c = lerp(lerp(base, (0, 0, 0), .15), lerp(base, WHITE, .3), q / 6)
                h = s / 2 * f
                dr.polygon([(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)], fill=c)
    for j in range(-1, ph // (s // 2) + 2):  # ステッチ
        for i in range(-1, pw // s + 2):
            cx = i * s + (j % 2) * s / 2
            cy = j * s / 2
            pts = [(cx, cy - s / 2), (cx + s / 2, cy), (cx, cy + s / 2), (cx - s / 2, cy), (cx, cy - s / 2)]
            for a, b in zip(pts, pts[1:]):
                for u in np.arange(0.06, 1, 0.16):
                    x0, y0 = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
                    x1, y1 = a[0] + (b[0] - a[0]) * (u + .08), a[1] + (b[1] - a[1]) * (u + .08)
                    dr.line([(x0, y0), (x1, y1)], fill=stitch, width=3)
    if stud:
        p = pearl(9)
        for j in range(-1, ph // (s // 2) + 2):
            for i in range(-1, pw // s + 2):
                paste_c(im, p, i * s + (j % 2) * s / 2, j * s / 2 + s / 2)
    return im


def gingham(pw, ph, base, stripe, step=100, hearts=None):
    im = Image.new("RGBA", (pw, ph), base + (255,))
    for vertical in (True, False):
        ov = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for v in range(0, pw if vertical else ph, step):
            od.rectangle([v, 0, v + step // 2, ph] if vertical else [0, v, pw, v + step // 2], fill=stripe)
        im = Image.alpha_composite(im, ov)
    if hearts:
        dr = ImageDraw.Draw(im)
        for y in range(step // 4, ph, step):
            for x in range(step * 3 // 4, pw, step):
                dr.polygon(heart_pts(x, y, 11), fill=hearts)
    return im


def candy_stripe(pw, ph, cols=(RED, WHITE, PINK, WHITE), w=46):
    im = Image.new("RGBA", (pw, ph), WHITE + (255,))
    dr = ImageDraw.Draw(im)
    i = 0
    for x in range(-ph, pw + ph, w):
        c = cols[i % len(cols)]
        dr.polygon([(x, 0), (x + w, 0), (x + w + ph, ph), (x + ph, ph)], fill=c)
        i += 1
    for x in range(-ph, pw + ph, w * 4):
        dr.line([(x, 0), (x + ph, ph)], fill=GOLD, width=4)
    return im


def polka(pw, ph, base, dot, r=16, step=64, hearts=None):
    im = Image.new("RGBA", (pw, ph), base + (255,))
    dr = ImageDraw.Draw(im)
    for yi, y in enumerate(range(0, ph + step, step // 2)):
        for x in range(-step, pw + step, step):
            ox = x + (yi % 2) * step // 2
            if hearts and (yi + x // step) % 3 == 0:
                dr.polygon(heart_pts(ox, y, r * 1.2), fill=hearts)
            else:
                dr.ellipse([ox - r, y - r, ox + r, y + r], fill=dot)
    return im


def rays(size, c0, c1, n=32, center=None):
    im = Image.new("RGBA", (size, size), c0 + (255,))
    dr = ImageDraw.Draw(im)
    c = size / 2
    for i in range(n):
        a0 = 2 * math.pi * i / n
        a1 = a0 + math.pi / n
        dr.polygon([(c, c), (c + math.cos(a0) * size, c + math.sin(a0) * size),
                    (c + math.cos(a1) * size, c + math.sin(a1) * size)], fill=c1)
    if center:
        g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse([c - 500, c - 500, c + 500, c + 500], fill=center)
        im.alpha_composite(g.filter(ImageFilter.GaussianBlur(160)))
    return im


# ---- カード枠 (ウィンドウの代わり) ------------------------------------------
def card(w, h, col=PINK, bow=None, label=None, font=None):
    """スカラップのレース縁 + ステッチ + 上にリボンのカード枠. 中身の場所は透明."""
    pad = 70
    W2, H2 = w + pad * 2, h + pad * 2
    im = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad + 8, pad + 16, pad + w + 8, pad + h + 16], radius=30,
                                         fill=(110, 20, 50, 130))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))

    def d(dr, k):
        x0, y0, x1, y1 = (pad - 26) * k, (pad - 26) * k, (pad + w + 26) * k, (pad + h + 26) * k
        r = 18 * k
        # レースのスカラップ
        for x in np.arange(x0, x1, r * 1.6):
            for y in (y0, y1):
                dr.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)
        for y in np.arange(y0, y1, r * 1.6):
            for x in (x0, x1):
                dr.ellipse([x - r, y - r, x + r, y + r], fill=WHITE)
        dr.rounded_rectangle([x0, y0, x1, y1], radius=int(30 * k), fill=WHITE)
        dr.rounded_rectangle([(pad - 14) * k, (pad - 14) * k, (pad + w + 14) * k, (pad + h + 14) * k],
                             radius=int(26 * k), fill=col)
        dark = lerp(col, (80, 0, 30), .3)
        for x in np.arange((pad - 4) * k, (pad + w + 4) * k, 18 * k):
            for y in ((pad - 7) * k, (pad + h + 7) * k):
                dr.line([(x, y), (x + 9 * k, y)], fill=WHITE, width=int(3 * k))
        for y in np.arange((pad - 4) * k, (pad + h + 4) * k, 18 * k):
            for x in ((pad - 7) * k, (pad + w + 7) * k):
                dr.line([(x, y), (x, y + 9 * k)], fill=WHITE, width=int(3 * k))
        for (cx, cy) in ((x0 + 6 * k, y0 + 6 * k), (x1 - 6 * k, y0 + 6 * k), (x0 + 6 * k, y1 - 6 * k),
                         (x1 - 6 * k, y1 - 6 * k)):
            dr.polygon(heart_pts(cx, cy, 20 * k), fill=GOLD)
            dr.polygon(heart_pts(cx, cy, 14 * k), fill=RED)
        dr.rounded_rectangle([pad * k, pad * k, (pad + w) * k, (pad + h) * k], radius=int(16 * k), fill=dark)
    fr = supersample(W2, H2, d, 2)
    im.alpha_composite(fr)
    arr = np.asarray(im).copy()
    arr[pad + 4:pad + h - 4, pad + 4:pad + w - 4, 3] = 0
    im = Image.fromarray(arr)
    if label and font:
        f = ImageFont.truetype(font, 30)
        tw = int(f.getlength(label)) + 60
        tag = Image.new("RGBA", (tw, 56), (0, 0, 0, 0))
        td = ImageDraw.Draw(tag)
        td.rounded_rectangle([0, 0, tw - 1, 55], radius=28, fill=WHITE, outline=RED, width=4)
        td.text((tw / 2, 28), label, font=f, anchor="mm", fill=RED)
        paste_c(im, tag, pad + 40 + tw / 2, pad + h + 8)
    if bow is not None:
        paste_c(im, bow, W2 / 2, pad - 10)
    return im, (pad, pad, pad + w, pad + h)


# ---- 可愛い文字 ------------------------------------------------------------
STYLES = {
    "berry": dict(top=(255, 255, 255), bot=(255, 150, 190), stroke=RED, outer=WHITE, shadow=(140, 10, 50), dots=True),
    "choco": dict(top=(170, 100, 65), bot=(70, 34, 20), stroke=(255, 130, 175), outer=WHITE, shadow=(90, 20, 40)),
    "lemon": dict(top=(255, 252, 220), bot=(255, 200, 60), stroke=BROWN, outer=WHITE, shadow=(150, 70, 30)),
    "milk": dict(top=(255, 255, 255), bot=(255, 228, 240), stroke=HOTPINK, outer=RED, shadow=(120, 0, 40)),
    "cherry": dict(top=(255, 120, 150), bot=(200, 10, 50), stroke=WHITE, outer=(110, 20, 40), shadow=(60, 0, 20),
                   dots=True),
}


def cute_char(ch, size, style, font):
    st = STYLES[style]
    pad = int(size * 0.5)
    dim = size + pad * 2
    c = (dim / 2, dim / 2)
    f = ImageFont.truetype(font, size)
    im = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    # 影
    sh = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((c[0] + size * .05, c[1] + size * .09), ch, font=f, anchor="mm",
                            fill=st["shadow"] + (200,), stroke_width=int(size * .2), stroke_fill=st["shadow"] + (200,))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(size * .025)))
    dr = ImageDraw.Draw(im)
    dr.text(c, ch, font=f, anchor="mm", fill=st["outer"], stroke_width=int(size * .2), stroke_fill=st["outer"])
    dr.text(c, ch, font=f, anchor="mm", fill=st["stroke"], stroke_width=int(size * .11), stroke_fill=st["stroke"])
    # グラデーション塗り
    m = Image.new("L", (dim, dim), 0)
    ImageDraw.Draw(m).text(c, ch, font=f, anchor="mm", fill=255, stroke_width=int(size * .03), stroke_fill=255)
    bb = m.getbbox() or (0, 0, dim, dim)
    g = vgrad(dim, dim, st["top"], st["top"])
    g.paste(vgrad(dim, max(1, bb[3] - bb[1]), st["top"], st["bot"]), (0, bb[1]))
    g.paste(st["bot"] + (255,), (0, bb[3], dim, dim))
    if st.get("dots"):
        gd = ImageDraw.Draw(g)
        r = max(2, size * .03)
        for y in range(0, dim, int(size * .3)):
            for x in range(0, dim, int(size * .3)):
                ox = x + (y // int(size * .3)) % 2 * size * .15
                gd.ellipse([ox - r, y - r, ox + r, y + r], fill=(255, 255, 255, 220))
    im.paste(g, (0, 0), m)
    # ツヤ
    gl = Image.new("L", (dim, dim), 0)
    ImageDraw.Draw(gl).ellipse([bb[0] - size * .2, bb[1] - size * .7, bb[2] + size * .1, bb[1] + (bb[3] - bb[1]) * .45],
                               fill=90)
    gl = gl.filter(ImageFilter.GaussianBlur(size * .06))
    gl = Image.fromarray(np.minimum(np.asarray(gl), np.asarray(m)))
    im.paste((255, 255, 255, 255), (0, 0), gl)
    if st.get("drip"):
        dr = ImageDraw.Draw(im)
        rnd = random.Random(ord(ch))
        for _ in range(2):
            x = rnd.uniform(bb[0] + size * .15, bb[2] - size * .15)
            L = rnd.uniform(size * .12, size * .3)
            w = size * .07
            dr.rounded_rectangle([x - w, bb[3] - size * .1, x + w, bb[3] + L], radius=int(w), fill=st["bot"])
    return im


def bubble(ch, size, font, col=RED, rim=WHITE, txt=WHITE, txt_stroke=DRED):
    """ハートのチョコプレート風の吹き出し + 文字."""
    s = int(size * 1.55)

    def d(dr, k):
        c = s * k / 2
        dr.polygon(heart_pts(c + 3 * k, c + s * k * .09, s * k * .49), fill=(100, 10, 40, 160))
        dr.polygon(heart_pts(c, c + s * k * .05, s * k * .49), fill=rim)
        dr.polygon(heart_pts(c, c + s * k * .05, s * k * .42), fill=col)
        dr.polygon(heart_pts(c - s * k * .06, c, s * k * .2), fill=lerp(col, WHITE, .25))
        dr.ellipse([c - s * k * .28, c - s * k * .27, c - s * k * .17, c - s * k * .17], fill=WHITE)
    im = supersample(s, s, d, 2)
    f = ImageFont.truetype(font, int(size * 0.66))
    ImageDraw.Draw(im).text((s / 2, s / 2 + size * .03), ch, font=f, anchor="mm", fill=txt,
                            stroke_width=max(2, int(size * .06)), stroke_fill=txt_stroke)
    return im


def banner(width, font=None):
    """赤いサテンのリボンバナー (レースのフリル付き)."""
    h = 190
    total = width + 200

    def d(dr, k):
        W2, H2 = total * k, h * k
        y0, y1 = H2 * .24, H2 * .76
        for sx, x in ((1, 0), (-1, W2)):  # 二股のしっぽ
            dr.polygon([(x, y0 + 26 * k), (x + sx * 140 * k, y0 + 26 * k), (x + sx * 140 * k, y1 + 26 * k),
                        (x, y1 + 26 * k), (x + sx * 50 * k, (y0 + y1) / 2 + 26 * k)], fill=DRED)
        n = int(total / 30)
        for i in range(n + 1):  # 上下のレース
            x = 90 * k + (W2 - 180 * k) * i / n
            r = 17 * k
            dr.ellipse([x - r, y0 - r * 1.1, x + r, y0 + r * .5], fill=WHITE)
            dr.ellipse([x - r, y1 - r * .5, x + r, y1 + r * 1.1], fill=WHITE)
        dr.rectangle([90 * k, y0, W2 - 90 * k, y1], fill=RED)
        dr.rectangle([90 * k, y0, W2 - 90 * k, y0 + (y1 - y0) * .35], fill=(238, 60, 92))
        dr.rectangle([90 * k, y1 - (y1 - y0) * .18, W2 - 90 * k, y1], fill=(190, 16, 50))
        for x in np.arange(100 * k, W2 - 100 * k, 26 * k):
            dr.line([(x, y0 + 9 * k), (x + 13 * k, y0 + 9 * k)], fill=YELLOW, width=int(3 * k))
            dr.line([(x, y1 - 9 * k), (x + 13 * k, y1 - 9 * k)], fill=YELLOW, width=int(3 * k))
    return supersample(total, h, d, 2)


def sprinkles(w, h, n, seed=1):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rnd = random.Random(seed)
    for _ in range(n):
        x, y = rnd.uniform(0, w), rnd.uniform(0, h)
        a = rnd.uniform(0, math.pi)
        L = rnd.uniform(8, 14)
        col = rnd.choice([WHITE, YELLOW, RED, PINK, BROWN])
        dr.line([(x - math.cos(a) * L, y - math.sin(a) * L), (x + math.cos(a) * L, y + math.sin(a) * L)], fill=col,
                width=7)
    return im


def star(size, col=YELLOW):
    def d(dr, k):
        s = size * k
        c = s / 2
        pts = []
        for i in range(10):
            r = s * (.5 if i % 2 == 0 else .22)
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((c + math.cos(a) * r, c + math.sin(a) * r))
        dr.polygon(pts, fill=WHITE)
        pts2 = [(c + (x - c) * .78, c + (y - c) * .78) for x, y in pts]
        dr.polygon(pts2, fill=col)
    return supersample(size, size, d, 3)


def twinkle(size, col=(255, 250, 220)):
    def d(dr, k):
        s = size * k
        c = s / 2
        dr.polygon([(c, 0), (c + s * .08, c - s * .08), (s, c), (c + s * .08, c + s * .08), (c, s),
                    (c - s * .08, c + s * .08), (0, c), (c - s * .08, c - s * .08)], fill=col)
    return supersample(size, size, d, 3)
