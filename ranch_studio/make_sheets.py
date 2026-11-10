# モデリング構造シート (画像) を作る
# 使い方: python3 make_sheets.py <shot.jsで書き出した素材フォルダ> <stats.json>
import sys, json, os
from PIL import Image, ImageDraw, ImageFont
RAW, STATS = sys.argv[1], json.load(open(sys.argv[2]))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_sheet')
F = '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf'
def font(s): return ImageFont.truetype(F, s)
PINK, DEEP, GREEN, YEL, INK = (255,214,230), (232,98,150), (128,180,60), (255,226,122), (110,70,90)
BG = (255,247,250)

def img(name, w, h, checker=False):
    im = Image.open(os.path.join(RAW, name)).convert('RGBA').resize((w, h), Image.LANCZOS)
    if checker:
        bg = Image.new('RGBA', (w, h), (255,255,255,255)); d = ImageDraw.Draw(bg)
        for y in range(0, h, 24):
            for x in range(0, w, 24):
                if (x//24 + y//24) % 2: d.rectangle([x, y, x+23, y+23], fill=(236,228,234,255))
        bg.alpha_composite(im); im = bg
    return im.convert('RGB')

def card(sheet, d, im, x, y, title, sub=None, col=DEEP):
    w, h = im.size
    d.rounded_rectangle([x-8, y-8, x+w+8, y+h+8], 22, fill=(255,255,255), outline=PINK, width=4)
    sheet.paste(im, (x, y))
    tw = d.textlength(title, font=font(30)) + 36
    d.rounded_rectangle([x+14, y+14, x+14+tw, y+62], 24, fill=col)
    d.text((x+32, y+22), title, font=font(30), fill='white')
    if sub: d.text((x+4, y+h+18), sub, font=font(24), fill=INK)

def header(d, W, title, sub):
    d.rectangle([0, 0, W, 120], fill=PINK)
    for i in range(0, W, 46): d.ellipse([i, 106, i+28, 134], fill=BG)
    d.text((48, 26), title, font=font(54), fill=DEEP)
    d.text((48 + d.textlength(title, font=font(54)) + 30, 46), sub, font=font(28), fill=INK)

fmt = lambda n: f'{n:,}'

# ---------- シート1: 全体構成 ----------
W, H = 2560, 1640
s = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(s)
header(d, W, '牧草ロールの撮影スタジオ ― 全体構成', f'three.js / 16:9 / 10秒ループ / 総ポリゴン 約{STATS["total"]/1e6:.1f}M tris')
card(s, d, img('beauty.png', 1600, 900), 48, 160, '完成イメージ (t=2.0s)')
card(s, d, img('clay.png', 800, 450), 1720, 160, '白粘土 (形だけ)', col=(170,140,160))
card(s, d, img('wire.png', 800, 450), 1720, 650, 'ワイヤーフレーム', col=(170,140,160))
y = 1130
d.text((48, y), 'レイヤー構造 ― キャラは専用レイヤーで描くので、ロールにめり込まず「上に座って足を垂らす」重なりになる', font=font(30), fill=DEEP)
y += 56
for i, (f, t, sub) in enumerate([('layer_bg.png', '① 背景レイヤー', 'スタジオ・芝生・牧草ロール・羊・柵'),
                                ('layer_chara.png', '② キャラレイヤー', '2人の全身絵の差し込み枠 (透過PNG)'),
                                ('layer_fg.png', '③ 前景レイヤー', '犬2匹・浮かぶハート・キラキラ')]):
    x = 48 + i * 560
    card(s, d, img(f, 512, 288, checker=i > 0), x, y, t, sub, col=[DEEP, GREEN, (230,180,40)][i])
    if i < 2: d.text((x + 522, y + 110), '＋', font=font(48), fill=DEEP)
x0 = 1720; yy = 1150
notes = ['● キャラ差し込み',
         '  index.html?a=キャラA.png&b=キャラB.png',
         '  絵の下端→お尻までの割合 ahip / bhip (既定0.42)',
         '  サイズ ah / bh、左右位置 ax / bx で微調整',
         '  板ポリはY軸ビルボード＝常にカメラ正面',
         '  座面にピンクの影を自動で敷く',
         '● カメラ',
         '  ゆっくり左右に回り込み＋寄り引き (10秒で一周)']
for n in notes:
    d.text((x0, yy), n, font=font(27 if n.startswith('●') else 25), fill=DEEP if n.startswith('●') else INK); yy += 50 if n.startswith('●') else 40
s.save(os.path.join(OUT, '1_overview.png'))

# ---------- シート2: パーツ別モデリング ----------
parts = [('bale', '牧草ロール', 'ラテ(回転体)で角丸円柱 220分割 → ノイズで\nわらのでこぼこ / 端面は頂点色でうずまき\n＋わら1,500本(チューブ)・リボン帯・リボン'),
         ('blanket', 'ギンガムのブランケット', '140×120分割の板を円柱に沿って巻きつけ\nフチだけ浮かせてフリル感 / 手前にレース'),
         ('sheep', '羊', '高密度の楕円球に「ふくらみ」42個を\nソフトに押し出した1枚メッシュの毛\n顔・耳・ほっぺ・頭のリボンは別パーツ'),
         ('dog', '犬 (2匹・色違い)', '球と楕円の組み合わせで2頭身のおすわり\nくるんと巻いたしっぽ(チューブ)・首輪\n黄色ハートのタグ'),
         ('clover', 'クローバー', 'ハート型の葉をベベル付き押し出し\n三つ葉520本＋四つ葉70本をインスタンス配置'),
         ('whiteclover', 'シロツメクサ', 'カプセル花びらを球状に36枚\n下側だけピンク / 110本配置'),
         ('fence', '白い柵', '先の丸い杭をベベル押し出し×34本\n弧に沿ったレール2本・ところどころリボン'),
         ('garland', 'ガーランド', '懸垂曲線のひもに三角旗×46枚\nピンク・黄・黄緑・白を順番に / ゆらゆら'),
         ('sign', '看板', '角丸ボードに「Clover Ranch」\nキャンバス描画のテクスチャを貼り付け')]
CW, CH = 820, 461
W, H = 48 + 3 * (CW + 48), 160 + 3 * (CH + 190)
s = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(s)
header(d, W, 'パーツ別モデリング', '左：完成の見た目 / 右：白粘土＋ワイヤー (ポリゴンの細かさ)')
for i, (k, name, how) in enumerate(parts):
    x = 48 + (i % 3) * (CW + 48); y = 160 + (i // 3) * (CH + 190)
    card(s, d, img(f'part_{k}.png', CW, CH), x, y, name)
    tris = STATS.get(k, {}).get('tris')
    if tris: d.text((x + CW - d.textlength(f'{fmt(tris)} tris', font=font(26)) - 10, y + 22), f'{fmt(tris)} tris', font=font(26), fill=(150,110,130))
    d.multiline_text((x + 4, y + CH + 18), how, font=font(24), fill=INK, spacing=10)
s.save(os.path.join(OUT, '2_parts.png'))

# ---------- シート3: 動き ----------
W, H = 2560, 1620
s = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(s)
header(d, W, '動きの設計 (10秒でぴったりループ)', 'ここでは静止画のみ。動画への書き出しはまだしてへん')
fw, fh = 960, 540
for i, t in enumerate(['0', '2.5', '5', '7.5']):
    x = 48 + (i % 2) * (fw + 48); y = 160 + (i // 2) * (fh + 60)
    card(s, d, img(f'anim_{t}.png', fw, fh), x, y, f't = {t} 秒')
x0, yy = 2080, 170
for n in ['● カメラ', '左右に±9°回り込み', '寄り引き・高さもふんわり',
          '● 犬', 'しっぽフリフリ (0.5秒周期)', '首かしげ・ぴょこっと跳ねる', '耳ぴくぴく',
          '● 羊', '呼吸でふくらむ・首ふり', '子羊はぴょんぴょん', '耳ゆらゆら',
          '● 草・クローバー', '頂点シェーダーで風になびく', '(16,000本を一括で)',
          '● ガーランド', '旗が1枚ずつずれて揺れる',
          '● ハート・キラキラ', '下からふわっと浮かんで消える', 'キラキラが瞬く']:
    big = n.startswith('●')
    d.text((x0, yy), n if big else '  ' + n, font=font(28 if big else 24), fill=DEEP if big else INK); yy += 50 if big else 38
s.save(os.path.join(OUT, '3_motion.png'))
print('ok')
