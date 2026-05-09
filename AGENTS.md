# AGENTS.md

このリポジトリは、team-info から分離したジモティ専用の作業リポジトリです。

## 開発モード管理
新規ファイル・フォルダの作成を伴う作業前に `.dev-mode` を読み、現在のモードをユーザーへ提示して確認すること。

- `team`: 通常のチーム開発モード
- `personal`: 個人作業は `personal/<account>/` 配下へ置く

## Slash Commands
slash command はまず `.agent/skills/common/agent-org-ceo/SKILL.md` が受け付け、必要なスキルへ振り分ける。

| コマンド | 読み込むスキル | 概要 |
|---|---|---|
| `/c` | `.agent/skills/common/git-workflow/SKILL.md` | コミットのみ |
| `/git` | `.agent/skills/common/git-workflow/SKILL.md` | コミットと反映 |
| `/git-nd` | `.agent/skills/common/git-workflow/SKILL.md` | コミットと反映、Discord報告なし |
| `/pull` | Git fetch / pull --rebase | 最新ソース同期 |
| `/ceo` | `.agent/skills/common/agent-org-ceo/SKILL.md` | CEO 経由で振り分け |
| `/setup` | `.agent/skills/common/team-info-setup/SKILL.md` | 初期セットアップ補助 |
| `/jmty` | `.agent/skills/jmty/jmty-posts/SKILL.md` | ジモティ投稿作成 |
| `/jmty-weekly` | `.agent/skills/nanobanana-banner-gen/scripts/jmty_weekly_assets.py` | ジモティ週次素材処理 |

## Git 運用
Git 関連操作を行う場合は `.agent/skills/common/git-workflow/SKILL.md` を使う。新しいリモートはこの repo 用に別途設定する。

## Secret Handling
`config/discord-jmty-webhook.json` はローカル秘密情報として扱い、Git に含めない。共有が必要な場合は example ファイルだけを使う。

## Code File Header Rule
新しく作るコードファイルには、冒頭に「何をするコードか」を 2-4 行で説明するコメントを入れる。
