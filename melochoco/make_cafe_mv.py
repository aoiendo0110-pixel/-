"""3Dカフェ (cafe3d.py の出力) にキャラと歌詞を合成して MV にする.

  python3 make_cafe_mv.py --frames cafe_frames --image illust.png --audio source.mov \
      --font Mochiy.ttf --font-sub Hachi.ttf --out cafe_mv.mp4

歌詞の位置は、各行が出ている間の「顔の位置」を調べて、顔に重ならない場所を自動で選ぶ。
"""
import argparse
import glob
import json
import math
import os
import random
import subprocess
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import deco as D

W, H, FPS = 1920, 1080, 30
FACE = (915, 285)          # 元イラスト上の顔の中心
FACE_R = 150               # 元イラスト上の顔の半径 (髪を含めてゆったり)
CHAR_SWITCH = [0.0, 2.2, 4.1, 4.95, 7.35, 9.95, 13.45, 16.8, 21.4, 25.15, 26.65, 28.6]

# 歌詞: (行の開始秒, テキスト, スタイル, サイズ) を並べたグループ
GROUPS = [
    dict(start=0.05, end=2.2, plaque="banner", rows=[(0.05, "める散らかして", "milk", 96)]),
    dict(start=2.25, end=4.1, plaque="bubble", rows=[(2.25, "吐き気催すまで", None, 100)]),
    dict(start=4.1, end=4.72, plaque=None, rows=[(4.1, "受け取れ", "cherry", 200)], slam=True, burst=True),
    dict(start=4.72, end=7.25, plaque=None, rows=[(4.72, "メロディック", "lemon", 118), (5.4, "チョコレート", "choco", 118),
                                                  (6.2, "メンタル", "berry", 130)]),
    dict(start=7.4, end=9.8, plaque=None, rows=[(7.4, "お好み通り", "cherry", 150)]),
    dict(start=9.95, end=11.1, plaque="bubble", rows=[(9.95, "型に流して", None, 104)]),
    dict(start=11.15, end=12.0, plaque=None, rows=[(11.15, "冷やして", "milk", 140)]),
    dict(start=12.05, end=13.3, plaque=None, rows=[(12.05, "できあがり", "cherry", 140)], burst=True),
    dict(start=13.7, end=16.65, plaque=None, rows=[(13.7, "ハートに", "berry", 112), (14.6, "割れ目", "cherry", 150),
                                                   (15.15, "できませんように", "milk", 88)]),
    dict(start=16.7, end=17.85, plaque=None, rows=[(16.7, "絶対零度で", "milk", 130)]),
    dict(start=17.85, end=19.45, plaque=None, rows=[(17.85, "固めて", "milk", 170)]),
    dict(start=19.45, end=21.2, plaque=None, rows=[(19.45, "とじこめる", "cherry", 150)]),
    dict(start=21.45, end=22.6, plaque="banner", rows=[(21.45, "しろくろリボン", "milk", 96)]),
    dict(start=22.65, end=25.0, plaque="banner", rows=[(22.65, "強く結んだなら", "milk", 96)]),
    dict(start=25.15, end=26.5, plaque="bubble", rows=[(25.15, "できあがりよ", None, 108)], burst=True),
    dict(start=26.55, end=28.45, plaque="banner", rows=[(26.55, "欲しいならあげる", "milk", 96)]),
    dict(start=28.6, end=99, plaque=None, rows=[(28.6, "君を", "cherry", 190), (29.3, "めろつかせ", "berry", 130),
                                                (29.95, "ちゃうぞ", "berry", 130)], burst=True),
]

A = {}
_c = {}


def cached(k, fn):
    if k not in _c:
        _c[k] = fn()
    return _c[k]


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def spring(t, freq=15.0, damp=7.5):
    """0 → 1 に少し行き過ぎて戻る、ぷるんとした動き."""
    if t <= 0:
        return 0.0
    return 1 - math.exp(-damp * t) * math.cos(freq * t)


def paste(dst, src, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        src = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))), Image.BILINEAR)
    if abs(rot) > 0.05:
        src = src.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 0.999:
        src = src.copy()
        src.putalpha(src.getchannel("A").point(lambda v: int(v * alpha)))
    D._clip(dst, src, int(cx - src.width / 2), int(cy - src.height / 2))


# ---- アンカー (キャラ位置) --------------------------------------------------
def load_anchors(d):
    an = {}
    for f in glob.glob(os.path.join(d, "anchors_[0-9]*.jsonl")):
        for line in open(f):
            j = json.loads(line)
            an[int(round(j["t"] * FPS))] = j
    return an


