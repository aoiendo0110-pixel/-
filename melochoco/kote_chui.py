"""「コテ注意 / ワンク4秒」の注意画面動画 (16:9) を書き出す.

  python3 kote_chui.py --font HachiMaruPop.ttf --out clips/text/kote_chui.mp4 [--length 207]

動きの1周を --length 秒 (既定 3.27秒) にして、ちょうど1周ぶんを書き出す (繰り返し再生してもつながる)。
  背景: ピンクとクリームの斜めストライプ (小さいハート) が流れる
  上:   チョコがとろっと垂れる / 下: ピンクと白レースの2段フリルが揺れる / 左右: 回る3Dのチョコハート
  主役: 「コテ」はいちごピンク、「注意」はチョコがけ。画面いっぱいに、ビートで波のように跳ねる
  札:   「ワンク4秒」を燕尾のサテンリボンに
"""
import argparse
import math
import os
import random
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from melodic_choco_logo import MILK, Glyph, bow
from zettai_reido_logo import CHOCO_D, PINK_D, WHITE, heart_poly, heart_sticker, put, sparkle

W, H, FPS = 1920, 1080, 30
LOOP = 4.0  # 動きの1周の長さ (--length で動画の長さに合わせる)
RED = dict(top=(255, 120, 170), bot=(226, 40, 104), stitch=WHITE, ext=(120, 16, 56), ring=CHOCO_D)
PINK = dict(top=(255, 200, 226), bot=(250, 130, 182), stitch=WHITE, ext=(150, 30, 80), ring=CHOCO_D)
# (文字, 大きさ, 傾き, 上下のずれ, 色)
MAIN = [("コ", 1.0, -10, 10, PINK), ("テ", 0.95, 8, -18, PINK), ("注", 1.12, -6, 6, MILK), ("意", 1.12, 7, -10, MILK)]
MAIN_Y, GAP = 440, -16


def hump(u):
    return math.sin(math.pi * min(max(u, 0.0), 1.0))


