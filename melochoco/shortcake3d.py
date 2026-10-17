"""いちごのショートケーキ (カット1切れ) の3Dモデルを作って、回転する透過動画にする (Blender Cycles).

  pip install bpy
  python3 shortcake3d.py --out cake_out                 # 8秒で1回転するループ (240フレーム)
  python3 shortcake3d.py --out cake_out --preview 0 60  # 指定フレームの静止画だけ

出力 (1920x1080 / 30fps)
- shortcake_turn.mov            ProRes 4444 (アルファ付き)
- shortcake_turn.webm           VP9 (アルファ付き)
- shortcake_turn_greenback.mp4  グリーンバック
スポンジ2段 + 生クリーム + 断面に半割りのいちご、上にクリームの絞りと丸ごとのいちご.
"""
import argparse
import glob
import math
import os
import random
import subprocess

import bpy
import bmesh  # noqa: E402  (bpy を先に import する必要がある)
from mathutils import Matrix, Vector

R = 1.0                     # ケーキの半径
HALF = math.radians(27.5)   # カットの角度の半分 (55度の1切れ)
COAT = 0.05                 # 外側のクリームの厚み
Z_CRUST, Z_S1, Z_CR, Z_S2, Z_TOP = 0.02, 0.25, 0.41, 0.66, 0.74


# ---- マテリアル -------------------------------------------------------------------
def principled(name, color, rough=0.5, sss=0.0, sss_r=(1.0, 0.5, 0.3), sss_scale=0.05, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Subsurface Weight"].default_value = sss
    b.inputs["Subsurface Radius"].default_value = sss_r
    b.inputs["Subsurface Scale"].default_value = sss_scale
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.08
    return m, b


def mat_sponge(name, color, scale=70):
    """ふわふわのスポンジ: ボロノイで気泡のくぼみ + ノイズで色むら."""
    m, b = principled(name, color, rough=0.85)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = scale
    vor.inputs["Randomness"].default_value = 1.0
    noi = nt.nodes.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 18
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.004
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], noi.inputs["Vector"])
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["Factor"].default_value = 0.25
    mix.inputs[6].default_value = (*color, 1)
    mix.inputs[7].default_value = (color[0] * 0.92, color[1] * 0.85, color[2] * 0.7, 1)
    nt.links.new(noi.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def mat_cream():
    m, b = principled("cream", (1.0, 0.985, 0.96), rough=0.45)   # 表面下散乱は重いのでいちごだけ
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noi = nt.nodes.new("ShaderNodeTexNoise")
    noi.inputs["Scale"].default_value = 9
    noi.inputs["Detail"].default_value = 4
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.01
    nt.links.new(tc.outputs["Object"], noi.inputs["Vector"])
    nt.links.new(noi.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_berry():
    """つやつやのいちご (ナパージュのコート + 表面下散乱)."""
    m, b = principled("berry", (0.78, 0.02, 0.06), rough=0.3, sss=0.35, sss_r=(1.0, 0.15, 0.1),
                      sss_scale=0.03, coat=0.9)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.95, 0.25, 0.22, 1)   # へた側は少し明るい
    els[1].position, els[1].color = 0.35, (0.8, 0.02, 0.06, 1)
    e = els.new(1.0)
    e.color = (0.6, 0.01, 0.04, 1)
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = -1.0
    mapr.inputs["From Max"].default_value = 1.3
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
    nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def mat_berry_cut():
    """半割りいちごの断面: 中心は白っぽく、外側ほど赤い."""
    m, b = principled("berry_cut", (1, 0.6, 0.6), rough=0.25, coat=0.5)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (1.0, 0.86, 0.84, 1)
    els[1].position, els[1].color = 1.0, (0.72, 0.02, 0.07, 1)
    for pos, col in [(0.45, (1.0, 0.55, 0.58, 1)), (0.8, (0.92, 0.12, 0.18, 1))]:
        e = els.new(pos)
        e.color = col
    nt.links.new(tc.outputs["Object"], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


# ---- 形 ---------------------------------------------------------------------------
def obj_from_bm(name, bm, material, smooth_angle=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.append(material)
    if smooth_angle is not None:
        for p in me.polygons:
            p.use_smooth = True
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle))
        ob.select_set(False)
    return ob


def wedge(name, r0, r1, z0, z1, material, seg=64, bevel=0.0):
    """扇形 (r0=0) または扇形のリングの柱."""
    prof = [(r1 * math.cos(a), r1 * math.sin(a)) for a in
            [-HALF + 2 * HALF * i / seg for i in range(seg + 1)]]
    if r0 > 0:
        prof += [(r0 * math.cos(a), r0 * math.sin(a)) for a in
                 [HALF - 2 * HALF * i / seg for i in range(seg + 1)]]
    else:
        prof.append((0.0, 0.0))
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in prof]
    top = [bm.verts.new((x, y, z1)) for x, y in prof]
    n = len(prof)
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    ob = obj_from_bm(name, bm, material, smooth_angle=35)
    if bevel:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = 4
        md.limit_method = "ANGLE"
        md.angle_limit = math.radians(50)
    return ob


