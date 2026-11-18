#!/usr/bin/env python3
"""お葬式・偲ぶ会用のメモリアルムービー（写真スライドショー）を作るスクリプト。

    python3 make_memorial.py --config config.json --out memorial.mp4

- オープニング（お名前・生没年）→ 写真をゆっくりズームしながらクロスフェード → エンディング
- 縦長写真やサイズの違う写真も、ぼかした同じ写真を背景に敷いて中央に収める
- 写真ごとに一言（キャプション）を付けられる
- BGMを指定すると、最後に向けてフェードアウトする
"""
import argparse
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H = 1920, 1080
FPS = 30
ZOOM = 1.07  # ケンバーンズのズーム量（1.0で静止）

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "C:/Windows/Fonts/yumin.ttf",
]
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic")


def find_font(path):
    if path:
        return path
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("明朝フォントが見つからへん。--font でフォントファイルを指定してな")


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    base = os.path.dirname(os.path.abspath(path))
    cfg.setdefault("seconds_per_photo", 6.0)
    cfg.setdefault("fade_seconds", 1.5)
    cfg.setdefault("title_seconds", 7.0)
    cfg.setdefault("ending_seconds", 8.0)

    photos = cfg.get("photos")
    if not photos:  # photos 未指定ならフォルダの画像を名前順に
        d = os.path.join(base, cfg.get("photo_dir", "photos"))
        photos = [{"file": os.path.join(d, n)} for n in sorted(os.listdir(d))
                  if n.lower().endswith(IMG_EXT)]
    norm = []
    for p in photos:
        if isinstance(p, str):
            p = {"file": p}
        if not os.path.isabs(p["file"]):
            cand = os.path.join(base, cfg.get("photo_dir", "photos"), p["file"])
            p["file"] = cand if os.path.exists(cand) else os.path.join(base, p["file"])
        norm.append(p)
    cfg["photos"] = norm
    if cfg.get("music") and not os.path.isabs(cfg["music"]):
        cfg["music"] = os.path.join(base, cfg["music"])
    return cfg


# ---------- 描画 ----------

def draw_text_center(img, text, font, y, fill, shadow=True, spacing=0):
    d = ImageDraw.Draw(img)
    # 字間を空けて描く（明朝の余白感を出す）
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * max(len(text) - 1, 0)
    x = (img.width - total) / 2
    for ch, w in zip(text, widths):
        if shadow:
            d.text((x + 2, y + 2), ch, font=font, fill=(0, 0, 0, 160))
        d.text((x, y), ch, font=font, fill=fill)
        x += w + spacing


def make_slide(path, scale):
    """写真1枚分の画面を、ズーム用に少し大きめのサイズで作る。"""
    sw, sh = int(W * scale), int(H * scale)
    im = Image.open(path)
    im = ImageOps.exif_transpose(im).convert("RGB")

    # 背景：同じ写真を画面いっぱいに拡大→ぼかし→暗く
    bg = ImageOps.fit(im, (sw // 4, sh // 4), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(10)).resize((sw, sh), Image.BICUBIC)
    bg = Image.blend(bg, Image.new("RGB", bg.size, (12, 12, 16)), 0.55)

    # 前景：写真を画面内に収める（上下左右に余白）
    max_w, max_h = int(sw * 0.86), int(sh * 0.80)
    r = min(max_w / im.width, max_h / im.height)
    fg = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    fx, fy = (sw - fg.width) // 2, int((sh - fg.height) / 2 - sh * 0.025)

    # やわらかい影
    shadow = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(shadow).rectangle([fx + 10, fy + 16, fx + fg.width + 10, fy + fg.height + 16], fill=170)
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(22 * scale)))
    bg.paste((0, 0, 0), (0, 0), shadow)
    # 細い白フチ
    border = int(5 * scale)
    ImageDraw.Draw(bg).rectangle([fx - border, fy - border, fx + fg.width + border - 1,
                                  fy + fg.height + border - 1], fill=(238, 234, 226))
    bg.paste(fg, (fx, fy))
    return bg


