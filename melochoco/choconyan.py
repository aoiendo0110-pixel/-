"""チョコ大好きなゆるキャラ猫「ちょこにゃん」の SVG / 透過 PNG とキャラクターシートを作る.

  python3 choconyan.py --out nyan_out --font-pop MochiyPopOne-Regular.ttf --font-hand HachiMaruPop-Regular.ttf

パティシエ少女 (sd_chara3d.py) がモチーフ: 白いベレー帽 + チョコのハート、赤×黄色ストライプのリボンと金の鈴、
ドリルみたいにくるんと巻いたしっぽ. 頭にチョコがとろ〜っとかかった白猫で、口からいつもチョコを垂らしている.
カラーパレットは 赤・ピンク・茶・黄・白. PNG は Chromium (headless) で SVG を描画して作る.
"""
import argparse
import math
import os
import subprocess

W = H = 1000
C = dict(
    white="#FFF9F2", shade="#F3DDD3", choco="#6B3A2E", choco_hi="#9A5A44", dark="#43221C",
    pink="#FFB3CC", blush="#FF8FB1", red="#E0384F", red_dk="#B8243A", yellow="#FFD45C",
    gold="#F7C531", gold_dk="#D49B1B", line="#43221C",
)
LW = 9   # 輪郭線の太さ
HEADLESS = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"


def heart_d(cx, cy, s, rot=0):
    """ハートのパス (s は幅). 先端が下."""
    pts = [(0, 0.42), (-0.15, 0.3), (-0.52, 0.05), (-0.52, -0.2), (-0.52, -0.5), (-0.15, -0.58), (0, -0.32),
           (0.15, -0.58), (0.52, -0.5), (0.52, -0.2), (0.52, 0.05), (0.15, 0.3), (0, 0.42)]
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    q = [(cx + s * (x * ca - y * sa), cy + s * (x * sa + y * ca)) for x, y in pts]
    f = lambda p: f"{p[0]:.1f},{p[1]:.1f}"
    return (f"M{f(q[0])} C{f(q[1])} {f(q[2])} {f(q[3])} C{f(q[4])} {f(q[5])} {f(q[6])} "
            f"C{f(q[7])} {f(q[8])} {f(q[9])} C{f(q[10])} {f(q[11])} {f(q[12])}Z")


def poly(points):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points) + "Z"


def drip_edge(x0, x1, base, drips, n=160, wobble=6):
    """下側がしずく状に垂れたチョコの縁 (上は大きく覆う)."""
    pts = [(x0, base - 400)]
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        y = base + wobble * math.sin(x / 23)
        for dx, ln, w in drips:
            y += ln * math.exp(-((x - dx) / w) ** 4)
        pts.append((x, y))
    pts.append((x1, base - 400))
    return poly(pts)


# ---- パーツ ------------------------------------------------------------------------
def defs():
    return f"""
<defs>
  <clipPath id="headclip"><ellipse cx="500" cy="430" rx="268" ry="212"/></clipPath>
  <clipPath id="footclipL"><ellipse cx="428" cy="868" rx="60" ry="36"/></clipPath>
  <clipPath id="footclipR"><ellipse cx="572" cy="868" rx="60" ry="36"/></clipPath>
  <linearGradient id="eyeg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{C['dark']}"/><stop offset="1" stop-color="#8E2F45"/>
  </linearGradient>
  <linearGradient id="chocog" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{C['choco_hi']}"/><stop offset="0.45" stop-color="{C['choco']}"/>
    <stop offset="1" stop-color="#5A2E24"/>
  </linearGradient>
  <radialGradient id="bodyg" cx="0.45" cy="0.35" r="0.75">
    <stop offset="0.6" stop-color="{C['white']}"/><stop offset="1" stop-color="{C['shade']}"/>
  </radialGradient>
  <radialGradient id="bellg" cx="0.35" cy="0.3" r="0.8">
    <stop offset="0" stop-color="#FFF2B8"/><stop offset="0.45" stop-color="{C['gold']}"/>
    <stop offset="1" stop-color="{C['gold_dk']}"/>
  </radialGradient>
  <pattern id="stripe" width="22" height="22" patternUnits="userSpaceOnUse" patternTransform="rotate(90)">
    <rect width="22" height="22" fill="{C['red']}"/><rect width="5" height="22" x="8" fill="{C['yellow']}"/>
  </pattern>
  <mask id="bite">
    <rect x="0" y="0" width="1000" height="1000" fill="white"/>
    <circle cx="583" cy="712" r="22" fill="black"/><circle cx="600" cy="738" r="20" fill="black"/>
    <circle cx="566" cy="696" r="16" fill="black"/>
  </mask>
</defs>"""


