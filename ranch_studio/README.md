# 牧草ロールの撮影スタジオ (3D)

クローバー・牧場・犬・羊 / ピンク・黄色・黄緑。牧草ロールの上に2人が座れる撮影スタジオ風の3Dシーン (three.js, 16:9, 10秒ループ)。

- `index.html` … シーン本体。ブラウザで開くと動く (ローカルサーバー経由で開いてな)
- `shot.js` … 静止画の書き出し `node shot.js out.png "<?クエリ#ハッシュ>" <秒>`
- `make_sheets.py` … モデリング構造シート (`model_sheet/`) を作る

## キャラの差し込み
`index.html?a=キャラA.png&b=キャラB.png`
- `ahip` / `bhip` … 絵の下端からお尻までの高さの割合 (既定 0.42)
- `ah` / `bh` … 絵の高さ、`ax` / `bx` … 左右の位置
- キャラは専用レイヤーで描くので、ロールにめり込まずに上に座って足を垂らした重なりになる

## 表示モード (ハッシュ)
`#view=wire` / `#view=clay` / `#layer=bg|chara|fg` / `#part=bale|sheep|dog|…` / `#still&t=2`