def ken_burns(slide, t, idx):
    """t: 0→1。写真ごとにズームイン／アウトとパンの向きを変える。"""
    t = 0.5 - 0.5 * math.cos(math.pi * t)  # ease in-out
    zin = idx % 2 == 0
    z = 1 + (ZOOM - 1) * (t if zin else 1 - t)  # 1.0〜ZOOM
    sw, sh = slide.size
    vw, vh = sw / z, sh / z
    dirs = [(0.5, 0.5), (0.35, 0.5), (0.65, 0.5), (0.5, 0.4)]
    ax, ay = dirs[idx % len(dirs)]
    cx = sw / 2 + (ax - 0.5) * (sw - vw) * t
    cy = sh / 2 + (ay - 0.5) * (sh - vh) * t
    box = (cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2)
    return slide.resize((W, H), Image.BICUBIC, box=box)


def caption_layer(text, font):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if text:
        # 下部を少しだけ暗くして読みやすく
        grad = Image.new("L", (1, 220))
        for y in range(220):
            grad.putpixel((0, y), int(150 * (y / 219) ** 1.6))
        layer.paste((0, 0, 0, 255), (0, H - 220), grad.resize((W, 220)))
        draw_text_center(layer, text, font, H - 96, (245, 241, 232, 255), spacing=4)
    return layer


def title_card(cfg, fonts):
    img = Image.new("RGB", (W, H), (10, 10, 14)).convert("RGBA")
    big, mid, small = fonts
    lines = []
    if cfg.get("title_top"):
        lines.append((cfg["title_top"], small, 10))
    lines.append((cfg.get("name", ""), big, 26))
    if cfg.get("dates"):
        lines.append((cfg["dates"], mid, 8))
    if cfg.get("title_bottom"):
        lines.append((cfg["title_bottom"], small, 8))
    heights = [f.size * 1.9 for _, f, _ in lines]
    y = (H - sum(heights)) / 2
    for (text, f, sp), h in zip(lines, heights):
        draw_text_center(img, text, f, y, (240, 236, 226, 255), shadow=False, spacing=sp)
        if f is big:  # 名前の下に細い線
            ImageDraw.Draw(img).line([(W / 2 - 180, y + f.size * 1.55), (W / 2 + 180, y + f.size * 1.55)],
                                     fill=(170, 160, 140, 255), width=1)
        y += h
    return img.convert("RGB")


def ending_card(cfg, fonts):
    img = Image.new("RGB", (W, H), (10, 10, 14)).convert("RGBA")
    _, mid, small = fonts
    lines = cfg.get("ending_lines") or ["ありがとう"]
    lh = mid.size * 2.1
    y = (H - lh * len(lines)) / 2
    for text in lines:
        draw_text_center(img, text, mid, y, (240, 236, 226, 255), shadow=False, spacing=10)
        y += lh
    return img.convert("RGB")


def fade_black(img, a):
    if a >= 1:
        return img
    return Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, max(0.0, a))


# ---------- タイムライン ----------

def build_timeline(cfg):
    """(開始秒, 長さ, 種類, データ) の並び。隣同士は fade 秒だけ重なる。"""
    fade = cfg["fade_seconds"]
    items = []
    t = 0.0
    items.append([t, cfg["title_seconds"], "title", None])
    t += cfg["title_seconds"] - fade
    for i, p in enumerate(cfg["photos"]):
        dur = float(p.get("seconds", cfg["seconds_per_photo"]))
        items.append([t, dur, "photo", (i, p)])
        t += dur - fade
    items.append([t, cfg["ending_seconds"], "ending", None])
    total = t + cfg["ending_seconds"]
    return items, total


