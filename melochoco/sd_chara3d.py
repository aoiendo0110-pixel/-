"""ショコラ×ロリータのパティシエ少女を、SD (ちびキャラ) 等身の3Dモデルにする (Blender Cycles + Freestyle の線).

  pip install bpy pillow
  python3 sd_chara3d.py --out chara_out              # 4方向の静止画 + .blend + .glb
  python3 sd_chara3d.py --out chara_out --turntable  # 8秒で1回転する透過動画も

パーツ (全部コードで作っている)
- 顔: 目・口・ほっぺは PIL で描いたテクスチャを顔の前面に貼る (アニメ塗りの目)
- 髪: ラズベリー色のボブ + ぱっつん前髪 + 左右のドリル (縦ロール)、白いベレー帽、ストライプのリボンと鈴
- 服: 白いブラウス + パフスリーブ、赤い襟とチョコのハートのブローチ、コルセット、フレアスカート + 白フリル、
      チョコが垂れたハートのエプロン、背中の大きなピンクのリボン (ハートの白抜き)
- 小物: チョコがけの泡立て器 (ストライプのリボン付き)、手袋、網タイツ / リボンを巻いた脚、厚底の靴と鈴
座標は Z が上、キャラの正面が -Y. 全身でおよそ 2.6 (頭が全体の約 1/2.3 の SD 体型).
"""
import argparse
import math
import os
import random
import subprocess

import bpy
import bmesh  # noqa: E402  (bpy を先に import する必要がある)
from mathutils import Matrix, Vector
from PIL import Image, ImageDraw, ImageFilter

HEAD_C = Vector((0, 0, 1.85))
HEAD_S = Vector((0.64, 0.58, 0.6))
NOLINE = None   # 線を描かないオブジェクトのコレクション (顔のテクスチャなど)


# ---- 基本 ----------------------------------------------------------------------------
def link(ob, noline=False):
    (NOLINE if noline else bpy.context.scene.collection).objects.link(ob)
    return ob


def principled(name, color, rough=0.6, metal=0.0, coat=0.0, sheen=0.0, spec=0.35):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.1
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Specular IOR Level"].default_value = spec
    return m, b


