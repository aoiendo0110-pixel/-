"""人物 (差し替え可能) が主役の、ピンク×フリル×リボンのロリータ系ステージMV.

  python3 make_stage_mv.py --subject person.png --audio source.mov --font Mochiy.ttf --font-sub Hachi.ttf \
      --cache cache3d --out stage_mv.mp4

--subject は透過PNG推奨。白背景の画像なら白を自動で抜く。
人物の上には何も重ねない (装飾・パーティクルは全部うしろ、歌詞は人物を避けて配置)。
"""
import argparse
import math
import random
import subprocess
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import deco as D
import render3d

W, H, FPS = 1920, 1080, 30
WW, WH = 2560, 1440                 # ステージ全体 (ワールド) の大きさ
SUBJ_C = (1280, 760)                # 人物の中心 (ワールド)
SUBJ_H = 1040                       # 人物の高さ (ワールド)
FACE_Y = 0.24                       # 人物の上から何割が「顔」か

PINK = (247, 161, 196)
DPINK = (240, 110, 160)
LPINK = (255, 228, 238)
RED = (226, 64, 110)
WHITE = (255, 255, 255)
GOLD = (236, 196, 120)

A = {}
_c = {}


def cached(k, fn):
    if k not in _c:
        _c[k] = fn()
    return _c[k]


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def smooth(x):
    x = clamp01(x)
    return x * x * x * (x * (x * 6 - 15) + 10)


def spring(t, freq=14.0, damp=7.0):
    return 0.0 if t <= 0 else 1 - math.exp(-damp * t) * math.cos(freq * t)


def paste(dst, src, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.BILINEAR)
    if abs(rot) > 0.05:
        src = src.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 0.999:
        src = src.copy()
        src.putalpha(src.getchannel("A").point(lambda v: int(v * alpha)))
    D._clip(dst, src, int(cx - src.width / 2), int(cy - src.height / 2))


def ss(w, h, fn, k=2):
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    fn(ImageDraw.Draw(im), k)
    return im.resize((w, h), Image.LANCZOS)


# ---- 主役 (人物) --------------------------------------------------------------
def load_subject(path):
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    if a[..., 3].min() > 250:  # 透過なし → 白を抜く
        whiteness = a[..., :3].min(-1)
        alpha = np.clip((255 - whiteness) / 40, 0, 1) * 255
        # 白に近い部分の色を戻す (白フチのにじみ対策)
        a[..., 3] = alpha
    im = Image.fromarray(a.astype(np.uint8), "RGBA")
    im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox())
    sc = SUBJ_H / im.height
    im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
    # 白いフチ + ピンクのグロー + 影 (ステッカー風で主役を目立たせる)
    pad = 60
    base = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    al = Image.new("L", base.size, 0)
    al.paste(im.getchannel("A"), (pad, pad))
    border = al.filter(ImageFilter.MaxFilter(25)).filter(ImageFilter.GaussianBlur(1.5))
    glow = al.filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(22))
    shadow = al.filter(ImageFilter.GaussianBlur(20))
    out = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sh = Image.new("RGBA", base.size, (190, 60, 120, 0))
    sh.putalpha(shadow.point(lambda v: int(v * 0.45)))
    out.alpha_composite(sh, (14, 24))
    g = Image.new("RGBA", base.size, (255, 150, 200, 0))
    g.putalpha(glow.point(lambda v: int(v * 0.9)))
    out.alpha_composite(g)
    wb = Image.new("RGBA", base.size, (255, 255, 255, 0))
    wb.putalpha(border)
    out.alpha_composite(wb)
    out.alpha_composite(im, (pad, pad))
    A["subj_inner"] = im.size
    return out


# ---- ステージのレイヤー ----------------------------------------------------------
PADW = 900  # レイヤーの外側の余白 (カメラが端に寄っても黒くならない)


