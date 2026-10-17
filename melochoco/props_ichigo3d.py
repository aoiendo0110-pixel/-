"""ショートケーキ・いちご・ケーキ作り・カフェの3Dモデル → 透過PNG (Blender Cycles).

  pip install bpy
  python3 props_ichigo3d.py --out props_ichigo [--only strawberry cake] [--samples 64]

kote_chui_vertical_ichigo.py の飾りに使う. いちごはヘタ (緑) を付けず、上にホイップをのせる (グリーンバック対策).
  strawberry  いちご (種のつぶつぶ + ホイップ)
  cream       星口金で絞ったホイップ
  cake        ショートケーキの一切れ (スポンジ / クリーム / いちごの断面 + 上にホイップといちご)
  latte       ソーサー付きのラテ (ハートのラテアート)
  whisk       ホイップのついた泡立て器
  bowl        ホイップの入ったボウル
  bag         絞り袋 (先からホイップ)
  bow         サテンのリボン
"""
import argparse
import math
import os
import random
import sys

import bpy
import bmesh  # noqa: E402  (bpy を読み込んだ後でないと使えない)
from mathutils import Vector

import props3d as P

RED = (0.86, 0.06, 0.16)
SEED = (1.0, 0.86, 0.45)
CREAM = (0.92, 0.87, 0.83)
SPONGE = (0.98, 0.8, 0.5)
SPONGE_D = (0.86, 0.6, 0.3)
PINK = (1.0, 0.62, 0.78)
HOT = (0.95, 0.36, 0.58)
STEEL = (0.92, 0.9, 0.93)
COFFEE = (0.62, 0.4, 0.26)

BERRY = dict(rough=0.18, coat=0.8, sss=0.15)
WHIP = dict(rough=0.42, sss=0.2)
GLAZE = dict(rough=0.25, coat=0.5)


def star(n=8, depth=0.12):
    """星口金のギザギザ (rmod 用)."""
    return lambda th, i: 1 - depth * (0.5 + 0.5 * math.cos(th * n))


# ---------------------------------------------------------------- 部品
def cream_swirl(loc=(0, 0, 0), s=1.0, twist=1.6):
    """ねじれたホイップ. 下は太く、上で先がとがる."""
    prof = []
    N = 26
    for i in range(N + 1):
        v = i / N
        r = 0.32 * (1 - v) ** 0.8 * (1 + 0.18 * math.sin(v * math.pi * 3.2)) + 0.004
        prof.append((r * s, 0.48 * v * s))
    o = P.lathe("cream", prof, CREAM, loc=loc, n=96,
                rmod=lambda th, i: 1 - 0.3 * (0.5 + 0.5 * math.cos(th * 8 + twist * i / 6)) ** 2, **WHIP)
    P.smooth(o)
    return o


def strawberry(loc=(0, 0, 0), s=1.0, with_cream=True, rnd=None):
    rnd = rnd or random.Random(1)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3 * s, location=loc, segments=48, ring_count=32)
    o = bpy.context.active_object
    for v in o.data.vertices:  # 下へいくほど細い、いちごの形
        z = v.co.z / (0.3 * s)
        k = 1 - 0.42 * max(0.0, -z) ** 1.3
        v.co.x *= k
        v.co.y *= k
        v.co.z *= 1.18 if z < 0 else 0.86
    P.smooth(o)
    o.data.materials.append(P.M(RED, **BERRY))
    parts = [o]
    # 種: 表面に小さな粒 (少しくぼませずに、つぶつぶ感を出す)
    me = o.data
    vs = [o.matrix_world @ v.co for v in me.vertices]
    ns = [v.normal for v in me.vertices]
    for j in range(0, len(vs), 11):
        p, nrm = vs[j], ns[j]
        if p.z - loc[2] > 0.18 * s:
            continue
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.009 * s, location=p - nrm * 0.003 * s, segments=8,
                                             ring_count=6)
        sd = bpy.context.active_object
        sd.scale = (1, 1, 0.6)
        sd.rotation_euler = nrm.to_track_quat("Z", "Y").to_euler()
        sd.data.materials.append(P.M(SEED, rough=0.3))
        parts.append(sd)
    if with_cream:
        parts.append(cream_swirl((loc[0], loc[1], loc[2] + 0.2 * s), 0.55 * s))
    return parts