def lin(hexstr):
    """'#rrggbb' (イラストの色) → リニアの RGB."""
    c = [int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mat(name, color, **kw):
    return principled(name, color, **kw)[0]


def mat_stripe(name, base, stripe, scale=3.2, width=0.8, direction="X"):
    """ストライプのリボン (Object 座標の帯)."""
    m, b = principled(name, base, rough=0.55, sheen=0.4)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"
    wv.bands_direction = direction
    wv.inputs["Scale"].default_value = scale
    wv.inputs["Distortion"].default_value = 0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (*base, 1)
    els[1].position, els[1].color = width, (*stripe, 1)
    nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def mat_fishnet(name, base, line, k=95.0):
    """網タイツ: 斜めに交差する細い線."""
    m, b = principled(name, base, rough=0.6)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    ang = nt.nodes.new("ShaderNodeMath")
    ang.operation = "ARCTAN2"
    nt.links.new(sep.outputs["Y"], ang.inputs[0])
    nt.links.new(sep.outputs["X"], ang.inputs[1])

    def lines(sign):
        a = nt.nodes.new("ShaderNodeMath")
        a.operation = "MULTIPLY_ADD"          # z*k + sign*angle*n
        nt.links.new(ang.outputs[0], a.inputs[0])
        a.inputs[1].default_value = sign * 9.0
        z = nt.nodes.new("ShaderNodeMath")
        z.operation = "MULTIPLY"
        nt.links.new(sep.outputs["Z"], z.inputs[0])
        z.inputs[1].default_value = k
        nt.links.new(z.outputs[0], a.inputs[2])
        s = nt.nodes.new("ShaderNodeMath")
        s.operation = "SINE"
        nt.links.new(a.outputs[0], s.inputs[0])
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        nt.links.new(s.outputs[0], ab.inputs[0])
        lt = nt.nodes.new("ShaderNodeMath")
        lt.operation = "LESS_THAN"
        nt.links.new(ab.outputs[0], lt.inputs[0])
        lt.inputs[1].default_value = 0.2
        return lt

    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(lines(1).outputs[0], mx.inputs[0])
    nt.links.new(lines(-1).outputs[0], mx.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*base, 1)
    mix.inputs[7].default_value = (*line, 1)
    nt.links.new(mx.outputs[0], mix.inputs["Factor"])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def mat_decal(name, img_path):
    """透過 PNG を貼るマテリアル (アルファの所だけ見える)."""
    m, b = principled(name, (1, 1, 1), rough=0.6)
    nt = m.node_tree
    img = bpy.data.images.load(img_path)
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    tx.interpolation = "Cubic"
    nt.links.new(tx.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tx.outputs["Alpha"], b.inputs["Alpha"])
    return m


def mesh_obj(name, bm, material, smooth=True, noline=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        me.shade_smooth()
    me.materials.append(material)
    return link(bpy.data.objects.new(name, me), noline)


def place(ob, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    ob.location, ob.rotation_euler, ob.scale = loc, rot, scale
    return ob


def sphere(name, material, loc, scale, rot=(0, 0, 0), seg=40, rings=24, deform=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1)
    if deform:
        for v in bm.verts:
            v.co = Vector(deform(v.co))
    return place(mesh_obj(name, bm, material), loc, rot, scale)


def box(name, material, loc, half, bevel=0.02):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2)
    ob = place(mesh_obj(name, bm, material, smooth=False), loc, (0, 0, 0), half)
    md = ob.modifiers.new("bevel", "BEVEL")
    md.width, md.segments = bevel, 4
    ob.data.shade_smooth()
    return ob


def tube(name, material, pts, radius=0.05, radii=None, cyclic=False, profile=None, res=12, tilts=None):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = res
    if profile is not None:
        cu.bevel_mode = "OBJECT"
        cu.bevel_object = profile
    else:
        cu.bevel_depth = radius
        cu.bevel_resolution = 5
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for i, bp in enumerate(sp.bezier_points):
        bp.co = pts[i]
        bp.handle_left_type = bp.handle_right_type = "AUTO"
        bp.radius = radii[i] if radii else 1.0
        if tilts:
            bp.tilt = tilts[i]
    sp.use_cyclic_u = cyclic
    cu.materials.append(material)
    return link(bpy.data.objects.new(name, cu))


def ring_tube(name, material, center, radius, thick, normal=(0, 0, 1), n=24, sy=1.0):
    nrm = Vector(normal).normalized()
    a = nrm.orthogonal().normalized()
    b = nrm.cross(a)
    pts = [Vector(center) + radius * (math.cos(t) * a + sy * math.sin(t) * b)
           for t in [math.tau * i / n for i in range(n)]]
    return tube(name, material, pts, thick, cyclic=True)


def ring_strip(name, material, z0, z1, r0, r1, waves=0, amp=0.0, grow=True, seg=240, rows=10,
               thick=0.01, center=(0, 0), sy=1.0, power=1.0, phase=0.0, axis_m=None):
    """回転体の帯 (スカート・フリル・襟). waves/amp で波打たせる."""
    bm = bmesh.new()
    grid = []
    for j in range(rows + 1):
        v = j / rows
        z = z0 + (z1 - z0) * v
        r = r0 + (r1 - r0) * v ** power
        row = []
        for i in range(seg):
            th = math.tau * i / seg
            rr = r + amp * (v if grow else 1.0) * math.sin(waves * th + phase)
            p = Vector((center[0] + rr * math.cos(th), center[1] + sy * rr * math.sin(th), z))
            row.append(bm.verts.new(axis_m @ p if axis_m else p))
        grid.append(row)
    for j in range(rows):
        for i in range(seg):
            k = (i + 1) % seg
            bm.faces.new((grid[j][i], grid[j][k], grid[j + 1][k], grid[j + 1][i]))
    ob = mesh_obj(name, bm, material)
    if thick:
        md = ob.modifiers.new("solid", "SOLIDIFY")
        md.thickness = thick
        md.offset = 0
    return ob


def heart2d(n=96):
    pts = []
    for i in range(n):
        t = math.tau * i / n
        pts.append((16 * math.sin(t) ** 3, 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    s = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    return [((x - cx) / s, (y - cy) / s) for x, y in pts]


def frame_matrix(origin, normal, up=(0, 0, 1)):
    """origin を原点、normal を +Z、up を +Y にした座標系."""
    z = Vector(normal).normalized()
    y = Vector(up) - Vector(up).dot(z) * z
    if y.length < 1e-6:
        y = z.orthogonal()
    y.normalize()
    x = y.cross(z)
    return Matrix((
        (x.x, y.x, z.x, origin[0]), (x.y, y.y, z.y, origin[1]), (x.z, y.z, z.z, origin[2]), (0, 0, 0, 1)))


def flat_shape(name, material, pts2d, M, scale=1.0, depth=0.01, bevel=0.003, noline=False):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = depth
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts2d) - 1)
    for p, (x, y) in zip(sp.points, pts2d):
        p.co = (x * scale, y * scale, 0, 1)
    sp.use_cyclic_u = True
    cu.materials.append(material)
    ob = link(bpy.data.objects.new(name, cu), noline)
    ob.matrix_world = M
    return ob


def heart_obj(name, material, origin, normal, size, depth=0.012, up=(0, 0, 1)):
    return flat_shape(name, material, heart2d(), frame_matrix(origin, normal, up), size, depth,
                      bevel=min(0.003, size * 0.03))   # 大きいベベルはくぼみに棘が出る


def parent_to(children, root):
    for c in children:
        c.parent = root


def bow(name, loc, forward, s, wing, knot=None, bell=None, heart=None, tails=True, tail_len=1.0, up=(0, 0, 1)):
    """リボン. forward がリボンの正面の向き, s が大きさ."""
    root = link(bpy.data.objects.new(name, None))
    root.matrix_world = frame_matrix(loc, Vector(forward), up) @ Matrix.Rotation(math.pi / 2, 4, "X")
    # ↑ ローカルの -Y が forward、+Z が up になる
    knot = knot or wing
    kids = []
    for side in (-1, 1):
        def pinch(co, side=side):
            f = 0.32 + 0.68 * max(0.0, (co.x * side + 1) / 2) ** 0.7
            return (co.x, co.y * f, co.z * f * (1 + 0.15 * co.x * side))
        kids.append(sphere(f"{name}_w", wing, (side * 0.43 * s, 0, 0.05 * s), (0.46 * s, 0.17 * s, 0.33 * s),
                           (0, -side * 0.28, 0), deform=pinch))
        if tails:
            kids.append(sphere(f"{name}_t", wing, (side * 0.17 * s, 0.03 * s, -0.36 * s * tail_len),
                               (0.11 * s, 0.05 * s, 0.38 * s * tail_len), (0, side * 0.42, 0)))
    kids.append(sphere(f"{name}_k", knot, (0, -0.02 * s, 0), (0.15 * s, 0.13 * s, 0.17 * s)))
    if bell:
        kids.append(sphere(f"{name}_bell", bell, (0, -0.16 * s, -0.02 * s), (0.15 * s,) * 3))
        kids.append(sphere(f"{name}_slit", MATS["dark"], (0, -0.29 * s, -0.06 * s), (0.08 * s, 0.03 * s, 0.015 * s)))
    if heart:
        h = heart_obj(f"{name}_h", heart, (0, 0, 0), (0, -1, 0), 0.17 * s, depth=0.06 * s)
        h.matrix_world = Matrix.Translation((0, -0.13 * s, 0.0)) @ frame_matrix((0, 0, 0), (0, -1, 0))
        kids.append(h)
    parent_to(kids, root)
    return root


# ---- 顔のテクスチャ ------------------------------------------------------------------
def draw_face(path, size=1024):
    """頭のローカル座標 (x,z ∈ [-1,1]) に合わせて目・口・ほっぺを描く."""
    S = size * 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    def px(wx, wz):   # ワールド座標 → 画素
        lx, lz = (wx - HEAD_C.x) / HEAD_S.x, (wz - HEAD_C.z) / HEAD_S.z
        return (lx + 1) / 2 * S, (1 - (lz + 1) / 2) * S

    # ほっぺ
    blush = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blush)
    for sx in (-1, 1):
        cx, cy = px(sx * 0.3, 1.655)
        bd.ellipse((cx - 70, cy - 34, cx + 70, cy + 34), fill=(255, 120, 150, 120))
    im = Image.alpha_composite(im, blush.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(im)

    for sx in (-1, 1):
        cx, cy = px(sx * 0.215, 1.74)
        w, h = 0.19 / HEAD_S.x / 2 * S, 0.25 / HEAD_S.z / 2 * S
        top, bot = cy - h / 2, cy + h / 2

        def lid_y(x):   # まぶたのライン (真ん中が高い、ゆるいアーチ)
            u = (x - cx) / (w / 2)
            return top + h * 0.12 + h * 0.09 * u * u

        xs = [cx - w * 0.62 + w * 1.24 * k / 40 for k in range(41)]
        above = [(x, lid_y(x)) for x in xs] + [(xs[-1], 0), (xs[0], 0)]
        # 白目 (うっすら)
        mask = Image.new("L", (S, S), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse((cx - w * 0.6, top, cx + w * 0.6, bot), fill=255)
        md.polygon(above, fill=0)
        im.paste((255, 255, 255, 255), (0, 0), mask)
        # 瞳 (上が濃い紫 → 下が明るいラベンダー)
        grad = Image.new("RGBA", (S, S))
        gd = ImageDraw.Draw(grad)
        for yy in range(int(top), int(bot) + 1):
            t = (yy - top) / h
            gd.line((cx - w, yy, cx + w, yy), fill=(int(75 + 125 * t), int(45 + 110 * t), int(140 + 105 * t), 255))
        mask = Image.new("L", (S, S), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse((cx - w / 2, top, cx + w / 2, bot), fill=255)
        md.polygon(above, fill=0)
        im.paste(grad, (0, 0), mask)
        pm = Image.new("L", (S, S), 0)
        pd = ImageDraw.Draw(pm)
        pd.ellipse((cx - w * 0.22, cy - h * 0.2, cx + w * 0.22, cy + h * 0.22), fill=255)
        pd.polygon(above, fill=0)
        im.paste((65, 28, 110, 255), (0, 0), pm)
        d = ImageDraw.Draw(im)
        d.arc((cx - w / 2, top, cx + w / 2, bot), 15, 165, fill=(80, 35, 100, 255), width=8)
        # ハイライト
        ly = lid_y(cx - w * 0.3 * sx)
        d.ellipse((cx - w * 0.3 * sx - 30, ly + 22, cx - w * 0.3 * sx + 30, ly + 92), fill=(255, 255, 255, 255))
        d.ellipse((cx + w * 0.2 * sx - 14, cy + h * 0.2, cx + w * 0.2 * sx + 14, cy + h * 0.2 + 26),
                  fill=(255, 255, 255, 240))
        # 上まつげ (まぶたのアーチに沿った太い線 + 目尻のはね)
        lx = [cx - sx * w * 0.6 + sx * w * 1.25 * k / 30 for k in range(31)]
        lash = [(x, lid_y(x) - 2) for x in lx]
        d.line(lash, fill=(48, 18, 42, 255), width=26, joint="curve")
        ox, oy = lash[-1]
        d.polygon([(ox - sx * 30, oy - 12), (ox + sx * 34, oy - 46), (ox + sx * 10, oy + 14)], fill=(48, 18, 42, 255))
        for k in range(3):
            bx = ox - sx * (14 + k * 26)
            by = lid_y(bx)
            d.line((bx, by - 8, bx + sx * 18, by - 38 + k * 6), fill=(48, 18, 42, 255), width=9)
        # 下まつげ
        d.arc((cx - w * 0.42, cy, cx + w * 0.42, bot + 14), 65, 115, fill=(120, 55, 85, 255), width=7)
    # 口 (小さい「o」)
    mx, my = px(0, 1.585)
    d.ellipse((mx - 12, my - 9, mx + 12, my + 11), fill=(150, 50, 70, 255))
    d.ellipse((mx - 5, my - 2, mx + 5, my + 8), fill=(230, 120, 140, 255))
    im.resize((size, size), Image.LANCZOS).save(path)


# ---- パーツ ------------------------------------------------------------------------
MATS = {}


def make_materials():
    MATS.update(
        skin=mat("skin", lin("#ffe9e0"), rough=0.55),
        hair=mat("hair", lin("#b23a6c"), rough=0.45, coat=0.1),
        rasp=mat("rasp", lin("#a8264f"), rough=0.6, sheen=0.4),
        pink=mat("pink", lin("#fbbde4"), rough=0.55, sheen=0.5),
        white=mat("white", lin("#f7f3f4"), rough=0.6, sheen=0.3),
        choco=mat("choco", lin("#5a2f2a"), rough=0.2, coat=0.7),
        shoe=mat("shoe", lin("#6a3e38"), rough=0.35, coat=0.3),
        gold=mat("gold", lin("#f2c463"), rough=0.22, metal=1.0),
        dark=mat("dark", lin("#3a1c1c"), rough=0.5),
        silver=mat("silver", lin("#f4f2f6"), rough=0.2, metal=0.6),
        stripe=mat_stripe("stripe", lin("#a8264f"), lin("#ffd98a")),
        fishnet=mat_fishnet("fishnet", lin("#f7f3f4"), lin("#3a2026")),
    )


def build_head(face_png):
    sphere("head", MATS["skin"], HEAD_C, HEAD_S, seg=64, rings=48)
    # 顔の前面だけを少し大きくした殻に、描いた顔を貼る
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=64, radius=1.004)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().y > -0.3], context="FACES")
    uv = bm.loops.layers.uv.new()
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = ((lp.vert.co.x + 1) / 2, (lp.vert.co.z + 1) / 2)
    place(mesh_obj("face", bm, mat_decal("face", face_png), noline=True), HEAD_C, (0, 0, 0), HEAD_S)
    # 耳 (髪で半分隠れる)
    for sx in (-1, 1):
        sphere("ear", MATS["skin"], (sx * 0.62, 0.02, 1.76), (0.06, 0.05, 0.09))
    sphere("neck", MATS["skin"], (0, 0.0, 1.36), (0.075, 0.075, 0.14))


def build_hair():
    c, s = Vector((0, 0.025, 1.87)), Vector((0.67, 0.625, 0.648))
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=256, v_segments=192, radius=1)
    kill = []
    for v in bm.verts:
        w = c + Vector((v.co.x * s.x, v.co.y * s.y, v.co.z * s.z))
        face = w.y < -0.05 and abs(w.x) < 0.44 and w.z < 1.935     # ぱっつん前髪
        side_cut = w.z < 1.43
        if face or side_cut:
            kill.append(v)
    bmesh.ops.delete(bm, geom=kill, context="VERTS")
    hair = place(mesh_obj("hair", bm, MATS["hair"]), c, (0, 0, 0), s)
    md = hair.modifiers.new("solid", "SOLIDIFY")
    md.thickness, md.offset = 0.03, 1
    # ドリル (縦ロール)
    for sx in (-1, 1):
        pts, radii = [], []
        n = 70
        for i in range(n):
            t = i / (n - 1)
            a = t * math.tau * 4.2
            R = 0.075 * (1 - t) + 0.02
            pts.append((sx * (0.66 + 0.06 * t) + R * math.cos(a) * sx, 0.1 + R * math.sin(a),
                        1.95 - 0.7 * t))
            radii.append(1.0 - 0.62 * t)
        tube("drill", MATS["hair"], pts, radius=0.13, radii=radii)
        sphere("drill_top", MATS["hair"], pts[0], (0.13, 0.13, 0.13))
        # 耳の前に流れる横の髪 (おくれ毛)
        tube("sidelock", MATS["hair"], [(sx * 0.43, -0.4, 1.93), (sx * 0.46, -0.42, 1.7), (sx * 0.44, -0.36, 1.5),
                                        (sx * 0.42, -0.32, 1.42)], 0.05, radii=[1.2, 1.0, 0.7, 0.3])


