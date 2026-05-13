---
name: github-task-board
description: JMTY workspace の改善メモや作業タスクを GitHub Projects の Task Board に登録・確認するためのスキル。ジモティ機能改善、運用改善、調査メモ、あとで直すこと、GitHub Issue/Project 登録依頼で使う。
---

# GitHub Task Board スキル

## 役割
JMTY workspace の改善案、調査メモ、あとで直す作業を GitHub の `Task Board` に残す。
ユーザーが「メモして」「タスク化して」「改善すべきことを残して」「あとでやるに入れて」と言ったらこのスキルを使う。
ユーザーが「メモされたタスクをやって」「Task Board の次のタスクを実行して」「終わったことを知らせて」と言った場合もこのスキルを使う。

## 前提
- repo: `akakakak19810406-lab/jmty-workspace`
- Project: `Task Board`
- Project number: `1`
- `.env` に `OWNER`, `REPO`, `PROJECT_TITLE`, `COLLABORATOR` があればそれを優先する。
- GitHub CLI は `project` スコープ付きでログイン済みであること。

## 登録方針
- まず GitHub Issue を作る。
- Issue に labels を付ける。
- Issue を Project `Task Board` に追加する。
- 可能なら Project の `Status`, `Priority`, `Type`, `Area` も設定する。
- 迷ったら Status は `Backlog`、Priority は `Medium`、Type は `Improvement`、Area は `Ops` にする。

## ラベル対応
- Type:
  - `Feature` -> `type:feature`
  - `Bug` -> `type:bug`
  - `Improvement` -> `type:improvement`
  - `Chore` -> `type:chore`
  - `Research` -> `type:research`
- Priority:
  - `High` -> `priority:high`
  - `Medium` -> `priority:medium`
  - `Low` -> `priority:low`
- Area:
  - `Frontend` -> `area:frontend`
  - `Backend` -> `area:backend`
  - `Infra` -> `area:infra`
  - `Docs` -> `area:docs`
  - `Design` -> `area:design`
  - `Ops` -> `area:ops`

## タスク登録
補助スクリプトを使う。

```bash
python3 .agent/skills/common/scripts/github_task_board.py create \
  --title "画像プロンプトのランダム選択を見直す" \
  --body "在宅画像の画風が偏るため、カテゴリ単位の抽選と選択ログを追加する。" \
  --type Improvement \
  --priority Medium \
  --area Backend \
  --status Backlog
```

## メモ登録
調査メモや改善候補も、あとで拾えるように Issue と Project item として残す。

```bash
python3 .agent/skills/common/scripts/github_task_board.py memo \
  --title "次回確認: Drive同期失敗時の復旧導線" \
  --body "GWS認証切れのとき、Chrome fallback と Discord通知が期待通り動くか確認する。" \
  --area Ops
```

## 確認

```bash
python3 .agent/skills/common/scripts/github_task_board.py list
```

次に実行できるタスクを1件だけ見る:

```bash
python3 .agent/skills/common/scripts/github_task_board.py next
```

## メモされたタスクを実行する
ユーザーが「メモされたタスクをそのまま実行して」と言ったら、次の順で進める。

1. `next` で `Backlog` / `Todo` のタスクを1件読む。
2. Issue のタイトル、本文、ラベル、Project fields から作業内容を判断する。
3. 作業前に `start <issue番号またはURL>` を実行し、Status を `In Progress` にする。
4. repo の該当ファイルを調査・修正・検証する。
5. 完了後に `done <issue番号またはURL>` を実行し、Issue コメントと Status を更新する。

作業開始:

```bash
python3 .agent/skills/common/scripts/github_task_board.py start 12
```

完了:

```bash
python3 .agent/skills/common/scripts/github_task_board.py done 12 \
  --summary "画風選択の偏りを調査し、選択ログを残す処理を追加しました。" \
  --tests "python3 -m py_compile scripts/jmty_gui.py"
```

レビュー待ちにしたい場合:

```bash
python3 .agent/skills/common/scripts/github_task_board.py done 12 \
  --status Review \
  --summary "実装は完了。画面確認だけユーザーにお願いする状態です。"
```

## 完了通知の考え方
- 作業が終わったら Issue に日本語で短い完了コメントを残す。
- Status は、確認不要なら `Done`、ユーザー確認が必要なら `Review` にする。
- final response では Issue URL、変更内容、確認結果、Project status を伝える。
- Git commit / push が必要な場合は、別途 `git-workflow` に従う。

## 完了報告
ユーザーには次を短く伝える。
- 作成した Issue URL
- Project に追加できたか
- 設定した Status / Priority / Type / Area
- タスクを実行した場合は、完了コメントを書いた Issue URL と最終 Status
