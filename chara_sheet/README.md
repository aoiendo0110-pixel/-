# しょこら 設定シート

絵師さんへの依頼資料 兼 SNS投稿用のキャラ設定シート（ゆめかわ・ロリータ系）。

- `shokora_sheet.html` … シート本体。設定の文章や色はここを直す
- `img/shokora.png` … 全身イラスト（背景透過）
- `render.js` … PNG書き出し `node render.js`
  - `out/shokora_sheet_3x4.png` (1500×2000)
  - `out/shokora_sheet_4x5.png` (1600×2000, Instagram向け)
- イラスト上のハート番号の位置は `.mk` の `left` / `top`（%指定）で調整

## ゴテゴテ版 (`shokora_sheet_gotegote.html`)

バレンタイン × チョコ × 鈴リボンのロリータ版。茶色水玉・ピンクチェック・板チョコ・白レース・
パール縁のキルティングハート・フリル付きストライプリボン・鈴・ボタン・トリュフ・市松クッキー。

- `out/shokora_gotegote_3x4.png` / `out/shokora_gotegote_4x5.png`
- ちらし飾りの位置は `<script>` 内の配列 `D`（[種類, x, y, 幅, 回転, 色, 重なり順]、x が負なら右端から）
- レース・フリル・パールの柄は `<script>` で SVG を組み立てて CSS 変数に入れている

## ショコラボックス版 (`shokora_chocobox.html`, 16:9)

イラストがメインの横長版。開けたハート型のバレンタインチョコ箱に、しょこらが「いちばん特別な一粒」として入っている構図。

- 左上: 外したフタ（名前）／左下: ショコラメニュー（POINT を一粒ずつ紹介）
- 右上: ギフトタグ（プロフィール）／右中: メッセージカード（性格）／右下: 仕切りトレー（配色）
- `out/shokora_chocobox_16x9.png` (3840×2160, 1920×1080 の 2 倍)

## 設定シート 16:9 (`shokora_sheet_16x9.html`)

右にキャラを大きく、パーツ説明は吹き出し＋線で直接指す設定画スタイル。左に名前・プロフィール・性格・配色。
ゴテゴテ（チョコ垂れ・レース・鈴リボン／お菓子の行列）は上下の縁とハートのメダルの縁に集めている。

- 編集は `src_patisserie.html` → `python3 build_patisserie.py` で `shokora_sheet_16x9.html` を生成 → `node render.js`
- `out/shokora_sheet_16x9.png` (3840×2160)
- 吹き出しの位置は `CALLOUTS`（[番号, 見出し, 補足, x, y, 指す場所fx, fy]）
