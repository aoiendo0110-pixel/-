# 牧場 × クローバー × お花 × フリル × ハート × レース 汎用動画素材

ピンク・黄色・黄緑のパステル系で統一した動画素材のセット。すべて 30fps。

| ファイル (`out/`) | 内容 | サイズ / 長さ | 背景 |
|---|---|---|---|
| `ranch_loop.mp4` / `.webm` | 牧場の背景（羊・柵・風車・納屋・クローバー畑・お花・ちょうちょ） | 1920×1080 / 8秒ループ | あり |
| `frill_frame_transparent.webm` ほか `_yellow` `_green` | **フレーム**：2段フリル＋レース＋四隅の花束（クローバー・お花・リボン） | 1920×1080 / 6秒ループ | 中央透過 |
| `heart3d_transparent.webm` | **3Dモデル**：フリルに包まれたぷっくりハートがくるっと回り、周りをクローバー・お花・ハート・パールが回る | 1080×1080 / 6秒ループ | 透過 |
| `falling_transparent.webm` / `falling_up_transparent.webm` | ハート・クローバー・お花・花びら・キラキラが降る / 下から昇る | 1920×1080 / 8秒ループ | 透過 |
| `frill_transition_transparent.webm` | フリルの布が緑→黄→ピンクの順に降りてきて画面をおおい、下へ抜けるトランジション（0.6〜1.25秒は全面がかくれるので 0.9秒ごろでカットをつなぐ） | 1920×1080 / 2秒 | 透過 |
| `plant_grow_transparent.webm` | 画面の下の両すみからツルが伸びて葉っぱ・クローバー・お花が咲く（伸びきったあとは揺れる） | 1920×1080 / 6秒 | 透過 |
| `pattern_loop.mp4` / `.webm` ほか `_yellow` `_green` | ギンガムチェック＋モチーフ柄がななめに流れ、上下にフリルとレース | 1920×1080 / 6秒ループ | あり |

- 透過素材は **WebM (VP9 アルファ付き)**。編集ソフトが透過 WebM を読めないときは、`*_greenback.mp4`（グリーンバック）をクロマキーで抜く
- 透過 MOV (ProRes 4444) がほしいときは `PRORES=1` を付けて書き出す
- `*_thumb.png` は各素材の途中のコマ

## 作り直し方

各素材は `src/*.html`（Canvas 2D / 3D は three.js）。パーツは `src/motifs.js`（ハート・クローバー・デイジー・小花・チューリップ・葉っぱ・リボン・パール・フリル・レース・ギンガム）。

```
# リポジトリ直下で
python3 -m http.server 8765 &
node ranch_motif/src/render.mjs ranch_loop            # → ranch_motif/out/ranch_loop.mp4 / .webm
node ranch_motif/src/render.mjs frill_frame yellow    # #yellow 版
node ranch_motif/src/render.mjs heart3d --still 1.5   # 1.5秒のコマを PNG で 1 枚だけ
PRORES=1 node ranch_motif/src/render.mjs heart3d      # 透過 MOV も書き出す
```

ブラウザで `http://localhost:8765/ranch_motif/src/frill_frame.html#green` のように開くと、その素材の 1 コマ目を確認できる。