def olw(w):
    return ol(f'stroke-width="{w}"')


def ol(extra=""):
    return f'stroke="{C["line"]}" stroke-width="{LW}" stroke-linejoin="round" stroke-linecap="round" {extra}'


def tail():
    # くるんと巻いたドリルしっぽ (先はチョコがけ) + ピンクのリボン
    d = "M640,770 C730,780 790,720 770,640 C755,585 700,585 700,630 C700,665 745,668 748,636"
    return f"""
<g id="tail">
  <path d="{d}" fill="none" stroke="{C['line']}" stroke-width="58" stroke-linecap="round"/>
  <path d="{d}" fill="none" stroke="{C['white']}" stroke-width="40" stroke-linecap="round"/>
  <path d="M770,640 C755,585 700,585 700,630 C700,665 745,668 748,636" fill="none" stroke="{C['choco']}"
        stroke-width="40" stroke-linecap="round"/>
  <path d="M742,600 C728,592 712,598 708,612" fill="none" stroke="{C['choco_hi']}" stroke-width="8"
        stroke-linecap="round"/>
  {bow(770, 706, 0.42, C['pink'], C['pink'], rot=-30)}
</g>"""


def ears():
    out = []
    for s in (-1, 1):
        bx = 500 + s * 175
        tip = (500 + s * 255, 175)
        outer = f"M{bx - s * 95},330 Q{tip[0] - s * 40},200 {tip[0]},{tip[1]} Q{bx + s * 70},215 {bx + s * 85},300 Z"
        inner = f"M{bx - s * 55},320 Q{tip[0] - s * 30},235 {tip[0] - s * 8},{tip[1] + 38} Q{bx + s * 40},240 {bx + s * 50},305 Z"
        out.append(f'<path d="{outer}" fill="{C["choco"]}" {ol()}/>')
        out.append(f'<path d="{inner}" fill="{C["pink"]}"/>')
    return "\n".join(out)


def head(choco_wet=True):
    drips = [(300, 40, 26), (372, 78, 22), (452, 30, 20), (548, 58, 22), (632, 92, 22), (700, 36, 24)]
    choco = drip_edge(210, 790, 340, drips)
    shine = ""
    if choco_wet:
        shine = (f'<path d="M330,265 Q420,228 520,235" fill="none" stroke="{C["choco_hi"]}" stroke-width="14" '
                 f'stroke-linecap="round" opacity="0.9"/>'
                 f'<ellipse cx="610" cy="262" rx="20" ry="10" fill="white" opacity="0.75" transform="rotate(12 610 262)"/>'
                 f'<circle cx="374" cy="402" r="6" fill="white" opacity="0.7"/>'
                 f'<circle cx="634" cy="420" r="7" fill="white" opacity="0.7"/>')
    return f"""
<g id="head">
  <ellipse cx="500" cy="430" rx="268" ry="212" fill="url(#bodyg)"/>
  <g clip-path="url(#headclip)">
    <path d="{choco}" fill="url(#chocog)"/>
    {shine}
  </g>
  <ellipse cx="500" cy="430" rx="268" ry="212" fill="none" {ol()}/>
</g>"""


def beret():
    return f"""
<g id="beret" transform="rotate(14 560 222)">
  <ellipse cx="560" cy="222" rx="128" ry="52" fill="{C['white']}" {ol()}/>
  <path d="M480,236 Q560,262 640,236" fill="none" stroke="{C['shade']}" stroke-width="10" stroke-linecap="round"/>
  <path d="M553,172 q8,-26 22,-8" fill="{C['white']}" {ol()}/>
  <path d="{heart_d(625, 226, 42, -8)}" fill="{C['choco']}" {olw(6)}/>
  <path d="{heart_d(588, 238, 18, 10)}" fill="{C['pink']}" {olw(4)}/>
</g>"""


