"""src_patisserie.html に共通の SVG パーツと JS ヘルパーを差し込んで shokora_sheet_16x9.html を作る."""
import pathlib
here = pathlib.Path(__file__).parent
box = (here / 'shokora_chocobox.html').read_text()
a = box.index('<svg width="0" height="0"'); b = box.index('</svg>\n\n<div class="stage"') + 6
h0 = box.index('const css = document.documentElement.style;'); h1 = box.index('/* ---- ハートの箱 ---- */')
src = (here / 'src_patisserie.html').read_text()
(here / 'shokora_sheet_16x9.html').write_text(src.replace('{{DEFS}}', box[a:b]).replace('{{HELPERS}}', box[h0:h1]))
