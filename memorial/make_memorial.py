#!/usr/bin/env python3
"""お葬式・偲ぶ会用のメモリアルムービー（写真スライドショー）を作るスクリプト。

    python3 make_memorial.py --config config.json --out memorial.mp4

- オープニング（お名前・生没年）→ 章ごとの文字カードと写真 → エンディング
- ごく淡いピンクと薄紫の色調。桜・胡蝶蘭・紫陽花を飾り、花びらと光の粒が舞う
- "lavish": true の章は、お花を増やして紫陽花の小花も舞う、いちばん華やかな演出
- 縦長写真やサイズの違う写真も、ぼかした同じ写真を背景に敷いて中央に収める
- BGMを指定すると、最後に向けてフェードアウトする
"""
import argparse
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from flowers import PetalField, bouquet, paste_clip

W, H = 1920, 1080
FPS = 30
ZOOM = 1.07  # ケンバーンズのズーム量（1.0で静止）

INK = (112, 90, 120)        # 文字色（くすんだ藤色）
LINE = (204, 184, 216)      # 細い飾り線（淡い藤色）
PAPER_TOP = (254, 250, 252)  # ごく淡いピンク
PAPER_BOTTOM = (245, 240, 251)  # ごく淡い薄紫

# 房ごとの花の種類の比率
KINDS_NORMAL = {"sakura": 4, "orchid": 3, "hydrangea": 2, "rose": 1, "gyp": 2}
KINDS_LAVISH = {"sakura": 3, "orchid": 4, "hydrangea": 4, "rose": 2, "gyp": 3}

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-mincho/ipam.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",
    "/System/Library/Fonts/ヒラギノ明朝 ProN.ttc",
    "C:/Windows/Fonts/yumin.ttf",
]
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


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
    cfg.setdefault("chapter_seconds", 6.5)
    cfg.setdefault("fade_seconds", 1.6)
    cfg.setdefault("title_seconds", 8.0)
    cfg.setdefault("ending_seconds", 9.0)
    cfg.setdefault("petals", True)
    photo_dir = os.path.join(base, cfg.get("photo_dir", "photos"))

    sections = cfg.get("sections")
    if not sections:  # 章なし：photos、またはフォルダの画像を名前順に
        photos = cfg.get("photos") or sorted(n for n in os.listdir(photo_dir) if n.lower().endswith(IMG_EXT))
        sections = [{"photos": photos}]

    seq = []  # 再生順の並び
    n = 0
    for sec in sections:
        lavish = bool(sec.get("lavish"))
        if sec.get("heading") or sec.get("lines"):
            seq.append({"type": "chapter", "heading": sec.get("heading", ""), "lines": sec.get("lines", []),
                        "lavish": lavish, "seconds": sec.get("seconds", cfg["chapter_seconds"])})
        for p in sec.get("photos", []):
            if isinstance(p, str):
                p = {"file": p}
            p = dict(p)
            if not os.path.isabs(p["file"]):
                cand = os.path.join(photo_dir, p["file"])
                p["file"] = cand if os.path.exists(cand) else os.path.join(base, p["file"])
            p.update(type="photo", index=n, lavish=p.get("lavish", lavish))
            p.setdefault("seconds", cfg["seconds_per_photo"] + (0.5 if lavish else 0))
            seq.append(p)
            n += 1
    cfg["seq"] = seq
    cfg["n_photos"] = n
    if cfg.get("music") and not os.path.isabs(cfg["music"]):
        cfg["music"] = os.path.join(base, cfg["music"])
    return cfg


# ---------- 描画部品 ----------

