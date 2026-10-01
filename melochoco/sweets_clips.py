"""3Dのスイーツが動くグリーンバック素材を書き出す.

  python3 sweets_clips.py --out clips [--only ichigo_bounce donut_roll] [--jobs 4]

render3d.py のスプライト (回転の連番) を使って、跳ねる・積み上がる・転がる・回る・降る、を作る。
1本ごとに
  <name>_greenback.mp4 : 緑 (0,255,0) 背景の H.264
  <name>.webm          : 背景透過の VP9
  <name>.png           : 途中の1コマ (確認用)
を出力する。初回はスプライトを --cache に保存するので2回目からは速い。
"""
import argparse
import math
import os
import random
import subprocess
from multiprocessing import Pool

import imageio_ffmpeg
from PIL import Image

import render3d as R

FPS = 30
GREEN = (0, 255, 0)
SPR = {}  # name -> [Image] (回転の連番)

# スプライト: 名前 -> (大きさ, 1周のコマ数)
SPEC = {
    "ichigo_choco": (560, 60),
    "macaron": (480, 60), "macaron_y": (480, 60), "macaron_c": (480, 60),
    "cupcake": (560, 60),
    "donut_front": (560, 1),
    "choco_heart": (520, 60),
    "gift": (520, 60),
    "truffle": (300, 48), "truffle_w": (300, 48), "strawberry": (300, 48), "candy_p": (300, 48),
    "candy": (300, 48), "cookie": (300, 48), "bow_pink": (300, 48), "cherry": (300, 48), "bar": (300, 48),
    "heart": (160, 36), "heart_white": (160, 36),
}
SMALL = ["truffle", "truffle_w", "strawberry", "candy_p", "candy", "cookie", "bow_pink", "cherry", "bar",
         "macaron", "macaron_y", "macaron_c"]


