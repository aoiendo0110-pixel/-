"""めろチョコ 可愛いゴテゴテ版 MV (お菓子作り × チョコ × バレンタイン × ロリータ).

使い方:
  python3 make_cute.py --image illust.png --audio source.mov \
      --font Mochiy.ttf --font-sub Hachi.ttf --out cute.mp4
"""
import argparse
import math
import random
import subprocess
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import deco as D
import make_mv as M
import render3d
from make_video import FPS, H, W, ease_out, ease_out_back, heart_pts, make_doily, paste
from make_mv import (CHEST, FACE, FULL, LEGS, SHOES, WHISK, arc_pos, cam, clamp01, col_pos, desat, draw3d, ease_io,
                     glitch, heart_mask, row_pos, tint)

A = M.A
_c = M._c
cached = M.cached

SPRITES = {"heart": (300, 32), "heart_white": (180, 24), "choco_heart": (440, 32), "gift": (420, 32),
           "macaron": (220, 24), "macaron_y": (200, 24), "macaron_c": (200, 24), "strawberry": (220, 24),
           "cupcake": (240, 24), "cookie": (220, 24), "bow": (280, 24), "bow_pink": (220, 24),
           "bow_bw": (520, 32), "cherry": (180, 24), "candy": (180, 24), "candy_p": (180, 24)}
SWEETS = ["macaron", "macaron_y", "macaron_c", "strawberry", "cupcake", "cookie", "cherry", "candy", "candy_p",
          "choco_heart", "heart", "bow_pink"]


# ---- 背景 ------------------------------------------------------------------
PAD = 240


def make_bgs():
    pw, ph = W + PAD * 2, H + PAD * 2
    b = {}
    b["quilt_pink"] = D.quilt(pw, ph, (255, 160, 200), D.WHITE)
    b["quilt_choco"] = D.quilt(pw, ph, (110, 56, 36), (255, 150, 190))
    b["quilt_red"] = D.quilt(pw, ph, (215, 30, 64), (255, 220, 120))
    b["gingham_red"] = D.gingham(pw, ph, (255, 250, 246), (220, 28, 62, 95), 110, hearts=(255, 255, 255))
    b["gingham_pink"] = D.gingham(pw, ph, (255, 246, 240), (255, 120, 170, 80), 110, hearts=(255, 255, 255))
    b["polka"] = D.polka(pw, ph, (255, 160, 200), (255, 255, 255), hearts=(220, 28, 62))
    b["polka_cream"] = D.polka(pw, ph, (255, 246, 232), (255, 205, 220), hearts=(255, 214, 90))
    b["stripe"] = D.candy_stripe(pw, ph)
    b["mono"] = D.candy_stripe(pw, ph, ((30, 28, 30), D.WHITE), 70)
    b["frosty"] = D.vgrad(pw, ph, (255, 236, 244), (255, 255, 255))
    b["rays"] = D.rays(2600, (255, 150, 195), (255, 110, 170), 32, center=(255, 240, 150, 255))
    b["rays_red"] = D.rays(2600, (150, 12, 40), (96, 20, 24), 32, center=(255, 180, 90, 220))
    b["rays_pink"] = D.rays(2600, (255, 200, 220), (255, 160, 200), 28, center=(255, 250, 200, 255))
    return b


