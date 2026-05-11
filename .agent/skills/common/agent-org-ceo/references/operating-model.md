# Operating Model

## 目的
JMTY workspace の作業を、投稿文作成・素材整理・Git 運用に絞って振り分ける。

## 受付
- CEO は依頼を短く言い換える。
- JMTY 投稿、素材整理、Google Drive 同期、Git 運用、セットアップのどれかへ分類する。

## 振り分け
- 投稿文作成: Writing Manager（`jmty-posts`）
- 求人素材の確認: Research Manager
- 画像・週次素材処理: Media Manager（`jmty-posts`）
- Drive 同期・定型処理: Automation Manager（`jmty-posts` / `gdrive-copy`）
- Git / setup / repo 整理: Ops Manager
- Web Manager は JMTY で必要な簡易表示物があるときだけ使う。

## 読み込み境界
- CEO は `skill-finder` と `agents/` の README だけを見る。
- メンバーは自分の担当スキルだけ読む。
- JMTY と関係しないスキルや外部 repo の運用を混ぜない。

## 典型パターン

| 依頼 | 流れ |
|---|---|
| 投稿文を作る | CEO -> Writing Manager |
| 入力素材を確認して投稿文を作る | CEO -> Research Manager -> Writing Manager |
| 生成物を Drive へ送る | CEO -> Automation Manager |
| 画像配置を整理する | CEO -> Media Manager |
| 変更を保存・反映する | CEO -> Ops Manager |
