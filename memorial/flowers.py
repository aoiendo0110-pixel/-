"""お花・花びら・光の粒をコードで描く部品（画像素材なし）。"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

SS = 4  # スーパーサンプリング倍率（なめらかな輪郭のため）

PETAL_COLORS = [
    ((255, 196, 212), (255, 238, 243)),  # 桜ピンク
    ((250, 214, 226), (255, 248, 250)),  # 淡いピンク
    ((236, 236, 244), (255, 255, 255)),  # 白
    ((224, 206, 238), (248, 242, 252)),  # 藤色
    ((255, 214, 200), (255, 244, 238)),  # ピーチ
]


def _gradient(size, base, tip):
    """下（付け根）が base、上（先端）が tip の縦グラデ。"""
    w, h = size
    g = Image.new("RGB", (1, h))
    for y in range(h):
        k = y / max(h - 1, 1)
        g.putpixel((0, y), tuple(int(tip[i] * (1 - k) + base[i] * k) for i in range(3)))
    return g.resize((w, h))


def petal_mask(length, width, notch=True):
    """付け根が下、先端が上の花びら形のマスク（L）。SS倍で描いて縮小する。"""
    L, Wd = length * SS, width * SS
    w, h = int(Wd * 1.1) + 4, int(L) + 4
    m = Image.new("L", (w, h), 0)
    cx = w / 2
    pts_l, pts_r = [], []
    k1 = 0.84 if notch else 0.92  # 切れ込みありは先端に幅を残す
    for i in range(41):
        s = i / 40
        half = Wd / 2 * (math.sin(math.pi * (s * k1 + 0.08)) ** 0.7) * (0.35 + 0.65 * s ** 0.5)
        y = h - 2 - s * L
        pts_l.append((cx - half, y))
        pts_r.append((cx + half, y))
    top = h - 2 - L
    if notch:
        tip = [(cx, top + L * 0.13)]  # 桜の花びらの切れ込み
    else:
        tip = [(cx, top)]
    ImageDraw.Draw(m).polygon(pts_l + tip + pts_r[::-1], fill=255)
    return m.resize((max(1, w // SS), max(1, h // SS)), Image.LANCZOS)


def _rot(spr, ang):
    """乗算済みアルファで回転（透明部分の黒がフチににじまないように）。"""
    return spr.convert("RGBa").rotate(ang, resample=Image.BICUBIC, expand=True).convert("RGBA")


def petal_sprite(length, width, colors, notch=True, alpha=235):
    m = petal_mask(length, width, notch)
    base, tip = colors
    spr = _gradient(m.size, base, tip).convert("RGBA")
    spr.putalpha(m.point(lambda v: v * alpha // 255))
    return spr


def flower(size, kind, colors, rng):
    """size四方の花1輪（RGBA）。kind: sakura / daisy / rose"""
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

    if kind == "sakura":
        for k in range(5):
            place(petal_sprite(S * 0.46, S * 0.36, colors, True, 245), rot0 + k * 72, -S * 0.03)
        _stamens(img, c, S * 0.13, rng, (240, 190, 110), (220, 120, 140))
    elif kind == "daisy":  # 白い小菊風
        n = rng.randint(16, 20)
        for k in range(n):
            place(petal_sprite(S * 0.44, S * 0.11, colors, False, 240), rot0 + k * 360 / n + rng.uniform(-4, 4))
        for k in range(n):
            place(petal_sprite(S * 0.32, S * 0.09, colors, False, 250), rot0 + (k + 0.5) * 360 / n)
        d = ImageDraw.Draw(img)
        r = S * 0.11
        d.ellipse([c - r, c - r, c + r, c + r], fill=(246, 214, 120, 255))
        d.ellipse([c - r * 0.6, c - r * 0.6, c + r * 0.6, c + r * 0.6], fill=(232, 186, 90, 255))
    else:  # rose / ラナンキュラス風：重なった丸い花びら
        base, tip = colors
        d = ImageDraw.Draw(img)
        for layer in range(6):
            rr = S * 0.46 * (1 - layer * 0.14)
            n = 7 - layer // 2
            for k in range(n):
                a = math.radians(rot0 + k * 360 / n + layer * 23)
                off = rr * 0.35
                x, y = c + math.cos(a) * off, c + math.sin(a) * off
                pr = rr * 0.62
                kk = layer / 6
                col = tuple(int(tip[i] * (1 - kk) + base[i] * kk) for i in range(3))
                d.ellipse([x - pr, y - pr, x + pr, y + pr], fill=col + (255,),
                          outline=tuple(max(0, v - 18) for v in base) + (90,), width=SS)
    img = img.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")
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
    col = rng.choice([(168, 190, 160), (150, 176, 150), (186, 200, 170)])
    m = petal_mask(length, length * 0.38, notch=False)
    spr = _gradient(m.size, tuple(v - 25 for v in col), col).convert("RGBA")
    spr.putalpha(m.point(lambda v: v * 215 // 255))
    d = ImageDraw.Draw(spr)
    d.line([(spr.width / 2, spr.height), (spr.width / 2, spr.height * 0.1)], fill=(255, 255, 255, 60), width=1)
    return spr


def bouquet(R, angle, seed, density=1.0, scale=1.0):
    """中心から angle(度, 0=右, 90=下) の方向へ広がる花の房。
    返り値: (RGBA画像, 中心のx, 中心のy)。房が切れないよう余白付きのキャンバスに描く。"""
    rng = random.Random(seed)
    maxf = int(200 * scale) + 20
    size = int(2 * (R + maxf))
    c = size / 2
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    base = math.radians(angle)

    def pos(spread, rmax):
        a = base + rng.gauss(0, spread)
        d = min(rmax, abs(rng.gauss(0, 0.5)) * rmax)
        return a, d, c + math.cos(a) * d, c + math.sin(a) * d

    # 葉っぱ（奥）：外へ向かって伸びる
    for _ in range(int(16 * density)):
        a, d, x, y = pos(0.75, R * 0.85)
        lf = leaf(int(rng.uniform(80, 150) * scale), rng)
        ang = -math.degrees(a) - 90 + rng.uniform(-30, 30)
        r = _rot(lf, ang)
        # 葉の付け根を (x,y) 付近に
        x += math.cos(a) * lf.height * 0.4
        y += math.sin(a) * lf.height * 0.4
        _paste_clip(layer, r, x - r.width / 2, y - r.height / 2)
    items = []
    for _ in range(int(24 * density)):
        a, d, x, y = pos(0.7, R)
        size_f = int(max(28, (190 - d / R * 120) * scale * rng.uniform(0.65, 1.15)))
        items.append((d, x, y, size_f))
    for d, x, y, s in sorted(items, key=lambda t: -t[0]):  # 外側（小さい花）から描く
        kind = rng.choices(["sakura", "daisy", "rose"], [4, 3, 3])[0]
        cols = ((236, 236, 240), (255, 255, 255)) if kind == "daisy" else rng.choice(PETAL_COLORS)
        _paste_clip(layer, flower(s, kind, cols, rng), x - s / 2, y - s / 2)
    sh = layer.getchannel("A").filter(ImageFilter.GaussianBlur(8 * scale))
    out = Image.new("RGBA", (size, size), (120, 90, 100, 0))
    out.putalpha(sh.point(lambda v: v * 45 // 255))
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
    """画面全体に舞い散る花びらと光の粒。時刻 t から位置を計算するので、どのフレームからでも描ける。"""

    def __init__(self, W, H, n_petals=34, n_bokeh=26, seed=7):
        self.W, self.H = W, H
        rng = random.Random(seed)
        self.petals = []
        for i in range(n_petals):
            depth = rng.random()  # 0=奥 1=手前
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
                flipf=rng.uniform(0.2, 0.6), flipph=rng.uniform(0, math.tau)))
        self.petals.sort(key=lambda p: p["depth"])
        self.bokeh = []
        for i in range(n_bokeh):
            r = rng.uniform(6, 34)
            col = rng.choice([(255, 255, 255), (255, 236, 220), (255, 228, 236)])
            m = Image.new("L", (int(r * 4), int(r * 4)), 0)
            ImageDraw.Draw(m).ellipse([r, r, r * 3, r * 3], fill=255)
            spr = Image.new("RGBA", m.size, col + (0,))
            spr.putalpha(m.filter(ImageFilter.GaussianBlur(r * (0.35 if r > 18 else 0.6))))
            self.bokeh.append(dict(spr=spr, x0=rng.uniform(0, W), y0=rng.uniform(0, H),
                                   vy=rng.uniform(-14, -4), vx=rng.uniform(-6, 6),
                                   a=rng.uniform(0.25, 0.6), tw=rng.uniform(0.3, 0.9), ph=rng.uniform(0, math.tau)))

    def draw(self, img, t, strength=1.0, petals=True):
        """img: RGBA。strength で全体の濃さを調整（0〜1）。"""
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