def wedge(z0, z1, col, r=1.0, ang=38, inset=0.0, **kw):
    """ケーキの一切れの形 (扇形の柱). 先が手前 (−y)."""
    bm = bmesh.new()
    a0, a1 = math.radians(90 - ang / 2), math.radians(90 + ang / 2)
    tip = Vector((0, -0.55 * r, 0))
    ring = [tip] + [tip + Vector((math.cos(a0 + (a1 - a0) * i / 20), math.sin(a0 + (a1 - a0) * i / 20), 0)) *
                    (r - inset) for i in range(21)]
    bot = [bm.verts.new((p.x, p.y, z0)) for p in ring]
    top = [bm.verts.new((p.x, p.y, z1)) for p in ring]
    bm.faces.new(bot[::-1])
    bm.faces.new(top)
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    me = bpy.data.meshes.new("w")
    bm.to_mesh(me)
    bm.free()
    o = P.link(bpy.data.objects.new("w", me))
    b = o.modifiers.new("b", "BEVEL")
    b.width = 0.012
    b.segments = 3
    o.data.materials.append(P.M(col, **kw))
    return o


def build_cake():
    # 層: スポンジ / クリーム / スポンジ / クリーム (上)
    wedge(0.0, 0.16, SPONGE, rough=0.8)
    wedge(0.16, 0.24, CREAM, inset=-0.005, **WHIP)
    wedge(0.24, 0.40, SPONGE, rough=0.8)
    wedge(0.40, 0.48, CREAM, inset=-0.01, **WHIP)
    # 側面 (手前の2面) に見えるいちごの断面
    a0 = math.radians(90 - 19)
    for side in (-1, 1):
        for k in range(4):
            u = 0.22 + k * 0.2
            tip = Vector((0, -0.55, 0))
            edge = Vector((side * math.cos(a0), math.sin(a0), 0)) if side > 0 else Vector((-math.cos(a0), math.sin(a0), 0))
            p = tip + edge * u
            nrm = Vector((edge.y, -edge.x, 0)) * (1 if side > 0 else -1)
            h = P.puffy_heart("sb", 0.045, 0.01, RED, loc=(p.x + nrm.x * 0.008, p.y + nrm.y * 0.008, 0.2), puff=0.008,
                              **BERRY)
            h.rotation_euler = (math.pi / 2, 0, math.atan2(nrm.y, nrm.x) - math.pi / 2)
            h.scale = (1, 1, 1)
    # 上: ホイップといちご
    cream_swirl((0, 0.25, 0.48), 0.42)
    strawberry((0, 0.25, 0.68), 0.55, with_cream=False)
    for x in (-0.2, 0.2):
        cream_swirl((x, 0.55, 0.48), 0.28)
    P.TILT = math.radians(26)


def build_strawberry():
    strawberry((0, 0, 0.36), 1.0)
    P.TILT = math.radians(14)


def build_cream():
    cream_swirl((0, 0, 0), 1.0)
    P.TILT = math.radians(18)


def build_latte():
    cup = [(0.0, 0.03), (0.2, 0.03), (0.26, 0.08), (0.32, 0.22), (0.36, 0.42), (0.37, 0.48), (0.35, 0.48),
           (0.34, 0.43), (0.3, 0.22), (0.0, 0.2)]
    P.lathe("cup", cup, PINK, n=96, **GLAZE)
    P.lathe("coffee", [(0.0, 0.43), (0.335, 0.43), (0.335, 0.44), (0.0, 0.44)], COFFEE, n=96, rough=0.35)
    h = P.puffy_heart("art", 0.11, 0.004, CREAM, loc=(0, 0.0, 0.445), rot=(0, 0, 0), puff=0.004, rough=0.5)
    h.rotation_euler = (0, 0, math.pi)
    P.lathe("saucer", [(0.0, 0.0), (0.5, 0.0), (0.56, 0.05), (0.54, 0.06), (0.32, 0.035), (0.0, 0.035)], PINK,
            n=96, **GLAZE)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.11, minor_radius=0.03, location=(0.42, 0, 0.3),
                                     rotation=(math.pi / 2, 0, 0))
    t = bpy.context.active_object
    P.smooth(t)
    t.data.materials.append(P.M(PINK, **GLAZE))
    for k in range(8):  # 白い水玉
        a = 2 * math.pi * k / 8 + 0.2
        if math.cos(a) > 0.92:
            continue
        P.ball((0.345 * math.cos(a), 0.345 * math.sin(a), 0.3), 0.035, CREAM, scale=(1, 1, 1), rough=0.3)
    P.TILT = math.radians(30)


