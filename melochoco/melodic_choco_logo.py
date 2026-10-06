"""「メロディックチョコレート」の動く文字 (文字が主役のロゴ) をグリーンバックで書き出す.

  python3 melodic_choco_logo.py --font HachiMaruPop.ttf --fat 8 --out clips/text/melodic_choco_logo

背景の飾りは置かず、文字そのものを大きく・作り込んで見せる.
  文字: 手書きの丸文字を太らせ、ステッチ・ツヤ・深い厚み・白フチ + ピンクの外フチ
        「メロディック」= いちごピンク / 「チョコレート」= ミルクチョコの上半分にビターチョコがけ
  飾り: 文字にくっつくものだけ (「メ」のリボン・「ク」の横の音符・文字の角のきらめき)
  0.0-1.0  「メロディック」が1文字ずつ回りながらぽんっ
  0.7-1.5  「チョコレート」が上からドンッ → むにっ
  1.6      ロゴ全体がドンッと膨らみ、ツヤの光が横切る
  1.8-5.3  ビートに合わせて文字が波のように跳ねる / ツヤがもう一度 / 角がキラッ
  5.3-6.0  1文字ずつぽんっと弾けて消える
クロマキー用に、緑系の色と半透明のぼかしは使わない。
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

from zettai_reido_logo import CHOCO_D, PINK_D, WHITE, clamp01, ease_out, ease_out_back, put, sparkle, spring

W, H, FPS, DUR = 1920, 1080, 30, 6.0
EXIT_T = 5.3
BEAT = 60 / 128
FS = 300  # 文字の大きさの基準

STRAWBERRY = dict(top=(255, 190, 220), bot=(244, 96, 158), stitch=WHITE, ext=(150, 30, 80), ring=CHOCO_D)
MILK = dict(top=(226, 170, 128), bot=(176, 112, 74), stitch=(255, 170, 205), ext=(70, 34, 22), ring=CHOCO_D,
            glaze=((112, 58, 38), (78, 38, 24)))  # 上半分にかかるビターチョコ

# (文字, 大きさ, 傾き, 上下のずれ). 横の位置は文字幅から自動で並べる
LINE1 = [("メ", 1.0, -9, 10), ("ロ", 0.94, 6, -22), ("デ", 1.06, -5, 6), ("ィ", 0.6, 10, 62), ("ッ", 0.6, -8, 58),
         ("ク", 1.0, 8, -14)]
LINE2 = [("チ", 1.06, -7, 0), ("ョ", 0.64, 10, 66), ("コ", 1.04, 5, -16), ("レ", 0.98, -8, 8), ("ー", 0.92, 3, 10),
         ("ト", 1.06, 8, -12)]
LINE_Y = (345, 735)
LINE_T0 = (0.0, 0.72)
DRIPS = ""  # 文字の下に垂らす文字 (いまはチョコがけで表現するので無し)
GAP = -18  # 白フチどうしを少し重ねて一体感を出す


def hump(u):
    return math.sin(math.pi * clamp01(u))


def ease_in(x):
    return clamp01(x) ** 2


# ---------------------------------------------------------------- 文字
class Glyph:
    """1文字のロゴ用スプライト. 外側 (厚み・ピンクの外フチ・白フチ・こげ茶フチ) と中身を分けて持ち、
    間にチョコの垂れを挟む / 中身の上にツヤの帯を走らせる."""

    def __init__(self, ch, font, size, st, fat, drip):
        f = ImageFont.truetype(font, size)
        S = self.S = int(size * 1.9)

        def mask(w):
            m = Image.new("L", (S, S), 0)
            ImageDraw.Draw(m).text((S / 2, S / 2), ch, font=f, anchor="mm", fill=255, stroke_width=w + fat,
                                   stroke_fill=255)
            return m
        m0, m_ring, m_white, m_out = mask(0), mask(10), mask(30), mask(38)
        self.st = st
        outer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        n = 18
        for k in range(n, 0, -1):  # 深い厚み
            outer.paste(st["ext"] + (255,), (round(7 * k / n), round(20 * k / n)), m_out)
        outer.paste(PINK_D + (255,), (0, 0), m_out)
        outer.paste(WHITE + (255,), (0, 0), m_white)
        outer.paste(st["ring"] + (255,), (0, 0), m_ring)
        self.outer = outer
        a = np.array(m0)
        self.mask = m0
        bb = m0.getbbox()
        g = np.zeros((S, S, 4), np.uint8)
        yy = np.clip((np.arange(S) - bb[1]) / (bb[3] - bb[1]), 0, 1)[:, None]
        for c in range(3):
            g[..., c] = (st["top"][c] * (1 - yy) + st["bot"][c] * yy).astype(np.uint8)
        g[..., 3] = a
        fill = Image.fromarray(g, "RGBA")
        if "glaze" in st:  # 上半分のチョコがけ: 下の縁が波打ち、ところどころ垂れる
            Yg, Xg = np.mgrid[0:S, 0:S]
            hgt = bb[3] - bb[1]
            edge = bb[1] + hgt * 0.42 + 9 * np.sin(Xg / 19) + hgt * 0.16 * np.maximum(0, np.sin(Xg / 31 + 1)) ** 10
            gm = (Yg < edge) & (a > 128)
            gy = np.clip((Yg - bb[1]) / (hgt * 0.6), 0, 1)[..., None]
            gc = np.array(st["glaze"][0]) * (1 - gy) + np.array(st["glaze"][1]) * gy
            arr = np.array(fill)
            arr[gm, :3] = gc[gm].astype(np.uint8)
            # 縁の少し上に照り
            rim = gm & (Yg > edge - 9) & (Yg < edge - 5)
            arr[rim, :3] = (150, 92, 64)
            fill = Image.fromarray(arr, "RGBA")
        # ステッチ
        e1 = np.array(m0.filter(ImageFilter.MinFilter(15))) > 128
        e2 = np.array(m0.filter(ImageFilter.MinFilter(21))) > 128
        Y, X = np.mgrid[0:S, 0:S]
        stt = ((e1 & ~e2) & (((X + Y) // 10) % 2 == 0)).astype(np.uint8) * 255
        fill.paste(st["stitch"] + (255,), (0, 0), Image.fromarray(stt))
        # ぷるんとしたツヤ (上側)
        inner = np.array(m0.filter(ImageFilter.MinFilter(11))).astype(np.float32) / 255
        inner = np.roll(inner, 6, 0)
        fade = np.clip((0.46 - yy) / 0.3, 0, 1)
        hl = Image.fromarray(np.minimum((inner * fade * 0.6 * 255).astype(np.uint8), a))
        fill.paste(WHITE + (255,), (0, 0), hl.filter(ImageFilter.GaussianBlur(1.5)))
        self.fill = fill
        # 文字幅 (並べる用) ときらめきの位置 (右上の角)
        ob = m_white.getbbox()
        self.width = ob[2] - ob[0]
        ys, xs = np.nonzero(a > 128)
        j = np.argmax(xs - ys)
        self.glint = (xs[j] - S / 2, ys[j] - S / 2)
        self.drips = []
        if drip:  # いちばん下の画の、幅のある所に1本
            low = np.where(a > 128, np.arange(S)[:, None], -1).max(0)
            xs2 = np.nonzero(low >= low.max() - 18)[0]
            if len(xs2):
                sg = max(np.split(xs2, np.nonzero(np.diff(xs2) > 1)[0] + 1), key=len)
                if len(sg) >= 18:
                    cx = float(sg.mean())
                    self.drips.append((cx, int(low[int(cx)]) - 12, min(30, len(sg) * 0.6), 38))

    def draw(self, drip_k, shine):
        im = self.outer.copy()
        if drip_k > 0.01:
            d = ImageDraw.Draw(im)
            for cx, y0, w, L in self.drips:
                ln = L * drip_k
                for pad, col in ((38, PINK_D), (30, WHITE), (10, CHOCO_D), (0, self.st["bot"])):
                    r = w * 0.85 + pad
                    d.rounded_rectangle((cx - w / 2 - pad, y0 - pad, cx + w / 2 + pad, y0 + ln + pad),
                                        radius=w / 2 + pad, fill=col)
                    d.ellipse((cx - r, y0 + ln - r, cx + r, y0 + ln + r), fill=col)
                d.ellipse((cx - w * 0.5, y0 + ln - w * 0.4, cx - w * 0.15, y0 + ln - w * 0.05), fill=(230, 176, 146))
        im.alpha_composite(self.fill)
        if shine is not None:  # 斜めのツヤの帯
            band = Image.new("L", im.size, 0)
            bx = -0.3 * self.S + 1.6 * self.S * shine
            ImageDraw.Draw(band).polygon([(bx, 0), (bx + 70, 0), (bx - 150, self.S), (bx - 220, self.S)], fill=255)
            band = Image.fromarray(np.minimum(np.array(band), np.array(self.mask)) // 4 * 3)
            im.paste(WHITE + (255,), (0, 0), band)
        return im


def bow():
    S = (260, 190)
    im = Image.new("RGBA", S, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = S[0] / 2, 80
    sat, satd, satl = (236, 76, 138), (186, 38, 98), (255, 160, 198)
    for pad, col in ((14, PINK_D), (9, WHITE), (0, None)):
        for s in (-1, 1):
            d.polygon([(cx, cy), (cx + s * (100 + pad), cy - 56 - pad), (cx + s * (110 + pad), cy + 48 + pad)],
                      fill=col or sat)
            d.polygon([(cx - s * 4, cy + 6), (cx + s * (44 + pad), cy + 100 + pad), (cx + s * 26, cy + 88),
                       (cx + s * 14, cy + 106 + pad)], fill=col or satd)
    for s in (-1, 1):
        d.polygon([(cx, cy), (cx + s * 62, cy - 22), (cx + s * 66, cy + 20)], fill=satd)
        d.line([(cx + s * 36, cy - 26), (cx + s * 88, cy - 46)], fill=satl, width=7)
    d.ellipse((cx - 30, cy - 28, cx + 30, cy + 28), fill=WHITE)
    d.ellipse((cx - 22, cy - 21, cx + 22, cy + 21), fill=sat)
    return im


def note():
    S = 210
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hx, hy = 72, 158

    def shape(pad, col):
        d.ellipse((hx - 34 - pad, hy - 25 - pad, hx + 34 + pad, hy + 25 + pad), fill=col)
        d.rectangle((hx + 20 - pad, hy - 120 - pad, hx + 34 + pad, hy), fill=col)
        d.polygon([(hx + 20 - pad, hy - 122 - pad), (hx + 86 + pad, hy - 76), (hx + 72 + pad, hy - 54 + pad),
                   (hx + 34, hy - 80)], fill=col)
    shape(16, PINK_D)
    shape(10, WHITE)
    shape(4, CHOCO_D)
    shape(0, (255, 150, 196))
    d.ellipse((hx - 22, hy - 16, hx - 6, hy - 4), fill=WHITE)
    return im


# ---------------------------------------------------------------- シーン
class Scene:
    def __init__(self, font, fat):
        self.letters = []  # (段, 段の中の番号, 通し番号, 配置)
        order = 0
        for li, (spec, style) in enumerate(((LINE1, STRAWBERRY), (LINE2, MILK))):
            glyphs = [Glyph(ch, font, round(FS * sc), style, fat, li == 1 and ch in DRIPS) for ch, sc, _, _ in spec]
            total = sum(g.width for g in glyphs) + GAP * (len(glyphs) - 1)
            x = W / 2 - total / 2
            for i, (g, (ch, sc, rot, dy)) in enumerate(zip(glyphs, spec)):
                self.letters.append((li, i, order, dict(g=g, x=x + g.width / 2, y=LINE_Y[li] + dy, rot=rot)))
                x += g.width + GAP
                order += 1
        self.n = order
        self.bow = bow()
        self.note = note()
        self.glint = sparkle(30, WHITE, (255, 128, 182))

    def frame(self, t):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        idle = clamp01((t - 1.8) / 0.4)
        ex = (t - EXIT_T) / (DUR - EXIT_T)
        bump = spring(t - 1.6, 0.06, 16, 6) if t > 1.6 else 0  # ロゴ全体のドンッ
        beat_ph = t / BEAT
        sway = 2 * math.pi * t / (BEAT * 8)
        me = None  # 「メ」の位置 (リボン用)
        # 下の段から描く (上の段の厚みが下の段にかぶる)
        for li, i, order, it in sorted(self.letters, key=lambda z: -z[0]):
            g = it["g"]
            if li == 0:  # 回りながらぽんっ
                t0 = LINE_T0[0] + i * 0.13
                u = (t - t0) / 0.38
                if u < 0:
                    continue
                k = ease_out_back(u, 2.8)
                y = it["y"] - 90 * hump(u)
                rot = it["rot"] + 360 * (1 - ease_out(u)) * (1 if i % 2 else -1)
                land = t - t0 - 0.38
            else:  # 上からドンッ
                t0 = LINE_T0[1] + i * 0.11
                u = (t - t0) / 0.28
                if u < 0:
                    continue
                k = 1.0
                uu = clamp01(u)
                y = it["y"] - 700 * (1 - uu * uu)
                rot = it["rot"] + (1 - uu) * (20 if i % 2 else -20)
                land = t - t0 - 0.28
            sq = spring(land, 0.2, 22, 8)
            # 待機: ビートに合わせて波のように跳ねる
            q = (beat_ph / 4 - order / self.n * 0.9) % 1
            y -= idle * 26 * hump(q / 0.18)
            rot += idle * 2.5 * math.sin(sway + order)
            sc = k * (1 + bump)
            # 退場: 1文字ずつ、ちょっと膨らんでから弾けて消える
            if ex > 0:
                e = clamp01((ex - order / self.n * 0.55) / 0.35)
                sc *= (1 + 0.25 * hump(e / 0.5)) * (1 - ease_in((e - 0.4) / 0.6))
                y -= 60 * hump(e / 0.8)
            if sc <= 0.01:
                continue
            shine = None
            for st0 in (1.6, 3.5):  # 左から右へ順に
                s_ = (t - st0 - (it["x"] / W) * 0.45) / 0.4
                if 0 < s_ < 1:
                    shine = s_
            drip = ease_out_back((t - t0 - 0.32) / 0.8, 1.3) if li == 1 else 0
            put(im, g.draw(drip, shine), it["x"], y, sc, rot, 1 + sq, 1 - sq)
            if li == 0 and i == 0:
                me = (it["x"], y, sc, rot)
            # 角のきらめき
            if t > 1.9:
                ph = (t / 1.3 + order * 0.37) % 1
                s2 = hump(ph / 0.3) ** 2 * sc
                if s2 > 0.05:
                    gx, gy = g.glint
                    a = math.radians(-rot)
                    px = it["x"] + (gx * math.cos(a) - gy * math.sin(a)) * sc
                    py = y + (gx * math.sin(a) + gy * math.cos(a)) * sc
                    put(im, self.glint, px, py, s2 * 1.2, 45 * ph)
        # 「メ」の上のリボン
        if me is not None:
            x, y, sc, rot = me
            kk = min(sc, ease_out_back((t - 0.35) / 0.35, 2.8))
            if kk > 0.01:
                put(im, self.bow, x - 95, y - 150, kk, 18 + spring(t - 0.35, 14, 14, 4) + idle * 4 * math.sin(sway * 2))
        # 「ク」の右上の音符
        last = [z[3] for z in self.letters if z[0] == 0][-1]
        kk = ease_out_back((t - 0.95) / 0.35, 2.8)
        if ex > 0:
            kk *= 1 - ease_in(clamp01((ex - 0.1) / 0.3))
        if kk > 0.01:
            q = (beat_ph / 2) % 1
            put(im, self.note, last["x"] + 175, last["y"] - 125 - idle * 18 * hump(q / 0.3), kk * (1 + bump),
                12 + idle * 8 * math.sin(sway * 2))
        return im


SCENE = None


def _init(font, fat):
    global SCENE
    SCENE = Scene(font, fat)


def _frame(i):
    return SCENE.frame(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True, help="Hachi Maru Pop など手書きの丸文字")
    ap.add_argument("--fat", type=int, default=8, help="細いフォントを太らせる量 (px)")
    ap.add_argument("--out", default="melodic_choco_logo")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--preview", type=float, nargs="*")
    a = ap.parse_args()
    if a.preview is not None:
        _init(a.font, a.fat)
        for t in a.preview:
            bg = Image.new("RGBA", (W, H), (0, 255, 0, 255))
            bg.alpha_composite(SCENE.frame(t))
            bg.convert("RGB").save(f"{a.out}_{t:.2f}.png")
        return
    n = round(DUR * FPS)
    with Pool(a.jobs, initializer=_init, initargs=(a.font, a.fat)) as pool:
        frames = pool.map(_frame, range(n), chunksize=4)
    Image.frombytes("RGBA", (W, H), frames[int(n * 0.55)]).save(a.out + ".png")
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
