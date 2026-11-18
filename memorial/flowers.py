"""お花・花びら・光の粒をコードで描く部品（画像素材なし）。
桜・胡蝶蘭・紫陽花・バラ・かすみ草を、ごく淡いピンクと薄紫で描く。"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

SS = 4  # スーパーサンプリング倍率（なめらかな輪郭のため）

# (付け根の色, 先端の色)  どれも本当に淡く
PINK = [((248, 214, 228), (255, 244, 248)), ((246, 222, 234), (255, 250, 252))]
LAVENDER = [((226, 214, 242), (248, 244, 254)), ((232, 220, 244), (252, 248, 255))]
WHITE = [((240, 232, 244), (255, 255, 255))]
PETAL_COLORS = PINK + LAVENDER + WHITE
HYDRANGEA = [((214, 204, 238), (240, 234, 252)), ((222, 210, 240), (246, 240, 252)),
             ((236, 214, 236), (250, 238, 248)), ((210, 214, 240), (238, 240, 252))]


def _gradient(size, base, tip):
    """下（付け根）が base、上（先端）が tip の縦グラデ。"""
    w, h = size
    g = Image.new("RGB", (1, h))
    for y in range(h):
        k = y / max(h - 1, 1)
        g.putpixel((0, y), tuple(int(tip[i] * (1 - k) + base[i] * k) for i in range(3)))
    return g.resize((w, h))


def _rot(spr, ang):
    """乗算済みアルファで回転（透明部分の黒がフチににじまないように）。"""
    return spr.convert("RGBa").rotate(ang, resample=Image.BICUBIC, expand=True).convert("RGBA")


def petal_mask(length, width, notch=True, round_tip=False):
    """付け根が下、先端が上の花びら形のマスク（L）。SS倍で描いて縮小する。"""
    L, Wd = length * SS, width * SS
    w, h = int(Wd * 1.1) + 4, int(L) + 4
    m = Image.new("L", (w, h), 0)
    cx = w / 2
    pts_l, pts_r = [], []
    k1 = 0.84 if notch else 0.92  # 切れ込みありは先端に幅を残す
    for i in range(41):
        s = i / 40
        if round_tip:  # 胡蝶蘭の丸い花びら
            half = Wd / 2 * math.sin(math.pi * (0.06 + 0.94 * s ** 0.8)) ** 0.55 * (0.3 + 0.7 * s ** 0.4)
        else:
            half = Wd / 2 * (math.sin(math.pi * (s * k1 + 0.08)) ** 0.7) * (0.35 + 0.65 * s ** 0.5)
        y = h - 2 - s * L
        pts_l.append((cx - half, y))
        pts_r.append((cx + half, y))
    top = h - 2 - L
    tip = [(cx, top + L * 0.13)] if notch else [(cx, top)]
    ImageDraw.Draw(m).polygon(pts_l + tip + pts_r[::-1], fill=255)
    return m.resize((max(1, w // SS), max(1, h // SS)), Image.LANCZOS)


def petal_sprite(length, width, colors, notch=True, alpha=235, round_tip=False):
    m = petal_mask(length, width, notch, round_tip)
    base, tip = colors
    spr = _gradient(m.size, base, tip).convert("RGBA")
    spr.putalpha(m.point(lambda v: v * alpha // 255))
    return spr


def floret_sprite(size, colors, rng, alpha=245):
    """紫陽花の小花（4枚花びら）1つ。"""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = S / 2
    rot0 = rng.uniform(0, 90)
    for k in range(4):
        p = petal_sprite(S * 0.48, S * 0.42, colors, False, alpha)
        r = _rot(p, rot0 + k * 90)
        rad = math.radians(rot0 + k * 90)
        ox, oy = -math.sin(rad) * p.height / 2, -math.cos(rad) * p.height / 2
        img.alpha_composite(r, (int(c + ox - r.width / 2), int(c + oy - r.height / 2)))
    d = ImageDraw.Draw(img)
    r0 = S * 0.05
    d.ellipse([c - r0, c - r0, c + r0, c + r0], fill=(200, 184, 226, 255))
    return img.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def flower(size, kind, colors, rng):
    """size四方の花1輪（RGBA）。kind: sakura / orchid / hydrangea / rose / gyp"""
    if kind == "hydrangea":
        return hydrangea(size, rng)
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c = S / 2
    rot0 = rng.uniform(0, 360)

    def place(spr, ang, dist=0):
        r = _rot(spr, ang)
        # 付け根（下端中央）を花の中心に合わせる
        rad = math.radians(ang)
        ox = -math.sin(rad) * (spr.height / 2 + dist)
        oy = -math.cos(rad) * (spr.height / 2 + dist)
        img.alpha_composite(r, (int(c + ox - r.width / 2), int(c + oy - r.height / 2)))

    d = ImageDraw.Draw(img)
    if kind == "sakura":
        for k in range(5):
            place(petal_sprite(S * 0.46, S * 0.36, colors, True, 245), rot0 + k * 72, -S * 0.03)
        _stamens(img, c, S * 0.13, rng, (236, 200, 150), (226, 160, 182))
    elif kind == "orchid":  # 胡蝶蘭：上のがく＋左右に丸く大きな花びら＋下のがく2枚＋中心の唇弁
        tilt = rng.uniform(-12, 12)
        for a in (152, 208):  # 下のがく
            place(petal_sprite(S * 0.40, S * 0.22, colors, False, 250, round_tip=True), tilt + a, -S * 0.03)
        place(petal_sprite(S * 0.40, S * 0.24, colors, False, 250, round_tip=True), tilt, -S * 0.03)
        for a in (88, -88):  # 左右の大きな花びら
            place(petal_sprite(S * 0.43, S * 0.52, colors, False, 252, round_tip=True), tilt + a, -S * 0.05)
        # 唇弁：小さく、ほんのり濃いピンク
        rad = math.radians(tilt)
        lx, ly = c + math.sin(rad) * S * 0.07, c + math.cos(rad) * S * 0.07
        d.ellipse([lx - S * 0.06, ly - S * 0.035, lx + S * 0.06, ly + S * 0.085], fill=(238, 196, 220, 240))
        d.ellipse([lx - S * 0.03, ly - S * 0.01, lx + S * 0.03, ly + S * 0.05], fill=(226, 172, 204, 230))
        d.ellipse([c - S * 0.045, c - S * 0.06, c + S * 0.045, c + S * 0.02], fill=(255, 250, 252, 255))
        d.ellipse([c - S * 0.018, c - S * 0.035, c + S * 0.018, c - S * 0.003], fill=(244, 222, 160, 255))
    elif kind == "gyp":  # かすみ草：白い小さな粒
        for _ in range(rng.randint(7, 12)):
            x, y = c + rng.gauss(0, S * 0.15), c + rng.gauss(0, S * 0.15)
            r = S * rng.uniform(0.03, 0.05)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 240),
                      outline=(236, 228, 242, 255), width=SS // 2)
    else:  # rose：重なった丸い花びら
        base, tip = colors
        for layer in range(6):
            rr = S * 0.46 * (1 - layer * 0.14)
            n = 7 - layer // 2
            for k in range(n):
                a = math.radians(rot0 + k * 360 / n + layer * 23)
                x, y = c + math.cos(a) * rr * 0.35, c + math.sin(a) * rr * 0.35
                pr = rr * 0.62
                kk = layer / 6
                col = tuple(int(tip[i] * (1 - kk) + base[i] * kk) for i in range(3))
                d.ellipse([x - pr, y - pr, x + pr, y + pr], fill=col + (255,),
                          outline=tuple(max(0, v - 14) for v in base) + (80,), width=SS)
    return img.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def hydrangea(size, rng):
    """紫陽花：小花をこんもり丸く集める。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size / 2
    fs = max(10, int(size * 0.24))
    pts = []
    for _ in range(int(48 * (size / 160) ** 0.5) + 18):
        a = rng.uniform(0, math.tau)
        r = (size * 0.40 - fs * 0.35) * math.sqrt(rng.random())
        pts.append((c + math.cos(a) * r, c + math.sin(a) * r * 0.92))
    base_col = rng.randrange(len(HYDRANGEA))
    for x, y in sorted(pts, key=lambda p: (p[0] - c) ** 2 + (p[1] - c) ** 2, reverse=True):
        col = HYDRANGEA[base_col if rng.random() < 0.6 else rng.randrange(len(HYDRANGEA))]
        f = floret_sprite(int(fs * rng.uniform(0.8, 1.1)), col, rng)
        _paste_clip(img, f, x - f.width / 2, y - f.height / 2)
    return img


