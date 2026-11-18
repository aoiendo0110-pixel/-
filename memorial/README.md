# メモリアルムービー（お葬式・偲ぶ会用スライドショー）

写真を入れるだけで、落ち着いた雰囲気のスライドショー動画（1920×1080 / 30fps / mp4）を作る。

```
cd memorial
cp config.example.json config.json   # 名前・日付・キャプションを書き換える
mkdir photos                          # ここに写真を入れる（01.jpg, 02.jpg … の順に流れる）
python3 make_memorial.py --config config.json --out memorial.mp4
```

構成: オープニング（名前・生没年）→ 写真（ゆっくりズーム＋クロスフェード）→ エンディング

- `photos` を消すと `photos/` フォルダの画像を名前順に全部使う
- 写真ごとに `caption`（一言）と `seconds`（表示秒数）を指定できる
- `music` に音源ファイルを指定すると、動画の長さに合わせて最後をフェードアウト
- 縦長・横長が混ざっても、ぼかした同じ写真を背景に敷いて中央に収める
- `--preview 3 10 20` で指定秒の静止画だけ確認できる
- 明朝フォントは IPA明朝 などを自動で探す（`--font` で指定も可）
- 必要なもの: Python3 + Pillow, ffmpeg
- 写真・音源・config.json・mp4 は個人情報なのでリポジトリに入れない（.gitignore済み）