def background():
    """ピンクとクリームの斜めストライプ + 小さいハート (1周期ぶん横に長く描いて、ずらして使う)."""
    P = 120
    yy, xx = np.mgrid[0:H, 0:W + P]
    s = ((xx + yy) // (P // 2)) % 2
    arr = np.zeros((H, W + P, 3), np.uint8)
    arr[s == 0] = (255, 210, 228)
    arr[s == 1] = (255, 240, 236)
    im = Image.fromarray(arr)
    d = ImageDraw.Draw(im)
    for y in range(60, H, 120):
        for x in range(0, W + P, 120):
            ox = 60 if (y // 120) % 2 else 0
            d.polygon(heart_poly(x + ox, y, 11), fill=WHITE)
    return im, P


def choco_top():
    """上から垂れるチョコ (ツヤ + 照り). 垂れの先は毎コマ少し伸び縮みさせる."""
    h = 230
    im = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rnd = random.Random(4)
    drips = []
    x = 20
    while x < W:
        drips.append((x, rnd.uniform(40, 150), rnd.uniform(26, 44)))
        x += rnd.uniform(90, 170)
    for pad, col in ((10, WHITE), (0, (92, 46, 30))):
        d.rectangle((0, 0, W, 70 + pad), fill=col)
        for i in range(0, W + 60, 60):  # 波打つ縁
            d.ellipse((i - 40, 40 - pad, i + 40, 100 + pad), fill=col)
    d.rectangle((0, 0, W, 66), fill=(92, 46, 30))
    d.line([(0, 26), (W, 26)], fill=(150, 90, 62), width=8)
    return im, drips


def draw_drips(im, drips, u):
    d = ImageDraw.Draw(im)
    for j, (x, L, w) in enumerate(drips):
        ln = L * (0.85 + 0.15 * math.sin(2 * math.pi * (u + j * 0.13)))
        for pad, col in ((10, WHITE), (0, (92, 46, 30))):
            d.rounded_rectangle((x - w / 2 - pad, 50, x + w / 2 + pad, 70 + ln + pad), radius=w / 2 + pad, fill=col)
            d.ellipse((x - w * 0.62 - pad, 70 + ln - w * 0.6 - pad, x + w * 0.62 + pad, 70 + ln + w * 0.6 + pad),
                      fill=col)
        d.ellipse((x - w * 0.35, 66 + ln - w * 0.3, x - w * 0.05, 66 + ln), fill=(170, 108, 78))


def frill_bottom(phase):
    """下のフリル2段 (ピンクのプリーツ + 白いレース). phase でひだが揺れる."""
    h = 170
    im = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pw = 64
    for layer, (top, col, dark, amp) in enumerate(((10, (255, 150, 196), (226, 88, 150), 1.0),
                                                     (74, WHITE, (255, 196, 220), 0.7))):
        off = (phase * pw * (1 if layer else -1)) % pw
        for k in range(-1, W // pw + 2):
            x = k * pw + off
            sway = 6 * math.sin(2 * math.pi * (phase + k * 0.15)) * amp
            pts = [(x, top), (x + pw, top), (x + pw + sway, h - 20), (x + sway, h - 20)]
            d.polygon(pts, fill=col)
            d.line([(x + pw / 2, top + 6), (x + pw / 2 + sway, h - 28)], fill=dark, width=5)
            d.ellipse((x + sway - 2, h - 52, x + pw + sway + 2, h - 2), fill=col)
            if layer:  # レースの穴
                d.ellipse((x + pw / 2 + sway - 7, h - 34, x + pw / 2 + sway + 7, h - 20), fill=(255, 196, 220))
    d.rectangle((0, 0, W, 24), fill=(236, 76, 138))
    d.rectangle((0, 4, W, 8), fill=(255, 170, 205))
    for x in range(0, W, 26):
        d.rectangle((x, 16, x + 13, 19), fill=WHITE)
    return im


def plate(font):
    """「ワンク4秒」を燕尾のリボン帯に."""
    f = ImageFont.truetype(font, 92)
    txt = "ワンク4秒"
    w = int(f.getlength(txt)) + 150
    h = 150
    S = (w + 300, h + 60)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = S[0] / 2, S[1] / 2
    sat, satd, satl = (236, 76, 138), (186, 38, 98), (255, 170, 205)
    for s in (-1, 1):  # 燕尾のしっぽ (後ろ)
        x0, x1 = cx + s * (w / 2 - 40), cx + s * (w / 2 + 130)
        for pad, col in ((10, WHITE), (0, satd)):
            d.polygon([(x0, cy - h / 2 + 30 - pad), (x1 + s * pad, cy - h / 2 + 30 - pad), (x1 - s * 50, cy + 16),
                       (x1 + s * pad, cy + h / 2 + 30 + pad), (x0, cy + h / 2 + 30 + pad)], fill=col)
    for pad, col in ((14, (226, 78, 140)), (8, WHITE), (0, sat)):
        d.rounded_rectangle((cx - w / 2 - pad, cy - h / 2 - pad, cx + w / 2 + pad, cy + h / 2 + pad), 24, fill=col)
    d.rectangle((cx - w / 2, cy - h / 2 + 14, cx + w / 2, cy - h / 2 + 24), fill=satl)
    for x in range(int(cx - w / 2) + 20, int(cx + w / 2) - 20, 24):
        d.rectangle((x, cy + h / 2 - 20, x + 12, cy + h / 2 - 16), fill=WHITE)
    d.text((cx, cy + 4), txt, font=f, anchor="mm", fill=WHITE, stroke_width=10, stroke_fill=CHOCO_D)
    return im


class Scene:
    def __init__(self, font, cache):
        self.bg, self.bgP = background()
        self.choco, self.drips = choco_top()
        self.plate = plate(font)
        self.heart3d = [Image.open(os.path.join(cache, f"choco_heart_520_{i:02d}.png")).convert("RGBA")
                        for i in range(60)]
        self.hearts = {r: heart_sticker(r) for r in (18, 26)}
        self.bow = bow()
        self.glint = sparkle(34, WHITE, (255, 128, 182))
        gl = [Glyph(ch, font, round(300 * sc), st, 9, False) for ch, sc, _, _, st in MAIN]
        total = sum(g.width for g in gl) + GAP * (len(gl) - 1)
        x = W / 2 - total / 2
        self.letters = []
        for g, (ch, sc, rot, dy, _) in zip(gl, MAIN):
            self.letters.append(dict(g=g, x=x + g.width / 2, y=MAIN_Y + dy, rot=rot))
            x += g.width + GAP

    def frame(self, t):
        u = t / LOOP  # 0-1 で1周 (すべての動きを整数倍の周期にしてループさせる)
        sh = int(self.bgP * ((u * 4) % 1))
        im = self.bg.crop((self.bgP - sh, 0, self.bgP - sh + W, H)).convert("RGBA")
        # 浮かぶハート (奥)
        for j, (x, ph, r) in enumerate(((300, 0.0, 26), (1640, 0.5, 18), (180, 0.3, 18), (1760, 0.8, 26))):
            q = (u * 2 + ph) % 1
            put(im, self.hearts[r], x + 20 * math.sin(q * 6), 860 - 560 * q, hump(q) * 1.2, 15 * math.sin(q * 5))
        # 3Dのチョコハート (左右で回る)
        for x, y, s, ph, rot in ((150, 480, 0.46, 0.0, -14), (1770, 480, 0.46, 0.5, 14)):
            k = int(((u + ph) % 1) * 60) % 60
            put(im, self.heart3d[k], x, y + 16 * math.sin(2 * math.pi * (u * 2 + ph)), s, rot)
        # 上のチョコの垂れ / 下のフリル
        im.alpha_composite(self.choco)
        draw_drips(im, self.drips, u)
        fr = frill_bottom(u * 2)
        im.alpha_composite(fr, (0, H - fr.height))
        # 主役の文字: ビートで波のように跳ねる (1周期に4拍)
        for i, it in enumerate(self.letters):
            q = (u * 4 - i * 0.18) % 1
            hop = 34 * hump(q / 0.3)
            sq = 0.07 * (hump((q - 0.3) / 0.15) - 0.5 * hump(q / 0.06))
            rot = it["rot"] + 3 * math.sin(2 * math.pi * (u * 2) + i)
            pulse = 1 + 0.03 * math.exp(-((u * 4) % 1) * 6)
            shine = ((u * 2) % 1 - i * 0.06) / 0.25
            put(im, it["g"].draw(0, shine if 0 < shine < 1 else None), it["x"], it["y"] - hop, pulse, rot,
                1 + sq, 1 - sq)
            ph = (u * 2 + i * 0.27) % 1
            s2 = hump(ph / 0.3) ** 2
            if s2 > 0.05:
                gx, gy = it["g"].glint
                a = math.radians(-rot)
                put(im, self.glint, it["x"] + gx * math.cos(a) - gy * math.sin(a),
                    it["y"] - hop + gx * math.sin(a) + gy * math.cos(a), s2 * 1.3, 45 * ph)
        first = self.letters[0]
        put(im, self.bow, first["x"] - 110, first["y"] - 190 - 34 * hump(((u * 4) % 1) / 0.3), 1.1,
            16 + 6 * math.sin(2 * math.pi * u * 2))
        # ワンク4秒の札 (ふわふわ)
        put(im, self.plate, W / 2, 790 + 10 * math.sin(2 * math.pi * u * 2), 1, -3 + 2 * math.sin(2 * math.pi * u))
        return im.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Hachi Maru Pop など手書きの丸文字")
    ap.add_argument("--out", default="kote_chui.mp4")
    ap.add_argument("--length", type=float, default=3.27, help="動画の長さ (秒). 動きの1周もこの長さにする")
    ap.add_argument("--cache", default="cache3d", help="render3d の3Dチョコハートのスプライト")
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    global LOOP
    LOOP = a.length
    import render3d as R
    from multiprocessing import Pool
    with Pool() as pool:
        R.build_sprites(pool, a.cache, {"choco_heart": (520, 60)})
    sc = Scene(a.font, a.cache)
    if a.preview is not None:
        for t in a.preview:
            sc.frame(t).save(f"{os.path.splitext(a.out)[0]}_{t:.2f}.png")
        return
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    p = subprocess.Popen([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
                          str(FPS), "-i", "-", "-t", str(a.length), "-c:v", "libx264", "-crf", "16", "-pix_fmt",
                          "yuv420p", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    for i in range(math.ceil(a.length * FPS)):
        p.stdin.write(sc.frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()

if __name__ == "__main__":
    main()
