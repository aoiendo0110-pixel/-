"""動く3Dチョコレート素材 (Blender Cycles) をグリーンバックで書き出す.

  pip install bpy
  python3 choco3d_clips.py --out clips/choco3d [--only bar heart truffle snap] [--preview 0 1.5] [--samples 48]

  bar     ハートの型押しの板チョコ + サテンのリボン. 1回転しながらふわふわ (4秒ループ)
  heart   ぷっくりツヤツヤのハートチョコ + ピンクのドリズル. 回りながらゆらゆら (4秒ループ)
  truffle ビター / ホワイト / いちごのトリュフが順にぽよんと跳ねる (4秒ループ)
  snap    板チョコがパキッと割れて2つに分かれ、かけらが飛ぶ (4秒)
床の影は付けない (クロマキーで抜きやすく)。1本ごとに
  <name>_greenback.mp4 (緑 0,255,0) / <name>.webm (背景透過) / <name>.png (確認用)
を出力する。連番PNGは <out>/<name>_frames/ に残るので、途中で止めても続きから描ける。
"""
import argparse
import math
import os
import random
import subprocess
import sys

import bpy
from mathutils import Euler, Matrix, Vector

import props3d as P

FPS = 30
SIZE = 800

DARK = (0.26, 0.12, 0.07)
MILK = (0.42, 0.22, 0.13)
WHITE_C = (1.0, 0.94, 0.84)
STRAW = (1.0, 0.62, 0.74)
DRIZ_PINK = (1.0, 0.58, 0.74)
SATIN = (0.95, 0.36, 0.56)
CHOCO = dict(rough=0.22, coat=0.7)


# ---------------------------------------------------------------- 形
def bar_piece(cols, rows, cell=0.36, depth=0.16, base=0.07, name="bar"):
    """ハートの型押し入りのブロックが並んだ板チョコ (原点が中心). 返り値: パーツのリスト."""
    parts = []
    W_, H_ = cols * cell, rows * cell
    parts.append(P.rbox((0, 0, base / 2), (W_, H_, base), MILK, bevel=0.03, **CHOCO))
    for i in range(cols):
        for j in range(rows):
            x = (i - (cols - 1) / 2) * cell
            y = (j - (rows - 1) / 2) * cell
            parts.append(P.pillow((x, y, base + depth / 2 - 0.01), (cell - 0.035, cell - 0.035, depth), MILK,
                                  round_=0.28, **CHOCO))
            h = P.puffy_heart("h", cell * 0.24, 0.02, MILK, loc=(x, y, base + depth - 0.012), rot=(0, 0, 0),
                              puff=0.016, **CHOCO)
            parts.append(h)
    return parts


def parent_all(parts, name):
    root = P.link(bpy.data.objects.new(name, None))
    for o in parts:
        o.parent = root
    return root


def drizzle_on_heart(size, front_y, n=5, col=DRIZ_PINK):
    """ハートの前面をジグザグに横切るドリズル (ハートの形の内側だけ)."""
    poly = [(x * 0.86, z * 0.86) for x, z in P.heart_xy(size, 80)]

    def inside(x, z):
        c = False
        for (x1, z1), (x2, z2) in zip(poly, poly[1:] + poly[:1]):
            if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1 + 1e-9) + x1:
                c = not c
        return c
    out = []
    for k in range(n):
        z0 = size * (0.62 - k * 0.36)
        seg = []
        for u in range(81):
            x = (u / 80 - 0.5) * size * 2.2
            z = z0 + 0.4 * x + size * 0.06 * math.sin(u * 0.55 + k)
            if inside(x, z):
                seg.append((x, front_y, z))
            elif len(seg) > 2:
                out.append(P.tube(seg, size * 0.03, col, rough=0.3, coat=0.4))
                seg = []
            else:
                seg = []
        if len(seg) > 2:
            out.append(P.tube(seg, size * 0.03, col, rough=0.3, coat=0.4))
    return out


def satin_band(w, h, t, y, col=SATIN):
    """板チョコに巻いたリボン (縦に1周)."""
    return P.rbox((0, y, t / 2 - 0.004), (w + 0.03, 0.16, t + 0.03), col, bevel=0.012, rough=0.35, sheen=0.6)


