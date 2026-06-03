# AGENTS.md

このリポジトリは、ジモティ投稿作成・素材整理・生成物管理に用途を絞った JMTY workspace です。

## 計画先行ワークフロー
すべての作業は、着手前に必ず計画を立て、ユーザーへ提示して確認を取ってから実行すること。

- 可能な環境では Plan mode を使い、計画作成とユーザー確認を先に行う。
- Plan mode が使えない環境でも、同等の手順として「実行前の計画提示」と「確認後の実行」を徹底する。
- ファイル変更、コマンド実行、Git 操作、外部サービス連携、長時間処理は、特に実行前確認を省略しない。
- ユーザーが明示的に即時実行を求めた場合でも、最低限の短い計画を提示してから進める。

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
| `/setup` | `.agent/skills/common/jmty-setup/SKILL.md` | JMTY workspace 初期セットアップ補助 |
| `/jmty` | `.agent/skills/jmty/jmty-posts/SKILL.md` | ジモティ統合作業 |
| `/jmty-weekly` | `.agent/skills/jmty/jmty-posts/SKILL.md` | ジモティ週次素材処理 |

## Git 運用
Git 関連操作を行う場合は `.agent/skills/common/git-workflow/SKILL.md` を使う。リモートはこの JMTY repo 専用の `origin` を使う。

## Secret Handling
`config/discord-jmty-webhook.json` はローカル秘密情報として扱い、Git に含めない。共有が必要な場合は example ファイルだけを使う。

## Code File Header Rule
新しく作るコードファイルには、冒頭に「何をするコードか」を 2-4 行で説明するコメントを入れる。

## ブラウザ操作のモデル分担

- Kimi WebBridge、agent-browser、Canva、実サイト確認などのブラウザ操作はトークン消費が大きいため、サブエージェントとモデル指定が使える環境では `codex-5.3spark` / `GPT-5.3 Codex Spark` 相当をブラウザ操作担当に優先指定する。
- Spark担当はクリック、待機、ページ移動、スクリーンショット取得、単純な表示確認、反復的なブラウザ検証を担当し、Spark利用枠を積極的に消費する。
- メインエージェントまたは高精度モデルは、作業計画、合否判断、公開可否、最終文言、設計判断、ファイル統合を担当する。ブラウザ操作を高精度モデル単体で長時間抱え込まない。
- 画像生成、複雑な設計判断、最終品質判断が必要な作業は、Spark担当ではなくメインエージェントまたは適切な高精度・画像対応モデルに戻す。
- git status/diff/add/commit/push などの定型的なGit操作も、サブエージェントとモデル指定が使える環境では `codex-5.3spark` / `GPT-5.3 Codex Spark` 相当に優先して任せ、メインエージェントは差分の妥当性、コミット範囲、公開不可情報の混入有無、最終判断を担当する。
- モデル指定やサブエージェント呼び出しができない環境では、同じ役割分担を手順として分離し、スクリーンショット回数、snapshot回数、ページ移動回数を最小化する。
