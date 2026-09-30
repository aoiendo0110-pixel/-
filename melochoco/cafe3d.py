"""Blender (bpy) で作る、ピンクのお菓子カフェ＆キッチンの3D空間.

  python3 cafe3d.py --font Mochiy.ttf --out frames_dir [--start 0 --end 928] [--preview 1.0 5.0]

各フレームの PNG と、キャラクター合成用のアンカー (画面座標) を anchors.jsonl に書き出す。
"""
import argparse
import json
import math
import os
import random

import bpy
import bmesh
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

FPS = 30
W, H = 1920, 1080

PINK = (1.0, 0.62, 0.76)
LPINK = (1.0, 0.84, 0.9)
HOT = (1.0, 0.36, 0.62)
RED = (0.86, 0.1, 0.24)
BROWN = (0.38, 0.19, 0.12)
DBROWN = (0.22, 0.1, 0.07)
CREAM = (1.0, 0.96, 0.9)
WHITE = (1.0, 1.0, 1.0)
YELLOW = (1.0, 0.84, 0.36)
GOLD = (0.93, 0.73, 0.3)
MINT = (0.7, 0.93, 0.85)

OBJ = {}
_mats = {}


# ---- 基本 -----------------------------------------------------------------
def lin(c):
    """sRGB → リニア (Blender のカラーはリニア)."""
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


def mat(rgb, rough=0.35, metal=0.0):
    key = (rgb, rough, metal)
    if key not in _mats:
        m = bpy.data.materials.new(f"m{len(_mats)}")
        m.diffuse_color = lin(rgb) + (1,)
        m.roughness = rough
        m.metallic = metal
        _mats[key] = m
    return _mats[key]


def tex_mat(path, name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(path)
    nt.links.new(t.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes.active = t
    m.roughness = 0.6
    return m


def finish(o, col, rough=0.35, metal=0.0, smooth=True, bevel=0.0, parent=None):
    if isinstance(col, bpy.types.Material):
        o.data.materials.append(col)
    else:
        o.data.materials.append(mat(col, rough, metal))
    if smooth and o.type == "MESH":
        for p in o.data.polygons:
            p.use_smooth = True
    if bevel > 0:
        b = o.modifiers.new("b", "BEVEL")
        b.width = bevel
        b.segments = 3
    if parent:
        o.parent = parent
    return o


def box(loc, size, col, bevel=0.03, rot=(0, 0, 0), **kw):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(scale=True)
    return finish(o, col, bevel=bevel, smooth=False, **kw)


def sphere(loc, r, col, scale=(1, 1, 1), **kw):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=32, ring_count=16)
    o = bpy.context.active_object
    o.scale = scale
    return finish(o, col, **kw)


def cyl(loc, r, h, col, verts=48, rot=(0, 0, 0), bevel=0.02, **kw):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, location=loc, vertices=verts, rotation=rot)
    o = bpy.context.active_object
    return finish(o, col, bevel=bevel, **kw)


def torus(loc, R, r, col, rot=(0, 0, 0), **kw):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, rotation=rot,
                                     major_segments=48, minor_segments=16)
    o = bpy.context.active_object
    return finish(o, col, **kw)


