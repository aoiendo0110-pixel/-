"""縦 (9:16) の「コテ注意 / 御相手様映り込みなし」ロゴ動画をグリーンバックで書き出す.

  python3 kote_chui_vertical.py --font HachiMaruPop.ttf --out clips/text/kote_chui_vertical [--length 3.27]

画面の中央にどデカく置く前提のロゴ. モチーフはバレンタイン・チョコ・お菓子作り・お菓子.
  メイン: 「コテ」(いちごピンク) /「注意」(チョコがけ) の2段. 1文字ずつ角度・高さ違い
  サブ:   「御相手様映り込みなし」を、絞り出しクリームで縁取ったピンクのプレートに
  飾り:   チョコのついた泡立て器 (かき混ぜるように揺れる)・ボウル・3Dのチョコハート/カップケーキ/
          マカロン/クッキー/トリュフ・リボン・きらめき (どれもロゴにくっつく位置だけ)
動きは --length 秒でちょうど1周するので、繰り返し再生してもつながる。
クロマキー用に、緑系の色と半透明のぼかしは使わない (3Dも緑の入らないお菓子だけ)。
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import os
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

import render3d as R
from melodic_choco_logo import MILK, STRAWBERRY, Glyph, bow
from zettai_reido_logo import CHOCO_D, PINK_D, WHITE, heart_poly, heart_sticker, put, sparkle

W, H, FPS = 1080, 1920, 30
SPRITES = {"choco_heart": (520, 60), "cupcake": (560, 60), "macaron": (480, 60), "cookie": (300, 48),
           "truffle": (300, 48), "truffle_w": (300, 48)}
# (文字, 中心, 大きさ, 傾き, 色)
MAIN = [("コ", (330, 680), 1.0, -10, STRAWBERRY), ("テ", (740, 645), 0.95, 9, STRAWBERRY),
        ("注", (315, 1065), 1.02, -6, MILK), ("意", (765, 1090), 1.02, 7, MILK)]
FS = 400
SUB_Y = 1495
CHOCO_B = (112, 58, 38)


def hump(u):
    return math.sin(math.pi * min(max(u, 0.0), 1.0))


# ---------------------------------------------------------------- 部品
def sub_plate(font, fill=(255, 150, 196), crumb=(222, 160, 178), line=CHOCO_B):
    """「御相手様映り込みなし」: ピンクのプレート + 絞り出しクリームの縁 + チョコのステッチ."""
    f = ImageFont.truetype(font, 82)
    txt = "御相手様映り込みなし"
    tw = f.getlength(txt)
    w, h = int(tw) + 150, 190
    S = (w + 80, h + 90)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0 = 40, 40
    d.rounded_rectangle((x0 + 6, y0 + 18, x0 + w + 6, y0 + h + 18), 60, fill=CHOCO_D)  # 厚み
    d.rounded_rectangle((x0 - 12, y0 - 12, x0 + w + 12, y0 + h + 12), 70, fill=PINK_D)
    d.rounded_rectangle((x0 - 6, y0 - 6, x0 + w + 6, y0 + h + 6), 66, fill=WHITE)
    d.rounded_rectangle((x0 + 10, y0 + 10, x0 + w - 10, y0 + h - 10), 54, fill=fill)
    # 絞り出しクリームの縁 (しずく形をぐるっと)
    per = 2 * (w + h)
    n = int(per / 34)
    for k in range(n):
        s = k / n * per
        if s < w:
            x, y = x0 + s, y0
        elif s < w + h:
            x, y = x0 + w, y0 + (s - w)
        elif s < 2 * w + h:
            x, y = x0 + w - (s - w - h), y0 + h
        else:
            x, y = x0, y0 + h - (s - 2 * w - h)
        x = min(max(x, x0 + 30), x0 + w - 30)
        y = min(max(y, y0 + 4), y0 + h - 4)
        d.ellipse((x - 20, y - 20, x + 20, y + 20), fill=crumb)
        d.ellipse((x - 17, y - 19, x + 17, y + 15), fill=WHITE)
        d.ellipse((x - 9, y - 13, x - 1, y - 6), fill=(255, 236, 244))
    d.text((x0 + w / 2 + 4, y0 + h / 2 + 10), txt, font=f, anchor="mm", fill=CHOCO_D, stroke_width=11,
           stroke_fill=CHOCO_D)
    d.text((x0 + w / 2, y0 + h / 2 + 4), txt, font=f, anchor="mm", fill=WHITE, stroke_width=8, stroke_fill=line)
    for s in (-1, 1):
        cx = x0 + w / 2 + s * (w / 2 - 6)
        d.polygon(heart_poly(cx, y0 + h / 2, 30), fill=WHITE)
        d.polygon(heart_poly(cx, y0 + h / 2, 22), fill=(236, 60, 120))
    return im


def whisk(coat=CHOCO_B, coat_hi=(176, 112, 82)):
    """チョコのついた泡立て器 (持ち手が上・ワイヤーが下). ステッカー風の白フチ."""
    S = (300, 640)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = S[0] / 2
    neck, tip = 290, 600

    def wire_pts(k, v0=0.0):
        pts = []
        for i in range(41):
            v = v0 + (1 - v0) * i / 40  # 0: 首 → 1: 先
            pts.append((cx + k * 118 * math.sin(math.pi * v) ** 0.75, neck + (tip - neck) * v))
        return pts
    ks = (-1, -0.5, 0, 0.5, 1)
    for wd, col in ((26, WHITE), (16, PINK_D), (9, (236, 226, 232))):
        for k in ks:
            d.line(wire_pts(k), fill=col, width=wd, joint="curve")
        d.ellipse((cx - 30 - wd / 2, tip - 22 - wd / 2, cx + 30 + wd / 2, tip + 8 + wd / 2), fill=col)
    # 先についたチョコ (下側だけ) と垂れ
    for wd, col in ((32, WHITE), (20, coat)):
        for k in ks:
            d.line(wire_pts(k, 0.62), fill=col, width=wd, joint="curve")
        d.ellipse((cx - 44 - wd / 3, tip - 30 - wd / 3, cx + 44 + wd / 3, tip + 14 + wd / 3), fill=col)
    for x, L in ((-30, 22), (18, 36)):
        for pad, col in ((8, WHITE), (0, coat)):
            d.rounded_rectangle((cx + x - 9 - pad, tip, cx + x + 9 + pad, tip + L + pad), 9 + pad, fill=col)
            d.ellipse((cx + x - 12 - pad, tip + L - 12 - pad, cx + x + 12 + pad, tip + L + 12 + pad), fill=col)
    d.ellipse((cx - 70, tip - 70, cx - 52, tip - 52), fill=coat_hi)
    # 持ち手 (ピンク)
    for pad, col in ((12, WHITE), (6, PINK_D), (0, (255, 150, 196))):
        d.rounded_rectangle((cx - 24 - pad, 20 - pad, cx + 24 + pad, neck + 12 + pad), 24 + pad, fill=col)
    d.rectangle((cx - 13, 50, cx - 5, neck - 20), fill=(255, 210, 228))
    d.ellipse((cx - 10, 32, cx + 10, 52), fill=WHITE)
    return im


def bowl(content=CHOCO_B, content_hi=(170, 108, 78)):
    """チョコの入ったピンクのボウル."""
    S = (360, 250)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = S[0] / 2
    for pad, col in ((14, WHITE), (6, PINK_D), (0, (255, 160, 200))):
        d.chord((cx - 160 - pad, -20 - pad, cx + 160 + pad, 220 + pad), 0, 180, fill=col)
        d.ellipse((cx - 166 - pad, 70 - pad, cx + 166 + pad, 130 + pad), fill=col)
    d.ellipse((cx - 150, 78, cx + 150, 122), fill=content)
    d.ellipse((cx - 120, 84, cx - 40, 98), fill=content_hi)
    for x in range(int(cx - 120), int(cx + 130), 40):  # ドット柄
        d.ellipse((x - 8, 160, x + 8, 176), fill=WHITE)
    return im


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, cache, L):
        self.L = L
        self.letters = [dict(g=Glyph(ch, font, round(FS * sc), st, 10, False), x=x, y=y, rot=rot)
                        for ch, (x, y), sc, rot, st in MAIN]
        self.sub = sub_plate(font)
        self.whisk, self.bowl, self.bow = whisk(), bowl(), bow()
        self.glint = sparkle(36, WHITE, (255, 128, 182))
        self.hearts = {r: heart_sticker(r) for r in (18, 26, 34)}
        self.spr = {name: [Image.open(os.path.join(cache, f"{name}_{size}_{i:02d}.png")).convert("RGBA")
                           for i in range(n)] for name, (size, n) in SPRITES.items()}

    def sprite(self, name, rev):
        seq = self.spr[name]
        return seq[int(math.floor(rev * len(seq))) % len(seq)]

    def frame(self, t):
        u = t / self.L  # 0-1 で1周. 動きはすべて整数回の周期
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        beat = (u * 4) % 1
        pulse = 1 + 0.025 * math.exp(-beat * 6)

        # 後ろ: ボウルと泡立て器 (「テ」の右上でかき混ぜる)
        stir = 14 * math.sin(2 * math.pi * u * 4)
        put(im, self.whisk, 865, 250 + 6 * math.sin(2 * math.pi * u * 4 + 1), 0.72, -8 + stir)
        put(im, self.bowl, 880, 485, 0.82, 6 + 2 * math.sin(2 * math.pi * u * 2))
        # 浮かぶハート (奥・ロゴのまわりだけ)
        for x, ph, r in ((120, 0.0, 26), (980, 0.5, 18), (90, 0.35, 18), (1000, 0.8, 34)):
            q = (u * 2 + ph) % 1
            put(im, self.hearts[r], x + 18 * math.sin(q * 6), 1300 - 700 * q, hump(q) * 1.1, 15 * math.sin(q * 5))

        # メインの文字 (ビートで波のように跳ねる)
        for i, it in enumerate(self.letters):
            q = (u * 4 - i * 0.16) % 1
            hop = 30 * hump(q / 0.3)
            sq = 0.06 * (hump((q - 0.3) / 0.15) - 0.5 * hump(q / 0.06))
            rot = it["rot"] + 3 * math.sin(2 * math.pi * u * 2 + i)
            sh = ((u * 2) % 1 - i * 0.07) / 0.25
            put(im, it["g"].draw(0, sh if 0 < sh < 1 else None), it["x"], it["y"] - hop, pulse, rot, 1 + sq, 1 - sq)
            ph = (u * 2 + i * 0.27) % 1
            s2 = hump(ph / 0.3) ** 2
            if s2 > 0.05:
                gx, gy = it["g"].glint
                a = math.radians(-rot)
                put(im, self.glint, it["x"] + gx * math.cos(a) - gy * math.sin(a),
                    it["y"] - hop + gx * math.sin(a) + gy * math.cos(a), s2 * 1.3, 45 * ph)
        # 「コ」の上のリボン
        c = self.letters[0]
        q = (u * 4) % 1
        put(im, self.bow, c["x"] - 120, c["y"] - 235 - 30 * hump(q / 0.3), 1.15, 18 + 6 * math.sin(2 * math.pi * u * 2))

        # 3Dのお菓子 (ロゴの角にくっつける)
        put(im, self.sprite("choco_heart", u), 150, 255 + 14 * math.sin(2 * math.pi * u * 2), 0.42, -16)
        put(im, self.sprite("macaron", u), 975, 900 + 14 * math.sin(2 * math.pi * u * 2 + 2), 0.36, 14)
        put(im, self.sprite("truffle", u * 2), 110, 1290 + 12 * math.sin(2 * math.pi * u * 2 + 1), 0.6, -8)

        # サブ文字のプレート
        put(im, self.sub, W / 2, SUB_Y + 8 * math.sin(2 * math.pi * u * 2), 1, -2 + 1.5 * math.sin(2 * math.pi * u))
        # プレートの下: カップケーキ・クッキー・トリュフ (並んでぴょこぴょこ)
        for j, (name, x, s, rv) in enumerate((("cookie", 250, 0.75, 1), ("cupcake", 540, 0.5, 1),
                                              ("truffle_w", 830, 0.6, 2))):
            q = (u * 4 - j * 0.2) % 1
            put(im, self.sprite(name, u * rv), x, 1720 - 26 * hump(q / 0.3), s, 8 * math.sin(2 * math.pi * u * 2 + j))
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
    ap.add_argument("--out", default="kote_chui_vertical")
    ap.add_argument("--length", type=float, default=3.27, help="動画の長さ (秒). 動きの1周もこの長さ")
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    with Pool(a.jobs) as pool:
        R.build_sprites(pool, a.cache, SPRITES)
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
