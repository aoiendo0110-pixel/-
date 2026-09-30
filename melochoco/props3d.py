"""ロリータ×バレンタインのカフェ家具 3Dモデル → 正面からの透過PNG (Blender Cycles).

  python3 props3d.py --out props_out --font Mochiy.ttf [--only sofa table ...] [--preview]

全アイテムを同じ縮尺 (PPU ピクセル/メートル)・同じ角度・同じライティングでレンダリングするので、
そのまま並べて合成してもサイズ感と光が揃う。床の影はシャドウキャッチャーで透過PNGに含める。
"""
import argparse
import math
import os
import random

import bpy
from mathutils import Matrix, Vector

import cafe3d as C

PINK = (1.0, 0.58, 0.74)
LPINK = (1.0, 0.86, 0.91)
HOT = (1.0, 0.38, 0.62)
RED = (0.84, 0.08, 0.2)
BROWN = (0.36, 0.18, 0.11)
DBROWN = (0.2, 0.09, 0.06)
CREAM = (1.0, 0.96, 0.9)
WHITE = (1.0, 1.0, 1.0)
YELLOW = (1.0, 0.85, 0.4)
GOLD = (1.0, 0.78, 0.36)
PEARL = (1.0, 0.95, 0.96)

TILT = math.radians(10)   # 正面から少しだけ見下ろす
PPU = 420                 # 1メートルあたりのピクセル数 (全アイテム共通)
_mats = {}


# ---- マテリアル (Cycles) ----------------------------------------------------------
def M(rgb, rough=0.45, metal=0.0, sheen=0.0, coat=0.0, trans=0.0, emit=0.0, sss=0.0):
    key = (tuple(rgb), rough, metal, sheen, coat, trans, emit, sss)
    if key in _mats:
        return _mats[key]
    m = bpy.data.materials.new(f"M{len(_mats)}")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    col = C.lin(rgb) + (1,)
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
        b.inputs["Sheen Roughness"].default_value = 0.4
        b.inputs["Sheen Tint"].default_value = (1, 1, 1, 1)
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.08
    if trans:
        b.inputs["Transmission Weight"].default_value = trans
        b.inputs["IOR"].default_value = 1.45
    if emit:
        b.inputs["Emission Color"].default_value = col
        b.inputs["Emission Strength"].default_value = emit
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (0.1, 0.05, 0.05)
        b.inputs["Subsurface Scale"].default_value = 0.05
    m.diffuse_color = col
    _mats[key] = m
    return m


def mat_compat(rgb, rough=0.35, metal=0.0):
    """cafe3d のヘルパーから呼ばれる用."""
    return M(rgb, rough, metal, coat=0.3 if rough < 0.3 else 0.0)


C.mat = mat_compat  # cafe3d の形状ヘルパーを Cycles マテリアルで使う

VELVET = dict(rough=0.7, sheen=1.0)
GLOSS = dict(rough=0.25, coat=0.6)
GOLDM = dict(rough=0.22, metal=1.0)


def setmat(o, rgb, **kw):
    o.data.materials.clear()
    o.data.materials.append(M(rgb, **kw))
    return o


def subsurf(o, lv=2):
    m = o.modifiers.new("sub", "SUBSURF")
    m.levels = lv
    m.render_levels = lv
    return o


def smooth(o):
    if o.type == "MESH":
        for p in o.data.polygons:
            p.use_smooth = True
    return o


def link(o):
    bpy.context.collection.objects.link(o)
    return o


def mesh_obj(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return link(bpy.data.objects.new(name, me))


# ---- 形状パーツ --------------------------------------------------------------
def pillow(loc, size, col, round_=0.35, rot=(0, 0, 0), **kw):
    """ふっくらクッション (ベベル + サブディビジョン)."""
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    b = o.modifiers.new("b", "BEVEL")
    b.width = min(size) * round_
    b.segments = 3
    subsurf(o, 2)
    smooth(o)
    o.data.materials.append(M(col, **kw))
    return o


def rbox(loc, size, col, bevel=0.02, rot=(0, 0, 0), **kw):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        b = o.modifiers.new("b", "BEVEL")
        b.width = bevel
        b.segments = 4
        b.harden_normals = True
    smooth(o)
    o.data.materials.append(M(col, **kw))
    return o


def ball(loc, r, col, scale=(1, 1, 1), **kw):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=40, ring_count=20)
    o = bpy.context.active_object
    o.scale = scale
    smooth(o)
    o.data.materials.append(M(col, **kw))
    return o


def tube(pts, r, col, cyclic=False, **kw):
    """点列に沿ったパイプ (パイピングや金の縁取り)."""
    cu = bpy.data.curves.new("tube", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 6
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (q[0], q[1], q[2], 1)
    sp.use_cyclic_u = cyclic
    o = link(bpy.data.objects.new("tube", cu))
    o.data.materials.append(M(col, **kw))
    return o


def heart_xy(size, n=160, half=0):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 16 * size, y / 16 * size))
    for _ in range(3):
        q = []
        for a, b in zip(pts, pts[1:] + pts[:1]):
            q.append((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25))
            q.append((a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))
        pts = q
    return pts


def puffy_heart(name, size, depth, col, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), puff=None, **kw):
    """ぷっくりハート (曲線を押し出し + 大きめのベベル)."""
    o = C.heart_curve(name, size, depth, col, loc=loc, rot=rot, bevel=puff if puff is not None else size * 0.12)
    o.data.bevel_resolution = 8
    o.data.materials.clear()
    o.data.materials.append(M(col, **kw))
    return o