def lathe(name, profile, col, loc=(0, 0, 0), n=64, rmod=None, **kw):
    """回転体. profile=[(r, z), ...] 下から上. rmod(theta, i) で半径を波打たせる."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for i, (r, z) in enumerate(profile):
        ring = []
        for j in range(n):
            th = 2 * math.pi * j / n
            rr = r * (rmod(th, i) if rmod else 1)
            ring.append(bm.verts.new((rr * math.cos(th), rr * math.sin(th), z)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for j in range(n):
            bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        if profile[0 if flip else -1][0] > 1e-4:
            bm.faces.new(ring[::-1] if flip else ring)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.location = loc
    bpy.context.collection.objects.link(o)
    return finish(o, col, **kw)


def heart_curve(name, size, depth, col, loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), bevel=0.06, half=0, **kw):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    sp = cu.splines.new("POLY")
    pts = []
    for i in range(72):
        t = 2 * math.pi * i / 72
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 16 * size, y / 16 * size + size * 0.1))
    if half:  # 左半分 (-1) / 右半分 (1) だけのハート
        pts = [p for p in pts if p[0] * half >= 0]
        pts = sorted(pts, key=lambda p: math.atan2(p[1] - size * 0.1, p[0] * half))
    for _ in range(4):  # 角を丸めて、ベベルがトゲにならないようにする
        q = []
        for a, b in zip(pts, pts[1:] + pts[:1]):
            q.append((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25))
            q.append((a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))
        pts = q
    bevel = min(bevel, size * 0.14)
    cu.bevel_depth = bevel
    sp.points.add(len(pts) - 1)
    for p, (x, y) in zip(sp.points, pts):
        p.co = (x, y, 0, 1)
    sp.use_cyclic_u = True
    o = bpy.data.objects.new(name, cu)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat(col, kw.get("rough", 0.25)))
    return o


def text3d(body, size, col, loc, rot=(math.pi / 2, 0, 0), depth=0.04, align="CENTER", font=None):
    cu = bpy.data.curves.new("txt", "FONT")
    cu.body = body
    cu.font = font or OBJ["font"]
    cu.size = size
    cu.extrude = depth
    cu.bevel_depth = depth * 0.4
    cu.align_x = align
    cu.align_y = "CENTER"
    o = bpy.data.objects.new("txt", cu)
    o.location = loc
    o.rotation_euler = rot
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat(col, 0.3))
    return o


def bow(loc, s, col, rot=(0, 0, 0), dots=None):
    """ぷっくりリボン (楕円体の組み合わせ)."""
    root = bpy.data.objects.new("bow", None)
    root.location = loc
    root.rotation_euler = rot
    root.scale = (s, s, s)
    bpy.context.collection.objects.link(root)
    for sx in (-1, 1):
        sphere((sx * 0.45, 0, 0.1), 0.5, col, scale=(1, 0.42, 0.62), parent=root).rotation_euler = (0, sx * -0.35, 0)
        sphere((sx * 0.28, 0, -0.5), 0.5, col, scale=(0.26, 0.16, 0.9), parent=root).rotation_euler = (0, sx * 0.4, 0)
    sphere((0, -0.02, 0.08), 0.22, col, parent=root)
    return root


# ---- テクスチャ (PIL) -------------------------------------------------------
def make_textures(d):
    from PIL import Image, ImageDraw
    os.makedirs(d, exist_ok=True)

    def hp(cx, cy, s, n=40):
        out = []
        for i in range(n):
            t = 2 * math.pi * i / n
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            out.append((cx + x * s / 16, cy - y * s / 16))
        return out
    # 床: ピンクと白の市松
    im = Image.new("RGB", (1024, 1024))
    dr = ImageDraw.Draw(im)
    n = 16
    s = 1024 // n
    for i in range(n):
        for j in range(n):
            c = (255, 196, 216) if (i + j) % 2 else (255, 250, 246)
            dr.rectangle([i * s, j * s, i * s + s, j * s + s], fill=c)
            if (i + j) % 2 == 0:
                dr.polygon(hp(i * s + s / 2, j * s + s / 2, 7), fill=(255, 205, 222))
    im.save(f"{d}/floor.png")
    # 壁紙: ピンクストライプ + 小さいハート
    im = Image.new("RGB", (1024, 1024), (255, 214, 228))
    dr = ImageDraw.Draw(im)
    for x in range(0, 1024, 64):
        dr.rectangle([x, 0, x + 26, 1024], fill=(255, 190, 210))
        dr.line([(x + 40, 0), (x + 40, 1024)], fill=(255, 245, 248), width=3)
    for y in range(32, 1024, 96):
        for x in range(45, 1024, 128):
            dr.polygon(hp(x + (y // 96 % 2) * 64, y, 9), fill=(255, 120, 165))
    im.save(f"{d}/wall.png")
    # 黒板
    im = Image.new("RGB", (512, 512), (70, 44, 40))
    dr = ImageDraw.Draw(im)
    for i in range(0, 512, 32):
        dr.line([(0, i + 10), (512, i + 14)], fill=(78, 50, 46), width=2)
    im.save(f"{d}/board.png")


def textured_plane(size, loc, rot, m, uv_scale=(1, 1)):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = (size[0], size[1], 1)
    bpy.ops.object.transform_apply(scale=True)
    for loop in o.data.uv_layers.active.data:
        loop.uv = (loop.uv[0] * uv_scale[0], loop.uv[1] * uv_scale[1])
    o.data.materials.append(m)
    return o


# ---- 部屋 -----------------------------------------------------------------
def build_room(texdir):
    make_textures(texdir)
    floor = tex_mat(f"{texdir}/floor.png", "floor")
    wall = tex_mat(f"{texdir}/wall.png", "wall")
    textured_plane((20, 16), (0, 0, 0), (0, 0, 0), floor, (2.5, 2))
    textured_plane((20, 7), (0, 7, 3.5), (math.pi / 2, 0, 0), wall, (4, 1.4))                   # 奥
    textured_plane((16, 7), (-9, 0, 3.5), (math.pi / 2, 0, math.pi / 2), wall, (3.2, 1.4))      # 左
    textured_plane((16, 7), (9, 0, 3.5), (math.pi / 2, 0, -math.pi / 2), wall, (3.2, 1.4))      # 右
    textured_plane((20, 16), (0, -7.5, 3.5), (math.pi / 2, 0, math.pi), wall, (4, 1.4))         # 手前
    box((0, 0, 7), (20, 16, 0.1), LPINK, bevel=0)                                              # 天井
    # 腰壁 (白いパネル) + モールディング
    for (x, y, rz, L) in ((0, 6.92, 0, 18), (-8.92, 0, math.pi / 2, 14), (8.92, 0, math.pi / 2, 14)):
        box((x, y, 0.75), (L, 0.12, 1.5), WHITE, bevel=0.02, rot=(0, 0, rz))
        box((x, y, 1.52), (L, 0.2, 0.08), HOT, bevel=0.02, rot=(0, 0, rz))
        box((x, y, 0.08), (L, 0.2, 0.16), BROWN, bevel=0.02, rot=(0, 0, rz))
        for k in range(-int(L / 2) + 1, int(L / 2), 2):
            dx, dy = (k, 0) if rz == 0 else (0, k)
            box((x + dx, y - (0.07 if rz == 0 else 0), 0.75), (1.4, 0.04, 1.0) if rz == 0 else (1.4, 0.04, 1.0),
                LPINK, bevel=0.01, rot=(0, 0, rz))
    # 天井のスカラップ飾り
    for x in range(-9, 10):
        sphere((x + 0.5, 6.85, 6.75), 0.5, HOT, scale=(1, 0.2, 0.55))
        sphere((x + 0.5, 6.8, 6.75), 0.18, WHITE)


def build_window():
    x = -8.85
    box((x, 1, 3.6), (0.2, 3.2, 3.2), WHITE, bevel=0.05)
    box((x + 0.02, 1, 3.6), (0.1, 2.8, 2.8), (0.8, 0.93, 1.0), bevel=0)
    for dz in (-0.45, 0.45):
        box((x + 0.05, 1, 3.6 + dz * 2.4 / 0.9 * 0.3), (0.1, 2.8, 0.08), WHITE, bevel=0)
    box((x + 0.05, 1, 3.6), (0.1, 0.08, 2.8), WHITE, bevel=0)
    # フリルカーテン
    for side in (-1, 1):
        me = bpy.data.meshes.new("curtain")
        bm = bmesh.new()
        nx, nz = 24, 20
        vs = []
        for iz in range(nz + 1):
            row = []
            z = 5.4 - 3.6 * iz / nz
            pinch = 1 - 0.55 * math.exp(-((z - 3.0) / 0.5) ** 2)
            for ix in range(nx + 1):
                u = ix / nx
                yy = 1 + side * (1.0 + 0.9 * u * pinch)
                xx = x + 0.3 + 0.12 * math.sin(u * 18) + 0.05
                row.append(bm.verts.new((xx, yy, z)))
            vs.append(row)
        for a, b in zip(vs, vs[1:]):
            for i in range(nx):
                bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new("curtain", me)
        bpy.context.collection.objects.link(o)
        finish(o, PINK, rough=0.6)
        o.modifiers.new("s", "SOLIDIFY").thickness = 0.03
        bow((x + 0.5, 1 + side * 1.55, 3.0), 0.35, RED, rot=(0, 0, math.pi / 2))
    # 上のバランス (フリル)
    lathe("valance", [(1.9, 5.1), (1.9, 5.6)], WHITE, loc=(x + 0.3, 1, 0), n=64,
          rmod=lambda th, i: 1 + (0.06 * abs(math.sin(th * 12)) if i == 0 else 0)).scale = (0.18, 1, 1)


def build_table(c=(0, 0, 0)):
    x, y, _ = c
    # テーブル + レースのクロス
    cyl((x, y, 0.5), 0.12, 1.0, WHITE)
    cyl((x, y, 0.04), 0.6, 0.08, WHITE)
    lathe("cloth", [(1.75, 0.55), (1.72, 0.7), (1.62, 1.02), (0.0, 1.06)], WHITE, loc=(x, y, 0),
          rmod=lambda th, i: 1 + (0.05 * abs(math.sin(th * 14)) if i < 2 else 0))
    lathe("cloth2", [(1.5, 0.8), (1.45, 1.03), (0.0, 1.075)], LPINK, loc=(x, y, 0),
          rmod=lambda th, i: 1 + (0.06 * abs(math.sin(th * 10)) if i == 0 else 0))
    # 3段ケーキスタンド
    cyl((x, y, 1.9), 0.04, 1.7, GOLD, rough=0.2, metal=0.8)
    for k, (r, z) in enumerate(((0.95, 1.2), (0.7, 1.75), (0.45, 2.25))):
        lathe("plate", [(r * 0.5, z - 0.03), (r, z), (r * 1.02, z + 0.04), (0, z + 0.02)], WHITE, loc=(x, y, 0),
              rmod=lambda th, i: 1 + 0.04 * abs(math.sin(th * 12)))
        rnd = random.Random(k)
        for j in range(6 - k):
            a = 2 * math.pi * j / (6 - k)
            px, py = x + math.cos(a) * r * 0.62, y + math.sin(a) * r * 0.62
            kind = (j + k) % 3
            if kind == 0:  # マカロン
                colm = [PINK, YELLOW, (0.62, 0.4, 0.28), MINT][rnd.randrange(4)]
                sphere((px, py, z + 0.14), 0.16, colm, scale=(1, 1, 0.55))
                cyl((px, py, z + 0.2), 0.14, 0.05, CREAM, bevel=0.01)
                sphere((px, py, z + 0.27), 0.16, colm, scale=(1, 1, 0.55))
            elif kind == 1:  # いちご
                sphere((px, py, z + 0.15), 0.13, RED, scale=(1, 1, 1.25))
                sphere((px, py, z + 0.31), 0.07, (0.4, 0.75, 0.4), scale=(1, 1, 0.3))
            else:  # カップケーキ
                lathe("cup", [(0.1, z), (0.15, z + 0.18)], HOT, loc=(px, py, 0),
                      rmod=lambda th, i: 1 + 0.06 * math.cos(th * 16))
                lathe("cream", [(0.17, z + 0.18), (0.14, z + 0.26), (0.08, z + 0.33), (0.0, z + 0.38)], CREAM,
                      loc=(px, py, 0))
                sphere((px, py, z + 0.42), 0.05, RED)
    torus((x, y, 2.78), 0.14, 0.035, GOLD, rot=(math.pi / 2, 0, 0), rough=0.2, metal=0.8)
    # ティーカップ
    for (dx, dy, col) in ((1.1, -0.6, PINK), (-1.1, -0.5, WHITE)):
        lathe("saucer", [(0.3, 1.08), (0.34, 1.12), (0, 1.1)], WHITE, loc=(x + dx, y + dy, 0))
        lathe("cup", [(0.12, 1.1), (0.2, 1.2), (0.24, 1.4), (0.22, 1.4), (0.18, 1.2), (0.0, 1.18)], col,
              loc=(x + dx, y + dy, 0))
        cyl((x + dx, y + dy, 1.36), 0.2, 0.02, DBROWN, bevel=0)
        torus((x + dx + 0.26, y + dy, 1.27), 0.08, 0.025, col, rot=(math.pi / 2, 0, 0))
    # ショートケーキ (ホール)
    for (r, z0, z1, col) in ((0.55, 1.08, 1.4, CREAM), (0.56, 1.4, 1.46, WHITE)):
        lathe("cake", [(r, z0), (r, z1), (0, z1)], col, loc=(x - 0.2, y - 1.05, 0))
    for j in range(10):
        a = 2 * math.pi * j / 10
        sphere((x - 0.2 + math.cos(a) * 0.42, y - 1.05 + math.sin(a) * 0.42, 1.52), 0.09, WHITE)
        if j % 2 == 0:
            sphere((x - 0.2 + math.cos(a) * 0.42, y - 1.05 + math.sin(a) * 0.42, 1.64), 0.07, RED, scale=(1, 1, 1.2))
    OBJ["table_cake"] = Vector((x - 0.2, y - 1.05, 1.5))


def build_showcase():
    # 奥の左: チョコのショーケース
    x0, y0 = -4.2, 5.6
    box((x0, y0, 0.55), (5.0, 1.4, 1.1), WHITE, bevel=0.06)
    for i in range(10):
        box((x0 - 2.25 + i * 0.5, y0 - 0.71, 0.55), (0.42, 0.04, 0.9), LPINK, bevel=0.02)
    box((x0, y0, 1.15), (5.1, 1.5, 0.1), HOT, bevel=0.04)
    for dx in (-2.45, 0, 2.45):
        cyl((x0 + dx, y0 - 0.6, 1.75), 0.05, 1.2, GOLD, metal=0.7, rough=0.2)
    box((x0, y0 + 0.1, 2.35), (5.1, 1.4, 0.1), HOT, bevel=0.04)
    # 中のチョコとケーキ
    rnd = random.Random(3)
    for i in range(9):
        cx = x0 - 2.0 + i * 0.5
        k = i % 3
        if k == 0:
            heart_curve("choc", 0.2, 0.05, DBROWN if i % 2 else BROWN, loc=(cx, y0 - 0.25, 1.42),
                        rot=(math.pi / 2 - 0.4, 0, 0))
        elif k == 1:
            lathe("slice", [(0.18, 1.2), (0.18, 1.5), (0, 1.5)], [PINK, BROWN, CREAM][rnd.randrange(3)],
                  loc=(cx, y0 - 0.2, 0), n=4)
            sphere((cx, y0 - 0.2, 1.58), 0.07, RED)
        else:
            sphere((cx, y0 - 0.2, 1.32), 0.13, BROWN)
            sphere((cx, y0 - 0.2, 1.42), 0.06, HOT)
    # ケーキの上段 (チョコケーキ)
    lathe("choco_cake", [(0.45, 2.4), (0.45, 2.85), (0, 2.85)], BROWN, loc=(x0 - 1.5, y0, 0))
    lathe("icing", [(0.47, 2.72), (0.47, 2.88), (0, 2.9)], DBROWN, loc=(x0 - 1.5, y0, 0),
          rmod=lambda th, i: 1 + (0.05 * math.sin(th * 9) if i == 0 else 0))
    for j in range(8):
        a = 2 * math.pi * j / 8
        sphere((x0 - 1.5 + math.cos(a) * 0.33, y0 + math.sin(a) * 0.33, 2.95), 0.07, PINK)
    heart_curve("topper", 0.2, 0.04, RED, loc=(x0 - 1.5, y0, 3.2))
    # マカロンタワー
    for lv in range(7):
        r = 0.55 - lv * 0.07
        n = max(3, int(2 * math.pi * r / 0.2))
        for j in range(n):
            a = 2 * math.pi * j / n + lv * 0.3
            col = [PINK, WHITE, YELLOW, HOT][lv % 4]
            sphere((x0 + 1.5 + math.cos(a) * r, y0 + math.sin(a) * r, 2.5 + lv * 0.17), 0.09, col,
                   scale=(1, 1, 0.8))
    OBJ["showcase"] = Vector((x0, y0 - 0.2, 1.5))


def build_menu():
    x, y = 3.8, 6.85
    box((x, y, 3.3), (3.6, 0.14, 2.6), GOLD, bevel=0.06, rough=0.25, metal=0.6)
    bd = tex_mat(OBJ["texdir"] + "/board.png", "board")
    textured_plane((3.2, 2.2), (x, y - 0.09, 3.3), (math.pi / 2, 0, 0), bd)
    for dx in (-1.8, 1.8):
        for dz in (-1.3, 1.3):
            sphere((x + dx, y - 0.1, 3.3 + dz), 0.14, HOT)
    bow((x, y - 0.2, 4.72), 0.45, RED)
    text3d("MENU", 0.42, WHITE, (x, y - 0.12, 4.05), depth=0.02)
    for i, (s, c) in enumerate((("いちごケーキ", PINK), ("ショコラ", (0.9, 0.7, 0.55)), ("マカロン", YELLOW),
                                ("めろめろ♡", HOT))):
        text3d(s, 0.28, c, (x - 1.3, y - 0.12, 3.55 - i * 0.42), depth=0.015, align="LEFT")
    OBJ["menu"] = Vector((x, y - 0.1, 3.3))
    # ネオン風の看板
    t = text3d("melochoco café", 0.62, HOT, (-0.3, 6.8, 5.6), depth=0.08)
    OBJ["sign"] = t
    heart_curve("sign_h", 0.3, 0.06, RED, loc=(2.3, 6.8, 5.62))


def build_kitchen():
    # 右の壁: キッチンカウンター
    x = 7.9
    box((x, 1.5, 0.55), (1.8, 5.0, 1.1), WHITE, bevel=0.05)
    for i in range(5):
        box((x - 0.92, -0.5 + i * 1.0, 0.55), (0.04, 0.85, 0.85), LPINK, bevel=0.02)
        sphere((x - 0.96, -0.5 + i * 1.0, 0.8), 0.05, GOLD, metal=0.8, rough=0.2)
    box((x, 1.5, 1.14), (1.9, 5.1, 0.1), CREAM, bevel=0.03)
    # 棚とジャー
    box((x + 0.55, 1.5, 3.2), (0.7, 5.0, 0.08), WHITE, bevel=0.02)
    for i, col in enumerate((PINK, YELLOW, MINT, HOT, CREAM, RED)):
        lathe("jar", [(0.2, 3.24), (0.25, 3.35), (0.25, 3.8), (0.18, 3.9), (0, 3.9)], (0.95, 0.97, 1.0),
              loc=(x + 0.55, -0.4 + i * 0.75, 0), rough=0.05)
        lathe("jar_in", [(0.2, 3.26), (0.2, 3.62), (0, 3.62)], col, loc=(x + 0.55, -0.4 + i * 0.75, 0))
        sphere((x + 0.55, -0.4 + i * 0.75, 3.95), 0.1, col, scale=(1.4, 1.4, 0.5))
    # ボウルと泡立て器
    lathe("bowl", [(0.2, 1.2), (0.45, 1.3), (0.62, 1.6), (0.58, 1.6), (0.42, 1.34), (0, 1.3)], PINK,
          loc=(x - 0.2, 0.2, 0))
    lathe("batter", [(0.56, 1.52), (0, 1.54)], BROWN, loc=(x - 0.2, 0.2, 0))
    for k in range(6):
        torus((x - 0.2, 0.25, 1.95), 0.18, 0.012, (0.85, 0.85, 0.9), rot=(0, 0.3, k * math.pi / 6), metal=0.9,
              rough=0.2).scale = (1, 0.4, 1.4)
    cyl((x - 0.2, 0.25, 2.45), 0.04, 0.5, HOT, rot=(0, 0.3, 0))
    # ハートの型 (チョコを流し込む)
    mx, my, mz = x - 0.3, 2.2, 1.22
    heart_curve("mold", 0.62, 0.02, GOLD, loc=(mx, my, mz), rot=(0, 0, 0), bevel=0.08, rough=0.2)
    heart_curve("mold_in", 0.52, 0.02, LPINK, loc=(mx, my, mz + 0.05), rot=(0, 0, 0), bevel=0.02)
    fill = heart_curve("mold_fill", 0.5, 0.02, BROWN, loc=(mx, my, mz + 0.08), rot=(0, 0, 0), bevel=0.03)
    OBJ["mold_fill"] = fill
    OBJ["mold"] = Vector((mx, my, mz + 0.1))
    # 飛び出すハートチョコ
    ch = heart_curve("pop_heart", 0.42, 0.12, BROWN, loc=(mx, my, mz + 0.4), bevel=0.06, rough=0.15)
    for k in range(5):
        heart_curve("drizzle", 0.1, 0.02, HOT, loc=(-0.3 + k * 0.15, -0.2, 0.1 + 0.05 * (k % 2)),
                    rot=(0, 0, 0), bevel=0.02).parent = ch
    ch.scale = (0.001,) * 3
    OBJ["pop_heart"] = ch
    # オーブン
    box((x - 0.05, 4.4, 2.0), (1.6, 1.4, 1.5), HOT, bevel=0.08)
    cyl((x - 0.86, 4.4, 2.0), 0.42, 0.06, (0.35, 0.2, 0.2), rot=(0, math.pi / 2, 0), rough=0.05)
    torus((x - 0.89, 4.4, 2.0), 0.44, 0.05, WHITE, rot=(0, math.pi / 2, 0))
    for k in range(3):
        sphere((x - 0.86, 3.95 + k * 0.45, 2.6), 0.07, WHITE)
    # 冷蔵庫 (ピンクのレトロ)
    fx, fy = 7.9, -3.2
    box((fx + 0.7, fy, 1.7), (0.12, 1.6, 3.4), PINK, bevel=0.04)
    for dy in (-0.75, 0.75):
        box((fx, fy + dy, 1.7), (1.5, 0.12, 3.4), PINK, bevel=0.04)
    for z in (0.06, 3.35):
        box((fx, fy, z), (1.5, 1.6, 0.14), PINK, bevel=0.04)
    box((fx + 0.62, fy, 1.7), (0.04, 1.4, 3.2), (0.93, 0.97, 1.0), bevel=0)
    for z in (1.2, 2.2):
        box((fx, fy, z - 0.3), (1.3, 1.45, 0.05), WHITE, bevel=0.01)
    door = bpy.data.objects.new("door_pivot", None)
    door.location = (fx - 0.78, fy + 0.8, 1.7)
    bpy.context.collection.objects.link(door)
    d = box((fx - 0.78, fy, 1.7), (0.12, 1.6, 3.3), LPINK, bevel=0.05)
    d.parent = door
    d.location = (0, -0.8, 0)
    cyl((-0.1, -1.4, 0.4), 0.05, 0.9, WHITE, parent=door)
    heart_curve("fridge_h", 0.3, 0.03, RED, loc=(-0.1, -0.8, 1.1), rot=(math.pi / 2, 0, math.pi / 2)).parent = door
    OBJ["fridge_door"] = door
    # 冷蔵庫の中 (氷のハート)
    for k in range(6):
        heart_curve("ice", 0.2, 0.08, [(0.9, 0.96, 1.0), PINK, BROWN][k % 3],
                    loc=(fx - 0.1, fy - 0.45 + (k % 3) * 0.45, 1.12 + (k // 3) * 1.0),
                    rot=(math.pi / 2, 0, math.pi / 2), rough=0.05)
    OBJ["fridge"] = Vector((fx - 0.8, fy, 1.8))
    # とじこめるリボン (2本のバンド)
    bands = []
    for s in (-1, 1):
        b = box((fx - 0.95, fy, 1.7), (0.08, 0.35, 4.6), RED, bevel=0.02, rot=(s * 0.6, 0, 0))
        b.scale = (1, 1, 0.001)
        bands.append(b)
    OBJ["bands"] = bands
    lock = heart_curve("lock", 0.35, 0.15, HOT, loc=(fx - 1.05, fy, 1.7), rot=(math.pi / 2, 0, math.pi / 2),
                       bevel=0.08)
    lock.scale = (0.001,) * 3
    OBJ["lock"] = lock


def build_wrapping():
    # 左手前: ラッピング台
    x, y = -6.4, -2.4
    box((x, y, 0.55), (2.6, 1.6, 1.1), (0.95, 0.9, 0.86), bevel=0.05)
    box((x, y, 1.13), (2.7, 1.7, 0.08), BROWN, bevel=0.03)
    for i, (col, rib) in enumerate(((PINK, RED), (WHITE, (0.12, 0.1, 0.1)), (RED, WHITE))):
        gx = x - 0.8 + i * 0.8
        s = 0.55 - i * 0.08
        box((gx, y + 0.2, 1.17 + s / 2), (s, s, s), col, bevel=0.03)
        box((gx, y + 0.2, 1.17 + s / 2), (s + 0.02, 0.1, s + 0.02), rib, bevel=0.01)
        box((gx, y + 0.2, 1.17 + s / 2), (0.1, s + 0.02, s + 0.02), rib, bevel=0.01)
        bow((gx, y + 0.2, 1.24 + s), 0.18, rib)
    # リボンのスプール (白黒)
    spools = []
    for i, col in enumerate(((0.12, 0.1, 0.1), WHITE, RED)):
        sp = cyl((x - 0.9 + i * 0.9, y - 0.55, 1.33), 0.17, 0.16, col, rot=(0, math.pi / 2, 0))
        cyl((x - 0.9 + i * 0.9, y - 0.55, 1.33), 0.06, 0.22, GOLD, rot=(0, math.pi / 2, 0), metal=0.7)
        spools.append(sp)
    OBJ["spools"] = spools
    big = bow((x + 0.3, y - 0.1, 2.35), 0.001, (0.12, 0.1, 0.1))
    OBJ["big_bow"] = big
    OBJ["wrap"] = Vector((x, y, 1.6))
    # 大きいプレゼント
    gx, gy = -5.0, -4.6
    box((gx, gy, 0.6), (1.2, 1.2, 1.2), PINK, bevel=0.05)
    box((gx, gy, 0.6), (1.22, 0.2, 1.22), RED, bevel=0.01)
    box((gx, gy, 0.6), (0.2, 1.22, 1.22), RED, bevel=0.01)
    lid = bpy.data.objects.new("lid", None)
    lid.location = (gx, gy, 1.3)
    bpy.context.collection.objects.link(lid)
    l = box((0, 0, 0), (1.35, 1.35, 0.3), PINK, bevel=0.05)
    l.parent = lid
    box((0, 0, 0), (1.37, 0.2, 0.32), RED, bevel=0.01).parent = lid
    box((0, 0, 0), (0.2, 1.37, 0.32), RED, bevel=0.01).parent = lid
    bow((0, 0, 0.35), 0.4, RED).parent = lid
    OBJ["gift_lid"] = lid
    OBJ["gift"] = Vector((gx, gy, 1.2))


def build_deco():
    # 天井から吊るしたハート
    hs = []
    rnd = random.Random(8)
    for i in range(22):
        x, y = rnd.uniform(-8, 8), rnd.uniform(-5, 6)
        z = rnd.uniform(4.6, 6.2)
        col = rnd.choice([HOT, RED, PINK, WHITE, (1.0, 0.8, 0.85)])
        h = heart_curve("hang", rnd.uniform(0.18, 0.34), 0.06, col, loc=(x, y, z), bevel=0.07, rough=0.2)
        cyl((x, y, (z + 7) / 2 + 0.2), 0.008, 7 - z, WHITE, verts=6, bevel=0)
        hs.append((h, rnd.random() * 6))
    OBJ["hang"] = hs
    # 風船
    for (x, y, col) in ((-7.8, 5.6, HOT), (-7.2, 6.1, WHITE), (-6.6, 5.7, RED), (7.6, 5.8, PINK), (7.0, 6.2, WHITE)):
        sphere((x, y, 4.6), 0.4, col, scale=(1, 1, 1.15), rough=0.15)
        cyl((x, y, 2.9), 0.006, 3.0, WHITE, verts=6, bevel=0)
    # 大きいハート (割れる) : 左右の半分
    cx, cy, cz = 2.6, 1.8, 2.6
    halves = []
    for s in (-1, 1):
        halves.append(heart_curve("big_heart", 0.9, 0.2, RED, loc=(cx, cy, cz), bevel=0.16, rough=0.15, half=s))
    OBJ["big_heart"] = halves
    OBJ["big_heart_pos"] = Vector((cx, cy, cz))
    # ケーキスタンド風の台
    lathe("stand", [(0.5, 0), (0.15, 0.1), (0.1, 1.2), (0.7, 1.3), (0.7, 1.36), (0, 1.36)], WHITE, loc=(cx, cy, 0))
    # 床のラグ (ハート)
    rug = heart_curve("rug", 2.2, 0.01, (1.0, 0.75, 0.84), loc=(0, 0, 0.02), rot=(0, 0, 0), bevel=0.02)
    rug.scale = (1, 1.3, 1)


# ---- シーン設定 -------------------------------------------------------------
def setup_render(samples, res=(1280, 720)):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.display.render_aa = samples
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.studio_light = "paint.sl"
    sh.use_world_space_lighting = True
    sh.studiolight_rotate_z = 0.6
    sh.studiolight_intensity = 1.3
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.shadow_intensity = 0.28
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.cavity_ridge_factor = 1.0
    sh.cavity_valley_factor = 1.0
    sh.curvature_ridge_factor = 1.2
    sh.curvature_valley_factor = 0.8
    sh.show_object_outline = True
    sh.object_outline_color = lin((0.55, 0.2, 0.3))
    sh.show_specular_highlight = True
    sh.use_dof = False
    sc.display.light_direction = (0.45, -0.35, 0.82)
    sc.display.shadow_shift = 0.05
    sc.display.shadow_focus = 0.3
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.image_settings.file_format = "PNG"
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 28
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 2.8
    cam.data.clip_start = 0.05
    OBJ["cam"] = cam


def look_at(cam, pos, target, roll=0.0):
    cam.location = pos
    d = Vector(target) - Vector(pos)
    q = d.to_track_quat("-Z", "Y")
    e = q.to_euler()
    e.rotate_axis("Z", roll)
    cam.rotation_euler = e
    cam.data.dof.focus_distance = d.length


# ---- カメラワーク ------------------------------------------------------------
V = Vector
# (時刻, カメラ位置, 注視点, レンズ, キャラの位置(3D), キャラの高さ)
SHOTS = [
    (0.0, V((-0.9, -2.2, 1.45)), V((-0.2, -1.05, 1.45)), 40),
    (1.4, V((-1.2, -4.8, 2.4)), V((0.0, 0.0, 1.8)), 30),
    (2.2, V((2.8, -4.2, 2.2)), V((0.2, 0.0, 1.7)), 30),
    (4.0, V((-2.4, -4.4, 2.0)), V((0.0, 0.2, 1.8)), 30),
    (4.1, V((0.2, -3.2, 2.4)), V((0.8, -0.8, 2.4)), 34),
    (4.7, V((0.4, -2.2, 2.6)), V((1.0, -0.5, 2.5)), 38),
    (4.95, V((-3.4, 2.4, 2.0)), V((-4.2, 5.4, 1.6)), 32),
    (7.1, V((-5.4, 2.6, 2.1)), V((-4.4, 5.5, 1.8)), 32),
    (7.35, V((2.4, 2.8, 3.1)), V((3.8, 6.8, 3.3)), 30),
    (9.7, V((4.6, 3.2, 3.0)), V((3.8, 6.8, 3.2)), 30),
    (9.95, V((5.2, 0.6, 2.6)), V((7.6, 2.2, 1.3)), 32),
    (11.1, V((5.6, 1.5, 2.9)), V((7.6, 2.2, 1.3)), 34),
    (12.0, V((5.0, 1.0, 2.4)), V((7.6, 2.2, 1.7)), 30),
    (13.2, V((4.6, 1.4, 2.2)), V((7.6, 2.2, 1.8)), 30),
    (13.45, V((0.8, -1.6, 2.6)), V((2.6, 1.8, 2.6)), 30),
    (16.5, V((1.4, -1.9, 2.8)), V((2.6, 1.8, 2.6)), 32),
    (16.8, V((3.8, -5.2, 2.3)), V((7.4, -3.0, 1.8)), 28),
    (19.4, V((4.4, -4.8, 2.3)), V((7.4, -3.0, 1.8)), 30),
    (21.1, V((4.8, -4.4, 2.2)), V((7.6, -3.0, 1.8)), 30),
    (21.4, V((-3.4, -5.0, 2.3)), V((-6.0, -2.3, 1.8)), 28),
    (24.9, V((-3.6, -4.4, 2.6)), V((-6.0, -2.2, 2.0)), 28),
    (25.15, V((-2.8, -6.2, 2.0)), V((-5.0, -4.6, 1.2)), 30),
    (26.4, V((-2.9, -6.4, 2.3)), V((-5.0, -4.6, 1.4)), 28),
    (26.65, V((5.5, -6.6, 4.2)), V((-1.0, 3.0, 2.2)), 24),
    (28.4, V((4.6, -6.4, 3.4)), V((-1.0, 3.0, 2.2)), 24),
    (28.6, V((0.2, -4.8, 2.2)), V((0.2, -1.0, 2.4)), 30),
    (31.0, V((0.2, -3.2, 2.35)), V((0.2, -1.0, 2.45)), 34),
]


def smooth(x):
    x = min(max(x, 0), 1)
    return x * x * x * (x * (x * 6 - 15) + 10)


def camera_at(t):
    for a, b in zip(SHOTS, SHOTS[1:]):
        if a[0] <= t <= b[0]:
            u = (t - a[0]) / max(b[0] - a[0], 1e-6)
            fast = b[0] - a[0] < 0.4
            k = smooth(u) if fast else (u * 0.35 + smooth(u) * 0.65)
            return a[1].lerp(b[1], k), a[2].lerp(b[2], k), a[3] + (b[3] - a[3]) * k, fast
    s = SHOTS[-1]
    return s[1], s[2], s[3], False


# キャラ (立ち絵) の配置: (開始時刻, 画面の左右 -1..1, カメラからの距離, 高さ)
# 各場面の最初のカメラ位置を基準に3D空間に置くので、場面の中ではカメラの動きに合わせて自然に動く
CHAR = [
    (0.0, 0.55, 2.8, 1.35, 1.2),
    (2.2, -0.58, 3.2, 1.3, 3.0),
    (4.1, 0.0, 2.2, 1.55),
    (4.95, 0.6, 2.8, 1.45),
    (7.35, -0.6, 2.8, 1.45),
    (9.95, -0.58, 2.6, 1.4),
    (13.45, 0.62, 2.8, 1.45),
    (16.8, -0.62, 2.8, 1.45),
    (21.4, 0.6, 2.8, 1.45),
    (25.15, 0.6, 2.8, 1.45),
    (26.65, 0.3, 3.2, 1.5),
    (28.6, 0.0, 2.4, 1.6),
]
_char_cache = {}


def char_at(t):
    cur = CHAR[0]
    for c in CHAR:
        if t >= c[0]:
            cur = c
    st, side, dist, hh = cur[:4]
    ref = cur[4] if len(cur) > 4 else st + 0.05  # この時刻のカメラを基準に置く
    if st not in _char_cache:
        pos, tgt, lens, _ = camera_at(ref)
        fwd = (tgt - pos).normalized()
        right = fwd.cross(V((0, 0, 1))).normalized()
        up = right.cross(fwd).normalized()
        half_w = dist * 18 / lens
        _char_cache[st] = pos + fwd * dist + right * side * half_w * 0.62 - up * 0.04 * dist
    return st, _char_cache[st], hh


# ---- アニメーション ---------------------------------------------------------
def animate(t):
    for h, ph in OBJ["hang"]:
        h.rotation_euler = (math.pi / 2, 0, 0.5 * math.sin(t * 1.2 + ph))
        h.location.z += 0.0
    # チョコを型に流す
    lvl = smooth((t - 9.95) / 1.1)
    f = OBJ["mold_fill"]
    f.scale = (0.2 + 0.8 * lvl, 0.2 + 0.8 * lvl, 1)
    f.hide_render = t < 9.95 or t > 12.05
    cold = smooth((t - 11.1) / 0.3) * (1 - smooth((t - 12.0) / 0.3))
    f.data.materials[0] = mat(tuple(BROWN[i] * (1 - cold) + (0.85, 0.9, 1.0)[i] * cold * 0.8 for i in range(3)))
    ph = OBJ["pop_heart"]
    k = smooth((t - 12.0) / 0.35)
    bounce = math.sin(min(max(t - 12.0, 0), 1.3) * 9) * math.exp(-max(t - 12.0, 0) * 3) * 0.3
    s = max(0.001, k * (1 + bounce))
    ph.scale = (s, s, s)
    ph.location.z = OBJ["mold"].z + 0.2 + 0.9 * k
    ph.rotation_euler = (math.pi / 2, 0, (t - 12.0) * 2.2)
    ph.hide_render = t < 12.0 or t > 13.5
    # 大きいハートが割れる → 戻る
    gap = 0.0
    if t >= 14.6:
        gap = 0.28 * smooth((t - 14.6) / 0.2) * (1 - smooth((t - 15.2) / 0.5))
    shake = 0.03 * math.sin(t * 60) if 14.6 <= t < 15.1 else 0
    for s, h in zip((-1, 1), OBJ["big_heart"]):
        p = OBJ["big_heart_pos"]
        h.location = (p.x + s * gap + shake, p.y, p.z + 0.08 * math.sin(t * 2))
        h.rotation_euler = (math.pi / 2, s * gap * 0.6, 0.25 * math.sin(t * 0.8))
    # 冷蔵庫
    open_k = smooth((t - 16.8) / 0.5) * (1 - smooth((t - 19.3) / 0.25))
    OBJ["fridge_door"].rotation_euler = (0, 0, -1.6 * open_k)
    bk = smooth((t - 19.45) / 0.35)
    for b in OBJ["bands"]:
        b.scale = (1, 1, max(0.001, bk))
        b.hide_render = t < 19.4
    lk = smooth((t - 19.7) / 0.3)
    lb = 1 + 0.25 * math.sin(max(t - 19.7, 0) * 12) * math.exp(-max(t - 19.7, 0) * 4)
    OBJ["lock"].scale = (max(0.001, lk * lb),) * 3
    # リボン
    for i, sp in enumerate(OBJ["spools"]):
        sp.rotation_euler = (t * (2 + i), math.pi / 2, 0)
    bb = OBJ["big_bow"]
    bk = smooth((t - 22.65) / 0.45)
    wob = 1 + 0.15 * math.sin(max(t - 22.65, 0) * 10) * math.exp(-max(t - 22.65, 0) * 3)
    bb.scale = (max(0.001, 0.75 * bk * wob),) * 3
    bb.rotation_euler = (0, 0, 0.89 + (1 - bk) * 6.28)
    # プレゼントのフタが飛ぶ
    lid = OBJ["gift_lid"]
    lk = max(0.0, t - 25.55)
    lid.location = (OBJ["gift"].x + lk * 0.8, OBJ["gift"].y + lk * 0.3, 1.3 + 3.2 * lk - 5 * lk * lk if lk < 0.7 else -5)
    lid.rotation_euler = (lk * 5, lk * 3, 0)


def project(p):
    sc = bpy.context.scene
    co = world_to_camera_view(sc, OBJ["cam"], Vector(p))
    return (co.x * W, (1 - co.y) * H, co.z)


def frame(t, fast_prev=None):
    pos, tgt, lens, fast = camera_at(t)
    cam = OBJ["cam"]
    # ゆるい手持ち感
    pos = pos + V((0.02 * math.sin(t * 1.3), 0.015 * math.sin(t * 0.9), 0.02 * math.sin(t * 1.7)))
    look_at(cam, pos, tgt, 0.02 * math.sin(t * 0.7))
    cam.data.lens = lens
    cam.data.dof.aperture_fstop = 1.6 if fast else 3.2
    animate(t)
    bpy.context.view_layer.update()  # カメラ行列を更新してから投影する
    c0, ch_h = char_at(t)[1], char_at(t)[2]
    bob = 0.08 * math.sin(t * 2.0)
    center = c0 + V((0, 0, bob))
    # 画面上でのキャラ中心と上端 → スケール
    up = (tgt - pos).normalized().cross(V((0, 0, 1))).cross((tgt - pos).normalized()).normalized()
    a = project(center)
    b = project(center + up * ch_h / 2)
    return dict(t=t, cx=a[0], cy=a[1], depth=a[2], half_h=abs(a[1] - b[1]), fast=fast)


def build(font, texdir):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    OBJ["font"] = bpy.data.fonts.load(font)
    OBJ["texdir"] = texdir
    build_room(texdir)
    build_window()
    build_table()
    build_showcase()
    build_menu()
    build_kitchen()
    build_wrapping()
    build_deco()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=928)
    ap.add_argument("--aa", default="FXAA")
    ap.add_argument("--preview", type=float, nargs="*")
    ap.add_argument("--anchors-only", action="store_true", help="描画せずにアンカーだけ書き出す")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    build(args.font, os.path.join(args.out, "tex"))
    setup_render(args.aa)
    sc = bpy.context.scene
    times = args.preview if args.preview else [i / FPS for i in range(args.start, args.end)]
    with open(os.path.join(args.out, f"anchors_{args.start}.jsonl" if not args.preview else "anchors_pv.jsonl"),
              "w") as fp:
        for t in times:
            info = frame(t)
            name = f"pv_{t:05.2f}.png" if args.preview else f"f_{int(round(t * FPS)):04d}.png"
            sc.render.filepath = os.path.join(args.out, name)
            if not args.anchors_only:
                bpy.ops.render.render(write_still=True)
            info["file"] = name
            fp.write(json.dumps(info) + "\n")
            fp.flush()


if __name__ == "__main__":
    main()