def char_geom(fi):
    """フレーム fi でのキャラの (中心x, 中心y, スケール, 顔x, 顔y, 顔半径, bbox)."""
    a = A["anch"][min(fi, max(A["anch"]))]
    crop = A["crop"]
    sc = 2 * a["half_h"] / crop.height
    cx, cy = a["cx"], a["cy"]
    ox, oy = A["crop_off"]
    fx = cx + (FACE[0] - ox - crop.width / 2) * sc
    fy = cy + (FACE[1] - oy - crop.height / 2) * sc
    bb = (cx - crop.width * sc / 2, cy - crop.height * sc / 2, cx + crop.width * sc / 2, cy + crop.height * sc / 2)
    return cx, cy, sc, fx, fy, FACE_R * sc, bb, a


# ---- 歌詞のレイアウト (顔を避ける) -------------------------------------------
def block_size(g):
    ws, hs = [], []
    for _, text, style, size in g["rows"]:
        k = 1.5 if g["plaque"] == "bubble" else 1.0
        ws.append(len(text) * size * 0.98 * k + (160 if g["plaque"] == "banner" else 0) + size * 0.4)
        hs.append(size * (1.5 if g["plaque"] == "bubble" else 1.25) + (60 if g["plaque"] == "banner" else 0))
    return max(ws), sum(hs), hs


def rect_circle(r, c):
    x = min(max(c[0], r[0]), r[2])
    y = min(max(c[1], r[1]), r[3])
    return math.hypot(x - c[0], y - c[1]) < c[2]


def rect_overlap(a, b):
    w = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    return w * h


def choose_layout(g):
    bw, bh, _ = block_size(g)
    f0 = int(g["start"] * FPS)
    f1 = min(int(min(g["end"], 31) * FPS), max(A["anch"]))
    faces, bodies = [], []
    for fi in range(f0, f1 + 1, 2):
        _, _, _, fx, fy, fr, bb, _ = char_geom(fi)
        faces.append((fx, fy, fr * 1.25 + 30))
        bodies.append(bb)
    fx_mean = sum(f[0] for f in faces) / len(faces)
    cands = []
    for cx in np.linspace(bw / 2 + 60, W - bw / 2 - 60, 13):
        for cy in np.linspace(bh / 2 + 70, H - bh / 2 - 60, 9):
            r = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
            if any(rect_circle(r, f) for f in faces):
                continue
            body = sum(rect_overlap(r, b) for b in bodies) / len(bodies) / (bw * bh)
            score = body * 2.0                              # 体にもなるべく重ねない
            score += abs(cy - H * 0.62) / H * 0.8           # やや下寄りが読みやすい
            score += 0.6 if (cx - W / 2) * (fx_mean - W / 2) > 0 else 0   # 顔と反対側を優先
            score += abs(cx - (W - fx_mean)) / W * 0.3
            cands.append((score, cx, cy))
    if not cands:  # どうしても無理なら上か下の端
        return (W / 2, H - bh / 2 - 40)
    cands.sort()
    return cands[0][1], cands[0][2]


# ---- 文字 ------------------------------------------------------------------
def csprite(ch, size, style):
    return cached(("c", ch, size, style), lambda: D.cute_char(ch, size, style, A["font"]))


def bsprite(ch, size, col):
    return cached(("b", ch, size, col), lambda: D.bubble(ch, size, A["font"], col))


def draw_group(im, g, gi, t, p):
    if t < g["start"] - 0.05 or t > g["end"] + 0.3:
        return
    cx, cy = A["layout"][gi]
    bw, bh, hs = block_size(g)
    y = cy - bh / 2
    out_u = clamp01((t - g["end"]) / 0.25) if t > g["end"] else 0.0
    rnd = random.Random(gi * 31)
    for ri, (st, text, style, size) in enumerate(g["rows"]):
        rh = hs[ri]
        ry = y + rh / 2
        y += rh
        nxt = g["rows"][ri + 1][0] if ri + 1 < len(g["rows"]) else min(g["end"], st + 2.0)
        span = max(0.2, min(0.65, (nxt - st) * 0.6))
        gap = size * (1.5 if g["plaque"] == "bubble" else 0.98)
        if g["plaque"] == "banner":
            bwid = int(len(text) * size * 1.02 + 60)
            ban = cached(("ban", bwid), lambda: D.banner(bwid))
            k = spring(t - st + 0.05, 12, 6)
            paste(im, ban, cx, ry + 4, 0.6 + 0.4 * k, 0, clamp01(k * 3) * (1 - out_u))
        n = len(text)
        for i, ch in enumerate(text):
            ti = st + span * i / max(n, 1)
            lt = t - ti
            if lt < 0:
                continue
            x = cx + (i - (n - 1) / 2) * gap
            r0 = rnd.uniform(-28, 28)
            k = spring(lt, 16, 7)
            if g.get("slam"):
                sc = 1 + 1.4 * math.exp(-lt * 14)
                alpha = clamp01(lt / 0.06)
            else:
                sc = k
                alpha = clamp01(lt / 0.05)
            yy = ry + (1 - k) * 60 + 5 * math.sin(t * 3.2 + i * 0.7)
            rot = r0 * (1 - smooth(lt / 0.35)) + 3 * math.sin(t * 2.2 + i)
            sc *= 1 + 0.05 * p
            if out_u > 0:  # 1文字ずつ ぽんっ と消える
                u = clamp01(out_u * 1.6 - i / max(n, 1) * 0.6)
                sc *= (1 + 0.25 * math.sin(u * math.pi)) * (1 - smooth(u))
                alpha *= 1 - smooth(u)
            spr = bsprite(ch, size, (220, 28, 62) if i % 2 == 0 else (255, 110, 165)) if style is None \
                else csprite(ch, size, style)
            paste(im, spr, x, yy, sc, rot, alpha)
        # 行の端にキラキラ
        if t > st:
            tw = cached("tw", lambda: D.twinkle(56))
            s = (0.55 + 0.45 * abs(math.sin(t * 5 + ri))) * (1 - out_u)
            paste(im, tw, cx - (n / 2) * gap - size * 0.4, ry - size * 0.45, s, t * 40)
            paste(im, tw, cx + (n / 2) * gap + size * 0.35, ry + size * 0.3, s * 0.8, -t * 40)


