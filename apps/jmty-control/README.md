# JMTY Control

Vercel 側に置く管理画面とジョブキューです。Mac 側の `scripts/jmty_worker.py` がこの API を毎分ポーリングし、ローカルの Codex / gws / ファイル操作を実行します。

## Local Dev

```bash
cd apps/jmty-control
npm install
npm run dev
```

ローカルでは `/tmp/jmty-control-store` にJSONファイルとして保存します。

## Vercel Env

本番では次の環境変数を設定します。

```text
JMTY_WORKER_TOKEN=<MacワーカーとVercelで共通にする長いランダム文字列>
NEON_DATABASE_URL=<Neon Postgresの接続URL>
```

`NEON_DATABASE_URL` は `team-info` と同じ変数名です。一般的な `DATABASE_URL` または `POSTGRES_URL` でも動作します。

起動時または初回保存時に、Neon側へ `jmty_control_store` テーブルを自動作成します。

`NEON_DATABASE_URL` / `DATABASE_URL` / `POSTGRES_URL` がない場合は、互換用に `UPSTASH_REDIS_REST_*` を使います。それもない場合、Vercel の一時ファイルに保存しようとするため本番運用には向きません。

## Create First Admin

初期管理者はチャットにメールアドレスやパスワードを書かず、ローカルのターミナルからVercel本番DBへ直接登録します。

`<...>` の部分だけ自分の値に置き換えて実行してください。

```bash
cd /Users/deguchishouma/Desktop/jmty/jmty-workspace/apps/jmty-control

ADMIN_EMAIL="<管理者のメールアドレス>" \
ADMIN_ACCOUNT_NAME="<管理者のアカウント名>" \
ADMIN_PASSWORD="<管理者のログインパスワード>" \
NEON_DATABASE_URL="<Neon Postgresの接続URL>" \
npm run admin:create
```

入力時に画面へパスワードを表示したくない場合はこちらを使います。

```bash
cd /Users/deguchishouma/Desktop/jmty/jmty-workspace/apps/jmty-control

read -r -p "Admin email: " ADMIN_EMAIL
read -r -p "Admin account name: " ADMIN_ACCOUNT_NAME
read -r -s -p "Admin password: " ADMIN_PASSWORD
echo

NEON_DATABASE_URL="<Neon Postgresの接続URL>" \
ADMIN_EMAIL="$ADMIN_EMAIL" \
ADMIN_ACCOUNT_NAME="$ADMIN_ACCOUNT_NAME" \
ADMIN_PASSWORD="$ADMIN_PASSWORD" \
npm run admin:create

unset ADMIN_PASSWORD
```

すでに同じメールアドレスのユーザーがいる場合は、そのユーザーを管理者へ更新します。パスワードは平文では保存せず、PBKDF2ハッシュとして保存します。
