# めろチョコ 歌詞動画ジェネレーター

イラスト1枚と音源から、バレンタイン×ロリータ風（チョコ・フリル・リボン）の歌詞動画を作るスクリプト。

```
pip install pillow numpy
python3 make_video.py --image illust.png --audio source.mov \
    --font-pop DelaGothicOne.ttf --font-cute HachiMaruPop.ttf --out out.mp4
```

- 歌詞とタイミングは `GROUPS`、背景の切り替えは `BG_SCHEDULE` で編集できる
- `--preview 1.5 10.0` で指定秒の静止画だけ書き出し
- フォント: Dela Gothic One / Hachi Maru Pop（どちらも SIL OFL）
- 音源・動画・フォントファイルはリポジトリに含めない

## MV風バージョン (`make_mv.py`)

カメラワーク（ズーム・パン・チルト）、レトロPC風ウィンドウ、ハート型の切り抜き、
numpy 製の3Dオブジェクト（`render3d.py`）を使った、動きの多いバージョン。

```
python3 make_mv.py --image illust.png --audio source.mov \
    --font-pop DelaGothicOne.ttf --font-cute HachiMaruPop.ttf --out mv.mp4
```

- シーン構成は `SCENES`（開始秒・終了秒・描画関数・入りのトランジション）
- 3Dスプライトは初回にレンダリングして `--cache` のフォルダに保存する

## ゴテゴテ可愛い版 (`make_cute.py`)

お菓子作り × チョコ × バレンタイン × ロリータ仕様。チョコ垂れ・パール・3段フリル・レースのフレーム、
キルティングやギンガムの背景、3Dのお菓子（マカロン・いちご・カップケーキ・クッキー・リボンなど）入り。
装飾パーツは `deco.py`。

```
python3 make_cute.py --image illust.png --audio source.mov \
    --font MochiyPopOne.ttf --font-sub HachiMaruPop.ttf --out cute.mp4
```

## 3Dカフェ版 (`cafe3d.py` + `make_cafe_mv.py`)

Blender (`pip install bpy`) でピンクのお菓子カフェ＆キッチンを丸ごとコードで作り、
カメラが部屋の中を移動する3D映像をレンダリング。そこにキャラと歌詞を合成する。
歌詞は、各行が出ている間の顔の位置を調べて、顔に重ならない場所へ自動で配置する。

```
# 1) 3D (Workbench, 1280x720) をレンダリング。2プロセスに分けると速い
python3 cafe3d.py --font Mochiy.ttf --out frames --start 0 --end 464
python3 cafe3d.py --font Mochiy.ttf --out frames --start 464 --end 928
# キャラ位置 (アンカー) だけ作り直すとき
python3 cafe3d.py --font Mochiy.ttf --out anchors --anchors-only
# 2) 合成
python3 make_cafe_mv.py --frames frames --anchors anchors --image illust.png --audio source.mov \
    --font Mochiy.ttf --font-sub Hachi.ttf --out cafe_mv.mp4
```

## イラストを動かす (`animate_illust.py`)

イラスト1枚に、まばたき・頭の傾き・ツインテールの揺れ・泡立て器を振る腕・脚・呼吸・ふわふわ浮遊をつけた10秒ループ動画。
閉じ目は目の部分を肌で埋めて描き足し、体は `cv2.remap` の変形場で動かす。肘から先 (泡立て器) は別レイヤーに切り抜いて形を保ったまま回す (座標は元イラスト 4409x3206 基準)。

```
pip install opencv-python-headless pillow numpy imageio-ffmpeg
python3 animate_illust.py --image illust.png --out anim.mp4 --webm anim_alpha.webm
```

- `--webm` は背景透過の VP9。`--preview 1.8 3.0` で指定秒の静止画だけ書き出し

## 合成用エフェクト素材 (`make_fx.py`)

3Dのお菓子・チョコの動画に重ねて使う汎用エフェクト。1920x1080 / 30fps で、
透過 ProRes 4444 (`.mov`)・透過 VP9 (`.webm`)・グリーンバック (`_greenback.mp4`) を書き出す。

| 名前 | 秒 | 内容 |
|---|---|---|
| sparkle | 8 (loop) | キラキラが瞬く (画面中央は少なめ) |
| sprinkles | 8 (loop) | カラースプレーが回りながら降る |
| hearts | 8 (loop) | ぷっくりハートがゆらゆら上る |
| confetti | 7 | 左右下からクラッカーの紙吹雪 |
| steam | 8 (loop) | 下中央から立ちのぼる湯気 |
| sugar | 10 (loop) | 粉砂糖がふわふわ舞い落ちる (奥行きぼかし付き) |
| shine | 5 | 斜めの光が2回スーッと通る (ツヤ出し用) |
| pop | 5 | 登場時の「ポン!」(閃光・リング・集中線・ハートと星が飛び散る) |
| drip_choco / drip_berry | 6 | 画面上からチョコ / いちごチョコが垂れてくる |
| aurora | 10 (loop) | 白いオーロラのリボンがふわふわ流れる |

```
python3 make_fx.py --out fx_out            # 全部
python3 make_fx.py --out fx_out pop hearts # 一部だけ
```

- sparkle / steam / shine / aurora はスクリーン・加算合成用の黒背景版 (`_blackback.mp4`) も出る
- 湯気・光・粉砂糖のような半透明のものは、グリーンバックだと緑が透けるので透過版を推奨
- shine はお菓子のレイヤーでクリッピング (またはスクリーン合成) して使う想定
