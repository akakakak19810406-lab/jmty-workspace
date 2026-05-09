---
name: skill-finder
description: JMTY workspace で利用可能なスキルを一覧し、タスクに適したスキルを特定する。
---

# skill-finder スキル

## 役割
ユーザーの依頼内容から、この repo 内に実在するスキルを選び、読むべき `SKILL.md` のパスを提示する。

## 保守ルール
- このファイルを JMTY workspace のスキル索引の正本として扱う。
- スキルを追加・更新・削除したときは、この一覧と `マニュアル/skills/README.md` を同時に更新する。
- JMTY と関係しない動画制作、Web 制作、note 記事制作などのスキルはこの一覧に戻さない。

## スキル一覧

### JMTY 投稿

| スキル名 | 概要 | パス |
|---|---|---|
| `jmty-posts` | ジモティ投稿作成の起点。工場求人 / 在宅求人を選ぶ | `.agent/skills/jmty/jmty-posts/SKILL.md` |
| `jmty-posts-factory-14` | 工場求人素材から14本の投稿文を作る | `.agent/skills/jmty/jmty-posts/jmty-posts-factory-14/SKILL.md` |
| `jmty-posts-remote-14` | 在宅求人素材から14本の投稿文を作る | `.agent/skills/jmty/jmty-posts/jmty-posts-remote-14/SKILL.md` |
| `jmty-posts-14-variants` | 汎用的に14パターンの投稿文を作る | `.agent/skills/jmty/jmty-posts/jmty-posts-14-variants/SKILL.md` |
| `jmty-posts-gdrive-sync` | 投稿出力を Google Drive へ同期する | `.agent/skills/jmty/jmty-posts/jmty-posts-gdrive-sync/SKILL.md` |
| `jmty-image-organizer` | スプレッドシート画像と Drive フォルダを整理する | `.agent/skills/jmty/jmty-image-organizer/SKILL.md` |

### 共通運用

| スキル名 | 概要 | パス |
|---|---|---|
| `jmty-setup` | JMTY workspace の初期設定と状態確認 | `.agent/skills/common/jmty-setup/SKILL.md` |
| `git-workflow` | コミット、pull、push、PR、Discord 報告の運用 | `.agent/skills/common/git-workflow/SKILL.md` |
| `gdrive-copy` | 出力ファイルを Google Drive へコピーする補助 | `.agent/skills/common/git-workflow/gdrive-copy/SKILL.md` |
| `agent-org-ceo` | 依頼内容を見て適切なスキルへ振り分ける | `.agent/skills/common/agent-org-ceo/SKILL.md` |
| `skill-finder` | この一覧を使ってスキルを探す | `.agent/skills/skill-finder/SKILL.md` |

### 週次素材処理

| スキル名 | 概要 | パス |
|---|---|---|
| `jmty-weekly-assets` | ジモティ週次素材処理スクリプト | `.agent/skills/nanobanana-banner-gen/scripts/jmty_weekly_assets.py` |

## 選び方

| やりたいこと | 使うスキル |
|---|---|
| ジモティ投稿を作りたい | `jmty-posts` |
| 工場求人だけ作りたい | `jmty-posts-factory-14` |
| 在宅求人だけ作りたい | `jmty-posts-remote-14` |
| 投稿文を Google Drive へ送る | `jmty-posts-gdrive-sync` |
| 画像とスプレッドシートの整合性を見たい | `jmty-image-organizer` |
| Git で保存・反映したい | `git-workflow` |
| 初期状態を確認したい | `jmty-setup` |
