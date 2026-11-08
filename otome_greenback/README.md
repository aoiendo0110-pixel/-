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

## 再生成

```sh
cd src
node render.js preview <出力先>   # 代表フレームPNG
node render.js video ..           # MP4を書き出し（素材名を後ろに付けると個別に）
```

`src/index.html#m=<素材名>&t=<秒>` でブラウザ確認、`&transparent` で背景なし。