def frill_strip(path, height, col, pleats_per_m=22, amp=0.035, scallop=0.025, thick=0.012, **kw):
    """path(=[(x,y)] 上端の水平パス) に沿って垂れ下がるプリーツのフリル. z=0 が上端."""
    L = [0.0]
    for a, b in zip(path, path[1:]):
        L.append(L[-1] + math.dist(a, b))
    total = L[-1]
    n = max(8, int(total * 160))
    rows = 8
    verts, faces = [], []
    for i in range(n + 1):
        s = total * i / n
        k = max(j for j in range(len(L)) if L[j] <= s + 1e-9)
        k = min(k, len(path) - 2)
        u = (s - L[k]) / max(L[k + 1] - L[k], 1e-9)
        x = path[k][0] + (path[k + 1][0] - path[k][0]) * u
        y = path[k][1] + (path[k + 1][1] - path[k][1]) * u
        dx, dy = path[k + 1][0] - path[k][0], path[k + 1][1] - path[k][1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = dy / ln, -dx / ln  # 外向き法線
        ph = math.sin(s * pleats_per_m * 2 * math.pi)
        for r in range(rows + 1):
            v = r / rows
            off = amp * abs(ph) * (0.3 + 0.7 * v) + 0.03 * v
            z = -height * v - (scallop * (1 - abs(math.sin(s * pleats_per_m * math.pi))) if r == rows else 0)
            verts.append((x + nx * off, y + ny * off, z))
    for i in range(n):
        for r in range(rows):
            a = i * (rows + 1) + r
            b = (i + 1) * (rows + 1) + r
            faces.append((a, b, b + 1, a + 1))
    o = mesh_obj("frill", verts, faces)
    sol = o.modifiers.new("s", "SOLIDIFY")
    sol.thickness = thick
    smooth(o)
    o.data.materials.append(M(col, **kw))
    return o


def curvy_leg(loc, h, col=GOLD, flip=1):
    """猫脚 (外に反った金の脚)."""
    pts = []
    for i in range(16):
        u = i / 15
        z = h * (1 - u)
        x = flip * 0.06 * math.sin(u * math.pi * 1.1) - flip * 0.03 * u ** 3
        pts.append((loc[0] + x, loc[1], loc[2] + z))
    t = tube(pts, 0.028, col, **GOLDM)
    ball((pts[-1][0] + flip * 0.01, loc[1], loc[2] + 0.02), 0.035, col, **GOLDM)
    return t


def fancy_bow(loc, s, col, rot=(0, 0, 0), knot=GOLD, **kw):
    """ぷっくりリボン (輪 + 結び目 + V字カットの垂れ)."""
    root = link(bpy.data.objects.new("bow", None))
    root.location = loc
    root.rotation_euler = rot
    root.scale = (s, s, s)
    kw = kw or dict(rough=0.35, sheen=0.4)
    for sx in (-1, 1):
        # 輪: ぷっくりした楕円体
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(sx * 0.36, 0, 0.1), segments=40, ring_count=20)
        o = bpy.context.active_object
        o.scale = (0.4, 0.17, 0.27)
        o.rotation_euler = (0, sx * -0.3, 0)
        smooth(o)
        o.data.materials.append(M(col, **kw))
        o.parent = root
        # 垂れ
        v = []
        f = []
        w0, w1, L = 0.13, 0.17, 0.75
        pts = [(-w0, 0), (w0, 0), (w1, -L), (0, -L + 0.12), (-w1, -L)]
        for (x, z) in pts:
            v.append((x, -0.02, z))
        for (x, z) in pts:
            v.append((x, 0.02, z))
        f = [(0, 1, 2, 3, 4), (9, 8, 7, 6, 5), (0, 5, 6, 1), (1, 6, 7, 2), (2, 7, 8, 3), (3, 8, 9, 4), (4, 9, 5, 0)]
        t = mesh_obj("tail", v, f)
        t.location = (sx * 0.08, 0.06, 0.02)
        t.rotation_euler = (0, sx * 0.45, 0)
        b = t.modifiers.new("b", "BEVEL")
        b.width = 0.012
        b.segments = 3
        t.data.materials.append(M(col, **kw))
        t.parent = root
    k = ball((0, -0.02, 0.06), 0.13, col, scale=(1, 0.8, 1.1), **kw)
    k.parent = root
    g = ball((0, -0.13, 0.06), 0.06, knot, **GOLDM)
    g.parent = root
    return root


def pearl_line(pts, r=0.018, gap=None):
    gap = gap or r * 2.1
    out = []
    acc = 0
    for a, b in zip(pts, pts[1:]):
        d = math.dist(a, b)
        while acc <= d:
            u = acc / d if d else 0
            out.append(tuple(a[i] + (b[i] - a[i]) * u for i in range(3)))
            acc += gap
        acc -= d
    for p in out:
        ball(p, r, PEARL, rough=0.15, coat=1.0)


def lathe(name, profile, col, loc=(0, 0, 0), n=72, rmod=None, **kw):
    o = C.lathe(name, profile, col, loc=loc, n=n, rmod=rmod)
    o.data.materials.clear()
    o.data.materials.append(M(col, **kw))
    return o


# ---- 1. ソファ ----------------------------------------------------------------
def heart_inside(x, y, size):
    """heart_xy(size) の内側なら True (近似)."""
    X, Y = x / size, y / size * 1.0 + 0.05
    return (X * X + Y * Y - 1) ** 3 - X * X * Y ** 3 < 0