def make_bg():
    bw, bh = WW + PADW * 2, WH + PADW * 2
    g = np.linspace(0, 1, bh)[:, None, None]
    top, bot = np.array([255, 222, 236]), np.array([255, 240, 246])
    arr = (top * (1 - g) + bot * g).repeat(bw, 1)
    im = Image.fromarray(arr.astype(np.uint8), "RGB")
    dr = ImageDraw.Draw(im)
    for x in range(0, bw, 120):
        dr.rectangle([x, 0, x + 54, bh], fill=(255, 214, 230))
        dr.line([(x + 80, 0), (x + 80, bh)], fill=(255, 246, 250), width=3)
    for j, y in enumerate(range(60, bh, 120)):
        for x in range(90 if j % 2 else 30, bw, 120):
            dr.polygon(D.heart_pts(x, y, 11), fill=(255, 176, 206))
    return im


def make_backdrop():
    """人物のうしろのアーチ枠 (レース + パール + リボン)."""
    im = Image.new("RGBA", (WW, WH), (0, 0, 0, 0))
    aw, ah = 1320, 1300
    cx, bottom = SUBJ_C[0], 1360
    top = bottom - ah
    r = aw / 2

    def arch(inset):
        pts = []
        for i in range(61):
            a = math.pi + math.pi * i / 60
            pts.append((cx + (r - inset) * math.cos(a), top + r + (r - inset) * math.sin(a)))
        pts += [(cx + r - inset, bottom), (cx - r + inset, bottom)]
        return pts
    # 光 (中が明るい)
    glow = Image.new("L", (WW, WH), 0)
    ImageDraw.Draw(glow).polygon(arch(40), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    lay = Image.new("RGBA", (WW, WH), (255, 250, 252, 0))
    lay.putalpha(glow.point(lambda v: int(v * 0.95)))
    # レースの縁
    dr = ImageDraw.Draw(im)
    outline = arch(0)
    for (x, y) in outline[:61]:
        dr.ellipse([x - 34, y - 34, x + 34, y + 34], fill=(255, 255, 255, 255))
    for side in (-1, 1):
        for y in np.arange(top + r, bottom, 40):
            dr.ellipse([cx + side * r - 34, y - 34, cx + side * r + 34, y + 34], fill=(255, 255, 255, 255))
    dr.polygon(arch(-10), fill=(255, 255, 255, 255))
    dr.polygon(arch(12), fill=PINK + (255,))
    dr.polygon(arch(26), fill=(255, 255, 255, 255))
    dr.polygon(arch(34), fill=(255, 238, 244, 255))
    im.alpha_composite(lay)
    # 穴あきレース
    for (x, y) in outline[:61:2]:
        dr.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 214, 230, 255))
    # パール
    pr = D.pearl(11)
    for (x, y) in arch(19)[:61]:
        D.paste_c(im, pr, x, y)
    for side in (-1, 1):
        for y in np.arange(top + r, bottom, 23):
            D.paste_c(im, pr, cx + side * (r - 19), y)
    # 宝石のハート
    gem = D.gem_heart(46, RED)
    for i in range(0, 61, 10):
        x, y = outline[i]
        D.paste_c(im, gem, x, y)
    A["arch"] = (cx, top, r, bottom)
    return im


def make_curtain(side):
    """左右のカーテン (ひだ + フリルの縁 + タッセルの位置でしぼる)."""
    w, h = 640 + PADW, WH
    arr = np.zeros((h, w, 4), np.float32)
    ys = np.arange(h)[:, None]
    xs = np.arange(w)[None, :]
    pinch_y = 900
    pinch = 1 - 0.5 * np.exp(-((ys - pinch_y) / 220.0) ** 2)
    width = (w - PADW) * pinch + PADW * np.where(ys < pinch_y, 1.0, 1.0 + 0.25 * np.clip((ys - pinch_y) / 400, 0, 1))
    width = np.minimum(width, w)
    u = xs / np.maximum(width, 1)
    inside = u <= 1.0
    fold = 0.93 + 0.07 * np.sin(xs / 46.0 + 0.3) + 0.04 * np.sin(xs / 17.0)
    edge = np.clip((width - xs) / 160, 0, 1)  # 内側の縁ほど明るく
    col = np.array([248, 166, 200], np.float32)
    arr[..., :3] = col * fold[..., None] * (0.92 + 0.08 * edge[..., None])
    arr[..., 3] = inside * 255
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")
    dr = ImageDraw.Draw(im)
    # 内側のフリル
    for y in range(0, h, 26):
        ww = float(width[min(y, h - 1), 0])
        dr.ellipse([ww - 24, y - 20, ww + 24, y + 20], fill=(255, 255, 255, 255))
        dr.ellipse([ww - 12, y - 10, ww + 12, y + 10], fill=(255, 226, 238, 255))
    im = im.filter(ImageFilter.SMOOTH)
    if side > 0:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


