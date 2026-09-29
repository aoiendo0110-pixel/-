"""めろチョコ MV風 歌詞動画ジェネレーター (カメラワーク + ウィンドウUI + 3Dオブジェクト).

使い方:
  python3 make_mv.py --image illust.png --audio source.mov \
      --font-pop Dela.ttf --font-cute Hachi.ttf --out mv.mp4
"""
import argparse
import math
import random
import subprocess
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import render3d
from make_video import (FPS, H, W, char_sprite, ease_out, ease_out_back, heart_pts, make_bow, make_doily,
                        make_ribbon_banner, make_sparkle, paste, supersample)

PINK = (255, 150, 195)
HOTPINK = (255, 92, 160)
BERRY = (196, 28, 92)
CHOCO = (74, 36, 24)
DARKCHOCO = (46, 22, 16)
CREAM = (255, 244, 226)
WHITE = (255, 255, 255)

# イラスト上の注目ポイント (元画像 1440x1080 の座標)
FACE = (915, 285)
WHISK = (1300, 290)
CHEST = (830, 545)
LEGS = (660, 690)
SHOES = (330, 850)
FULL = (720, 540)

A = {}
_c = {}


def cached(key, fn):
    if key not in _c:
        _c[key] = fn()
    return _c[key]


def ease_io(x):
    x = min(max(x, 0), 1)
    return x * x * (3 - 2 * x)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


# ---- カメラ ----------------------------------------------------------------
def cam(sx, sy, zoom, rot=0.0, out=(W, H)):
    """元イラストの (sx, sy) を中心に zoom 倍で out サイズに切り出す."""
    src = A["char2"]
    k = 2 / zoom
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    ow, oh = out
    a, b, d, e = k * c, -k * s, k * s, k * c
    return src.transform(out, Image.AFFINE, (a, b, 2 * sx - a * ow / 2 - b * oh / 2,
                                             d, e, 2 * sy - d * ow / 2 - e * oh / 2), Image.BILINEAR)


def tint(im, rgb, amt):
    arr = np.asarray(im).astype(np.float32)
    arr[..., :3] = arr[..., :3] * (1 - amt) + np.array(rgb, np.float32) * amt * (arr[..., :3] / 255 * 0.6 + 0.4)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), im.mode)


def desat(im, amt):
    arr = np.asarray(im).astype(np.float32)
    g = arr[..., :3].mean(-1, keepdims=True) * 1.08
    arr[..., :3] = arr[..., :3] * (1 - amt) + g * amt
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8), im.mode)


# ---- 背景 ------------------------------------------------------------------
PAD = 240


