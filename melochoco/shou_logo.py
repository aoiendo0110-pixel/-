"""「星導ショウ」の文字だけのロゴ動画 (16:9・グリーンバック).

  python3 shou_logo.py --font HachiMaruPop.ttf --out clips/text/shou_logo [--length 3.27]

飾りは置かず、文字そのもので見せる (手書きの丸文字を太らせ、ステッチ・ツヤ・深い厚み・白フチ + ピンクの外フチ).
  「星導」= いちごピンク / 「ショウ」= ミルクチョコにビターチョコがけ
  1文字ずつ大きさ・角度・高さを変え、ビートで波のように跳ねる / ツヤの光が走る / 角がキラッ
動きは --length 秒でちょうど1周するので、繰り返し再生してもつながる。
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import os
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
from PIL import Image

from melodic_choco_logo import MILK, STRAWBERRY, Glyph
from zettai_reido_logo import WHITE, put, sparkle

W, H, FPS = 1920, 1080, 30
FS = 380
GAP = -22
# (文字, 大きさ, 傾き, 上下のずれ, 色, 太らせる量). 画数の多い「導」は太らせすぎると線がつぶれる
TEXT = [("星", 1.0, -9, -10, STRAWBERRY, 9), ("導", 1.08, 6, -30, STRAWBERRY, 3),
        ("シ", 0.9, -8, 24, MILK, 10), ("ョ", 0.58, 12, 92, MILK, 10), ("ウ", 0.96, 8, 6, MILK, 10)]
BASE_Y = 540


def hump(u):
    return math.sin(math.pi * min(max(u, 0.0), 1.0))


class Scene:
    def __init__(self, font, L):
        self.L = L
        gl = [Glyph(ch, font, round(FS * sc), st, fat, False) for ch, sc, _, _, st, fat in TEXT]
        total = sum(g.width for g in gl) + GAP * (len(gl) - 1)
        x = W / 2 - total / 2
        self.letters = []
        for g, (ch, sc, rot, dy, _, _) in zip(gl, TEXT):
            self.letters.append(dict(g=g, x=x + g.width / 2, y=BASE_Y + dy, rot=rot))
            x += g.width + GAP
        self.glint = sparkle(40, WHITE, (255, 128, 182))
        self.glint_s = sparkle(24, WHITE, (255, 128, 182))

    def frame(self, t):
        u = t / self.L  # 0-1 で1周
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pulse = 1 + 0.03 * math.exp(-((u * 4) % 1) * 6)  # 拍ごとにドンッ
        n = len(self.letters)
        for i, it in enumerate(self.letters):
            q = (u * 4 - i / n * 0.8) % 1
            hop = 36 * hump(q / 0.28)
            sq = 0.07 * (hump((q - 0.28) / 0.14) - 0.5 * hump(q / 0.06))
            rot = it["rot"] + 3 * math.sin(2 * math.pi * u * 2 + i * 1.3)
            sh = ((u * 2) % 1 - it["x"] / W * 0.35) / 0.22
            g = it["g"].draw(0, sh if 0 < sh < 1 else None)
            put(im, g, it["x"], it["y"] - hop, pulse, rot, 1 + sq, 1 - sq)
            for k, (spr, ph0) in enumerate(((self.glint, 0.0), (self.glint_s, 0.5))):
                ph = (u * 2 + i * 0.29 + ph0) % 1
                s2 = hump(ph / 0.3) ** 2
                if s2 < 0.05:
                    continue
                gx, gy = it["g"].glint
                if k:  # 小さい方は左下の角
                    gx, gy = -gx * 0.8, -gy * 0.6
                a = math.radians(-rot)
                put(im, spr, it["x"] + gx * math.cos(a) - gy * math.sin(a),
                    it["y"] - hop + gx * math.sin(a) + gy * math.cos(a), s2 * 1.3, 45 * ph)
        return im


SCENE = None


def _init(font, L):
    global SCENE
    SCENE = Scene(font, L)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Hachi Maru Pop など手書きの丸文字")
    ap.add_argument("--out", default="shou_logo")
    ap.add_argument("--length", type=float, default=3.27, help="動画の長さ (秒). 動きの1周もこの長さ")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    if a.preview is not None:
        _init(a.font, a.length)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = math.ceil(a.length * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.length)) as pool:
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