def bg(name, t, vx=40, vy=20, rot=0.0):
    im = A["bg"][name]
    if name.startswith("rays"):
        r = im.rotate(t * rot, Image.BILINEAR)
        c = r.width // 2
        return r.crop((c - W // 2, c - H // 2, c + W // 2, c + H // 2))
    ox = int((t * vx) % 220) + 10
    oy = int((t * vy) % 220) + 10
    return im.crop((ox, oy, ox + W, oy + H))


# ---- ゴテゴテのフレーム --------------------------------------------------------
def make_frame():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # パールのスワッグ + ハートのチャーム
    p = D.pearl(10)
    gem = D.gem_heart(40)
    span = 320
    for x0 in range(-span // 2, W + span, span):
        for u in np.linspace(0, 1, 15):
            x = x0 + u * span
            y = 150 + 48 * math.sin(math.pi * u)
            D.paste_c(im, p, x, y)
        D.paste_c(im, gem, x0 + span / 2, 214)
    # 下のフリル (赤 → ピンク → レース → ステッチの帯)
    y0 = H - 128
    im.alpha_composite(D.frill(W + 80, 128, D.RED, trim=(255, 190, 205)), (-40, y0))
    im.alpha_composite(D.frill(W + 60, 100, D.PINK, trim=D.WHITE, n=34), (-30, y0))
    im.alpha_composite(D.lace(W + 40, 58), (-20, y0))
    im.alpha_composite(D.stitch_band(W, 34, D.BROWN), (0, y0 - 18))
    # 左右の細いレース
    side = D.lace(H, 40).rotate(90, expand=True)
    im.alpha_composite(side, (0, 0))
    im.alpha_composite(side.transpose(Image.FLIP_LEFT_RIGHT), (W - side.width, 0))
    return im


def make_drips():
    return [D.choco_drips(W, 200, base=44, t=i * 0.4) for i in range(16)]


def frame_layer(im, t, p):
    im.alpha_composite(A["frame"])
    im.alpha_composite(A["drips"][int(t * 5) % 16])
    # 上の角の大きいリボン
    b = A["3d"]["bow"][0]
    paste(im, b, 150, 115, 1.05 + 0.04 * p, 18 + 4 * math.sin(t * 2))
    paste(im, b, W - 150, 115, 1.05 + 0.04 * p, -18 - 4 * math.sin(t * 2))
    # 下の角のお菓子の山
    for (x, y, n, s, ph) in ((70, H - 150, "cupcake", 170, 0), (190, H - 95, "macaron", 130, .3),
                             (40, H - 60, "strawberry", 120, .6), (300, H - 60, "cherry", 100, .1),
                             (W - 70, H - 150, "choco_heart", 170, .2), (W - 195, H - 95, "macaron_y", 130, .5),
                             (W - 40, H - 60, "cookie", 120, .7), (W - 300, H - 60, "candy_p", 110, .4)):
        draw3d(im, n, x, y + 4 * math.sin(t * 3 + ph * 6), s * (1 + 0.05 * p), t, 0.35, ph, shadow=False)
    # 下中央のリボン
    draw3d(im, "bow_pink", W / 2, H - 112, 150, 0, 0, 0, 3 * math.sin(t * 2), shadow=False)
    im.alpha_composite(A["tag"], (W - A["tag"].width - 300, 22))


def make_tag(font):
    f = ImageFont.truetype(font, 26)
    text = "♡ めろチョコ 歌ってみた ♡"
    tw = int(f.getlength(text)) + 50
    lab = Image.new("RGBA", (tw, 54), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lab)
    dr.rounded_rectangle([0, 0, tw - 1, 53], radius=27, fill=(255, 255, 255, 240), outline=D.RED, width=4)
    dr.text((tw / 2, 28), text, font=f, anchor="mm", fill=D.RED)
    return lab


# ---- 文字 ------------------------------------------------------------------
def csprite(ch, size, style):
    return cached(("cute", ch, size, style), lambda: D.cute_char(ch, size, style, A["font"]))


def bsprite(ch, size, col=D.RED):
    return cached(("bub", ch, size, col), lambda: D.bubble(ch, size, A["font"], col))


def ctext(dst, text, pos, size, t, st, span, style="berry", mode="pop", out_t=None, seed=0, shake=0.0,
          bubble=None):
    rnd = random.Random(seed)
    n = len(text)
    for i, ch in enumerate(text):
        pp = pos[i]
        x, y = pp[0], pp[1]
        rot = pp[2] if len(pp) > 2 else rnd.uniform(-6, 6)
        r1, r2 = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
        lt = t - (st + span * i / max(n, 1))
        if lt < 0:
            continue
        a = 1.0
        if out_t is not None and t > out_t:
            k = clamp01((t - out_t) / 0.18)
            a, y = 1 - k, y - 40 * k
        k = clamp01(lt / 0.22)
        sc = ease_out_back(k)
        if mode == "drop":
            y -= (1 - ease_out(k)) * 320
            sc, rot = 1, rot + (1 - k) * 40 * r1
        elif mode == "slam":
            sc = 1 + 2.0 * (1 - ease_out(clamp01(lt / 0.16)))
            a *= clamp01(lt / 0.08)
        elif mode == "fly":
            k2 = ease_out(clamp01(lt / 0.3))
            x += (1 - k2) * r1 * 900
            y += (1 - k2) * r2 * 600
            rot += (1 - k2) * 360 * r1
            sc = 0.4 + 0.6 * k2
        elif mode == "spin":
            rot += (1 - ease_out(k)) * 540
        x += 4 * math.sin(t * 3 + i)
        y += 7 * math.sin(t * 4.5 + i * 0.9)
        if shake:
            x += r1 * shake * math.sin(t * 50 + i)
            y += r2 * shake * math.cos(t * 47 + i)
        spr = bsprite(ch, size, bubble) if bubble else csprite(ch, size, style)
        paste(dst, spr, x, y, sc, rot, a)
    # 行の両端にキラキラ
    if t > st and pos:
        tw = cached("twk", lambda: D.twinkle(50))
        s = 0.6 + 0.4 * abs(math.sin(t * 6 + seed))
        paste(dst, tw, pos[0][0] - size * 0.8, pos[0][1] - size * 0.5, s)
        paste(dst, tw, pos[-1][0] + size * 0.8, pos[-1][1] + size * 0.4, s * 0.8)


def btext(dst, text, cx, cy, t, st, size=96, style="milk", out_t=None, seed=0):
    """赤いリボンバナーに乗せた文字."""
    bw = int(len(text) * size * 1.02 + 60)
    ban = cached(("ban", bw), lambda: D.banner(bw))
    k = ease_out((t - st + 0.1) / 0.3)
    bx = cx - (1 - k) * W
    a = 1.0 if out_t is None or t < out_t else 1 - clamp01((t - out_t) / 0.18)
    paste(dst, ban, bx, cy, 1.0, 1.5 * math.sin(t * 2), a)
    ctext(dst, text, row_pos(text, bx, cy - 4, size, 1.02), size, t, st, 0.5, style, out_t=out_t, seed=seed)


# ---- 枠 ------------------------------------------------------------------------
def card_img(w, h, col=D.PINK, label=None, bow=True):
    def mk():
        b = A["3d"]["bow"][0].resize((150, 150), Image.LANCZOS) if bow else None
        return D.card(w, h, col, b, label, A["font_sub"])
    return cached(("card", w, h, col, label, bow), mk)


def card(dst, cx, cy, w, h, content_fn, scale=1.0, rot=0.0, alpha=1.0, col=D.PINK, label=None, bgcol=D.CREAM,
         bow=True):
    frame, inner = card_img(w, h, col, label, bow)
    im = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    im.paste(bgcol + (255,), inner)
    c = content_fn(inner[2] - inner[0], inner[3] - inner[1])
    if c is not None:
        im.alpha_composite(c, inner[:2])
    im.alpha_composite(frame)
    paste(dst, im, cx, cy, scale, rot, alpha)


def fancy_heart(dst, cx, cy, size, content):
    """金の縁 + パール付きのハート窓."""
    def mk():
        pad = 90
        o = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(o)
        c = o.width / 2
        dr.polygon(heart_pts(c + 10, c + size * .04 + 16, size * .5 + 34), fill=(120, 10, 40, 120))
        dr.polygon(heart_pts(c, c + size * .04, size * .5 + 36), fill=D.WHITE)
        dr.polygon(heart_pts(c, c + size * .04, size * .5 + 24), fill=D.GOLD)
        dr.polygon(heart_pts(c, c + size * .04, size * .5 + 14), fill=D.RED)
        dr.polygon(heart_pts(c, c + size * .04, size * .5 + 6), fill=D.WHITE)
        o = o.filter(ImageFilter.GaussianBlur(0.6))
        pr = D.pearl(11)
        for (x, y) in heart_pts(c, c + size * .04, size * .5 + 48, 60):
            D.paste_c(o, pr, x, y)
        return o
    paste(dst, cached(("fheart", size), mk), cx, cy)
    m = heart_mask(size)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    im.paste(content, (0, 0), m)
    paste(dst, im, cx, cy)


def char_full(dst, t, x, y, zoom=0.9, fn=None):
    c = cam(FULL[0], FULL[1], zoom, 0, (int(1440 * zoom * 1.1), int(1080 * zoom * 1.1)))
    if fn:
        c = fn(c)
    a = c.getchannel("A").filter(ImageFilter.GaussianBlur(14))
    s = Image.new("RGBA", c.size, (140, 10, 60, 0))
    s.putalpha(a.point(lambda v: v * 0.5))
    paste(dst, s, x + 14, y + 22)
    paste(dst, c, x, y)


class Float:
    def __init__(self, seed, n, kinds=SWEETS, size=(70, 130), vy=(-70, -25)):
        rnd = random.Random(seed)
        self.it = [dict(k=rnd.choice(kinds), x=rnd.uniform(0, W), y=rnd.uniform(0, H), s=rnd.uniform(*size),
                        vy=rnd.uniform(*vy), ph=rnd.random(), sp=rnd.uniform(.3, .7), r=rnd.uniform(-20, 20))
                   for _ in range(n)]

    def draw(self, dst, t):
        for it in self.it:
            y = (it["y"] + it["vy"] * t) % (H + 300) - 150
            x = it["x"] + 30 * math.sin(t * 1.3 + it["ph"] * 6)
            draw3d(dst, it["k"], x, y, it["s"], t, it["sp"], it["ph"], it["r"] + 8 * math.sin(t * 2 + it["ph"]),
                   shadow=False)


def confetti(dst, t, t0, cx, cy, n=60, seed=1, spread=1000):
    if t < t0:
        return
    rnd = random.Random(seed)
    dr = ImageDraw.Draw(dst)
    tw = cached("twk", lambda: D.twinkle(50))
    for i in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        d = ease_out((t - t0) / 0.8) * rnd.uniform(150, spread)
        x = cx + math.cos(a) * d
        y = cy + math.sin(a) * d * 0.7 + (t - t0) ** 2 * 380
        k = rnd.random()
        col = rnd.choice([D.RED, D.WHITE, D.YELLOW, D.PINK, D.BROWN])
        if k < 0.4:
            dr.polygon(heart_pts(x, y, 15), fill=col)
        elif k < 0.75:
            ang = rnd.uniform(0, math.pi) + t * 4
            dr.line([(x - math.cos(ang) * 12, y - math.sin(ang) * 12), (x + math.cos(ang) * 12,
                                                                        y + math.sin(ang) * 12)], fill=col, width=8)
        else:
            paste(dst, tw, x, y, 0.6, t * 90)


# ---- シーン ----------------------------------------------------------------
def sc_intro(t, lt, T, p):  # める散らかして
    im = bg("quilt_pink", t, 30, 15)
    paste(im, A["doily"], 960, 470, 1.25, t * 12)
    k = ease_io(lt / 2.0)
    z = 0.95 + 1.3 * k
    sx = FULL[0] + (FACE[0] - FULL[0]) * k
    sy = FULL[1] + (FACE[1] - 20 - FULL[1]) * k
    objs = ["strawberry", "macaron", "bow_pink", "cherry", "cupcake", "macaron_y", "heart", "cookie"]
    orb = [(i * 2 * math.pi / len(objs) + t * 1.5, o) for i, o in enumerate(objs)]
    for a, o in orb:
        if math.sin(a) < 0:
            draw3d(im, o, 960 + math.cos(a) * 640, 460 + math.sin(a) * 150, 110 + 30 * math.sin(a), t, .6, a)
    im.alpha_composite(cam(sx, sy, z, -3 + 5 * k))
    for a, o in orb:
        if math.sin(a) >= 0:
            draw3d(im, o, 960 + math.cos(a) * 640, 460 + math.sin(a) * 150, 150 + 40 * math.sin(a), t, .6, a)
    btext(im, "める散らかして", 960, 800, t, 0.05, 100, "milk")
    return im


def sc_hakike(t, lt, T, p):  # 吐き気催すまで
    im = bg("quilt_choco", t, 60, 0)

    def face(w, h):
        c = Image.new("RGBA", (w, h), (255, 205, 225, 255))
        c.alpha_composite(cam(FACE[0] + 8 * math.sin(t * 9), FACE[1], 2.4 + 0.2 * lt, 3 * math.sin(t * 7), (w, h)))
        return glitch(c, t, 0.6)
    card(im, 720, 490, 960, 560, face, ease_out_back(lt / 0.3), -2, col=D.PINK, label="melty♡choco")
    text = "吐き気催すまで"
    spots = [(1480, 260), (1270, 450), (1600, 520), (1350, 700), (1640, 760), (470, 830), (820, 850)]
    macs = ["macaron", "macaron_y", "macaron_c"]
    for i, ch in enumerate(text):
        ti = 2.25 + 1.5 * i / len(text)
        if t < ti:
            continue
        x, y = spots[i]
        k = ease_out_back((t - ti) / 0.22)
        y += 8 * math.sin(t * 4 + i)
        draw3d(im, macs[i % 3], x, y + 10, 400 * k, 0, 0, 0, 0)
        paste(im, csprite(ch, 84, ["berry", "milk", "berry"][i % 3]), x, y - 6, k, 6 * math.sin(t * 3 + i))
    draw3d(im, "choco_heart", 240, 300, 240, t, 0.6)
    return im


def sc_uketore(t, lt, T, p):  # 受け取れ
    im = bg("rays", t, rot=80)
    z = 2.5 - 0.9 * ease_out(lt / 0.6)
    sh = 16 * (1 - clamp01(lt / 0.5))
    im.alpha_composite(cam(CHEST[0] + random.Random(int(t * 30)).uniform(-1, 1) * sh, CHEST[1] - 60, z,
                           4 * math.sin(t * 20) * (1 - lt)))
    objs = ["choco_heart", "strawberry", "bow", "macaron", "heart", "cupcake", "cherry", "cookie", "candy", "gift"]
    for i, o in enumerate(objs):
        a = i * 2 * math.pi / len(objs) + 0.3
        d = ease_out(lt / 0.6)
        draw3d(im, o, 960 + math.cos(a) * 900 * d, 500 + math.sin(a) * 480 * d, 90 + 200 * d, t, 1.0, i * .1,
               shadow=False)
    ctext(im, "受け取れ", row_pos("受け取れ", 960, 500, 230, 1.0), 230, t, 4.1, 0.35, "cherry", "slam", seed=3)
    confetti(im, t, 4.1, 960, 500, 50, 3)
    return im


def sc_melodic(t, lt, T, p):  # メロディック チョコレート メンタル
    im = bg("polka", t, 100, 50)
    panels = [(4.7, FACE, 2.3, "メロディック", "berry"), (5.4, WHISK, 2.2, "チョコレート", "choco"),
              (6.2, CHEST, 2.0, "メンタル", "lemon")]
    pw, slant = 640, 130
    pr = cached("pr8", lambda: D.pearl(8))
    for i, (st, pt, z, word, style) in enumerate(panels):
        if t < st - 0.05:
            continue
        k = ease_out((t - st + 0.05) / 0.3)
        cx = 340 + i * 620
        dy = (1 - k) * (H + 200) * (-1 if i % 2 == 0 else 1)
        ph = 760
        content = cam(pt[0] + 30 * math.sin(t + i), pt[1] + 20 * math.cos(t * 1.2 + i), z + 0.1 * (t - st), 0,
                      (pw + slant, ph))
        panel = Image.new("RGBA", content.size, (255, 228, 238, 255))
        panel.alpha_composite(content)
        m = Image.new("L", content.size, 0)
        poly = [(slant, 0), (pw + slant, 0), (pw, ph), (0, ph)]
        ImageDraw.Draw(m).polygon(poly, fill=255)
        pm = Image.new("RGBA", (content.width + 40, ph + 40), (0, 0, 0, 0))
        pm.paste(panel, (20, 20), m)
        dr = ImageDraw.Draw(pm)
        pl = [(x + 20, y + 20) for x, y in poly] + [(poly[0][0] + 20, 20)]
        dr.line(pl, fill=D.WHITE, width=22)
        dr.line(pl, fill=D.RED, width=8)
        for a, b in zip(pl, pl[1:]):
            for u in np.linspace(0, 1, 18):
                D.paste_c(pm, pr, a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        paste(im, pm, cx, 520 + dy)
        draw3d(im, ["bow", "bow_pink", "bow"][i], cx + 60, 150 + dy, 170, 0, 0, 0, 0, shadow=False)
        ctext(im, word, col_pos(word, cx - 180, 530 + dy, 100, 1.0), 100, t, st, 0.5, style, "spin", seed=i)
    Float(4, 6, ["candy", "candy_p", "macaron", "cherry"], (60, 110)).draw(im, t)
    return im


def sc_okonomi(t, lt, T, p):  # お好み通り
    im = bg("gingham_red", t, -40, 20)
    char_full(im, t, 1330 + 40 * math.sin(lt * 0.8), 560 + 12 * math.sin(t * 2), 0.98 + 0.04 * lt)
    items = [("strawberry", "いちご♡"), ("macaron", "ミルク"), ("choco_heart", "ビター"), ("cupcake", "めろめろ♡")]

    def menu(w, h):
        c = Image.new("RGBA", (w, h), (255, 250, 244, 255))
        c.alpha_composite(D.gingham(w, 90, (255, 250, 244), (255, 120, 170, 70), 40))
        dr = ImageDraw.Draw(c)
        dr.text((w / 2, 48), "Recipe", font=ImageFont.truetype(A["font"], 52), anchor="mm", fill=D.RED,
                stroke_width=5, stroke_fill=D.WHITE)
        for i in range(0, w, 30):
            dr.polygon(heart_pts(i + 15, 100, 7), fill=(255, 150, 190))
        fi = ImageFont.truetype(A["font"], 40)
        for i, (obj, name) in enumerate(items):
            ti = 7.4 + i * 0.5
            yy = 175 + i * 112
            if t < ti:
                continue
            k = ease_out_back((t - ti) / 0.25)
            draw3d(c, obj, 70, yy, 100 * k, t, 0.8, i * .2, shadow=False)
            dr.text((135, yy), name, font=fi, anchor="lm", fill=D.BROWN)
            bx = w - 70
            dr.polygon(heart_pts(bx, yy, 30), fill=D.RED)
            dr.polygon(heart_pts(bx, yy, 24), fill=D.WHITE if t < ti + 0.25 else (255, 110, 160))
            if t > ti + 0.25:
                dr.polygon(heart_pts(bx - 6, yy - 5, 8), fill=D.WHITE)
        return c
    card(im, 450, 540, 560, 620, menu, ease_out_back(lt / 0.3), -3 + 2 * math.sin(t), col=D.RED)
    ctext(im, "お好み通り", row_pos("お好み通り", 1270, 260, 150), 150, t, 7.4, 1.2, "cherry", "drop", seed=5)
    Float(6, 5, ["cherry", "macaron", "candy"], (60, 110)).draw(im, t)
    return im


def make_pot():
    def d(dr, k):
        dr.rounded_rectangle([20 * k, 40 * k, 230 * k, 210 * k], radius=int(50 * k), fill=(255, 150, 195),
                             outline=D.WHITE, width=int(9 * k))
        dr.polygon([(215 * k, 80 * k), (290 * k, 45 * k), (296 * k, 66 * k), (228 * k, 118 * k)],
                   fill=(255, 150, 195))
        dr.rectangle([20 * k, 120 * k, 230 * k, 140 * k], fill=D.RED)
        for i in range(4):
            dr.polygon(heart_pts((62 + i * 42) * k, 175 * k, 12 * k), fill=D.WHITE)
    from make_video import supersample
    return supersample(310, 240, d, 2)


def sc_cook(t, lt, T, p):  # 型に流して 冷やして できあがり
    cold = clamp01((t - 11.1) / 0.3) * (1 - clamp01((t - 12.0) / 0.3))
    im = bg("polka_cream", t, 30, 30)
    if cold > 0:
        im = Image.blend(im, bg("frosty", t), cold * 0.7)
    char_full(im, t, 1470, 560 + 10 * math.sin(t * 2), 0.8)
    cx, cy, S = 650, 470, 600
    if t < 12.0:
        mold = Image.new("RGBA", (S + 80, S + 80), (0, 0, 0, 0))
        dr = ImageDraw.Draw(mold)
        c = (S + 80) / 2
        dr.polygon(heart_pts(c, c + S * .04, S * .5 + 32), fill=D.WHITE)
        dr.polygon(heart_pts(c, c + S * .04, S * .5 + 22), fill=D.GOLD)
        dr.polygon(heart_pts(c, c + S * .04, S * .5 + 8), fill=D.RED)
        dr.polygon(heart_pts(c, c + S * .04, S * .5 - 8), fill=(255, 215, 230))
        lvl = ease_io((t - 10.0) / 1.0)
        fill = Image.new("RGBA", mold.size, (0, 0, 0, 0))
        fd = ImageDraw.Draw(fill)
        top_y = c + S * .45 - lvl * S * .95
        pts = [(x, top_y + 12 * math.sin(x / 38 + t * 7)) for x in range(0, S + 81, 10)]
        fd.polygon(pts + [(S + 80, S + 80), (0, S + 80)], fill=(104, 52, 34))
        fd.line(pts, fill=(160, 92, 64), width=10)
        hm = Image.new("L", mold.size, 0)
        ImageDraw.Draw(hm).polygon(heart_pts(c, c + S * .04, S * .5 - 8), fill=255)
        mold.paste(fill, (0, 0), Image.fromarray(np.minimum(np.asarray(hm), np.asarray(fill.getchannel("A")))))
        if t < 11.1:
            ImageDraw.Draw(mold).rounded_rectangle([c - 22 + 6 * math.sin(t * 12), 0, c + 22, top_y + 10],
                                                  radius=20, fill=(104, 52, 34))
        if cold > 0:
            mold = tint(mold, (255, 245, 250), 0.45 * cold)
        pr = cached("pr10", lambda: D.pearl(10))
        for (x, y) in heart_pts(c, c + S * .04, S * .5 + 40, 50):
            D.paste_c(mold, pr, x, y)
        paste(im, mold, cx, cy, 1 + 0.02 * p)
        if t < 11.1:
            paste(im, cached("pot", make_pot), cx + 90, 170 + 8 * math.sin(t * 5), 1.0, -35)
        if cold > 0:
            tw = cached("twk", lambda: D.twinkle(50))
            for i in range(30):
                rnd = random.Random(i)
                y = (rnd.uniform(0, H) + (t - 11.1) * 240) % H
                paste(im, tw, rnd.uniform(0, W), y, rnd.uniform(.5, 1.3) * cold, t * 90 + i * 20)
    else:
        k = ease_out_back((t - 12.0) / 0.35)
        draw3d(im, "choco_heart", cx, cy - 20 * math.sin(t * 3), 540 * k, t, 0.9)
        for i, o in enumerate(["bow", "strawberry", "macaron", "cherry", "bow_pink", "cookie"]):
            a = i * math.pi / 3 + t * 1.2
            draw3d(im, o, cx + math.cos(a) * 360 * k, cy + math.sin(a) * 260 * k, 110 * k, t, .7, i * .2,
                   shadow=False)
        confetti(im, t, 12.0, cx, cy, 70, 2)
    for st, en, word in ((9.95, 11.1, "型に流して"), (11.15, 12.0, "冷やして"), (12.05, 13.4, "できあがり")):
        if st - 0.05 <= t < en:
            ctext(im, word, row_pos(word, cx, 830, 108), 108, t, st, 0.55, out_t=en - 0.1 if en < 13 else None,
                  seed=int(st), bubble=D.RED if word != "冷やして" else (255, 150, 195))
    return im


def sc_heart(t, lt, T, p):  # ハートに 割れ目 できませんように
    im = bg("quilt_red", t, 40, -20)
    paste(im, A["doily"], 960, 490, 1.2, t * 15)
    S = 620
    face = cam(FACE[0], FACE[1] + 25, 1.75 + 0.08 * lt, 0, (S, S))
    back = Image.new("RGBA", (S, S), (255, 205, 225, 255))
    back.alpha_composite(face)
    gap = 0
    if t >= 14.6:
        gap = 36 * ease_out((t - 14.6) / 0.2) * (1 - ease_io((t - 15.2) / 0.5))
    sh = random.Random(int(t * 30)).uniform(-1, 1) * (14 if 14.6 <= t < 15.1 else 0)
    cy = 480
    if gap > 0.5:
        full = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        full.paste(back, (0, 0), heart_mask(S))
        paste(im, full.crop((0, 0, S // 2, S)), 960 - S / 4 - gap + sh, cy, rot=gap * 0.15)
        paste(im, full.crop((S // 2, 0, S, S)), 960 + S / 4 + gap + sh, cy, rot=-gap * 0.15)
    else:
        fancy_heart(im, 960 + sh, cy, S, back)
    if t >= 14.6:
        dr = ImageDraw.Draw(im)
        pts = [(960 + (18 if i % 2 else -18), cy - 250 + i * 55) for i in range(10)]
        if t < 15.2:
            q = clamp01((t - 14.6) / 0.15)
            dr.line(pts[:max(2, int(len(pts) * q))], fill=(60, 20, 30), width=10, joint="curve")
        else:
            for i, (x, y) in enumerate(pts[:-1]):
                if t > 15.2 + i * 0.08:
                    dr.line([(x - 26, y + 10), (x + 26, y + 30)], fill=D.WHITE, width=11)
                    dr.line([(x - 26, y + 10), (x + 26, y + 30)], fill=(255, 90, 160), width=6)
    for i, o in enumerate(["heart", "heart_white", "cherry", "macaron", "strawberry"]):
        a = i * 2 * math.pi / 5 + t * 1.3
        draw3d(im, o, 960 + math.cos(a) * 560, cy + math.sin(a) * 300, 100 + 30 * math.sin(a), t, .8, a)
    ctext(im, "ハートに", arc_pos("ハートに", 960, cy + 40, 450, -150, -30), 100, t, 13.7, 0.6, "cherry", seed=7)
    if t >= 14.6:
        ctext(im, "割れ目", col_pos("割れ目", 1640, 480, 160), 160, t, 14.6, 0.35, "lemon", "slam", seed=8,
              shake=8 if t < 15.1 else 0)
    ctext(im, "できませんように", row_pos("できませんように", 960, 850, 90), 90, t, 15.15, 1.0, bubble=(255, 120, 170))
    return im


def sc_ice(t, lt, T, p):  # 絶対零度で 固めて とじこめる
    im = Image.blend(bg("quilt_pink", t, 20, 10), bg("frosty", t), 0.5)
    paste(im, cached("sil", lambda: M.make_silhouettes()), W / 2, H / 2 - (t * 30) % 300 + 150)
    tw = cached("twk", lambda: D.twinkle(50))
    for i in range(40):
        rnd = random.Random(i + 100)
        y = (rnd.uniform(0, H) + t * rnd.uniform(60, 160)) % H
        paste(im, tw, rnd.uniform(0, W) + 30 * math.sin(t + i), y, rnd.uniform(.4, 1.1), t * 60 + i * 30)
    z = 1.0 + 0.3 * ease_io(lt / T)
    c = cam(720, 430, z, 0)
    im.alpha_composite(c)
    if t >= 17.85:
        k = ease_out_back((t - 17.85) / 0.3)
        paste(im, cached("cube", make_cube), 960, 440, k)
    if t >= 19.45:
        k = ease_out((t - 19.45) / 0.35)
        band = cached("xband", make_xband)
        paste(im, band, 960 - (1 - k) * 1600, 440 - (1 - k) * 900, 1, -28)
        paste(im, band, 960 + (1 - k) * 1600, 440 - (1 - k) * 900, 1, 28)
        kk = ease_out_back((t - 19.7) / 0.3)
        draw3d(im, "heart", 960, 440, 260 * kk, t, 0.5)
        if kk > 0.5:
            dr = ImageDraw.Draw(im)
            dr.ellipse([948, 420, 972, 444], fill=D.GOLD)
            dr.polygon([(952, 438), (968, 438), (964, 470), (956, 470)], fill=D.GOLD)
    rows = [(16.7, 17.85, "絶対零度で", 140), (17.85, 19.45, "固めて", 180), (19.45, 99, "とじこめる", 150)]
    for st, en, word, size in rows:
        if st <= t < en + 0.2:
            ctext(im, word, row_pos(word, 960, 815, size), size, t, st, 0.6, "milk", "drop",
                  out_t=en if en < 99 else None, seed=int(st * 10))
    return im


def make_cube():
    w, h = 880, 720
    from make_video import supersample

    def d(dr, k):
        dr.rounded_rectangle([0, 0, w * k, h * k], radius=int(80 * k), fill=(255, 240, 248, 70),
                             outline=(255, 255, 255, 240), width=int(16 * k))
        dr.rounded_rectangle([30 * k, 30 * k, (w - 30) * k, (h - 30) * k], radius=int(60 * k),
                             outline=(255, 180, 210, 180), width=int(6 * k))
        for i in range(3):
            dr.line([((90 + i * 60) * k, 60 * k), ((50 + i * 60) * k, 220 * k)], fill=(255, 255, 255, 190),
                    width=int(14 * k))
    return supersample(w, h, d, 1)


def make_xband():
    w, h = 2600, 120
    im = D.candy_stripe(w, h, (D.RED, D.WHITE), 40)
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, w, 12], fill=D.WHITE)
    dr.rectangle([0, h - 12, w, h], fill=D.WHITE)
    for x in range(0, w, 30):
        dr.ellipse([x, -8, x + 24, 16], fill=D.WHITE)
        dr.ellipse([x, h - 16, x + 24, h + 8], fill=D.WHITE)
    return im


def sc_ribbon(t, lt, T, p):  # しろくろリボン 強く結んだなら
    im = bg("mono", t, 90, 0)
    k = ease_io(lt / T)
    sy = SHOES[1] + (FACE[1] - SHOES[1]) * k
    sx = SHOES[0] + (FACE[0] - SHOES[0]) * k
    im.alpha_composite(desat(cam(sx, sy, 1.9 - 0.3 * k, -6 + 6 * k), 0.3))
    dr = ImageDraw.Draw(im)
    pr = cached("pr9", lambda: D.pearl(9))
    for j, (col, edge, yb, amp) in enumerate((((255, 255, 255), D.RED, 230, 60), ((30, 28, 30), D.PINK, 900, 50),
                                               (D.PINK, D.WHITE, 560, 80))):
        pts = [(x, yb + amp * math.sin(x / 190 + t * 3 + j * 2)) for x in range(-40, W + 60, 30)]
        dr.line(pts, fill=edge, width=70, joint="curve")
        dr.line(pts, fill=col, width=52, joint="curve")
        if j == 2:
            for x, y in pts[::2]:
                D.paste_c(im, pr, x, y)
    if t >= 22.6:
        k2 = ease_out_back((t - 22.6) / 0.4)
        spr = A["3d"]["bow_bw"]
        idx = int(clamp01((t - 22.6) / 0.6) * len(spr) * 2) % len(spr) if t < 23.2 else 0
        paste(im, spr[idx], 450, 380, k2 * (1 + 0.08 * p), (1 - k2) * 30)
    btext(im, "しろくろリボン", 960, 800, t, 21.45, 96, "milk", out_t=22.55)
    if t >= 22.6:
        btext(im, "強く結んだなら", 1000, 800, t, 22.65, 96, "milk", seed=2)
    return im


def sc_gift(t, lt, T, p):  # できあがりよ
    im = bg("rays_pink", t, rot=40)
    if t >= 25.55:
        char_full(im, t, 1400, 560, 0.95)
        k = ease_out_back((t - 25.55) / 0.35)
        draw3d(im, "gift", 560, 470, 460 * k, t, 0.7)
        confetti(im, t, 25.55, 560, 470, 70, 4)
    if t < 25.75:
        q = clamp01((t - 25.05) / 0.5)

        def load(w, h):
            c = Image.new("RGBA", (w, h), (255, 248, 240, 255))
            dr = ImageDraw.Draw(c)
            f = ImageFont.truetype(A["font"], 58)
            dr.text((w / 2, h * .25), "Now Baking...", font=f, anchor="mm", fill=D.RED, stroke_width=5,
                    stroke_fill=D.WHITE)
            dr.rounded_rectangle([50, h * .5, w - 50, h * .5 + 80], radius=40, fill=D.WHITE, outline=D.RED, width=7)
            for i in range(10):
                hx = 90 + i * (w - 180) / 9
                dr.polygon(heart_pts(hx, h * .5 + 40, 22), fill=D.RED if i < int(q * 10) + 1 and q > 0 else D.LPINK)
            dr.text((w / 2, h * .83), f"{int(q * 100)}%", font=f, anchor="mm", fill=(255, 110, 160))
            return c
        out = clamp01((t - 25.55) / 0.2)
        card(im, 960, 470, 860, 480, load, ease_out_back(lt / 0.25) * (1 + out * 0.5), 0, 1 - out, col=D.RED)
    ctext(im, "できあがりよ", row_pos("できあがりよ", 960, 830, 108), 108, t, 25.15, 0.8, bubble=D.RED)
    return im


def sc_grid(t, lt, T, p):  # 欲しいならあげる
    im = bg("stripe", t, 100, 0)
    shots = [(FACE, 2.4), (WHISK, 2.0), (CHEST, 1.8), (SHOES, 1.6), (FULL, 0.62), (LEGS, 1.6), (FACE, 3.2),
             ((900, 470), 1.9), ((1250, 420), 1.8)]
    cols = [D.PINK, D.RED, (255, 200, 90), D.BROWN, D.PINK, D.RED, (255, 200, 90), D.PINK, D.BROWN]
    order = [4, 0, 8, 2, 6, 1, 3, 7, 5]
    for n, i in enumerate(order):
        ti = 26.5 + n * 0.13
        if t < ti:
            continue
        r, c = divmod(i, 3)
        (sx, sy), z = shots[i]
        x = 340 + c * 620 + 8 * math.sin(t * 3 + i)
        y = 250 + r * 290 + 8 * math.cos(t * 3 + i)

        def content(w, h, sx=sx, sy=sy, z=z, i=i):
            return cam(sx + 25 * math.sin(t * 1.5 + i), sy + 15 * math.cos(t * 1.3 + i), z, 0, (w, h))
        card(im, x, y, 470, 200, content, ease_out_back((t - ti) / 0.2), 3 * math.sin(i), col=cols[i],
             bgcol=(255, 225, 238), bow=False)
    Float(21, 8, ["gift", "heart", "choco_heart", "bow", "strawberry"], (90, 150), vy=(-170, -90)).draw(im, t)
    btext(im, "欲しいならあげる", 960, 520, t, 26.55, 100, "milk", seed=4)
    return im


def sc_final(t, lt, T, p):  # 君をめろつかせちゃうぞ
    im = bg("rays_red", t, rot=-60)
    S = 660
    z = 2.0 + 0.22 * p + 0.15 * lt
    back = Image.new("RGBA", (S, S), (255, 200, 225, 255))
    back.alpha_composite(cam(FACE[0], FACE[1] + 15, z, 0, (S, S)))
    for i in range(16):
        rnd = random.Random(i + 50)
        a = rnd.uniform(0, 2 * math.pi)
        d = ((lt * rnd.uniform(0.5, 1.0) + rnd.random()) % 1.2) / 1.2
        draw3d(im, rnd.choice(SWEETS), 1330 + math.cos(a) * d * 1100, 480 + math.sin(a) * d * 700, 60 + d * 200,
               t, 1.0, rnd.random(), shadow=False)
    s2 = int(S * (1 + 0.04 * p))
    fancy_heart(im, 1330, 470, s2, back.resize((s2, s2)))
    ctext(im, "君を", [(310, 300), (560, 300)], 240, t, 28.6, 0.3, "cherry", "slam", seed=11)
    text = "めろつかせちゃうぞ"
    pos = [(170 + i * 140, 570 + 22 * math.sin(i * 1.4)) if i < 5 else (260 + (i - 5) * 140, 760)
           for i in range(len(text))]
    ctext(im, text, pos, 138, t, 29.3, 1.1, "berry", "fly", seed=12, shake=6 * p)
    confetti(im, t, 29.3, 1330, 470, 60, 9, 1200)
    return im


SCENES = [
    (0.0, 2.2, sc_intro, "white"),
    (2.2, 4.1, sc_hakike, "iris"),
    (4.1, 4.7, sc_uketore, "flash"),
    (4.7, 7.25, sc_melodic, "slide"),
    (7.25, 9.8, sc_okonomi, "iris"),
    (9.8, 13.3, sc_cook, "zoom"),
    (13.3, 16.65, sc_heart, "flash"),
    (16.65, 21.2, sc_ice, "white"),
    (21.2, 25.0, sc_ribbon, "whip"),
    (25.0, 26.5, sc_gift, "flash"),
    (26.5, 28.5, sc_grid, "zoom"),
    (28.5, 99, sc_final, "iris"),
]


def render(fi):
    M.SCENES = SCENES
    t = fi / FPS
    p = float(A["pulse"][min(fi, len(A["pulse"]) - 1)])
    im, flash = M.compose(t, p)
    # ハートのフラッシュは白よりピンク寄りに
    frame_layer(im, t, p)
    if p > 0.05:
        s = 1 + 0.02 * p
        z = im.resize((int(W * s), int(H * s)), Image.BILINEAR)
        im = z.crop(((z.width - W) // 2, (z.height - H) // 2, (z.width - W) // 2 + W, (z.height - H) // 2 + H))
    im = ImageEnhance.Color(im.convert("RGB")).enhance(1.12)
    arr = np.asarray(im).astype(np.float32) / 255
    if flash > 0:
        arr = arr * (1 - flash) + np.array([1.0, 0.93, 0.96]) * flash
    end_t = A["nframes"] / FPS
    if t > end_t - 0.45:
        k = clamp01((t - (end_t - 0.45)) / 0.4)
        m = Image.new("L", (W, H), 255)
        ImageDraw.Draw(m).polygon(heart_pts(1330, 480, max(1, 1400 * (1 - ease_io(k)))), fill=0)
        mm = np.asarray(m).astype(np.float32)[..., None] / 255
        arr = arr * (1 - mm) + np.array([0.35, 0.05, 0.14]) * mm
    out = (arr * 255).clip(0, 255).astype(np.uint8)
    out = M.rgb_split(out, 6 * max(0, p - 0.6))
    return out.tobytes()


def build(args, pool):
    ch = Image.open(args.image).convert("RGBA")
    ch = ImageEnhance.Contrast(ImageEnhance.Color(ch).enhance(1.1)).enhance(1.08)
    A["char2"] = ch.resize((ch.width * 2, ch.height * 2), Image.LANCZOS)
    A["font"], A["font_sub"] = args.font, args.font_sub
    A["fpop"], A["fcute"] = args.font, args.font_sub
    A["3d"] = render3d.build_sprites(pool, args.cache, SPRITES)
    A["bg"] = make_bgs()
    A["frame"] = make_frame()
    A["drips"] = make_drips()
    A["tag"] = make_tag(args.font_sub)
    A["doily"] = make_doily(1000)
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
    ap.add_argument("--font", required=True, help="メインのポップ体 (Mochiy Pop One など)")
    ap.add_argument("--font-sub", required=True, help="小さい文字用 (Hachi Maru Pop など)")
    ap.add_argument("--out", default="cute.mp4")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    with Pool(args.jobs) as pool:
        build(args, pool)
    M.SCENES = SCENES
    if args.preview:
        for s in args.preview:
            Image.frombytes("RGB", (W, H), render(int(s * FPS))).save(f"cute_{s:05.2f}.png")
        return
    enc = subprocess.Popen([args.ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", args.audio,
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-b:v", "6500k",
                            "-maxrate", "8000k", "-bufsize", "12000k", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out], stdin=subprocess.PIPE)
    with Pool(args.jobs) as pool:
        for i, fr in enumerate(pool.imap(render, range(A["nframes"]), chunksize=2)):
            enc.stdin.write(fr)
            if i % 60 == 0:
                print(f"frame {i}/{A['nframes']}", flush=True)
    enc.stdin.close()
    enc.wait()


if __name__ == "__main__":
    main()
