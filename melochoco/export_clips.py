"""MV風バージョン (make_mv.py) の一部パーツを、背景透過の動画として書き出す.

  python3 export_clips.py --image illust.png --audio source.mov --font-pop Dela.ttf --font-cute Hachi.ttf \
      --cache cache3d --out clips

- menu:   「お好み通り」のメニューカード (3Dのお菓子アイコンが回って並び、チェックが入る)
- choco:  「できあがり」の回る3Dハートチョコ
それぞれ ProRes 4444 (.mov) と VP9 (.webm) の透過動画、先頭フレームの PNG を出力する。
"""
import argparse
import math
import os
import subprocess
from multiprocessing import Pool
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

import make_mv as M
from make_video import FPS, H, W, ease_out_back, heart_pts

A = M.A


def menu_frame(t):
    """make_mv.sc_okonomi のメニューカードだけを透過キャンバスに描く."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lt = t - 7.25
    items = [("choco_heart", "ビター"), ("bar", "ミルク"), ("donut", "いちご"), ("gift", "めろめろ♡")]

    def menu(w, h):
        c = Image.new("RGBA", (w, h), (255, 250, 244, 255))
        dr = ImageDraw.Draw(c)
        dr.text((w / 2, 50), "MENU", font=ImageFont.truetype(A["fcute"], 58), anchor="mm", fill=M.BERRY)
        for i in range(0, w, 30):
            dr.polygon(heart_pts(i + 15, 95, 7), fill=(255, 170, 205))
        fi = ImageFont.truetype(A["fcute"], 48)
        for i, (obj, name) in enumerate(items):
            ti = 7.4 + i * 0.5
            yy = 170 + i * 118
            if t < ti:
                continue
            k = ease_out_back((t - ti) / 0.25)
            M.draw3d(c, obj, 70, yy, 100 * k, t, 0.8, i * .2, shadow=False)
            dr.text((140, yy), name, font=fi, anchor="lm", fill=M.CHOCO)
            if t > ti + 0.25:
                q = M.clamp01((t - ti - 0.25) / 0.15)
                x0, y0 = w - 80, yy
                pts = [(x0 - 22, y0), (x0 - 6, y0 + 18), (x0 + 26, y0 - 22)]
                dr.line(pts[:2] if q < .5 else pts, fill=M.HOTPINK, width=10, joint="curve")
        return c
    M.window(im, 470, 560, 620, 720, "order_menu", menu, ease_out_back(lt / 0.3), -3 + 2 * math.sin(t))
    return im.crop((20, 70, 920, 1050))


def choco_frame(t):
    """make_mv.sc_cook の「できあがり」で飛び出して回る3Dハートチョコ."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    k = ease_out_back((t - 12.0) / 0.35)
    M.draw3d(im, "choco_heart", 640, 480 - 20 * math.sin(t * 3), 560 * k, t, 0.9)
    return im.crop((260, 90, 1020, 870))


CLIPS = {
    "menu_okonomi": (menu_frame, 7.25, 10.25),
    "choco_dekiagari": (choco_frame, 12.0, 16.0),
}


def _render(job):
    name, fi = job
    fn, t0, _ = CLIPS[name]
    return fn(t0 + fi / FPS).tobytes()


def write(name, frames_bytes, size, out):
    w, h = size
    base = os.path.join(out, name)
    for codec in (["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0",
                   base + ".mov"],
                  ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24", "-row-mt", "1",
                   "-auto-alt-ref", "0", base + ".webm"]):
        p = subprocess.Popen([A["ffmpeg"], "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
                              "-r", str(FPS), "-i", "-"] + codec, stdin=subprocess.PIPE)
        for fb in frames_bytes:
            p.stdin.write(fb)
        p.stdin.close()
        p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--font-pop", required=True)
    ap.add_argument("--font-cute", required=True)
    ap.add_argument("--cache", default="cache3d")
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--out", default="clips")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    with Pool(args.jobs) as pool:
        M.build(SimpleNamespace(image=args.image, audio=args.audio, font_pop=args.font_pop, font_cute=args.font_cute,
                                cache=args.cache, ffmpeg=args.ffmpeg), pool)
    A["ffmpeg"] = args.ffmpeg
    for name, (fn, t0, t1) in CLIPS.items():
        n = int(round((t1 - t0) * FPS))
        with Pool(args.jobs) as pool:
            frames = pool.map(_render, [(name, i) for i in range(n)])
        size = fn(t0).size
        write(name, frames, size, args.out)
        # 動きの途中の1枚を PNG でも保存 (確認用)
        Image.frombytes("RGBA", size, frames[min(n - 1, int(n * 0.7))]).save(os.path.join(args.out, name + ".png"))
        print("done", name, n, "frames", size, flush=True)


if __name__ == "__main__":
    main()