def make_valance():
    """上の飾り幕 (スワッグ + レース + パール)."""
    h = 230
    TW = WW + 2 * PADW
    n = 14
    sw = TW / n

    def draw(dr, k):
        dr.rectangle([0, 0, TW * k, 60 * k], fill=(240, 120, 170))
        for i in range(n):
            x0 = i * sw
            pts = [(x0 + sw * u, 40 + 120 * math.sin(math.pi * u)) for u in np.linspace(0, 1, 40)]
            poly = [(x * k, 0) for x, _ in pts[:1]] + [(x * k, y * k) for x, y in pts] + [((x0 + sw) * k, 0)]
            dr.polygon(poly, fill=(247, 150, 190))
            for j in range(1, 6):  # ひだ
                v = j / 6
                q = [(x0 + sw * u, 40 + 120 * math.sin(math.pi * u) * v) for u in np.linspace(0.05, 0.95, 30)]
                dr.line([(x * k, y * k) for x, y in q], fill=(232, 120, 165), width=3 * k)
            for x, y in pts[::2]:  # レース
                dr.ellipse([(x - 13) * k, (y - 4) * k, (x + 13) * k, (y + 20) * k], fill=(255, 255, 255))
        dr.rectangle([0, 0, TW * k, 18 * k], fill=GOLD)
    im = ss(TW, h, draw, 1)
    pr = D.pearl(9)
    for i in range(n):
        x0 = i * sw
        for u in np.linspace(0, 1, 34):
            D.paste_c(im, pr, x0 + sw * u, 196 * 0 + 40 + 120 * math.sin(math.pi * u) + 22)
    return im


def make_stage():
    h = 170
    TW = WW + 2 * PADW
    im = Image.new("RGBA", (TW, h), (0, 0, 0, 0))
    im.alpha_composite(D.frill(TW + 100, 150, (247, 150, 190), trim=WHITE, n=80), (-50, 20))
    im.alpha_composite(D.lace(TW + 60, 60), (-30, 18))
    im.alpha_composite(D.stitch_band(TW, 30, (240, 110, 160), stitch=WHITE), (0, 0))
    return im


# ---- カメラ ------------------------------------------------------------------
FACE = (SUBJ_C[0], SUBJ_C[1] - SUBJ_H * (0.5 - FACE_Y))


def shot(kind, zoom=None):
    """人物を画面の決まった位置に置くカメラ. _l は人物が左 (歌詞は右)."""
    z, tx, target_y, anchor_y = {
        "wide_l": (1.02, 700, 560, SUBJ_C[1]),
        "wide_r": (1.02, 1220, 560, SUBJ_C[1]),
        "med_l": (1.2, 560, 540, SUBJ_C[1] - 60),
        "med_r": (1.2, 1360, 540, SUBJ_C[1] - 60),
        "face_l": (1.6, 450, 430, FACE[1]),
        "face_r": (1.6, 1470, 430, FACE[1]),
    }[kind]
    z = zoom or z
    s = W * z / WW
    return (SUBJ_C[0] - (tx - W / 2) / s, anchor_y - (target_y - H / 2) / s, z)


# (時刻, ショット, 移動時間) : 移動時間が短いものはキビキビ、長いものはゆっくり
CAM = [
    (0.0, shot("wide_l", 1.08), 0), (2.1, shot("wide_l", 1.0), 2.1),
    (2.35, shot("med_l"), 0.25), (4.05, shot("face_l", 1.55), 1.7),
    (4.25, shot("face_l", 1.75), 0.15), (4.7, shot("face_l", 1.62), 0.45),
    (4.72, shot("med_r"), 0.18), (5.43, shot("med_l"), 0.18), (6.23, shot("med_r"), 0.18),
    (7.25, shot("med_r", 1.3), 0.9),
    (7.5, shot("wide_r"), 0.25), (9.7, shot("wide_r", 1.08), 2.2),
    (10.0, shot("med_r"), 0.3), (13.2, shot("med_r", 1.3), 3.2),
    (13.5, shot("face_l"), 0.3), (16.5, shot("face_l", 1.75), 3.0),
    (16.9, shot("wide_l", 1.0), 0.4), (21.1, shot("wide_l", 1.08), 4.2),
    (21.45, shot("med_l"), 0.35), (24.9, shot("med_l", 1.3), 3.45),
    (25.2, shot("med_r"), 0.3), (26.4, shot("med_r", 1.28), 1.2),
    (26.8, shot("wide_r", 0.98), 0.4), (28.4, shot("wide_r", 1.02), 1.6),
    (28.7, shot("face_r"), 0.3), (31.0, shot("face_r", 1.9), 2.3),
]