def eyes(kind="sleepy"):
    out = []
    for s in (-1, 1):
        cx, cy = 500 + s * 98, 452
        if kind == "sleepy":    # とろんとした半目
            cy += 8
            ix, ox = cx - s * 36, cx + s * 38          # 目頭 / 目尻 (目尻が下がったタレ目)
            lid = f"M{ix},{cy - 14} Q{cx},{cy - 34} {ox},{cy - 4}"
            out.append(f'<clipPath id="lid{s}"><path d="{lid} L{ox},{cy + 60} L{ix},{cy + 60}Z"/></clipPath>')
            out.append(f'<ellipse cx="{cx}" cy="{cy + 4}" rx="31" ry="36" fill="url(#eyeg)" clip-path="url(#lid{s})"/>')
            out.append(f'<path d="{lid}" fill="none" stroke="{C["line"]}" stroke-width="10" stroke-linecap="round"/>')
            out.append(f'<circle cx="{cx - 9}" cy="{cy + 6}" r="8.5" fill="white"/>')
            out.append(f'<circle cx="{cx + 11}" cy="{cy + 25}" r="4" fill="white"/>')
        elif kind == "happy":   # ^ ^
            out.append(f'<path d="M{cx - 34},{cy + 12} Q{cx},{cy - 34} {cx + 34},{cy + 12}" fill="none" '
                       f'stroke="{C["line"]}" stroke-width="12" stroke-linecap="round"/>')
        elif kind == "heart":   # チョコを見つけたハートの目
            out.append(f'<path d="{heart_d(cx, cy, 88)}" fill="{C["red"]}" {ol()}/>')
            out.append(f'<ellipse cx="{cx - 18}" cy="{cy - 14}" rx="10" ry="7" fill="white" '
                       f'transform="rotate(-30 {cx - 18} {cy - 14})"/>')
    return "\n".join(out)


def cheeks(lines=True):
    out = []
    for s in (-1, 1):
        cx, cy = 500 + s * 168, 520
        out.append(f'<ellipse cx="{cx}" cy="{cy}" rx="42" ry="24" fill="{C["blush"]}" opacity="0.75"/>')
        if lines:
            for k in (-1, 0, 1):
                x = cx + k * 16
                out.append(f'<path d="M{x + 6},{cy - 9} l-10,16" stroke="white" stroke-width="4" '
                           f'stroke-linecap="round" opacity="0.9"/>')
    return "\n".join(out)


def whiskers():
    out = []
    for s in (-1, 1):
        for k, dy in enumerate((-8, 14)):
            x0 = 500 + s * 225
            out.append(f'<path d="M{x0},{505 + dy} l{s * 52},{dy * 0.6 - 4}" stroke="{C["line"]}" '
                       f'stroke-width="6" stroke-linecap="round"/>')
    return "\n".join(out)


def mouth(kind="omega", drool=True):
    nose = f'<path d="M488,500 Q500,494 512,500 Q506,512 500,513 Q494,512 488,500Z" fill="{C["pink"]}" {olw(5)}/>'
    if kind == "omega":
        m = (f'<path d="M500,514 L500,522" stroke="{C["line"]}" stroke-width="7" stroke-linecap="round"/>'
             f'<path d="M466,520 Q482,548 500,522 Q518,548 534,520" fill="none" stroke="{C["line"]}" '
             f'stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>')
    else:   # もぐもぐ (口いっぱい)
        m = (f'<path d="M470,522 Q500,565 530,522 Z" fill="#8E2F45" {olw(7)}/>'
             f'<path d="M482,538 Q500,556 518,538" fill="{C["choco"]}"/>')
    out = []
    if drool:
        # 口の端からとろ〜っと垂れるチョコ (細い筋 → 丸いしずく)
        drop = ("M531,515 C541,511 549,519 546,531 C543,545 541,555 547,569 "
                "C557,589 549,612 532,612 C514,612 508,594 518,578 C526,564 528,552 528,538 C528,528 524,519 531,515Z")
        out.append(f'<path d="{drop}" fill="{C["choco"]}" {olw(6)}/>')
        out.append(f'<ellipse cx="527" cy="596" rx="5" ry="8" fill="white" opacity="0.8"/>')
        out.append(f'<circle cx="550" cy="628" r="6" fill="{C["choco"]}" {olw(4)}/>')
    out += [nose, m]     # 口の線はチョコの上に
    return "\n".join(out)