def build_headwear():
    # ベレー帽 (右に傾けてかぶる)
    def puff(co):
        return (co.x, co.y, co.z * (0.75 if co.z < 0 else 1.0))
    beret = sphere("beret", MATS["white"], (0.16, 0.0, 2.43), (0.42, 0.4, 0.15), (0.12, 0.42, 0.0), seg=64,
                   rings=32, deform=puff)
    bpy.context.view_layer.update()
    mw = beret.matrix_world.copy()
    nm = mw.to_3x3().inverted().transposed()
    for nm_, mt, d, size in (("beret_heart", MATS["choco"], (0.62, -0.72, 0.05), 0.07),
                             ("beret_heart2", MATS["pink"], (0.82, -0.5, 0.2), 0.032)):
        p = Vector(d).normalized()
        heart_obj(nm_, mt, mw @ p, (nm @ p).normalized(), size, depth=0.015)
    # ストライプのカチューシャ (頭の丸みに沿った帯)
    ex, ey = Vector((1, 0, 0)), Vector((0, -math.sin(0.42), math.cos(0.42)))
    ax = ex.cross(ey)
    bm = bmesh.new()
    rows = []
    for i in range(61):
        th = math.radians(12 + 156 * i / 60)
        d = math.cos(th) * ex + math.sin(th) * ey
        p = Vector((0, 0.025, 1.87)) + Vector((d.x * 0.705, d.y * 0.665, d.z * 0.685))
        rows.append([bm.verts.new(p - ax * 0.05), bm.verts.new(p + ax * 0.05)])
    for i in range(60):
        bm.faces.new((rows[i][0], rows[i + 1][0], rows[i + 1][1], rows[i][1]))
    band = mesh_obj("headband", bm, MATS["stripe"])
    band.modifiers.new("solid", "SOLIDIFY").thickness = 0.02
    th = math.radians(128)
    d = math.cos(th) * ex + math.sin(th) * ey
    p = Vector((0, 0.025, 1.87)) + Vector((d.x * 0.72, d.y * 0.68, d.z * 0.7))
    bow("head_bow", p, (d.x * 0.6, -0.8, d.z * 0.3), 0.26, MATS["stripe"], knot=MATS["rasp"], bell=MATS["gold"],
        up=(d.x, d.y, d.z))