# ---------------------------------------------------------------- シーン
def setup(cam_loc, target, lens=55):
    P.new_scene()
    P.lights(1.0)
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    cam = P.link(bpy.data.objects.new("cam", bpy.data.cameras.new("cam")))
    cam.data.lens = lens
    cam.location = cam_loc
    d = Vector(target) - Vector(cam_loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    return sc


def ease_out_back(x, s=1.7):
    x = min(max(x, 0.0), 1.0)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def build_bar():
    setup((0, -4.2, 2.2), (0, 0, 0.05), lens=58)
    parts = bar_piece(3, 5)
    parts.append(satin_band(3 * 0.36, 5 * 0.36, 0.23, 0.36))
    parts.append(P.fancy_bow((0, 0.36, 0.34), 0.42, SATIN, rot=(math.radians(-70), 0, 0)))
    root = parent_all([p for p in parts if p.parent is None], "root")

    def pose(t):
        a = 2 * math.pi * t / 4.0
        root.rotation_euler = Euler((math.radians(62), 0, a), "XZY")
        root.rotation_euler = (Matrix.Rotation(math.radians(8) * math.sin(a * 2), 4, "Y")
                               @ Matrix.Rotation(math.radians(58), 4, "X") @ Matrix.Rotation(a, 4, "Z")).to_euler()
        root.location = (0, 0, 0.06 * math.sin(a * 2))
    return pose, 4.0


def build_heart():
    setup((0, -5.6, 0.6), (0, 0, -0.05), lens=58)
    size, depth, puff = 0.95, 0.14, 0.2
    h = P.puffy_heart("ch", size, depth, MILK, loc=(0, 0, 0), puff=puff, **CHOCO)
    dz = drizzle_on_heart(size, -(depth + puff * 0.92)) + drizzle_on_heart(size, depth + puff * 0.92)  # 表と裏
    root = parent_all([h] + dz, "root")

    def pose(t):
        a = 2 * math.pi * t / 4.0
        root.rotation_euler = (Matrix.Rotation(math.radians(10) * math.sin(a), 4, "Y")
                               @ Matrix.Rotation(a, 4, "Z")).to_euler()
        root.location = (0, 0, 0.07 * math.sin(a * 2))
    return pose, 4.0


def truffle(col, line, kind, x):
    body = P.ball((0, 0, 0.34), 0.36, col, scale=(1, 1, 0.92), **CHOCO)
    parts = [body]
    if kind == "drizzle":
        for k in range(4):
            pts = []
            for u in range(61):
                a = 2 * math.pi * u / 60
                z = 0.42 + 0.08 * k + 0.05 * math.sin(a * 5 + k)
                r = math.sqrt(max(0.0, 0.36 ** 2 - (z - 0.34) ** 2 / 0.92 ** 2)) + 0.012
                pts.append((r * math.cos(a), r * math.sin(a), z))
            parts.append(P.tube(pts, 0.022, line, cyclic=True, rough=0.3, coat=0.4))
    else:  # いちご: 上にカラースプレー
        rnd = random.Random(3)
        for _ in range(70):
            a, b = rnd.uniform(0, 2 * math.pi), rnd.uniform(0.15, 0.95)
            pz = 0.34 + 0.33 * math.cos(b * math.pi / 2)
            pr = 0.36 * math.sin(b * math.pi / 2) + 0.01
            o = P.rbox((pr * math.cos(a), pr * math.sin(a), pz), (0.07, 0.022, 0.022),
                       rnd.choice([(1, 1, 1), (1, 0.85, 0.4), (0.42, 0.22, 0.13), (1, 0.4, 0.6)]), bevel=0.008,
                       rot=(rnd.uniform(0, 3), rnd.uniform(0, 3), a), rough=0.3)
            parts.append(o)
    parts.append(P.ball((0, 0, 0.74), 0.06, line, rough=0.2, coat=0.6))
    root = parent_all(parts, "t")
    root.location = (x, 0, 0)
    return root


def build_truffle():
    setup((0, -3.9, 1.5), (0, 0, 0.45), lens=44)
    ts = [truffle(DARK, DRIZ_PINK, "drizzle", -0.95), truffle(WHITE_C, MILK, "drizzle", 0.0),
          truffle(STRAW, (1, 1, 1), "sprinkle", 0.95)]

    def pose(t):
        for i, o in enumerate(ts):
            ph = ((t / 4.0) * 2 - i / 6) % 1  # 2秒に1回ずつ、順に跳ねる
            jump = 0.0
            sx = sz = 1.0
            if ph < 0.32:  # 空中
                u = ph / 0.32
                jump = 0.75 * 4 * u * (1 - u)
                st = 0.12 * (1 - abs(2 * u - 1))
                sx, sz = 1 - st, 1 + st
            elif ph < 0.45:  # 着地の潰れ
                u = (ph - 0.32) / 0.13
                s = 0.2 * math.exp(-u * 4) * math.cos(u * 9)
                sx, sz = 1 + s, 1 - s
            o.location.z = jump
            o.scale = (sx, sx, sz)
            o.rotation_euler = (0, 0, 2 * math.pi * (t / 4.0) * (1 if i % 2 else -1) + i)
    return pose, 4.0


def build_snap():
    setup((0, -4.0, 2.3), (0, 0, 0.1), lens=60)
    cell = 0.36
    left = parent_all([p for p in bar_piece(3, 2, cell) if p.parent is None], "L")
    right = parent_all([p for p in bar_piece(3, 2, cell) if p.parent is None], "R")
    rnd = random.Random(8)
    crumbs = []
    for _ in range(14):
        s = rnd.uniform(0.03, 0.07)
        o = P.rbox((0, 0, 0.1), (s, s * rnd.uniform(0.6, 1.2), s), MILK, bevel=0.006, **CHOCO)
        crumbs.append(dict(o=o, v=Vector((rnd.uniform(-0.8, 0.8), rnd.uniform(-1.4, -0.4), rnd.uniform(1.2, 2.4))),
                           w=Vector((rnd.uniform(-9, 9), rnd.uniform(-9, 9), rnd.uniform(-9, 9))),
                           p0=Vector((rnd.uniform(-0.5, 0.5), 0, rnd.uniform(0.05, 0.2)))))
    base_rot = Matrix.Rotation(math.radians(58), 4, "X")

    def pose(t):
        snap = 1.2
        u = max(0.0, t - snap)
        # 割れる前は少し曲がってプルプル
        bend = math.radians(6) * min(1, t / snap) ** 3 if t < snap else 0
        shake = math.radians(1.5) * math.sin(t * 60) * (min(1, t / snap) ** 2) if t < snap else 0
        sep = 0.0 if t < snap else 0.32 * (1 - math.exp(-u * 3.2))
        tilt = 0.0 if t < snap else math.radians(28) * (1 - math.exp(-u * 4)) + math.radians(4) * math.sin(u * 3)
        for side, o in ((-1, left), (1, right)):
            o.location = base_rot @ Vector((0, side * (cell + sep), 0)) + Vector((0, 0, 0.05 * math.sin(u * 2.5)))
            rot = (base_rot @ Matrix.Rotation(side * (bend + tilt) + shake, 4, "X")
                   @ Matrix.Rotation(side * math.radians(6) * (1 - math.exp(-u * 3)), 4, "Z"))
            o.rotation_euler = rot.to_euler()
        for c in crumbs:
            o = c["o"]
            if t < snap:
                o.hide_render = True
                continue
            o.hide_render = u > 2.2
            p = c["p0"] + c["v"] * u + Vector((0, 0, -4.0)) * (u * u / 2)
            o.location = base_rot @ Vector((p.x, 0, 0)) + Vector((0, p.y * 0.6, p.z + 0.15))
            o.rotation_euler = (c["w"] * u).to_tuple()
    return pose, 4.0


CLIPS = {"bar": build_bar, "heart": build_heart, "truffle": build_truffle, "snap": build_snap}


# ---------------------------------------------------------------- 書き出し
def render_clip(name, out, samples, preview):
    pose, dur = CLIPS[name]()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.15
    fdir = os.path.join(out, name + "_frames")
    os.makedirs(fdir, exist_ok=True)
    n = round(dur * FPS)
    frames = [round(x * FPS) for x in preview] if preview else range(n)
    for i in frames:
        path = os.path.join(fdir, f"{i:04d}.png")
        if os.path.exists(path) and not preview:  # 途中で止めても続きから
            continue
        pose(i / FPS)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(name, i, "/", n, flush=True)
    if preview:
        return
    ff = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    seq = os.path.join(fdir, "%04d.png")
    base = os.path.join(out, name)
    subprocess.run([ff, "-y", "-v", "error", "-framerate", str(FPS), "-i", seq, "-f", "lavfi", "-i",
                    f"color=0x00FF00:s={SIZE}x{SIZE}:r={FPS}", "-filter_complex",
                    "[1][0]overlay=shortest=1,format=yuv420p", "-c:v", "libx264", "-crf", "16", "-movflags",
                    "+faststart", base + "_greenback.mp4"], check=True)
    subprocess.run([ff, "-y", "-v", "error", "-framerate", str(FPS), "-i", seq, "-c:v", "libvpx-vp9", "-pix_fmt",
                    "yuva420p", "-b:v", "0", "-crf", "24", "-row-mt", "1", "-auto-alt-ref", "0", base + ".webm"],
                   check=True)
    from PIL import Image
    Image.open(os.path.join(fdir, f"{int(n * 0.35):04d}.png")).save(base + ".png")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="clips/choco3d")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--preview", type=float, nargs="*", help="指定秒のコマだけ描く")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for name in CLIPS:
        if a.only and name not in a.only:
            continue
        render_clip(name, a.out, a.samples, a.preview)
        print("done", name, flush=True)


if __name__ == "__main__":
    main()
