"""イラスト1枚をまばたき + 体の揺れで動かす (約10秒ループ).

  python3 animate_illust.py --image illust.png --out anim.mp4 [--webm anim.webm] [--width 1920]

- 目は塗りつぶした「閉じ目」と、上まぶたを下へ押しつぶす中間フレームで瞬きさせる
- 体は cv2.remap の変形場で動かす (ふわふわ浮遊・頭の傾き・ツインテールの揺れ・泡立て器を振る腕・呼吸)
- 座標は元画像 (4409x3206) 基準。別サイズの画像でも比率で合わせる
"""
import argparse
import math
import subprocess

import cv2
import numpy as np
from PIL import Image

import imageio_ffmpeg

BASE_W = 4409
FPS = 30
DUR = 10.0

# 目: 輪郭ポリゴン, 閉じ目の線 [端, 中央, 端]
EYES = [
    dict(poly=[(2528, 836), (2553, 808), (2585, 785), (2625, 778), (2667, 792), (2688, 813), (2698, 860),
               (2684, 890), (2650, 910), (2605, 910), (2566, 892), (2542, 864)],
         lid=[(2532, 846), (2600, 884), (2692, 872)]),
    dict(poly=[(2876, 778), (2882, 733), (2913, 706), (2960, 693), (3012, 700), (3030, 725), (3027, 768),
               (3003, 812), (2960, 830), (2912, 824), (2886, 804)],
         lid=[(3024, 752), (2956, 800), (2880, 790)]),
]


def bezier(p, n=40):
    t = np.linspace(0, 1, n)[:, None]
    p = np.array(p, float)
    return (1 - t) ** 2 * p[0] + 2 * (1 - t) * t * p[1] + t ** 2 * p[2]


def eye_mask(shape, e, s, grow=1.0):
    m = np.zeros(shape[:2], np.uint8)
    p = np.array(e["poly"], float)
    c = p.mean(0)
    p = (c + (p - c) * grow) * s
    cv2.fillPoly(m, [np.round(p * 8).astype(np.int32)], 255, cv2.LINE_AA, shift=3)
    return cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=max(1, round(4 * s)))


def make_closed(rgba, s):
    """目を肌で埋めて、閉じたまぶたの線を描いた画像."""
    rgb = np.ascontiguousarray(rgba[..., :3])
    out = rgb.copy()
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    skin = (hsv[..., 2] > 195) & (hsv[..., 1] < 85)
    for e in EYES:
        m = eye_mask(rgb.shape, e, s)
        # 肌以外 (髪・睫毛) を材料にしないよう、目の周りの肌以外の画素も穴にしてから埋める
        near = eye_mask(rgb.shape, e, s, 1.9)
        hole = np.where((m > 0) | ((near > 0) & ~skin), 255, 0).astype(np.uint8)
        fill = cv2.inpaint(out, hole, max(3, round(24 * s)), cv2.INPAINT_TELEA)
        fill = cv2.GaussianBlur(fill, (0, 0), 5 * s)
        k = cv2.GaussianBlur(m, (0, 0), 2 * s)[..., None] / 255.0
        out = (out * (1 - k) + fill * k).astype(np.uint8)
    # まぶたの線 (抜き入りの太さ) と外側の睫毛
    ov = out.astype(np.float32)
    col = np.array([118, 66, 92], np.float32)
    layer = np.zeros(rgb.shape[:2], np.float32)
    for e in EYES:
        pts = bezier(e["lid"]) * s
        n = len(pts)
        for i in range(n - 1):
            u = i / (n - 1)
            w = (2.0 + 5.5 * math.sin(math.pi * min(1, u * 1.15)) ** 0.7) * s
            cv2.line(layer, tuple(np.round(pts[i] * 8).astype(int)), tuple(np.round(pts[i + 1] * 8).astype(int)),
                     1.0, max(1, round(w)), cv2.LINE_AA, shift=3)
        # 外側の睫毛 3本
        p0 = pts[0]
        d = pts[0] - pts[4]
        d /= np.linalg.norm(d)
        nrm = np.array([d[1], -d[0]]) if e["lid"][0][0] < e["lid"][2][0] else np.array([-d[1], d[0]])
        for k, (a, L) in enumerate([(-0.5, 26), (0.1, 30), (0.7, 22)]):
            base = pts[min(len(pts) - 1, k * 3)]
            dirv = d * math.cos(a) + nrm * math.sin(a) * 0.9
            tip = base + dirv * L * s
            cv2.line(layer, tuple(np.round(base * 8).astype(int)), tuple(np.round(tip * 8).astype(int)),
                     1.0, max(1, round(3 * s)), cv2.LINE_AA, shift=3)
    layer = np.clip(layer, 0, 1)[..., None]
    ov = ov * (1 - layer) + col * layer
    res = rgba.copy()
    res[..., :3] = np.clip(ov, 0, 255).astype(np.uint8)
    return res


