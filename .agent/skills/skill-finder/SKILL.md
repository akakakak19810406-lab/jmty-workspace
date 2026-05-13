---
name: skill-finder
description: JMTY workspace で利用可能なスキルを一覧し、タスクに適したスキルを特定する。
---

# skill-finder スキル

## 役割
ユーザーの依頼内容から、この repo 内で読むべき `SKILL.md` を提示する。

## 保守ルール
- このファイルを JMTY workspace のスキル索引の正本として扱う。
- JMTY 制作の入口は増やさず、原則 `jmty-posts` に集約する。
- 内部スクリプトやテンプレートを個別スキルとして一覧に戻さない。

## スキル一覧

| スキル名 | 用途 | パス |
|---|---|---|
| `jmty-posts` | 投稿文作成、週次画像素材、画像整理、Drive 同期を扱う JMTY 統合スキル | `.agent/skills/jmty/jmty-posts/SKILL.md` |
| `jmty-setup` | JMTY workspace の初期設定と状態確認 | `.agent/skills/common/jmty-setup/SKILL.md` |
| `git-workflow` | コミット、pull、push、PR、Discord 報告の運用 | `.agent/skills/common/git-workflow/SKILL.md` |
| `github-task-board` | 改善メモ、調査メモ、あとで直す作業を GitHub Task Board に登録・確認する | `.agent/skills/common/github-task-board/SKILL.md` |
| `gdrive-copy` | 任意ファイルを Google Drive へコピーする補助 | `.agent/skills/common/git-workflow/gdrive-copy/SKILL.md` |
| `agent-org-ceo` | 依頼内容を見て適切なスキルへ振り分ける | `.agent/skills/common/agent-org-ceo/SKILL.md` |
| `skill-finder` | この一覧を使ってスキルを探す | `.agent/skills/skill-finder/SKILL.md` |

## 選び方

| やりたいこと | 使うスキル |
|---|---|
| ジモティ投稿文を作る | `jmty-posts` |
| 工場求人だけ作る | `jmty-posts` の `factory` |
| 在宅求人だけ作る | `jmty-posts` の `remote` |
| 週次画像素材を処理する | `jmty-posts` の `weekly-assets` |
| 画像とスプレッドシートの整合性を見る | `jmty-posts` の `image-organize` |
| 投稿文を共有ストレージへ同期する | `jmty-posts` の `sync` |
| Git で保存・反映したい | `git-workflow` |
| 改善メモやあとで直すタスクを Task Board に残したい | `github-task-board` |
| 初期状態を確認したい | `jmty-setup` |