# ---- エフェクト ---------------------------------------------------------------
def confetti(im, t, t0, cx, cy, seed=1, n=70, spread=900):
    if t < t0 or t > t0 + 1.6:
        return
    rnd = random.Random(seed)
    dr = ImageDraw.Draw(im)
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        d = (1 - math.exp(-(t - t0) * 4)) * rnd.uniform(150, spread)
        x = cx + math.cos(a) * d
        y = cy + math.sin(a) * d * 0.7 + (t - t0) ** 2 * 420
        col = rnd.choice([D.RED, D.WHITE, D.YELLOW, D.PINK, (255, 110, 165)])
        if rnd.random() < 0.5:
            dr.polygon(D.heart_pts(x, y, rnd.uniform(10, 18)), fill=col)
        else:
            ang = rnd.uniform(0, math.pi) + t * 5
            dr.line([(x - math.cos(ang) * 12, y - math.sin(ang) * 12), (x + math.cos(ang) * 12, y + math.sin(ang) * 12)],
                    fill=col, width=8)


def sparkles(im, t, p):
    tw = cached("tw", lambda: D.twinkle(56))
    rnd = random.Random(int(t * 3))
    for i in range(6):
        ph = ((t * 3) % 1)
        x, y = rnd.uniform(80, W - 80), rnd.uniform(80, H - 80)
        paste(im, tw, x, y, 0.3 + 0.7 * math.sin(ph * math.pi), t * 60 + i * 30, 0.9)


def make_tag():
    f = ImageFont.truetype(A["font_sub"], 26)
    text = "♡ めろチョコ 歌ってみた ♡"
    tw = int(f.getlength(text)) + 50
    lab = Image.new("RGBA", (tw, 54), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lab)
    dr.rounded_rectangle([0, 0, tw - 1, 53], radius=27, fill=(255, 255, 255, 235), outline=D.RED, width=4)
    dr.text((tw / 2, 28), text, font=f, anchor="mm", fill=D.RED)
    return lab


# ---- 1フレーム ---------------------------------------------------------------
def load_bg(fi):
    fi = min(fi, A["nrender"] - 1)
    im = Image.open(os.path.join(A["frames"], f"f_{fi:04d}.png")).convert("RGB")
    return im.resize((W, H), Image.LANCZOS)