def camera(t):
    prev = CAM[0]
    for c in CAM[1:]:
        t1, target, dur = c
        if t < t1:
            t0 = t1 - dur
            if t <= t0:
                return prev[1]
            u = (t - t0) / dur
            k = smooth(u) if dur < 0.5 else (0.3 * u + 0.7 * smooth(u))
            a, b = prev[1], target
            return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))
        prev = c
    return CAM[-1][1]


def to_screen(wx, wy, cam, f=1.0):
    cx, cy, z = cam
    cxf = WW / 2 + (cx - WW / 2) * f
    cyf = WH / 2 + (cy - WH / 2) * f
    zf = 1 + (z - 1) * f
    vw = WW / zf
    s = W / vw
    return (wx - (cxf - vw / 2)) * s, (wy - (cyf - WH / zf / 2)) * s, s


def view(layer, cam, f, pad=0):
    cx, cy, z = cam
    cxf = WW / 2 + (cx - WW / 2) * f
    cyf = WH / 2 + (cy - WH / 2) * f
    zf = 1 + (z - 1) * f
    vw, vh = WW / zf, WH / zf
    box = (cxf - vw / 2 + pad, cyf - vh / 2 + pad, cxf + vw / 2 + pad, cyf + vh / 2 + pad)
    return layer.transform((W, H), Image.EXTENT, box, Image.BILINEAR)


def subject_box(t, cam):
    """画面上の人物の四角 (白フチ込み)."""
    sw, sh = A["subj_inner"]
    x0, y0, s = to_screen(SUBJ_C[0] - sw / 2 - 20, SUBJ_C[1] - sh / 2 - 20, cam)
    x1, y1, _ = to_screen(SUBJ_C[0] + sw / 2 + 20, SUBJ_C[1] + sh / 2 + 20, cam)
    return (x0, y0, x1, y1)


# ---- 歌詞 ------------------------------------------------------------------
GROUPS = [
    dict(start=0.4, end=2.2, rows=[(0.4, "める散らかして")], pref="right"),
    dict(start=2.3, end=4.05, rows=[(2.3, "吐き気催すまで")], pref="right"),
    dict(start=4.1, end=4.7, rows=[(4.1, "受け取れ")], pref="right", big=True, style="red"),
    dict(start=4.75, end=5.22, rows=[(4.75, "メロディック")], pref="left"),
    dict(start=5.45, end=6.02, rows=[(5.45, "チョコレート")], pref="right"),
    dict(start=6.25, end=7.25, rows=[(6.25, "メンタル")], pref="left", big=True),
    dict(start=7.45, end=9.8, rows=[(7.45, "お好み通り")], pref="left"),
    dict(start=9.95, end=13.3, rows=[(9.95, "型に流して"), (11.15, "冷やして"), (12.05, "できあがり")], pref="left"),
    dict(start=13.6, end=16.65, rows=[(13.6, "ハートに"), (14.6, "割れ目"), (15.15, "できませんように")],
         pref="right"),
    dict(start=16.8, end=21.2, rows=[(16.8, "絶対零度で"), (17.85, "固めて"), (19.45, "とじこめる")], pref="right"),
    dict(start=21.5, end=25.0, rows=[(21.5, "しろくろリボン"), (22.65, "強く結んだなら")], pref="right"),
    dict(start=25.2, end=26.5, rows=[(25.2, "できあがりよ")], pref="left", style="red"),
    dict(start=26.8, end=28.45, rows=[(26.8, "欲しいなら"), (27.5, "あげる")], pref="left"),
    dict(start=28.7, end=99, rows=[(28.7, "君を"), (29.3, "めろつかせ"), (29.95, "ちゃうぞ")], pref="left",
         big=True, style="red"),
]