def build_body():
    W, R, P = MATS["white"], MATS["rasp"], MATS["pink"]
    sphere("torso", W, (0, 0, 1.16), (0.25, 0.19, 0.23))
    for sx in (-1, 1):
        sphere("bust", W, (sx * 0.085, -0.11, 1.19), (0.1, 0.085, 0.09))
    # コルセット + 上のピンクのレース
    ring_strip("corset", R, 1.12, 0.96, 0.215, 0.235, sy=0.82, thick=0.012)
    ring_strip("corset_lace", P, 1.14, 1.105, 0.225, 0.245, waves=34, amp=0.006, grow=False, sy=0.82,
               thick=0.006)
    # 胸のチョコのリボン
    bow("chest_bow", (0, -0.205, 1.145), (0, -1, 0.2), 0.13, MATS["choco"])
    # 襟 + 金の縁 + チョコのハートのブローチ + ピンクのタイ
    ring_strip("collar", R, 1.45, 1.33, 0.095, 0.125, thick=0.012)
    ring_tube("collar_gold", MATS["gold"], (0, 0, 1.45), 0.096, 0.008)
    heart_obj("brooch", MATS["choco"], (0, -0.135, 1.37), (0, -1, 0.1), 0.05, depth=0.02)
    ring_tube("brooch_rim", MATS["gold"], (0, -0.13, 1.37), 0.045, 0.006, normal=(0, -1, 0.1))
    for sx in (-1, 1):
        sphere("tie", P, (sx * 0.028, -0.165, 1.27), (0.032, 0.012, 0.075), (-0.35, sx * 0.25, 0))
    # 肩のパフ + 赤いカフスのフリル + 小さいピンクのリボン
    for sx in (-1, 1):
        sphere("puff", W, (sx * 0.275, 0.0, 1.27), (0.125, 0.12, 0.11))
        ring_strip("cuff", R, 1.2, 1.15, 0.085, 0.115, waves=14, amp=0.012, center=(sx * 0.3, 0.0), thick=0.008)
        bow("cuff_bow", (sx * 0.33, -0.1, 1.2), (sx * 0.3, -1, 0), 0.07, P)