def blink_frame(open_img, closed_img, o, s):
    """o=1 開き, o=0 閉じ. 中間は上まぶたを閉じ線の高さへ押しつぶす."""
    if o >= 0.999:
        return open_img
    if o <= 0.001:
        return closed_img
    out = closed_img.copy()
    H, W = open_img.shape[:2]
    for e in EYES:
        m = eye_mask(open_img.shape, e, s, 1.08)
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        # 閉じ線 (列ごとの y)
        pts = bezier(e["lid"], 200) * s
        xx = np.arange(x0, x1)
        order = np.argsort(pts[:, 0])
        yc = np.interp(xx, pts[order, 0], pts[order, 1])
        gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        ycg = yc[None, :].astype(np.float32)
        # 上半分は下へ潰す、下半分は少しだけ持ち上げる
        up = gy < ycg
        sy = np.where(up, ycg - (ycg - gy) / o, ycg + (gy - ycg) / (0.6 + 0.4 * o))
        sub = cv2.remap(open_img, gx, sy.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        eyeish = cv2.remap(m, gx, sy.astype(np.float32), cv2.INTER_LINEAR, borderValue=0).astype(np.float32) / 255
        region = m[y0:y1, x0:x1].astype(np.float32) / 255
        k = (eyeish * region)[..., None]
        blk = out[y0:y1, x0:x1].astype(np.float32)
        out[y0:y1, x0:x1] = (blk * (1 - k) + sub.astype(np.float32) * k).astype(np.uint8)
    return out


# ---------------------------------------------------------------- 体の動き
D = 4409 / 2000  # 下の座標は元画像を横2000pxで見たときの値 → 元解像度へ


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def soft_poly(shape, pts, s, pad, blur):
    m = np.zeros(shape, np.float32)
    cv2.fillPoly(m, [np.round((np.array(pts, float) * D * s + pad) * 8).astype(np.int32)], 1.0, cv2.LINE_AA, shift=3)
    return cv2.GaussianBlur(m, (0, 0), blur * D * s)


class Rig:
    def __init__(self, h, w, s, pad):
        self.s, self.pad = s, pad
        gy, gx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.gx, self.gy = gx, gy
        X, Y = (gx - pad) / (D * s), (gy - pad) / (D * s)  # 表示座標 (横2000px基準)
        # 頭 (髪ごと): 首より上。右は泡立て器の手の手前まで
        self.w_head = (1 - smooth(440, 482, Y)) * (1 - smooth(1535, 1580, X))
        self.p_head = (1265, 478)
        # ツインテール: 根元から先へいくほど揺れる
        self.w_curl_l = soft_poly((h, w), [(800, 120), (1000, 110), (1010, 300), (1000, 470), (800, 480)], s, pad, 18) \
            * smooth(120, 330, Y)
        self.p_curl_l = (975, 110)
        self.w_curl_r = soft_poly((h, w), [(1385, 110), (1545, 100), (1560, 480), (1395, 480)], s, pad, 14) \
            * smooth(120, 330, Y)
        self.p_curl_r = (1420, 105)
        # 泡立て器を持つ腕: 肘まわりで回す
        self.w_arm = soft_poly((h, w), [(1545, 380), (1840, 380), (1840, 700), (1640, 800), (1560, 770)], s, pad, 16) \
            * smooth(0, 60, np.hypot(X - 1575, Y - 745))
        self.p_arm = (1575, 745)
        # 浮いている脚 (網タイツ側): 膝で回す。膝の近くは動かさない
        self.w_leg = soft_poly((h, w), [(80, 640), (320, 610), (690, 450), (880, 430), (940, 560), (700, 650),
                                         (405, 770), (385, 890), (300, 925), (80, 925)], s, pad, 10) \
            * smooth(40, 260, np.hypot(X - 900, Y - 510))
        self.p_leg = (900, 510)
        # 呼吸: 胸から上を少し持ち上げる
        self.w_breath = np.clip((950 - Y) / 480, 0, 1) * np.exp(-((X - 1250) / 420) ** 2)

    def rot(self, p, deg):
        """点 p まわりに deg 回したときの変位 (出力座標px)."""
        a = math.radians(deg)
        px, py = p[0] * D * self.s + self.pad, p[1] * D * self.s + self.pad
        x, y = self.gx - px, self.gy - py
        c, sn = math.cos(a), math.sin(a)
        return x * c - y * sn - x, x * sn + y * c - y

    def maps(self, t):
        T = 2 * math.pi * t / DUR  # 10秒で1周 → ループ
        head = 2.2 * math.sin(2 * T) + 0.8 * math.sin(4 * T + 0.6)
        curl = 2.6 * math.sin(4 * T - 0.9) + 1.0 * math.sin(8 * T - 1.4)
        arm = 5.0 * math.sin(8 * T) ** 3 + 1.5 * math.sin(2 * T)
        leg = 3.0 * math.sin(4 * T + 1.2)
        dx = np.zeros_like(self.gx)
        dy = np.zeros_like(self.gx)
        # ツインテールは頭の回転 (w_head) に揺れを上乗せする
        for w, p, deg in ((self.w_head, self.p_head, head),
                          (self.w_curl_l, self.p_curl_l, curl),
                          (self.w_curl_r, self.p_curl_r, curl * 0.9),
                          (self.w_arm, self.p_arm, arm),
                          (self.w_leg, self.p_leg, leg)):
            ux, uy = self.rot(p, deg)
            dx += w * ux
            dy += w * uy
        dy += -self.w_breath * (4.0 * D * self.s) * (0.5 - 0.5 * math.cos(5 * T))
        # 全体: ふわふわ浮遊 + ほんの少しの傾き
        bob_y = 16 * D * self.s * math.sin(2 * T)
        bob_x = 5 * D * self.s * math.sin(T + 0.5)
        ga = math.radians(0.8 * math.sin(2 * T + 1.0))
        cx, cy = self.gx.shape[1] / 2, self.gx.shape[0] / 2
        # 出力 → 全体変換を戻す → 局所変形を戻す
        x0, y0 = self.gx - cx - bob_x, self.gy - cy - bob_y
        c, sn = math.cos(-ga), math.sin(-ga)
        qx, qy = x0 * c - y0 * sn + cx, x0 * sn + y0 * c + cy
        ix = np.clip(np.round(qx), 0, self.gx.shape[1] - 1).astype(np.int32)
        iy = np.clip(np.round(qy), 0, self.gx.shape[0] - 1).astype(np.int32)
        return (qx - dx[iy, ix]).astype(np.float32), (qy - dy[iy, ix]).astype(np.float32)


def openness(t):
    """まばたき (1=開き). 2回目はパチパチの2連続."""
    o = 1.0
    for tb in (1.7, 4.6, 4.95, 8.0):
        u = t - tb
        if 0 <= u < 0.07:
            o = min(o, 1 - u / 0.07)
        elif 0.07 <= u < 0.12:
            o = 0.0
        elif 0.12 <= u < 0.26:
            o = min(o, (u - 0.12) / 0.14)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", default="anim.mp4")
    ap.add_argument("--webm", help="背景透過の VP9 も書き出す")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--preview", type=float, nargs="*", help="指定秒の静止画だけ書き出す")
    a = ap.parse_args()

    src = Image.open(a.image).convert("RGBA")
    full = np.array(src)
    closed_full = make_closed(full, src.width / BASE_W)
    w = a.width // 2 * 2
    h = round(src.height * w / src.width) // 2 * 2
    # 動いたときに端が切れないよう少し余白をつける
    pad = round(0.03 * w)
    W, H = w + 2 * pad, h + 2 * pad

    def prep(arr):
        im = Image.fromarray(arr).resize((w, h), Image.LANCZOS)
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        c.paste(im, (pad, pad))
        return np.array(c)

    open_img, closed_img = prep(full), prep(closed_full)
    s = w / src.width * (src.width / BASE_W)
    # 目と各パーツの座標を、余白ぶんずらした出力座標で扱う
    for e in EYES:
        e["poly"] = [(x + pad / s, y + pad / s) for x, y in e["poly"]]
        e["lid"] = [(x + pad / s, y + pad / s) for x, y in e["lid"]]
    rig = Rig(H, W, s, pad)

    def frame(t):
        img = blink_frame(open_img, closed_img, openness(t), s)
        mx, my = rig.maps(t)
        return cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    if a.preview is not None:
        for t in a.preview:
            Image.fromarray(frame(t)).save(f"preview_{t:.2f}.png")
        return

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    raw = ["-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    procs = [subprocess.Popen([ff, "-y", "-loglevel", "error", *raw, "-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}",
                               "-filter_complex", "[1][0]overlay=shortest=1,format=yuv420p",
                               "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-movflags", "+faststart", a.out],
                              stdin=subprocess.PIPE)]
    if a.webm:
        procs.append(subprocess.Popen([ff, "-y", "-loglevel", "error", *raw, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
                                       "-b:v", "0", "-crf", "24", "-row-mt", "1", a.webm], stdin=subprocess.PIPE))
    n = round(DUR * FPS)
    for i in range(n):
        buf = frame(i / FPS).tobytes()
        for p in procs:
            p.stdin.write(buf)
        if i % 30 == 0:
            print(f"{i}/{n}", flush=True)
    for p in procs:
        p.stdin.close()
        p.wait()


if __name__ == "__main__":
    main()
