"""numpy だけで動く、ぷっくりツヤツヤな3Dスプライトのレンダラー.

各形状は「内側で負になる関数」で定義し、レイマーチ + 二分法で交点を求める。
回転させた連番スプライト (RGBA) を返す。
"""
import math
import os

import numpy as np
from PIL import Image

RANGE = 1.45  # 画面に収める物体空間の半幅


def _rot(rx, spin, roll):
    """spin: 縦軸まわりの回転, rx: 手前への傾き, roll: 画面内の傾き."""
    cx, sx = math.cos(rx), math.sin(rx)
    cs, ss = math.cos(spin), math.sin(spin)
    cr, sr = math.cos(roll), math.sin(roll)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Rz = np.array([[cs, -ss, 0], [ss, cs, 0], [0, 0, 1]])
    Ry = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
    return Ry @ Rx @ Rz


# ---- 形状 (座標: x 右, y 奥行き, z 上) ---------------------------------------
def f_heart(x, y, z):
    z = z * 1.08 + 0.08
    x = x * 1.02
    y = y * 1.25
    a = x * x + 2.25 * y * y + z * z - 1
    return a * a * a - x * x * z ** 3 - 0.1125 * y * y * z ** 3


def f_sphere(x, y, z):
    return x * x + y * y + z * z - 0.8


def f_torus(x, y, z, R=0.66, r=0.34):
    q = np.sqrt(x * x + z * z) - R
    return q * q + y * y - r * r


def f_rbox(x, y, z, b=(0.72, 0.72, 0.72), r=0.14):
    qx = np.abs(x) - b[0] + r
    qy = np.abs(y) - b[1] + r
    qz = np.abs(z) - b[2] + r
    out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
    inside = np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0)
    return out + inside - r


def f_gift(x, y, z):
    box = f_rbox(x, y, z + 0.12, (0.68, 0.68, 0.62), 0.1)
    bows = []
    for sx in (-1, 1):  # 上のリボンの輪っか (xz 平面のトーラス)
        px, pz = x - sx * 0.27, z - 0.72
        q = np.sqrt(px * px + (pz * 1.4) ** 2) - 0.24
        bows.append(q * q + y * y * 1.8 - 0.085 ** 2)
    knot = x * x + y * y + (z - 0.62) ** 2 - 0.12 ** 2
    return np.minimum(np.minimum(box, knot), np.minimum(bows[0], bows[1]))


def f_bar(x, y, z):
    return f_rbox(x, y, z, (0.62, 0.2, 0.85), 0.1)


# ---- 色 -------------------------------------------------------------------
def c_const(rgb):
    def f(p, n):
        return np.broadcast_to(np.array(rgb, np.float32) / 255, p.shape).copy()
    return f


def c_choco_heart(p, n):
    base = np.broadcast_to(np.array([95, 48, 32], np.float32) / 255, p.shape).copy()
    # ピンクのドリズル
    s = np.sin(p[..., 0] * 9 + p[..., 2] * 7 + np.sin(p[..., 2] * 5) * 1.5)
    m = (s > 0.82) & (p[..., 1] < 0)
    base[m] = np.array([255, 150, 190]) / 255
    return base


def c_gift(p, n):
    base = np.broadcast_to(np.array([255, 150, 195], np.float32) / 255, p.shape).copy()
    rib = (np.abs(p[..., 0]) < 0.13) | (np.abs(p[..., 1]) < 0.13) | (p[..., 2] > 0.48)
    base[rib] = np.array([255, 250, 250]) / 255
    dots = (np.sin(p[..., 0] * 22) * np.sin(p[..., 2] * 22) > 0.8) & ~rib
    base[dots] = np.array([255, 225, 238]) / 255
    return base


def c_donut(p, n):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    th = np.arctan2(z, x)
    base = np.broadcast_to(np.array([226, 170, 110], np.float32) / 255, p.shape).copy()
    icing = y < 0.04 + 0.07 * np.sin(th * 7)
    base[icing] = np.array([255, 140, 185]) / 255
    # スプリンクル
    h = np.sin(np.floor(x * 14) * 12.9898 + np.floor(z * 14) * 78.233 + np.floor(y * 14) * 3.1) * 43758.5
    h = h - np.floor(h)
    cols = np.array([[255, 255, 255], [120, 200, 255], [255, 230, 120], [110, 60, 40]]) / 255
    sp = icing & (h > 0.86)
    base[sp] = cols[(h[sp] * 100).astype(int) % 4]
    return base


def c_bar(p, n):
    base = np.broadcast_to(np.array([98, 52, 34], np.float32) / 255, p.shape).copy()
    gx = np.abs(((p[..., 0] + 0.62) / 0.413) % 1 - 0.5) > 0.44
    gz = np.abs(((p[..., 2] + 0.85) / 0.425) % 1 - 0.5) > 0.44
    base[(gx | gz) & (p[..., 1] < -0.1)] = np.array([60, 30, 20]) / 255
    return base