def build_sofa():
    W2, D2 = 1.0, 0.45  # 半幅, 半奥行き
    # 土台
    rbox((0, 0, 0.32), (2 * W2, 2 * D2, 0.26), PINK, bevel=0.07, **VELVET)
    # 二重のフリルスカート + 金のライン
    path = [(-W2 - 0.03, D2 * 0.5), (-W2 - 0.03, -D2 - 0.03), (W2 + 0.03, -D2 - 0.03), (W2 + 0.03, D2 * 0.5)]
    f = frill_strip(path, 0.26, WHITE, pleats_per_m=16, amp=0.04, scallop=0.03, rough=0.6, sheen=0.5)
    f.location.z = 0.42
    f = frill_strip([(x, y - 0.01) for x, y in path], 0.17, HOT, pleats_per_m=12, amp=0.055, scallop=0.035,
                    rough=0.55, sheen=0.9)
    f.location.z = 0.44
    tube([(-W2 - 0.05, -D2 - 0.07, 0.44), (W2 + 0.05, -D2 - 0.07, 0.44)], 0.02, GOLD, **GOLDM)
    pearl_line([(-W2 + 0.05, -D2 - 0.09, 0.3), (W2 - 0.05, -D2 - 0.09, 0.3)], 0.014)
    # 座面クッション (2つ)
    for sx in (-1, 1):
        pillow((sx * W2 / 2, -0.03, 0.55), (W2 - 0.03, 2 * D2 - 0.05, 0.22), PINK, round_=0.32, **VELVET)
    # ハートの背もたれ
    size, dep, puff = 0.98, 0.1, 0.13
    back = C.heart_curve("back", size, dep, PINK, loc=(0, D2 - 0.12, 1.08), rot=(math.pi / 2 + 0.1, 0, 0),
                         bevel=puff)
    back.data.bevel_resolution = 10
    back.data.materials.clear()
    back.data.materials.append(M(PINK, **VELVET))
    back.scale = (1.1, 0.8, 1.0)
    bpy.context.view_layer.update()
    mw = back.matrix_world.copy()
    front = dep + puff  # 前面 (ローカル z)
    # 金のパイピング (背もたれのフチの少し内側)
    pip = C.heart_curve("pipe", size * 0.9, 0.0, GOLD, loc=(0, 0, 0), rot=(0, 0, 0), bevel=0.0)
    pip.data.fill_mode = "NONE"
    pip.data.extrude = 0
    pip.data.bevel_depth = 0.022
    pip.data.bevel_resolution = 6
    pip.data.materials.clear()
    pip.data.materials.append(M(GOLD, **GOLDM))
    pip.matrix_world = mw @ Matrix.Translation((0, 0, front + 0.008))
    # タフティング (パールのボタン + くぼみ)
    for iy in range(-5, 7):
        for ix in range(-6, 7):
            x = ix * 0.2 + (iy % 2) * 0.1
            y = iy * 0.17
            if not heart_inside(x, y - size * 0.1, size * 0.8):
                continue
            p = mw @ Vector((x, y, front + 0.005))
            ball(tuple(p), 0.03, (0.93, 0.5, 0.64), scale=(1, 0.3, 1), rough=0.8)
            q = mw @ Vector((x, y, front + 0.018))
            ball(tuple(q), 0.021, PEARL, rough=0.15, coat=1.0)
    fancy_bow(tuple(mw @ Vector((0, size * 0.72, front + 0.05))), 0.34, RED)
    # アーム (ロール)
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=2 * D2 + 0.02, location=(sx * (W2 + 0.03), 0, 0.66),
                                            rotation=(math.pi / 2, 0, 0), vertices=64)
        o = bpy.context.active_object
        b = o.modifiers.new("b", "BEVEL")
        b.width = 0.06
        b.segments = 6
        smooth(o)
        o.data.materials.append(M(PINK, **VELVET))
        rbox((sx * (W2 + 0.03), 0, 0.5), (0.27, 2 * D2 + 0.02, 0.34), PINK, bevel=0.06, **VELVET)
        bpy.ops.mesh.primitive_cylinder_add(radius=0.11, depth=0.03, location=(sx * (W2 + 0.03), -D2 - 0.02, 0.66),
                                            rotation=(math.pi / 2, 0, 0), vertices=64)
        o = bpy.context.active_object
        smooth(o)
        o.data.materials.append(M(HOT, **VELVET))
        ring = [(sx * (W2 + 0.03) + 0.11 * math.cos(a), -D2 - 0.04, 0.66 + 0.11 * math.sin(a)) for a in
                [2 * math.pi * k / 48 for k in range(49)]]
        tube(ring, 0.012, GOLD, **GOLDM)
        puffy_heart("armh", 0.05, 0.01, RED, loc=(sx * (W2 + 0.03), -D2 - 0.05, 0.66), puff=0.012, **GLOSS)
        fancy_bow((sx * (W2 + 0.05), -D2 + 0.05, 0.86), 0.24, RED, rot=(0, 0, 0))
    # 猫脚
    for sx in (-1, 1):
        for sy in (-1, 1):
            curvy_leg((sx * (W2 - 0.06), sy * (D2 - 0.12), 0.0), 0.22, flip=sx)
    # クッション: ハート (赤) + 丸いフリル (白)
    puffy_heart("cush", 0.26, 0.08, RED, loc=(-0.48, 0.02, 0.93), rot=(math.pi / 2 + 0.22, 0, 0.18), puff=0.08,
                rough=0.55, sheen=0.9)
    fancy_bow((-0.5, -0.12, 1.1), 0.11, WHITE)
    pillow((0.48, 0.0, 0.88), (0.44, 0.15, 0.44), WHITE, round_=0.45, rot=(0.22, 0, -0.12), rough=0.6, sheen=0.6)
    ring = [(0.48 + 0.25 * math.cos(a), -0.1, 0.88 + 0.25 * math.sin(a)) for a in
            [2 * math.pi * k / 90 for k in range(91)]]
    pearl_line(ring, 0.015)
    puffy_heart("cush2", 0.08, 0.02, HOT, loc=(0.48, -0.1, 0.88), rot=(math.pi / 2 + 0.22, 0, -0.12), puff=0.02,
                **GLOSS)


# ---- 2. テーブル ------------------------------------------------------------------
def build_table():
    R = 0.55
    lathe("top", [(R, 0.72), (R + 0.02, 0.74), (R + 0.02, 0.77), (0, 0.775)], WHITE, rough=0.3, coat=0.5)
    # テーブルクロス (ピンクのスカラップ + 白レース)
    lathe("cloth", [(R + 0.11, 0.5), (R + 0.1, 0.6), (R + 0.06, 0.74), (R + 0.03, 0.782), (0, 0.785)], WHITE,
          rmod=lambda th, i: 1 + (0.035 * abs(math.sin(th * 16)) if i < 2 else 0), rough=0.6, sheen=0.5)
    lathe("cloth2", [(R + 0.07, 0.6), (R + 0.06, 0.68), (R + 0.035, 0.76), (0, 0.79)], PINK,
          rmod=lambda th, i: 1 + (0.05 * abs(math.sin(th * 10)) if i < 2 else 0), rough=0.55, sheen=0.8)
    for i in range(10):  # 裾のミニリボン
        a = 2 * math.pi * i / 10 + 0.3
        x, y = (R + 0.1) * math.cos(a), (R + 0.1) * math.sin(a)
        if y < 0.1:
            fancy_bow((x * 0.99, y * 0.99 - 0.01, 0.63), 0.07, RED, rot=(0, 0, a + math.pi / 2))
    # 脚 (金のペデスタル + 3本の猫脚)
    lathe("ped", [(0.06, 0.1), (0.045, 0.2), (0.07, 0.28), (0.035, 0.4), (0.05, 0.5), (0.03, 0.6), (0.08, 0.66),
                  (0.0, 0.67)], GOLD, n=48, **GOLDM)
    for k in range(3):
        a = 2 * math.pi * k / 3 - math.pi / 2
        pts = []
        for i in range(14):
            u = i / 13
            r = 0.04 + 0.32 * u
            z = 0.14 - 0.12 * u + 0.05 * math.sin(u * math.pi)
            pts.append((r * math.cos(a), r * math.sin(a), max(z, 0.025)))
        tube(pts, 0.022, GOLD, **GOLDM)
        ball((pts[-1][0], pts[-1][1], 0.03), 0.035, GOLD, **GOLDM)
    lathe("ball", [(0.0, 0.05), (0.07, 0.1), (0.07, 0.14), (0, 0.18)], GOLD, n=48, **GOLDM)