BREAKS = {"める散らかして": ("める", "散らかして"), "吐き気催すまで": ("吐き気", "催すまで"),
          "できませんように": ("できません", "ように"), "しろくろリボン": ("しろくろ", "リボン"),
          "強く結んだなら": ("強く", "結んだなら"), "欲しいならあげる": ("欲しいなら", "あげる"),
          "絶対零度で": ("絶対", "零度で"), "できあがりよ": ("できあがり", "よ")}


def fit_group(g):
    """人物に重ならない場所と文字サイズを決める (行の表示中ずっと安全な場所)."""
    f0, f1 = int(g["start"] * FPS), int(min(g["end"], 30.9) * FPS)
    boxes = [subject_box(fi / FPS, camera(fi / FPS)) for fi in range(f0, f1 + 1, 2)]
    ux0 = min(b[0] for b in boxes)
    ux1 = max(b[2] for b in boxes)
    uy0 = min(b[1] for b in boxes)
    uy1 = max(b[3] for b in boxes)
    zones = {"left": (60, 150, ux0 - 50, H - 170), "right": (ux1 + 50, 150, W - 60, H - 170),
             "bottom": (80, uy1 + 30, W - 80, H - 60), "top": (80, 60, W - 80, uy0 - 30)}
    split = []
    for st, text in g["rows"]:
        if text in BREAKS:  # 言葉の切れ目で折り返す
            a, b = BREAKS[text]
            split += [(st, a), (st + 0.3 * len(a) / len(text) + 0.1, b)]
        else:
            split.append((st, text))
    best = None
    for rows in (g["rows"], split):
        cand = _fit(rows, zones, g)
        if cand and (best is None or (best[3] < 100 and cand[3] > best[3] * 1.15)):  # 1行で十分大きければ折り返さない
            best = cand + (rows,)
    if best is None:  # どこにも十分な余白がない → 画面下に小さく
        best = ("bottom", W / 2, H - 90, 64, g["rows"])
    return best


def _fit(rows, zones, g):
    n = len(rows)
    longest = max(len(r[1]) for r in rows)
    best = None
    for name in [g["pref"]] + [z for z in ("left", "right", "bottom", "top") if z != g["pref"]]:
        x0, y0, x1, y1 = zones[name]
        zw, zh = x1 - x0, y1 - y0
        if zw < 120 or zh < 100:
            continue
        size = min((zw - 80) / (longest * 1.02), (zh - 60) / (n * 1.35), 200 if g.get("big") else 150)
        if size >= 64:
            best = (name, (x0 + x1) / 2, (y0 + y1) / 2, size)
            break
        if not best or size > best[3]:
            best = (name, (x0 + x1) / 2, (y0 + y1) / 2, size)
    return best


def lolita_styles():
    D.STYLES["lolita"] = dict(top=(255, 255, 255), bot=(255, 222, 236), stroke=DPINK, outer=WHITE,
                              shadow=(210, 80, 140))
    D.STYLES["lolita_red"] = dict(top=(255, 170, 196), bot=(226, 50, 100), stroke=WHITE, outer=(250, 140, 185),
                                  shadow=(160, 30, 80))


def csprite(ch, size, style):
    return cached(("c", ch, size, style), lambda: D.cute_char(ch, size, style, A["font"]))


def plate(w, h):
    def mk():
        pad = 40
        im = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))

        def d(dr, k):
            x0, y0, x1, y1 = pad * k, pad * k, (pad + w) * k, (pad + h) * k
            r = 16 * k
            for x in np.arange(x0, x1, r * 1.5):
                for y in (y0, y1):
                    dr.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 235))
            for y in np.arange(y0, y1, r * 1.5):
                for x in (x0, x1):
                    dr.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 235))
            dr.rounded_rectangle([x0, y0, x1, y1], radius=int(28 * k), fill=(255, 255, 255, 225))
            dr.rounded_rectangle([x0 + 12 * k, y0 + 12 * k, x1 - 12 * k, y1 - 12 * k], radius=int(20 * k),
                                 outline=(247, 161, 196, 255), width=int(3 * k))
        im = ss(im.width, im.height, d, 2)
        return im
    return cached(("plate", w, h), mk)


