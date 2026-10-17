"""縦 (9:16) の「コテ注意 / 御相手様映り込みなし」ロゴ動画: ショートケーキ・いちご・ケーキ作り・ホイップ・カフェ版.

  python3 props_ichigo3d.py --out props_ichigo        # 3Dモデル (Blender) を先に作る
  python3 kote_chui_vertical_ichigo.py --font HachiMaruPop.ttf --props props_ichigo --out clips/text/kote_chui_vertical_ichigo

kote_chui_vertical.py (チョコ版) と同じ配置・同じ動きで、モチーフだけ差し替えた別バージョン.
  メイン: 「コテ」= いちごの赤 /「注意」= スポンジに生クリームがけ
  サブ:   いちご色のプレート + 絞り出しホイップの縁
  飾り:   ホイップのついた泡立て器とボウル・絞り袋・いちご (丸ごと / 断面)・ショートケーキ・
          ラテのカップ (湯気が揺れる)・リボン・きらめき
いちごはヘタ (緑) を付けずに描く (クロマキーで抜けないように)。
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import os
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

from kote_chui_vertical import FS, SUB_Y, H, W, FPS, bowl, hump, sub_plate, whisk
from melodic_choco_logo import Glyph, bow
from zettai_reido_logo import CHOCO_D, PINK_D, WHITE, heart_poly, heart_sticker, put, sparkle

RED, RED_D, RED_L = (236, 52, 86), (170, 20, 50), (255, 130, 150)
CREAM, CREAM_S = (255, 252, 248), (238, 214, 220)  # 生クリームと、その影
SPONGE, SPONGE_D = (250, 214, 140), (222, 168, 92)
STRAW = dict(top=(255, 116, 140), bot=(222, 30, 64), stitch=WHITE, ext=(120, 10, 34), ring=CHOCO_D)
CAKE = dict(top=(252, 222, 150), bot=(232, 182, 104), stitch=(255, 150, 180), ext=(140, 90, 40), ring=CHOCO_D,
            glaze=(CREAM, (252, 238, 236)), glaze_rim=(255, 196, 212))
MAIN = [("コ", (330, 680), 1.0, -10, STRAW), ("テ", (740, 645), 0.95, 9, STRAW),
        ("注", (315, 1065), 1.02, -6, CAKE), ("意", (765, 1090), 1.02, 7, CAKE)]


# ---------------------------------------------------------------- 部品 (どれもステッカー風: 白フチ + こげ茶の線)
def _canvas(w, h):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def strawberry_pts(cx, cy, r, pad=0):
    pts = []
    for i in range(60):
        a = 2 * math.pi * i / 60
        x = math.sin(a) * (0.82 + 0.18 * math.cos(a))
        y = -math.cos(a)
        y = y * (1.1 if y > 0 else 0.8)
        k = 1 - 0.32 * max(0, y)  # 下ほど細く
        pts.append((cx + (x * k * r) + math.copysign(pad, x), cy + y * r + math.copysign(pad, y)))
    return pts


def strawberry(r=90):
    im, d = _canvas(int(r * 2.6), int(r * 2.8))
    cx, cy = im.width / 2, im.height / 2 + 6
    d.polygon(strawberry_pts(cx, cy, r, 14), fill=WHITE)
    d.polygon(strawberry_pts(cx, cy, r, 6), fill=CHOCO_D)
    d.polygon(strawberry_pts(cx, cy, r), fill=RED)
    d.polygon(strawberry_pts(cx + r * 0.12, cy + r * 0.1, r * 0.82), fill=(214, 34, 70))
    d.polygon(strawberry_pts(cx - r * 0.06, cy - r * 0.04, r * 0.8), fill=RED)
    for j in range(5):  # 種
        for i in range(6 - j % 2):
            x = cx + (i - 2.5 + 0.5 * (j % 2)) * r * 0.3 * (1 - j * 0.12)
            y = cy - r * 0.45 + j * r * 0.3
            d.ellipse((x - 4, y - 6, x + 4, y + 6), fill=(255, 226, 120))
    d.ellipse((cx - r * 0.55, cy - r * 0.62, cx - r * 0.2, cy - r * 0.35), fill=(255, 190, 200))
    # ヘタの代わりに、上にちょこんとホイップ
    put(im, cream_dollop(r * 0.42), cx, cy - r * 0.86, 1.0)
    return im


def strawberry_half(r=80):
    """いちごの断面 (ハート形)."""
    im, d = _canvas(int(r * 2.8), int(r * 2.8))
    c = im.width / 2
    d.polygon(heart_poly(c, c, r + 14), fill=WHITE)
    d.polygon(heart_poly(c, c, r + 6), fill=CHOCO_D)
    d.polygon(heart_poly(c, c, r), fill=RED)
    d.polygon(heart_poly(c, c - 4, r * 0.72), fill=RED_L)
    d.polygon(heart_poly(c, c - 8, r * 0.42), fill=(255, 220, 226))
    for a in range(0, 360, 30):
        x, y = c + r * 0.55 * math.cos(math.radians(a)), c - 6 + r * 0.45 * math.sin(math.radians(a))
        d.line([(c, c - 8), (x, y)], fill=(255, 196, 206), width=3)
    return im


def cream_dollop(r=60):
    """絞り出したホイップ (段々 + 先がくるん)."""
    im, d = _canvas(int(r * 2.6), int(r * 2.6))
    cx, cy = im.width / 2, im.height / 2 + r * 0.35
    tiers = [(1.0, 0.0), (0.74, -0.42), (0.48, -0.8)]
    for pad, col in ((10, WHITE), (5, CREAM_S)):
        for k, dy in tiers:
            d.ellipse((cx - r * k - pad, cy + dy * r - r * 0.36 * k - pad, cx + r * k + pad,
                       cy + dy * r + r * 0.36 * k + pad), fill=col)
        d.polygon([(cx - r * 0.3 - pad, cy - r * 0.9), (cx + r * 0.25 + pad, cy - r * 0.95),
                   (cx + r * 0.12, cy - r * 1.45 - pad)], fill=col)
    for k, dy in tiers:
        d.ellipse((cx - r * k, cy + dy * r - r * 0.36 * k, cx + r * k, cy + dy * r + r * 0.36 * k), fill=CREAM)
        d.arc((cx - r * k * 0.8, cy + dy * r - r * 0.3 * k, cx + r * k * 0.8, cy + dy * r + r * 0.3 * k), 20, 160,
              fill=CREAM_S, width=4)
    d.polygon([(cx - r * 0.28, cy - r * 0.9), (cx + r * 0.22, cy - r * 0.95), (cx + r * 0.12, cy - r * 1.42)],
              fill=CREAM)
    d.ellipse((cx - r * 0.5, cy - r * 0.18, cx - r * 0.2, cy - r * 0.02), fill=WHITE)
    return im


def piping_bag():
    """絞り袋 (先からホイップが出ている). 先が左下."""
    im, d = _canvas(360, 360)
    tip = (95, 270)
    body = [(150, 40), (330, 160), (tip[0] + 18, tip[1] - 30), (tip[0] - 6, tip[1] - 46)]
    for pad, col in ((14, WHITE), (6, CHOCO_D)):
        d.polygon([(x + (pad if x > 200 else -pad), y + (pad if y > 200 else -pad)) for x, y in body], fill=col)
    d.polygon(body, fill=(255, 196, 220))
    for k in range(1, 5):  # 縞
        u = k / 5
        a = (150 + (330 - 150) * u, 40 + (160 - 40) * u)
        d.line([a, (tip[0] + 6, tip[1] - 38)], fill=WHITE, width=10)
    d.rounded_rectangle((280, 110, 352, 200), 18, fill=PINK_D)  # ねじった口
    for pad, col in ((10, WHITE), (4, CHOCO_D), (0, (236, 226, 232))):  # 口金
        d.polygon([(tip[0] - 10 - pad, tip[1] - 52 - pad), (tip[0] + 30 + pad, tip[1] - 26 - pad),
                   (tip[0] + 4, tip[1] + pad), (tip[0] - 14 - pad, tip[1] - 10)], fill=col)
    return im


def shortcake():
    """ショートケーキの一切れ (斜め前から)."""
    im, d = _canvas(380, 380)
    L, R_, T, B = 60, 330, 170, 320
    apex = (90, 120)
    for pad, col in ((14, WHITE), (6, CHOCO_D)):
        d.polygon([(L - pad, T - pad), (apex[0] - pad, apex[1] - pad), (R_ + pad, T - 10 - pad), (R_ + pad, B + pad),
                   (L - pad, B + pad)], fill=col)
    d.polygon([(L, T), apex, (R_, T - 10), (L + 40, T + 4)], fill=CREAM)  # 上面のクリーム
    d.rectangle((L, T, R_, B), fill=SPONGE)  # 側面: スポンジ / クリーム / いちご / スポンジ
    d.rectangle((L, T, R_, T + 18), fill=CREAM)
    d.rectangle((L, T + 60, R_, T + 92), fill=CREAM)
    for x in range(L + 18, R_ - 10, 44):
        d.ellipse((x - 18, T + 62, x + 18, T + 92), fill=RED)
        d.ellipse((x - 9, T + 68, x + 9, T + 86), fill=RED_L)
    d.rectangle((L, B - 16, R_, B), fill=SPONGE_D)
    for x in range(L + 10, R_, 22):
        d.ellipse((x - 3, T + 30, x + 3, T + 36), fill=SPONGE_D)
        d.ellipse((x + 8, T + 116, x + 14, T + 122), fill=SPONGE_D)
    put(im, cream_dollop(46), 200, T - 40, 1.0)
    put(im, strawberry(46), 205, T - 92, 1.0, 10)
    return im


def latte():
    """ソーサー付きのラテ (ハートのラテアート). 湯気は frame で描く."""
    im, d = _canvas(360, 300)
    cx = 170
    for pad, col in ((12, WHITE), (6, CHOCO_D), (0, (255, 214, 228))):  # ソーサー
        d.ellipse((cx - 160 - pad, 220 - pad, cx + 160 + pad, 290 + pad), fill=col)
    for pad, col in ((12, WHITE), (6, CHOCO_D), (0, (255, 160, 200))):  # 取っ手
        d.ellipse((cx + 100 - pad, 110 - pad, cx + 175 + pad, 200 + pad), outline=col, width=26 + pad)
    for pad, col in ((12, WHITE), (6, CHOCO_D), (0, (255, 160, 200))):  # カップ
        d.chord((cx - 125 - pad, 10 - pad, cx + 125 + pad, 270 + pad), 0, 180, fill=col)
        d.ellipse((cx - 128 - pad, 90 - pad, cx + 128 + pad, 160 + pad), fill=col)
    d.ellipse((cx - 112, 98, cx + 112, 152), fill=(196, 140, 98))
    d.polygon(heart_poly(cx, 124, 28), fill=CREAM)
    d.polygon(heart_poly(cx, 128, 14), fill=(214, 166, 124))
    for x in range(cx - 90, cx + 100, 36):  # 水玉
        d.ellipse((x - 8, 200, x + 8, 216), fill=WHITE)
    return im


def steam(im, x, y, u):
    d = ImageDraw.Draw(im)
    for k in range(3):
        pts = [(x + (k - 1) * 40 + 10 * math.sin(2 * math.pi * (u * 2 + k * 0.3) + j / 3), y - j * 7)
               for j in range(9)]
        d.line(pts, fill=WHITE, width=12, joint="curve")


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, L, props=None):
        self.L = L
        self.letters = [dict(g=Glyph(ch, font, round(FS * sc), st, 10, False), x=x, y=y, rot=rot)
                        for ch, (x, y), sc, rot, st in MAIN]
        self.sub = sub_plate(font, fill=RED, crumb=CREAM_S, line=RED_D)
        self.whisk = whisk(CREAM, WHITE)
        self.bowl = bowl((255, 250, 248), WHITE)
        self.bow = bow()
        self.bag, self.cake, self.cup = piping_bag(), shortcake(), latte()
        self.berry, self.half, self.dollop = strawberry(), strawberry_half(), cream_dollop(56)
        self.glint = sparkle(36, WHITE, (255, 128, 182))
        self.hearts = {r: heart_sticker(r) for r in (18, 26, 34)}
        if props:  # 3Dモデル (props_ichigo3d.py) があれば差し替える. 高さを2D版の絵に合わせて縮める
            def load(name, ref, k=0.9):
                im = Image.open(os.path.join(props, name + ".png")).convert("RGBA")
                s = ref.height * k / im.height
                return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
            self.whisk = load("whisk", self.whisk, 0.92)
            self.bowl = load("bowl", self.bowl, 1.05)
            self.bag = load("bag", self.bag, 1.0)
            self.dollop = load("cream", self.dollop, 0.8)
            self.cake = load("cake", self.cake, 0.95)
            self.cup = load("latte", self.cup, 0.95)
            self.bow = load("bow", self.bow, 0.95)
            self.berry = load("strawberry", self.berry, 0.95)
            self.half = load("strawberry", self.half, 1.25)

    def frame(self, t):
        u = t / self.L  # 0-1 で1周
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pulse = 1 + 0.025 * math.exp(-((u * 4) % 1) * 6)
        s2pi = lambda k, ph=0.0: math.sin(2 * math.pi * u * k + ph)

        # 右上: ホイップを泡立て中のボウル / 左上: 絞り袋からホイップ
        put(im, self.bowl, 880, 485, 0.82, 6 + 2 * s2pi(2))
        put(im, self.whisk, 865, 250 + 6 * s2pi(4, 1), 0.72, -8 + 14 * s2pi(4))  # 泡立て器はボウルの手前
        squeeze = 0.9 + 0.1 * hump(((u * 2) % 1) / 0.5)
        put(im, self.bag, 470, 190 + 6 * s2pi(2), 0.8 * squeeze, 4 * s2pi(2, 1))
        put(im, self.dollop, 575, 385, 0.7 * (0.85 + 0.15 * squeeze), 0)
        for x, ph, r in ((120, 0.0, 26), (980, 0.5, 18), (90, 0.35, 18), (1000, 0.8, 34)):
            q = (u * 2 + ph) % 1
            put(im, self.hearts[r], x + 18 * math.sin(q * 6), 1300 - 700 * q, hump(q) * 1.1, 15 * math.sin(q * 5))

        # メインの文字
        for i, it in enumerate(self.letters):
            q = (u * 4 - i * 0.16) % 1
            hop = 30 * hump(q / 0.3)
            sq = 0.06 * (hump((q - 0.3) / 0.15) - 0.5 * hump(q / 0.06))
            rot = it["rot"] + 3 * s2pi(2, i)
            sh = ((u * 2) % 1 - i * 0.07) / 0.25
            put(im, it["g"].draw(0, sh if 0 < sh < 1 else None), it["x"], it["y"] - hop, pulse, rot, 1 + sq, 1 - sq)
            ph = (u * 2 + i * 0.27) % 1
            s3 = hump(ph / 0.3) ** 2
            if s3 > 0.05:
                gx, gy = it["g"].glint
                a = math.radians(-rot)
                put(im, self.glint, it["x"] + gx * math.cos(a) - gy * math.sin(a),
                    it["y"] - hop + gx * math.sin(a) + gy * math.cos(a), s3 * 1.3, 45 * ph)
        c = self.letters[0]
        put(im, self.bow, c["x"] - 120, c["y"] - 235 - 30 * hump(((u * 4) % 1) / 0.3), 1.15, 18 + 6 * s2pi(2))
        # 横: いちごの断面
        put(im, self.half, 980, 905 + 14 * s2pi(2, 2), 0.62, 14 + 6 * s2pi(2))
        put(im, self.half, 100, 1290 + 12 * s2pi(2, 1), 0.5, -12 + 6 * s2pi(2, 1))

        # 下: ショートケーキ・ラテ・いちご (順にぴょこぴょこ)
        for j, (spr, x, s) in enumerate(((self.berry, 230, 0.95), (self.cake, 540, 0.74), (self.cup, 850, 0.72))):
            q = (u * 4 - j * 0.2) % 1
            hop = 26 * hump(q / 0.3)
            put(im, spr, x, 1765 - hop, s, 6 * s2pi(2, j))
            if spr is self.cup:
                steam(im, x - 10, 1765 - hop - 95, u)
        # サブ文字のプレート
        put(im, self.sub, W / 2, SUB_Y + 8 * s2pi(2), 1, -2 + 1.5 * s2pi(1))
        return im


SCENE = None


def _init(font, L, props):
    global SCENE
    SCENE = Scene(font, L, props)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Hachi Maru Pop など手書きの丸文字")
    ap.add_argument("--out", default="kote_chui_vertical_ichigo")
    ap.add_argument("--length", type=float, default=3.27, help="動画の長さ (秒). 動きの1周もこの長さ")
    ap.add_argument("--props", help="props_ichigo3d.py で作った3Dモデルの透過PNGのフォルダ (無ければ2Dの絵)")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    if a.preview is not None:
        _init(a.font, a.length, a.props)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = math.ceil(a.length * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.length, a.props)) as pool:
        frames = pool.map(_frame, range(n), chunksize=4)
    Image.frombytes("RGBA", (W, H), frames[n // 3]).save(a.out + ".png")
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    raw = ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    for args in ([*raw, "-f", "lavfi", "-i", f"color=0x00FF00:s={W}x{H}:r={FPS}",
                  "-filter_complex", "[1][0]overlay=shortest=1,format=yuv420p", "-t", str(a.length), "-c:v",
                  "libx264", "-crf", "16", "-movflags", "+faststart", a.out + "_greenback.mp4"],
                 [*raw, "-t", str(a.length), "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
                  "-row-mt", "1", "-auto-alt-ref", "0", a.out + ".webm"]):
        p = subprocess.Popen([ff, "-y", "-v", "error", *args], stdin=subprocess.PIPE)
        for fb in frames:
            p.stdin.write(fb)
        p.stdin.close()
        p.wait()


if __name__ == "__main__":
    main()