def berry_mesh(name, material, w=0.12, h=0.15):
    """先がとがった丸ごといちご (先端が +Z)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1)
    ob = bpy.context.active_object
    ob.name = name
    for v in ob.data.vertices:
        x, y, z = v.co
        t = (z + 1) / 2
        k = 1.0 - 0.72 * t ** 1.7
        if z < -0.5:                       # へた側を少し平らに
            z = -0.5 + (z + 0.5) * 0.55
        v.co = (x * k, y * k, z * 1.2)
    ob.scale = (w, w, h / 1.2)
    ob.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return ob


def add_seeds(berry, seed_mat, rng, n=70):
    """種 (つぶつぶ) を表面に並べる."""
    me = berry.data
    base = bpy.data.meshes.new("seed")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=1)
    bm.to_mesh(base)
    bm.free()
    base.materials.append(seed_mat)
    verts = [v for v in me.vertices if -0.55 < v.co.z < 1.05]
    for v in rng.sample(verts, n):
        s = bpy.data.objects.new("seed", base)
        bpy.context.collection.objects.link(s)
        s.parent = berry
        nrm = v.normal
        s.location = v.co + nrm * 0.0
        s.rotation_euler = nrm.to_track_quat("Z", "Y").to_euler()
        sc = berry.scale
        s.scale = (0.006 / sc.x, 0.009 / sc.y, 0.004 / sc.z)


def star_profile(points=8, r_out=0.07, r_in=0.045):
    cu = bpy.data.curves.new("star", "CURVE")
    cu.dimensions = "2D"
    sp = cu.splines.new("POLY")
    pts = []
    for i in range(points * 2):
        a = math.pi * i / points
        r = r_out if i % 2 == 0 else r_in
        pts.append((r * math.cos(a), r * math.sin(a), 0, 1))
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = co
    sp.use_cyclic_u = True
    sp.use_smooth = True
    ob = bpy.data.objects.new("star", cu)
    bpy.context.collection.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


def rosette(name, material, cx, cy, cz, prof):
    """生クリームの絞り (星口金をうずまき状に)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "OBJECT"
    cu.bevel_object = prof
    cu.use_fill_caps = True
    cu.resolution_u = 4
    sp = cu.splines.new("POLY")
    n = 90
    sp.points.add(n - 1)
    for i, p in enumerate(sp.points):
        t = i / (n - 1)
        a = t * math.tau * 2.3
        r = 0.14 * (1 - t) ** 0.8 + 0.005
        p.co = (cx + r * math.cos(a), cy + r * math.sin(a), cz + 0.03 + 0.2 * t ** 0.9, 1)
        p.radius = 1.0 if t < 0.75 else max(0.05, 1 - (t - 0.75) / 0.25)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob


def cut_slices(material, rng):
    """両方の切り口の、真ん中のクリーム層に見える半割りいちご."""
    obs = []
    zc = (Z_S1 + Z_CR) / 2
    for side in (1, -1):
        phi = side * HALF
        X = Vector((math.cos(phi), math.sin(phi), 0))
        nrm = Vector((-math.sin(phi), side * math.cos(phi), 0))   # 切り口の外向き
        Y = Vector((0, 0, 1))
        Z = X.cross(Y)
        for k, r in enumerate([0.22, 0.47, 0.72]):
            bpy.ops.mesh.primitive_circle_add(vertices=48, radius=1, fill_type="TRIFAN")
            ob = bpy.context.active_object
            for v in ob.data.vertices:          # 少したまご形に
                x, y, _ = v.co
                v.co.x = x * (1 - 0.18 * y)
            rot = Matrix((X, Y, Z)).transposed().to_4x4()
            ob.matrix_world = (Matrix.Translation(X * (r + rng.uniform(-0.03, 0.03)) + Vector((0, 0, zc))
                                                  + nrm * 0.004) @ rot)
            ob.scale = (0.105, 0.064, 1)
            ob.data.materials.append(material)
            bpy.ops.object.shade_smooth()
            obs.append(ob)
    return obs


