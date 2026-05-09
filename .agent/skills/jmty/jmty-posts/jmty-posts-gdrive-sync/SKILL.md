---
name: jmty-posts-gdrive-sync
description: ジモティー投稿出力（factory/remote）をGoogle Drive などの共有ストレージへ同期コピーする。既存フォルダがある場合は差分同期する。
---

# ジモティー投稿 共有ストレージ同期スキル

## 目的
- `outputs/jmty/factory` と `outputs/jmty/remote` を共有ストレージへコピーする。
- コピー先に同名フォルダがすでにある場合は、最新状態で上書き同期する。

## 同期仕様
- 方式: Python 実装のミラー同期
- 意味:
- 追加/更新ファイルはコピー
- コピー元で削除されたファイルはコピー先からも削除

## デフォルトコピー先
- `TEAM_INFO_SHARED_ROOT/outputs/jmty/`
- `TEAM_INFO_SHARED_ROOT` が未設定の場合は、一般的な Google Drive / OneDrive 配下の `team-info/` を自動検出する。
- `JMTY_GDRIVE_DEST_ROOT` を設定すると同期先を直接上書きできる。

## 実行フロー
1. コピー元フォルダが存在するか確認する。
- `outputs/jmty/factory`
- `outputs/jmty/remote`
2. `.agent/skills/jmty/jmty-posts/jmty-posts-gdrive-sync/scripts/sync_jmty_posts_to_gdrive.py` を実行する。
3. 実行後、同期先に `factory` と `remote` が存在することを確認する。

## 実行コマンド
```bash
python "$TEAM_INFO_ROOT/.agent/skills/jmty/jmty-posts/jmty-posts-gdrive-sync/scripts/sync_jmty_posts_to_gdrive.py"
```

## 引数でコピー先を変更する場合
```bash
python "$TEAM_INFO_ROOT/.agent/skills/jmty/jmty-posts/jmty-posts-gdrive-sync/scripts/sync_jmty_posts_to_gdrive.py" "/destination/root/absolute/path"
```

## 完了報告
- 同期したソース
- 同期先パス
- 実行結果（成功/失敗）