def render(cfg, out, font_path, preview=None):
    big = ImageFont.truetype(font_path, 92)
    mid = ImageFont.truetype(font_path, 52)
    small = ImageFont.truetype(font_path, 36)
    cap_font = ImageFont.truetype(font_path, 44)
    fonts = (big, mid, small)
    fade = cfg["fade_seconds"]

    items, total = build_timeline(cfg)
    n_frames = int(round(total * FPS))
    cache = {}

    def get(kind, data):
        key = (kind, data[0] if data else None)
        if key not in cache:
            if kind == "title":
                cache[key] = title_card(cfg, fonts)
            elif kind == "ending":
                cache[key] = ending_card(cfg, fonts)
            else:
                i, p = data
                print(f"  写真 {i + 1}/{len(cfg['photos'])}: {os.path.basename(p['file'])}", flush=True)
                cache[key] = (make_slide(p["file"], ZOOM + 0.02), caption_layer(p.get("caption", ""), cap_font))
        return cache[key]

    def frame_of(item, t):
        start, dur, kind, data = item
        lt = (t - start) / dur
        if kind == "photo":
            slide, cap = get(kind, data)
            fr = ken_burns(slide, lt, data[0]).convert("RGBA")
            # キャプションは少し遅れて出て、早めに消える
            ca = min(1, max(0, (t - start - fade - 0.3) / 0.8), max(0, (start + dur - fade - t) / 0.6))
            if ca > 0 and data[1].get("caption"):
                c = cap.copy()
                c.putalpha(c.getchannel("A").point(lambda v: int(v * ca)))
                fr.alpha_composite(c)
            return fr.convert("RGB")
        img = get(kind, data)
        if kind == "title":  # 黒からゆっくり
            img = fade_black(img, (t - start) / 2.0)
        else:  # 最後は黒へ
            img = fade_black(img, min((t - start) / 1.5, (start + dur - t) / 2.5))
        return img

    def compose(t):
        active = [it for it in items if it[0] <= t < it[0] + it[1]]
        if not active:
            active = [items[-1]]
        if len(active) == 1:
            return frame_of(active[0], t)
        a, b = active[-2], active[-1]
        x = (t - b[0]) / fade
        x = 0.5 - 0.5 * math.cos(math.pi * min(1, max(0, x)))
        return Image.blend(frame_of(a, t), frame_of(b, t), x)

    if preview is not None:
        for s in preview:
            compose(s).save(f"preview_{s:06.2f}.png")
            print(f"preview_{s:06.2f}.png")
        return

    print(f"全体 {total:.1f} 秒 / 写真 {len(cfg['photos'])} 枚")
    tmp = out + ".video.mp4" if cfg.get("music") else out
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
    for f in range(n_frames):
        ff.stdin.write(compose(f / FPS).tobytes())
        # 使い終わった写真はメモリから捨てる
        if f % FPS == 0:
            t = f / FPS
            for it in items:
                if it[2] == "photo" and it[0] + it[1] < t:
                    cache.pop(("photo", it[3][0]), None)
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg でエラーが出たで")

    if cfg.get("music"):
        fo = 5.0
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-stream_loop", "-1", "-i", cfg["music"],
            "-filter_complex",
            f"[1:a]atrim=0:{total:.3f},afade=t=in:d=2,afade=t=out:st={max(0, total - fo):.3f}:d={fo},"
            f"volume={cfg.get('music_volume', 0.9)}[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", out], check=True)
        os.remove(tmp)
    print(f"できたで → {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--out", default="memorial.mp4")
    ap.add_argument("--font", help="明朝体フォント（.ttf/.otf/.ttc）")
    ap.add_argument("--preview", type=float, nargs="+", help="指定秒の静止画だけ書き出す")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if not cfg["photos"]:
        sys.exit("写真が見つからへん。photos フォルダに入れてな")
    render(cfg, a.out, find_font(a.font), a.preview)


if __name__ == "__main__":
    main()
