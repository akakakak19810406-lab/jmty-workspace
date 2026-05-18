# JMTY週次処理 改善レポート 20260518_020544

- コマンド: `validate-sheet-posts`
- 分類: 未分類エラー
- エラー種別: `NameError`

## エラー概要
```text
name 'normalized_condition_text' is not defined
```

## 自動で行った改善プロセス
- 未分類でも改善レポートとDiscord通知の対象にする
- 次回以降の分類追加に使える情報を保存する

## 次の改善候補
- エラー本文と実行コマンドをもとに再発防止策を追加する
- 同じ失敗が繰り返される場合は known error として分類ルールを増やす