def build_arms():
    S, R, P = MATS["skin"], MATS["rasp"], MATS["pink"]
    # 左手 (画面の左): 下ろしている
    tube("arm_l", S, [(-0.29, 0, 1.2), (-0.34, -0.02, 1.06), (-0.37, -0.03, 1.01)], 0.045)
    tube("glove_l", R, [(-0.37, -0.03, 1.02), (-0.41, -0.06, 0.92), (-0.44, -0.08, 0.83)], 0.05,
         radii=[1.1, 1.0, 0.9])
    ring_strip("glove_cuff_l", R, 1.045, 1.0, 0.05, 0.075, waves=12, amp=0.01, center=(-0.37, -0.03), thick=0.006)
    sphere("hand_l", R, (-0.45, -0.09, 0.79), (0.05, 0.04, 0.065), (0.2, 0.25, 0))
    bow("wrist_bow_l", (-0.42, -0.12, 0.89), (-0.3, -1, 0), 0.07, P)
    # 右手 (画面の右): 泡立て器を持ち上げている
    tube("arm_r", S, [(0.29, 0, 1.2), (0.38, -0.02, 1.08), (0.44, -0.04, 1.03)], 0.045)
    tube("glove_r", R, [(0.44, -0.04, 1.04), (0.52, -0.12, 1.1), (0.58, -0.2, 1.17)], 0.05, radii=[1.1, 1.0, 0.9])
    ring_strip("glove_cuff_r", R, 1.07, 1.02, 0.05, 0.075, waves=12, amp=0.01, center=(0.44, -0.04), thick=0.006)
    sphere("hand_r", R, (0.6, -0.22, 1.2), (0.055, 0.05, 0.06))
    bow("wrist_bow_r", (0.52, -0.17, 1.1), (0.3, -1, 0), 0.07, P)


