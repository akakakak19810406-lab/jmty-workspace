# JMTY Workspace

ジモティ関連のスキル、入力素材、生成物、共通エージェント基盤を team-info から分離した作業用リポジトリです。

## Main Areas
- `.agent/skills/jmty/`: ジモティ専用スキル
- `inputs/jmty_*`: 投稿生成用の入力素材
- `outputs/jmty/`: 既存の生成済み投稿文
- `.agent/skills/common/git-workflow/`: Git 運用スキル
- `.agent/skills/common/agent-org-ceo/`: slash command 受付用 CEO 基盤

## Secret Handling
`config/discord-jmty-webhook.json` はローカル設定として `.gitignore` に入れています。新しいリモートへは送らないでください。
