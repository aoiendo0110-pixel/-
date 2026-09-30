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
    base[rib] = np.array([222, 28, 62]) / 255
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



# ---- お菓子の追加形状 ----------------------------------------------------------
def ell(x, y, z, cx, cy, cz, rx, ry, rz):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 + ((z - cz) / rz) ** 2 - 1


def f_macaron(x, y, z):
    top = ell(x, y, z, 0, 0, 0.26, 0.8, 0.8, 0.3)
    bot = ell(x, y, z, 0, 0, -0.26, 0.8, 0.8, 0.3)
    fill = ell(x, y, z, 0, 0, 0, 0.7, 0.7, 0.17)
    return np.minimum(np.minimum(top, bot), fill)


def c_macaron(shell):
    def f(p, n):
        x, y, z = p[..., 0], p[..., 1], p[..., 2]
        base = np.broadcast_to(np.array(shell, np.float32) / 255, p.shape).copy()
        th = np.arctan2(y, x)
        feet = (np.abs(z) > 0.07) & (np.abs(z) < 0.15 + 0.03 * np.sin(th * 28))
        base[feet] = np.minimum(np.array(shell) / 255 * 1.12, 1)
        base[np.abs(z) <= 0.07] = np.array([255, 246, 232]) / 255
        return base
    return f


def f_strawberry(x, y, z):
    w = 0.42 + 0.36 * np.clip((z + 0.95) / 1.25, 0, 1)
    body = (x * x + y * y) / (w * w) + ((z - 0.02) / 0.9) ** 2 - 1
    leaves = ell(x, y, z, 0, 0, 0.8, 0.5, 0.5, 0.08)
    stem = ell(x, y, z, 0, 0, 0.95, 0.06, 0.06, 0.16)
    return np.minimum(body, np.minimum(leaves, stem))


def c_strawberry(p, n):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    base = np.broadcast_to(np.array([228, 32, 64], np.float32) / 255, p.shape).copy()
    a = np.arctan2(y, x)
    h = np.sin(np.floor(a * 5) * 12.9898 + np.floor(z * 9) * 78.233) * 43758.5
    h -= np.floor(h)
    fa = (a * 5) % 1
    fz = (z * 9) % 1
    seed = (np.abs(fa - 0.5) < 0.16) & (np.abs(fz - 0.5) < 0.2) & (z < 0.7)
    base[seed] = np.array([255, 220, 90]) / 255
    base[z > 0.72] = np.array([90, 180, 90]) / 255
    return base


def f_cupcake(x, y, z):
    r = np.sqrt(x * x + y * y)
    th = np.arctan2(y, x)
    rc = (0.5 + 0.2 * (z + 0.95) / 0.8) * (1 + 0.035 * np.cos(th * 16))
    cup = np.maximum(r - rc, np.maximum(-0.95 - z, z + 0.12))
    fr = None
    for R, rr, zc in ((0.56, 0.21, -0.05), (0.4, 0.18, 0.2), (0.22, 0.15, 0.42)):
        q = r - R
        t = q * q + (z - zc) ** 2 - rr * rr
        fr = t if fr is None else np.minimum(fr, t)
    cherry = ell(x, y, z, 0, 0, 0.72, 0.19, 0.19, 0.19)
    return np.minimum(np.minimum(cup, fr), cherry)


def c_cupcake(p, n):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    base = np.broadcast_to(np.array([255, 196, 220], np.float32) / 255, p.shape).copy()
    th = np.arctan2(y, x)
    cup = z < -0.12
    stripe = np.sin(th * 8) > 0
    base[cup & stripe] = np.array([255, 110, 160]) / 255
    base[cup & ~stripe] = np.array([255, 250, 250]) / 255
    base[z > 0.55] = np.array([220, 20, 55]) / 255
    h = np.sin(np.floor(x * 16) * 12.9898 + np.floor(y * 16) * 78.233 + np.floor(z * 16) * 3.1) * 43758.5
    h -= np.floor(h)
    sp = (z > -0.12) & (z < 0.55) & (h > 0.88)
    cols = np.array([[255, 255, 255], [255, 220, 90], [110, 55, 35], [230, 30, 70]]) / 255
    base[sp] = cols[(h[sp] * 100).astype(int) % 4]
    return base


def f_cookie(x, y, z):
    return f_heart(x, y * 2.4, z)


def c_cookie(p, n):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    base = np.broadcast_to(np.array([236, 180, 105], np.float32) / 255, p.shape).copy()
    icing = (f_heart(x * 1.18, y * 0, z * 1.18 + 0.02) < 0) & (y < 0)
    base[icing] = np.array([255, 140, 185]) / 255
    ring = (f_heart(x * 1.1, y * 0, z * 1.1 + 0.01) < 0) & ~icing & (y < 0)
    base[ring] = np.array([255, 255, 255]) / 255
    dots = icing & (np.sin(x * 20) * np.sin(z * 20) > 0.85)
    base[dots] = np.array([255, 255, 255]) / 255
    return base