# ---- 3. 壁 (背景) ---------------------------------------------------------------
def wallpaper_texture(path):
    from PIL import Image, ImageDraw, ImageFilter
    S = 2048
    im = Image.new("RGB", (S, S), (255, 196, 216))
    dr = ImageDraw.Draw(im)
    stripe = S // 8
    for x in range(0, S, stripe):
        dr.rectangle([x, 0, x + stripe // 2, S], fill=(255, 176, 202))
        dr.line([(x + stripe // 2 + 6, 0), (x + stripe // 2 + 6, S)], fill=(255, 250, 252), width=4)
        dr.line([(x - 6, 0), (x - 6, S)], fill=(255, 250, 252), width=4)

    def hp(cx, cy, s):
        return [(cx + 16 * math.sin(t) ** 3 * s / 16, cy - (13 * math.cos(t) - 5 * math.cos(2 * t) -
                 2 * math.cos(3 * t) - math.cos(4 * t)) * s / 16) for t in [2 * math.pi * i / 60 for i in range(60)]]
    for j, y in enumerate(range(stripe // 2, S, stripe)):
        for i, x in enumerate(range(stripe // 4, S, stripe)):
            cx = x + (stripe // 2 if j % 2 else 0)
            cx = cx % S
            dr.polygon(hp(cx, y, 26), fill=(235, 60, 110))
            dr.polygon(hp(cx - 5, y - 6, 7), fill=(255, 200, 220))
            for a in range(8):  # 小花
                ang = a * math.pi / 4
                dr.ellipse([cx + math.cos(ang) * 44 - 4, y + math.sin(ang) * 44 - 4, cx + math.cos(ang) * 44 + 4,
                            y + math.sin(ang) * 44 + 4], fill=(255, 245, 248))
    im = im.filter(ImageFilter.SMOOTH)
    im.save(path)


def tex_M(path, rough=0.7):
    m = bpy.data.materials.new("wall")
    m.use_nodes = True
    nt = m.node_tree
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(path)
    nt.links.new(t.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = rough
    return m


def plane(size, loc, rot, m, uv=(1, 1)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    for lp in o.data.uv_layers.active.data:
        lp.uv = (lp.uv[0] * uv[0], lp.uv[1] * uv[1])
    o.data.materials.append(m)
    return o


def build_wall(texdir):
    os.makedirs(texdir, exist_ok=True)
    wallpaper_texture(f"{texdir}/wallpaper.png")
    Wd, Ht = 6.4, 3.4
    wall = tex_M(f"{texdir}/wallpaper.png")
    plane((Wd, Ht), (0, 0, Ht / 2), (math.pi / 2, 0, 0), wall, (Wd / 1.1, Ht / 1.1))
    # 床 (市松)
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (1024, 1024))
    dr = ImageDraw.Draw(im)
    for i in range(8):
        for j in range(8):
            dr.rectangle([i * 128, j * 128, i * 128 + 128, j * 128 + 128],
                         fill=(255, 196, 214) if (i + j) % 2 else (255, 250, 246))
    im.save(f"{texdir}/floor.png")
    plane((Wd, 3.0), (0, -1.5, 0), (0, 0, 0), tex_M(f"{texdir}/floor.png", 0.35), (Wd / 0.9, 3.0 / 0.9))
    # 腰壁パネル
    y = -0.02
    rbox((0, y, 0.5), (Wd, 0.04, 1.0), WHITE, bevel=0.01, rough=0.4)
    for i in range(-5, 6):
        rbox((i * 0.56, y - 0.03, 0.52), (0.44, 0.03, 0.66), PINK, bevel=0.012, rough=0.45)
        rbox((i * 0.56, y - 0.045, 0.52), (0.36, 0.02, 0.56), WHITE, bevel=0.008, rough=0.4)
    rbox((0, y - 0.05, 1.02), (Wd, 0.08, 0.06), HOT, bevel=0.015, rough=0.35, coat=0.4)
    tube([(-Wd / 2, y - 0.1, 1.02), (Wd / 2, y - 0.1, 1.02)], 0.012, GOLD, **GOLDM)
    rbox((0, y - 0.04, 0.06), (Wd, 0.06, 0.12), BROWN, bevel=0.01, rough=0.35, coat=0.4)
    # 天井の廻り縁 + スカラップの飾り + パール
    rbox((0, y - 0.06, Ht - 0.08), (Wd, 0.14, 0.16), WHITE, bevel=0.02, rough=0.4)
    for i in range(-8, 9):
        x = i * 0.4
        o = ball((x, y - 0.09, Ht - 0.24), 0.2, HOT, scale=(1, 0.18, 0.55), rough=0.6, sheen=0.8)
        pts = [(x - 0.2 + 0.4 * u, y - 0.14, Ht - 0.28 - 0.1 * math.sin(math.pi * u)) for u in
               [k / 10 for k in range(11)]]
        pearl_line(pts, 0.014)
        if i % 2 == 0:
            fancy_bow((x - 0.2, y - 0.15, Ht - 0.2), 0.1, RED)
    # アーチ窓 + カーテン
    wx, wz, ww, wh = 0.0, 1.8, 1.2, 1.0
    arch = [(wx + ww / 2 * math.cos(a), wz + wh / 2 - 0.1 + ww / 2 * math.sin(a)) for a in
            [math.pi * i / 40 for i in range(41)]]
    outline = [(wx + ww / 2, wz - wh / 2)] + arch + [(wx - ww / 2, wz - wh / 2)]
    # 窓ガラス (空色 + 雲っぽいグラデ)
    v = [(x, y - 0.01, z) for x, z in outline]
    g = mesh_obj("glass", v, [tuple(range(len(v)))])
    g.data.materials.append(M((0.85, 0.94, 1.0), rough=0.1, emit=0.6))
    tube([(x, y - 0.04, z) for x, z in outline] + [(outline[0][0], y - 0.04, outline[0][1])], 0.05, WHITE,
         rough=0.35)
    tube([(wx, y - 0.05, wz - wh / 2), (wx, y - 0.05, wz + wh / 2 - 0.1 + ww / 2)], 0.02, WHITE, rough=0.35)
    tube([(wx - ww / 2, y - 0.05, wz + 0.05), (wx + ww / 2, y - 0.05, wz + 0.05)], 0.02, WHITE, rough=0.35)
    rbox((wx, y - 0.1, wz - wh / 2 - 0.04), (ww + 0.3, 0.16, 0.06), WHITE, bevel=0.015, rough=0.35)
    for side in (-1, 1):
        verts, faces = [], []
        nx, nz = 40, 30
        top, bot = wz + wh / 2 + ww / 2 + 0.05, wz - wh / 2 - 0.35
        for iz in range(nz + 1):
            z = top - (top - bot) * iz / nz
            pinch = 1 - 0.6 * math.exp(-((z - (wz - 0.15)) / 0.28) ** 2)
            for ix in range(nx + 1):
                u = ix / nx
                x = side * (ww / 2 - 0.05 + 0.55 * u * pinch + 0.02)
                yy = y - 0.12 - 0.05 * abs(math.sin(u * 14)) * (0.4 + 0.6 * pinch)
                verts.append((x, yy, z))
        for iz in range(nz):
            for ix in range(nx):
                a = iz * (nx + 1) + ix
                faces.append((a, a + 1, a + nx + 2, a + nx + 1))
        o = mesh_obj("curtain", verts, faces)
        o.modifiers.new("s", "SOLIDIFY").thickness = 0.01
        smooth(o)
        o.data.materials.append(M(PINK, rough=0.6, sheen=0.9))
        fancy_bow((side * (ww / 2 + 0.25), y - 0.22, wz - 0.15), 0.16, RED)
    # バランス (上のフリル)
    f = frill_strip([(-ww / 2 - 0.7, y - 0.16), (ww / 2 + 0.7, y - 0.16)], 0.32, WHITE, pleats_per_m=10, amp=0.06,
                    rough=0.6, sheen=0.5)
    top = wz + wh / 2 + ww / 2 + 0.1
    f.location.z = top
    f = frill_strip([(-ww / 2 - 0.7, y - 0.2), (ww / 2 + 0.7, y - 0.2)], 0.2, HOT, pleats_per_m=8, amp=0.07,
                    rough=0.6, sheen=0.8)
    f.location.z = top
    fancy_bow((0, y - 0.3, top), 0.26, RED)
    return (Wd, Ht)


# ---- 4. ソファの後ろの家具・小物 -----------------------------------------------
def build_cabinet():
    """お菓子の飾り棚 (ガラス扉)."""
    w, d, h = 1.0, 0.4, 1.7
    t = 0.05  # 板の厚み (中が見える中空の棚)
    wood = dict(rough=0.35, coat=0.3)
    for sx in (-1, 1):
        rbox((sx * (w / 2 - t / 2), 0, h / 2 + 0.1), (t, d, h), WHITE, bevel=0.012, **wood)
    for z in (0.1 + t / 2, h + 0.1 - t / 2):
        rbox((0, 0, z), (w, d, t), WHITE, bevel=0.012, **wood)
    rbox((0, d / 2 - 0.02, h / 2 + 0.1), (w - 0.02, 0.03, h), LPINK, bevel=0.005, rough=0.5)
    rbox((0, -d / 2 + 0.01, 0.1 + 0.07), (w, 0.03, 0.14), WHITE, bevel=0.01, **wood)
    # アーチの頭 + ハートのクレスト
    lathe_top = C.lathe("crown", [(0.0, 0.0), (0.5, 0.0), (0.5, 0.05), (0.0, 0.05)], WHITE)
    lathe_top.data.materials.clear()
    lathe_top.data.materials.append(M(WHITE, rough=0.35))
    lathe_top.location = (0, 0, h + 0.1)
    lathe_top.scale = (1, 0.4, 1)
    arch = [(0.5 * math.cos(a), -d / 2 - 0.02, h + 0.1 + 0.28 * math.sin(a)) for a in
            [math.pi * i / 40 for i in range(41)]]
    v = [(x, y, z) for x, y, z in arch]
    o = mesh_obj("arch", v, [tuple(range(len(v)))])
    o.modifiers.new("s", "SOLIDIFY").thickness = d - 0.04
    o.data.materials.append(M(WHITE, rough=0.35, coat=0.3))
    tube(arch, 0.018, GOLD, **GOLDM)
    puffy_heart("crest", 0.16, 0.05, RED, loc=(0, -d / 2 - 0.05, h + 0.24), puff=0.03, **GLOSS)
    fancy_bow((0, -d / 2 - 0.06, h + 0.42), 0.2, HOT)
    # 棚板と中身
    shelves = [0.45, 0.9, 1.35]
    for z in shelves:
        rbox((0, 0.0, z), (w - 0.12, d - 0.06, 0.03), WHITE, bevel=0.005)
    rnd = random.Random(2)
    for si, z in enumerate([0.16] + shelves):
        for k in range(4):
            x = -0.33 + k * 0.22
            kind = (si + k) % 4
            if kind == 0:  # マカロンタワー小
                for lv in range(4):
                    ball((x, -0.02, z + 0.04 + lv * 0.055), 0.05 - lv * 0.006, [PINK, YELLOW, WHITE, HOT][lv],
                         scale=(1, 1, 0.6), rough=0.5)
            elif kind == 1:  # ジャー
                lathe("jar", [(0.06, z + 0.02), (0.075, z + 0.05), (0.075, z + 0.22), (0.05, z + 0.25),
                              (0, z + 0.25)], (0.95, 0.98, 1.0), loc=(x, -0.02, 0), rough=0.05, trans=0.9)
                for c in range(6):
                    ball((x + rnd.uniform(-0.04, 0.04), -0.02 + rnd.uniform(-0.03, 0.03), z + 0.05 + c * 0.028),
                         0.022, rnd.choice([RED, HOT, YELLOW, WHITE, BROWN]), rough=0.3, coat=0.5)
                ball((x, -0.02, z + 0.27), 0.04, HOT, scale=(1.6, 1.6, 0.5), rough=0.4)
            elif kind == 2:  # ケーキ
                lathe("cake", [(0.09, z + 0.02), (0.09, z + 0.14), (0, z + 0.14)], CREAM, loc=(x, -0.02, 0))
                lathe("icing", [(0.095, z + 0.11), (0.095, z + 0.15), (0, z + 0.155)], PINK, loc=(x, -0.02, 0),
                      rmod=lambda th, i: 1 + (0.06 * math.sin(th * 9) if i == 0 else 0), **GLOSS)
                ball((x, -0.02, z + 0.18), 0.03, RED, **GLOSS)
            else:  # ハートチョコ
                puffy_heart("hc", 0.08, 0.03, BROWN if k % 2 else DBROWN, loc=(x, -0.02, z + 0.11), puff=0.02,
                            **GLOSS)
    # ガラス扉 + 金の取っ手
    for sx in (-1, 1):
        frame = [(sx * 0.235 - 0.225, -d / 2 - 0.025, 0.21), (sx * 0.235 + 0.225, -d / 2 - 0.025, 0.21),
                 (sx * 0.235 + 0.225, -d / 2 - 0.025, h + 0.03), (sx * 0.235 - 0.225, -d / 2 - 0.025, h + 0.03)]
        tube(frame + frame[:1], 0.012, GOLD, **GOLDM)
        ball((sx * 0.03, -d / 2 - 0.04, h / 2 + 0.1), 0.02, GOLD, **GOLDM)
    for sx in (-1, 1):
        curvy_leg((sx * (w / 2 - 0.06), -d / 2 + 0.06, 0.0), 0.12, flip=sx)
        curvy_leg((sx * (w / 2 - 0.06), d / 2 - 0.06, 0.0), 0.12, flip=sx)


def build_lamp():
    """フリンジ付きのフロアランプ."""
    lathe("base", [(0.2, 0.0), (0.2, 0.03), (0.08, 0.08), (0.03, 0.12), (0, 0.12)], GOLD, **GOLDM)
    lathe("pole", [(0.018, 0.1), (0.018, 1.35), (0, 1.35)], GOLD, n=32, **GOLDM)
    for z in (0.4, 0.8, 1.1):
        ball((0, 0, z), 0.035, GOLD, **GOLDM)
    # 電球 (光る)
    ball((0, 0, 1.42), 0.06, (1.0, 0.95, 0.8), emit=6.0)
    # シェード (スカラップ + プリーツ)
    lathe("shade", [(0.34, 1.3), (0.3, 1.4), (0.22, 1.62), (0.2, 1.64), (0, 1.645)], PINK,
          rmod=lambda th, i: 1 + (0.04 * abs(math.sin(th * 14)) if i == 0 else 0.02 * math.sin(th * 28)),
          rough=0.6, sheen=0.9)
    lathe("shade_in", [(0.33, 1.3), (0.2, 1.62)], (1.0, 0.9, 0.8), rough=0.6, emit=0.4)
    # フリンジとパール
    for i in range(60):
        a = 2 * math.pi * i / 60
        r = 0.345 * (1 + 0.04 * abs(math.sin(a * 14)))
        x, y = r * math.cos(a), r * math.sin(a)
        if y > 0.15:
            continue
        tube([(x, y, 1.3), (x * 1.01, y * 1.01, 1.18)], 0.004, WHITE, rough=0.6)
        if i % 3 == 0:
            ball((x * 1.01, y * 1.01, 1.17), 0.012, PEARL, rough=0.15, coat=1.0)
    ring = [(0.21 * math.cos(a), 0.21 * math.sin(a), 1.635) for a in [2 * math.pi * i / 60 for i in range(61)]]
    tube(ring, 0.012, GOLD, **GOLDM)
    fancy_bow((0, -0.33, 1.42), 0.13, RED)


def build_cakestand():
    """背の高い3段ケーキスタンド (ケーキとお菓子入り)."""
    lathe("foot", [(0.18, 0.0), (0.18, 0.03), (0.05, 0.08), (0, 0.08)], GOLD, **GOLDM)
    lathe("pole", [(0.02, 0.05), (0.02, 1.55), (0, 1.55)], GOLD, n=32, **GOLDM)
    tiers = [(0.36, 0.55), (0.28, 0.95), (0.2, 1.3)]
    for ti, (r, z) in enumerate(tiers):
        lathe("plate", [(r * 0.4, z - 0.03), (r, z), (r * 1.03, z + 0.03), (0, z + 0.015)], WHITE,
              rmod=lambda th, i: 1 + 0.04 * abs(math.sin(th * 12)), rough=0.2, coat=0.8)
        ring = [(r * 1.03 * math.cos(a), r * 1.03 * math.sin(a), z + 0.02) for a in
                [2 * math.pi * i / 80 for i in range(81)]]
        tube(ring, 0.008, GOLD, **GOLDM)
        n = 6 - ti
        for k in range(n):
            a = 2 * math.pi * k / n + 0.3
            x, y = math.cos(a) * r * 0.62, math.sin(a) * r * 0.62
            kind = (k + ti) % 3
            if kind == 0:  # マカロン
                col = [PINK, YELLOW, (0.62, 0.4, 0.28), WHITE][(k + ti) % 4]
                ball((x, y, z + 0.05), 0.055, col, scale=(1, 1, 0.55), rough=0.5)
                lathe("f", [(0.048, z + 0.065), (0.048, z + 0.08), (0, z + 0.08)], CREAM, loc=(x, y, 0), n=32)
                ball((x, y, z + 0.1), 0.055, col, scale=(1, 1, 0.55), rough=0.5)
            elif kind == 1:  # いちご
                ball((x, y, z + 0.06), 0.045, RED, scale=(1, 1, 1.25), **GLOSS)
                ball((x, y, z + 0.115), 0.022, (0.35, 0.7, 0.35), scale=(1.4, 1.4, 0.35), rough=0.5)
            else:  # カップケーキ
                lathe("cup", [(0.035, z + 0.01), (0.05, z + 0.07)], HOT, loc=(x, y, 0), n=32,
                      rmod=lambda th, i: 1 + 0.07 * math.cos(th * 16), rough=0.5)
                lathe("cream", [(0.055, z + 0.07), (0.045, z + 0.1), (0.025, z + 0.125), (0, z + 0.14)], CREAM,
                      loc=(x, y, 0), n=32)
                ball((x, y, z + 0.155), 0.018, RED, **GLOSS)
    # 頂上のホールケーキ
    lathe("topcake", [(0.13, 1.33), (0.13, 1.47), (0, 1.47)], CREAM)
    lathe("topicing", [(0.135, 1.42), (0.135, 1.48), (0, 1.49)], PINK,
          rmod=lambda th, i: 1 + (0.07 * math.sin(th * 10) if i == 0 else 0), **GLOSS)
    for k in range(8):
        a = 2 * math.pi * k / 8
        ball((0.09 * math.cos(a), 0.09 * math.sin(a), 1.51), 0.022, RED if k % 2 else WHITE, **GLOSS)
    puffy_heart("topper", 0.07, 0.02, RED, loc=(0, 0, 1.6), puff=0.015, **GLOSS)
    tube([(0, 0, 1.49), (0, 0, 1.56)], 0.004, GOLD, **GOLDM)


def build_balloons():
    """ハートの風船の束."""
    rnd = random.Random(4)
    cols = [RED, HOT, WHITE, PINK, RED, LPINK]
    tops = []
    for i, col in enumerate(cols):
        x = (i - 2.5) * 0.18 + rnd.uniform(-0.05, 0.05)
        z = 1.55 + rnd.uniform(-0.12, 0.25) + (0.15 if i in (2, 3) else 0)
        y = rnd.uniform(-0.1, 0.1)
        puffy_heart("bal", 0.2, 0.12, col, loc=(x, y, z), rot=(math.pi / 2, rnd.uniform(-.2, .2), rnd.uniform(-.25, .25)),
                    puff=0.08, rough=0.12, coat=1.0)
        tops.append((x, y, z - 0.22))
    knot = (0.0, 0.0, 0.25)
    for tx, ty, tz in tops:
        pts = [(tx + (knot[0] - tx) * u + 0.03 * math.sin(u * 9), ty + (knot[1] - ty) * u,
                tz + (knot[2] - tz) * u) for u in [k / 20 for k in range(21)]]
        tube(pts, 0.004, WHITE, rough=0.4)
    fancy_bow((0, -0.02, 0.25), 0.14, RED)
    # 重り (ハートの箱)
    rbox((0, 0, 0.08), (0.16, 0.16, 0.16), PINK, bevel=0.02, rough=0.4)
    rbox((0, 0, 0.08), (0.17, 0.03, 0.17), RED, bevel=0.005)
    rbox((0, 0, 0.08), (0.03, 0.17, 0.17), RED, bevel=0.005)


def build_sidetable():
    """小さいサイドテーブル + ティーセット."""
    R = 0.3
    lathe("top", [(R, 0.6), (R + 0.02, 0.62), (R + 0.02, 0.65), (0, 0.655)], WHITE, rough=0.25, coat=0.6)
    ring = [((R + 0.022) * math.cos(a), (R + 0.022) * math.sin(a), 0.635) for a in
            [2 * math.pi * i / 80 for i in range(81)]]
    tube(ring, 0.01, GOLD, **GOLDM)
    lathe("doily", [(R - 0.02, 0.656), (0, 0.657)], WHITE, rmod=lambda th, i: 1 + 0.05 * abs(math.sin(th * 18)),
          rough=0.7)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pts = [(sx * (0.12 + 0.08 * u + 0.05 * math.sin(u * math.pi)), sy * (0.12 + 0.08 * u), 0.6 - 0.6 * u)
                   for u in [k / 12 for k in range(13)]]
            tube(pts, 0.016, GOLD, **GOLDM)
    # ティーポット
    z0 = 0.657
    lathe("pot", [(0.06, z0), (0.1, z0 + 0.03), (0.12, z0 + 0.1), (0.1, z0 + 0.17), (0.05, z0 + 0.2), (0, z0 + 0.2)],
          WHITE, loc=(-0.08, 0.05, 0), rough=0.15, coat=1.0)
    lathe("lid", [(0.055, z0 + 0.2), (0.03, z0 + 0.24), (0, z0 + 0.25)], PINK, loc=(-0.08, 0.05, 0), **GLOSS)
    ball((-0.08, 0.05, z0 + 0.265), 0.02, GOLD, **GOLDM)
    tube([(-0.19, 0.05, z0 + 0.1), (-0.24, 0.05, z0 + 0.16), (-0.27, 0.05, z0 + 0.2)], 0.014, WHITE, rough=0.15,
         coat=1.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.05, minor_radius=0.012, location=(0.05, 0.05, z0 + 0.11),
                                     rotation=(math.pi / 2, 0, 0))
    o = bpy.context.active_object
    smooth(o)
    o.data.materials.append(M(WHITE, rough=0.15, coat=1.0))
    puffy_heart("potheart", 0.05, 0.01, HOT, loc=(-0.08, -0.07, z0 + 0.1), puff=0.01, **GLOSS)
    # カップ&ソーサー
    for (x, col) in ((0.14, PINK), (0.02, WHITE)):
        y = -0.14
        lathe("saucer", [(0.07, z0), (0.08, z0 + 0.01), (0, z0 + 0.008)], WHITE, loc=(x, y, 0), rough=0.15, coat=1.0)
        lathe("cup", [(0.03, z0 + 0.01), (0.05, z0 + 0.03), (0.055, z0 + 0.07), (0.05, z0 + 0.07),
                      (0.045, z0 + 0.03), (0, z0 + 0.025)], col, loc=(x, y, 0), rough=0.15, coat=1.0)
        lathe("tea", [(0.049, z0 + 0.06), (0, z0 + 0.06)], (0.55, 0.25, 0.15), loc=(x, y, 0), rough=0.05)
    # マカロンの皿
    lathe("plate", [(0.08, z0), (0.09, z0 + 0.012), (0, z0 + 0.01)], WHITE, loc=(0.16, 0.1, 0), rough=0.2)
    for k, col in enumerate((PINK, YELLOW, WHITE)):
        ball((0.13 + k * 0.03, 0.1, z0 + 0.03 + k * 0.012), 0.03, col, scale=(1, 1, 0.6), rough=0.5)


def build_mirror():
    """金フチのハートの鏡 (壁掛け)."""
    puffy_heart("back", 0.5, 0.01, WHITE, loc=(0, 0.02, 1.0), puff=0.01, rough=0.4)
    puffy_heart("mirror", 0.46, 0.005, (0.97, 0.88, 0.93), loc=(0, -0.01, 1.0), puff=0.003, rough=0.04, coat=1.0)
    ring = [(x, -0.03, 1.0 + y + 0.05) for (x, y) in heart_xy(0.5, 160)]
    tube(ring + ring[:1], 0.035, GOLD, **GOLDM)
    ring = [(x, -0.07, 1.0 + y + 0.05) for (x, y) in heart_xy(0.56, 140)]
    pearl_line(ring + ring[:1], 0.014)
    fancy_bow((0, -0.12, 1.52), 0.22, RED)
    for sx in (-1, 1):
        puffy_heart("sidebud", 0.05, 0.02, HOT, loc=(sx * 0.46, -0.08, 1.12), puff=0.01, **GLOSS)


# ---- レンダリング -------------------------------------------------------------
def new_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _mats.clear()
    C._mats.clear()


def lights(scale=1.0):
    def area(loc, rot, size, energy, col):
        l = bpy.data.lights.new("a", "AREA")
        l.size = size * scale
        l.energy = energy * scale * scale
        l.color = col
        o = link(bpy.data.objects.new("a", l))
        o.location = Vector(loc) * scale
        o.rotation_euler = rot
    area((-2.6, -3.2, 3.6), (math.radians(50), 0, math.radians(-40)), 3.0, 420, (1.0, 0.97, 0.95))
    area((3.2, -2.8, 1.8), (math.radians(70), 0, math.radians(48)), 3.0, 160, (1.0, 0.9, 0.94))
    area((0.5, 3.5, 3.8), (math.radians(-45), 0, math.radians(175)), 2.0, 260, (1.0, 0.95, 0.97))
    w = bpy.data.worlds.new("w")
    bpy.context.scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = C.lin((1.0, 0.9, 0.93)) + (1,)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.55


def shadow_catcher():
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    o = bpy.context.active_object
    o.is_shadow_catcher = True
    o.name = "catcher"
    return o


def scene_bbox(exclude=("catcher",)):
    dg = bpy.context.evaluated_depsgraph_get()
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for o in bpy.context.scene.objects:
        if o.type not in ("MESH", "CURVE", "FONT") or o.name.startswith(exclude):
            continue
        ev = o.evaluated_get(dg)
        for c in ev.bound_box:
            w = ev.matrix_world @ Vector(c)
            mn = Vector((min(mn[i], w[i]) for i in range(3)))
            mx = Vector((max(mx[i], w[i]) for i in range(3)))
    return mn, mx


def camera_front(pad=0.06, fixed=None):
    """正面 (少し見下ろし) の正投影カメラ. 縮尺は PPU で固定."""
    sc = bpy.context.scene
    rot = Matrix.Rotation(math.pi / 2 - TILT, 3, "X")
    cam = link(bpy.data.objects.new("cam", bpy.data.cameras.new("cam")))
    cam.data.type = "ORTHO"
    cam.rotation_euler = rot.to_euler()
    sc.camera = cam
    mn, mx = scene_bbox()
    inv = rot.transposed()
    pts = [inv @ Vector((x, y, z)) for x in (mn.x, mx.x) for y in (mn.y, mx.y) for z in (mn.z, mx.z)]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    if fixed:
        wc, lx, ly = fixed
        c = inv @ Vector(wc)
    else:
        lx, ly = hi.x - lo.x + 2 * pad, hi.y - lo.y + 2 * pad
        c = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, 0))
    world_c = rot @ Vector((c.x, c.y, hi.z + 20))
    cam.location = world_c
    rx, ry = int(round(lx * PPU)), int(round(ly * PPU))
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    cam.data.sensor_fit = "AUTO"
    cam.data.ortho_scale = max(lx, ly)
    cam.data.clip_end = 100
    return cam


def render(path, samples=96, transparent=True, preview=False):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16 if preview else samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.cycles.transmission_bounces = 6
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    if sc.get("exp_set") is None:
        sc.view_settings.exposure = -0.1
    if preview:
        sc.render.resolution_percentage = 35
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    if transparent:
        from PIL import Image
        im = Image.open(path)
        bb = im.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()
        if bb:
            pad = 16
            im.crop((max(0, bb[0] - pad), max(0, bb[1] - pad), min(im.width, bb[2] + pad),
                     min(im.height, bb[3] + pad))).save(path)


ITEMS = {
    "sofa": build_sofa,
    "table": build_table,
    "cabinet": build_cabinet,
    "lamp": build_lamp,
    "cakestand": build_cakestand,
    "balloons": build_balloons,
    "sidetable": build_sidetable,
    "mirror": build_mirror,
}


def main():
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--font", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--samples", type=int, default=96)
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    names = args.only or (list(ITEMS) + ["wall"])
    for name in names:
        new_scene()
        C.OBJ["font"] = bpy.data.fonts.load(args.font)
        lights()
        if name == "wall":
            Wd, Ht = build_wall(os.path.join(args.out, "tex"))
            camera_front(fixed=((0, -0.4, 1.58), 16 / 9 * 3.5, 3.5))
            bpy.context.scene.view_settings.exposure = -1.1
            bpy.context.scene["exp_set"] = 1
            render(os.path.join(args.out, "wall_bg.png"), args.samples, transparent=False, preview=args.preview)
            continue
        ITEMS[name]()
        if name != "mirror":
            shadow_catcher()
        camera_front()
        render(os.path.join(args.out, f"{name}.png"), args.samples, preview=args.preview)
        print("done", name, flush=True)


if __name__ == "__main__":
    main()
