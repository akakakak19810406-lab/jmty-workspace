---
name: repo-adapted-tool-import
description: 外部リポジトリ、CLI、AI skill、MCP サーバーなどを team-info に取り込むための起点スキル。現在の repo の運用を優先し、パス、設定、資格情報、OpenClaw 連携、常駐プロセス方針の衝突を整理して、安全なラッパーと保存先へ変換して導入する。
---

# repo-adapted-tool-import スキル

## 目的
- 外部ツールや外部リポジトリを、そのまま入れずに `team-info` 向けへ作り替えて導入する。
- 衝突しそうな場所は、原則として **現在の repo のルールを優先** して書き換える。
- 次回以降も同じ形で導入できるよう、repo 内に正本を残す。

## 使う場面
- GitHub の外部 repo を `team-info` に取り込みたい。
- 外部 CLI や MCP を入れたいが、設定先や保存先を repo ルールに合わせたい。
- OpenClaw / Claude / agents 用 skill を、repo 正本から同期したい。
- upstream の install 手順が `~/.xxx` や `/usr/local` を前提にしていて、そのままでは運用がぶつかる。

## repo 優先ルール
- `.agent/skills` を正本にする。外部 skill ディレクトリを正本にしない。
- upstream の README や `CLAUDE.md` より、この repo の `AGENTS.md` と既存運用を優先する。
- 既存の Git フロー、Docker 運用、秘密情報の扱い、絶対パス案内を崩さない。
- 迷ったら「current repo wins」で判断する。

## 標準の置き方

### repo に置くもの
- `.agent/skills/common/<tool-name>/SKILL.md`
- `.agent/skills/common/<tool-name>/scripts/team_info_<tool>.py`
- `.agent/skills/common/<tool-name>/scripts/install_team_info_<tool>.py`
- 必要なら `.agent/skills/common/<tool-name>/vendor/...`
- upstream をコピーしたなら `UPSTREAM_LICENSE` や元 metadata
- `skill-finder` への索引追加
- よく使うなら `AGENTS.md` の slash command 追加

### ローカルに置くもの
- 永続データ: `~/.config/team-info/<tool-name>/`
- Python 仮想環境: `~/.config/team-info/<tool-name>/venv/`
- npm グローバル相当: `~/.config/team-info/<tool-name>/npm-global/`
- cookie、token、API key、ログイン情報
- upstream が生成する作業ファイルや tool clone

### repo に置いてよいもの
- チームで共有する軽い設定
- 例: `config/<tool>.json`
- 条件: 秘密情報を含まず、チームで同じ値を使う意味があること

## 導入フロー
1. `.dev-mode` を確認し、新規ファイル作成の承認を取る。
2. 必要なら `worked-before-status` でその PC が既知か確認する。
3. upstream repo / docs / install 手順を読み、次の衝突を洗い出す。
4. repo 正本、ローカル保存先、ラッパー方式を先に決める。
5. upstream をそのまま使わず、repo 側に adapter を作る。
6. `skill-finder` と必要な導線を更新する。
7. インストール後に `doctor` / `--help` / `openclaw skills list` などで動作確認する。
8. 有効になった範囲と未設定の残りを分けて報告する。

## 先に確認する衝突ポイント
- skill の正本がどこにある前提か
- config / cache / cookies / logs の保存先
- `npm install -g`、`brew install`、`pipx`、`/usr/local` 書き込みの有無
- MCP の設定ファイル、port、常駐サーバー、watch / cron
- Docker を常時起動する前提かどうか
- Git の branch / PR / main push ルール
- repo 内に secrets を置く設計になっていないか
- 出力ファイルを workspace 直下へ散らさないか

## 実装ルール
- まず wrapper を作り、ユーザーには wrapper 経由のコマンドを見せる。
- Python 系は `~/.config/team-info/<tool-name>/venv/` を使い、必要なら wrapper で re-exec する。
- npm 系は `NPM_CONFIG_PREFIX=~/.config/team-info/<tool-name>/npm-global` を使う。
- upstream が `~/.agent-reach` のような固定パスを持つなら、helper を作って team-info 向けパスへ寄せる。
- upstream の skill を使う場合も、repo の `SKILL.md` を source にして OpenClaw 側へ同期する。
- 外部ツールの自動導入順が不自然なら、repo 側で順序を直して再現性を上げる。
- 既存 repo を upstream に合わせて変えるのではなく、upstream を repo に合わせて包む。

## 検証の最低ライン
- install スクリプトが最後まで完走する
- wrapper 経由で `doctor` または同等の自己診断が動く
- 必要な CLI が local prefix / venv から見える
- OpenClaw 連携がある場合は `openclaw skills list` で確認する
- repo に秘密情報が入っていない
- 未設定のチャネルや追加で必要な API key を切り分けて説明できる

## 完了条件
- repo 内に再利用できる skill と wrapper がある
- upstream の衝突点が team-info 優先で吸収されている
- チーム共有すべき設定だけが repo に残っている
- ユーザーが次回同種の依頼をしたとき、このスキルを起点に同じ流れで進められる

## 参考例
- `Agent-Reach` の取り込み例は `.agent/skills/common/agent-reach/` を見る
- project 共有の MCP 設定例は `config/mcporter.json` を見る
