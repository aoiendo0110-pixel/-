"""src_profile.html に共通の SVG パーツと JS ヘルパーを差し込んで profile_frame.html を作る."""
import pathlib
here = pathlib.Path(__file__).parent
box = (here / 'shokora_chocobox.html').read_text()
a = box.index('<svg width="0" height="0"'); b = box.index('</svg>\n\n<div class="stage"') + 6
h0 = box.index('const css = document.documentElement.style;'); h1 = box.index('/* ---- ハートの箱 ---- */')
src = (here / 'src_profile.html').read_text()
(here / 'profile_frame.html').write_text(src.replace('{{DEFS}}', box[a:b]).replace('{{HELPERS}}', box[h0:h1]))