def build_whisk():
    neck, tip = 0.0, -0.75
    for k in range(6):
        th = math.pi * k / 6
        pts = []
        for i in range(41):
            v = i / 40
            r = 0.26 * math.sin(math.pi * v) ** 0.75
            z = neck + (tip - neck) * math.sin(math.pi * v / 2) ** 1.2
            pts.append((r * math.cos(th), r * math.sin(th), z))
        pts += [(-x, -y, z) for x, y, z in pts[::-1]][1:]
        P.tube(pts, 0.012, STEEL, rough=0.15, metal=1.0)
    P.lathe("handle", [(0.0, 0.0), (0.05, 0.0), (0.055, 0.15), (0.05, 0.5), (0.055, 0.54), (0.0, 0.56)], HOT, n=48,
            **GLAZE)
    P.lathe("ring", [(0.04, -0.02), (0.065, -0.02), (0.065, 0.02), (0.04, 0.02)], STEEL, n=48, rough=0.15, metal=1)
    P.ball((0, 0, tip + 0.12), 0.2, CREAM, scale=(1, 1, 0.75), **WHIP)
    cream_swirl((0, 0, tip + 0.18), 0.4)
    P.TILT = math.radians(12)


def build_bowl():
    P.lathe("bowl", [(0.0, 0.0), (0.18, 0.0), (0.2, 0.02), (0.4, 0.12), (0.52, 0.3), (0.55, 0.36), (0.52, 0.37),
                     (0.49, 0.31), (0.38, 0.15), (0.0, 0.06)], PINK, n=96, **GLAZE)
    P.lathe("whip", [(0.0, 0.2), (0.49, 0.28), (0.4, 0.36), (0.25, 0.42), (0.0, 0.44)], CREAM, n=96,
            rmod=lambda th, i: 1 + 0.05 * math.sin(th * 7 + i), **WHIP)
    cream_swirl((0.05, 0.0, 0.4), 0.5)
    for k in range(10):
        a = 2 * math.pi * k / 10
        P.ball((0.47 * math.cos(a), 0.47 * math.sin(a), 0.2), 0.03, CREAM, rough=0.3)
    P.TILT = math.radians(30)


def build_bag():
    o = P.lathe("bag", [(0.0, -0.5), (0.03, -0.5), (0.2, -0.05), (0.26, 0.15), (0.12, 0.28), (0.07, 0.36),
                        (0.0, 0.38)], PINK, n=64, rmod=lambda th, i: 1 + 0.04 * math.sin(th * 6), rough=0.3, coat=0.4)
    P.lathe("nozzle", [(0.0, -0.6), (0.035, -0.6), (0.06, -0.46), (0.0, -0.46)], STEEL, n=48, rough=0.15, metal=1)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.08, minor_radius=0.03, location=(0, 0, 0.3))
    t = bpy.context.active_object
    t.data.materials.append(P.M(HOT, rough=0.35, sheen=0.5))
    P.smooth(t)
    c = cream_swirl((0, 0, -0.62), 0.5)
    c.rotation_euler = (math.pi, 0, 0)
    for ob in list(bpy.context.scene.objects):
        if ob.type in ("MESH", "CURVE"):
            ob.rotation_euler.rotate_axis("Y", math.radians(-38))
            ob.location.rotate(__import__("mathutils").Euler((0, math.radians(-38), 0)))
    P.TILT = math.radians(10)


def build_bow():
    P.fancy_bow((0, 0, 0), 1.0, HOT, rot=(math.radians(-12), 0, 0), knot=(1.0, 0.82, 0.86))
    P.TILT = math.radians(6)


ITEMS = {"strawberry": build_strawberry, "cream": build_cream, "cake": build_cake, "latte": build_latte,
         "whisk": build_whisk, "bowl": build_bowl, "bag": build_bag, "bow": build_bow}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="props_ichigo")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--samples", type=int, default=64)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for name, fn in ITEMS.items():
        if a.only and name not in a.only:
            continue
        P.new_scene()
        P.TILT = math.radians(10)
        fn()
        P.lights(1.0)
        P.camera_front(pad=0.05)
        bpy.context.scene.view_settings.exposure = 0.0
        bpy.context.scene["exp_set"] = 1
        P.render(os.path.abspath(os.path.join(a.out, name + ".png")), samples=a.samples)
        print("done", name, flush=True)


if __name__ == "__main__":
    main()
