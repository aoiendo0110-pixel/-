"""ピンクのキラキラ×ハート素材がゆらゆら動くループ動画を作る。

    pip install numpy pillow imageio-ffmpeg
    python3 make_loop.py --out pink_loop.mp4 --size 1080 --seconds 15

最初と最後のフレームがつながるので、そのままループ再生できる。
"""
import argparse
import subprocess

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

TAU = np.pi * 2


def lerp(a, b, t):
    return a + (b - a) * t[..., None]


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)


DEEP = hexc("#e2105f")
HOT = hexc("#ff3d8f")
LIGHT = hexc("#ff9fcf")
IRIS = hexc("#ffd6f0")


# ---------- 背景: 液体みたいにうねるピンク ----------
def background(S, th):
    """th は 0..2π のループ位相。中の時間変化はすべて th の整数倍で回るのでループする。"""
    s = S // 2  # 半分の解像度で計算して拡大 (なめらかな絵なので十分)
    y, x = np.mgrid[0:s, 0:s].astype(np.float32) / s
    # 斜めに流れる座標
    u = x * 0.8 + y * 0.6
    v = -x * 0.6 + y * 0.8
    # ドメインワープ
    q1 = np.sin(v * 5.0 + 1.4 * np.sin(u * 3.0 + th) + th)
    q2 = np.cos(u * 4.0 + 1.2 * np.sin(v * 3.5 - th) - 2 * th)
    w1 = u + 0.22 * q1
    w2 = v + 0.22 * q2
    f = np.sin(w2 * 9.0 + 1.6 * np.sin(w1 * 4.0 + th) + 0.8 * q2 + th)
    g = np.sin(w1 * 6.0 + 1.3 * np.cos(w2 * 5.0 - th) - th)

    # ベースの色: 濃いピンク〜明るいピンク
    tone = 0.5 + 0.5 * np.sin(w1 * 3.2 + w2 * 2.0 + 0.9 * g + th)
    col = lerp(DEEP, HOT, np.clip(tone * 1.2, 0, 1))
    col = lerp(col, LIGHT, np.clip((g * 0.5 + 0.5) ** 3 * 0.9, 0, 1))

    # つやつやした白い筋 (ガラスみたいなハイライト)
    streak = (1 - np.abs(f)) ** 5 * 0.75
    streak2 = (1 - np.abs(np.sin(w2 * 17.0 + 2.0 * g - th))) ** 14 * 0.45
    gloss = np.clip(np.sin(w1 * 5.0 - w2 * 7.0 + 1.5 * q1 + th) * 1.6 - 0.6, 0, 1) ** 2 * 0.55
    sheen = np.clip(streak + streak2 + gloss, 0, 1)
    col = lerp(col, IRIS, sheen * 0.8)
    col = col + sheen[..., None] * 0.25

    # ふんわり光るムラ
    glow = np.exp(-((x - 0.35 - 0.08 * np.sin(th)) ** 2 + (y - 0.35 - 0.06 * np.cos(th)) ** 2) / 0.05)
    glow += 0.7 * np.exp(-((x - 0.25 + 0.05 * np.cos(th)) ** 2 + (y - 0.78) ** 2) / 0.03)
    col = col + glow[..., None] * 0.35

    img = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)
    return np.asarray(img).astype(np.float32) / 255


# ---------- スプライト ----------
def heart_points(cx, cy, r, n=200):
    t = np.linspace(0, TAU, n)
    hx = 16 * np.sin(t) ** 3
    hy = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
    return list(zip(cx + hx * r / 17, cy + hy * r / 17))