def make_bgs():
    bgs = {}
    pw, ph = W + PAD * 2, H + PAD * 2

    def gingham(base, stripe, step=120):
        im = Image.new("RGBA", (pw, ph), base)
        ov = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        for x in range(0, pw, step):
            od.rectangle([x, 0, x + step // 2, ph], fill=stripe)
        for y in range(0, ph, step):
            od.rectangle([0, y, pw, y + step // 2], fill=stripe)
        return Image.alpha_composite(im, ov)

    bgs["gingham"] = gingham((255, 222, 234, 255), (255, 150, 190, 90))
    bgs["gingham_cream"] = gingham((255, 246, 236, 255), (255, 175, 200, 80))
    im = Image.new("RGBA", (pw, ph), (255, 182, 212, 255))
    dr = ImageDraw.Draw(im)
    for y in range(0, ph, 60):
        for x in range(-120, pw, 120):
            ox = x + (y // 60) % 2 * 60
            dr.ellipse([ox - 16, y - 16, ox + 16, y + 16], fill=(255, 135, 185))
    bgs["dots"] = im
    im = Image.new("RGBA", (pw, ph), DARKCHOCO + (255,))
    dr = ImageDraw.Draw(im)
    for y in range(0, ph, 70):
        for x in range(-140, pw, 140):
            ox = x + (y // 70) % 2 * 70
            dr.polygon(heart_pts(ox, y, 18), fill=(100, 44, 42))
    bgs["choco"] = im
    im = Image.new("RGBA", (pw, ph), BERRY + (255,))
    dr = ImageDraw.Draw(im)
    for x in range(-ph, pw, 70):
        dr.polygon([(x, 0), (x + 30, 0), (x + 30 + ph, ph), (x + ph, ph)], fill=(160, 16, 72))
    bgs["stripes"] = im
    im = Image.new("RGBA", (pw, ph), (250, 250, 250, 255))
    dr = ImageDraw.Draw(im)
    for x in range(-ph, pw, 120):
        dr.polygon([(x, 0), (x + 60, 0), (x + 60 + ph, ph), (x + ph, ph)], fill=(28, 24, 26))
    bgs["mono"] = im
    # 氷: グラデーション
    g = np.linspace(0, 1, ph)[:, None]
    top, bot = np.array([30, 40, 100]), np.array([175, 215, 255])
    arr = (top * (1 - g) + bot * g)[:, None, :].repeat(pw, 1)
    im = Image.fromarray(np.concatenate([arr, np.full((ph, pw, 1), 255)], -1).astype(np.uint8), "RGBA")
    bgs["ice"] = im
    # 集中線 (ピンク / ダーク)
    for name, c0, c1 in (("burst", (255, 170, 205), (255, 110, 170)), ("final", (40, 12, 30), (120, 20, 80))):
        size = 2600
        im = Image.new("RGBA", (size, size), c0 + (255,))
        dr = ImageDraw.Draw(im)
        for i in range(28):
            a0 = 2 * math.pi * i / 28
            a1 = a0 + math.pi / 28
            dr.polygon([(size / 2, size / 2), (size / 2 + math.cos(a0) * 2000, size / 2 + math.sin(a0) * 2000),
                        (size / 2 + math.cos(a1) * 2000, size / 2 + math.sin(a1) * 2000)], fill=c1)
        bgs[name] = im
    return bgs


def bg(name, t, vx=50, vy=25, rot_speed=0.0):
    im = A["bg"][name]
    if name in ("burst", "final"):
        r = im.rotate(t * rot_speed, Image.BILINEAR)
        c = r.width // 2
        return r.crop((c - W // 2, c - H // 2, c + W // 2, c + H // 2))
    ox = int((t * vx) % 120) + PAD // 2
    oy = int((t * vy) % 120) + PAD // 2
    return im.crop((ox, oy, ox + W, oy + H))


def make_silhouettes():
    """背景に漂う白いシルエット (ハート・リボン・パール)."""
    im = Image.new("RGBA", (W + 600, H + 600), (0, 0, 0, 0))
    rnd = random.Random(5)
    bow = make_bow(200, (255, 255, 255), (255, 255, 255), stripe=False)
    dr = ImageDraw.Draw(im)
    for i in range(34):
        x, y = rnd.uniform(0, im.width), rnd.uniform(0, im.height)
        k = rnd.random()
        if k < 0.45:
            dr.polygon(heart_pts(x, y, rnd.uniform(40, 110)), fill=(255, 255, 255, 110))
        elif k < 0.7:
            paste(im, bow, x, y, rnd.uniform(0.5, 1.0), rnd.uniform(-30, 30), 0.45)
        else:
            r = rnd.uniform(10, 26)
            for j in range(5):
                dr.ellipse([x + j * r * 2.2 - r, y - r, x + j * r * 2.2 + r, y + r], fill=(255, 255, 255, 110))
    return im.filter(ImageFilter.GaussianBlur(3))


def make_bokeh():
    im = Image.new("RGBA", (W + 400, H + 400), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    rnd = random.Random(9)
    for i in range(26):
        x, y, r = rnd.uniform(0, im.width), rnd.uniform(0, im.height), rnd.uniform(30, 110)
        col = rnd.choice([(255, 255, 255, 60), (255, 180, 215, 70), (255, 220, 170, 50)])
        if rnd.random() < 0.5:
            dr.ellipse([x - r, y - r, x + r, y + r], fill=col)
        else:
            dr.polygon(heart_pts(x, y, r), fill=col)
    return im.filter(ImageFilter.GaussianBlur(10))


def make_leak():
    im = Image.new("RGB", (W // 4, H // 4), (0, 0, 0))
    dr = ImageDraw.Draw(im)
    for (x, y, r, c) in ((30, 20, 140, (255, 120, 170)), (460, 60, 120, (255, 190, 140)),
                         (420, 260, 150, (200, 120, 255)), (60, 250, 90, (255, 255, 255))):
        dr.ellipse([x - r, y - r, x + r, y + r], fill=c)
    im = im.filter(ImageFilter.GaussianBlur(60)).resize((W, H), Image.BILINEAR)
    return np.asarray(im).astype(np.float32) / 255


# ---- 装飾 ------------------------------------------------------------------
def make_border():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def d(dr, k):
        dr.rounded_rectangle([0, 0, W * k, H * k], radius=0, outline=(255, 170, 205), width=int(26 * k))
        dr.rounded_rectangle([18 * k, 18 * k, (W - 18) * k, (H - 18) * k], radius=int(40 * k),
                             outline=(255, 255, 255), width=int(8 * k))
        for i in range(0, W, 46):  # 上下のハート列
            for y in (8, H - 8):
                dr.polygon(heart_pts((i + 23) * k, y * k, 7 * k), fill=(255, 255, 255))
    im = supersample(W, H, d, 1)
    # 角を埋める (角丸の外側)
    corner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    m = Image.new("L", (W, H), 255)
    ImageDraw.Draw(m).rounded_rectangle([18, 18, W - 18, H - 18], radius=40, fill=0)
    corner.paste((255, 170, 205, 255), (0, 0, W, H), m)
    corner.alpha_composite(im)
    return corner


def make_tag(font):
    lab = Image.new("RGBA", (470, 76), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lab)
    dr.rounded_rectangle([4, 4, 466, 72], radius=30, fill=(255, 255, 255, 235), outline=HOTPINK, width=4)
    dr.text((235, 40), "♡ めろチョコ ♡ 歌ってみた ♡", font=ImageFont.truetype(font, 30), anchor="mm", fill=BERRY)
    return lab


def make_window(w, h, title, theme="pink"):
    """レトロPC風ウィンドウ枠 (中身の部分は透明)."""
    key = ("win", w, h, title, theme)
    if key in _c:
        return _c[key]
    col = {"pink": ((255, 150, 195), (255, 205, 225)), "dark": ((60, 28, 24), (140, 70, 60)),
           "ice": ((120, 170, 240), (210, 230, 255)), "mono": ((30, 30, 30), (230, 230, 230))}[theme]
    pad = 30
    im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad + 10, pad + 14, pad + w + 10, pad + h + 14], radius=18,
                                         fill=(90, 20, 50, 120))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([pad, pad, pad + w, pad + h], radius=18, fill=col[1], outline=(255, 255, 255), width=5)
    dr.rounded_rectangle([pad + 6, pad + 6, pad + w - 6, pad + 50], radius=12, fill=col[0])
    f = ImageFont.truetype(A["fcute"], 26)
    dr.text((pad + 22, pad + 28), "♡ " + title, font=f, anchor="lm",
            fill=(255, 255, 255) if theme != "mono" else (250, 250, 250))
    for i, sym in enumerate(("×", "□", "＿")):
        bx = pad + w - 30 - i * 40
        dr.rounded_rectangle([bx - 15, pad + 13, bx + 15, pad + 43], radius=7, fill=(255, 255, 255))
        dr.text((bx, pad + 28), sym, font=f, anchor="mm", fill=col[0])
    inner = (pad + 12, pad + 58, pad + w - 12, pad + h - 12)
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rectangle(inner, fill=255)
    arr = np.asarray(im).copy()
    arr[..., 3][np.asarray(m) > 0] = 0
    im = Image.fromarray(arr)
    ImageDraw.Draw(im).rectangle([inner[0] - 3, inner[1] - 3, inner[2] + 3, inner[3] + 3],
                                 outline=(255, 255, 255), width=3)
    _c[key] = (im, inner)
    return _c[key]


def window(dst, cx, cy, w, h, title, content_fn, scale=1.0, rot=0.0, alpha=1.0, theme="pink", bgcol=None):
    frame, inner = make_window(w, h, title, theme)
    iw, ih = inner[2] - inner[0], inner[3] - inner[1]
    im = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    if bgcol:
        im.paste(bgcol + (255,), inner)
    c = content_fn(iw, ih)
    if c is not None:
        im.alpha_composite(c, (inner[0], inner[1]))
    im.alpha_composite(frame)
    paste(dst, im, cx, cy, scale, rot, alpha)


def heart_mask(size):
    def mk():
        m = Image.new("L", (size * 2, size * 2), 0)
        ImageDraw.Draw(m).polygon(heart_pts(size, size * 1.04, size * 0.95), fill=255)
        return m.resize((size, size), Image.LANCZOS)
    return cached(("hmask", size), mk)


def heart_frame(dst, cx, cy, size, content, outline=True):
    """content (size x size) をハート型に切り抜いて貼る."""
    m = heart_mask(size)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    im.paste(content, (0, 0), m)
    if outline:
        def mk():
            o = Image.new("RGBA", (size + 80, size + 80), (0, 0, 0, 0))
            dr = ImageDraw.Draw(o)
            c = (size + 80) / 2
            dr.polygon(heart_pts(c, c + size * 0.04, size * 0.5 + 26), fill=(255, 120, 175))
            dr.polygon(heart_pts(c, c + size * 0.04, size * 0.5 + 12), fill=(255, 255, 255))
            return o
        paste(dst, cached(("hframe", size), mk), cx, cy)
    paste(dst, im, cx, cy)


# ---- 3D -------------------------------------------------------------------
SPRITES_3D = {"heart": (300, 32), "heart_white": (180, 24), "choco_heart": (440, 32), "gift": (420, 32),
              "donut": (200, 24), "pearl": (120, 1), "bar": (220, 24)}


def s3d(name, t, speed=0.5, phase=0.0):
    fr = A["3d"][name]
    return fr[int((t * speed + phase) * len(fr)) % len(fr)]


def draw3d(dst, name, x, y, size, t, speed=0.5, phase=0.0, rot=0.0, alpha=1.0, shadow=True):
    spr = s3d(name, t, speed, phase)
    sc = size / spr.width
    if shadow and size > 60:
        def mk():
            a = spr.getchannel("A").filter(ImageFilter.GaussianBlur(8))
            s = Image.new("RGBA", spr.size, (120, 20, 60, 0))
            s.putalpha(a.point(lambda v: v * 0.4))
            return s
        paste(dst, cached(("sh3d", name, id(spr)), mk), x + size * 0.06, y + size * 0.1, sc, rot, alpha)
    paste(dst, spr, x, y, sc, rot, alpha)


class Floaters:
    """画面を漂う3Dオブジェクト群."""

    def __init__(self, seed, n, kinds, size=(60, 140), area=(0, 0, W, H), vy=(-60, -20)):
        rnd = random.Random(seed)
        self.items = [dict(k=rnd.choice(kinds), x=rnd.uniform(area[0], area[2]), y=rnd.uniform(area[1], area[3]),
                           s=rnd.uniform(*size), vy=rnd.uniform(*vy), ph=rnd.random(), sp=rnd.uniform(.3, .8),
                           sw=rnd.uniform(10, 40), r=rnd.uniform(-20, 20)) for _ in range(n)]

    def draw(self, dst, t, alpha=1.0):
        for it in self.items:
            y = (it["y"] + it["vy"] * t) % (H + 300) - 150
            x = it["x"] + it["sw"] * math.sin(t * 1.3 + it["ph"] * 6)
            draw3d(dst, it["k"], x, y, it["s"], t, it["sp"], it["ph"], it["r"] + 8 * math.sin(t * 2 + it["ph"]),
                   alpha, shadow=False)


# ---- 文字 ------------------------------------------------------------------
POP = (CREAM, CHOCO, HOTPINK, WHITE)
ICY = (WHITE, (40, 60, 120), (150, 220, 255), WHITE)
BERRYTXT = (WHITE, BERRY, (255, 190, 215), WHITE)


def bubble_sprite(ch, size, col=(255, 120, 175)):
    key = ("bub", ch, size, col)
    if key in _c:
        return _c[key]
    s = int(size * 1.5)

    def d(dr, k):
        c = s * k / 2
        dr.polygon(heart_pts(c, c + s * k * 0.05, s * k * 0.49), fill=(255, 255, 255))
        dr.polygon(heart_pts(c, c + s * k * 0.05, s * k * 0.43), fill=col)
        dr.ellipse([c - s * k * .28, c - s * k * .28, c - s * k * .16, c - s * k * .16], fill=(255, 255, 255, 180))
    im = supersample(s, s, d, 2)
    f = ImageFont.truetype(A["fcute"], int(size * 0.72))
    ImageDraw.Draw(im).text((s / 2, s / 2 + size * 0.02), ch, font=f, anchor="mm", fill=(255, 255, 255),
                            stroke_width=max(2, int(size * 0.05)), stroke_fill=(200, 40, 110))
    _c[key] = im
    return im


def row_pos(text, cx, cy, size, gap=0.98):
    return [(cx + (i - (len(text) - 1) / 2) * size * gap, cy) for i in range(len(text))]


def col_pos(text, cx, cy, size, gap=1.0):
    return [(cx, cy + (i - (len(text) - 1) / 2) * size * gap) for i in range(len(text))]


def arc_pos(text, cx, cy, R, a0, a1):
    n = len(text)
    out = []
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * (i / max(n - 1, 1)))
        out.append((cx + math.cos(a) * R, cy + math.sin(a) * R, math.degrees(-a) - 90))
    return out


def text_fx(dst, text, pos, size, t, st, span, mode="pop", font=None, cols=POP, bubble=False, out_t=None,
            seed=0, shake=0.0):
    """1文字ずつ出す. mode: pop / drop / slam / fly / spin."""
    rnd = random.Random(seed)
    n = len(text)
    for i, ch in enumerate(text):
        p = pos[i]
        x, y = p[0], p[1]
        rot = p[2] if len(p) > 2 else rnd.uniform(-7, 7)
        ti = st + span * i / max(n, 1)
        lt = t - ti
        r1, r2 = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
        if lt < 0 or ch == " ":
            continue
        a = 1.0
        if out_t is not None and t > out_t:
            k = clamp01((t - out_t) / 0.18)
            a = 1 - k
            y -= 40 * k
        k = clamp01(lt / 0.22)
        sc = ease_out_back(k)
        if mode == "drop":
            y -= (1 - ease_out(k)) * 300
            sc = 1
            rot += (1 - k) * 40 * r1
        elif mode == "slam":
            sc = 1 + 2.2 * (1 - ease_out(clamp01(lt / 0.16)))
            a *= clamp01(lt / 0.1)
        elif mode == "fly":
            k2 = ease_out(clamp01(lt / 0.3))
            x += (1 - k2) * r1 * 900
            y += (1 - k2) * r2 * 600
            rot += (1 - k2) * 360 * r1
            sc = 0.4 + 0.6 * k2
        elif mode == "spin":
            rot += (1 - ease_out(k)) * 540
        x += 5 * math.sin(t * 3 + i)
        y += 6 * math.sin(t * 4 + i * 0.9)
        if shake:
            x += rnd.uniform(-1, 1) * shake * math.sin(t * 50 + i)
            y += rnd.uniform(-1, 1) * shake * math.cos(t * 47 + i)
        if bubble:
            spr = bubble_sprite(ch, size)
        else:
            spr = char_sprite(ch, font or A["fpop"], size, *cols)
        paste(dst, spr, x, y, sc, rot, a)


def ribbon_text(dst, text, cx, cy, t, st, size=92, slide=0.3, out_t=None):
    bw = int(len(text) * size * 1.02 + 60)
    ban = cached(("ban", bw), lambda: make_ribbon_banner(bw))
    k = ease_out((t - st + 0.1) / slide)
    bx = cx + (1 - k) * -(W)
    a = 1.0 if out_t is None or t < out_t else 1 - clamp01((t - out_t) / 0.18)
    paste(dst, ban, bx, cy, 1.0, 2 * math.sin(t * 2), a)
    text_fx(dst, text, row_pos(text, bx, cy, size, 1.02), size, t, st, 0.5, "pop", A["fcute"],
            (CREAM, (120, 20, 60), HOTPINK, None), out_t=out_t)


def glitch(im, t, amt):
    if amt <= 0:
        return im
    arr = np.asarray(im).copy()
    rnd = random.Random(int(t * 30))
    for _ in range(int(6 * amt)):
        y = rnd.randrange(0, H - 40)
        h = rnd.randrange(8, 60)
        arr[y:y + h] = np.roll(arr[y:y + h], rnd.randint(-80, 80) * 1, axis=1)
    return Image.fromarray(arr, im.mode)


def rgb_split(arr, k):
    k = int(k)
    if k <= 0:
        return arr
    out = arr.copy()
    out[:, k:, 0] = arr[:, :-k, 0]
    out[:, :-k, 2] = arr[:, k:, 2]
    return out


# ---- シーン ----------------------------------------------------------------
def char_full(dst, t, x, y, zoom=0.9, rot=0.0, shadow=True, img_fn=None):
    """全身キャラを (x, y) に配置 (FULL を中心として)."""
    c = cam(FULL[0], FULL[1], zoom, rot, (int(1440 * zoom * 1.1), int(1080 * zoom * 1.1)))
    if img_fn:
        c = img_fn(c)
    if shadow:
        def mk():
            a = c.getchannel("A").filter(ImageFilter.GaussianBlur(16))
            s = Image.new("RGBA", c.size, (110, 10, 60, 0))
            s.putalpha(a.point(lambda v: v * 0.55))
            return s
        paste(dst, mk(), x + 14, y + 22)
    paste(dst, c, x, y)


def sc_intro(t, lt, T, p):  # める散らかして
    im = bg("gingham", t)
    paste(im, A["sil"], W / 2 - (t * 30) % 300 + 150, H / 2, 1.0)
    k = ease_io(lt / 2.0)
    z = 0.95 + 1.35 * k
    sx = FULL[0] + (FACE[0] - FULL[0]) * k
    sy = FULL[1] + (FACE[1] - 30 - FULL[1]) * k
    # 顔のまわりを回る3Dハート (奥側)
    orb = [(i * 2 * math.pi / 6 + t * 1.6) for i in range(6)]
    for a in orb:
        if math.sin(a) < 0:
            draw3d(im, "heart", 960 + math.cos(a) * 620, 470 + math.sin(a) * 140, 110 + 30 * math.sin(a), t, .7, a)
    im.alpha_composite(cam(sx, sy, z, -3 + 5 * k))
    for a in orb:
        if math.sin(a) >= 0:
            draw3d(im, "heart", 960 + math.cos(a) * 620, 470 + math.sin(a) * 140, 150 + 40 * math.sin(a), t, .7, a)
    text_fx(im, "める散らかして", row_pos("める散らかして", 960, 900, 118), 118, t, 0.05, 1.3, bubble=True)
    return im


def sc_hakike(t, lt, T, p):  # 吐き気催すまで
    im = bg("choco", t, 80, 0)
    draw3d(im, "choco_heart", 1620, 780, 360, t, 0.6)
    draw3d(im, "bar", 260, 260, 200, t, 0.8, 0.3, -15)

    def face(w, h):
        c = cam(FACE[0] + 10 * math.sin(t * 9), FACE[1], 2.5 + 0.2 * lt, 3 * math.sin(t * 7), (w, h))
        return glitch(c, t, 1.0)
    window(im, 780, 520, 1080, 700, "melty_choco.exe", face, ease_out_back(lt / 0.3), 0, theme="dark",
           bgcol=(255, 200, 225))
    text = "吐き気催すまで"
    rnd = random.Random(12)
    spots = [(1450, 250), (1250, 520), (1560, 470), (380, 820), (700, 880), (1080, 860), (1480, 900)]
    for i, ch in enumerate(text):
        ti = 2.25 + 1.5 * i / len(text)
        if t < ti:
            continue
        x, y = spots[i]

        def content(w, h, ch=ch):
            c = Image.new("RGBA", (w, h), (255, 240, 246, 255))
            paste(c, char_sprite(ch, A["fpop"], 120, *BERRYTXT), w / 2, h / 2)
            return c
        window(im, x, y, 250, 230, "error♡", content, ease_out_back((t - ti) / 0.2), rnd.uniform(-8, 8))
    return im


def sc_uketore(t, lt, T, p):  # 受け取れ
    im = bg("burst", t, rot_speed=90)
    z = 2.6 - 0.9 * ease_out(lt / 0.6)
    sh = 18 * (1 - clamp01(lt / 0.5))
    im.alpha_composite(cam(CHEST[0] + random.Random(int(t * 30)).uniform(-1, 1) * sh / 2, CHEST[1] - 40, z,
                           4 * math.sin(t * 20) * (1 - lt)))
    for i in range(10):  # カメラに向かって飛んでくる3Dチョコ
        a = i * 2 * math.pi / 10
        d = ease_out(lt / 0.6)
        draw3d(im, "choco_heart" if i % 2 else "heart", 960 + math.cos(a) * 900 * d, 540 + math.sin(a) * 520 * d,
               80 + 200 * d, t, 1.0, i * .1, shadow=False)
    text_fx(im, "受け取れ", row_pos("受け取れ", 960, 540, 250, 1.0), 250, t, 4.1, 0.35, "slam", seed=3)
    return im


def sc_melodic(t, lt, T, p):  # メロディック チョコレート メンタル
    im = bg("dots", t, 120, 60)
    paste(im, A["sil"], W / 2 + (t * 40) % 300 - 150, H / 2)
    panels = [(4.7, FACE, 2.3, "メロディック"), (5.4, WHISK, 2.2, "チョコレート"), (6.2, CHEST, 2.0, "メンタル")]
    pw, slant = 700, 140
    for i, (st, pt, z, word) in enumerate(panels):
        if t < st - 0.05:
            continue
        k = ease_out((t - st + 0.05) / 0.3)
        cx = 330 + i * 630
        dy = (1 - k) * (H + 200) * (-1 if i % 2 == 0 else 1)
        content = cam(pt[0] + 30 * math.sin(t + i), pt[1] + 20 * math.cos(t * 1.2 + i), z + 0.1 * (t - st),
                      0, (pw + slant, H + 40))
        panel = Image.new("RGBA", content.size, (255, 225, 238, 255))
        panel.alpha_composite(content)
        m = Image.new("L", content.size, 0)
        dr = ImageDraw.Draw(m)
        poly = [(slant, 0), (pw + slant, 0), (pw, H + 40), (0, H + 40)]
        dr.polygon(poly, fill=255)
        pm = Image.new("RGBA", content.size, (0, 0, 0, 0))
        pm.paste(panel, (0, 0), m)
        ImageDraw.Draw(pm).line(poly + [poly[0]], fill=(255, 255, 255), width=14)
        ImageDraw.Draw(pm).line(poly + [poly[0]], fill=(255, 120, 175), width=5)
        paste(im, pm, cx, 540 + dy)
        text_fx(im, word, col_pos(word, cx - 200, 540 + dy, 112, 1.0), 112, t, st, 0.5, "spin",
                cols=POP if i != 1 else (CREAM, CHOCO, (255, 200, 120), WHITE), seed=i)
    Floaters(4, 7, ["pearl", "heart_white", "heart"], (50, 110)).draw(im, t)
    return im


def sc_okonomi(t, lt, T, p):  # お好み通り
    im = bg("gingham_cream", t, -40, 20)
    paste(im, A["sil"], W / 2, H / 2 - (t * 30) % 300 + 150)
    char_full(im, t, 1300 + 40 * math.sin(lt * 0.8), 560 + 12 * math.sin(t * 2), 1.02 + 0.04 * lt)
    items = [("choco_heart", "ビター"), ("bar", "ミルク"), ("donut", "いちご"), ("gift", "めろめろ♡")]

    def menu(w, h):
        c = Image.new("RGBA", (w, h), (255, 250, 244, 255))
        dr = ImageDraw.Draw(c)
        f = ImageFont.truetype(A["fcute"], 58)
        dr.text((w / 2, 50), "MENU", font=f, anchor="mm", fill=BERRY)
        for i in range(0, w, 30):
            dr.polygon(heart_pts(i + 15, 95, 7), fill=(255, 170, 205))
        fi = ImageFont.truetype(A["fcute"], 48)
        for i, (obj, name) in enumerate(items):
            ti = 7.4 + i * 0.5
            yy = 170 + i * 118
            if t < ti:
                continue
            k = ease_out_back((t - ti) / 0.25)
            draw3d(c, obj, 70, yy, 100 * k, t, 0.8, i * .2, shadow=False)
            dr.text((140, yy), name, font=fi, anchor="lm", fill=CHOCO)
            if t > ti + 0.25:  # チェック
                q = clamp01((t - ti - 0.25) / 0.15)
                x0, y0 = w - 80, yy
                pts = [(x0 - 22, y0), (x0 - 6, y0 + 18), (x0 + 26, y0 - 22)]
                dr.line(pts[:2] if q < .5 else pts, fill=HOTPINK, width=10, joint="curve")
        return c
    window(im, 470, 560, 620, 720, "order_menu", menu, ease_out_back(lt / 0.3), -3 + 2 * math.sin(t))
    text_fx(im, "お好み通り", row_pos("お好み通り", 1280, 170, 150), 150, t, 7.4, 1.2, "drop", seed=5)
    Floaters(6, 5, ["heart", "donut"], (60, 110)).draw(im, t)
    return im


def sc_cook(t, lt, T, p):  # 型に流して 冷やして できあがり
    cold = clamp01((t - 11.1) / 0.3) * (1 - clamp01((t - 12.0) / 0.3))
    im = bg("gingham", t, 30, 30)
    if cold > 0:
        im = Image.blend(im, bg("ice", t), cold * 0.6)
    char_full(im, t, 1500, 580 + 10 * math.sin(t * 2), 0.78)
    cx, cy, S = 640, 480, 640
    if t < 12.0:
        mold = Image.new("RGBA", (S + 60, S + 60), (0, 0, 0, 0))
        dr = ImageDraw.Draw(mold)
        c = (S + 60) / 2
        dr.polygon(heart_pts(c, c + S * .04, S * .5 + 22), fill=(255, 255, 255))
        dr.polygon(heart_pts(c, c + S * .04, S * .5 + 8), fill=(160, 60, 90))
        dr.polygon(heart_pts(c, c + S * .04, S * .5 - 10), fill=(255, 215, 230))
        # 流し込まれるチョコ
        lvl = ease_io((t - 10.0) / 1.0)
        fill = Image.new("RGBA", mold.size, (0, 0, 0, 0))
        fd = ImageDraw.Draw(fill)
        top_y = c + S * .45 - lvl * S * .95
        pts = [(x, top_y + 12 * math.sin(x / 38 + t * 7)) for x in range(0, S + 61, 10)]
        fd.polygon(pts + [(S + 60, S + 60), (0, S + 60)], fill=(98, 50, 34))
        fd.line(pts, fill=(150, 85, 60), width=8)
        hm = Image.new("L", mold.size, 0)
        ImageDraw.Draw(hm).polygon(heart_pts(c, c + S * .04, S * .5 - 10), fill=255)
        mold.paste(fill, (0, 0), Image.fromarray(np.minimum(np.asarray(hm), np.asarray(fill.getchannel("A")))))
        if t < 11.1:  # 上から注ぐ
            ImageDraw.Draw(mold).rounded_rectangle([c - 22 + 6 * math.sin(t * 12), 0, c + 22, top_y + 10],
                                                  radius=20, fill=(98, 50, 34))
        if cold > 0:
            mold = tint(mold, (170, 220, 255), 0.5 * cold)
        paste(im, mold, cx, cy, 1 + 0.02 * p)
        if t < 11.1:
            paste(im, cached("pot", lambda: make_pot()), cx + 80, 120 + 8 * math.sin(t * 5), 1.0, -35)
        if cold > 0:
            for i in range(26):  # 雪の結晶
                rnd = random.Random(i)
                y = (rnd.uniform(0, H) + (t - 11.1) * 260) % H
                paste(im, A["spark"][0], rnd.uniform(0, W), y, rnd.uniform(.6, 1.4), t * 90 + i * 20, cold)
    else:  # できあがり: 3Dチョコが飛び出す
        k = ease_out_back((t - 12.0) / 0.35)
        draw3d(im, "choco_heart", cx, cy - 20 * math.sin(t * 3), 560 * k, t, 0.9)
        rnd = random.Random(2)
        for i in range(40):  # 紙吹雪
            a = rnd.uniform(0, 2 * math.pi)
            d = ease_out((t - 12.0) / 0.8) * rnd.uniform(200, 900)
            x, y = cx + math.cos(a) * d, cy + math.sin(a) * d * 0.7 + (t - 12) ** 2 * 300
            col = rnd.choice([HOTPINK, WHITE, (255, 220, 120), BERRY])
            ImageDraw.Draw(im).rectangle([x - 9, y - 5, x + 9, y + 5], fill=col)
    for st, en, word in ((9.95, 11.1, "型に流して"), (11.15, 12.0, "冷やして"), (12.05, 13.4, "できあがり")):
        if st - 0.05 <= t < en:
            text_fx(im, word, row_pos(word, cx, 930, 110), 110, t, st, 0.55, bubble=True,
                    out_t=en - 0.1 if en < 13 else None, seed=int(st))
    return im


def make_pot():
    def d(dr, k):
        dr.rounded_rectangle([20 * k, 40 * k, 220 * k, 200 * k], radius=int(40 * k), fill=(255, 150, 195),
                             outline=(255, 255, 255), width=int(8 * k))
        dr.polygon([(200 * k, 70 * k), (270 * k, 40 * k), (275 * k, 60 * k), (215 * k, 110 * k)], fill=(255, 150, 195))
        for i in range(4):
            dr.polygon(heart_pts((60 + i * 40) * k, 120 * k, 12 * k), fill=(255, 255, 255))
    return supersample(290, 230, d, 2)


def sc_heart(t, lt, T, p):  # ハートに 割れ目 できませんように
    im = bg("dots", t, 60, -30)
    paste(im, A["doily"], 960, 520, 1.15, t * 15)
    S = 700
    face = cam(FACE[0], FACE[1] + 20, 1.9 + 0.08 * lt, 0, (S, S))
    back = Image.new("RGBA", (S, S), (255, 200, 225, 255))
    back.alpha_composite(face)
    gap = 0
    if t >= 14.6:
        gap = 34 * ease_out((t - 14.6) / 0.2) * (1 - ease_io((t - 15.2) / 0.5))
    sh = random.Random(int(t * 30)).uniform(-1, 1) * (14 if 14.6 <= t < 15.1 else 0)
    if gap > 0.5:
        hm = heart_mask(S)
        full = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        full.paste(back, (0, 0), hm)
        L = full.crop((0, 0, S // 2, S))
        R = full.crop((S // 2, 0, S, S))
        paste(im, L, 960 - S / 4 - gap + sh, 520, rot=gap * 0.15)
        paste(im, R, 960 + S / 4 + gap + sh, 520, rot=-gap * 0.15)
    else:
        heart_frame(im, 960 + sh, 520, S, back)
    if t >= 14.6:  # ひび / 縫い目
        dr = ImageDraw.Draw(im)
        pts = [(960 + (18 if i % 2 else -18), 250 + i * 55) for i in range(10)]
        if t < 15.2:
            q = clamp01((t - 14.6) / 0.15)
            dr.line(pts[:max(2, int(len(pts) * q))], fill=(60, 20, 30), width=10, joint="curve")
        else:
            for i, (x, y) in enumerate(pts[:-1]):
                if t > 15.2 + i * 0.08:
                    dr.line([(x - 26, y + 10), (x + 26, y + 30)], fill=(255, 90, 160), width=9)
                    dr.line([(x - 26, y + 10), (x + 26, y + 30)], fill=(255, 255, 255), width=3)
    orb = [(i * 2 * math.pi / 5 + t * 1.3) for i in range(5)]
    for a in orb:
        draw3d(im, "heart_white" if math.sin(a) < 0 else "heart", 960 + math.cos(a) * 560, 520 + math.sin(a) * 330,
               90 + 30 * math.sin(a), t, .8, a)
    text_fx(im, "ハートに", arc_pos("ハートに", 960, 560, 470, -150, -30), 105, t, 13.7, 0.6, "pop",
            cols=POP, seed=7)
    if t >= 14.6:
        text_fx(im, "割れ目", col_pos("割れ目", 1650, 520, 170), 170, t, 14.6, 0.35, "slam",
                cols=(WHITE, (60, 20, 30), BERRY, WHITE), seed=8, shake=8 if t < 15.1 else 0)
    text_fx(im, "できませんように", row_pos("できませんように", 960, 955, 96), 96, t, 15.15, 1.0, bubble=True)
    return im


def sc_ice(t, lt, T, p):  # 絶対零度で 固めて とじこめる
    im = bg("ice", t)
    for i in range(40):  # 雪
        rnd = random.Random(i + 100)
        y = (rnd.uniform(0, H) + t * rnd.uniform(60, 160)) % H
        x = rnd.uniform(0, W) + 30 * math.sin(t + i)
        paste(im, A["spark"][0], x, y, rnd.uniform(.3, 1.0), t * 60 + i * 30, 0.8)
    z = 1.0 + 0.35 * ease_io(lt / T)
    c = cam(720, 430, z, 0)
    c = tint(c, (150, 200, 255), 0.35)
    im.alpha_composite(c)
    if t >= 17.85:  # 氷のキューブ
        k = ease_out_back((t - 17.85) / 0.3)
        cube = cached("cube", make_cube)
        paste(im, cube, 960, 440, k)
    if t >= 19.45:  # リボンでとじこめる
        k = ease_out((t - 19.45) / 0.35)
        band = cached("xband", make_xband)
        paste(im, band, 960 - (1 - k) * 1600, 440 - (1 - k) * 900, 1, -28)
        paste(im, band, 960 + (1 - k) * 1600, 440 - (1 - k) * 900, 1, 28)
        draw3d(im, "heart", 960, 440, 260 * ease_out_back((t - 19.7) / 0.3), t, 0.5)
    im.alpha_composite(cached("frost", make_frost))
    rows = [(16.7, 17.85, "絶対零度で", 150), (17.85, 19.45, "固めて", 200), (19.45, 99, "とじこめる", 170)]
    for st, en, word, size in rows:
        if st <= t < en + 0.2:
            text_fx(im, word, row_pos(word, 960, 900, size), size, t, st, 0.6, "drop", cols=ICY,
                    out_t=en if en < 99 else None, seed=int(st * 10))
    return im


def make_cube():
    w, h = 900, 760

    def d(dr, k):
        dr.rounded_rectangle([0, 0, w * k, h * k], radius=int(80 * k), fill=(200, 235, 255, 70),
                             outline=(235, 250, 255, 230), width=int(14 * k))
        dr.rounded_rectangle([30 * k, 30 * k, (w - 30) * k, (h - 30) * k], radius=int(60 * k),
                             outline=(255, 255, 255, 120), width=int(5 * k))
        for i in range(3):
            dr.line([((80 + i * 60) * k, 60 * k), ((40 + i * 60) * k, 220 * k)], fill=(255, 255, 255, 170),
                    width=int(14 * k))
    return supersample(w, h, d, 1)


def make_xband():
    w, h = 2600, 110
    im = Image.new("RGBA", (w, h), (30, 20, 24, 255))
    dr = ImageDraw.Draw(im)
    for x in range(0, w, 80):
        dr.polygon([(x, 0), (x + 40, 0), (x + 20 + 40, h), (x + 20, h)], fill=(255, 255, 255))
    dr.rectangle([0, 0, w, 10], fill=(255, 120, 175))
    dr.rectangle([0, h - 10, w, h], fill=(255, 120, 175))
    return im


def make_frost():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    m = Image.new("L", (W, H), 255)
    ImageDraw.Draw(m).ellipse([-100, -60, W + 100, H + 60], fill=0)
    m = m.filter(ImageFilter.GaussianBlur(80))
    im.paste((230, 245, 255, 255), (0, 0, W, H), m.point(lambda v: v * 0.85))
    return im


def sc_ribbon(t, lt, T, p):  # しろくろリボン 強く結んだなら
    im = bg("mono", t, 90, 0)
    # チルトアップ: 足元 → 顔
    k = ease_io(lt / T)
    sy = SHOES[1] + (FACE[1] - SHOES[1]) * k
    sx = SHOES[0] + (FACE[0] - SHOES[0]) * k
    c = cam(sx, sy, 1.9 - 0.3 * k, -6 + 6 * k)
    c = desat(c, 0.6)
    im.alpha_composite(c)
    dr = ImageDraw.Draw(im)
    for j, (col, edge, yb, amp) in enumerate(((WHITE, (20, 20, 20), 200, 70), ((20, 20, 20), WHITE, 880, 60),
                                               ((255, 120, 175), WHITE, 540, 90))):
        pts = [(x, yb + amp * math.sin(x / 190 + t * 3 + j * 2)) for x in range(-40, W + 60, 30)]
        dr.line(pts, fill=edge, width=64, joint="curve")
        dr.line(pts, fill=col, width=48, joint="curve")
    if t >= 22.6:
        k2 = ease_out_back((t - 22.6) / 0.4)
        squash = 1 + 0.08 * p
        bow = cached("monobow", lambda: make_bow(560, (250, 250, 250), (20, 20, 20)))
        paste(im, bow, 430, 360, k2 * squash, (1 - k2) * 360)
    ribbon_text(im, "しろくろリボン", 960, 860, t, 21.45, out_t=22.55)
    if t >= 22.6:
        ribbon_text(im, "強く結んだなら", 1000, 860, t, 22.65)
    Floaters(11, 6, ["pearl", "heart_white"], (40, 90)).draw(im, t)
    return im


def sc_gift(t, lt, T, p):  # できあがりよ
    im = bg("burst", t, rot_speed=40)
    paste(im, A["sil"], W / 2, H / 2 + (t * 40) % 300 - 150)
    if t >= 25.55:
        char_full(im, t, 1420, 560, 0.95)
        k = ease_out_back((t - 25.55) / 0.35)
        draw3d(im, "gift", 540, 520, 480 * k, t, 0.7)
        rnd = random.Random(4)
        for i in range(50):
            a = rnd.uniform(0, 2 * math.pi)
            d = ease_out((t - 25.55) / 0.7) * rnd.uniform(200, 1000)
            x, y = 540 + math.cos(a) * d, 520 + math.sin(a) * d * 0.7 + (t - 25.55) ** 2 * 400
            ImageDraw.Draw(im).polygon(heart_pts(x, y, 14), fill=rnd.choice([HOTPINK, WHITE, (255, 220, 120)]))
    if t < 25.75:
        q = clamp01((t - 25.05) / 0.5)

        def load(w, h):
            c = Image.new("RGBA", (w, h), (255, 245, 250, 255))
            dr = ImageDraw.Draw(c)
            f = ImageFont.truetype(A["fcute"], 60)
            dr.text((w / 2, h * .32), "Now Loading...", font=f, anchor="mm", fill=BERRY)
            dr.rounded_rectangle([60, h * .55, w - 60, h * .55 + 70], radius=35, outline=HOTPINK, width=6)
            dr.rounded_rectangle([72, h * .55 + 12, 72 + (w - 144) * q, h * .55 + 58], radius=24, fill=HOTPINK)
            for i in range(int(q * 10)):
                dr.polygon(heart_pts(100 + i * (w - 200) / 9, h * .55 + 35, 14), fill=WHITE)
            dr.text((w / 2, h * .85), f"{int(q * 100)}%", font=f, anchor="mm", fill=HOTPINK)
            return c
        out = clamp01((t - 25.55) / 0.2)
        window(im, 960, 520, 900, 540, "present.exe", load, ease_out_back(lt / 0.25) * (1 + out * 0.5), 0,
               1 - out)
    text_fx(im, "できあがりよ", row_pos("できあがりよ", 960, 930, 112), 112, t, 25.15, 0.8, bubble=True)
    return im


def sc_grid(t, lt, T, p):  # 欲しいならあげる
    im = bg("stripes", t, 100, 0)
    shots = [(FACE, 2.4), (WHISK, 2.0), (CHEST, 1.8), (SHOES, 1.6), (FULL, 0.7), (LEGS, 1.6), (FACE, 3.2),
             ((900, 470), 1.9), ((1250, 420), 1.8)]
    titles = ["face.png", "whisk.png", "choco.png", "shoes.png", "all.png", "ribbon.png", "eyes.png",
              "frill.png", "hand.png"]
    order = [4, 0, 8, 2, 6, 1, 3, 7, 5]
    for n, i in enumerate(order):
        ti = 26.5 + n * 0.13
        if t < ti:
            continue
        r, c = divmod(i, 3)
        (sx, sy), z = shots[i]
        x = 330 + c * 630 + 8 * math.sin(t * 3 + i)
        y = 200 + r * 340 + 8 * math.cos(t * 3 + i)

        def content(w, h, sx=sx, sy=sy, z=z, i=i):
            return cam(sx + 25 * math.sin(t * 1.5 + i), sy + 15 * math.cos(t * 1.3 + i), z, 0, (w, h))
        window(im, x, y, 590, 320, titles[i], content, ease_out_back((t - ti) / 0.2), 0, bgcol=(255, 220, 235))
    Floaters(21, 8, ["gift", "heart", "choco_heart"], (80, 150), vy=(-160, -80)).draw(im, t)
    ribbon_text(im, "欲しいならあげる", 960, 540, t, 26.55, size=104)
    return im


def sc_final(t, lt, T, p):  # 君をめろつかせちゃうぞ
    im = bg("final", t, rot_speed=-60)
    S = 820
    z = 2.1 + 0.25 * p + 0.15 * lt
    face = cam(FACE[0], FACE[1] + 10, z, 0, (S, S))
    back = Image.new("RGBA", (S, S), (255, 190, 220, 255))
    back.alpha_composite(face)
    for i in range(14):  # はじけ飛ぶ3Dハート
        rnd = random.Random(i + 50)
        a = rnd.uniform(0, 2 * math.pi)
        d = ((lt * rnd.uniform(0.5, 1.0) + rnd.random()) % 1.2) / 1.2
        draw3d(im, rnd.choice(["heart", "heart_white", "choco_heart"]), 1320 + math.cos(a) * d * 1100,
               520 + math.sin(a) * d * 700, 60 + d * 220, t, 1.0, rnd.random(), shadow=False)
    heart_frame(im, 1320, 520, int(S * (1 + 0.04 * p)), back.resize((int(S * (1 + 0.04 * p)),) * 2))
    text_fx(im, "君を", [(300, 250), (580, 250)], 280, t, 28.6, 0.3, "slam", seed=11)
    text = "めろつかせちゃうぞ"
    pos = [(170 + i * 150, 600 + 25 * math.sin(i * 1.4)) if i < 5 else (270 + (i - 5) * 150, 820)
           for i in range(len(text))]
    text_fx(im, text, pos, 150, t, 29.3, 1.1, "fly", seed=12, shake=6 * p)
    return im


# (開始, 終了, 関数, 入りのトランジション)
SCENES = [
    (0.0, 2.2, sc_intro, "white"),
    (2.2, 4.1, sc_hakike, "glitch"),
    (4.1, 4.7, sc_uketore, "flash"),
    (4.7, 7.25, sc_melodic, "slide"),
    (7.25, 9.8, sc_okonomi, "iris"),
    (9.8, 13.3, sc_cook, "zoom"),
    (13.3, 16.65, sc_heart, "flash"),
    (16.65, 21.2, sc_ice, "ice"),
    (21.2, 25.0, sc_ribbon, "whip"),
    (25.0, 26.5, sc_gift, "flash"),
    (26.5, 28.5, sc_grid, "zoom"),
    (28.5, 99, sc_final, "iris"),
]
TR = 0.28


def scene_frame(i, t, p):
    t0, t1, fn, _ = SCENES[i]
    return fn(t, t - t0, t1 - t0, p)


def compose(t, p):
    i = max(j for j, s in enumerate(SCENES) if t >= s[0])
    t0, _, _, tr = SCENES[i]
    lt = t - t0
    cur = scene_frame(i, t, p)
    if lt >= TR:
        return cur, 0.0
    q = lt / TR
    flash = 0.0
    if tr == "white":
        flash = 1 - q
    elif tr in ("flash", "ice"):
        flash = (1 - q) * 0.9
        if tr == "ice":
            cur.alpha_composite(Image.new("RGBA", (W, H), (190, 225, 255, int(200 * (1 - q)))))
            flash = 0
    elif tr == "glitch":
        prev = scene_frame(i - 1, t, p)
        if q < 0.5:
            cur = prev
        cur = glitch(cur, t, 3)
    elif tr == "slide":
        prev = scene_frame(i - 1, t, p)
        k = ease_out(q)
        base = Image.new("RGBA", (W, H))
        base.alpha_composite(prev.crop((int(W * k), 0, W, H)), (0, 0))
        base.alpha_composite(cur.crop((0, 0, max(1, int(W * k)), H)), (W - int(W * k), 0))
        cur = base
    elif tr == "whip":
        prev = scene_frame(i - 1, t, p)
        k = ease_io(q)
        base = Image.new("RGBA", (W, H))
        off = int(W * k)
        base.alpha_composite(prev.crop((off, 0, W, H)) if off < W else prev.crop((0, 0, 1, 1)), (0, 0))
        if off > 0:
            base.alpha_composite(cur.crop((0, 0, off, H)), (W - off, 0))
        small = base.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.BoxBlur(3))
        cur = Image.blend(base, small.resize((W, H), Image.BILINEAR), 0.6 * math.sin(math.pi * q))
    elif tr == "zoom":
        prev = scene_frame(i - 1, t, p)
        s = 1 + 0.6 * (1 - ease_out(q))
        z = cur.resize((int(W * s), int(H * s)), Image.BILINEAR)
        z = z.crop(((z.width - W) // 2, (z.height - H) // 2, (z.width - W) // 2 + W, (z.height - H) // 2 + H))
        cur = Image.blend(prev, z, ease_out(q))
    elif tr == "iris":
        prev = scene_frame(i - 1, t, p)
        m = Image.new("L", (W, H), 0)
        r = 1500 * ease_io(q)
        ImageDraw.Draw(m).polygon(heart_pts(W / 2, H / 2, max(r, 1)), fill=255)
        prev.paste(cur, (0, 0), m)
        cur = prev
    return cur, flash


def render(fi):
    t = fi / FPS
    p = float(A["pulse"][min(fi, len(A["pulse"]) - 1)])
    im, flash = compose(t, p)
    paste(im, A["bokeh"], W / 2 + 80 * math.sin(t * 0.4), H / 2 + (t * 25) % 200 - 100)
    im.alpha_composite(A["border"])
    im.alpha_composite(A["tag"], (W - 520, 34))
    # ビートでズームバンプ
    if p > 0.05:
        s = 1 + 0.025 * p
        z = im.resize((int(W * s), int(H * s)), Image.BILINEAR)
        im = z.crop(((z.width - W) // 2, (z.height - H) // 2, (z.width - W) // 2 + W, (z.height - H) // 2 + H))
    arr = np.asarray(im.convert("RGB")).astype(np.float32) / 255
    # ブルーム + 光漏れ (スクリーン合成)
    small = im.convert("RGB").resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5))
    bloom = np.asarray(small.resize((W, H), Image.BILINEAR)).astype(np.float32) / 255
    bloom = np.clip(bloom - 0.72, 0, 1) * 1.6
    leak = A["leak"] * (0.12 + 0.06 * math.sin(t * 1.3))
    leak = np.roll(leak, int(200 * math.sin(t * 0.5)), axis=1)
    for layer in (bloom * 0.45, leak):
        arr = 1 - (1 - arr) * (1 - layer)
    if flash > 0:
        arr = arr * (1 - flash) + flash
    end_t = A["nframes"] / FPS
    if t > end_t - 0.45:  # 最後はハートのアイリスで閉じる
        k = clamp01((t - (end_t - 0.45)) / 0.4)
        m = Image.new("L", (W, H), 255)
        ImageDraw.Draw(m).polygon(heart_pts(1320, 540, max(1, 1400 * (1 - ease_io(k)))), fill=0)
        mm = np.asarray(m).astype(np.float32)[..., None] / 255
        arr = arr * (1 - mm) + np.array([0.12, 0.03, 0.07]) * mm
    out = (arr * 255).clip(0, 255).astype(np.uint8)
    out = rgb_split(out, 8 * max(0, p - 0.5))
    return out.tobytes()


def build(args, pool):
    ch = Image.open(args.image).convert("RGBA")
    A["char2"] = ch.resize((ch.width * 2, ch.height * 2), Image.LANCZOS)
    A["fpop"], A["fcute"] = args.font_pop, args.font_cute
    A["bg"] = make_bgs()
    A["sil"] = make_silhouettes()
    A["bokeh"] = make_bokeh()
    A["leak"] = make_leak()
    A["border"] = make_border()
    A["tag"] = make_tag(args.font_cute)
    A["doily"] = make_doily(900)
    A["spark"] = [make_sparkle(40), make_sparkle(28, (255, 230, 150))]
    A["3d"] = render3d.build_sprites(pool, args.cache, SPRITES_3D)
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
        pulse[i] = max(min(onset[i], 1.2), pulse[i - 1] * 0.75 if i else 0)
    A["pulse"] = np.clip(pulse, 0, 1.2)
    A["nframes"] = n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--font-pop", required=True)
    ap.add_argument("--font-cute", required=True)
    ap.add_argument("--out", default="mv.mp4")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    with Pool(args.jobs) as pool:
        build(args, pool)
    if args.preview:
        for s in args.preview:
            Image.frombytes("RGB", (W, H), render(int(s * FPS))).save(f"mv_{s:05.2f}.png")
        return
    enc = subprocess.Popen([args.ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", args.audio,
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
                            "-movflags", "+faststart", args.out], stdin=subprocess.PIPE)
    with Pool(args.jobs) as pool:
        for i, fr in enumerate(pool.imap(render, range(A["nframes"]), chunksize=2)):
            enc.stdin.write(fr)
            if i % 60 == 0:
                print(f"frame {i}/{A['nframes']}", flush=True)
    enc.stdin.close()
    enc.wait()


if __name__ == "__main__":
    main()