def build_whisk():
    o = Vector((0.6, -0.23, 1.2))
    d = Vector((0.33, -0.08, 1.0)).normalized()
    side = d.cross(Vector((0, -1, 0))).normalized()
    fwd = side.cross(d).normalized()
    tube("whisk_handle", MATS["white"], [o - 0.24 * d, o, o + 0.1 * d], 0.03)
    ring_tube("whisk_charm", MATS["white"], o - 0.27 * d, 0.025, 0.006, normal=fwd)
    h0, L = o + 0.1 * d, 0.44
    for k in range(7):
        a = math.pi * k / 7
        rv = math.cos(a) * side + math.sin(a) * fwd
        pts = []
        for i in range(25):
            u = -1 + 2 * i / 24
            s_ = 1 - abs(u)                       # 0 → 1 (先端) → 0
            t = math.sin(math.pi * (1 - abs(u)) / 2)
            r = 0.125 * math.sin(math.pi * s_ * 0.92) ** 0.9 * (1 if u >= 0 else -1)
            pts.append(h0 + d * (L * t) + rv * r)
        tube("whisk_wire", MATS["silver"], pts, 0.007)
    # 先っぽのチョコがけ + 垂れ
    top = h0 + d * L
    sphere("whisk_choco", MATS["choco"], top - d * 0.1 + side * 0.03, (0.14, 0.12, 0.12),
           rot=(0, math.atan2(d.x, d.z), 0), deform=lambda co: (co.x, co.y, co.z * (1.0 if co.z > -0.2 else 0.6)))
    tube("whisk_drip", MATS["choco"], [top - d * 0.12 + side * 0.15 + fwd * 0.02, top - d * 0.22 + side * 0.16,
                                       top - d * 0.27 + side * 0.15], 0.025, radii=[1, 0.8, 1.2])
    bow("whisk_bow", h0 + d * 0.02 - fwd * 0.03, (0.2, -1, 0.1), 0.2, MATS["stripe"], knot=MATS["rasp"],
        heart=MATS["choco"], up=d)


def build_skirt():
    W, R = MATS["white"], MATS["rasp"]
    ring_strip("skirt", R, 1.0, 0.66, 0.24, 0.58, waves=9, amp=0.035, power=0.85, thick=0.012)
    ring_strip("skirt_frill", W, 0.69, 0.62, 0.565, 0.645, waves=48, amp=0.014, grow=False, thick=0.008)
    ring_strip("petticoat", W, 0.665, 0.58, 0.47, 0.55, waves=42, amp=0.012, grow=False, thick=0.008,
               phase=0.6)