def bow(cx, cy, s, fill, knot, rot=0, tails=True):
    w = (f'M{cx},{cy} C{cx - 40 * s},{cy - 70 * s} {cx - 125 * s},{cy - 55 * s} {cx - 110 * s},{cy} '
         f'C{cx - 125 * s},{cy + 55 * s} {cx - 40 * s},{cy + 70 * s} {cx},{cy}Z '
         f'M{cx},{cy} C{cx + 40 * s},{cy - 70 * s} {cx + 125 * s},{cy - 55 * s} {cx + 110 * s},{cy} '
         f'C{cx + 125 * s},{cy + 55 * s} {cx + 40 * s},{cy + 70 * s} {cx},{cy}Z')
    t = ""
    if tails:
        t = (f'<path d="M{cx - 8 * s},{cy + 10 * s} L{cx - 55 * s},{cy + 95 * s} L{cx - 30 * s},{cy + 85 * s} '
             f'L{cx - 22 * s},{cy + 108 * s} L{cx + 6 * s},{cy + 18 * s}Z M{cx + 8 * s},{cy + 10 * s} '
             f'L{cx + 55 * s},{cy + 95 * s} L{cx + 30 * s},{cy + 85 * s} L{cx + 22 * s},{cy + 108 * s} '
             f'L{cx - 6 * s},{cy + 18 * s}Z" fill="{fill}" {olw(LW * 0.8)}/>')
    return (f'<g transform="rotate({rot} {cx} {cy})">{t}<path d="{w}" fill="{fill}" {olw(LW * 0.8)}/>'
            f'<ellipse cx="{cx}" cy="{cy}" rx="{24 * s}" ry="{28 * s}" fill="{knot}" {olw(LW * 0.8)}/></g>')


def collar():
    return f"""
<g id="collar">
  {bow(500, 640, 0.85, 'url(#stripe)', C['red'], tails=False)}
  <circle cx="500" cy="694" r="27" fill="url(#bellg)" {olw(7)}/>
  <path d="M478,694 L522,694" stroke="{C['gold_dk']}" stroke-width="6" stroke-linecap="round"/>
  <circle cx="500" cy="706" r="6" fill="{C['line']}"/>
  <circle cx="490" cy="683" r="6" fill="white" opacity="0.85"/>
</g>"""


def body():
    feet = []
    for s, cl in ((-1, "footclipL"), (1, "footclipR")):
        cx = 500 + s * 72
        feet.append(f'<ellipse cx="{cx}" cy="868" rx="60" ry="36" fill="{C["white"]}"/>'
                    f'<g clip-path="url(#{cl})"><path d="M{cx - 70},872 Q{cx - 35},862 {cx},874 Q{cx + 35},862 '
                    f'{cx + 70},872 L{cx + 70},920 L{cx - 70},920Z" fill="{C["choco"]}"/></g>'
                    f'<ellipse cx="{cx}" cy="868" rx="60" ry="36" fill="none" {ol()}/>')
    return f"""
<g id="body">
  {''.join(feet)}
  <ellipse cx="500" cy="728" rx="172" ry="150" fill="url(#bodyg)" {ol()}/>
  <ellipse cx="500" cy="770" rx="105" ry="85" fill="{C['white']}" opacity="0.8"/>
</g>"""


def held_heart(bitten=True):
    m = 'mask="url(#bite)"' if bitten else ""
    drizzle = ("M432,750 Q458,722 480,752 Q502,782 524,750 Q546,720 566,748")
    return f"""
<g id="choco_heart" {m} transform="translate(0,30)">
  <path d="{heart_d(500, 772, 190)}" fill="url(#chocog)" {ol()}/>
  <path d="{drizzle}" fill="none" stroke="{C['pink']}" stroke-width="11" stroke-linecap="round"/>
  <path d="{heart_d(500, 795, 46)}" fill="{C['red']}" {olw(5)}/>
  <ellipse cx="452" cy="726" rx="14" ry="8" fill="white" opacity="0.6" transform="rotate(-35 452 726)"/>
</g>"""


def paws(y=802):
    out = []
    for s in (-1, 1):
        cx = 500 + s * 95
        out.append(f'<ellipse cx="{cx}" cy="{y}" rx="40" ry="34" fill="{C["white"]}" {ol()} '
                   f'transform="rotate({s * -20} {cx} {y})"/>')
        for k in (-1, 0, 1):
            out.append(f'<circle cx="{cx + k * 13}" cy="{y - 12 + abs(k) * 4}" r="5.5" fill="{C["pink"]}"/>')
    return "\n".join(out)


