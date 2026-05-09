# team-info — Claude Code 入口

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
- ユーザー向けコマンドは `TEAM_INFO_ROOT` を使った絶対パスで案内する
- 新規ファイル・フォルダを作る前に `.dev-mode` を確認し、現在モードをユーザーに提示する
- `.gitignore` はユーザーが明示しない限り勝手に変えない
- Claude Code native command と repo 独自 command の衝突は `AGENTS.md` を正本として扱う