# ---------------------------------------------------------------- 道具
def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out_back(x, s=1.9):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_out(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def spr(name, rev):
    """rev 回転ぶん回ったときのスプライト."""
    seq = SPR[name]
    return seq[int(math.floor(rev * len(seq))) % len(seq)]


def bottom(name):
    """スプライトの中心から、物体の下端までの距離 (スプライト幅に対する比)."""
    b = max(im.getbbox()[3] for im in SPR[name])
    return b / SPR[name][0].height - 0.5


def put(dst, im, cx, cy, size, sx=1.0, sy=1.0, rot=0.0, alpha=1.0, anchor_bottom=None):
    """im を幅 size で (cx, cy) 中心に置く. sx/sy で伸び縮み, anchor_bottom を渡すと下端を固定して潰す."""
    if size < 2 or alpha <= 0:
        return
    w = max(1, round(size * sx))
    h = max(1, round(size * sy))
    if anchor_bottom is not None:  # 下端 (中心から anchor_bottom*size 下) を固定
        cy = cy + anchor_bottom * size - anchor_bottom * h
    q = im.resize((w, h), Image.LANCZOS)
    if rot:
        q = q.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1:
        q.putalpha(q.getchannel("A").point(lambda v: round(v * alpha)))
    # 画面からはみ出す分は切り取ってから重ねる
    x, y = round(cx - q.width / 2), round(cy - q.height / 2)
    l, tp = max(0, -x), max(0, -y)
    r, b = min(q.width, dst.width - x), min(q.height, dst.height - y)
    if r > l and b > tp:
        dst.alpha_composite(q.crop((l, tp, r, b)), (x + l, y + tp))


def bounce_squash(u):
    """着地直後の潰れ (u: 着地からの秒). 減衰しながらぷるんと戻る."""
    if u < 0:
        return 0.0
    return 0.22 * math.exp(-u * 9) * math.cos(u * 26)


# ---------------------------------------------------------------- クリップ
def ichigo_bounce(t):
    """チョコがけいちごが、ぽんっと出てきて3回ぴょんぴょん跳ねる (4秒)."""
    im = Image.new("RGBA", (620, 900), (0, 0, 0, 0))
    S, ground = 560, 860
    ab = bottom("ichigo_choco")
    cy0 = ground - ab * S
    k = ease_out_back(t / 0.35)
    hops = [(0.6, 0.62, 230), (1.4, 0.62, 260), (2.2, 0.7, 320)]  # (開始, 長さ, 高さ)
    y, sx, sy, rot, land = 0.0, 1.0, 1.0, 0.0, 0.35
    for t0, d, hgt in hops:
        u = (t - t0) / d
        if 0 <= u < 1:
            y = -hgt * 4 * u * (1 - u)
            st = 0.12 * (1 - abs(2 * u - 1))  # 空中は縦にのびる
            sx, sy = 1 - st, 1 + st
            rot = 10 * math.sin(u * math.pi * 2) * (1 if t0 != 1.4 else -1)
        elif u >= 1:
            land = t0 + d
        if -0.12 < t - t0 < 0:  # ジャンプ前のため
            q = (t - t0 + 0.12) / 0.12
            sx, sy = 1 + 0.16 * math.sin(q * math.pi), 1 - 0.16 * math.sin(q * math.pi)
    if all(not (0 <= (t - t0) / d < 1) for t0, d, _ in hops) and t > 0.35:
        s = bounce_squash(t - land)
        sx, sy = 1 + s, 1 - s
    rev = 0.35 * t + (0.5 * clamp01((t - 2.2) / 0.7) if t > 2.2 else 0)  # 最後のジャンプで半回転
    put(im, spr("ichigo_choco", rev), 310, cy0 + y, S * k, sx, sy, rot, anchor_bottom=ab)
    return im


def macaron_tower(t):
    """マカロンが上から落ちてきて3段に積み上がり、最後にハートがのる (4秒)."""
    im = Image.new("RGBA", (560, 960), (0, 0, 0, 0))
    S = 470
    ground = 930
    step = 158  # 1段の高さ
    items = [("macaron", 0.15), ("macaron_y", 0.85), ("macaron_c", 1.55)]
    fall = 0.42
    wob = 0.0
    for i, (_, t0) in enumerate(items):  # 着地のたびに塔が揺れる
        u = t - (t0 + fall)
        if u > 0:
            wob += 5 * math.exp(-u * 4) * math.sin(u * 14) * (1 if i % 2 == 0 else -1)
    for i, (name, t0) in enumerate(items):
        if t < t0:
            continue
        u = (t - t0) / fall
        rest = ground - 0.5 * S * 0.42 - i * step
        if u < 1:
            y = -260 + (rest + 260) * u * u  # 重力っぽく加速して落ちる
            sx, sy = 0.94, 1.08
        else:
            y = rest
            s = bounce_squash(t - t0 - fall)
            sx, sy = 1 + s, 1 - s * 1.4
        # 揺れは下の段ほど小さく (塔の根元を軸に傾ける)
        lean = wob * (i + 1) / 3
        x = 280 + math.sin(math.radians(lean)) * (ground - y)
        put(im, spr(name, 0.12 * t + i * 0.3), x, y, S, sx, sy, -lean)
    # てっぺんにハート
    t0 = 2.35
    if t > t0:
        u = (t - t0) / 0.4
        rest = ground - 0.5 * S * 0.42 - 2 * step - 150
        y = -120 + (rest + 120) * min(u, 1) ** 2
        s = bounce_squash(t - t0 - 0.4) if u >= 1 else 0
        x = 280 + math.sin(math.radians(wob)) * (ground - y)
        put(im, spr("heart", 0.4 * t), x, y, 230, 1 + s, 1 - s, -wob)
    return im


def cupcake_pop(t):
    """カップケーキがぽんっと出てきてくるっと回り、ハートがはじける (4秒)."""
    im = Image.new("RGBA", (900, 900), (0, 0, 0, 0))
    cx, cy = 450, 470
    k = ease_out_back(t / 0.4, 2.4)
    # 最初は勢いよく回って、だんだんゆっくり
    rev = 1.2 * ease_out(t / 1.2) + 0.15 * max(0, t - 1.2)
    bob = 12 * math.sin(max(0, t - 0.4) * 3)
    s = bounce_squash(t - 0.4) * 0.6
    # はじけるハート (後ろ半分は本体の奥に)
    hearts = []
    if t > 0.55:
        for j in range(10):
            u = (t - 0.55) / 1.6
            if u > 1:
                continue
            a = j / 10 * 2 * math.pi + 0.3
            r = 90 + 300 * ease_out(u)
            hx, hy = cx + r * math.cos(a), cy - 30 + r * math.sin(a) * 0.85 - 60 * u
            hearts.append((math.sin(a) < -0.2, ("heart", "heart_white")[j % 2], hx, hy, 90 * (1 - 0.4 * u),
                           1 - clamp01((u - 0.6) / 0.4), j))
    for back, n, hx, hy, sz, al, j in hearts:
        if back:
            put(im, spr(n, t * 0.8 + j * 0.1), hx, hy, sz, alpha=al, rot=20 * math.sin(t * 4 + j))
    put(im, spr("cupcake", rev), cx, cy + bob, 520 * k, 1 + s, 1 - s)
    for back, n, hx, hy, sz, al, j in hearts:
        if not back:
            put(im, spr(n, t * 0.8 + j * 0.1), hx, hy, sz, alpha=al, rot=20 * math.sin(t * 4 + j))
    return im


def donut_roll(t):
    """ドーナツが左からころころ転がってきて、止まってぴょん (3.5秒)."""
    im = Image.new("RGBA", (1600, 700), (0, 0, 0, 0))
    S = 540
    r = S * 0.5 * (0.66 + 0.34) / R.RANGE  # 見た目の半径
    ground = 640
    x0, x1 = -S * 0.6, 800
    u = ease_out(t / 1.8)
    x = x0 + (x1 - x0) * u
    ang = -math.degrees((x - x0) / r)  # 転がった距離 = 半径 × 角度
    y = ground - r
    sx = sy = 1.0
    if t > 1.8:  # 止まった反動で左右にゆらゆら
        w = t - 1.8
        ang += 14 * math.exp(-w * 3.5) * math.sin(w * 9)
    if 2.5 < t < 3.1:  # ぴょん
        q = (t - 2.5) / 0.6
        y -= 150 * 4 * q * (1 - q)
        st = 0.08 * (1 - abs(2 * q - 1))
        sx, sy = 1 - st, 1 + st
    elif t >= 3.1:
        s = bounce_squash(t - 3.1)
        sx, sy = 1 + s, 1 - s
    put(im, SPR["donut_front"][0], x, y, S, sx, sy, ang)
    return im


def sweets_orbit(t, dur=4.0):
    """チョコハートのまわりをスイーツがくるくる回る (4秒でループ)."""
    im = Image.new("RGBA", (1000, 900), (0, 0, 0, 0))
    cx, cy = 500, 450
    names = ["macaron", "truffle", "strawberry", "candy_p", "truffle_w", "cookie"]
    items = []
    for i, n in enumerate(names):
        th = 2 * math.pi * (t / dur + i / len(names))
        z = math.sin(th)  # 奥 (-1) ～ 手前 (+1)
        x = cx + 360 * math.cos(th)
        y = cy + 70 * math.sin(th) - 40 * math.cos(th)
        items.append((z, n, x, y, 150 * (0.82 + 0.25 * z), i))
    items.sort()
    for z, n, x, y, sz, i in items:
        if z < 0:
            put(im, spr(n, t / dur * 2 + i * 0.17), x, y, sz, rot=12 * math.sin(2 * math.pi * t / dur + i))
    put(im, spr("choco_heart", t / dur), cx, cy + 14 * math.sin(2 * math.pi * t / dur * 2), 460)
    for z, n, x, y, sz, i in items:
        if z >= 0:
            put(im, spr(n, t / dur * 2 + i * 0.17), x, y, sz, rot=12 * math.sin(2 * math.pi * t / dur + i))
    return im


RAIN = None


def sweets_rain(t, dur=6.0):
    """スイーツがふわふわ降ってくる (1920x1080, 6秒でループ)."""
    global RAIN
    W, H, m = 1920, 1080, 160
    if RAIN is None:
        rnd = random.Random(7)
        RAIN = []
        for i in range(34):
            laps = rnd.choice([1, 1, 2])  # 6秒で画面を何回通るか (ループさせるため整数)
            RAIN.append(dict(n=SMALL[i % len(SMALL)] if rnd.random() > 0.2 else rnd.choice(["heart", "heart_white"]),
                             x=rnd.uniform(40, W - 40), y0=rnd.uniform(0, H + 2 * m), laps=laps,
                             s=rnd.uniform(90, 170) / laps ** 0.3, ph=rnd.random(), rev=rnd.choice([1, 2, -1]),
                             sw=rnd.uniform(15, 45), r0=rnd.uniform(-25, 25)))
        RAIN.sort(key=lambda d: d["s"])  # 小さい (奥) ものから
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for d in RAIN:
        y = (d["y0"] + (H + 2 * m) * d["laps"] * t / dur) % (H + 2 * m) - m
        x = d["x"] + d["sw"] * math.sin(2 * math.pi * (t / dur * 2 + d["ph"]))
        rot = d["r0"] + 15 * math.sin(2 * math.pi * (t / dur * 3 + d["ph"]))
        put(im, spr(d["n"], d["rev"] * t / dur + d["ph"]), x, y, d["s"], rot=rot)
    return im


def gift_surprise(t):
    """プレゼント箱がガタガタ揺れて、ぴょんと跳ねたら中からお菓子が飛び出す (4秒)."""
    im = Image.new("RGBA", (900, 1000), (0, 0, 0, 0))
    S, ground = 540, 960
    ab = bottom("gift")
    cy0 = ground - ab * S
    k = ease_out_back(t / 0.35)
    rot, y, sx, sy = 0.0, 0.0, 1.0, 1.0
    if 0.6 < t < 1.6:  # ガタガタ (だんだん強く)
        q = (t - 0.6) / 1.0
        rot = 9 * q * math.sin(t * 50)
        s = 0.04 * q * abs(math.sin(t * 25))
        sx, sy = 1 + s, 1 - s
    if 1.6 <= t < 1.75:  # ため
        q = (t - 1.6) / 0.15
        sx, sy = 1 + 0.15 * q, 1 - 0.15 * q
    if 1.75 <= t < 2.3:  # ジャンプ
        q = (t - 1.75) / 0.55
        y = -170 * 4 * q * (1 - q)
        sx, sy = 0.92, 1.1
    if t >= 2.3:
        s = bounce_squash(t - 2.3)
        sx, sy = 1 + s, 1 - s
    # 飛び出すお菓子 (放物線)。上がっている間は箱の奥、落ちてくると手前
    pops = []
    if t > 1.85:
        rnd = random.Random(3)
        for j in range(9):
            t0 = 1.85 + j * 0.05
            u = t - t0
            if u < 0:
                continue
            vx = rnd.uniform(-250, 250)
            vy = rnd.uniform(-1650, -1300)
            n = rnd.choice(SMALL + ["heart", "heart"])
            px = 450 + vx * u
            py = cy0 - 60 + vy * u + 1100 * u * u
            al = 1 - clamp01((u - 1.5) / 0.3)
            pops.append((vy + 2200 * u > 0, n, px, py, rnd.uniform(150, 210), al, rnd.uniform(-1.5, 1.5) * u))
    for front, n, px, py, sz, al, rv in pops:
        if not front:
            put(im, spr(n, rv), px, py, sz, alpha=al, rot=rv * 60)
    put(im, spr("gift", 0.08 * t + 0.05), 450, cy0 + y, S * k, sx, sy, rot, anchor_bottom=ab)
    for front, n, px, py, sz, al, rv in pops:
        if front:
            put(im, spr(n, rv), px, py, sz, alpha=al, rot=rv * 60)
    return im


CLIPS = {
    "ichigo_bounce": (ichigo_bounce, 4.0),
    "macaron_tower": (macaron_tower, 4.0),
    "cupcake_pop": (cupcake_pop, 4.0),
    "donut_roll": (donut_roll, 3.5),
    "sweets_orbit": (sweets_orbit, 4.0),
    "sweets_rain": (sweets_rain, 6.0),
    "gift_surprise": (gift_surprise, 4.0),
}


# ---------------------------------------------------------------- 書き出し
def _init(cache):
    for name, (size, n) in SPEC.items():
        SPR[name] = [Image.open(os.path.join(cache, f"{name}_{size}_{i:02d}.png")).convert("RGBA") for i in range(n)]


def _frame(job):
    name, i = job
    fn, _ = CLIPS[name]
    return fn(i / FPS).tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="clips")
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with Pool(a.jobs) as pool:
        R.build_sprites(pool, a.cache, SPEC)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    with Pool(a.jobs, initializer=_init, initargs=(a.cache,)) as pool:
        _init(a.cache)
        for name, (fn, dur) in CLIPS.items():
            if a.only and name not in a.only:
                continue
            n = round(dur * FPS)
            frames = pool.map(_frame, [(name, i) for i in range(n)])
            w, h = fn(0).size
            base = os.path.join(a.out, name)
            raw = ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-"]
            for args in ([*raw, "-f", "lavfi", "-i", f"color=0x00FF00:s={w}x{h}:r={FPS}",
                          "-filter_complex", "[1][0]overlay=shortest=1,format=yuv420p",
                          "-c:v", "libx264", "-crf", "16", "-movflags", "+faststart", base + "_greenback.mp4"],
                         [*raw, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
                          "-row-mt", "1", "-auto-alt-ref", "0", base + ".webm"]):
                p = subprocess.Popen([ff, "-y", "-v", "error", *args], stdin=subprocess.PIPE)
                for fb in frames:
                    p.stdin.write(fb)
                p.stdin.close()
                p.wait()
            Image.frombytes("RGBA", (w, h), frames[int(n * 0.6)]).save(base + ".png")
            print("done", name, n, "frames", (w, h), flush=True)


if __name__ == "__main__":
    main()