def choco_bar():
    """もぐもぐ用: かじりかけの板チョコ."""
    return f"""
<g id="bar" transform="rotate(-12 500 760)">
  <rect x="420" y="700" width="160" height="120" rx="12" fill="{C['choco']}" {ol()}/>
  <path d="M473,700 L473,820 M527,700 L527,820 M420,760 L580,760" stroke="#5A2E24" stroke-width="6"/>
  <path d="M410,780 L590,780 L590,830 L410,830Z" fill="{C['red']}" {ol()}/>
  <path d="M410,792 L590,792" stroke="{C['yellow']}" stroke-width="6"/>
  <path d="{heart_d(500, 812, 30)}" fill="{C['pink']}"/>
  <circle cx="440" cy="705" r="20" fill="{C['white']}" opacity="0"/>
</g>"""


def floating_hearts(seed=0):
    import random
    rnd = random.Random(seed)
    out = []
    for (x, y, s, col) in [(220, 300, 46, C['pink']), (800, 340, 38, C['red']), (180, 620, 30, C['red']),
                           (830, 560, 50, C['pink']), (760, 180, 26, C['yellow'])]:
        out.append(f'<path d="{heart_d(x, y, s, rnd.uniform(-20, 20))}" fill="{col}" {olw(6)}/>')
    return "\n".join(out)


def sparkle(x, y, s, col):
    d = (f"M{x},{y - s} Q{x + s * 0.18},{y - s * 0.18} {x + s},{y} Q{x + s * 0.18},{y + s * 0.18} {x},{y + s} "
         f"Q{x - s * 0.18},{y + s * 0.18} {x - s},{y} Q{x - s * 0.18},{y - s * 0.18} {x},{y - s}Z")
    return f'<path d="{d}" fill="{col}" {olw(5)}/>'


def nyan(variant="main"):
    """variant: main (ハートのチョコを持ってとろ〜ん) / mogu (板チョコをもぐもぐ) / love (チョコ発見!ハートの目)."""
    eye = {"main": "sleepy", "mogu": "happy", "love": "heart"}[variant]
    parts = [defs(), tail(), body(), ears(), head(), beret(), eyes(eye), cheeks(), whiskers(),
             mouth("mogu" if variant == "mogu" else "omega", drool=True), collar()]
    if variant == "mogu":
        parts += [choco_bar(), paws(735)]
        parts.append(f'<circle cx="392" cy="560" r="9" fill="{C["choco"]}"/><circle cx="410" cy="578" r="5" fill="{C["choco"]}"/>')
        parts.append(f'<text x="745" y="470" font-family="Hand" font-size="64" fill="{C["choco"]}" '
                     f'stroke="white" stroke-width="10" paint-order="stroke" transform="rotate(12 745 470)">もぐ</text>')
        parts.append(f'<text x="770" y="545" font-family="Hand" font-size="56" fill="{C["choco"]}" '
                     f'stroke="white" stroke-width="10" paint-order="stroke" transform="rotate(12 770 545)">もぐ</text>')
    else:
        parts += [held_heart(bitten=variant == "main"), paws()]
    if variant == "love":
        parts.append(floating_hearts())
        parts.append(sparkle(250, 200, 34, C["yellow"]))
        parts.append(sparkle(840, 760, 28, C["yellow"]))
    body_svg = "\n".join(parts)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n'
            f'{body_svg}\n</svg>')


# ---- 書き出し ----------------------------------------------------------------------
def font_css(pop, hand):
    return (f"@font-face{{font-family:Pop;src:url('file://{os.path.abspath(pop)}')}}"
            f"@font-face{{font-family:Hand;src:url('file://{os.path.abspath(hand)}')}}")


def shoot(html, png, w, h, scale=2):
    tmp = png + ".html"
    with open(tmp, "w") as f:
        f.write(html)
    subprocess.run([HEADLESS, "--no-sandbox", "--hide-scrollbars", f"--window-size={w},{h}",
                    f"--force-device-scale-factor={scale}", "--default-background-color=00000000",
                    "--virtual-time-budget=3000", f"--screenshot={os.path.abspath(png)}",
                    "file://" + os.path.abspath(tmp)], check=True, capture_output=True)
    os.remove(tmp)


