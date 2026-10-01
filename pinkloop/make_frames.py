"""動画にのせて使える、ピンク×ロリータ×フリル×リボンの透過フレーム素材 (ループ) を作る。

    pip install numpy pillow imageio-ffmpeg
    python3 make_frames.py --out out_frames            # 2種類とも 1920x1080
    python3 make_frames.py --out out_frames --vertical # 縦型 1080x1920
    python3 make_frames.py --only curtain --preview 2.5

出力 (種類ごと):
  *_alpha.mov   ProRes 4444 透過 (Premiere / Final Cut / DaVinci 向け)
  *_alpha.webm  VP9 透過 (CapCut・ブラウザなど)
  *_green.mp4   グリーンバック (クロマキーで抜く用)
  *.png         1コマ目の透過PNG
最初と最後のコマがつながるので、何回並べてもループする。
"""
import argparse
import math
import os
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 2  # 2倍で描いて縮小 (なめらかなフチにする)
TAU = math.tau

PINK = (255, 156, 196, 255)
PINK_L = (255, 199, 221, 255)
PINK_P = (255, 228, 239, 255)
HOT = (240, 96, 154, 255)
DEEP = (214, 70, 128, 255)
WHITE = (255, 255, 255, 255)
CREAM = (255, 248, 251, 255)
LACE_HOLE = (255, 214, 230, 255)
PEARL = (255, 250, 252, 255)


# ---------- 形のパーツ ----------
def heart_poly(cx, cy, r, ang=0.0, n=48):
    pts = []
    ca, sa = math.cos(ang), math.sin(ang)
    for i in range(n):
        t = TAU * i / n
        x = 16 * math.sin(t) ** 3 / 17 * r
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 17 * r
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


def star_poly(cx, cy, r, inner=0.28):
    pts = []
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def rot(pts, cx, cy, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def bow(d, cx, cy, s, ang=0.0, sway=0.0, body=PINK, dark=DEEP, light=PINK_L, outline=None):
    """リボン結び。s は片側の輪の幅くらい。sway で垂れの揺れ。"""
    ow = max(2, int(s * 0.06))
    outline = outline or dark

    def lobe(sign):
        pts = []
        for i in range(40):
            t = TAU * i / 40
            x = -0.55 * s + 0.55 * s * math.cos(t)
            y = -0.06 * s + 0.4 * s * math.sin(t)
            # 根元をしぼる
            dd = -x
            if dd < 0.32 * s:
                y *= 0.3 + 0.7 * max(dd, 0) / (0.32 * s)
            x2, y2 = x * math.cos(-0.2) - y * math.sin(-0.2), x * math.sin(-0.2) + y * math.cos(-0.2)
            pts.append((x2 * sign, y2))
        return pts

    def tail(sign):
        sw = sway * sign
        return [(0.16 * s * sign, 0.0), (0.72 * s * sign + sw, 1.0 * s),
                (0.56 * s * sign + sw, 0.95 * s), (0.4 * s * sign + sw, 1.2 * s), (-0.1 * s * sign, 0.18 * s)]

    for sign in (-1, 1):
        d.polygon(rot(tail(sign), cx, cy, ang), fill=body, outline=outline, width=ow)
        # 垂れの折り目
        t = tail(sign)
        d.line(rot([(0.0, 0.1 * s), ((t[1][0] + t[3][0]) / 2, (t[1][1] + t[3][1]) / 2)], cx, cy, ang),
               fill=light, width=max(2, int(s * 0.07)))
    for sign in (-1, 1):
        lb = lobe(sign)
        d.polygon(rot(lb, cx, cy, ang), fill=body, outline=outline, width=ow)
        inner = [(x * 0.62 + 0.08 * s * sign, y * 0.55 + 0.02 * s) for x, y in lb]
        d.line(rot(inner[5:30], cx, cy, ang), fill=dark, width=max(2, int(s * 0.05)), joint="curve")
        hl = [(x * 0.75, y * 0.6 - 0.12 * s) for x, y in lb[14:24]]
        d.line(rot(hl, cx, cy, ang), fill=light, width=max(2, int(s * 0.08)), joint="curve")
    k = 0.2 * s
    d.ellipse([cx - k, cy - k * 1.05, cx + k, cy + k * 1.05], fill=body, outline=outline, width=ow)
    d.arc([cx - k * 0.6, cy - k * 0.7, cx + k * 0.4, cy + k * 0.2], 200, 300, fill=light, width=max(2, int(s * 0.05)))


def pearl(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PEARL, outline=(236, 196, 214, 255), width=max(1, int(r * 0.18)))
    h = r * 0.35
    d.ellipse([cx - r * 0.45 - h / 2, cy - r * 0.45 - h / 2, cx - r * 0.45 + h / 2, cy - r * 0.45 + h / 2], fill=WHITE)


def resample(pts, step):
    """折れ線を等間隔の点 (位置・内向き法線) に並べ直す。"""
    out = []
    acc = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        if seg == 0:
            continue
        tx, ty = (x1 - x0) / seg, (y1 - y0) / seg
        while acc <= seg:
            out.append((x0 + tx * acc, y0 + ty * acc, -ty, tx))
            acc += step
        acc -= seg
    return out


def frill_along(d, path, r, th, lace=True, col=PINK, pleat=DEEP, seed=0, wave=0.1):
    """path (時計回りの点列) の内側に向けて、レース+フリルを並べる。"""
    pts = resample(path, r * 1.15)
    if lace:
        for i, (x, y, nx, ny) in enumerate(pts):
            rr = r * 0.62 * (1 + wave * math.sin(2 * th + i * 0.55 + seed))
            cx, cy = x + nx * r * 1.25, y + ny * r * 1.25
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=WHITE, outline=(244, 200, 220, 255), width=max(1, int(r * 0.06)))
            h = rr * 0.22
            d.ellipse([cx - h, cy - h + rr * 0.25, cx + h, cy + h + rr * 0.25], fill=LACE_HOLE)
    for i, (x, y, nx, ny) in enumerate(pts):
        rr = r * (1 + wave * math.sin(2 * th + i * 0.55 + seed))
        cx, cy = x + nx * r * 0.45, y + ny * r * 0.45
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col, outline=pleat, width=max(2, int(r * 0.08)))
    for i, (x, y, nx, ny) in enumerate(pts):
        rr = r * (1 + wave * math.sin(2 * th + i * 0.55 + seed))
        # ひだの線
        for off in (-0.35, 0.35):
            tx, ty = ny, -nx
            sx, sy = x + tx * off * rr, y + ty * off * rr
            d.line([(sx, sy), (sx + nx * rr * 1.2, sy + ny * rr * 1.2)], fill=PINK_L, width=max(2, int(r * 0.09)))


