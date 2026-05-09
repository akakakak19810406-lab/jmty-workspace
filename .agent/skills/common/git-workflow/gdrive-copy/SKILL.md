---
name: gdrive-copy
description: ローカルのファイルやフォルダを rclone 経由で Google Drive の team-info フォルダにアップロードするスキル。Google Drive for Desktop のローカルパスに依存せず、チーム全員が共通コマンドで実行できる。
---

# Google Drive アップロードスキル（rclone 版）

## 目的

`マイドライブ/team-info`（フォルダID: `1QKaUP9fvA46mINkpSR1b2wqrIBE6By0t`）へ
ローカルのファイル・フォルダを **rclone** 経由でアップロードする。

Google Drive for Desktop のローカルマウントパスには依存しない。

---

## 【初回のみ】セットアップ手順

> **初回だけ** 以下を実行してください。2回目以降は不要です。

### ステップ 1：rclone を確認する

`/setup` を済ませていれば、通常はこのコマンドが通ります。

**Mac:**
```bash
brew install rclone
```

**Windows（winget）:**
```powershell
winget install Rclone.Rclone
```

**Windows（手動）:**
https://rclone.org/downloads/ から `.exe` をダウンロードし、PATHの通った場所に置く。

インストール確認：
```bash
rclone version
```

---

### ステップ 2：Google Drive の remote を設定する

```bash
rclone config
```

対話プロンプトで以下のように進めてください：

```
n  → 新規リモートを作る
name: gdrive           ← 必ず "gdrive" にする
Storage: drive         ← Google Drive を選ぶ（番号 or "drive" と入力）
client_id: （空のまま Enter）
client_secret: （空のまま Enter）
scope: 1               ← drive（フルアクセス）を選ぶ
root_folder_id: （空のまま Enter）
service_account_file: （空のまま Enter）
Edit advanced config? n
Use auto config? y     ← ブラウザが開く
```

ブラウザで Google アカウントにログインし、アクセスを許可してください。

> **注意:** アップロード先フォルダ（フォルダID: `1QKaUP9fvA46mINkpSR1b2wqrIBE6By0t`）へのアクセス権限（書き込み可）が付与されたアカウントでログインしてください。

---

### ステップ 3：接続確認

```bash
rclone lsd gdrive:
```

マイドライブのフォルダ一覧が表示されれば設定完了です。

---

## 日常運用：実行コマンド

### コンテキストからコピー対象が明確な場合（推奨）

スキルの流れや会話の中でコピー元・コピー先がわかっている場合は、引数付きで即実行できるコマンドをユーザーに渡すこと。

```bash
python3 "$TEAM_INFO_ROOT/.agent/skills/common/git-workflow/gdrive-copy/scripts/gdrive_copy.py" \
  --src "[コピー元の絶対パス]" \
  --dest "[team-info直下のコピー先サブパス]"
```

**例（アコリエル動画）:**
```bash
python3 "$TEAM_INFO_ROOT/.agent/skills/common/git-workflow/gdrive-copy/scripts/gdrive_copy.py" \
  --src "$TEAM_INFO_ROOT/outputs/acoriel/renders/Hana.mp4" \
  --dest "outputs/アコリエル/"
```

引数を渡した場合は確認なしで即アップロードし、完了後に Google Drive の URL を表示する。

---

### インタラクティブモード（コピー対象が不明な場合）

```bash
python3 "$TEAM_INFO_ROOT/.agent/skills/common/git-workflow/gdrive-copy/scripts/gdrive_copy.py"
```

対話形式でコピー元・コピー先サブフォルダを選んでアップロードします。

---

## 動作フロー（インタラクティブモード）

1. **事前チェック**
   - `TEAM_INFO_ROOT` 環境変数の確認
   - `rclone` コマンドの存在確認
   - `gdrive` リモートの設定確認

2. **コピーモード選択**
   - `1` フォルダごとアップロード
   - `2` ファイル/フォルダを番号で選んでアップロード

3. **コピー元パス入力**
   - 絶対パス、または `TEAM_INFO_ROOT` からの相対パスで指定
   - 例: `outputs/acoriel/renders`、`Remotion/my-video/out`

4. **ファイル選択**（モード2のみ）
   - 番号（複数はカンマ区切り）または `all` で全選択

5. **コピー先サブフォルダ指定**
   - `team-info` 直下なら Enter、サブフォルダ名を入力して掘り下げも可能

6. **確認後に rclone で実行** → macOS 通知で完了を知らせる

---

## スキル発動トリガー

ユーザーが以下のような発言をしたとき:
- 「Google Drive にアップロードして」
- 「team-info の Drive フォルダに送って」
- 「gdrive に上げて」
- 「Drive にコピーして」
- `/gdrive`

---

## エラー対処

| エラーメッセージ | 原因 | 対処 |
|---|---|---|
| `TEAM_INFO_ROOT が未設定です` | 環境変数が設定されていない | `setup-local-machine` を実行する |
| `rclone が見つかりません` | rclone 未インストール | `brew install rclone`（Mac）または winget でインストール |
| `gdrive リモートが未設定です` | rclone config 未実施 | `rclone config` で gdrive を追加する |
| `対象パスが見つかりません` | コピー元パスが存在しない | パスを再確認する |
| `403 Forbidden` | Drive への書き込み権限がない | フォルダのアクセス権を確認し、権限付きアカウントで `rclone config reconnect gdrive:` を実行 |
| `Failed to copy` | ネットワーク断や容量不足など | `rclone copy ... -v` で詳細ログを確認する |