def build(seed=3):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    rng = random.Random(seed)
    sponge = mat_sponge("sponge", (1.0, 0.76, 0.36))
    crust = mat_sponge("crust", (0.78, 0.5, 0.24), scale=110)
    cream = mat_cream()
    berry = mat_berry()
    cut = mat_berry_cut()
    seedm, _ = principled("seed", (0.95, 0.75, 0.3), rough=0.4)

    parts = [
        wedge("crust", 0, R, 0, Z_CRUST, crust, bevel=0.006),
        wedge("sponge1", 0, R, Z_CRUST, Z_S1, sponge),
        wedge("cream_mid", 0, R, Z_S1, Z_CR, cream),
        wedge("sponge2", 0, R, Z_CR, Z_S2, sponge),
        wedge("cream_top", 0, R + COAT, Z_S2, Z_TOP, cream, bevel=0.03),
        wedge("cream_back", R, R + COAT, 0, Z_TOP - 0.015, cream, bevel=0.015),
    ]
    parts += cut_slices(cut, rng)
    prof = star_profile()
    parts.append(rosette("rosette", cream, 0.82, 0.0, Z_TOP, prof))
    b = berry_mesh("berry", berry, w=0.17, h=0.22)
    b.location = (0.5, 0.0, Z_TOP + 0.17)
    b.rotation_euler = (math.radians(8), math.radians(-6), 0)
    add_seeds(b, seedm, rng)
    parts.append(b)

    # 扇形の重心を回転の中心に
    cx = 2 * R * math.sin(HALF) / (3 * HALF)
    pivot = bpy.data.objects.new("pivot", None)
    bpy.context.collection.objects.link(pivot)
    pivot.location = (cx, 0, 0)
    bpy.context.view_layer.update()
    for p in parts:
        if p.parent is None:
            mw = p.matrix_world.copy()
            p.parent = pivot
            p.matrix_world = mw
    pivot.location = (0, 0, 0)
    return pivot


def setup_scene(pivot, frames, samples, res):
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.fps = 30
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.03
    sc.cycles.use_denoising = True
    sc.cycles.denoising_quality = "BALANCED"
    sc.cycles.max_bounces = 6
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.0

    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1.0, 0.95, 0.96, 1)
    bg.inputs["Strength"].default_value = 0.3

    def area(name, loc, energy, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, color
        ob = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector((0, 0, 0.4)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    area("key", (-2.6, -3.0, 4.0), 230, 3.0, (1.0, 0.97, 0.93))
    area("fill", (3.2, -2.4, 1.8), 70, 4.0, (1.0, 0.93, 0.95))
    area("rim", (0.8, 3.8, 3.2), 260, 2.5, (1.0, 0.95, 0.97))

    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 50
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.collection.objects.link(cam)
    cam.location = (0, -3.35, 1.95)
    cam.rotation_euler = (Vector((0, 0, 0.45)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam

    # 8秒で1回転 (最後のフレームの次が最初と同じ角度になるように)
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert("rotation_euler", index=2, frame=1)
    pivot.rotation_euler = (0, 0, math.tau)
    pivot.keyframe_insert("rotation_euler", index=2, frame=frames + 1)
    for fc in _fcurves(pivot):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def _fcurves(ob):
    """Blender 4.4+ の layered action にも対応して F-Curve を列挙する."""
    act = ob.animation_data.action
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out


def encode(seq_dir, out, name, fps=30):
    pat = os.path.join(seq_dir, "f_%04d.png")
    base = os.path.join(out, name)
    run = lambda *a: subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                                     "-i", pat, *a], check=True)
    run("-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16",
        "-vendor", "apl0", base + ".mov")
    run("-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24", "-row-mt", "1",
        "-auto-alt-ref", "0", base + ".webm")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=0x00FF00:s=1920x1080:r=30",
                    "-framerate", str(fps), "-i", pat, "-filter_complex", "[0][1]overlay=shortest=1,format=yuv420p",
                    "-c:v", "libx264", "-crf", "16", "-movflags", "+faststart", base + "_greenback.mp4"], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cake_out")
    ap.add_argument("--frames", type=int, default=240)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--preview", type=int, nargs="*", help="このフレームだけ静止画で書き出す")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    pivot = build()
    setup_scene(pivot, a.frames, a.samples, (1920, 1080))
    sc = bpy.context.scene
    if a.preview is not None:
        for f in a.preview or [1]:
            sc.frame_set(f)
            sc.render.filepath = os.path.abspath(os.path.join(a.out, f"preview_{f:04d}.png"))
            bpy.ops.render.render(write_still=True)
        return
    seq = os.path.join(a.out, "seq_shortcake")
    os.makedirs(seq, exist_ok=True)
    sc.render.filepath = os.path.abspath(os.path.join(seq, "f_####"))
    sc.render.use_overwrite = False     # 途中から再開できるように
    bpy.ops.render.render(animation=True)
    assert len(glob.glob(os.path.join(seq, "f_*.png"))) == a.frames
    encode(seq, a.out, "shortcake_turn")


if __name__ == "__main__":
    main()
