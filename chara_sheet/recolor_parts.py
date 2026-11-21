"""parts.html の色を しょこらの公式カラー に置き換えて parts_shokora.html を作る."""
import pathlib, re
here = pathlib.Path(__file__).parent
MAP = {
  # 淡いピンク → 透けパネルのピンク系 (#FCC0E4)
  '#fde3ec':'#feeaf5','#fde8ef':'#feeef7','#fbd6e2':'#fdd9ee','#fbd2df':'#fdd3ec','#f7c6d5':'#fcc8e7','#f5b8cb':'#fcc0e4',
  '#f3b3c8':'#f9b2dc','#fff2f6':'#fff4fa','#ffd3e4':'#fdd3ec','#fbc2d4':'#fcc8e7','#f7a5c1':'#f8aed9','#fbd9e4':'#fde0f0',
  '#f6c4d4':'#fcc0e4','#f6b3c8':'#fcc0e4','#ef9fbb':'#f59fd2','#f7c4d5':'#fcc8e7','#fbd0de':'#fdd3ec','#fde6ee':'#feeaf5','#ffb6cd':'#f8b4dc',
  # 濃いピンク → ワイン系 (#A82454 / #A83C60)
  '#f09bb6':'#f59fd2','#f2a9c0':'#f2a2cf','#e68fae':'#e98cc0','#e27fa6':'#d76aa6','#f78fb2':'#e27ab4','#ff9fc0':'#d8507f',
  '#ec6f99':'#b8305f','#c94d7b':'#8a1d45','#e8789d':'#a82454','#e75b93':'#a82454','#ff5f8f':'#c8336a','#f07ea4':'#c8467a',
  '#c75f86':'#a83c60','#c8678b':'#a83c60','#d0708f':'#c05a7c','#a14767':'#a82454','#a8355f':'#6e1236','#d95f8b':'#a83c60',
  # チョコ → ココア系 (#6C4848)
  '#8b5a44':'#8a6262','#5a3426':'#6c4848','#3a1f16':'#3e2a2c','#3e2219':'#4a3234','#4a291f':'#553a3c','#6b3f2e':'#6c4848',
  '#7a4a36':'#7c5656','#9a6650':'#9a7272','#2e1710':'#33222a','#b98a6e':'#a88080','#5b3a1e':'#4a3234',
  # 金 → 公式の金 (#F0E4A8) 寄り
  '#d8b072':'#e6cf86','#e9c47a':'#efd890','#fff6d6':'#fffbe8',
  # クリーム
  '#fff8f0':'#fffbfd',
}
s = (here / 'parts.html').read_text()
s = re.sub(r'#[0-9a-fA-F]{6}\b', lambda m: MAP.get(m.group(0).lower(), m.group(0)), s)
s = s.replace('Sweet Chocolat Parts', 'Shokora Color Parts').replace('のパーツ素材（背景透過PNG）', 'のパーツ素材・しょこら公式カラー（背景透過PNG）')
(here / 'parts_shokora.html').write_text(s)