def _stamens(img, c, r, rng, tip_col, line_col):
    d = ImageDraw.Draw(img)
    for _ in range(14):
        a = rng.uniform(0, math.tau)
        rr = r * rng.uniform(0.6, 1.0)
        x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
        d.line([(c, c), (x, y)], fill=line_col + (200,), width=max(1, SS // 2))
        s = SS * 1.6
        d.ellipse([x - s, y - s, x + s, y + s], fill=tip_col + (255,))


def leaf(length, rng):
    col = rng.choice([(196, 210, 192), (186, 204, 188), (204, 214, 196)])
    m = petal_mask(length, length * 0.38, notch=False)
    spr = _gradient(m.size, tuple(v - 22 for v in col), col).convert("RGBA")
    spr.putalpha(m.point(lambda v: v * 200 // 255))
    d = ImageDraw.Draw(spr)
    d.line([(spr.width / 2, spr.height), (spr.width / 2, spr.height * 0.1)], fill=(255, 255, 255, 70), width=1)
    return spr


DEFAULT_KINDS = {"sakura": 4, "orchid": 3, "hydrangea": 2, "rose": 1, "gyp": 2}


def bouquet(R, angle, seed, density=1.0, scale=1.0, kinds=None):
    """中心から angle(度, 0=右, 90=下) の方向へ広がる花の房。
    返り値: (RGBA画像, 中心のx, 中心のy)。房が切れないよう余白付きのキャンバスに描く。"""
    rng = random.Random(seed)
    kinds = kinds or DEFAULT_KINDS
    maxf = int(260 * scale) + 20
    size = int(2 * (R + maxf))
    c = size / 2
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    base = math.radians(angle)

    def pos(spread, rmax):
        a = base + rng.gauss(0, spread)
        d = min(rmax, abs(rng.gauss(0, 0.5)) * rmax)
        return a, d, c + math.cos(a) * d, c + math.sin(a) * d

    # 葉っぱ（奥）：外へ向かって伸びる
    for _ in range(int(14 * density)):
        a, d, x, y = pos(0.75, R * 0.85)
        lf = leaf(int(rng.uniform(80, 150) * scale), rng)
        r = _rot(lf, -math.degrees(a) - 90 + rng.uniform(-30, 30))
        x += math.cos(a) * lf.height * 0.4
        y += math.sin(a) * lf.height * 0.4
        _paste_clip(layer, r, x - r.width / 2, y - r.height / 2)
    items = []
    names, weights = zip(*kinds.items())
    for _ in range(int(24 * density)):
        a, d, x, y = pos(0.7, R)
        kind = rng.choices(names, weights)[0]
        s = (190 - d / R * 120) * scale * rng.uniform(0.65, 1.15)
        s *= {"hydrangea": 1.35, "orchid": 1.1, "gyp": 0.7}.get(kind, 1.0)
        # 紫陽花は奥に（先に描く）
        items.append((0 if kind == "hydrangea" else 1, d, x, y, int(max(28, s)), kind))
    for _, d, x, y, s, kind in sorted(items, key=lambda t: (t[0], -t[1])):
        cols = rng.choice(WHITE + PINK if kind == "orchid" else PETAL_COLORS)
        _paste_clip(layer, flower(s, kind, cols, rng), x - s / 2, y - s / 2)
    sh = layer.getchannel("A").filter(ImageFilter.GaussianBlur(8 * scale))
    out = Image.new("RGBA", (size, size), (130, 110, 140, 0))
    out.putalpha(sh.point(lambda v: v * 36 // 255))
    out.alpha_composite(layer)
    return out, c, c


def blur_alpha(spr, r):
    """色はそのまま、アルファだけぼかす（黒いフチが出ないように）。"""
    out = spr.copy()
    out.putalpha(spr.getchannel("A").filter(ImageFilter.GaussianBlur(r)))
    return out


def _paste_clip(dst, src, x, y):
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1, sy1 = min(src.width, dst.width - x), min(src.height, dst.height - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    dst.alpha_composite(src, (x + sx0, y + sy0), (sx0, sy0, sx1, sy1))


paste_clip = _paste_clip


class PetalField:
    """画面全体に舞い散る花びらと光の粒。時刻 t から位置を計算するので、どのフレームからでも描ける。
    kind="petal" は桜などの花びら、kind="floret" は紫陽花の小花や小さな桜の花が舞う。"""

    def __init__(self, W, H, n_petals=34, n_bokeh=26, seed=7, kind="petal"):
        self.W, self.H = W, H
        rng = random.Random(seed)
        self.petals = []
        for i in range(n_petals):
            depth = rng.random()  # 0=奥 1=手前
            if kind == "floret":
                sz = int(26 + depth * 40)
                if rng.random() < 0.6:
                    spr = floret_sprite(sz, rng.choice(HYDRANGEA), rng, int(190 + 50 * depth))
                else:
                    spr = flower(sz, "sakura", rng.choice(PINK + WHITE), rng)
                    spr.putalpha(spr.getchannel("A").point(lambda v: v * 225 // 255))
            else:
                L = 22 + depth * 46
                spr = petal_sprite(L, L * 0.78, rng.choice(PETAL_COLORS), True, int(170 + 70 * depth))
            if depth > 0.82:  # 手前はぼかして被写界深度っぽく
                spr = blur_alpha(spr, 2.2)
            elif depth < 0.25:
                spr = blur_alpha(spr, 0.8)
            self.petals.append(dict(
                spr=spr, depth=depth,
                x0=rng.uniform(-0.1, 1.1) * W, y0=rng.uniform(0, 1),
                vy=(38 + depth * 70) * rng.uniform(0.8, 1.2), vx=rng.uniform(-30, 8),
                amp=rng.uniform(30, 90), fq=rng.uniform(0.15, 0.35), ph=rng.uniform(0, math.tau),
                rot0=rng.uniform(0, 360), rotv=rng.uniform(-45, 45),
                flipf=rng.uniform(0.2, 0.6) if kind == "petal" else rng.uniform(0.08, 0.2),
                flipph=rng.uniform(0, math.tau)))
        self.petals.sort(key=lambda p: p["depth"])
        self.bokeh = []
        for i in range(n_bokeh):
            r = rng.uniform(6, 34)
            col = rng.choice([(255, 255, 255), (250, 236, 246), (240, 232, 252)])
            m = Image.new("L", (int(r * 4), int(r * 4)), 0)
            ImageDraw.Draw(m).ellipse([r, r, r * 3, r * 3], fill=255)
            spr = Image.new("RGBA", m.size, col + (0,))
            spr.putalpha(m.filter(ImageFilter.GaussianBlur(r * (0.35 if r > 18 else 0.6))))
            self.bokeh.append(dict(spr=spr, x0=rng.uniform(0, W), y0=rng.uniform(0, H),
                                   vy=rng.uniform(-14, -4), vx=rng.uniform(-6, 6),
                                   a=rng.uniform(0.25, 0.6), tw=rng.uniform(0.3, 0.9), ph=rng.uniform(0, math.tau)))

    def draw(self, img, t, strength=1.0, petals=True):
        """img: RGBA。strength で全体の濃さを調整（0〜1）。"""
        if strength <= 0.01:
            return
        W, H = self.W, self.H
        for b in self.bokeh:
            a = b["a"] * (0.55 + 0.45 * math.sin(t * b["tw"] + b["ph"])) * strength
            if a <= 0.02:
                continue
            x = (b["x0"] + b["vx"] * t) % (W + 200) - 100
            y = (b["y0"] + b["vy"] * t) % (H + 200) - 100
            s = b["spr"].copy()
            s.putalpha(s.getchannel("A").point(lambda v, a=a: int(v * a)))
            _paste_clip(img, s, x - s.width / 2, y - s.height / 2)
        if not petals:
            return
        span = H + 240
        for p in self.petals:
            y = (p["y0"] * span + p["vy"] * t) % span - 120
            x = p["x0"] + p["vx"] * t + p["amp"] * math.sin(p["fq"] * math.tau * t + p["ph"])
            x = (x + 200) % (W + 400) - 200
            flip = abs(math.cos(p["flipf"] * math.tau * t + p["flipph"]))  # ひらひら裏返る
            spr = p["spr"]
            sw = max(2, int(spr.width * (0.25 + 0.75 * flip)))
            s = spr.convert("RGBa").resize((sw, spr.height), Image.BILINEAR)
            s = s.rotate(p["rot0"] + p["rotv"] * t, resample=Image.BICUBIC, expand=True).convert("RGBA")
            if strength < 1:
                s.putalpha(s.getchannel("A").point(lambda v: int(v * strength)))
            _paste_clip(img, s, x - s.width / 2, y - s.height / 2)
