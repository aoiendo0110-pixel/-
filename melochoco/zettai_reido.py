"""「絶対零度」の動く文字 (かわいい氷テイスト) をグリーンバックで書き出す.

  python3 zettai_reido.py --font MochiyPopOne.ttf --out clips/zettai_reido

- 1文字ずつ上からぽよんと落ちてきて、着地するとつららが伸びる
- 「−273.15°C」の札が出たあとは、文字がゆらゆら揺れ、雪の結晶とキラキラが舞い、ツヤが横切る
- クロマキーで抜きやすいよう、緑系の色と半透明のぼかしは使わない (縁はアンチエイリアスのみ)
出力: <out>_greenback.mp4 (緑 0,255,0) / <out>.webm (背景透過) / <out>.png (確認用)
"""
import argparse
import math
import random
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1600, 760, 30, 5.0
TEXT = "絶対零度"
FS = 290  # 文字の大きさ
GAP = 330  # 文字の間隔
BASE_Y = 300  # 文字の中心の高さ

WHITE = (255, 255, 255)
EDGE = (92, 132, 230)  # 内側のフチ (氷の青)
SHADOW = (70, 96, 196)
TOP, BOTTOM = (178, 236, 255), (196, 168, 255)  # 水色 → ラベンダー
PINK = (255, 138, 196)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out_back(x, s=2.2):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


# ---------------------------------------------------------------- 文字のスプライト
def glyph(ch, font):
    """1文字ぶんの (本体RGBA, ツヤ用の文字マスク). 白フチ + 青フチ + 影 + グラデ + ツヤ."""
    S = int(FS * 1.7)
    def mask(stroke):
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).text((S / 2, S / 2), ch, font=font, anchor="mm", fill=255,
                               stroke_width=stroke, stroke_fill=255)
        return m
    m_fill, m_edge, m_white = mask(0), mask(9), mask(24)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # 影 (下にずらした濃い青。半透明にしない)
    sh = Image.new("RGBA", (S, S), SHADOW + (255,))
    im.paste(sh, (0, 14), m_white)
    im.paste(Image.new("RGBA", (S, S), WHITE + (255,)), (0, 0), m_white)
    im.paste(Image.new("RGBA", (S, S), EDGE + (255,)), (0, 0), m_edge)
    # 縦グラデの本体
    bb = m_fill.getbbox()
    g = np.zeros((S, S, 4), np.uint8)
    yy = np.clip((np.arange(S) - bb[1]) / max(1, bb[3] - bb[1]), 0, 1)[:, None]
    for c in range(3):
        g[..., c] = (TOP[c] * (1 - yy) + BOTTOM[c] * yy).astype(np.uint8)
    g[..., 3] = 255
    im.paste(Image.fromarray(g, "RGBA"), (0, 0), m_fill)
    # 上半分のツヤ (文字の形を少し内側に寄せて、上だけ白っぽく)
    a = np.array(m_fill).astype(np.float32) / 255
    inner = np.minimum(a, np.roll(a, 7, 0)) * np.minimum(np.roll(a, 5, 1), np.roll(a, -5, 1))
    top = (np.arange(S)[:, None] < bb[1] + (bb[3] - bb[1]) * 0.42).astype(np.float32)
    hl = (inner * top * 0.55 * 255).astype(np.uint8)
    im.paste(Image.new("RGBA", (S, S), WHITE + (255,)), (0, 0), Image.fromarray(hl))
    return im, m_fill, bb


def icicle(length, w=46):
    """丸い先のつらら (白フチつき)."""
    S = (w + 16, int(length) + 20)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    if length < 4:
        return im
    d = ImageDraw.Draw(im)
    cx = S[0] / 2
    def shape(pad, col):
        r = max(2, w / 2 * 0.28 - pad * 0.1)
        pts = [(cx - w / 2 - pad, 4 - pad), (cx + w / 2 + pad, 4 - pad), (cx + r, length - r), (cx - r, length - r)]
        d.polygon(pts, fill=col)
        d.ellipse((cx - r - pad * 0.6, length - 2 * r - pad * 0.3, cx + r + pad * 0.6, length + pad * 0.6), fill=col)
    shape(6, WHITE)
    shape(0, (205, 238, 255))
    d.line([(cx - w * 0.18, 10), (cx - 2, length * 0.65)], fill=WHITE, width=4)
    return im


