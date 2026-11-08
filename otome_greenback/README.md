# 乙女グリーンバック素材

フリル・リボン・レース・ハートの、ピンク系ゆめかわ動画素材（グリーンバック #00FF00）。
すべて 1920×1080 / 30fps / H.264 MP4。緑を含まない色だけで描いているので、クロマキーできれいに抜けます。

![preview](preview_sheet.png)

| # | ファイル | 長さ | 内容 | 使いどころ |
|---|---|---|---|---|
| 1 | `heart_float_greenback.mp4` | 6秒 | ハートとキラキラがふわふわ上昇 | **シームレスループ**。画面全体のデコ |
| 2 | `ribbon_pop_greenback.mp4` | 4秒 | 中央に大きなリボンがポンッと弾んで登場＋ハートが飛び散る | 冒頭・強調 |
| 3 | `lace_frame_greenback.mp4` | 5秒 | 四辺のレースが伸びて、四隅にリボン＋パールライン | 画面フレーム（中央は抜け） |
| 3b | `lace_frame_skyyellow_greenback.mp4` | 5秒 | 3 のリボンだけ水色×黄色（対角で交互） | 画面フレーム（中央は抜け） |
| 4 | `frill_telop_greenback.mp4` | 5秒 | フリル付きテロップ枠が登場→待機→退場 | 下部テロップ。中は空欄で文字入れ用 |
| 5 | `heart_burst_greenback.mp4` | 2秒 | ハートがパーンと弾ける | 強調・トランジション |
| 6 | `lace_line_greenback.mp4` | 3秒 | リボン付きレースラインが中央から伸びる | タイトル下の区切り線 |
| 7 | `heart_bubble_greenback.mp4` | 5秒 | フリル縁のハート吹き出しが登場→鼓動→退場 | セリフ・コメント枠 |
| 8 | `garland_greenback.mp4` | 4秒 | ハート・レース・リボンのガーランドがゆらゆら | **シームレスループ**。画面上部 |
| 9 | `moon_3d_greenback.mp4` | 8秒 | ふんわり3D満月（ハートのクレーター入り）がくるっと自転、パステルの星が周りを回って、もこもこ雲がゆらゆら | **シームレスループ**。夜・おやすみ系の演出 |
| 10 | `dream_float_bg_greenback.mp4` | 10秒 | ゆめかわ浮遊3D背景：お姫さまベッド・満月・おすわり黒猫・リボンのへび・リボン・ハート・星が奥行きのある空間でゆらゆら、手前に雲海 | **シームレスループ**。ステージ・MV背景 |

## マスキングテープ画像素材（`masking_tape/`）

手でちぎったギザギザ端／ギザギザばさみのジグザグ端のマステ切れ端。全13柄 × 長・短の2サイズ。
`transparent/` が背景透過PNG、`greenback/` がグリーンバックPNG（どちらも2倍解像度）。
柄：ピンクギンガム・ラベンダーギンガム・ピンクドット・水色ドット・ハート・キャンディストライプ・レース柄・星・リボン柄・お花・黄色チェック・ステッチハート・水色ハート。
`sheet_corners.png` は四隅留め（写真やワイプの角に）、`sheet_all.png` は全柄の一覧（どちらも3840×2160）。
`node src/export_tape.js masking_tape` で再書き出し。

## 再生成

```sh
cd src
node render.js preview <出力先>   # 代表フレームPNG
node render.js video ..           # MP4を書き出し（素材名を後ろに付けると個別に）
PAGE=moon.html node render.js video ..   # 満月3D（three.js）
PAGE=dream_bg.html node render.js video ..   # ゆめかわ浮遊3D背景
```

`src/index.html#m=<素材名>&t=<秒>` でブラウザ確認、`&transparent` で背景なし。
