"""「コテ注意 / ワンク4秒」の注意画面動画 (16:9) を書き出す.

  python3 kote_chui.py --font HachiMaruPop.ttf --out clips/text/kote_chui.mp4 [--length 207]

4秒でつながるループを1回だけ描き、ffmpeg で --length 秒 (既定 3:27) までつなげる。
  背景: ピンクの斜めストライプが流れ、上下に「CAUTION ♡」の注意テープが流れる
  主役: 「コテ注意」を画面いっぱいに (1文字ずつ角度・高さ違い、ビートで波のように跳ねる)
  下:   「ワンク4秒」のリボン札
"""
import argparse
import math
import os
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from melodic_choco_logo import Glyph, bow
from zettai_reido_logo import CHOCO_D, PINK_D, WHITE, put, sparkle

W, H, FPS, LOOP = 1920, 1080, 30, 4.0
RED = dict(top=(255, 120, 170), bot=(226, 40, 104), stitch=WHITE, ext=(120, 16, 56), ring=CHOCO_D)
PINK = dict(top=(255, 200, 226), bot=(250, 130, 182), stitch=WHITE, ext=(150, 30, 80), ring=CHOCO_D)
# (文字, 大きさ, 傾き, 上下のずれ, 色)
MAIN = [("コ", 1.0, -10, 10, PINK), ("テ", 0.95, 8, -18, PINK), ("注", 1.12, -6, 6, RED), ("意", 1.12, 7, -10, RED)]
MAIN_Y, GAP = 455, -16


def hump(u):
    return math.sin(math.pi * min(max(u, 0.0), 1.0))


def background():
    """ピンクの斜めストライプ (1周期ぶん横に長く描いて、ずらして使う)."""
    P = 120
    yy, xx = np.mgrid[0:H, 0:W + P]
    s = ((xx + yy) // (P // 2)) % 2
    arr = np.zeros((H, W + P, 3), np.uint8)
    arr[s == 0] = (255, 214, 230)
    arr[s == 1] = (255, 236, 244)
    im = Image.fromarray(arr)
    d = ImageDraw.Draw(im)
    for y in range(0, H, 90):  # 白い水玉
        for x in range(0, W + P, 90):
            ox = 45 if (y // 90) % 2 else 0
            d.ellipse((x + ox - 7, y - 7, x + ox + 7, y + 7), fill=WHITE)
    return im, P


def tape(font, text="CAUTION ♡ コテ注意 ♡ "):
    """注意テープ (ピンクと白の斜め縞 + 文字). 横に1周期ぶん長い."""
    f = ImageFont.truetype(font, 54)
    unit = int(f.getlength(text)) + 40
    L = unit * (W // unit + 2)
    h = 96
    im = Image.new("RGB", (L, h), (40, 20, 24))
    d = ImageDraw.Draw(im)
    for x in range(-h, L + h, 48):
        d.polygon([(x, 8), (x + 24, 8), (x + 24 - (h - 16), h - 8), (x - (h - 16), h - 8)], fill=(255, 128, 182))
    d.rectangle((0, 8, L, h - 8), outline=WHITE, width=4)
    d.rectangle((0, 24, L, h - 24), fill=WHITE)
    x = 20
    while x < L:
        d.text((x, h / 2 + 2), text, font=f, anchor="lm", fill=PINK_D, stroke_width=3, stroke_fill=WHITE)
        x += unit
    return im, unit


def plate(font):
    """「ワンク4秒」の札."""
    f = ImageFont.truetype(font, 96)
    txt = "ワンク4秒"
    w = int(f.getlength(txt)) + 140
    h = 170
    im = Image.new("RGBA", (w + 30, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 26, w + 20, h + 30), 80, fill=CHOCO_D)
    d.rounded_rectangle((4, 6, w + 26, h + 18), 86, fill=PINK_D)
    d.rounded_rectangle((12, 14, w + 18, h + 10), 78, fill=WHITE)
    d.rounded_rectangle((26, 28, w + 4, h - 4), 66, fill=(255, 150, 196))
    for x in range(60, w - 30, 22):  # ステッチ
        d.rectangle((x, 40, x + 11, 44), fill=WHITE)
        d.rectangle((x, h - 20, x + 11, h - 16), fill=WHITE)
    d.text((w / 2 + 15, h / 2 + 10), txt, font=f, anchor="mm", fill=WHITE, stroke_width=10, stroke_fill=CHOCO_D)
    return im


class Scene:
    def __init__(self, font):
        self.bg, self.bgP = background()
        self.tape, self.tapeU = tape(font)
        self.plate = plate(font)
        self.bow = bow()
        self.glint = sparkle(34, WHITE, (255, 128, 182))
        gl = [Glyph(ch, font, round(330 * sc), st, 9, False) for ch, sc, _, _, st in MAIN]
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
        # 注意テープ (上は右へ、下は左へ流れる)
        o = int(self.tapeU * ((u * 2) % 1))
        top = self.tape.crop((self.tapeU - o, 0, self.tapeU - o + W, self.tape.height))
        bot = self.tape.crop((o, 0, o + W, self.tape.height))
        im.paste(top, (0, 40))
        im.paste(bot, (0, H - 136))
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
        put(im, self.plate, W / 2, 835 + 10 * math.sin(2 * math.pi * u * 2), 1, -3 + 2 * math.sin(2 * math.pi * u))
        return im.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Hachi Maru Pop など手書きの丸文字")
    ap.add_argument("--out", default="kote_chui.mp4")
    ap.add_argument("--length", type=float, default=207, help="動画の長さ (秒). 既定 3:27")
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    sc = Scene(a.font)
    if a.preview is not None:
        for t in a.preview:
            sc.frame(t).save(f"{os.path.splitext(a.out)[0]}_{t:.2f}.png")
        return
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    loop = os.path.splitext(a.out)[0] + "_loop.mp4"
    p = subprocess.Popen([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r",
                          str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", loop],
                         stdin=subprocess.PIPE)
    for i in range(round(LOOP * FPS)):
        p.stdin.write(sc.frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()
    subprocess.run([ff, "-y", "-v", "error", "-stream_loop", "-1", "-i", loop, "-t", str(a.length), "-c", "copy",
                    "-movflags", "+faststart", a.out], check=True)
    os.remove(loop)


if __name__ == "__main__":
    main()
