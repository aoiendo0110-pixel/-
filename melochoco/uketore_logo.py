"""「受け取れ♥」の動く文字 (フェルトのワッペン文字 × サテンのリボン × レースのハート) をグリーンバックで書き出す.

  python3 uketore_logo.py --font MochiyPopOne.ttf --font-sub HachiMaruPop.ttf --out clips/text/uketore_logo

  0.0-0.7  ピンクのサテンリボンが左から描かれていく
  0.3-1.1  リボンの先を追いかけて、文字が1つずつぽんっと跳ね出す (大きさ・角度・高さは1文字ずつ違う)
  1.1-1.6  レースのハートが奥から回りながら飛んできてドンッ → ハートが弾け、リボン結びがぽんっ
  1.6-4.4  リボンが波打ち、文字はそれぞれ違う揺れ方、ハートはドキドキ
  4.4-5.0  リボンが巻き戻り、文字が順に消える
文字はフェルト風 (中身の内側に白いステッチ)。クロマキー用に緑系の色と半透明のぼかしは使わない。
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

from zettai_reido_logo import (CHOCO_D, PINK, PINK_D, PINK_L, WHITE, clamp01, ease_out, ease_out_back, heart_poly,
                               heart_sticker, put, sparkle, spring)

W, H, FPS, DUR = 1920, 1080, 30, 5.0
EXIT_T = 4.4
SATIN, SATIN_D, SATIN_L = (236, 76, 138), (186, 38, 98), (255, 160, 198)
BERRY = (232, 58, 108)

# (文字, 中心, 大きさ, 傾き, 登場時刻, 中身の上色, 下色, ステッチの色)
LETTERS = [
    ("受", (390, 545), 1.18, -12, 0.30, (255, 178, 212), (246, 120, 172), WHITE),
    ("け", (668, 640), 0.86, 10, 0.46, (255, 250, 244), (255, 218, 232), PINK),
    ("取", (945, 510), 1.10, -5, 0.62, (246, 84, 132), (204, 34, 84), WHITE),
    ("れ", (1222, 615), 0.90, 13, 0.78, (255, 178, 212), (246, 120, 172), WHITE),
]
HEART_C, HEART_R, HEART_T = (1545, 480), 185, 1.1
# リボンの通り道 (Catmull-Rom で補間). 最後は♥の左上の結び目へ
RIBBON = [(40, 900), (260, 830), (480, 740), (660, 770), (840, 840), (1060, 720), (1250, 780), (1380, 610), (1420, 380)]
FRONT = []  # 文字の手前を通る区間 (経路の割合). 例: [(0.32, 0.40)]


def hump(u):
    return math.sin(math.pi * clamp01(u))


def ease_in(x):
    return clamp01(x) ** 2


# ---------------------------------------------------------------- 部品
def felt_letter(ch, font, size, top, bot, stitch):
    """フェルトのワッペン風の1文字: 厚み + 白フチ + チョコのフチ + グラデの中身 + 内側の点線ステッチ."""
    f = ImageFont.truetype(font, size)
    S = int(size * 1.7)

    def mask(st):
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).text((S / 2, S / 2), ch, font=f, anchor="mm", fill=255, stroke_width=st, stroke_fill=255)
        return m
    m0, m1, m2 = mask(0), mask(9), mask(26)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    for k in range(12, 0, -1):
        im.paste(CHOCO_D + (255,), (round(5 * k / 12), round(13 * k / 12)), m2)
    im.paste(WHITE + (255,), (0, 0), m2)
    im.paste(CHOCO_D + (255,), (0, 0), m1)
    a = np.array(m0)
    bb = m0.getbbox()
    g = np.zeros((S, S, 4), np.uint8)
    yy = np.clip((np.arange(S) - bb[1]) / (bb[3] - bb[1]), 0, 1)[:, None]
    for c in range(3):
        g[..., c] = (top[c] * (1 - yy) + bot[c] * yy).astype(np.uint8)
    g[..., 3] = a
    im.alpha_composite(Image.fromarray(g, "RGBA"))
    # 内側のステッチ: 少し細らせた輪郭の線を、点線にする
    e1 = np.array(m0.filter(ImageFilter.MinFilter(13))) > 128
    e2 = np.array(m0.filter(ImageFilter.MinFilter(19))) > 128
    ring = e1 & ~e2
    Y, X = np.mgrid[0:S, 0:S]
    dash = ((X + Y) // 9) % 2 == 0
    st = (ring & dash).astype(np.uint8) * 255
    im.paste(stitch + (255,), (0, 0), Image.fromarray(st))
    # ツヤ (上のほう)
    inner = np.array(m0.filter(ImageFilter.MinFilter(25))).astype(np.float32) / 255
    fade = np.clip((0.42 - yy) / 0.3, 0, 1)
    hl = Image.fromarray(np.minimum((inner * fade * 0.45 * 255).astype(np.uint8), a))
    im.paste(WHITE + (255,), (0, 0), hl.filter(ImageFilter.GaussianBlur(2)))
    return im


def lace_heart(r):
    """レースのフリルで縁取ったハート (ステッチ + ツヤ + 厚み)."""
    S = int(r * 2.9)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    outline = heart_poly(c, c, r + 26, 96)
    # フリル: 輪郭に沿って丸を並べる
    for pad, col in ((10, PINK_D), (5, WHITE)):
        for x, y in outline[::2]:
            d.ellipse((x - 22 - pad, y - 22 - pad, x + 22 + pad, y + 22 + pad), fill=col)
        d.polygon(heart_poly(c, c, r + 26 + pad, 96), fill=col)
    for x, y in outline[1::2]:  # レースの穴
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=PINK_L)
    d.polygon(heart_poly(c + 6, c + 14, r + 4), fill=CHOCO_D)  # 厚み
    d.polygon(heart_poly(c, c, r + 4), fill=CHOCO_D)
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon(heart_poly(c, c, r - 4), fill=255)
    a = np.array(m)
    yy = np.clip((np.arange(S) - (c - r)) / (2 * r), 0, 1)[:, None]
    g = np.zeros((S, S, 4), np.uint8)
    for k, (t0, b0) in enumerate(zip((255, 120, 168), BERRY)):
        g[..., k] = (t0 * (1 - yy) + b0 * yy).astype(np.uint8)
    g[..., 3] = a
    im.alpha_composite(Image.fromarray(g, "RGBA"))
    pts = heart_poly(c, c, r - 22, 140)  # ステッチ
    for i in range(0, len(pts) - 1, 2):
        d.line([pts[i], pts[i + 1]], fill=WHITE, width=6)
    d.ellipse((c - r * 0.62, c - r * 0.62, c - r * 0.18, c - r * 0.3), fill=(255, 214, 230))
    d.ellipse((c - r * 0.52, c - r * 0.56, c - r * 0.32, c - r * 0.42), fill=WHITE)
    return im


def bow():
    S = (300, 220)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = S[0] / 2, 90
    for pad, col in ((9, WHITE), (0, None)):
        for s in (-1, 1):
            d.polygon([(cx, cy), (cx + s * (115 + pad), cy - 62 - pad), (cx + s * (125 + pad), cy + 52 + pad)],
                      fill=col or SATIN)
            d.polygon([(cx - s * 4, cy + 6), (cx + s * (52 + pad), cy + 118 + pad), (cx + s * 30, cy + 104),
                       (cx + s * 16, cy + 124 + pad)], fill=col or SATIN_D)
    for s in (-1, 1):
        d.polygon([(cx, cy), (cx + s * 70, cy - 26), (cx + s * 76, cy + 22)], fill=SATIN_D)
        d.line([(cx + s * 40, cy - 30), (cx + s * 100, cy - 52)], fill=SATIN_L, width=7)
    d.ellipse((cx - 32, cy - 30, cx + 32, cy + 30), fill=WHITE)
    d.ellipse((cx - 24, cy - 23, cx + 24, cy + 23), fill=SATIN)
    return im


def tag(font):
    f = ImageFont.truetype(font, 56)
    txt = "for you♡"
    w = int(f.getlength(txt)) + 70
    im = Image.new("RGBA", (w + 20, 124), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 18, w + 12, 114), 46, fill=CHOCO_D)
    d.rounded_rectangle((4, 8, w + 8, 104), 46, fill=WHITE)
    d.rounded_rectangle((12, 16, w, 96), 40, fill=(255, 238, 244))
    for x in range(34, w - 20, 16):
        d.rectangle((x, 86, x + 8, 89), fill=PINK)
    d.text((w / 2 + 6, 54), txt, font=f, anchor="mm", fill=PINK_D)
    return im


def catmull(pts, n=500):
    P = np.array(pts, float)
    P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]])
    out = []
    seg = len(P) - 3
    for i in range(seg):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for u in np.linspace(0, 1, n // seg, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    out.append(P[-2])
    return np.array(out)


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, font_sub):
        self.letters = [felt_letter(ch, font, round(220 * sc), top, bot, st)
                        for ch, _, sc, _, _, top, bot, st in LETTERS]
        self.heart = lace_heart(HEART_R)
        self.bow = bow()
        self.tag = tag(font_sub)
        self.path = catmull(RIBBON)
        self.hearts = {r: heart_sticker(r) for r in (16, 22, 30)}
        self.sp_w, self.sp_p = sparkle(24), sparkle(30, PINK, WHITE)
        self.twinkles = [(300, 420, "w", 0.0), (820, 330, "p", 0.35), (1700, 300, "w", 0.6), (1650, 760, "p", 0.15),
                         (560, 840, "w", 0.8), (1080, 820, "p", 0.5)]

    def ribbon_pts(self, t, reveal):
        n = len(self.path)
        k = max(2, int(n * reveal))
        p = self.path[:k].copy()
        idle = clamp01((t - 1.6) / 0.4)
        s = np.arange(k) / n
        p[:, 1] += idle * 12 * np.sin(2 * math.pi * t / 1.6 - s * 14) * np.minimum(1, (1 - s) * 6)
        return p

    def draw_ribbon(self, im, p, ranges=None):
        d = ImageDraw.Draw(im)
        n = len(self.path)
        idx = np.arange(len(p)) / n

        def segs():
            if ranges is None:
                yield p
                return
            for a, b in ranges:
                q = p[(idx >= a) & (idx <= b)]
                if len(q) > 1:
                    yield q
        for q in segs():
            # 太い線をつなぐと継ぎ目にトゲが出るので、丸を連ねて描く
            nrm = np.gradient(q, axis=0)
            nrm = np.stack([-nrm[:, 1], nrm[:, 0]], 1)
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-6
            layers = ((31, WHITE, 0), (23, SATIN, 0), (5, SATIN_D, -14), (4.5, SATIN_L, 11))
            if ranges is not None:  # 手前の区間は白フチなしで、奥のリボンとつなげる
                layers = layers[1:]
            for r, col, off in layers:
                for (x, y), (nx, ny) in zip(q, nrm):
                    x, y = x + nx * off, y + ny * off
                    d.ellipse((x - r, y - r, x + r, y + r), fill=col)
            for i in range(0, len(q) - 1, 9):  # ステッチ
                x, y = q[i] + nrm[i] * 17
                d.ellipse((x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=WHITE)
            if ranges is None:  # 端の丸
                e = q[0]
                d.ellipse((e[0] - 31, e[1] - 31, e[0] + 31, e[1] + 31), fill=WHITE)
                d.ellipse((e[0] - 23, e[1] - 23, e[0] + 23, e[1] + 23), fill=SATIN)

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idle = clamp01((t - 1.6) / 0.4)
        P = 2 * math.pi * t / 1.6
        ex = clamp01((t - EXIT_T) / (DUR - EXIT_T))
        reveal = ease_out(t / 0.7) * (1 - ease_in(ex / 0.7))
        beat = (hump((t % 0.9) / 0.11) * 0.08 + hump(((t % 0.9) - 0.16) / 0.11) * 0.05) * idle

        # キラキラ
        if t > 1.5:
            for x, y, kind, ph in self.twinkles:
                q = ((t - 1.5) / 1.1 + ph) % 1
                put(im, self.sp_w if kind == "w" else self.sp_p, x, y, hump(q / 0.45) ** 2 * 1.2 * (1 - ex), 45 * q)
        # リボン (文字の奥)
        p = self.ribbon_pts(t, reveal) if reveal > 0.002 else None
        if p is not None:
            self.draw_ribbon(im, p)
            tip = p[-1]
            if t < 0.75:
                put(im, self.sp_w, tip[0], tip[1], 1.3, t * 300)

        # ハート (♥): 奥から回りながら飛んでくる
        if t > HEART_T:
            u = (t - HEART_T) / 0.4
            e = ease_out(u)
            cx, cy = HEART_C
            x, y = 960 + (cx - 960) * e, 540 + (cy - 540) * e
            land = t - HEART_T - 0.4
            s = (0.15 + 0.85 * ease_out_back(u, 2.6)) * (1 + beat)
            s *= 1 - ease_in((ex - 0.55) / 0.45)
            sq = spring(land, 0.16, 20, 7)
            rot = 10 + 360 * (1 - e) + idle * 4 * math.sin(P * 0.5)
            put(im, self.heart, x, y, s, rot, 1 + sq, 1 - sq)
            if 0 < land < 0.7:
                q = land / 0.7
                for k in range(10):
                    a = 2 * math.pi * k / 10 + 0.3
                    rr = 220 + 200 * ease_out(q)
                    put(im, self.hearts[(16, 22, 30)[k % 3]], cx + rr * math.cos(a), cy + rr * math.sin(a) - 30 * q,
                        1.2 * (1 - q ** 2), 20 * k)
            # 浮かんでいく小さいハート
            if t > 1.8:
                for j in range(4):
                    q = ((t - 1.8) / 1.6 + j / 4) % 1
                    put(im, self.hearts[16 if j % 2 else 22], cx + 230 + 30 * math.sin(q * 8 + j), cy - 80 - 260 * q,
                        hump(q) * (1 - ex), 15 * math.sin(q * 6))

        # 文字: リボンの先を追いかけてぽんっ
        for i, (ch, (x, y), sc, rot, t0, *_ ) in enumerate(LETTERS):
            u = (t - t0) / 0.4
            if u < 0:
                continue
            k = ease_out_back(u, 2.6) * (1 - ease_in((ex * 1.6 - (3 - i) * 0.12) / 0.5))
            if k <= 0.01:
                continue
            land = t - t0 - 0.4
            jump = 70 * hump(u / 0.9)
            r = rot + (1 - ease_out(u)) * (-35 if i % 2 == 0 else 35)
            # 待機: 1文字ずつ違う揺れ方
            if i % 2 == 0:  # ゆらゆら
                r += idle * 4 * math.sin(P * 0.8 + i)
                yy = y + idle * 6 * math.sin(P * 0.8 + i)
                sx = sy = 1.0
            else:  # ぴょこぴょこ
                q = (P / (2 * math.pi) * 1.25 + i * 0.3) % 1
                yy = y - idle * 22 * hump(q / 0.35)
                sq = idle * 0.06 * (hump((q - 0.35) / 0.2) - hump(q / 0.08) * 0.5)
                sx, sy = 1 + sq, 1 - sq
            sq2 = spring(land, 0.14, 22, 8)
            put(im, self.letters[i], x, yy - jump, k, r, sx * (1 + sq2), sy * (1 - sq2))

        # リボン (文字の手前を通る区間)
        if p is not None and FRONT:
            self.draw_ribbon(im, p, FRONT)
        # リボン結び (♥の左上)
        if t > HEART_T + 0.3:
            k = ease_out_back((t - HEART_T - 0.3) / 0.35, 2.8) * (1 - ease_in(ex / 0.5))
            if k > 0:
                put(im, self.bow, RIBBON[-1][0] + 10, RIBBON[-1][1] - 10, k,
                    -18 + spring(t - HEART_T - 0.3, 16, 13, 4) + idle * 4 * math.sin(P * 0.6))
        # for you タグ
        k = ease_out_back((t - 1.6) / 0.4, 2.4) * (1 - ease_in(ex / 0.5))
        if k > 0:
            put(im, self.tag, 1640, 800 + idle * 6 * math.sin(P + 1), k, -8 + spring(t - 1.6, 18, 10, 4)
                + idle * 3 * math.sin(P * 0.7))
        return im


SCENE = None


def _init(font, font_sub):
    global SCENE
    SCENE = Scene(font, font_sub)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Mochiy Pop One など丸い太字")
    ap.add_argument("--font-sub", required=True, help="Hachi Maru Pop など手書き風")
    ap.add_argument("--out", default="uketore_logo")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    if a.preview is not None:
        _init(a.font, a.font_sub)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = round(DUR * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.font_sub)) as pool:
        frames = pool.map(_frame, range(n), chunksize=4)
    Image.frombytes("RGBA", (W, H), frames[int(n * 0.6)]).save(a.out + ".png")
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
