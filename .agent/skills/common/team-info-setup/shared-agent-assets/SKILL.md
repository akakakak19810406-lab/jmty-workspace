---
name: shared-agent-assets
description: 複数 repo で共有する Claude / Codex / Claudian 向けルール・スキル資産を team-info 流儀で同期する。`AGENTS.md` と `.agent/skills` を正本のまま維持しつつ、外部共有 repo は補助レイヤーとして扱う。
---

# shared-agent-assets スキル

## 役割
- 複数 repo で共有したいルールやスキルを、専用 repo で一元管理する運用を team-info 向けに整える。
- 同期はまず手動実行を基本にし、**team-info の `AGENTS.md` と `.agent/skills` は置き換えない**。
- 共有 repo は補助レイヤーとして扱い、repo 固有ルールと衝突したら current repo wins で判断する。

## upstream からの変換ポイント
- upstream 記事は `CLAUDE.md` と `.claude/skills/` を前提にしている。
- team-info では `AGENTS.md` が正本で、スキル正本は `.agent/skills/`。
- そのため、shared repo を導入するときも次の順で優先する。
  1. repo 固有の `AGENTS.md`
  2. repo 固有の `.agent/skills/`
  3. shared repo の補助ルール / 補助スキル

## 推奨の shared repo 例

```text
shared-agent-assets/
├── rules/
│   ├── session-start.md
│   └── review-rules.md
└── skills/
    ├── deploy/SKILL.md
    └── review/SKILL.md
```

## team-info 側の置き方
- shared repo の markdown ルールは、必要なら `.agent/shared-rules/` や repo 固有 docs へシンボリックリンクする。
- shared skill を runtime で使いたいときは、`.agent/skills/shared/<skill>/SKILL.md` へシンボリックリンクする。
- Claudian / Claude Code 用に vault や `~/.claude/skills/` へ配る場合も、repo 側の正本は `.agent/skills/` に置く。

## 同期コマンド

```bash
bash "$TEAM_INFO_ROOT/.agent/skills/common/team-info-setup/shared-agent-assets/scripts/sync_shared_agent_repo.sh" "/absolute/path/to/shared-agent-assets"
```

引数を省略した場合は、次の順で shared repo を探します。

1. `TEAM_INFO_SHARED_AGENT_ASSETS_ROOT`
2. `"$TEAM_INFO_ROOT/../shared-agent-assets"`
3. `"$TEAM_INFO_ROOT/../shared-rules-repo"`

そのため、repo を sibling 配置できるなら次でも動きます。

```bash
bash "$TEAM_INFO_ROOT/.agent/skills/common/team-info-setup/shared-agent-assets/scripts/sync_shared_agent_repo.sh"
```

## team-info 優先ルール
- `AGENTS.md` は shared repo へ逃がさない。補助ルールだけ shared repo 化する。
- `.agent/skills` を唯一のスキル正本として維持する。`~/.claude/skills` や vault `.claude/skills` は runtime 配布先に留める。
- Hook で実行するスクリプトは短く、`stdout` には一行の状態だけ出す。
- shared repo に未コミット差分があるときは pull しない。
- symlink 先が壊れても repo 本体で作業継続できるようにする。
- repo 共有の `SessionStart` hook に `git fetch` / `git pull` は入れない。必要なら個人ローカル設定で opt-in する。

## 向いているもの
- PR レビュー観点
- チーム共通のコミット規約
- タスク管理 / カンバン運用
- 複数 repo で同じ調査フローや継続フロー

## shared repo に置かないもの
- repo 固有のディレクトリ構造
- repo 固有の build / deploy コマンド
- repo 固有の secret 参照ルール
- `AGENTS.md` の本体

## 参考
- DevelopersIO 記事: `複数リポジトリでClaude Codeのルール・スキルを一元管理する`
- この repo で外部取り込みをするときは `repo-adapted-tool-import` を併用する