def render(fi):
    t = fi / FPS
    p = float(A["pulse"][min(fi, len(A["pulse"]) - 1)])
    bg = load_bg(fi)
    cx, cy, sc, fx, fy, fr, bb, a = char_geom(fi)
    if a.get("fast") and fi > 0:  # カメラが速く動くところはモーションブラー
        bg = Image.blend(bg, load_bg(fi - 1), 0.45)
    bg = bg.filter(ImageFilter.UnsharpMask(1.4, 60, 2))
    im = bg.convert("RGBA")
    # キャラ: 切り替わりで ぽよん と登場
    since = t - max(s for s in CHAR_SWITCH if s <= t + 1e-6)
    k = spring(since + 0.02, 13, 6) if since < 0.8 else 1.0
    if a["depth"] > 0:
        s2 = sc * (0.8 + 0.2 * k) * (1 + 0.012 * p)
        shadow = cached("shadow", make_shadow)
        paste(im, shadow, cx + 18 * s2 / sc, cy + 30 * s2 / sc, s2, 0, 0.55 * clamp01(k * 2))
        paste(im, A["crop"], cx, cy, s2, 1.5 * math.sin(t * 1.3), clamp01(k * 2))
    # 歌詞
    for gi, g in enumerate(GROUPS):
        draw_group(im, g, gi, t, p)
        if g.get("burst"):
            gx, gy = A["layout"][gi]
            confetti(im, t, g["start"], gx, gy, seed=gi, spread=1100)
    sparkles(im, t, p)
    im.alpha_composite(A["tag"], (W - A["tag"].width - 36, 28))
    # 仕上げ: ほんのりブルーム + 彩度
    rgb = im.convert("RGB")
    small = rgb.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)).resize((W, H),
                                                                                                    Image.BILINEAR)
    arr = np.asarray(rgb).astype(np.float32) / 255
    bl = np.clip(np.asarray(small).astype(np.float32) / 255 - 0.7, 0, 1) * 1.2
    arr = 1 - (1 - arr) * (1 - bl * 0.5)
    yy, xx = np.mgrid[0:H, 0:W]
    vig = (((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    arr = arr * (1 - np.clip(vig - 0.55, 0, 1)[..., None] * np.array([0.25, 0.4, 0.32]))
    end_t = A["nframes"] / FPS
    if t > end_t - 0.5:
        u = smooth((t - (end_t - 0.5)) / 0.45)
        m = Image.new("L", (W, H), 255)
        ImageDraw.Draw(m).polygon(D.heart_pts(fx, fy + fr * 0.2, max(1, 1500 * (1 - u))), fill=0)
        mm = np.asarray(m).astype(np.float32)[..., None] / 255
        arr = arr * (1 - mm) + np.array([0.55, 0.12, 0.28]) * mm
    out = Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8))
    out = ImageEnhance.Color(out).enhance(1.08)
    return out.tobytes()


def make_shadow():
    a = A["crop"].getchannel("A").filter(ImageFilter.GaussianBlur(18))
    s = Image.new("RGBA", A["crop"].size, (120, 20, 60, 0))
    s.putalpha(a.point(lambda v: int(v * 0.6)))
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--anchors", help="アンカーのフォルダ (省略時は --frames)")
    ap.add_argument("--image", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--font", required=True)
    ap.add_argument("--font-sub", required=True)
    ap.add_argument("--out", default="cafe_mv.mp4")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    A["frames"], A["font"], A["font_sub"] = args.frames, args.font, args.font_sub
    ch = Image.open(args.image).convert("RGBA")
    ch = ImageEnhance.Contrast(ch).enhance(1.04)
    bbox = ch.getbbox()
    A["crop"] = ch.crop(bbox)
    A["crop_off"] = bbox[:2]
    A["anch"] = load_anchors(args.anchors or args.frames)
    A["nrender"] = max(int(os.path.basename(f)[2:6]) for f in glob.glob(os.path.join(args.frames, "f_*.png"))) + 1
    A["tag"] = make_tag()
    raw = subprocess.run([args.ffmpeg, "-v", "error", "-i", args.audio, "-vn", "-ac", "1", "-ar", "11025",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    au = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    spf = 11025 // FPS
    n = len(au) // spf
    rms = np.sqrt((au[: n * spf].reshape(n, spf) ** 2).mean(1))
    rms = rms / (np.percentile(rms, 95) + 1e-6)
    onset = np.maximum(0, np.diff(rms, prepend=rms[0]))
    onset = onset / (np.percentile(onset, 97) + 1e-6)
    pulse = np.zeros(n)
    for i in range(n):
        pulse[i] = max(min(onset[i], 1.2), pulse[i - 1] * 0.72 if i else 0)
    A["pulse"] = pulse
    A["nframes"] = min(n, A["nrender"]) if not args.preview else n
    A["layout"] = [choose_layout(g) for g in GROUPS]
    if args.preview:
        for s in args.preview:
            Image.frombytes("RGB", (W, H), render(int(round(s * FPS)))).save(f"cmv_{s:05.2f}.png")
        return
    enc = subprocess.Popen([args.ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", args.audio,
                            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-b:v", "6500k",
                            "-maxrate", "8000k", "-bufsize", "12000k", "-pix_fmt", "yuv420p", "-c:a", "aac",
                            "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out], stdin=subprocess.PIPE)
    with Pool(args.jobs) as pool:
        for i, fr in enumerate(pool.imap(render, range(A["nframes"]), chunksize=2)):
            enc.stdin.write(fr)
            if i % 60 == 0:
                print(f"frame {i}/{A['nframes']}", flush=True)
    enc.stdin.close()
    enc.wait()


if __name__ == "__main__":
    main()
