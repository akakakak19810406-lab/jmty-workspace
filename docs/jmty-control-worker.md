# JMTY Control Worker

Vercel 上の `apps/jmty-control` がジョブキューを持ち、この Mac の `scripts/jmty_worker.py` が定期的に取りに行く構成です。

## Local Test

1. Vercel 側アプリを起動します。

```bash
cd apps/jmty-control
npm install
npm run dev
```

2. 別ターミナルで Mac ワーカーを1回だけ実行します。

```bash
python3 scripts/jmty_worker.py --once --base-url http://127.0.0.1:3000
```

3. 管理画面で `test` ジョブを作ると、ワーカーが拾って `done` に更新します。

## Production Env

Mac 側の `.env` には次を置きます。

```text
JMTY_CONTROL_BASE_URL=<Vercelで公開したJMTY ControlのURL>
JMTY_WORKER_TOKEN=<Vercel側と同じ長いランダム文字列>
JMTY_WORKER_INTERVAL=60
JMTY_WORKER_ID=<このMacを識別する名前>
```

Vercel 側には次を設定します。

```text
JMTY_WORKER_TOKEN=<Mac側と同じ長いランダム文字列>
NEON_DATABASE_URL=<Neon Postgresの接続URL>
JMTY_CONTROL_PUBLIC_URL=<Vercelで公開したJMTY ControlのURL>
```

`NEON_DATABASE_URL` は `DATABASE_URL` または `POSTGRES_URL` でも動作します。

例:

```text
JMTY_CONTROL_BASE_URL=https://jmty-control-example.vercel.app
JMTY_WORKER_TOKEN=replace-with-a-long-random-secret
JMTY_WORKER_INTERVAL=60
JMTY_WORKER_ID=main-mac
```

## Current Scope

現在の実装は疎通確認用です。`test` は実行され、`generate_image` などの実ジョブはプレースホルダーとして `done` になります。次の段階で既存の `scripts/jmty_gui.py` と週次処理スクリプトの実行関数を接続します。
