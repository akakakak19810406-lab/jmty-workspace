---
name: agent-org-ceo
description: オーナーの下で意思決定を行う CEO エージェントと、その配下の役割別メンバー構成を使って、必要なスキルだけを読む形で token 消費を抑えながら仕事を振り分けたいときに使う。
---

# agent-org-ceo

## 役割
- ユーザーを最終オーナーとして扱う
- CEO エージェントは意思決定と優先順位づけだけを担当する
- 実作業は配下のメンバーへ振り分ける
- メンバーは担当領域に関係するスキルだけを読む
- CEO 自身は全スキル本文を読まず、索引と役割表だけで判断する

## 基本原則
- オーナー: ユーザー。最終判断を持つ
- CEO: 方針決定、担当割り当て、成果物の統合
- メンバー: 専門領域ごとの実行担当
- 正本: `.agent/skills/**/SKILL.md`
- CLI 別の `.codex/prompts/` や `.claude/commands/` は薄い入口に留める

## 受付フロー

### `/コマンド` 経由の場合
1. `AGENTS.md` のコマンド表を参照し、対応するスキルを特定する
2. CEO はそのスキルを担当するメンバーを 1 行で指名する
3. 指名されたメンバーがスキルを読んで実行する

### 自由文依頼の場合
1. CEO が依頼を 1 文で再定義する
2. `agents/` の役割別 README を見て担当メンバー候補を選ぶ
3. 候補が複数ある場合は最初に必要な 1 メンバーから始める
4. CEO は必要なメンバーだけに仕事を渡す
5. 各メンバーは自分の担当に関係するスキルだけを読む
6. CEO が結果をまとめ、オーナーに確認事項だけ返す

## トークン節約ルール
- CEO は `skill-finder` と `agents/` 配下の役割別 README だけを見る
- メンバーは自分に関係するスキル本文だけ読む
- 無関係なスキル一覧を毎回列挙しない
- 長い作業では `context-handoff` を使って途中経過を圧縮する
- 同じ領域の依頼では同じメンバーに寄せ、探索をやり直さない

## 役割の分け方
役割の分類ビューは `agents/` ディレクトリ構成とする。
各スキル本文の正本は `.agent/skills/**/SKILL.md` に置く。

標準構成:
- CEO
- Ops Manager
- Web Manager
- Media Manager
- Research Manager
- Writing Manager
- Automation Manager

必要ならタスク単位でワーカーを増やしてよいが、恒久的な役割追加は `agents/` の構成を先に更新する。

## CEO の判断基準
- まず「何を決める仕事か」「何を作る仕事か」を分ける
- 決めるだけなら CEO が保持する
- 作る仕事は担当メンバーへ渡す
- 複数領域にまたがるときだけ CEO が統合役になる

## メンバー連携の典型パターン
詳細は `references/operating-model.md` を正本とする。要約:

| パターン | 流れ |
|---------|------|
| Web 改修 | CEO → Web Manager（→ 必要なら Research Manager）→ Ops Manager（Git） |
| 動画制作 | CEO → Writing Manager（台本）→ Media Manager（制作）→ 必要なら Automation Manager |
| GWS 自動化 | CEO → Automation Manager（→ repo 変更があれば Ops Manager） |

## Writing Manager と Media Manager の境界
- 台本・テキスト生成 → Writing Manager
- 動画レンダリング・音声・字幕・Canva → Media Manager
- 動画制作では必ず Writing Manager が先に台本を完成させてから Media Manager に渡す

## フォールバック対応
- 担当スキルが見つからない → CEO が `skill-finder` で再探索し、最も近いスキルを使う
- どのメンバーにも当たらない → CEO がユーザーに確認し、スキルなしで通常対応するか判断を仰ぐ
- メンバーが担当外依頼を受けた場合 → CEO に差し戻し、再アサインする

## 参照ファイル
- 役割一覧（正本）: `agents/`
- 役割一覧（補助・人向け要約）: `references/member-roster.md`
- 組織図: `references/org-chart.md`
- 運用手順: `references/operating-model.md`
