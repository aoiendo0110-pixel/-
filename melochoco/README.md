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
