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