def snowflake(r, col=WHITE, edge=EDGE):
    S = int(r * 2 + 16)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    for width, color in ((max(4, r * 0.28), edge), (max(2, r * 0.14), col)):
        for k in range(6):
            a = math.pi / 3 * k
            ex, ey = c + r * math.cos(a), c + r * math.sin(a)
            d.line([(c, c), (ex, ey)], fill=color, width=round(width))
            for f in (0.55,):  # 枝
                bx, by = c + r * f * math.cos(a), c + r * f * math.sin(a)
                for s in (-1, 1):
                    b = a + s * 0.75
                    d.line([(bx, by), (bx + r * 0.32 * math.cos(b), by + r * 0.32 * math.sin(b))], fill=color,
                           width=round(width))
        d.ellipse((c - width, c - width, c + width, c + width), fill=color)
    return im


def sparkle(r, col=WHITE):
    """4本のとげのキラキラ (青フチ)."""
    S = int(r * 2 + 12)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = S / 2
    for pad, color in ((4, EDGE), (0, col)):
        R, q = r + pad, r * 0.22 + pad
        d.polygon([(c, c - R), (c + q, c - q), (c + R, c), (c + q, c + q), (c, c + R), (c - q, c + q), (c - R, c),
                   (c - q, c - q)], fill=color)
    return im


def tag(font):
    """「−273.15°C」の札 (ピンクの角丸 + 白フチ)."""
    txt = "−273.15°C"
    f = ImageFont.truetype(font, 64)
    bb = f.getbbox(txt)
    w, h = bb[2] - bb[0] + 80, 104
    im = Image.new("RGBA", (w + 20, h + 26), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 12, w + 16, h + 22), 52, fill=SHADOW)
    d.rounded_rectangle((4, 4, w + 16, h + 14), 52, fill=WHITE)
    d.rounded_rectangle((14, 14, w + 6, h + 4), 44, fill=PINK)
    d.text((w / 2 + 10, h / 2 + 9), txt, font=f, anchor="mm", fill=WHITE, stroke_width=6, stroke_fill=(222, 80, 150))
    return im