def round_rect_path(x0, y0, x1, y1, rad, n=12):
    """時計回り。内向き法線が中心を向くよう、resample では (-ty, tx) を使う。"""
    pts = []
    corners = [(x1 - rad, y0 + rad, -90), (x1 - rad, y1 - rad, 0), (x0 + rad, y1 - rad, 90), (x0 + rad, y0 + rad, 180)]
    for cx, cy, a0 in corners:
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    pts.append(pts[0])
    return pts


def glow_layer(size, items):
    """キラキラの光 (ぼかした白)。items: [(kind, x, y, r, a)]"""
    W, H = size
    m = Image.new("L", (W // 2, H // 2), 0)
    dm = ImageDraw.Draw(m)
    for kind, x, y, r, a in items:
        v = int(255 * a)
        if kind == "star":
            dm.polygon(star_poly(x / 2, y / 2, r / 2, 0.3), fill=v)
        else:
            dm.ellipse([x / 2 - r / 2, y / 2 - r / 2, x / 2 + r / 2, y / 2 + r / 2], fill=v)
    m = m.filter(ImageFilter.GaussianBlur(max(2, W // 400))).resize((W, H), Image.BILINEAR)
    return m


# ---------- フレーム1: フリル額縁 ----------
def frame_frill(W, H, th, rng_state):
    S = SS
    w, h = W * S, H * S
    u = min(W, H) / 1080 * S  # 基準単位
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    band = int(64 * u)
    mx0 = band + int(10 * u)
    path = round_rect_path(mx0, mx0, w - mx0, h - mx0, int(38 * u))
    r = 20 * u
    frill_along(d, path, r, th)
    # 外側の帯 (ピンク×白ドット)
    ring = Image.new("L", (w, h), 255)
    ImageDraw.Draw(ring).rounded_rectangle([band, band, w - band, h - band], radius=int(46 * u), fill=0)
    bandlayer = Image.new("RGBA", (w, h), PINK)
    bd = ImageDraw.Draw(bandlayer)
    step = int(34 * u)
    for yy in range(0, h + step, step):
        for xx in range(0, w + step, step):
            ox = step // 2 if (yy // step) % 2 else 0
            rr = 4.5 * u
            bd.ellipse([xx + ox - rr, yy - rr, xx + ox + rr, yy + rr], fill=PINK_P)
    im.paste(bandlayer, (0, 0), ring)
    d = ImageDraw.Draw(im)
    # 帯のふち (白いステッチ)
    d.rounded_rectangle([band - 4 * u, band - 4 * u, w - band + 4 * u, h - band + 4 * u], radius=int(50 * u),
                        outline=WHITE, width=int(5 * u))
    d.rounded_rectangle([band * 0.35, band * 0.35, w - band * 0.35, h - band * 0.35], radius=int(30 * u),
                        outline=CREAM, width=int(3 * u))
    # パールのたるみ (上下)
    for edge in (0, 1):
        n_sw = max(3, int(W / H * 4))
        for k in range(n_sw):
            x0 = band + (w - 2 * band) * k / n_sw
            x1 = band + (w - 2 * band) * (k + 1) / n_sw
            sag = (34 + 6 * math.sin(th + k)) * u
            for j in range(1, 14):
                t = j / 14
                x = x0 + (x1 - x0) * t
                y = mx0 + r * 2.4 + sag * math.sin(math.pi * t)
                if edge:
                    y = h - y
                pearl(d, x, y, 5.5 * u)
    # 四隅のハート
    for cx, cy in ((band * 0.9, band * 0.9), (w - band * 0.9, band * 0.9), (band * 0.9, h - band * 0.9), (w - band * 0.9, h - band * 0.9)):
        d.polygon(heart_poly(cx, cy + 3 * u, 30 * u), fill=HOT, outline=WHITE, width=int(4 * u))
        d.ellipse([cx - 12 * u, cy - 10 * u, cx - 4 * u, cy - 2 * u], fill=(255, 200, 225, 255))
    # 上のおおきいリボン (ゆらゆら)
    bow(d, w / 2, band * 0.75, 150 * u, ang=0.05 * math.sin(th), sway=18 * u * math.sin(th + 0.8))
    # 左右の小さいリボン
    for sx in (0.5, 1.5):
        cy = h * 0.5
        cx = band * 0.55 if sx < 1 else w - band * 0.55
        bow(d, cx, cy - 30 * u, 52 * u, ang=(math.pi / 2 if sx < 1 else -math.pi / 2) * 0 + 0.08 * math.sin(th * 2 + sx),
            sway=6 * u * math.sin(th * 2 + sx), body=HOT, light=PINK, dark=DEEP)

    # キラキラ & 浮かぶハート (枠の上)
    items = []
    rng = np.random.default_rng(rng_state)
    for i in range(46):
        edge = rng.integers(0, 4)
        tpos = rng.uniform(0, 1)
        off = rng.uniform(0.2, 1.5) * band
        if edge == 0:
            x, y = tpos * w, off
        elif edge == 1:
            x, y = tpos * w, h - off
        elif edge == 2:
            x, y = off, tpos * h
        else:
            x, y = w - off, tpos * h
        ph = rng.uniform(0, TAU)
        a = max(0.0, math.sin(int(rng.integers(2, 5)) * th + ph)) ** 2
        rr = rng.uniform(7, 16) * u
        if a > 0.02:
            d.polygon(star_poly(x, y, rr * (0.6 + 0.4 * a)), fill=(255, 255, 255, int(255 * a)))
            items.append(("star", x, y, rr * 2.2, a * 0.8))
    for i in range(14):
        side = i % 2
        span = h + 120 * u
        y = (rng.uniform(0, span) - (th / TAU) * span * int(rng.integers(1, 3))) % span - 60 * u
        x = (rng.uniform(0.15, 1.2) * band) if side == 0 else w - rng.uniform(0.15, 1.2) * band
        x += 10 * u * math.sin(th * 2 + i)
        hr = rng.uniform(11, 20) * u
        d.polygon(heart_poly(x, y, hr, 0.25 * math.sin(th + i)), fill=(255, 255, 255, 235), outline=HOT, width=int(3 * u))
    return finish(im, W, H, items)


# ---------- フレーム2: カーテン & スワッグ ----------
def frame_curtain(W, H, th, rng_state):
    S = SS
    w, h = W * S, H * S
    u = min(W, H) / 1080 * S
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    vertical = H > W

    # 左右のカーテン
    tie_y = h * 0.6
    for side in (0, 1):
        def edge_x(y):
            top = w * (0.2 if not vertical else 0.3)
            tie = w * (0.085 if not vertical else 0.13)
            bot = w * (0.15 if not vertical else 0.22)
            if y < tie_y:
                t = y / tie_y
                x = top + (tie - top) * (1 - (1 - t) ** 2)
            else:
                t = (y - tie_y) / (h - tie_y)
                x = tie + (bot - tie) * t ** 0.7
            return x + 7 * u * math.sin(th + y / (90 * u)) * (1 - abs(y - tie_y) / h)

        ys = np.linspace(0, h, 80)
        inner = [(edge_x(y), y) for y in ys]
        if side:
            inner = [(w - x, y) for x, y in inner]
        poly = ([(0, 0)] if not side else [(w, 0)]) + inner + ([(0, h)] if not side else [(w, h)])
        d.polygon(poly, fill=PINK)
        # ひだ
        for j in range(1, 7):
            f = j / 7
            line = []
            for y in ys:
                x = edge_x(y) * f
                line.append((w - x if side else x, y))
            d.line(line, fill=PINK_L if j % 2 else HOT, width=int((6 if j % 2 else 3) * u), joint="curve")
        # 内側のフリル (上から下へ時計回り/反時計回りで法線を内側へ)
        path = inner if side == 0 else inner
        if side == 0:
            frill_path = [(x, y) for x, y in inner]
        else:
            frill_path = [(x, y) for x, y in inner][::-1]
        frill_along(d, frill_path, 15 * u, th, seed=side * 2)
        # 留めリボン
        tx = edge_x(tie_y)
        tx = w - tx * 0.6 if side else tx * 0.6
        d.rounded_rectangle([tx - 70 * u if not side else tx - 70 * u, tie_y - 14 * u, tx + 70 * u, tie_y + 14 * u],
                            radius=int(12 * u), fill=HOT)
        bow(d, tx, tie_y, 70 * u, ang=0.06 * math.sin(th * 2 + side), sway=10 * u * math.sin(th * 2 + side),
            body=HOT, light=PINK, dark=DEEP)

    # 上のスワッグ (たるんだ布)
    n_sw = 4 if not vertical else 3
    top_h = 70 * u
    for k in range(n_sw):
        x0 = w * k / n_sw
        x1 = w * (k + 1) / n_sw
        depth = (h * (0.09 if not vertical else 0.05)) * (1 + 0.05 * math.sin(th + k * 1.3))
        arc = [(x0 + (x1 - x0) * t, top_h + depth * math.sin(math.pi * t)) for t in np.linspace(0, 1, 40)]
        d.polygon([(x0, 0)] + arc + [(x1, 0)], fill=PINK)
        for j, f in enumerate((0.35, 0.6, 0.82)):
            fold = [(x0 + (x1 - x0) * t, top_h * f + depth * f * math.sin(math.pi * t)) for t in np.linspace(0, 1, 40)]
            d.line(fold, fill=PINK_L if j != 1 else HOT, width=int((6 if j != 1 else 3) * u), joint="curve")
        frill_along(d, arc[::-1] if False else arc, 13 * u, th, seed=k)
        # パールの紐
        for j in range(1, 18):
            t = j / 18
            pearl(d, x0 + (x1 - x0) * t, top_h + depth * 1.35 * math.sin(math.pi * t) + 30 * u, 5 * u)
    for k in range(n_sw + 1):
        bx = w * k / n_sw
        bow(d, bx, top_h * 0.9, 62 * u, ang=0.07 * math.sin(th * 2 + k), sway=8 * u * math.sin(th * 2 + k + 1),
            body=HOT, light=PINK, dark=DEEP)
    # 一番上のバンド
    d.rectangle([0, 0, w, top_h * 0.45], fill=HOT)
    for xx in np.arange(0, w, 26 * u):
        pearl(d, xx, top_h * 0.45, 7 * u)

    # 下のレース
    lace_y = h - 34 * u
    d.rectangle([0, lace_y, w, h], fill=WHITE)
    for i, xx in enumerate(np.arange(0, w + 30 * u, 30 * u)):
        rr = 17 * u
        d.ellipse([xx - rr, lace_y - rr * 0.8, xx + rr, lace_y + rr * 1.2], fill=WHITE)
        d.ellipse([xx - 4 * u, lace_y - 2 * u, xx + 4 * u, lace_y + 6 * u], fill=LACE_HOLE)
    d.line([(0, h - 14 * u), (w, h - 14 * u)], fill=PINK, width=int(8 * u))

    # キラキラとハート (カーテンまわり)
    items = []
    rng = np.random.default_rng(rng_state)
    for i in range(40):
        side = i % 2
        x = rng.uniform(0.01, 0.16 if not vertical else 0.25) * w
        x = w - x if side else x
        y = rng.uniform(0.12, 0.95) * h
        ph = rng.uniform(0, TAU)
        a = max(0.0, math.sin(int(rng.integers(2, 5)) * th + ph)) ** 2
        rr = rng.uniform(7, 16) * u
        if a > 0.02:
            d.polygon(star_poly(x, y, rr * (0.6 + 0.4 * a)), fill=(255, 255, 255, int(255 * a)))
            items.append(("star", x, y, rr * 2.2, a * 0.8))
    for i in range(16):
        side = i % 2
        span = h + 120 * u
        y = (rng.uniform(0, span) - (th / TAU) * span * int(rng.integers(1, 3))) % span - 60 * u
        x = rng.uniform(0.02, 0.14 if not vertical else 0.22) * w
        x = (w - x if side else x) + 10 * u * math.sin(th * 2 + i)
        hr = rng.uniform(10, 18) * u
        d.polygon(heart_poly(x, y, hr, 0.25 * math.sin(th + i)), fill=(255, 255, 255, 235), outline=HOT, width=int(3 * u))
    return finish(im, W, H, items)


def finish(im, W, H, items):
    """縮小 → 内側にうすい影 → キラキラの光を足す。"""
    w, h = im.size
    glow = glow_layer((w, h), items).resize((W, H), Image.BILINEAR)
    im = im.resize((W, H), Image.LANCZOS)
    a = im.getchannel("A")
    sh = a.filter(ImageFilter.GaussianBlur(max(3, W // 240)))
    sh = Image.eval(sh, lambda v: int(v * 0.35))
    shadow = Image.new("RGBA", (W, H), (150, 40, 90, 0))
    shadow.putalpha(sh)
    out = Image.alpha_composite(shadow, im)
    g = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    g.putalpha(glow)
    return Image.alpha_composite(out, g)


FRAMES = {"frill": frame_frill, "curtain": frame_curtain}


def export(name, fn, W, H, secs, fps, outdir, ffmpeg):
    n = int(secs * fps)
    base = os.path.join(outdir, name)
    common = ["-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    procs = [
        subprocess.Popen([ffmpeg] + common + ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                                              "-vendor", "apl0", base + "_alpha.mov"], stdin=subprocess.PIPE),
        subprocess.Popen([ffmpeg] + common + ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "26",
                                              "-row-mt", "1", "-auto-alt-ref", "0", base + "_alpha.webm"], stdin=subprocess.PIPE),
        subprocess.Popen([ffmpeg] + common + ["-c:v", "libx264", "-pix_fmt", "yuv420p",
                                                   "-crf", "16", base + "_green.mp4"], stdin=subprocess.PIPE),
    ]
    green = Image.new("RGBA", (W, H), (0, 255, 0, 255))
    for i in range(n):
        fr = fn(W, H, TAU * i / n, 7)
        if i == 0:
            fr.save(base + ".png")
        raw = fr.tobytes()
        procs[0].stdin.write(raw)
        procs[1].stdin.write(raw)
        procs[2].stdin.write(Image.alpha_composite(green, fr).tobytes())
        if i % 30 == 0:
            print(name, f"{i}/{n}", flush=True)
    for p in procs:
        p.stdin.close()
        p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out_frames")
    ap.add_argument("--only", choices=list(FRAMES))
    ap.add_argument("--vertical", action="store_true", help="縦型 1080x1920 で作る")
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--preview", type=float, default=None, help="この秒の確認用画像だけ書き出す")
    args = ap.parse_args()
    W, H = (1080, 1920) if args.vertical else (1920, 1080)
    os.makedirs(args.out, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    names = [args.only] if args.only else list(FRAMES)
    suffix = "_v" if args.vertical else ""
    for name in names:
        if args.preview is not None:
            fr = FRAMES[name](W, H, TAU * args.preview / args.seconds, 7)
            bg = Image.linear_gradient("L").resize((W, H)).convert("RGBA")
            Image.alpha_composite(bg, fr).save(os.path.join(args.out, f"preview_{name}{suffix}.png"))
            continue
        export(f"frame_{name}{suffix}", FRAMES[name], W, H, args.seconds, args.fps, args.out, ffmpeg)


if __name__ == "__main__":
    main()
