"""「街はバレンタイン」のロゴ動画 (16:9・グリーンバック).

  python3 machi_valentine.py --font HachiMaruPop.ttf --out clips/text/machi_valentine [--length 3.27] [--cache cache3d]

  文字:  「街は」= クリーム色 (ピンクのステッチ) を左上に小さめ、「バレンタイン」= いちごピンクとミルクチョコを交互に、
         画面いっぱいに. 手書きの丸文字を太らせ、ステッチ・ツヤ・深い厚み・白フチ + ピンクの外フチ
  上:    ハートの旗飾り (ガーランド) が2本、ゆらゆら
  下:    チョコといちごのお菓子の家が並ぶ街並み (屋根にアイシングが垂れ、ハートの窓の灯りがまたたく、
         煙突からハートの煙)
  まわり: 浮かぶハート・3Dのチョコハート・きらめき
動きは --length 秒でちょうど1周するので、繰り返し再生してもつながる。緑系の色は使わない。
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import os
import random
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
from PIL import Image, ImageDraw

import render3d as R
from melodic_choco_logo import MILK, STRAWBERRY, Glyph, bow
from zettai_reido_logo import CHOCO_D, PINK_D, PINK_L, WHITE, heart_poly, heart_sticker, put, sparkle

W, H, FPS = 1920, 1080, 30
CREAMY = dict(top=(255, 252, 248), bot=(255, 218, 232), stitch=(255, 128, 182), ext=(150, 30, 80), ring=CHOCO_D)
FS = 290
GAP = -20
# (文字, 大きさ, 傾き, 上下のずれ, 色, 太らせる量)
LINE2 = [("バ", 1.0, -8, 0, STRAWBERRY, 9), ("レ", 0.92, 7, -20, MILK, 10), ("ン", 0.88, -6, 18, STRAWBERRY, 10),
         ("タ", 1.0, 8, -12, MILK, 10), ("イ", 0.95, -7, 10, STRAWBERRY, 10), ("ン", 0.9, 9, -16, MILK, 10)]
LINE1 = [("街", 0.62, -10, 0, CREAMY, 4), ("は", 0.56, 8, 12, CREAMY, 8)]
LINE2_Y, LINE1_POS = 560, (470, 300)

ROOF = [(112, 58, 38), (236, 76, 138), (255, 150, 196), (150, 90, 60)]
WALL = [(255, 236, 228), (255, 214, 230), (226, 170, 128), (255, 246, 236)]
LIGHT = (255, 232, 150)


def hump(u):
    return math.sin(math.pi * min(max(u, 0.0), 1.0))


# ---------------------------------------------------------------- 街並み
def house(w, h, roof_kind, wall, roof, seed):
    """お菓子の家1軒 (ステッカー風). 窓と煙突の位置は frame で灯りや煙を描くので返す."""
    rnd = random.Random(seed)
    rh = int(w * (0.7 if roof_kind == "tri" else 0.5))
    S = (w + 60, h + rh + 60)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = 30, 30 + rh
    body = (x0, y0, x0 + w, y0 + h)
    for pad, col in ((14, WHITE), (7, CHOCO_D)):
        d.rounded_rectangle((body[0] - pad, body[1] - pad, body[2] + pad, body[3] + pad), 18, fill=col)
        if roof_kind == "tri":
            d.polygon([(x0 - 22 - pad, y0 + 6), (x0 + w / 2, 30 - pad * 1.3), (x0 + w + 22 + pad, y0 + 6)], fill=col)
        else:
            d.pieslice((x0 - 14 - pad, 30 + rh * 0.1 - pad, x0 + w + 14 + pad, y0 + rh * 0.9 + pad), 180, 360,
                       fill=col)
    d.rounded_rectangle(body, 14, fill=wall)
    for yy in range(body[1] + 26, body[3], 34):  # 壁のドット
        for xx in range(body[0] + 20 + (17 if (yy // 34) % 2 else 0), body[2] - 10, 34):
            d.ellipse((xx - 4, yy - 4, xx + 4, yy + 4), fill=PINK_L)
    if roof_kind == "tri":
        d.polygon([(x0 - 22, y0 + 6), (x0 + w / 2, 30), (x0 + w + 22, y0 + 6)], fill=roof)
    else:
        d.pieslice((x0 - 14, 30 + rh * 0.1, x0 + w + 14, y0 + rh * 0.9), 180, 360, fill=roof)
    # 屋根の縁からアイシングが垂れる
    ey = y0 + 6
    d.rectangle((x0 - 20, ey - 10, x0 + w + 20, ey + 6), fill=WHITE)
    x = x0 - 14
    while x < x0 + w + 14:
        L = rnd.uniform(10, 34)
        d.rounded_rectangle((x - 9, ey - 4, x + 9, ey + L), 9, fill=WHITE)
        x += rnd.uniform(22, 34)
    # ドア
    dw, dh = w * 0.26, h * 0.42
    dx = x0 + w * rnd.choice((0.28, 0.5, 0.72)) - dw / 2
    d.rounded_rectangle((dx - 6, body[3] - dh - 6, dx + dw + 6, body[3] + 2), 16, fill=CHOCO_D)
    d.rounded_rectangle((dx, body[3] - dh, dx + dw, body[3]), 12, fill=(150, 90, 60))
    d.polygon(heart_poly(dx + dw / 2, body[3] - dh * 0.62, dw * 0.22), fill=PINK_L)
    # 窓 (ハート形). 灯りは frame で
    wins = []
    for k in range(rnd.choice((1, 2))):
        wx = x0 + w * (0.25 + 0.5 * k) if dx > x0 + w * 0.4 or k else x0 + w * 0.72
        wy = body[1] + h * 0.3
        r = min(w * 0.13, 28)
        d.polygon(heart_poly(wx, wy, r + 6), fill=CHOCO_D)
        d.polygon(heart_poly(wx, wy, r), fill=(150, 90, 70))
        wins.append((wx, wy, r))
    chim = None
    if roof_kind == "tri" and rnd.random() < 0.7:  # 煙突
        cx = x0 + w * 0.72
        cy = 30 + rh * 0.45
        for pad, col in ((10, WHITE), (5, CHOCO_D), (0, (236, 76, 138))):
            d.rectangle((cx - 16 - pad, cy - 40 - pad, cx + 16 + pad, cy + 10), fill=col)
        chim = (cx, cy - 50)
    return im, wins, chim


class Town:
    def __init__(self, seed=3):
        rnd = random.Random(seed)
        self.houses = []
        x = -40
        k = 0
        while x < W + 40:
            w = rnd.randint(150, 230)
            h = rnd.randint(110, 200)
            im, wins, chim = house(w, h, rnd.choice(("tri", "tri", "dome")), WALL[k % 4], ROOF[(k * 3) % 4], k)
            self.houses.append(dict(im=im, x=x + im.width / 2, y=H + 30 - im.height / 2 + rnd.randint(0, 40),
                                    wins=wins, chim=chim, ph=rnd.random()))
            x += w + rnd.randint(10, 40)
            k += 1


# ---------------------------------------------------------------- 上のガーランド
def flag(col):
    S = 110
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    d.polygon(heart_poly(c, c + 4, 40), fill=WHITE)
    d.polygon(heart_poly(c, c + 4, 34), fill=CHOCO_D)
    d.polygon(heart_poly(c, c + 4, 30), fill=col)
    d.ellipse((c - 18, c - 10, c - 6, c), fill=WHITE)
    return im


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, cache, L):
        self.L = L
        gl = [Glyph(ch, font, round(FS * sc), st, fat, False) for ch, sc, _, _, st, fat in LINE2]
        total = sum(g.width for g in gl) + GAP * (len(gl) - 1)
        x = W / 2 - total / 2
        self.letters = []
        for g, (ch, sc, rot, dy, _, _) in zip(gl, LINE2):
            self.letters.append(dict(g=g, x=x + g.width / 2, y=LINE2_Y + dy, rot=rot))
            x += g.width + GAP
        x0, y0 = LINE1_POS
        for j, (ch, sc, rot, dy, st, fat) in enumerate(LINE1):
            g = Glyph(ch, font, round(FS * sc), st, fat, False)
            self.letters.insert(j, dict(g=g, x=x0 + j * 215, y=y0 + dy, rot=rot))
        self.town = Town()
        self.bow = bow()
        self.flags = [flag(c) for c in ((255, 128, 182), (255, 236, 244), (236, 60, 120), (166, 98, 66))]
        self.hearts = {r: heart_sticker(r) for r in (16, 22, 30)}
        self.glint = sparkle(36, WHITE, (255, 128, 182))
        self.sp = sparkle(22, WHITE, (255, 128, 182))
        self.heart3d = [Image.open(os.path.join(cache, f"choco_heart_520_{i:02d}.png")).convert("RGBA")
                        for i in range(60)]

    def garland(self, im, u, y0, sag, ph, off):
        """左右の端から垂れ下がる紐に、ハートの旗."""
        d = ImageDraw.Draw(im)
        sw = 10 * math.sin(2 * math.pi * (u * 2 + ph))
        pts = [(x, y0 + sag * (1 - ((x - W / 2) / (W / 2)) ** 2) + sw * math.sin(math.pi * x / W))
               for x in range(-20, W + 21, 20)]
        d.line(pts, fill=WHITE, width=10)
        d.line(pts, fill=PINK_D, width=5)
        for k, x in enumerate(range(60 + off, W, 130)):
            y = y0 + sag * (1 - ((x - W / 2) / (W / 2)) ** 2) + sw * math.sin(math.pi * x / W)
            put(im, self.flags[k % 4], x, y + 42, 1, 6 * math.sin(2 * math.pi * (u * 2 + k * 0.17 + ph)))

    def frame(self, t):
        u = t / self.L  # 0-1 で1周
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        s2pi = lambda k, ph=0.0: math.sin(2 * math.pi * u * k + ph)
        pulse = 1 + 0.03 * math.exp(-((u * 4) % 1) * 6)

        # 上のガーランド 2本
        self.garland(im, u, -10, 120, 0.0, 0)
        self.garland(im, u, -40, 70, 0.4, 65)
        # 浮かぶハート (街から空へ)
        for j, (x, ph, r) in enumerate(((180, 0.0, 22), (520, 0.3, 16), (1420, 0.55, 30), (1760, 0.8, 22),
                                        (980, 0.15, 16), (1180, 0.7, 22))):
            q = (u * 2 + ph) % 1
            put(im, self.hearts[r], x + 22 * math.sin(q * 6 + j), 820 - 560 * q, hump(q) * 1.2, 15 * math.sin(q * 5))
        # 3Dのチョコハート (左右の空で回る)
        for x, y, ph, rot in ((150, 330, 0.0, -16), (1770, 360, 0.5, 14)):
            k = int(((u + ph) % 1) * 60) % 60
            put(im, self.heart3d[k], x, y + 16 * s2pi(2, ph * 6), 0.42, rot)

        # 街並み (下)
        for i, hs in enumerate(self.town.houses):
            bob = 4 * hump(((u * 4 - i * 0.12) % 1) / 0.25)  # 家も拍に合わせてちょっと弾む
            put(im, hs["im"], hs["x"], hs["y"] - bob, 1, 0)
            d = ImageDraw.Draw(im)
            left = hs["x"] - hs["im"].width / 2
            top = hs["y"] - bob - hs["im"].height / 2
            for j, (wx, wy, r) in enumerate(hs["wins"]):  # 窓の灯りがまたたく
                on = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(2 * math.pi * (u * 2 + hs["ph"] + j * 0.3)))
                col = tuple(int(150 + (c - 150) * on) for c in LIGHT)
                d.polygon(heart_poly(left + wx, top + wy, r), fill=col)
                d.ellipse((left + wx - r * 0.45, top + wy - r * 0.5, left + wx - r * 0.1, top + wy - r * 0.2),
                          fill=WHITE)
            if hs["chim"]:  # 煙突からハートの煙
                cx, cy = hs["chim"]
                for k in range(2):
                    q = (u * 2 + hs["ph"] + k * 0.5) % 1
                    put(im, self.hearts[16], left + cx + 18 * math.sin(q * 5), top + cy - 140 * q, hump(q) * 1.1,
                        10 * math.sin(q * 4))

        # 文字
        n = len(self.letters)
        for i, it in enumerate(self.letters):
            q = (u * 4 - i / n * 0.8) % 1
            hop = 32 * hump(q / 0.28)
            sq = 0.07 * (hump((q - 0.28) / 0.14) - 0.5 * hump(q / 0.06))
            rot = it["rot"] + 3 * s2pi(2, i * 1.3)
            sh = ((u * 2) % 1 - it["x"] / W * 0.35) / 0.22
            put(im, it["g"].draw(0, sh if 0 < sh < 1 else None), it["x"], it["y"] - hop, pulse, rot, 1 + sq, 1 - sq)
            ph = (u * 2 + i * 0.29) % 1
            s2 = hump(ph / 0.3) ** 2
            if s2 > 0.05:
                gx, gy = it["g"].glint
                a = math.radians(-rot)
                put(im, self.glint, it["x"] + gx * math.cos(a) - gy * math.sin(a),
                    it["y"] - hop + gx * math.sin(a) + gy * math.cos(a), s2 * 1.3, 45 * ph)
        m = self.letters[0]  # 「街」の左上にリボン
        put(im, self.bow, m["x"] - 100, m["y"] - 130 - 32 * hump(((u * 4) % 1) / 0.28), 0.85, -16 + 5 * s2pi(2))
        # 空のきらめき
        for j, (x, y) in enumerate(((760, 250), (1180, 230), (1560, 600), (260, 640), (1000, 780), (1660, 200))):
            q = (u * 2 + j * 0.23) % 1
            put(im, self.sp, x, y, hump(q / 0.4) ** 2 * 1.3, 45 * q)
        return im


SCENE = None


def _init(font, cache, L):
    global SCENE
    SCENE = Scene(font, cache, L)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Hachi Maru Pop など手書きの丸文字")
    ap.add_argument("--out", default="machi_valentine")
    ap.add_argument("--length", type=float, default=3.27, help="動画の長さ (秒). 動きの1周もこの長さ")
    ap.add_argument("--cache", default="cache3d", help="render3d の3Dチョコハートのスプライト")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    with Pool(a.jobs) as pool:
        R.build_sprites(pool, a.cache, {"choco_heart": (520, 60)})
    if a.preview is not None:
        _init(a.font, a.cache, a.length)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = math.ceil(a.length * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.cache, a.length)) as pool:
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