def paper(w=W, h=H):
    """ごく淡いピンク→薄紫のグラデーションの地紙＋中央にやわらかい光。"""
    g = Image.new("RGB", (1, h))
    for y in range(h):
        k = y / (h - 1)
        g.putpixel((0, y), tuple(int(PAPER_TOP[i] * (1 - k) + PAPER_BOTTOM[i] * k) for i in range(3)))
    img = g.resize((w, h)).convert("RGBA")
    glow = Image.new("L", (w // 8, h // 8), 0)
    ImageDraw.Draw(glow).ellipse([w // 8 * 0.2, h // 8 * 0.1, w // 8 * 0.8, h // 8 * 0.9], fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(w // 80)).resize((w, h), Image.BICUBIC)
    img.paste((255, 253, 254, 255), (0, 0), glow)
    return img


def soft_vignette():
    """画面の縁を白くかすませるレイヤー（儚さ・光に包まれる感じ）。"""
    m = Image.new("L", (W // 8, H // 8), 255)
    ImageDraw.Draw(m).ellipse([-W // 8 * 0.05, -H // 8 * 0.1, W // 8 * 1.05, H // 8 * 1.1], fill=0)
    m = m.filter(ImageFilter.GaussianBlur(W // 70)).resize((W, H), Image.BICUBIC)
    layer = Image.new("RGBA", (W, H), (253, 248, 254, 0))
    layer.putalpha(m.point(lambda v: int(v * 0.55)))
    return layer


def text_layer(img, text, font, y, fill=INK, spacing=0, glow=True):
    """字間を空けた中央揃えの文字。後ろに白いにじみを付けて読みやすく。返り値は文字幅。"""
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * max(len(text) - 1, 0)
    x = (img.width - total) / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=fill + (255,))
        x += w + spacing
    if glow:
        halo = Image.new("RGBA", img.size, (255, 255, 255, 0))
        halo.putalpha(lay.getchannel("A").filter(ImageFilter.GaussianBlur(10)).point(lambda v: min(255, v * 2)))
        img.alpha_composite(halo)
    img.alpha_composite(lay)
    return total


def ornament(img, y, half=200, gap=14):
    """細い線と小さなひし形の飾り。gap を広げると見出しを左右から挟む形になる。"""
    d = ImageDraw.Draw(img)
    cx = W / 2
    d.line([(cx - half, y), (cx - gap, y)], fill=LINE + (230,), width=1)
    d.line([(cx + gap, y), (cx + half, y)], fill=LINE + (230,), width=1)
    if gap <= 14:
        d.polygon([(cx, y - 6), (cx + 6, y), (cx, y + 6), (cx - 6, y)], fill=LINE + (230,))


def corner_flowers(img, specs, kinds=KINDS_NORMAL):
    """画面の四隅にお花の房。specs: (corner, seed, 大きさ0〜1)"""
    for corner, seed, k in specs:
        x = 0 if corner[1] == "l" else W
        y = 0 if corner[0] == "t" else H
        ang = {"tl": 45, "tr": 135, "bl": 315, "br": 225}[corner]  # 画面の内側へ
        lay, ox, oy = bouquet(520 * k + 80, ang, seed=seed, density=0.5 + 0.8 * k,
                              scale=0.55 + 0.55 * k, kinds=kinds)
        paste_clip(img, lay, x - ox, y - oy)


def make_slide(path, scale, idx, lavish=False):
    """写真1枚分の画面を、ズーム用に少し大きめのサイズで作る。"""
    sw, sh = int(W * scale), int(H * scale)
    im = Image.open(path)
    im = ImageOps.exif_transpose(im).convert("RGB")

    # 背景：同じ写真をぼかして、淡い地紙に溶かす
    bg = ImageOps.fit(im, (sw // 6, sh // 6), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(6)).resize((sw, sh), Image.BICUBIC)
    bg = Image.blend(bg, paper(sw, sh).convert("RGB"), 0.70).convert("RGBA")

    # 前景：写真を画面内に収める
    max_w, max_h = int(sw * 0.80), int(sh * 0.76)
    r = min(max_w / im.width, max_h / im.height)
    fg = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    # ほんの少しだけ明るく柔らかく（ソフトフォーカス）
    soft = fg.filter(ImageFilter.GaussianBlur(6))
    fg = Image.blend(fg, Image.blend(soft, Image.new("RGB", fg.size, (255, 250, 254)), 0.15), 0.16)
    fx, fy = (sw - fg.width) // 2, int((sh - fg.height) / 2 - sh * 0.02)

    # やわらかい影
    shadow = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(shadow).rectangle([fx + 6, fy + 14, fx + fg.width + 6, fy + fg.height + 14], fill=100)
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(26 * scale)))
    bg.paste((110, 90, 120, 255), (0, 0), shadow)
    # 白いフチ（プリント写真風）
    b = int(12 * scale)
    ImageDraw.Draw(bg).rectangle([fx - b, fy - b, fx + fg.width + b - 1, fy + fg.height + b - 1],
                                 fill=(255, 254, 255, 255))
    bg.paste(fg, (fx, fy))

    # 写真の角にお花を添える。華やかな章は四隅すべてに大きめに
    if lavish:
        corners = [("bl", 1.0), ("tr", 0.85), ("br", 0.75), ("tl", 0.6)]
        kinds = KINDS_LAVISH
    else:
        corners = [[("bl", 1.0), ("tr", 0.6)], [("br", 1.0), ("tl", 0.6)]][idx % 2]
        kinds = KINDS_NORMAL
    for k, (corner, sz) in enumerate(corners):
        cx = fx - b if corner[1] == "l" else fx + fg.width + b
        cy = fy - b if corner[0] == "t" else fy + fg.height + b
        ang = {"tl": 225, "tr": 315, "bl": 135, "br": 45}[corner]  # 写真の外側へ広がる
        boost = 1.25 if lavish else 1.0
        lay, ox, oy = bouquet((150 + 170 * sz) * scale * boost, ang, seed=idx * 31 + k * 7,
                              density=(0.45 + 0.55 * sz) * boost, scale=(0.55 + 0.4 * sz) * scale, kinds=kinds)
        paste_clip(bg, lay, cx - ox, cy - oy)
    return bg.convert("RGB")


def ken_burns(slide, t, idx):
    """t: 0→1。写真ごとにズームイン／アウトとパンの向きを変える。"""
    t = 0.5 - 0.5 * math.cos(math.pi * t)  # ease in-out
    z = 1 + (ZOOM - 1) * (t if idx % 2 == 0 else 1 - t)
    sw, sh = slide.size
    vw, vh = sw / z, sh / z
    ax, ay = [(0.5, 0.5), (0.38, 0.5), (0.62, 0.5), (0.5, 0.42)][idx % 4]
    cx = sw / 2 + (ax - 0.5) * (sw - vw) * t
    cy = sh / 2 + (ay - 0.5) * (sh - vh) * t
    return slide.resize((W, H), Image.BICUBIC, box=(cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2))


def slow_zoom(img, k):
    """文字カード用：ほんの少しずつ寄っていく。k: 0→1"""
    z = 1 + 0.03 * k
    return img.resize((W, H), Image.BICUBIC,
                      box=(W / 2 - W / z / 2, H / 2 - H / z / 2, W / 2 + W / z / 2, H / 2 + H / z / 2))


def caption_layer(text, font):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if text:
        text_layer(layer, text, font, H - 100, spacing=6)
    return layer


def title_card(cfg, fonts):
    big, mid, small = fonts["big"], fonts["mid"], fonts["small"]
    img = paper()
    corner_flowers(img, [("tl", 11, 1.0), ("br", 23, 1.0), ("tr", 5, 0.45), ("bl", 17, 0.45)])
    lines = []
    if cfg.get("title_top"):
        lines.append(("top", cfg["title_top"], small, 12))
    lines.append(("name", cfg.get("name", ""), big, 30))
    if cfg.get("dates"):
        lines.append(("dates", cfg["dates"], mid, 6))
    if cfg.get("title_bottom"):
        lines.append(("bottom", cfg["title_bottom"], small, 8))
    heights = [f.size * (2.3 if k == "name" else 1.9) for k, _, f, _ in lines]
    y = (H - sum(heights)) / 2
    for (kind, text, f, sp), h in zip(lines, heights):
        text_layer(img, text, f, y, spacing=sp)
        if kind == "name":
            ornament(img, y + f.size * 1.6)
        y += h
    return img.convert("RGB")


def chapter_card(item, fonts, seed):
    """章の扉：見出し＋本文。華やかな章は四隅をお花でいっぱいに。"""
    img = paper()
    if item["lavish"]:
        corner_flowers(img, [("tl", seed, 1.15), ("br", seed + 1, 1.15), ("tr", seed + 2, 0.85),
                             ("bl", seed + 3, 0.85)], KINDS_LAVISH)
    else:
        pair = [("tl", "br"), ("tr", "bl")][seed % 2]
        corner_flowers(img, [(pair[0], seed, 0.9), (pair[1], seed + 1, 0.9)])
    head, body = fonts["head"], fonts["body"]
    lines = item["lines"]
    total = (head.size * 3.2 if item["heading"] else 0) + body.size * 2.1 * len(lines)
    y = (H - total) / 2
    if item["heading"]:
        w = text_layer(img, item["heading"], head, y, spacing=22)
        ornament(img, y + head.size * 0.62, half=w / 2 + 120, gap=w / 2 + 34)
        y += head.size * 3.2
    for text in lines:
        text_layer(img, text, body, y, spacing=8)
        y += body.size * 2.1
    return img.convert("RGB")


def ending_card(cfg, fonts):
    mid = fonts["mid"]
    img = paper()
    corner_flowers(img, [("tr", 41, 1.0), ("bl", 53, 1.0), ("tl", 7, 0.4), ("br", 29, 0.4)])
    lines = cfg.get("ending_lines") or ["ありがとう"]
    lh = mid.size * 2.2
    y = (H - lh * len(lines)) / 2
    for text in lines:
        text_layer(img, text, mid, y, spacing=12)
        y += lh
    return img.convert("RGB")


def fade_white(img, a):
    if a >= 1:
        return img
    return Image.blend(Image.new("RGB", img.size, (255, 252, 254)), img, max(0.0, a))


# ---------- タイムライン ----------

def build_timeline(cfg):
    """[開始秒, 長さ, 種類, データ] の並び。隣同士は fade 秒だけ重なる。"""
    fade = cfg["fade_seconds"]
    items = [[0.0, cfg["title_seconds"], "title", None]]
    t = cfg["title_seconds"] - fade
    for k, e in enumerate(cfg["seq"]):
        dur = float(e["seconds"])
        items.append([t, dur, e["type"], dict(e, key=k)])
        t += dur - fade
    items.append([t, cfg["ending_seconds"], "ending", None])
    return items, t + cfg["ending_seconds"]


def render(cfg, out, font_path, preview=None):
    F = lambda s: ImageFont.truetype(font_path, s)
    fonts = dict(big=F(96), mid=F(54), small=F(36), head=F(44), body=F(52), cap=F(46))
    fade = cfg["fade_seconds"]
    field = PetalField(W, H)
    florets = PetalField(W, H, n_petals=26, n_bokeh=10, seed=21, kind="floret")
    vignette = soft_vignette()

    items, total = build_timeline(cfg)
    n_frames = int(round(total * FPS))
    cache = {}

    # 華やかな章の区間（前後1.5秒でふわっと切り替え）
    lav = [(it[0], it[0] + it[1]) for it in items if it[3] and it[3].get("lavish")]
    lav_range = (min(a for a, _ in lav), max(b for _, b in lav)) if lav else None

    def lavish_at(t):
        if not lav_range:
            return 0.0
        a, b = lav_range
        return max(0.0, min(1.0, (t - a) / 1.5, (b - t) / 1.5))

    def get(kind, data):
        key = (kind, data["key"] if data else None)
        if key not in cache:
            if kind == "title":
                cache[key] = title_card(cfg, fonts)
            elif kind == "ending":
                cache[key] = ending_card(cfg, fonts)
            elif kind == "chapter":
                cache[key] = chapter_card(data, fonts, seed=100 + data["key"] * 5)
            else:
                print(f"  写真 {data['index'] + 1}/{cfg['n_photos']}: {os.path.basename(data['file'])}", flush=True)
                cache[key] = (make_slide(data["file"], ZOOM + 0.02, data["index"], data["lavish"]),
                              caption_layer(data.get("caption", ""), fonts["cap"]))
        return cache[key]

    def frame_of(item, t):
        start, dur, kind, data = item
        k = (t - start) / dur
        if kind == "photo":
            slide, cap = get(kind, data)
            fr = ken_burns(slide, k, data["index"])
            ca = min(1, max(0, (t - start - fade - 0.3) / 1.0), max(0, (start + dur - fade - t) / 0.7))
            if ca > 0 and data.get("caption"):
                fr = fr.convert("RGBA")
                c = cap.copy()
                c.putalpha(c.getchannel("A").point(lambda v: int(v * ca)))
                fr.alpha_composite(c)
                fr = fr.convert("RGB")
            return fr
        img = slow_zoom(get(kind, data), k)
        if kind == "title":  # 白い光の中からゆっくり
            return fade_white(img, (t - start) / 2.5)
        if kind == "ending":  # 最後は光に溶けるように白へ
            return fade_white(img, (start + dur - t) / 3.0)
        return img

    def compose(t):
        active = [it for it in items if it[0] <= t < it[0] + it[1]] or [items[-1]]
        if len(active) == 1:
            base = frame_of(active[0], t)
        else:
            a, b = active[-2], active[-1]
            x = 0.5 - 0.5 * math.cos(math.pi * min(1, max(0, (t - b[0]) / fade)))
            base = Image.blend(frame_of(a, t), frame_of(b, t), x)
        img = base.convert("RGBA")
        img.alpha_composite(vignette)
        # 花びらは最後の数秒で静かに消えていく
        s = min(1.0, t / 1.5, max(0.0, (total - t - 0.5) / 2.5))
        field.draw(img, t, strength=s, petals=cfg["petals"])
        florets.draw(img, t, strength=s * lavish_at(t), petals=cfg["petals"])
        return img.convert("RGB")

    if preview is not None:
        for s in preview:
            compose(s).save(f"preview_{s:06.2f}.png")
            print(f"preview_{s:06.2f}.png")
        return

    print(f"全体 {total:.1f} 秒 / 写真 {cfg['n_photos']} 枚")
    tmp = out + ".video.mp4" if cfg.get("music") else out
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
    for f in range(n_frames):
        ff.stdin.write(compose(f / FPS).tobytes())
        if f % FPS == 0:  # 使い終わった画面はメモリから捨てる
            for it in items:
                if it[3] and it[0] + it[1] < f / FPS:
                    cache.pop((it[2], it[3]["key"]), None)
        if f % (FPS * 10) == 0:
            print(f"  {f / FPS:.0f}/{total:.0f} 秒", flush=True)
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg でエラーが出たで")

    if cfg.get("music"):
        fo = 6.0
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
    ap.add_argument("--timeline", action="store_true", help="各場面の開始秒を表示するだけ")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if not cfg["n_photos"]:
        sys.exit("写真が見つからへん。photos フォルダに入れてな")
    if a.timeline:
        items, total = build_timeline(cfg)
        for s, d, k, data in items:
            label = (data or {}).get("heading") or os.path.basename((data or {}).get("file", "")) or ""
            print(f"{s:6.1f}s  {k:8s} {label}")
        print(f"合計 {total:.1f}s")
        return
    render(cfg, a.out, find_font(a.font), a.preview)


if __name__ == "__main__":
    main()
