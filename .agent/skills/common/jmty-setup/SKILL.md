---
name: jmty-setup
description: JMTY workspace の初期セットアップと状態確認を行う起点スキル。JMTY_ROOT の登録、Git hook、ローカル秘密情報、slash command adapter の確認まで扱う。
---

# JMTY セットアップスキル

## 絶対パスルール
- ユーザーにコマンドを渡すときは、固定の `/Users/...` ではなく `JMTY_ROOT` を使う。
- 初回セットアップ前で `JMTY_ROOT` がない場合だけ、現在の repo ルートの絶対パスを明示してよい。

## 目的
- `/setup` から JMTY workspace の作業場所を登録する。
- このパソコンが過去に JMTY workspace を触ったか確認する。
- `JMTY_ROOT`、Git hook、Discord webhook の状態を確認する。
- `.claude` / `.codex` / `.gemini` の slash command adapter を同期する。

## 参照ファイル
- `AGENTS.md`
- `RULES.md`
- `マニュアル/まずはこちらをお読みください.md`
- `.agent/skills/common/scripts/jmty_runtime.py`
- `scripts/sync_cross_cli_commands.py`

## 必須フロー
1. リポジトリルートで `python3 .agent/skills/common/scripts/jmty_runtime.py worked-before-status` を実行して状態を見る。
2. `JMTY_ROOT` が未設定または別 repo を指している場合は、次を実行して登録し直す。

```bash
python3 .agent/skills/common/scripts/jmty_runtime.py setup-local-machine --repo-root .
```

3. コマンド adapter を同期する。

```bash
python3 scripts/sync_cross_cli_commands.py
```

4. `config/discord-jmty-webhook.json` は秘密情報なので Git に含めない。共有する場合は `config/discord-jmty-webhook.example.json` だけを使う。
5. 最後に `git status --short` を確認し、セットアップで変わったファイルを報告する。

## ユーザー向け確認コマンド

```bash
echo "$JMTY_ROOT"
python3 "$JMTY_ROOT/.agent/skills/common/scripts/jmty_runtime.py" owner-status
python3 "$JMTY_ROOT/scripts/sync_cross_cli_commands.py"
```

## 承認ルール
- 状態確認とこの repo 内の adapter 同期はそのまま実行してよい。
- 外部ツールのインストール、認証、秘密情報の保存は、実行前にユーザーへ確認する。