def build_apron():
    T, B = Vector((0, -0.25, 1.07)), Vector((0, -0.6, 0.66))
    up = (T - B).normalized()
    n = Vector((0, -up.z, up.y))
    c = (T + B) / 2 + n * 0.035
    M = frame_matrix(c, n, up)
    hp = heart2d()
    flat_shape("apron", MATS["white"], hp, M, 0.27, depth=0.006)
    # ふちのレース (パイピング)
    pts = [M @ Vector((x * 0.27, y * 0.27, 0.004)) for x, y in hp[::2]]
    tube("apron_lace", MATS["white"], pts, 0.014, cyclic=True)
    # 上半分にチョコがとろっと
    top = [(x, y) for x, y in hp if y > 0.3]
    i0 = next(i for i, (x, y) in enumerate(hp) if y <= 0.3 and x > 0)
    ordered = [hp[(i0 - 1 - k) % len(hp)] for k in range(len(top))]   # 右下 → 上 → 左下
    ordered = [(x * 1.03, y * 1.03 + 0.005) for x, y in ordered]
    lo = []
    x0, x1 = ordered[-1][0], ordered[0][0]
    drips = [(-0.62, 0.22), (-0.36, 0.4), (-0.08, 0.28), (0.2, 0.46), (0.5, 0.3)]
    for i in range(121):
        x = x0 + (x1 - x0) * i / 120
        y = 0.3 - 0.03 * math.sin(x * 9) - sum(dd * math.exp(-((x - dx) / 0.075) ** 4) for dx, dd in drips)
        lo.append((x, y))
    flat_shape("apron_choco", MATS["choco"], ordered + lo,
               M @ Matrix.Translation((0, 0, 0.008)), 0.27, depth=0.008, bevel=0.006)


def build_back_bow():
    P, W = MATS["pink"], MATS["white"]
    bow("back_bow", (0, 0.3, 1.03), (0, 1, 0.15), 0.8, P, tails=False)
    for sx in (-1, 1):
        T = Vector((sx * 0.14, 0.32, 0.98))
        Bt = Vector((sx * 0.62, 0.12, 0.2))
        v = (Bt - T)
        Lh = v.length
        n0 = Vector((sx * 0.35, -1, 0)).normalized()
        n = (n0 - n0.dot(v.normalized()) * v.normalized()).normalized()
        M = frame_matrix(T, n, -v)
        w0, w1 = 0.2, 0.36
        shape = [(-w0 / 2, 0), (w0 / 2, 0), (w1 / 2, -Lh), (0, -Lh + 0.1), (-w1 / 2, -Lh)]
        flat_shape("bow_tail", P, shape, M, 1.0, depth=0.014, bevel=0.004)
        edge = [M @ Vector((x, y, 0.007)) for x, y in [(-w0 / 2, 0), (-w1 / 2, -Lh), (0, -Lh + 0.1),
                                                       (w1 / 2, -Lh), (w0 / 2, 0)]]
        for a, b in zip(edge[:-1], edge[1:]):
            tube("bow_tail_edge", W, [a, (a + b) / 2, b], 0.011)
        hm = M @ Matrix.Translation((0, -Lh * 0.68, -0.012))
        flat_shape("bow_tail_heart", W, heart2d(), hm, 0.075, depth=0.03, bevel=0.006)


def build_legs():
    W, R, P = MATS["white"], MATS["rasp"], MATS["pink"]
    for sx, m in ((-1, MATS["fishnet"]), (1, W)):
        x = sx * 0.13
        tube("leg", m, [(x, 0, 0.8), (x, -0.01, 0.5), (x, 0, 0.2)], 0.085, radii=[1.1, 0.85, 0.7])
        ring_tube("garter", R, (x, 0, 0.69), 0.088, 0.016)
    bow("leg_bow_l", (-0.13, -0.085, 0.5), (0, -1, 0), 0.12, R, heart=P)
    bow("garter_bow_r", (0.2, -0.06, 0.69), (0.6, -1, 0), 0.11, MATS["stripe"], knot=R)
    # 右脚に巻きつくストライプのリボン
    pts = []
    for i in range(40):
        t = i / 39
        a = t * math.tau * 2.3 + 0.5
        z = 0.66 - 0.42 * t
        r = 0.085 * (1.1 - 0.4 * (0.66 - z) / 0.46) + 0.012
        pts.append((0.13 + r * math.cos(a), r * math.sin(a), z))
    tube("leg_ribbon", MATS["stripe"], pts, 0.016)


def build_shoes():
    Sh = MATS["shoe"]
    for sx in (-1, 1):
        x = sx * 0.13
        box("sole", Sh, (x, -0.04, 0.06), (0.1, 0.17, 0.06), bevel=0.03)
        box("heel", Sh, (x, 0.08, 0.09), (0.09, 0.07, 0.09), bevel=0.03)
        sphere("shoe_upper", Sh, (x, -0.05, 0.16), (0.1, 0.15, 0.075))
        ring_tube("strap", Sh, (x, 0, 0.25), 0.068, 0.014)
        ring_strip("shoe_frill", MATS["white"], 0.28, 0.25, 0.06, 0.085, waves=14, amp=0.008, center=(x, 0),
                   thick=0.005)
        bow("ankle_bow", (x, -0.085, 0.27), (0, -1, 0.1), 0.13, MATS["stripe"], knot=MATS["rasp"],
            bell=MATS["gold"])
        bow("toe_bow", (x, -0.19, 0.17), (0, -1, 0.5), 0.08, MATS["rasp"], heart=MATS["pink"], tails=False)