# ---- レンダリング ------------------------------------------------------------
def render(fn, col_fn, size, rx, spin, roll=0.0, steps=72, gloss=1.0):
    ss = 2  # アンチエイリアス
    N = size * ss
    u = np.linspace(-RANGE, RANGE, N, dtype=np.float32)
    U, V = np.meshgrid(u, -u)
    M = _rot(rx, spin, roll).astype(np.float32)
    Mi = M.T
    # ワールド: カメラは -y から +y を見る (正射影)
    o = np.stack([U, np.full_like(U, -2.0), V], -1)
    d = np.array([0, 1, 0], np.float32)
    oo = o @ Mi.T
    dd = d @ Mi.T

    def F(t):
        p = oo + t[..., None] * dd
        return fn(p[..., 0], p[..., 1], p[..., 2])

    t0, t1 = 2.0 - RANGE, 2.0 + RANGE
    ts = np.linspace(t0, t1, steps, dtype=np.float32)
    hit = np.zeros(U.shape, bool)
    tlo = np.zeros(U.shape, np.float32)
    thi = np.zeros(U.shape, np.float32)
    prev = F(np.full(U.shape, t0, np.float32))
    for i in range(1, steps):
        cur = F(np.full(U.shape, ts[i], np.float32))
        new = (~hit) & (cur < 0) & (prev >= 0)
        tlo[new], thi[new] = ts[i - 1], ts[i]
        hit |= new
        prev = cur
    for _ in range(12):
        mid = (tlo + thi) / 2
        inside = F(mid) < 0
        thi = np.where(inside, mid, thi)
        tlo = np.where(inside, tlo, mid)
    t = thi
    p = oo + t[..., None] * dd
    e = 2e-3
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    n = np.stack([fn(x + e, y, z) - fn(x - e, y, z), fn(x, y + e, z) - fn(x, y - e, z),
                  fn(x, y, z + e) - fn(x, y, z - e)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    base = col_fn(p, n)
    nw = n @ M.T  # ワールド法線
    L = np.array([-0.45, -0.7, 0.6], np.float32)
    L /= np.linalg.norm(L)
    Vd = np.array([0, -1, 0], np.float32)
    ndl = (nw * L).sum(-1)
    wrap = np.clip(0.5 + 0.5 * ndl, 0, 1)
    Hh = L + Vd
    Hh /= np.linalg.norm(Hh)
    spec = np.clip((nw * Hh).sum(-1), 0, 1) ** 60 * 0.9 * gloss
    spec2 = np.clip((nw * Hh).sum(-1), 0, 1) ** 8 * 0.15 * gloss
    rim = (1 - np.abs((nw * Vd).sum(-1))) ** 3
    col = base * (0.42 + 0.7 * wrap[..., None])
    col = col + (spec + spec2)[..., None] + rim[..., None] * np.array([1.0, 0.85, 0.92]) * 0.35
    # 下からのピンクの照り返し
    col = col + np.clip(-nw[..., 2], 0, 1)[..., None] * np.array([0.25, 0.08, 0.14]) * 0.6
    col = np.clip(col, 0, 1)
    rgba = np.zeros(U.shape + (4,), np.uint8)
    rgba[..., :3] = (col * 255).astype(np.uint8)
    rgba[..., 3] = hit * 255
    im = Image.fromarray(rgba, "RGBA")
    return im.resize((size, size), Image.LANCZOS)


OBJECTS = {
    "heart": (f_heart, c_const((255, 110, 165)), 0.25, 1.0),
    "heart_white": (f_heart, c_const((255, 236, 244)), 0.25, 1.0),
    "choco_heart": (f_heart, c_choco_heart, 0.3, 1.2),
    "gift": (f_gift, c_gift, 0.45, 0.8),
    "donut": (f_torus, c_donut, -0.9, 0.7),
    "pearl": (f_sphere, c_const((255, 225, 238)), 0.0, 1.3),
    "bar": (f_bar, c_bar, 0.2, 1.0),
}


def _job(args):
    name, size, i, n = args
    fn, col, rx, gloss = OBJECTS[name]
    return render(fn, col, size, rx, 2 * math.pi * i / n, 0.15 * math.sin(2 * math.pi * i / n), gloss=gloss)


def build_sprites(pool, cache_dir, spec):
    """spec: {name: (size, n_angles)} → {name: [PIL.Image]} (ディスクにキャッシュ)."""
    os.makedirs(cache_dir, exist_ok=True)
    out = {}
    for name, (size, n) in spec.items():
        paths = [os.path.join(cache_dir, f"{name}_{size}_{i:02d}.png") for i in range(n)]
        if all(os.path.exists(p) for p in paths):
            out[name] = [Image.open(p).convert("RGBA") for p in paths]
            continue
        ims = pool.map(_job, [(name, size, i, n) for i in range(n)])
        for im, p in zip(ims, paths):
            im.save(p)
        out[name] = ims
    return out