def page(css, inner, bg="transparent"):
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}"
            f"html,body{{margin:0;background:{bg};overflow:hidden}}</style></head><body>{inner}</body></html>")


def sheet(svgs, css):
    pal = [("白", C["white"]), ("ピンク", C["pink"]), ("赤", C["red"]), ("黄", C["yellow"]),
           ("ミルクチョコ", C["choco"]), ("ビターチョコ", C["dark"])]
    chips = "".join(f"<div class='chip'><span style='background:{c}'></span>{n}</div>" for n, c in pal)
    prof = [("なまえ", "ちょこにゃん"), ("すきなもの", "チョコレート (ぜんぶ)"),
            ("とくちょう", "頭からチョコをかぶっている白ねこ。いつも口からチョコがとろ〜り"),
            ("チャームポイント", "ベレー帽のハート、しましまリボンと金の鈴、くるんと巻いたしっぽ"),
            ("ひとこと", "「チョコはのみもの…にゃ」")]
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in prof)
    st = f"""
    .wrap{{width:1800px;height:1100px;position:relative;background:#FFF1F5;
      background-image:radial-gradient(#FFD6E4 3px,transparent 3.5px);background-size:36px 36px;
      font-family:Hand,sans-serif;color:{C['dark']}}}
    .main{{position:absolute;left:20px;top:80px;width:980px;height:980px}}
    .main svg,.sub svg{{width:100%;height:100%}}
    h1{{position:absolute;left:60px;top:22px;margin:0;font-family:Pop;font-size:96px;color:{C['red']};
      -webkit-text-stroke:0;text-shadow:5px 5px 0 {C['dark']}, 0 0 0 #000;letter-spacing:4px}}
    h1 small{{font-size:40px;color:{C['choco']};text-shadow:none;margin-left:16px}}
    .card{{position:absolute;left:1000px;top:60px;width:700px;background:white;border:6px solid {C['dark']};
      border-radius:36px;padding:26px 32px;box-shadow:10px 10px 0 {C['pink']}}}
    table{{border-collapse:collapse;font-size:30px;width:100%}}
    th{{text-align:left;white-space:nowrap;color:{C['red']};padding:8px 18px 8px 0;vertical-align:top;font-family:Pop;
      font-size:26px;font-weight:normal}}
    td{{padding:8px 0;line-height:1.35}}
    .pal{{display:flex;gap:14px;margin-top:18px;flex-wrap:wrap}}
    .chip{{display:flex;align-items:center;gap:8px;font-size:24px}}
    .chip span{{width:38px;height:38px;border-radius:50%;border:4px solid {C['dark']};display:inline-block}}
    .sub{{position:absolute;top:640px;width:380px;height:380px;background:white;border-radius:50%;
      border:6px solid {C['dark']};box-shadow:8px 8px 0 {C['pink']}}}
    .cap{{position:absolute;top:1030px;width:380px;text-align:center;font-family:Pop;font-size:30px;color:{C['choco']}}}
    """
    inner = (f"<div class='wrap'><h1>ちょこにゃん<small>Choco-nyan</small></h1>"
             f"<div class='main'>{svgs['main']}</div>"
             f"<div class='card'><table>{rows}</table><div class='pal'>{chips}</div></div>"
             f"<div class='sub' style='left:1010px'>{svgs['mogu']}</div><div class='cap' style='left:1010px'>もぐもぐ</div>"
             f"<div class='sub' style='left:1400px'>{svgs['love']}</div><div class='cap' style='left:1400px'>チョコみつけた！</div>"
             f"</div>")
    return page(css + st, inner)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="nyan_out")
    ap.add_argument("--font-pop", required=True)
    ap.add_argument("--font-hand", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    css = font_css(a.font_pop, a.font_hand)
    svgs = {}
    for v in ("main", "mogu", "love"):
        svgs[v] = nyan(v)
        with open(os.path.join(a.out, f"choconyan_{v}.svg"), "w") as f:
            f.write(svgs[v])
        shoot(page(css, svgs[v]), os.path.join(a.out, f"choconyan_{v}.png"), W, H)
    shoot(sheet(svgs, css), os.path.join(a.out, "choconyan_sheet.png"), 1800, 1100, scale=1)


if __name__ == "__main__":
    main()