def f_bow(x, y, z):
    parts = []
    for s in (-1, 1):
        u, v = x - s * 0.48, z - 0.12
        c, sn = math.cos(0.35), math.sin(0.35) * s
        uu, vv = u * c + v * sn, -u * sn + v * c
        parts.append((uu / 0.5) ** 2 + (y / 0.2) ** 2 + (vv / 0.3) ** 2 - 1)
        u, v = x - s * 0.3, z + 0.52
        c, sn = math.cos(0.4), math.sin(0.4) * s
        uu, vv = u * c + v * sn, -u * sn + v * c
        parts.append((uu / 0.14) ** 2 + (y / 0.08) ** 2 + (vv / 0.48) ** 2 - 1)
    parts.append(ell(x, y, z, 0, -0.02, 0.1, 0.2, 0.24, 0.22))
    out = parts[0]
    for q in parts[1:]:
        out = np.minimum(out, q)
    return out


def c_bow(main, dot=(255, 255, 255)):
    def f(p, n):
        x, y, z = p[..., 0], p[..., 1], p[..., 2]
        base = np.broadcast_to(np.array(main, np.float32) / 255, p.shape).copy()
        dots = (np.sin(x * 16) * np.sin(z * 16) > 0.75) & (np.abs(x) > 0.22)
        base[dots] = np.array(dot) / 255
        return base
    return f


def f_cherry(x, y, z):
    a = ell(x, y, z, -0.33, 0, -0.4, 0.36, 0.36, 0.36)
    b = ell(x, y, z, 0.33, 0, -0.4, 0.36, 0.36, 0.36)
    s1 = ell(x + 0.33 * (z - 0.55) / 0.9, y, z, 0, 0, 0.1, 0.045, 0.045, 0.55)
    s2 = ell(x - 0.33 * (z - 0.55) / 0.9, y, z, 0, 0, 0.1, 0.045, 0.045, 0.55)
    return np.minimum(np.minimum(a, b), np.minimum(s1, s2))


def c_cherry(p, n):
    base = np.broadcast_to(np.array([215, 20, 50], np.float32) / 255, p.shape).copy()
    base[p[..., 2] > -0.05] = np.array([110, 60, 35]) / 255
    return base


def f_candy(x, y, z):
    mid = ell(x, y, z, 0, 0, 0, 0.46, 0.38, 0.38)
    ends = []
    for s in (-1, 1):
        k = np.clip((np.abs(x) - 0.4) / 0.45, 0, 1)
        ends.append(np.maximum(((y / 0.1) ** 2 + (z / (0.1 + 0.28 * k)) ** 2 - 1),
                               np.maximum(0.4 - s * x, s * x - 0.88)))
    return np.minimum(mid, np.minimum(ends[0], ends[1]))


def c_candy(a, b):
    def f(p, n):
        x, y, z = p[..., 0], p[..., 1], p[..., 2]
        base = np.broadcast_to(np.array(a, np.float32) / 255, p.shape).copy()
        st = np.sin(x * 9 + np.arctan2(z, y) * 2) > 0
        base[st & (np.abs(x) < 0.46)] = np.array(b) / 255
        return base
    return f


OBJECTS = {
    "heart": (f_heart, c_const((255, 110, 165)), 0.25, 1.0),
    "heart_white": (f_heart, c_const((255, 236, 244)), 0.25, 1.0),
    "choco_heart": (f_heart, c_choco_heart, 0.3, 1.2),
    "gift": (f_gift, c_gift, 0.45, 0.8),
    "donut": (f_torus, c_donut, -0.9, 0.7),
    "pearl": (f_sphere, c_const((255, 225, 238)), 0.0, 1.3),
    "bar": (f_bar, c_bar, 0.2, 1.0),
    "macaron": (f_macaron, c_macaron((255, 160, 195)), 0.55, 0.8),
    "macaron_y": (f_macaron, c_macaron((255, 214, 100)), 0.55, 0.8),
    "macaron_c": (f_macaron, c_macaron((150, 90, 60)), 0.55, 0.8),
    "strawberry": (f_strawberry, c_strawberry, 0.2, 1.1),
    "cupcake": (f_cupcake, c_cupcake, 0.35, 0.9),
    "cookie": (f_cookie, c_cookie, 0.15, 0.6),
    "bow": (f_bow, c_bow((220, 25, 60)), 0.1, 1.2),
    "bow_pink": (f_bow, c_bow((255, 130, 180)), 0.1, 1.2),
    "bow_bw": (f_bow, c_bow((34, 30, 32)), 0.1, 1.3),
    "cherry": (f_cherry, c_cherry, 0.1, 1.3),
    "candy": (f_candy, c_candy((255, 215, 90), (255, 255, 255)), 0.2, 1.2),
    "candy_p": (f_candy, c_candy((255, 120, 170), (255, 255, 255)), 0.2, 1.2),
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