def draw_lyrics(im, t, p):
    for gi, g in enumerate(GROUPS):
        if t < g["start"] - 0.1 or t > g["end"] + 0.35:
            continue
        zone, cx, cy, size, rows = A["layout"][gi]
        size = int(size)
        style = "lolita_red" if g.get("style") == "red" else "lolita"
        n = len(rows)
        bh = n * size * 1.35 + 10
        out_u = clamp01((t - g["end"]) / 0.3) if t > g["end"] else 0.0
        k = spring(t - g["start"] + 0.1, 11, 6)
        vis = sum(1 for r in rows if t >= r[0] - 0.05)
        vw = max(len(r[1]) for r in rows[:max(vis, 1)]) * size * 1.02 + 40
        ph = max(vis, 1) * size * 1.35 + 10
        top_y = cy - bh / 2
        pl = plate(int(vw) // 20 * 20 + 20, int(ph) // 20 * 20 + 20)
        paste(im, pl, cx, top_y + ph / 2, 0.85 + 0.15 * k, 0, clamp01(k * 2) * (1 - out_u))
        bow = cached("bow_s", lambda: A["3d"]["bow_pink"][0].resize((150, 150), Image.LANCZOS))
        paste(im, bow, cx - vw / 2 - 10, top_y - 12, 0.8 + 0.2 * k, -18, clamp01(k * 2) * (1 - out_u))
        rnd = random.Random(gi)
        for ri, (st, text) in enumerate(rows):
            ry = cy - bh / 2 + 5 + size * 1.35 * (ri + 0.5)
            nxt = rows[ri + 1][0] if ri + 1 < n else min(g["end"], st + 2.0)
            span = max(0.2, min(0.6, (nxt - st) * 0.55))
            m = len(text)
            for i, ch in enumerate(text):
                lt = t - (st + span * i / m)
                if lt < 0:
                    continue
                kk = spring(lt, 15, 7)
                x = cx + (i - (m - 1) / 2) * size * 1.02
                y = ry + (1 - kk) * 40 + 4 * math.sin(t * 3 + i * 0.8)
                rot = rnd.uniform(-20, 20) * (1 - smooth(lt / 0.35)) + 2 * math.sin(t * 2 + i)
                a = clamp01(lt / 0.06)
                sc = kk * (1 + 0.04 * p)
                if out_u > 0:
                    u = clamp01(out_u * 1.6 - i / m * 0.6)
                    sc *= (1 + 0.2 * math.sin(u * math.pi)) * (1 - smooth(u))
                    a *= 1 - smooth(u)
                paste(im, csprite(ch, size, style), x, y, sc, rot, a)


# ---- うしろのパーティクル --------------------------------------------------------
class Particles:
    def __init__(self):
        rnd = random.Random(3)
        self.items = [dict(x=rnd.uniform(0, W), y=rnd.uniform(0, H), s=rnd.uniform(0.35, 1.0), vy=rnd.uniform(-60, -20),
                           ph=rnd.random() * 6, k=rnd.choice(["heart", "heart", "bow", "spark", "pearl"]),
                           c=rnd.choice([PINK, WHITE, (255, 200, 220), RED])) for _ in range(40)]

    def draw(self, im, t, burst=0.0):
        dr = ImageDraw.Draw(im)
        tw = cached("tw", lambda: D.twinkle(48))
        for it in self.items:
            y = (it["y"] + it["vy"] * t) % (H + 120) - 60
            x = it["x"] + 30 * math.sin(t * 0.9 + it["ph"])
            s = it["s"]
            if it["k"] == "heart":
                dr.polygon(D.heart_pts(x, y, 20 * s), fill=it["c"] + (200,))
            elif it["k"] == "bow":
                paste(im, A["3d"]["bow_pink"][int(t * 6 + it["ph"] * 4) % 24], x, y, 0.35 * s, 10 * math.sin(t + it["ph"]))
            elif it["k"] == "pearl":
                paste(im, cached("pr14", lambda: D.pearl(14)), x, y, s)
            else:
                paste(im, tw, x, y, s * (0.5 + 0.5 * abs(math.sin(t * 4 + it["ph"]))), t * 40)


def heart_burst(im, t, t0, cx, cy, seed, n=24, spread=700):
    if not (t0 <= t < t0 + 1.4):
        return
    rnd = random.Random(seed)
    u = t - t0
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        d = (1 - math.exp(-u * 4)) * rnd.uniform(200, spread)
        x, y = cx + math.cos(a) * d, cy + math.sin(a) * d * 0.8 - u * 60
        sprite = A["3d"][rnd.choice(["heart", "heart_white", "bow_pink"])]
        paste(im, sprite[int(u * 20 + rnd.random() * 20) % len(sprite)], x, y, rnd.uniform(0.25, 0.45) * (1 - u / 1.4 * 0.6),
              0, clamp01((1.4 - u) * 2))


def ribbons_behind(im, t, cam):
    """人物のうしろを横切るリボン (しろくろ / 赤)."""
    if 19.45 <= t < 21.3:
        k = smooth((t - 19.45) / 0.4)
        cols = [(RED, WHITE), (DPINK, WHITE)]
    elif 21.3 <= t < 25.1:
        k = 1.0
        cols = [((30, 28, 30), WHITE), (WHITE, (30, 28, 30))]
    else:
        return
    dr = ImageDraw.Draw(im)
    for j, (c, e) in enumerate(cols):
        pts = []
        for x in range(-60, int(W * k) + 60, 30):
            y = H * (0.35 + 0.3 * j) + 70 * math.sin(x / 210 + t * 2.4 + j * 2)
            pts.append((x, y))
        if len(pts) > 1:
            dr.line(pts, fill=e, width=76, joint="curve")
            dr.line(pts, fill=c, width=58, joint="curve")


# ---- 1フレーム -------------------------------------------------------------------
def render(fi):
    t = fi / FPS
    p = float(A["pulse"][min(fi, len(A["pulse"]) - 1)])
    cam = list(camera(t))
    if 4.1 <= t < 4.4:  # 受け取れ: 画面をゆらす
        s = 14 * (1 - (t - 4.1) / 0.3)
        cam[0] += s * math.sin(t * 90)
        cam[1] += s * math.cos(t * 77)
    cam = tuple(cam)
    im = view(A["bg"], cam, 0.5, PADW).convert("RGBA")
    im.alpha_composite(view(A["backdrop"], cam, 0.85))
    A["particles"].draw(im, t)
    ribbons_behind(im, t, cam)
    # カーテン (最初に開く)
    open_k = smooth((t - 0.1) / 1.1)
    P = PADW
    cur = Image.new("RGBA", (WW + 2 * P, WH + 2 * P), (0, 0, 0, 0))
    lc, rc = A["curtain"]
    shift = (1 - open_k) * 700
    cur.alpha_composite(lc, (int(P - lc.width + 580 + shift), P))
    cur.alpha_composite(rc, (int(P + WW - 580 - shift), P))
    for x in (int(P + 580 - 330 + shift), int(P + WW - 580 + 330 - shift)):
        D.paste_c(cur, A["tieback"], x, P + 900)
    cur.alpha_composite(A["valance"], (0, P))
    cur.alpha_composite(A["stage"], (0, P + WH - A["stage"].height))
    # 主役
    sx, sy, s = to_screen(SUBJ_C[0], SUBJ_C[1], cam)
    enter = spring(t - 0.35, 9, 5)
    jump = 0.0
    for t0, amp in ((4.1, 60), (25.2, 50), (28.7, 40)):
        if t0 <= t < t0 + 0.8:
            jump = max(jump, amp * math.sin((t - t0) / 0.8 * math.pi) * math.exp(-(t - t0) * 2))
    breathe = 1 + 0.012 * math.sin(t * 2.2)
    sc = s * enter * (1 + 0.025 * p)
    # うしろのハートバースト (人物の後ろ)
    for gi, (t0, seed) in enumerate(((4.1, 1), (12.05, 2), (25.2, 3), (28.7, 4))):
        heart_burst(im, t, t0, sx, sy - 100 * s, seed, spread=900 * s)
    subj = A["subject"]
    if sc > 0.02:
        img = subj.resize((max(1, int(subj.width * sc)), max(1, int(subj.height * sc * breathe))), Image.BILINEAR)
        img = img.rotate(1.2 * math.sin(t * 1.3), Image.BICUBIC, expand=True)
        D._clip(im, img, int(sx - img.width / 2), int(sy - img.height / 2 - jump * s + (1 - enter) * 80))
    # 前景 (カーテン・幕・舞台): 人物にはかからない位置
    im.alpha_composite(view(cur, cam, 1.0, PADW))
    draw_lyrics(im, t, p)
    im.alpha_composite(A["tag"], (40, H - A["tag"].height - 30))
    arr = np.asarray(im.convert("RGB")).astype(np.float32)
    end_t = A["nframes"] / FPS
    if t > end_t - 0.5:  # 最後は顔を中心にハートで閉じる
        fx, fy, _ = to_screen(FACE[0], FACE[1], cam)
        u = smooth((t - (end_t - 0.5)) / 0.45)
        m = Image.new("L", (W, H), 255)
        ImageDraw.Draw(m).polygon(D.heart_pts(fx, fy, max(1, 1600 * (1 - u))), fill=0)
        mm = np.asarray(m).astype(np.float32)[..., None] / 255
        arr = arr * (1 - mm) + np.array([247, 161, 196]) * mm
    return arr.clip(0, 255).astype(np.uint8).tobytes()


def make_tag():
    f = ImageFont.truetype(A["font_sub"], 26)
    text = "♡ めろチョコ 歌ってみた ♡"
    tw = int(f.getlength(text)) + 50
    lab = Image.new("RGBA", (tw, 54), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lab)
    dr.rounded_rectangle([0, 0, tw - 1, 53], radius=27, fill=(255, 255, 255, 235), outline=DPINK, width=4)
    dr.text((tw / 2, 28), text, font=f, anchor="mm", fill=DPINK)
    return lab


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--font", required=True)
    ap.add_argument("--font-sub", required=True)
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--out", default="stage_mv.mp4")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    A["font"], A["font_sub"] = args.font, args.font_sub
    lolita_styles()
    with Pool(args.jobs) as pool:
        A["3d"] = render3d.build_sprites(pool, args.cache, {"heart": (300, 32), "heart_white": (180, 24),
                                                            "bow_pink": (220, 24)})
    A["subject"] = load_subject(args.subject)
    A["bg"] = make_bg()
    A["backdrop"] = make_backdrop()
    A["curtain"] = (make_curtain(-1), make_curtain(1))
    A["tieback"] = A["3d"]["bow_pink"][0]
    A["valance"] = make_valance()
    A["stage"] = make_stage()
    A["particles"] = Particles()
    A["tag"] = make_tag()
    raw = subprocess.run([args.ffmpeg, "-v", "error", "-i", args.audio, "-vn", "-ac", "1", "-ar", "11025",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    au = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    spf = 11025 // FPS
    n = len(au) // spf
    rms = np.sqrt((au[: n * spf].reshape(n, spf) ** 2).mean(1))
    rms = rms / (np.percentile(rms, 95) + 1e-6)
    onset = np.maximum(0, np.diff(rms, prepend=rms[0]))
    onset = onset / (np.percentile(onset, 97) + 1e-6)
    pulse = np.zeros(n)
    for i in range(n):
        pulse[i] = max(min(onset[i], 1.2), pulse[i - 1] * 0.72 if i else 0)
    A["pulse"] = pulse
    A["nframes"] = n
    A["layout"] = [fit_group(g) for g in GROUPS]
    if args.preview:
        for s in args.preview:
            Image.frombytes("RGB", (W, H), render(int(round(s * FPS)))).save(f"stage_{s:05.2f}.png")
        return
    enc = subprocess.Popen([args.ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", args.audio,
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-b:v", "6000k",
                            "-maxrate", "8000k", "-bufsize", "12000k", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out], stdin=subprocess.PIPE)
    with Pool(args.jobs) as pool:
        for i, fr in enumerate(pool.imap(render, range(n), chunksize=2)):
            enc.stdin.write(fr)
            if i % 60 == 0:
                print(f"frame {i}/{n}", flush=True)
    enc.stdin.close()
    enc.wait()


if __name__ == "__main__":
    main()
