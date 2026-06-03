# JMTY Workspace — Claude Code 入口

このファイルは Claude Code 向けの短い入口です。長い運用ルールの正本ではありません。
Claude Code では、まず `AGENTS.md` を読み込んでから必要な補足へ進んでください。

@AGENTS.md

## まず読むもの

1. `AGENTS.md`
   - エージェントの行動原則、承認方針、Git 運用、Slash Commands の正本
2. `RULES.md`
   - フォルダ構造、命名規則、禁止事項の正本
3. 作業中フォルダの `CLAUDE.md`
   - その場所だけの用途と注意点
4. `.agent/skills/**/SKILL.md`
   - スキルを使うと決まったときだけ読む

## この repo での役割分担

- `AGENTS.md`: 人と全エージェント共通の運用ルール
- `RULES.md`: リポジトリ構造と命名のルール
- ルート `CLAUDE.md`: Claude Code 用の薄い案内
- `.agent/skills/`: スキルの正本
- `.claude/settings.json`: Claude Code の共有 permission 基準と repo 共有してよい hook
- `.claude/settings.local.json`: 個人用 override と個人 hook。Git 管理外
- `.claude/commands/`: Claude Code 互換用ラッパー。新しい運用ロジックはここに増やさず、`AGENTS.md` と `.agent/skills/` を更新する
- `.gemini/settings.json`: Gemini CLI に `AGENTS.md` を読ませる設定
- `.gemini/commands/`: Gemini CLI の project-local slash commands。`AGENTS.md` から作るアダプタ
- `.codex/prompts/`: Codex custom prompts の repo 側アダプタ。実行用には `~/.codex/prompts/` へ同期する

## すぐ守ること

- ユーザーとの対話は日本語で行う
- ユーザー向けコマンドは `JMTY_ROOT` を使った絶対パスで案内する
- 新規ファイル・フォルダを作る前に `.dev-mode` を確認し、現在モードをユーザーに提示する
- `.gitignore` はユーザーが明示しない限り勝手に変えない
- Claude Code native command と repo 独自 command の衝突は `AGENTS.md` を正本として扱う

## ブラウザ操作のモデル分担

- Kimi WebBridge、agent-browser、Canva、実サイト確認などのブラウザ操作はトークン消費が大きいため、サブエージェントとモデル指定が使える環境では `codex-5.3spark` / `GPT-5.3 Codex Spark` 相当をブラウザ操作担当に優先指定する。
- Spark担当はクリック、待機、ページ移動、スクリーンショット取得、単純な表示確認、反復的なブラウザ検証を担当し、Spark利用枠を積極的に消費する。
- メインエージェントまたは高精度モデルは、作業計画、合否判断、公開可否、最終文言、設計判断、ファイル統合を担当する。ブラウザ操作を高精度モデル単体で長時間抱え込まない。
- 画像生成、複雑な設計判断、最終品質判断が必要な作業は、Spark担当ではなくメインエージェントまたは適切な高精度・画像対応モデルに戻す。
- git status/diff/add/commit/push などの定型的なGit操作も、サブエージェントとモデル指定が使える環境では `codex-5.3spark` / `GPT-5.3 Codex Spark` 相当に優先して任せ、メインエージェントは差分の妥当性、コミット範囲、公開不可情報の混入有無、最終判断を担当する。
- モデル指定やサブエージェント呼び出しができない環境では、同じ役割分担を手順として分離し、スクリーンショット回数、snapshot回数、ページ移動回数を最小化する。