def build(out):
    global NOLINE
    bpy.ops.wm.read_factory_settings(use_empty=True)
    NOLINE = bpy.data.collections.new("noline")
    bpy.context.scene.collection.children.link(NOLINE)
    make_materials()
    face_png = os.path.abspath(os.path.join(out, "face_tex.png"))
    draw_face(face_png)
    build_head(face_png)
    build_hair()
    build_headwear()
    build_body()
    build_arms()
    build_whisk()
    build_skirt()
    build_apron()
    build_back_bow()
    build_legs()
    build_shoes()
    root = bpy.data.objects.new("chara", None)
    bpy.context.scene.collection.objects.link(root)
    for ob in list(bpy.data.objects):
        if ob is not root and ob.parent is None and ob.type in ("MESH", "CURVE", "EMPTY"):
            ob.parent = root
    for ob in bpy.data.objects:             # 断面用の形状オブジェクトは非表示
        if ob.type == "CURVE" and ob.data.dimensions == "2D" and ob.name.startswith("prof"):
            ob.hide_render = True
    return root


# ---- 撮影 --------------------------------------------------------------------------
def setup_scene(samples=24, res=(1920, 1080)):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.use_denoising = True
    sc.cycles.denoising_quality = "BALANCED"
    sc.cycles.max_bounces = 6
    sc.cycles.transparent_max_bounces = 16
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.render.fps = 30
    # 輪郭線 (Freestyle)
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    sc.render.line_thickness = 1.0
    fs = sc.view_layers[0].freestyle_settings
    fs.crease_angle = math.radians(120)
    ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("lines")
    ls.select_silhouette, ls.select_border, ls.select_crease = True, True, False
    ls.select_by_collection = True
    ls.collection = NOLINE
    ls.collection_negation = "EXCLUSIVE"
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("line")
    ls.linestyle.color = (0.32, 0.1, 0.16)
    ls.linestyle.thickness = 2.6

    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1.0, 0.96, 0.97, 1)
    bg.inputs["Strength"].default_value = 0.4

    def area(name, loc, energy, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, color
        ob = bpy.data.objects.new(name, ld)
        sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0, 0, 1.2)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    area("key", (-3.0, -5.0, 4.5), 330, 4.0, (1.0, 0.97, 0.95))
    area("fill", (4.0, -4.0, 2.0), 140, 5.0, (1.0, 0.93, 0.96))
    area("rim", (1.0, 5.0, 4.0), 320, 3.0)

    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 62
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    cam.location = (0, -9.2, 2.1)
    cam.rotation_euler = (Vector((0, 0, 1.33)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam


def still(root, path, angle):
    root.rotation_euler = (0, 0, math.radians(angle))
    sc = bpy.context.scene
    sc.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)


def turntable(root, out, frames=240):
    sc = bpy.context.scene
    seq = os.path.join(out, "seq_turn")
    os.makedirs(seq, exist_ok=True)
    for f in range(frames):
        p = os.path.join(seq, f"f_{f:04d}.png")
        if os.path.exists(p):
            continue
        still(root, p, -360 * f / frames)
    pat = os.path.join(seq, "f_%04d.png")
    base = os.path.join(out, "chara_turn")
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", pat]
    subprocess.run([*ff, "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                    "-alpha_bits", "16", "-vendor", "apl0", base + ".mov"], check=True)
    subprocess.run([*ff, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
                    "-row-mt", "1", "-auto-alt-ref", "0", base + ".webm"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=0x00FF00:s=1920x1080:r=30",
                    "-framerate", "30", "-i", pat, "-filter_complex", "[0][1]overlay=shortest=1,format=yuv420p",
                    "-c:v", "libx264", "-crf", "16", "-movflags", "+faststart", base + "_greenback.mp4"], check=True)


def export_models(root, out):
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(out, "sd_chara.blend")))
    try:
        bpy.ops.export_scene.gltf(filepath=os.path.abspath(os.path.join(out, "sd_chara.glb")),
                                  export_apply=True, export_lights=False, export_cameras=False)
    except Exception as e:     # glb は可能なら
        print("glb export failed:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="chara_out")
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--angles", type=float, nargs="*", default=[0, -35, -90, 180])
    ap.add_argument("--turntable", action="store_true")
    ap.add_argument("--turn-samples", type=int, default=12)
    ap.add_argument("--no-export", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    root = build(a.out)
    setup_scene(a.samples)
    for ang in a.angles:
        still(root, os.path.join(a.out, f"view_{int(ang):+04d}.png"), ang)
    if not a.no_export:
        root.rotation_euler = (0, 0, 0)
        export_models(root, a.out)
    if a.turntable:
        bpy.context.scene.cycles.samples = a.turn_samples
        turntable(root, a.out)


if __name__ == "__main__":
    main()