def heart_sprite(size, fill_alpha):
    """光る輪郭のハート。返り値は 0..1 の明るさマップ (加算・スクリーン用)。"""
    pad = size
    W = size * 2 + pad
    c = W / 2
    im = Image.new("L", (W, W), 0)
    d = ImageDraw.Draw(im)
    pts = heart_points(c, c + size * 0.05, size)
    d.polygon(pts, fill=int(255 * fill_alpha))
    d.line(pts + [pts[0]], fill=255, width=max(2, size // 9), joint="curve")
    core = np.asarray(im).astype(np.float32) / 255
    glow = np.asarray(im.filter(ImageFilter.GaussianBlur(size * 0.22))).astype(np.float32) / 255
    glow2 = np.asarray(im.filter(ImageFilter.GaussianBlur(size * 0.6))).astype(np.float32) / 255
    return np.clip(core * 0.9 + glow * 0.9 + glow2 * 0.6, 0, 1)


def star_sprite(size):
    W = size * 4
    c = W / 2
    y, x = np.mgrid[0:W, 0:W].astype(np.float32) - c + 0.5
    r = np.hypot(x, y) / size
    # 4本の光線 + まるい光
    rays = np.exp(-np.abs(x) / (size * 0.07)) * np.exp(-np.abs(y) / (size * 1.2))
    rays += np.exp(-np.abs(y) / (size * 0.07)) * np.exp(-np.abs(x) / (size * 1.2))
    dot = np.exp(-r ** 2 / 0.08) + 0.5 * np.exp(-r ** 2 / 0.6)
    return np.clip(rays * 0.9 + dot, 0, 1)


def screen_add(frame, sprite, cx, cy, amount, tint):
    """frame に sprite をスクリーン合成する (はみ出しはクリップ)。"""
    S = frame.shape[0]
    h, w = sprite.shape
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    xs, ys = max(0, x0), max(0, y0)
    xe, ye = min(S, x0 + w), min(S, y0 + h)
    if xs >= xe or ys >= ye:
        return
    a = sprite[ys - y0:ye - y0, xs - x0:xe - x0, None] * amount * tint
    region = frame[ys:ye, xs:xe]
    frame[ys:ye, xs:xe] = 1 - (1 - region) * (1 - a)


# ---------- メイン ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="pink_loop.mp4")
    ap.add_argument("--size", type=int, default=1080)
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--preview", type=float, default=None, help="この秒の静止画だけ書き出す")
    args = ap.parse_args()

    S, fps = args.size, args.fps
    n = int(args.seconds * fps)
    rng = np.random.default_rng(args.seed)
    k = S / 1080

    white = np.array([1, 1, 1], np.float32)
    pinkwhite = np.array([1, 0.86, 0.95], np.float32)

    # ハート: ゆっくり上へのぼりつつ、左右にゆらゆら
    hearts = []
    for _ in range(60):
        size = int(rng.choice([14, 18, 22, 26, 30, 36, 44, 54]) * k)
        spr = heart_sprite(size, fill_alpha=rng.uniform(0.15, 0.4))
        spr = np.asarray(Image.fromarray((spr * 255).astype(np.uint8)).rotate(
            rng.uniform(-30, 30), resample=Image.BICUBIC)).astype(np.float32) / 255
        hearts.append(dict(
            spr=spr, x=rng.uniform(0, S), y=rng.uniform(0, S),
            rise=int(rng.integers(1, 3)),          # ループ中に何周のぼるか
            sway=rng.uniform(10, 34) * k, sk=int(rng.integers(1, 4)), ph=rng.uniform(0, TAU),
            tw=int(rng.integers(2, 6)), amt=rng.uniform(0.55, 0.95),
            tint=pinkwhite if rng.random() < 0.5 else white,
        ))
    # キラキラ
    stars = []
    for _ in range(220):
        size = int(rng.choice([4, 5, 6, 8, 10, 14, 20]) * k)
        stars.append(dict(
            spr=star_sprite(size), x=rng.uniform(0, S), y=rng.uniform(0, S),
            dx=rng.uniform(6, 20) * k, dk=int(rng.integers(1, 3)), ph=rng.uniform(0, TAU),
            tw=int(rng.integers(3, 9)), amt=rng.uniform(0.5, 1.0),
        ))
    # 大きいぼんやり光
    bokeh = [dict(spr=_soft_blob(int(110 * k)),
                  x=rng.uniform(0, S), y=rng.uniform(0, S), r=rng.uniform(30, 90) * k,
                  ph=rng.uniform(0, TAU), amt=rng.uniform(0.35, 0.6)) for _ in range(6)]

    margin = 120 * k

    def render(i):
        p = (i % n) / n
        th = p * TAU
        frame = background(S, th)
        for b in bokeh:
            screen_add(frame, b["spr"], b["x"] + b["r"] * np.cos(th + b["ph"]),
                       b["y"] + b["r"] * np.sin(th + b["ph"]),
                       b["amt"] * (0.75 + 0.25 * np.sin(2 * th + b["ph"])), white)
        for h in hearts:
            span = S + margin * 2
            y = (h["y"] - p * span * h["rise"]) % span - margin
            x = h["x"] + h["sway"] * np.sin(h["sk"] * th + h["ph"])
            a = h["amt"] * (0.7 + 0.3 * np.sin(h["tw"] * th + h["ph"]))
            screen_add(frame, h["spr"], x, y, a, h["tint"])
        for s in stars:
            x = s["x"] + s["dx"] * np.sin(s["dk"] * th + s["ph"])
            tw = 0.5 + 0.5 * np.sin(s["tw"] * th + s["ph"])
            screen_add(frame, s["spr"], x, s["y"], s["amt"] * tw ** 2, white)
        return bloom(frame)

    if args.preview is not None:
        Image.fromarray(render(int(args.preview * fps))).save(args.out)
        return

    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{S}x{S}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "17", "-preset", "slow",
           "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(render(i).tobytes())
        if i % 30 == 0:
            print(f"{i}/{n}", flush=True)
    proc.stdin.close()
    proc.wait()
    print("done:", args.out)


def bloom(frame):
    """明るいところをにじませて、キラッと光らせる。"""
    S = frame.shape[0]
    hi = np.clip(frame - 0.78, 0, 1) * 4
    small = Image.fromarray((np.clip(hi, 0, 1) * 255).astype(np.uint8)).resize((S // 4, S // 4), Image.BILINEAR)
    b1 = np.asarray(small.filter(ImageFilter.GaussianBlur(4)).resize((S, S), Image.BICUBIC)).astype(np.float32) / 255
    b2 = np.asarray(small.filter(ImageFilter.GaussianBlur(14)).resize((S, S), Image.BICUBIC)).astype(np.float32) / 255
    glow = np.clip(b1 * 0.45 + b2 * 0.5, 0, 1) * np.array([1, 0.9, 0.96], np.float32)
    out = 1 - (1 - frame) * (1 - glow)
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def _soft_blob(size):
    W = size * 2
    y, x = np.mgrid[0:W, 0:W].astype(np.float32) - size + 0.5
    r = np.hypot(x, y) / size
    return np.clip(np.exp(-r ** 2 * 3.0) * 1.0, 0, 1)


if __name__ == "__main__":
    main()
