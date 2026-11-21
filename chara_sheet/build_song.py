"""src_song.html に共通パーツを差し込み、しょこら公式カラーに置き換えて song_frame.html を作る."""
import pathlib, re
here = pathlib.Path(__file__).parent
box = (here / 'shokora_chocobox.html').read_text()
a = box.index('<svg width="0" height="0"'); b = box.index('</svg>\n\n<div class="stage"') + 6
h0 = box.index('const css = document.documentElement.style;'); h1 = box.index('/* ---- ハートの箱 ---- */')
src = (here / 'src_song.html').read_text().replace('{{DEFS}}', box[a:b]).replace('{{HELPERS}}', box[h0:h1])
rc = (here / 'recolor_parts.py').read_text()
MAP = eval(rc[rc.index('MAP = ') + 6:rc.index('}\n') + 1])
src = re.sub(r'#[0-9a-fA-F]{6}\b', lambda m: MAP.get(m.group(0).lower(), m.group(0)), src)
(here / 'song_frame.html').write_text(src)