# ---------------------------------------------------------------- 1コマ
class Scene:
    def __init__(self, font):
        f = ImageFont.truetype(font, FS)
        self.g = [glyph(c, f) for c in TEXT]
        self.tag = tag(font)
        self.flakes = {r: snowflake(r) for r in (22, 32, 44)}
        self.sparks = {r: sparkle(r, c) for r, c in ((20, WHITE), (30, WHITE), (40, WHITE), (26, PINK))}
        rnd = random.Random(5)
        self.snow = [dict(x=rnd.uniform(40, W - 40), y0=rnd.uniform(0, H), r=rnd.choice((22, 32, 44)),
                          v=rnd.uniform(40, 90), ph=rnd.random(), rot=rnd.uniform(-60, 60)) for _ in range(16)]
        self.spark_pos = [(rnd.uniform(90, W - 90), rnd.uniform(60, 600), rnd.choice((20, 30, 40, 26)), rnd.random())
                          for _ in range(12)]
        self.x0 = W / 2 - GAP * (len(TEXT) - 1) / 2

    @staticmethod
    def put(dst, im, cx, cy, sx=1.0, sy=1.0, rot=0.0, anchor=(0.5, 0.5)):
        w, h = max(1, round(im.width * sx)), max(1, round(im.height * sy))
        q = im.resize((w, h), Image.LANCZOS) if (w, h) != im.size else im
        if rot:
            q = q.rotate(rot, Image.BICUBIC, expand=True)
        x, y = round(cx - q.width * anchor[0]), round(cy - q.height * anchor[1])
        l, t = max(0, -x), max(0, -y)
        r, b = min(q.width, dst.width - x), min(q.height, dst.height - y)
        if r > l and b > t:
            dst.alpha_composite(q.crop((l, t, r, b)), (x + l, y + t))

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idle = clamp01((t - 1.6) / 0.5)  # 着地後のゆらゆらの強さ
        # 降る雪 (文字の奥)
        if t > 1.2:
            a = clamp01((t - 1.2) / 0.4)
            for s in self.snow:
                y = (s["y0"] + s["v"] * t) % (H + 80) - 40
                x = s["x"] + 22 * math.sin(t * 1.4 + s["ph"] * 6)
                self.put(im, self.flakes[s["r"]], x, y, a, a, s["rot"] + 40 * t)
        for i, (spr, m, bb) in enumerate(self.g):
            t0 = 0.12 + i * 0.22
            u = (t - t0) / 0.42
            if u < 0:
                continue
            cx = self.x0 + i * GAP
            # 落ちてくる → 着地でむにっと潰れて戻る
            fall = ease_out(u)
            cy = BASE_Y - 420 * (1 - fall)
            land = t - t0 - 0.42
            sq = 0.2 * math.exp(-land * 8) * math.cos(land * 22) if land > 0 else -0.08 * (1 - u)
            sx, sy = 1 + sq, 1 - sq
            rot = (1 - fall) * (-18 if i % 2 else 18)
            # ゆらゆら (1文字ずつずらして)
            cy += idle * 12 * math.sin(2 * math.pi * (t / 1.6) - i * 0.9)
            rot += idle * 4 * math.sin(2 * math.pi * (t / 1.6) - i * 0.9 + 1.2)
            bottom = (bb[3] - spr.height / 2) * sy
            # つらら (着地してから伸びる)
            if land > 0:
                for k, (dx, L) in enumerate(((-0.24, 105), (0.06, 150), (0.3, 85))):
                    gl = ease_out_back((land - k * 0.08) / 0.45, 1.4) * L
                    if gl > 4:
                        ang = math.radians(rot)
                        ox, oy = dx * FS, bottom + 4
                        px = cx + ox * math.cos(ang) + oy * math.sin(ang)
                        py = cy - ox * math.sin(ang) + oy * math.cos(ang)
                        self.put(im, icicle(gl), px, py, rot=rot, anchor=(0.5, 0.0))
            # ツヤが横切る (斜めの白い帯を文字の中だけに)
            g = spr
            sh = (t - 2.7) / 0.9
            if 0 < sh < 1:
                band = Image.new("L", spr.size, 0)
                bx = -spr.width * 0.6 + (spr.width * 2.2) * sh - (i * 0.25 - 0.4) * spr.width
                ImageDraw.Draw(band).polygon([(bx, 0), (bx + 70, 0), (bx - 110, spr.height), (bx - 180, spr.height)],
                                             fill=255)
                band = Image.fromarray(np.minimum(np.array(band), np.array(m)))
                g = spr.copy()
                g.paste(Image.new("RGBA", spr.size, WHITE + (255,)), (0, 0), band)
            self.put(im, g, cx, cy, sx, sy, rot)
        # 札
        if t > 1.25:
            k = ease_out_back((t - 1.25) / 0.4, 2.6)
            wob = 3 * math.sin(2 * math.pi * t / 1.6 + 0.5) * idle
            self.put(im, self.tag, W / 2, 680 + 6 * math.sin(2 * math.pi * t / 1.6) * idle, k, k, wob)
        # キラキラ (ぱちっと光って消える)
        if t > 1.4:
            for x, y, r, ph in self.spark_pos:
                q = ((t - 1.4) / 1.1 + ph) % 1
                s = math.sin(q * math.pi) ** 2 if q < 0.5 else 0
                if s > 0.05:
                    self.put(im, self.sparks[r], x, y, s * 1.3, s * 1.3, 45 * q)
        return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Mochiy Pop One など丸い太字")
    ap.add_argument("--out", default="zettai_reido")
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    sc = Scene(a.font)
    if a.preview is not None:
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(sc.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    raw = ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    procs = [subprocess.Popen([ff, "-y", "-v", "error", *raw, "-f", "lavfi", "-i", f"color=0x00FF00:s={W}x{H}:r={FPS}",
                               "-filter_complex", "[1][0]overlay=shortest=1,format=yuv420p", "-c:v", "libx264",
                               "-crf", "16", "-movflags", "+faststart", a.out + "_greenback.mp4"], stdin=subprocess.PIPE),
             subprocess.Popen([ff, "-y", "-v", "error", *raw, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0",
                               "-crf", "24", "-row-mt", "1", "-auto-alt-ref", "0", a.out + ".webm"],
                              stdin=subprocess.PIPE)]
    n = round(DUR * FPS)
    for i in range(n):
        fr = sc.frame(i / FPS)
        if i == int(n * 0.6):
            fr.save(a.out + ".png")
        b = fr.tobytes()
        for p in procs:
            p.stdin.write(b)
    for p in procs:
        p.stdin.close()
        p.wait()


if __name__ == "__main__":
    main()
